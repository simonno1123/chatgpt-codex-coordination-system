"""Read-only Production Host / Control Producer contract (offline materialization).

There is deliberately no production resolver, trusted-clock provisioning or
source registration here. The fixed production factory fails closed. Independently
established sources may use this contract in a separately qualified integrating
host; JSON, digests, PID/UID and descriptor possession never establish that trust.
No issuer, governance writer, credential reader, network client or retry exists.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import ctypes
import hashlib
import json
import os
import re
import select
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SELF = ROOT / "scripts/acos-v2-production-host-control-producer.py"
PYTHON = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13"
PYTHON_APP = "/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python"
HOST_SCHEMA = "acos-v2-production-host-observation/1"
CONTROL_SCHEMA = "acos-v2-production-control-observation/1"
QUERY_SCHEMA = "acos-v2-production-host-query/1"
HOST_MAX, CONTROL_MAX, MAX_DEPTH = 262144, 8192, 8
FRAME_TIMEOUT, HEARTBEAT_NS, LEASE_NS = 0.2, 100_000_000, 800_000_000
PHASES = {"SETUP", "MUTATION", "READ_RECONCILIATION", "DISPOSAL"}
SLOTS = ("authority", "grant", "capability_state", "clock", "baseline", "target",
         "revocation", "credential_reference", "caller", "runtime_reference",
         "network_handoff", "governance_projection")
SOURCE_CLASSES = dict(zip(SLOTS, (
    "CORE_AUTHORITY", "D04_GRANT", "D04_STATE", "D04_TRUSTED_CLOCK",
    "WORKFLOW_BASELINE", "D09_TARGET", "D09_REVOCATION", "CREDENTIAL_METADATA",
    "AUTHENTICATED_CALLER", "RUNTIME_QUALIFICATION", "NETWORK_HANDOFF",
    "CORE_GOVERNANCE_PROJECTION")))
QUERY_KEYS = {"schema", "kind", "run_id", "process_incarnation",
              "runtime_binding_digest", "baseline", "phase", "profile_digest", "request_nonce"}
HOST_KEYS = {"schema", "kind", "producer_reference", "producer_identity",
    "producer_implementation_digest", "producer_runtime_digest", "host_qualification_reference",
    "source_catalog_digest", "observation_epoch", "observation_sequence", "observed_at",
    "expires_at", "run_id", "process_incarnation", "runtime_binding_digest",
    "baseline", "phase", "request_nonce", "observations", "package_digest"}
SLOT_KEYS = {"source_class", "source_reference", "reader_implementation_digest",
    "source_identity_reference", "source_generation", "source_version", "sampled_at",
    "expires_at", "value_digest", "value"}
CONTROL_KEYS = {"schema", "kind", "producer_reference", "producer_implementation_digest",
    "host_qualification_reference", "observation_epoch", "sequence", "run_id", "process_id",
    "process_incarnation", "parent_id", "parent_chain_digest", "runtime_binding_digest",
    "baseline", "phase", "network_generation", "lifecycle_generation", "sleep_wake_generation",
    "foreground", "alive", "terminal_open", "restart_policy", "clock_domain_reference",
    "sampled_continuous_ns", "expires_continuous_ns", "lease_until_monotonic_ns",
    "failure_class", "package_digest"}
IDENTITY_KEYS = {"process_id", "uid", "process_incarnation", "boot_identity",
                 "parent_id", "parent_chain_digest", "binary_path", "binary_digest"}
ENVELOPE_KEYS = {"capability_id", "capability_class", "operation", "target",
                "execution_identity", "authority_reference", "not_after", "consumption_policy",
                "cancellation_binding"}
STATE_KEYS = {"capability_id", "execution_identity", "authority_reference",
              "cancellation_binding", "runtime_state", "consumed"}
EXECUTION_KEYS = {"project_id", "stage_id", "task_id", "authorization_id",
                  "executor_role", "execution_attempt_id", "baseline_revision"}
AUTHORITY_KEYS = {"authorization_id", "content_digest"}
TARGET_KEYS = {"binding_id", "generation", "organization", "project", "conversation_id",
               "provenance_digest", "credential_ref", "credential_version", "provider", "origin",
               "effect", "content_profile", "nonproduction_disposable_exclusive", "revocation_at_binding"}


class Unavailable(Exception):
    """Fixed redacted reason only, including exceptions from external readers."""
    def __init__(self, reason="SOURCE_UNAVAILABLE"):
        self.reason = reason
        super().__init__(reason)


def fail(reason):
    raise Unavailable(reason) from None


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except Exception:
        fail("ENCODING")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def _keys(value, keys, reason="SCHEMA"):
    if type(value) is not dict or set(value) != keys:
        fail(reason)


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum or value > 2**63 - 1:
        fail("INTEGER")
    return value


def _identifier(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        fail("IDENTIFIER")
    return value


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        fail("DIGEST")
    return value


def _instant(value):
    try:
        if type(value) is not str:
            fail("CLOCK")
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            fail("CLOCK")
        return result
    except Unavailable:
        raise
    except Exception:
        fail("CLOCK")


def _tree(value, depth=0):
    if depth > MAX_DEPTH:
        fail("DEPTH")
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str or len(key) > 128:
                fail("KEY")
            if key.lower() in {"material", "secret", "authorization", "cookie", "environment"}:
                fail("SECRET_FIELD")
            _tree(child, depth + 1)
    elif type(value) is list:
        for child in value:
            _tree(child, depth + 1)
    elif type(value) is str:
        if len(value) > 8192 or value.startswith(("sk-", "fixture-only-")) or "Bearer " in value:
            fail("SECRET_VALUE")
    elif type(value) is int:
        _integer(value)
    elif value is not None and type(value) is not bool:
        # Protocol counters/timestamps are integers; no floating/NaN coercion.
        fail("VALUE_TYPE")


def strict_json(raw, maximum=HOST_MAX):
    if type(raw) is not bytes or not 1 <= len(raw) <= maximum:
        fail("FRAME_SIZE")
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                fail("DUPLICATE_KEY")
            out[key] = value
        return out
    try:
        result = json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                            parse_constant=lambda _: fail("CONSTANT"))
        _tree(result)
        return result
    except Unavailable:
        raise
    except Exception:
        fail("JSON")


def _channel_io(fd, size, *, data=None, deadline=None):
    deadline = time.monotonic() + FRAME_TIMEOUT if deadline is None else deadline
    result, offset = bytearray(), 0
    try:
        while offset < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                fail("FRAME_TIMEOUT")
            read, write, _ = select.select([fd] if data is None else [],
                                          [] if data is None else [fd], [], remaining)
            if not (read or write):
                fail("FRAME_TIMEOUT")
            # Never a blocking write of a large frame; chunks fit local pipe/socket
            # capacity after readiness, with one bounded deadline.
            amount = min(size - offset, 1024)
            if data is None:
                chunk = os.read(fd, amount)
                if not chunk:
                    fail("CHANNEL_EOF")
                result.extend(chunk)
                offset += len(chunk)
            else:
                sent = os.write(fd, data[offset:offset + amount])
                if sent <= 0:
                    fail("CHANNEL_EOF")
                offset += sent
        return bytes(result)
    except Unavailable:
        raise
    except Exception:
        fail("CHANNEL_IO")


def read_frame(fd, maximum):
    deadline = time.monotonic() + FRAME_TIMEOUT
    size = int.from_bytes(_channel_io(fd, 4, deadline=deadline), "big")
    if not 1 <= size <= maximum:
        fail("FRAME_SIZE")
    return _channel_io(fd, size, deadline=deadline)


def write_frame(fd, value, maximum):
    raw = canonical(value)
    if not 1 <= len(raw) <= maximum:
        fail("FRAME_SIZE")
    framed = len(raw).to_bytes(4, "big") + raw
    _channel_io(fd, len(framed), data=framed)


def seal(value):
    return {**value, "package_digest": digest(value)}


def unseal(value, keys):
    _keys(value, keys)
    _hash(value["package_digest"])
    if value["package_digest"] != digest({k: v for k, v in value.items() if k != "package_digest"}):
        fail("PACKAGE_DIGEST")


def validate_query(query):
    _keys(query, QUERY_KEYS)
    if query["schema"] != QUERY_SCHEMA or query["kind"] != "OBSERVE_BOUND_FACTS":
        fail("QUERY_OPERATION")
    for key in ("run_id", "process_incarnation", "request_nonce"):
        _identifier(query[key])
    for key in ("runtime_binding_digest", "profile_digest"):
        _hash(query[key])
    if (query["phase"] not in PHASES or type(query["baseline"]) is not str
            or not re.fullmatch(r"[0-9a-f]{40}", query["baseline"])):
        fail("QUERY_SCOPE")
    _tree(query)


@dataclass(frozen=True)
class Pin:
    path: str
    sha256: str
    size: int
    device: int
    inode: int

    def verify(self, exact):
        path = Path(self.path)
        if (self.path != str(exact) or path.is_symlink() or path.resolve() != path
                or type(self.sha256) is not str or not re.fullmatch("[0-9a-f]{64}", self.sha256)):
            fail("IMPLEMENTATION_PATH")
        try:
            stat = path.stat()
            if (stat.st_size, stat.st_dev, stat.st_ino) != (self.size, self.device, self.inode):
                fail("IMPLEMENTATION_IDENTITY")
            if hashlib.sha256(path.read_bytes()).hexdigest() != self.sha256:
                fail("IMPLEMENTATION_DRIFT")
        except Unavailable:
            raise
        except Exception:
            fail("IMPLEMENTATION_UNAVAILABLE")


@dataclass(frozen=True)
class SourceReader:
    source_class: str
    reference: str
    implementation_digest: str
    identity_reference: str
    generation: int
    sample: object
    version: object

    def metadata(self):
        _identifier(self.reference)
        _identifier(self.identity_reference)
        _hash(self.implementation_digest)
        _integer(self.generation, 1)
        if not callable(self.sample) or not callable(self.version):
            fail("READ_ONLY_SOURCE")
        return {"source_class": self.source_class, "source_reference": self.reference,
                "reader_implementation_digest": self.implementation_digest,
                "source_identity_reference": self.identity_reference,
                "source_generation": self.generation}


@dataclass(frozen=True)
class Registration:
    """Outside-payload observation binding; evidence, never issuer authority."""
    role: str
    reference: str
    qualification_reference: str
    epoch: str
    runtime_digest: str
    baseline: str
    run_id: str
    process_incarnation: str
    phase: str
    implementation: Pin
    interpreter: Pin
    producer_runtime_digest: str
    identity: dict
    channel_role: str
    custody_reference: str
    clock_domain_reference: str
    sleep_wake_generation: int

    def verify(self, context):
        expected_channel = {"HOST": "FD4_HOST_OBSERVATION", "CONTROL": "FD6_LIFECYCLE"}
        if (self.role not in expected_channel or self.channel_role != expected_channel[self.role]
                or type(self.identity) is not dict or set(self.identity) != IDENTITY_KEYS):
            fail("PRODUCER_ROLE")
        for field in ("reference", "qualification_reference", "epoch", "custody_reference",
                      "clock_domain_reference"):
            _identifier(getattr(self, field))
        for field in ("runtime_digest", "producer_runtime_digest"):
            _hash(getattr(self, field))
        _integer(self.sleep_wake_generation, 1)
        self.implementation.verify(SELF)
        self.interpreter.verify(PYTHON)
        if (self.run_id, self.process_incarnation, self.runtime_digest, self.baseline, self.phase) != (
                context["run_id"], context["process_incarnation"], context["runtime_binding_digest"],
                context["baseline"], context["phase"]):
            fail("PRODUCER_SCOPE")
        _integer(self.identity["process_id"], 1)
        _integer(self.identity["uid"])
        _integer(self.identity["parent_id"], 1)
        _identifier(self.identity["process_incarnation"])
        _identifier(self.identity["boot_identity"])
        _hash(self.identity["parent_chain_digest"])
        _hash(self.identity["binary_digest"])
        if self.identity["binary_path"] != PYTHON_APP:
            fail("PRODUCER_BINARY")
        # Worker/launcher cannot attest itself as its own control producer.
        if self.identity["process_id"] == os.getpid():
            fail("SELF_CONTROL")


class ExternalSources:
    """Existing host readers + independent provenance verifier, not a registry.

    Constructed only by an independently qualified integrating host (or an
    explicit offline test harness). No FD3/FD4 deserializer builds this object.
    Qualification callbacks must resolve registered implementation, OS identity,
    channel custody, clocks and source pins outside the candidate payload.
    """
    def __init__(self, host, control, readers, provenance_reader, kernel_reader,
                 governance_clock, continuous_clock, monotonic_clock,
                 network_reader, control_reader):
        if type(host) is not Registration or type(control) is not Registration:
            fail("EXTERNAL_BINDING")
        if host.role != "HOST" or control.role != "CONTROL":
            fail("SEPARATE_ROLES")
        if host.channel_role == control.channel_role or host.epoch == control.epoch:
            fail("SEPARATE_CHANNEL_GENERATION")
        if type(readers) is not dict or set(readers) != set(SLOTS):
            fail("SOURCE_CATALOG")
        for slot, reader in readers.items():
            if type(reader) is not SourceReader or reader.source_class != SOURCE_CLASSES[slot]:
                fail("SOURCE_CLASS")
            reader.metadata()
        if (type(control_reader) is not SourceReader
                or control_reader.source_class != "CONTROL_LIFECYCLE"):
            fail("CONTROL_READER_PROVENANCE")
        control_reader.metadata()
        if any(control_reader.reference == r.reference or
               control_reader.identity_reference == r.identity_reference for r in readers.values()):
            fail("SEPARATE_READER_PROVENANCE")
        if not all(callable(x) for x in (provenance_reader, kernel_reader, governance_clock,
                continuous_clock, monotonic_clock, network_reader)):
            fail("EXTERNAL_READERS")
        self.host, self.control, self.readers = host, control, dict(readers)
        self._provenance, self._kernel = provenance_reader, kernel_reader
        self.governance_clock, self.continuous_clock = governance_clock, continuous_clock
        self.monotonic_clock, self.network_reader = monotonic_clock, network_reader
        self.control_reader = control_reader

    @property
    def catalog_digest(self):
        return digest({slot: reader.metadata() for slot, reader in self.readers.items()})

    @property
    def control_catalog_digest(self):
        return digest(self.control_reader.metadata())

    def qualify(self, role, context, channel_fd):
        if role not in {"HOST", "CONTROL"}:
            fail("PRODUCER_ROLE")
        registration = self.host if role == "HOST" else self.control
        registration.verify(context)
        try:
            # The verifier receives the expected binding; the observation never
            # supplies its own initial trust root or qualified boolean.
            proof = self._provenance(role, registration, context, channel_fd)
            _keys(proof, {"registration_reference", "qualification_reference", "channel_role",
                          "custody_reference", "catalog_digest", "runtime_digest"})
            expected = {"registration_reference": registration.reference,
                        "qualification_reference": registration.qualification_reference,
                        "channel_role": registration.channel_role,
                        "custody_reference": registration.custody_reference,
                        "catalog_digest": self.catalog_digest if role == "HOST" else self.control_catalog_digest,
                        "runtime_digest": registration.runtime_digest}
            identity = self._kernel(registration, channel_fd)
            _keys(identity, IDENTITY_KEYS)
            for field in ("process_id", "uid", "parent_id"):
                _integer(identity[field], 0 if field == "uid" else 1)
            if proof != expected or identity != registration.identity:
                fail("INDEPENDENT_PROVENANCE")
            now = self.governance_clock()
            if type(now) is not datetime or now.tzinfo is None:
                fail("TRUSTED_CLOCK_UNAVAILABLE")
            _integer(self.continuous_clock(), 1)
            _integer(self.monotonic_clock(), 1)
            return True
        except Unavailable:
            raise
        except Exception:
            fail("PROVENANCE_UNAVAILABLE")


def _identity_values(value):
    _keys(value, EXECUTION_KEYS)
    for key, item in value.items():
        if key == "baseline_revision":
            if type(item) is not str or not re.fullmatch(r"[0-9a-f]{40}", item):
                fail("EXECUTION_BASELINE")
        else:
            _identifier(item)


def _authority_values(value):
    _keys(value, AUTHORITY_KEYS)
    _identifier(value["authorization_id"])
    _hash(value["content_digest"])


def validate_value(slot, value):
    """Finite typed observations; no arbitrary data, URL, SQL or credential."""
    if slot == "authority":
        _keys(value, {"authority_reference", "execution_identity", "selector", "authorized"})
        _authority_values(value["authority_reference"])
        _identity_values(value["execution_identity"])
        if type(value["selector"]) is not str or not value["selector"].startswith("remote-context-live/1:"):
            fail("AUTHORITY_SELECTOR")
        _hash(value["selector"].split("remote-context-live/1:", 1)[1])
        if type(value["authorized"]) is not bool:
            fail("AUTHORITY_VALUE")
    elif slot == "grant":
        _keys(value, ENVELOPE_KEYS)
        _authority_values(value["authority_reference"])
        _identity_values(value["execution_identity"])
        _instant(value["not_after"])
        for name in ("capability_id", "capability_class", "operation", "cancellation_binding"):
            _identifier(value[name])
        if value["consumption_policy"] not in {"SINGLE_USE", "REUSABLE"}:
            fail("CAPABILITY_POLICY")
        if type(value["target"]) is not str or not value["target"].startswith("remote-context-live/1:"):
            fail("CAPABILITY_SELECTOR")
    elif slot == "capability_state":
        _keys(value, STATE_KEYS)
        _identifier(value["capability_id"])
        _identifier(value["cancellation_binding"])
        _authority_values(value["authority_reference"])
        _identity_values(value["execution_identity"])
        if type(value["consumed"]) is not bool or value["runtime_state"] not in {"ACTIVE", "INACTIVE", "REVOKED", "CANCELLED"}:
            fail("CAPABILITY_STATE")
    elif slot == "clock":
        _keys(value, {"trusted_now", "clock_reference", "certain"})
        _instant(value["trusted_now"])
        _identifier(value["clock_reference"])
        if value["certain"] is not True:
            fail("TRUSTED_CLOCK_UNCERTAIN")
    elif slot == "baseline":
        _keys(value, {"baseline"})
        if type(value["baseline"]) is not str or not re.fullmatch(r"[0-9a-f]{40}", value["baseline"]):
            fail("BASELINE")
    elif slot == "target":
        if value == {"status": "NOT_APPLICABLE"}:
            return
        _keys(value, TARGET_KEYS)
        for key in ("binding_id", "organization", "project", "conversation_id", "credential_ref"):
            _identifier(value[key])
        _integer(value["generation"], 1)
        _integer(value["credential_version"], 1)
        _hash(value["provenance_digest"])
        if (value["provider"] != "OPENAI" or value["origin"] != "https://api.openai.com"
                or value["effect"] != "REMOTE_CONTEXT_MUTATION" or value["content_profile"] != "ONE_USER_INPUT_TEXT"
                or value["nonproduction_disposable_exclusive"] is not True or value["revocation_at_binding"] != "ACTIVE"):
            fail("TARGET_PROFILE")
    elif slot == "revocation":
        _keys(value, {"status", "binding_digest"})
        if value["status"] not in {"ACTIVE", "REVOKED", "UNKNOWN", "NOT_APPLICABLE"}:
            fail("REVOCATION")
        if value["status"] == "NOT_APPLICABLE":
            if value["binding_digest"] != "UNBOUND":
                fail("REVOCATION_SCOPE")
        else:
            _hash(value["binding_digest"])
    elif slot == "credential_reference":
        _keys(value, {"reference", "version", "organization", "project"})
        for key in ("reference", "organization", "project"):
            _identifier(value[key])
        _integer(value["version"], 1)
    elif slot == "caller":
        _keys(value, {"caller_id", "execution_identity"})
        _identifier(value["caller_id"])
        _identity_values(value["execution_identity"])
    elif slot == "runtime_reference":
        _keys(value, {"runtime_binding_digest"})
        _hash(value["runtime_binding_digest"])
    elif slot == "network_handoff":
        _keys(value, {"producer_reference", "evidence_reference", "qualification_digest"})
        _identifier(value["producer_reference"])
        _identifier(value["evidence_reference"])
        _hash(value["qualification_digest"])
    elif slot == "governance_projection":
        _keys(value, {"authority_effect", "execution_admission", "journal_generation"})
        if value["authority_effect"] != "NONE" or value["execution_admission"] != "NONE":
            fail("GOVERNANCE_EFFECT")
        _integer(value["journal_generation"], 1)
    else:
        fail("SOURCE_CLASS")
    _tree(value)


class HostObservationProducer:
    def __init__(self, sources, context, channel_fd=4):
        if type(sources) is not ExternalSources:
            fail("EXTERNAL_BINDING")
        self.sources, self.context, self.fd = sources, dict(context), channel_fd
        self.sequence, self.nonces, self.invalid = 0, set(), False

    def observe(self, query):
        try:
            if self.invalid:
                fail("HOST_TERMINAL")
            validate_query(query)
            if any(query[k] != self.context[k] for k in QUERY_KEYS - {"schema", "kind", "request_nonce"}):
                fail("QUERY_CONTEXT")
            if query["request_nonce"] in self.nonces:
                fail("QUERY_REPLAY")
            self.sources.qualify("HOST", self.context, self.fd)
            self.nonces.add(query["request_nonce"])
            versions = {k: _integer(r.version(), 1) for k, r in self.sources.readers.items()}
            now = self.sources.governance_clock()
            observations = {}
            for slot, reader in self.sources.readers.items():
                value = reader.sample()
                validate_value(slot, value)
                observations[slot] = {**reader.metadata(), "source_version": versions[slot],
                    "sampled_at": now.isoformat(),
                    "expires_at": (now + timedelta(seconds=0.8)).isoformat(),
                    "value_digest": digest(value), "value": value}
            if {k: r.version() for k, r in self.sources.readers.items()} != versions:
                fail("SOURCE_CHANGED_DURING_SNAPSHOT")
            self.sources.qualify("HOST", self.context, self.fd)
            self.sequence += 1
            reg = self.sources.host
            return seal({"schema": HOST_SCHEMA, "kind": "HOST_OBSERVATION",
                "producer_reference": reg.reference, "producer_identity": dict(reg.identity),
                "producer_implementation_digest": "sha256:" + reg.implementation.sha256,
                "producer_runtime_digest": reg.producer_runtime_digest,
                "host_qualification_reference": reg.qualification_reference,
                "source_catalog_digest": self.sources.catalog_digest,
                "observation_epoch": reg.epoch, "observation_sequence": self.sequence,
                "observed_at": now.isoformat(), "expires_at": observations["clock"]["expires_at"],
                "run_id": reg.run_id, "process_incarnation": reg.process_incarnation,
                "runtime_binding_digest": reg.runtime_digest, "baseline": reg.baseline,
                "phase": reg.phase, "request_nonce": query["request_nonce"],
                "observations": observations})
        except Unavailable:
            self.invalid = True
            raise
        except Exception:
            self.invalid = True
            fail("HOST_SOURCE_UNAVAILABLE")

    def serve_once(self):
        try:
            query = strict_json(read_frame(self.fd, HOST_MAX))
            write_frame(self.fd, self.observe(query), HOST_MAX)
        except Unavailable:
            self.invalid = True
            raise


class HostObservationClient:
    def __init__(self, sources, context, channel_fd=4):
        if type(sources) is not ExternalSources:
            fail("EXTERNAL_BINDING")
        self.sources, self.context, self.fd = sources, dict(context), channel_fd
        self.sequence, self.nonces, self.invalid = 0, set(), False
        self._last_versions = None

    def accept(self, response, nonce):
        try:
            if self.invalid:
                fail("HOST_TERMINAL")
            self.sources.qualify("HOST", self.context, self.fd)
            _tree(response)
            unseal(response, HOST_KEYS)
            reg = self.sources.host
            _keys(response["producer_identity"], IDENTITY_KEYS)
            for field in ("process_id", "uid", "parent_id"):
                _integer(response["producer_identity"][field], 0 if field == "uid" else 1)
            expected = {"schema": HOST_SCHEMA, "kind": "HOST_OBSERVATION",
                "producer_reference": reg.reference, "producer_identity": reg.identity,
                "producer_implementation_digest": "sha256:" + reg.implementation.sha256,
                "producer_runtime_digest": reg.producer_runtime_digest,
                "host_qualification_reference": reg.qualification_reference,
                "source_catalog_digest": self.sources.catalog_digest, "observation_epoch": reg.epoch,
                "run_id": reg.run_id, "process_incarnation": reg.process_incarnation,
                "runtime_binding_digest": reg.runtime_digest, "baseline": reg.baseline,
                "phase": reg.phase, "request_nonce": nonce}
            if any(response[k] != v for k, v in expected.items()) or nonce in self.nonces:
                fail("HOST_PROVENANCE_OR_REPLAY")
            if _integer(response["observation_sequence"], 1) != self.sequence + 1:
                fail("HOST_SEQUENCE")
            now = self.sources.governance_clock()
            if not _instant(response["observed_at"]) <= now < _instant(response["expires_at"]):
                fail("HOST_EXPIRED")
            if (_instant(response["expires_at"]) - _instant(response["observed_at"])).total_seconds() > 0.8:
                fail("HOST_LEASE")
            _keys(response["observations"], set(SLOTS))
            versions = {}
            for slot, observation in response["observations"].items():
                _keys(observation, SLOT_KEYS)
                reader = self.sources.readers[slot]
                _integer(observation["source_generation"], 1)
                if any(observation[k] != v for k, v in reader.metadata().items()):
                    fail("SOURCE_PROVENANCE")
                version = _integer(observation["source_version"], 1)
                if version != reader.version():
                    fail("SOURCE_VERSION")
                versions[slot] = version
                if (observation["sampled_at"] != response["observed_at"]
                        or observation["expires_at"] != response["expires_at"]
                        or not _instant(observation["sampled_at"]) <= now < _instant(observation["expires_at"])):
                    fail("SOURCE_EXPIRED")
                validate_value(slot, observation["value"])
                if observation["value_digest"] != digest(observation["value"]):
                    fail("VALUE_DIGEST")
            clock_sample = _instant(response["observations"]["clock"]["value"]["trusted_now"])
            if not 0 <= (now - clock_sample).total_seconds() <= 0.8:
                fail("TRUSTED_CLOCK_STALE")
            if {slot: reader.version() for slot, reader in self.sources.readers.items()} != versions:
                fail("SOURCE_CHANGED_DURING_READ")
            if self._last_versions is not None and versions != self._last_versions:
                # No cross-source atomicity promise. Any generation/version drift
                # terminates this run rather than combining old/new snapshots.
                fail("CROSS_SOURCE_DRIFT")
            self.sources.qualify("HOST", self.context, self.fd)
            self.sequence, self._last_versions = response["observation_sequence"], versions
            self.nonces.add(nonce)
            return {k: v["value"] for k, v in response["observations"].items()}
        except Unavailable:
            self.invalid = True
            raise
        except Exception:
            self.invalid = True
            fail("HOST_OBSERVATION_UNAVAILABLE")

    def observe(self):
        try:
            nonce = os.urandom(16).hex()
            query = {**self.context, "schema": QUERY_SCHEMA, "kind": "OBSERVE_BOUND_FACTS",
                     "request_nonce": nonce}
            validate_query(query)
            self.sources.qualify("HOST", self.context, self.fd)
            write_frame(self.fd, query, HOST_MAX)
            response = strict_json(read_frame(self.fd, HOST_MAX))
            return self.accept(response, nonce)
        except Unavailable:
            self.invalid = True
            raise


class ControlObservationProducer:
    def __init__(self, sources, context, channel_fd=6):
        self.sources, self.context, self.fd = sources, dict(context), channel_fd
        self.sequence, self.invalid, self.last_sample = 0, False, None

    def sample(self):
        try:
            if self.invalid:
                fail("CONTROL_TERMINAL")
            self.sources.qualify("CONTROL", self.context, self.fd)
            version = _integer(self.sources.control_reader.version(), 1)
            facts = self.sources.control_reader.sample()
            if self.sources.control_reader.version() != version:
                fail("CONTROL_SOURCE_CHANGED")
            required = {"process_id", "parent_id", "parent_chain_digest", "network_generation",
                        "lifecycle_generation", "sleep_wake_generation", "foreground", "alive",
                        "terminal_open", "restart_policy"}
            _keys(facts, required)
            for field in ("process_id", "parent_id", "network_generation", "lifecycle_generation", "sleep_wake_generation"):
                _integer(facts[field], 1)
            if any(type(facts[field]) is not bool for field in ("foreground", "alive", "terminal_open")):
                fail("CONTROL_BOOLEAN")
            if facts["lifecycle_generation"] != version:
                fail("CONTROL_SOURCE_GENERATION")
            now = _integer(self.sources.continuous_clock(), 1)
            mono = _integer(self.sources.monotonic_clock(), 1)
            if self.last_sample is not None and not 0 <= now - self.last_sample <= HEARTBEAT_NS:
                fail("CONTROL_HEARTBEAT_GAP")
            self.last_sample = now
            valid = facts["foreground"] is True and facts["alive"] is True and facts["terminal_open"] is True and facts["restart_policy"] == "NONE"
            reg = self.sources.control
            self.sequence += 1
            result = seal({"schema": CONTROL_SCHEMA, "kind": "CONTINUE_VALID" if valid else "INVALIDATE",
                "producer_reference": reg.reference,
                "producer_implementation_digest": "sha256:" + reg.implementation.sha256,
                "host_qualification_reference": reg.qualification_reference,
                "observation_epoch": reg.epoch, "sequence": self.sequence,
                "run_id": reg.run_id, "process_incarnation": reg.process_incarnation,
                "runtime_binding_digest": reg.runtime_digest, "baseline": reg.baseline,
                "phase": reg.phase, **facts, "clock_domain_reference": reg.clock_domain_reference,
                "sampled_continuous_ns": now, "expires_continuous_ns": now + LEASE_NS,
                "lease_until_monotonic_ns": mono + LEASE_NS,
                "failure_class": "NONE" if valid else "LIFECYCLE_INVALID"}
            )
            self.invalid = not valid
            return result
        except Unavailable:
            self.invalid = True
            raise
        except Exception:
            self.invalid = True
            fail("CONTROL_SOURCE_UNAVAILABLE")

    def emit_once(self):
        try:
            write_frame(self.fd, self.sample(), CONTROL_MAX)
        except Unavailable:
            self.invalid = True
            raise


class ControlObservationClient:
    """Terminal invalidation, including retained FD after producer process death."""
    def __init__(self, sources, context, run, channel_fd=6):
        self.sources, self.context, self.run, self.fd = sources, dict(context), run, channel_fd
        self.sequence, self.invalid, self.last = 0, False, None

    def accept(self, package):
        try:
            if self.invalid:
                fail("CONTROL_TERMINAL")
            self.sources.qualify("CONTROL", self.context, self.fd)
            _tree(package)
            unseal(package, CONTROL_KEYS)
            reg, run = self.sources.control, self.run
            for field in ("sequence", "process_id", "parent_id", "network_generation",
                          "lifecycle_generation", "sleep_wake_generation"):
                _integer(package[field], 1)
            if any(type(package[field]) is not bool for field in ("foreground", "alive", "terminal_open")):
                fail("CONTROL_BOOLEAN")
            expected = {"schema": CONTROL_SCHEMA, "kind": "CONTINUE_VALID",
                "producer_reference": reg.reference,
                "producer_implementation_digest": "sha256:" + reg.implementation.sha256,
                "host_qualification_reference": reg.qualification_reference,
                "observation_epoch": reg.epoch, "run_id": reg.run_id,
                "process_id": run["process_id"], "process_incarnation": reg.process_incarnation,
                "parent_id": run["parent_id"], "parent_chain_digest": run["parent_chain_digest"],
                "runtime_binding_digest": reg.runtime_digest, "baseline": reg.baseline, "phase": reg.phase,
                "network_generation": run["network_generation"],
                "lifecycle_generation": run["lifecycle_generation"],
                "sleep_wake_generation": reg.sleep_wake_generation, "clock_domain_reference": reg.clock_domain_reference,
                "foreground": True, "alive": True, "terminal_open": True,
                "restart_policy": "NONE", "failure_class": "NONE"}
            if (any(package[k] != v for k, v in expected.items())
                    or self.sources.control_reader.version() != package["lifecycle_generation"]):
                fail("CONTROL_INVALID")
            if _integer(package["sequence"], 1) != self.sequence + 1:
                fail("CONTROL_SEQUENCE")
            now, mono = self.sources.continuous_clock(), self.sources.monotonic_clock()
            sample = _integer(package["sampled_continuous_ns"], 1)
            expiry = _integer(package["expires_continuous_ns"], 1)
            lease = _integer(package["lease_until_monotonic_ns"], 1)
            if (not sample <= now < expiry or expiry - sample > LEASE_NS
                    or not mono < lease <= mono + LEASE_NS):
                fail("CONTROL_LEASE")
            self.sequence, self.last = package["sequence"], dict(package)
            return self._observation(package)
        except Unavailable:
            self.invalid = True
            raise
        except Exception:
            self.invalid = True
            fail("CONTROL_UNAVAILABLE")

    def _observation(self, package):
        return {k: package[k] for k in ("run_id", "process_id", "process_incarnation",
            "parent_id", "parent_chain_digest", "network_generation", "lifecycle_generation",
            "foreground", "alive", "terminal_open", "restart_policy")} | {
                "lease_until": package["lease_until_monotonic_ns"] / 1_000_000_000}

    def observe(self):
        try:
            if self.invalid:
                fail("CONTROL_TERMINAL")
            # Do not reuse a previous positive heartbeat after EOF or process death.
            self.sources.qualify("CONTROL", self.context, self.fd)
            observation = self.accept(strict_json(read_frame(self.fd, CONTROL_MAX), CONTROL_MAX))
            # Validate every queued sequence, then use the freshest heartbeat.
            # An expired/invalid intermediate frame cannot be skipped.
            for _ in range(16):
                if not select.select([self.fd], [], [], 0)[0]:
                    break
                observation = self.accept(strict_json(read_frame(self.fd, CONTROL_MAX), CONTROL_MAX))
            else:
                fail("CONTROL_BACKLOG")
            if self.sources.continuous_clock() - self.last["sampled_continuous_ns"] > HEARTBEAT_NS:
                fail("CONTROL_NOT_FRESH")
            return observation
        except Unavailable:
            self.invalid = True
            raise


class ObservationBoundary:
    """Read-only adaptation of qualified FD4/FD6 observations to frozen worker."""
    def __init__(self, sources, packet, host_fd=4, control_fd=6):
        if type(sources) is not ExternalSources:
            fail("EXTERNAL_BINDING")
        self.sources, self.packet = sources, packet
        context = {"run_id": packet["run"]["run_id"],
            "process_incarnation": packet["run"]["process_incarnation"],
            "runtime_binding_digest": digest(packet["runtime"]),
            "baseline": packet["runtime"]["implementation_commit"],
            "phase": packet["run"]["phase"], "profile_digest": digest(packet["profile"])}
        self.context = context
        sources.qualify("HOST", context, host_fd)
        sources.qualify("CONTROL", context, control_fd)
        if (packet["producer"]["host_reference"], packet["producer"]["control_reference"]) != (
                sources.host.reference, sources.control.reference):
            fail("CANDIDATE_PRODUCER_REFERENCE")
        self.host = HostObservationClient(sources, context, host_fd)
        self.control = ControlObservationClient(sources, context, packet["run"], control_fd)
        self.adapter, self.bound_runtime = None, None

    def bind_canonical(self, adapter, runtime):
        self.adapter, self.bound_runtime = adapter, runtime

    def source_qualified(self, kind, run):
        try:
            if kind not in {"HOST", "CONTROL"} or run.run_id != self.context["run_id"]:
                return False
            if self.host.invalid or self.control.invalid:
                return False
            return self.sources.qualify(kind, self.context, self.host.fd if kind == "HOST" else self.control.fd)
        except Unavailable:
            return False

    def _value(self, name):
        if self.adapter is None or self.bound_runtime is None:
            fail("CANONICAL_BINDING")
        return self.host.observe()[name]

    def authority(self, reference, identity, profile):
        value = self._value("authority")
        return (value["authorized"] is True and value["authority_reference"] == asdict(reference)
                and value["execution_identity"] == asdict(identity) and value["selector"] == profile.selector)

    def grant(self, capability_id):
        value = dict(self._value("grant"))
        if value["capability_id"] != capability_id:
            return None
        value["execution_identity"] = self.adapter._core.ExecutionIdentity(**value["execution_identity"])
        value["authority_reference"] = self.adapter._core.AuthorityReference(**value["authority_reference"])
        value["not_after"] = _instant(value["not_after"])
        return self.adapter._cap.CapabilityEnvelope(**value)

    def state(self, capability_id):
        value = dict(self._value("capability_state"))
        if value["capability_id"] != capability_id:
            return None
        value["execution_identity"] = self.adapter._core.ExecutionIdentity(**value["execution_identity"])
        value["authority_reference"] = self.adapter._core.AuthorityReference(**value["authority_reference"])
        return self.adapter._cap.CapabilityStateEvidence(**value)

    def clock(self):
        sampled = _instant(self._value("clock")["trusted_now"])
        now = self.sources.governance_clock()
        if (type(now) is not datetime or now.tzinfo is None
                or not 0 <= (now - sampled).total_seconds() <= 0.8):
            fail("TRUSTED_CLOCK_STALE")
        # Current independently supplied D-04 time can only tighten expiry.
        # The transported timestamp cannot extend a grant by its observation age.
        return now

    def baseline(self):
        return self._value("baseline")["baseline"]

    def target(self, binding_id):
        value = self._value("target")
        if value == {"status": "NOT_APPLICABLE"} or value["binding_id"] != binding_id:
            return None
        return self.adapter.TargetBinding(**value)

    def revocation(self, binding_digest):
        value = self._value("revocation")
        return value["status"] if value["binding_digest"] == binding_digest else "UNKNOWN"

    def credential_reference(self, reference):
        value = self._value("credential_reference")
        return (value["version"], value["organization"], value["project"]) if value["reference"] == reference else None

    def caller(self):
        value = self._value("caller")
        grant = self._value("grant")
        if value["execution_identity"] != grant["execution_identity"]:
            fail("CALLER_EXECUTION_IDENTITY")
        return value["caller_id"]

    def runtime(self):
        value = self._value("runtime_reference")
        return self.bound_runtime if value["runtime_binding_digest"] == self.bound_runtime.digest else None

    def network(self, producer_reference, evidence_reference):
        value = self._value("network_handoff")
        if (value["producer_reference"], value["evidence_reference"]) != (producer_reference, evidence_reference):
            fail("NETWORK_HANDOFF")
        # Independently qualified external evidence, not local HTTP client flags.
        result = self.sources.network_reader(producer_reference, evidence_reference)
        if result is None or result.digest != value["qualification_digest"]:
            fail("NETWORK_SOURCE_UNESTABLISHED")
        return result

    def lifecycle(self):
        return self.control.observe()


def production_sources():
    """No producer trust is bootstrapped from any candidate or local shortcut.

    Integration of actual existing host readers is a separate qualification
    gate. This materialization intentionally provisions none of those sources.
    """
    fail("PRODUCTION_SOURCES_NOT_ESTABLISHED")


def establish(packet):
    """The sole fixed launcher factory; no CLI/provider/path injection."""
    sources = production_sources()
    if type(sources) is not ExternalSources:
        fail("PRODUCTION_SOURCES_NOT_ESTABLISHED")
    return ObservationBoundary(sources, packet)


def credential_free_preflight(a, profile, envelope, runtime, network, run, target, store, boundary,
                              operation=None):
    """Canonical read-only validation; no lease, sender, reservation or consume.

    A pre-existing LiveEvidenceStore may hold its existing single-writer lock;
    verify() is replay/read-only. No create/append/repair is called here.
    Full frozen LiveWorker validation still runs again after FD5.
    """
    try:
        if (not a._modules_intact() or type(profile) is not a.LiveProfile
                or type(envelope) is not a._cap.CapabilityEnvelope or profile.phase != run.phase
                or type(store) is not a.LiveEvidenceStore):
            fail("CANONICAL_PREFLIGHT")
        if (boundary.source_qualified("HOST", run) is not True
                or boundary.source_qualified("CONTROL", run) is not True):
            fail("PRODUCER_QUALIFICATION")
        if boundary.authority(envelope.authority_reference, envelope.execution_identity, profile) is not True:
            fail("AUTHORITY")
        identity = envelope.execution_identity
        validator = a._cap.CapabilityValidator(trusted_grant_resolver=boundary.grant,
            trusted_state_reader=boundary.state, trusted_clock=boundary.clock)
        request = a._cap.ValidationRequest("REMOTE_CONTEXT_PILOT_" + run.phase,
            profile.scope_operation, profile.selector, identity, envelope.authority_reference,
            a._core.WorkflowScope(identity.project_id, identity.stage_id, identity.task_id),
            runtime.implementation_commit, envelope.cancellation_binding)
        result = a._VALIDATE(validator, envelope, request)
        if type(result) is not a._cap.ValidationResult or result.status != "PASS":
            fail("CAPABILITY")
        if boundary.runtime() != runtime or boundary.baseline() != runtime.implementation_commit:
            fail("RUNTIME_BASELINE")
        runtime.verify()
        if (profile.runtime_digest != runtime.digest or profile.network_digest != network.digest
                or profile.run_id != run.run_id or run.phase != profile.phase
                or profile.store_id != store.handle.store_id or run.store_id != profile.store_id):
            fail("PROFILE_BINDING")
        state = store.verify()
        if run.phase != "READ_RECONCILIATION" and envelope.consumption_policy != a._cap.SINGLE_USE:
            fail("SINGLE_USE_REQUIRED")
        if operation is not None:
            _keys(operation, set(operation), "OPERATION_SCHEMA")
            name = operation.get("name")
            valid = (
                (run.phase == "SETUP" and name == "SETUP" and set(operation) == {"name"}) or
                (run.phase == "MUTATION" and name == "MUTATION" and set(operation) == {"name"}) or
                (run.phase == "READ_RECONCILIATION" and name == "LIST_ITEMS"
                 and set(operation) <= {"name", "after"} and operation.get("after") == profile.read_after) or
                (run.phase == "READ_RECONCILIATION" and name == "RETRIEVE_ITEM"
                 and set(operation) == {"name", "item_id"} and operation["item_id"] in profile.item_ids) or
                (run.phase == "DISPOSAL" and name == "DELETE_ITEM"
                 and set(operation) == {"name", "item_id"} and operation["item_id"] in profile.item_ids) or
                (run.phase == "DISPOSAL" and name == "DELETE_CONTAINER"
                 and set(operation) == {"name"} and profile.allow_container_delete))
            if not valid:
                fail("OPERATION_SCOPE")
            budget = {"SETUP": ("SETUP", 1), "MUTATION": ("MUTATION", 1),
                      "LIST_ITEMS": ("READ", 3), "RETRIEVE_ITEM": ("READ", 3),
                      "DELETE_ITEM": ("DELETE_ITEM", 1), "DELETE_CONTAINER": ("DELETE_CONTAINER", 1)}[name]
            if state["counts"].get(budget[0], 0) >= budget[1]:
                fail("BUDGET_EXHAUSTED")
        if target is not None:
            if (type(target) is not a.TargetBinding or target.digest != profile.binding_digest
                    or target.generation != profile.generation
                    or (target.organization, target.project, target.credential_ref, target.credential_version)
                    != (profile.organization, profile.project, profile.credential_ref, profile.credential_version)
                    or boundary.target(target.binding_id) != target
                    or state["bindings"].get(target.digest) != asdict(target)
                    or target.digest in state["revoked"] or boundary.revocation(target.digest) != "ACTIVE"):
                fail("TARGET_REVOCATION")
        elif run.phase != "SETUP" or profile.binding_digest != "UNBOUND" or profile.generation != 0:
            fail("TARGET_REQUIRED")
        if boundary.credential_reference(profile.credential_ref) != (
                profile.credential_version, profile.organization, profile.project):
            fail("CREDENTIAL_REFERENCE")
        if boundary.caller() != profile.caller_id:
            fail("CALLER")
        now = boundary.clock()
        if type(now) is not datetime or now.tzinfo is None or now >= envelope.not_after:
            fail("EXPIRY")
        # These checks only tighten permissions. They do not substitute for the
        # D-04 trusted clock above or consume any capability/reservation.
        network.verify(boundary.network, boundary.clock)
        run.verify(runtime, network, boundary.lifecycle())
        if boundary.source_qualified("HOST", run) is not True or boundary.source_qualified("CONTROL", run) is not True:
            fail("SOURCE_LOSS")
        return True
    except Unavailable:
        raise
    except Exception:
        fail("PREFLIGHT_UNAVAILABLE")


class DarwinReadOnlyObservations:
    """Candidate unprivileged OS reads, never a qualification/trust provider.

    Actual clock/process/channel qualification remains NOT ESTABLISHED.
    Unsupported platform/API or no qualified terminal fails closed.
    """
    def __init__(self):
        if sys.platform != "darwin":
            fail("NATIVE_API_UNAVAILABLE")
        try:
            self.lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
            self.lib.mach_continuous_time.restype = ctypes.c_uint64
            self.lib.proc_pidpath.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
            self.lib.proc_pidpath.restype = ctypes.c_int
            self.lib.proc_pidinfo.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint64,
                                              ctypes.c_void_p, ctypes.c_int)
            self.lib.proc_pidinfo.restype = ctypes.c_int
        except Exception:
            fail("NATIVE_API_UNAVAILABLE")

    def continuous_ns(self):
        class Timebase(ctypes.Structure):
            _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]
        try:
            info = Timebase()
            if self.lib.mach_timebase_info(ctypes.byref(info)) != 0 or not info.denom:
                fail("CONTINUOUS_CLOCK_UNAVAILABLE")
            return int(self.lib.mach_continuous_time()) * info.numer // info.denom
        except Unavailable:
            raise
        except Exception:
            fail("CONTINUOUS_CLOCK_UNAVAILABLE")

    def process(self, pid):
        class BSD(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint32) for n in (
                "flags", "status", "xstatus", "pid", "ppid", "uid", "gid", "ruid", "rgid", "svuid", "svgid", "reserved")]
            _fields_ += [("comm", ctypes.c_char * 16), ("name", ctypes.c_char * 32)]
            _fields_ += [(n, ctypes.c_uint32) for n in ("nfiles", "pgid", "pjobc", "e_tdev", "e_tpgid", "nice")]
            _fields_ += [("start_sec", ctypes.c_uint64), ("start_usec", ctypes.c_uint64)]
        _integer(pid, 1)
        try:
            info, binary = BSD(), ctypes.create_string_buffer(4096)
            if self.lib.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info)) != ctypes.sizeof(info):
                fail("PROCESS_UNAVAILABLE")
            if self.lib.proc_pidpath(pid, binary, len(binary)) <= 0:
                fail("PROCESS_BINARY_UNAVAILABLE")
            return {"process_id": int(info.pid), "uid": int(info.uid), "parent_id": int(info.ppid),
                    "process_incarnation": str(info.start_sec) + "_" + str(info.start_usec),
                    "binary_path": binary.value.decode("utf-8", "strict"),
                    "process_group": int(info.pgid), "terminal_foreground_group": int(info.e_tpgid)}
        except Unavailable:
            raise
        except Exception:
            fail("PROCESS_UNAVAILABLE")

    def peer(self, fd):
        # Dup only an inherited local AF_UNIX descriptor. No bind/connect/listen.
        try:
            with socket.socket(fileno=os.dup(fd)) as channel:
                if channel.family != socket.AF_UNIX:
                    fail("CHANNEL_NOT_LOCAL")
                pid = int.from_bytes(channel.getsockopt(0, 0x002, 4), sys.byteorder, signed=True)
                uid, gid = ctypes.c_uint(), ctypes.c_uint()
                if self.lib.getpeereid(channel.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
                    fail("PEER_UNAVAILABLE")
                return {"process_id": pid, "uid": uid.value}
        except Unavailable:
            raise
        except Exception:
            fail("PEER_UNAVAILABLE")

    def foreground(self, pid, terminal_fd):
        try:
            facts = self.process(pid)
            if not os.isatty(terminal_fd):
                fail("QUALIFIED_FOREGROUND_UNAVAILABLE")
            group = os.tcgetpgrp(terminal_fd)
            if group != facts["process_group"] or group != facts["terminal_foreground_group"]:
                fail("QUALIFIED_FOREGROUND_UNAVAILABLE")
            return True
        except Unavailable:
            raise
        except Exception:
            fail("QUALIFIED_FOREGROUND_UNAVAILABLE")

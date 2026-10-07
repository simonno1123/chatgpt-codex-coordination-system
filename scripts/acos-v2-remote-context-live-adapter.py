"""D-09 live adapter contract; offline qualification does not authorize live use.

Only a separately qualified host may supply authority, credential and network
evidence. Data, file descriptors and digests are not trust anchors. This module
issues no capability, admits no execution and introduces no architectural writer.
One consumed reservation bounds this controlled worker to at most one mutation
POST; provider multiplicity and cross-host atomicity are not guaranteed.
"""
from dataclasses import dataclass, asdict, field, replace
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from contextlib import contextmanager
import asyncio
import fcntl
import hashlib
import importlib.metadata
import json
import logging
import os
import platform
import re
import sqlite3
import ssl
import sys
import tempfile
import threading
import time
import uuid

import httpx
import httpcore

ROOT = Path(__file__).resolve().parent.parent
DESIGN_BASELINE = "182e42d9578972798c43f998a9f7f1243edf28a1"
ORIGIN = "https://api.openai.com"
FORMAT = "acos-v2-remote-context-live-evidence/1"
SCHEMA_VERSION = 1
PHASES = ("SETUP", "MUTATION", "READ_RECONCILIATION", "DISPOSAL")
LIMITS = {"SETUP": 1, "MUTATION": 1, "READ": 3, "DELETE_ITEM": 1, "DELETE_CONTAINER": 1}
MAX_READS, MAX_RESPONSE_BYTES, REQUEST_DEADLINE, FOREGROUND_DEADLINE = 3, 1048576, 30.0, 120.0
DEPENDENCIES = {"httpx": "0.28.1", "httpcore": "1.0.9", "h11": "0.16.0",
                "anyio": "4.13.0", "sniffio": "1.3.1", "certifi": "2026.4.22",
                "idna": "3.13", "typing_extensions": "4.15.0"}
SOURCE_PINS = {
    "acos_v2_core_substrate": ("acos-v2-core-substrate.py", "fb2cdec2a8d3aaeb1c4a1c293f4f8c92120ff576e1309d7c88b10bc419407c7b"),
    "acos_v2_capability": ("acos-v2-capability.py", "884efc61d934e1c361bb9e7a97b4e8ee7807c3adc64fff6114088ad3f9817d40"),
    "acos_v2_remote_context_mutation_pilot": ("acos-v2-remote-context-mutation-pilot.py", "c0f54646059e85813463dbeb46adc389f1f9e54bdb251f4cfef5516210168829"),
}
def _sha(data):
    return hashlib.sha256(data).hexdigest()

def _module(name):
    filename, digest = SOURCE_PINS[name]
    m = sys.modules.get(name)
    path = str(ROOT / "scripts" / filename)
    if (not isinstance(m, ModuleType) or m.__file__ != path
            or _sha(Path(path).read_bytes()) != digest
            or any(isinstance(x, ModuleType) and x is not m and
                   vars(x).get("__file__") == path for x in tuple(sys.modules.values()))):
        raise ImportError("canonical frozen contract required")
    return m

_core = _module("acos_v2_core_substrate")
_cap = _module("acos_v2_capability")
shared = _module("acos_v2_remote_context_mutation_pilot")
_canonical, _digest, _identifier, _hash, _strict_json = (
    shared._canonical, shared._digest, shared._identifier, shared._hash, shared._strict_json)
TargetBinding, Outcome, exact_item = shared.TargetBinding, shared.Outcome, shared.exact_item
BODY_BYTES, BODY_SHA256, WIRE_BYTES, WIRE_SHA256 = (
    shared.BODY_BYTES, shared.BODY_SHA256, shared.WIRE_BYTES, shared.WIRE_SHA256)
_VALIDATE = _cap.CapabilityValidator.validate
_CONTRACT_CALLABLES = (shared.exact_item, shared._strict_json, shared._identifier, shared._canonical)

class Denied(ValueError):
    """Only fixed, non-secret failure labels may leave the boundary."""

class StoreBlocked(RuntimeError):
    pass

class CommitUnknown(StoreBlocked):
    pass

class FenceDenied(Denied):
    pass

def _modules_intact():
    try:
        return (_module("acos_v2_core_substrate") is _core
                and _module("acos_v2_capability") is _cap
                and _module("acos_v2_remote_context_mutation_pilot") is shared
                and _cap._canonical_core_intact()
                and _cap.CapabilityValidator.validate is _VALIDATE
                and _CONTRACT_CALLABLES == (shared.exact_item, shared._strict_json,
                                            shared._identifier, shared._canonical))
    except Exception:
        return False

@dataclass(frozen=True)
class FilePin:
    path: str
    sha256: str
    size: int
    device: int
    inode: int

    def verify(self):
        p = Path(self.path)
        if p.is_symlink() or not p.is_absolute() or str(p.resolve()) != self.path:
            raise Denied("FILE_IDENTITY")
        s = p.stat()
        if (s.st_dev, s.st_ino, s.st_size) != (self.device, self.inode, self.size):
            raise Denied("FILE_IDENTITY")
        if _sha(p.read_bytes()) != self.sha256:
            raise Denied("FILE_DIGEST")
        return True

@dataclass(frozen=True)
class DependencyPin:
    name: str
    version: str
    location: str
    files: tuple

    def verify(self, approved_location):
        if self.name not in DEPENDENCIES or self.version != DEPENDENCIES[self.name]:
            raise Denied("DEPENDENCY_VERSION")
        if self.location != approved_location or not self.files:
            raise Denied("DEPENDENCY_LOCATION")
        d = importlib.metadata.distribution(self.name)
        if d.version != self.version or str(Path(d.locate_file("")).resolve()) != self.location:
            raise Denied("DEPENDENCY_DRIFT")
        for pin in self.files:
            if type(pin) is not FilePin or not Path(pin.path).is_relative_to(Path(self.location).parents[2]):
                raise Denied("DEPENDENCY_FILE")
            pin.verify()
        # Bind the full installed distribution inventory, including unhashed files.
        installed = {str(Path(d.locate_file(f)).resolve()) for f in (d.files or ())
                     if Path(d.locate_file(f)).is_file()}
        if installed != {p.path for p in self.files}:
            raise Denied("DEPENDENCY_INVENTORY")
        return True

@dataclass(frozen=True)
class RuntimeBinding:
    """Qualification evidence only; construction is not qualification."""
    generation: int
    implementation_commit: str
    source_pins: tuple
    launcher_pin: FilePin
    adapter_pin: FilePin
    requirements_pin: FilePin
    python_pin: FilePin
    python_app_pin: FilePin
    framework_pin: FilePin
    python_version: str
    architecture: str
    dependency_location: str
    dependencies: tuple
    ca_pin: FilePin
    parent_chain_digest: str
    design_baseline: str = DESIGN_BASELINE
    flags: tuple = ("-I", "-S", "-B")
    cwd: str = str(ROOT)

    @property
    def digest(self):
        return _digest(asdict(self))

    def verify(self):
        if (self.design_baseline != DESIGN_BASELINE or type(self.generation) is not int
                or self.generation < 1 or not re.fullmatch(r"[0-9a-f]{40}", self.implementation_commit)
                or self.flags != ("-I", "-S", "-B") or self.cwd != str(ROOT)
                or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode)):
            raise Denied("RUNTIME_BINDING")
        if self.python_pin.path != "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13":
            raise Denied("INTERPRETER_PATH")
        if (str(Path(sys.executable).resolve()) != self.python_pin.path
                or platform.python_version() != self.python_version
                or platform.machine() != self.architecture):
            raise Denied("INTERPRETER_IDENTITY")
        expected = {str(ROOT/"scripts"/x[0]): x[1] for x in SOURCE_PINS.values()}
        if {p.path: p.sha256 for p in self.source_pins} != expected:
            raise Denied("SOURCE_SCOPE")
        for pin in (*self.source_pins, self.launcher_pin, self.adapter_pin,
                    self.requirements_pin, self.python_pin, self.python_app_pin,
                    self.framework_pin, self.ca_pin):
            if type(pin) is not FilePin:
                raise Denied("FILE_PIN")
            pin.verify()
        if (self.adapter_pin.path != str(ROOT/"scripts/acos-v2-remote-context-live-adapter.py")
                or self.launcher_pin.path != str(ROOT/"scripts/acos-v2-remote-context-live-launcher.py")
                or self.requirements_pin.path != str(ROOT/"requirements-acos-v2-remote-context-mutation-pilot.txt")
                or self.python_app_pin.path != "/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python"
                or self.framework_pin.path != "/Library/Frameworks/Python.framework/Versions/3.13/Python"
                or self.ca_pin.path != str(Path(self.dependency_location)/"certifi/cacert.pem")
                or self.ca_pin.sha256 != "16be3f6feb15408195dcfe3aa1a75ef9db72f646b96ebbefdc68f56255f799f8"
                or self.requirements_pin.sha256 != "fe11dc0a5dcd7695c49e577e055bac2afa17dfdba79b2b132ded338897fcdb75"):
            raise Denied("RUNTIME_SOURCE")
        if {d.name for d in self.dependencies} != set(DEPENDENCIES) or len(self.dependencies) != len(DEPENDENCIES):
            raise Denied("DEPENDENCY_SET")
        for dep in self.dependencies:
            if type(dep) is not DependencyPin:
                raise Denied("DEPENDENCY_PIN")
            dep.verify(self.dependency_location)
        _hash(self.parent_chain_digest)
        if not _modules_intact():
            raise Denied("CANONICAL_MODULE")
        return True

@dataclass(frozen=True)
class RunBinding:
    run_id: str
    phase: str
    runtime_digest: str
    network_digest: str
    store_id: str
    process_id: int
    process_incarnation: str
    parent_id: int
    parent_chain_digest: str
    network_generation: int
    lifecycle_generation: int
    deadline: float

    def verify(self, runtime, network, observation):
        if (self.phase not in PHASES or self.process_id != os.getpid()
                or self.parent_id != os.getppid() or self.runtime_digest != runtime.digest
                or self.network_digest != network.digest or self.parent_chain_digest != runtime.parent_chain_digest
                or time.monotonic() >= self.deadline):
            raise Denied("RUN_BINDING")
        _identifier(self.run_id)
        _identifier(self.store_id)
        _identifier(self.process_incarnation)
        required = {"run_id": self.run_id, "process_id": self.process_id,
                    "process_incarnation": self.process_incarnation,
                    "parent_id": self.parent_id, "parent_chain_digest": self.parent_chain_digest,
                    "network_generation": self.network_generation,
                    "lifecycle_generation": self.lifecycle_generation}
        if (type(observation) is not dict or any(observation.get(k) != v for k, v in required.items())
                or observation.get("foreground") is not True or observation.get("alive") is not True
                or observation.get("restart_policy") != "NONE"
                or observation.get("terminal_open") is not True
                or type(observation.get("lease_until")) not in (int, float)
                or time.monotonic() >= observation["lease_until"]
                or observation["lease_until"] > time.monotonic() + 1.1):
            raise Denied("LIFETIME")
        return True

@dataclass(frozen=True)
class NetworkQualificationBinding:
    generation: int
    interface: str
    route: str
    system_proxy_observation: str
    transport_mode: str
    evidence_reference: str
    producer_reference: str
    observed_at: datetime
    not_after: datetime
    replay_boundary: tuple
    hostname: str = "api.openai.com"
    application_proxy: str = "NONE"
    trust_env: bool = False
    tls_verification: str = "CERTIFICATE_AND_HOSTNAME"
    explicit_gateway: str = "NONE"

    @property
    def digest(self):
        return _digest({**asdict(self), "observed_at": self.observed_at.isoformat(),
                        "not_after": self.not_after.isoformat()})

    def verify(self, independent_reader, clock):
        # NO values are not manufactured from local client flags.
        required = {"TLSTermination", "HTTPRegeneration", "POSTReplayCapability",
                    "AutomaticRetry", "FallbackHTTPGateway"}
        values = dict(self.replay_boundary)
        if (len(self.replay_boundary) != len(required) or set(values) != required
                or any(v != "NO" for v in values.values())
                or self.hostname != "api.openai.com" or self.application_proxy != "NONE"
                or self.trust_env is not False or self.tls_verification != "CERTIFICATE_AND_HOSTNAME"
                or self.explicit_gateway != "NONE" or self.generation < 1
                or not self.interface or not self.route or not self.system_proxy_observation
                or self.transport_mode not in ("DIRECT_TLS", "FAKE_IP_TLS", "TUN_TLS", "TCP_FORWARD_TLS")
                or self.observed_at.tzinfo is None or self.not_after.tzinfo is None):
            raise Denied("NETWORK_BOUNDARY")
        now = clock()
        if self.observed_at > now or now >= self.not_after:
            raise Denied("NETWORK_EVIDENCE_EXPIRED")
        _identifier(self.producer_reference)
        _identifier(self.evidence_reference)
        if not callable(independent_reader) or independent_reader(
                self.producer_reference, self.evidence_reference) != self:
            raise Denied("NETWORK_SOURCE_UNESTABLISHED")
        return True

@dataclass(frozen=True)
class CredentialLease:
    """Opaque injection contract; no discovery, refresh, or issuer."""
    reference: str
    version: int
    organization: str
    project: str
    run_id: str
    process_id: int
    not_after: datetime
    material: bytes = field(repr=False, compare=False)

    def validate(self, profile, run, now):
        if (self.reference, self.version, self.organization, self.project) != (
                profile.credential_ref, profile.credential_version, profile.organization, profile.project):
            raise Denied("CREDENTIAL_REFERENCE")
        if (self.run_id != run.run_id or self.process_id != os.getpid()
                or self.not_after.tzinfo is None or now >= self.not_after
                or type(self.material) is not bytes or not 1 <= len(self.material) <= 8192
                or any(b < 33 or b > 126 for b in self.material)):
            raise Denied("CREDENTIAL_LEASE")
        return True

@dataclass(frozen=True)
class LiveProfile:
    """Only a bounded selector under existing D-04; never a grant."""
    contract: shared.Profile
    runtime_digest: str
    network_digest: str
    run_id: str
    read_after: str | None = None

    def __post_init__(self):
        if type(self.contract) is not shared.Profile:
            raise Denied("PROFILE_CONTRACT")
        _hash(self.runtime_digest)
        _hash(self.network_digest)
        _identifier(self.run_id)
        if self.read_after is not None:
            _identifier(self.read_after)
            if self.contract.phase != "READ_RECONCILIATION":
                raise Denied("READ_CURSOR_PHASE")

    def __getattr__(self, name):
        if name in shared.Profile.__dataclass_fields__ or name == "scope_operation":
            return getattr(self.contract, name)
        raise AttributeError(name)

    @property
    def selector(self):
        return "remote-context-live/1:" + _digest(asdict(self))

    @property
    def semantic_digest(self):
        return _digest({"domain": "acos-remote-context-live-semantic/1",
                        "contract": self.contract.semantic_digest,
                        "runtime": self.runtime_digest, "network": self.network_digest,
                        "read_after": self.read_after})

@dataclass(frozen=True)
class LiveHostReads:
    """Producer trust must be independently established; fixtures are not trust."""
    authority_reader: object
    capability_validator: object
    baseline_reader: object
    binding_reader: object
    revocation_reader: object
    credential_reference_reader: object
    caller_reader: object
    clock: object
    runtime_reader: object
    network_evidence_reader: object
    lifecycle_reader: object
    source_qualification_reader: object

@dataclass(frozen=True)
class LiveStoreHandle:
    path: str
    store_id: str
    device: int
    inode: int

def _empty():
    return {**shared._empty(), "exposure_arms": []}

def _apply(state, kind, data):
    if kind == "EXPOSURE_ARM":
        if set(data) != {"reservation_id", "permit_digest"} or data["reservation_id"] not in state["reservations"]:
            raise StoreBlocked("EXPOSURE_SCOPE")
        _hash(data["permit_digest"])
        if any(x["reservation_id"] == data["reservation_id"] for x in state["exposure_arms"]):
            raise FenceDenied("SECOND_EXPOSURE")
        state["exposure_arms"].append(data)
    else:
        shared._apply(state, kind, data)

_EVIDENCE_KEYS = {
    "BINDING": set(TargetBinding.__dataclass_fields__),
    "REVOKE": {"binding"},
    "RESERVE": {"reservation_id", "operation", "binding", "generation", "authority_reference",
                "capability_id", "consumption_policy", "capability_profile_digest", "execution_identity",
                "baseline", "caller_id", "credential_ref", "credential_version", "submission_id",
                "delivery_id", "relay_attempt_id", "http_attempt_ordinal", "method", "path",
                "payload_sha256", "semantic_digest", "wire_sha256", "budget_consumed", "reserved_at",
                "runtime_digest", "network_digest", "run_id", "store_id"},
    "OBSERVATION": {"reservation_id", "control", "presence", "error_class", "provider_request_id",
                    "provider_response_digest", "observed_at"},
    "RECEIPT": {"reservation_id", "stage", "item_ids", "control", "presence", "observed_at", "authority_effect"},
    "TOMBSTONE": {"binding", "container_deleted", "item_purge_proven", "history_preserved"},
    "EXPOSURE_ARM": {"reservation_id", "permit_digest"},
}
def _evidence_safe(kind, data):
    if kind not in _EVIDENCE_KEYS or type(data) is not dict or not set(data) <= _EVIDENCE_KEYS[kind]:
        raise StoreBlocked("EVIDENCE_SCHEMA")
    def walk(value):
        if type(value) is dict:
            for k, v in value.items():
                if k.lower() in {"authorization", "bearer", "secret", "material", "cookie",
                                 "environment", "traceback", "response", "request"}:
                    raise StoreBlocked("EVIDENCE_SECRET_FIELD")
                walk(v)
        elif type(value) in (list, tuple):
            for v in value:
                walk(v)
        elif type(value) is str:
            if len(value) > 1024 or "Bearer " in value or value.startswith(("sk-", "fixture-only-")):
                raise StoreBlocked("EVIDENCE_SECRET_VALUE")
        elif value is not None and type(value) not in (bool, int, float):
            raise StoreBlocked("EVIDENCE_TYPE")
    walk(data)
    _canonical(data)

class LiveEvidenceStore:
    """Existing D-08/D-09 non-authoritative role; one logical writer per instance."""
    def __init__(self, handle):
        if type(handle) is not LiveStoreHandle:
            raise StoreBlocked("STORE_HANDLE")
        self.handle, self._fd = handle, None
        self._check_identity()
        try:
            self._fd = os.open(str(Path(handle.path).parent), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.verify()
        except Exception:
            self.close()
            raise StoreBlocked("STORE_WRITER_OR_REPLAY") from None

    @classmethod
    def create(cls, directory):
        """Only separately authorized fresh local preparation; dispatch never creates."""
        root = Path(directory)
        temp = Path(tempfile.gettempdir()).resolve()
        if root.is_symlink() or root.resolve() != root or temp not in root.parents or (
                not root.name.startswith("acos-remote-context-live-")):
            raise StoreBlocked("FRESH_LIVE_DIRECTORY")
        path = root / "pilot.sqlite"
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        sid = uuid.uuid4().hex
        c = sqlite3.connect(str(path))
        try:
            c.execute("PRAGMA synchronous=FULL")
            c.executescript("""
                CREATE TABLE metadata(format TEXT,version INTEGER,store_id TEXT);
                CREATE TABLE journal(seq INTEGER PRIMARY KEY,kind TEXT NOT NULL,
                  body BLOB NOT NULL,previous TEXT NOT NULL,digest TEXT NOT NULL);
                CREATE TABLE projection(id INTEGER PRIMARY KEY CHECK(id=1),body BLOB NOT NULL);
                CREATE TRIGGER journal_no_update BEFORE UPDATE ON journal BEGIN
                  SELECT RAISE(ABORT,'append-only'); END;
                CREATE TRIGGER journal_no_delete BEFORE DELETE ON journal BEGIN
                  SELECT RAISE(ABORT,'append-only'); END;
                CREATE TRIGGER metadata_no_update BEFORE UPDATE ON metadata BEGIN
                  SELECT RAISE(ABORT,'immutable'); END;
                CREATE TRIGGER metadata_no_delete BEFORE DELETE ON metadata BEGIN
                  SELECT RAISE(ABORT,'immutable'); END;
            """)
            c.execute("INSERT INTO metadata VALUES(?,?,?)", (FORMAT, SCHEMA_VERSION, sid))
            c.execute("INSERT INTO projection VALUES(1,?)", (_canonical(_empty()),))
            c.commit()
        finally:
            c.close()
        s = path.stat()
        return cls(LiveStoreHandle(str(path), sid, s.st_dev, s.st_ino))

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def _check_identity(self):
        p = Path(self.handle.path)
        temp = Path(tempfile.gettempdir()).resolve()
        if (p.is_symlink() or p.parent.is_symlink() or p.resolve() != p
                or temp not in p.parents or not p.parent.name.startswith("acos-remote-context-live-")
                or p.name != "pilot.sqlite"):
            raise StoreBlocked("STORE_PATH")
        s = p.stat()
        if (s.st_dev, s.st_ino) != (self.handle.device, self.handle.inode):
            raise StoreBlocked("STORE_REPLACED")
        if self._fd is not None:
            directory = p.parent.stat()
            held = os.fstat(self._fd)
            if (directory.st_dev, directory.st_ino) != (held.st_dev, held.st_ino):
                raise StoreBlocked("DIRECTORY_REPLACED")

    def _connect(self, readonly=False):
        self._check_identity()
        if self._fd is None:
            raise StoreBlocked("STORE_CLOSED")
        c = sqlite3.connect(Path(self.handle.path).as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
                            uri=True, timeout=1.0, isolation_level=None)
        if not readonly:
            c.execute("PRAGMA synchronous=FULL")
        return c

    def _replay(self, c):
        if c.execute("SELECT format,version,store_id FROM metadata").fetchall() != [
                (FORMAT, SCHEMA_VERSION, self.handle.store_id)]:
            raise StoreBlocked("STORE_FORMAT")
        if c.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise StoreBlocked("STORE_CORRUPT")
        triggers = {x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        if triggers != {"journal_no_update", "journal_no_delete", "metadata_no_update", "metadata_no_delete"}:
            raise StoreBlocked("STORE_SCHEMA")
        state, prev = _empty(), "GENESIS"
        for expected, (seq, kind, raw, predecessor, digest) in enumerate(
                c.execute("SELECT seq,kind,body,previous,digest FROM journal ORDER BY seq"), 1):
            data = _strict_json(raw)
            _evidence_safe(kind, data)
            if seq != expected or predecessor != prev or digest != _digest(
                    {"seq": seq, "kind": kind, "body": data, "previous": predecessor}):
                raise StoreBlocked("JOURNAL_CHAIN")
            _apply(state, kind, data)
            prev = digest
        projection = c.execute("SELECT id,body FROM projection").fetchall()
        if projection != [(1, _canonical(state))]:
            raise StoreBlocked("PROJECTION_NO_REPAIR")
        return state, prev

    def verify(self):
        try:
            c = self._connect(readonly=True)
            try:
                return self._replay(c)[0]
            finally:
                c.close()
        except (Denied, StoreBlocked):
            raise
        except Exception:
            raise StoreBlocked("STORE_REPLAY") from None

    def append(self, kind, data):
        _evidence_safe(kind, data)
        c, committed = self._connect(), False
        try:
            c.execute("BEGIN IMMEDIATE")
            state, prev = self._replay(c)
            _apply(state, kind, data)
            seq = c.execute("SELECT count(*) FROM journal").fetchone()[0] + 1
            digest = _digest({"seq": seq, "kind": kind, "body": data, "previous": prev})
            c.execute("INSERT INTO journal VALUES(?,?,?,?,?)", (seq, kind, _canonical(data), prev, digest))
            c.execute("UPDATE projection SET body=? WHERE id=1", (_canonical(state),))
            c.execute("COMMIT")
            committed = True
            self._check_identity()
        except (Denied, StoreBlocked, shared.Denied, shared.StoreBlocked):
            if not committed:
                c.execute("ROLLBACK")
            raise
        except Exception:
            if not committed:
                try:
                    c.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise CommitUnknown("LOCAL_COMMIT_UNKNOWN") from None
        finally:
            c.close()

    def bind_target(self, binding):
        if type(binding) is not TargetBinding:
            raise Denied("TARGET_BINDING")
        self.append("BINDING", asdict(binding))

    def revoke(self, binding):
        self.append("REVOKE", {"binding": binding.digest})

@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    body: bytes

def _operation(method, path, body):
    allowed = ((method == "POST" and path == "/v1/conversations" and body == b"{}")
        or (method == "POST" and re.fullmatch(r"/v1/conversations/[A-Za-z0-9_-]+/items", path)
            and body == BODY_BYTES)
        or (method == "GET" and re.fullmatch(
            r"/v1/conversations/[A-Za-z0-9_-]+/items(?:/[A-Za-z0-9_-]+|\?limit=100&order=asc(?:&after=[A-Za-z0-9_-]+)?)", path)
            and body == b"")
        or (method == "DELETE" and re.fullmatch(
            r"/v1/conversations/[A-Za-z0-9_-]+(?:/items/[A-Za-z0-9_-]+)?", path) and body == b""))
    if type(body) is not bytes or not allowed:
        raise FenceDenied("OPERATION_WHITELIST")
    return Operation(method, path, body)

class _HeaderPermit:
    def __init__(self, reservation, operation, binding_digest, generation, credential, runtime, network, run,
                 organization, project, store, final_validate):
        self.reservation = reservation
        self._credential = credential
        self.operation = operation
        self.organization, self.project = organization, project
        self.scope = {"reservation_id": reservation, "method": operation.method, "path": operation.path,
                      "binding": binding_digest, "generation": generation, "payload": _sha(operation.body),
                      "credential_ref": credential.reference, "credential_version": credential.version,
                      "runtime_generation": runtime.generation, "runtime_digest": runtime.digest,
                      "network_generation": network.generation, "network_digest": network.digest,
                      "run_id": run.run_id, "process_id": run.process_id,
                      "process_incarnation": run.process_incarnation}
        self.store, self.final_validate = store, final_validate
        self.count, self.claimed, self.lock = 0, False, threading.Lock()

    def close(self):
        with self.lock:
            self.claimed = True

    def __reduce__(self):
        raise FenceDenied("PERMIT_NOT_SERIALIZABLE")

    async def trace(self, name, info):
        if name != "http11.send_request_headers.started":
            return
        with self.lock:
            if self.claimed:
                raise FenceDenied("SECOND_HEADERS")
            self.claimed = True
            self.final_validate()
            request = info.get("request")
            if (request is None or request.method != self.operation.method.encode("ascii")
                    or request.url.target != self.operation.path.encode("ascii")
                    or request.url.origin.host != b"api.openai.com"
                    or request.url.origin.scheme != b"https" or request.url.origin.port != 443):
                raise FenceDenied("ALTERED_REQUEST")
            if type(request.stream) is not httpx.ByteStream or request.stream._stream != self.operation.body:
                raise FenceDenied("ALTERED_BODY")
            if len({k.lower() for k, _ in request.headers}) != len(request.headers):
                raise FenceDenied("DUPLICATE_HEADERS")
            headers = {k.lower(): v for k, v in request.headers}
            if (headers.get(b"openai-organization") != self.organization.encode()
                    or headers.get(b"openai-project") != self.project.encode()
                    or headers.get(b"host") != b"api.openai.com"
                    or headers.get(b"authorization") != b"Bearer " + self._credential.material
                    or headers.get(b"content-length") not in ((b"0", None) if not self.operation.body
                                                              else (str(len(self.operation.body)).encode(),))):
                raise FenceDenied("ALTERED_HEADERS")
            self.store.append("EXPOSURE_ARM", {"reservation_id": self.reservation,
                                               "permit_digest": _digest(self.scope)})
            self.count = 1

_LOG_LOCK = threading.Lock()
_LOG_USERS = 0
_LOG_BASELINE = 0

@contextmanager
def _quiet_transport_logs():
    # Overlapping async clients must not restore logging while another is active.
    global _LOG_USERS, _LOG_BASELINE
    with _LOG_LOCK:
        if _LOG_USERS == 0:
            _LOG_BASELINE = logging.root.manager.disable
        _LOG_USERS += 1
        logging.disable(max(_LOG_BASELINE, logging.CRITICAL + 1))
    try:
        yield
    finally:
        with _LOG_LOCK:
            _LOG_USERS -= 1
            if _LOG_USERS == 0:
                logging.disable(_LOG_BASELINE)

class LiveNetworkAdapter:
    """HTTPS transport only; methods, URLs, clients and auth are not caller supplied."""
    def __init__(self, credential, runtime):
        if type(credential) is not CredentialLease or type(runtime) is not RuntimeBinding:
            raise Denied("ADAPTER_INPUT")
        self._credential, self._runtime = credential, runtime

    async def _dispatch(self, operation, permit, remaining):
        if type(operation) is not Operation or type(permit) is not _HeaderPermit or permit.operation != operation:
            raise FenceDenied("PERMIT_REQUIRED")
        _operation(operation.method, operation.path, operation.body)
        permit.final_validate()  # BEFORE any resolver/backend/connect call.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_verify_locations(cafile=self._runtime.ca_pin.path)
        context.set_alpn_protocols(["http/1.1"])
        transport = httpx.AsyncHTTPTransport(verify=context, retries=0, trust_env=False, proxy=None,
            http1=True, http2=False, limits=httpx.Limits(max_connections=1, max_keepalive_connections=0))
        with _quiet_transport_logs():
            async with httpx.AsyncClient(transport=transport, trust_env=False, follow_redirects=False,
                                        auth=None, proxy=None, mounts=None, event_hooks={}) as client:
                headers = {"Content-Type": "application/json", "Accept-Encoding": "identity",
                           "Authorization": "Bearer " + self._credential.material.decode("ascii"),
                           "OpenAI-Organization": permit.organization, "OpenAI-Project": permit.project}
                extensions = {"trace": permit.trace, "timeout": {k: REQUEST_DEADLINE
                              for k in ("connect", "read", "write", "pool")}}
                async with asyncio.timeout(min(REQUEST_DEADLINE, remaining)):
                    async with client.stream(operation.method, ORIGIN + operation.path,
                            content=operation.body, headers=headers, extensions=extensions,
                            auth=None, follow_redirects=False) as response:
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > MAX_RESPONSE_BYTES:
                                raise Denied("RESPONSE_BOUND")
                        if self._credential.material in bytes(chunks):
                            raise Denied("SECRET_RESPONSE")
                        request_id = response.headers.get("x-request-id")
                        if (not isinstance(request_id, str)
                                or not re.fullmatch(r"req_[A-Za-z0-9_-]{1,120}", request_id)
                                or self._credential.material.decode("ascii") in request_id):
                            request_id = None
                        return response.status_code, _strict_json(bytes(chunks)), request_id

class LiveWorker:
    """Validate + reserve + dispatch + evidence; no admission or issuer."""
    def __init__(self, store, host, credential, runtime, network, run):
        if (type(store) is not LiveEvidenceStore or type(host) is not LiveHostReads
                or type(credential) is not CredentialLease or type(runtime) is not RuntimeBinding
                or type(network) is not NetworkQualificationBinding or type(run) is not RunBinding):
            raise Denied("WORKER_INPUT")
        self.store, self.host, self.credential = store, host, credential
        self.runtime, self.network, self.run = runtime, network, run
        self._sender = LiveNetworkAdapter(credential, runtime)
        self._started = time.monotonic()

    def _validate(self, profile, envelope, phase, binding):
        if not _modules_intact() or type(profile) is not LiveProfile or profile.phase != phase:
            raise Denied("CANONICAL_PHASE")
        if type(envelope) is not _cap.CapabilityEnvelope:
            raise Denied("CAPABILITY_MISSING")
        h = self.host
        try:
            if not callable(h.source_qualification_reader) or h.source_qualification_reader(
                    "HOST", self.run) is not True:
                raise Denied("HOST_SOURCE_UNESTABLISHED")
            if not callable(h.authority_reader) or h.authority_reader(
                    envelope.authority_reference, envelope.execution_identity, profile) is not True:
                raise Denied("AUTHORITY")
            if type(h.capability_validator) is not _cap.CapabilityValidator:
                raise Denied("CANONICAL_D04")
            identity = envelope.execution_identity
            request = _cap.ValidationRequest("REMOTE_CONTEXT_PILOT_" + phase, profile.scope_operation,
                profile.selector, identity, envelope.authority_reference,
                _core.WorkflowScope(identity.project_id, identity.stage_id, identity.task_id),
                self.runtime.implementation_commit, envelope.cancellation_binding)
            result = _VALIDATE(h.capability_validator, envelope, request)
            if type(result) is not _cap.ValidationResult or result.status != "PASS":
                raise Denied("CAPABILITY")
            if not callable(h.runtime_reader) or h.runtime_reader() != self.runtime:
                raise Denied("RUNTIME_REFERENCE")
            self.runtime.verify()
            if not callable(h.baseline_reader) or h.baseline_reader() != self.runtime.implementation_commit:
                raise Denied("BASELINE")
            if (profile.runtime_digest != self.runtime.digest or profile.network_digest != self.network.digest
                    or profile.run_id != self.run.run_id or self.run.phase != phase
                    or profile.store_id != self.store.handle.store_id or self.run.store_id != profile.store_id):
                raise Denied("PROFILE_BINDING")
            if binding is not None:
                if type(binding) is not TargetBinding or (
                        binding.digest != profile.binding_digest or binding.generation != profile.generation
                        or (binding.organization, binding.project, binding.credential_ref, binding.credential_version)
                        != (profile.organization, profile.project, profile.credential_ref, profile.credential_version)):
                    raise Denied("TARGET_GENERATION")
                if not callable(h.binding_reader) or h.binding_reader(binding.binding_id) != binding:
                    raise Denied("TARGET_SOURCE")
                state = self.store.verify()
                if state["bindings"].get(binding.digest) != asdict(binding):
                    raise Denied("TARGET_NOT_PINNED")
                if binding.digest in state["revoked"] or not callable(h.revocation_reader) or (
                        h.revocation_reader(binding.digest) != "ACTIVE"):
                    raise Denied("REVOCATION")
            elif phase != "SETUP":
                raise Denied("TARGET_REQUIRED")
            if not callable(h.credential_reference_reader) or h.credential_reference_reader(
                    profile.credential_ref) != (profile.credential_version, profile.organization, profile.project):
                raise Denied("CREDENTIAL_REFERENCE")
            if not callable(h.caller_reader) or h.caller_reader() != profile.caller_id:
                raise Denied("CALLER")
            now = h.clock()
            if type(now) is not datetime or now.tzinfo is None or now >= envelope.not_after:
                raise Denied("EXPIRY")
            self.credential.validate(profile, self.run, now)
            self.network.verify(h.network_evidence_reader, h.clock)
            if not callable(h.lifecycle_reader):
                raise Denied("LIFETIME_SOURCE")
            self.run.verify(self.runtime, self.network, h.lifecycle_reader())
            if time.monotonic() - self._started >= FOREGROUND_DEADLINE:
                raise Denied("FOREGROUND_DEADLINE")
        except (Denied, StoreBlocked):
            raise
        except Exception:
            raise Denied("INDEPENDENT_VALIDATION_UNAVAILABLE") from None

    def _knowledge(self):
        state = self.store.verify()
        if any(r["stage"] in ("REMOTE_ITEM_CREATED", "REMOTE_CONTEXT_MUTATION_CONFIRMED")
               for r in state["receipts"]):
            return "KNOWN_MUTATED"
        return "UNKNOWN" if state["counts"].get("MUTATION", 0) else "NOT_DISPATCHED"

    def _known_items(self):
        return {i for r in self.store.verify()["receipts"] for i in r.get("item_ids", [])}

    def _quarantined(self):
        state = self.store.verify()
        return any(r.get("control") == "QUARANTINED" for r in state["receipts"] + state["observations"])

    def _evidence(self, reservation, stage, item_ids=(), control="STOPPED", presence="PRESENT"):
        self.store.append("RECEIPT", {"reservation_id": reservation, "stage": stage,
            "item_ids": list(item_ids), "control": control, "presence": presence,
            "observed_at": datetime.now(timezone.utc).isoformat(), "authority_effect": "NONE"})

    def _observe(self, reservation, control, presence, error_class):
        self.store.append("OBSERVATION", {"reservation_id": reservation,
            "control": control, "presence": presence, "error_class": error_class,
            "observed_at": datetime.now(timezone.utc).isoformat()})

    def _dispatch(self, profile, envelope, phase, binding, operation, path, body=b""):
        self._validate(profile, envelope, phase, binding)
        if phase == "DISPOSAL" and operation != profile.scope_operation:
            raise Denied("DISPOSAL_SCOPE")
        if phase in ("SETUP", "MUTATION", "DISPOSAL") and envelope.consumption_policy != _cap.SINGLE_USE:
            raise Denied("SINGLE_USE_REQUIRED")
        op = _operation({"SETUP": "POST", "MUTATION": "POST", "READ": "GET",
                         "DELETE_ITEM": "DELETE", "DELETE_CONTAINER": "DELETE"}[operation], path, body)
        rid = uuid.uuid4().hex
        data = {"reservation_id": rid, "operation": operation,
                "binding": profile.binding_digest, "generation": profile.generation,
                "authority_reference": asdict(envelope.authority_reference),
                "capability_id": envelope.capability_id, "consumption_policy": envelope.consumption_policy,
                "capability_profile_digest": _digest(asdict(profile)),
                "execution_identity": asdict(envelope.execution_identity),
                "baseline": self.runtime.implementation_commit, "caller_id": profile.caller_id,
                "credential_ref": profile.credential_ref, "credential_version": profile.credential_version,
                "submission_id": profile.submission_id, "delivery_id": profile.delivery_id,
                "relay_attempt_id": uuid.uuid4().hex,
                "http_attempt_ordinal": self.store.verify()["counts"].get(operation, 0) + 1,
                "method": op.method, "path": path, "payload_sha256": _sha(body),
                "semantic_digest": profile.semantic_digest, "wire_sha256": WIRE_SHA256,
                "budget_consumed": True, "reserved_at": datetime.now(timezone.utc).isoformat(),
                "runtime_digest": self.runtime.digest, "network_digest": self.network.digest,
                "run_id": self.run.run_id, "store_id": self.store.handle.store_id}
        # No dependent network call after failure/unknown reservation acknowledgement.
        self.store.append("RESERVE", data)
        final = lambda: self._validate(profile, envelope, phase, binding)
        final()  # Separate pre-connect fence: no DNS/TCP/TLS has occurred.
        permit = _HeaderPermit(rid, op, profile.binding_digest, profile.generation,
            self.credential, self.runtime, self.network, self.run, profile.organization,
            profile.project, self.store, final)
        remaining = min(self.run.deadline - time.monotonic(),
                        FOREGROUND_DEADLINE - (time.monotonic() - self._started))
        if remaining <= 0:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "DEADLINE_BEFORE_SEND")
            return rid, None, None, Outcome("KNOWN_NOT_MUTATED", "STOPPED", reason="no headers exposure")
        try:
            async def controlled_send():
                task = asyncio.create_task(self._sender._dispatch(op, permit, remaining))
                try:
                    while not task.done():
                        done, _ = await asyncio.wait({task}, timeout=0.1)
                        if done:
                            break
                        # Qualified host lifecycle/power/route observations; never
                        # discover or certify their production sources here.
                        self._validate(profile, envelope, phase, binding)
                    return task.result()
                finally:
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            status, response, request_id = asyncio.run(controlled_send())
            self.store.append("OBSERVATION", {"reservation_id": rid, "control": "STOPPED",
                "presence": "NOT_OBSERVED", "error_class": "RESPONSE_OBSERVED",
                "provider_request_id": request_id, "provider_response_digest": _digest(response),
                "observed_at": datetime.now(timezone.utc).isoformat()})
            if 300 <= status < 400:
                self._observe(rid, "QUARANTINED", "NOT_OBSERVED", "REDIRECT_DENIED")
                return rid, None, None, Outcome(self._knowledge(), "QUARANTINED", reason="redirect denied")
            return rid, status, response, None
        except Exception:
            # Only this controlled callback ordering supplies positive no-headers proof.
            knowledge = "KNOWN_NOT_MUTATED" if permit.count == 0 else self._knowledge()
            if knowledge == "NOT_DISPATCHED":
                knowledge = "UNKNOWN"
            try:
                self._observe(rid, "STOPPED", "NOT_OBSERVED",
                              "BEFORE_HEADERS" if permit.count == 0 else "REQUEST_OUTCOME_UNRESOLVED")
            except Exception:
                return rid, None, None, Outcome(knowledge, "STOPPED", reason="EVIDENCE_UNRESOLVED")
            return rid, None, None, Outcome(knowledge, "STOPPED", reason="request outcome unresolved")
        finally:
            permit.close()

    def setup_conversation(self, profile, envelope, *, binding_id):
        rid, status, body, failed = self._dispatch(profile, envelope, "SETUP", None,
            "SETUP", "/v1/conversations", b"{}")
        if failed:
            return failed
        if status != 200 or type(body) is not dict or not str(body.get("id", "")).startswith("conv_"):
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "SETUP_UNRESOLVED")
            return Outcome("UNKNOWN", "STOPPED")
        try:
            cid = _identifier(body["id"])
            binding = TargetBinding(binding_id, 1, profile.organization, profile.project, cid,
                _digest({"setup_reservation": rid, "conversation_id": cid,
                         "organization": profile.organization, "project": profile.project}),
                profile.credential_ref, profile.credential_version)
            self._evidence(rid, "SETUP_ID_OBSERVED")
            self.store.bind_target(binding)
            return Outcome("NOT_DISPATCHED", "STOPPED", stages=("SETUP_ID_OBSERVED",), binding=binding)
        except CommitUnknown:
            return Outcome("UNKNOWN", "STOPPED", reason="setup local evidence unresolved")

    def mutate_one_item(self, profile, envelope, binding):
        if self._quarantined():
            raise Denied("quarantined fixture cannot mutate")
        rid, status, body, failed = self._dispatch(profile, envelope, "MUTATION", binding,
            "MUTATION", "/v1/conversations/" + binding.conversation_id + "/items", BODY_BYTES)
        if failed:
            return failed
        items = body.get("data", []) if type(body) is dict else []
        if not 200 <= status < 300 or type(body) is not dict or body.get("object") != "list" or type(items) is not list:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "CREATE_UNRESOLVED")
            return Outcome("UNKNOWN", "STOPPED")
        ids = tuple(i["id"] for i in items if type(i) is dict
                    and type(i.get("id")) is str and re.fullmatch(r"msg_[A-Za-z0-9_-]{1,120}", i["id"]))
        stages = ("REMOTE_REQUEST_ACCEPTED",)
        control = "STOPPED" if len(items) == 1 and len(ids) == 1 and exact_item(items[0]) else "QUARANTINED"
        try:
            self._evidence(rid, "REMOTE_REQUEST_ACCEPTED", control=control)
            if ids:
                self._evidence(rid, "REMOTE_ITEM_CREATED", ids, control=control)
                stages += ("REMOTE_ITEM_CREATED",)
            return Outcome("KNOWN_MUTATED" if ids else "UNKNOWN", control, stages=stages, item_ids=ids)
        except (CommitUnknown, StoreBlocked):
            return Outcome("KNOWN_MUTATED" if ids else "UNKNOWN", "STOPPED",
                           stages=stages, item_ids=ids, reason="local receipt persistence unresolved")

    def _read_once(self, profile, envelope, binding, *, item_id=None, after=None):
        if after != profile.read_after or (item_id is not None and profile.read_after is not None):
            raise Denied("READ_CURSOR_SCOPE")
        if item_id is not None:
            _identifier(item_id)
            if item_id not in set(profile.item_ids) | self._known_items():
                raise Denied("read item outside pinned scope")
            path = "/v1/conversations/" + binding.conversation_id + "/items/" + item_id
        else:
            path = "/v1/conversations/" + binding.conversation_id + "/items?limit=100&order=asc"
            if after is not None:
                _identifier(after)
                path += "&after=" + after
        rid, status, body, failed = self._dispatch(profile, envelope, "READ_RECONCILIATION",
                                                   binding, "READ", path)
        if failed:
            return Outcome(self._knowledge(), failed.control, reason=failed.reason)
        if status == 404:
            self._observe(rid, "STOPPED", "UNAVAILABLE", "ITEM_ABSENT" if item_id else "TARGET_UNAVAILABLE")
            return Outcome(self._knowledge(), "STOPPED", "UNAVAILABLE")
        if status != 200:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "READ_UNRESOLVED")
            return Outcome(self._knowledge(), "STOPPED")
        if item_id is not None:
            candidates = [body] if exact_item(body, item_id) else []
            conflict = not candidates
        else:
            data = body.get("data") if type(body) is dict else None
            if type(data) is not list or len(data) > 100 or type(body.get("has_more")) is not bool:
                self._observe(rid, "QUARANTINED", "NOT_OBSERVED", "LIST_SHAPE_INVALID")
                return Outcome(self._knowledge(), "QUARANTINED")
            candidates = [i for i in data if exact_item(i)]
            conflict = len(candidates) > 1
        if conflict:
            self._observe(rid, "QUARANTINED", "PRESENT", "READ_CONFLICT")
            return Outcome(self._knowledge(), "QUARANTINED", "PRESENT")
        if not candidates:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "ZERO_MATCHES")
            return Outcome(self._knowledge(), "STOPPED")
        ids = (candidates[0]["id"],)
        state = self.store.verify()
        mutation = [r for r in state["reservations"].values() if r["operation"] == "MUTATION"]
        attributable = len(mutation) == 1 and (
            mutation[0]["binding"] == profile.binding_digest
            and mutation[0]["generation"] == profile.generation
            and mutation[0]["submission_id"] == profile.submission_id
            and mutation[0]["delivery_id"] == profile.delivery_id)
        if not attributable:
            self._observe(rid, "STOPPED", "PRESENT", "UNATTRIBUTED_CONTEXT")
            return Outcome(self._knowledge(), "STOPPED", "PRESENT",
                           reason="observation not correlated to mutation reservation")
        known = self._known_items()
        if known and ids[0] not in known:
            self._observe(rid, "QUARANTINED", "PRESENT", "ITEM_ID_CONFLICT")
            return Outcome(self._knowledge(), "QUARANTINED", "PRESENT")
        if item_id is None and body.get("has_more") is True:
            self._evidence(rid, "REMOTE_ITEM_READBACK_VERIFIED", ids)
            return Outcome("KNOWN_MUTATED", "STOPPED", "PRESENT",
                           ("REMOTE_ITEM_READBACK_VERIFIED",), ids, "enumeration incomplete")
        if self._quarantined():
            self._observe(rid, "QUARANTINED", "PRESENT", "PRIOR_CONFLICT_PRESERVED")
            return Outcome(self._knowledge(), "QUARANTINED", "PRESENT", item_ids=ids)
        try:
            self._evidence(rid, "REMOTE_ITEM_READBACK_VERIFIED", ids)
            self._evidence(rid, "REMOTE_CONTEXT_MUTATION_CONFIRMED", ids)
            return Outcome("KNOWN_MUTATED", "STOPPED", "PRESENT",
                ("REMOTE_ITEM_READBACK_VERIFIED", "REMOTE_CONTEXT_MUTATION_CONFIRMED"), ids)
        except (CommitUnknown, StoreBlocked):
            return Outcome("KNOWN_MUTATED", "STOPPED", "PRESENT",
                           ("REMOTE_ITEM_READBACK_VERIFIED",), ids,
                           "local confirmation acknowledgement unresolved")

    def _dispose_once(self, profile, envelope, binding, *, item_id=None, container=False, rollback=False):
        if rollback or type(container) is not bool or (container and item_id is not None):
            raise Denied("disposal cannot roll back history")
        state = self.store.verify()
        confirmed = any(r["stage"] == "REMOTE_CONTEXT_MUTATION_CONFIRMED" for r in state["receipts"])
        if not confirmed or self._quarantined():
            raise Denied("disposal unresolved; no scope expansion")
        if container:
            if not profile.allow_container_delete or not any(
                    o["error_class"] == "ITEM_ABSENT"
                    and state["reservations"][o["reservation_id"]]["path"] in {
                        "/v1/conversations/" + binding.conversation_id + "/items/" + i
                        for r in state["receipts"] if r["stage"] == "ITEM_DELETE_ACK"
                        for i in r["item_ids"]}
                    for o in state["observations"]) or not any(
                    r["stage"] == "ITEM_DELETE_ACK" for r in state["receipts"]):
                raise Denied("container disposal preconditions unresolved")
            operation = "DELETE_CONTAINER"
            path = "/v1/conversations/" + binding.conversation_id
        else:
            _identifier(item_id)
            if item_id not in profile.item_ids or item_id not in self._known_items():
                raise Denied("delete item outside approved known set")
            operation = "DELETE_ITEM"
            path = "/v1/conversations/" + binding.conversation_id + "/items/" + item_id
        rid, status, body, failed = self._dispatch(profile, envelope, "DISPOSAL",
                                                  binding, operation, path)
        if failed:
            return Outcome(self._knowledge(), "STOPPED", reason="DISPOSAL_UNRESOLVED")
        matches = status == 200 and type(body) is dict and body.get("id") == binding.conversation_id
        if container:
            matches = matches and body.get("deleted") is True
        if not matches:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "DISPOSAL_UNRESOLVED")
            return Outcome(self._knowledge(), "STOPPED", reason="DISPOSAL_UNRESOLVED")
        self._evidence(rid, "CONTAINER_DELETE_ACK" if container else "ITEM_DELETE_ACK", () if container else (item_id,))
        if container:
            self.store.append("TOMBSTONE", {"binding": binding.digest,
                "container_deleted": True, "item_purge_proven": False,
                "history_preserved": True})
        return Outcome(self._knowledge(), "STOPPED",
                       reason="CONTAINER_DELETED_ITEMS_NOT_PURGED" if container else "DISPOSAL_UNRESOLVED")


    def list_items_once(self, profile, envelope, binding, *, after=None):
        return self._read_once(profile, envelope, binding, after=after)

    def retrieve_item_once(self, profile, envelope, binding, *, item_id):
        return self._read_once(profile, envelope, binding, item_id=item_id)

    def delete_item_once(self, profile, envelope, binding, *, item_id):
        return self._dispose_once(profile, envelope, binding, item_id=item_id)

    def delete_container_once(self, profile, envelope, binding):
        return self._dispose_once(profile, envelope, binding, container=True)

if __name__ == "__main__":
    raise SystemExit("Use only the bound launcher; no standalone adapter execution.")

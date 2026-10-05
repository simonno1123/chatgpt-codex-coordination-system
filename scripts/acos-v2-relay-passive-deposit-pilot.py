"""D-08 isolated PASSIVE_DEPOSIT pilot; transport observations, no authority.

Explicit fresh /2 fixtures only. No /1 migration, network, commands, agents,
context injection, scheduler, automatic retry or production authentication.
The canonical sibling /1 module owns artifact/identity semantics unchanged.
One logical CoordinationJournalWriter owns the journal and its derived view.
Reader/Recorder are cooperative Python custody boundaries, not hostile-process
isolation. Digests, fixture permits and receipts confer no governance rights.
SQLite atomicity ends before the local sink effect; UNKNOWN is resolved through
read-only stable-request lookup, never inferred from missing receipts or expiry.
"""

from contextlib import contextmanager
from dataclasses import dataclass, replace
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


_canonical_source = Path(__file__).resolve().with_name("acos-v2-coordination.py")
_spec = importlib.util.spec_from_file_location("acos_v2_relay_canonical_v0", _canonical_source)
v0 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = v0
_spec.loader.exec_module(v0)

STORE_FORMAT = "acos-v2-coordination/2"
STORE_SCHEMA_VERSION = 2
ARTIFACT_SCHEMA_VERSION = 1
RELAY_FACT_SCHEMA_VERSION = 1
PASSIVE_DEPOSIT = "PASSIVE_DEPOSIT"
ASSURANCE = v0.ASSURANCE
BOUNDARY = dict(v0.BOUNDARY, pilot="ISOLATED_LOCAL_NON_AGENT",
                effects=[PASSIVE_DEPOSIT], production_effect=False,
                delivery_semantics="LOCAL_PASSIVE_DEPOSIT_OBSERVATION")
FACT_KINDS = (
    "BINDING_CREATED", "BINDING_REVOKED", "ARTIFACT_PUBLISHED",
    "DELIVERY_BOUND", "ATTEMPT_PREPARED", "DISPATCH_INTENT",
    "OUTCOME_RECORDED", "RECEIPT_RECORDED", "RECONCILIATION_RECORDED",
    "RETRY_SCHEDULED", "RECEIPT_CONFLICT_QUARANTINED", "OWNERSHIP_EXPIRED",
)
STATES = ("READY", "KNOWN_NOT_DELIVERED", "UNKNOWN", "KNOWN_DELIVERED", "QUARANTINED")
RECEIPT_FIELDS = frozenset((
    "artifact_id", "delivery_id", "envelope_digest", "recipient_json",
    "recipient_digest", "binding_id", "generation", "relay_attempt_id",
    "stable_adapter_request_id", "endpoint_receipt_id",
    "semantic_effect_request_digest", "effect_class", "reporting_principal",
    "assurance", "authority", "receipt_stage",
))


class Rejected(ValueError):
    """Known rejection; does not authorize a send or retry."""


class ScopeDenied(Rejected):
    pass


class StoreBlocked(RuntimeError):
    """Preserve incompatible or unverifiable files; never repair."""


class OutcomeUnknown(StoreBlocked):
    """Commit acknowledgment unresolved; no dependent sink effect."""


class ReceiptConflict(Rejected):
    """Well-formed conflicting evidence was durably quarantined."""

    def __init__(self, message, original_fact=None):
        super().__init__(message)
        self.original_fact = _copy(original_fact) if original_fact is not None else None


class SinkRejected(Rejected):
    """Positive synchronous rejection before any fixture sink effect."""


def _text(value, name):
    try:
        v0._text(value, name)
        return value
    except v0.ArtifactRejected as exc:
        raise Rejected(str(exc)) from exc


def _positive(value, name):
    if type(value) is not int or not 1 <= value <= 1000000:
        raise Rejected(name + " must be a bounded positive integer")
    return value


def _json(value):
    try:
        return v0.canonical(value)
    except v0.ArtifactRejected as exc:
        raise Rejected(str(exc)) from exc


def _copy(value):
    return v0.strict_json(_json(value))


def _exact(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise Rejected("unexpected fields")


def _identity(value):
    try:
        return v0.LocalIdentity.from_dict(value)
    except (v0.ArtifactRejected, TypeError) as exc:
        raise Rejected("invalid complete identity") from exc


def _artifact(value):
    try:
        return v0.CoordinationArtifact.from_json(value)
    except (v0.ArtifactRejected, TypeError) as exc:
        raise Rejected("invalid canonical artifact") from exc


def _binding_key(binding_id, generation):
    return _text(binding_id, "binding_id") + ":" + str(_positive(generation, "generation"))


def _empty(project_id):
    return dict(format=STORE_FORMAT, schema_version=STORE_SCHEMA_VERSION,
                project_id=project_id, boundary=BOUNDARY, bindings={}, artifacts={},
                deliveries={}, attempts={}, facts={})


@dataclass(frozen=True)
class ReadScope:
    project_id: str
    recipient_digest: str
    binding_id: str
    generation: int
    effects: tuple = (PASSIVE_DEPOSIT,)

    def __post_init__(self):
        _text(self.project_id, "project_id")
        _text(self.binding_id, "binding_id")
        _positive(self.generation, "generation")
        if type(self.recipient_digest) is not str or not v0.DIGEST.fullmatch(self.recipient_digest):
            raise ScopeDenied("full recipient binding digest required")
        if type(self.effects) is not tuple or self.effects != (PASSIVE_DEPOSIT,):
            raise ScopeDenied("only PASSIVE_DEPOSIT is allowed")


@dataclass(frozen=True)
class TransportPermit:
    """Local test scope descriptor, not a capability or production credential."""
    project_id: str
    binding_id: str
    generation: int
    recipient_digest: str
    expires_at: str = "2099-01-01T00:00:00Z"
    effect_class: str = PASSIVE_DEPOSIT
    max_attempts: int = 2
    allow_retry: bool = True

    def __post_init__(self):
        ReadScope(self.project_id, self.recipient_digest, self.binding_id, self.generation)
        try:
            v0._timestamp(self.expires_at)
        except v0.ArtifactRejected as exc:
            raise Rejected(str(exc)) from exc
        if self.effect_class != PASSIVE_DEPOSIT:
            raise Rejected("effect class denied")
        _positive(self.max_attempts, "max_attempts")
        if type(self.allow_retry) is not bool:
            raise Rejected("invalid retry flag")

    def to_dict(self):
        return dict(project_id=self.project_id, binding_id=self.binding_id,
                    generation=self.generation, recipient_digest=self.recipient_digest,
                    expires_at=self.expires_at, effect_class=self.effect_class,
                    max_attempts=self.max_attempts, allow_retry=self.allow_retry)


@dataclass(frozen=True)
class DeliverySnapshot:
    project_id: str
    delivery_id: str
    artifact_id: str
    envelope_json: str
    envelope_digest: str
    publisher_json: str
    recipient_json: str
    recipient_digest: str
    binding_id: str
    generation: int
    revision: int
    semantic_effect_request_digest: str
    stable_adapter_request_id: str
    state: str
    attempt_ids: tuple
    effect_class: str = PASSIVE_DEPOSIT
    assurance: str = ASSURANCE
    authority: str = "NONE"
    dispatch_committed_now: bool = False

    @property
    def artifact(self):
        return _artifact(self.envelope_json)


def _snapshot(state, delivery_id):
    d = state["deliveries"][delivery_id]
    if not d["binding_id"]:
        raise Rejected("explicit endpoint binding required")
    return DeliverySnapshot(state["project_id"], delivery_id, d["artifact_id"],
                            d["envelope_json"], d["envelope_digest"], d["publisher_json"],
                            d["recipient_json"], d["recipient_digest"], d["binding_id"],
                            d["generation"], d["revision"], d["semantic_effect_request_digest"],
                            d["stable_adapter_request_id"], d["state"], tuple(d["attempt_ids"]))


def _semantic(d):
    return v0.digest(dict(artifact_id=d["artifact_id"], delivery_id=d["delivery_id"],
                         envelope_json=d["envelope_json"], envelope_digest=d["envelope_digest"],
                         recipient_json=d["recipient_json"], binding_id=d["binding_id"],
                         generation=d["generation"], effect_class=PASSIVE_DEPOSIT))


def _stable(d):
    return "request:" + v0.digest(dict(delivery_id=d["delivery_id"], binding_id=d["binding_id"],
                                    generation=d["generation"], effect_class=PASSIVE_DEPOSIT,
                                    semantic_effect_request_digest=_semantic(d))).split(":")[1]


def _scope_delivery(state, scope, delivery_id):
    _scope_state(state, scope)
    d = state["deliveries"].get(delivery_id)
    if (scope.project_id != state["project_id"] or d is None or
            d["recipient_digest"] != scope.recipient_digest or
            d["binding_id"] != scope.binding_id or d["generation"] != scope.generation):
        raise ScopeDenied("scoped delivery not found")
    return d


def _scope_state(state, scope):
    if type(scope) is not ReadScope or scope.project_id != state["project_id"] or scope.effects != (PASSIVE_DEPOSIT,):
        raise ScopeDenied("reader/recorder project or effect scope mismatch")
    b = state["bindings"].get(_binding_key(scope.binding_id, scope.generation))
    if not b or b["recipient_digest"] != scope.recipient_digest:
        raise ScopeDenied("full recipient endpoint binding scope mismatch")


def _active(state, d):
    b = state["bindings"].get(_binding_key(d["binding_id"], d["generation"]))
    if (not b or b["revoked"] or b["superseded"] or
            b["recipient_digest"] != d["recipient_digest"]):
        raise Rejected("binding is not active")
    if not d["owner_active"]:
        raise Rejected("ownership expired")


def _permit(state, d, raw, observed_at, retry=False):
    _exact(raw, TransportPermit.__dataclass_fields__)
    p = TransportPermit(**raw)
    if (p.project_id != state["project_id"] or p.binding_id != d["binding_id"] or
            p.generation != d["generation"] or p.recipient_digest != d["recipient_digest"]):
        raise ScopeDenied("permit tuple mismatch")
    if p.expires_at <= observed_at:
        raise Rejected("permit expired")
    _active(state, d)
    if retry and (not p.allow_retry or d["state"] != "KNOWN_NOT_DELIVERED" or
                  d["failure_reason"] != "LOCAL_SINK_PRE_EFFECT_REJECTION" or
                  d["unresolved"] or d["receipt"] or d["quarantine"] or
                  len(d["attempt_ids"]) >= p.max_attempts):
        raise Rejected("full safe retry predicate not satisfied")
    return p


def _receipt(state, d, attempt_id, receipt):
    _exact(receipt, RECEIPT_FIELDS)
    a = state["attempts"].get(attempt_id)
    if not a or a["delivery_id"] != d["delivery_id"] or not a["intent"]:
        raise Rejected("receipt requires its historical durable intent")
    original_attempt = state["attempts"].get(receipt["relay_attempt_id"])
    if (not original_attempt or original_attempt["delivery_id"] != d["delivery_id"] or
            not original_attempt["intent"]):
        raise Rejected("receipt attempt mismatch")
    expected = dict(artifact_id=d["artifact_id"], delivery_id=d["delivery_id"],
                    envelope_digest=d["envelope_digest"], recipient_json=d["recipient_json"],
                    recipient_digest=d["recipient_digest"], binding_id=d["binding_id"],
                    generation=d["generation"], stable_adapter_request_id=d["stable_adapter_request_id"],
                    semantic_effect_request_digest=d["semantic_effect_request_digest"],
                    effect_class=PASSIVE_DEPOSIT, reporting_principal="local-passive-sink",
                    assurance=ASSURANCE, authority="NONE", receipt_stage="ENDPOINT_CONTENT_ACCEPTED")
    if any(receipt[k] != val for k, val in expected.items()):
        raise Rejected("protected receipt tuple mismatch")
    _text(receipt["relay_attempt_id"], "relay_attempt_id")
    _text(receipt["endpoint_receipt_id"], "endpoint_receipt_id")
    if type(receipt["generation"]) is not int:
        raise Rejected("invalid receipt generation")
    return _copy(receipt)


def _receipt_conflict(state, d, receipt):
    if d["quarantine"]:
        return True
    if d["receipt"] is not None and d["receipt"] != receipt:
        return True
    original_attempt = state["attempts"].get(receipt["relay_attempt_id"])
    if original_attempt and original_attempt["outcome"] == "KNOWN_NOT_DELIVERED":
        return True  # Preserve contradiction to an earlier positive pre-effect rejection.
    return any(other is not d and other["receipt"] is not None and
               other["receipt"]["endpoint_receipt_id"] == receipt["endpoint_receipt_id"]
               for other in state["deliveries"].values())


def _apply(state, kind, body, seq, recorded_at):
    """Deterministic closed reducer shared by writes and full journal verification."""
    if kind not in FACT_KINDS:
        raise Rejected("unknown fact kind")
    _exact(body, ("fact_id", "fact_schema_version", "reporting_principal", "data"))
    fid = _text(body["fact_id"], "fact_id")
    _text(body["reporting_principal"], "reporting_principal")
    if type(body["fact_schema_version"]) is not int or body["fact_schema_version"] != 1:
        raise Rejected("fact schema mismatch")
    if fid in state["facts"]:
        raise Rejected("duplicate journal fact id")
    data = body["data"]
    admin = kind in ("BINDING_CREATED", "BINDING_REVOKED", "ARTIFACT_PUBLISHED", "DELIVERY_BOUND", "OWNERSHIP_EXPIRED")
    if admin and body["reporting_principal"] != "fixture-custodian":
        raise Rejected("custodian-only fact")
    if not admin and body["reporting_principal"] != "fixture-relay":
        raise Rejected("unregistered local transport reporter")
    delivery_id = data.get("delivery_id") if type(data) is dict else None
    d = state["deliveries"].get(delivery_id)
    if kind == "BINDING_CREATED":
        _exact(data, ("binding_id", "generation", "recipient_json", "effect_class", "endpoint_class"))
        if data["effect_class"] != PASSIVE_DEPOSIT or data["endpoint_class"] != "LOCAL_NON_AGENT_FIXTURE":
            raise Rejected("endpoint/effect denied")
        ident = _identity(v0.strict_json(data["recipient_json"]))
        if ident.to_dict() != v0.strict_json(data["recipient_json"]):
            raise Rejected("identity not exact")
        key = _binding_key(data["binding_id"], data["generation"])
        previous = [b for b in state["bindings"].values() if b["binding_id"] == data["binding_id"]]
        if key in state["bindings"] or (previous and data["generation"] <= max(b["generation"] for b in previous)):
            raise Rejected("binding generation must be new and increasing")
        for b in previous:
            b["superseded"] = True
        state["bindings"][key] = dict(data, recipient_digest=v0.digest(ident.to_dict()), revoked=False, superseded=False)
    elif kind == "BINDING_REVOKED":
        _exact(data, ("binding_id", "generation"))
        b = state["bindings"].get(_binding_key(data["binding_id"], data["generation"]))
        if not b or b["revoked"]:
            raise Rejected("missing or already revoked binding")
        b["revoked"] = True
    elif kind == "ARTIFACT_PUBLISHED":
        _exact(data, ("envelope_json", "publisher_json", "recipient_json", "delivery_id"))
        artifact = _artifact(data["envelope_json"])
        publisher = _identity(v0.strict_json(data["publisher_json"]))
        recipient = _identity(v0.strict_json(data["recipient_json"]))
        if (artifact.to_json() != data["envelope_json"] or
                _json(publisher.to_dict()) != data["publisher_json"] or
                _json(recipient.to_dict()) != data["recipient_json"]):
            raise Rejected("canonical envelope required")
        try:
            v0._routing(artifact, publisher, recipient, state["project_id"])
        except v0.ArtifactRejected as exc:
            raise Rejected(str(exc)) from exc
        if artifact.artifact_id in state["artifacts"] or data["delivery_id"] != v0._delivery_id(artifact, recipient):
            raise Rejected("immutable publication conflict")
        state["artifacts"][artifact.artifact_id] = artifact.to_json()
        d = dict(data, artifact_id=artifact.artifact_id, envelope_digest=artifact.envelope_digest,
                 recipient_digest=v0.digest(recipient.to_dict()), binding_id=None, generation=None,
                 semantic_effect_request_digest=None, stable_adapter_request_id=None, state="READY",
                 attempt_ids=[], receipt=None, quarantine=[], failure_reason=None, retry_scheduled=False,
                 owner_active=True, unresolved=False, late_receipt=False)
        state["deliveries"][delivery_id] = d
    elif kind == "DELIVERY_BOUND":
        _exact(data, ("delivery_id", "binding_id", "generation"))
        if not d or d["binding_id"]:
            raise Rejected("delivery tuple is immutable")
        b = state["bindings"].get(_binding_key(data["binding_id"], data["generation"]))
        if not b or b["revoked"] or b["superseded"] or b["recipient_digest"] != d["recipient_digest"]:
            raise Rejected("explicit matching active binding required")
        d["binding_id"], d["generation"] = data["binding_id"], data["generation"]
        d["semantic_effect_request_digest"], d["stable_adapter_request_id"] = _semantic(d), _stable(d)
    elif kind in ("ATTEMPT_PREPARED", "DISPATCH_INTENT"):
        _exact(data, ("delivery_id", "relay_attempt_id", "expected_revision", "permit", "observed_at"))
        if not d or not d["binding_id"]:
            raise Rejected("explicit endpoint binding required")
        _text(data["relay_attempt_id"], "relay_attempt_id")
        v0._timestamp(data["observed_at"])
        if data["observed_at"] > recorded_at:
            raise Rejected("future permit check")
        if type(data["expected_revision"]) is not int or data["expected_revision"] != d["revision"]:
            raise Rejected("stale delivery revision")
        p = _permit(state, d, data["permit"], data["observed_at"])
        aid = data["relay_attempt_id"]
        if kind == "ATTEMPT_PREPARED":
            if (aid in state["attempts"] or d["state"] not in ("READY", "KNOWN_NOT_DELIVERED") or
                    d["unresolved"] or any(state["attempts"][i]["active"] for i in d["attempt_ids"])):
                raise Rejected("concurrent, reused or unresolved attempt")
            if d["attempt_ids"]:
                _permit(state, d, data["permit"], data["observed_at"], retry=True)
                if not d["retry_scheduled"]:
                    raise Rejected("explicit retry scheduling required")
            if len(d["attempt_ids"]) >= p.max_attempts:
                raise Rejected("attempt bound exhausted")
            state["attempts"][aid] = dict(delivery_id=delivery_id, intent=False, active=True, outcome=None)
            d["attempt_ids"].append(aid)
            d["retry_scheduled"] = False
        else:
            a = state["attempts"].get(aid)
            if (d["state"] not in ("READY", "KNOWN_NOT_DELIVERED") or d["unresolved"] or
                    d["receipt"] or d["quarantine"] or len(d["attempt_ids"]) > p.max_attempts):
                raise Rejected("dispatch blocked by current delivery evidence")
            if (d["state"] == "KNOWN_NOT_DELIVERED" and
                    (not p.allow_retry or d["failure_reason"] != "LOCAL_SINK_PRE_EFFECT_REJECTION")):
                raise Rejected("retry dispatch predicate no longer satisfied")
            if not a or a["delivery_id"] != delivery_id or not a["active"] or a["intent"]:
                raise Rejected("fresh prepared attempt required")
            a["intent"] = True
            d["state"], d["unresolved"] = "UNKNOWN", True
    elif kind in ("OUTCOME_RECORDED", "RECONCILIATION_RECORDED"):
        _exact(data, ("delivery_id", "relay_attempt_id", "outcome", "reason", "receipt"))
        if not d:
            raise Rejected("missing delivery")
        a = state["attempts"].get(data["relay_attempt_id"])
        if not a or a["delivery_id"] != delivery_id or not a["intent"]:
            raise Rejected("outcome requires durable intent")
        outcome = data["outcome"]
        if kind == "OUTCOME_RECORDED":
            if outcome not in ("KNOWN_NOT_DELIVERED", "UNKNOWN") or data["receipt"] is not None:
                raise Rejected("unsupported outcome")
            if d["receipt"] or d["quarantine"] or a["outcome"] == "KNOWN_DELIVERED":
                raise Rejected("cannot downgrade observed receipt")
            if (outcome == "KNOWN_NOT_DELIVERED" and
                    (data["reason"] != "LOCAL_SINK_PRE_EFFECT_REJECTION" or a["outcome"] is not None)):
                raise Rejected("positive pre-effect rejection required")
            if outcome == "UNKNOWN" and data["reason"] != "LOCAL_SINK_OUTCOME_UNRESOLVED":
                raise Rejected("invalid unknown reason")
            a["active"], a["outcome"] = False, outcome
            d["state"], d["unresolved"] = outcome, outcome == "UNKNOWN"
            d["failure_reason"] = data["reason"]
        else:
            if data["reason"] != "STABLE_REQUEST_LOOKUP" or outcome not in ("UNKNOWN", "KNOWN_DELIVERED"):
                raise Rejected("invalid reconciliation")
            if outcome == "UNKNOWN":
                if data["receipt"] is not None or d["receipt"] or d["quarantine"]:
                    raise Rejected("cannot downgrade receipt")
                d["state"], d["unresolved"] = "UNKNOWN", True
                a["active"], a["outcome"] = False, "UNKNOWN"
            else:
                rec = _receipt(state, d, data["relay_attempt_id"], data["receipt"])
                _accept_receipt(state, d, a, rec)
    elif kind in ("RECEIPT_RECORDED", "RECEIPT_CONFLICT_QUARANTINED"):
        _exact(data, ("delivery_id", "relay_attempt_id", "receipt"))
        if not d:
            raise Rejected("missing delivery")
        rec = _receipt(state, d, data["relay_attempt_id"], data["receipt"])
        a = state["attempts"][data["relay_attempt_id"]]
        if kind == "RECEIPT_CONFLICT_QUARANTINED":
            if not _receipt_conflict(state, d, rec):
                raise Rejected("no well-formed receipt conflict")
            d["quarantine"].append(rec)
            d["state"], d["unresolved"], d["retry_scheduled"] = "QUARANTINED", True, False
            for aid in d["attempt_ids"]:
                state["attempts"][aid]["active"] = False
        else:
            _accept_receipt(state, d, a, rec)
    elif kind == "RETRY_SCHEDULED":
        _exact(data, ("delivery_id", "permit", "observed_at"))
        if not d:
            raise Rejected("missing delivery")
        v0._timestamp(data["observed_at"])
        if data["observed_at"] > recorded_at:
            raise Rejected("future permit check")
        _permit(state, d, data["permit"], data["observed_at"], retry=True)
        if d["retry_scheduled"] or any(state["attempts"][i]["active"] for i in d["attempt_ids"]):
            raise Rejected("pending attempt/retry")
        d["retry_scheduled"] = True
    elif kind == "OWNERSHIP_EXPIRED":
        _exact(data, ("delivery_id",))
        if not d or not d["owner_active"]:
            raise Rejected("missing or already expired ownership")
        d["owner_active"] = False
    if d is not None:
        d["revision"] = seq
    state["facts"][fid] = dict(kind=kind, body=body, seq=seq, delivery_id=delivery_id)


def _accept_receipt(state, d, a, receipt):
    if d["quarantine"] or _receipt_conflict(state, d, receipt):
        raise ReceiptConflict("existing evidence conflicts")
    # Receipt identities cannot move across deliveries, even within a fixture.
    for other in state["deliveries"].values():
        if (other is not d and other["receipt"] and
                other["receipt"]["endpoint_receipt_id"] == receipt["endpoint_receipt_id"]):
            raise Rejected("receipt identity already used by another delivery")
    d["receipt"], d["state"], d["unresolved"] = receipt, "KNOWN_DELIVERED", False
    d["failure_reason"], d["retry_scheduled"] = None, False
    b = state["bindings"][_binding_key(d["binding_id"], d["generation"])]
    d["late_receipt"] = b["revoked"] or b["superseded"] or not d["owner_active"]
    for aid in d["attempt_ids"]:
        state["attempts"][aid]["active"] = False
    a["outcome"] = "KNOWN_DELIVERED"


SCHEMA = (
    "CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE coordination_events (seq INTEGER PRIMARY KEY CHECK(seq>0), kind TEXT NOT NULL CHECK(kind IN (" +
    ",".join("'" + k + "'" for k in FACT_KINDS) + ")), recorded_at TEXT NOT NULL, body_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE)",
    "CREATE TABLE transport_projection (singleton INTEGER PRIMARY KEY CHECK(singleton=1), body_json TEXT NOT NULL)",
    "CREATE TRIGGER events_no_update BEFORE UPDATE ON coordination_events BEGIN SELECT RAISE(ABORT,'append only'); END",
    "CREATE TRIGGER events_no_delete BEFORE DELETE ON coordination_events BEGIN SELECT RAISE(ABORT,'append only'); END",
    "CREATE TRIGGER events_no_replace BEFORE INSERT ON coordination_events WHEN EXISTS(SELECT 1 FROM coordination_events WHERE seq=NEW.seq OR event_hash=NEW.event_hash) BEGIN SELECT RAISE(ABORT,'append only'); END",
    "CREATE TRIGGER meta_no_update BEFORE UPDATE ON store_meta BEGIN SELECT RAISE(ABORT,'immutable'); END",
    "CREATE TRIGGER meta_no_delete BEFORE DELETE ON store_meta BEGIN SELECT RAISE(ABORT,'immutable'); END",
    "CREATE TRIGGER meta_no_replace BEFORE INSERT ON store_meta WHEN EXISTS(SELECT 1 FROM store_meta WHERE key=NEW.key) BEGIN SELECT RAISE(ABORT,'immutable'); END",
)


def _metadata(project_id):
    return dict(format=STORE_FORMAT, project_id=project_id, artifact_schema_version="1",
                relay_fact_schema_version="1", fixture="ISOLATED_LOCAL_NON_AGENT",
                authority="NONE", authentication="NOT PRODUCTION AUTHENTICATED")


class CoordinationJournalWriter:
    """Private custodian-owned writer; only closed transport requests reach it."""
    def __init__(self, path, project_id):
        self._path, self._project_id = Path(path).absolute(), _text(project_id, "project_id")

    @contextmanager
    def _connection(self, write=False):
        if not self._path.is_file() or self._path.is_symlink():
            raise StoreBlocked("explicit regular fixture initialization required")
        conn = None
        try:
            mode = "rw" if write else "ro"
            conn = sqlite3.connect(self._path.as_uri() + "?mode=" + mode, uri=True,
                                   timeout=1, isolation_level=None)
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=1000")
            conn.execute("PRAGMA synchronous=FULL")
            if not write:
                conn.execute("PRAGMA query_only=ON")
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
        except (sqlite3.Error, OSError) as exc:
            raise StoreBlocked("fixture SQLite unavailable; preserve") from exc
        finally:
            if conn is not None:
                if conn.in_transaction:
                    conn.rollback()
                conn.close()

    def _verify(self, conn):
        try:
            if (conn.execute("PRAGMA user_version").fetchone()[0] != STORE_SCHEMA_VERSION or
                    conn.execute("PRAGMA application_id").fetchone()[0] != v0.APPLICATION_ID or
                    conn.execute("PRAGMA journal_mode").fetchone()[0] != "delete"):
                raise StoreBlocked("not an isolated /2 store")
            actual = {r[0] for r in conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")}
            if actual != set(SCHEMA):
                raise StoreBlocked("schema manifest mismatch")
            if dict(conn.execute("SELECT key,value FROM store_meta")) != _metadata(self._project_id):
                raise StoreBlocked("metadata/project mismatch")
            if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or conn.execute("PRAGMA foreign_key_check").fetchall():
                raise StoreBlocked("integrity failure")
            state = _empty(self._project_id)
            previous, count = v0.GENESIS_HASH, 0
            for row in conn.execute("SELECT seq,kind,recorded_at,body_json,previous_hash,event_hash FROM coordination_events ORDER BY seq"):
                event = v0.CoordinationEvent(*row)
                count += 1
                if (type(event.seq) is not int or event.seq != count or event.previous_hash != previous or
                        _json(event.body) != event.body_json or event.calculated_hash() != event.event_hash):
                    raise StoreBlocked("journal hash/sequence/canonical mismatch")
                v0._timestamp(event.recorded_at)
                _apply(state, event.kind, event.body, event.seq, event.recorded_at)
                previous = event.event_hash
            projection = conn.execute("SELECT singleton,body_json FROM transport_projection").fetchall()
            if projection != [(1, _json(state))]:
                raise StoreBlocked("projection mismatch; no repair")
            return state, count, previous
        except (Rejected, v0.ArtifactRejected, KeyError, TypeError, ValueError) as exc:
            raise StoreBlocked("semantic replay failed; preserve") from exc

    def read(self):
        with self._connection() as conn:
            return self._verify(conn)[0]

    def _commit(self, connection):
        connection.commit()

    def _append(self, kind, data, fact_id, principal, scope=None, receipt_mode=False):
        body = dict(fact_id=_text(fact_id, "fact_id"), fact_schema_version=1,
                    reporting_principal=_text(principal, "reporting_principal"), data=_copy(data))
        _json(body)
        conflict = False
        with self._connection(write=True) as conn:
            state, count, previous = self._verify(conn)
            d = None
            if scope is not None:
                d = _scope_delivery(state, scope, data["delivery_id"])
            old = state["facts"].get(fact_id)
            if old:
                if (receipt_mode and old["kind"] == "RECEIPT_CONFLICT_QUARANTINED" and old["body"] == body):
                    raise ReceiptConflict("original quarantined fact already recorded", old)
                if old["kind"] != kind or old["body"] != body:
                    raise Rejected("fact id input conflict")
                return dict(_copy(old), recorded_now=False)
            if receipt_mode:
                rec = _receipt(state, d, data["relay_attempt_id"], data["receipt"])
                if d["receipt"] == rec:
                    return dict(already_recorded=True, receipt=_copy(rec))
                if rec in d["quarantine"]:
                    original = next(f for f in state["facts"].values()
                                    if f["kind"] == "RECEIPT_CONFLICT_QUARANTINED" and
                                    f["delivery_id"] == d["delivery_id"] and f["body"]["data"]["receipt"] == rec)
                    raise ReceiptConflict("original quarantined observation already recorded", original)
                if _receipt_conflict(state, d, rec):
                    kind, conflict = "RECEIPT_CONFLICT_QUARANTINED", True
            event = v0.CoordinationEvent.create(count + 1, kind, body, previous)
            _apply(state, kind, body, event.seq, event.recorded_at)
            conn.execute("INSERT INTO coordination_events VALUES (?,?,?,?,?,?)",
                         (event.seq, event.kind, event.recorded_at, event.body_json, event.previous_hash, event.event_hash))
            conn.execute("UPDATE transport_projection SET body_json=? WHERE singleton=1", (_json(state),))
            try:
                self._commit(conn)
            except (sqlite3.Error, OSError) as exc:
                raise OutcomeUnknown("commit acknowledgment unresolved; lookup fact, do not send") from exc
            result = dict(_copy(state["facts"][fact_id]), recorded_now=True)
        if conflict:
            original = {key: value for key, value in result.items() if key != "recorded_now"}
            raise ReceiptConflict("conflicting receipt preserved/quarantined", original)
        return result


class PilotCustodian:
    def __init__(self, path, project_id):
        self._writer = CoordinationJournalWriter(path, project_id)
        self._writer.read()

    @classmethod
    def init(cls, path, project_id):
        path = Path(path).absolute()
        _text(project_id, "project_id")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError as exc:
            raise StoreBlocked("explicit init cannot overwrite/create unavailable path") from exc
        os.close(fd)
        conn = None
        try:
            conn = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA application_id=" + str(v0.APPLICATION_ID))
            conn.execute("PRAGMA user_version=2")
            conn.execute("BEGIN IMMEDIATE")
            for sql in SCHEMA:
                conn.execute(sql)
            conn.executemany("INSERT INTO store_meta VALUES (?,?)", _metadata(project_id).items())
            conn.execute("INSERT INTO transport_projection VALUES (1,?)", (_json(_empty(project_id)),))
            conn.commit()
        except (sqlite3.Error, OSError) as exc:
            raise StoreBlocked("partial initialization preserved; no rebuild") from exc
        finally:
            if conn is not None:
                conn.close()
        return cls(path, project_id)

    def publish(self, artifact, publisher, recipient, fact_id):
        artifact = _artifact(artifact.to_json())
        publisher, recipient = _identity(publisher.to_dict()), _identity(recipient.to_dict())
        did = v0._delivery_id(artifact, recipient)
        self._writer._append("ARTIFACT_PUBLISHED", dict(envelope_json=artifact.to_json(),
                             publisher_json=_json(publisher.to_dict()), recipient_json=_json(recipient.to_dict()),
                             delivery_id=did), fact_id, "fixture-custodian")
        return did

    def create_binding(self, binding_id, recipient, generation=1, fact_id=None):
        if fact_id is None:
            raise Rejected("explicit fact_id required")
        self._writer._append("BINDING_CREATED", dict(binding_id=binding_id, generation=generation,
                             recipient_json=_json(_identity(recipient.to_dict()).to_dict()),
                             effect_class=PASSIVE_DEPOSIT, endpoint_class="LOCAL_NON_AGENT_FIXTURE"),
                             fact_id, "fixture-custodian")

    def revoke_binding(self, binding_id, generation, fact_id):
        self._writer._append("BINDING_REVOKED", dict(binding_id=binding_id, generation=generation), fact_id, "fixture-custodian")

    def bind_delivery(self, delivery_id, binding_id, generation, fact_id):
        self._writer._append("DELIVERY_BOUND", dict(delivery_id=delivery_id, binding_id=binding_id,
                             generation=generation), fact_id, "fixture-custodian")

    def expire_ownership(self, delivery_id, fact_id):
        self._writer._append("OWNERSHIP_EXPIRED", dict(delivery_id=delivery_id), fact_id, "fixture-custodian")

    def _scope(self, scope):
        if not isinstance(scope, ReadScope) or scope.project_id != self._writer._project_id:
            raise ScopeDenied("scope project mismatch")
        state = self._writer.read()
        b = state["bindings"].get(_binding_key(scope.binding_id, scope.generation))
        if not b or b["recipient_digest"] != scope.recipient_digest:
            raise ScopeDenied("explicit full recipient endpoint binding required")

    def reader(self, scope):
        self._scope(scope)
        return VerifiedTransportReader(self._writer, scope)

    def recorder(self, scope, reporting_principal="fixture-relay"):
        self._scope(scope)
        if reporting_principal != "fixture-relay":
            raise ScopeDenied("fixture reporter is enrolled by custodian")
        return TransportFactRecorder(self._writer, scope, reporting_principal)


class VerifiedTransportReader:
    def __init__(self, writer, scope):
        self.__read = writer.read
        self._scope = scope

    def read_delivery(self, delivery_id):
        state = self.__read()
        _scope_delivery(state, self._scope, delivery_id)
        return _snapshot(state, delivery_id)

    def status(self):
        state = self.__read()
        _scope_state(state, self._scope)
        ids = [did for did, d in state["deliveries"].items()
               if d["recipient_digest"] == self._scope.recipient_digest and d["binding_id"] == self._scope.binding_id
               and d["generation"] == self._scope.generation]
        return _copy(dict(format=STORE_FORMAT, schema_version=2, boundary=BOUNDARY,
                          artifacts={state["deliveries"][i]["artifact_id"]: state["deliveries"][i]["envelope_json"] for i in ids},
                          deliveries={i: state["deliveries"][i] for i in ids},
                          bindings={_binding_key(self._scope.binding_id, self._scope.generation):
                                    state["bindings"][_binding_key(self._scope.binding_id, self._scope.generation)]}))

    def lookup_fact(self, fact_id):
        state = self.__read()
        _scope_state(state, self._scope)
        fact = state["facts"].get(fact_id)
        if fact is None:
            return None
        if fact["delivery_id"] is None:
            raise ScopeDenied("only scoped delivery facts are readable")
        _scope_delivery(state, self._scope, fact["delivery_id"])
        return _copy(fact)

    def read_attempt(self, relay_attempt_id):
        state = self.__read()
        _scope_state(state, self._scope)
        attempt = state["attempts"].get(relay_attempt_id)
        if attempt is None:
            raise ScopeDenied("scoped attempt not found")
        _scope_delivery(state, self._scope, attempt["delivery_id"])
        return _copy(attempt)


class TransportFactRecorder:
    def __init__(self, writer, scope, principal):
        self.__append, self.__read = writer._append, writer.read
        self._scope, self.__principal = scope, principal

    def _record(self, kind, data, fact_id, receipt_mode=False):
        return self.__append(kind, data, fact_id, self.__principal, self._scope, receipt_mode)

    def _fresh(self, delivery_id):
        state = self.__read()
        _scope_delivery(state, self._scope, delivery_id)
        return _snapshot(state, delivery_id)

    def check_current(self, delivery_id, permit, attempt_id):
        """Read-only recheck; never creates authority or permits replay of intent."""
        state = self.__read()
        d = _scope_delivery(state, self._scope, delivery_id)
        _permit(state, d, permit.to_dict(), v0._now())
        a = state["attempts"].get(attempt_id)
        if (d["state"] != "UNKNOWN" or not d["unresolved"] or d["receipt"] or d["quarantine"] or
                not a or a["delivery_id"] != delivery_id or not a["intent"] or not a["active"]):
            raise Rejected("fresh in-flight intent no longer eligible")

    def prepare(self, snapshot, attempt_id, permit, fact_id):
        self._request("ATTEMPT_PREPARED", snapshot, attempt_id, permit, fact_id)
        return self._fresh(snapshot.delivery_id)

    def dispatch(self, snapshot, attempt_id, permit, fact_id):
        result = self._request("DISPATCH_INTENT", snapshot, attempt_id, permit, fact_id)
        return replace(self._fresh(snapshot.delivery_id), dispatch_committed_now=result["recorded_now"])

    def _request(self, kind, snapshot, attempt_id, permit, fact_id):
        if type(snapshot) is not DeliverySnapshot or type(permit) is not TransportPermit:
            raise Rejected("typed snapshot/permit required")
        current = self._fresh(snapshot.delivery_id)
        # Snapshot content is evidence, not a credential. Reject altered tuples.
        for field in DeliverySnapshot.__dataclass_fields__:
            if field not in ("revision", "state", "attempt_ids", "dispatch_committed_now") and getattr(snapshot, field) != getattr(current, field):
                raise Rejected("altered immutable snapshot")
        old = self.__read()["facts"].get(fact_id)
        observed_at = old["body"]["data"]["observed_at"] if old and old["kind"] == kind else v0._now()
        return self._record(kind, dict(delivery_id=snapshot.delivery_id, relay_attempt_id=attempt_id,
                            expected_revision=snapshot.revision, permit=permit.to_dict(), observed_at=observed_at), fact_id)

    def record_receipt(self, delivery_id, attempt_id, receipt, fact_id):
        return self._record("RECEIPT_RECORDED", dict(delivery_id=delivery_id, relay_attempt_id=attempt_id,
                            receipt=receipt), fact_id, receipt_mode=True)

    def outcome(self, delivery_id, attempt_id, outcome, reason, fact_id):
        return self._record("OUTCOME_RECORDED", dict(delivery_id=delivery_id, relay_attempt_id=attempt_id,
                            outcome=outcome, reason=reason, receipt=None), fact_id)

    def reconcile(self, delivery_id, attempt_id, outcome, receipt=None, fact_id=None):
        if fact_id is None:
            raise Rejected("explicit fact_id required")
        if receipt is not None:
            # Route conflicts through the preserving/quarantine variant.
            state = self.__read()
            d = _scope_delivery(state, self._scope, delivery_id)
            rec = _receipt(state, d, attempt_id, receipt)
            if _receipt_conflict(state, d, rec):
                return self.record_receipt(delivery_id, attempt_id, rec, fact_id)
        return self._record("RECONCILIATION_RECORDED", dict(delivery_id=delivery_id, relay_attempt_id=attempt_id,
                            outcome=outcome, reason="STABLE_REQUEST_LOOKUP", receipt=receipt), fact_id)

    def schedule_retry(self, delivery_id, permit, fact_id):
        if type(permit) is not TransportPermit:
            raise Rejected("typed permit required")
        old = self.__read()["facts"].get(fact_id)
        observed_at = old["body"]["data"]["observed_at"] if old and old["kind"] == "RETRY_SCHEDULED" else v0._now()
        return self._record("RETRY_SCHEDULED", dict(delivery_id=delivery_id, permit=permit.to_dict(),
                            observed_at=observed_at), fact_id)


class LocalPassiveSink:
    """Bound isolated file fixture. Exact deposits only; no payload interpretation."""
    def __init__(self, directory, binding_id, generation, recipient_digest):
        self._directory = Path(directory).absolute()
        self._binding_id, self._generation, self._recipient_digest = binding_id, generation, recipient_digest
        ReadScope("fixture-sink", recipient_digest, binding_id, generation)
        if self._directory.is_symlink() or not self._directory.is_dir():
            raise StoreBlocked("explicit fixture sink initialization required")
        expected = dict(fixture="LOCAL_NON_AGENT_PASSIVE_SINK", binding_id=binding_id,
                        generation=generation, recipient_digest=recipient_digest, effect_class=PASSIVE_DEPOSIT)
        try:
            marker = self._directory / "fixture.json"
            if marker.is_symlink() or marker.read_text("ascii") != _json(expected):
                raise StoreBlocked("sink binding manifest mismatch")
        except OSError as exc:
            raise StoreBlocked("sink manifest unavailable") from exc

    @classmethod
    def init(cls, directory, binding_id, generation, recipient_digest):
        ReadScope("fixture-sink", recipient_digest, binding_id, generation)
        directory = Path(directory).absolute()
        try:
            directory.mkdir(mode=0o700)
            marker = dict(fixture="LOCAL_NON_AGENT_PASSIVE_SINK", binding_id=binding_id,
                          generation=generation, recipient_digest=recipient_digest, effect_class=PASSIVE_DEPOSIT)
            with (directory / "fixture.json").open("x", encoding="ascii") as stream:
                stream.write(_json(marker))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            raise StoreBlocked("cannot initialize/overwrite sink fixture") from exc
        return cls(directory, binding_id, generation, recipient_digest)

    def deposit_path(self, stable_adapter_request_id):
        if (type(stable_adapter_request_id) is not str or not stable_adapter_request_id.startswith("request:") or
                not v0.DIGEST.fullmatch("sha256:" + stable_adapter_request_id[8:])):
            raise SinkRejected("invalid stable request key")
        return self._directory / (stable_adapter_request_id[8:] + ".deposit.json")

    def _body(self, snapshot):
        if not isinstance(snapshot, DeliverySnapshot) or snapshot.effect_class != PASSIVE_DEPOSIT or snapshot.authority != "NONE":
            raise SinkRejected("only passive immutable snapshots")
        d = dict(artifact_id=snapshot.artifact_id, delivery_id=snapshot.delivery_id,
                 envelope_json=snapshot.envelope_json, envelope_digest=snapshot.envelope_digest,
                 recipient_json=snapshot.recipient_json, binding_id=snapshot.binding_id, generation=snapshot.generation)
        artifact, recipient = _artifact(snapshot.envelope_json), _identity(v0.strict_json(snapshot.recipient_json))
        if (snapshot.binding_id != self._binding_id or snapshot.generation != self._generation or
                snapshot.recipient_digest != self._recipient_digest or v0.digest(recipient.to_dict()) != snapshot.recipient_digest or
                artifact.to_json() != snapshot.envelope_json or artifact.artifact_id != snapshot.artifact_id or
                artifact.project_id != snapshot.project_id or artifact.envelope_digest != snapshot.envelope_digest or
                v0._delivery_id(artifact, recipient) != snapshot.delivery_id or
                _semantic(d) != snapshot.semantic_effect_request_digest or _stable(d) != snapshot.stable_adapter_request_id):
            raise SinkRejected("protected immutable deposit mismatch")
        return dict(d, recipient_digest=snapshot.recipient_digest, effect_class=PASSIVE_DEPOSIT,
                    stable_adapter_request_id=snapshot.stable_adapter_request_id,
                    semantic_effect_request_digest=snapshot.semantic_effect_request_digest)

    def _before_deposit(self, snapshot, relay_attempt_id):
        """Fault injection seam. SinkRejected is only valid before persistence."""

    def _read(self, path):
        if path.is_symlink():
            raise StoreBlocked("sink deposit symlink forbidden")
        try:
            text = path.read_text("ascii")
            result = v0.strict_json(text)
            _exact(result, ("deposit", "receipt"))
            _exact(result["receipt"], RECEIPT_FIELDS)
            if _json(result) != text:
                raise StoreBlocked("sink deposit not canonical")
            dep, rec = result["deposit"], result["receipt"]
            _exact(dep, ("artifact_id", "delivery_id", "envelope_json", "envelope_digest", "recipient_json",
                         "binding_id", "generation", "recipient_digest", "effect_class",
                         "stable_adapter_request_id", "semantic_effect_request_digest"))
            snap = DeliverySnapshot(_artifact(dep["envelope_json"]).project_id, dep["delivery_id"], dep["artifact_id"],
                                    dep["envelope_json"], dep["envelope_digest"], "{}", dep["recipient_json"],
                                    dep["recipient_digest"], dep["binding_id"], dep["generation"], 0,
                                    dep["semantic_effect_request_digest"], dep["stable_adapter_request_id"], "UNKNOWN", ())
            if self._body(snap) != dep:
                raise StoreBlocked("deposit tuple mismatch")
            expected = self._make_receipt(snap, rec["relay_attempt_id"])
            if rec != expected or path != self.deposit_path(dep["stable_adapter_request_id"]):
                raise StoreBlocked("sink receipt/key mismatch")
            return result
        except (OSError, Rejected, v0.ArtifactRejected, KeyError, TypeError) as exc:
            raise StoreBlocked("sink deposit unavailable/unverifiable; preserve") from exc

    def _make_receipt(self, snapshot, relay_attempt_id):
        _text(relay_attempt_id, "relay_attempt_id")
        dep = self._body(snapshot)
        rec = {k: val for k, val in dep.items() if k != "envelope_json"}
        return dict(rec, relay_attempt_id=relay_attempt_id,
                    endpoint_receipt_id="receipt:" + v0.digest(dep).split(":")[1],
                    reporting_principal="local-passive-sink", assurance=ASSURANCE, authority="NONE",
                    receipt_stage="ENDPOINT_CONTENT_ACCEPTED")

    def deposit(self, snapshot, relay_attempt_id):
        if snapshot.state != "UNKNOWN":
            raise SinkRejected("fixture deposit requires a dispatch-intent snapshot")
        dep = self._body(snapshot)
        path = self.deposit_path(snapshot.stable_adapter_request_id)
        if path.exists() or path.is_symlink():
            existing = self._read(path)
            if existing["deposit"] != dep:
                raise SinkRejected("stable request key conflict")
            return _copy(existing["receipt"])
        self._before_deposit(snapshot, relay_attempt_id)
        receipt = self._make_receipt(snapshot, relay_attempt_id)
        text = _json(dict(deposit=dep, receipt=receipt))
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=self._directory)
        try:
            with os.fdopen(fd, "w", encoding="ascii") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)  # Exclusive installation; never replaces accepted content.
            except FileExistsError:
                existing = self._read(path)
                if existing["deposit"] != dep:
                    raise SinkRejected("concurrent stable key conflict")
                return _copy(existing["receipt"])
            dir_fd = os.open(self._directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            return _copy(receipt)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def status(self, stable_adapter_request_id):
        path = self.deposit_path(stable_adapter_request_id)
        if not path.exists() and not path.is_symlink():
            return None  # Absence proves no negative outcome.
        return _copy(self._read(path)["receipt"])

    @property
    def effect_count(self):
        paths = list(self._directory.glob("*.deposit.json"))
        for path in paths:
            self._read(path)
        return len(paths)


class RelayWorker:
    """One foreground call. No background loop, retry, endpoint discovery or CLI."""
    def __init__(self, reader, recorder, sink, permit):
        if (type(reader) is not VerifiedTransportReader or type(recorder) is not TransportFactRecorder or
                type(sink) is not LocalPassiveSink or type(permit) is not TransportPermit):
            raise Rejected("closed local fixture interfaces only")
        if reader._scope != recorder._scope:
            raise ScopeDenied("reader/recorder scope mismatch")
        scope = reader._scope
        if (sink._binding_id != scope.binding_id or sink._generation != scope.generation or
                sink._recipient_digest != scope.recipient_digest):
            raise ScopeDenied("sink bound destination mismatch")
        self.reader, self.recorder, self.sink, self.permit = reader, recorder, sink, permit

    def _after_deposit(self, receipt):
        """Crash injection seam after sink acceptance, before local receipt."""

    def deliver(self, delivery_id, relay_attempt_id):
        snapshot = self.reader.read_delivery(delivery_id)
        if snapshot.state in ("KNOWN_DELIVERED", "UNKNOWN", "QUARANTINED"):
            return snapshot.state
        prepare_id, intent_id = relay_attempt_id + ":prepare", relay_attempt_id + ":intent"
        snapshot = self.recorder.prepare(snapshot, relay_attempt_id, self.permit, prepare_id)
        # Existing intent is recovery evidence, never a fresh grant to call sink.
        if self.reader.lookup_fact(intent_id) is not None:
            return "UNKNOWN"
        snapshot = self.recorder.dispatch(snapshot, relay_attempt_id, self.permit, intent_id)
        if not snapshot.dispatch_committed_now:
            return "UNKNOWN"  # Exact replay records evidence; it never grants a second sink call.
        # Recheck current binding/owner just before the one local effect. A race
        # still cannot create a cross-store atomic revocation guarantee.
        self.recorder.check_current(delivery_id, self.permit, relay_attempt_id)
        try:
            receipt = self.sink.deposit(snapshot, relay_attempt_id)
        except SinkRejected:
            self.recorder.outcome(delivery_id, relay_attempt_id, "KNOWN_NOT_DELIVERED",
                                  "LOCAL_SINK_PRE_EFFECT_REJECTION", relay_attempt_id + ":outcome")
            return "KNOWN_NOT_DELIVERED"
        except Exception:
            self.recorder.outcome(delivery_id, relay_attempt_id, "UNKNOWN",
                                  "LOCAL_SINK_OUTCOME_UNRESOLVED", relay_attempt_id + ":outcome")
            return "UNKNOWN"
        self._after_deposit(receipt)
        self.recorder.record_receipt(delivery_id, relay_attempt_id, receipt, relay_attempt_id + ":receipt")
        return "KNOWN_DELIVERED"

    def reconcile(self, delivery_id):
        snapshot = self.reader.read_delivery(delivery_id)
        if snapshot.state in ("KNOWN_DELIVERED", "QUARANTINED"):
            return snapshot.state
        intents = [i for i in snapshot.attempt_ids if self.reader.read_attempt(i)["intent"]]
        if not intents:
            raise Rejected("no durable intent to reconcile")
        attempt_id = intents[-1]
        receipt = self.sink.status(snapshot.stable_adapter_request_id)
        outcome = "KNOWN_DELIVERED" if receipt else "UNKNOWN"
        fact_id = attempt_id + ":reconcile:" + v0.digest(receipt).split(":")[1]
        self.recorder.reconcile(delivery_id, attempt_id, outcome, receipt, fact_id)
        return outcome

"""D-08: durable, NON-AUTHORITATIVE local coordination transport, format /1.

Only CoordinationJournalWriter mutates transport facts. This module neither
imports governance/capability modules nor calls agents, Git, or networks.
ACK is exact-content receipt, never acceptance, authority, or execution admission.
UNVERIFIED_LOCAL identities are caller-supplied bindings, NOT PRODUCTION
AUTHENTICATED. Roles, payload prose, hashes and reply links cannot raise trust.
Python encapsulation and journal hashes are not protection against direct file
or process control. v0 verifies the complete journal on every operation; it has
no automatic repair/migration, daemon, delivery adapter or exactly-once execution.

Local format choices: integer-only ASCII canonical JSON, UTC second timestamps,
one receiver binding per artifact, 1 MiB envelopes, bounded 1000 ms SQLite wait,
separate file named coordination.db, FULL synchronous rollback journal writes.
Expiration, authority/baseline/attempt references and dependency links are opaque
transport data; no runtime authorization or stage progression is derived.
"""

import argparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys


FORMAT = "acos-v2-coordination/1"
SCHEMA_VERSION = 1
APPLICATION_ID = 0x41434F43
ASSURANCE = "UNVERIFIED_LOCAL"
AUTHENTICATION = "NOT PRODUCTION AUTHENTICATED"
GENESIS_HASH = "sha256:" + "0" * 64
MAX_JSON_BYTES = 1024 * 1024
BUSY_TIMEOUT_MS = 1000
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
BOUNDARY = {
    "decision": "D-08", "authority": "NONE", "authentication": AUTHENTICATION,
    "ack_meaning": "EXACT_CONTENT_RECEIPT", "governance_acceptance": False,
    "execution_admission": False, "activation": "LOCKED", "operational_entry": "LOCKED",
    "redelivery_is_reexecution": False, "ack_is_acceptance": False,
    "delivery_is_authorization": False, "result_is_acceptance": False,
    "delivery_semantics": "LOCAL_AVAILABILITY",
}


class ArtifactRejected(ValueError):
    """Malformed or unsupported transport input, before any write."""


class StoreBlocked(RuntimeError):
    """Missing, damaged, incompatible or busy store. Preserve; no repair."""


class MutationOutcomeUnknown(StoreBlocked):
    """Commit acknowledgement failed. Re-read durable facts; never auto-retry."""


class PublicationConflict(ArtifactRejected):
    def __init__(self, reason, event_seq):
        super().__init__(f"{reason}; conflict quarantined at event {event_seq}")
        self.reason = reason
        self.event_seq = event_seq


def _json_value(value, depth=0):
    if depth > 64:
        raise ArtifactRejected("JSON nesting exceeds local bound")
    if value is None or type(value) in (bool, int):
        return
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ArtifactRejected("invalid Unicode scalar") from exc
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ArtifactRejected("JSON keys must be strings")
            _json_value(key, depth + 1)
            _json_value(item, depth + 1)
        return
    raise ArtifactRejected("JSON requires integer numbers and standard value types")


def canonical(value):
    _json_value(value)
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode("ascii")) > MAX_JSON_BYTES:
        raise ArtifactRejected("JSON exceeds local size bound")
    return encoded


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ArtifactRejected(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    if type(text) is not str or len(text.encode("utf-8", errors="surrogatepass")) > MAX_JSON_BYTES:
        raise ArtifactRejected("invalid JSON input or size")
    try:
        value = json.loads(text, object_pairs_hook=pairs)
        canonical(value)
        return value
    except (ValueError, RecursionError) as exc:
        raise ArtifactRejected(f"invalid JSON: {exc}") from exc


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode("ascii")).hexdigest()


def _text(value, name):
    if type(value) is not str or not value or value != value.strip() or len(value) > 512:
        raise ArtifactRejected(f"invalid {name}")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ArtifactRejected(f"control character in {name}")
    _json_value(value)


def _timestamp(value):
    if type(value) is not str or not TIMESTAMP.fullmatch(value):
        raise ArtifactRejected("timestamp requires UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ArtifactRejected("invalid calendar timestamp") from exc


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class LocalIdentity:
    """Host/store binding, distinct from artifact role labels; v0 test identity."""
    role: str
    receiver_id: str
    consumer_id: str
    principal_id: str
    conversation_id: str
    session_id: str
    assurance: str = ASSURANCE

    def __post_init__(self):
        for name, value in asdict(self).items():
            _text(value, name)
        if self.assurance != ASSURANCE:
            raise ArtifactRejected("v0 supports UNVERIFIED_LOCAL only")

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {f.name for f in fields(cls)}:
            raise ArtifactRejected("identity requires six distinct bindings and assurance")
        return cls(**value)

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class CoordinationArtifact:
    artifact_id: str
    artifact_type: str
    project_id: str
    stage_id: str
    task_id: str
    from_role: str
    to_role: str
    receiver_id: str
    correlation_id: str
    created_at: str
    payload_json: str
    metadata_json: str = "{}"
    execution_attempt_id: str | None = None
    authority_reference: str | None = None
    baseline_revision: str | None = None
    predecessor_artifact_id: str | None = None
    reply_to_artifact_id: str | None = None
    reply_to_digest: str | None = None
    expires_at: str | None = None
    delivery_policy: str = "SINGLE_RECEIVER"
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        for name in ("artifact_id", "artifact_type", "project_id", "stage_id", "task_id", "from_role",
                     "to_role", "receiver_id", "correlation_id"):
            _text(getattr(self, name), name)
        for name in ("execution_attempt_id", "authority_reference", "baseline_revision",
                     "predecessor_artifact_id", "reply_to_artifact_id"):
            value = getattr(self, name)
            if value is not None:
                _text(value, name)
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ArtifactRejected("unsupported artifact schema")
        if self.delivery_policy != "SINGLE_RECEIVER":
            raise ArtifactRejected("unsupported delivery policy")
        created = _timestamp(self.created_at)
        if self.expires_at is not None and _timestamp(self.expires_at) <= created:
            raise ArtifactRejected("expires_at must follow created_at")
        if (self.reply_to_artifact_id is None) != (self.reply_to_digest is None):
            raise ArtifactRejected("reply requires parent ID and exact envelope digest")
        if self.reply_to_digest is not None and (type(self.reply_to_digest) is not str or not DIGEST.fullmatch(self.reply_to_digest)):
            raise ArtifactRejected("invalid reply digest")
        if self.artifact_id in (self.reply_to_artifact_id, self.predecessor_artifact_id):
            raise ArtifactRejected("self relation is unsupported")
        for name in ("payload_json", "metadata_json"):
            text = getattr(self, name)
            value = strict_json(text)
            if canonical(value) != text:
                raise ArtifactRejected(f"{name} must be canonical")
            if name == "metadata_json" and type(value) is not dict:
                raise ArtifactRejected("metadata must be an object")
        canonical(self.to_dict())

    @classmethod
    def build(cls, *, payload, metadata=None, **values):
        return cls(payload_json=canonical(payload), metadata_json=canonical({} if metadata is None else metadata), **values)

    @classmethod
    def from_dict(cls, value):
        expected = ({f.name for f in fields(cls)} - {"payload_json", "metadata_json"}) | {
            "payload", "metadata", "payload_digest", "envelope_digest"}
        if type(value) is not dict or set(value) != expected:
            raise ArtifactRejected("artifact fields missing or unexpected")
        body = dict(value)
        claimed_payload = body.pop("payload_digest")
        claimed_envelope = body.pop("envelope_digest")
        artifact = cls.build(**body)
        if claimed_payload != artifact.payload_digest or claimed_envelope != artifact.envelope_digest:
            raise ArtifactRejected("artifact digest mismatch")
        return artifact

    @classmethod
    def from_json(cls, text):
        return cls.from_dict(strict_json(text))

    @property
    def payload(self):
        return strict_json(self.payload_json)

    @property
    def metadata(self):
        return strict_json(self.metadata_json)

    @property
    def payload_digest(self):
        return digest(self.payload)

    def _body(self):
        result = asdict(self)
        del result["payload_json"], result["metadata_json"]
        result.update(payload=self.payload, metadata=self.metadata, payload_digest=self.payload_digest)
        return result

    @property
    def envelope_digest(self):
        return digest(self._body())

    def to_dict(self):
        return {**self._body(), "envelope_digest": self.envelope_digest}

    def to_json(self):
        return canonical(self.to_dict())


@dataclass(frozen=True)
class CoordinationEvent:
    seq: int
    kind: str
    recorded_at: str
    body_json: str
    previous_hash: str
    event_hash: str

    @property
    def body(self):
        return strict_json(self.body_json)

    @classmethod
    def create(cls, seq, kind, body, previous_hash):
        recorded_at = _now()
        hashed = dict(seq=seq, kind=kind, recorded_at=recorded_at, body=body, previous_hash=previous_hash)
        return cls(seq, kind, recorded_at, canonical(body), previous_hash, digest(hashed))

    def calculated_hash(self):
        return digest(dict(seq=self.seq, kind=self.kind, recorded_at=self.recorded_at,
                           body=self.body, previous_hash=self.previous_hash))


@dataclass(frozen=True)
class PublishReceipt:
    artifact_id: str
    delivery_id: str
    envelope_digest: str
    event_seq: int
    event_hash: str
    publisher_binding_digest: str
    recipient_binding_digest: str
    assurance: str = ASSURANCE
    authority: str = "NONE"


@dataclass(frozen=True)
class AckReceipt:
    artifact_id: str
    delivery_id: str
    consumer_id: str
    envelope_digest: str
    event_seq: int
    event_hash: str
    consumer_binding_digest: str
    meaning: str = "EXACT_CONTENT_RECEIPT"
    authority: str = "NONE"


SCHEMA = (
    "CREATE TABLE coordination_metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1), format TEXT NOT NULL, project_id TEXT NOT NULL, assurance TEXT NOT NULL, authentication TEXT NOT NULL, boundary_json TEXT NOT NULL)",
    "CREATE TABLE coordination_events (seq INTEGER PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('PUBLISHED','ACK_RECORDED','CONFLICT_QUARANTINED')), recorded_at TEXT NOT NULL, body_json TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE)",
    "CREATE TABLE artifact_projection (artifact_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, envelope_json TEXT NOT NULL, envelope_digest TEXT NOT NULL, publisher_json TEXT NOT NULL, recipient_json TEXT NOT NULL, published_seq INTEGER NOT NULL UNIQUE REFERENCES coordination_events(seq), published_hash TEXT NOT NULL, delivery_id TEXT NOT NULL UNIQUE, reply_state TEXT NOT NULL, predecessor_state TEXT NOT NULL)",
    "CREATE TABLE delivery_projection (delivery_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL UNIQUE REFERENCES artifact_projection(artifact_id), receiver_id TEXT NOT NULL, consumer_id TEXT NOT NULL, recipient_json TEXT NOT NULL, envelope_digest TEXT NOT NULL, transport_state TEXT NOT NULL CHECK(transport_state IN ('AVAILABLE','ACKED')), ack_seq INTEGER UNIQUE REFERENCES coordination_events(seq), ack_hash TEXT)",
    "CREATE TRIGGER coordination_events_no_update BEFORE UPDATE ON coordination_events BEGIN SELECT RAISE(ABORT, 'append-only coordination events'); END",
    "CREATE TRIGGER coordination_events_no_delete BEFORE DELETE ON coordination_events BEGIN SELECT RAISE(ABORT, 'append-only coordination events'); END",
    "CREATE TRIGGER coordination_metadata_no_update BEFORE UPDATE ON coordination_metadata BEGIN SELECT RAISE(ABORT, 'immutable coordination metadata'); END",
    "CREATE TRIGGER coordination_metadata_no_delete BEFORE DELETE ON coordination_metadata BEGIN SELECT RAISE(ABORT, 'immutable coordination metadata'); END",
    "CREATE TRIGGER coordination_events_no_replace BEFORE INSERT ON coordination_events WHEN EXISTS (SELECT 1 FROM coordination_events WHERE seq=NEW.seq OR event_hash=NEW.event_hash) BEGIN SELECT RAISE(ABORT, 'append-only journal: replacement forbidden'); END",
    "CREATE TRIGGER coordination_metadata_no_replace BEFORE INSERT ON coordination_metadata WHEN EXISTS (SELECT 1 FROM coordination_metadata) BEGIN SELECT RAISE(ABORT, 'immutable metadata: replacement forbidden'); END",
)
ARTIFACT_COLUMNS = ("artifact_id", "project_id", "envelope_json", "envelope_digest", "publisher_json", "recipient_json", "published_seq", "published_hash", "delivery_id", "reply_state", "predecessor_state")
DELIVERY_COLUMNS = ("delivery_id", "artifact_id", "receiver_id", "consumer_id", "recipient_json", "envelope_digest", "transport_state", "ack_seq", "ack_hash")


def _delivery_id(artifact, recipient):
    return "delivery:" + digest(dict(artifact_id=artifact.artifact_id, envelope_digest=artifact.envelope_digest,
                                    recipient=recipient.to_dict())).split(":", 1)[1]


def _routing(artifact, publisher, recipient, project_id):
    if artifact.project_id != project_id:
        raise ArtifactRejected("store project mismatch")
    if publisher.role != artifact.from_role:
        raise ArtifactRejected("publisher role declaration mismatch")
    if (recipient.role, recipient.receiver_id) != (artifact.to_role, artifact.receiver_id):
        raise ArtifactRejected("recipient routing mismatch")


def _relation_problem(child, kind, artifacts):
    parent_id = getattr(child, "reply_to_artifact_id" if kind == "reply" else "predecessor_artifact_id")
    if parent_id is None or parent_id not in artifacts:
        return None
    parent = CoordinationArtifact.from_json(artifacts[parent_id]["envelope_json"])
    if child.project_id != parent.project_id:
        return "CROSS_PROJECT_PARENT"
    if kind == "reply" and child.reply_to_digest != parent.envelope_digest:
        return "REPLY_DIGEST_MISMATCH"
    if kind == "reply" and child.correlation_id != parent.correlation_id:
        return "REPLY_CORRELATION_MISMATCH"
    # A declared dependency must not turn into an implicit cyclic chain.
    seen = set()
    todo = [parent_id]
    while todo:
        current = todo.pop()
        if current == child.artifact_id:
            return "RELATION_CYCLE"
        if current in seen or current not in artifacts:
            continue
        seen.add(current)
        envelope = strict_json(artifacts[current]["envelope_json"])
        todo.extend(x for x in (envelope["reply_to_artifact_id"], envelope["predecessor_artifact_id"]) if x)
    return None


def _update_relations(artifacts):
    for row in artifacts.values():
        child = CoordinationArtifact.from_json(row["envelope_json"])
        for kind, field in (("reply", "reply_to_artifact_id"), ("predecessor", "predecessor_artifact_id")):
            parent_id = getattr(child, field)
            if parent_id is None:
                state = "NONE"
            elif parent_id not in artifacts:
                state = "PENDING"
            elif _relation_problem(child, kind, artifacts):
                state = "QUARANTINED"
            else:
                state = "LINKED"
            row[kind + "_state"] = state


def _parse_publication(body, project_id):
    if type(body) is not dict or set(body) != {"artifact", "publisher", "recipient", "delivery_id"}:
        raise ArtifactRejected("invalid publication event body")
    artifact = CoordinationArtifact.from_dict(body["artifact"])
    publisher = LocalIdentity.from_dict(body["publisher"])
    recipient = LocalIdentity.from_dict(body["recipient"])
    _routing(artifact, publisher, recipient, project_id)
    if body["delivery_id"] != _delivery_id(artifact, recipient):
        raise ArtifactRejected("delivery identity mismatch")
    return artifact, publisher, recipient


def _replay(events, project_id):
    artifacts, deliveries, conflicts = {}, {}, []
    previous = GENESIS_HASH
    for seq, event in enumerate(events, 1):
        if type(event.seq) is not int or event.seq != seq or event.previous_hash != previous:
            raise ArtifactRejected("journal sequence/hash linkage mismatch")
        _timestamp(event.recorded_at)
        if event.body_json != canonical(event.body) or event.event_hash != event.calculated_hash():
            raise ArtifactRejected("journal content/hash mismatch")
        body = event.body
        if event.kind == "PUBLISHED":
            artifact, publisher, recipient = _parse_publication(body, project_id)
            if artifact.artifact_id in artifacts:
                raise ArtifactRejected("duplicate publication in journal")
            for kind in ("reply", "predecessor"):
                problem = _relation_problem(artifact, kind, artifacts)
                if problem:
                    raise ArtifactRejected("invalid direct relation in journal: " + problem)
            row = dict(artifact_id=artifact.artifact_id, project_id=project_id, envelope_json=artifact.to_json(),
                       envelope_digest=artifact.envelope_digest, publisher_json=canonical(publisher.to_dict()),
                       recipient_json=canonical(recipient.to_dict()), published_seq=event.seq,
                       published_hash=event.event_hash, delivery_id=body["delivery_id"],
                       reply_state="NONE", predecessor_state="NONE")
            artifacts[artifact.artifact_id] = row
            deliveries[body["delivery_id"]] = dict(delivery_id=body["delivery_id"], artifact_id=artifact.artifact_id,
                receiver_id=recipient.receiver_id, consumer_id=recipient.consumer_id, recipient_json=row["recipient_json"],
                envelope_digest=artifact.envelope_digest, transport_state="AVAILABLE", ack_seq=None, ack_hash=None)
            _update_relations(artifacts)
        elif event.kind == "ACK_RECORDED":
            if type(body) is not dict or set(body) != {"artifact_id", "delivery_id", "envelope_digest", "consumer"}:
                raise ArtifactRejected("invalid ACK event body")
            consumer = LocalIdentity.from_dict(body["consumer"])
            row = deliveries.get(body["delivery_id"])
            if row is None or row["artifact_id"] != body["artifact_id"] or row["envelope_digest"] != body["envelope_digest"]:
                raise ArtifactRejected("ACK targets unknown or different content")
            if row["recipient_json"] != canonical(consumer.to_dict()) or row["ack_seq"] is not None:
                raise ArtifactRejected("invalid or duplicate ACK journal event")
            row.update(transport_state="ACKED", ack_seq=event.seq, ack_hash=event.event_hash)
        elif event.kind == "CONFLICT_QUARANTINED":
            if type(body) is not dict or set(body) != {"candidate", "reason"}:
                raise ArtifactRejected("invalid conflict event")
            candidate, publisher, recipient = _parse_publication(body["candidate"], project_id)
            original = artifacts.get(candidate.artifact_id)
            mismatch = original is not None and (
                original["envelope_json"] != candidate.to_json() or
                original["publisher_json"] != canonical(publisher.to_dict()))
            relation = next((p for k in ("reply", "predecessor") if (p := _relation_problem(candidate, k, artifacts))), None)
            expected = "ARTIFACT_ID_CONFLICT" if mismatch else relation if original is None else None
            if not expected or body["reason"] != expected:
                raise ArtifactRejected("unsupported conflict evidence")
            conflicts.append(dict(event_seq=seq, event_hash=event.event_hash, **body))
        else:
            raise ArtifactRejected("unknown coordination event")
        previous = event.event_hash
    return artifacts, deliveries, conflicts


class CoordinationStore:
    """Verified transport reads only; no implicit creation or receipt side effects."""
    def __init__(self, path, *, project_id):
        _text(project_id, "project_id")
        self.path = Path(path).absolute()
        self.project_id = project_id
        if self.path.name != "coordination.db" or self.path.is_symlink():
            raise StoreBlocked("separate regular file named coordination.db required")
        with self._transaction(False):
            pass

    @classmethod
    def init(cls, path, *, project_id):
        _text(project_id, "project_id")
        path = Path(path).absolute()
        if path.name != "coordination.db":
            raise StoreBlocked("separate file named coordination.db required")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        except OSError as exc:
            raise StoreBlocked(f"explicit init refused: {exc}") from exc
        connection = None
        try:
            connection = cls._connect(path, True)
            connection.execute("BEGIN IMMEDIATE")
            for statement in SCHEMA:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
            connection.execute("INSERT INTO coordination_metadata VALUES (1,?,?,?,?,?)",
                               (FORMAT, project_id, ASSURANCE, AUTHENTICATION, canonical(BOUNDARY)))
            cls._commit(connection)
        except (sqlite3.Error, ArtifactRejected, OSError) as exc:
            raise StoreBlocked(f"init failed; preserve incomplete store: {exc}") from exc
        finally:
            if connection is not None:
                if connection.in_transaction:
                    connection.rollback()
                connection.close()
        return cls(path, project_id=project_id)

    @staticmethod
    def _connect(path, writable):
        if path.is_symlink() or not path.is_file():
            raise StoreBlocked("store missing or not a regular file; use explicit init")
        try:
            connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if writable else "?mode=ro"),
                                         uri=True, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
            if not writable:
                connection.execute("PRAGMA query_only=ON")
            return connection
        except sqlite3.Error as exc:
            if 'connection' in locals():
                connection.close()
            raise StoreBlocked(f"connection blocked: {exc}") from exc

    @staticmethod
    def _commit(connection):
        try:
            connection.commit()
        except sqlite3.Error as exc:
            raise MutationOutcomeUnknown("commit outcome unknown; preserve, read, do not auto-retry") from exc

    def _verify(self, connection):
        if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION or connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise ArtifactRejected("schema version/application mismatch")
        if connection.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
            raise ArtifactRejected("unsupported journal mode")
        actual_sql = {row[0].strip() for row in connection.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")}
        if actual_sql != set(SCHEMA):
            raise ArtifactRejected("schema/trigger mismatch; no automatic migration")
        if [tuple(row) for row in connection.execute("PRAGMA quick_check")] != [("ok",)] or list(connection.execute("PRAGMA foreign_key_check")):
            raise ArtifactRejected("SQLite integrity/foreign key check failed")
        metadata = [tuple(row) for row in connection.execute("SELECT * FROM coordination_metadata")]
        if metadata != [(1, FORMAT, self.project_id, ASSURANCE, AUTHENTICATION, canonical(BOUNDARY))]:
            raise ArtifactRejected("coordination metadata mismatch")
        events = [CoordinationEvent(**dict(row)) for row in connection.execute("SELECT * FROM coordination_events ORDER BY seq")]
        artifacts, deliveries, conflicts = _replay(events, self.project_id)
        for table, columns, expected in (("artifact_projection", ARTIFACT_COLUMNS, artifacts),
                                         ("delivery_projection", DELIVERY_COLUMNS, deliveries)):
            actual = {row[columns[0]]: dict(row) for row in connection.execute("SELECT * FROM " + table)}
            if actual != expected:
                raise ArtifactRejected(table + " mismatch; preserve; no automatic rebuild")
        return events, artifacts, deliveries, conflicts

    @contextmanager
    def _transaction(self, writable):
        connection = self._connect(self.path, writable)
        try:
            connection.execute("BEGIN IMMEDIATE" if writable else "BEGIN")
            snapshot = self._verify(connection)
            yield connection, snapshot
            if writable:
                self._commit(connection)
        except (sqlite3.Error, ArtifactRejected, TypeError, KeyError, OverflowError, RecursionError) as exc:
            raise StoreBlocked(f"store validation/operation blocked: {exc}") from exc
        finally:
            try:
                if connection.in_transaction:
                    connection.rollback()
            finally:
                connection.close()

    def writer(self):
        return CoordinationJournalWriter(self)

    def read(self, artifact_id):
        _text(artifact_id, "artifact_id")
        with self._transaction(False) as (_, snapshot):
            row = snapshot[1].get(artifact_id)
            return None if row is None else CoordinationArtifact.from_json(row["envelope_json"])

    def inbox(self, receiver_id, *, consumer=None, include_acked=False):
        _text(receiver_id, "receiver_id")
        if consumer is not None and (type(consumer) is not LocalIdentity or consumer.receiver_id != receiver_id):
            raise ArtifactRejected("consumer receiver mismatch")
        with self._transaction(False) as (_, snapshot):
            return [dict(row) for row in snapshot[2].values() if row["receiver_id"] == receiver_id
                    and (consumer is None or row["recipient_json"] == canonical(consumer.to_dict()))
                    and (include_acked or row["transport_state"] != "ACKED")]

    def outbox(self, publisher):
        if type(publisher) is not LocalIdentity:
            raise ArtifactRejected("explicit publisher binding required")
        with self._transaction(False) as (_, snapshot):
            return [dict(row) for row in snapshot[1].values() if row["publisher_json"] == canonical(publisher.to_dict())]

    def status(self, artifact_id=None):
        if artifact_id is not None:
            _text(artifact_id, "artifact_id")
        with self._transaction(False) as (_, snapshot):
            events, artifacts, deliveries, conflicts = snapshot
            chosen = [row for row in artifacts.values() if artifact_id is None or row["artifact_id"] == artifact_id]
            return dict(boundary=dict(BOUNDARY), project_id=self.project_id, event_count=len(events),
                        journal_head=events[-1].event_hash if events else GENESIS_HASH,
                        artifacts=[dict(row) for row in chosen],
                        deliveries=[dict(deliveries[row["delivery_id"]]) for row in chosen],
                        conflicts=[dict(row) for row in conflicts if artifact_id is None or row["candidate"]["artifact"]["artifact_id"] == artifact_id])


class CoordinationJournalWriter:
    """One logical transport writer; SQLite serializes independent handles.

    No governance credentials or state/capability references are resolved.
    Connection ownership is per operation; no connection is exposed by the API.
    """
    def __init__(self, store):
        if type(store) is not CoordinationStore:
            raise ArtifactRejected("expected CoordinationStore")
        self.store = store

    @staticmethod
    def _persist(connection, events, artifacts, deliveries, event, project_id):
        # Derive and verify the event's effects before touching SQLite. Updating
        # projections here is normal journal application, never startup repair.
        next_artifacts, next_deliveries, _ = _replay([*events, event], project_id)
        connection.execute("INSERT INTO coordination_events VALUES (?,?,?,?,?,?)",
                           (event.seq, event.kind, event.recorded_at, event.body_json, event.previous_hash, event.event_hash))
        for table, columns, before, after in (("artifact_projection", ARTIFACT_COLUMNS, artifacts, next_artifacts),
                                               ("delivery_projection", DELIVERY_COLUMNS, deliveries, next_deliveries)):
            for key, row in after.items():
                if key not in before:
                    connection.execute("INSERT INTO " + table + " VALUES (" + ",".join("?" for _ in columns) + ")",
                                       tuple(row[name] for name in columns))
                elif row != before[key]:
                    connection.execute("UPDATE " + table + " SET " + ",".join(name + "=?" for name in columns[1:]) + " WHERE " + columns[0] + "=?",
                                       (*[row[name] for name in columns[1:]], key))

    @staticmethod
    def _publish_receipt(row):
        return PublishReceipt(row["artifact_id"], row["delivery_id"], row["envelope_digest"],
                              row["published_seq"], row["published_hash"],
                              digest(strict_json(row["publisher_json"])), digest(strict_json(row["recipient_json"])))

    @staticmethod
    def _ack_receipt(row):
        return AckReceipt(row["artifact_id"], row["delivery_id"], row["consumer_id"], row["envelope_digest"],
                          row["ack_seq"], row["ack_hash"], digest(strict_json(row["recipient_json"])))

    def publish(self, artifact, *, publisher, recipient):
        if type(artifact) is not CoordinationArtifact or type(publisher) is not LocalIdentity or type(recipient) is not LocalIdentity:
            raise ArtifactRejected("explicit artifact and host identity bindings required")
        # Reconstruct validated immutable objects; reject forged object state.
        artifact = CoordinationArtifact.from_json(artifact.to_json())
        publisher = LocalIdentity.from_dict(publisher.to_dict())
        recipient = LocalIdentity.from_dict(recipient.to_dict())
        _routing(artifact, publisher, recipient, self.store.project_id)
        body = dict(artifact=artifact.to_dict(), publisher=publisher.to_dict(), recipient=recipient.to_dict(),
                    delivery_id=_delivery_id(artifact, recipient))
        conflict = None
        with self.store._transaction(True) as (connection, snapshot):
            events, artifacts, deliveries, _ = snapshot
            existing = artifacts.get(artifact.artifact_id)
            if existing is not None:
                if existing["envelope_json"] == artifact.to_json() and existing["publisher_json"] == canonical(publisher.to_dict()):
                    # The frozen replay key does not rebind an existing delivery.
                    # Return its original receipt/binding even if a caller supplies
                    # a different local session for the same declared receiver.
                    return self._publish_receipt(existing)
                reason = "ARTIFACT_ID_CONFLICT"
            else:
                reason = next((p for k in ("reply", "predecessor") if (p := _relation_problem(artifact, k, artifacts))), None)
            event = CoordinationEvent.create(len(events) + 1, "CONFLICT_QUARANTINED" if reason else "PUBLISHED",
                dict(candidate=body, reason=reason) if reason else body, events[-1].event_hash if events else GENESIS_HASH)
            self._persist(connection, events, artifacts, deliveries, event, self.store.project_id)
            if reason:
                conflict = PublicationConflict(reason, event.seq)
            else:
                row = _replay([*events, event], self.store.project_id)[0][artifact.artifact_id]
                receipt = self._publish_receipt(row)
        if conflict:
            raise conflict
        return receipt

    def reply(self, artifact, *, publisher, recipient):
        if type(artifact) is not CoordinationArtifact or artifact.reply_to_artifact_id is None:
            raise ArtifactRejected("reply operation requires an explicit exact parent reference")
        return self.publish(artifact, publisher=publisher, recipient=recipient)

    def ack(self, *, artifact_id, delivery_id, consumer_id, envelope_digest, consumer):
        for name, value in (("artifact_id", artifact_id), ("delivery_id", delivery_id), ("consumer_id", consumer_id)):
            _text(value, name)
        if type(consumer) is not LocalIdentity or consumer.consumer_id != consumer_id:
            raise ArtifactRejected("explicit consumer binding mismatch")
        consumer = LocalIdentity.from_dict(consumer.to_dict())
        if type(envelope_digest) is not str or not DIGEST.fullmatch(envelope_digest):
            raise ArtifactRejected("exact envelope digest required")
        with self.store._transaction(True) as (connection, snapshot):
            events, artifacts, deliveries, _ = snapshot
            row = deliveries.get(delivery_id)
            if row is None or row["artifact_id"] != artifact_id or row["envelope_digest"] != envelope_digest or row["recipient_json"] != canonical(consumer.to_dict()):
                raise ArtifactRejected("ACK target/content/consumer mismatch")
            if row["ack_seq"] is not None:
                return self._ack_receipt(row)
            body = dict(artifact_id=artifact_id, delivery_id=delivery_id, envelope_digest=envelope_digest, consumer=consumer.to_dict())
            event = CoordinationEvent.create(len(events) + 1, "ACK_RECORDED", body, events[-1].event_hash if events else GENESIS_HASH)
            self._persist(connection, events, artifacts, deliveries, event, self.store.project_id)
            return self._ack_receipt(_replay([*events, event], self.store.project_id)[1][delivery_id])


def _file_json(path):
    return strict_json(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="separate coordination.db path")
    parser.add_argument("--project-id", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    for command in ("publish", "reply"):
        sub = commands.add_parser(command)
        sub.add_argument("--artifact", required=True)
        sub.add_argument("--publisher", required=True, help="UNVERIFIED_LOCAL host binding JSON")
        sub.add_argument("--recipient", required=True, help="UNVERIFIED_LOCAL host binding JSON")
    sub = commands.add_parser("read")
    sub.add_argument("artifact_id")
    sub = commands.add_parser("inbox")
    sub.add_argument("--receiver-id", required=True)
    sub.add_argument("--consumer")
    sub.add_argument("--include-acked", action="store_true")
    sub = commands.add_parser("outbox")
    sub.add_argument("--publisher", required=True)
    sub = commands.add_parser("status")
    sub.add_argument("--artifact-id")
    sub = commands.add_parser("ack")
    for flag in ("artifact-id", "delivery-id", "consumer-id", "envelope-digest", "consumer"):
        sub.add_argument("--" + flag, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            store = CoordinationStore.init(args.db, project_id=args.project_id)
            result = store.status()
        else:
            store = CoordinationStore(args.db, project_id=args.project_id)
            if args.command in ("publish", "reply"):
                result = asdict(getattr(store.writer(), args.command)(CoordinationArtifact.from_dict(_file_json(args.artifact)),
                    publisher=LocalIdentity.from_dict(_file_json(args.publisher)), recipient=LocalIdentity.from_dict(_file_json(args.recipient))))
            elif args.command == "ack":
                result = asdict(store.writer().ack(artifact_id=args.artifact_id, delivery_id=args.delivery_id,
                    consumer_id=args.consumer_id, envelope_digest=args.envelope_digest,
                    consumer=LocalIdentity.from_dict(_file_json(args.consumer))))
            elif args.command == "read":
                artifact = store.read(args.artifact_id)
                result = None if artifact is None else artifact.to_dict()
            elif args.command == "inbox":
                result = store.inbox(args.receiver_id, consumer=LocalIdentity.from_dict(_file_json(args.consumer)) if args.consumer else None, include_acked=args.include_acked)
            elif args.command == "outbox":
                result = store.outbox(LocalIdentity.from_dict(_file_json(args.publisher)))
            else:
                result = store.status(args.artifact_id)
        print(canonical(dict(boundary=dict(BOUNDARY), result=result)))
        return 0
    except (ArtifactRejected, StoreBlocked, OSError) as exc:
        print(canonical(dict(boundary=dict(BOUNDARY), error=type(exc).__name__, diagnostic=str(exc))), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded v2 journal substrate; no adapters, activation, or governance issuer.

Authority resolution and writer authentication are explicit trusted-boundary
inputs, never inferred from role/PRODUCER labels. Test doubles are not production
authentication. Python encapsulation and hashes do not protect against a caller
with process introspection or direct database/filesystem control.

Local, reversible implementation choices: one workflow per SQLite store, schema
format /1, canonical ASCII JSON, zero-digest genesis, and BEGIN IMMEDIATE with
FULL synchronous writes. expected_journal_seq means the current predecessor's
sequence, not the sequence of the proposed event. No WAL/lease/topology is frozen.
"""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import re
import sqlite3


GENESIS_HASH = "sha256:" + "0" * 64
FORMAT = "acos-v2-core-substrate/1"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
TERMINAL = frozenset({"STOPPED", "QUARANTINED", "PRESERVE_ONLY"})
EDGES = {
    "DRAFT": frozenset({"REVIEW_PENDING"}),
    "REVIEW_PENDING": frozenset({"AUTHORIZED", "ACCEPTED", "RETURNED", "BLOCKED"}),
    "AUTHORIZED": frozenset({"EXECUTING"}),
    "EXECUTING": frozenset({"RESULT_RECORDED"}),
    "RESULT_RECORDED": frozenset({"REVIEW_PENDING"}),
    "ACCEPTED": frozenset({"STAGE_CLOSED"}),
    "STAGE_CLOSED": frozenset({"CHECKPOINT_PENDING"}),
    "CHECKPOINT_PENDING": frozenset({"CHECKPOINTED"}),
    "RETURNED": frozenset(),
    "BLOCKED": frozenset(),
    "CHECKPOINTED": frozenset(),
}
STATES = frozenset(EDGES) | TERMINAL


class TransitionDenied(ValueError):
    """A candidate contradicts the bounded transition contract."""


class StoreBlocked(RuntimeError):
    """Missing trusted evidence, damaged storage, or unresolved effect."""


class MutationOutcomeUnknown(StoreBlocked):
    """Commit acknowledgement failed; no automatic retry/reconciliation."""


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def require_text(value, label):
    if not isinstance(value, str) or not value or value != value.strip():
        raise TransitionDenied(f"invalid {label}")


@dataclass(frozen=True)
class WorkflowScope:
    project_id: str
    stage_id: str
    task_id: str


@dataclass(frozen=True)
class ExecutionIdentity:
    project_id: str
    stage_id: str
    task_id: str
    authorization_id: str
    executor_role: str
    execution_attempt_id: str
    baseline_revision: str


@dataclass(frozen=True)
class AuthorityReference:
    authorization_id: str
    content_digest: str


@dataclass(frozen=True)
class CandidateTransition:
    transition_id: str
    candidate_id: str
    expected_parent_event_hash: str
    expected_journal_seq: int
    validated_baseline: str
    authority_reference: AuthorityReference
    execution_identity: ExecutionIdentity
    from_state: str
    to_state: str


@dataclass(frozen=True)
class AuthorityEvidence:
    """Output of an independently established, read-only authority resolver.

    This is not an input-file authentication scheme or a new Decision source.
    The integrating boundary must authenticate its source and validate the exact
    candidate/identity/gates before returning this object. No default exists.
    """

    authority_reference: AuthorityReference
    execution_identity: ExecutionIdentity
    candidate_id: str
    from_state: str
    to_state: str
    governance_source: str
    authenticated: bool
    required_gates: tuple
    verified_gates: tuple


@dataclass(frozen=True)
class AcceptedTransitionRecord(CandidateTransition):
    governance_source: str
    required_gates: tuple
    verified_gates: tuple
    _issuance: object = field(default=None, repr=False, compare=False)

    def body(self):
        return {
            **{name: getattr(self, name) for name in (
                "transition_id", "candidate_id", "expected_parent_event_hash",
                "expected_journal_seq", "validated_baseline", "from_state",
                "to_state", "governance_source", "required_gates", "verified_gates",
            )},
            "authority_reference": asdict(self.authority_reference),
            "execution_identity": asdict(self.execution_identity),
        }


@dataclass(frozen=True)
class StateSnapshot:
    state: str
    last_applied_seq: int
    head_event_hash: str
    transition_ids: frozenset


@dataclass(frozen=True)
class DurableReconciliation:
    """Durable facts only; never an accepted record or permission to retry."""

    consistent: bool
    snapshot: StateSnapshot | None
    transition_id: str | None
    transition_outcome: str | None
    reason: str | None = None


def check_candidate(candidate, scope, baseline):
    if not isinstance(candidate, CandidateTransition):
        raise TransitionDenied("expected a candidate transition")
    for name in ("transition_id", "candidate_id"):
        require_text(getattr(candidate, name), name)
    if type(candidate.expected_journal_seq) is not int or candidate.expected_journal_seq < 0:
        raise TransitionDenied("invalid expected_journal_seq")
    if not isinstance(candidate.expected_parent_event_hash, str) or not DIGEST.fullmatch(candidate.expected_parent_event_hash):
        raise TransitionDenied("invalid predecessor hash")
    if candidate.validated_baseline != baseline:
        raise TransitionDenied("baseline mismatch")
    identity = candidate.execution_identity
    reference = candidate.authority_reference
    if type(identity) is not ExecutionIdentity or type(reference) is not AuthorityReference:
        raise TransitionDenied("missing identity or authority reference")
    for name, value in asdict(identity).items():
        require_text(value, name)
    require_text(reference.authorization_id, "authority reference")
    if not isinstance(reference.content_digest, str) or not DIGEST.fullmatch(reference.content_digest):
        raise TransitionDenied("invalid authority content digest")
    if identity.authorization_id != reference.authorization_id:
        raise TransitionDenied("authority/identity linkage mismatch")
    if identity.baseline_revision != baseline:
        raise TransitionDenied("identity baseline mismatch")
    if (identity.project_id, identity.stage_id, identity.task_id) != (
        scope.project_id, scope.stage_id, scope.task_id
    ):
        raise TransitionDenied("workflow scope mismatch")
    require_text(candidate.from_state, "from_state")
    require_text(candidate.to_state, "to_state")
    if candidate.from_state not in STATES or candidate.to_state not in STATES:
        raise TransitionDenied("unknown workflow state")
    if candidate.from_state in TERMINAL:
        raise TransitionDenied("no automatic exit from exceptional terminal state")
    if candidate.to_state not in EDGES[candidate.from_state] | TERMINAL:
        raise TransitionDenied("unsupported state move")


def check_predecessor(candidate, snapshot):
    if candidate.transition_id in snapshot.transition_ids:
        raise TransitionDenied("duplicate transition_id")
    if candidate.expected_journal_seq != snapshot.last_applied_seq:
        raise TransitionDenied("stale expected sequence")
    if candidate.expected_parent_event_hash != snapshot.head_event_hash:
        raise TransitionDenied("stale predecessor hash")
    if candidate.from_state != snapshot.state:
        raise TransitionDenied("predecessor state mismatch")


def check_gates(required, verified):
    if not isinstance(required, (list, tuple)) or not isinstance(verified, (list, tuple)):
        raise TransitionDenied("invalid gate evidence")
    for value in (*required, *verified):
        require_text(value, "gate")
    if len(set(required)) != len(required) or len(set(verified)) != len(verified):
        raise TransitionDenied("duplicate gate evidence")
    if not set(required).issubset(verified):
        raise StoreBlocked("required governance gate not verified")


class _RecordIssuer:
    def __init__(self):
        self._issued = {}

    def issue(self, candidate, evidence):
        token = object()
        record = AcceptedTransitionRecord(
            **{name: getattr(candidate, name) for name in CandidateTransition.__dataclass_fields__},
            governance_source=evidence.governance_source,
            required_gates=tuple(evidence.required_gates),
            verified_gates=tuple(evidence.verified_gates),
            _issuance=token,
        )
        self._issued[token] = canonical(record.body())
        return record

    def check(self, record):
        if type(record) is not AcceptedTransitionRecord:
            raise TransitionDenied("only an accepted transition record may append")
        if type(record._issuance) is not object or self._issued.get(record._issuance) != canonical(record.body()):
            raise TransitionDenied("unissued, altered, or foreign accepted record")

    def consume(self, record):
        del self._issued[record._issuance]


class TransitionEngine:
    """Validation-only object: no connection, writer, append, or persist API."""

    def __init__(self, snapshot_reader, scope, baseline, trusted_resolver, authenticate_submission, issuer):
        self._snapshot_reader = snapshot_reader
        self._scope = scope
        self._baseline = baseline
        self._trusted_resolver = trusted_resolver
        self._authenticate_submission = authenticate_submission
        self._issuer = issuer

    def validate(self, candidate, submitting_credential=None):
        check_candidate(candidate, self._scope, self._baseline)
        check_predecessor(candidate, self._snapshot_reader())
        if not callable(self._authenticate_submission):
            raise StoreBlocked("independent submission authentication unavailable")
        try:
            authenticated_identity = self._authenticate_submission(submitting_credential)
        except Exception as exc:
            raise StoreBlocked("submission authentication failed") from exc
        if type(authenticated_identity) is not ExecutionIdentity or authenticated_identity != candidate.execution_identity:
            raise TransitionDenied("submitting identity not independently authenticated")
        if not callable(self._trusted_resolver):
            raise StoreBlocked("independent authority resolver unavailable")
        try:
            evidence = self._trusted_resolver(candidate.authority_reference)
        except Exception as exc:
            raise StoreBlocked("authority resolution failed") from exc
        if type(evidence) is not AuthorityEvidence or evidence.authenticated is not True:
            raise TransitionDenied("authority was not independently authenticated")
        if evidence.governance_source not in {"User Decision", "ChatGPT Review"}:
            raise TransitionDenied("not an applicable governance event source")
        if (
            evidence.authority_reference != candidate.authority_reference
            or evidence.execution_identity != candidate.execution_identity
            or evidence.candidate_id != candidate.candidate_id
            or evidence.from_state != candidate.from_state
            or evidence.to_state != candidate.to_state
        ):
            raise TransitionDenied("authority does not bind this exact candidate")
        check_gates(evidence.required_gates, evidence.verified_gates)
        return self._issuer.issue(candidate, evidence)


SCHEMA = {
    "core_metadata": "CREATE TABLE core_metadata (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), format TEXT NOT NULL, scope TEXT NOT NULL, baseline TEXT NOT NULL, writer_principal TEXT NOT NULL)",
    "state_journal": "CREATE TABLE state_journal (seq INTEGER PRIMARY KEY CHECK (seq > 0), transition_id TEXT NOT NULL UNIQUE, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL UNIQUE, record_json TEXT NOT NULL)",
    "derived_projection": "CREATE TABLE derived_projection (singleton INTEGER PRIMARY KEY CHECK (singleton = 1), state TEXT NOT NULL, last_applied_seq INTEGER NOT NULL, head_event_hash TEXT NOT NULL)",
    "state_journal_no_update": "CREATE TRIGGER state_journal_no_update BEFORE UPDATE ON state_journal BEGIN SELECT RAISE(ABORT, 'append-only journal'); END",
    "state_journal_no_delete": "CREATE TRIGGER state_journal_no_delete BEFORE DELETE ON state_journal BEGIN SELECT RAISE(ABORT, 'append-only journal'); END",
}


class StateStore:
    """Read API plus factories for distinct validation and authenticated writer roles.

    No public SQL/connection/append API exists. Bootstrap creates only metadata
    and a DRAFT genesis projection, not an authorization. Existing stores are
    verified, never silently initialized, migrated, or schema-repaired.
    """

    def __init__(self, path, scope, baseline, writer_principal, authenticate_writer, *, create=False):
        if type(scope) is not WorkflowScope or not isinstance(baseline, str) or not REVISION.fullmatch(baseline):
            raise StoreBlocked("missing exact workflow/baseline binding")
        for name, value in asdict(scope).items():
            require_text(value, name)
        require_text(writer_principal, "writer principal")
        if not callable(authenticate_writer):
            raise StoreBlocked("independent writer authentication unavailable")
        path = Path(path).absolute()
        if path.is_symlink() or (create and path.exists()) or (not create and not path.is_file()):
            raise StoreBlocked("explicit new regular store or verified existing store required")
        self._scope = scope
        self._baseline = baseline
        self._writer_principal = writer_principal
        self._authenticate_writer = authenticate_writer
        self._issuer = _RecordIssuer()
        self._outcome_unknown = False
        self._reconciled = create
        self._closed = False
        mode = "rwc" if create else "rw"
        self._db = sqlite3.connect(path.as_uri() + "?mode=" + mode, uri=True, isolation_level=None, timeout=5)
        self._db.row_factory = sqlite3.Row
        try:
            self._db.execute("PRAGMA synchronous = FULL")
            self._db.execute("PRAGMA foreign_keys = ON")
            if self._db.execute("PRAGMA synchronous").fetchone()[0] != 2:
                raise StoreBlocked("FULL synchronous unavailable")
            if create:
                with self._transaction():
                    for sql in SCHEMA.values():
                        self._db.execute(sql)
                    self._db.execute("INSERT INTO core_metadata VALUES (1, ?, ?, ?, ?)", self._metadata())
                    self._db.execute("INSERT INTO derived_projection VALUES (1, 'DRAFT', 0, ?)", (GENESIS_HASH,))
            if create:
                self._consistent_snapshot()
            else:
                reconciliation = self.reconcile()
                if not reconciliation.consistent:
                    raise StoreBlocked("durable reconciliation unresolved: " + reconciliation.reason)
        except BaseException:
            self._db.close()
            self._closed = True
            raise

    def _metadata(self):
        return (FORMAT, canonical(asdict(self._scope)), self._baseline, self._writer_principal)

    def _require_open(self):
        if self._closed or self._outcome_unknown:
            raise StoreBlocked("closed store or unresolved mutation outcome; no automatic retry")

    def _require_available(self):
        self._require_open()
        if not self._reconciled:
            raise StoreBlocked("durable reconciliation required before transition acceptance")

    def _verify_schema(self):
        self._require_open()
        for name, sql in SCHEMA.items():
            row = self._db.execute("SELECT sql FROM sqlite_schema WHERE name = ?", (name,)).fetchone()
            if row is None or row[0] != sql:
                raise StoreBlocked("store schema mismatch; no automatic schema repair")
        rows = self._db.execute("SELECT format, scope, baseline, writer_principal FROM core_metadata").fetchall()
        if len(rows) != 1 or tuple(rows[0]) != self._metadata():
            raise StoreBlocked("store metadata/baseline/writer binding mismatch")

    def _commit_transaction(self):
        self._db.execute("COMMIT")

    @contextmanager
    def _transaction(self):
        self._require_available()
        try:
            self._db.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as exc:
            raise StoreBlocked("unable to acquire single SQLite write transaction") from exc
        committing = False
        try:
            yield
            committing = True
            self._commit_transaction()
        except BaseException as exc:
            if self._db.in_transaction:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error:
                    self._outcome_unknown = True
            if committing or self._outcome_unknown:
                self._outcome_unknown = True
                raise MutationOutcomeUnknown("commit/rollback outcome unresolved; preserve store") from exc
            if isinstance(exc, sqlite3.Error):
                raise StoreBlocked("SQLite write failed; transaction rolled back") from exc
            raise

    def _replay_journal(self):
        state, seq, head, ids = "DRAFT", 0, GENESIS_HASH, set()
        for row in self._db.execute("SELECT * FROM state_journal ORDER BY seq"):
            try:
                body = json.loads(row["record_json"])
                reference = AuthorityReference(**body["authority_reference"])
                identity = ExecutionIdentity(**body["execution_identity"])
                record = AcceptedTransitionRecord(**{**body, "authority_reference": reference, "execution_identity": identity})
                check_candidate(record, self._scope, self._baseline)
                check_gates(record.required_gates, record.verified_gates)
                check_predecessor(record, StateSnapshot(state, seq, head, frozenset(ids)))
                if record.governance_source not in {"User Decision", "ChatGPT Review"}:
                    raise TransitionDenied("non-governance journal source")
                expected_hash = digest({"seq": seq + 1, "previous_hash": head, "record": body})
                if (
                    row["seq"] != seq + 1 or row["transition_id"] != record.transition_id
                    or row["previous_hash"] != head or row["event_hash"] != expected_hash
                    or row["record_json"] != canonical(record.body())
                ):
                    raise TransitionDenied("journal chain/content mismatch")
            except (TypeError, KeyError, ValueError, StoreBlocked) as exc:
                raise StoreBlocked("journal invalid; cannot derive projection") from exc
            state, seq, head = record.to_state, row["seq"], row["event_hash"]
            ids.add(record.transition_id)
        return StateSnapshot(state, seq, head, frozenset(ids))

    def _consistent_snapshot(self):
        self._verify_schema()
        expected = self._replay_journal()
        rows = self._db.execute("SELECT state, last_applied_seq, head_event_hash FROM derived_projection").fetchall()
        if len(rows) != 1 or tuple(rows[0]) != (expected.state, expected.last_applied_seq, expected.head_event_hash):
            raise StoreBlocked("journal/projection mismatch; transition acceptance blocked")
        return expected

    def reconcile(self, transition_id=None):
        """Read-only restart gate and optional transition outcome resolution.

        A commit-uncertain instance remains blocked and must first be closed.
        Reopening runs this gate before exposing normal operations. Only one
        consistent journal/projection read can reopen acceptance; no authority
        or retry permission follows from COMMITTED or NOT_COMMITTED evidence.
        """
        self._require_open()
        if transition_id is not None:
            require_text(transition_id, "transition_id to reconcile")
        self._reconciled = False
        started = False
        snapshot = None
        failure = None
        try:
            self._db.execute("BEGIN")
            started = True
            snapshot = self._consistent_snapshot()
        except (sqlite3.Error, StoreBlocked) as exc:
            failure = str(exc)
        finally:
            if started:
                try:
                    self._db.execute("ROLLBACK")
                except sqlite3.Error as exc:
                    failure = "reconciliation read transaction could not close: " + str(exc)
        if failure is not None:
            return DurableReconciliation(False, None, transition_id, "UNRESOLVED", failure)
        outcome = None
        if transition_id is not None:
            outcome = "COMMITTED" if transition_id in snapshot.transition_ids else "NOT_COMMITTED"
        self._reconciled = True
        return DurableReconciliation(True, snapshot, transition_id, outcome)

    def snapshot(self):
        self._require_available()
        self._db.execute("BEGIN")
        try:
            return self._consistent_snapshot()
        except sqlite3.Error as exc:
            raise StoreBlocked("unable to verify journal/projection") from exc
        finally:
            self._db.execute("ROLLBACK")

    def transition_engine(self, trusted_resolver, authenticate_submission=None):
        return TransitionEngine(self.snapshot, self._scope, self._baseline, trusted_resolver, authenticate_submission, self._issuer)

    def _check_writer(self, credential):
        self._require_available()
        try:
            principal = self._authenticate_writer(credential)
        except Exception as exc:
            raise StoreBlocked("writer authentication unavailable") from exc
        if not isinstance(principal, str) or principal != self._writer_principal:
            raise TransitionDenied("writer identity not independently authenticated")

    def writer(self, credential):
        self._check_writer(credential)
        return StateJournalWriter(self, credential, _WRITER_CONSTRUCTION)

    def _insert_journal(self, record, seq, event_hash):
        self._db.execute(
            "INSERT INTO state_journal VALUES (?, ?, ?, ?, ?)",
            (seq, record.transition_id, record.expected_parent_event_hash, event_hash, canonical(record.body())),
        )

    def _update_projection(self, state, seq, head):
        changed = self._db.execute(
            "UPDATE derived_projection SET state = ?, last_applied_seq = ?, head_event_hash = ? WHERE singleton = 1",
            (state, seq, head),
        ).rowcount
        if changed != 1:
            raise StoreBlocked("projection update did not affect exactly one row")

    def close(self):
        if not self._closed:
            self._db.close()
            self._closed = True


_WRITER_CONSTRUCTION = object()


class StateJournalWriter:
    """The only logical append path; cannot choose states or issue authority."""

    def __init__(self, store, credential, construction=None):
        if construction is not _WRITER_CONSTRUCTION:
            raise TransitionDenied("writer construction requires authenticated store boundary")
        self._store = store
        self._credential = credential

    def append(self, record):
        store = self._store
        store._check_writer(self._credential)
        if type(record) is not AcceptedTransitionRecord:
            raise TransitionDenied("accepted transition record required")
        with store._transaction():
            snapshot = store._consistent_snapshot()
            check_candidate(record, store._scope, store._baseline)
            check_predecessor(record, snapshot)
            store._issuer.check(record)
            seq = snapshot.last_applied_seq + 1
            head = digest({"seq": seq, "previous_hash": snapshot.head_event_hash, "record": record.body()})
            store._insert_journal(record, seq, head)
            store._update_projection(record.to_state, seq, head)
        store._issuer.consume(record)
        return StateSnapshot(record.to_state, seq, head, snapshot.transition_ids | {record.transition_id})

    def rebuild_projection(self):
        """Journal-only catch-up; no journal rewrite or exceptional-state exit."""
        store = self._store
        store._check_writer(self._credential)
        with store._transaction():
            store._verify_schema()
            expected = store._replay_journal()
            store._db.execute("DELETE FROM derived_projection")
            store._db.execute(
                "INSERT INTO derived_projection VALUES (1, ?, ?, ?)",
                (expected.state, expected.last_applied_seq, expected.head_event_hash),
            )
            store._consistent_snapshot()
        return expected

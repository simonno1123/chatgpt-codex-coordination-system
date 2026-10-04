"""One host-authorized, test-only repair on a pre-prepared disposable fixture.

This entry is not a broker, production trust anchor, or mandatory dispatcher.
The host must independently establish its read-only grant/state/baseline/target
providers and preload canonical repository modules. Process-local claims are
not durable consumption or cross-process replay protection. Cancellation is
observed at final admission, not atomically with the subsequent repair.
Preparation and disposal belong to an external lifecycle owner. A crash must
not reopen, retry, or resume this fixture. Existing direct writers remain
outside this pilot. Python process control is outside its trust boundary.
"""

from dataclasses import dataclass, field, asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
from types import ModuleType
import uuid


_DIRECTORY = Path(__file__).resolve().parent


def _preloaded(name, filename):
    module = sys.modules.get(name)
    if not isinstance(module, ModuleType) or vars(module).get("__file__") != str(_DIRECTORY / filename):
        raise ImportError("preload canonical " + name + " from its repository path")
    return module


_core = _preloaded("acos_v2_core_substrate", "acos-v2-core-substrate.py")
_capability = _preloaded("acos_v2_capability", "acos-v2-capability.py")
_runner = _preloaded("acos_w3b_b_p1_single_index_repair", "acos-w3b-b-p1-single-index-repair.py")
_factory = _preloaded("acos_w3b_b_p1_fixture_factory", "acos-w3b-b-p1-fixture-factory.py")
_verifier = _preloaded("acos_w3b_b_p1_poststate_verifier", "acos-w3b-b-p1-poststate-verifier.py")
_policy = _preloaded("acos_w3b_b_p1_disposable_mutator", "acos-w3b-b-p1-disposable-mutator.py")
if not _capability._canonical_core_intact() or _runner.factory_module is not _factory:
    raise ImportError("one canonical Core/Capability/W3B module universe is required")

_Envelope = _capability.CapabilityEnvelope
_Request = _capability.ValidationRequest
_Validator = _capability.CapabilityValidator
_ValidationResult = _capability.ValidationResult
_Handle = _factory.FixtureHandle
_Registry = _factory.FixtureRegistry
_WriterOutcome = _factory.WriterOutcome
_Repair = _factory.RepairMutator
_Verifier = _verifier.PoststateVerifier
_EXECUTE = _Repair.execute
_PRIME = _Repair.prime_runtime_compatibility
_VALIDATE = _Validator.validate
_VERIFY = _Verifier.verify
_OPEN_READ_ONLY = _Verifier.open_read_only
_BYTE_DIGEST = _factory.fixture_byte_digest
_CHECKPOINT = _factory.verify_identity_checkpoint
_SQL_CHECK = _factory._verify_canonical_repair_operation_digest
_REQUIRE = _Registry.require_current
_TRANSITION = _Registry.transition
_REINDEX_CALLBACK = _policy._REPAIR_REINDEX_CALLBACK

FIXED_SQL = "CREATE INDEX idx_audit_events_aggregate\nON audit_events(aggregate_type, aggregate_id, sequence);"
FIXED_SQL_DIGEST = "sha256:" + hashlib.sha256(FIXED_SQL.encode("utf-8")).hexdigest()
CAPABILITY_CLASS = "DISPOSABLE_FIXTURE_REPAIR_ONLY"
OPERATION = "CREATE_INDEX_IDX_AUDIT_EVENTS_AGGREGATE"
COMMITTED = "COMMITTED"
NOT_COMMITTED = "NOT_COMMITTED"
UNRESOLVED = "UNRESOLVED"
FULL_PATH_MEDIATION = False

_MODULES = tuple((name, module, module.__file__, hashlib.sha256(Path(module.__file__).read_bytes()).digest())
                for name, module in (("acos_v2_core_substrate", _core),
                                     ("acos_v2_capability", _capability),
                                     ("acos_w3b_b_p1_single_index_repair", _runner),
                                     ("acos_w3b_b_p1_fixture_factory", _factory),
                                     ("acos_w3b_b_p1_poststate_verifier", _verifier),
                                     ("acos_w3b_b_p1_disposable_mutator", _policy)))


def _canonical_intact():
    try:
        for name, module, path, digest in _MODULES:
            if sys.modules.get(name) is not module or vars(module).get("__file__") != path:
                return False
            if hashlib.sha256(Path(path).read_bytes()).digest() != digest:
                return False
            if any(other is not module and isinstance(other, ModuleType)
                   and vars(other).get("__file__") == path for other in tuple(sys.modules.values())):
                return False
        if not _capability._canonical_core_intact():
            return False
        pins = ((_capability, "CapabilityEnvelope", _Envelope),
                (_capability, "ValidationRequest", _Request),
                (_capability, "CapabilityValidator", _Validator),
                (_capability, "ValidationResult", _ValidationResult),
                (_factory, "FixtureHandle", _Handle), (_factory, "FixtureRegistry", _Registry),
                (_factory, "WriterOutcome", _WriterOutcome), (_factory, "RepairMutator", _Repair),
                (_factory, "fixture_byte_digest", _BYTE_DIGEST),
                (_factory, "verify_identity_checkpoint", _CHECKPOINT),
                (_factory, "_verify_canonical_repair_operation_digest", _SQL_CHECK),
                (_verifier, "PoststateVerifier", _Verifier),
                (_Repair, "execute", _EXECUTE), (_Repair, "prime_runtime_compatibility", _PRIME),
                (_Validator, "validate", _VALIDATE), (_Verifier, "verify", _VERIFY),
                (_Verifier, "open_read_only", _OPEN_READ_ONLY),
                (_Registry, "require_current", _REQUIRE), (_Registry, "transition", _TRANSITION))
        if any(getattr(owner, name, None) is not expected for owner, name, expected in pins):
            return False
        _factory.canonical_module_fingerprint()
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class PilotTargetDescriptor:
    fixture_uuid: str
    database_path: str
    device_id: int
    inode: int
    fixture_generation: int
    prestate_digest: str
    fixed_sql_digest: str

    def canonical_target(self):
        if _descriptor_error(self):
            raise ValueError("invalid exact pilot target descriptor")
        encoded = json.dumps(asdict(self), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        return "acos-v2-disposable-repair/1:sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _descriptor_error(value):
    if type(value) is not PilotTargetDescriptor:
        return "non-canonical target descriptor"
    try:
        if type(value.fixture_uuid) is not str or str(uuid.UUID(value.fixture_uuid)) != value.fixture_uuid:
            return "invalid fixture UUID"
        path = value.database_path
        if (not _capability._exact_selector(path) or not Path(path).is_absolute()
                or os.path.normpath(path) != path or "\x00" in path):
            return "invalid canonical database path"
        for name, minimum in (("device_id", 0), ("inode", 1), ("fixture_generation", 0)):
            if type(getattr(value, name)) is not int or getattr(value, name) < minimum:
                return "invalid target " + name
        if any(type(getattr(value, name)) is not str or not _core.DIGEST.fullmatch(getattr(value, name))
               for name in ("prestate_digest", "fixed_sql_digest")):
            return "invalid target digest"
    except Exception:
        return "invalid target descriptor"
    return None


def observe_fixture_target(handle, registry):
    """Read-only observation, not a grant; the host establishes its provenance."""
    if not _canonical_intact() or type(registry) is not _Registry or type(handle) is not _Handle:
        raise ValueError("canonical registered fixture required")
    current = _REQUIRE(registry, handle)
    _CHECKPOINT("A", current, registry)
    digest, _size = _BYTE_DIGEST(current, registry)
    return PilotTargetDescriptor(current.fixture_instance_id, str(current.database.resolve()),
                                 current.database_identity.st_dev, current.database_identity.st_ino,
                                 current.generation, digest, FIXED_SQL_DIGEST)


@dataclass(frozen=True)
class _Snapshot:
    byte_digest: str
    evidence: object
    schema_rows: tuple


def _snapshot(handle, registry):
    before, _ = _BYTE_DIGEST(handle, registry)
    verifier = _Verifier()
    evidence = _VERIFY(verifier, handle.database)
    connection = _OPEN_READ_ONLY(verifier, handle.database)
    try:
        rows = tuple(connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name, tbl_name"
        ))
    finally:
        connection.close()
    after, _ = _BYTE_DIGEST(handle, registry)
    if before != after:
        raise ValueError("fixture changed during read-only verification")
    return _Snapshot(after, evidence, rows)


def _prestate_valid(snapshot):
    evidence = snapshot.evidence
    return (evidence.index_present is False and evidence.integrity_check == "ok"
            and evidence.user_version == 100 and not any(row[1] == _verifier.FIXED_INDEX
                                                        for row in snapshot.schema_rows))


def classify_outcome(outcome, before, after):
    """A writer report alone never establishes durable effect or rollback."""
    if type(outcome) is not _WriterOutcome or type(before) is not _Snapshot or type(after) is not _Snapshot:
        return UNRESOLVED
    if (outcome.profile != _factory.PROFILE_REPAIR or outcome.security_lifecycle_failure is not None
            or any(type(getattr(outcome, name)) is not bool for name in
                   ("mutation_attempted", "rollback_proven", "commit_proven", "outcome_uncertain", "authorization_denied"))
            or outcome.outcome_uncertain):
        return UNRESOLVED
    evidence = after.evidence
    unchanged = (after.byte_digest == before.byte_digest and after.schema_rows == before.schema_rows
                 and evidence == before.evidence)
    no_commit_proof = (not outcome.commit_proven and
                      (outcome.rollback_proven or (outcome.authorization_denied and not outcome.mutation_attempted)))
    if no_commit_proof and unchanged:
        return NOT_COMMITTED
    added = tuple(row for row in after.schema_rows if row[1] == _verifier.FIXED_INDEX)
    remaining = tuple(row for row in after.schema_rows if row[1] != _verifier.FIXED_INDEX)
    exact_index = (len(added) == 1 and added[0][:3] == ("index", _verifier.FIXED_INDEX, "audit_events")
                   and _verifier.validate_expected_index_sql(added[0][3]))
    exact_callback = (tuple(callback for callback in outcome.callbacks
                            if callback[0] == sqlite3.SQLITE_REINDEX) == (_REINDEX_CALLBACK,))
    if (outcome.commit_proven and outcome.mutation_attempted and not outcome.rollback_proven
            and not outcome.authorization_denied and evidence.expected is True
            and evidence.audit_events_digest == before.evidence.audit_events_digest
            and evidence.user_version == before.evidence.user_version and exact_index and exact_callback
            and remaining == before.schema_rows):
        return COMMITTED
    return UNRESOLVED


@dataclass(frozen=True)
class PilotResult:
    status: str
    reason: str
    pilot_admitted: bool
    transition_outcome: str
    fixture_state: str | None = None
    fixture_disposition: str = "PRESERVE_FOR_EXTERNAL_LIFECYCLE"
    governance_authority: bool = field(default=False, init=False)
    capability_issued: bool = field(default=False, init=False)
    general_execution_permission: bool = field(default=False, init=False)
    full_path_mediation: bool = field(default=False, init=False)
    durable_consumption: bool = field(default=False, init=False)
    cross_process_replay_protection: bool = field(default=False, init=False)
    restart_resume_supported: bool = field(default=False, init=False)
    authority_effect: str = field(default="NONE", init=False)


def _input_error(envelope, request):
    error = _capability._envelope_error(envelope)
    if error:
        return error
    if type(request) is not _Request:
        return "canonical ValidationRequest required"
    error = _capability._identity_error(request.execution_identity, request.authority_reference)
    if error:
        return error
    if type(request.scope) is not _core.WorkflowScope or not all(
        _capability._text(getattr(request.scope, name)) for name in _core.WorkflowScope.__dataclass_fields__
    ):
        return "canonical workflow scope required"
    if type(request.baseline_revision) is not str or not _core.REVISION.fullmatch(request.baseline_revision):
        return "invalid requested baseline"
    if not _capability._text(request.cancellation_binding):
        return "invalid cancellation binding"
    if (request.capability_class != CAPABILITY_CLASS or envelope.capability_class != CAPABILITY_CLASS
            or request.operation != OPERATION or envelope.operation != OPERATION
            or envelope.consumption_policy != _capability.SINGLE_USE):
        return "only one fixed, single-use repair operation is supported"
    return None


def _invoke_repair(handle, registry):
    # No injected adapter or caller SQL: invoke the captured canonical methods.
    repair = _Repair()
    _PRIME(repair)
    return _EXECUTE(repair, handle, registry)


class DisposableRepairPilot:
    """One instance, one terminal attempt; the host cannot supply an adapter."""

    def __init__(self, *, registry=None, validator=None, trusted_current_baseline_reader=None,
                 trusted_target_observer=None):
        self._registry = registry
        self._validator = validator
        self._baseline_reader = trusted_current_baseline_reader
        self._target_observer = trusted_target_observer
        self._claim_lock = threading.Lock()
        self._claim_state = "NEW"

    @property
    def claim_state(self):
        with self._claim_lock:
            return self._claim_state

    def execute(self, envelope, request, handle):
        with self._claim_lock:
            if self._claim_state != "NEW":
                # No new invocation is not proof about the earlier attempt's effect.
                return PilotResult("DENY", "attempt is non-reusable; no new repair invocation", False, UNRESOLVED)
            self._claim_state = "CHECKING"
        try:
            return self._execute_once(envelope, request, handle)
        finally:
            with self._claim_lock:
                self._claim_state = "FINISHED"

    def _execute_once(self, envelope, request, handle):
        admitted = False
        current = None
        try:
            if not _canonical_intact():
                raise ValueError("canonical module/type integrity failed")
            if type(self._registry) is not _Registry or type(self._validator) is not _Validator:
                raise ValueError("canonical registry and capability validator required")
            error = _input_error(envelope, request)
            if error:
                raise ValueError(error)
            if type(handle) is not _Handle:
                raise ValueError("canonical fixture handle required")
            if not callable(self._baseline_reader):
                raise ValueError("trusted current-baseline observation unavailable")
            observed_baseline = self._baseline_reader()
            if (type(observed_baseline) is not str or not _core.REVISION.fullmatch(observed_baseline)
                    or not observed_baseline == request.baseline_revision == request.execution_identity.baseline_revision):
                raise ValueError("observed/request/identity baseline mismatch")
            if not callable(self._target_observer):
                raise ValueError("trusted disposable-target observation unavailable")
            target = self._target_observer(handle)
            error = _descriptor_error(target)
            if error:
                raise ValueError(error)
            if not _canonical_intact():
                raise ValueError("canonical modules changed during observation")
            current = _REQUIRE(self._registry, handle)
            if (current.lifecycle_state != _factory.STATE_READY or current.reusable is not True
                    or current.mutation_attempt_count != 0):
                raise ValueError("fresh pre-prepared READY fixture required")
            _CHECKPOINT("A", current, self._registry)
            observed_identity = (current.fixture_instance_id, str(current.database.resolve()),
                                 current.database_identity.st_dev, current.database_identity.st_ino, current.generation)
            declared_identity = (target.fixture_uuid, target.database_path, target.device_id, target.inode, target.fixture_generation)
            if declared_identity != observed_identity:
                raise ValueError("exact disposable target identity mismatch")
            if not envelope.target == request.target == target.canonical_target():
                raise ValueError("capability exact target mismatch")
            if (target.fixed_sql_digest != FIXED_SQL_DIGEST or _SQL_CHECK() != FIXED_SQL
                    or _factory.REPAIR_SQL_DIGEST != FIXED_SQL_DIGEST):
                raise ValueError("fixed SQL digest mismatch")
            before = _snapshot(current, self._registry)
            if before.byte_digest != target.prestate_digest or not _prestate_valid(before):
                raise ValueError("exact missing-index prestate verification failed")
            with self._claim_lock:
                if self._claim_state != "CHECKING":
                    raise ValueError("attempt claim is not available")
                self._claim_state = "CLAIMED"
            validation = _VALIDATE(self._validator, envelope, request)
            if (not _canonical_intact() or type(validation) is not _ValidationResult
                    or validation.validation_only is not True or validation.execution_authorized is not False
                    or any(getattr(validation, name) != "NONE" for name in
                           ("authority_effect", "execution_effect", "consumption_effect", "reservation_effect"))):
                raise ValueError("invalid non-authorizing capability validation result")
            if validation.status != "PASS":
                raise ValueError("final capability validation denied: " + validation.reason)
            # This is the bounded admission point, not atomic consume-and-execute.
            admitted = True
            current = _TRANSITION(self._registry, current, _factory.STATE_READY, _factory.STATE_MUTATION_TASK_BOUND)
            current = _TRANSITION(self._registry, current, _factory.STATE_MUTATION_TASK_BOUND, _factory.STATE_MUTATION_ATTEMPTED)
            outcome = _invoke_repair(current, self._registry)
            if type(outcome) is _WriterOutcome and outcome.commit_proven is True and not outcome.outcome_uncertain:
                current = _TRANSITION(self._registry, current, _factory.STATE_MUTATION_ATTEMPTED, _factory.STATE_MUTATION_COMMITTED)
                current = _TRANSITION(self._registry, current, _factory.STATE_MUTATION_COMMITTED, _factory.STATE_VERIFYING)
            after = _snapshot(current, self._registry)
            classification = classify_outcome(outcome, before, after)
            if classification != COMMITTED:
                if current.lifecycle_state == _factory.STATE_MUTATION_ATTEMPTED:
                    state = (_factory.STATE_MUTATION_ROLLED_BACK if classification == NOT_COMMITTED
                             else _factory.STATE_MUTATION_OUTCOME_UNKNOWN)
                    current = _TRANSITION(self._registry, current, current.lifecycle_state, state)
                current = self._quarantine(current)
            return PilotResult("PASS" if classification == COMMITTED else "NON_PASS",
                               "independent fixed-repair evidence classified", True, classification,
                               current.lifecycle_state,
                               "PRESERVE_FOR_EXTERNAL_LIFECYCLE" if classification == COMMITTED else "QUARANTINE_FOR_REVIEW")
        except Exception as exc:
            if admitted:
                state = None
                try:
                    current = self._registry.get(handle.fixture_instance_id)
                    if current.lifecycle_state == _factory.STATE_MUTATION_ATTEMPTED:
                        current = _TRANSITION(self._registry, current, current.lifecycle_state, _factory.STATE_MUTATION_OUTCOME_UNKNOWN)
                    current = self._quarantine(current)
                    state = current.lifecycle_state
                except Exception:
                    pass
                return PilotResult("NON_PASS", "effect unresolved: " + type(exc).__name__, True,
                                   UNRESOLVED, state, "PRESERVE_QUARANTINE_FOR_REVIEW")
            return PilotResult("DENY", str(exc), False, NOT_COMMITTED,
                               current.lifecycle_state if current is not None else None)

    def _quarantine(self, handle):
        if handle.lifecycle_state == _factory.STATE_QUARANTINED:
            return handle
        return _TRANSITION(self._registry, handle, handle.lifecycle_state, _factory.STATE_QUARANTINED)

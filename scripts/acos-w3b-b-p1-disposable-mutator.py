#!/usr/bin/env python3
"""Fail-closed policy and transaction semantics for W3B-B-P1."""

from __future__ import annotations

import hashlib
import hmac
import json
import platform
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

RESULT_PASS = "PASS"
RESULT_DENY = "DENY"
RESULT_BLOCKED = "BLOCKED"
RESULT_FAILED_MUTATION = "FAILED_MUTATION"
RESULT_FAILED_POSTSTATE = "FAILED_POSTSTATE"
RESULT_FAILED_DISPOSAL = "FAILED_DISPOSAL"

EFFECT_NONE = "NONE"
EFFECT_ROLLED_BACK = "ATTEMPTED_AND_ROLLED_BACK"
EFFECT_COMMITTED = "COMMITTED_TEST_ONLY_DISPOSABLE_FIXTURE"
EFFECT_UNKNOWN = "UNKNOWN_TEST_ONLY_DISPOSABLE_FIXTURE_EFFECT"

OUTCOME_NOT_STARTED = "NOT_STARTED"
OUTCOME_ROLLED_BACK = "ROLLED_BACK_PROVEN"
OUTCOME_COMMITTED = "COMMITTED_PROVEN"
OUTCOME_UNKNOWN = "UNKNOWN"

STATE_READY = "READY"
STATE_MUTATION_ATTEMPTED = "MUTATION_ATTEMPTED"
STATE_MUTATION_COMMITTED = "MUTATION_COMMITTED"
STATE_MUTATION_ROLLED_BACK = "MUTATION_ROLLED_BACK"
STATE_UNKNOWN = "MUTATION_OUTCOME_UNKNOWN"
STATE_VERIFYING = "VERIFYING"
STATE_QUARANTINED = "QUARANTINED"

PROFILE_SEED = "SEED_INITIALIZER"
PROFILE_FAULT = "FAULT_INJECTOR"
PROFILE_REPAIR = "REPAIR_MUTATOR"
PROFILE_PREFLIGHT_DENY = "PREFLIGHT_DENY"

FIXED_INDEX = "idx_audit_events_aggregate"
FIXED_TABLE = "audit_events"
CANONICAL_SEED_INDEX_NAMES = frozenset(
    {
        "idx_grant_observations_grant_id",
        "idx_authorization_events_authorization",
        "idx_workflow_state_events_task",
        FIXED_INDEX,
    }
)
_DIGEST_PATTERN = re.compile(r"^sha256:([0-9a-f]{64})$")


class MutationPolicyError(RuntimeError):
    """A fail-closed policy or transaction boundary was violated."""


@dataclass(frozen=True)
class Digest256:
    raw: bytes

    def __post_init__(self) -> None:
        if len(self.raw) != 32:
            raise ValueError("SHA-256 digest must contain exactly 32 bytes")

    @classmethod
    def parse(cls, value: str) -> "Digest256":
        match = _DIGEST_PATTERN.fullmatch(value)
        if not match:
            raise ValueError("digest must be sha256:<64 lowercase hex>")
        return cls(bytes.fromhex(match.group(1)))

    @classmethod
    def of_bytes(cls, value: bytes) -> "Digest256":
        return cls(hashlib.sha256(value).digest())

    def serialize(self) -> str:
        return f"sha256:{self.raw.hex()}"

    def constant_time_equals(self, other: "Digest256") -> bool:
        return hmac.compare_digest(self.raw, other.raw)


def canonical_json_bytes(value: Any) -> bytes:
    """Reuse the frozen W3B-A canonical JSON serialization."""

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return Digest256.of_bytes(canonical_json_bytes(value)).serialize()


def digest_without(document: Mapping[str, Any], field: str) -> str:
    value = dict(document)
    value.pop(field, None)
    return canonical_digest(value)


def digests_equal(left: str, right: str) -> bool:
    return Digest256.parse(left).constant_time_equals(Digest256.parse(right))


@dataclass(frozen=True)
class MutationClassification:
    transaction_outcome: str
    mutation_effect: str
    terminal_state: str
    reusable: bool


def classify_mutation_effect(
    *,
    mutation_attempted: bool,
    rollback_proven: bool,
    commit_proven: bool,
) -> MutationClassification:
    """Pure DS-01 mapping; poststate observations are intentionally absent."""

    if rollback_proven and commit_proven:
        return MutationClassification(
            OUTCOME_UNKNOWN, EFFECT_UNKNOWN, STATE_UNKNOWN, False
        )
    if commit_proven:
        return MutationClassification(
            OUTCOME_COMMITTED, EFFECT_COMMITTED, STATE_MUTATION_COMMITTED, False
        )
    if rollback_proven and mutation_attempted:
        return MutationClassification(
            OUTCOME_ROLLED_BACK, EFFECT_ROLLED_BACK,
            STATE_MUTATION_ROLLED_BACK, False
        )
    if not mutation_attempted:
        return MutationClassification(
            OUTCOME_NOT_STARTED, EFFECT_NONE, STATE_READY, True
        )
    return MutationClassification(OUTCOME_UNKNOWN, EFFECT_UNKNOWN, STATE_UNKNOWN, False)


def classify_commit_exception(*, connection_in_transaction: bool) -> str:
    """A commit exception never proves rollback or commit."""

    return "ACTIVE_TRANSACTION" if connection_in_transaction else OUTCOME_UNKNOWN


@dataclass(frozen=True)
class CandidateAuthorizerProfile:
    name: str
    allowed_actions: frozenset[int]
    fixed_index: str | None = None
    fixed_table: str | None = None
    characterized: bool = False

    def decide(
        self,
        action: int,
        arg1: str | None,
        arg2: str | None,
        database: str | None,
        trigger: str | None,
    ) -> int:
        if action not in self.allowed_actions:
            return sqlite3.SQLITE_DENY

        if action == getattr(sqlite3, "SQLITE_REINDEX", -1):
            return (
                sqlite3.SQLITE_OK
                if self.name == PROFILE_SEED
                and arg1 in CANONICAL_SEED_INDEX_NAMES
                and arg2 is None
                and database == "main"
                and trigger is None
                else sqlite3.SQLITE_DENY
            )

        if self.name == PROFILE_FAULT and action == sqlite3.SQLITE_DROP_INDEX:
            return (
                sqlite3.SQLITE_OK
                if arg1 == self.fixed_index and arg2 in {None, self.fixed_table}
                else sqlite3.SQLITE_DENY
            )
        if self.name == PROFILE_REPAIR and action == sqlite3.SQLITE_CREATE_INDEX:
            return (
                sqlite3.SQLITE_OK
                if arg1 == self.fixed_index and arg2 in {None, self.fixed_table}
                else sqlite3.SQLITE_DENY
            )
        if self.name == PROFILE_SEED and action == sqlite3.SQLITE_PRAGMA:
            return sqlite3.SQLITE_OK if arg1 == "user_version" else sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_PRAGMA:
            return sqlite3.SQLITE_DENY
        if self.name in {PROFILE_FAULT, PROFILE_REPAIR}:
            if action in {
                getattr(sqlite3, "SQLITE_INSERT", -1),
                getattr(sqlite3, "SQLITE_UPDATE", -1),
                getattr(sqlite3, "SQLITE_DELETE", -1),
            }:
                return (
                    sqlite3.SQLITE_OK
                    if arg1 in {"sqlite_master", "sqlite_schema"}
                    else sqlite3.SQLITE_DENY
                )
            if action == getattr(sqlite3, "SQLITE_READ", -1):
                return (
                    sqlite3.SQLITE_OK
                    if arg1 in {self.fixed_table, "sqlite_master", "sqlite_schema"}
                    else sqlite3.SQLITE_DENY
                )
        return sqlite3.SQLITE_OK


_REPAIR_REINDEX_CALLBACK = (
    getattr(sqlite3, "SQLITE_REINDEX", -1),
    FIXED_INDEX,
    None,
    "main",
    None,
)


_SEED_ALLOWED = frozenset(
    value
    for value in (
        getattr(sqlite3, "SQLITE_CREATE_TABLE", -1),
        getattr(sqlite3, "SQLITE_CREATE_INDEX", -1),
        getattr(sqlite3, "SQLITE_CREATE_TRIGGER", -1),
        getattr(sqlite3, "SQLITE_INSERT", -1),
        getattr(sqlite3, "SQLITE_UPDATE", -1),
        getattr(sqlite3, "SQLITE_TRANSACTION", -1),
        getattr(sqlite3, "SQLITE_SELECT", -1),
        getattr(sqlite3, "SQLITE_READ", -1),
        getattr(sqlite3, "SQLITE_FUNCTION", -1),
        getattr(sqlite3, "SQLITE_PRAGMA", -1),
        getattr(sqlite3, "SQLITE_REINDEX", -1),
    )
    if value >= 0
)
_FAULT_ALLOWED = frozenset(
    value
    for value in (
        getattr(sqlite3, "SQLITE_DROP_INDEX", -1),
        getattr(sqlite3, "SQLITE_TRANSACTION", -1),
        getattr(sqlite3, "SQLITE_INSERT", -1),
        getattr(sqlite3, "SQLITE_UPDATE", -1),
        getattr(sqlite3, "SQLITE_DELETE", -1),
        getattr(sqlite3, "SQLITE_READ", -1),
    )
    if value >= 0
)
_REPAIR_ALLOWED = frozenset(
    value
    for value in (
        getattr(sqlite3, "SQLITE_CREATE_INDEX", -1),
        getattr(sqlite3, "SQLITE_TRANSACTION", -1),
        getattr(sqlite3, "SQLITE_INSERT", -1),
        getattr(sqlite3, "SQLITE_UPDATE", -1),
        getattr(sqlite3, "SQLITE_DELETE", -1),
        getattr(sqlite3, "SQLITE_READ", -1),
        getattr(sqlite3, "SQLITE_REINDEX", -1),
    )
    if value >= 0
)

CANDIDATE_PROFILES = {
    PROFILE_SEED: CandidateAuthorizerProfile(PROFILE_SEED, _SEED_ALLOWED),
    PROFILE_FAULT: CandidateAuthorizerProfile(
        PROFILE_FAULT, _FAULT_ALLOWED, FIXED_INDEX, FIXED_TABLE
    ),
    PROFILE_REPAIR: CandidateAuthorizerProfile(
        PROFILE_REPAIR, _REPAIR_ALLOWED, FIXED_INDEX, FIXED_TABLE
    ),
    PROFILE_PREFLIGHT_DENY: CandidateAuthorizerProfile(
        PROFILE_PREFLIGHT_DENY, frozenset()
    ),
}


class AuthorizerRecorder:
    """Records synthetic/engine callbacks without claiming characterization."""

    def __init__(
        self,
        profile: CandidateAuthorizerProfile,
        *,
        connection_identity: int | None = None,
    ) -> None:
        self.profile = profile
        self.connection_identity = connection_identity
        self.callbacks: list[tuple[int, str | None, str | None, str | None, str | None]] = []
        self.denied_callbacks: list[
            tuple[int, str | None, str | None, str | None, str | None]
        ] = []

    def __call__(
        self,
        action: int,
        arg1: str | None,
        arg2: str | None,
        database: str | None,
        trigger: str | None,
    ) -> int:
        callback = (action, arg1, arg2, database, trigger)
        self.callbacks.append(callback)
        decision = self.profile.decide(action, arg1, arg2, database, trigger)
        if decision == sqlite3.SQLITE_DENY:
            self.denied_callbacks.append(callback)
        return decision


def install_candidate_authorizer(
    connection: sqlite3.Connection,
    profile_name: str,
) -> AuthorizerRecorder:
    try:
        profile = CANDIDATE_PROFILES[profile_name]
    except KeyError as exc:
        raise MutationPolicyError("unknown capability profile") from exc
    if not hasattr(connection, "set_authorizer"):
        raise MutationPolicyError("sqlite authorizer API is unavailable")
    if profile_name == PROFILE_REPAIR:
        raise MutationPolicyError(
            "repair authorizer requires the internal privileged lifecycle"
        )
    recorder = AuthorizerRecorder(
        profile,
        connection_identity=id(connection),
    )
    connection.set_authorizer(recorder)
    return recorder


def _build_internal_repair_authorizer_claim():
    context_token = object()
    recorder_token = object()
    claimed = False

    class PrivilegedRepairContext:
        """Closure-private one-shot admission state for canonical repair."""

        __slots__ = (
            "_token",
            "canonical_sql_digest",
            "connection_identity",
            "fixture_identity",
            "runtime_fingerprint",
            "expected_callback",
            "authorization_phase",
            "callback_consumed",
            "active",
            "expired",
        )

        def __init__(
            self,
            token: object,
            *,
            canonical_sql_digest: str,
            connection_identity: int,
            fixture_identity: tuple[object, ...],
            runtime_fingerprint: str,
            authorization_phase: str,
        ) -> None:
            if token is not context_token:
                raise MutationPolicyError("privileged repair context is internal only")
            Digest256.parse(canonical_sql_digest)
            Digest256.parse(runtime_fingerprint)
            self._token = token
            self.canonical_sql_digest = canonical_sql_digest
            self.connection_identity = connection_identity
            self.fixture_identity = fixture_identity
            self.runtime_fingerprint = runtime_fingerprint
            self.expected_callback = _REPAIR_REINDEX_CALLBACK
            self.authorization_phase = authorization_phase
            self.callback_consumed = False
            self.active = False
            self.expired = False

        def activate(
            self,
            *,
            canonical_sql_digest: str,
            connection_identity: int,
            fixture_identity: tuple[object, ...],
            runtime_fingerprint: str,
            authorization_phase: str,
        ) -> None:
            if self.expired or self.active or self.callback_consumed:
                raise MutationPolicyError("privileged repair context is stale")
            observed = (
                canonical_sql_digest,
                connection_identity,
                fixture_identity,
                runtime_fingerprint,
                authorization_phase,
            )
            expected = (
                self.canonical_sql_digest,
                self.connection_identity,
                self.fixture_identity,
                self.runtime_fingerprint,
                self.authorization_phase,
            )
            if observed != expected:
                raise MutationPolicyError(
                    "privileged repair context binding mismatch"
                )
            self.active = True

        def admit_reindex(
            self,
            token: object,
            connection_identity: int,
            callback: tuple[
                int, str | None, str | None, str | None, str | None
            ],
        ) -> int:
            if (
                token is not recorder_token
                or self._token is not context_token
                or not self.active
                or self.expired
                or self.callback_consumed
                or connection_identity != self.connection_identity
                or self.authorization_phase != "REPAIR_STATEMENT_PREPARE_EXECUTE"
                or callback != self.expected_callback
            ):
                return sqlite3.SQLITE_DENY
            self.callback_consumed = True
            return sqlite3.SQLITE_OK

        def expire(self) -> None:
            self.active = False
            self.expired = True

    class PrivilegedAuthorizerRecorder(AuthorizerRecorder):
        """Recorder available only through the claimed internal installer."""

        def __init__(
            self,
            token: object,
            *,
            connection_identity: int,
            repair_context: PrivilegedRepairContext,
        ) -> None:
            if token is not recorder_token:
                raise MutationPolicyError("privileged recorder is internal only")
            if type(repair_context) is not PrivilegedRepairContext:
                raise MutationPolicyError("repair context type is not canonical")
            super().__init__(
                CANDIDATE_PROFILES[PROFILE_REPAIR],
                connection_identity=connection_identity,
            )
            self.__repair_context = repair_context

        @property
        def privileged_admission_consumed(self) -> bool:
            return self.__repair_context.callback_consumed

        @property
        def privileged_context_expired(self) -> bool:
            return self.__repair_context.expired

        def __call__(
            self,
            action: int,
            arg1: str | None,
            arg2: str | None,
            database: str | None,
            trigger: str | None,
        ) -> int:
            callback = (action, arg1, arg2, database, trigger)
            self.callbacks.append(callback)
            if action == getattr(sqlite3, "SQLITE_REINDEX", -1):
                decision = self.__repair_context.admit_reindex(
                    recorder_token, self.connection_identity, callback
                )
            else:
                decision = self.profile.decide(
                    action, arg1, arg2, database, trigger
                )
            if decision == sqlite3.SQLITE_DENY:
                self.denied_callbacks.append(callback)
            return decision

    def claim(factory_loader_provenance: object):
        nonlocal claimed
        module = sys.modules.get(__name__)
        if (
            claimed
            or module is None
            or factory_loader_provenance is None
            or getattr(module, "__acos_canonical_loader_provenance__", None)
            is not factory_loader_provenance
        ):
            raise MutationPolicyError(
                "repair installer lacks unclaimed canonical factory provenance"
            )
        claimed = True

        def install(
            connection: sqlite3.Connection,
            *,
            canonical_sql_digest: str,
            fixture_identity: tuple[object, ...],
            runtime_fingerprint: str,
            authorization_phase: str,
        ) -> tuple[AuthorizerRecorder, object]:
            if not hasattr(connection, "set_authorizer"):
                raise MutationPolicyError("sqlite authorizer API is unavailable")
            context = PrivilegedRepairContext(
                context_token,
                canonical_sql_digest=canonical_sql_digest,
                connection_identity=id(connection),
                fixture_identity=fixture_identity,
                runtime_fingerprint=runtime_fingerprint,
                authorization_phase=authorization_phase,
            )
            recorder = PrivilegedAuthorizerRecorder(
                recorder_token,
                connection_identity=id(connection),
                repair_context=context,
            )
            connection.set_authorizer(recorder)
            return recorder, context

        return install

    return claim


_claim_internal_repair_authorizer_installer = (
    _build_internal_repair_authorizer_claim()
)
del _build_internal_repair_authorizer_claim


@dataclass(frozen=True)
class RuntimePreflightEvidence:
    python_version: str
    sqlite_version: str
    platform: str
    compile_options: tuple[str, ...]
    compile_options_digest: str
    runtime_fingerprint: str
    authorizer_api_present: bool
    authorizer_installation_proven: bool
    bounded_deny_self_check: bool
    mutation_permitted: bool = False


def runtime_preflight(
    *,
    canonical_sql_digest: str = "sha256:" + ("0" * 64),
    canonical_module_fingerprint: str = "sha256:" + ("0" * 64),
) -> RuntimePreflightEvidence:
    """IC-01 non-mutating runtime check; compile options are evidence only."""

    connection = sqlite3.connect(":memory:")
    try:
        compile_options = tuple(
            sorted(str(row[0]) for row in connection.execute("PRAGMA compile_options"))
        )
        api_present = hasattr(connection, "set_authorizer")
        if not api_present:
            raise MutationPolicyError("sqlite authorizer API is unavailable")

        recorder = install_candidate_authorizer(connection, PROFILE_PREFLIGHT_DENY)
        denied = False
        try:
            connection.execute("SELECT 1").fetchone()
        except sqlite3.DatabaseError:
            denied = True
        finally:
            connection.set_authorizer(None)
        if not denied or not recorder.callbacks:
            raise MutationPolicyError("bounded authorizer deny self-check failed")
        compile_options_digest = canonical_digest(compile_options)
        runtime_fingerprint = canonical_digest(
            {
                "python_implementation": platform.python_implementation(),
                "python_version": sys.version.split()[0],
                "sqlite_adapter": sqlite3.__name__,
                "sqlite_adapter_version": getattr(sqlite3, "version", "unknown"),
                "sqlite_runtime_version": sqlite3.sqlite_version,
                "sqlite_threadsafety": sqlite3.threadsafety,
                "platform": platform.platform(),
                "compile_options_digest": compile_options_digest,
                "canonical_sql_digest": canonical_sql_digest,
                "canonical_module_fingerprint": canonical_module_fingerprint,
            }
        )
        return RuntimePreflightEvidence(
            python_version=sys.version.split()[0],
            sqlite_version=sqlite3.sqlite_version,
            platform=platform.platform(),
            compile_options=compile_options,
            compile_options_digest=compile_options_digest,
            runtime_fingerprint=runtime_fingerprint,
            authorizer_api_present=api_present,
            authorizer_installation_proven=True,
            bounded_deny_self_check=True,
        )
    finally:
        connection.close()


@dataclass(frozen=True)
class RepairResult:
    operation_id: str
    result: str
    reason_code: str
    reason: str
    state: str
    fixture_instance_id: str
    binding_id: str
    plan_id: str
    prestate_digest: str | None
    poststate_digest: str | None
    mutation_attempt_count: int
    transaction_outcome: str
    mutation_effect: str
    poststate_status: str
    disposal_state: str
    started_at: str
    completed_at: str
    scope: str = "DISPOSABLE_FIXTURE_ONLY"
    evidence_class: str = "DECLARED_RESULT_EVIDENCE"
    governance_status: str = "UNAUTHENTICATED_SHADOW"
    effects: str = "NONE"
    eligible_for_execution: bool = False
    fixture_mutation_scope: str = "TEST_ONLY_DISPOSABLE_FIXTURE"
    production_repair_effect: str = "NONE"
    production_eligibility: bool = False
    operational_entry_effect: str = "NONE"
    profile_version: str = "1.0"
    contract_version: str = "2.0"
    object_type: str = "disposable_fixture_repair_result"
    operation: str = "shadow_disposable_index_repair"

    def to_mapping(self) -> dict[str, object]:
        return asdict(self)

    def to_canonical_json(self) -> str:
        return json.dumps(
            self.to_mapping(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )


def profile_decisions(
    profile_name: str,
    callbacks: Iterable[
        tuple[int, str | None, str | None, str | None, str | None]
    ],
) -> Sequence[int]:
    """Pure helper for Category A synthetic callback testing."""

    try:
        profile = CANDIDATE_PROFILES[profile_name]
    except KeyError as exc:
        raise MutationPolicyError("unknown capability profile") from exc
    return tuple(profile.decide(*callback) for callback in callbacks)

#!/usr/bin/env python3
"""W3B-B-P1 fixed disposable-fixture orchestration surface.

The module has no command-line entry point and performs no work at import.
Its runner is gated by a process-local observation tied to one exact research
binding. That observation limits accidental invocation; it is not authority.
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping

_SCRIPT_DIRECTORY = Path(__file__).resolve().parent
_CANONICAL_RUNNER_NAME = "acos_w3b_b_p1_single_index_repair"
_CANONICAL_FACTORY_NAME = "acos_w3b_b_p1_fixture_factory"
_FACTORY_LOADER_PROVENANCE = object()


def _source_digest(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _load_canonical_factory() -> ModuleType:
    module_name = _CANONICAL_FACTORY_NAME
    filename = "acos-w3b-b-p1-fixture-factory.py"
    path = _SCRIPT_DIRECTORY / filename
    source_digest = _source_digest(path)
    existing = sys.modules.get(module_name)
    if existing is not None:
        existing_path = Path(str(getattr(existing, "__file__", ""))).resolve()
        if (
            getattr(existing, "__acos_canonical_loader_provenance__", None)
            is not _FACTORY_LOADER_PROVENANCE
            or existing_path != path.resolve()
            or getattr(existing, "__acos_canonical_source_sha256__", None)
            != source_digest
            or _source_digest(existing_path) != source_digest
        ):
            raise RuntimeError("canonical fixture-factory identity collision")
        return existing
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load fixed W3B-B-P1 module: {filename}")
    module = importlib.util.module_from_spec(spec)
    module.__acos_canonical_source_sha256__ = source_digest
    module.__acos_canonical_loader_provenance__ = _FACTORY_LOADER_PROVENANCE
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    if sys.modules.get(module_name) is not module:
        raise RuntimeError("canonical fixture-factory object was replaced during load")
    return module


factory_module = _load_canonical_factory()
mutator_module = factory_module._load_fixed_policy_module()
verifier_module = factory_module.load_canonical_sibling(
    "acos_w3b_b_p1_poststate_verifier", "acos-w3b-b-p1-poststate-verifier.py"
)
w3b_a_module = factory_module.load_canonical_sibling(
    "acos_w3b_a_read_only_repair_planner",
    "acos-w3b-a-read-only-repair-planner.py",
)

_runner_module = sys.modules.get(__name__)
if __name__ != _CANONICAL_RUNNER_NAME or sys.modules.get(_CANONICAL_RUNNER_NAME) is not _runner_module:
    raise RuntimeError("runner must be loaded as the canonical module object")
_runner_source_digest = _source_digest(Path(__file__).resolve())
_declared_runner_digest = getattr(
    _runner_module, "__acos_canonical_source_sha256__", None
)
if _declared_runner_digest not in {None, _runner_source_digest}:
    raise RuntimeError("canonical runner source identity mismatch")
_runner_module.__acos_canonical_source_sha256__ = _runner_source_digest
_runner_module.__acos_canonical_loader_provenance__ = (
    factory_module._CANONICAL_SIBLING_PROVENANCE
)
factory_module._CANONICAL_MODULES[_CANONICAL_RUNNER_NAME] = _runner_module


class OrchestrationBlocked(RuntimeError):
    """Required evidence failed closed or physical effect became uncertain."""


_GATE_TOKEN = object()
_MUTATION_TEST_TASK_ID = "ACOS-MIG-W3B-B-P1-MUTATION-TEST"
_TASK_ENV = "ACOS_W3B_B_P1_MUTATION_TEST_TASK_ID"
_BINDING_ENV = "ACOS_W3B_B_P1_MUTATION_TEST_BINDING_DIGEST"


class MutationTestGateObservation:
    """Non-authority observation; callers cannot construct an authorized gate."""

    __slots__ = ("task_id", "binding_digest", "matched")

    def __init__(
        self,
        token: object,
        task_id: str,
        binding_digest: str,
        matched: bool,
    ) -> None:
        if token is not _GATE_TOKEN:
            raise TypeError("MutationTestGateObservation is not caller-constructible")
        self.task_id = task_id
        self.binding_digest = binding_digest
        self.matched = matched

    def require(self, binding: Mapping[str, Any]) -> None:
        if not self.matched:
            raise OrchestrationBlocked("exact mutation-test gate observation is absent")
        if self.task_id != _MUTATION_TEST_TASK_ID:
            raise OrchestrationBlocked("mutation-test task observation mismatch")
        if not mutator_module.digests_equal(
            self.binding_digest, str(binding["binding_digest"])
        ):
            raise OrchestrationBlocked("mutation-test binding observation mismatch")


def observe_mutation_test_gate(
    binding: Mapping[str, Any],
) -> MutationTestGateObservation:
    """Observe exact task/binding environment facts without creating authority."""

    task_id = os.environ.get(_TASK_ENV, "")
    binding_digest = os.environ.get(_BINDING_ENV, "")
    expected_digest = str(binding.get("binding_digest", ""))
    matched = False
    try:
        matched = (
            task_id == _MUTATION_TEST_TASK_ID
            and mutator_module.digests_equal(binding_digest, expected_digest)
        )
    except ValueError:
        matched = False
    return MutationTestGateObservation(
        _GATE_TOKEN, task_id, binding_digest, matched
    )


_REQUIRED_BINDING_VALUES = {
    "profile_version": "1.0",
    "contract_version": "2.0",
    "object_type": "disposable_fixture_research_binding",
    "task_id": "ACOS-MIG-W3B-B-P1-IMPLEMENTATION-02",
    "fixture_factory_version": "w3b-b-p1/1.0",
    "allowed_action": "RECREATE_MISSING_CANONICAL_INDEX",
    "maximum_mutation_count": 1,
    "scope": "DISPOSABLE_FIXTURE_ONLY",
    "evidence_class": "DECLARED_BINDING_EVIDENCE",
    "governance_status": "UNAUTHENTICATED_SHADOW",
    "effects": "NONE",
    "eligible_for_execution": False,
    "fixture_mutation_scope": "TEST_ONLY_DISPOSABLE_FIXTURE",
    "production_repair_effect": "NONE",
    "production_eligibility": False,
    "operational_entry_effect": "NONE",
}

_DIGEST_FIELDS = {
    "binding_digest",
    "chatgpt_task_digest",
    "canonical_seed_digest",
    "pre_mutation_fixture_digest",
    "fault_profile_digest",
    "plan_digest",
    "evidence_set_digest",
    "expected_postconditions_digest",
}

_OBJECT_FIELDS = {
    "chatgpt_task_evidence",
    "fault_profile",
    "snapshot_reference",
    "repair_evidence",
    "repair_plan",
    "plan_verification",
    "expected_postconditions",
}

_ALLOWED_BINDING_FIELDS = {
    "profile_version", "contract_version", "object_type", "binding_id",
    "binding_digest", "task_id", "user_decision_reference",
    "chatgpt_task_evidence", "chatgpt_task_digest", "fixture_instance_id",
    "fixture_factory_version", "canonical_seed_digest",
    "pre_mutation_fixture_digest", "fault_profile", "fault_profile_digest",
    "snapshot_reference", "repair_evidence", "repair_plan",
    "plan_verification", "plan_id", "plan_digest", "evidence_set_digest",
    "allowed_action", "expected_postconditions",
    "expected_postconditions_digest", "maximum_mutation_count", "issued_at",
    "expires_at", "operation_id", "nonce", "executor_claim",
    "authorization_source_claim", "scope", "evidence_class",
    "governance_status", "effects", "eligible_for_execution",
    "fixture_mutation_scope", "production_repair_effect",
    "production_eligibility", "operational_entry_effect",
}


def _require_mapping(binding: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    value = binding.get(field)
    if not isinstance(value, Mapping):
        raise OrchestrationBlocked(f"missing canonical object: {field}")
    return value


def _require_digest_equal(left: str, right: str, reason: str) -> None:
    try:
        equal = mutator_module.digests_equal(left, right)
    except ValueError as exc:
        raise OrchestrationBlocked(reason) from exc
    if not equal:
        raise OrchestrationBlocked(reason)


def _parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise OrchestrationBlocked(f"invalid timestamp: {field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OrchestrationBlocked(f"invalid timestamp: {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OrchestrationBlocked(f"timestamp must be timezone-aware: {field}")
    return parsed.astimezone(timezone.utc)


def _validate_lifetime(
    binding: Mapping[str, Any], now: datetime | None
) -> None:
    issued_at = _parse_timestamp(binding.get("issued_at"), "issued_at")
    expires_at = _parse_timestamp(binding.get("expires_at"), "expires_at")
    if issued_at >= expires_at:
        raise OrchestrationBlocked("binding lifetime is empty or reversed")
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if observed_at < issued_at or observed_at >= expires_at:
        raise OrchestrationBlocked("research binding is not currently valid")


def validate_research_binding(
    binding: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> None:
    """Validate actual W3B-A objects, canonical digests, and lifetime."""

    if set(binding) != _ALLOWED_BINDING_FIELDS:
        raise OrchestrationBlocked("research binding field set is not closed")
    for key, expected in _REQUIRED_BINDING_VALUES.items():
        if binding.get(key) != expected:
            raise OrchestrationBlocked(f"research binding mismatch: {key}")
    for key in _DIGEST_FIELDS:
        try:
            mutator_module.Digest256.parse(str(binding.get(key, "")))
        except ValueError as exc:
            raise OrchestrationBlocked(f"invalid canonical digest: {key}") from exc
    for field in _OBJECT_FIELDS:
        _require_mapping(binding, field)

    if binding["canonical_seed_digest"] != factory_module.CANONICAL_SEED_DIGEST:
        raise OrchestrationBlocked("binding does not pin the canonical W3A seed")

    task_evidence = _require_mapping(binding, "chatgpt_task_evidence")
    fault_profile = _require_mapping(binding, "fault_profile")
    snapshot = _require_mapping(binding, "snapshot_reference")
    evidence = _require_mapping(binding, "repair_evidence")
    plan = _require_mapping(binding, "repair_plan")
    verification = _require_mapping(binding, "plan_verification")
    postconditions = _require_mapping(binding, "expected_postconditions")

    if task_evidence != {
        "task_id": binding["task_id"],
        "user_decision_reference": binding["user_decision_reference"],
        "scope": "TEST_ONLY_DISPOSABLE_FIXTURE",
    }:
        raise OrchestrationBlocked("task evidence differs from binding")
    if fault_profile != {
        "profile": factory_module.PROFILE_FAULT,
        "statement": factory_module.FAULT_SQL,
        "target_index": mutator_module.FIXED_INDEX,
        "target_table": mutator_module.FIXED_TABLE,
    }:
        raise OrchestrationBlocked("fault profile differs from fixed capability")
    if postconditions != {
        "index_name": verifier_module.FIXED_INDEX,
        "table_name": verifier_module.FIXED_TABLE,
        "index_columns": list(verifier_module.FIXED_COLUMNS),
        "unexpected_schema_objects": [],
    }:
        raise OrchestrationBlocked("expected postconditions differ from fixed model")

    expected_types = {
        "snapshot_reference": snapshot,
        "repair_evidence": evidence,
        "repair_plan": plan,
        "repair_plan_verification": verification,
    }
    for expected_type, value in expected_types.items():
        if value.get("object_type") != expected_type:
            raise OrchestrationBlocked(
                f"W3B-A object type mismatch: {expected_type}"
            )

    recomputed = {
        "chatgpt_task_digest": mutator_module.canonical_digest(task_evidence),
        "fault_profile_digest": mutator_module.canonical_digest(fault_profile),
        "evidence_set_digest": mutator_module.digest_without(
            evidence, "evidence_set_digest"
        ),
        "plan_digest": mutator_module.digest_without(plan, "plan_digest"),
        "expected_postconditions_digest": mutator_module.canonical_digest(
            postconditions
        ),
        "binding_digest": mutator_module.digest_without(binding, "binding_digest"),
    }
    for field, actual in recomputed.items():
        _require_digest_equal(
            str(binding[field]), actual, f"recomputed digest mismatch: {field}"
        )

    if plan.get("plan_state") != "PLANNED":
        raise OrchestrationBlocked("repair plan is not in PLANNED state")
    if verification.get("verification_state") != "PLAN_VERIFIED":
        raise OrchestrationBlocked("repair plan verification is not terminal")
    if plan.get("plan_id") != binding.get("plan_id"):
        raise OrchestrationBlocked("binding plan_id differs from repair plan")
    if verification.get("plan_id") != plan.get("plan_id"):
        raise OrchestrationBlocked("plan verification plan_id mismatch")

    snapshot_digest = str(snapshot.get("snapshot_digest", ""))
    cross_object_digests = {
        "pre_mutation_fixture_digest": str(
            binding["pre_mutation_fixture_digest"]
        ),
        "repair_evidence.snapshot_digest": str(evidence.get("snapshot_digest", "")),
        "repair_plan.snapshot_digest": str(plan.get("snapshot_digest", "")),
        "plan_verification.snapshot_digest": str(
            verification.get("snapshot_digest", "")
        ),
    }
    for label, value in cross_object_digests.items():
        _require_digest_equal(
            snapshot_digest, value, f"snapshot binding mismatch: {label}"
        )

    evidence_digest = str(evidence.get("evidence_set_digest", ""))
    for label, value in {
        "binding.evidence_set_digest": str(binding["evidence_set_digest"]),
        "repair_plan.evidence_set_digest": str(
            plan.get("evidence_set_digest", "")
        ),
        "plan_verification.evidence_set_digest": str(
            verification.get("evidence_set_digest", "")
        ),
    }.items():
        _require_digest_equal(
            evidence_digest, value, f"evidence binding mismatch: {label}"
        )

    plan_digest = str(plan.get("plan_digest", ""))
    _require_digest_equal(
        plan_digest, str(binding["plan_digest"]), "binding plan digest mismatch"
    )
    _require_digest_equal(
        plan_digest,
        str(verification.get("plan_digest", "")),
        "plan verification digest mismatch",
    )

    if evidence.get("snapshot_size") != snapshot.get("snapshot_size"):
        raise OrchestrationBlocked("evidence snapshot size mismatch")
    if plan.get("snapshot_size") != snapshot.get("snapshot_size"):
        raise OrchestrationBlocked("plan snapshot size mismatch")
    if plan.get("observed_store_version") != snapshot.get(
        "observed_store_version"
    ):
        raise OrchestrationBlocked("plan store version mismatch")

    try:
        expected_verification = w3b_a_module.verify_plan_documents(
            snapshot,
            evidence,
            plan,
            str(verification.get("verification_id", "")),
            str(verification.get("verified_at", "")),
        )
    except Exception as exc:
        raise OrchestrationBlocked(
            "frozen W3B-A plan verification rejected the supplied objects"
        ) from exc
    if mutator_module.canonical_digest(
        expected_verification
    ) != mutator_module.canonical_digest(verification):
        raise OrchestrationBlocked(
            "plan verification object differs from frozen W3B-A output"
        )

    _validate_lifetime(binding, now)


def validate_current_fixture_binding(
    binding: Mapping[str, Any],
    handle: Any,
    registry: Any,
) -> str:
    """Bind the verified current fixture bytes to the W3B-A snapshot chain."""

    current_digest, current_size = factory_module.fixture_byte_digest(
        handle, registry
    )
    snapshot = _require_mapping(binding, "snapshot_reference")
    if binding.get("fixture_instance_id") != handle.fixture_instance_id:
        raise OrchestrationBlocked("fixture_instance_id binding mismatch")
    _require_digest_equal(
        current_digest,
        str(binding["pre_mutation_fixture_digest"]),
        "current fixture digest differs from bound prestate",
    )
    _require_digest_equal(
        current_digest,
        str(snapshot.get("snapshot_digest", "")),
        "current fixture digest differs from W3B-A snapshot",
    )
    if current_size != snapshot.get("snapshot_size"):
        raise OrchestrationBlocked("current fixture size differs from W3B-A snapshot")
    return current_digest


def load_research_binding(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise OrchestrationBlocked("research binding must be an object")
    validate_research_binding(value)
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_result(
    *,
    binding: Mapping[str, Any],
    result: str,
    reason_code: str,
    reason: str,
    state: str,
    prestate_digest: str | None,
    poststate_digest: str | None,
    mutation_attempt_count: int,
    transaction_outcome: str,
    mutation_effect: str,
    poststate_status: str,
    disposal_state: str,
    started_at: str,
) -> Any:
    return mutator_module.RepairResult(
        operation_id=str(binding["operation_id"]),
        result=result,
        reason_code=reason_code,
        reason=reason,
        state=state,
        fixture_instance_id=str(binding["fixture_instance_id"]),
        binding_id=str(binding["binding_id"]),
        plan_id=str(binding["plan_id"]),
        prestate_digest=prestate_digest,
        poststate_digest=poststate_digest,
        mutation_attempt_count=mutation_attempt_count,
        transaction_outcome=transaction_outcome,
        mutation_effect=mutation_effect,
        poststate_status=poststate_status,
        disposal_state=disposal_state,
        started_at=started_at,
        completed_at=_now(),
    )


class DisposableSingleIndexRepairRunner:
    """Orchestrates only the fixed disposable-fixture research operation."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()
        self.registry = factory_module.FixtureRegistry()
        self.factory = factory_module.DisposableFixtureFactory(self.registry)
        self.seed_initializer = factory_module.SeedInitializer(self.repository_root)
        self.fault_injector = factory_module.FaultInjector()
        self.repair_mutator = factory_module.RepairMutator()
        self.verifier = verifier_module.PoststateVerifier()

    def _inject_fixed_fault(self, handle: Any) -> Any:
        construction = self.fault_injector.inject(handle, self.registry)
        if not construction.commit_proven:
            self.factory.quarantine(handle)
            if construction.outcome_uncertain:
                raise OrchestrationBlocked(
                    "fault construction physical effect is unknown; fixture quarantined"
                )
            raise OrchestrationBlocked(
                "fault construction did not commit; fixture quarantined"
            )
        factory_module.verify_identity_checkpoint("C", handle, self.registry)
        return handle

    def run(self, binding: Mapping[str, Any]) -> Any:
        """Execute only under a separately authorized Category B task."""

        started_at = _now()
        validate_research_binding(binding)
        observe_mutation_test_gate(binding).require(binding)
        self.repair_mutator.prime_runtime_compatibility()

        handle = self.factory.create(str(binding["fixture_instance_id"]))
        prestate_digest: str | None = None
        effect = mutator_module.EFFECT_NONE

        try:
            self.seed_initializer.initialize(handle, self.registry)
            factory_module.verify_identity_checkpoint("C", handle, self.registry)
            self._inject_fixed_fault(handle)

            prestate = self.verifier.verify(handle.database)
            if prestate.index_present:
                raise OrchestrationBlocked("fault prestate still contains fixed index")
            prestate_digest = validate_current_fixture_binding(
                binding, handle, self.registry
            )

            bound = self.registry.transition(
                handle,
                factory_module.STATE_READY,
                factory_module.STATE_MUTATION_TASK_BOUND,
            )
            attempted = self.registry.transition(
                bound,
                factory_module.STATE_MUTATION_TASK_BOUND,
                factory_module.STATE_MUTATION_ATTEMPTED,
            )

            writer_outcome = self.repair_mutator.execute(attempted, self.registry)
            classification = mutator_module.classify_mutation_effect(
                mutation_attempted=writer_outcome.mutation_attempted,
                rollback_proven=writer_outcome.rollback_proven,
                commit_proven=writer_outcome.commit_proven,
            )
            effect = classification.mutation_effect

            if (
                writer_outcome.authorization_denied
                and not writer_outcome.mutation_attempted
            ):
                quarantined = self.factory.quarantine(attempted)
                return _make_result(
                    binding=binding,
                    result=mutator_module.RESULT_DENY,
                    reason_code="REPAIR_AUTHORIZATION_DENIED",
                    reason=(
                        "Repair authorization failed before mutation-capable "
                        "execution; DS-01 does not apply."
                    ),
                    state=quarantined.lifecycle_state,
                    prestate_digest=prestate_digest,
                    poststate_digest=None,
                    mutation_attempt_count=attempted.mutation_attempt_count,
                    transaction_outcome=mutator_module.OUTCOME_NOT_STARTED,
                    mutation_effect=mutator_module.EFFECT_NONE,
                    poststate_status="NOT_EVALUATED",
                    disposal_state="QUARANTINED",
                    started_at=started_at,
                )

            if classification.transaction_outcome != mutator_module.OUTCOME_COMMITTED:
                if classification.transaction_outcome == mutator_module.OUTCOME_ROLLED_BACK:
                    terminal = self.registry.transition(
                        attempted,
                        factory_module.STATE_MUTATION_ATTEMPTED,
                        factory_module.STATE_MUTATION_ROLLED_BACK,
                    )
                elif writer_outcome.outcome_uncertain or writer_outcome.mutation_attempted:
                    terminal = self.registry.transition(
                        attempted,
                        factory_module.STATE_MUTATION_ATTEMPTED,
                        factory_module.STATE_MUTATION_OUTCOME_UNKNOWN,
                    )
                else:
                    terminal = attempted
                quarantined = self.factory.quarantine(terminal)
                return _make_result(
                    binding=binding,
                    result=mutator_module.RESULT_FAILED_MUTATION,
                    reason_code=(
                        writer_outcome.security_lifecycle_failure
                        or "MUTATION_OUTCOME_NOT_COMMITTED"
                    ),
                    reason=(
                        "The privileged security lifecycle did not close cleanly; "
                        "the physical effect is treated as unknown."
                        if writer_outcome.security_lifecycle_failure
                        else "The physical mutation effect was not proven committed."
                    ),
                    state=quarantined.lifecycle_state,
                    prestate_digest=prestate_digest,
                    poststate_digest=None,
                    mutation_attempt_count=attempted.mutation_attempt_count,
                    transaction_outcome=classification.transaction_outcome,
                    mutation_effect=effect,
                    poststate_status="INDETERMINATE",
                    disposal_state="QUARANTINED",
                    started_at=started_at,
                )

            committed = self.registry.transition(
                attempted,
                factory_module.STATE_MUTATION_ATTEMPTED,
                factory_module.STATE_MUTATION_COMMITTED,
            )
            factory_module.verify_identity_checkpoint("C", committed, self.registry)
            verifying = self.registry.transition(
                committed,
                factory_module.STATE_MUTATION_COMMITTED,
                factory_module.STATE_VERIFYING,
            )
            poststate = self.verifier.verify(verifying.database)
            if not poststate.expected:
                self.factory.quarantine(verifying)
                return _make_result(
                    binding=binding,
                    result=mutator_module.RESULT_FAILED_POSTSTATE,
                    reason_code="POSTSTATE_UNEXPECTED",
                    reason="Independent poststate evidence did not match the fixed index.",
                    state=factory_module.STATE_QUARANTINED,
                    prestate_digest=prestate_digest,
                    poststate_digest=poststate.schema_digest,
                    mutation_attempt_count=attempted.mutation_attempt_count,
                    transaction_outcome=classification.transaction_outcome,
                    mutation_effect=effect,
                    poststate_status="UNEXPECTED",
                    disposal_state="QUARANTINED",
                    started_at=started_at,
                )

            try:
                disposed = self.factory.dispose(verifying)
            except Exception:
                return _make_result(
                    binding=binding,
                    result=mutator_module.RESULT_FAILED_DISPOSAL,
                    reason_code="DISPOSAL_FAILED",
                    reason="Disposal failed; the prior mutation effect is preserved.",
                    state=verifying.lifecycle_state,
                    prestate_digest=prestate_digest,
                    poststate_digest=poststate.schema_digest,
                    mutation_attempt_count=attempted.mutation_attempt_count,
                    transaction_outcome=classification.transaction_outcome,
                    mutation_effect=effect,
                    poststate_status="EXPECTED",
                    disposal_state="FAILED",
                    started_at=started_at,
                )

            return _make_result(
                binding=binding,
                result=mutator_module.RESULT_PASS,
                reason_code="DISPOSABLE_REPAIR_VERIFIED",
                reason="The fixed disposable repair and independent poststate passed.",
                state=disposed.lifecycle_state,
                prestate_digest=prestate_digest,
                poststate_digest=poststate.schema_digest,
                mutation_attempt_count=attempted.mutation_attempt_count,
                transaction_outcome=classification.transaction_outcome,
                mutation_effect=effect,
                poststate_status="EXPECTED",
                disposal_state="DISPOSED",
                started_at=started_at,
            )
        except Exception:
            try:
                current = self.registry.get(handle.fixture_instance_id)
            except Exception:
                current = handle
            if current.lifecycle_state not in {
                factory_module.STATE_DISPOSED,
                factory_module.STATE_QUARANTINED,
            }:
                try:
                    self.factory.quarantine(current)
                except Exception:
                    pass
            raise

#!/usr/bin/env python3
"""Run deterministic, fixture-only ACOS cross-component scenarios."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PASS = "PASS"
DENY = "DENY"
BLOCKED = "BLOCKED"
RESULTS = {PASS, DENY, BLOCKED}
ROOT = Path(__file__).resolve().parents[1]

COMPONENTS = {
    "runtime_identity": "scripts/acos-runtime-identity-simulator.py",
    "filesystem_permission": "scripts/acos-filesystem-permission-checker.py",
    "git_operation": "scripts/acos-git-operation-gate.py",
    "audit_jsonl": "scripts/acos-audit-jsonl-writer.py",
    "advisory_gate": "scripts/acos-advisory-gate-checker.py",
    "user_decision_gate": "scripts/acos-user-decision-gate-checker.py",
}

COMPONENT_FIXTURE_DIRECTORIES = {
    "runtime_identity": "fixtures/runtime-identity",
    "filesystem_permission": "fixtures/filesystem-permission",
    "git_operation": "fixtures/git-operation",
    "audit_jsonl": "fixtures/audit-jsonl",
    "advisory_gate": "fixtures/advisory-gate",
    "user_decision_gate": "fixtures/user-decision-gate",
}
SCENARIO_FIXTURE_DIRECTORY = ROOT / "fixtures/validation-scenarios"

MODES = {
    "validate_scenario",
    "run_pipeline",
    "verify_component_contracts",
    "compare_results",
    "detect_policy_drift",
}

SCENARIO_TYPES = {
    "valid_task_lifecycle",
    "blocked_task_resume",
    "unauthorized_runtime",
    "producer_spoofing",
    "filesystem_scope_escape",
    "git_authorization_inheritance",
    "blanket_staging_attempt",
    "unauthorized_commit",
    "unauthorized_push",
    "force_push_attempt",
    "audit_as_authorization",
    "advisory_as_authorization",
    "user_decision_as_git_authorization",
    "missing_user_decision",
    "stale_user_decision",
    "duplicate_user_decision_consumption",
    "mandatory_advisory_skipped",
    "advisory_rework_ignored",
    "advisory_blocked_ignored",
    "wrong_project_binding",
    "wrong_task_binding",
    "wrong_branch_or_head",
    "audit_chain_tampering",
    "component_contract_mismatch",
    "component_result_conflict",
    "policy_version_mismatch",
    "policy_mapping_drift",
    "incomplete_lifecycle",
    "illegal_next_task_start",
    "valid_commit_then_push_separation",
    "valid_end_to_end_shadow_flow",
    "read_only_validation",
}

LIFECYCLE_STATES = {
    "SCENARIO_VALIDATED",
    "PIPELINE_READY",
    "PIPELINE_PASS",
    "PIPELINE_DENIED",
    "PIPELINE_BLOCKED",
    "COMPONENT_CONTRACT_INVALID",
    "IDENTITY_INVALID",
    "USER_DECISION_REQUIRED",
    "USER_DECISION_INVALID",
    "ADVISORY_REQUIRED",
    "ADVISORY_INVALID",
    "FILESYSTEM_SCOPE_INVALID",
    "GIT_AUTHORIZATION_INVALID",
    "AUDIT_CHAIN_INVALID",
    "POLICY_DRIFT_DETECTED",
    "FINAL_CHATGPT_DECISION_REQUIRED",
    "NEXT_USER_DECISION_REQUIRED",
}

DEFAULT_ORDER = [
    "runtime_identity",
    "user_decision_gate",
    "filesystem_permission",
    "advisory_gate",
    "git_operation",
    "audit_jsonl",
]

NOTICE = (
    "Fixture-only evaluation; no real operation, authorization, external call, "
    "or production enforcement occurred."
)


class ScenarioBlocked(Exception):
    """Raised when a scenario cannot be evaluated safely."""


class ScenarioDenied(Exception):
    """Raised for an explicit cross-component governance violation."""


@dataclass
class ScenarioResult:
    scenario_id: str
    mode: str | None
    scenario_type: str | None
    project: str | None
    task_id: str | None
    required_components: list[str] | None
    executed_components: list[str] = field(default_factory=list)
    skipped_components: list[str] = field(default_factory=list)
    component_order: list[str] | None = None
    component_results: list[dict[str, Any]] = field(default_factory=list)
    component_contracts_valid: bool | None = None
    identity_valid: bool | None = None
    scope_valid: bool | None = None
    user_decision_valid: bool | None = None
    advisory_valid: bool | None = None
    git_authorization_valid: bool | None = None
    audit_chain_valid: bool | None = None
    policy_drift_detected: bool | None = None
    lifecycle_state: str | None = None
    allowed: bool = False
    overall_result: str = BLOCKED
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    failed_components: list[str] = field(default_factory=list)
    denied_components: list[str] = field(default_factory=list)
    blocked_components: list[str] = field(default_factory=list)
    source: str = "<memory>"
    expected_result: str | None = None
    expectation_met: bool | None = None
    policy_versions: dict[str, str] | None = None
    policy_digests: dict[str, str] | None = None
    version_mismatches: list[str] = field(default_factory=list)
    digest_mismatches: list[str] = field(default_factory=list)
    result_conflicts: list[str] = field(default_factory=list)
    lifecycle_steps: list[str] | None = None
    completed_steps: list[str] | None = None
    missing_steps: list[str] = field(default_factory=list)
    invalid_order_steps: list[str] = field(default_factory=list)
    next_required_authority: str | None = None


def nonempty_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def require_string(data: dict[str, Any], key: str) -> str:
    value = nonempty_string(data.get(key))
    if value is None:
        raise ScenarioBlocked(f"missing or invalid {key}")
    return value


def string_list(
    data: dict[str, Any], key: str, *, required: bool = False
) -> list[str]:
    if key not in data:
        if required:
            raise ScenarioBlocked(f"missing {key}")
        return []
    value = data[key]
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ScenarioBlocked(f"{key} must be an array of non-empty strings")
    if required and not value:
        raise ScenarioBlocked(f"{key} must not be empty")
    return value


def object_value(
    data: dict[str, Any], key: str, *, required: bool = False
) -> dict[str, Any]:
    if key not in data:
        if required:
            raise ScenarioBlocked(f"missing {key}")
        return {}
    value = data[key]
    if not isinstance(value, dict):
        raise ScenarioBlocked(f"{key} must be an object")
    return value


def boolean_value(data: dict[str, Any], key: str, default: bool) -> bool:
    if key not in data:
        return default
    if not isinstance(data[key], bool):
        raise ScenarioBlocked(f"{key} must be a boolean")
    return data[key]


def load_component_module(component: str):
    if component not in COMPONENTS:
        raise ScenarioBlocked(f"unknown component: {component}")
    path = ROOT / COMPONENTS[component]
    if not path.is_file():
        raise ScenarioBlocked(f"component import failure: {component}")
    module_name = f"acos_scenario_{component}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ScenarioBlocked(f"component import failure: {component}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise ScenarioBlocked(f"component import failure {component}: {exc}") from exc
    return module


def normalize_component_result(component: str, raw: Any) -> dict[str, Any]:
    result = getattr(raw, "result", None) or getattr(raw, "overall_result", None)
    allowed = getattr(raw, "allowed", None)
    reason = getattr(raw, "reason", None)
    warnings = getattr(raw, "warnings", [])
    source = getattr(raw, "source", None)

    if result not in RESULTS:
        raise ScenarioBlocked(f"component output has unknown result: {component}")
    if not isinstance(allowed, bool) or allowed != (result == PASS):
        raise ScenarioBlocked(f"component result/allowed contradiction: {component}")
    if not isinstance(reason, str) or not reason:
        raise ScenarioBlocked(f"component output missing reason: {component}")
    if not isinstance(warnings, list):
        raise ScenarioBlocked(f"component warnings have wrong type: {component}")

    normalized = {
        "component": component,
        "invoked": True,
        "input_valid": True,
        "result": result,
        "allowed": allowed,
        "reason": reason,
        "lifecycle_state": getattr(raw, "lifecycle_state", None),
        "warnings": warnings,
        "source": source,
        "contract_version": "1.0",
    }
    required_fields = {
        "component",
        "invoked",
        "input_valid",
        "result",
        "allowed",
        "reason",
        "lifecycle_state",
        "warnings",
        "source",
        "contract_version",
    }
    if set(normalized) != required_fields:
        raise ScenarioBlocked(f"component contract incomplete: {component}")
    return normalized


def invoke_component(component: str, input_data: Any) -> dict[str, Any]:
    if not isinstance(input_data, dict):
        raise ScenarioBlocked(f"component adapter input invalid: {component}")
    if input_data.get("simulate_import_failure") is True:
        raise ScenarioBlocked(f"component import failure: {component}")
    if input_data.get("simulate_adapter_failure") is True:
        raise ScenarioBlocked(f"component adapter failure: {component}")
    if input_data.get("simulate_output"):
        raw = type("SyntheticResult", (), input_data["simulate_output"])()
        normalized = normalize_component_result(component, raw)
        if "contract_version_override" in input_data:
            normalized["contract_version"] = input_data["contract_version_override"]
        return normalized

    module = load_component_module(component)
    try:
        if "fixture_path" in input_data:
            fixture_path = input_data["fixture_path"]
            if not isinstance(fixture_path, str):
                raise ScenarioBlocked(f"fixture_path must be a string: {component}")
            candidate = (ROOT / fixture_path).resolve()
            allowed_directory = (ROOT / COMPONENT_FIXTURE_DIRECTORIES[component]).resolve()
            try:
                candidate.relative_to(allowed_directory)
            except ValueError as exc:
                raise ScenarioBlocked(
                    f"component fixture path escapes its static fixture directory: {component}"
                ) from exc
            if not candidate.is_file():
                raise ScenarioBlocked(f"component fixture does not exist: {component}")
            raw = module.load_fixture(candidate)
        else:
            raw = module.evaluate_fixture(input_data, source=f"scenario:{component}")
    except ScenarioBlocked:
        raise
    except Exception as exc:
        raise ScenarioBlocked(f"component adapter failure {component}: {exc}") from exc
    normalized = normalize_component_result(component, raw)
    if "contract_version_override" in input_data:
        normalized["contract_version"] = input_data["contract_version_override"]
    return normalized


def validate_dependency_graph(
    data: dict[str, Any], order: list[str]
) -> tuple[list[str], list[str]]:
    graph = object_value(data, "dependency_graph")
    if not graph:
        return [], []
    for component, dependencies in graph.items():
        if component not in COMPONENTS:
            raise ScenarioBlocked(f"dependency graph contains unknown component: {component}")
        if not isinstance(dependencies, list) or any(
            dependency not in COMPONENTS for dependency in dependencies
        ):
            raise ScenarioBlocked("dependency_graph must map components to component arrays")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(component: str) -> None:
        if component in visiting:
            raise ScenarioBlocked("dependency graph cycle")
        if component in visited:
            return
        visiting.add(component)
        for dependency in graph.get(component, []):
            visit(dependency)
        visiting.remove(component)
        visited.add(component)

    for component in graph:
        visit(component)

    positions = {component: index for index, component in enumerate(order)}
    invalid = [
        f"{dependency}->{component}"
        for component, dependencies in graph.items()
        for dependency in dependencies
        if component in positions
        and dependency in positions
        and positions[dependency] > positions[component]
    ]
    return [], invalid


def validate_lifecycle(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    lifecycle_steps = string_list(data, "lifecycle_steps")
    completed_steps = string_list(data, "completed_steps")
    if not lifecycle_steps and not completed_steps:
        return [], []
    missing = [step for step in lifecycle_steps if step not in completed_steps]
    positions = {step: index for index, step in enumerate(lifecycle_steps)}
    ordered = [step for step in completed_steps if step in positions]
    invalid = [
        step
        for index, step in enumerate(ordered[1:], start=1)
        if positions[ordered[index - 1]] > positions[step]
    ]
    return missing, invalid


def validate_policy_metadata(
    data: dict[str, Any], required_components: list[str]
) -> tuple[bool, list[str], list[str]]:
    versions = object_value(data, "policy_versions", required=True)
    digests = object_value(data, "policy_digests", required=True)
    missing_versions = [component for component in required_components if component not in versions]
    missing_digests = [component for component in required_components if component not in digests]
    if missing_versions or missing_digests:
        missing = sorted(set(missing_versions + missing_digests))
        raise ScenarioBlocked(f"unable to determine governing policy: {', '.join(missing)}")
    version_mismatches = [
        component for component in required_components if versions[component] != "1.0"
    ]
    digest_mismatches = [
        component for component in required_components if digests[component] != "aligned"
    ]
    return bool(version_mismatches or digest_mismatches), version_mismatches, digest_mismatches


def result_flag(results: list[dict[str, Any]], component: str) -> bool | None:
    match = next((item for item in results if item["component"] == component), None)
    return None if match is None else match["result"] == PASS


def evaluate(data: Any, source: str = "<memory>") -> ScenarioResult:
    scenario_id = Path(source).stem
    mode = scenario_type = project = task_id = expected_result = None
    required_components: list[str] | None = None
    component_order: list[str] | None = None
    executed: list[str] = []
    skipped: list[str] = []
    component_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    denied: list[str] = []
    blocked: list[str] = []
    conflicts: list[str] = []
    version_mismatches: list[str] = []
    digest_mismatches: list[str] = []
    policy_drift_detected: bool | None = None
    lifecycle_state = "PIPELINE_BLOCKED"
    missing_steps: list[str] = []
    invalid_order_steps: list[str] = []
    result = BLOCKED
    reason = "Scenario input is not an object."

    try:
        if not isinstance(data, dict):
            raise ScenarioBlocked("scenario fixture root must be an object")
        scenario_id = require_string(data, "scenario_id")
        mode = require_string(data, "mode")
        scenario_type = require_string(data, "scenario_type")
        project = require_string(data, "project")
        task_id = require_string(data, "task_id")
        expected_result = require_string(data, "expected_result")
        for key in (
            "title",
            "description",
            "producer",
            "runtime_identity",
            "source",
            "expected_lifecycle_state",
        ):
            require_string(data, key)
        if mode not in MODES:
            raise ScenarioBlocked(f"unknown mode: {mode}")
        if scenario_type not in SCENARIO_TYPES:
            raise ScenarioBlocked(f"unknown scenario_type: {scenario_type}")
        if expected_result not in RESULTS:
            raise ScenarioBlocked(f"unknown expected result: {expected_result}")

        required_components = string_list(data, "required_components", required=True)
        optional_components = string_list(data, "optional_components")
        component_order = string_list(data, "component_order", required=True)
        if any(
            component not in COMPONENTS
            for component in required_components + optional_components + component_order
        ):
            raise ScenarioBlocked("unknown component")
        if len(component_order) != len(set(component_order)):
            raise ScenarioBlocked("duplicate component without explicit allowance")
        if not set(required_components).issubset(component_order):
            raise ScenarioBlocked("missing required component")
        if not component_order:
            raise ScenarioBlocked("no component executed")
        positions = {
            component: index for index, component in enumerate(component_order)
        }
        governance_edges = (
            ("runtime_identity", "user_decision_gate"),
            ("runtime_identity", "filesystem_permission"),
            ("runtime_identity", "advisory_gate"),
            ("runtime_identity", "git_operation"),
            ("user_decision_gate", "filesystem_permission"),
            ("user_decision_gate", "git_operation"),
            ("advisory_gate", "git_operation"),
            ("git_operation", "audit_jsonl"),
        )
        reversed_edges = [
            f"{before}->{after}"
            for before, after in governance_edges
            if before in positions
            and after in positions
            and positions[before] > positions[after]
        ]
        if reversed_edges:
            invalid_order_steps.extend(reversed_edges)
            raise ScenarioDenied("critical governance component order reversed")

        component_inputs = object_value(data, "component_inputs", required=True)
        expected_component_results = object_value(
            data, "expected_component_results", required=True
        )
        expected_overall_result = require_string(data, "expected_overall_result")
        if expected_overall_result not in RESULTS:
            raise ScenarioBlocked("unknown expected_overall_result")
        if any(value not in RESULTS for value in expected_component_results.values()):
            raise ScenarioBlocked("expected_component_results contains unknown result")

        stop_on_deny = boolean_value(data, "stop_on_deny", False)
        stop_on_blocked = boolean_value(data, "stop_on_blocked", True)
        allow_optional_failure = boolean_value(data, "allow_optional_failure", False)
        for optional_array in (
            "preconditions",
            "assertions",
            "expected_reason_contains",
            "expected_warnings",
            "scenario_tags",
        ):
            string_list(data, optional_array)
        if data.get("contradictory_stop_settings") is True:
            raise ScenarioBlocked("contradictory stop_on_deny / stop_on_blocked settings")
        if data.get("non_deterministic") is True:
            raise ScenarioBlocked("non-deterministic fixture marker")
        if data.get("claims_live_state") is True:
            raise ScenarioBlocked("scenario claims real external state without static evidence")

        _, dependency_order_errors = validate_dependency_graph(data, component_order)
        if dependency_order_errors:
            invalid_order_steps.extend(dependency_order_errors)
            raise ScenarioDenied("dependency order violates declared governance flow")

        missing_steps, lifecycle_order_errors = validate_lifecycle(data)
        if lifecycle_order_errors:
            invalid_order_steps.extend(lifecycle_order_errors)
            raise ScenarioDenied("illegal lifecycle order")

        if mode == "detect_policy_drift":
            (
                policy_drift_detected,
                version_mismatches,
                digest_mismatches,
            ) = validate_policy_metadata(data, required_components)
            if policy_drift_detected:
                lifecycle_state = "POLICY_DRIFT_DETECTED"
                raise ScenarioDenied("policy version or mapping digest mismatch")
        else:
            policy_drift_detected = False

        skipped_by_fixture = string_list(data, "skip_optional_components")
        known_facts = object_value(data, "known_fact_expected_results")
        for component in component_order:
            if component in skipped_by_fixture:
                if component in required_components:
                    raise ScenarioBlocked(f"required component skipped: {component}")
                skipped.append(component)
                warnings.append(f"optional component skipped: {component}")
                continue
            if component not in component_inputs:
                if component in required_components:
                    raise ScenarioBlocked(f"required input absent: {component}")
                skipped.append(component)
                warnings.append(f"optional component skipped: {component}")
                continue

            normalized = invoke_component(component, component_inputs[component])
            if normalized.get("contract_version") is None:
                raise ScenarioBlocked(f"missing contract version: {component}")
            if normalized.get("contract_version") != "1.0":
                raise ScenarioBlocked(f"unsupported contract version: {component}")
            executed.append(component)
            component_results.append(normalized)
            actual = normalized["result"]
            expected = expected_component_results.get(component)
            if expected is not None and expected != actual:
                conflicts.append(component)
            known = known_facts.get(component)
            if known is not None and known != actual:
                conflicts.append(component)
                raise ScenarioDenied(
                    f"component result conflicts with known governing fact: {component}"
                )

            is_optional = component in optional_components and component not in required_components
            if actual == DENY:
                if is_optional and allow_optional_failure:
                    warnings.append(f"optional component denied: {component}")
                else:
                    denied.append(component)
            elif actual == BLOCKED:
                if is_optional and allow_optional_failure:
                    warnings.append(f"optional component blocked: {component}")
                else:
                    blocked.append(component)

            if actual == BLOCKED and stop_on_blocked:
                break
            if actual == DENY and stop_on_deny:
                break

        skipped.extend(
            component
            for component in component_order
            if component not in executed and component not in skipped
        )
        if not executed:
            raise ScenarioBlocked("no component executed")
        if conflicts:
            raise ScenarioBlocked("component result conflicts with fixture expectation")

        actual_overall = BLOCKED if blocked else DENY if denied else PASS
        if actual_overall != expected_overall_result:
            raise ScenarioBlocked("aggregate conflicts with expected_overall_result")

        result = actual_overall
        lifecycle_state = {
            PASS: "PIPELINE_PASS",
            DENY: "PIPELINE_DENIED",
            BLOCKED: "PIPELINE_BLOCKED",
        }[result]
        if missing_steps and result == PASS:
            lifecycle_state = "FINAL_CHATGPT_DECISION_REQUIRED"
        reason = "Scenario evaluated deterministically."
    except ScenarioDenied as exc:
        result = DENY
        lifecycle_state = (
            lifecycle_state
            if lifecycle_state == "POLICY_DRIFT_DETECTED"
            else "PIPELINE_DENIED"
        )
        reason = str(exc)
    except ScenarioBlocked as exc:
        result = BLOCKED
        lifecycle_state = "PIPELINE_BLOCKED"
        reason = str(exc)
    except Exception as exc:  # Defensive fail-closed boundary.
        result = BLOCKED
        lifecycle_state = "PIPELINE_BLOCKED"
        reason = f"unexpected evaluation failure: {exc}"

    if expected_result is None and isinstance(data, dict):
        expected_result = nonempty_string(data.get("expected_result"))
    expectation_met = result == expected_result if expected_result in RESULTS else False
    failed = list(dict.fromkeys(denied + blocked + conflicts))

    return ScenarioResult(
        scenario_id=scenario_id,
        mode=mode,
        scenario_type=scenario_type,
        project=project,
        task_id=task_id,
        required_components=required_components,
        executed_components=executed,
        skipped_components=skipped,
        component_order=component_order,
        component_results=component_results,
        component_contracts_valid=bool(component_results) and not conflicts and not blocked,
        identity_valid=result_flag(component_results, "runtime_identity"),
        scope_valid=result_flag(component_results, "filesystem_permission"),
        user_decision_valid=result_flag(component_results, "user_decision_gate"),
        advisory_valid=result_flag(component_results, "advisory_gate"),
        git_authorization_valid=result_flag(component_results, "git_operation"),
        audit_chain_valid=result_flag(component_results, "audit_jsonl"),
        policy_drift_detected=policy_drift_detected,
        lifecycle_state=lifecycle_state,
        allowed=result == PASS,
        overall_result=result,
        reason=f"{reason} {NOTICE}",
        warnings=warnings,
        failed_components=failed,
        denied_components=denied,
        blocked_components=blocked,
        source=source,
        expected_result=expected_result,
        expectation_met=expectation_met,
        policy_versions=(
            data.get("policy_versions")
            if isinstance(data, dict) and isinstance(data.get("policy_versions"), dict)
            else None
        ),
        policy_digests=(
            data.get("policy_digests")
            if isinstance(data, dict) and isinstance(data.get("policy_digests"), dict)
            else None
        ),
        version_mismatches=version_mismatches,
        digest_mismatches=digest_mismatches,
        result_conflicts=conflicts,
        lifecycle_steps=(
            data.get("lifecycle_steps")
            if isinstance(data, dict) and isinstance(data.get("lifecycle_steps"), list)
            else None
        ),
        completed_steps=(
            data.get("completed_steps")
            if isinstance(data, dict) and isinstance(data.get("completed_steps"), list)
            else None
        ),
        missing_steps=missing_steps,
        invalid_order_steps=invalid_order_steps,
        next_required_authority=(
            nonempty_string(data.get("next_required_authority"))
            if isinstance(data, dict)
            else None
        ),
    )


BASE: dict[str, Any] = {
    "scenario_id": "SCN-057",
    "mode": "run_pipeline",
    "title": "Valid shadow flow",
    "description": "All six fixture-only components pass.",
    "project": str(ROOT),
    "task_id": "TASK_057",
    "scenario_type": "valid_end_to_end_shadow_flow",
    "producer": "ChatGPT Review",
    "runtime_identity": "ChatGPT Review Runtime",
    "required_components": list(COMPONENTS),
    "optional_components": [],
    "component_order": DEFAULT_ORDER,
    "component_inputs": {
        "runtime_identity": {
            "fixture_path": "fixtures/runtime-identity/valid-chatgpt-task.json"
        },
        "user_decision_gate": {
            "fixture_path": "fixtures/user-decision-gate/valid-task-start-decision.json"
        },
        "filesystem_permission": {
            "fixture_path": "fixtures/filesystem-permission/valid-codex-create-script.json"
        },
        "advisory_gate": {
            "fixture_path": "fixtures/advisory-gate/valid-accepted-review.json"
        },
        "git_operation": {
            "fixture_path": "fixtures/git-operation/valid-codex-commit-authorized.json"
        },
        "audit_jsonl": {
            "fixture_path": "fixtures/audit-jsonl/valid-lifecycle-chain.json"
        },
    },
    "expected_component_results": {component: PASS for component in COMPONENTS},
    "expected_overall_result": PASS,
    "expected_lifecycle_state": "PIPELINE_PASS",
    "source": "static fixture",
    "expected_result": PASS,
}

TEMPLATES = {
    "valid": BASE,
    "drift": {
        **BASE,
        "mode": "detect_policy_drift",
        "policy_versions": {component: "1.0" for component in COMPONENTS},
        "policy_digests": {component: "aligned" for component in COMPONENTS},
    },
}


def merge_template(data: dict[str, Any]) -> dict[str, Any]:
    template_name = data.get("template")
    if template_name not in TEMPLATES:
        raise ScenarioBlocked(f"unknown template: {template_name}")
    merged = copy.deepcopy(TEMPLATES[template_name])
    merge_keys = {
        "component_inputs",
        "expected_component_results",
        "policy_versions",
        "policy_digests",
    }
    for key, value in data.items():
        if key in {
            "template",
            "omit_fields",
            "remove_component_inputs",
            "remove_policy_versions",
            "remove_policy_digests",
        }:
            continue
        if key in merge_keys and isinstance(value, dict):
            merged.setdefault(key, {}).update(value)
        else:
            merged[key] = value
    for key in data.get("remove_component_inputs", []):
        merged.get("component_inputs", {}).pop(key, None)
    for key in data.get("remove_policy_versions", []):
        merged.get("policy_versions", {}).pop(key, None)
    for key in data.get("remove_policy_digests", []):
        merged.get("policy_digests", {}).pop(key, None)
    for key in data.get("omit_fields", []):
        merged.pop(key, None)
    return merged


def load_fixture(path: Path) -> ScenarioResult:
    inferred = (
        PASS
        if path.name.startswith("valid-")
        else DENY
        if path.name.startswith("invalid-")
        else BLOCKED
        if path.name.startswith("blocked-")
        else None
    )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return evaluate(
            {"scenario_id": path.stem, "expected_result": inferred}, str(path)
        )
    if not isinstance(data, dict):
        result = evaluate(data, str(path))
        result.expected_result = inferred
        result.expectation_met = result.overall_result == inferred
        return result
    explicit_expected = "expected_result" in data
    try:
        if "template" in data:
            data = merge_template(data)
    except ScenarioBlocked as exc:
        return evaluate(
            {
                "scenario_id": path.stem,
                "expected_result": inferred,
                "mode": "invalid-template",
                "scenario_type": "invalid-template",
                "project": str(ROOT),
                "task_id": "TASK_057",
                "title": "Invalid template",
                "description": str(exc),
                "producer": "fixture",
                "runtime_identity": "fixture",
                "source": "static fixture",
                "expected_lifecycle_state": "PIPELINE_BLOCKED",
            },
            str(path),
        )
    if inferred and not explicit_expected:
        data["expected_result"] = inferred
    result = evaluate(data, str(path))
    if inferred and result.expected_result not in RESULTS:
        result.expected_result = inferred
        result.expectation_met = result.overall_result == inferred
    return result


# Stable import name used by the earlier shadow components and unit tests.
load = load_fixture


def collect_paths(raw_paths: list[str]) -> tuple[list[Path], list[str]]:
    paths: list[Path] = []
    errors: list[str] = []
    allowed_directory = SCENARIO_FIXTURE_DIRECTORY.resolve()
    for raw in raw_paths:
        path = Path(raw)
        try:
            path.resolve().relative_to(allowed_directory)
        except ValueError:
            errors.append(f"input path is outside the static scenario directory: {raw}")
            continue
        if path.is_file():
            paths.append(path)
        elif path.is_dir():
            paths.extend(sorted(path.rglob("*.json")))
        else:
            errors.append(f"input path does not exist: {raw}")
    if not paths and not errors:
        errors.append("no scenario fixtures found")
    return sorted(set(paths)), errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run fixture-only ACOS validation scenarios."
    )
    parser.add_argument("fixtures", nargs="+")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    paths, errors = collect_paths(args.fixtures)
    if errors:
        for error in errors:
            print(f"BLOCKED: {error}", file=sys.stderr)
        return 2

    results = [load_fixture(path) for path in paths]
    counts = {status: sum(item.overall_result == status for item in results) for status in RESULTS}
    mismatches = sum(not item.expectation_met for item in results)
    if args.format == "json":
        print(json.dumps([asdict(item) for item in results], indent=2, sort_keys=True))
    else:
        lines = [
            f"{item.overall_result}: {item.scenario_id} - {item.reason}" for item in results
        ]
        lines.append(
            "SUMMARY: "
            f"total={len(results)} pass={counts[PASS]} deny={counts[DENY]} "
            f"blocked={counts[BLOCKED]} expectation_mismatches={mismatches}"
        )
        print("\n".join(lines))
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())

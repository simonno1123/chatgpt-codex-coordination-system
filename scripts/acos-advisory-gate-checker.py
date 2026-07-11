#!/usr/bin/env python3
"""Fixture-only ACOS External Advisory Gate checker.

This checker evaluates declared JSON facts. It never contacts a provider,
sends or consumes a real advisory artifact, changes Git, or grants authority.
"""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

PASS = "PASS"
DENY = "DENY"
BLOCKED = "BLOCKED"
RESULT_VALUES = frozenset({PASS, DENY, BLOCKED})

NOT_REQUIRED = "advisory_not_required"
OPTIONAL = "advisory_optional"
MANDATORY = "advisory_mandatory"
TRIGGER_LEVELS = frozenset({NOT_REQUIRED, OPTIONAL, MANDATORY})

TRIGGER_CATEGORIES = {
    "routine_operation": NOT_REQUIRED,
    "fixture_only_validation": NOT_REQUIRED,
    "documentation_wording": OPTIONAL,
    "non_governance_readme": OPTIONAL,
    "instance_onboarding_example": OPTIONAL,
    "explanatory_reorganization": OPTIONAL,
    "governance_architecture": MANDATORY,
    "runtime_isolation": MANDATORY,
    "runtime_role_permissions": MANDATORY,
    "filesystem_permission_policy": MANDATORY,
    "git_operation_policy": MANDATORY,
    "audit_schema": MANDATORY,
    "advisory_gate_logic": MANDATORY,
    "user_decision_gate": MANDATORY,
    "enforcement_architecture": MANDATORY,
    "blocking_enforcement_transition": MANDATORY,
    "live_repository_connection": MANDATORY,
    "instance_project_connection": MANDATORY,
    "release_authorization_model": MANDATORY,
    "identity_authorization_credentials": MANDATORY,
    "core_instance_boundary_dispute": MANDATORY,
    "safety_governance_weakening": MANDATORY,
}

MODES = frozenset(
    {"classify_trigger", "validate_request", "validate_review", "consume_review", "verify_lifecycle"}
)
CONCLUSIONS = frozenset({"ACCEPTED", "REWORK", "BLOCKED"})
RUNTIME_PRODUCERS = {
    "ChatGPT Review Runtime": frozenset({"ChatGPT", "ChatGPT Review"}),
    "Codex Executor Runtime": frozenset({"Codex Executor"}),
    "External Advisory Runtime": frozenset({"External Advisory Reviewer"}),
    "Automation Runtime": frozenset({"Automation"}),
}
READ_ONLY_COMMANDS = frozenset(
    {
        "view_file",
        "read_file",
        "list_dir",
        "unit_test",
        "fixture_cli_validation",
        "compilation_validation",
        "git status",
        "git diff",
        "git log",
    }
)
READ_ONLY_GIT_ACTIONS = frozenset({"none", "git status", "git diff", "git log"})
REQUIRED_LIFECYCLE = (
    "preliminary_review",
    "advisory_request",
    "advisory_review",
    "chatgpt_final_decision",
)
DRY_RUN_NOTICE = (
    "Fixture-only advisory gate evaluation; no real request, advisory review, "
    "decision, authorization, Git operation, or next task was created."
)

BASE_COMMON = {
    "task_id": "TASK_055",
    "change_category": "advisory_gate_logic",
    "declared_trigger_level": MANDATORY,
    "project": "/Users/zhang/Documents/chatgpt-codex-coordination-system",
}
BASE_REQUEST = {
    **BASE_COMMON,
    "mode": "validate_request",
    "producer": "ChatGPT Review",
    "runtime_identity": "ChatGPT Review Runtime",
    "artifact_type": "ADVISORY REQUEST",
    "to": "External Advisory Reviewer",
    "next_receiver": "External Advisory Reviewer",
    "request_id": "REQ-TASK-055-001",
    "request_status": "open",
    "request_mode": "ADVISORY / READONLY",
    "target_files": ["scripts/acos-advisory-gate-checker.py"],
    "reference_files": ["docs/acos-v2-external-advisory-trigger-policy.md"],
    "review_questions": ["Does the target preserve advisory authority boundaries?"],
    "authority_limits": ["Non-executing second opinion only; no authorization or decision"],
    "forbidden_actions": ["No file modification, Git write, authorization, or decision"],
    "preliminary_review_status": "ACCEPTED",
    "mandatory_reason": "Advisory gate logic is a Level 2 governance change.",
}
BASE_REVIEW = {
    **BASE_COMMON,
    "mode": "validate_review",
    "producer": "External Advisory Reviewer",
    "runtime_identity": "External Advisory Runtime",
    "artifact_type": "ADVISORY REVIEW",
    "to": "ChatGPT Review",
    "next_receiver": "ChatGPT Review",
    "request_id": "REQ-TASK-055-001",
    "review_id": "ADV-TASK-055-001",
    "request_id_ref": "REQ-TASK-055-001",
    "review_mode": "ADVISORY / READONLY",
    "reviewer_identity": "External Advisory Reviewer",
    "conclusion": "ACCEPTED",
    "target_files": ["scripts/acos-advisory-gate-checker.py"],
    "reference_files": ["docs/acos-v2-external-advisory-trigger-policy.md"],
    "reviewed_targets": ["scripts/acos-advisory-gate-checker.py"],
    "reviewed_references": ["docs/acos-v2-external-advisory-trigger-policy.md"],
    "review_project": "/Users/zhang/Documents/chatgpt-codex-coordination-system",
    "review_task_id": "TASK_055",
    "findings": ["The fixture-only checker preserves the non-executing boundary."],
    "claimed_commands": [],
    "claimed_mutations": ["none"],
    "claimed_git_actions": ["none"],
    "recommendation": "ChatGPT Review may consider the findings.",
    "compliance_declaration": "Read-only review; no writes, Git changes, or authorization.",
}
BASE_CONSUMPTION = {
    **BASE_REVIEW,
    "mode": "consume_review",
    "consumer_runtime": "ChatGPT Review Runtime",
    "consumer_identity": "ChatGPT Review",
    "request_validated": True,
    "review_validated": True,
    "review_consumed": True,
    "final_decision_present": True,
    "final_decision_producer": "ChatGPT Review",
    "final_decision_status": "ACCEPTED",
    "commit_authorization_present": False,
    "push_authorization_present": False,
    "release_authorization_present": False,
    "user_decision_present": False,
    "next_task_started": False,
}
FIXTURE_TEMPLATES = {
    "classify_mandatory": {
        **BASE_COMMON,
        "mode": "classify_trigger",
        "producer": "ChatGPT Review",
        "runtime_identity": "ChatGPT Review Runtime",
        "artifact_type": "TRIGGER ASSESSMENT",
        "to": "ChatGPT Review",
        "next_receiver": "ChatGPT Review",
        "advisory_required": True,
    },
    "classify_optional": {
        **BASE_COMMON,
        "mode": "classify_trigger",
        "change_category": "documentation_wording",
        "declared_trigger_level": OPTIONAL,
        "producer": "ChatGPT Review",
        "runtime_identity": "ChatGPT Review Runtime",
        "artifact_type": "TRIGGER ASSESSMENT",
        "to": "ChatGPT Review",
        "next_receiver": "ChatGPT Review",
        "advisory_required": False,
    },
    "classify_not_required": {
        **BASE_COMMON,
        "mode": "classify_trigger",
        "change_category": "routine_operation",
        "declared_trigger_level": NOT_REQUIRED,
        "producer": "ChatGPT Review",
        "runtime_identity": "ChatGPT Review Runtime",
        "artifact_type": "TRIGGER ASSESSMENT",
        "to": "ChatGPT Review",
        "next_receiver": "ChatGPT Review",
        "advisory_required": False,
    },
    "valid_request": BASE_REQUEST,
    "valid_review": BASE_REVIEW,
    "valid_consumption": BASE_CONSUMPTION,
    "valid_lifecycle": {
        **BASE_COMMON,
        "mode": "verify_lifecycle",
        "producer": "ChatGPT Review",
        "runtime_identity": "ChatGPT Review Runtime",
        "artifact_type": "LIFECYCLE RECORD",
        "to": "ChatGPT Review",
        "next_receiver": "ChatGPT Review",
        "lifecycle_events": list(REQUIRED_LIFECYCLE),
    },
}


@dataclass
class GateResult:
    case_id: str
    mode: str | None
    task_id: str | None
    change_category: str | None
    declared_trigger_level: str | None
    calculated_trigger_level: str | None
    advisory_required: bool | None
    producer: str | None
    runtime_identity: str | None
    artifact_type: str | None
    to: str | None
    next_receiver: str | None
    request_id: str | None
    review_id: str | None
    request_id_ref: str | None
    conclusion: str | None
    request_valid: bool | None
    review_valid: bool | None
    lifecycle_state: str | None
    consumed: bool | None
    allowed: bool
    result: str
    reason: str
    warnings: list[str]
    source: str
    expected_result: str | None
    expectation_met: bool | None
    target_files: list[str] | None = None
    reviewed_targets: list[str] | None = None
    missing_targets: list[str] | None = None
    reference_files: list[str] | None = None
    reviewed_references: list[str] | None = None
    missing_references: list[str] | None = None
    claimed_commands: list[str] | None = None
    claimed_mutations: list[str] | None = None
    claimed_git_actions: list[str] | None = None
    role_violations: list[str] | None = None
    authority_violations: list[str] | None = None


class GateBlocked(ValueError):
    pass


class GateDenied(ValueError):
    pass


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _required_text(data: Mapping[str, Any], name: str) -> str:
    value = _text(data.get(name))
    if value is None:
        raise GateBlocked(f"missing or invalid {name}")
    return value


def _bool(data: Mapping[str, Any], name: str, *, required: bool = False) -> bool:
    if name not in data:
        if required:
            raise GateBlocked(f"missing required boolean field: {name}")
        return False
    value = data[name]
    if not isinstance(value, bool):
        raise GateBlocked(f"{name} must be a boolean")
    return value


def _strings(
    data: Mapping[str, Any], name: str, *, required: bool = False, nonempty: bool = False
) -> list[str]:
    if name not in data:
        if required:
            raise GateBlocked(f"missing required array: {name}")
        return []
    value = data[name]
    if not isinstance(value, list):
        raise GateBlocked(f"{name} must be an array")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise GateBlocked(f"{name} entries must be non-empty strings")
    cleaned = [item.strip() for item in value]
    if nonempty and not cleaned:
        raise GateBlocked(f"{name} must not be empty")
    return cleaned


def _infer_expected(path: Path) -> str | None:
    if path.name.startswith("valid-"):
        return PASS
    if path.name.startswith("invalid-"):
        return DENY
    if path.name.startswith("blocked-"):
        return BLOCKED
    return None


def _role_binding(runtime: str, producer: str) -> None:
    if runtime not in RUNTIME_PRODUCERS:
        raise GateBlocked(f"unknown runtime_identity: {runtime}")
    if producer not in RUNTIME_PRODUCERS[runtime]:
        raise GateDenied("producer does not match runtime_identity")


def _expectation(
    result: str,
    reason: str,
    expected_result: str | None,
    expected_allowed: bool | None,
    expected_reason: str | None,
) -> bool:
    checks = [result == expected_result] if expected_result else [result == PASS]
    if expected_allowed is not None:
        checks.append((result == PASS) == expected_allowed)
    if expected_reason:
        checks.append(expected_reason in reason)
    return all(checks)


def _result(
    data: Mapping[str, Any],
    *,
    source: str,
    result: str,
    reason: str,
    calculated: str | None,
    request_valid: bool | None = None,
    review_valid: bool | None = None,
    lifecycle_state: str | None = None,
    consumed: bool | None = None,
    warnings: list[str] | None = None,
    missing_targets: list[str] | None = None,
    missing_references: list[str] | None = None,
    role_violations: list[str] | None = None,
    authority_violations: list[str] | None = None,
) -> GateResult:
    expected = _text(data.get("expected_result"))
    expected = expected.upper() if expected else None
    expected_allowed = data.get("expected_allowed")
    if expected_allowed is not None and not isinstance(expected_allowed, bool):
        expected_allowed = None
    expected_reason = _text(data.get("expected_reason_contains"))
    return GateResult(
        case_id=_text(data.get("case_id")) or Path(source).stem,
        mode=_text(data.get("mode")),
        task_id=_text(data.get("task_id")),
        change_category=_text(data.get("change_category")),
        declared_trigger_level=_text(data.get("declared_trigger_level")),
        calculated_trigger_level=calculated,
        advisory_required=calculated == MANDATORY if calculated else None,
        producer=_text(data.get("producer")),
        runtime_identity=_text(data.get("runtime_identity")),
        artifact_type=_text(data.get("artifact_type")),
        to=_text(data.get("to")),
        next_receiver=_text(data.get("next_receiver")),
        request_id=_text(data.get("request_id")),
        review_id=_text(data.get("review_id")),
        request_id_ref=_text(data.get("request_id_ref")),
        conclusion=_text(data.get("conclusion")),
        request_valid=request_valid,
        review_valid=review_valid,
        lifecycle_state=lifecycle_state,
        consumed=consumed,
        allowed=result == PASS,
        result=result,
        reason=f"{reason} {DRY_RUN_NOTICE}",
        warnings=warnings or [],
        source=source,
        expected_result=expected,
        expectation_met=_expectation(
            result, reason, expected, expected_allowed, expected_reason
        ),
        target_files=data.get("target_files") if isinstance(data.get("target_files"), list) else None,
        reviewed_targets=data.get("reviewed_targets") if isinstance(data.get("reviewed_targets"), list) else None,
        missing_targets=missing_targets,
        reference_files=data.get("reference_files") if isinstance(data.get("reference_files"), list) else None,
        reviewed_references=data.get("reviewed_references") if isinstance(data.get("reviewed_references"), list) else None,
        missing_references=missing_references,
        claimed_commands=data.get("claimed_commands") if isinstance(data.get("claimed_commands"), list) else None,
        claimed_mutations=data.get("claimed_mutations") if isinstance(data.get("claimed_mutations"), list) else None,
        claimed_git_actions=data.get("claimed_git_actions") if isinstance(data.get("claimed_git_actions"), list) else None,
        role_violations=role_violations or [],
        authority_violations=authority_violations or [],
    )


def _classify(data: Mapping[str, Any]) -> str:
    category = _required_text(data, "change_category")
    if category not in TRIGGER_CATEGORIES:
        raise GateBlocked(f"unknown change_category: {category}")
    declared = _required_text(data, "declared_trigger_level")
    if declared not in TRIGGER_LEVELS:
        raise GateBlocked(f"unknown declared_trigger_level: {declared}")
    calculated = TRIGGER_CATEGORIES[category]
    if declared != calculated:
        raise GateBlocked(f"trigger level contradicts category: {declared} != {calculated}")
    if "advisory_required" in data:
        required = _bool(data, "advisory_required", required=True)
        if calculated == MANDATORY and not required:
            raise GateDenied("mandatory change attempts to skip advisory review")
        if calculated != MANDATORY and required and not _bool(data, "advisory_override"):
            raise GateBlocked("advisory_required contradicts trigger classification")
    return calculated


def _common(data: Mapping[str, Any]) -> tuple[str, str, str, str, str, str]:
    task_id = _required_text(data, "task_id")
    producer = _required_text(data, "producer")
    runtime = _required_text(data, "runtime_identity")
    artifact = _required_text(data, "artifact_type")
    receiver = _required_text(data, "to")
    next_receiver = _required_text(data, "next_receiver")
    _required_text(data, "project")
    _role_binding(runtime, producer)
    return task_id, producer, runtime, artifact, receiver, next_receiver


def _validate_request(data: Mapping[str, Any]) -> None:
    _, producer, runtime, artifact, receiver, next_receiver = _common(data)
    violations: list[str] = []
    if runtime != "ChatGPT Review Runtime" or producer not in {"ChatGPT", "ChatGPT Review"}:
        violations.append("ADVISORY REQUEST must be produced by ChatGPT Review Runtime")
    if artifact != "ADVISORY REQUEST":
        violations.append("artifact_type must be ADVISORY REQUEST")
    if receiver != "External Advisory Reviewer" or next_receiver != "External Advisory Reviewer":
        violations.append("request must route to External Advisory Reviewer")
    _required_text(data, "request_id")
    request_mode = _required_text(data, "request_mode").lower()
    if "read" not in request_mode or "advisory" not in request_mode:
        violations.append("request_mode must be read-only advisory review")
    _strings(data, "target_files", required=True, nonempty=True)
    _strings(data, "reference_files", required=True, nonempty=True)
    _strings(data, "review_questions", required=True, nonempty=True)
    authority = _strings(data, "authority_limits", required=True, nonempty=True)
    forbidden = _strings(data, "forbidden_actions", required=True, nonempty=True)
    preliminary = _required_text(data, "preliminary_review_status").upper()
    if preliminary not in {"ACCEPTED", "PRELIMINARY ACCEPTED", "COMPLETE"}:
        raise GateBlocked("unknown preliminary_review_status")
    if _classify(data) == MANDATORY and not _text(data.get("mandatory_reason")):
        raise GateBlocked("mandatory request requires mandatory_reason")
    limits = " ".join(authority + forbidden).lower()
    for token in ("non-execut", "modif", "git", "authoriz", "decision"):
        if token not in limits:
            raise GateBlocked("request authority limits or forbidden actions are incomplete")
    if _bool(data, "requests_modification"):
        violations.append("request asks advisory reviewer to modify files")
    if _bool(data, "requests_git_write"):
        violations.append("request asks advisory reviewer to perform Git writes")
    if _bool(data, "requests_user_decision"):
        violations.append("request asks advisory reviewer to make User Decision")
    if _bool(data, "commit_authorization_present") or _bool(data, "push_authorization_present"):
        violations.append("ADVISORY REQUEST contains Git authorization")
    if violations:
        raise GateDenied("; ".join(violations))


def _review_behavior(data: Mapping[str, Any]) -> list[str]:
    commands = _strings(data, "claimed_commands", required=True)
    mutations = _strings(data, "claimed_mutations", required=True)
    git_actions = _strings(data, "claimed_git_actions", required=True)
    violations: list[str] = []
    for command in commands:
        if command.lower() not in READ_ONLY_COMMANDS:
            violations.append(f"non-read-only command claimed: {command}")
    active_mutations = [item for item in mutations if item.lower() not in {"none", "no mutations"}]
    if active_mutations:
        violations.append("advisory review claims file mutations")
    for action in git_actions:
        if action.lower() not in READ_ONLY_GIT_ACTIONS:
            violations.append(f"forbidden Git action claimed: {action}")
    declaration = _required_text(data, "compliance_declaration").lower()
    no_command_claims = ("zero commands", "no commands executed", "无工具调用", "未执行任何命令")
    if commands and any(claim in declaration for claim in no_command_claims):
        violations.append("command declaration contradicts claimed_commands")
    if active_mutations and any(claim in declaration for claim in ("no writes", "no mutations", "read-only")):
        violations.append("mutation declaration contradicts claimed_mutations")
    if _bool(data, "used_apply_patch"):
        violations.append("External Advisory Reviewer used apply_patch")
    if _bool(data, "network_accessed") or _bool(data, "model_api_called"):
        violations.append("External Advisory Reviewer accessed network or model API")
    return violations


def _validate_review(data: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    _, producer, runtime, artifact, receiver, next_receiver = _common(data)
    violations: list[str] = []
    if runtime != "External Advisory Runtime" or producer != "External Advisory Reviewer":
        violations.append("ADVISORY REVIEW must be produced by External Advisory Runtime")
    if artifact != "ADVISORY REVIEW":
        violations.append("artifact_type must be ADVISORY REVIEW")
    if receiver != "ChatGPT Review" or next_receiver != "ChatGPT Review":
        violations.append("ADVISORY REVIEW must return to ChatGPT Review")
    _required_text(data, "review_id")
    request_id = _required_text(data, "request_id")
    if _required_text(data, "request_id_ref") != request_id:
        violations.append("review is bound to the wrong or stale request_id")
    if "read" not in _required_text(data, "review_mode").lower():
        violations.append("review_mode must be read-only")
    if _required_text(data, "reviewer_identity") != "External Advisory Reviewer":
        violations.append("reviewer_identity is invalid")
    conclusion = _required_text(data, "conclusion").upper()
    if conclusion not in CONCLUSIONS:
        raise GateBlocked(f"unknown conclusion: {conclusion}")
    _strings(data, "findings", required=True, nonempty=True)
    targets = _strings(data, "target_files", required=True, nonempty=True)
    references = _strings(data, "reference_files", required=True, nonempty=True)
    reviewed_targets = _strings(data, "reviewed_targets", required=True, nonempty=True)
    reviewed_references = _strings(data, "reviewed_references", required=True, nonempty=True)
    normalize = lambda items: {str(PurePosixPath(item)) for item in items}
    missing_targets = sorted(normalize(targets) - normalize(reviewed_targets))
    missing_references = sorted(normalize(references) - normalize(reviewed_references))
    metadata_exception = _bool(data, "metadata_path_error") and _bool(
        data, "actual_target_confirmed", required=True
    )
    if missing_targets and not metadata_exception:
        violations.append("review omitted requested target files")
    if missing_references and not metadata_exception:
        violations.append("review omitted requested reference files")
    project = _required_text(data, "project")
    if _required_text(data, "review_project") != project:
        violations.append("review targets the wrong project or repository")
    if _required_text(data, "review_task_id") != _required_text(data, "task_id"):
        violations.append("review targets the wrong task")
    violations.extend(_review_behavior(data))
    boolean_violations = {
        "produces_task": "External Advisory Reviewer produced TASK",
        "produces_decision": "External Advisory Reviewer produced DECISION",
        "forges_user_decision": "External Advisory Reviewer forged User Decision",
        "authorizes_commit": "External Advisory Reviewer authorized commit",
        "authorizes_push": "External Advisory Reviewer authorized push",
        "authorizes_release": "External Advisory Reviewer authorized release",
        "starts_next_task": "External Advisory Reviewer started next task",
        "audit_record_as_review": "audit record cannot substitute for ADVISORY REVIEW",
    }
    for field, message in boolean_violations.items():
        if _bool(data, field):
            violations.append(message)
    if violations:
        raise GateDenied("; ".join(violations))
    return missing_targets, missing_references


def _consume(data: Mapping[str, Any]) -> tuple[str, bool]:
    if _required_text(data, "consumer_runtime") != "ChatGPT Review Runtime" or _required_text(data, "consumer_identity") not in {"ChatGPT", "ChatGPT Review"}:
        raise GateDenied("ADVISORY REVIEW must be consumed by ChatGPT Review")
    if not _bool(data, "request_validated", required=True) or not _bool(
        data, "review_validated", required=True
    ):
        raise GateDenied("invalid request or review cannot be consumed")
    consumed = _bool(data, "review_consumed", required=True)
    if _bool(data, "stale"):
        raise GateDenied("stale advisory review cannot be consumed")
    if _bool(data, "superseded"):
        raise GateDenied("superseded advisory review cannot be consumed")
    duplicate = _bool(data, "duplicate")
    if duplicate and not _text(data.get("duplicate_state")):
        raise GateBlocked("duplicate review state is missing or ambiguous")
    if duplicate:
        if consumed or _bool(data, "commit_authorization_present"):
            raise GateDenied("duplicate advisory review cannot be consumed or authorize commit")
        return "DUPLICATE_CONSUMPTION_DENIED", False
    conclusion = _required_text(data, "conclusion").upper()
    if conclusion not in CONCLUSIONS:
        raise GateBlocked(f"unknown conclusion: {conclusion}")
    commit_auth = _bool(data, "commit_authorization_present", required=True)
    push_auth = _bool(data, "push_authorization_present", required=True)
    release_auth = _bool(data, "release_authorization_present")
    final_present = _bool(data, "final_decision_present", required=True)
    user_decision = _bool(data, "user_decision_present", required=True)
    if conclusion == "REWORK":
        if commit_auth or push_auth or final_present:
            raise GateDenied("REWORK advisory cannot be consumed as accepted")
        return "REWORK_REQUIRED", consumed
    if conclusion == "BLOCKED":
        if commit_auth or push_auth or final_present:
            raise GateDenied("BLOCKED advisory cannot be consumed as accepted")
        return "ADVISORY_BLOCKED", consumed
    if push_auth and not commit_auth:
        raise GateDenied("advisory acceptance cannot automatically authorize push")
    if release_auth and not push_auth:
        raise GateDenied("push state cannot automatically authorize release")
    if commit_auth and not final_present:
        raise GateDenied("advisory recommendation cannot substitute for commit authorization")
    if final_present:
        if _required_text(data, "final_decision_producer") not in {"ChatGPT", "ChatGPT Review"}:
            raise GateDenied("final decision must be produced by ChatGPT Review")
        if _required_text(data, "final_decision_status").upper() not in CONCLUSIONS:
            raise GateBlocked("unknown final_decision_status")
    if _bool(data, "next_task_started") and not user_decision:
        raise GateDenied("next task requires separate User Decision")
    return ("CONSUMED" if final_present else "FINAL_DECISION_REQUIRED"), consumed


def _lifecycle(data: Mapping[str, Any], calculated: str) -> str:
    events = _strings(data, "lifecycle_events", required=True, nonempty=True)
    if len(events) != len(set(events)):
        raise GateBlocked("lifecycle contains duplicate or contradictory states")
    if calculated == MANDATORY:
        if "advisory_request" not in events or "advisory_review" not in events:
            raise GateDenied("mandatory lifecycle skipped advisory request or review")
        missing = [event for event in REQUIRED_LIFECYCLE if event not in events]
        if missing:
            raise GateBlocked(f"mandatory lifecycle is incomplete: {', '.join(missing)}")
        indexes = [events.index(event) for event in REQUIRED_LIFECYCLE]
        if indexes != sorted(indexes):
            raise GateDenied("advisory lifecycle order is invalid")
    return "CONSUMED" if "chatgpt_final_decision" in events else "FINAL_DECISION_REQUIRED"


def evaluate_fixture(data: Mapping[str, Any], source: str = "<memory>") -> GateResult:
    calculated: str | None = None
    request_valid: bool | None = None
    review_valid: bool | None = None
    state: str | None = None
    consumed: bool | None = None
    warnings: list[str] = []
    missing_targets: list[str] | None = None
    missing_references: list[str] | None = None
    try:
        mode = _required_text(data, "mode")
        if mode not in MODES:
            raise GateBlocked(f"unknown mode: {mode}")
        expected = _text(data.get("expected_result"))
        if expected and expected.upper() not in RESULT_VALUES:
            raise GateBlocked(f"unknown expected_result: {expected}")
        calculated = _classify(data)
        _common(data)
        if mode == "classify_trigger":
            state = "ADVISORY_REQUIRED" if calculated == MANDATORY else calculated.upper()
        elif mode == "validate_request":
            _validate_request(data)
            request_valid = True
            state = "ADVISORY_REQUIRED" if calculated == MANDATORY else "REQUEST_VALID"
        elif mode == "validate_review":
            missing_targets, missing_references = _validate_review(data)
            review_valid = True
            state = "REVIEW_ACCEPTED_PENDING_DECISION"
        elif mode == "consume_review":
            missing_targets, missing_references = _validate_review(data)
            request_valid = True
            review_valid = True
            state, consumed = _consume(data)
        else:
            state = _lifecycle(data, calculated)
        if _bool(data, "metadata_path_error"):
            if not _bool(data, "actual_target_confirmed", required=True):
                raise GateDenied("path metadata error prevents reliable target binding")
            warnings.append("Non-substantive path metadata error; actual target is confirmed.")
        return _result(
            data,
            source=source,
            result=PASS,
            reason="Advisory gate fixture matches current policy.",
            calculated=calculated,
            request_valid=request_valid,
            review_valid=review_valid,
            lifecycle_state=state,
            consumed=consumed,
            warnings=warnings,
            missing_targets=missing_targets,
            missing_references=missing_references,
        )
    except GateDenied as exc:
        return _result(
            data,
            source=source,
            result=DENY,
            reason=str(exc),
            calculated=calculated,
            request_valid=False if request_valid is None else request_valid,
            review_valid=False if review_valid is None else review_valid,
            lifecycle_state="REVIEW_INVALID" if "review" in str(exc).lower() else "REQUEST_INVALID",
            consumed=False,
            warnings=warnings,
            missing_targets=missing_targets,
            missing_references=missing_references,
            authority_violations=[str(exc)],
        )
    except GateBlocked as exc:
        return _result(
            data,
            source=source,
            result=BLOCKED,
            reason=str(exc),
            calculated=calculated,
            request_valid=request_valid,
            review_valid=review_valid,
            lifecycle_state="REVIEW_PENDING",
            consumed=False,
            warnings=warnings,
            missing_targets=missing_targets,
            missing_references=missing_references,
        )


def load_fixture(path: Path) -> GateResult:
    inferred = _infer_expected(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result(
            {"case_id": path.stem, "expected_result": inferred},
            source=str(path),
            result=BLOCKED,
            reason=f"unable to read fixture: {exc}",
            calculated=None,
        )
    if not isinstance(data, dict):
        return _result(
            {"case_id": path.stem, "expected_result": inferred},
            source=str(path),
            result=BLOCKED,
            reason="fixture root must be a JSON object",
            calculated=None,
        )
    template_name = data.get("template")
    if template_name is not None:
        if not isinstance(template_name, str) or template_name not in FIXTURE_TEMPLATES:
            return _result(
                {"case_id": path.stem, "expected_result": inferred},
                source=str(path),
                result=BLOCKED,
                reason=f"unknown fixture template: {template_name!r}",
                calculated=None,
            )
        expanded = copy.deepcopy(FIXTURE_TEMPLATES[template_name])
        expanded.update({key: value for key, value in data.items() if key not in {"template", "omit_fields"}})
        omitted = data.get("omit_fields", [])
        if not isinstance(omitted, list) or any(not isinstance(item, str) for item in omitted):
            return _result(
                {"case_id": path.stem, "expected_result": inferred},
                source=str(path),
                result=BLOCKED,
                reason="omit_fields must be an array of strings",
                calculated=None,
            )
        for field in omitted:
            expanded.pop(field, None)
        data = expanded
    if "expected_result" not in data and inferred:
        data = dict(data)
        data["expected_result"] = inferred
    return evaluate_fixture(data, source=str(path))


def discover_paths(targets: Sequence[str]) -> tuple[list[Path], list[GateResult]]:
    paths: set[Path] = set()
    errors: list[GateResult] = []
    for target_text in targets:
        target = Path(target_text)
        if target.is_file():
            paths.add(target)
        elif target.is_dir():
            paths.update(path for path in target.rglob("*.json") if path.is_file())
        else:
            errors.append(
                _result(
                    {"case_id": target.name or "missing-target"},
                    source=str(target),
                    result=BLOCKED,
                    reason=f"fixture target does not exist: {target}",
                    calculated=None,
                )
            )
    return sorted(paths, key=str), errors


def render_text(results: Sequence[GateResult]) -> str:
    lines: list[str] = []
    fields = (
        "mode", "task_id", "change_category", "declared_trigger_level",
        "calculated_trigger_level", "advisory_required", "producer",
        "runtime_identity", "artifact_type", "to", "next_receiver",
        "request_id", "review_id", "request_id_ref", "conclusion",
        "request_valid", "review_valid", "lifecycle_state", "consumed",
        "allowed", "result", "reason", "warnings", "expected_result",
        "expectation_met",
    )
    for item in results:
        lines.append(f"{item.result}: {item.case_id}")
        lines.extend(f"  {field}: {getattr(item, field)!r}" for field in fields)
    counts = {value: sum(item.result == value for item in results) for value in RESULT_VALUES}
    mismatches = sum(not item.expectation_met for item in results)
    lines.append(
        f"SUMMARY: total={len(results)} pass={counts[PASS]} deny={counts[DENY]} "
        f"blocked={counts[BLOCKED]} expectation_mismatches={mismatches}"
    )
    return "\n".join(lines)


def render_json(results: Sequence[GateResult]) -> str:
    return json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixture-only ACOS advisory gate checker")
    parser.add_argument("fixtures", nargs="+", help="JSON fixtures or directories")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    paths, errors = discover_paths(args.fixtures)
    results = [load_fixture(path) for path in paths] + errors
    if not results:
        parser.error("No JSON fixtures found")
    print(render_json(results) if args.format == "json" else render_text(results))
    return 1 if any(not item.expectation_met for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

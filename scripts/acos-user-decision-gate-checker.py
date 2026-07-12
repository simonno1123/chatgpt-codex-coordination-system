#!/usr/bin/env python3
"""Deterministic fixture-only ACOS User Decision Gate checker."""

from __future__ import annotations

import argparse, copy, json, re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

PASS, DENY, BLOCKED = "PASS", "DENY", "BLOCKED"
RESULTS = {PASS, DENY, BLOCKED}
NOT_REQUIRED = "user_decision_not_required"
REQUIRED = "user_decision_required"
SATISFIED = "user_decision_already_satisfied"
LEVELS = {NOT_REQUIRED, REQUIRED, SATISFIED}
MODES = {"classify_requirement", "validate_decision", "consume_decision", "verify_scope", "verify_lifecycle"}
CATEGORIES = {
    "readonly_validation": NOT_REQUIRED, "routine_status_check": NOT_REQUIRED,
    "exact_prior_decision_verified": SATISFIED,
    **{name: REQUIRED for name in (
        "start_new_task", "start_next_phase", "resume_changed_or_expired_task",
        "expand_task_scope", "change_core_governance", "enable_blocking_enforcement",
        "connect_live_repository", "connect_instance_project", "run_production_test",
        "create_runtime_launcher", "enable_git_wrapper_or_hook", "publish_release",
        "close_phase_with_major_risk", "irreversible_or_destructive_operation",
        "change_frozen_scope", "start_task_057_or_later")},
}
TYPE_ACTION = {
    "authorize_task_start": "start_task", "authorize_task_resume": "resume_task",
    "authorize_scope_change": "change_scope", "authorize_commit": "commit",
    "authorize_push": "push", "authorize_release": "release",
    "authorize_live_connection": "connect_live_repository",
    "authorize_enforcement": "enable_enforcement", "authorize_task_closure": "close_task",
    "deny_action": "deny", "revoke_authorization": "deny",
}
STATUSES = {"AUTHORIZED", "DENIED", "REVOKED", "EXPIRED", "SUPERSEDED"}
ACTIONS = set(TYPE_ACTION.values()) | {"connect_instance"}
VAGUE = {"commit_and_push", "start_and_close", "all_actions", "future_tasks", "unrestricted", "wildcard"}
MUTATING = {"resume_task", "change_scope", "commit", "push", "release", "connect_live_repository", "connect_instance", "enable_enforcement", "close_task"}
OTHER_ROLES = {
    "ChatGPT Review Runtime": {"ChatGPT", "ChatGPT Review"},
    "Codex Executor Runtime": {"Codex Executor"},
    "External Advisory Runtime": {"External Advisory Reviewer"},
    "Automation Runtime": {"Automation"},
}
USER_RUNTIME = "User Decision Runtime"
LIFECYCLE = ["requirement_classified", "user_decision", "chatgpt_task_or_decision", "codex_execution"]
NOTICE = "Fixture-only result; no real identity, decision, authorization, action, Git operation, or external state was created."


@dataclass
class Result:
    case_id: str; mode: str | None; requirement_category: str | None
    declared_requirement: str | None; calculated_requirement: str | None
    user_decision_required: bool | None; project: str | None; task_id: str | None
    producer: str | None; runtime_identity: str | None; artifact_type: str | None
    decision_id: str | None; decision_type: str | None; decision_status: str | None
    authorized_action: str | None; requested_action: str | None
    decision_valid: bool | None; scope_valid: bool | None; consumable: bool | None
    consumed: bool | None; lifecycle_state: str | None; allowed: bool; result: str
    reason: str; warnings: list[str]; source: str; expected_result: str | None
    expectation_met: bool | None; authorized_scope: list[str] | None = None
    requested_scope: list[str] | None = None; target: str | None = None
    requested_target: str | None = None; branch: str | None = None
    requested_branch: str | None = None; head: str | None = None
    requested_head: str | None = None; scope_mismatches: list[str] | None = None
    role_violations: list[str] | None = None; authority_violations: list[str] | None = None
    duplicate_state: str | None = None; stale: bool | None = None
    revoked: bool | None = None; superseded: bool | None = None; expires_at: str | None = None


class Blocked(ValueError): pass
class Denied(ValueError): pass


def text(v: object) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def req(d: Mapping[str, Any], k: str) -> str:
    v = text(d.get(k))
    if not v: raise Blocked(f"missing or invalid {k}")
    return v


def opt(d: Mapping[str, Any], k: str) -> str | None:
    if k not in d or d[k] is None: return None
    v = text(d[k])
    if not v: raise Blocked(f"{k} must be a string or null")
    return v


def boolean(d: Mapping[str, Any], k: str, required: bool = False) -> bool:
    if k not in d:
        if required: raise Blocked(f"missing required boolean field: {k}")
        return False
    if not isinstance(d[k], bool): raise Blocked(f"{k} must be a boolean")
    return d[k]


def scope(d: Mapping[str, Any], k: str, required: bool = False) -> list[str]:
    if k not in d:
        if required: raise Blocked(f"missing required scope: {k}")
        return []
    v = d[k]
    if not isinstance(v, list): raise Blocked(f"{k} must be an array")
    if any(not text(x) for x in v): raise Blocked(f"{k} entries must be strings")
    if required and not v: raise Blocked(f"{k} must not be empty")
    return [x.strip() for x in v]


def timestamp(d: Mapping[str, Any], k: str) -> datetime:
    v = req(d, k)
    try: dt = datetime.fromisoformat(v[:-1] + "+00:00" if v.endswith("Z") else v)
    except ValueError as e: raise Blocked(f"{k} must be valid RFC3339") from e
    if not dt.tzinfo: raise Blocked(f"{k} must include timezone")
    return dt


def classify(d: Mapping[str, Any]) -> str:
    category, declared = req(d, "requirement_category"), req(d, "declared_requirement")
    if category not in CATEGORIES: raise Blocked(f"unknown requirement_category: {category}")
    if declared not in LEVELS: raise Blocked(f"unknown declared_requirement: {declared}")
    calculated = CATEGORIES[category]
    if declared != calculated: raise Blocked("declared requirement contradicts category")
    return calculated


def validate_identity(d: Mapping[str, Any]) -> None:
    producer, runtime = req(d, "producer"), req(d, "runtime_identity")
    if runtime == USER_RUNTIME:
        if producer not in {"User Decision", "User"}: raise Denied("invalid User Decision producer")
    elif runtime in OTHER_ROLES:
        if producer not in OTHER_ROLES[runtime]: raise Denied("producer/runtime mismatch")
        raise Denied("non-user runtime cannot produce USER DECISION")
    else: raise Blocked(f"unknown runtime_identity: {runtime}")


def validate_decision(d: Mapping[str, Any]) -> tuple[str, str]:
    if req(d, "artifact_type") != "USER DECISION": raise Denied("artifact_type must be USER DECISION")
    validate_identity(d); req(d, "decision_id"); req(d, "project"); req(d, "task_id")
    dtype, action = req(d, "decision_type"), req(d, "authorized_action")
    if dtype not in TYPE_ACTION: raise Blocked(f"unknown decision_type: {dtype}")
    if action in VAGUE or re.search(r"[,;+]|\band\b", action, re.I): raise Denied("merged or vague authorization")
    if action not in ACTIONS: raise Blocked(f"unknown authorized_action: {action}")
    if action != TYPE_ACTION[dtype]: raise Denied("authorized_action does not match decision_type")
    status = req(d, "decision_status").upper()
    if status not in STATUSES: raise Blocked(f"unknown decision_status: {status}")
    auth_scope = scope(d, "authorized_scope", True)
    if any(x.lower() in {"*", ".", "all", "repository", "entire repository"} for x in auth_scope): raise Denied("scope is vague or repository-wide")
    req(d, "target"); opt(d, "branch"); opt(d, "head")
    issued, expires, now = timestamp(d, "issued_at"), timestamp(d, "expires_at"), timestamp(d, "as_of")
    if expires <= issued: raise Blocked("expires_at must follow issued_at")
    one_time = boolean(d, "one_time", True); boolean(d, "consumed", True)
    superseded, revoked = boolean(d, "superseded", True), boolean(d, "revoked", True)
    if revoked != (status == "REVOKED"): raise Blocked("status contradicts revoked")
    if superseded != (status == "SUPERSEDED"): raise Blocked("status contradicts superseded")
    if (status == "EXPIRED") != (expires <= now): raise Blocked("status contradicts expiry")
    req(d, "reason"); receiver, next_receiver = req(d, "to"), req(d, "next_receiver")
    if receiver not in {"ChatGPT Review", "Codex Executor"} or next_receiver != "ChatGPT Review": raise Denied("invalid decision routing")
    if boolean(d, "multiple_authorizations"): raise Denied("multiple merged authorizations")
    if text(d.get("source_artifact")) in {"ADVISORY REVIEW", "AUDIT RECORD", "RESULT", "BLOCKED RESULT", "CHATGPT DECISION"}: raise Denied("non-user artifact cannot substitute for USER DECISION")
    if boolean(d, "implicit_consent"): raise Denied("implicit consent is forbidden")
    if action in {"commit", "push"} and (not text(d.get("branch")) or not text(d.get("head"))): raise Blocked(f"{action} requires branch and head")
    if dtype == "authorize_scope_change" and not (scope(d, "scope_additions", True) or scope(d, "scope_removals", True)): raise Blocked("scope change lacks explicit delta")
    _ = one_time
    return status, action


def mismatches(d: Mapping[str, Any]) -> list[str]:
    out = []
    if not set(scope(d, "requested_scope", True)).issubset(scope(d, "authorized_scope", True)): out.append("scope mismatch")
    for requested, authorized in (("requested_project", "project"), ("requested_task_id", "task_id"), ("requested_target", "target"), ("requested_branch", "branch"), ("requested_head", "head")):
        if opt(d, requested) != opt(d, authorized): out.append(f"{requested} mismatch")
    if req(d, "requested_action") != req(d, "authorized_action"): out.append("action mismatch")
    return out


def consume(d: Mapping[str, Any], status: str, action: str) -> tuple[str, bool, list[str]]:
    if not boolean(d, "decision_validated", True): raise Denied("invalid decision cannot be consumed")
    consumer, runtime = req(d, "consumer"), req(d, "consumer_runtime")
    chatgpt_actions = {"start_task", "change_scope", "release", "connect_live_repository", "connect_instance", "enable_enforcement", "close_task", "deny"}
    valid_consumer = (action in chatgpt_actions and runtime == "ChatGPT Review Runtime" and consumer in {"ChatGPT", "ChatGPT Review"}) or (action in {"resume_task", "commit", "push"} and runtime == "Codex Executor Runtime" and consumer == "Codex Executor")
    if not valid_consumer: raise Denied("consumer runtime is not authorized")
    if status != "AUTHORIZED":
        state = {"DENIED": "DECISION_DENIED", "REVOKED": "DECISION_REVOKED", "EXPIRED": "DECISION_EXPIRED", "SUPERSEDED": "DECISION_SUPERSEDED"}[status]
        if boolean(d, "attempt_execution"): raise Denied(f"{status} decision cannot execute")
        return state, False, []
    if boolean(d, "stale"): raise Denied("stale decision")
    if boolean(d, "duplicate") and not text(d.get("duplicate_state")): raise Blocked("duplicate state is unknown")
    count = d.get("previous_consumption_count")
    if type(count) is not int or count < 0: raise Blocked("previous_consumption_count must be non-negative integer")
    if boolean(d, "one_time", True) and (boolean(d, "consumed", True) or count > 0): raise Denied("one-time decision already consumed")
    problems = mismatches(d)
    if problems: raise Denied("; ".join(problems))
    if boolean(d, "scope_changed"): raise Denied("consumer expanded scope")
    if boolean(d, "auto_execute"): raise Denied("automatic execution is forbidden")
    if action in MUTATING and not boolean(d, "operation_authorization_present", True): raise Denied("separate operation authorization missing")
    return "DECISION_CONSUMABLE", True, []


def lifecycle(d: Mapping[str, Any], level: str) -> str:
    events = scope(d, "lifecycle_events", True)
    if len(events) != len(set(events)): raise Blocked("contradictory lifecycle")
    if level == REQUIRED:
        if "user_decision" not in events:
            if boolean(d, "attempt_execution"): raise Denied("required decision missing before execution")
            return "DECISION_MISSING"
        missing = [x for x in LIFECYCLE if x not in events]
        if missing: raise Blocked("incomplete lifecycle")
        indexes = [events.index(x) for x in LIFECYCLE]
        if indexes != sorted(indexes): raise Denied("invalid lifecycle order")
    return "DECISION_CONSUMED" if "codex_execution" in events else "FINAL_CHATGPT_ACTION_PENDING"


def make_result(d: Mapping[str, Any], source: str, result: str, reason: str, level: str | None, valid=None, scope_valid=None, consumable=None, state=None, problems=None) -> Result:
    expected = text(d.get("expected_result")); expected = expected.upper() if expected else None
    reason_plain = reason
    checks = [result == (expected or PASS)]
    if isinstance(d.get("expected_allowed"), bool): checks.append((result == PASS) == d["expected_allowed"])
    if text(d.get("expected_reason_contains")): checks.append(text(d["expected_reason_contains"]) in reason_plain)
    return Result(
        text(d.get("case_id")) or Path(source).stem, text(d.get("mode")), text(d.get("requirement_category")), text(d.get("declared_requirement")), level, level == REQUIRED if level else None,
        text(d.get("project")), text(d.get("task_id")), text(d.get("producer")), text(d.get("runtime_identity")), text(d.get("artifact_type")), text(d.get("decision_id")), text(d.get("decision_type")), text(d.get("decision_status")), text(d.get("authorized_action")), text(d.get("requested_action")), valid, scope_valid, consumable,
        d.get("consumed") if isinstance(d.get("consumed"), bool) else None, state, result == PASS, result, f"{reason} {NOTICE}", [], source, expected, all(checks),
        d.get("authorized_scope") if isinstance(d.get("authorized_scope"), list) else None, d.get("requested_scope") if isinstance(d.get("requested_scope"), list) else None,
        text(d.get("target")), text(d.get("requested_target")), text(d.get("branch")), text(d.get("requested_branch")), text(d.get("head")), text(d.get("requested_head")), problems or [], [], [reason] if result == DENY else [], text(d.get("duplicate_state")), d.get("stale") if isinstance(d.get("stale"), bool) else None, d.get("revoked") if isinstance(d.get("revoked"), bool) else None, d.get("superseded") if isinstance(d.get("superseded"), bool) else None, text(d.get("expires_at")))


def evaluate_fixture(d: Mapping[str, Any], source="<memory>") -> Result:
    level = None
    try:
        mode = req(d, "mode")
        if mode not in MODES: raise Blocked(f"unknown mode: {mode}")
        if text(d.get("expected_result")) and text(d["expected_result"]).upper() not in RESULTS: raise Blocked("unknown expected_result")
        level = classify(d); req(d, "project"); req(d, "task_id"); req(d, "producer"); req(d, "runtime_identity"); req(d, "artifact_type")
        if mode == "classify_requirement": return make_result(d, source, PASS, "Requirement classified.", level, state=level.upper())
        if mode == "verify_lifecycle": return make_result(d, source, PASS, "Lifecycle valid.", level, state=lifecycle(d, level))
        status, action = validate_decision(d)
        if mode == "validate_decision": return make_result(d, source, PASS, "Decision valid.", level, True, state="DECISION_" + status)
        if mode == "verify_scope":
            problems = mismatches(d)
            if problems: raise Denied("; ".join(problems))
            return make_result(d, source, PASS, "Scope valid.", level, True, True, state="DECISION_AUTHORIZED")
        state, consumable, problems = consume(d, status, action)
        return make_result(d, source, PASS, "Decision consumption valid.", level, True, not problems, consumable, state, problems)
    except Denied as e: return make_result(d, source, DENY, str(e), level, False, False, False, "DECISION_INVALID")
    except Blocked as e: return make_result(d, source, BLOCKED, str(e), level, state="DECISION_MISSING")


BASE = {"requirement_category":"start_new_task","declared_requirement":REQUIRED,"project":"/Users/zhang/Documents/chatgpt-codex-coordination-system","task_id":"TASK_056"}
DECISION = {**BASE,"mode":"validate_decision","producer":"User Decision","runtime_identity":USER_RUNTIME,"artifact_type":"USER DECISION","decision_id":"USER-DEC-056-001","decision_type":"authorize_task_start","decision_status":"AUTHORIZED","authorized_action":"start_task","authorized_scope":["TASK_056"],"target":"TASK_056","branch":None,"head":None,"issued_at":"2026-07-12T00:00:00Z","expires_at":"2026-07-13T00:00:00Z","as_of":"2026-07-12T01:00:00Z","one_time":True,"consumed":False,"superseded":False,"revoked":False,"reason":"Explicit bounded user authorization.","to":"ChatGPT Review","next_receiver":"ChatGPT Review"}
CONSUME = {**DECISION,"mode":"consume_decision","decision_validated":True,"consumer":"ChatGPT Review","consumer_runtime":"ChatGPT Review Runtime","requested_action":"start_task","requested_scope":["TASK_056"],"requested_project":DECISION["project"],"requested_task_id":"TASK_056","requested_target":"TASK_056","requested_branch":None,"requested_head":None,"previous_consumption_count":0,"operation_authorization_present":False}
TEMPLATES = {
    "classify_required":{**BASE,"mode":"classify_requirement","producer":"ChatGPT Review","runtime_identity":"ChatGPT Review Runtime","artifact_type":"REQUIREMENT ASSESSMENT"},
    "classify_not_required":{**BASE,"mode":"classify_requirement","requirement_category":"readonly_validation","declared_requirement":NOT_REQUIRED,"producer":"ChatGPT Review","runtime_identity":"ChatGPT Review Runtime","artifact_type":"REQUIREMENT ASSESSMENT"},
    "classify_satisfied":{**BASE,"mode":"classify_requirement","requirement_category":"exact_prior_decision_verified","declared_requirement":SATISFIED,"producer":"ChatGPT Review","runtime_identity":"ChatGPT Review Runtime","artifact_type":"REQUIREMENT ASSESSMENT"},
    "valid_decision":DECISION,"valid_consumption":CONSUME,"valid_scope":{**CONSUME,"mode":"verify_scope"},
    "valid_lifecycle":{**BASE,"mode":"verify_lifecycle","producer":"ChatGPT Review","runtime_identity":"ChatGPT Review Runtime","artifact_type":"LIFECYCLE RECORD","lifecycle_events":LIFECYCLE},
}


def load_fixture(path: Path) -> Result:
    inferred = PASS if path.name.startswith("valid-") else DENY if path.name.startswith("invalid-") else BLOCKED if path.name.startswith("blocked-") else None
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e: return make_result({"case_id":path.stem,"expected_result":inferred},str(path),BLOCKED,f"unable to read fixture: {e}",None)
    if not isinstance(data, dict): return make_result({"case_id":path.stem,"expected_result":inferred},str(path),BLOCKED,"fixture root must be object",None)
    template = data.get("template")
    if template is not None:
        if template not in TEMPLATES: return make_result({"case_id":path.stem,"expected_result":inferred},str(path),BLOCKED,"unknown fixture template",None)
        expanded = copy.deepcopy(TEMPLATES[template]); expanded.update({k:v for k,v in data.items() if k not in {"template","omit_fields"}})
        omitted = data.get("omit_fields",[])
        if not isinstance(omitted,list): return make_result({"case_id":path.stem,"expected_result":inferred},str(path),BLOCKED,"omit_fields must be array",None)
        for field in omitted: expanded.pop(field,None)
        data = expanded
    if inferred and "expected_result" not in data: data["expected_result"] = inferred
    return evaluate_fixture(data,str(path))


def discover_paths(targets: Sequence[str]):
    paths=set(); errors=[]
    for raw in targets:
        p=Path(raw)
        if p.is_file(): paths.add(p)
        elif p.is_dir(): paths.update(x for x in p.rglob("*.json") if x.is_file())
        else: errors.append(make_result({"case_id":p.name},str(p),BLOCKED,"fixture target does not exist",None))
    return sorted(paths,key=str),errors


def render_text(results):
    fields=("mode","requirement_category","declared_requirement","calculated_requirement","user_decision_required","project","task_id","producer","runtime_identity","artifact_type","decision_id","decision_type","decision_status","authorized_action","requested_action","decision_valid","scope_valid","consumable","consumed","lifecycle_state","allowed","result","reason","expected_result","expectation_met")
    lines=[]
    for item in results:
        lines.append(f"{item.result}: {item.case_id}"); lines.extend(f"  {f}: {getattr(item,f)!r}" for f in fields)
    counts={x:sum(r.result==x for r in results) for x in RESULTS}; mismatches=sum(not r.expectation_met for r in results)
    lines.append(f"SUMMARY: total={len(results)} pass={counts[PASS]} deny={counts[DENY]} blocked={counts[BLOCKED]} expectation_mismatches={mismatches}")
    return "\n".join(lines)


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument("fixtures",nargs="+"); parser.add_argument("--format",choices=("text","json"),default="text"); args=parser.parse_args(argv)
    paths,errors=discover_paths(args.fixtures); results=[load_fixture(p) for p in paths]+errors
    if not results: parser.error("No JSON fixtures found")
    print(json.dumps([asdict(r) for r in results],ensure_ascii=False,indent=2) if args.format=="json" else render_text(results))
    return 1 if any(not r.expectation_met for r in results) else 0


if __name__ == "__main__": raise SystemExit(main())

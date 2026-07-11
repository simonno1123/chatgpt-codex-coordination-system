#!/usr/bin/env python3
"""Fixture-only ACOS audit JSONL writer and hash-chain verifier."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

PASS = "PASS"
DENY = "DENY"
BLOCKED = "BLOCKED"
RESULT_VALUES = frozenset({PASS, DENY, BLOCKED})
SCHEMA_VERSION = "1.0"
HASH_ALGORITHM = "sha256"
GENESIS_PREVIOUS_HASH = None
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

EVENT_TYPES = frozenset(
    {
        "task_created",
        "result_received",
        "blocked_result_received",
        "review_completed",
        "advisory_requested",
        "advisory_review_received",
        "decision_issued",
        "operation_requested",
        "operation_authorized",
        "operation_denied",
        "operation_blocked",
        "operation_completed",
        "commit_created",
        "push_completed",
        "release_completed",
        "policy_violation_detected",
        "validation_completed",
        "task_closed",
    }
)

RUNTIME_PRODUCERS = {
    "ChatGPT Review Runtime": frozenset({"ChatGPT", "ChatGPT Review"}),
    "Codex Executor Runtime": frozenset({"Codex Executor"}),
    "External Advisory Runtime": frozenset({"External Advisory Reviewer"}),
    "Automation Runtime": frozenset({"Automation"}),
}

EVENT_RUNTIME_POLICY = {
    "task_created": frozenset({"ChatGPT Review Runtime"}),
    "result_received": frozenset({"Codex Executor Runtime", "Automation Runtime"}),
    "blocked_result_received": frozenset({"Codex Executor Runtime"}),
    "review_completed": frozenset({"ChatGPT Review Runtime"}),
    "advisory_requested": frozenset({"ChatGPT Review Runtime"}),
    "advisory_review_received": frozenset({"External Advisory Runtime"}),
    "decision_issued": frozenset({"ChatGPT Review Runtime"}),
    "operation_requested": frozenset({"Codex Executor Runtime"}),
    "operation_authorized": frozenset({"ChatGPT Review Runtime"}),
    "operation_denied": frozenset({"ChatGPT Review Runtime", "Automation Runtime"}),
    "operation_blocked": frozenset({"ChatGPT Review Runtime", "Automation Runtime"}),
    "operation_completed": frozenset({"Codex Executor Runtime"}),
    "commit_created": frozenset({"Codex Executor Runtime"}),
    "push_completed": frozenset({"Codex Executor Runtime"}),
    "release_completed": frozenset({"Codex Executor Runtime"}),
    "policy_violation_detected": frozenset({"Automation Runtime"}),
    "validation_completed": frozenset({"Automation Runtime"}),
    "task_closed": frozenset({"ChatGPT Review Runtime"}),
}

ARTIFACT_EXPECTATIONS = {
    "task_created": "TASK",
    "result_received": "RESULT",
    "blocked_result_received": "BLOCKED RESULT",
    "review_completed": "REVIEW",
    "advisory_review_received": "ADVISORY REVIEW",
    "decision_issued": "DECISION",
}

CANONICAL_FIELDS = (
    "schema_version",
    "event_id",
    "sequence",
    "timestamp",
    "event_type",
    "project",
    "task_id",
    "producer",
    "runtime_identity",
    "artifact_type",
    "operation",
    "status",
    "authorization_id",
    "authorization_source",
    "target",
    "repository_scope",
    "branch",
    "head",
    "commit_hash",
    "remote",
    "details",
    "previous_event_hash",
    "event_hash",
)

NON_NULL_REQUIRED = (
    "schema_version",
    "event_id",
    "sequence",
    "timestamp",
    "event_type",
    "project",
    "producer",
    "runtime_identity",
    "status",
    "details",
)


@dataclass
class AuditResult:
    case_id: str
    mode: str | None
    schema_version: str | None
    event_count: int
    first_sequence: int | None
    last_sequence: int | None
    chain_valid: bool
    tamper_detected: bool
    allowed: bool
    result: str
    reason: str
    source: str
    expected_result: str | None
    expectation_met: bool | None
    event: dict[str, Any] | None = None
    events: list[dict[str, Any]] | None = None
    canonical_payload: str | None = None
    calculated_event_hash: str | None = None
    failed_event_id: str | None = None
    failed_sequence: int | None = None
    expected_previous_hash: str | None = None
    observed_previous_hash: str | None = None
    expected_event_hash: str | None = None
    observed_event_hash: str | None = None


class AuditBlocked(ValueError):
    pass


class AuditDenied(ValueError):
    pass


@dataclass(frozen=True)
class ChainFailure:
    reason: str
    event_id: str | None = None
    sequence: int | None = None
    expected_previous_hash: str | None = None
    observed_previous_hash: str | None = None
    expected_event_hash: str | None = None
    observed_event_hash: str | None = None
    blocked: bool = False


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_payload(event: Mapping[str, Any]) -> str:
    payload = {field: event.get(field) for field in CANONICAL_FIELDS if field != "event_hash"}
    return canonical_json(payload)


def calculate_event_hash(event: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(event).encode("utf-8")).hexdigest()


def deterministic_event_id(event: Mapping[str, Any]) -> str:
    seed = {
        field: event.get(field)
        for field in CANONICAL_FIELDS
        if field not in {"event_id", "previous_event_hash", "event_hash"}
    }
    return "evt-" + hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:20]


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise AuditBlocked("timestamp must be a non-empty string")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise AuditBlocked("timestamp must be valid RFC3339/ISO 8601") from exc
    if parsed.tzinfo is None:
        raise AuditBlocked("timestamp must include a timezone")
    return parsed


def _normalize_event(
    raw: Mapping[str, Any], *, auto_event_id: bool, require_hash: bool
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise AuditBlocked("each event must be a JSON object")
    event = {field: raw.get(field) for field in CANONICAL_FIELDS}

    if event["schema_version"] is None:
        raise AuditBlocked("missing schema_version")
    if event["schema_version"] != SCHEMA_VERSION:
        raise AuditBlocked(f"unsupported schema_version: {event['schema_version']}")
    if event["event_id"] is None and auto_event_id:
        event["event_id"] = deterministic_event_id(event)
    if not _nonempty_string(event["event_id"]):
        raise AuditBlocked("missing or invalid event_id")
    if type(event["sequence"]) is not int or event["sequence"] <= 0:
        raise AuditBlocked("sequence must be a positive integer and bool is forbidden")
    _parse_timestamp(event["timestamp"])
    if not _nonempty_string(event["event_type"]):
        raise AuditBlocked("missing event_type")
    if event["event_type"] not in EVENT_TYPES:
        raise AuditBlocked(f"unknown event_type: {event['event_type']}")
    if not _nonempty_string(event["project"]):
        raise AuditBlocked("missing project")
    if not _nonempty_string(event["producer"]):
        raise AuditBlocked("missing producer")
    if not _nonempty_string(event["runtime_identity"]):
        raise AuditBlocked("missing runtime_identity")
    if event["runtime_identity"] not in RUNTIME_PRODUCERS:
        raise AuditBlocked(f"unknown runtime_identity: {event['runtime_identity']}")
    if event["producer"] not in RUNTIME_PRODUCERS[event["runtime_identity"]]:
        raise AuditDenied("producer does not match runtime_identity")
    if event["runtime_identity"] not in EVENT_RUNTIME_POLICY[event["event_type"]]:
        raise AuditDenied("event_type is not permitted for runtime_identity")
    if not _nonempty_string(event["status"]):
        raise AuditBlocked("missing status")
    if not isinstance(event["details"], dict):
        raise AuditBlocked("details must be an object")
    if event["artifact_type"] is not None and not isinstance(event["artifact_type"], str):
        raise AuditBlocked("artifact_type must be a string or null")
    expected_artifact = ARTIFACT_EXPECTATIONS.get(event["event_type"])
    if expected_artifact and event["artifact_type"] != expected_artifact:
        raise AuditDenied("artifact_type conflicts with event_type")
    if event["previous_event_hash"] is not None and not isinstance(
        event["previous_event_hash"], str
    ):
        raise AuditBlocked("previous_event_hash must be a string or null")
    if require_hash:
        if not isinstance(event["event_hash"], str):
            raise AuditBlocked("event_hash must be a string")
        if not HASH_PATTERN.fullmatch(event["event_hash"]):
            raise AuditBlocked("event_hash must be 64 lowercase hexadecimal characters")
    elif event["event_hash"] is not None:
        raise AuditDenied("generate input must not supply event_hash")

    if event["event_type"] in {
        "operation_requested",
        "operation_authorized",
        "operation_denied",
        "operation_blocked",
        "operation_completed",
    } and not _nonempty_string(event["operation"]):
        raise AuditBlocked("operation is required for operation event types")
    if event["event_type"] == "operation_authorized":
        if not _nonempty_string(event["authorization_id"]) or not _nonempty_string(
            event["authorization_source"]
        ):
            raise AuditBlocked("operation_authorized requires authorization_id and source")
    if event["event_type"] == "commit_created" and not _nonempty_string(
        event["commit_hash"]
    ):
        raise AuditBlocked("commit_created requires commit_hash")
    if event["event_type"] == "push_completed":
        if not _nonempty_string(event["commit_hash"]) or not _nonempty_string(event["remote"]):
            raise AuditBlocked("push_completed requires commit_hash and remote")
    if event["event_type"] == "release_completed":
        if not _nonempty_string(event["commit_hash"]) or not _nonempty_string(event["target"]):
            raise AuditBlocked("release_completed requires commit_hash and target")
    if event["authorization_source"] == "AUDIT RECORD" or event["details"].get(
        "grants_authorization"
    ) is True:
        raise AuditDenied("audit evidence cannot grant authorization")
    return event


def _sequence_failure(events: Sequence[Mapping[str, Any]]) -> ChainFailure | None:
    seen_ids: set[str] = set()
    seen_sequences: set[int] = set()
    previous_sequence = 0
    previous_timestamp: datetime | None = None
    for index, event in enumerate(events):
        event_id = event["event_id"]
        sequence = event["sequence"]
        timestamp = _parse_timestamp(event["timestamp"])
        if event_id in seen_ids:
            return ChainFailure("duplicate event_id", event_id, sequence)
        if sequence in seen_sequences:
            return ChainFailure("duplicate sequence", event_id, sequence)
        if index == 0 and sequence != 1:
            return ChainFailure("first sequence must be 1", event_id, sequence)
        if index > 0 and sequence != previous_sequence + 1:
            label = "sequence regression" if sequence < previous_sequence else "sequence gap"
            return ChainFailure(label, event_id, sequence)
        if previous_timestamp and timestamp < previous_timestamp:
            return ChainFailure("timestamp order contradicts sequence order", event_id, sequence)
        seen_ids.add(event_id)
        seen_sequences.add(sequence)
        previous_sequence = sequence
        previous_timestamp = timestamp
    return None


def generate_chain(raw_events: Sequence[Mapping[str, Any]], *, auto_event_id: bool) -> list[dict[str, Any]]:
    if not isinstance(raw_events, list) or not raw_events:
        raise AuditBlocked("audit chain must be a non-empty array")
    events = [
        _normalize_event(raw, auto_event_id=auto_event_id, require_hash=False)
        for raw in raw_events
    ]
    failure = _sequence_failure(events)
    if failure:
        raise AuditDenied(failure.reason)

    previous: str | None = GENESIS_PREVIOUS_HASH
    for event in events:
        if event["previous_event_hash"] not in (None, ""):
            raise AuditDenied("generate input must use canonical null genesis/linkage")
        event["previous_event_hash"] = previous
        event["event_hash"] = calculate_event_hash(event)
        previous = event["event_hash"]
    return events


def verify_chain(raw_events: Sequence[Mapping[str, Any]]) -> ChainFailure | None:
    if not isinstance(raw_events, list) or not raw_events:
        raise AuditBlocked("audit chain must be a non-empty array")
    events = [
        _normalize_event(raw, auto_event_id=False, require_hash=True) for raw in raw_events
    ]
    sequence_failure = _sequence_failure(events)
    if sequence_failure:
        return sequence_failure

    expected_previous: str | None = GENESIS_PREVIOUS_HASH
    for event in events:
        observed_previous = event["previous_event_hash"]
        if observed_previous != expected_previous:
            return ChainFailure(
                "previous_event_hash linkage mismatch",
                event["event_id"],
                event["sequence"],
                expected_previous_hash=expected_previous,
                observed_previous_hash=observed_previous,
            )
        expected_hash = calculate_event_hash(event)
        if event["event_hash"] != expected_hash:
            return ChainFailure(
                "event_hash mismatch",
                event["event_id"],
                event["sequence"],
                expected_event_hash=expected_hash,
                observed_event_hash=event["event_hash"],
            )
        expected_previous = event["event_hash"]
    return None


def events_to_jsonl(events: Sequence[Mapping[str, Any]]) -> str:
    return "".join(canonical_json(event) + "\n" for event in events)


def _simulate_tamper(events: list[dict[str, Any]], scenario: str) -> list[dict[str, Any]]:
    altered = copy.deepcopy(events)
    if scenario == "payload":
        altered[-1]["status"] = "tampered"
    elif scenario == "event_hash":
        altered[-1]["event_hash"] = "0" * 64
    elif scenario == "previous_hash":
        altered[-1]["previous_event_hash"] = "0" * 64
    elif scenario == "delete_middle":
        if len(altered) < 3:
            raise AuditBlocked("delete_middle requires at least three events")
        altered.pop(1)
    elif scenario == "insert_middle":
        if len(altered) < 2:
            raise AuditBlocked("insert_middle requires at least two events")
        inserted = copy.deepcopy(altered[0])
        inserted["event_id"] = "evt-inserted"
        inserted["sequence"] = 2
        altered.insert(1, inserted)
    elif scenario == "duplicate_event_id":
        altered[-1]["event_id"] = altered[0]["event_id"]
    elif scenario == "duplicate_sequence":
        altered[-1]["sequence"] = altered[0]["sequence"]
    elif scenario == "sequence_gap":
        altered[-1]["sequence"] += 1
    elif scenario == "sequence_regression":
        altered[-1]["sequence"] = 1
    elif scenario == "reorder":
        if len(altered) < 2:
            raise AuditBlocked("reorder requires at least two events")
        altered[0], altered[1] = altered[1], altered[0]
    elif scenario == "timestamp":
        altered[-1]["timestamp"] = "2020-01-01T00:00:00Z"
    elif scenario == "details":
        altered[-1]["details"]["tampered"] = True
    elif scenario == "genesis":
        altered[0]["previous_event_hash"] = "0" * 64
    elif scenario == "algorithm":
        raise AuditDenied("unknown hash algorithm")
    else:
        raise AuditBlocked(f"unknown tamper scenario: {scenario}")
    return altered


def _infer_expected_result(path: Path) -> str | None:
    name = path.name.lower()
    if name.startswith("valid-"):
        return PASS
    if name.startswith("invalid-"):
        return DENY
    if name.startswith("blocked-"):
        return BLOCKED
    return None


def _make_result(
    *,
    case_id: str,
    mode: str | None,
    result: str,
    reason: str,
    source: str,
    expected_result: str | None,
    events: list[dict[str, Any]] | None = None,
    failure: ChainFailure | None = None,
) -> AuditResult:
    events = events or []
    allowed = result == PASS
    return AuditResult(
        case_id=case_id,
        mode=mode,
        schema_version=events[0].get("schema_version") if events else None,
        event_count=len(events),
        first_sequence=events[0].get("sequence") if events else None,
        last_sequence=events[-1].get("sequence") if events else None,
        chain_valid=result == PASS,
        tamper_detected=result == DENY and failure is not None,
        allowed=allowed,
        result=result,
        reason=reason,
        source=source,
        expected_result=expected_result,
        expectation_met=(result == expected_result if expected_result else result == PASS),
        event=events[0] if len(events) == 1 else None,
        events=events or None,
        canonical_payload=canonical_payload(events[0]) if len(events) == 1 else None,
        calculated_event_hash=calculate_event_hash(events[0]) if len(events) == 1 else None,
        failed_event_id=failure.event_id if failure else None,
        failed_sequence=failure.sequence if failure else None,
        expected_previous_hash=failure.expected_previous_hash if failure else None,
        observed_previous_hash=failure.observed_previous_hash if failure else None,
        expected_event_hash=failure.expected_event_hash if failure else None,
        observed_event_hash=failure.observed_event_hash if failure else None,
    )


def evaluate_fixture(data: Mapping[str, Any], source: str = "<memory>") -> AuditResult:
    case_id = _nonempty_string(data.get("case_id")) or Path(source).stem or "unknown-case"
    mode = _nonempty_string(data.get("mode"))
    expected_raw = _nonempty_string(data.get("expected_result"))
    expected_result = expected_raw.upper() if expected_raw else None
    events: list[dict[str, Any]] = []
    if expected_result and expected_result not in RESULT_VALUES:
        return _make_result(
            case_id=case_id,
            mode=mode,
            result=BLOCKED,
            reason=f"unknown expected_result: {expected_result}",
            source=source,
            expected_result=expected_result,
        )
    if mode not in {"generate", "roundtrip", "verify", "simulate_tamper"}:
        return _make_result(
            case_id=case_id,
            mode=mode,
            result=BLOCKED,
            reason="mode must be generate, roundtrip, verify, or simulate_tamper",
            source=source,
            expected_result=expected_result,
        )
    if data.get("contradictory_input") is True:
        return _make_result(
            case_id=case_id,
            mode=mode,
            result=BLOCKED,
            reason="critical fixture fields are explicitly contradictory",
            source=source,
            expected_result=expected_result,
        )
    genesis_policy = data.get("genesis_policy")
    if genesis_policy not in (None, "null"):
        return _make_result(
            case_id=case_id,
            mode=mode,
            result=BLOCKED,
            reason=f"unable to determine canonical genesis from policy: {genesis_policy!r}",
            source=source,
            expected_result=expected_result,
        )
    algorithm = _nonempty_string(data.get("hash_algorithm")) or HASH_ALGORITHM
    if algorithm != HASH_ALGORITHM:
        return _make_result(
            case_id=case_id,
            mode=mode,
            result=DENY,
            reason=f"unknown hash algorithm: {algorithm}",
            source=source,
            expected_result=expected_result,
        )
    raw_events = data.get("events")
    try:
        if mode == "verify":
            if not isinstance(raw_events, list):
                raise AuditBlocked("events must be an array")
            events = [dict(event) if isinstance(event, dict) else event for event in raw_events]
            failure = verify_chain(events)
            if failure:
                return _make_result(
                    case_id=case_id,
                    mode=mode,
                    result=DENY,
                    reason=failure.reason,
                    source=source,
                    expected_result=expected_result,
                    events=events,
                    failure=failure,
                )
        else:
            events = generate_chain(
                raw_events,
                auto_event_id=bool(data.get("auto_event_id", False)),
            )
            if data.get("treat_audit_as_authorization") is True:
                raise AuditDenied("audit record cannot be treated as operation authorization")
            if mode == "simulate_tamper":
                scenario = _nonempty_string(data.get("tamper"))
                if not scenario:
                    raise AuditBlocked("simulate_tamper requires a tamper scenario")
                events = _simulate_tamper(events, scenario)
                failure = verify_chain(events)
                if failure:
                    return _make_result(
                        case_id=case_id,
                        mode=mode,
                        result=DENY,
                        reason=failure.reason,
                        source=source,
                        expected_result=expected_result,
                        events=events,
                        failure=failure,
                    )
                raise AuditBlocked("tamper scenario did not produce detectable evidence")
            failure = verify_chain(events)
            if failure:
                raise AuditBlocked(f"generated chain failed self-verification: {failure.reason}")
            if mode == "roundtrip":
                parsed = [json.loads(line) for line in events_to_jsonl(events).splitlines()]
                failure = verify_chain(parsed)
                if failure:
                    raise AuditBlocked(f"JSONL roundtrip failed: {failure.reason}")
                events = parsed
    except AuditDenied as exc:
        return _make_result(
            case_id=case_id,
            mode=mode,
            result=DENY,
            reason=str(exc),
            source=source,
            expected_result=expected_result,
            events=events,
        )
    except AuditBlocked as exc:
        return _make_result(
            case_id=case_id,
            mode=mode,
            result=BLOCKED,
            reason=str(exc),
            source=source,
            expected_result=expected_result,
            events=events,
        )
    return _make_result(
        case_id=case_id,
        mode=mode,
        result=PASS,
        reason=(
            "Audit chain is canonical and internally consistent; audit evidence does not grant authorization."
        ),
        source=source,
        expected_result=expected_result,
        events=events,
    )


def _load_jsonl(path: Path) -> AuditResult:
    expected = _infer_expected_result(path)
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise AuditBlocked("JSONL chain is empty")
        for number, line in enumerate(lines, start=1):
            if not line.strip():
                raise AuditBlocked(f"JSONL line {number} is empty")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise AuditBlocked(f"JSONL line {number} must be an object")
            events.append(value)
    except (OSError, json.JSONDecodeError, AuditBlocked) as exc:
        return _make_result(
            case_id=path.stem,
            mode="verify",
            result=BLOCKED,
            reason=f"Unable to read JSONL: {exc}",
            source=str(path),
            expected_result=expected,
        )
    return evaluate_fixture(
        {
            "case_id": path.stem,
            "mode": "verify",
            "events": events,
            "expected_result": expected,
        },
        source=str(path),
    )


def load_fixture(path: Path) -> AuditResult:
    if path.suffix == ".jsonl":
        return _load_jsonl(path)
    inferred = _infer_expected_result(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _make_result(
            case_id=path.stem,
            mode=None,
            result=BLOCKED,
            reason=f"Unable to read fixture: {exc}",
            source=str(path),
            expected_result=inferred,
        )
    if not isinstance(data, dict):
        return _make_result(
            case_id=path.stem,
            mode=None,
            result=BLOCKED,
            reason="fixture root must be a JSON object",
            source=str(path),
            expected_result=inferred,
        )
    if "expected_result" not in data and inferred:
        data = dict(data)
        data["expected_result"] = inferred
    return evaluate_fixture(data, source=str(path))


def discover_paths(targets: Sequence[str]) -> tuple[list[Path], list[AuditResult]]:
    paths: set[Path] = set()
    errors: list[AuditResult] = []
    for target_text in targets:
        target = Path(target_text)
        if target.is_file():
            paths.add(target)
        elif target.is_dir():
            paths.update(
                path for path in target.rglob("*") if path.is_file() and path.suffix in {".json", ".jsonl"}
            )
        else:
            errors.append(
                _make_result(
                    case_id=target.name or "missing-target",
                    mode=None,
                    result=BLOCKED,
                    reason=f"fixture target does not exist: {target}",
                    source=str(target),
                    expected_result=None,
                )
            )
    return sorted(paths, key=lambda path: str(path)), errors


def render_text(results: Sequence[AuditResult]) -> str:
    lines: list[str] = []
    for item in results:
        lines.append(f"{item.result}: {item.case_id}")
        for field in (
            "mode",
            "schema_version",
            "event_count",
            "first_sequence",
            "last_sequence",
            "chain_valid",
            "tamper_detected",
            "allowed",
            "result",
            "reason",
            "source",
            "expected_result",
            "expectation_met",
            "failed_event_id",
            "failed_sequence",
            "expected_previous_hash",
            "observed_previous_hash",
            "expected_event_hash",
            "observed_event_hash",
        ):
            lines.append(f"  {field}: {getattr(item, field)!r}")
    counts = {value: sum(item.result == value for item in results) for value in RESULT_VALUES}
    mismatches = sum(not item.expectation_met for item in results)
    lines.append(
        "SUMMARY: "
        f"total={len(results)} pass={counts[PASS]} deny={counts[DENY]} "
        f"blocked={counts[BLOCKED]} expectation_mismatches={mismatches}"
    )
    return "\n".join(lines)


def render_json(results: Sequence[AuditResult]) -> str:
    return json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fixture-only ACOS audit JSONL writer.")
    parser.add_argument("fixtures", nargs="+", help="JSON/JSONL fixture files or directories.")
    parser.add_argument("--format", choices=("text", "json", "jsonl"), default="text")
    args = parser.parse_args(argv)
    paths, errors = discover_paths(args.fixtures)
    results = [load_fixture(path) for path in paths]
    results.extend(errors)
    if not results:
        parser.error("No JSON or JSONL fixtures found")
    if args.format == "jsonl":
        if len(results) != 1 or results[0].result != PASS or not results[0].events:
            print(render_text(results))
            return 1
        print(events_to_jsonl(results[0].events), end="")
    else:
        print(render_json(results) if args.format == "json" else render_text(results))
    return 1 if any(not item.expectation_met for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

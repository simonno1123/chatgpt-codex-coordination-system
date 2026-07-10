#!/usr/bin/env python3
"""Fixture-only ACOS runtime identity authority simulator.

The simulator reads static JSON fixtures and reports PASS, DENY, or BLOCKED.
It does not modify files, invoke Git, access the network, or call providers.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

PASS = "PASS"
DENY = "DENY"
BLOCKED = "BLOCKED"
RESULT_VALUES = frozenset({PASS, DENY, BLOCKED})

KNOWN_ARTIFACT_TYPES = frozenset(
    {
        "TASK",
        "RESULT",
        "BLOCKED RESULT",
        "ADVISORY REVIEW",
        "REVIEW",
        "DECISION",
        "RECORD",
        "GOVERNANCE PROPOSAL",
        "CONTEXT PACK",
    }
)


@dataclass(frozen=True)
class RuntimePolicy:
    producer_labels: frozenset[str]
    allowed_artifact_types: frozenset[str]


RUNTIME_POLICIES = {
    "ChatGPT Review Runtime": RuntimePolicy(
        producer_labels=frozenset({"ChatGPT", "ChatGPT Review"}),
        allowed_artifact_types=frozenset(
            {"TASK", "REVIEW", "DECISION", "GOVERNANCE PROPOSAL", "CONTEXT PACK"}
        ),
    ),
    "Codex Executor Runtime": RuntimePolicy(
        producer_labels=frozenset({"Codex Executor"}),
        allowed_artifact_types=frozenset({"RESULT", "BLOCKED RESULT"}),
    ),
    "External Advisory Runtime": RuntimePolicy(
        producer_labels=frozenset({"External Advisory Reviewer"}),
        allowed_artifact_types=frozenset({"ADVISORY REVIEW"}),
    ),
    "Automation Runtime": RuntimePolicy(
        producer_labels=frozenset({"Automation"}),
        allowed_artifact_types=frozenset({"RESULT", "RECORD"}),
    ),
}


@dataclass
class SimulationResult:
    case_id: str
    runtime_identity: str | None
    producer: str | None
    artifact_type: str | None
    allowed: bool
    result: str
    reason: str
    source: str
    expected_result: str | None = None
    expectation_met: bool | None = None


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _result(
    *,
    case_id: str,
    runtime_identity: str | None,
    producer: str | None,
    artifact_type: str | None,
    result: str,
    reason: str,
    source: str,
    expected_result: str | None,
) -> SimulationResult:
    expectation_met = result == expected_result if expected_result else result == PASS
    return SimulationResult(
        case_id=case_id,
        runtime_identity=runtime_identity,
        producer=producer,
        artifact_type=artifact_type,
        allowed=result == PASS,
        result=result,
        reason=reason,
        source=source,
        expected_result=expected_result,
        expectation_met=expectation_met,
    )


def evaluate_fixture(data: Mapping[str, Any], source: str = "<memory>") -> SimulationResult:
    """Evaluate one fixture without changing external state."""

    case_id = _nonempty_string(data.get("case_id")) or Path(source).stem or "unknown-case"
    runtime_identity = _nonempty_string(data.get("runtime_identity"))
    producer = _nonempty_string(data.get("producer"))
    artifact_type_raw = _nonempty_string(data.get("artifact_type"))
    artifact_type = artifact_type_raw.upper() if artifact_type_raw else None
    expected_raw = _nonempty_string(data.get("expected_result"))
    expected_result = expected_raw.upper() if expected_raw else None

    if expected_result and expected_result not in RESULT_VALUES:
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            artifact_type=artifact_type,
            result=BLOCKED,
            reason=f"Unknown expected_result: {expected_result}",
            source=source,
            expected_result=expected_result,
        )

    missing = [
        name
        for name, value in (
            ("runtime_identity", runtime_identity),
            ("producer", producer),
            ("artifact_type", artifact_type),
        )
        if value is None
    ]
    if missing:
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            artifact_type=artifact_type,
            result=BLOCKED,
            reason="Missing required fixture fields: " + ", ".join(missing),
            source=source,
            expected_result=expected_result,
        )

    policy = RUNTIME_POLICIES.get(runtime_identity)
    if policy is None:
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            artifact_type=artifact_type,
            result=BLOCKED,
            reason=f"Unknown runtime identity: {runtime_identity}",
            source=source,
            expected_result=expected_result,
        )

    if artifact_type not in KNOWN_ARTIFACT_TYPES:
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            artifact_type=artifact_type,
            result=BLOCKED,
            reason=f"Unknown artifact type: {artifact_type}",
            source=source,
            expected_result=expected_result,
        )

    if producer not in policy.producer_labels:
        expected_labels = ", ".join(sorted(policy.producer_labels))
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            artifact_type=artifact_type,
            result=DENY,
            reason=(
                f"Producer {producer} does not match {runtime_identity}; "
                f"expected one of: {expected_labels}"
            ),
            source=source,
            expected_result=expected_result,
        )

    if artifact_type not in policy.allowed_artifact_types:
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            artifact_type=artifact_type,
            result=DENY,
            reason=f"{runtime_identity} may not create {artifact_type}",
            source=source,
            expected_result=expected_result,
        )

    return _result(
        case_id=case_id,
        runtime_identity=runtime_identity,
        producer=producer,
        artifact_type=artifact_type,
        result=PASS,
        reason=f"{runtime_identity} may create {artifact_type}",
        source=source,
        expected_result=expected_result,
    )


def load_fixture(path: Path) -> SimulationResult:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result(
            case_id=path.stem,
            runtime_identity=None,
            producer=None,
            artifact_type=None,
            result=BLOCKED,
            reason=f"Unable to read fixture: {exc}",
            source=str(path),
            expected_result=None,
        )

    if not isinstance(data, dict):
        return _result(
            case_id=path.stem,
            runtime_identity=None,
            producer=None,
            artifact_type=None,
            result=BLOCKED,
            reason="Fixture root must be a JSON object",
            source=str(path),
            expected_result=None,
        )

    return evaluate_fixture(data, source=str(path))


def discover_fixture_paths(targets: Sequence[str]) -> tuple[list[Path], list[SimulationResult]]:
    paths: set[Path] = set()
    errors: list[SimulationResult] = []

    for target_text in targets:
        target = Path(target_text)
        if target.is_file():
            paths.add(target)
        elif target.is_dir():
            paths.update(path for path in target.rglob("*.json") if path.is_file())
        else:
            errors.append(
                _result(
                    case_id=target.name or "missing-target",
                    runtime_identity=None,
                    producer=None,
                    artifact_type=None,
                    result=BLOCKED,
                    reason=f"Fixture target does not exist: {target}",
                    source=str(target),
                    expected_result=None,
                )
            )

    return sorted(paths, key=lambda path: str(path)), errors


def render_text(results: Sequence[SimulationResult]) -> str:
    lines: list[str] = []
    for item in results:
        lines.extend(
            [
                f"{item.result}: {item.case_id}",
                f"  runtime_identity: {item.runtime_identity or '<missing>'}",
                f"  producer: {item.producer or '<missing>'}",
                f"  artifact_type: {item.artifact_type or '<missing>'}",
                f"  allowed: {str(item.allowed).lower()}",
                f"  result: {item.result}",
                f"  reason: {item.reason}",
                f"  source: {item.source}",
            ]
        )
        if item.expected_result:
            lines.append(f"  expected_result: {item.expected_result}")
        lines.append(f"  expectation_met: {str(bool(item.expectation_met)).lower()}")

    counts = {value: sum(item.result == value for item in results) for value in RESULT_VALUES}
    mismatches = sum(not item.expectation_met for item in results)
    lines.append(
        "SUMMARY: "
        f"total={len(results)} pass={counts[PASS]} deny={counts[DENY]} "
        f"blocked={counts[BLOCKED]} expectation_mismatches={mismatches}"
    )
    return "\n".join(lines)


def render_json(results: Sequence[SimulationResult]) -> str:
    return json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run ACOS runtime identity and artifact authority fixtures."
    )
    parser.add_argument("fixtures", nargs="+", help="JSON fixture files or directories.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    paths, errors = discover_fixture_paths(args.fixtures)
    results = [load_fixture(path) for path in paths]
    results.extend(errors)

    if not results:
        parser.error("No JSON fixtures found")

    print(render_json(results) if args.format == "json" else render_text(results))
    return 1 if any(not item.expectation_met for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

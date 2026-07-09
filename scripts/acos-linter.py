#!/usr/bin/env python3
"""Deterministic ACOS artifact linter.

This tool validates ACOS artifact metadata, producer authority, and a small
set of path-protection rules. It does not use AI or external services.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterable

REQUIRED_METADATA = [
    "ARTIFACT TYPE",
    "PRODUCER",
    "TO",
    "NEXT RECEIVER",
    "MODE",
    "PROJECT",
    "AUTHORITY LIMIT",
    "FORBIDDEN",
    "OUTPUT",
]

ROLE_ARTIFACT_ALLOWLIST = {
    "ChatGPT": {"TASK", "REVIEW", "DECISION", "CONTEXT PACK", "GOVERNANCE PROPOSAL"},
    "ChatGPT Review": {"TASK", "REVIEW", "DECISION", "GOVERNANCE PROPOSAL"},
    "Codex Executor": {"RESULT", "BLOCKED RESULT"},
    "External Advisory Reviewer": {"ADVISORY REVIEW"},
    "Automation": {"RESULT", "RECORD"},
}

KNOWN_RECEIVERS = {
    "ChatGPT",
    "ChatGPT Review",
    "Codex Executor",
    "External Advisory Reviewer",
    "User Decision",
    "Automation",
    "Relevant Receiver",
    "None",
}

PATH_PATTERN = re.compile(r"(?:^|[`\s'\"(])((?:\.?/?[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+)(?=$|[`\s'\"),:;])")


@dataclass
class Finding:
    code: str
    message: str


@dataclass
class LintResult:
    path: str
    status: str = "PASSED"
    metadata: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)

    def add(self, code: str, message: str) -> None:
        self.status = "FAILED"
        self.findings.append(Finding(code, message))


def strip_fenced_code(text: str) -> list[str]:
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return lines


def parse_metadata(text: str) -> dict[str, str]:
    lines = strip_fenced_code(text)
    metadata: dict[str, str] = {}
    wanted = {field + ":": field for field in REQUIRED_METADATA}

    index = 0
    while index < len(lines):
        key = wanted.get(lines[index].strip().upper())
        if key and key not in metadata:
            value = ""
            lookahead = index + 1
            while lookahead < len(lines):
                candidate = lines[lookahead].strip()
                if candidate:
                    value = candidate
                    break
                lookahead += 1
            metadata[key] = value
            index = lookahead
        index += 1

    return metadata


def split_values(value: str) -> set[str]:
    cleaned = value.strip()
    if not cleaned:
        return set()
    cleaned = cleaned.strip("[]")
    parts = re.split(r"\s*/\s*|\s*,\s*", cleaned)
    return {part.strip() for part in parts if part.strip()}


def is_placeholder(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("[") and stripped.endswith("]")


def normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip().strip("`'\"")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return str(PurePosixPath(normalized))


def extract_paths(text: str) -> set[str]:
    paths: set[str] = set()
    for match in PATH_PATTERN.finditer(text):
        candidate = normalize_path(match.group(1))
        if "/" in candidate and not candidate.startswith("http"):
            paths.add(candidate)
    return paths


def validate_metadata(result: LintResult) -> None:
    missing = [field for field in REQUIRED_METADATA if not result.metadata.get(field)]
    if missing:
        result.add("BLOCKED: MISSING METADATA", "Missing required metadata: " + ", ".join(missing))


def validate_role_authority(result: LintResult) -> None:
    producer = result.metadata.get("PRODUCER", "").strip()
    artifact_type_raw = result.metadata.get("ARTIFACT TYPE", "").strip()
    if not producer or not artifact_type_raw:
        return

    if is_placeholder(producer) or is_placeholder(artifact_type_raw):
        return

    artifact_types = split_values(artifact_type_raw)
    allowed = ROLE_ARTIFACT_ALLOWLIST.get(producer)
    if allowed is None:
        result.add("ROLE AUTHORITY VIOLATION", f"Unknown producer: {producer}")
        return

    disallowed = sorted(artifact_types - allowed)
    if disallowed:
        result.add(
            "ROLE AUTHORITY VIOLATION",
            f"Producer {producer} may not produce: {', '.join(disallowed)}",
        )


def validate_receivers(result: LintResult) -> None:
    for field_name in ("TO", "NEXT RECEIVER"):
        value = result.metadata.get(field_name, "").strip()
        if not value or is_placeholder(value):
            continue
        receivers = split_values(value)
        unknown = sorted(receiver for receiver in receivers if receiver not in KNOWN_RECEIVERS)
        if unknown:
            result.add(
                "ROUTING VIOLATION",
                f"{field_name} contains unknown receiver: {', '.join(unknown)}",
            )


def validate_path_protection(result: LintResult, paths: Iterable[str]) -> None:
    producer = result.metadata.get("PRODUCER", "").strip()
    normalized_paths = {normalize_path(path) for path in paths}

    if producer == "Codex Executor":
        protected = sorted(
            path for path in normalized_paths
            if path.startswith(".codex-coordination/decisions/")
            or path.startswith("codex-coordination/decisions/")
        )
        if protected:
            result.add(
                "PATH PROTECTION VIOLATION",
                "Codex Executor must not modify decisions/: " + ", ".join(protected),
            )

    if producer == "External Advisory Reviewer":
        protected = sorted(
            path for path in normalized_paths
            if path.startswith(".codex-coordination/tasks/")
            or path.startswith("codex-coordination/tasks/")
            or path.startswith(".codex-coordination/inbox/")
            or path.startswith("codex-coordination/inbox/")
        )
        if protected:
            result.add(
                "PATH PROTECTION VIOLATION",
                "External Advisory Reviewer must not modify task inputs: " + ", ".join(protected),
            )


def lint_file(path: str, changed_paths: Iterable[str]) -> LintResult:
    result = LintResult(path=path)
    try:
        text = open(path, "r", encoding="utf-8").read()
    except OSError as exc:
        result.add("READ ERROR", str(exc))
        return result

    result.metadata = parse_metadata(text)
    validate_metadata(result)
    validate_role_authority(result)
    validate_receivers(result)

    discovered_paths = extract_paths(text)
    validate_path_protection(result, set(changed_paths) | discovered_paths)
    return result


def render_text(results: list[LintResult]) -> str:
    output: list[str] = []
    for result in results:
        output.append(f"{result.status}: {result.path}")
        if result.metadata:
            output.append("  Metadata:")
            for field_name in REQUIRED_METADATA:
                output.append(f"    {field_name}: {result.metadata.get(field_name, '<missing>')}")
        for finding in result.findings:
            output.append(f"  - {finding.code}: {finding.message}")
    return "\n".join(output)


def render_json(results: list[LintResult]) -> str:
    return json.dumps(
        [
            {
                "path": result.path,
                "status": result.status,
                "metadata": result.metadata,
                "findings": [finding.__dict__ for finding in result.findings],
            }
            for result in results
        ],
        ensure_ascii=False,
        indent=2,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint ACOS artifact metadata and authority boundaries.")
    parser.add_argument("artifacts", nargs="+", help="Artifact markdown files to lint.")
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="Path changed by the artifact. May be provided multiple times.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    results = [lint_file(path, args.changed_path) for path in args.artifacts]
    print(render_json(results) if args.format == "json" else render_text(results))
    return 1 if any(result.status == "FAILED" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

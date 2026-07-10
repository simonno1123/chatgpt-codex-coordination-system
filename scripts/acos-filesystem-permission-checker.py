#!/usr/bin/env python3
"""Fixture-only ACOS filesystem permission checker.

The checker performs lexical path analysis against static JSON fixtures. It
never reads a target path, follows a symlink, changes permissions, modifies Git,
or grants a live capability.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

PASS = "PASS"
DENY = "DENY"
BLOCKED = "BLOCKED"
RESULT_VALUES = frozenset({PASS, DENY, BLOCKED})

KNOWN_OPERATIONS = frozenset(
    {"inspect", "read", "create", "edit", "delete", "stage", "commit", "push", "release"}
)
READ_OPERATIONS = frozenset({"inspect", "read"})
WRITE_OPERATIONS = frozenset({"create", "edit", "delete"})
GIT_RELEASE_OPERATIONS = frozenset({"stage", "commit", "push", "release"})

ACOS_CORE = "ACOS CORE"
BUSINESS_PROJECT = "BUSINESS PROJECT"
KNOWN_REPOSITORY_SCOPES = frozenset({ACOS_CORE, BUSINESS_PROJECT})
VIRTUAL_REPOSITORY_ROOTS = {
    ACOS_CORE: PurePosixPath("/acos-core"),
    BUSINESS_PROJECT: PurePosixPath("/project-instance"),
}

ACOS_CORE_GOVERNANCE = "ACOS CORE GOVERNANCE"
ACOS_CORE_DOCUMENTATION = "ACOS CORE DOCUMENTATION"
ACOS_EXECUTABLE_TOOLING = "ACOS EXECUTABLE TOOLING"
TEST_ASSETS = "TEST ASSETS"
FIXTURE_ASSETS = "FIXTURE ASSETS"
GIT_HOOKS = "GIT HOOKS"
ROOT_GOVERNANCE_FILES = "ROOT GOVERNANCE FILES"
GIT_INTERNAL = "GIT INTERNAL"
INSTANCE_LOCAL_COORDINATION = "INSTANCE-LOCAL COORDINATION"
BUSINESS_PROJECT_CLASS = "BUSINESS PROJECT"
REPOSITORY_ROOT = "REPOSITORY ROOT"
UNKNOWN_PATH_CLASS = "UNKNOWN / UNCLASSIFIED"

KNOWN_PATH_CLASSES = frozenset(
    {
        ACOS_CORE_GOVERNANCE,
        ACOS_CORE_DOCUMENTATION,
        ACOS_EXECUTABLE_TOOLING,
        TEST_ASSETS,
        FIXTURE_ASSETS,
        GIT_HOOKS,
        ROOT_GOVERNANCE_FILES,
        GIT_INTERNAL,
        INSTANCE_LOCAL_COORDINATION,
        BUSINESS_PROJECT_CLASS,
        REPOSITORY_ROOT,
        UNKNOWN_PATH_CLASS,
    }
)

ROOT_GOVERNANCE_BASENAMES = frozenset(
    {"CODEX_WORKFLOW.md", "SCOPE_POLICY.md", "README.md", "PROJECT_BRIEF.md", "TASKS.md"}
)
CORE_GOVERNANCE_PREFIXES = frozenset(
    {"governance", "roles", "routing", "agents", "skills", "templates", ".codex-coordination"}
)

RUNTIME_PRODUCERS = {
    "ChatGPT Review Runtime": frozenset({"ChatGPT", "ChatGPT Review"}),
    "Codex Executor Runtime": frozenset({"Codex Executor"}),
    "External Advisory Runtime": frozenset({"External Advisory Reviewer"}),
    "Automation Runtime": frozenset({"Automation"}),
}


@dataclass(frozen=True)
class PathAnalysis:
    normalized_path: str
    path_class: str
    traversal_detected: bool = False
    cross_repository_scope: str | None = None


@dataclass
class CheckResult:
    case_id: str
    runtime_identity: str | None
    producer: str | None
    operation: str | None
    target_path: object
    normalized_path: str | None
    repository_scope: str | None
    path_class: str | None
    allowed: bool
    result: str
    reason: str
    source: str
    expected_result: str | None = None
    expectation_met: bool | None = None


class FixtureBlocked(ValueError):
    """Raised when fixture input cannot be classified safely."""


def _nonempty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _infer_expected_result(path: Path) -> str | None:
    name = path.name.lower()
    if name.startswith("valid-"):
        return PASS
    if name.startswith("invalid-"):
        return DENY
    if name.startswith("blocked-"):
        return BLOCKED
    return None


def _expectation_met(
    *,
    result: str,
    allowed: bool,
    path_class: str | None,
    expected_result: str | None,
    expected_allowed: bool | None,
    expected_path_class: str | None,
) -> bool:
    checks = [result == expected_result] if expected_result else [result == PASS]
    if expected_allowed is not None:
        checks.append(allowed == expected_allowed)
    if expected_path_class is not None:
        checks.append(path_class == expected_path_class)
    return all(checks)


def _result(
    *,
    case_id: str,
    runtime_identity: str | None,
    producer: str | None,
    operation: str | None,
    target_path: object,
    normalized_path: str | None,
    repository_scope: str | None,
    path_class: str | None,
    result: str,
    reason: str,
    source: str,
    expected_result: str | None,
    expected_allowed: bool | None = None,
    expected_path_class: str | None = None,
) -> CheckResult:
    allowed = result == PASS
    return CheckResult(
        case_id=case_id,
        runtime_identity=runtime_identity,
        producer=producer,
        operation=operation,
        target_path=target_path,
        normalized_path=normalized_path,
        repository_scope=repository_scope,
        path_class=path_class,
        allowed=allowed,
        result=result,
        reason=reason,
        source=source,
        expected_result=expected_result,
        expectation_met=_expectation_met(
            result=result,
            allowed=allowed,
            path_class=path_class,
            expected_result=expected_result,
            expected_allowed=expected_allowed,
            expected_path_class=expected_path_class,
        ),
    )


def _classify_path(normalized_path: str, repository_scope: str) -> str:
    if normalized_path == ".":
        return REPOSITORY_ROOT

    parts = PurePosixPath(normalized_path).parts
    first = parts[0]

    if first == ".git":
        return GIT_INTERNAL
    if repository_scope == BUSINESS_PROJECT:
        if first == ".codex-coordination":
            return INSTANCE_LOCAL_COORDINATION
        return BUSINESS_PROJECT_CLASS
    if first in CORE_GOVERNANCE_PREFIXES:
        return ACOS_CORE_GOVERNANCE
    if first == "docs":
        return ACOS_CORE_DOCUMENTATION
    if first == "scripts":
        return ACOS_EXECUTABLE_TOOLING
    if first == "tests":
        return TEST_ASSETS
    if first == "fixtures":
        return FIXTURE_ASSETS
    if first == ".githooks":
        return GIT_HOOKS
    if len(parts) == 1 and first in ROOT_GOVERNANCE_BASENAMES:
        return ROOT_GOVERNANCE_FILES
    return UNKNOWN_PATH_CLASS


def _relative_to_virtual_root(path: PurePosixPath, root: PurePosixPath) -> PurePosixPath | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def analyze_path(target_path: object, repository_scope: str) -> PathAnalysis:
    if not isinstance(target_path, str):
        raise FixtureBlocked("target_path must be a string")
    if not target_path.strip():
        raise FixtureBlocked("target_path must not be empty")
    if "\x00" in target_path:
        raise FixtureBlocked("target_path contains NUL")
    if "\\" in target_path:
        raise FixtureBlocked("target_path uses an ambiguous non-POSIX separator")

    raw = target_path.strip()
    path = PurePosixPath(raw)
    cross_scope: str | None = None

    if path.is_absolute():
        relative: PurePosixPath | None = None
        actual_scope: str | None = None
        for scope, root in VIRTUAL_REPOSITORY_ROOTS.items():
            candidate = _relative_to_virtual_root(path, root)
            if candidate is not None:
                relative = candidate
                actual_scope = scope
                break
        if relative is None or actual_scope is None:
            raise FixtureBlocked("absolute target_path is outside known fixture repository roots")
        if actual_scope != repository_scope:
            cross_scope = actual_scope
        raw_parts = relative.parts
    else:
        raw_parts = tuple(part for part in raw.split("/") if part != "")

    stack: list[str] = []
    traversal_detected = False
    for part in raw_parts:
        if part in ("", "."):
            continue
        if part == "..":
            traversal_detected = True
            if not stack:
                raise FixtureBlocked("path normalization escapes the declared repository root")
            stack.pop()
            continue
        stack.append(part)

    normalized = "/".join(stack) if stack else "."
    classification_scope = cross_scope or repository_scope
    return PathAnalysis(
        normalized_path=normalized,
        path_class=_classify_path(normalized, classification_scope),
        traversal_detected=traversal_detected,
        cross_repository_scope=cross_scope,
    )


def _normalize_capability_paths(value: object, field_name: str) -> list[tuple[str, bool]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise FixtureBlocked(f"{field_name} must be a list of relative paths")

    normalized: list[tuple[str, bool]] = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise FixtureBlocked(f"{field_name} entries must be non-empty strings")
        raw = entry.strip()
        if raw.startswith("/") or "\x00" in raw or "\\" in raw:
            raise FixtureBlocked(f"{field_name} entries must be safe relative POSIX paths")
        directory_grant = raw.endswith("/")
        parts: list[str] = []
        for part in raw.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                raise FixtureBlocked(f"{field_name} entries must not contain '..'")
            parts.append(part)
        if not parts:
            raise FixtureBlocked(f"{field_name} must not authorize the repository root")
        normalized.append(("/".join(parts), directory_grant))
    return normalized


def _path_is_granted(target: str, grants: Sequence[tuple[str, bool]]) -> bool:
    return any(
        target == grant or (directory_grant and target.startswith(grant + "/"))
        for grant, directory_grant in grants
    )


def _bool_field(data: Mapping[str, Any], name: str, default: bool = False) -> bool:
    value = data.get(name, default)
    if not isinstance(value, bool):
        raise FixtureBlocked(f"{name} must be a boolean")
    return value


def _core_coordination_path(path: str, area: str) -> bool:
    prefix = f".codex-coordination/{area}"
    return path == prefix or path.startswith(prefix + "/")


def _path_level_pass(reason: str, operation: str) -> tuple[str, str]:
    suffix = "Path-level dry-run only; operation authorization not granted."
    if operation in GIT_RELEASE_OPERATIONS:
        suffix = (
            "Path-level dry-run only; separate Git or release authorization is required "
            "and is not granted."
        )
    return PASS, f"{reason} {suffix}"


def _evaluate_chatgpt(
    operation: str,
    analysis: PathAnalysis,
    artifact_type: str | None,
    governance_authorized: bool,
) -> tuple[str, str]:
    if analysis.path_class == BUSINESS_PROJECT_CLASS:
        return DENY, "ChatGPT Review Runtime has no direct business-project filesystem access."
    if analysis.path_class == GIT_INTERNAL:
        return DENY, "Direct .git access is outside ChatGPT Review Runtime authority."
    if operation in READ_OPERATIONS:
        return _path_level_pass("Governance-context read is permitted.", operation)
    if operation in GIT_RELEASE_OPERATIONS or operation == "delete":
        return DENY, "ChatGPT Review Runtime cannot perform Git, release, or delete operations."

    role_owned = (
        (_core_coordination_path(analysis.normalized_path, "inbox") and artifact_type == "TASK")
        or (_core_coordination_path(analysis.normalized_path, "reviews") and artifact_type == "REVIEW")
        or (
            _core_coordination_path(analysis.normalized_path, "decisions")
            and artifact_type == "DECISION"
        )
    )
    if governance_authorized and role_owned:
        return _path_level_pass("Role-owned governance artifact path is permitted.", operation)
    return DENY, "ChatGPT Review Runtime cannot directly edit this path."


def _codex_scope_allowed(
    analysis: PathAnalysis,
    grants: Sequence[tuple[str, bool]],
    governance_authorized: bool,
    business_task_authorized: bool,
    local_mode_enabled: bool,
) -> tuple[bool, str]:
    path = analysis.normalized_path
    if analysis.path_class == GIT_INTERNAL:
        return False, "Codex Executor must not access .git as a filesystem target."
    if _core_coordination_path(path, "decisions"):
        return False, "Codex Executor must not write ACOS decisions."
    if not _path_is_granted(path, grants):
        return False, "Target path is outside task_allowed_paths."
    if analysis.path_class == BUSINESS_PROJECT_CLASS and not business_task_authorized:
        return False, "Business-project write lacks a bounded business task authorization."
    if analysis.path_class == INSTANCE_LOCAL_COORDINATION and not local_mode_enabled:
        return False, "Instance-local coordination write requires explicit local ACOS instance mode."
    if analysis.path_class not in {BUSINESS_PROJECT_CLASS, INSTANCE_LOCAL_COORDINATION}:
        if not governance_authorized:
            return False, "ACOS core write lacks governance authorization."
    return True, "Target path is within the declared task capability."


def _evaluate_codex(
    operation: str,
    analysis: PathAnalysis,
    grants: Sequence[tuple[str, bool]],
    governance_authorized: bool,
    business_task_authorized: bool,
    local_mode_enabled: bool,
    delete_authorized: bool,
) -> tuple[str, str]:
    if analysis.path_class == GIT_INTERNAL:
        return DENY, "Codex Executor must not modify or target .git internals."
    if operation in READ_OPERATIONS:
        if analysis.path_class in {BUSINESS_PROJECT_CLASS, INSTANCE_LOCAL_COORDINATION}:
            if not _path_is_granted(analysis.normalized_path, grants):
                return DENY, "Instance or business-project read is outside task_allowed_paths."
        return _path_level_pass("Codex read/inspect path is permitted.", operation)

    allowed, reason = _codex_scope_allowed(
        analysis,
        grants,
        governance_authorized,
        business_task_authorized,
        local_mode_enabled,
    )
    if not allowed:
        return DENY, reason
    if operation == "delete" and not delete_authorized:
        return DENY, "Delete requires a separate explicit capability."
    return _path_level_pass(reason, operation)


def _evaluate_advisory(operation: str, analysis: PathAnalysis) -> tuple[str, str]:
    if operation not in READ_OPERATIONS:
        return DENY, "External Advisory Runtime is read-only and cannot perform write or Git operations."
    if analysis.path_class in {GIT_INTERNAL, GIT_HOOKS, INSTANCE_LOCAL_COORDINATION}:
        return DENY, "External Advisory Runtime has no default access to this protected path class."
    return _path_level_pass("Read-only advisory inspection is permitted.", operation)


def _evaluate_automation(
    operation: str,
    analysis: PathAnalysis,
    artifact_type: str | None,
    grants: Sequence[tuple[str, bool]],
) -> tuple[str, str]:
    if operation in READ_OPERATIONS:
        if _path_is_granted(analysis.normalized_path, grants):
            return _path_level_pass("Policy-scoped automation read is permitted.", operation)
        return DENY, "Automation read is outside automation_allowed_paths."
    if operation != "create":
        return DENY, "Automation Runtime cannot edit, delete, stage, commit, push, or release."
    if artifact_type not in {"RESULT", "RECORD"}:
        return DENY, "Automation may create only RESULT or RECORD output."
    if not _core_coordination_path(analysis.normalized_path, "outbox"):
        return DENY, "Automation output must use its authorized coordination output path."
    if not _path_is_granted(analysis.normalized_path, grants):
        return DENY, "Automation output is outside automation_allowed_paths."
    return _path_level_pass("Authorized append-style automation output is permitted.", operation)


def evaluate_fixture(data: Mapping[str, Any], source: str = "<memory>") -> CheckResult:
    case_id = _nonempty_string(data.get("case_id")) or Path(source).stem or "unknown-case"
    runtime_identity = _nonempty_string(data.get("runtime_identity"))
    producer = _nonempty_string(data.get("producer"))
    operation_raw = _nonempty_string(data.get("operation"))
    operation = operation_raw.lower() if operation_raw else None
    target_path = data.get("target_path")
    scope_raw = _nonempty_string(data.get("repository_scope"))
    repository_scope = scope_raw.upper() if scope_raw else None
    expected_raw = _nonempty_string(data.get("expected_result"))
    expected_result = expected_raw.upper() if expected_raw else None
    declared_class_raw = _nonempty_string(data.get("path_class"))
    declared_class = declared_class_raw.upper() if declared_class_raw else None
    expected_class_raw = _nonempty_string(data.get("expected_path_class"))
    expected_path_class = expected_class_raw.upper() if expected_class_raw else None
    expected_allowed_raw = data.get("expected_allowed")
    expected_allowed = expected_allowed_raw if isinstance(expected_allowed_raw, bool) else None
    normalized_path: str | None = None
    actual_path_class: str | None = None

    def blocked(reason: str) -> CheckResult:
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            operation=operation,
            target_path=target_path,
            normalized_path=normalized_path,
            repository_scope=repository_scope,
            path_class=actual_path_class,
            result=BLOCKED,
            reason=reason,
            source=source,
            expected_result=expected_result,
            expected_allowed=expected_allowed,
            expected_path_class=expected_path_class,
        )

    if expected_result and expected_result not in RESULT_VALUES:
        return blocked(f"Unknown expected_result: {expected_result}")
    if expected_allowed_raw is not None and not isinstance(expected_allowed_raw, bool):
        return blocked("expected_allowed must be a boolean")
    if expected_path_class and expected_path_class not in KNOWN_PATH_CLASSES:
        return blocked(f"Unknown expected_path_class: {expected_path_class}")

    missing = [
        name
        for name, value in (
            ("runtime_identity", runtime_identity),
            ("producer", producer),
            ("operation", operation),
            ("target_path", target_path if target_path is not None else None),
            ("repository_scope", repository_scope),
        )
        if value is None
    ]
    if missing:
        return blocked("Missing required fixture fields: " + ", ".join(missing))
    if runtime_identity not in RUNTIME_PRODUCERS:
        return blocked(f"Unknown runtime identity: {runtime_identity}")
    if operation not in KNOWN_OPERATIONS:
        return blocked(f"Unknown operation: {operation}")
    if repository_scope not in KNOWN_REPOSITORY_SCOPES:
        return blocked(f"Unknown repository_scope: {repository_scope}")
    if producer not in RUNTIME_PRODUCERS[runtime_identity]:
        expected = ", ".join(sorted(RUNTIME_PRODUCERS[runtime_identity]))
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            operation=operation,
            target_path=target_path,
            normalized_path=None,
            repository_scope=repository_scope,
            path_class=None,
            result=DENY,
            reason=f"Producer does not match runtime identity; expected one of: {expected}",
            source=source,
            expected_result=expected_result,
            expected_allowed=expected_allowed,
            expected_path_class=expected_path_class,
        )

    try:
        analysis = analyze_path(target_path, repository_scope)
        normalized_path = analysis.normalized_path
        actual_path_class = analysis.path_class
        task_grants = _normalize_capability_paths(data.get("task_allowed_paths"), "task_allowed_paths")
        automation_grants = _normalize_capability_paths(
            data.get("automation_allowed_paths"), "automation_allowed_paths"
        )
        governance_authorized = _bool_field(data, "governance_authorized")
        business_task_authorized = _bool_field(data, "business_task_authorized")
        local_mode_enabled = _bool_field(data, "local_mode_enabled")
        delete_authorized = _bool_field(data, "delete_authorized")
    except FixtureBlocked as exc:
        return blocked(str(exc))

    if actual_path_class == UNKNOWN_PATH_CLASS:
        return blocked("target_path cannot be classified under the declared repository scope")
    if declared_class and declared_class not in KNOWN_PATH_CLASSES:
        return blocked(f"Unknown declared path_class: {declared_class}")
    if declared_class and declared_class != actual_path_class:
        return blocked(
            f"Declared path_class {declared_class} conflicts with classified path {actual_path_class}"
        )
    if analysis.cross_repository_scope:
        result, reason = (
            DENY,
            f"Absolute target escapes {repository_scope} into {analysis.cross_repository_scope}.",
        )
    elif analysis.traversal_detected:
        result, reason = DENY, "Explicit '..' traversal is forbidden even when normalization stays in-root."
    elif actual_path_class == REPOSITORY_ROOT and operation not in READ_OPERATIONS:
        result, reason = DENY, "Blanket repository-root write or Git authority is forbidden."
    else:
        artifact_raw = _nonempty_string(data.get("artifact_type"))
        if data.get("artifact_type") is not None and artifact_raw is None:
            return blocked("artifact_type must be a non-empty string when provided")
        artifact_type = artifact_raw.upper() if artifact_raw else None
        if runtime_identity == "ChatGPT Review Runtime":
            result, reason = _evaluate_chatgpt(
                operation, analysis, artifact_type, governance_authorized
            )
        elif runtime_identity == "Codex Executor Runtime":
            result, reason = _evaluate_codex(
                operation,
                analysis,
                task_grants,
                governance_authorized,
                business_task_authorized,
                local_mode_enabled,
                delete_authorized,
            )
        elif runtime_identity == "External Advisory Runtime":
            result, reason = _evaluate_advisory(operation, analysis)
        else:
            result, reason = _evaluate_automation(
                operation, analysis, artifact_type, automation_grants
            )

    return _result(
        case_id=case_id,
        runtime_identity=runtime_identity,
        producer=producer,
        operation=operation,
        target_path=target_path,
        normalized_path=normalized_path,
        repository_scope=repository_scope,
        path_class=actual_path_class,
        result=result,
        reason=reason,
        source=source,
        expected_result=expected_result,
        expected_allowed=expected_allowed,
        expected_path_class=expected_path_class,
    )


def load_fixture(path: Path) -> CheckResult:
    inferred_expected = _infer_expected_result(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result(
            case_id=path.stem,
            runtime_identity=None,
            producer=None,
            operation=None,
            target_path=None,
            normalized_path=None,
            repository_scope=None,
            path_class=None,
            result=BLOCKED,
            reason=f"Unable to read fixture: {exc}",
            source=str(path),
            expected_result=inferred_expected,
        )
    if not isinstance(data, dict):
        return _result(
            case_id=path.stem,
            runtime_identity=None,
            producer=None,
            operation=None,
            target_path=None,
            normalized_path=None,
            repository_scope=None,
            path_class=None,
            result=BLOCKED,
            reason="Fixture root must be a JSON object",
            source=str(path),
            expected_result=inferred_expected,
        )
    if "expected_result" not in data and inferred_expected:
        data = dict(data)
        data["expected_result"] = inferred_expected
    return evaluate_fixture(data, source=str(path))


def discover_fixture_paths(targets: Sequence[str]) -> tuple[list[Path], list[CheckResult]]:
    paths: set[Path] = set()
    errors: list[CheckResult] = []
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
                    operation=None,
                    target_path=str(target),
                    normalized_path=None,
                    repository_scope=None,
                    path_class=None,
                    result=BLOCKED,
                    reason=f"Fixture target does not exist: {target}",
                    source=str(target),
                    expected_result=None,
                )
            )
    return sorted(paths, key=lambda path: str(path)), errors


def render_text(results: Sequence[CheckResult]) -> str:
    lines: list[str] = []
    for item in results:
        lines.extend(
            [
                f"{item.result}: {item.case_id}",
                f"  runtime_identity: {item.runtime_identity or '<missing>'}",
                f"  producer: {item.producer or '<missing>'}",
                f"  operation: {item.operation or '<missing>'}",
                f"  target_path: {item.target_path!r}",
                f"  normalized_path: {item.normalized_path or '<unavailable>'}",
                f"  repository_scope: {item.repository_scope or '<missing>'}",
                f"  path_class: {item.path_class or '<unavailable>'}",
                f"  allowed: {str(item.allowed).lower()}",
                f"  result: {item.result}",
                f"  reason: {item.reason}",
                f"  source: {item.source}",
                f"  expected_result: {item.expected_result or '<unspecified>'}",
                f"  expectation_met: {str(bool(item.expectation_met)).lower()}",
            ]
        )
    counts = {value: sum(item.result == value for item in results) for value in RESULT_VALUES}
    mismatches = sum(not item.expectation_met for item in results)
    lines.append(
        "SUMMARY: "
        f"total={len(results)} pass={counts[PASS]} deny={counts[DENY]} "
        f"blocked={counts[BLOCKED]} expectation_mismatches={mismatches}"
    )
    return "\n".join(lines)


def render_json(results: Sequence[CheckResult]) -> str:
    return json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run ACOS filesystem path permission fixtures."
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

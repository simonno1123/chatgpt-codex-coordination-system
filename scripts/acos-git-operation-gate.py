#!/usr/bin/env python3
"""Fixture-only ACOS Git operation gate.

This module evaluates declared repository state, authorization, and command
strings without invoking Git, a shell, subprocesses, the network, or providers.
"""

from __future__ import annotations

import argparse
import json
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

PASS = "PASS"
DENY = "DENY"
BLOCKED = "BLOCKED"
RESULT_VALUES = frozenset({PASS, DENY, BLOCKED})

KNOWN_OPERATIONS = frozenset({"inspect", "test", "edit", "stage", "commit", "push", "release"})
READ_ONLY_OPERATIONS = frozenset({"inspect", "test"})
MUTATING_OPERATIONS = frozenset({"edit", "stage", "commit", "push", "release"})

KNOWN_WORKTREE_STATES = frozenset(
    {
        "clean",
        "dirty_unstaged",
        "dirty_staged",
        "mixed",
        "untracked_only",
        "merge_in_progress",
        "rebase_in_progress",
        "cherry_pick_in_progress",
        "detached_head",
        "unknown",
    }
)
IN_PROGRESS_STATES = frozenset(
    {"merge_in_progress", "rebase_in_progress", "cherry_pick_in_progress"}
)
KNOWN_REMOTE_RELATIONSHIPS = frozenset(
    {"synchronized", "ahead", "behind", "diverged", "no_upstream", "unknown"}
)
KNOWN_REPOSITORY_SCOPES = frozenset({"ACOS CORE", "BUSINESS PROJECT"})

RUNTIME_PRODUCERS = {
    "ChatGPT Review Runtime": frozenset({"ChatGPT", "ChatGPT Review"}),
    "Codex Executor Runtime": frozenset({"Codex Executor"}),
    "External Advisory Runtime": frozenset({"External Advisory Reviewer"}),
    "Automation Runtime": frozenset({"Automation"}),
}

MUTATION_AUTHORIZATION_SOURCES = frozenset({"CHATGPT REVIEW DECISION", "USER DECISION"})
READ_AUTHORIZATION_SOURCES = frozenset(
    {"TASK", "POLICY", "CHATGPT REVIEW DECISION", "USER DECISION"}
)
NON_AUTHORIZING_SOURCES = frozenset({"ADVISORY REVIEW", "AUDIT RECORD", "RESULT"})

DRY_RUN_NOTICE = (
    "Dry-run policy evaluation only; no Git operation was executed or authorized "
    "by the checker itself."
)
UNSAFE_SHELL_FRAGMENTS = ("&&", "||", ";", "|", ">", "<", "`", "$(", "\n", "\r")


@dataclass(frozen=True)
class ParsedCommand:
    argv: tuple[str, ...]
    operation: str | None
    risk: str
    pathspecs: tuple[str, ...] = ()
    denial_reason: str | None = None


@dataclass(frozen=True)
class PathSet:
    paths: tuple[str, ...]
    violations: tuple[str, ...]


@dataclass
class GateResult:
    case_id: str
    runtime_identity: str | None
    producer: str | None
    requested_operation: str | None
    authorized_operation: str | None
    repository_scope: str | None
    branch: str | None
    head: str | None
    worktree_state: str | None
    staged_paths: list[str] | None
    changed_paths: list[str] | None
    authorization_id: str | None
    allowed: bool
    result: str
    reason: str
    source: str
    expected_result: str | None
    expectation_met: bool | None
    remote: str | None = None
    upstream_branch: str | None = None
    local_ahead: int | None = None
    local_behind: int | None = None
    diverged: bool | None = None
    force: bool | None = None
    force_with_lease: bool | None = None
    command: str | None = None
    parsed_command: list[str] | None = None
    command_risk: str | None = None


class FixtureBlocked(ValueError):
    """Raised when fixture state cannot be evaluated safely."""


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
    result: str,
    allowed: bool,
    reason: str,
    expected_result: str | None,
    expected_allowed: bool | None,
    expected_reason_contains: str | None,
) -> bool:
    checks = [result == expected_result] if expected_result else [result == PASS]
    if expected_allowed is not None:
        checks.append(allowed == expected_allowed)
    if expected_reason_contains is not None:
        checks.append(expected_reason_contains in reason)
    return all(checks)


def _result(
    *,
    case_id: str,
    runtime_identity: str | None,
    producer: str | None,
    requested_operation: str | None,
    authorized_operation: str | None,
    repository_scope: str | None,
    branch: str | None,
    head: str | None,
    worktree_state: str | None,
    staged_paths: list[str] | None,
    changed_paths: list[str] | None,
    authorization_id: str | None,
    result: str,
    reason: str,
    source: str,
    expected_result: str | None,
    expected_allowed: bool | None = None,
    expected_reason_contains: str | None = None,
    remote: str | None = None,
    upstream_branch: str | None = None,
    local_ahead: int | None = None,
    local_behind: int | None = None,
    diverged: bool | None = None,
    force: bool | None = None,
    force_with_lease: bool | None = None,
    command: str | None = None,
    parsed_command: list[str] | None = None,
    command_risk: str | None = None,
) -> GateResult:
    allowed = result == PASS
    return GateResult(
        case_id=case_id,
        runtime_identity=runtime_identity,
        producer=producer,
        requested_operation=requested_operation,
        authorized_operation=authorized_operation,
        repository_scope=repository_scope,
        branch=branch,
        head=head,
        worktree_state=worktree_state,
        staged_paths=staged_paths,
        changed_paths=changed_paths,
        authorization_id=authorization_id,
        allowed=allowed,
        result=result,
        reason=reason,
        source=source,
        expected_result=expected_result,
        expectation_met=_expectation_met(
            result,
            allowed,
            reason,
            expected_result,
            expected_allowed,
            expected_reason_contains,
        ),
        remote=remote,
        upstream_branch=upstream_branch,
        local_ahead=local_ahead,
        local_behind=local_behind,
        diverged=diverged,
        force=force,
        force_with_lease=force_with_lease,
        command=command,
        parsed_command=parsed_command,
        command_risk=command_risk,
    )


def _bool_value(data: Mapping[str, Any], name: str, *, required: bool = False) -> bool:
    if name not in data:
        if required:
            raise FixtureBlocked(f"Missing required boolean field: {name}")
        return False
    value = data[name]
    if not isinstance(value, bool):
        raise FixtureBlocked(f"{name} must be a boolean")
    return value


def _int_value(data: Mapping[str, Any], name: str, *, required: bool = False) -> int | None:
    if name not in data:
        if required:
            raise FixtureBlocked(f"Missing required integer field: {name}")
        return None
    value = data[name]
    if type(value) is not int or value < 0:
        raise FixtureBlocked(f"{name} must be a non-negative integer")
    return value


def _normalize_repo_path(value: str) -> tuple[str, str | None]:
    if "\x00" in value or "\\" in value:
        raise FixtureBlocked("Path contains NUL or an ambiguous non-POSIX separator")
    raw = value.strip()
    if not raw:
        raise FixtureBlocked("Path entries must not be empty")
    path = PurePosixPath(raw)
    if path.is_absolute():
        return raw, "Absolute path escapes the authorized repository scope"

    parts: list[str] = []
    traversal = False
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            traversal = True
            if parts:
                parts.pop()
            continue
        parts.append(part)
    normalized = "/".join(parts) if parts else "."
    if traversal:
        return normalized, "Path contains forbidden '..' traversal"
    if normalized == ".":
        return normalized, "Repository-root pathspec is forbidden"
    if normalized == ".git" or normalized.startswith(".git/"):
        return normalized, "Direct .git internal state access is forbidden"
    return normalized, None


def _path_list(data: Mapping[str, Any], name: str, *, required: bool = False) -> PathSet:
    if name not in data:
        if required:
            raise FixtureBlocked(f"Missing required path list: {name}")
        return PathSet((), ())
    value = data[name]
    if not isinstance(value, list):
        raise FixtureBlocked(f"{name} must be an array")
    paths: list[str] = []
    violations: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise FixtureBlocked(f"{name} entries must be strings")
        normalized, violation = _normalize_repo_path(item)
        paths.append(normalized)
        if violation:
            violations.append(f"{item!r}: {violation}")
    return PathSet(tuple(paths), tuple(violations))


def _path_matches_grant(path: str, grant: str, directory_grants: set[str]) -> bool:
    return path == grant or (grant in directory_grants and path.startswith(grant + "/"))


def _all_paths_authorized(paths: Sequence[str], raw_grants: Sequence[str]) -> bool:
    normalized_grants: list[str] = []
    directory_grants: set[str] = set()
    for raw in raw_grants:
        normalized, violation = _normalize_repo_path(raw)
        if violation:
            return False
        normalized_grants.append(normalized)
        if raw.strip().endswith("/"):
            directory_grants.add(normalized)
    return all(
        any(_path_matches_grant(path, grant, directory_grants) for grant in normalized_grants)
        for path in paths
    )


def parse_command(command: object) -> ParsedCommand | None:
    if command is None:
        return None
    if not isinstance(command, str) or not command.strip():
        raise FixtureBlocked("command must be a non-empty string when provided")
    if any(fragment in command for fragment in UNSAFE_SHELL_FRAGMENTS):
        raise FixtureBlocked("command contains compound or unsafe shell syntax")
    try:
        argv = tuple(shlex.split(command, posix=True))
    except ValueError as exc:
        raise FixtureBlocked(f"command cannot be parsed safely: {exc}") from exc
    if len(argv) < 2 or argv[0] != "git":
        raise FixtureBlocked("command must be a recognized static Git command")

    subcommand = argv[1]
    args = argv[2:]
    if subcommand in {"status", "log"}:
        return ParsedCommand(argv, "inspect", "read-only")
    if subcommand == "diff":
        operation = "test" if "--check" in args else "inspect"
        return ParsedCommand(argv, operation, "read-only")
    if subcommand == "add":
        pathspecs = tuple(arg for arg in args if arg != "--" and not arg.startswith("-"))
        forbidden = {".", "-A", "--all", "-u"}.intersection(args)
        reason = "Blanket staging is forbidden" if forbidden else None
        return ParsedCommand(argv, "stage", "forbidden" if reason else "mutating", pathspecs, reason)
    if subcommand == "commit":
        if "-a" in args or "--all" in args:
            return ParsedCommand(argv, "commit", "forbidden", denial_reason="Implicit commit staging is forbidden")
        if "--no-verify" in args:
            return ParsedCommand(argv, "commit", "forbidden", denial_reason="Hook bypass is forbidden")
        return ParsedCommand(argv, "commit", "mutating")
    if subcommand == "push":
        forbidden_flags = {"--force", "-f", "--force-with-lease", "--mirror", "--delete", "--no-verify"}
        if forbidden_flags.intersection(args):
            return ParsedCommand(argv, "push", "forbidden", denial_reason="Force, broad, delete, or hook-bypass push is forbidden")
        return ParsedCommand(argv, "push", "mutating")
    if subcommand in {"reset", "clean", "pull", "merge", "rebase"}:
        return ParsedCommand(
            argv,
            None,
            "forbidden",
            denial_reason=f"git {subcommand} is outside this operation authorization model",
        )
    raise FixtureBlocked(f"Unrecognized Git command: git {subcommand}")


def _state_consistency(
    worktree_state: str,
    staged_paths: PathSet,
    changed_paths: PathSet,
) -> None:
    if worktree_state == "unknown":
        raise FixtureBlocked("worktree_state is unknown")
    if worktree_state == "clean" and (staged_paths.paths or changed_paths.paths):
        raise FixtureBlocked("clean worktree contradicts staged_paths or changed_paths")
    if worktree_state == "dirty_staged" and not staged_paths.paths:
        raise FixtureBlocked("dirty_staged requires non-empty staged_paths")
    if worktree_state == "dirty_unstaged" and staged_paths.paths:
        raise FixtureBlocked("dirty_unstaged contradicts non-empty staged_paths")
    if worktree_state == "untracked_only" and not changed_paths.paths:
        raise FixtureBlocked("untracked_only requires changed_paths")


def _remote_consistency(
    relationship: str | None,
    ahead: int | None,
    behind: int | None,
    diverged: bool | None,
    upstream_branch: str | None,
) -> None:
    if relationship is None:
        return
    if relationship not in KNOWN_REMOTE_RELATIONSHIPS:
        raise FixtureBlocked(f"Unknown remote_relationship: {relationship}")
    if relationship == "unknown":
        raise FixtureBlocked("remote_relationship is unknown")
    if ahead is None or behind is None or diverged is None:
        raise FixtureBlocked("Remote relationship requires local_ahead, local_behind, and diverged")
    if relationship == "synchronized" and (ahead != 0 or behind != 0 or diverged):
        raise FixtureBlocked("synchronized relationship contradicts ahead/behind/diverged")
    if relationship == "ahead" and (ahead < 1 or behind != 0 or diverged):
        raise FixtureBlocked("ahead relationship contradicts ahead/behind/diverged")
    if relationship == "behind" and (ahead != 0 or behind < 1 or diverged):
        raise FixtureBlocked("behind relationship contradicts ahead/behind/diverged")
    if relationship == "diverged" and (ahead < 1 or behind < 1 or not diverged):
        raise FixtureBlocked("diverged relationship contradicts ahead/behind/diverged")
    if relationship == "no_upstream" and upstream_branch is not None:
        raise FixtureBlocked("no_upstream relationship contradicts upstream_branch")


def _pass(reason: str) -> tuple[str, str]:
    return PASS, f"{reason} {DRY_RUN_NOTICE}"


def _evaluate_runtime(runtime_identity: str, requested_operation: str) -> tuple[str, str] | None:
    if requested_operation in READ_ONLY_OPERATIONS:
        return None
    if runtime_identity == "Codex Executor Runtime":
        return None
    if runtime_identity == "External Advisory Runtime":
        return DENY, "External Advisory Runtime cannot edit, stage, commit, push, or release."
    if runtime_identity == "Automation Runtime":
        return DENY, "Automation Runtime cannot edit, stage, commit, push, or release."
    return DENY, "ChatGPT Review Runtime authorizes Git mutations but does not execute them."


def _evaluate_inspect_or_test(
    requested_operation: str,
    parsed: ParsedCommand | None,
) -> tuple[str, str]:
    if parsed and parsed.operation != requested_operation:
        return DENY, "Command operation does not match the requested read-only operation."
    return _pass(f"Independent {requested_operation} authorization and state are consistent.")


def _evaluate_edit(changed: PathSet, authorized_paths: list[str]) -> tuple[str, str]:
    if not changed.paths:
        return BLOCKED, "Edit evaluation requires non-empty changed_paths."
    if changed.violations:
        return DENY, "; ".join(changed.violations)
    if not _all_paths_authorized(changed.paths, authorized_paths):
        return DENY, "changed_paths exceed authorized_paths."
    return _pass("Edit paths match the independent edit authorization.")


def _evaluate_stage(
    parsed: ParsedCommand | None,
    declared_pathspecs: PathSet,
    staged: PathSet,
    changed: PathSet,
    authorized_paths: list[str],
) -> tuple[str, str]:
    if parsed is None:
        return BLOCKED, "Stage evaluation requires a command."
    if parsed.operation != "stage":
        return DENY, "Command operation does not match stage authorization."
    if parsed.denial_reason:
        return DENY, parsed.denial_reason
    if not declared_pathspecs.paths or not parsed.pathspecs:
        return BLOCKED, "Stage requires explicit non-empty pathspecs."
    parsed_paths = PathSet(
        tuple(_normalize_repo_path(path)[0] for path in parsed.pathspecs),
        tuple(
            violation
            for path in parsed.pathspecs
            for violation in [_normalize_repo_path(path)[1]]
            if violation
        ),
    )
    violations = declared_pathspecs.violations + parsed_paths.violations + staged.violations
    if violations:
        return DENY, "; ".join(violations)
    if set(parsed_paths.paths) != set(declared_pathspecs.paths):
        return DENY, "Parsed command pathspecs do not match declared pathspecs."
    if set(staged.paths) != set(declared_pathspecs.paths):
        return DENY, "staged_paths do not match the explicit stage manifest."
    if not _all_paths_authorized(declared_pathspecs.paths, authorized_paths):
        return DENY, "Stage pathspecs exceed authorized_paths."
    if changed.paths and not set(declared_pathspecs.paths).issubset(changed.paths):
        return DENY, "Stage pathspecs are not present in changed_paths."
    return _pass("Explicit stage pathspecs match staged_paths and authorized_paths.")


def _evaluate_commit(
    data: Mapping[str, Any],
    parsed: ParsedCommand | None,
    staged: PathSet,
    authorized_paths: list[str],
    worktree_state: str,
) -> tuple[str, str]:
    if parsed is None:
        return BLOCKED, "Commit evaluation requires a command."
    if parsed.operation != "commit":
        return DENY, "Command operation does not match commit authorization."
    if parsed.denial_reason:
        return DENY, parsed.denial_reason
    if not staged.paths:
        return BLOCKED, "Commit requires non-empty staged_paths."
    if staged.violations:
        return DENY, "; ".join(staged.violations)
    if not _all_paths_authorized(staged.paths, authorized_paths):
        return DENY, "staged_paths exceed the reviewed commit manifest."
    if set(staged.paths) != set(_path_list(data, "authorized_paths", required=True).paths):
        return DENY, "staged_paths do not exactly match authorized_paths."
    if worktree_state in IN_PROGRESS_STATES and not _bool_value(data, "continuation_authorized"):
        return DENY, f"Commit during {worktree_state} requires separate continuation authorization."
    amend_requested = "--amend" in parsed.argv
    if amend_requested and not _bool_value(data, "amend_authorized"):
        return DENY, "Commit amend was not independently authorized."
    expected_message = _nonempty_string(data.get("expected_commit_message"))
    actual_message = _nonempty_string(data.get("commit_message"))
    if expected_message and actual_message != expected_message:
        return DENY, "commit_message does not match the authorization."
    return _pass("Staged manifest, branch baseline, and commit authorization match.")


def _evaluate_push(
    data: Mapping[str, Any],
    parsed: ParsedCommand | None,
    staged: PathSet,
    changed: PathSet,
    worktree_state: str,
    branch: str,
    head: str,
    remote: str | None,
    upstream_branch: str | None,
    ahead: int | None,
    behind: int | None,
    diverged: bool | None,
) -> tuple[str, str]:
    if parsed is None:
        return BLOCKED, "Push evaluation requires a command."
    if parsed.operation != "push":
        return DENY, "Command operation does not match push authorization."
    if parsed.denial_reason:
        return DENY, parsed.denial_reason
    if not remote or not upstream_branch:
        return BLOCKED, "Push requires remote and upstream_branch."
    if worktree_state != "clean" or staged.paths or changed.paths:
        return DENY, "Push requires a clean worktree and empty staged/changed path sets."
    if ahead is None or behind is None or diverged is None:
        return BLOCKED, "Push requires complete ahead/behind/diverged state."
    if behind != 0 or diverged:
        return DENY, "Push is forbidden while behind or diverged; no automatic repair is allowed."
    authorized_ahead = _int_value(data, "authorized_ahead", required=True)
    if ahead != authorized_ahead:
        return DENY, "local_ahead does not match the push authorization."
    if _nonempty_string(data.get("authorized_remote")) != remote:
        return DENY, "remote does not match the push authorization."
    if _nonempty_string(data.get("authorized_upstream_branch")) != upstream_branch:
        return DENY, "upstream_branch does not match the push authorization."
    if _nonempty_string(data.get("target_commit")) != head:
        return BLOCKED, "Push target_commit does not match current HEAD."
    if len(parsed.argv) < 4 or parsed.argv[2] != remote or parsed.argv[3] != branch:
        return DENY, "Push command does not explicitly match remote and branch."
    return _pass("Push state and independent push authorization match exactly.")


def _evaluate_release(
    data: Mapping[str, Any],
    staged: PathSet,
    changed: PathSet,
    worktree_state: str,
    head: str,
    relationship: str | None,
) -> tuple[str, str]:
    if not _nonempty_string(data.get("release_target")):
        return BLOCKED, "Release requires an explicit release_target."
    if _nonempty_string(data.get("target_commit")) != head:
        return BLOCKED, "Release target_commit does not match current HEAD."
    if worktree_state != "clean" or staged.paths or changed.paths:
        return DENY, "Release requires a clean repository state."
    if relationship != "synchronized":
        return DENY, "Release requires synchronized Git state and separate release authority."
    required_gates = ("review_accepted", "advisory_accepted", "user_decision_accepted")
    values = [_bool_value(data, name, required=True) for name in required_gates]
    if not all(values):
        return DENY, "Release review, advisory, and User Decision gates must all be accepted."
    return _pass("Independent release authorization and all declared review gates match.")


def evaluate_fixture(data: Mapping[str, Any], source: str = "<memory>") -> GateResult:
    case_id = _nonempty_string(data.get("case_id")) or Path(source).stem or "unknown-case"
    runtime_identity = _nonempty_string(data.get("runtime_identity"))
    producer = _nonempty_string(data.get("producer"))
    requested_raw = _nonempty_string(data.get("requested_operation"))
    requested_operation = requested_raw.lower() if requested_raw else None
    authorized_raw = _nonempty_string(data.get("authorized_operation"))
    authorized_operation = authorized_raw.lower() if authorized_raw else None
    scope_raw = _nonempty_string(data.get("repository_scope"))
    repository_scope = scope_raw.upper() if scope_raw else None
    branch = _nonempty_string(data.get("branch"))
    head = _nonempty_string(data.get("head"))
    state_raw = _nonempty_string(data.get("worktree_state"))
    worktree_state = state_raw.lower() if state_raw else None
    authorization_id = _nonempty_string(data.get("authorization_id"))
    expected_raw = _nonempty_string(data.get("expected_result"))
    expected_result = expected_raw.upper() if expected_raw else None
    expected_reason_contains = _nonempty_string(data.get("expected_reason_contains"))
    expected_allowed_raw = data.get("expected_allowed")
    expected_allowed = expected_allowed_raw if isinstance(expected_allowed_raw, bool) else None
    command_value = data.get("command")
    command = command_value if isinstance(command_value, str) else None
    remote = _nonempty_string(data.get("remote"))
    upstream_branch = _nonempty_string(data.get("upstream_branch"))
    staged_values = data.get("staged_paths") if isinstance(data.get("staged_paths"), list) else None
    changed_values = data.get("changed_paths") if isinstance(data.get("changed_paths"), list) else None
    parsed: ParsedCommand | None = None
    ahead: int | None = None
    behind: int | None = None
    diverged: bool | None = None

    def finish(result: str, reason: str) -> GateResult:
        return _result(
            case_id=case_id,
            runtime_identity=runtime_identity,
            producer=producer,
            requested_operation=requested_operation,
            authorized_operation=authorized_operation,
            repository_scope=repository_scope,
            branch=branch,
            head=head,
            worktree_state=worktree_state,
            staged_paths=staged_values,
            changed_paths=changed_values,
            authorization_id=authorization_id,
            result=result,
            reason=reason,
            source=source,
            expected_result=expected_result,
            expected_allowed=expected_allowed,
            expected_reason_contains=expected_reason_contains,
            remote=remote,
            upstream_branch=upstream_branch,
            local_ahead=ahead,
            local_behind=behind,
            diverged=diverged,
            force=data.get("force") if isinstance(data.get("force"), bool) else None,
            force_with_lease=(
                data.get("force_with_lease")
                if isinstance(data.get("force_with_lease"), bool)
                else None
            ),
            command=command,
            parsed_command=list(parsed.argv) if parsed else None,
            command_risk=parsed.risk if parsed else None,
        )

    if expected_result and expected_result not in RESULT_VALUES:
        return finish(BLOCKED, f"Unknown expected_result: {expected_result}")
    if expected_allowed_raw is not None and not isinstance(expected_allowed_raw, bool):
        return finish(BLOCKED, "expected_allowed must be a boolean")

    missing = [
        name
        for name, value in (
            ("runtime_identity", runtime_identity),
            ("producer", producer),
            ("requested_operation", requested_operation),
            ("authorized_operation", authorized_operation),
            ("repository_scope", repository_scope),
            ("branch", branch),
            ("head", head),
            ("worktree_state", worktree_state),
        )
        if value is None
    ]
    if missing:
        return finish(BLOCKED, "Missing required fixture fields: " + ", ".join(missing))
    if runtime_identity not in RUNTIME_PRODUCERS:
        return finish(BLOCKED, f"Unknown runtime identity: {runtime_identity}")
    if requested_operation not in KNOWN_OPERATIONS:
        return finish(BLOCKED, f"Unknown requested_operation: {requested_operation}")
    if authorized_operation not in KNOWN_OPERATIONS:
        if authorized_operation and (" and " in authorized_operation or "," in authorized_operation):
            return finish(DENY, "Combined or ambiguous operation authorization is forbidden.")
        return finish(BLOCKED, f"Unknown authorized_operation: {authorized_operation}")
    if repository_scope not in KNOWN_REPOSITORY_SCOPES:
        return finish(BLOCKED, f"Unknown repository_scope: {repository_scope}")
    if worktree_state not in KNOWN_WORKTREE_STATES:
        return finish(BLOCKED, f"Unknown worktree_state: {worktree_state}")
    if producer not in RUNTIME_PRODUCERS[runtime_identity]:
        return finish(DENY, "producer does not match runtime_identity.")
    if command_value is not None and not isinstance(command_value, str):
        return finish(BLOCKED, "command must be a string when provided")

    try:
        staged = _path_list(data, "staged_paths", required=True)
        changed = _path_list(data, "changed_paths", required=True)
        declared_pathspecs = _path_list(data, "pathspecs")
        authorized_path_set = _path_list(data, "authorized_paths")
        raw_authorized_paths = data.get("authorized_paths", [])
        if not isinstance(raw_authorized_paths, list) or not all(
            isinstance(item, str) for item in raw_authorized_paths
        ):
            raise FixtureBlocked("authorized_paths must be an array of strings")
        _state_consistency(worktree_state, staged, changed)
        parsed = parse_command(command_value)
        ahead = _int_value(data, "local_ahead")
        behind = _int_value(data, "local_behind")
        diverged = (
            _bool_value(data, "diverged", required=True) if "diverged" in data else None
        )
        relationship_raw = _nonempty_string(data.get("remote_relationship"))
        relationship = relationship_raw.lower() if relationship_raw else None
        _remote_consistency(relationship, ahead, behind, diverged, upstream_branch)
        expired = _bool_value(data, "authorization_expired")
        consumed = _bool_value(data, "authorization_consumed")
        force = _bool_value(data, "force")
        force_with_lease = _bool_value(data, "force_with_lease")
    except FixtureBlocked as exc:
        return finish(BLOCKED, str(exc))

    if staged.violations or changed.violations or authorized_path_set.violations:
        return finish(DENY, "; ".join(staged.violations + changed.violations + authorized_path_set.violations))
    if parsed and parsed.risk == "forbidden":
        return finish(DENY, parsed.denial_reason or "Forbidden Git command pattern.")
    if force or force_with_lease:
        return finish(DENY, "Force and force-with-lease are forbidden under ordinary push authority.")
    if requested_operation != authorized_operation:
        return finish(DENY, "requested_operation does not match the independent authorized_operation.")
    if not authorization_id:
        return finish(BLOCKED, "authorization_id is required for the requested operation.")

    authorization_runtime = _nonempty_string(data.get("authorization_runtime"))
    authorization_scope_raw = _nonempty_string(data.get("authorization_scope"))
    authorization_scope = authorization_scope_raw.upper() if authorization_scope_raw else None
    authorization_branch = _nonempty_string(data.get("authorization_branch"))
    authorization_head = _nonempty_string(data.get("authorization_head"))
    authorization_source_raw = _nonempty_string(data.get("authorization_source"))
    authorization_source = authorization_source_raw.upper() if authorization_source_raw else None
    if not all(
        (authorization_runtime, authorization_scope, authorization_branch, authorization_head, authorization_source)
    ):
        return finish(BLOCKED, "Authorization runtime, scope, branch, head, and source are required.")
    if authorization_runtime != runtime_identity:
        return finish(DENY, "Authorization runtime does not match the requesting runtime.")
    if authorization_scope != repository_scope:
        if _bool_value(data, "scope_conflict_known"):
            return finish(DENY, "Authorization is explicitly limited to a different repository scope.")
        return finish(BLOCKED, "authorization_scope conflicts with repository_scope.")
    if authorization_branch != branch:
        return finish(DENY, "Authorization branch does not match the current branch.")
    if authorization_head != head:
        return finish(BLOCKED, "Authorization target HEAD conflicts with current HEAD.")
    if expired or consumed:
        return finish(DENY, "Authorization is expired or already consumed.")
    if authorization_source in NON_AUTHORIZING_SOURCES:
        return finish(DENY, f"{authorization_source} is evidence or advice, not Git authorization.")
    allowed_sources = (
        READ_AUTHORIZATION_SOURCES
        if requested_operation in READ_ONLY_OPERATIONS
        else MUTATION_AUTHORIZATION_SOURCES
    )
    if authorization_source not in allowed_sources:
        return finish(DENY, "authorization_source cannot authorize the requested operation.")

    runtime_denial = _evaluate_runtime(runtime_identity, requested_operation)
    if runtime_denial:
        return finish(*runtime_denial)
    if parsed and parsed.operation and parsed.operation != requested_operation:
        return finish(DENY, "Parsed command operation does not match requested_operation.")

    if requested_operation in READ_ONLY_OPERATIONS:
        result, reason = _evaluate_inspect_or_test(requested_operation, parsed)
    elif requested_operation == "edit":
        if parsed is not None:
            result, reason = DENY, "Edit authorization does not authorize a Git command."
        else:
            result, reason = _evaluate_edit(changed, raw_authorized_paths)
    elif requested_operation == "stage":
        result, reason = _evaluate_stage(
            parsed, declared_pathspecs, staged, changed, raw_authorized_paths
        )
    elif requested_operation == "commit":
        result, reason = _evaluate_commit(
            data, parsed, staged, raw_authorized_paths, worktree_state
        )
    elif requested_operation == "push":
        result, reason = _evaluate_push(
            data,
            parsed,
            staged,
            changed,
            worktree_state,
            branch,
            head,
            remote,
            upstream_branch,
            ahead,
            behind,
            diverged,
        )
    else:
        result, reason = _evaluate_release(
            data, staged, changed, worktree_state, head, relationship
        )
    return finish(result, reason)


def load_fixture(path: Path) -> GateResult:
    inferred_expected = _infer_expected_result(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _result(
            case_id=path.stem,
            runtime_identity=None,
            producer=None,
            requested_operation=None,
            authorized_operation=None,
            repository_scope=None,
            branch=None,
            head=None,
            worktree_state=None,
            staged_paths=None,
            changed_paths=None,
            authorization_id=None,
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
            requested_operation=None,
            authorized_operation=None,
            repository_scope=None,
            branch=None,
            head=None,
            worktree_state=None,
            staged_paths=None,
            changed_paths=None,
            authorization_id=None,
            result=BLOCKED,
            reason="Fixture root must be a JSON object",
            source=str(path),
            expected_result=inferred_expected,
        )
    if "expected_result" not in data and inferred_expected:
        data = dict(data)
        data["expected_result"] = inferred_expected
    return evaluate_fixture(data, source=str(path))


def discover_fixture_paths(targets: Sequence[str]) -> tuple[list[Path], list[GateResult]]:
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
                    case_id=target.name or "missing-target",
                    runtime_identity=None,
                    producer=None,
                    requested_operation=None,
                    authorized_operation=None,
                    repository_scope=None,
                    branch=None,
                    head=None,
                    worktree_state=None,
                    staged_paths=None,
                    changed_paths=None,
                    authorization_id=None,
                    result=BLOCKED,
                    reason=f"Fixture target does not exist: {target}",
                    source=str(target),
                    expected_result=None,
                )
            )
    return sorted(paths, key=lambda path: str(path)), errors


def render_text(results: Sequence[GateResult]) -> str:
    lines: list[str] = []
    fields = (
        "runtime_identity",
        "producer",
        "requested_operation",
        "authorized_operation",
        "repository_scope",
        "branch",
        "head",
        "worktree_state",
        "staged_paths",
        "changed_paths",
        "authorization_id",
        "remote",
        "upstream_branch",
        "local_ahead",
        "local_behind",
        "diverged",
        "force",
        "force_with_lease",
        "command",
        "parsed_command",
        "command_risk",
        "allowed",
        "result",
        "reason",
        "source",
        "expected_result",
        "expectation_met",
    )
    for item in results:
        lines.append(f"{item.result}: {item.case_id}")
        for field in fields:
            lines.append(f"  {field}: {getattr(item, field)!r}")
    counts = {value: sum(item.result == value for item in results) for value in RESULT_VALUES}
    mismatches = sum(not item.expectation_met for item in results)
    lines.append(
        "SUMMARY: "
        f"total={len(results)} pass={counts[PASS]} deny={counts[DENY]} "
        f"blocked={counts[BLOCKED]} expectation_mismatches={mismatches}"
    )
    return "\n".join(lines)


def render_json(results: Sequence[GateResult]) -> str:
    return json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run ACOS Git operation authorization fixtures.")
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

#!/usr/bin/env python3
"""Deterministic fixture-only ACOS Schema Validator."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

try:
    import jsonschema
    from jsonschema import Draft7Validator, FormatChecker
except ModuleNotFoundError as exc:  # Report a controlled BLOCKED result at runtime.
    jsonschema = None
    Draft7Validator = None
    FormatChecker = None
    JSONSCHEMA_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    JSONSCHEMA_IMPORT_ERROR = None

PASS, DENY, BLOCKED = "PASS", "DENY", "BLOCKED"
RESULTS = {PASS, DENY, BLOCKED}
MODES = {"validate_envelope", "validate_policy"}

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "schema-validation"
ENVELOPE_SCHEMA_PATH = ROOT / "fixtures" / "schemas" / "envelope.schema.json"
POLICY_SCHEMA_PATH = ROOT / "fixtures" / "schemas" / "policy.schema.json"

MAX_FIXTURE_BYTES = 1_048_576
MAX_SCHEMA_BYTES = 524_288
MAX_JSON_DEPTH = 64
HELPER_KEYS = {"case_id", "mode", "template", "omit_fields", "expected_result"}

NOTICE = "Fixture-only schema validation; no real state, authorization, or enforcement was modified."
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?$")
RFC3339_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
def is_rfc3339_datetime(value: object) -> bool:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        return False
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.tzinfo is not None


if FormatChecker is not None:
    FORMAT_CHECKER = FormatChecker()
    FORMAT_CHECKER.checks("date-time", raises=ValueError)(is_rfc3339_datetime)
else:
    FORMAT_CHECKER = None


@dataclass
class Result:
    case_id: str
    mode: str | None
    result: str
    reason: str
    warnings: list[str]
    source: str
    expected_result: str | None
    expectation_met: bool | None


class Blocked(ValueError):
    pass


class Denied(ValueError):
    pass


class DuplicateKey(ValueError):
    pass


def text(v: object) -> str | None:
    return v.strip() if isinstance(v, str) and v.strip() else None


def req(d: Mapping[str, Any], k: str) -> str:
    v = text(d.get(k))
    if not v:
        raise Blocked(f"missing or invalid {k}")
    return v


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKey(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def json_depth(value: Any, depth: int = 1) -> int:
    if depth > MAX_JSON_DEPTH:
        raise Blocked(f"JSON nesting exceeds {MAX_JSON_DEPTH}")
    if isinstance(value, dict):
        return max((json_depth(item, depth + 1) for item in value.values()), default=depth)
    if isinstance(value, list):
        return max((json_depth(item, depth + 1) for item in value), default=depth)
    return depth


def read_json(path: Path, max_bytes: int, label: str) -> Any:
    try:
        if path.stat().st_size > max_bytes:
            raise Blocked(f"{label} exceeds {max_bytes} bytes")
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_keys)
        json_depth(data)
        return data
    except Blocked:
        raise
    except DuplicateKey as exc:
        raise Blocked(str(exc)) from exc
    except UnicodeDecodeError as exc:
        raise Blocked(f"{label} is not valid UTF-8: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise Blocked(f"unable to parse {label} JSON: {exc}") from exc
    except OSError as exc:
        raise Blocked(f"unable to read {label}: {exc}") from exc


def assert_local_references(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and (not isinstance(item, str) or not item.startswith("#")):
                raise Blocked("schema contains a non-local $ref")
            assert_local_references(item)
    elif isinstance(value, list):
        for item in value:
            assert_local_references(item)


def load_validator(path: Path, label: str) -> Draft7Validator:
    if jsonschema is None or Draft7Validator is None or FORMAT_CHECKER is None:
        detail = f": {JSONSCHEMA_IMPORT_ERROR}" if JSONSCHEMA_IMPORT_ERROR else ""
        raise Blocked(f"jsonschema dependency unavailable{detail}")
    if not path.is_file():
        raise Blocked(f"{label} schema file missing")
    schema = read_json(path, MAX_SCHEMA_BYTES, f"{label} schema")
    if not isinstance(schema, dict):
        raise Blocked(f"{label} schema root must be an object")
    assert_local_references(schema)
    try:
        Draft7Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise Blocked(f"invalid {label} schema: {exc.message}") from exc
    return Draft7Validator(schema, format_checker=FORMAT_CHECKER)


def parse_version(value: str) -> tuple[int, int, int]:
    if not SEMVER_RE.fullmatch(value):
        raise Denied(f"invalid version: {value}")
    parts = [int(part) for part in value.split(".")]
    return tuple((parts + [0])[:3])


def validate_logical_path(value: str, label: str) -> None:
    if "\x00" in value:
        raise Denied(f"{label} contains a NUL byte")
    if ".." in PurePosixPath(value.replace("\\", "/")).parts:
        raise Denied(f"{label} contains parent traversal")


def validate_envelope_semantics(data: Mapping[str, Any]) -> None:
    for index, value in enumerate(data.get("scope", [])):
        validate_logical_path(value, f"scope[{index}]")

    expires_at = data.get("expires_at")
    if expires_at:
        created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if expires <= created:
            raise Denied("expires_at must be later than created_at")


def validate_policy_semantics(data: Mapping[str, Any]) -> None:
    metadata = data["policy_metadata"]
    policy_version = parse_version(metadata["policy_version"])
    minimum = parse_version(metadata["minimum_supported_schema_version"])
    maximum = parse_version(metadata["maximum_supported_schema_version"])
    if minimum > maximum:
        raise Denied("minimum supported schema version exceeds maximum")

    rollback = metadata.get("rollback_target_version")
    if rollback is not None and parse_version(rollback) >= policy_version:
        raise Denied("rollback target must be lower than policy version")

    filesystem = data["filesystem_policies"]
    for group in ("protected_roots", "denied_path_classes"):
        for index, value in enumerate(filesystem[group]):
            validate_logical_path(value, f"{group}[{index}]")


# Static templates for fixture expansion.
ENVELOPE_TEMPLATE = {
    "artifact_id": "ART-059-001",
    "artifact_type": "USER DECISION",
    "schema_version": "1.0",
    "producer": "User Decision",
    "producer_role": "user_decision_source",
    "producer_runtime_id": "user-decision-local-059",
    "project_id": "/Users/zhang/Documents/chatgpt-codex-coordination-system",
    "task_id": "TASK_059",
    "workflow_id": "WF-059",
    "parent_artifact_id": None,
    "correlation_id": "CORR-059-001",
    "created_at": "2026-07-12T19:30:00Z",
    "expires_at": "2026-07-13T19:30:00Z",
    "sequence": 1,
    "scope": ["fixtures/schemas/envelope.schema.json"],
    "requested_action": "start_task",
    "authority_type": "user",
    "authorization_id": "AUTH-059-001",
    "policy_version": "1.0",
    "content_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "signature": "sig:user_decision_fixture_signature_059",
    "nonce": "nonce:fixture_nonce_059_abcdef",
    "replay_protection": {
        "class": "one_time",
        "max_consumption": 1
    },
    "to": "ChatGPT Review",
    "next_receiver": "ChatGPT Review",
    "status": "accepted",
    "payload": {
        "authorized_action": "start_task",
        "reason": "Authorized by user decision."
    }
}

POLICY_TEMPLATE = {
    "policy_metadata": {
      "schema_version": "1.0",
      "policy_version": "1.0",
      "effective_time": "2026-07-12T19:30:00Z",
      "rollback_target_version": None,
      "minimum_supported_schema_version": "1.0",
      "maximum_supported_schema_version": "1.0",
      "traceability_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "signing_key_id": "fixture-policy-key-059",
      "signature": "sig:policy_fixture_signature_059",
      "migration_notes": "Initial fixture-only policy schema release."
    },
    "role_permissions": {
      "user_decision_source": {
        "allowed_artifacts": ["USER DECISION"]
      },
      "chatgpt_review": {
        "allowed_artifacts": ["TASK", "REVIEW", "DECISION"]
      },
      "codex_executor": {
        "allowed_artifacts": ["RESULT", "BLOCKED RESULT"]
      },
      "external_advisory": {
        "allowed_artifacts": ["ADVISORY REVIEW"]
      },
      "automation": {
        "allowed_artifacts": ["RESULT", "AUDIT EVENT"]
      }
    },
    "requirement_categories": {
      "start_new_task": "user_decision_required"
    },
    "advisory_triggers": {},
    "user_decision_mappings": {},
    "filesystem_policies": {
      "protected_roots": [],
      "denied_path_classes": []
    },
    "git_policies": {
      "enforce_separate_capabilities": True,
      "branch_protections": {
        "require_signed_commits": True,
        "allow_force_push": False
      }
    },
    "lifecycle_order": ["task", "result", "review", "decision"],
    "aggregation_precedence": ["BLOCKED", "DENY", "PASS"],
    "contract_versions": {"artifact_envelope": ["1.0"]},
    "risk_levels": {}
}

TEMPLATES = {
    "valid_envelope": {**ENVELOPE_TEMPLATE, "mode": "validate_envelope"},
    "valid_policy": {**POLICY_TEMPLATE, "mode": "validate_policy"}
}


def make_result(
    d: Mapping[str, Any],
    source: str,
    result: str,
    reason: str,
    mode: str | None = None
) -> Result:
    expected = text(d.get("expected_result"))
    expected = expected.upper() if expected else None
    case_id = text(d.get("case_id")) or Path(source).stem

    expectation_met = None
    if expected:
        expectation_met = result == expected

    return Result(
        case_id=case_id,
        mode=mode or d.get("mode"),
        result=result,
        reason=f"{reason} {NOTICE}",
        warnings=[],
        source=source,
        expected_result=expected,
        expectation_met=expectation_met
    )


def evaluate_fixture(d: Mapping[str, Any], source: str = "<memory>") -> Result:
    try:
        if not isinstance(d, dict):
            raise Blocked("fixture root must be an object")

        json_depth(d)
        mode = req(d, "mode")
        if mode not in MODES:
            raise Blocked(f"unknown mode: {mode}")

        if text(d.get("expected_result")) and text(d["expected_result"]).upper() not in RESULTS:
            raise Blocked("unknown expected_result")

        clean_d = {key: value for key, value in d.items() if key not in HELPER_KEYS}
        if mode == "validate_envelope":
            validator = load_validator(ENVELOPE_SCHEMA_PATH, "envelope")
            errors = sorted(validator.iter_errors(clean_d), key=lambda error: list(error.absolute_path))
            if errors:
                raise Denied(f"envelope schema validation failed: {errors[0].message}")
            validate_envelope_semantics(clean_d)
        elif mode == "validate_policy":
            validator = load_validator(POLICY_SCHEMA_PATH, "policy")
            errors = sorted(validator.iter_errors(clean_d), key=lambda error: list(error.absolute_path))
            if errors:
                raise Denied(f"policy schema validation failed: {errors[0].message}")
            validate_policy_semantics(clean_d)

        return make_result(d, source, PASS, "Schema validation passed.", mode)

    except Denied as e:
        return make_result(d, source, DENY, str(e))
    except Blocked as e:
        return make_result(d, source, BLOCKED, str(e))
    except Exception as e:
        return make_result(d, source, BLOCKED, f"unexpected validation error: {e}")


def confined_path(path: Path, *, require_json: bool) -> Path:
    if ".." in path.parts:
        raise Blocked("fixture path contains parent traversal")
    try:
        absolute = path.expanduser()
        if not absolute.is_absolute():
            absolute = Path.cwd() / absolute
        current = Path(absolute.anchor)
        for part in absolute.parts[1:]:
            current /= part
            if current.is_symlink():
                raise Blocked("fixture target must not contain symbolic links")

        resolved = path.expanduser().resolve(strict=True)
        root = FIXTURE_ROOT.resolve(strict=True)
        resolved.relative_to(root)
    except Blocked:
        raise
    except FileNotFoundError as exc:
        raise Blocked("fixture target does not exist") from exc
    except ValueError as exc:
        raise Blocked("fixture target is outside the fixture root") from exc
    except OSError as exc:
        raise Blocked(f"unable to resolve fixture target: {exc}") from exc

    if require_json and (not resolved.is_file() or resolved.suffix.lower() != ".json"):
        raise Blocked("fixture target must be a JSON file")
    return resolved


def load_fixture(path: Path) -> Result:
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
        resolved = confined_path(path, require_json=True)
        data = read_json(resolved, MAX_FIXTURE_BYTES, "fixture")
    except Blocked as e:
        return make_result(
            {"case_id": path.stem, "expected_result": inferred},
            str(path),
            BLOCKED,
            str(e)
        )

    if not isinstance(data, dict):
        return make_result(
            {"case_id": path.stem, "expected_result": inferred},
            str(path),
            BLOCKED,
            "fixture root must be an object"
        )

    template = data.get("template")
    if template is not None:
        if template not in TEMPLATES:
            return make_result(
                {"case_id": path.stem, "expected_result": inferred},
                str(path),
                BLOCKED,
                "unknown fixture template"
            )
        expanded = copy.deepcopy(TEMPLATES[template])
        expanded.update({k: v for k, v in data.items() if k not in {"template", "omit_fields"}})
        omitted = data.get("omit_fields", [])
        if not isinstance(omitted, list):
            return make_result(
                {"case_id": path.stem, "expected_result": inferred},
                str(path),
                BLOCKED,
                "omit_fields must be an array"
            )
        for field in omitted:
            expanded.pop(field, None)
        data = expanded

    try:
        json_depth(data)
    except Blocked as exc:
        return make_result(data, str(path), BLOCKED, str(exc))

    if inferred and "expected_result" not in data:
        data["expected_result"] = inferred

    return evaluate_fixture(data, str(path))


def discover_paths(targets: Sequence[str]) -> tuple[list[Path], list[Result]]:
    paths: set[Path] = set()
    errors: list[Result] = []
    for raw in targets:
        p = Path(raw)
        try:
            resolved = confined_path(p, require_json=False)
            if resolved.is_file():
                paths.add(confined_path(p, require_json=True))
            elif resolved.is_dir():
                for candidate in resolved.rglob("*.json"):
                    paths.add(confined_path(candidate, require_json=True))
            else:
                raise Blocked("fixture target is neither a file nor a directory")
        except Blocked as exc:
            errors.append(
                make_result(
                    {"case_id": p.name},
                    str(p),
                    BLOCKED,
                    str(exc)
                )
            )
    return sorted(paths, key=str), errors


def render_text(results: list[Result]) -> str:
    fields = (
        "mode",
        "result",
        "reason",
        "expected_result",
        "expectation_met"
    )
    lines = []
    for item in results:
        lines.append(f"{item.result}: {item.case_id}")
        lines.extend(f"  {f}: {getattr(item, f)!r}" for f in fields)
    counts = {x: sum(r.result == x for r in results) for x in RESULTS}
    mismatches = sum(not r.expectation_met for r in results if r.expected_result)
    lines.append(
        f"SUMMARY: total={len(results)} pass={counts[PASS]} deny={counts[DENY]} "
        f"blocked={counts[BLOCKED]} expectation_mismatches={mismatches}"
    )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="ACOS Schema Validator CLI")
    parser.add_argument("fixtures", nargs="+")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    paths, errors = discover_paths(args.fixtures)
    results = [load_fixture(p) for p in paths] + errors
    if not results:
        parser.error("No JSON fixtures found")

    print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2) if args.format == "json" else render_text(results))
    if any(not r.expectation_met for r in results if r.expected_result):
        return 1
    if any(result.result == BLOCKED and result.expected_result is None for result in results):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

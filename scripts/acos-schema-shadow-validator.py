#!/usr/bin/env python3
"""Deterministic fixture-only ACOS W1 2.0 shadow schema validator."""

from __future__ import annotations

import argparse
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
except ModuleNotFoundError as exc:
    jsonschema = None
    Draft7Validator = None
    FormatChecker = None
    JSONSCHEMA_IMPORT_ERROR: ModuleNotFoundError | None = exc
else:
    JSONSCHEMA_IMPORT_ERROR = None

PASS, DENY, BLOCKED = "PASS", "DENY", "BLOCKED"
RESULTS = {PASS, DENY, BLOCKED}
MODES = {"validate_envelope", "validate_policy"}
SUPPORTED_VERSION = "2.0"

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "schema-validation-2.0"
ENVELOPE_SCHEMA_PATH = ROOT / "fixtures" / "schemas" / "2.0" / "envelope.schema.json"
POLICY_SCHEMA_PATH = ROOT / "fixtures" / "schemas" / "2.0" / "policy.schema.json"

MAX_FIXTURE_BYTES = 1_048_576
MAX_SCHEMA_BYTES = 524_288
MAX_JSON_DEPTH = 64
HELPER_KEYS = {"case_id", "mode", "expected_result"}
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?$")
RFC3339_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
NOTICE = (
    "W1 shadow validation only; schema validity does not authenticate identity, "
    "authority, Grant, Authorization, signature, receipt, persistence, or runtime "
    "state, and no operational enforcement occurred."
)

LIFECYCLE_STATES = {
    "ARTIFACT": {
        "DRAFT", "MATERIALIZED", "VALIDATED", "ACCEPTED", "REJECTED",
        "SUPERSEDED", "NON_CONSUMABLE",
    },
    "TASK": {
        "DEFINED", "MATERIALIZED", "READY", "EXECUTING", "RESULT",
        "REVIEW", "DECISION", "CLOSED", "BLOCKED",
    },
    "AUTHORIZATION": {
        "DECLARED", "ISSUED", "VALIDATED", "ACTIVE", "CONSUMED",
        "REVOKED", "EXPIRED", "DENIED", "SUPERSEDED", "FAILED",
    },
    "GIT": {"INSPECTED", "STAGED", "COMMITTED", "PUSHED", "RELEASED", "BLOCKED"},
    "ACTIVATION": {"LOCKED", "ELIGIBLE", "AUTHORIZED", "ACTIVE", "REVOKED"},
    "OPERATIONAL_ENTRY": {"LOCKED", "ELIGIBLE", "AUTHORIZED", "ENTERED", "EXITED"},
}


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


@dataclass(frozen=True)
class Result:
    case_id: str
    mode: str | None
    result: str
    reason: str
    notice: str
    authority_effect: str
    source: str
    expected_result: str | None
    expectation_met: bool | None


class Blocked(ValueError):
    pass


class Denied(ValueError):
    pass


class DuplicateKey(ValueError):
    pass


def text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def required_text(data: Mapping[str, Any], key: str) -> str:
    value = text(data.get(key))
    if not value:
        raise Blocked(f"missing or invalid {key}")
    return value


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


def make_result(
    data: Mapping[str, Any],
    source: str,
    result: str,
    reason: str,
    mode: str | None = None,
) -> Result:
    expected = text(data.get("expected_result"))
    expected = expected.upper() if expected else None
    case_id = text(data.get("case_id")) or Path(source).stem
    expectation_met = result == expected if expected else None
    return Result(
        case_id=case_id,
        mode=mode or (data.get("mode") if isinstance(data.get("mode"), str) else None),
        result=result,
        reason=reason,
        notice=NOTICE,
        authority_effect="NONE",
        source=source,
        expected_result=expected,
        expectation_met=expectation_met,
    )


def version_selectors(data: Mapping[str, Any], mode: str) -> tuple[str, str]:
    selector_source: Mapping[str, Any] = data
    if mode == "validate_policy":
        metadata = data.get("policy_metadata")
        if not isinstance(metadata, dict):
            raise Blocked("missing or invalid policy_metadata for version selectors")
        selector_source = metadata

    contract_version = required_text(selector_source, "contract_version")
    schema_version = required_text(selector_source, "schema_version")
    if not SEMVER_RE.fullmatch(contract_version):
        raise Blocked(f"malformed contract_version selector: {contract_version}")
    if not SEMVER_RE.fullmatch(schema_version):
        raise Blocked(f"malformed schema_version selector: {schema_version}")
    if contract_version != schema_version:
        raise Denied(
            "mixed contract/schema version tuple: "
            f"{contract_version}/{schema_version}"
        )
    if (contract_version, schema_version) != (SUPPORTED_VERSION, SUPPORTED_VERSION):
        raise Denied(
            "unsupported contract/schema version tuple: "
            f"{contract_version}/{schema_version}; no fallback or downgrade"
        )
    return contract_version, schema_version


def validate_logical_path(value: str, label: str) -> None:
    if "\x00" in value:
        raise Denied(f"{label} contains a NUL byte")
    if ".." in PurePosixPath(value.replace("\\", "/")).parts:
        raise Denied(f"{label} contains parent traversal")


def validate_envelope_semantics(data: Mapping[str, Any]) -> None:
    expires_at = data.get("expires_at")
    if expires_at:
        created = datetime.fromisoformat(str(data["created_at"]).replace("Z", "+00:00"))
        expires = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expires <= created:
            raise Denied("expires_at must be later than created_at")

    for index, scope in enumerate(data.get("scope", [])):
        if scope.get("scope_type") == "PATH":
            validate_logical_path(scope["target"], f"scope[{index}].target")

    artifact_id = data.get("artifact_id")
    parent_ids: set[str] = set()
    for index, parent in enumerate(data.get("lineage", [])):
        parent_id = parent["artifact_id"]
        if parent_id == artifact_id:
            raise Denied(f"lineage[{index}] self-references artifact_id")
        if parent_id in parent_ids:
            raise Denied(f"duplicate lineage parent: {parent_id}")
        parent_ids.add(parent_id)

    lifecycle = data["lifecycle"]
    family, state = lifecycle["family"], lifecycle["state"]
    if state not in LIFECYCLE_STATES[family]:
        raise Denied(f"unsupported lifecycle state for {family}: {state}")


def validate_policy_semantics(data: Mapping[str, Any]) -> None:
    for index, item in enumerate(data["supported_contract_schema_tuples"]):
        contract_version = item["contract_version"]
        schema_version = item["schema_version"]
        if not SEMVER_RE.fullmatch(contract_version) or not SEMVER_RE.fullmatch(schema_version):
            raise Denied(f"malformed supported version tuple at index {index}")


def evaluate_fixture(data: Mapping[str, Any], source: str = "<memory>") -> Result:
    try:
        if not isinstance(data, dict):
            raise Blocked("fixture root must be an object")
        json_depth(data)
        mode = required_text(data, "mode")
        if mode not in MODES:
            raise Blocked(f"unknown mode: {mode}")
        expected = text(data.get("expected_result"))
        if expected and expected.upper() not in RESULTS:
            raise Blocked("unknown expected_result")

        clean_data = {key: value for key, value in data.items() if key not in HELPER_KEYS}
        version_selectors(clean_data, mode)
        if mode == "validate_envelope":
            validator = load_validator(ENVELOPE_SCHEMA_PATH, "envelope 2.0")
            errors = sorted(validator.iter_errors(clean_data), key=lambda error: list(error.absolute_path))
            if errors:
                raise Denied(f"envelope 2.0 schema validation failed: {errors[0].message}")
            validate_envelope_semantics(clean_data)
        else:
            validator = load_validator(POLICY_SCHEMA_PATH, "policy 2.0")
            errors = sorted(validator.iter_errors(clean_data), key=lambda error: list(error.absolute_path))
            if errors:
                raise Denied(f"policy 2.0 schema validation failed: {errors[0].message}")
            validate_policy_semantics(clean_data)
        return make_result(data, source, PASS, "W1 2.0 shadow schema validation passed.", mode)
    except Denied as exc:
        return make_result(data, source, DENY, str(exc))
    except Blocked as exc:
        return make_result(data, source, BLOCKED, str(exc))
    except Exception as exc:
        return make_result(data, source, BLOCKED, f"unexpected validation error: {exc}")


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
        resolved = absolute.resolve(strict=True)
        root = FIXTURE_ROOT.resolve(strict=True)
        resolved.relative_to(root)
    except Blocked:
        raise
    except FileNotFoundError as exc:
        raise Blocked("fixture target does not exist") from exc
    except ValueError as exc:
        raise Blocked("fixture target is outside the W1 fixture root") from exc
    except OSError as exc:
        raise Blocked(f"unable to resolve fixture target: {exc}") from exc
    if require_json and (not resolved.is_file() or resolved.suffix.lower() != ".json"):
        raise Blocked("fixture target must be a JSON file")
    return resolved


def load_fixture(path: Path) -> Result:
    inferred = (
        PASS if path.name.startswith("valid-")
        else DENY if path.name.startswith("invalid-")
        else BLOCKED if path.name.startswith("blocked-")
        else None
    )
    try:
        resolved = confined_path(path, require_json=True)
        data = read_json(resolved, MAX_FIXTURE_BYTES, "fixture")
    except Blocked as exc:
        return make_result(
            {"case_id": path.stem, "expected_result": inferred},
            str(path),
            BLOCKED,
            str(exc),
        )
    if not isinstance(data, dict):
        return make_result(
            {"case_id": path.stem, "expected_result": inferred},
            str(resolved),
            BLOCKED,
            "fixture root must be an object",
        )
    if inferred and "expected_result" not in data:
        data = {**data, "expected_result": inferred}
    return evaluate_fixture(data, str(resolved))


def discover_paths(targets: Sequence[str]) -> tuple[list[Path], list[Result]]:
    paths: list[Path] = []
    errors: list[Result] = []
    for target in targets:
        raw = Path(target)
        try:
            resolved = confined_path(raw, require_json=False)
            if resolved.is_dir():
                paths.extend(sorted(path for path in resolved.iterdir() if path.is_file() and path.suffix.lower() == ".json"))
            elif resolved.is_file() and resolved.suffix.lower() == ".json":
                paths.append(resolved)
            else:
                raise Blocked("target must be a JSON file or directory")
        except Blocked as exc:
            errors.append(make_result({"case_id": raw.stem}, str(raw), BLOCKED, str(exc)))
    return paths, errors


def render_text(results: Sequence[Result]) -> str:
    blocks = []
    for result in results:
        blocks.append(
            "\n".join(
                [
                    f"CASE: {result.case_id}",
                    f"MODE: {result.mode or 'UNKNOWN'}",
                    f"RESULT: {result.result}",
                    f"REASON: {result.reason}",
                    f"AUTHORITY EFFECT: {result.authority_effect}",
                    f"NOTICE: {result.notice}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", help="W1 2.0 fixture files or directories")
    parser.add_argument("--json", action="store_true", help="render JSON results")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths, errors = discover_paths(args.targets)
    results = [*errors, *(load_fixture(path) for path in paths)]
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    else:
        print(render_text(results))
    if not results:
        return 2
    if any(
        result.result == BLOCKED and result.expected_result != BLOCKED
        for result in results
    ):
        return 2
    if any(result.expectation_met is False for result in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

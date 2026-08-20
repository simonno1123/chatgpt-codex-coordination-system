#!/usr/bin/env python3
"""Deterministic read-only verifier for the ACOS W2 1.0 shadow profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, MutableSet, Sequence

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
MODES = {
    "validate_runtime_registry",
    "validate_evidence_record",
    "validate_persistence_receipt",
}
SUPPORTED_PROFILE_VERSION = "1.0"
SUPPORTED_CONTRACT_VERSION = "2.0"
GOVERNANCE_STATUS = "UNAUTHENTICATED_SHADOW"

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "fixtures" / "schema-validation-w2" / "1.0"
SCHEMA_ROOT = ROOT / "fixtures" / "schemas" / "w2" / "1.0"
SCHEMA_PATHS = {
    "validate_runtime_registry": SCHEMA_ROOT / "runtime-registry.schema.json",
    "validate_evidence_record": SCHEMA_ROOT / "evidence-record.schema.json",
    "validate_persistence_receipt": SCHEMA_ROOT / "persistence-receipt.schema.json",
}

MAX_FIXTURE_BYTES = 1_048_576
MAX_SCHEMA_BYTES = 524_288
MAX_TARGET_BYTES = 4_194_304
MAX_JSON_DEPTH = 64
HELPER_KEYS = {"case_id", "mode", "expected_result"}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RFC3339_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)
EVIDENCE_METHODS = {
    "DECLARED_DIGEST_SHA256",
    "EXACT_BYTE_SHA256",
    "REFERENCE_MATCH",
    "REVOCATION_STATUS",
    "EXPIRY_STATUS",
}
NOTICE = (
    "W2 shadow verification does not authenticate runtime identity, confer "
    "authority, issue or consume a Grant or Authorization, establish a "
    "production trust decision, establish Activation, or establish Operational "
    "Entry."
)
REPLAY_NOTICE = "W2 has no durable replay registry."


def is_rfc3339_datetime(value: object) -> bool:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        return False
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
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
    replay_notice: str
    governance_status: str
    authority_effect: str
    identity_effect: str
    execution_effect: str
    activation_effect: str
    eligible_for_execution: bool
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


def load_validator(mode: str) -> Draft7Validator:
    if jsonschema is None or Draft7Validator is None or FORMAT_CHECKER is None:
        detail = f": {JSONSCHEMA_IMPORT_ERROR}" if JSONSCHEMA_IMPORT_ERROR else ""
        raise Blocked(f"jsonschema dependency unavailable{detail}")
    path = SCHEMA_PATHS[mode]
    if not path.is_file():
        raise Blocked(f"W2 schema file missing for mode {mode}")
    schema = read_json(path, MAX_SCHEMA_BYTES, f"{mode} schema")
    if not isinstance(schema, dict):
        raise Blocked(f"{mode} schema root must be an object")
    assert_local_references(schema)
    try:
        Draft7Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise Blocked(f"invalid W2 schema for {mode}: {exc.message}") from exc
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
    return Result(
        case_id=case_id,
        mode=mode or (data.get("mode") if isinstance(data.get("mode"), str) else None),
        result=result,
        reason=reason,
        notice=NOTICE,
        replay_notice=REPLAY_NOTICE,
        governance_status=GOVERNANCE_STATUS,
        authority_effect="NONE",
        identity_effect="NONE",
        execution_effect="NONE",
        activation_effect="NONE",
        eligible_for_execution=False,
        source=source,
        expected_result=expected,
        expectation_met=(result == expected if expected else None),
    )


def parse_time(value: str, label: str) -> datetime:
    if not is_rfc3339_datetime(value):
        raise Denied(f"{label} must be an RFC3339 date-time")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def version_selectors(data: Mapping[str, Any]) -> tuple[str, str]:
    profile_version = required_text(data, "profile_version")
    binding = data.get("contract_binding")
    if not isinstance(binding, dict):
        raise Blocked("missing or invalid contract_binding")
    contract_version = required_text(binding, "contract_version")
    if profile_version != SUPPORTED_PROFILE_VERSION:
        raise Denied(f"unsupported W2 profile_version: {profile_version}; no fallback or downgrade")
    if contract_version != SUPPORTED_CONTRACT_VERSION:
        raise Denied(f"unsupported ACOS contract binding: {contract_version}; no fallback or downgrade")
    return profile_version, contract_version


def explicit_verifier_time(value: str | None, required_for: str) -> datetime:
    if not value:
        raise Blocked(f"explicit verifier time required for {required_for}")
    return parse_time(value, "verifier_time")


def validate_window(
    *,
    valid_from: str | None,
    valid_until: str | None,
    verifier_time: str | None,
    label: str,
) -> None:
    start = parse_time(valid_from, f"{label}.valid_from") if valid_from else None
    end = parse_time(valid_until, f"{label}.valid_until") if valid_until else None
    if start and end and end <= start:
        raise Denied(f"{label} validity window is not increasing")
    if start or end:
        observed = explicit_verifier_time(verifier_time, f"{label} validity evaluation")
        if start and observed < start:
            raise Denied(f"{label} is not yet valid at the explicit verifier time")
        if end and observed >= end:
            raise Denied(f"{label} is expired at the explicit verifier time")


def validate_runtime_registry(data: Mapping[str, Any], verifier_time: str | None) -> None:
    domains: dict[str, Mapping[str, Any]] = {}
    for index, domain in enumerate(data["trust_domains"]):
        domain_id = domain["trust_domain_id"]
        if domain_id in domains:
            raise Denied(f"duplicate trust_domain_id: {domain_id}")
        domains[domain_id] = domain
        if domain["revocation_state"] == "REVOKED":
            raise Denied(f"trust domain is revoked: {domain_id}")
        validate_window(
            valid_from=domain.get("valid_from"),
            valid_until=domain.get("valid_until"),
            verifier_time=verifier_time,
            label=f"trust_domains[{index}]",
        )

    runtime_ids: set[str] = set()
    session_ids: set[str] = set()
    for index, entry in enumerate(data["runtime_entries"]):
        runtime_id = entry["runtime_id"]
        session_id = entry["session_id"]
        if runtime_id in runtime_ids:
            raise Denied(f"duplicate runtime_id: {runtime_id}")
        if session_id in session_ids:
            raise Denied(f"duplicate session_id: {session_id}")
        runtime_ids.add(runtime_id)
        session_ids.add(session_id)

        provider_id = entry.get("provider_id")
        model_id = entry.get("model_id")
        if runtime_id == provider_id:
            raise Denied(f"runtime_entries[{index}] runtime_id equals provider_id")
        if runtime_id == model_id:
            raise Denied(f"runtime_entries[{index}] runtime_id equals model_id")

        domain = domains.get(entry["trust_domain_id"])
        if domain is None:
            raise Denied(f"runtime_entries[{index}] references an unknown trust domain")
        if domain["revocation_state"] == "REVOKED":
            raise Denied(f"runtime_entries[{index}] references a revoked trust domain")
        if entry["identity_state"] == "REVOKED":
            raise Denied(f"runtime entry is revoked: {runtime_id}")
        if entry["identity_state"] == "EXPIRED":
            raise Denied(f"runtime entry is expired: {runtime_id}")

        created = parse_time(entry["created_at"], f"runtime_entries[{index}].created_at")
        expires_at = entry.get("expires_at")
        if expires_at:
            expires = parse_time(expires_at, f"runtime_entries[{index}].expires_at")
            if expires <= created:
                raise Denied(f"runtime_entries[{index}] expiry is not after creation")
            observed = explicit_verifier_time(verifier_time, "runtime expiry evaluation")
            if observed >= expires:
                raise Denied(f"runtime entry is expired at the explicit verifier time: {runtime_id}")


def validate_evidence_record(
    data: Mapping[str, Any],
    verifier_time: str | None,
    seen_nonces: MutableSet[str] | None,
) -> None:
    if data["verification_method"] not in EVIDENCE_METHODS:
        raise Denied(f"unsupported verification method: {data['verification_method']}")
    if not DIGEST_RE.fullmatch(data["content_digest"]):
        raise Denied("malformed evidence content_digest")

    evidence_id = data["evidence_id"]
    parents = data.get("parent_evidence_ids", [])
    if len(parents) != len(set(parents)):
        raise Denied("duplicate evidence parent")
    if evidence_id in parents:
        raise Denied("evidence record self-references its evidence_id")

    if data.get("revocation_state") == "REVOKED" or data["verification_result"] == "REVOKED":
        raise Denied("evidence record is revoked")
    if data["verification_result"] == "EXPIRED":
        raise Denied("evidence record declares an expired result")
    if data["verification_result"] == "MISMATCH":
        raise Denied("evidence verification reports a mismatch")
    if data["verification_result"] == "UNSUPPORTED":
        raise Denied("evidence verification method is unsupported")

    expires_at = data.get("expires_at")
    if expires_at:
        observed = explicit_verifier_time(verifier_time, "evidence expiry evaluation")
        if observed >= parse_time(expires_at, "evidence.expires_at"):
            raise Denied("evidence record is expired at the explicit verifier time")

    nonce = data.get("nonce")
    if nonce and seen_nonces is not None:
        if nonce in seen_nonces:
            raise Denied(f"duplicate nonce within supplied verification set: {nonce}")
        seen_nonces.add(nonce)


def confined_path(path: Path, root: Path, *, require_json: bool, label: str) -> Path:
    if ".." in path.parts:
        raise Blocked(f"{label} contains parent traversal")
    try:
        absolute = path.expanduser()
        if not absolute.is_absolute():
            absolute = Path.cwd() / absolute
        current = Path(absolute.anchor)
        for part in absolute.parts[1:]:
            current /= part
            if current.is_symlink():
                raise Blocked(f"{label} must not contain symbolic links")
        resolved = absolute.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except Blocked:
        raise
    except FileNotFoundError as exc:
        raise Blocked(f"{label} does not exist") from exc
    except ValueError as exc:
        raise Blocked(f"{label} is outside the permitted repository root") from exc
    except OSError as exc:
        raise Blocked(f"unable to resolve {label}: {exc}") from exc
    if require_json and (not resolved.is_file() or resolved.suffix.lower() != ".json"):
        raise Blocked(f"{label} must be a JSON file")
    return resolved


def digest_file(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_TARGET_BYTES:
            raise Blocked(f"exact-byte target exceeds {MAX_TARGET_BYTES} bytes")
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except Blocked:
        raise
    except OSError as exc:
        raise Blocked(f"unable to read exact-byte target: {exc}") from exc


def validate_persistence_receipt(
    data: Mapping[str, Any],
    exact_target: Path | None,
    exact_target_requested: bool,
) -> None:
    content_digest = data["content_digest"]
    observed = data["exact_byte_verification"]["observed_digest"]
    result = data["exact_byte_verification"]["result"]
    if result == "MISMATCH":
        raise Denied("persistence receipt reports an exact-byte mismatch")
    if result == "MATCH" and observed != content_digest:
        raise Denied("claimed content digest and observed digest do not match")

    if exact_target_requested and exact_target is None:
        raise Blocked("exact-byte verification requested without an explicit target")
    if exact_target is not None:
        target = confined_path(
            exact_target,
            ROOT,
            require_json=False,
            label="exact-byte target",
        )
        if not target.is_file():
            raise Blocked("exact-byte target must be a regular file")
        actual = digest_file(target)
        if actual != content_digest or actual != observed:
            raise Denied("exact-byte repository-local target digest mismatch")
        if result != "MATCH":
            raise Denied("exact-byte target matched but receipt result is not MATCH")


def evaluate_document(
    data: Mapping[str, Any],
    source: str = "<memory>",
    *,
    verifier_time: str | None = None,
    exact_target: Path | None = None,
    exact_target_requested: bool = False,
    seen_nonces: MutableSet[str] | None = None,
    cross_run_replay: bool = False,
) -> Result:
    try:
        if not isinstance(data, dict):
            raise Blocked("W2 document root must be an object")
        json_depth(data)
        mode = required_text(data, "mode")
        if mode not in MODES:
            raise Blocked(f"unknown mode: {mode}")
        expected = text(data.get("expected_result"))
        if expected and expected.upper() not in RESULTS:
            raise Blocked("unknown expected_result")
        if cross_run_replay:
            raise Blocked("cross-run replay determination requires unavailable durable state")

        document = {key: value for key, value in data.items() if key not in HELPER_KEYS}
        validator = load_validator(mode)
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
        if errors:
            raise Denied(f"W2 schema validation failed: {errors[0].message}")
        version_selectors(document)

        if mode == "validate_runtime_registry":
            validate_runtime_registry(document, verifier_time)
        elif mode == "validate_evidence_record":
            validate_evidence_record(document, verifier_time, seen_nonces)
        else:
            validate_persistence_receipt(document, exact_target, exact_target_requested)
        return make_result(data, source, PASS, "W2 1.0 shadow verification passed.", mode)
    except Denied as exc:
        return make_result(data, source, DENY, str(exc))
    except Blocked as exc:
        return make_result(data, source, BLOCKED, str(exc))
    except Exception as exc:
        return make_result(data, source, BLOCKED, f"unexpected W2 verification error: {exc}")


def load_fixture(
    path: Path,
    *,
    verifier_time: str | None = None,
    exact_target: Path | None = None,
    exact_target_requested: bool = False,
    seen_nonces: MutableSet[str] | None = None,
    cross_run_replay: bool = False,
) -> Result:
    inferred = PASS if path.name.startswith("valid-") else None
    try:
        resolved = confined_path(path, FIXTURE_ROOT, require_json=True, label="fixture target")
        data = read_json(resolved, MAX_FIXTURE_BYTES, "W2 fixture")
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
            "W2 fixture root must be an object",
        )
    if inferred and "expected_result" not in data:
        data = {**data, "expected_result": inferred}
    return evaluate_document(
        data,
        str(resolved),
        verifier_time=verifier_time,
        exact_target=exact_target,
        exact_target_requested=exact_target_requested,
        seen_nonces=seen_nonces,
        cross_run_replay=cross_run_replay,
    )


def discover_paths(targets: Sequence[str]) -> tuple[list[Path], list[Result]]:
    paths: list[Path] = []
    errors: list[Result] = []
    for target in targets:
        raw = Path(target)
        try:
            resolved = confined_path(raw, FIXTURE_ROOT, require_json=False, label="fixture target")
            if resolved.is_dir():
                paths.extend(
                    sorted(path for path in resolved.iterdir() if path.is_file() and path.suffix.lower() == ".json")
                )
            elif resolved.is_file() and resolved.suffix.lower() == ".json":
                paths.append(resolved)
            else:
                raise Blocked("fixture target must be a JSON file or directory")
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
                    f"GOVERNANCE STATUS: {result.governance_status}",
                    f"AUTHORITY EFFECT: {result.authority_effect}",
                    f"IDENTITY EFFECT: {result.identity_effect}",
                    f"EXECUTION EFFECT: {result.execution_effect}",
                    f"ACTIVATION EFFECT: {result.activation_effect}",
                    f"ELIGIBLE FOR EXECUTION: {str(result.eligible_for_execution).lower()}",
                    f"NOTICE: {result.notice}",
                    f"REPLAY NOTICE: {result.replay_notice}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", help="W2 1.0 fixture files or directories")
    parser.add_argument("--json", action="store_true", help="render JSON results")
    parser.add_argument("--verifier-time", help="explicit RFC3339 time for validity evaluation")
    parser.add_argument("--exact-target", type=Path, help="explicit repository-local exact-byte target")
    parser.add_argument(
        "--require-exact-target",
        action="store_true",
        help="block if an exact-byte target is not supplied",
    )
    parser.add_argument(
        "--cross-run-replay-check",
        action="store_true",
        help="request a replay determination that W2 cannot persist",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths, errors = discover_paths(args.targets)
    seen_nonces: set[str] = set()
    results = [
        *errors,
        *(
            load_fixture(
                path,
                verifier_time=args.verifier_time,
                exact_target=args.exact_target,
                exact_target_requested=args.require_exact_target,
                seen_nonces=seen_nonces,
                cross_run_replay=args.cross_run_replay_check,
            )
            for path in paths
        ),
    ]
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True))
    else:
        print(render_text(results))
    if not results:
        return 2
    if any(result.result == BLOCKED and result.expected_result != BLOCKED for result in results):
        return 2
    if any(result.expectation_met is False for result in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

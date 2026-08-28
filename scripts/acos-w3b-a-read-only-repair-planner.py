#!/usr/bin/env python3
"""Read-only W3B-A shadow inspection and declarative repair planning."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import quote

try:
    from jsonschema import Draft7Validator, FormatChecker
except ImportError:  # pragma: no cover - converted to a bounded result at runtime
    Draft7Validator = None
    FormatChecker = None


PASS = "PASS"
DENY = "DENY"
BLOCKED = "BLOCKED"
NONE = "NONE"
GOVERNANCE_STATUS = "UNAUTHENTICATED_SHADOW"

SUPPORTED_PROFILE_VERSION = "1.0"
SUPPORTED_CONTRACT_VERSION = "2.0"
SUPPORTED_STORE_USER_VERSION = 100
EXPECTED_CANONICAL_SQL_SHA256 = "a9efb6b932eb2a45e9be2cb89c364ef02c20ac2de96771f38b3aecff4244c60d"
AUDIT_GENESIS = "GENESIS"

MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 256 * 1024
MAX_JSON_DEPTH = 32
MAX_COLLECTION_ITEMS = 4096
MAX_SCHEMA_OBJECTS = 128
MAX_ROWS_INSPECTED = 10_000
MAX_EXTRACTED_VALUE_BYTES = 65_536
MAX_VM_CALLBACKS = 2_000
VM_PROGRESS_INTERVAL = 1_000

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SQL_PATH = ROOT / "fixtures" / "state-store-w3" / "1.0" / "state-store.sql"
SCHEMA_ROOT = ROOT / "fixtures" / "schemas" / "w3b-a" / "1.0"
SCHEMA_PATHS = {
    "snapshot_reference": SCHEMA_ROOT / "snapshot-reference.schema.json",
    "repair_evidence": SCHEMA_ROOT / "repair-evidence.schema.json",
    "repair_plan": SCHEMA_ROOT / "repair-plan.schema.json",
    "repair_plan_verification": SCHEMA_ROOT / "repair-plan-verification.schema.json",
}

ALLOWED_OPERATIONS = {
    "shadow_snapshot_inspect",
    "shadow_repair_inspect",
    "shadow_repair_plan",
    "shadow_repair_plan_verify",
}

CLASSIFICATIONS = {
    "DETERMINISTIC_PLAN_CANDIDATE",
    "MANUAL_DECISION_REQUIRED",
    "NON_REPAIRABLE_PRESERVE_AND_BLOCK",
    "AMBIGUOUS_FAIL_CLOSED",
}

ALLOWED_DIFF_ACTIONS = {
    "DECLARE_CANONICAL_INDEX_GAP",
    "REQUEST_MANUAL_DECISION",
    "PRESERVE_AND_BLOCK",
    "REPORT_AMBIGUITY",
}

PLAN_STATE_GRAPH = {
    "PLANNED": ("PLAN_VERIFIED",),
    "PLAN_VERIFIED": (),
}

EXPECTED_INVARIANTS = [
    "SOURCE_SNAPSHOT_UNCHANGED",
    "NO_STORE_MUTATION",
    "NO_AUTHORITY_EFFECT",
    "NO_EXECUTION_EFFECT",
    "NO_ACTIVATION_EFFECT",
    "PLAN_TERMINATES_AT_VERIFICATION",
]

IDENTITY_LIMITATIONS = [
    "FRESHNESS_NOT_ESTABLISHED",
    "AUTHENTICITY_NOT_ESTABLISHED",
    "LOGICAL_STORE_IDENTITY_NOT_ESTABLISHED",
    "GOVERNANCE_AUTHORITY_NONE",
]

EXPECTED_METADATA = {
    "state_store_version": "1.0",
    "w3_profile_version": "1.0",
    "acos_contract_version": "2.0",
    "governance_status": GOVERNANCE_STATUS,
}

EXPECTED_OBJECTS = {
    "table": {
        "store_metadata",
        "grant_observations",
        "authorization_state",
        "authorization_events",
        "workflow_state_events",
        "audit_events",
    },
    "index": {
        "idx_grant_observations_grant_id",
        "idx_authorization_events_authorization",
        "idx_workflow_state_events_task",
        "idx_audit_events_aggregate",
    },
    "trigger": {
        "authorization_events_no_update",
        "authorization_events_no_delete",
        "workflow_state_events_no_update",
        "workflow_state_events_no_delete",
        "audit_events_no_update",
        "audit_events_no_delete",
    },
}

EXPECTED_COLUMNS = {
    "store_metadata": {"metadata_key", "metadata_value"},
    "authorization_state": {
        "authorization_id", "claimed_governance_state", "current_observer_state",
        "version", "created_at", "updated_at", "governance_status",
        "authority_effect", "identity_effect", "execution_effect",
        "activation_effect", "eligible_for_execution",
    },
    "authorization_events": {
        "event_id", "authorization_id", "operation_id", "nonce",
        "canonical_request_digest", "event_type", "previous_observer_state",
        "observer_state", "state_version", "observed_at", "governance_status",
        "authority_effect", "identity_effect", "execution_effect",
        "activation_effect", "eligible_for_execution",
    },
    "audit_events": {
        "sequence", "audit_event_id", "event_type", "aggregate_type",
        "aggregate_id", "payload_digest", "previous_hash", "event_hash",
        "observed_at", "governance_status", "authority_effect",
        "identity_effect", "execution_effect", "activation_effect",
        "eligible_for_execution",
    },
}


def _sqlite_action_codes(names: Sequence[str]) -> frozenset[int]:
    return frozenset(
        value for name in names if isinstance((value := getattr(sqlite3, name, None)), int)
    )


DENIED_SQLITE_ACTIONS = _sqlite_action_codes((
    "SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE",
    "SQLITE_CREATE_INDEX", "SQLITE_CREATE_TABLE", "SQLITE_CREATE_TEMP_INDEX",
    "SQLITE_CREATE_TEMP_TABLE", "SQLITE_CREATE_TEMP_TRIGGER",
    "SQLITE_CREATE_TEMP_VIEW", "SQLITE_CREATE_TRIGGER", "SQLITE_CREATE_VIEW",
    "SQLITE_DROP_INDEX", "SQLITE_DROP_TABLE", "SQLITE_DROP_TEMP_INDEX",
    "SQLITE_DROP_TEMP_TABLE", "SQLITE_DROP_TEMP_TRIGGER", "SQLITE_DROP_TEMP_VIEW",
    "SQLITE_DROP_TRIGGER", "SQLITE_DROP_VIEW", "SQLITE_ALTER_TABLE",
    "SQLITE_CREATE_VTABLE", "SQLITE_DROP_VTABLE", "SQLITE_ATTACH",
    "SQLITE_DETACH", "SQLITE_TRANSACTION", "SQLITE_SAVEPOINT",
    "SQLITE_REINDEX", "SQLITE_ANALYZE",
))


class Blocked(RuntimeError):
    pass


class Denied(RuntimeError):
    pass


@dataclass
class PlannerResult:
    operation: str
    result: str
    reason_code: str
    reason: str
    data: Any = None
    governance_status: str = GOVERNANCE_STATUS
    authority_effect: str = NONE
    identity_effect: str = NONE
    execution_effect: str = NONE
    activation_effect: str = NONE
    eligible_for_execution: bool = False
    plan_effect: str = NONE
    mutation_effect: str = NONE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SnapshotObservation:
    path: Path
    digest: str
    size: int
    device: int
    inode: int
    modified_ns: int


def make_result(
    operation: str,
    result: str,
    reason_code: str,
    reason: str,
    data: Any = None,
) -> PlannerResult:
    return PlannerResult(operation, result, reason_code, reason, data)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_document(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def digest_without(document: Mapping[str, Any], field: str) -> str:
    value = dict(document)
    value.pop(field, None)
    return sha256_document(value)


def non_authority_fields() -> dict[str, Any]:
    return {
        "shadow_status": "SHADOW_ONLY",
        "execution_eligibility": "EXECUTION_INELIGIBLE",
        "authority_status": "AUTHORITY_NONE",
        "mutation_status": "MUTATION_NONE",
        "governance_status": GOVERNANCE_STATUS,
        "authority_effect": NONE,
        "identity_effect": NONE,
        "execution_effect": NONE,
        "activation_effect": NONE,
        "eligible_for_execution": False,
        "plan_effect": NONE,
        "mutation_effect": NONE,
    }


def require_text(value: Any, label: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise Blocked(f"missing or invalid {label}")
    return value


def check_json_limits(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        if depth > MAX_JSON_DEPTH:
            raise Blocked("JSON nesting exceeds the hard depth ceiling")
        count += 1
        if count > MAX_COLLECTION_ITEMS:
            raise Blocked("JSON collection exceeds the hard item ceiling")
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str) or len(key.encode("utf-8")) > MAX_EXTRACTED_VALUE_BYTES:
                    raise Blocked("JSON object key exceeds the hard text ceiling")
                stack.append((child, depth + 1))
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, str) and len(item.encode("utf-8")) > MAX_EXTRACTED_VALUE_BYTES:
            raise Blocked("JSON string exceeds the hard text ceiling")
    try:
        encoded_size = len(canonical_json(value).encode("utf-8"))
    except (RecursionError, ValueError) as exc:
        raise Blocked("JSON input cannot be serialized within the bounded model") from exc
    if encoded_size > MAX_JSON_BYTES:
        raise Blocked("JSON input exceeds the hard byte ceiling")


def read_json(path: Path) -> Any:
    try:
        with path.open("rb") as handle:
            payload = handle.read(MAX_JSON_BYTES + 1)
    except OSError as exc:
        raise Blocked(f"unable to read JSON input: {exc}") from exc
    if len(payload) > MAX_JSON_BYTES:
        raise Blocked("JSON input exceeds the hard byte ceiling")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise Blocked(f"malformed JSON input: {exc}") from exc
    check_json_limits(document)
    return document


def load_validator(kind: str) -> Any:
    if Draft7Validator is None or FormatChecker is None:
        raise Blocked("jsonschema dependency unavailable")
    path = SCHEMA_PATHS.get(kind)
    if path is None:
        raise Blocked(f"unknown W3B-A schema kind: {kind}")
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
        return Draft7Validator(schema, format_checker=FormatChecker())
    except (OSError, ValueError, TypeError) as exc:
        raise Blocked(f"invalid or unavailable W3B-A schema for {kind}: {exc}") from exc


def validate_document(kind: str, document: Mapping[str, Any]) -> None:
    if not isinstance(document, Mapping):
        raise Denied("W3B-A document root must be an object")
    check_json_limits(document)
    errors = sorted(load_validator(kind).iter_errors(document), key=lambda item: list(item.path))
    if errors:
        raise Denied(f"W3B-A {kind} schema validation failed: {errors[0].message}")


def check_canonical_baseline() -> None:
    try:
        actual = hashlib.sha256(CANONICAL_SQL_PATH.read_bytes()).hexdigest()
    except OSError as exc:
        raise Blocked(f"unable to read canonical W3A state-store SQL: {exc}") from exc
    if actual != EXPECTED_CANONICAL_SQL_SHA256:
        raise Blocked("CANONICAL_BASELINE_MISMATCH")


def secure_snapshot_path(snapshot_path: Path | str | None, permitted_root: Path | str | None) -> Path:
    raw_path = Path(require_text(str(snapshot_path) if snapshot_path is not None else None, "snapshot path", 4096))
    raw_root = Path(require_text(str(permitted_root) if permitted_root is not None else None, "permitted snapshot root", 4096))
    if raw_root.is_symlink():
        raise Blocked("permitted snapshot root must not be a symbolic link")
    try:
        root = raw_root.resolve(strict=True)
    except OSError as exc:
        raise Blocked(f"unable to resolve permitted snapshot root: {exc}") from exc
    if not root.is_dir():
        raise Blocked("permitted snapshot root must be a directory")
    if ".." in raw_path.parts:
        raise Blocked("snapshot path contains parent traversal")
    lexical_root = raw_root.absolute()
    candidate = raw_path if raw_path.is_absolute() else lexical_root / raw_path
    try:
        relative_candidate = candidate.relative_to(lexical_root)
    except ValueError:
        relative_candidate = None
    if candidate.is_symlink():
        raise Blocked("snapshot path must not be a symbolic link")
    if relative_candidate is not None:
        current = lexical_root
        for part in relative_candidate.parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise Blocked("snapshot path contains a symbolic-link parent")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise Blocked(f"snapshot path is unavailable or outside the permitted root: {exc}") from exc
    try:
        mode = resolved.lstat().st_mode
    except OSError as exc:
        raise Blocked(f"unable to inspect snapshot path: {exc}") from exc
    if stat.S_ISLNK(mode):
        raise Blocked("snapshot path must not be a symbolic link")
    if not stat.S_ISREG(mode):
        raise Blocked("snapshot path must name a regular file")
    return resolved


def open_snapshot_descriptor(path: Path) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        return os.open(path, flags)
    except OSError as exc:
        raise Blocked(f"unable to open supplied snapshot safely: {exc}") from exc


def write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise Blocked("unable to materialize the private inspection image")
        view = view[written:]


def observe_snapshot_descriptor(
    descriptor: int,
    path: Path,
    copy_descriptor: int | None = None,
) -> SnapshotObservation:
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise Blocked("supplied snapshot descriptor is not a regular file")
        if before.st_size <= 0:
            raise Blocked("supplied snapshot is empty")
        if before.st_size > MAX_SNAPSHOT_BYTES:
            raise Blocked("supplied snapshot exceeds the hard byte ceiling")
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(descriptor, min(65_536, MAX_SNAPSHOT_BYTES + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_SNAPSHOT_BYTES:
                raise Blocked("supplied snapshot exceeds the hard byte ceiling")
            digest.update(chunk)
            if copy_descriptor is not None:
                write_all(copy_descriptor, chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise Blocked("snapshot changed during exact-byte observation")
        return SnapshotObservation(
            path=path,
            digest="sha256:" + digest.hexdigest(),
            size=total,
            device=after.st_dev,
            inode=after.st_ino,
            modified_ns=after.st_mtime_ns,
        )
    except OSError as exc:
        raise Blocked(f"unable to observe supplied snapshot safely: {exc}") from exc


def observe_snapshot(path: Path) -> SnapshotObservation:
    descriptor = open_snapshot_descriptor(path)
    try:
        return observe_snapshot_descriptor(descriptor, path)
    finally:
        os.close(descriptor)


def same_snapshot(left: SnapshotObservation, right: SnapshotObservation) -> bool:
    return (
        left.path == right.path
        and left.digest == right.digest
        and left.size == right.size
        and left.device == right.device
        and left.inode == right.inode
        and left.modified_ns == right.modified_ns
    )


def same_snapshot_bytes(left: SnapshotObservation, right: SnapshotObservation) -> bool:
    return left.digest == right.digest and left.size == right.size


def materialize_private_inspection_image(
    source_descriptor: int,
    source_path: Path,
    image_path: Path,
) -> tuple[SnapshotObservation, SnapshotObservation]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        image_descriptor = os.open(image_path, flags, 0o600)
    except OSError as exc:
        raise Blocked(f"unable to create private inspection image: {exc}") from exc
    try:
        source_observation = observe_snapshot_descriptor(
            source_descriptor, source_path, image_descriptor,
        )
        os.fsync(image_descriptor)
    except OSError as exc:
        raise Blocked(f"unable to materialize private inspection image: {exc}") from exc
    finally:
        os.close(image_descriptor)
    image_observation = observe_snapshot(image_path)
    if not same_snapshot_bytes(source_observation, image_observation):
        raise Blocked("private inspection image differs from the supplied snapshot bytes")
    return source_observation, image_observation


def sqlite_read_only_authorizer(
    action: int,
    _parameter1: str | None,
    _parameter2: str | None,
    _database: str | None,
    _trigger: str | None,
) -> int:
    if action in DENIED_SQLITE_ACTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def open_snapshot_read_only(path: Path) -> sqlite3.Connection:
    uri = "file:" + quote(str(path), safe="/") + "?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=1.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        if hasattr(connection, "enable_load_extension"):
            connection.enable_load_extension(False)
        connection.execute("PRAGMA query_only=ON")
        try:
            connection.execute("PRAGMA trusted_schema=OFF")
        except sqlite3.DatabaseError:
            connection.close()
            raise Blocked("trusted_schema hardening is unavailable")
        callbacks = [0]

        def progress() -> int:
            callbacks[0] += 1
            return 1 if callbacks[0] > MAX_VM_CALLBACKS else 0

        connection.set_progress_handler(progress, VM_PROGRESS_INTERVAL)
        connection.set_authorizer(sqlite_read_only_authorizer)
        return connection
    except Blocked:
        raise
    except sqlite3.Error as exc:
        raise Blocked(f"unable to open supplied snapshot read-only: {exc}") from exc


def audit_hash(row: Mapping[str, Any]) -> str:
    value = canonical_json({
        "aggregate_id": row["aggregate_id"],
        "aggregate_type": row["aggregate_type"],
        "event_type": row["event_type"],
        "observed_at": row["observed_at"],
        "payload_digest": row["payload_digest"],
        "previous_hash": row["previous_hash"],
        "sequence": row["sequence"],
    })
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_object_reference(value: str, kind: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/#-]{1,511}", value):
        return value
    return f"{kind.lower()}:sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def opaque_store_reference(value: str, kind: str) -> str:
    return f"{kind.lower()}:sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def make_finding(
    code: str,
    classification: str,
    object_kind: str,
    object_reference: str,
    summary: str,
    evidence: Any,
) -> dict[str, Any]:
    if classification not in CLASSIFICATIONS:
        raise Blocked("internal W3B-A classification is outside the frozen vocabulary")
    reference = safe_object_reference(object_reference, object_kind)
    return {
        "code": code,
        "classification": classification,
        "object_kind": object_kind,
        "object_reference": reference,
        "evidence_digest": sha256_document({
            "code": code,
            "object_kind": object_kind,
            "object_reference": reference,
            "evidence": evidence,
        }),
        "summary": summary,
    }


def bounded_rows(connection: sqlite3.Connection, query: str) -> list[sqlite3.Row]:
    rows = connection.execute(query).fetchmany(MAX_ROWS_INSPECTED + 1)
    if len(rows) > MAX_ROWS_INSPECTED:
        raise Blocked("snapshot row inspection exceeds the hard ceiling")
    for row in rows:
        for value in row:
            if isinstance(value, str) and len(value.encode("utf-8")) > MAX_EXTRACTED_VALUE_BYTES:
                raise Blocked("snapshot text extraction exceeds the hard ceiling")
            if isinstance(value, bytes) and len(value) > MAX_EXTRACTED_VALUE_BYTES:
                raise Blocked("snapshot blob extraction exceeds the hard ceiling")
    return rows


def inspect_audit_chain(connection: sqlite3.Connection) -> dict[str, Any] | None:
    try:
        rows = bounded_rows(
            connection,
            "SELECT sequence, event_type, aggregate_type, aggregate_id, payload_digest, "
            "previous_hash, event_hash, observed_at FROM audit_events ORDER BY sequence",
        )
    except sqlite3.Error as exc:
        return {"reason": "audit rows are unreadable", "error_type": type(exc).__name__}
    previous = AUDIT_GENESIS
    for expected_sequence, row in enumerate(rows, start=1):
        if row["sequence"] != expected_sequence or row["previous_hash"] != previous:
            return {"reason": "audit sequence or linkage mismatch", "sequence": expected_sequence}
        if row["event_hash"] != audit_hash(row):
            return {"reason": "audit event hash mismatch", "sequence": expected_sequence}
        previous = row["event_hash"]
    return None


def inspect_state_event_consistency(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    try:
        states = bounded_rows(
            connection,
            "SELECT authorization_id, current_observer_state, version FROM authorization_state ORDER BY authorization_id",
        )
        events = bounded_rows(
            connection,
            "SELECT authorization_id, event_type, previous_observer_state, observer_state, state_version "
            "FROM authorization_events ORDER BY authorization_id, state_version",
        )
    except sqlite3.Error as exc:
        return [{"authorization_id": "unreadable", "reason": type(exc).__name__}]
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in events:
        grouped.setdefault(row["authorization_id"], []).append(row)
    inconsistencies: list[dict[str, Any]] = []
    state_ids = {row["authorization_id"] for row in states}
    for row in states:
        authorization_id = row["authorization_id"]
        history = grouped.get(authorization_id, [])
        expected_previous = "OBSERVED"
        for expected_version, event in enumerate(history, start=1):
            expected_type = "RESERVED" if expected_version == 1 else "CONSUMED" if expected_version == 2 else None
            if (
                event["state_version"] != expected_version
                or event["previous_observer_state"] != expected_previous
                or event["observer_state"] != event["event_type"]
                or event["event_type"] != expected_type
            ):
                inconsistencies.append({"authorization_id": authorization_id, "reason": "event chain mismatch"})
                break
            expected_previous = event["observer_state"]
        expected_state = history[-1]["observer_state"] if history else "OBSERVED"
        if row["version"] != len(history) or row["current_observer_state"] != expected_state:
            inconsistencies.append({"authorization_id": authorization_id, "reason": "current state disagrees with events"})
    for authorization_id in grouped.keys() - state_ids:
        inconsistencies.append({"authorization_id": authorization_id, "reason": "events lack current state row"})
    return inconsistencies


def inspect_connection(connection: sqlite3.Connection) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    quick_check = connection.execute("PRAGMA quick_check(1)").fetchone()
    integrity = str(quick_check[0]) if quick_check else "missing"
    if integrity != "ok":
        findings.append(make_finding(
            "SQLITE_INTEGRITY_FAILURE", "NON_REPAIRABLE_PRESERVE_AND_BLOCK",
            "STORE", "store:snapshot", "SQLite integrity verification did not pass.", integrity,
        ))

    user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if user_version != SUPPORTED_STORE_USER_VERSION:
        findings.append(make_finding(
            "UNSUPPORTED_USER_VERSION", "NON_REPAIRABLE_PRESERVE_AND_BLOCK",
            "STORE", "store:user-version", "Snapshot user_version is unsupported.", user_version,
        ))

    rows = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name LIMIT ?",
        (MAX_SCHEMA_OBJECTS + 1,),
    ).fetchall()
    if len(rows) > MAX_SCHEMA_OBJECTS:
        raise Blocked("snapshot schema-object count exceeds the hard ceiling")
    for row in rows:
        sql_text = row["sql"] or ""
        if len(sql_text.encode("utf-8")) > MAX_EXTRACTED_VALUE_BYTES:
            raise Blocked("snapshot schema text exceeds the hard ceiling")
    observed: dict[str, set[str]] = {"table": set(), "index": set(), "trigger": set()}
    unexpected: list[tuple[str, str]] = []
    for row in rows:
        kind = row["type"]
        name = row["name"]
        if kind in observed:
            observed[kind].add(name)
            if name not in EXPECTED_OBJECTS[kind]:
                unexpected.append((kind, name))
        else:
            unexpected.append((kind, name))

    for kind, expected_names in EXPECTED_OBJECTS.items():
        for name in sorted(expected_names - observed[kind]):
            if kind == "index":
                classification = "DETERMINISTIC_PLAN_CANDIDATE"
            elif kind == "trigger":
                classification = "MANUAL_DECISION_REQUIRED"
            else:
                classification = "NON_REPAIRABLE_PRESERVE_AND_BLOCK"
            code = f"MISSING_REQUIRED_{kind.upper()}"
            findings.append(make_finding(
                code, classification, kind.upper(), name,
                f"Canonical {kind} is absent from the supplied snapshot.", name,
            ))

    for kind, name in unexpected:
        opaque_reference = opaque_store_reference(name, kind)
        findings.append(make_finding(
            "UNEXPECTED_SCHEMA_OBJECT", "AMBIGUOUS_FAIL_CLOSED", "SCHEMA",
            opaque_reference,
            "Unexpected non-internal schema object is present.",
            {"kind": kind, "name_digest": sha256_bytes(name.encode("utf-8"))},
        ))

    for table, expected_columns in EXPECTED_COLUMNS.items():
        if table not in observed["table"]:
            continue
        quoted = table.replace('"', '""')
        columns = {row["name"] for row in connection.execute(f'PRAGMA table_info("{quoted}")').fetchall()}
        if columns != expected_columns:
            findings.append(make_finding(
                "TABLE_COLUMN_MISMATCH", "AMBIGUOUS_FAIL_CLOSED", "TABLE", table,
                "Canonical table-column set does not match.",
                {"observed_digest": sha256_document(sorted(columns)), "expected_digest": sha256_document(sorted(expected_columns))},
            ))

    metadata: dict[str, str] = {}
    if "store_metadata" in observed["table"] and not any(
        finding["code"] == "TABLE_COLUMN_MISMATCH" and finding["object_reference"] == "store_metadata"
        for finding in findings
    ):
        try:
            metadata_rows = bounded_rows(connection, "SELECT metadata_key, metadata_value FROM store_metadata ORDER BY metadata_key")
            metadata = {row["metadata_key"]: row["metadata_value"] for row in metadata_rows}
            for key, expected in EXPECTED_METADATA.items():
                if key not in metadata:
                    findings.append(make_finding(
                        "MISSING_STORE_METADATA", "MANUAL_DECISION_REQUIRED", "METADATA",
                        f"metadata:{key}", "Required store metadata is absent.", key,
                    ))
                elif metadata[key] != expected:
                    findings.append(make_finding(
                        "STORE_METADATA_MISMATCH", "MANUAL_DECISION_REQUIRED", "METADATA",
                        f"metadata:{key}", "Store metadata does not match the canonical value.",
                        {"key": key, "observed_digest": sha256_bytes(metadata[key].encode("utf-8"))},
                    ))
            for key in sorted(metadata.keys() - EXPECTED_METADATA.keys()):
                findings.append(make_finding(
                    "UNEXPECTED_STORE_METADATA", "AMBIGUOUS_FAIL_CLOSED", "METADATA",
                    opaque_store_reference(key, "metadata"),
                    "Unexpected store metadata is present.", sha256_bytes(key.encode("utf-8")),
                ))
        except sqlite3.Error as exc:
            findings.append(make_finding(
                "STORE_METADATA_UNREADABLE", "AMBIGUOUS_FAIL_CLOSED", "METADATA",
                "metadata:unreadable", "Store metadata cannot be read deterministically.", type(exc).__name__,
            ))

    if "audit_events" in observed["table"]:
        audit_problem = inspect_audit_chain(connection)
        if audit_problem:
            findings.append(make_finding(
                "AUDIT_CHAIN_INCONSISTENCY", "MANUAL_DECISION_REQUIRED", "AUDIT",
                "audit:chain", "Audit-chain inconsistency requires independent judgment.", audit_problem,
            ))

    if {"authorization_state", "authorization_events"}.issubset(observed["table"]):
        inconsistencies = inspect_state_event_consistency(connection)
        for item in inconsistencies[:MAX_SCHEMA_OBJECTS]:
            findings.append(make_finding(
                "STATE_EVENT_INCONSISTENCY", "MANUAL_DECISION_REQUIRED", "STATE_EVENT",
                opaque_store_reference(str(item["authorization_id"]), "state-event"),
                "Current observer state and append-only event evidence disagree.", item,
            ))

    findings.sort(key=lambda item: (item["code"], item["object_kind"], item["object_reference"]))
    return {
        "integrity_status": integrity,
        "observed_store_version": user_version,
        "observed_metadata_digest": sha256_document(metadata),
        "observed_schema_digest": sha256_document({key: sorted(value) for key, value in observed.items()}),
        "findings": findings,
    }


def make_snapshot_reference(
    observation: SnapshotObservation,
    logical_store_claim: str,
    observed_store_version: int,
    observed_at: str,
) -> dict[str, Any]:
    document = {
        "profile_version": SUPPORTED_PROFILE_VERSION,
        "contract_binding": {"contract_version": SUPPORTED_CONTRACT_VERSION},
        "object_type": "snapshot_reference",
        "snapshot_id": "snapshot:w3b-a:" + observation.digest.removeprefix("sha256:")[:24],
        "logical_store_claim": require_text(logical_store_claim, "logical_store_claim"),
        "physical_snapshot_path_observation": str(observation.path),
        "snapshot_digest": observation.digest,
        "snapshot_size": observation.size,
        "observed_store_version": observed_store_version,
        "canonical_w3a_schema_digest": "sha256:" + EXPECTED_CANONICAL_SQL_SHA256,
        "observed_at": require_text(observed_at, "observed_at"),
        "snapshot_status": "FROZEN_SUPPLIED",
        "identity_limitations": list(IDENTITY_LIMITATIONS),
        **non_authority_fields(),
    }
    validate_document("snapshot_reference", document)
    return document


def inspect_supplied_snapshot(
    snapshot_path: Path | str | None,
    permitted_root: Path | str | None,
    logical_store_claim: str,
    observed_at: str,
) -> dict[str, Any]:
    check_canonical_baseline()
    path = secure_snapshot_path(snapshot_path, permitted_root)
    source_descriptor = open_snapshot_descriptor(path)
    try:
        with tempfile.TemporaryDirectory(prefix="acos-w3b-a-inspection-") as temporary:
            image_path = Path(temporary) / "snapshot.sqlite"
            before, image_before = materialize_private_inspection_image(
                source_descriptor, path, image_path,
            )
            connection: sqlite3.Connection | None = None
            try:
                connection = open_snapshot_read_only(image_path)
                inspection = inspect_connection(connection)
            except sqlite3.DatabaseError as exc:
                raise Blocked(f"malformed or unreadable SQLite snapshot: {exc}") from exc
            finally:
                if connection is not None:
                    connection.close()
            image_after = observe_snapshot(image_path)
            if not same_snapshot(image_before, image_after):
                raise Blocked("private inspection image changed during bounded inspection")
        after = observe_snapshot_descriptor(source_descriptor, path)
        if not same_snapshot(before, after):
            raise Blocked("supplied snapshot changed during bounded inspection")
    finally:
        os.close(source_descriptor)
    current_path = secure_snapshot_path(path, permitted_root)
    current = observe_snapshot(current_path)
    if current_path != path or not same_snapshot(before, current):
        raise Blocked("supplied snapshot path binding changed during bounded inspection")
    snapshot_reference = make_snapshot_reference(
        before, logical_store_claim, inspection["observed_store_version"], observed_at,
    )
    return {"snapshot_reference": snapshot_reference, "inspection": inspection}


def build_evidence(inspection_data: Mapping[str, Any], evidence_id: str, created_at: str) -> dict[str, Any]:
    snapshot = inspection_data["snapshot_reference"]
    findings = list(inspection_data["inspection"]["findings"])
    document = {
        "profile_version": SUPPORTED_PROFILE_VERSION,
        "contract_binding": {"contract_version": SUPPORTED_CONTRACT_VERSION},
        "object_type": "repair_evidence",
        "evidence_id": require_text(evidence_id, "evidence_id"),
        "snapshot_digest": snapshot["snapshot_digest"],
        "snapshot_size": snapshot["snapshot_size"],
        "findings": findings,
        "created_at": require_text(created_at, "created_at"),
        **non_authority_fields(),
    }
    document["evidence_set_digest"] = digest_without(document, "evidence_set_digest")
    validate_document("repair_evidence", document)
    return document


def proposed_diff_for_findings(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    mapping = {
        "DETERMINISTIC_PLAN_CANDIDATE": (
            "DECLARE_CANONICAL_INDEX_GAP",
            "Declare a canonical index difference without applying a mutation.",
        ),
        "MANUAL_DECISION_REQUIRED": (
            "REQUEST_MANUAL_DECISION",
            "Preserve evidence and request an independent human governance decision.",
        ),
        "NON_REPAIRABLE_PRESERVE_AND_BLOCK": (
            "PRESERVE_AND_BLOCK",
            "Preserve the anomaly and block automated repair.",
        ),
        "AMBIGUOUS_FAIL_CLOSED": (
            "REPORT_AMBIGUITY",
            "Report ambiguity and fail closed without selecting a source of truth.",
        ),
    }
    proposed: list[dict[str, Any]] = []
    for finding in findings:
        classification = finding["classification"]
        action, rationale = mapping[classification]
        if action == "DECLARE_CANONICAL_INDEX_GAP" and finding["object_kind"] != "INDEX":
            raise Blocked("deterministic planning is restricted to canonical index gaps")
        proposed.append({
            "action": action,
            "subject": finding["object_reference"],
            "effect": NONE,
            "rationale": rationale,
        })
    return proposed


def build_plan(
    snapshot: Mapping[str, Any],
    evidence: Mapping[str, Any],
    plan_id: str,
    created_at: str,
) -> dict[str, Any]:
    classifications = sorted({item["classification"] for item in evidence["findings"]})
    document = {
        "profile_version": SUPPORTED_PROFILE_VERSION,
        "contract_binding": {"contract_version": SUPPORTED_CONTRACT_VERSION},
        "object_type": "repair_plan",
        "plan_id": require_text(plan_id, "plan_id"),
        "logical_store_claim": snapshot["logical_store_claim"],
        "snapshot_digest": snapshot["snapshot_digest"],
        "snapshot_size": snapshot["snapshot_size"],
        "observed_store_version": snapshot["observed_store_version"],
        "anomaly_classifications": classifications,
        "evidence_set_digest": evidence["evidence_set_digest"],
        "proposed_diff": proposed_diff_for_findings(evidence["findings"]),
        "expected_invariant_set": list(EXPECTED_INVARIANTS),
        "created_at": require_text(created_at, "created_at"),
        "plan_state": "PLANNED",
        **non_authority_fields(),
    }
    document["plan_digest"] = digest_without(document, "plan_digest")
    validate_document("repair_plan", document)
    return document


def verify_plan_documents(
    snapshot: Mapping[str, Any],
    evidence: Mapping[str, Any],
    plan: Mapping[str, Any],
    verification_id: str,
    verified_at: str,
) -> dict[str, Any]:
    validate_document("snapshot_reference", snapshot)
    validate_document("repair_evidence", evidence)
    validate_document("repair_plan", plan)
    if evidence["evidence_set_digest"] != digest_without(evidence, "evidence_set_digest"):
        raise Denied("evidence-set digest mismatch")
    if plan["plan_digest"] != digest_without(plan, "plan_digest"):
        raise Denied("repair-plan digest mismatch")
    if evidence["snapshot_digest"] != snapshot["snapshot_digest"] or plan["snapshot_digest"] != snapshot["snapshot_digest"]:
        raise Denied("wrong snapshot binding")
    if evidence["snapshot_size"] != snapshot["snapshot_size"] or plan["snapshot_size"] != snapshot["snapshot_size"]:
        raise Denied("wrong snapshot-size binding")
    if plan["evidence_set_digest"] != evidence["evidence_set_digest"]:
        raise Denied("wrong evidence-set binding")
    if plan["observed_store_version"] != snapshot["observed_store_version"]:
        raise Denied("wrong store-version binding")
    classifications = sorted({item["classification"] for item in evidence["findings"]})
    if plan["anomaly_classifications"] != classifications:
        raise Denied("plan classification set differs from evidence")
    if plan["proposed_diff"] != proposed_diff_for_findings(evidence["findings"]):
        raise Denied("proposed differences are not derived from trusted invariant rules")
    if plan["expected_invariant_set"] != EXPECTED_INVARIANTS:
        raise Denied("expected invariant set differs from the frozen W3B-A boundary")
    if any(item["action"] not in ALLOWED_DIFF_ACTIONS for item in plan["proposed_diff"]):
        raise Denied("unknown proposed-difference vocabulary")
    document = {
        "profile_version": SUPPORTED_PROFILE_VERSION,
        "contract_binding": {"contract_version": SUPPORTED_CONTRACT_VERSION},
        "object_type": "repair_plan_verification",
        "verification_id": require_text(verification_id, "verification_id"),
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "snapshot_digest": snapshot["snapshot_digest"],
        "evidence_set_digest": evidence["evidence_set_digest"],
        "verification_state": "PLAN_VERIFIED",
        "verified_at": require_text(verified_at, "verified_at"),
        "checks": [
            "SCHEMA_VALID", "PLAN_DIGEST_MATCH", "SNAPSHOT_BINDING_MATCH",
            "EVIDENCE_BINDING_MATCH", "VERSION_BINDING_MATCH",
            "PROPOSED_DIFF_VOCABULARY_VALID", "DESTRUCTIVE_PROPOSAL_ABSENT",
            "EXPECTED_INVARIANTS_VALID", "NON_AUTHORITY_TAINT_COMPLETE",
            "TERMINAL_STATE_PRESERVED",
        ],
        **non_authority_fields(),
    }
    validate_document("repair_plan_verification", document)
    return document


def run_operation(operation: str, callback: Callable[[], Any]) -> PlannerResult:
    try:
        return make_result(operation, PASS, "OPERATION_COMPLETED", "bounded W3B-A read-only operation completed", callback())
    except Denied as exc:
        return make_result(operation, DENY, "DECLARATIVE_VERIFICATION_DENIED", str(exc))
    except Blocked as exc:
        code = "CANONICAL_BASELINE_MISMATCH" if str(exc) == "CANONICAL_BASELINE_MISMATCH" else "OPERATION_BLOCKED"
        return make_result(operation, BLOCKED, code, str(exc))
    except sqlite3.Error as exc:
        return make_result(operation, BLOCKED, "SQLITE_BLOCKED", str(exc))
    except Exception as exc:
        return make_result(operation, BLOCKED, "UNEXPECTED_OPERATION_ERROR", str(exc))


def shadow_snapshot_inspect(
    snapshot_path: Path | str | None,
    permitted_root: Path | str | None,
    logical_store_claim: str,
    observed_at: str,
) -> PlannerResult:
    return run_operation(
        "shadow_snapshot_inspect",
        lambda: inspect_supplied_snapshot(snapshot_path, permitted_root, logical_store_claim, observed_at),
    )


def shadow_repair_inspect(
    snapshot_path: Path | str | None,
    permitted_root: Path | str | None,
    logical_store_claim: str,
    observed_at: str,
) -> PlannerResult:
    return run_operation(
        "shadow_repair_inspect",
        lambda: inspect_supplied_snapshot(snapshot_path, permitted_root, logical_store_claim, observed_at),
    )


def shadow_repair_plan(
    snapshot_path: Path | str | None,
    permitted_root: Path | str | None,
    logical_store_claim: str,
    evidence_id: str,
    plan_id: str,
    created_at: str,
) -> PlannerResult:
    def build() -> dict[str, Any]:
        inspection = inspect_supplied_snapshot(
            snapshot_path, permitted_root, logical_store_claim, created_at,
        )
        evidence = build_evidence(inspection, evidence_id, created_at)
        plan = build_plan(inspection["snapshot_reference"], evidence, plan_id, created_at)
        return {
            "snapshot_reference": inspection["snapshot_reference"],
            "repair_evidence": evidence,
            "repair_plan": plan,
        }

    return run_operation("shadow_repair_plan", build)


def shadow_repair_plan_verify(
    snapshot: Mapping[str, Any],
    evidence: Mapping[str, Any],
    plan: Mapping[str, Any],
    verification_id: str,
    verified_at: str,
) -> PlannerResult:
    return run_operation(
        "shadow_repair_plan_verify",
        lambda: verify_plan_documents(snapshot, evidence, plan, verification_id, verified_at),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ACOS W3B-A read-only repair planner shadow")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    def add_snapshot_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("--snapshot-path", required=True)
        command.add_argument("--snapshot-root", required=True)
        command.add_argument("--logical-store-claim", required=True)
        command.add_argument("--observed-at", required=True)

    for operation in ("shadow_snapshot_inspect", "shadow_repair_inspect"):
        add_snapshot_arguments(subparsers.add_parser(operation))

    plan = subparsers.add_parser("shadow_repair_plan")
    add_snapshot_arguments(plan)
    plan.add_argument("--evidence-id", required=True)
    plan.add_argument("--plan-id", required=True)

    verify = subparsers.add_parser("shadow_repair_plan_verify")
    verify.add_argument("--snapshot-reference", required=True)
    verify.add_argument("--repair-evidence", required=True)
    verify.add_argument("--repair-plan", required=True)
    verify.add_argument("--verification-id", required=True)
    verify.add_argument("--verified-at", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.operation in {"shadow_snapshot_inspect", "shadow_repair_inspect"}:
        function = shadow_snapshot_inspect if args.operation == "shadow_snapshot_inspect" else shadow_repair_inspect
        result = function(args.snapshot_path, args.snapshot_root, args.logical_store_claim, args.observed_at)
    elif args.operation == "shadow_repair_plan":
        result = shadow_repair_plan(
            args.snapshot_path, args.snapshot_root, args.logical_store_claim,
            args.evidence_id, args.plan_id, args.observed_at,
        )
    else:
        def verify_inputs() -> dict[str, Any]:
            snapshot = read_json(Path(args.snapshot_reference))
            evidence = read_json(Path(args.repair_evidence))
            plan = read_json(Path(args.repair_plan))
            return verify_plan_documents(
                snapshot, evidence, plan, args.verification_id, args.verified_at,
            )

        result = run_operation(args.operation, verify_inputs)
    print(json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if result.result == PASS else 2 if result.result == DENY else 3


if __name__ == "__main__":
    raise SystemExit(main())

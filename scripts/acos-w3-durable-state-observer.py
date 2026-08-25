#!/usr/bin/env python3
"""ACOS W3A local durable-state observer.

This module is SHADOW, NON-PRODUCTION, OBSERVER-ONLY, NON-AUTHORIZING,
and NON-ACTIVATING. It records bounded observations and never grants
permission to execute or enacts a governance transition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

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
SUPPORTED_PROFILE_VERSION = "1.0"
SUPPORTED_CONTRACT_VERSION = "2.0"
SUPPORTED_STORE_VERSION = "1.0"
GOVERNANCE_STATUS = "UNAUTHENTICATED_SHADOW"
NONE = "NONE"
MIN_BUSY_TIMEOUT_MS = 5000
OBSERVER_OPERATIONS = {"shadow_observe", "shadow_reserve", "shadow_consume"}
CLAIMED_STATES = {
    "DEFINED", "ISSUED", "VALIDATED", "ACTIVE", "CONSUMED",
    "DENIED", "REVOKED", "EXPIRED", "SUPERSEDED", "FAILED",
}
OBSERVER_STATES = {
    "OBSERVED", "RESERVED", "CONSUMED", "REVOKED", "EXPIRED",
    "SUPERSEDED", "CONFLICTED",
}
ALLOWED_WORKFLOW_EDGES = {
    ("DRAFT", "TASK_DEFINED"),
    ("TASK_DEFINED", "TASK_MATERIALIZED"),
    ("TASK_MATERIALIZED", "TASK_READY"),
    ("TASK_READY", "TASK_EXECUTING"),
    ("TASK_EXECUTING", "TASK_RESULT"),
    ("TASK_RESULT", "TASK_REVIEW"),
    ("TASK_REVIEW", "TASK_DECISION"),
    ("TASK_DECISION", "TASK_CLOSED"),
}
W2_REQUIRED_TAINT = {
    "governance_status": GOVERNANCE_STATUS,
    "authority_effect": NONE,
    "identity_effect": NONE,
    "execution_effect": NONE,
    "activation_effect": NONE,
    "eligible_for_execution": False,
}
NOTICE = (
    "W3A records shadow observations only. PASS, RESERVED, and CONSUMED do not "
    "confer authority, permission to execute, governance transition, Activation, "
    "or Operational Entry."
)
AUDIT_LIMITATION = (
    "Hash Chain != Signature; Hash Chain != Authenticated Producer; "
    "Hash Chain != Nonrepudiation; Hash Chain != Trust Anchor; "
    "Hash Chain != Host-Compromise Resistance."
)
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RFC3339_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "fixtures" / "schemas" / "w3" / "1.0"
STORE_SCHEMA_PATH = ROOT / "fixtures" / "state-store-w3" / "1.0" / "state-store.sql"
SCHEMA_PATHS = {
    "grant_observation": SCHEMA_ROOT / "grant-observation.schema.json",
    "authorization_state_event": SCHEMA_ROOT / "authorization-state-event.schema.json",
    "workflow_state_event": SCHEMA_ROOT / "workflow-state-event.schema.json",
    "audit_event": SCHEMA_ROOT / "audit-event.schema.json",
}
REQUIRED_STORE_OBJECTS = {
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


class Blocked(RuntimeError):
    """Required bounded evidence or safe local operation is unavailable."""


class Denied(RuntimeError):
    """A supplied claim or state transition contradicts the frozen model."""


@dataclass(frozen=True)
class ObserverResult:
    operation: str
    result: str
    reason_code: str
    reason: str
    governance_status: str = GOVERNANCE_STATUS
    authority_effect: str = NONE
    identity_effect: str = NONE
    execution_effect: str = NONE
    activation_effect: str = NONE
    eligible_for_execution: bool = False
    notice: str = NOTICE
    audit_limitation: str = AUDIT_LIMITATION


def make_result(operation: str, result: str, reason_code: str, reason: str) -> ObserverResult:
    return ObserverResult(operation=operation, result=result, reason_code=reason_code, reason=reason)


def is_rfc3339_datetime(value: object) -> bool:
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        return False
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.tzinfo is not None


if FormatChecker is not None:
    FORMAT_CHECKER = FormatChecker()
    FORMAT_CHECKER.checks("date-time", raises=ValueError)(is_rfc3339_datetime)
else:
    FORMAT_CHECKER = None


def require_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Blocked(f"missing or invalid {label}")
    return value.strip()


def require_digest(value: object, label: str) -> str:
    digest = require_text(value, label)
    if not DIGEST_RE.fullmatch(digest):
        raise Denied(f"{label} must be a lowercase sha256 digest")
    return digest


def require_timestamp(value: object, label: str) -> str:
    timestamp = require_text(value, label)
    if not is_rfc3339_datetime(timestamp):
        raise Denied(f"{label} must be an RFC3339 date-time")
    return timestamp


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_request_digest(value: Any) -> str:
    return sha256_text(canonical_json(value))


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Blocked(f"unable to read JSON input: {exc}") from exc


def load_schema(kind: str) -> Draft7Validator:
    if kind not in SCHEMA_PATHS:
        raise Blocked(f"unknown W3A schema kind: {kind}")
    if jsonschema is None or Draft7Validator is None or FORMAT_CHECKER is None:
        detail = f": {JSONSCHEMA_IMPORT_ERROR}" if JSONSCHEMA_IMPORT_ERROR else ""
        raise Blocked(f"jsonschema dependency unavailable{detail}")
    try:
        schema = json.loads(SCHEMA_PATHS[kind].read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
    except (OSError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        raise Blocked(f"invalid or unavailable W3A schema for {kind}: {exc}") from exc
    return Draft7Validator(schema, format_checker=FORMAT_CHECKER)


def validate_document_or_raise(kind: str, document: Mapping[str, Any]) -> None:
    if not isinstance(document, dict):
        raise Blocked("W3A document root must be an object")
    validator = load_schema(kind)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        raise Denied(f"W3A {kind} schema validation failed: {errors[0].message}")
    if document.get("profile_version") != SUPPORTED_PROFILE_VERSION:
        raise Denied("unsupported W3 auxiliary version; no fallback or downgrade")
    binding = document.get("contract_binding")
    if not isinstance(binding, dict) or binding.get("contract_version") != SUPPORTED_CONTRACT_VERSION:
        raise Denied("unsupported ACOS Contract binding; Contract 2.1 is not implied")


def validate_shadow_document(kind: str, document: Mapping[str, Any]) -> ObserverResult:
    try:
        validate_document_or_raise(kind, document)
        return make_result("shadow_observe", PASS, "SCHEMA_VALID", f"valid W3A {kind} shadow document")
    except Denied as exc:
        return make_result("shadow_observe", DENY, "SCHEMA_DENIED", str(exc))
    except Blocked as exc:
        return make_result("shadow_observe", BLOCKED, "SCHEMA_BLOCKED", str(exc))


def validate_w2_shadow_result(document: Mapping[str, Any]) -> ObserverResult:
    operation = "shadow_observe"
    if not isinstance(document, dict):
        return make_result(operation, BLOCKED, "W2_TAINT_MISSING", "W2 result must be an object")
    if document.get("result") != PASS:
        return make_result(operation, DENY, "W2_RESULT_NOT_PASS", "only a complete W2 PASS may be observed")
    missing = [key for key in W2_REQUIRED_TAINT if key not in document]
    if missing:
        return make_result(operation, BLOCKED, "W2_TAINT_MISSING", f"missing W2 taint: {', '.join(missing)}")
    for key in ("authority_effect", "execution_effect", "activation_effect"):
        if document.get(key) != NONE:
            return make_result(operation, DENY, "W2_AUTHORITY_LAUNDERING", f"W2 {key} must remain NONE")
    if document.get("eligible_for_execution") is not False:
        return make_result(operation, DENY, "W2_EXECUTION_ELIGIBILITY", "W2 result must remain ineligible for execution")
    if document.get("governance_status") != GOVERNANCE_STATUS:
        return make_result(operation, DENY, "W2_GOVERNANCE_STATUS", "W2 governance status must remain UNAUTHENTICATED_SHADOW")
    if document.get("identity_effect") != NONE:
        return make_result(operation, DENY, "W2_IDENTITY_EFFECT", "W2 identity_effect must remain NONE")
    return make_result(operation, PASS, "W2_SHADOW_OBSERVABLE", "complete W2 shadow result may be observed only")


def secure_state_path(state_path: Path | str | None, permitted_root: Path | str | None) -> Path:
    if state_path is None:
        raise Blocked("explicit --state-path is required")
    if permitted_root is None:
        raise Blocked("explicit permitted state root is required")
    raw_root = Path(permitted_root).expanduser()
    if raw_root.is_symlink():
        raise Blocked("permitted state root must not be a symbolic link")
    try:
        root = raw_root.resolve(strict=True)
    except OSError as exc:
        raise Blocked(f"unable to resolve permitted state root: {exc}") from exc
    if not root.is_dir():
        raise Blocked("permitted state root must be a directory")

    raw = Path(state_path).expanduser()
    if ".." in raw.parts:
        raise Blocked("state path contains parent traversal")
    lexical_root = Path(os.path.abspath(raw_root))
    lexical_candidate = Path(os.path.abspath(raw if raw.is_absolute() else lexical_root / raw))
    try:
        relative = lexical_candidate.relative_to(lexical_root)
    except ValueError as exc:
        try:
            resolved_parent = lexical_candidate.parent.resolve(strict=True)
            relative_parent = resolved_parent.relative_to(root)
        except (OSError, ValueError) as nested:
            raise Blocked("state path is outside the permitted local root") from nested
        relative = relative_parent / lexical_candidate.name
    if not relative.parts:
        raise Blocked("state path must name a database file")

    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise Blocked("state path contains a symbolic-link parent")
        if not current.exists() or not current.is_dir():
            raise Blocked("state path parent topology is unresolved or unsafe")
    target = current / relative.parts[-1]
    if target.is_symlink():
        raise Blocked("state path target must not be a symbolic link")
    if target.exists() and not target.is_file():
        raise Blocked("state path target must be a regular file")
    try:
        current.resolve(strict=True).relative_to(root)
        if target.exists():
            target.resolve(strict=True).relative_to(root)
    except (OSError, ValueError) as exc:
        raise Blocked(f"unsafe state path topology: {exc}") from exc
    return target


def audit_hash(
    previous_hash: str,
    sequence: int,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload_digest: str,
    observed_at: str,
) -> str:
    value = canonical_json({
        "aggregate_id": aggregate_id,
        "aggregate_type": aggregate_type,
        "event_type": event_type,
        "observed_at": observed_at,
        "payload_digest": payload_digest,
        "previous_hash": previous_hash,
        "sequence": sequence,
    })
    return sha256_text(value)


class StateStore:
    def __init__(
        self,
        state_path: Path | str | None,
        permitted_root: Path | str | None,
        *,
        busy_timeout_ms: int = MIN_BUSY_TIMEOUT_MS,
    ) -> None:
        if busy_timeout_ms < MIN_BUSY_TIMEOUT_MS:
            raise Blocked(f"busy_timeout must be at least {MIN_BUSY_TIMEOUT_MS}ms")
        self.busy_timeout_ms = busy_timeout_ms
        self.state_path = secure_state_path(state_path, permitted_root)
        store_existed_before_open = self.state_path.exists()
        self.connection: sqlite3.Connection | None = None
        try:
            self.connection = sqlite3.connect(
                str(self.state_path),
                timeout=busy_timeout_ms / 1000,
                isolation_level=None,
            )
            self.connection.row_factory = sqlite3.Row
            if self.state_path.is_symlink():
                raise Blocked("state path became a symbolic link during open")
            os.chmod(self.state_path, 0o600)
            self._configure_and_verify_connection()
            if not store_existed_before_open:
                self._initialize_store()
            self.verify_store()
        except Blocked:
            self.close()
            raise
        except (OSError, sqlite3.Error) as exc:
            self.close()
            raise Blocked(f"unable to establish W3A durable store: {exc}") from exc
        except Exception as exc:
            self.close()
            raise Blocked(f"unexpected W3A durable-store failure: {exc}") from exc

    def __enter__(self) -> "StateStore":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @property
    def db(self) -> sqlite3.Connection:
        if self.connection is None:
            raise Blocked("W3A state store is closed")
        return self.connection

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def _configure_and_verify_connection(self) -> None:
        db = self.db
        journal = str(db.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        synchronous = int(db.execute("PRAGMA synchronous").fetchone()[0])
        foreign_keys = int(db.execute("PRAGMA foreign_keys").fetchone()[0])
        busy_timeout = int(db.execute("PRAGMA busy_timeout").fetchone()[0])
        if journal != "wal":
            raise Blocked("effective journal_mode is not WAL")
        if synchronous != 2:
            raise Blocked("effective synchronous mode is not FULL")
        if foreign_keys != 1:
            raise Blocked("effective foreign_keys setting is not ON")
        if busy_timeout < MIN_BUSY_TIMEOUT_MS:
            raise Blocked("effective busy_timeout is below 5000ms")

    def pragma_state(self) -> dict[str, Any]:
        return {
            "journal_mode": str(self.db.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
            "synchronous": int(self.db.execute("PRAGMA synchronous").fetchone()[0]),
            "foreign_keys": int(self.db.execute("PRAGMA foreign_keys").fetchone()[0]),
            "busy_timeout": int(self.db.execute("PRAGMA busy_timeout").fetchone()[0]),
        }

    def _initialize_store(self) -> None:
        try:
            sql = STORE_SCHEMA_PATH.read_text(encoding="utf-8")
            self.db.executescript(sql)
        except (OSError, sqlite3.Error) as exc:
            raise Blocked(f"unable to initialize W3A state-store schema: {exc}") from exc

    def verify_store(self) -> None:
        try:
            integrity = self.db.execute("PRAGMA quick_check").fetchone()[0]
            if integrity != "ok":
                raise Blocked(f"SQLite bounded integrity check failed: {integrity}")
            user_version = int(self.db.execute("PRAGMA user_version").fetchone()[0])
            if user_version != 100:
                raise Blocked(f"unsupported W3A SQLite user_version: {user_version}")
            objects = self.db.execute(
                "SELECT type, name FROM sqlite_master "
                "WHERE type IN ('table', 'index', 'trigger')"
            ).fetchall()
            available = {(str(row["type"]), str(row["name"])) for row in objects}
            missing = [
                f"{object_type}:{name}"
                for object_type, names in REQUIRED_STORE_OBJECTS.items()
                for name in sorted(names)
                if (object_type, name) not in available
            ]
            if missing:
                raise Blocked(f"missing required W3A store objects: {', '.join(missing)}")
            metadata = dict(self.db.execute("SELECT metadata_key, metadata_value FROM store_metadata"))
        except sqlite3.Error as exc:
            raise Blocked(f"unable to verify W3A store: {exc}") from exc
        expected = {
            "state_store_version": SUPPORTED_STORE_VERSION,
            "w3_profile_version": SUPPORTED_PROFILE_VERSION,
            "acos_contract_version": SUPPORTED_CONTRACT_VERSION,
            "governance_status": GOVERNANCE_STATUS,
        }
        if metadata != expected:
            raise Blocked(f"unsupported or inconsistent W3A store metadata: {metadata}")
        self.verify_audit_chain()

    def verify_audit_chain(self) -> None:
        previous = "GENESIS"
        expected_sequence = 1
        try:
            rows = self.db.execute(
                "SELECT sequence, event_type, aggregate_type, aggregate_id, payload_digest, "
                "previous_hash, event_hash, observed_at FROM audit_events ORDER BY sequence"
            ).fetchall()
        except sqlite3.Error as exc:
            raise Blocked(f"unable to read W3A audit chain: {exc}") from exc
        for row in rows:
            if row["sequence"] != expected_sequence or row["previous_hash"] != previous:
                raise Blocked("W3A audit-chain sequence or linkage is inconsistent")
            computed = audit_hash(
                previous,
                row["sequence"],
                row["event_type"],
                row["aggregate_type"],
                row["aggregate_id"],
                row["payload_digest"],
                row["observed_at"],
            )
            if row["event_hash"] != computed:
                raise Blocked("W3A audit-chain hash is inconsistent")
            previous = computed
            expected_sequence += 1

    def _begin_immediate(self) -> None:
        self.db.execute("BEGIN IMMEDIATE")

    def _rollback(self) -> None:
        if self.db.in_transaction:
            self.db.execute("ROLLBACK")

    def _commit(self) -> None:
        self.db.execute("COMMIT")

    def _event_id(self, event_type: str, authorization_id: str, operation_id: str) -> str:
        digest = hashlib.sha256(f"{event_type}|{authorization_id}|{operation_id}".encode("utf-8")).hexdigest()
        return f"event:w3:{digest[:32]}"

    def _append_audit(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: Mapping[str, Any],
        observed_at: str,
    ) -> None:
        row = self.db.execute(
            "SELECT sequence, event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        sequence = int(row["sequence"]) + 1 if row else 1
        previous = str(row["event_hash"]) if row else "GENESIS"
        payload_digest = sha256_text(canonical_json(payload))
        event_hash = audit_hash(
            previous, sequence, event_type, aggregate_type, aggregate_id,
            payload_digest, observed_at,
        )
        self.db.execute(
            "INSERT INTO audit_events (sequence, audit_event_id, event_type, aggregate_type, "
            "aggregate_id, payload_digest, previous_hash, event_hash, observed_at, "
            "governance_status, authority_effect, identity_effect, execution_effect, "
            "activation_effect, eligible_for_execution) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sequence, f"audit:w3:{sequence:020d}", event_type, aggregate_type,
                aggregate_id, payload_digest, previous, event_hash, observed_at,
                GOVERNANCE_STATUS, NONE, NONE, NONE, NONE, 0,
            ),
        )

    def _run_mutation(self, operation: str, callback: Callable[[], ObserverResult]) -> ObserverResult:
        try:
            self._begin_immediate()
            result = callback()
            self._commit()
            return result
        except Denied as exc:
            self._rollback()
            return make_result(operation, DENY, "STATE_CONFLICT", str(exc))
        except Blocked as exc:
            self._rollback()
            return make_result(operation, BLOCKED, "OPERATION_BLOCKED", str(exc))
        except sqlite3.IntegrityError as exc:
            self._rollback()
            return make_result(operation, BLOCKED, "SQLITE_INTEGRITY_BLOCKED", str(exc))
        except sqlite3.OperationalError as exc:
            self._rollback()
            reason = str(exc)
            code = "SQLITE_BUSY" if "locked" in reason.lower() or "busy" in reason.lower() else "SQLITE_OPERATION_BLOCKED"
            return make_result(operation, BLOCKED, code, reason)
        except sqlite3.Error as exc:
            self._rollback()
            return make_result(operation, BLOCKED, "SQLITE_BLOCKED", str(exc))
        except Exception as exc:
            self._rollback()
            return make_result(operation, BLOCKED, "UNEXPECTED_OPERATION_ERROR", str(exc))

    def _run_public_operation(
        self,
        operation: str,
        callback: Callable[[], ObserverResult],
    ) -> ObserverResult:
        try:
            return callback()
        except Denied as exc:
            return make_result(operation, DENY, "OPERATION_DENIED", str(exc))
        except Blocked as exc:
            return make_result(operation, BLOCKED, "OPERATION_BLOCKED", str(exc))
        except sqlite3.Error as exc:
            return make_result(operation, BLOCKED, "SQLITE_BLOCKED", str(exc))
        except Exception as exc:
            return make_result(operation, BLOCKED, "UNEXPECTED_OPERATION_ERROR", str(exc))

    def shadow_observe(self, kind: str, document: Mapping[str, Any]) -> ObserverResult:
        return self._run_public_operation(
            "shadow_observe",
            lambda: self._shadow_observe(kind, document),
        )

    def _shadow_observe(self, kind: str, document: Mapping[str, Any]) -> ObserverResult:
        if kind == "grant_observation":
            return self._observe_grant(document)
        if kind == "workflow_state_event":
            return self._observe_workflow(document)
        if kind == "w2_shadow_result":
            return self._observe_w2(document)
        return make_result("shadow_observe", BLOCKED, "UNKNOWN_OBSERVATION_KIND", f"unknown observation kind: {kind}")

    def _observe_grant(self, document: Mapping[str, Any]) -> ObserverResult:
        try:
            validate_document_or_raise("grant_observation", document)
        except Denied as exc:
            return make_result("shadow_observe", DENY, "SCHEMA_DENIED", str(exc))
        except Blocked as exc:
            return make_result("shadow_observe", BLOCKED, "SCHEMA_BLOCKED", str(exc))

        def mutate() -> ObserverResult:
            existing = self.db.execute(
                "SELECT 1 FROM grant_observations WHERE observation_id = ?",
                (document["observation_id"],),
            ).fetchone()
            if existing:
                raise Denied("grant observation identifier already exists")
            self.db.execute(
                "INSERT INTO grant_observations (observation_id, grant_id, claimed_governance_state, "
                "observer_state, source_reference, observed_at, claim_status, governance_status, "
                "authority_effect, identity_effect, execution_effect, activation_effect, "
                "eligible_for_execution) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    document["observation_id"], document["grant_id"], document["claimed_governance_state"],
                    document["observer_state"], document["source_reference"], document["observed_at"],
                    document["claim_status"], GOVERNANCE_STATUS, NONE, NONE, NONE, NONE, 0,
                ),
            )
            self._append_audit(
                "shadow.observe.grant", "GRANT_OBSERVATION", document["observation_id"],
                document, document["observed_at"],
            )
            return make_result("shadow_observe", PASS, "GRANT_OBSERVED", "Grant claim recorded as a non-authorizing observation")

        return self._run_mutation("shadow_observe", mutate)

    def _observe_workflow(self, document: Mapping[str, Any]) -> ObserverResult:
        try:
            validate_document_or_raise("workflow_state_event", document)
            edge = (document["observed_from_state"], document["observed_to_state"])
            if edge not in ALLOWED_WORKFLOW_EDGES:
                raise Denied(f"invalid observed workflow edge: {edge[0]} -> {edge[1]}")
        except Denied as exc:
            return make_result("shadow_observe", DENY, "WORKFLOW_EDGE_DENIED", str(exc))
        except Blocked as exc:
            return make_result("shadow_observe", BLOCKED, "SCHEMA_BLOCKED", str(exc))

        def mutate() -> ObserverResult:
            self.db.execute(
                "INSERT INTO workflow_state_events (workflow_event_id, task_id, observed_from_state, "
                "observed_to_state, observer_state, source_reference, observed_at, governance_status, "
                "authority_effect, identity_effect, execution_effect, activation_effect, "
                "eligible_for_execution) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    document["workflow_event_id"], document["task_id"], document["observed_from_state"],
                    document["observed_to_state"], document["observer_state"], document["source_reference"],
                    document["observed_at"], GOVERNANCE_STATUS, NONE, NONE, NONE, NONE, 0,
                ),
            )
            self._append_audit(
                "shadow.observe.workflow", "WORKFLOW_OBSERVATION", document["workflow_event_id"],
                document, document["observed_at"],
            )
            return make_result("shadow_observe", PASS, "WORKFLOW_EDGE_OBSERVED", "workflow edge recorded; no governance transition enacted")

        return self._run_mutation("shadow_observe", mutate)

    def _observe_w2(self, document: Mapping[str, Any]) -> ObserverResult:
        validation = validate_w2_shadow_result(document)
        if validation.result != PASS:
            return validation
        case_id = require_text(document.get("case_id", "w2-shadow-result"), "W2 case_id")
        observed_at = require_timestamp(document.get("observed_at"), "W2 observed_at")

        def mutate() -> ObserverResult:
            self._append_audit(
                "shadow.observe.w2", "W2_SHADOW_OBSERVATION", case_id,
                document, observed_at,
            )
            return make_result("shadow_observe", PASS, "W2_SHADOW_OBSERVED", "complete W2 shadow boundary recorded without authority upgrade")

        return self._run_mutation("shadow_observe", mutate)

    def _replay_status(
        self,
        authorization_id: str,
        operation_id: str,
        nonce: str,
        digest: str,
        event_type: str,
    ) -> bool:
        by_operation = self.db.execute(
            "SELECT operation_id, nonce, canonical_request_digest, event_type FROM authorization_events "
            "WHERE authorization_id = ? AND operation_id = ?",
            (authorization_id, operation_id),
        ).fetchone()
        if by_operation:
            if (
                by_operation["nonce"] == nonce
                and by_operation["canonical_request_digest"] == digest
                and by_operation["event_type"] == event_type
            ):
                return True
            raise Denied("operation replay binding differs in nonce, digest, or event type")
        by_nonce = self.db.execute(
            "SELECT operation_id, canonical_request_digest, event_type FROM authorization_events "
            "WHERE authorization_id = ? AND nonce = ?",
            (authorization_id, nonce),
        ).fetchone()
        if by_nonce:
            raise Denied("authorization-scoped nonce was already bound to another operation or digest")
        return False

    def shadow_reserve(
        self,
        *,
        authorization_id: str,
        operation_id: str,
        nonce: str,
        canonical_request_digest: str,
        claimed_governance_state: str,
        observed_at: str,
        expected_version: int = 0,
    ) -> ObserverResult:
        return self._run_public_operation(
            "shadow_reserve",
            lambda: self._shadow_reserve(
                authorization_id=authorization_id,
                operation_id=operation_id,
                nonce=nonce,
                canonical_request_digest=canonical_request_digest,
                claimed_governance_state=claimed_governance_state,
                observed_at=observed_at,
                expected_version=expected_version,
            ),
        )

    def _shadow_reserve(
        self,
        *,
        authorization_id: str,
        operation_id: str,
        nonce: str,
        canonical_request_digest: str,
        claimed_governance_state: str,
        observed_at: str,
        expected_version: int = 0,
    ) -> ObserverResult:
        operation = "shadow_reserve"
        try:
            authorization_id = require_text(authorization_id, "authorization_id")
            operation_id = require_text(operation_id, "operation_id")
            nonce = require_text(nonce, "nonce")
            digest = require_digest(canonical_request_digest, "canonical_request_digest")
            observed_at = require_timestamp(observed_at, "observed_at")
            if claimed_governance_state not in CLAIMED_STATES:
                raise Denied("unknown claimed governance state")
            if expected_version < 0:
                raise Denied("expected_version must be non-negative")
        except Denied as exc:
            return make_result(operation, DENY, "INPUT_DENIED", str(exc))
        except Blocked as exc:
            return make_result(operation, BLOCKED, "INPUT_BLOCKED", str(exc))

        def mutate() -> ObserverResult:
            if self._replay_status(authorization_id, operation_id, nonce, digest, "RESERVED"):
                return make_result(operation, PASS, "IDEMPOTENT_REPLAY", "exact four-component replay; no second state effect")
            row = self.db.execute(
                "SELECT current_observer_state, version FROM authorization_state WHERE authorization_id = ?",
                (authorization_id,),
            ).fetchone()
            if row is None:
                self.db.execute(
                    "INSERT INTO authorization_state (authorization_id, claimed_governance_state, "
                    "current_observer_state, version, created_at, updated_at, governance_status, "
                    "authority_effect, identity_effect, execution_effect, activation_effect, "
                    "eligible_for_execution) VALUES (?, ?, 'OBSERVED', 0, ?, ?, ?, ?, ?, ?, ?, 0)",
                    (authorization_id, claimed_governance_state, observed_at, observed_at, GOVERNANCE_STATUS, NONE, NONE, NONE, NONE),
                )
            cursor = self.db.execute(
                "UPDATE authorization_state SET current_observer_state = 'RESERVED', version = version + 1, "
                "updated_at = ? WHERE authorization_id = ? AND current_observer_state = 'OBSERVED' AND version = ?",
                (observed_at, authorization_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise Denied("reservation state or optimistic version conflict; affected_rows != 1")
            new_version = expected_version + 1
            event_id = self._event_id("RESERVED", authorization_id, operation_id)
            self.db.execute(
                "INSERT INTO authorization_events (event_id, authorization_id, operation_id, nonce, "
                "canonical_request_digest, event_type, previous_observer_state, observer_state, "
                "state_version, observed_at, governance_status, authority_effect, identity_effect, "
                "execution_effect, activation_effect, eligible_for_execution) "
                "VALUES (?, ?, ?, ?, ?, 'RESERVED', 'OBSERVED', 'RESERVED', ?, ?, ?, ?, ?, ?, ?, 0)",
                (event_id, authorization_id, operation_id, nonce, digest, new_version, observed_at, GOVERNANCE_STATUS, NONE, NONE, NONE, NONE),
            )
            self._append_audit(
                "shadow.reserve", "AUTHORIZATION_OBSERVATION", authorization_id,
                {"authorization_id": authorization_id, "operation_id": operation_id, "nonce": nonce, "canonical_request_digest": digest, "state_version": new_version},
                observed_at,
            )
            return make_result(operation, PASS, "RESERVATION_OBSERVED", "reservation observation recorded; permission to execute was not granted")

        return self._run_mutation(operation, mutate)

    def shadow_consume(
        self,
        *,
        authorization_id: str,
        operation_id: str,
        nonce: str,
        canonical_request_digest: str,
        observed_at: str,
        expected_version: int,
    ) -> ObserverResult:
        return self._run_public_operation(
            "shadow_consume",
            lambda: self._shadow_consume(
                authorization_id=authorization_id,
                operation_id=operation_id,
                nonce=nonce,
                canonical_request_digest=canonical_request_digest,
                observed_at=observed_at,
                expected_version=expected_version,
            ),
        )

    def _shadow_consume(
        self,
        *,
        authorization_id: str,
        operation_id: str,
        nonce: str,
        canonical_request_digest: str,
        observed_at: str,
        expected_version: int,
    ) -> ObserverResult:
        operation = "shadow_consume"
        try:
            authorization_id = require_text(authorization_id, "authorization_id")
            operation_id = require_text(operation_id, "operation_id")
            nonce = require_text(nonce, "nonce")
            digest = require_digest(canonical_request_digest, "canonical_request_digest")
            observed_at = require_timestamp(observed_at, "observed_at")
            if expected_version < 0:
                raise Denied("expected_version must be non-negative")
        except Denied as exc:
            return make_result(operation, DENY, "INPUT_DENIED", str(exc))
        except Blocked as exc:
            return make_result(operation, BLOCKED, "INPUT_BLOCKED", str(exc))

        def mutate() -> ObserverResult:
            if self._replay_status(authorization_id, operation_id, nonce, digest, "CONSUMED"):
                return make_result(operation, PASS, "IDEMPOTENT_REPLAY", "exact four-component replay; no second state effect")
            cursor = self.db.execute(
                "UPDATE authorization_state SET current_observer_state = 'CONSUMED', "
                "version = version + 1, updated_at = ? WHERE authorization_id = ? "
                "AND current_observer_state = 'RESERVED' AND version = ?",
                (observed_at, authorization_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise Denied("consumption state or optimistic version conflict; affected_rows != 1")
            new_version = expected_version + 1
            event_id = self._event_id("CONSUMED", authorization_id, operation_id)
            self.db.execute(
                "INSERT INTO authorization_events (event_id, authorization_id, operation_id, nonce, "
                "canonical_request_digest, event_type, previous_observer_state, observer_state, "
                "state_version, observed_at, governance_status, authority_effect, identity_effect, "
                "execution_effect, activation_effect, eligible_for_execution) "
                "VALUES (?, ?, ?, ?, ?, 'CONSUMED', 'RESERVED', 'CONSUMED', ?, ?, ?, ?, ?, ?, ?, 0)",
                (event_id, authorization_id, operation_id, nonce, digest, new_version, observed_at, GOVERNANCE_STATUS, NONE, NONE, NONE, NONE),
            )
            self._append_audit(
                "shadow.consume", "AUTHORIZATION_OBSERVATION", authorization_id,
                {"authorization_id": authorization_id, "operation_id": operation_id, "nonce": nonce, "canonical_request_digest": digest, "state_version": new_version},
                observed_at,
            )
            return make_result(operation, PASS, "CONSUMPTION_OBSERVED", "consumption recorded; execution was not authorized")

        return self._run_mutation(operation, mutate)

    def authorization_state(self, authorization_id: str) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM authorization_state WHERE authorization_id = ?",
            (authorization_id,),
        ).fetchone()

    def count_rows(self, table: str) -> int:
        if table not in {
            "grant_observations", "authorization_state", "authorization_events",
            "workflow_state_events", "audit_events",
        }:
            raise Blocked("unsupported count target")
        return int(self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-path", required=True, help="explicit SQLite state path")
    parser.add_argument("--state-root", required=True, help="explicit permitted local root")
    subparsers = parser.add_subparsers(dest="operation", required=True)

    observe = subparsers.add_parser("shadow_observe")
    observe.add_argument("--kind", required=True, choices=["grant_observation", "workflow_state_event", "w2_shadow_result"])
    observe.add_argument("--input", required=True, type=Path)

    reserve = subparsers.add_parser("shadow_reserve")
    reserve.add_argument("--authorization-id", required=True)
    reserve.add_argument("--operation-id", required=True)
    reserve.add_argument("--nonce", required=True)
    reserve.add_argument("--canonical-request-digest", required=True)
    reserve.add_argument("--claimed-governance-state", required=True)
    reserve.add_argument("--observed-at", required=True)
    reserve.add_argument("--expected-version", type=int, default=0)

    consume = subparsers.add_parser("shadow_consume")
    consume.add_argument("--authorization-id", required=True)
    consume.add_argument("--operation-id", required=True)
    consume.add_argument("--nonce", required=True)
    consume.add_argument("--canonical-request-digest", required=True)
    consume.add_argument("--observed-at", required=True)
    consume.add_argument("--expected-version", required=True, type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = StateStore(args.state_path, args.state_root)
    except Blocked as exc:
        result = make_result(getattr(args, "operation", "shadow_observe"), BLOCKED, "STORE_BLOCKED", str(exc))
    else:
        with store:
            if args.operation == "shadow_observe":
                try:
                    document = read_json(args.input)
                except Blocked as exc:
                    result = make_result(args.operation, BLOCKED, "INPUT_BLOCKED", str(exc))
                else:
                    result = store.shadow_observe(args.kind, document)
            elif args.operation == "shadow_reserve":
                result = store.shadow_reserve(
                    authorization_id=args.authorization_id,
                    operation_id=args.operation_id,
                    nonce=args.nonce,
                    canonical_request_digest=args.canonical_request_digest,
                    claimed_governance_state=args.claimed_governance_state,
                    observed_at=args.observed_at,
                    expected_version=args.expected_version,
                )
            else:
                result = store.shadow_consume(
                    authorization_id=args.authorization_id,
                    operation_id=args.operation_id,
                    nonce=args.nonce,
                    canonical_request_digest=args.canonical_request_digest,
                    observed_at=args.observed_at,
                    expected_version=args.expected_version,
                )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0 if result.result == PASS else 1 if result.result == DENY else 2


if __name__ == "__main__":
    sys.exit(main())

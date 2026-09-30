#!/usr/bin/env python3
"""Independent read-only poststate verification for W3B-B-P1."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

FIXED_INDEX = "idx_audit_events_aggregate"
FIXED_TABLE = "audit_events"
FIXED_COLUMNS = ("aggregate_type", "aggregate_id", "sequence")
EXPECTED_INDEX_SQL = (
    "CREATE INDEX idx_audit_events_aggregate\n"
    "ON audit_events(aggregate_type, aggregate_id, sequence)"
)


class PoststateVerificationError(RuntimeError):
    """Poststate evidence was absent, ambiguous, or unexpected."""


def _typed_value(value: Any) -> list[Any]:
    if value is None:
        return ["null", None]
    if isinstance(value, bool):
        return ["integer", int(value)]
    if isinstance(value, int):
        return ["integer", value]
    if isinstance(value, float):
        return ["real", value.hex()]
    if isinstance(value, bytes):
        return ["blob", value.hex()]
    if isinstance(value, str):
        return ["text", value]
    raise TypeError(f"unsupported SQLite value type: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_digest(value: object) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def canonical_rows_digest(rows: Iterable[Sequence[Any]]) -> str:
    typed_rows = [[_typed_value(value) for value in row] for row in rows]
    return canonical_digest(typed_rows)


@dataclass(frozen=True)
class PoststateEvidence:
    schema_digest: str
    audit_events_digest: str
    index_present: bool
    index_unique: bool
    index_columns: tuple[str, ...]
    integrity_check: str
    user_version: int
    expected: bool


class PoststateVerifier:
    """Uses a new read-only connection and trusts no writer-side result."""

    def open_read_only(self, database: Path) -> sqlite3.Connection:
        uri = f"file:{database.resolve().as_posix()}?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only=ON")
        try:
            connection.execute("PRAGMA trusted_schema=OFF")
        except sqlite3.DatabaseError:
            connection.close()
            raise
        return connection

    def verify(self, database: Path) -> PoststateEvidence:
        connection = self.open_read_only(database)
        try:
            schema_rows = tuple(
                connection.execute(
                    """
                    SELECT type, name, tbl_name, sql
                    FROM sqlite_master
                    WHERE name NOT LIKE 'sqlite_%'
                    ORDER BY type, name, tbl_name
                    """
                )
            )
            schema_digest = canonical_rows_digest(schema_rows)

            audit_rows = tuple(
                connection.execute(
                    """
                    SELECT sequence, audit_event_id, event_type,
                           aggregate_type, aggregate_id, payload_digest,
                           previous_hash, event_hash, observed_at,
                           governance_status, authority_effect,
                           identity_effect, execution_effect,
                           activation_effect, eligible_for_execution
                    FROM audit_events
                    ORDER BY sequence
                    """
                )
            )
            audit_digest = canonical_rows_digest(audit_rows)

            indexes = {
                row[1]: bool(row[2])
                for row in connection.execute("PRAGMA index_list('audit_events')")
            }
            index_present = FIXED_INDEX in indexes
            index_unique = indexes.get(FIXED_INDEX, False)
            index_columns = (
                tuple(
                    row[2]
                    for row in connection.execute(
                        f"PRAGMA index_info('{FIXED_INDEX}')"
                    )
                )
                if index_present
                else ()
            )
            integrity_row = connection.execute("PRAGMA integrity_check").fetchone()
            user_version_row = connection.execute("PRAGMA user_version").fetchone()
            integrity_check = str(integrity_row[0]) if integrity_row else "missing"
            user_version = int(user_version_row[0]) if user_version_row else -1

            expected = (
                index_present
                and not index_unique
                and index_columns == FIXED_COLUMNS
                and integrity_check == "ok"
                and user_version == 100
            )
            return PoststateEvidence(
                schema_digest=schema_digest,
                audit_events_digest=audit_digest,
                index_present=index_present,
                index_unique=index_unique,
                index_columns=index_columns,
                integrity_check=integrity_check,
                user_version=user_version,
                expected=expected,
            )
        finally:
            connection.close()


def validate_expected_index_sql(sql: str | None) -> bool:
    if sql is None:
        return False
    normalized = " ".join(sql.strip().rstrip(";").split())
    expected = " ".join(EXPECTED_INDEX_SQL.split())
    return normalized == expected

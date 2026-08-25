import argparse
import contextlib
import copy
import importlib.util
import io
import json
import os
import sqlite3
import stat
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acos-w3-durable-state-observer.py"
PROFILE = ROOT / "docs" / "acos-w3-authorization-durable-state-observer-profile.md"
TRANSACTIONS = ROOT / "docs" / "acos-w3-state-transaction-semantics.md"
SCHEMAS = ROOT / "fixtures" / "schemas" / "w3" / "1.0"
FIXTURES = ROOT / "fixtures" / "schema-validation-w3" / "1.0"
SQL_PATH = ROOT / "fixtures" / "state-store-w3" / "1.0" / "state-store.sql"

SPEC = importlib.util.spec_from_file_location("acos_w3_durable_state_observer", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)

FIXTURE_PATHS = {
    "grant_observation": FIXTURES / "valid-grant-observation.json",
    "authorization_state_event": FIXTURES / "valid-authorization-state-event.json",
    "workflow_state_event": FIXTURES / "valid-workflow-state-event.json",
    "audit_event": FIXTURES / "valid-audit-event.json",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def w2_result():
    return {
        "case_id": "w2-shadow-case",
        "result": "PASS",
        "observed_at": "2026-08-20T10:00:00Z",
        "governance_status": "UNAUTHENTICATED_SHADOW",
        "authority_effect": "NONE",
        "identity_effect": "NONE",
        "execution_effect": "NONE",
        "activation_effect": "NONE",
        "eligible_for_execution": False,
    }


class W3ATestCase(unittest.TestCase):
    def make_store(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        store = gate.StateStore(root / "state.sqlite", root)
        self.addCleanup(store.close)
        return root, store

    def reserve(self, store, **overrides):
        values = {
            "authorization_id": "authorization:shadow:001",
            "operation_id": "operation:reserve:001",
            "nonce": "nonce-reserve-001",
            "canonical_request_digest": "sha256:" + "1" * 64,
            "claimed_governance_state": "VALIDATED",
            "observed_at": "2026-08-20T10:01:00Z",
            "expected_version": 0,
        }
        values.update(overrides)
        return store.shadow_reserve(**values)

    def consume(self, store, **overrides):
        values = {
            "authorization_id": "authorization:shadow:001",
            "operation_id": "operation:consume:001",
            "nonce": "nonce-consume-001",
            "canonical_request_digest": "sha256:" + "2" * 64,
            "observed_at": "2026-08-20T10:02:00Z",
            "expected_version": 1,
        }
        values.update(overrides)
        return store.shadow_consume(**values)

    def assert_taint(self, result):
        self.assertEqual(result.governance_status, "UNAUTHENTICATED_SHADOW")
        self.assertEqual(result.authority_effect, "NONE")
        self.assertEqual(result.identity_effect, "NONE")
        self.assertEqual(result.execution_effect, "NONE")
        self.assertEqual(result.activation_effect, "NONE")
        self.assertFalse(result.eligible_for_execution)


class SchemaAndProfileTests(W3ATestCase):
    def test_all_four_positive_fixtures_validate(self):
        for kind, path in FIXTURE_PATHS.items():
            with self.subTest(kind=kind):
                self.assertEqual(gate.validate_shadow_document(kind, load_json(path)).result, gate.PASS)

    def test_schemas_are_draft7_and_closed(self):
        for path in SCHEMAS.glob("*.json"):
            schema = load_json(path)
            self.assertEqual(schema["$schema"], "http://json-schema.org/draft-07/schema#")
            self.assertFalse(schema["additionalProperties"])

    def test_unknown_top_level_field_denied(self):
        for kind, path in FIXTURE_PATHS.items():
            candidate = load_json(path)
            candidate["permission"] = "execute"
            self.assertEqual(gate.validate_shadow_document(kind, candidate).result, gate.DENY)

    def test_unsupported_w3_version_denied(self):
        candidate = load_json(FIXTURE_PATHS["grant_observation"])
        candidate["profile_version"] = "2.0"
        self.assertEqual(gate.validate_shadow_document("grant_observation", candidate).result, gate.DENY)

    def test_wrong_contract_binding_denied(self):
        candidate = load_json(FIXTURE_PATHS["grant_observation"])
        candidate["contract_binding"]["contract_version"] = "2.1"
        self.assertEqual(gate.validate_shadow_document("grant_observation", candidate).result, gate.DENY)

    def test_no_contract_21_implication(self):
        text = PROFILE.read_text(encoding="utf-8")
        self.assertIn("does not create or imply Contract 2.1", text)
        self.assertNotIn('"contract_version": {"const": "2.1"}', "".join(p.read_text() for p in SCHEMAS.glob("*.json")))

    def test_positive_fixtures_are_non_authorizing(self):
        for path in FIXTURE_PATHS.values():
            data = load_json(path)
            self.assertEqual(data["authority_effect"], "NONE")
            self.assertEqual(data["execution_effect"], "NONE")
            self.assertEqual(data["activation_effect"], "NONE")
            self.assertFalse(data["eligible_for_execution"])

    def test_claimed_active_is_observation_only(self):
        data = load_json(FIXTURE_PATHS["grant_observation"])
        self.assertEqual(data["claimed_governance_state"], "ACTIVE")
        self.assertEqual(data["observer_state"], "OBSERVED")
        self.assertFalse(data["eligible_for_execution"])

    def test_profile_has_state_inequalities(self):
        text = PROFILE.read_text(encoding="utf-8")
        for term in (
            "Governance State != Stored Runtime State",
            "Observed Authorization != Authorization",
            "Reservation Success != Permission To Execute",
            "Consumption Recorded != Execution Authorized",
            "Durable State != Governance Authority",
        ):
            self.assertIn(term, text)

    def test_w3a_is_not_oer_phase3(self):
        self.assertIn("W3A Migration Shadow Kernel", PROFILE.read_text(encoding="utf-8"))
        self.assertIn("OER Phase 3 Operational Durable-State Entry", PROFILE.read_text(encoding="utf-8"))

    def test_profile_freezes_activation_boundary(self):
        text = PROFILE.read_text(encoding="utf-8")
        self.assertIn("Activation: LOCKED", text)
        self.assertIn("Operational Entry: LOCKED", text)
        self.assertIn("Default Consumption: NOT AUTHORIZED", text)

    def test_unknown_schema_kind_blocks(self):
        result = gate.validate_shadow_document("unknown", {})
        self.assertEqual(result.result, gate.BLOCKED)


class SQLiteConfigurationTests(W3ATestCase):
    def test_wal_is_effective(self):
        _, store = self.make_store()
        self.assertEqual(store.pragma_state()["journal_mode"], "wal")

    def test_synchronous_full_is_effective(self):
        _, store = self.make_store()
        self.assertEqual(store.pragma_state()["synchronous"], 2)

    def test_foreign_keys_on_is_effective(self):
        _, store = self.make_store()
        self.assertEqual(store.pragma_state()["foreign_keys"], 1)

    def test_busy_timeout_is_at_least_5000(self):
        _, store = self.make_store()
        self.assertGreaterEqual(store.pragma_state()["busy_timeout"], 5000)

    def test_too_small_busy_timeout_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(gate.Blocked):
                gate.StateStore(Path(directory) / "state.sqlite", directory, busy_timeout_ms=4999)

    def test_configuration_failure_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(gate.StateStore, "_configure_and_verify_connection", side_effect=gate.Blocked("configuration failure")):
                with self.assertRaises(gate.Blocked):
                    gate.StateStore(Path(directory) / "state.sqlite", directory)

    def test_store_metadata_versions(self):
        _, store = self.make_store()
        metadata = dict(store.db.execute("SELECT metadata_key, metadata_value FROM store_metadata"))
        self.assertEqual(metadata["state_store_version"], "1.0")
        self.assertEqual(metadata["w3_profile_version"], "1.0")
        self.assertEqual(metadata["acos_contract_version"], "2.0")

    def test_store_has_minimum_tables(self):
        _, store = self.make_store()
        names = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertTrue({"grant_observations", "authorization_state", "authorization_events", "workflow_state_events", "audit_events"}.issubset(names))

    def test_new_store_initializes_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            self.assertFalse(path.exists())
            with gate.StateStore(path, directory) as store:
                store.verify_store()
                self.assertEqual(store.db.execute("PRAGMA user_version").fetchone()[0], 100)
                self.assertEqual(
                    dict(store.db.execute("SELECT metadata_key, metadata_value FROM store_metadata")),
                    {
                        "state_store_version": "1.0",
                        "w3_profile_version": "1.0",
                        "acos_contract_version": "2.0",
                        "governance_status": "UNAUTHENTICATED_SHADOW",
                    },
                )

    def test_existing_store_user_version_mismatch_blocks_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            gate.StateStore(path, directory).close()
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                db.execute("PRAGMA user_version=999")
            with self.assertRaises(gate.Blocked):
                gate.StateStore(path, directory)
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 999)

    def test_existing_store_missing_metadata_blocks_without_recreation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            gate.StateStore(path, directory).close()
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                db.execute("DELETE FROM store_metadata WHERE metadata_key = 'w3_profile_version'")
            with self.assertRaises(gate.Blocked):
                gate.StateStore(path, directory)
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                self.assertIsNone(
                    db.execute(
                        "SELECT metadata_value FROM store_metadata WHERE metadata_key = 'w3_profile_version'"
                    ).fetchone()
                )

    def test_existing_store_missing_trigger_blocks_without_recreation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            gate.StateStore(path, directory).close()
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                db.execute("DROP TRIGGER audit_events_no_delete")
            with self.assertRaises(gate.Blocked):
                gate.StateStore(path, directory)
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = 'audit_events_no_delete'"
                    ).fetchone()
                )

    def test_existing_store_missing_table_blocks_without_recreation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            gate.StateStore(path, directory).close()
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                db.execute("DROP TABLE workflow_state_events")
            with self.assertRaises(gate.Blocked):
                gate.StateStore(path, directory)
            with contextlib.closing(sqlite3.connect(path)) as db, db:
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'workflow_state_events'"
                    ).fetchone()
                )

    def test_valid_existing_store_reopens_without_schema_or_data_repair(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with gate.StateStore(path, directory) as store:
                self.reserve(store)

            def snapshot():
                with contextlib.closing(sqlite3.connect(path)) as db, db:
                    return {
                        "objects": db.execute(
                            "SELECT type, name, sql FROM sqlite_master "
                            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                        ).fetchall(),
                        "metadata": db.execute(
                            "SELECT metadata_key, metadata_value FROM store_metadata ORDER BY metadata_key"
                        ).fetchall(),
                        "state": db.execute(
                            "SELECT * FROM authorization_state ORDER BY authorization_id"
                        ).fetchall(),
                        "events": db.execute(
                            "SELECT * FROM authorization_events ORDER BY event_id"
                        ).fetchall(),
                        "audit": db.execute(
                            "SELECT * FROM audit_events ORDER BY sequence"
                        ).fetchall(),
                    }

            before = snapshot()
            with gate.StateStore(path, directory) as reopened:
                reopened.verify_store()
            self.assertEqual(snapshot(), before)


class PathSafetyTests(W3ATestCase):
    def test_explicit_state_path_required(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(gate.Blocked):
                gate.secure_state_path(None, directory)

    def test_explicit_root_required(self):
        with self.assertRaises(gate.Blocked):
            gate.secure_state_path("state.sqlite", None)

    def test_parent_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(gate.Blocked):
                gate.secure_state_path("../state.sqlite", directory)

    def test_outside_root_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(gate.Blocked):
                gate.secure_state_path(Path(directory).parent / "outside.sqlite", directory)

    def test_symlink_target_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real.sqlite"
            real.write_bytes(b"")
            link = root / "link.sqlite"
            link.symlink_to(real)
            with self.assertRaises(gate.Blocked):
                gate.secure_state_path(link, root)

    def test_symlink_parent_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / "linked").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(gate.Blocked):
                gate.secure_state_path(root / "linked" / "state.sqlite", root)

    def test_missing_parent_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(gate.Blocked):
                gate.secure_state_path(Path(directory) / "missing" / "state.sqlite", directory)

    def test_directory_target_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(gate.Blocked):
                gate.secure_state_path(directory, directory)

    def test_database_mode_0600(self):
        root, store = self.make_store()
        mode = stat.S_IMODE((root / "state.sqlite").stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_root_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as holder:
            link = Path(holder) / "root-link"
            link.symlink_to(directory, target_is_directory=True)
            with self.assertRaises(gate.Blocked):
                gate.secure_state_path("state.sqlite", link)


class TransactionAndReplayTests(W3ATestCase):
    def test_reserve_uses_begin_immediate(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('self.db.execute("BEGIN IMMEDIATE")', source)

    def test_reserve_success(self):
        _, store = self.make_store()
        result = self.reserve(store)
        self.assertEqual(result.result, gate.PASS)
        self.assert_taint(result)
        self.assertEqual(store.authorization_state("authorization:shadow:001")["current_observer_state"], "RESERVED")

    def test_reserve_state_event_audit_atomic_presence(self):
        _, store = self.make_store()
        self.reserve(store)
        self.assertEqual(store.count_rows("authorization_state"), 1)
        self.assertEqual(store.count_rows("authorization_events"), 1)
        self.assertEqual(store.count_rows("audit_events"), 1)

    def test_forced_audit_failure_rolls_back_reserve(self):
        _, store = self.make_store()
        store._append_audit = mock.Mock(side_effect=sqlite3.IntegrityError("forced audit failure"))
        result = self.reserve(store)
        self.assertEqual(result.result, gate.BLOCKED)
        self.assertEqual(result.reason_code, "SQLITE_INTEGRITY_BLOCKED")
        self.assert_taint(result)
        self.assertEqual(store.count_rows("authorization_state"), 0)
        self.assertEqual(store.count_rows("authorization_events"), 0)
        self.assertEqual(store.count_rows("audit_events"), 0)

    def test_unexpected_operation_exception_blocks_and_rolls_back(self):
        _, store = self.make_store()
        store._append_audit = mock.Mock(side_effect=RuntimeError("unexpected audit failure"))
        result = self.reserve(store)
        self.assertEqual(result.result, gate.BLOCKED)
        self.assertEqual(result.reason_code, "UNEXPECTED_OPERATION_ERROR")
        self.assert_taint(result)
        self.assertEqual(store.count_rows("authorization_state"), 0)
        self.assertEqual(store.count_rows("authorization_events"), 0)
        self.assertEqual(store.count_rows("audit_events"), 0)

    def test_reserve_wrong_version_denied(self):
        _, store = self.make_store()
        result = self.reserve(store, expected_version=1)
        self.assertEqual(result.result, gate.DENY)
        self.assertIn("affected_rows != 1", result.reason)

    def test_second_reservation_conflict_denied(self):
        _, store = self.make_store()
        self.assertEqual(self.reserve(store).result, gate.PASS)
        result = self.reserve(store, operation_id="operation:reserve:002", nonce="nonce-reserve-002")
        self.assertEqual(result.result, gate.DENY)

    def test_busy_is_blocked(self):
        _, store = self.make_store()
        with mock.patch.object(store, "_begin_immediate", side_effect=sqlite3.OperationalError("database is locked")):
            result = self.reserve(store)
        self.assertEqual(result.result, gate.BLOCKED)
        self.assertEqual(result.reason_code, "SQLITE_BUSY")

    def test_consume_success(self):
        _, store = self.make_store()
        self.reserve(store)
        result = self.consume(store)
        self.assertEqual(result.result, gate.PASS)
        self.assert_taint(result)
        state = store.authorization_state("authorization:shadow:001")
        self.assertEqual(state["current_observer_state"], "CONSUMED")
        self.assertEqual(state["version"], 2)

    def test_consume_without_reservation_denied(self):
        _, store = self.make_store()
        self.assertEqual(self.consume(store).result, gate.DENY)

    def test_consume_wrong_version_denied(self):
        _, store = self.make_store()
        self.reserve(store)
        self.assertEqual(self.consume(store, expected_version=0).result, gate.DENY)

    def test_consumption_requires_affected_rows_one(self):
        self.assertIn("cursor.rowcount != 1", SCRIPT.read_text(encoding="utf-8"))

    def test_exact_reserve_replay_is_idempotent(self):
        _, store = self.make_store()
        self.assertEqual(self.reserve(store).result, gate.PASS)
        result = self.reserve(store)
        self.assertEqual(result.result, gate.PASS)
        self.assertEqual(result.reason_code, "IDEMPOTENT_REPLAY")

    def test_exact_reserve_replay_has_no_second_effect(self):
        _, store = self.make_store()
        self.reserve(store)
        before = (store.count_rows("authorization_events"), store.count_rows("audit_events"))
        self.reserve(store)
        after = (store.count_rows("authorization_events"), store.count_rows("audit_events"))
        self.assertEqual(before, after)

    def test_same_operation_changed_nonce_denied(self):
        _, store = self.make_store()
        self.reserve(store)
        self.assertEqual(self.reserve(store, nonce="nonce-reserve-changed").result, gate.DENY)

    def test_same_operation_changed_digest_denied(self):
        _, store = self.make_store()
        self.reserve(store)
        self.assertEqual(self.reserve(store, canonical_request_digest="sha256:" + "9" * 64).result, gate.DENY)

    def test_same_nonce_different_operation_denied(self):
        _, store = self.make_store()
        self.reserve(store)
        result = self.reserve(store, operation_id="operation:reserve:other", expected_version=1)
        self.assertEqual(result.result, gate.DENY)

    def test_same_nonce_different_authorization_allowed(self):
        _, store = self.make_store()
        self.assertEqual(self.reserve(store).result, gate.PASS)
        result = self.reserve(
            store,
            authorization_id="authorization:shadow:002",
            operation_id="operation:reserve:002",
        )
        self.assertEqual(result.result, gate.PASS)

    def test_exact_consume_replay_is_idempotent(self):
        _, store = self.make_store()
        self.reserve(store)
        self.assertEqual(self.consume(store).result, gate.PASS)
        result = self.consume(store)
        self.assertEqual(result.result, gate.PASS)
        self.assertEqual(result.reason_code, "IDEMPOTENT_REPLAY")

    def test_exact_consume_replay_has_no_second_effect(self):
        _, store = self.make_store()
        self.reserve(store)
        self.consume(store)
        before = (store.count_rows("authorization_events"), store.count_rows("audit_events"))
        self.consume(store)
        self.assertEqual(before, (store.count_rows("authorization_events"), store.count_rows("audit_events")))

    def test_sql_has_operation_uniqueness(self):
        sql = SQL_PATH.read_text(encoding="utf-8")
        self.assertIn("UNIQUE (authorization_id, operation_id)", sql)

    def test_sql_has_authorization_scoped_nonce_uniqueness(self):
        sql = SQL_PATH.read_text(encoding="utf-8")
        self.assertIn("UNIQUE (authorization_id, nonce)", sql)
        self.assertNotIn("UNIQUE (authorization_id, operation_id, nonce)", sql)

    def test_invalid_digest_denied(self):
        _, store = self.make_store()
        self.assertEqual(self.reserve(store, canonical_request_digest="bad").result, gate.DENY)

    def test_missing_identifier_blocks(self):
        _, store = self.make_store()
        self.assertEqual(self.reserve(store, authorization_id="").result, gate.BLOCKED)


class ConcurrencyAndRestartTests(W3ATestCase):
    def test_concurrent_reserve_at_most_one_state_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with gate.StateStore(root / "state.sqlite", root):
                pass
            barrier = threading.Barrier(2)

            def worker(index):
                with gate.StateStore(root / "state.sqlite", root) as store:
                    barrier.wait()
                    return store.shadow_reserve(
                        authorization_id="authorization:race:reserve",
                        operation_id=f"operation:race:{index}",
                        nonce=f"nonce-race-reserve-{index}",
                        canonical_request_digest="sha256:" + str(index) * 64,
                        claimed_governance_state="VALIDATED",
                        observed_at="2026-08-20T11:00:00Z",
                    ).result

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, (1, 2)))
            self.assertEqual(results.count(gate.PASS), 1)
            self.assertEqual(results.count(gate.DENY), 1)

    def test_concurrent_consume_has_no_double_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with gate.StateStore(root / "state.sqlite", root) as store:
                self.reserve(store, authorization_id="authorization:race:consume")
            barrier = threading.Barrier(2)

            def worker(index):
                with gate.StateStore(root / "state.sqlite", root) as store:
                    barrier.wait()
                    return store.shadow_consume(
                        authorization_id="authorization:race:consume",
                        operation_id=f"operation:consume-race:{index}",
                        nonce=f"nonce-consume-race-{index}",
                        canonical_request_digest="sha256:" + str(index) * 64,
                        observed_at="2026-08-20T11:01:00Z",
                        expected_version=1,
                    ).result

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(worker, (3, 4)))
            self.assertEqual(results.count(gate.PASS), 1)
            self.assertEqual(results.count(gate.DENY), 1)

    def test_clean_close_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            gate.StateStore(path, directory).close()
            with gate.StateStore(path, directory) as reopened:
                self.assertEqual(reopened.pragma_state()["journal_mode"], "wal")

    def test_reserved_state_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with gate.StateStore(path, directory) as store:
                self.reserve(store)
            with gate.StateStore(path, directory) as reopened:
                self.assertEqual(reopened.authorization_state("authorization:shadow:001")["current_observer_state"], "RESERVED")

    def test_consumed_state_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with gate.StateStore(path, directory) as store:
                self.reserve(store)
                self.consume(store)
            with gate.StateStore(path, directory) as reopened:
                self.assertEqual(reopened.authorization_state("authorization:shadow:001")["current_observer_state"], "CONSUMED")

    def test_replay_binding_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with gate.StateStore(path, directory) as store:
                self.reserve(store)
            with gate.StateStore(path, directory) as reopened:
                self.assertEqual(self.reserve(reopened).reason_code, "IDEMPOTENT_REPLAY")

    def test_unsupported_store_version_blocks_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with gate.StateStore(path, directory) as store:
                store.db.execute("UPDATE store_metadata SET metadata_value = '2.0' WHERE metadata_key = 'state_store_version'")
            with self.assertRaises(gate.Blocked):
                gate.StateStore(path, directory)

    def test_audit_chain_inconsistency_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with gate.StateStore(path, directory) as store:
                self.reserve(store)
                store.db.execute("DROP TRIGGER audit_events_no_update")
                store.db.execute("UPDATE audit_events SET payload_digest = ? WHERE sequence = 1", ("sha256:" + "f" * 64,))
            with self.assertRaises(gate.Blocked):
                gate.StateStore(path, directory)

    def test_detectable_database_corruption_blocks_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            gate.StateStore(path, directory).close()
            path.write_bytes(b"not-a-sqlite-database")
            with self.assertRaises(gate.Blocked):
                gate.StateStore(path, directory)

    def test_rollback_store_reopens_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.sqlite"
            with gate.StateStore(path, directory) as store:
                store._append_audit = mock.Mock(side_effect=sqlite3.IntegrityError("forced"))
                self.assertEqual(self.reserve(store).result, gate.BLOCKED)
            with gate.StateStore(path, directory) as reopened:
                reopened.verify_store()
                self.assertEqual(reopened.count_rows("authorization_state"), 0)


class W2TaintAndAuthorityTests(W3ATestCase):
    def test_complete_w2_shadow_result_may_be_observed_only(self):
        self.assertEqual(gate.validate_w2_shadow_result(w2_result()).result, gate.PASS)

    def test_naked_w2_pass_blocks(self):
        self.assertEqual(gate.validate_w2_shadow_result({"result": "PASS"}).result, gate.BLOCKED)

    def test_missing_w2_taint_blocks(self):
        for field in gate.W2_REQUIRED_TAINT:
            candidate = w2_result()
            candidate.pop(field)
            with self.subTest(field=field):
                self.assertEqual(gate.validate_w2_shadow_result(candidate).result, gate.BLOCKED)

    def test_w2_authority_effect_denied(self):
        candidate = w2_result()
        candidate["authority_effect"] = "GRANTED"
        self.assertEqual(gate.validate_w2_shadow_result(candidate).result, gate.DENY)

    def test_w2_execution_effect_denied(self):
        candidate = w2_result()
        candidate["execution_effect"] = "EXECUTE"
        self.assertEqual(gate.validate_w2_shadow_result(candidate).result, gate.DENY)

    def test_w2_activation_effect_denied(self):
        candidate = w2_result()
        candidate["activation_effect"] = "ACTIVATE"
        self.assertEqual(gate.validate_w2_shadow_result(candidate).result, gate.DENY)

    def test_w2_identity_effect_denied(self):
        candidate = w2_result()
        candidate["identity_effect"] = "AUTHENTICATED"
        self.assertEqual(gate.validate_w2_shadow_result(candidate).result, gate.DENY)

    def test_w2_execution_eligibility_denied(self):
        candidate = w2_result()
        candidate["eligible_for_execution"] = True
        self.assertEqual(gate.validate_w2_shadow_result(candidate).result, gate.DENY)

    def test_w2_observation_is_durable_audit_only(self):
        _, store = self.make_store()
        result = store.shadow_observe("w2_shadow_result", w2_result())
        self.assertEqual(result.result, gate.PASS)
        self.assertEqual(store.count_rows("audit_events"), 1)
        self.assertEqual(store.count_rows("authorization_state"), 0)

    def test_complete_w2_taint_missing_observed_at_blocks_without_escape(self):
        _, store = self.make_store()
        candidate = w2_result()
        candidate.pop("observed_at")
        result = store.shadow_observe("w2_shadow_result", candidate)
        self.assertEqual(result.result, gate.BLOCKED)
        self.assert_taint(result)
        self.assertEqual(store.count_rows("audit_events"), 0)

    def test_complete_w2_taint_invalid_observed_at_denied_without_escape(self):
        _, store = self.make_store()
        candidate = w2_result()
        candidate["observed_at"] = "not-a-timestamp"
        result = store.shadow_observe("w2_shadow_result", candidate)
        self.assertEqual(result.result, gate.DENY)
        self.assert_taint(result)
        self.assertEqual(store.count_rows("audit_events"), 0)

    def test_invalid_w2_case_metadata_blocks_without_escape(self):
        _, store = self.make_store()
        candidate = w2_result()
        candidate["case_id"] = ""
        result = store.shadow_observe("w2_shadow_result", candidate)
        self.assertEqual(result.result, gate.BLOCKED)
        self.assert_taint(result)
        self.assertEqual(store.count_rows("audit_events"), 0)

    def test_all_result_classes_preserve_non_authority(self):
        results = [
            gate.make_result("shadow_observe", gate.PASS, "PASS", "ok"),
            gate.make_result("shadow_observe", gate.DENY, "DENY", "no"),
            gate.make_result("shadow_observe", gate.BLOCKED, "BLOCKED", "blocked"),
        ]
        for result in results:
            self.assert_taint(result)

    def test_operation_vocabulary_is_exact(self):
        self.assertEqual(gate.OBSERVER_OPERATIONS, {"shadow_observe", "shadow_reserve", "shadow_consume"})

    def test_forbidden_operational_subcommands_absent(self):
        parser = gate.build_parser()
        subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
        self.assertTrue({"authorize", "approve", "grant", "execute"}.isdisjoint(subparsers.choices))

    def test_reserved_result_never_eligible(self):
        _, store = self.make_store()
        result = self.reserve(store)
        self.assert_taint(result)

    def test_consumed_result_never_eligible(self):
        _, store = self.make_store()
        self.reserve(store)
        self.assert_taint(self.consume(store))

    def test_w2_pass_is_not_w3_authorization(self):
        self.assertIn("W2 PASS != W3 Authorization", PROFILE.read_text(encoding="utf-8"))


class AuditAndWorkflowTests(W3ATestCase):
    def test_audit_chain_consistent_after_reserve_and_consume(self):
        _, store = self.make_store()
        self.reserve(store)
        self.consume(store)
        store.verify_audit_chain()
        self.assertEqual(store.count_rows("audit_events"), 2)

    def test_audit_sequence_is_deterministic(self):
        _, store = self.make_store()
        self.reserve(store)
        self.consume(store)
        sequences = [row[0] for row in store.db.execute("SELECT sequence FROM audit_events ORDER BY sequence")]
        self.assertEqual(sequences, [1, 2])

    def test_audit_events_are_append_only(self):
        _, store = self.make_store()
        self.reserve(store)
        with self.assertRaises(sqlite3.IntegrityError):
            store.db.execute("UPDATE audit_events SET event_type = 'changed' WHERE sequence = 1")

    def test_authorization_events_are_append_only(self):
        _, store = self.make_store()
        self.reserve(store)
        with self.assertRaises(sqlite3.IntegrityError):
            store.db.execute("DELETE FROM authorization_events")

    def test_audit_hash_limitations_are_explicit(self):
        text = PROFILE.read_text(encoding="utf-8") + TRANSACTIONS.read_text(encoding="utf-8")
        for term in ("Hash Chain != Signature", "Hash Chain != Authenticated Producer", "Hash Chain != Nonrepudiation", "Hash Chain != Trust Anchor", "Hash Chain != Host-Compromise Resistance"):
            self.assertIn(term, text)

    def test_valid_workflow_edge_is_recorded(self):
        _, store = self.make_store()
        document = load_json(FIXTURE_PATHS["workflow_state_event"])
        result = store.shadow_observe("workflow_state_event", document)
        self.assertEqual(result.result, gate.PASS)
        self.assertEqual(store.count_rows("workflow_state_events"), 1)
        self.assertEqual(store.count_rows("audit_events"), 1)

    def test_invalid_workflow_edge_denied(self):
        _, store = self.make_store()
        document = load_json(FIXTURE_PATHS["workflow_state_event"])
        document["observed_from_state"] = "TASK_READY"
        document["observed_to_state"] = "TASK_CLOSED"
        self.assertEqual(store.shadow_observe("workflow_state_event", document).result, gate.DENY)

    def test_workflow_observer_does_not_create_canonical_state_table(self):
        _, store = self.make_store()
        names = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertNotIn("task_state", names)
        self.assertNotIn("governance_state", names)

    def test_workflow_profile_preserves_authority(self):
        self.assertIn("governance state transition enacted", PROFILE.read_text(encoding="utf-8"))
        self.assertIn("ChatGPT Review remains", PROFILE.read_text(encoding="utf-8"))

    def test_grant_observation_is_atomic_with_audit(self):
        _, store = self.make_store()
        document = load_json(FIXTURE_PATHS["grant_observation"])
        self.assertEqual(store.shadow_observe("grant_observation", document).result, gate.PASS)
        self.assertEqual(store.count_rows("grant_observations"), 1)
        self.assertEqual(store.count_rows("audit_events"), 1)

    def test_duplicate_grant_observation_denied(self):
        _, store = self.make_store()
        document = load_json(FIXTURE_PATHS["grant_observation"])
        store.shadow_observe("grant_observation", document)
        self.assertEqual(store.shadow_observe("grant_observation", document).result, gate.DENY)

    def test_sql_has_no_authorization_broker(self):
        sql = SQL_PATH.read_text(encoding="utf-8").lower()
        self.assertNotIn("authorization_broker", sql)
        self.assertNotIn("permission_to_execute", sql)

    def test_w3b_repair_is_not_implemented(self):
        source = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("automatic_repair", source)
        self.assertNotIn("reconcile_authoritative", source)
        self.assertIn("deferred to W3B", PROFILE.read_text(encoding="utf-8"))


class CLITests(W3ATestCase):
    def test_cli_requires_state_path(self):
        with self.assertRaises(SystemExit):
            gate.build_parser().parse_args(["--state-root", "/tmp", "shadow_observe", "--kind", "grant_observation", "--input", "x"])

    def test_cli_requires_state_root(self):
        with self.assertRaises(SystemExit):
            gate.build_parser().parse_args(["--state-path", "x.sqlite", "shadow_observe", "--kind", "grant_observation", "--input", "x"])

    def test_cli_grant_observation_passes(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            code = gate.main([
                "--state-path", str(Path(directory) / "state.sqlite"),
                "--state-root", directory,
                "shadow_observe", "--kind", "grant_observation",
                "--input", str(FIXTURE_PATHS["grant_observation"]),
            ])
        self.assertEqual(code, 0)

    def test_cli_reserve_passes(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            code = gate.main([
                "--state-path", str(Path(directory) / "state.sqlite"),
                "--state-root", directory,
                "shadow_reserve",
                "--authorization-id", "authorization:cli:001",
                "--operation-id", "operation:cli:reserve:001",
                "--nonce", "nonce-cli-reserve-001",
                "--canonical-request-digest", "sha256:" + "4" * 64,
                "--claimed-governance-state", "VALIDATED",
                "--observed-at", "2026-08-20T12:00:00Z",
            ])
        self.assertEqual(code, 0)

    def test_cli_output_is_machine_readable_non_authority(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(output):
            gate.main([
                "--state-path", str(Path(directory) / "state.sqlite"),
                "--state-root", directory,
                "shadow_reserve",
                "--authorization-id", "authorization:cli:002",
                "--operation-id", "operation:cli:reserve:002",
                "--nonce", "nonce-cli-reserve-002",
                "--canonical-request-digest", "sha256:" + "5" * 64,
                "--claimed-governance-state", "ACTIVE",
                "--observed-at", "2026-08-20T12:01:00Z",
            ])
        data = json.loads(output.getvalue())
        self.assertEqual(data["authority_effect"], "NONE")
        self.assertFalse(data["eligible_for_execution"])

    def test_cli_missing_w2_observed_at_is_machine_readable_blocked(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            candidate = w2_result()
            candidate.pop("observed_at")
            input_path = Path(directory) / "w2-result.json"
            input_path.write_text(json.dumps(candidate), encoding="utf-8")
            with contextlib.redirect_stdout(output):
                code = gate.main([
                    "--state-path", str(Path(directory) / "state.sqlite"),
                    "--state-root", directory,
                    "shadow_observe", "--kind", "w2_shadow_result",
                    "--input", str(input_path),
                ])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(result["result"], gate.BLOCKED)
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertFalse(result["eligible_for_execution"])


# Each generated test is a separate unittest case, keeping fixture/schema
# coverage explicit in the reported W3A test count.
def _make_fixture_test(kind):
    def test(self):
        self.assertEqual(gate.validate_shadow_document(kind, load_json(FIXTURE_PATHS[kind])).result, gate.PASS)
    return test


def _make_closed_schema_test(kind):
    def test(self):
        candidate = load_json(FIXTURE_PATHS[kind])
        candidate["authority_upgrade"] = True
        self.assertEqual(gate.validate_shadow_document(kind, candidate).result, gate.DENY)
    return test


for _kind in sorted(FIXTURE_PATHS):
    setattr(SchemaAndProfileTests, f"test_fixture_{_kind}_passes", _make_fixture_test(_kind))
    setattr(SchemaAndProfileTests, f"test_fixture_{_kind}_rejects_authority_expansion", _make_closed_schema_test(_kind))


if __name__ == "__main__":
    unittest.main()

import argparse
import copy
import importlib.util
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acos-w3b-a-read-only-repair-planner.py"
W3A_SCRIPT = ROOT / "scripts" / "acos-w3-durable-state-observer.py"
PROFILE = ROOT / "docs" / "acos-w3b-a-read-only-repair-planner-shadow-profile.md"
SEMANTICS = ROOT / "docs" / "acos-w3b-a-snapshot-plan-verification-semantics.md"
SCHEMA_ROOT = ROOT / "fixtures" / "schemas" / "w3b-a" / "1.0"
FIXTURE_ROOT = ROOT / "fixtures" / "schema-validation-w3b-a" / "1.0"
SQL_PATH = ROOT / "fixtures" / "state-store-w3" / "1.0" / "state-store.sql"

SPEC = importlib.util.spec_from_file_location("acos_w3b_a_read_only_repair_planner", SCRIPT)
planner = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = planner
SPEC.loader.exec_module(planner)

W3A_SPEC = importlib.util.spec_from_file_location("acos_w3_durable_state_observer_for_w3b_a", W3A_SCRIPT)
w3a = importlib.util.module_from_spec(W3A_SPEC)
assert W3A_SPEC.loader is not None
sys.modules[W3A_SPEC.name] = w3a
W3A_SPEC.loader.exec_module(w3a)

SCHEMA_FILES = {
    "snapshot_reference": SCHEMA_ROOT / "snapshot-reference.schema.json",
    "repair_evidence": SCHEMA_ROOT / "repair-evidence.schema.json",
    "repair_plan": SCHEMA_ROOT / "repair-plan.schema.json",
    "repair_plan_verification": SCHEMA_ROOT / "repair-plan-verification.schema.json",
}

FIXTURE_FILES = {
    "snapshot_reference": FIXTURE_ROOT / "valid-snapshot-reference.json",
    "repair_evidence": FIXTURE_ROOT / "valid-repair-evidence.json",
    "repair_plan": FIXTURE_ROOT / "valid-repair-plan.json",
    "repair_plan_verification": FIXTURE_ROOT / "valid-repair-plan-verification.json",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class W3BATestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def make_snapshot(self, mutator=None):
        path = self.root / "snapshot.sqlite"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(SQL_PATH.read_text(encoding="utf-8"))
            connection.commit()
        finally:
            connection.close()
        if mutator is not None:
            connection = sqlite3.connect(path)
            try:
                mutator(connection)
                connection.commit()
            finally:
                connection.close()
        return path

    def add_audit_event(self, connection, event_hash=None):
        row = {
            "sequence": 1,
            "event_type": "GRANT_OBSERVATION",
            "aggregate_type": "GRANT_OBSERVATION",
            "aggregate_id": "grant:test:001",
            "payload_digest": "sha256:" + "1" * 64,
            "previous_hash": planner.AUDIT_GENESIS,
            "observed_at": "2026-08-25T10:00:00Z",
        }
        observed_hash = event_hash or planner.audit_hash(row)
        connection.execute(
            "INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                1, "audit:w3:00000000000000000001", row["event_type"],
                row["aggregate_type"], row["aggregate_id"], row["payload_digest"],
                row["previous_hash"], observed_hash, row["observed_at"],
                "UNAUTHENTICATED_SHADOW", "NONE", "NONE", "NONE", "NONE", 0,
            ),
        )

    def inspect(self, path=None):
        path = path or self.make_snapshot()
        return planner.shadow_snapshot_inspect(
            path,
            self.root,
            "store:shadow:test:001",
            "2026-08-25T10:00:00Z",
        )

    def plan(self, path=None):
        path = path or self.make_snapshot()
        return planner.shadow_repair_plan(
            path,
            self.root,
            "store:shadow:test:001",
            "evidence:w3b-a:test:001",
            "plan:w3b-a:test:001",
            "2026-08-25T10:00:00Z",
        )

    def fixture_documents(self):
        return (
            load_json(FIXTURE_FILES["snapshot_reference"]),
            load_json(FIXTURE_FILES["repair_evidence"]),
            load_json(FIXTURE_FILES["repair_plan"]),
        )

    def verify_fixture(self, snapshot=None, evidence=None, plan=None):
        base_snapshot, base_evidence, base_plan = self.fixture_documents()
        return planner.shadow_repair_plan_verify(
            snapshot or base_snapshot,
            evidence or base_evidence,
            plan or base_plan,
            "verification:w3b-a:test:001",
            "2026-08-25T10:01:00Z",
        )

    def assert_taint(self, result):
        self.assertEqual(result.governance_status, "UNAUTHENTICATED_SHADOW")
        self.assertEqual(result.authority_effect, "NONE")
        self.assertEqual(result.identity_effect, "NONE")
        self.assertEqual(result.execution_effect, "NONE")
        self.assertEqual(result.activation_effect, "NONE")
        self.assertFalse(result.eligible_for_execution)
        self.assertEqual(result.plan_effect, "NONE")
        self.assertEqual(result.mutation_effect, "NONE")


class SchemaFixtureTests(W3BATestCase):
    def test_schema_set_is_exact(self):
        self.assertEqual({path.name for path in SCHEMA_ROOT.glob("*.json")}, {path.name for path in SCHEMA_FILES.values()})

    def test_fixture_set_is_exact(self):
        self.assertEqual({path.name for path in FIXTURE_ROOT.glob("*.json")}, {path.name for path in FIXTURE_FILES.values()})

    def test_evidence_fixture_digest_is_valid(self):
        evidence = load_json(FIXTURE_FILES["repair_evidence"])
        self.assertEqual(evidence["evidence_set_digest"], planner.digest_without(evidence, "evidence_set_digest"))

    def test_plan_fixture_digest_is_valid(self):
        plan = load_json(FIXTURE_FILES["repair_plan"])
        self.assertEqual(plan["plan_digest"], planner.digest_without(plan, "plan_digest"))

    def test_fixture_bundle_verifies(self):
        result = self.verify_fixture()
        self.assertEqual(result.result, planner.PASS)
        self.assertEqual(result.data["verification_state"], "PLAN_VERIFIED")

    def test_all_fixture_objects_are_execution_ineligible(self):
        for path in FIXTURE_FILES.values():
            value = load_json(path)
            self.assertEqual(value["shadow_status"], "SHADOW_ONLY")
            self.assertEqual(value["execution_eligibility"], "EXECUTION_INELIGIBLE")
            self.assertEqual(value["authority_status"], "AUTHORITY_NONE")
            self.assertEqual(value["mutation_status"], "MUTATION_NONE")

    def test_schema_classification_vocabulary_is_closed(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in SCHEMA_FILES.values())
        for value in planner.CLASSIFICATIONS:
            self.assertIn(value, text)
        self.assertNotIn("AUTHORIZED_LOCAL_MUTATION_CANDIDATE", text)

    def test_schema_operation_effects_are_none(self):
        for path in SCHEMA_FILES.values():
            text = path.read_text(encoding="utf-8")
            self.assertIn('"mutation_effect": {"const": "NONE"}', text)


def _make_schema_shape_test(kind):
    def test(self):
        schema = load_json(SCHEMA_FILES[kind])
        self.assertEqual(schema["$schema"], "http://json-schema.org/draft-07/schema#")
        self.assertFalse(schema["additionalProperties"])
        planner.Draft7Validator.check_schema(schema)
    return test


def _make_fixture_validation_test(kind):
    def test(self):
        planner.validate_document(kind, load_json(FIXTURE_FILES[kind]))
    return test


for _kind in sorted(SCHEMA_FILES):
    setattr(SchemaFixtureTests, f"test_schema_{_kind}_is_draft7_and_closed", _make_schema_shape_test(_kind))
    setattr(SchemaFixtureTests, f"test_fixture_{_kind}_validates", _make_fixture_validation_test(_kind))


class ProfileBoundaryTests(W3BATestCase):
    def test_profile_declares_all_six_boundaries(self):
        text = PROFILE.read_text(encoding="utf-8")
        for value in ("SHADOW", "NON-PRODUCTION", "READ-ONLY", "NON-AUTHORIZING", "NON-MUTATING", "NON-ACTIVATING"):
            self.assertIn(value, text)

    def test_profile_freezes_core_inequalities(self):
        text = PROFILE.read_text(encoding="utf-8")
        for value in (
            "Repair Inspection != Repair Authorization",
            "Repair Plan != Repair Grant",
            "Plan Verification != Permission To Execute",
            "PLAN_VERIFIED != EXECUTION_READY",
            "Deterministic Plan != Authorized Mutation",
            "Plan Persistence != Plan Authority",
        ):
            self.assertIn(value, text)

    def test_profile_freezes_snapshot_identity_limitations(self):
        text = PROFILE.read_text(encoding="utf-8")
        for value in ("path != stable identity", "inode != stable identity", "digest != logical identity"):
            self.assertIn(value, text)

    def test_profile_freezes_activation(self):
        text = PROFILE.read_text(encoding="utf-8")
        self.assertIn("Default Consumption: NOT AUTHORIZED", text)
        self.assertIn("Activation: LOCKED", text)
        self.assertIn("Operational Entry: LOCKED", text)

    def test_profile_has_no_authorized_local_mutation_category(self):
        self.assertNotIn("AUTHORIZED_LOCAL_MUTATION_CANDIDATE", planner.CLASSIFICATIONS)

    def test_semantics_define_declarative_verification(self):
        text = SEMANTICS.read_text(encoding="utf-8")
        self.assertIn("PLAN_VERIFY = DECLARATIVE INVARIANT CHECK", text)
        self.assertIn("PLAN_VERIFY != DRY-RUN APPLY", text)

    def test_semantics_reject_universal_source_of_truth(self):
        self.assertIn("does not encode a winner", SEMANTICS.read_text(encoding="utf-8"))

    def test_semantics_terminal_state_has_no_successor(self):
        self.assertEqual(planner.PLAN_STATE_GRAPH["PLAN_VERIFIED"], ())

    def test_profile_binds_canonical_digest(self):
        self.assertIn(planner.EXPECTED_CANONICAL_SQL_SHA256, PROFILE.read_text(encoding="utf-8"))

    def test_profile_prohibits_audit_self_repair(self):
        self.assertIn("cannot bootstrap trust for its own repair", PROFILE.read_text(encoding="utf-8"))


class PathAndResourceTests(W3BATestCase):
    def test_parent_traversal_blocks(self):
        result = planner.shadow_snapshot_inspect("../outside.sqlite", self.root, "store:test", "2026-08-25T10:00:00Z")
        self.assertEqual(result.result, planner.BLOCKED)

    def test_outside_absolute_path_blocks(self):
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / "snapshot.sqlite"
            outside.write_bytes(b"x")
            result = planner.shadow_snapshot_inspect(outside, self.root, "store:test", "2026-08-25T10:00:00Z")
        self.assertEqual(result.result, planner.BLOCKED)

    def test_snapshot_symlink_blocks(self):
        path = self.make_snapshot()
        link = self.root / "link.sqlite"
        link.symlink_to(path)
        self.assertEqual(self.inspect(link).result, planner.BLOCKED)

    def test_symlink_parent_blocks(self):
        path = self.make_snapshot()
        real = self.root / "real"
        real.mkdir()
        nested = real / "snapshot.sqlite"
        path.replace(nested)
        link = self.root / "linked"
        link.symlink_to(real, target_is_directory=True)
        self.assertEqual(self.inspect(link / "snapshot.sqlite").result, planner.BLOCKED)

    def test_directory_snapshot_blocks(self):
        self.assertEqual(self.inspect(self.root).result, planner.BLOCKED)

    def test_empty_snapshot_blocks(self):
        path = self.root / "empty.sqlite"
        path.write_bytes(b"")
        self.assertEqual(self.inspect(path).result, planner.BLOCKED)

    def test_oversized_snapshot_blocks(self):
        path = self.root / "large.sqlite"
        with path.open("wb") as handle:
            handle.truncate(planner.MAX_SNAPSHOT_BYTES + 1)
        self.assertEqual(self.inspect(path).result, planner.BLOCKED)

    def test_json_depth_abuse_blocks(self):
        value = []
        current = value
        for _ in range(planner.MAX_JSON_DEPTH + 2):
            nested = []
            current.append(nested)
            current = nested
        with self.assertRaises(planner.Blocked):
            planner.check_json_limits(value)

    def test_json_collection_abuse_blocks(self):
        with self.assertRaises(planner.Blocked):
            planner.check_json_limits([0] * (planner.MAX_COLLECTION_ITEMS + 1))

    def test_deep_json_beyond_python_recursion_is_machine_readable_blocked(self):
        payload = self.root / "deep.json"
        payload.write_text("[" * 2_000 + "0" + "]" * 2_000, encoding="utf-8")
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            exit_status = planner.main([
                "shadow_repair_plan_verify",
                "--snapshot-reference", str(payload),
                "--repair-evidence", str(payload),
                "--repair-plan", str(payload),
                "--verification-id", "verification:w3b-a:test:deep",
                "--verified-at", "2026-08-25T10:01:00Z",
            ])
        result = json.loads(output.getvalue())
        self.assertEqual(exit_status, 3)
        self.assertEqual(result["result"], planner.BLOCKED)
        self.assertNotIn("Traceback", output.getvalue())

    def test_deep_in_memory_verification_document_blocks(self):
        snapshot, evidence, plan = self.fixture_documents()
        value = []
        current = value
        for _ in range(planner.MAX_JSON_DEPTH + 2):
            nested = []
            current.append(nested)
            current = nested
        snapshot["unexpected_nested_value"] = value
        result = self.verify_fixture(snapshot, evidence, plan)
        self.assertEqual(result.result, planner.BLOCKED)

    def test_schema_object_ceiling_blocks(self):
        def mutate(connection):
            for index in range(planner.MAX_SCHEMA_OBJECTS + 1):
                connection.execute(f'CREATE TABLE "extra_{index:03d}"(value TEXT)')

        self.assertEqual(self.inspect(self.make_snapshot(mutate)).result, planner.BLOCKED)

    def test_bounded_row_ceiling_blocks(self):
        def mutate(connection):
            connection.executemany(
                "INSERT INTO store_metadata VALUES (?, ?)",
                ((f"extra_{index:05d}", "value") for index in range(planner.MAX_ROWS_INSPECTED + 1)),
            )

        self.assertEqual(self.inspect(self.make_snapshot(mutate)).result, planner.BLOCKED)

    def test_extracted_text_ceiling_blocks(self):
        path = self.make_snapshot(lambda connection: connection.execute(
            "INSERT INTO store_metadata VALUES (?, ?)",
            ("oversized_text", "x" * (planner.MAX_EXTRACTED_VALUE_BYTES + 1)),
        ))
        self.assertEqual(self.inspect(path).result, planner.BLOCKED)

    def test_extracted_blob_ceiling_blocks(self):
        path = self.make_snapshot(lambda connection: connection.execute(
            "INSERT INTO store_metadata VALUES (?, ?)",
            ("oversized_blob", sqlite3.Binary(b"x" * (planner.MAX_EXTRACTED_VALUE_BYTES + 1))),
        ))
        self.assertEqual(self.inspect(path).result, planner.BLOCKED)

    def test_sqlite_vm_progress_ceiling_blocks(self):
        with (
            mock.patch.object(planner, "MAX_VM_CALLBACKS", 0),
            mock.patch.object(planner, "VM_PROGRESS_INTERVAL", 1),
        ):
            result = self.inspect(self.make_snapshot())
        self.assertEqual(result.result, planner.BLOCKED)


class SnapshotInspectionTests(W3BATestCase):
    def test_valid_canonical_snapshot_inspects(self):
        result = self.inspect()
        self.assertEqual(result.result, planner.PASS)
        self.assertEqual(result.data["inspection"]["findings"], [])

    def test_snapshot_bytes_unchanged_after_inspection(self):
        path = self.make_snapshot()
        before = path.read_bytes()
        self.assertEqual(self.inspect(path).result, planner.PASS)
        self.assertEqual(path.read_bytes(), before)

    def test_aba_path_replacement_cannot_change_inspected_bytes(self):
        path = self.make_snapshot()
        replacement = self.root / "replacement.sqlite"
        replacement.write_bytes(path.read_bytes())
        with sqlite3.connect(replacement) as connection:
            connection.execute("DROP INDEX idx_audit_events_aggregate")
        original_inspect = planner.inspect_connection

        def replace_restore(connection):
            held_original = self.root / "held-original.sqlite"
            path.replace(held_original)
            replacement.replace(path)
            try:
                return original_inspect(connection)
            finally:
                path.replace(replacement)
                held_original.replace(path)

        with mock.patch.object(planner, "inspect_connection", side_effect=replace_restore):
            result = self.inspect(path)
        self.assertEqual(result.result, planner.PASS)
        self.assertEqual(result.data["inspection"]["findings"], [])

    def test_persistent_path_replacement_blocks(self):
        path = self.make_snapshot()
        replacement = self.root / "replacement.sqlite"
        replacement.write_bytes(path.read_bytes())
        with sqlite3.connect(replacement) as connection:
            connection.execute("DROP INDEX idx_audit_events_aggregate")
        original_inspect = planner.inspect_connection

        def replace_source(connection):
            path.replace(self.root / "held-original.sqlite")
            replacement.replace(path)
            return original_inspect(connection)

        with mock.patch.object(planner, "inspect_connection", side_effect=replace_source):
            result = self.inspect(path)
        self.assertEqual(result.result, planner.BLOCKED)

    def test_snapshot_change_during_inspection_blocks(self):
        path = self.make_snapshot()
        original = planner.inspect_connection

        def change(connection):
            result = original(connection)
            path.write_bytes(path.read_bytes() + b"x")
            return result

        with mock.patch.object(planner, "inspect_connection", side_effect=change):
            result = self.inspect(path)
        self.assertEqual(result.result, planner.BLOCKED)

    def test_snapshot_truncation_during_inspection_blocks(self):
        path = self.make_snapshot()
        original = planner.inspect_connection

        def truncate(connection):
            result = original(connection)
            with path.open("r+b") as handle:
                handle.truncate(max(1, path.stat().st_size // 2))
            return result

        with mock.patch.object(planner, "inspect_connection", side_effect=truncate):
            result = self.inspect(path)
        self.assertEqual(result.result, planner.BLOCKED)

    def test_malformed_database_blocks_without_traceback(self):
        path = self.root / "malformed.sqlite"
        path.write_bytes(b"not-a-sqlite-database")
        result = self.inspect(path)
        self.assertEqual(result.result, planner.BLOCKED)
        self.assert_taint(result)

    def test_unsupported_version_is_non_repairable(self):
        path = self.make_snapshot(lambda db: db.execute("PRAGMA user_version=200"))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "UNSUPPORTED_USER_VERSION" and item["classification"] == "NON_REPAIRABLE_PRESERVE_AND_BLOCK" for item in findings))

    def test_missing_metadata_table_is_non_repairable(self):
        path = self.make_snapshot(lambda db: db.execute("DROP TABLE store_metadata"))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "MISSING_REQUIRED_TABLE" and item["object_reference"] == "store_metadata" for item in findings))

    def test_metadata_mismatch_requires_manual_decision(self):
        path = self.make_snapshot(lambda db: db.execute("UPDATE store_metadata SET metadata_value='9.0' WHERE metadata_key='state_store_version'"))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "STORE_METADATA_MISMATCH" and item["classification"] == "MANUAL_DECISION_REQUIRED" for item in findings))

    def test_missing_table_preserves_and_blocks(self):
        path = self.make_snapshot(lambda db: db.execute("DROP TABLE grant_observations"))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "MISSING_REQUIRED_TABLE" and item["classification"] == "NON_REPAIRABLE_PRESERVE_AND_BLOCK" for item in findings))

    def test_missing_index_is_deterministic_plan_candidate(self):
        path = self.make_snapshot(lambda db: db.execute("DROP INDEX idx_audit_events_aggregate"))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "MISSING_REQUIRED_INDEX" and item["classification"] == "DETERMINISTIC_PLAN_CANDIDATE" for item in findings))

    def test_missing_trigger_requires_manual_decision(self):
        path = self.make_snapshot(lambda db: db.execute("DROP TRIGGER audit_events_no_update"))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "MISSING_REQUIRED_TRIGGER" and item["classification"] == "MANUAL_DECISION_REQUIRED" for item in findings))

    def test_unexpected_schema_object_fails_closed(self):
        path = self.make_snapshot(lambda db: db.execute("CREATE TABLE unexpected_object(value TEXT)"))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "UNEXPECTED_SCHEMA_OBJECT" and item["classification"] == "AMBIGUOUS_FAIL_CLOSED" for item in findings))

    def test_valid_non_empty_w3a_audit_chain_is_consistent(self):
        path = self.make_snapshot(lambda connection: self.add_audit_event(connection))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertFalse(any(item["code"] == "AUDIT_CHAIN_INCONSISTENCY" for item in findings))

    def test_audit_genesis_and_hash_match_durable_w3a(self):
        row = {
            "sequence": 1,
            "event_type": "GRANT_OBSERVATION",
            "aggregate_type": "GRANT_OBSERVATION",
            "aggregate_id": "grant:test:001",
            "payload_digest": "sha256:" + "1" * 64,
            "previous_hash": planner.AUDIT_GENESIS,
            "observed_at": "2026-08-25T10:00:00Z",
        }
        self.assertEqual(planner.AUDIT_GENESIS, "GENESIS")
        self.assertEqual(
            planner.audit_hash(row),
            w3a.audit_hash(
                row["previous_hash"], row["sequence"], row["event_type"],
                row["aggregate_type"], row["aggregate_id"],
                row["payload_digest"], row["observed_at"],
            ),
        )

    def test_tampered_w3a_audit_chain_is_detected(self):
        path = self.make_snapshot(lambda connection: self.add_audit_event(
            connection, "sha256:" + "9" * 64,
        ))
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "AUDIT_CHAIN_INCONSISTENCY" for item in findings))

    def test_audit_chain_inconsistency_requires_manual_decision(self):
        def mutate(db):
            db.execute("DROP TRIGGER audit_events_no_update")
            db.execute("INSERT INTO audit_events VALUES (1,'audit:bad','x','GRANT_OBSERVATION','g','sha256:" + "1" * 64 + "','sha256:" + "0" * 64 + "','sha256:" + "2" * 64 + "','2026-08-25T10:00:00Z','UNAUTHENTICATED_SHADOW','NONE','NONE','NONE','NONE',0)")
        path = self.make_snapshot(mutate)
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "AUDIT_CHAIN_INCONSISTENCY" and item["classification"] == "MANUAL_DECISION_REQUIRED" for item in findings))

    def test_state_event_conflict_requires_manual_decision(self):
        def mutate(db):
            values = ("a", "VALIDATED", "RESERVED", 3, "2026-08-25T10:00:00Z", "2026-08-25T10:00:00Z", "UNAUTHENTICATED_SHADOW", "NONE", "NONE", "NONE", "NONE", 0)
            db.execute("INSERT INTO authorization_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", values)
        path = self.make_snapshot(mutate)
        findings = self.inspect(path).data["inspection"]["findings"]
        self.assertTrue(any(item["code"] == "STATE_EVENT_INCONSISTENCY" for item in findings))

    def test_snapshot_reference_records_limitations(self):
        reference = self.inspect().data["snapshot_reference"]
        self.assertEqual(set(reference["identity_limitations"]), set(planner.IDENTITY_LIMITATIONS))

    def test_same_snapshot_inspection_is_deterministic(self):
        path = self.make_snapshot()
        left = self.inspect(path).data
        right = self.inspect(path).data
        self.assertEqual(left, right)

    def test_read_only_connection_denies_insert(self):
        path = self.make_snapshot()
        connection = planner.open_snapshot_read_only(path)
        self.addCleanup(connection.close)
        with self.assertRaises(sqlite3.DatabaseError):
            connection.execute("INSERT INTO store_metadata VALUES ('x','y')")

    def test_read_only_connection_denies_attach(self):
        path = self.make_snapshot()
        connection = planner.open_snapshot_read_only(path)
        self.addCleanup(connection.close)
        with self.assertRaises(sqlite3.DatabaseError):
            connection.execute("ATTACH DATABASE ':memory:' AS other")


class PlanAndVerificationTests(W3BATestCase):
    def test_healthy_snapshot_generates_empty_symbolic_diff(self):
        result = self.plan()
        self.assertEqual(result.result, planner.PASS)
        self.assertEqual(result.data["repair_plan"]["proposed_diff"], [])

    def test_missing_index_generates_only_declarative_gap(self):
        path = self.make_snapshot(lambda db: db.execute("DROP INDEX idx_audit_events_aggregate"))
        plan = self.plan(path).data["repair_plan"]
        self.assertEqual([item["action"] for item in plan["proposed_diff"]], ["DECLARE_CANONICAL_INDEX_GAP"])

    def test_store_controlled_object_name_cannot_select_plan_action(self):
        path = self.make_snapshot(lambda db: db.execute('CREATE TABLE "DROP_TABLE_audit_events"(value TEXT)'))
        result = self.plan(path)
        self.assertEqual(result.result, planner.PASS)
        plan = result.data["repair_plan"]
        self.assertEqual([item["action"] for item in plan["proposed_diff"]], ["REPORT_AMBIGUITY"])
        self.assertNotIn("DROP_TABLE", planner.canonical_json(plan["proposed_diff"]))

    def test_unexpected_metadata_key_is_opaque_in_plan(self):
        token = "raw_metadata_plan_poison"
        path = self.make_snapshot(lambda connection: connection.execute(
            "INSERT INTO store_metadata VALUES (?, ?)", (token, "value"),
        ))
        result = self.plan(path)
        self.assertEqual(result.result, planner.PASS)
        self.assertNotIn(token, planner.canonical_json(result.data["repair_plan"]))

    def test_store_controlled_authorization_id_is_opaque_in_plan(self):
        token = "raw_authorization_plan_poison"

        def mutate(connection):
            values = (
                token, "VALIDATED", "RESERVED", 3,
                "2026-08-25T10:00:00Z", "2026-08-25T10:00:00Z",
                "UNAUTHENTICATED_SHADOW", "NONE", "NONE", "NONE", "NONE", 0,
            )
            connection.execute("INSERT INTO authorization_state VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", values)

        result = self.plan(self.make_snapshot(mutate))
        self.assertEqual(result.result, planner.PASS)
        self.assertNotIn(token, planner.canonical_json(result.data["repair_plan"]))

    def test_same_evidence_generates_same_plan_digest(self):
        path = self.make_snapshot(lambda db: db.execute("DROP INDEX idx_audit_events_aggregate"))
        left = self.plan(path).data["repair_plan"]
        right = self.plan(path).data["repair_plan"]
        self.assertEqual(left, right)

    def test_valid_plan_verification_is_terminal(self):
        result = self.verify_fixture()
        self.assertEqual(result.result, planner.PASS)
        self.assertEqual(result.data["verification_state"], "PLAN_VERIFIED")
        self.assertEqual(planner.PLAN_STATE_GRAPH["PLAN_VERIFIED"], ())

    def test_plan_digest_mismatch_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["plan_digest"] = "sha256:" + "9" * 64
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_wrong_snapshot_binding_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["snapshot_digest"] = "sha256:" + "3" * 64
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_wrong_snapshot_size_binding_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["snapshot_size"] += 1
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_wrong_version_binding_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["observed_store_version"] = 99
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_wrong_evidence_digest_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["evidence_set_digest"] = "sha256:" + "4" * 64
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_evidence_self_digest_mismatch_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        evidence["created_at"] = "2026-08-25T11:00:00Z"
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_healthy_key_mutation_proposal_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["proposed_diff"][0]["action"] = "SET_METADATA"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_destructive_deletion_proposal_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["proposed_diff"][0]["action"] = "DELETE_TABLE"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_executable_sql_in_plan_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["proposed_diff"][0]["rationale"] = "DROP TABLE audit_events"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_shell_directive_in_plan_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["proposed_diff"][0]["rationale"] = "rm -rf snapshot"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_python_directive_in_plan_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["proposed_diff"][0]["rationale"] = "import sqlite3"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_authority_effect_laundering_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["authority_effect"] = "GRANTED"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_execution_effect_laundering_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["execution_effect"] = "EXECUTE"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_mutation_effect_laundering_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["mutation_effect"] = "MUTATE"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_execution_eligibility_laundering_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["eligible_for_execution"] = True
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_w3a_pass_laundering_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["w3a_result"] = "PASS"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_w3a_blocked_laundering_denied(self):
        snapshot, evidence, plan = self.fixture_documents()
        plan["w3a_result"] = "BLOCKED"
        plan["plan_digest"] = planner.digest_without(plan, "plan_digest")
        self.assertEqual(self.verify_fixture(snapshot, evidence, plan).result, planner.DENY)

    def test_unexpected_exception_is_machine_readable_blocked(self):
        with mock.patch.object(planner, "inspect_supplied_snapshot", side_effect=RuntimeError("unexpected")):
            result = planner.shadow_snapshot_inspect("x", self.root, "store:test", "2026-08-25T10:00:00Z")
        self.assertEqual(result.result, planner.BLOCKED)
        self.assertEqual(result.reason_code, "UNEXPECTED_OPERATION_ERROR")
        self.assert_taint(result)


class StaticCapabilityTests(W3BATestCase):
    def test_allowed_operation_vocabulary_is_exact(self):
        self.assertEqual(planner.ALLOWED_OPERATIONS, {
            "shadow_snapshot_inspect", "shadow_repair_inspect",
            "shadow_repair_plan", "shadow_repair_plan_verify",
        })

    def test_cli_operation_vocabulary_is_exact(self):
        parser = planner.build_parser()
        action = next(value for value in parser._actions if isinstance(value, argparse._SubParsersAction))
        self.assertEqual(set(action.choices), planner.ALLOWED_OPERATIONS)

    def test_no_apply_restore_reconcile_authorize_accept_api(self):
        for name in dir(planner):
            if callable(getattr(planner, name)):
                self.assertFalse(re.search(r"(?:^|_)(apply|restore|reconcile|authorize|accept)(?:_|$)", name))

    def test_no_w3b_b_or_c_import(self):
        source = SCRIPT.read_text(encoding="utf-8").lower()
        self.assertNotIn("import acos_w3b_b", source)
        self.assertNotIn("import acos_w3b_c", source)

    def test_no_sql_mutation_execution_implementation(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"execute\(\s*['\"]\s*(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|REPLACE|VACUUM|REINDEX)\b", source, re.IGNORECASE))

    def test_sqlite_uri_is_read_only_and_immutable(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("mode=ro&immutable=1", source)
        self.assertIn("PRAGMA query_only=ON", source)

    def test_extension_loading_is_disabled(self):
        self.assertIn("enable_load_extension(False)", SCRIPT.read_text(encoding="utf-8"))

    def test_trusted_schema_is_disabled(self):
        self.assertIn("PRAGMA trusted_schema=OFF", SCRIPT.read_text(encoding="utf-8"))

    def test_plan_state_graph_terminates(self):
        self.assertEqual(planner.PLAN_STATE_GRAPH, {"PLANNED": ("PLAN_VERIFIED",), "PLAN_VERIFIED": ()})

    def test_canonical_sql_digest_matches(self):
        actual = planner.hashlib.sha256(SQL_PATH.read_bytes()).hexdigest()
        self.assertEqual(actual, planner.EXPECTED_CANONICAL_SQL_SHA256)

    def test_canonical_baseline_mismatch_blocks(self):
        with mock.patch.object(planner, "EXPECTED_CANONICAL_SQL_SHA256", "0" * 64):
            result = self.inspect(self.make_snapshot())
        self.assertEqual(result.reason_code, "CANONICAL_BASELINE_MISMATCH")

    def test_all_result_classes_preserve_taint(self):
        for value in (planner.PASS, planner.DENY, planner.BLOCKED):
            self.assert_taint(planner.make_result("shadow_repair_inspect", value, value, value))


def _make_authorizer_denial_test(action_name):
    def test(self):
        action = getattr(sqlite3, action_name)
        self.assertEqual(planner.sqlite_read_only_authorizer(action, None, None, None, None), sqlite3.SQLITE_DENY)
    return test


for _action_name in (
    "SQLITE_INSERT", "SQLITE_UPDATE", "SQLITE_DELETE", "SQLITE_CREATE_INDEX",
    "SQLITE_CREATE_TABLE", "SQLITE_CREATE_TEMP_INDEX", "SQLITE_CREATE_TEMP_TABLE",
    "SQLITE_CREATE_TEMP_TRIGGER", "SQLITE_CREATE_TEMP_VIEW", "SQLITE_CREATE_TRIGGER",
    "SQLITE_CREATE_VIEW", "SQLITE_DROP_INDEX", "SQLITE_DROP_TABLE",
    "SQLITE_DROP_TEMP_INDEX", "SQLITE_DROP_TEMP_TABLE", "SQLITE_DROP_TEMP_TRIGGER",
    "SQLITE_DROP_TEMP_VIEW", "SQLITE_DROP_TRIGGER", "SQLITE_DROP_VIEW",
    "SQLITE_ALTER_TABLE", "SQLITE_CREATE_VTABLE", "SQLITE_DROP_VTABLE",
    "SQLITE_ATTACH", "SQLITE_DETACH", "SQLITE_TRANSACTION", "SQLITE_SAVEPOINT",
    "SQLITE_REINDEX", "SQLITE_ANALYZE",
):
    if hasattr(sqlite3, _action_name):
        setattr(StaticCapabilityTests, f"test_authorizer_denies_{_action_name.lower()}", _make_authorizer_denial_test(_action_name))


if __name__ == "__main__":
    unittest.main()

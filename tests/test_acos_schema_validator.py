from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acos-schema-validator.py"
FIXTURES = ROOT / "fixtures" / "schema-validation"

SPEC = importlib.util.spec_from_file_location("acos_schema_validator", SCRIPT)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


class SchemaValidatorTests(unittest.TestCase):
    def load(self, name: str):
        return gate.load_fixture(FIXTURES / name)

    def test_modes_coverage(self):
        self.assertEqual(gate.MODES, {"validate_envelope", "validate_policy"})

    def test_valid_fixtures(self):
        for name in ("valid-envelope.json", "valid-policy.json"):
            with self.subTest(name=name):
                res = self.load(name)
                self.assertEqual(res.result, gate.PASS, res.reason)

    def test_fixture_inventory_and_determinism(self):
        paths_one, errors_one = gate.discover_paths([str(FIXTURES)])
        paths_two, errors_two = gate.discover_paths([str(FIXTURES)])
        self.assertEqual(paths_one, paths_two)
        self.assertEqual(errors_one, errors_two)
        self.assertEqual(len(paths_one), 9)
        self.assertEqual(self.load("valid-envelope.json"), self.load("valid-envelope.json"))

    def test_invalid_fixtures_deny(self):
        for name in (
            "invalid-envelope-missing-id.json",
            "invalid-envelope-unknown-type.json",
            "invalid-policy-missing-metadata.json"
        ):
            with self.subTest(name=name):
                res = self.load(name)
                self.assertEqual(res.result, gate.DENY, res.reason)

    def test_blocked_fixtures(self):
        for name in (
            "blocked-malformed.json",
            "blocked-root-array.json",
            "blocked-missing-mode.json",
            "blocked-unknown-mode.json"
        ):
            with self.subTest(name=name):
                res = self.load(name)
                self.assertEqual(res.result, gate.BLOCKED, res.reason)

    def test_format_and_envelope_authority_constraints(self):
        cases = {
            "invalid date-time": {"created_at": "not-a-date"},
            "invalid producer role": {"producer_role": "unknown_role"},
            "invalid runtime id": {"producer_runtime_id": "Vendor Runtime Name"},
            "invalid digest": {"content_digest": "sha256:not-a-digest"},
            "invalid signature": {"signature": "not-a-signature"},
            "expired before creation": {"expires_at": "2026-07-11T19:30:00Z"},
            "scope traversal": {"scope": ["../outside"]},
            "replay widening": {"replay_protection": {"class": "one_time", "max_consumption": 2}},
        }
        for label, changes in cases.items():
            with self.subTest(label=label):
                fixture = copy.deepcopy(gate.TEMPLATES["valid_envelope"])
                fixture.update(changes)
                result = gate.evaluate_fixture(fixture)
                self.assertEqual(result.result, gate.DENY, result.reason)

        fixture = copy.deepcopy(gate.TEMPLATES["valid_envelope"])
        fixture["producer_runtime_id"] = "future-agent-runtime-01"
        result = gate.evaluate_fixture(fixture)
        self.assertEqual(result.result, gate.PASS, result.reason)

    def test_policy_semantic_constraints(self):
        cases = {
            "invalid effective time": {"effective_time": "not-a-date"},
            "invalid rollback": {"rollback_target_version": "1.0"},
            "invalid compatibility": {
                "minimum_supported_schema_version": "2.0",
                "maximum_supported_schema_version": "1.0",
            },
        }
        for label, changes in cases.items():
            with self.subTest(label=label):
                fixture = copy.deepcopy(gate.TEMPLATES["valid_policy"])
                fixture["policy_metadata"].update(changes)
                result = gate.evaluate_fixture(fixture)
                self.assertEqual(result.result, gate.DENY, result.reason)

        fixture = copy.deepcopy(gate.TEMPLATES["valid_policy"])
        fixture["filesystem_policies"]["protected_roots"] = ["../outside"]
        result = gate.evaluate_fixture(fixture)
        self.assertEqual(result.result, gate.DENY, result.reason)

        authority_cases = {
            "codex decision": ("codex_executor", "DECISION"),
            "advisory task": ("external_advisory", "TASK"),
            "automation review": ("automation", "REVIEW"),
            "chatgpt result": ("chatgpt_review", "RESULT"),
        }
        for label, (role, artifact) in authority_cases.items():
            with self.subTest(label=label):
                fixture = copy.deepcopy(gate.TEMPLATES["valid_policy"])
                fixture["role_permissions"][role]["allowed_artifacts"] = [artifact]
                result = gate.evaluate_fixture(fixture)
                self.assertEqual(result.result, gate.DENY, result.reason)

    def test_parser_and_schema_fail_closed(self):
        with self.assertRaises(gate.DuplicateKey):
            json.loads('{"duplicate": 1, "duplicate": 2}', object_pairs_hook=gate.reject_duplicate_keys)
        for reference in (
            "http://example.invalid/schema.json",
            "https://example.invalid/schema.json",
            "file:///tmp/schema.json",
        ):
            with self.subTest(reference=reference):
                with self.assertRaises(gate.Blocked):
                    gate.assert_local_references({"$ref": reference})

        nested: dict[str, object] = {}
        cursor = nested
        for _ in range(gate.MAX_JSON_DEPTH + 1):
            child: dict[str, object] = {}
            cursor["nested"] = child
            cursor = child
        fixture = {"mode": "validate_envelope", "payload": nested}
        result = gate.evaluate_fixture(fixture)
        self.assertEqual(result.result, gate.BLOCKED, result.reason)

        with mock.patch.object(gate, "MAX_FIXTURE_BYTES", 1):
            result = self.load("valid-envelope.json")
        self.assertEqual(result.result, gate.BLOCKED, result.reason)

        with mock.patch.object(gate, "MAX_SCHEMA_BYTES", 1):
            result = gate.evaluate_fixture(copy.deepcopy(gate.TEMPLATES["valid_envelope"]))
        self.assertEqual(result.result, gate.BLOCKED, result.reason)

    def test_path_confinement_and_missing_targets(self):
        traversal = FIXTURES / ".." / "schema-validation" / "valid-envelope.json"
        paths, errors = gate.discover_paths([str(traversal)])
        self.assertEqual(paths, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("parent traversal", errors[0].reason)

        outside = ROOT / "fixtures" / "schemas" / "envelope.schema.json"
        paths, errors = gate.discover_paths([str(outside)])
        self.assertEqual(paths, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].result, gate.BLOCKED)

        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / "fixture.json"
            try:
                link.symlink_to(FIXTURES / "valid-envelope.json")
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            paths, errors = gate.discover_paths([str(link)])
            self.assertEqual(paths, [])
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].result, gate.BLOCKED)
            self.assertIn("symbolic link", errors[0].reason)

        missing = FIXTURES / "does-not-exist.json"
        paths, errors = gate.discover_paths([str(missing)])
        self.assertEqual(paths, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].result, gate.BLOCKED)

    def test_text_and_json_rendering(self):
        res = self.load("valid-envelope.json")
        text_out = gate.render_text([res])
        self.assertIn("Schema validation passed", text_out)
        self.assertIn("validate_envelope", text_out)

        json_out = json.loads(json.dumps([gate.asdict(res)]))[0]
        self.assertEqual(json_out["result"], gate.PASS)

    def test_cli_execution_and_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            # Valid fixture exits with 0
            self.assertEqual(gate.main([str(FIXTURES / "valid-envelope.json")]), 0)
            # All fixtures run successfully exits with 0 (since all match expected_result)
            self.assertEqual(gate.main([str(FIXTURES)]), 0)

            # Missing or out-of-root targets are unexpected operational blockers.
            self.assertEqual(gate.main([str(FIXTURES / "does-not-exist.json")]), 2)

        mismatch = gate.make_result(
            {"case_id": "mismatch", "expected_result": "DENY"},
            str(FIXTURES / "valid-envelope.json"),
            gate.PASS,
            "synthetic mismatch",
        )
        with mock.patch.object(gate, "load_fixture", return_value=mismatch):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main([str(FIXTURES / "valid-envelope.json")]), 1)

    def test_dependency_and_schema_errors_are_blocked(self):
        with (
            mock.patch.object(gate, "jsonschema", None),
            mock.patch.object(gate, "Draft7Validator", None),
            mock.patch.object(gate, "FORMAT_CHECKER", None),
            mock.patch.object(gate, "JSONSCHEMA_IMPORT_ERROR", ModuleNotFoundError("jsonschema")),
        ):
            result = gate.evaluate_fixture(copy.deepcopy(gate.TEMPLATES["valid_envelope"]))
        self.assertEqual(result.result, gate.BLOCKED, result.reason)
        self.assertIn("dependency unavailable", result.reason)

        with mock.patch.object(gate, "ENVELOPE_SCHEMA_PATH", FIXTURES / "does-not-exist.json"):
            result = gate.evaluate_fixture(copy.deepcopy(gate.TEMPLATES["valid_envelope"]))
        self.assertEqual(result.result, gate.BLOCKED, result.reason)

        with mock.patch.object(gate, "POLICY_SCHEMA_PATH", FIXTURES / "does-not-exist.json"):
            result = gate.evaluate_fixture(copy.deepcopy(gate.TEMPLATES["valid_policy"]))
        self.assertEqual(result.result, gate.BLOCKED, result.reason)

        with mock.patch.object(gate, "ENVELOPE_SCHEMA_PATH", FIXTURES / "blocked-malformed.json"):
            result = gate.evaluate_fixture(copy.deepcopy(gate.TEMPLATES["valid_envelope"]))
        self.assertEqual(result.result, gate.BLOCKED, result.reason)
        self.assertIn("parse envelope schema JSON", result.reason)

        with mock.patch.object(gate, "read_json", return_value={"type": "not-a-json-schema-type"}):
            with self.assertRaises(gate.Blocked) as caught:
                gate.load_validator(gate.ENVELOPE_SCHEMA_PATH, "envelope")
        self.assertIn("invalid envelope schema", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

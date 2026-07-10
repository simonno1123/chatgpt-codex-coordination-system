from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "acos-filesystem-permission-checker.py"
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "filesystem-permission"

SPEC = importlib.util.spec_from_file_location("acos_filesystem_permission_checker", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load checker: {SCRIPT_PATH}")

checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


class FilesystemPermissionCheckerTests(unittest.TestCase):
    def codex_fixture(self, operation: str, target_path: object = "scripts/new-tool.py") -> dict:
        return {
            "case_id": f"codex-{operation}",
            "runtime_identity": "Codex Executor Runtime",
            "producer": "Codex Executor",
            "operation": operation,
            "target_path": target_path,
            "repository_scope": "ACOS CORE",
            "task_allowed_paths": ["scripts/new-tool.py"],
            "governance_authorized": True,
        }

    def test_all_operations_are_modeled(self) -> None:
        expected = {
            "inspect": checker.PASS,
            "read": checker.PASS,
            "create": checker.PASS,
            "edit": checker.PASS,
            "delete": checker.DENY,
            "stage": checker.PASS,
            "commit": checker.PASS,
            "push": checker.PASS,
            "release": checker.PASS,
        }
        self.assertEqual(set(expected), checker.KNOWN_OPERATIONS)
        for operation, expected_result in expected.items():
            with self.subTest(operation=operation):
                result = checker.evaluate_fixture(self.codex_fixture(operation))
                self.assertEqual(result.result, expected_result)
                if operation in checker.GIT_RELEASE_OPERATIONS:
                    self.assertIn("not granted", result.reason)

    def test_all_runtime_identities_are_modeled(self) -> None:
        fixtures = [
            {
                "runtime_identity": "ChatGPT Review Runtime",
                "producer": "ChatGPT Review",
                "operation": "read",
                "target_path": "docs/policy.md",
                "repository_scope": "ACOS CORE",
            },
            self.codex_fixture("create"),
            {
                "runtime_identity": "External Advisory Runtime",
                "producer": "External Advisory Reviewer",
                "operation": "inspect",
                "target_path": "scripts/tool.py",
                "repository_scope": "ACOS CORE",
            },
            {
                "runtime_identity": "Automation Runtime",
                "producer": "Automation",
                "operation": "create",
                "target_path": ".codex-coordination/outbox/record.json",
                "repository_scope": "ACOS CORE",
                "artifact_type": "RECORD",
                "automation_allowed_paths": [
                    ".codex-coordination/outbox/record.json"
                ],
            },
        ]
        for fixture in fixtures:
            with self.subTest(runtime=fixture["runtime_identity"]):
                self.assertEqual(checker.evaluate_fixture(fixture).result, checker.PASS)

    def test_dot_segments_are_normalized_lexically(self) -> None:
        result = checker.evaluate_fixture(
            self.codex_fixture("create", "./scripts/./new-tool.py")
        )
        self.assertEqual(result.result, checker.PASS)
        self.assertEqual(result.normalized_path, "scripts/new-tool.py")
        self.assertEqual(result.path_class, checker.ACOS_EXECUTABLE_TOOLING)

    def test_in_root_parent_traversal_is_denied(self) -> None:
        fixture = self.codex_fixture("edit", "docs/../scripts/new-tool.py")
        result = checker.evaluate_fixture(fixture)
        self.assertEqual(result.result, checker.DENY)
        self.assertEqual(result.normalized_path, "scripts/new-tool.py")

    def test_repository_root_escape_is_blocked(self) -> None:
        result = checker.evaluate_fixture(
            self.codex_fixture("edit", "../../outside.txt")
        )
        self.assertEqual(result.result, checker.BLOCKED)

    def test_cross_repository_absolute_path_is_denied(self) -> None:
        fixture = self.codex_fixture("edit", "/project-instance/src/app.py")
        fixture["task_allowed_paths"] = ["src/app.py"]
        result = checker.evaluate_fixture(fixture)
        self.assertEqual(result.result, checker.DENY)
        self.assertEqual(result.path_class, checker.BUSINESS_PROJECT_CLASS)

    def test_unknown_absolute_path_is_blocked(self) -> None:
        result = checker.evaluate_fixture(self.codex_fixture("edit", "/tmp/outside"))
        self.assertEqual(result.result, checker.BLOCKED)

    def test_missing_and_unknown_fields_are_blocked(self) -> None:
        cases = [
            {},
            {**self.codex_fixture("create"), "runtime_identity": "Unknown Runtime"},
            {**self.codex_fixture("create"), "operation": "teleport"},
            {**self.codex_fixture("create"), "target_path": 123},
            {**self.codex_fixture("create"), "repository_scope": "UNKNOWN"},
        ]
        for fixture in cases:
            with self.subTest(fixture=fixture):
                self.assertEqual(checker.evaluate_fixture(fixture).result, checker.BLOCKED)

    def test_declared_path_class_conflict_is_blocked(self) -> None:
        fixture = self.codex_fixture("create")
        fixture["path_class"] = "ACOS CORE DOCUMENTATION"
        result = checker.evaluate_fixture(fixture)
        self.assertEqual(result.result, checker.BLOCKED)

    def test_external_advisory_is_read_only(self) -> None:
        fixture = {
            "runtime_identity": "External Advisory Runtime",
            "producer": "External Advisory Reviewer",
            "operation": "edit",
            "target_path": "docs/policy.md",
            "repository_scope": "ACOS CORE",
        }
        self.assertEqual(checker.evaluate_fixture(fixture).result, checker.DENY)

    def test_instance_local_coordination_is_not_acos_core(self) -> None:
        fixture = {
            "runtime_identity": "Codex Executor Runtime",
            "producer": "Codex Executor",
            "operation": "create",
            "target_path": ".codex-coordination/outbox/result.md",
            "repository_scope": "BUSINESS PROJECT",
            "task_allowed_paths": [".codex-coordination/outbox/result.md"],
            "governance_authorized": True,
        }
        result = checker.evaluate_fixture(fixture)
        self.assertEqual(result.path_class, checker.INSTANCE_LOCAL_COORDINATION)
        self.assertEqual(result.result, checker.DENY)

    def test_text_output_contains_required_fields(self) -> None:
        result = checker.evaluate_fixture(self.codex_fixture("create"))
        output = checker.render_text([result])
        for field in (
            "runtime_identity:",
            "producer:",
            "operation:",
            "target_path:",
            "normalized_path:",
            "repository_scope:",
            "path_class:",
            "allowed:",
            "result:",
            "reason:",
            "source:",
            "expected_result:",
            "expectation_met:",
        ):
            self.assertIn(field, output)

    def test_json_output_contains_required_fields(self) -> None:
        result = checker.evaluate_fixture(self.codex_fixture("create"))
        item = json.loads(checker.render_json([result]))[0]
        required = {
            "case_id",
            "runtime_identity",
            "producer",
            "operation",
            "target_path",
            "normalized_path",
            "repository_scope",
            "path_class",
            "allowed",
            "result",
            "reason",
            "source",
            "expected_result",
            "expectation_met",
        }
        self.assertTrue(required.issubset(item))

    def test_single_file_cli_text_and_json(self) -> None:
        fixture = FIXTURE_ROOT / "valid-codex-create-script.json"
        for output_format in ("text", "json"):
            argv = ["--format", output_format, str(fixture)]
            with self.subTest(output_format=output_format), contextlib.redirect_stdout(
                io.StringIO()
            ) as captured:
                self.assertEqual(checker.main(argv), 0)
                self.assertTrue(captured.getvalue().strip())

    def test_directory_cli_exit_code_and_summary(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(checker.main([str(FIXTURE_ROOT)]), 0)
        self.assertIn("expectation_mismatches=0", captured.getvalue())

    def test_expectation_mismatch_returns_one(self) -> None:
        fixture = {
            **self.codex_fixture("delete"),
            "expected_result": "PASS",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mismatch.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(checker.main([str(path)]), 1)

    def test_all_repository_fixtures_match_expectations(self) -> None:
        fixture_paths = sorted(FIXTURE_ROOT.glob("*.json"))
        self.assertGreater(len(fixture_paths), 0)
        results = [checker.load_fixture(path) for path in fixture_paths]
        mismatches = [item.case_id for item in results if not item.expectation_met]
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()

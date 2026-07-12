from __future__ import annotations

import contextlib, copy, importlib.util, io, json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acos-user-decision-gate-checker.py"
FIXTURES = ROOT / "fixtures" / "user-decision-gate"
SPEC = importlib.util.spec_from_file_location("acos_user_decision_gate_checker", SCRIPT)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC); sys.modules[SPEC.name] = gate; SPEC.loader.exec_module(gate)


class UserDecisionGateTests(unittest.TestCase):
    def load(self, name): return gate.load_fixture(FIXTURES / name)

    def test_five_modes(self):
        files = ["valid-new-task-required.json", "valid-task-start-decision.json", "valid-chatgpt-consumes-task-start.json", "valid-exact-scope.json", "valid-complete-lifecycle.json"]
        self.assertEqual({self.load(name).mode for name in files}, gate.MODES)

    def test_three_requirement_levels(self):
        files = ["valid-readonly-not-required.json", "valid-new-task-required.json", "valid-existing-decision-satisfied.json"]
        self.assertEqual({self.load(name).calculated_requirement for name in files}, gate.LEVELS)

    def test_all_required_categories(self):
        base = copy.deepcopy(gate.TEMPLATES["classify_required"])
        for category, level in gate.CATEGORIES.items():
            if level == gate.REQUIRED:
                data = {**base, "requirement_category": category}
                self.assertEqual(gate.evaluate_fixture(data).result, gate.PASS)

    def test_valid_start_resume_and_git_decisions(self):
        for name in ("valid-task-start-decision.json", "valid-task-resume-decision.json", "valid-commit-decision.json", "valid-push-decision.json", "valid-release-decision.json"):
            self.assertEqual(self.load(name).result, gate.PASS, name)

    def test_live_enforcement_and_closure(self):
        for name in ("valid-live-connection-decision.json", "valid-enforcement-decision.json", "valid-task-closure-decision.json"):
            self.assertEqual(self.load(name).result, gate.PASS, name)

    def test_user_runtime_is_fixture_only_and_other_roles_denied(self):
        self.assertEqual(self.load("valid-task-start-decision.json").runtime_identity, gate.USER_RUNTIME)
        for name in ("invalid-codex-user-decision.json", "invalid-chatgpt-user-decision.json", "invalid-advisory-user-decision.json", "invalid-automation-user-decision.json"):
            self.assertEqual(self.load(name).result, gate.DENY, name)

    def test_non_user_artifacts_not_decisions(self):
        for name in ("invalid-advisory-as-user-decision.json", "invalid-audit-as-user-decision.json", "invalid-result-as-user-decision.json"):
            self.assertEqual(self.load(name).result, gate.DENY, name)

    def test_no_permission_inheritance(self):
        for name in ("invalid-task-start-used-for-commit.json", "invalid-task-start-used-for-push.json", "invalid-commit-used-for-push.json", "invalid-push-used-for-release.json"):
            self.assertEqual(self.load(name).result, gate.DENY, name)

    def test_scope_project_task_target_branch_head(self):
        self.assertEqual(self.load("valid-exact-scope.json").result, gate.PASS)
        self.assertEqual(self.load("valid-branch-head.json").result, gate.PASS)
        for name in ("invalid-old-task-authorization.json", "invalid-other-project-authorization.json", "invalid-wrong-target.json", "invalid-wrong-branch.json", "invalid-wrong-head.json", "invalid-wrong-scope.json"):
            self.assertEqual(self.load(name).result, gate.DENY, name)

    def test_statuses(self):
        for name in ("valid-denied-status.json", "valid-revoked-status.json", "valid-expired-status.json", "valid-superseded-status.json"):
            self.assertEqual(self.load(name).result, gate.PASS, name)
        for name in ("invalid-expired-consumed.json", "invalid-revoked-consumed.json", "invalid-superseded-consumed.json"):
            self.assertEqual(self.load(name).result, gate.DENY, name)

    def test_one_time_and_duplicate(self):
        self.assertEqual(self.load("valid-one-time-first-consumption.json").result, gate.PASS)
        self.assertEqual(self.load("valid-reusable-decision.json").result, gate.PASS)
        self.assertEqual(self.load("invalid-one-time-repeat.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-duplicate-authority.json").result, gate.DENY)

    def test_vague_merged_and_implicit_authority_denied(self):
        for name in ("invalid-unrestricted-action.json", "invalid-combined-commit-push.json", "invalid-future-tasks-authorization.json", "invalid-implicit-consent.json"):
            self.assertEqual(self.load(name).result, gate.DENY, name)

    def test_chatgpt_and_codex_scope_expansion_denied(self):
        self.assertEqual(self.load("invalid-chatgpt-expands-scope.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-codex-expands-scope.json").result, gate.DENY)

    def test_no_automatic_execution_or_next_task(self):
        for name in ("invalid-auto-close-task.json", "invalid-auto-enable-enforcement.json", "invalid-auto-connect-instance.json", "invalid-auto-start-task-057.json", "invalid-start-task-057-without-decision.json"):
            self.assertEqual(self.load(name).result, gate.DENY, name)

    def test_separate_operation_authorization(self):
        self.assertEqual(self.load("valid-codex-consumes-commit.json").result, gate.PASS)
        self.assertEqual(self.load("invalid-missing-operation-authorization.json").result, gate.DENY)

    def test_lifecycle(self):
        self.assertEqual(self.load("valid-complete-lifecycle.json").lifecycle_state, "DECISION_CONSUMED")
        self.assertEqual(self.load("blocked-lifecycle-contradiction.json").result, gate.BLOCKED)

    def test_blocked_missing_types_unknowns(self):
        for name in ("blocked-malformed-json.json", "blocked-root-array.json", "blocked-missing-mode.json", "blocked-unknown-mode.json", "blocked-missing-decision-id.json", "blocked-unknown-decision-type.json", "blocked-unknown-decision-status.json", "blocked-authorized-scope-type.json", "blocked-one-time-type.json", "blocked-status-expiry-contradiction.json"):
            self.assertEqual(self.load(name).result, gate.BLOCKED, name)

    def test_text_and_json_output(self):
        result = self.load("valid-task-start-decision.json")
        self.assertIn("calculated_requirement", gate.render_text([result]))
        self.assertIn("decision_id", json.loads(json.dumps([gate.asdict(result)]))[0])

    def test_cli_single_directory_and_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main([str(FIXTURES / "valid-task-start-decision.json")]), 0)
            self.assertEqual(gate.main([str(FIXTURES)]), 0)
            self.assertEqual(gate.main(["/private/tmp/no-user-decision-fixture.json"]), 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mismatch.json"; path.write_text(json.dumps({"template":"classify_required","expected_result":"DENY"}))
            with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(gate.main([str(path)]), 1)

    def test_all_fixtures_match(self):
        paths, errors = gate.discover_paths([str(FIXTURES)]); self.assertFalse(errors)
        results = [gate.load_fixture(path) for path in paths]
        self.assertEqual([r.case_id for r in results if not r.expectation_met], [])
        self.assertGreaterEqual(sum(r.result == gate.PASS for r in results), 20)
        self.assertGreaterEqual(sum(r.result == gate.DENY for r in results), 30)
        self.assertGreaterEqual(sum(r.result == gate.BLOCKED for r in results), 40)


if __name__ == "__main__": unittest.main()

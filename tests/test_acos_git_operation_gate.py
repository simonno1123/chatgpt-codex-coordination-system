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
SCRIPT_PATH = REPO_ROOT / "scripts" / "acos-git-operation-gate.py"
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "git-operation"

SPEC = importlib.util.spec_from_file_location("acos_git_operation_gate", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load gate: {SCRIPT_PATH}")

gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


class GitOperationGateTests(unittest.TestCase):
    def load(self, name: str):
        return gate.load_fixture(FIXTURE_ROOT / name)

    def test_all_operations_have_passing_dry_run_fixture(self) -> None:
        fixtures = {
            "inspect": "valid-chatgpt-inspect.json",
            "test": "valid-automation-test.json",
            "edit": "valid-codex-edit-authorized.json",
            "stage": "valid-codex-stage-authorized.json",
            "commit": "valid-codex-commit-authorized.json",
            "push": "valid-codex-push-authorized.json",
            "release": "valid-codex-release-authorized.json",
        }
        self.assertEqual(set(fixtures), gate.KNOWN_OPERATIONS)
        for operation, filename in fixtures.items():
            with self.subTest(operation=operation):
                result = self.load(filename)
                self.assertEqual(result.result, gate.PASS)
                self.assertIn(gate.DRY_RUN_NOTICE, result.reason)

    def test_all_runtime_identities_are_covered(self) -> None:
        fixtures = {
            "ChatGPT Review Runtime": "valid-chatgpt-inspect.json",
            "Codex Executor Runtime": "valid-codex-edit-authorized.json",
            "External Advisory Runtime": "valid-advisory-inspect.json",
            "Automation Runtime": "valid-automation-test.json",
        }
        self.assertEqual(set(fixtures), set(gate.RUNTIME_PRODUCERS))
        for runtime, filename in fixtures.items():
            with self.subTest(runtime=runtime):
                result = self.load(filename)
                self.assertEqual(result.runtime_identity, runtime)
                self.assertEqual(result.result, gate.PASS)

    def test_operation_authorizations_are_not_inherited(self) -> None:
        names = (
            "invalid-edit-auth-request-stage.json",
            "invalid-stage-auth-request-commit.json",
            "invalid-commit-auth-request-push.json",
            "invalid-push-auth-request-release.json",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_blanket_stage_patterns_are_denied(self) -> None:
        for name in (
            "invalid-git-add-dot.json",
            "invalid-git-add-A.json",
            "invalid-git-add-all.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_commit_all_and_amend_are_denied(self) -> None:
        self.assertEqual(self.load("invalid-git-commit-all.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-git-commit-amend.json").result, gate.DENY)

    def test_force_push_variants_are_denied(self) -> None:
        self.assertEqual(self.load("invalid-git-push-force.json").result, gate.DENY)
        self.assertEqual(
            self.load("invalid-git-push-force-with-lease.json").result, gate.DENY
        )

    def test_destructive_and_repair_commands_are_denied(self) -> None:
        names = (
            "invalid-git-reset-hard.json",
            "invalid-git-clean-fd.json",
            "invalid-git-pull.json",
            "invalid-git-merge.json",
            "invalid-git-rebase.json",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_branch_head_and_repository_mismatches_fail_closed(self) -> None:
        self.assertEqual(self.load("invalid-wrong-branch-commit.json").result, gate.DENY)
        self.assertEqual(
            self.load("blocked-authorization-head-conflict.json").result, gate.BLOCKED
        )
        self.assertEqual(
            self.load("invalid-wrong-repository-scope.json").result, gate.DENY
        )
        self.assertEqual(
            self.load("blocked-authorization-scope-conflict.json").result,
            gate.BLOCKED,
        )

    def test_push_ahead_behind_and_diverged(self) -> None:
        self.assertEqual(self.load("valid-codex-push-authorized.json").result, gate.PASS)
        self.assertEqual(self.load("invalid-push-behind.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-push-diverged.json").result, gate.DENY)

    def test_repository_state_catalog_is_complete(self) -> None:
        self.assertEqual(
            gate.KNOWN_WORKTREE_STATES,
            {
                "clean",
                "dirty_unstaged",
                "dirty_staged",
                "mixed",
                "untracked_only",
                "merge_in_progress",
                "rebase_in_progress",
                "cherry_pick_in_progress",
                "detached_head",
                "unknown",
            },
        )

    def test_in_progress_commits_are_denied(self) -> None:
        for name in (
            "invalid-merge-in-progress-commit.json",
            "invalid-rebase-in-progress-commit.json",
            "invalid-cherry-pick-in-progress-commit.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_advisory_and_audit_records_do_not_authorize(self) -> None:
        self.assertEqual(
            self.load("invalid-advisory-as-authorization.json").result, gate.DENY
        )
        self.assertEqual(
            self.load("invalid-audit-record-as-authorization.json").result,
            gate.DENY,
        )

    def test_external_and_automation_mutations_are_denied(self) -> None:
        names = (
            "invalid-external-stage.json",
            "invalid-external-commit.json",
            "invalid-external-push.json",
            "invalid-external-release.json",
            "invalid-automation-commit.json",
            "invalid-automation-push.json",
            "invalid-automation-release.json",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_unsafe_and_unparseable_commands_are_blocked(self) -> None:
        self.assertEqual(
            self.load("blocked-compound-shell-command.json").result, gate.BLOCKED
        )
        self.assertEqual(
            self.load("blocked-unparseable-command.json").result, gate.BLOCKED
        )

    def test_wrong_field_types_are_blocked(self) -> None:
        names = (
            "blocked-staged-paths-not-array.json",
            "blocked-changed-paths-not-array.json",
            "blocked-pathspecs-not-array.json",
            "blocked-local-ahead-type.json",
            "blocked-local-behind-type.json",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.BLOCKED)

    def test_malformed_and_non_object_fixtures_are_blocked(self) -> None:
        self.assertEqual(self.load("blocked-malformed-json.json").result, gate.BLOCKED)
        self.assertEqual(self.load("blocked-non-object-root.json").result, gate.BLOCKED)

    def test_text_output_contains_required_fields(self) -> None:
        output = gate.render_text([self.load("valid-codex-push-authorized.json")])
        for field in (
            "runtime_identity:",
            "producer:",
            "requested_operation:",
            "authorized_operation:",
            "repository_scope:",
            "branch:",
            "head:",
            "worktree_state:",
            "staged_paths:",
            "changed_paths:",
            "authorization_id:",
            "remote:",
            "upstream_branch:",
            "local_ahead:",
            "local_behind:",
            "diverged:",
            "command:",
            "parsed_command:",
            "command_risk:",
            "result:",
            "reason:",
            "expectation_met:",
        ):
            self.assertIn(field, output)

    def test_json_output_contains_required_fields(self) -> None:
        item = json.loads(
            gate.render_json([self.load("valid-codex-push-authorized.json")])
        )[0]
        required = {
            "case_id",
            "runtime_identity",
            "producer",
            "requested_operation",
            "authorized_operation",
            "repository_scope",
            "branch",
            "head",
            "worktree_state",
            "staged_paths",
            "changed_paths",
            "authorization_id",
            "allowed",
            "result",
            "reason",
            "source",
            "expected_result",
            "expectation_met",
            "remote",
            "upstream_branch",
            "local_ahead",
            "local_behind",
            "diverged",
            "force",
            "force_with_lease",
            "command",
            "parsed_command",
            "command_risk",
        }
        self.assertTrue(required.issubset(item))

    def test_single_file_cli_text_and_json(self) -> None:
        fixture = FIXTURE_ROOT / "valid-codex-push-authorized.json"
        for output_format in ("text", "json"):
            with self.subTest(output_format=output_format), contextlib.redirect_stdout(
                io.StringIO()
            ) as captured:
                self.assertEqual(
                    gate.main(["--format", output_format, str(fixture)]), 0
                )
                self.assertTrue(captured.getvalue().strip())

    def test_directory_cli_exit_code_and_summary(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(gate.main([str(FIXTURE_ROOT)]), 0)
        self.assertIn("expectation_mismatches=0", captured.getvalue())

    def test_expectation_mismatch_returns_one(self) -> None:
        fixture_path = FIXTURE_ROOT / "invalid-git-add-dot.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        fixture["expected_result"] = "PASS"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mismatch.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main([str(path)]), 1)

    def test_all_repository_fixtures_match_expectations(self) -> None:
        fixture_paths = sorted(FIXTURE_ROOT.glob("*.json"))
        self.assertGreater(len(fixture_paths), 0)
        results = [gate.load_fixture(path) for path in fixture_paths]
        mismatches = [item.case_id for item in results if not item.expectation_met]
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()

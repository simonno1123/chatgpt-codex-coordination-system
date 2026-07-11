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


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acos-advisory-gate-checker.py"
FIXTURES = ROOT / "fixtures" / "advisory-gate"
SPEC = importlib.util.spec_from_file_location("acos_advisory_gate_checker", SCRIPT)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)


def case(template: str, **overrides):
    data = copy.deepcopy(gate.FIXTURE_TEMPLATES[template])
    data.update({"case_id": "memory-case", "expected_result": "PASS"})
    data.update(overrides)
    return data


class AdvisoryGateCheckerTests(unittest.TestCase):
    def load(self, name: str):
        return gate.load_fixture(FIXTURES / name)

    def test_five_modes_have_passing_fixtures(self) -> None:
        fixtures = {
            "classify_trigger": "valid-mandatory-governance-classification.json",
            "validate_request": "valid-advisory-request.json",
            "validate_review": "valid-accepted-review.json",
            "consume_review": "valid-accepted-review-consumption.json",
            "verify_lifecycle": "valid-complete-lifecycle.json",
        }
        self.assertEqual(set(fixtures), gate.MODES)
        for mode, filename in fixtures.items():
            with self.subTest(mode=mode):
                result = self.load(filename)
                self.assertEqual(result.result, gate.PASS, result.reason)
                self.assertEqual(result.mode, mode)

    def test_three_trigger_levels(self) -> None:
        fixtures = {
            gate.NOT_REQUIRED: "valid-not-required-classification.json",
            gate.OPTIONAL: "valid-optional-classification.json",
            gate.MANDATORY: "valid-mandatory-governance-classification.json",
        }
        for level, filename in fixtures.items():
            with self.subTest(level=level):
                self.assertEqual(self.load(filename).calculated_trigger_level, level)

    def test_every_mandatory_category_maps_to_level_two(self) -> None:
        mandatory = {
            category for category, level in gate.TRIGGER_CATEGORIES.items() if level == gate.MANDATORY
        }
        self.assertGreaterEqual(len(mandatory), 16)
        for category in mandatory:
            with self.subTest(category=category):
                result = gate.evaluate_fixture(
                    case("classify_mandatory", change_category=category)
                )
                self.assertEqual(result.result, gate.PASS, result.reason)
                self.assertTrue(result.advisory_required)

    def test_unknown_or_contradictory_trigger_is_blocked(self) -> None:
        self.assertEqual(self.load("blocked-unknown-change-category.json").result, gate.BLOCKED)
        self.assertEqual(self.load("blocked-trigger-category-contradiction.json").result, gate.BLOCKED)

    def test_mandatory_skip_is_denied(self) -> None:
        result = self.load("invalid-mandatory-change-skips-advisory.json")
        self.assertEqual(result.result, gate.DENY)
        self.assertIn("skip", result.reason)

    def test_valid_request_metadata_and_route(self) -> None:
        result = self.load("valid-advisory-request.json")
        self.assertEqual(result.result, gate.PASS)
        self.assertTrue(result.request_valid)
        self.assertEqual(result.to, "External Advisory Reviewer")

    def test_invalid_request_producer_and_execution_scope(self) -> None:
        for name in (
            "invalid-codex-advisory-request.json",
            "invalid-request-executing-modification.json",
            "invalid-request-asks-git-write.json",
            "invalid-request-asks-user-decision.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_accepted_rework_and_blocked_reviews_are_valid_advice(self) -> None:
        for conclusion, name in (
            ("ACCEPTED", "valid-accepted-review.json"),
            ("REWORK", "valid-rework-review.json"),
            ("BLOCKED", "valid-blocked-review.json"),
        ):
            with self.subTest(conclusion=conclusion):
                result = self.load(name)
                self.assertEqual(result.result, gate.PASS, result.reason)
                self.assertEqual(result.conclusion, conclusion)

    def test_all_four_runtime_identities_are_fail_closed(self) -> None:
        self.assertEqual(self.load("valid-advisory-request.json").runtime_identity, "ChatGPT Review Runtime")
        self.assertEqual(self.load("valid-accepted-review.json").runtime_identity, "External Advisory Runtime")
        self.assertEqual(self.load("invalid-codex-advisory-review.json").result, gate.DENY)
        automation = case(
            "valid_review",
            producer="Automation",
            runtime_identity="Automation Runtime",
            expected_result="DENY",
        )
        self.assertEqual(gate.evaluate_fixture(automation).result, gate.DENY)

    def test_wrong_role_artifact_and_user_impersonation_are_denied(self) -> None:
        for name in (
            "invalid-chatgpt-forges-advisory-review.json",
            "invalid-advisory-produces-task.json",
            "invalid-advisory-produces-decision.json",
            "invalid-advisory-forges-user-decision.json",
            "invalid-audit-record-as-advisory-review.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_target_reference_binding_and_metadata_warning(self) -> None:
        self.assertEqual(self.load("valid-target-reference-binding.json").result, gate.PASS)
        warning = self.load("valid-minor-path-metadata-warning.json")
        self.assertEqual(warning.result, gate.PASS)
        self.assertTrue(warning.warnings)
        self.assertEqual(self.load("invalid-review-missing-target.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-review-missing-reference.json").result, gate.DENY)

    def test_wrong_repository_task_and_request_binding_are_denied(self) -> None:
        for name in (
            "invalid-review-wrong-task.json",
            "invalid-review-wrong-repository.json",
            "invalid-review-old-request-id.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_readonly_validation_commands_are_allowed_when_declared(self) -> None:
        result = self.load("valid-readonly-tests-declared.json")
        self.assertEqual(result.result, gate.PASS, result.reason)
        self.assertIn("unit_test", result.claimed_commands)

    def test_write_and_command_contradictions_are_denied(self) -> None:
        for name in (
            "invalid-advisory-modifies-file.json",
            "invalid-advisory-uses-apply-patch.json",
            "invalid-advisory-git-add.json",
            "invalid-advisory-git-commit.json",
            "invalid-advisory-git-push.json",
            "invalid-tests-claimed-zero-commands.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.DENY)

    def test_stale_superseded_and_duplicate_consumption(self) -> None:
        self.assertEqual(self.load("invalid-stale-review-consumed.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-superseded-review-consumed.json").result, gate.DENY)
        duplicate = self.load("valid-duplicate-review-not-reconsumed.json")
        self.assertEqual(duplicate.result, gate.PASS)
        self.assertEqual(duplicate.lifecycle_state, "DUPLICATE_CONSUMPTION_DENIED")
        self.assertEqual(self.load("invalid-duplicate-review-reauthorizes.json").result, gate.DENY)

    def test_accepted_review_still_requires_chatgpt_decision(self) -> None:
        result = self.load("valid-accepted-pending-chatgpt-decision.json")
        self.assertEqual(result.result, gate.PASS)
        self.assertEqual(result.lifecycle_state, "FINAL_DECISION_REQUIRED")

    def test_rework_and_blocked_consumption_states(self) -> None:
        rework = self.load("valid-rework-consumption.json")
        blocked = self.load("valid-blocked-consumption.json")
        self.assertEqual(rework.lifecycle_state, "REWORK_REQUIRED")
        self.assertEqual(blocked.lifecycle_state, "ADVISORY_BLOCKED")
        self.assertEqual(self.load("invalid-rework-forced-accepted.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-blocked-forced-accepted.json").result, gate.DENY)

    def test_commit_push_release_authorization_remain_separate(self) -> None:
        self.assertEqual(self.load("valid-commit-push-separation.json").result, gate.PASS)
        self.assertEqual(self.load("invalid-recommendation-as-commit-authorization.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-accepted-review-auto-push.json").result, gate.DENY)
        release = gate.evaluate_fixture(
            case(
                "valid_consumption",
                push_authorization_present=False,
                release_authorization_present=True,
                expected_result="DENY",
            )
        )
        self.assertEqual(release.result, gate.DENY)

    def test_next_task_requires_user_decision(self) -> None:
        self.assertEqual(self.load("invalid-next-task-without-user-decision.json").result, gate.DENY)
        self.assertEqual(self.load("invalid-gate-auto-starts-task-056.json").result, gate.DENY)

    def test_lifecycle_order_and_mandatory_advisory(self) -> None:
        self.assertEqual(self.load("valid-complete-lifecycle.json").result, gate.PASS)
        self.assertEqual(self.load("invalid-mandatory-lifecycle-skips-advisory.json").result, gate.DENY)
        self.assertEqual(self.load("blocked-lifecycle-contradictory.json").result, gate.BLOCKED)

    def test_malformed_missing_wrong_types_and_unknowns_are_blocked(self) -> None:
        names = (
            "blocked-malformed-json.json",
            "blocked-root-array.json",
            "blocked-missing-mode.json",
            "blocked-unknown-mode.json",
            "blocked-missing-task-id.json",
            "blocked-missing-change-category.json",
            "blocked-unknown-change-category.json",
            "blocked-missing-trigger-level.json",
            "blocked-unknown-trigger-level.json",
            "blocked-target-files-not-array.json",
            "blocked-findings-not-array.json",
            "blocked-claimed-commands-wrong-type.json",
            "blocked-unknown-conclusion.json",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(self.load(name).result, gate.BLOCKED)

    def test_text_and_json_output_include_required_fields(self) -> None:
        result = self.load("valid-accepted-review-consumption.json")
        text = gate.render_text([result])
        encoded = gate.render_json([result])
        self.assertIn("calculated_trigger_level", text)
        self.assertIn("lifecycle_state", text)
        payload = json.loads(encoded)[0]
        for field in ("case_id", "request_id", "review_id", "allowed", "expectation_met"):
            self.assertIn(field, payload)

    def test_single_file_and_directory_cli_exit_zero(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main([str(FIXTURES / "valid-advisory-request.json")]), 0)
            self.assertEqual(gate.main([str(FIXTURES)]), 0)

    def test_expectation_mismatch_and_missing_path_exit_nonzero(self) -> None:
        data = {"template": "classify_mandatory", "expected_result": "DENY"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mismatch.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main([str(path)]), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main(["/private/tmp/no-advisory-fixture.json"]), 1)

    def test_every_repository_fixture_matches_expected_result(self) -> None:
        paths, errors = gate.discover_paths([str(FIXTURES)])
        self.assertFalse(errors)
        results = [gate.load_fixture(path) for path in paths]
        self.assertEqual([item.case_id for item in results if not item.expectation_met], [])
        self.assertGreaterEqual(sum(item.result == gate.PASS for item in results), 15)
        self.assertGreaterEqual(sum(item.result == gate.DENY for item in results), 30)
        self.assertGreaterEqual(sum(item.result == gate.BLOCKED for item in results), 32)


if __name__ == "__main__":
    unittest.main()

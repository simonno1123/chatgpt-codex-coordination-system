"""Tests for the fixture-only ACOS validation scenario runner."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/acos-validation-scenario-runner.py"
FIXTURES = ROOT / "fixtures/validation-scenarios"
SPEC = importlib.util.spec_from_file_location("acos_validation_runner", SCRIPT)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


class ScenarioRunnerTests(unittest.TestCase):
    def fixture(self, name: str):
        return RUNNER.load_fixture(FIXTURES / name)

    def data(self, **updates):
        data = copy.deepcopy(RUNNER.BASE)
        data.update(updates)
        return data

    def test_all_five_modes(self):
        for mode in sorted(RUNNER.MODES):
            with self.subTest(mode=mode):
                data = copy.deepcopy(
                    RUNNER.TEMPLATES["drift"]
                    if mode == "detect_policy_drift"
                    else RUNNER.BASE
                )
                data["mode"] = mode
                self.assertEqual(RUNNER.evaluate(data).overall_result, RUNNER.PASS)

    def test_all_six_component_identifiers(self):
        result = self.fixture("valid-end-to-end-shadow-flow.json")
        self.assertEqual(set(result.executed_components), set(RUNNER.COMPONENTS))

    def test_pass_result(self):
        self.assertEqual(
            self.fixture("valid-end-to-end-shadow-flow.json").overall_result,
            RUNNER.PASS,
        )

    def test_deny_result(self):
        self.assertEqual(
            self.fixture("invalid-runtime-spoofing.json").overall_result,
            RUNNER.DENY,
        )

    def test_blocked_result(self):
        self.assertEqual(
            self.fixture("blocked-malformed.json").overall_result, RUNNER.BLOCKED
        )

    def test_schema_missing_fields_fail_closed(self):
        for name in (
            "blocked-missing-id.json",
            "blocked-missing-mode.json",
            "blocked-missing-type.json",
            "blocked-missing-project.json",
            "blocked-missing-task.json",
            "blocked-missing-expected-overall.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.fixture(name).overall_result, RUNNER.BLOCKED)

    def test_schema_wrong_types_fail_closed(self):
        for name in (
            "blocked-required-type.json",
            "blocked-order-type.json",
            "blocked-input-type.json",
            "blocked-expected-type.json",
            "blocked-policy-digest-type.json",
            "blocked-expectation-structure.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.fixture(name).overall_result, RUNNER.BLOCKED)

    def test_unknown_values_fail_closed(self):
        for name in (
            "blocked-unknown-mode.json",
            "blocked-unknown-type.json",
            "blocked-unknown-component.json",
            "blocked-unknown-expected-overall.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.fixture(name).overall_result, RUNNER.BLOCKED)

    def test_component_contract_normalization(self):
        result = self.fixture("valid-contract-six.json")
        self.assertTrue(result.component_contracts_valid)
        for component in result.component_results:
            self.assertEqual(component["contract_version"], "1.0")
            self.assertEqual(component["allowed"], component["result"] == RUNNER.PASS)

    def test_component_import_failure_blocks(self):
        self.assertEqual(
            self.fixture("blocked-component-import.json").overall_result,
            RUNNER.BLOCKED,
        )

    def test_component_adapter_failure_blocks(self):
        self.assertEqual(
            self.fixture("blocked-component-adapter.json").overall_result,
            RUNNER.BLOCKED,
        )

    def test_component_fixture_path_escape_blocks(self):
        data = self.data(
            scenario_id="component-fixture-path-escape",
            required_components=["runtime_identity"],
            optional_components=[],
            component_order=["runtime_identity"],
            component_inputs={
                "runtime_identity": {"fixture_path": "fixtures/../CODEX_WORKFLOW.md"}
            },
            expected_component_results={"runtime_identity": RUNNER.BLOCKED},
            expected_overall_result=RUNNER.BLOCKED,
            expected_result=RUNNER.BLOCKED,
        )
        result = RUNNER.evaluate(data)
        self.assertEqual(result.overall_result, RUNNER.BLOCKED)
        self.assertIn("escapes", result.reason)

    def test_component_contract_failures_block(self):
        for name in (
            "blocked-component-output-missing-result.json",
            "blocked-component-output-unknown-result.json",
            "blocked-component-result-allowed.json",
            "blocked-contract-version-missing.json",
            "blocked-contract-version-unsupported.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.fixture(name).overall_result, RUNNER.BLOCKED)

    def test_runtime_identity_flow(self):
        self.assertTrue(self.fixture("valid-identity-flow.json").identity_valid)
        self.assertFalse(self.fixture("invalid-runtime-spoofing.json").identity_valid)

    def test_filesystem_scope_flow(self):
        self.assertTrue(self.fixture("valid-filesystem-flow.json").scope_valid)
        self.assertFalse(self.fixture("invalid-filesystem-escape.json").scope_valid)

    def test_git_stage_commit_push_separation(self):
        self.assertEqual(
            self.fixture("valid-path-limited-stage.json").overall_result, RUNNER.PASS
        )
        self.assertEqual(
            self.fixture("valid-commit-authorization.json").overall_result, RUNNER.PASS
        )
        self.assertEqual(
            self.fixture("valid-push-authorization.json").overall_result, RUNNER.PASS
        )

    def test_commit_authorization_does_not_authorize_push(self):
        self.assertEqual(
            self.fixture("invalid-commit-auth-reused-push.json").overall_result,
            RUNNER.DENY,
        )

    def test_push_authorization_does_not_authorize_release(self):
        self.assertEqual(
            self.fixture("invalid-push-auth-reused-release.json").overall_result,
            RUNNER.DENY,
        )

    def test_blanket_and_hidden_staging_denied(self):
        for name in ("invalid-blanket-staging.json", "invalid-hidden-staged-file.json"):
            with self.subTest(name=name):
                self.assertEqual(self.fixture(name).overall_result, RUNNER.DENY)

    def test_audit_chain_validation(self):
        self.assertTrue(self.fixture("valid-audit-chain.json").audit_chain_valid)
        self.assertFalse(self.fixture("invalid-audit-tamper.json").audit_chain_valid)

    def test_audit_record_is_not_authorization(self):
        self.assertEqual(
            self.fixture("invalid-audit-authorization.json").overall_result,
            RUNNER.DENY,
        )

    def test_advisory_lifecycle(self):
        self.assertTrue(
            self.fixture("valid-advisory-pending-decision.json").advisory_valid
        )
        self.assertEqual(
            self.fixture("invalid-advisory-skipped.json").overall_result, RUNNER.DENY
        )

    def test_advisory_is_not_user_decision(self):
        self.assertEqual(
            self.fixture("invalid-advisory-as-user-decision.json").overall_result,
            RUNNER.DENY,
        )

    def test_user_decision_lifecycle(self):
        self.assertTrue(self.fixture("valid-user-decision-flow.json").user_decision_valid)
        for name in (
            "invalid-expired-decision.json",
            "invalid-revoked-decision.json",
            "invalid-duplicate-decision-consumption.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.fixture(name).overall_result, RUNNER.DENY)

    def test_missing_user_decision_denied(self):
        self.assertEqual(
            self.fixture("invalid-missing-user-decision.json").overall_result,
            RUNNER.DENY,
        )

    def test_task_058_requires_new_user_decision(self):
        for name in (
            "invalid-automation-task058.json",
            "invalid-task057-decision-reused-task058.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(self.fixture(name).overall_result, RUNNER.DENY)

    def test_fail_closed_blocked_precedes_deny(self):
        data = self.data(
            scenario_id="blocked-precedes-deny",
            component_order=["runtime_identity", "user_decision_gate"],
            required_components=["runtime_identity", "user_decision_gate"],
            component_inputs={
                "runtime_identity": {
                    "fixture_path": "fixtures/runtime-identity/invalid-codex-decision.json"
                },
                "user_decision_gate": {
                    "fixture_path": "fixtures/user-decision-gate/blocked-consumption-undetermined.json"
                },
            },
            expected_component_results={
                "runtime_identity": RUNNER.DENY,
                "user_decision_gate": RUNNER.BLOCKED,
            },
            expected_overall_result=RUNNER.BLOCKED,
            expected_result=RUNNER.BLOCKED,
        )
        result = RUNNER.evaluate(data)
        self.assertEqual(result.overall_result, RUNNER.BLOCKED)
        self.assertEqual(result.denied_components, ["runtime_identity"])
        self.assertEqual(result.blocked_components, ["user_decision_gate"])

    def test_stop_on_deny(self):
        data = self.data(
            scenario_id="stop-on-deny",
            component_order=["runtime_identity", "audit_jsonl"],
            required_components=["runtime_identity", "audit_jsonl"],
            component_inputs={
                "runtime_identity": {
                    "fixture_path": "fixtures/runtime-identity/invalid-codex-decision.json"
                },
                "audit_jsonl": {
                    "fixture_path": "fixtures/audit-jsonl/valid-lifecycle-chain.json"
                },
            },
            expected_component_results={
                "runtime_identity": RUNNER.DENY,
                "audit_jsonl": RUNNER.PASS,
            },
            expected_overall_result=RUNNER.DENY,
            expected_result=RUNNER.DENY,
            stop_on_deny=True,
        )
        result = RUNNER.evaluate(data)
        self.assertEqual(result.executed_components, ["runtime_identity"])
        self.assertEqual(result.skipped_components, ["audit_jsonl"])

    def test_stop_on_blocked(self):
        data = self.data(
            scenario_id="stop-on-blocked",
            component_order=["runtime_identity", "audit_jsonl"],
            required_components=["runtime_identity", "audit_jsonl"],
            component_inputs={
                "runtime_identity": {"simulate_adapter_failure": True},
                "audit_jsonl": {
                    "fixture_path": "fixtures/audit-jsonl/valid-lifecycle-chain.json"
                },
            },
            expected_component_results={
                "runtime_identity": RUNNER.BLOCKED,
                "audit_jsonl": RUNNER.PASS,
            },
            expected_overall_result=RUNNER.BLOCKED,
            expected_result=RUNNER.BLOCKED,
            stop_on_blocked=True,
        )
        result = RUNNER.evaluate(data)
        self.assertEqual(result.overall_result, RUNNER.BLOCKED)
        self.assertEqual(result.executed_components, [])

    def test_optional_component_warning(self):
        result = self.fixture("valid-optional-warning.json")
        self.assertEqual(result.overall_result, RUNNER.PASS)
        self.assertIn("audit_jsonl", result.skipped_components)
        self.assertTrue(result.warnings)

    def test_deterministic_component_order(self):
        result = self.fixture("valid-end-to-end-shadow-flow.json")
        self.assertEqual(result.executed_components, RUNNER.DEFAULT_ORDER)

    def test_dependency_cycle_blocks(self):
        self.assertEqual(
            self.fixture("blocked-dependency-cycle.json").overall_result,
            RUNNER.BLOCKED,
        )

    def test_critical_component_order_reversal_denied(self):
        data = self.data(
            scenario_id="reversed-git-gates",
            component_order=["git_operation", "user_decision_gate"],
            required_components=["git_operation", "user_decision_gate"],
            expected_overall_result=RUNNER.DENY,
            expected_result=RUNNER.DENY,
        )
        result = RUNNER.evaluate(data)
        self.assertEqual(result.overall_result, RUNNER.DENY)
        self.assertIn("user_decision_gate->git_operation", result.invalid_order_steps)

    def test_illegal_lifecycle_order_denied(self):
        result = self.fixture("invalid-illegal-lifecycle-order.json")
        self.assertEqual(result.overall_result, RUNNER.DENY)
        self.assertTrue(result.invalid_order_steps)

    def test_policy_version_mismatch(self):
        result = self.fixture("invalid-policy-version.json")
        self.assertEqual(result.overall_result, RUNNER.DENY)
        self.assertTrue(result.version_mismatches)

    def test_mapping_digest_mismatch(self):
        result = self.fixture("invalid-policy-digest.json")
        self.assertEqual(result.overall_result, RUNNER.DENY)
        self.assertTrue(result.digest_mismatches)

    def test_policy_metadata_missing_blocks(self):
        self.assertEqual(
            self.fixture("blocked-unable-governing-policy.json").overall_result,
            RUNNER.BLOCKED,
        )

    def test_component_result_conflict_blocks(self):
        result = self.fixture("blocked-result-conflict.json")
        self.assertEqual(result.overall_result, RUNNER.BLOCKED)
        self.assertTrue(result.result_conflicts)

    def test_malformed_and_non_object_json_block(self):
        for name in ("blocked-malformed.json", "blocked-root-array.json"):
            with self.subTest(name=name):
                self.assertEqual(self.fixture(name).overall_result, RUNNER.BLOCKED)

    def test_output_contract_contains_required_fields(self):
        fields = set(asdict(self.fixture("valid-end-to-end-shadow-flow.json")))
        required = {
            "scenario_id",
            "mode",
            "scenario_type",
            "project",
            "task_id",
            "required_components",
            "executed_components",
            "skipped_components",
            "component_order",
            "component_results",
            "component_contracts_valid",
            "identity_valid",
            "scope_valid",
            "user_decision_valid",
            "advisory_valid",
            "git_authorization_valid",
            "audit_chain_valid",
            "policy_drift_detected",
            "lifecycle_state",
            "allowed",
            "overall_result",
            "reason",
            "warnings",
            "failed_components",
            "denied_components",
            "blocked_components",
            "source",
            "expected_result",
            "expectation_met",
        }
        self.assertTrue(required.issubset(fields))

    def test_repeated_output_is_deterministic(self):
        first = asdict(self.fixture("valid-deterministic-repeat.json"))
        second = asdict(self.fixture("valid-deterministic-repeat.json"))
        self.assertEqual(first, second)

    def test_fixture_counts(self):
        results = [RUNNER.load_fixture(path) for path in FIXTURES.glob("*.json")]
        counts = {
            state: sum(result.overall_result == state for result in results)
            for state in RUNNER.RESULTS
        }
        self.assertEqual(counts, {RUNNER.PASS: 21, RUNNER.DENY: 41, RUNNER.BLOCKED: 41})

    def test_all_fixtures_match_expected_result(self):
        results = [RUNNER.load_fixture(path) for path in FIXTURES.glob("*.json")]
        self.assertEqual(
            [result.scenario_id for result in results if not result.expectation_met], []
        )

    def test_text_cli_single_file(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = RUNNER.main([str(FIXTURES / "valid-end-to-end-shadow-flow.json")])
        self.assertEqual(code, 0)
        self.assertIn("SUMMARY:", output.getvalue())

    def test_json_cli_single_file(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = RUNNER.main(
                [
                    "--format",
                    "json",
                    str(FIXTURES / "valid-end-to-end-shadow-flow.json"),
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())[0]["overall_result"], RUNNER.PASS)

    def test_directory_cli(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = RUNNER.main([str(FIXTURES)])
        self.assertEqual(code, 0)
        self.assertIn("total=103", output.getvalue())

    def test_cli_missing_path_returns_nonzero(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = RUNNER.main([str(FIXTURES / "does-not-exist.json")])
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED", error.getvalue())


if __name__ == "__main__":
    unittest.main()

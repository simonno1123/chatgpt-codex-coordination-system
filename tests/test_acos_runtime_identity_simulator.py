from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "acos-runtime-identity-simulator.py"
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "runtime-identity"

SPEC = importlib.util.spec_from_file_location("acos_runtime_identity_simulator", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load simulator: {SCRIPT_PATH}")

simulator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = simulator
SPEC.loader.exec_module(simulator)


class RuntimeIdentitySimulatorTests(unittest.TestCase):
    def fixture(
        self,
        runtime_identity: str,
        producer: str,
        artifact_type: str,
    ) -> dict[str, str]:
        return {
            "case_id": "unit-test",
            "runtime_identity": runtime_identity,
            "producer": producer,
            "artifact_type": artifact_type,
        }

    def test_known_artifact_catalog_is_complete(self) -> None:
        self.assertEqual(
            simulator.KNOWN_ARTIFACT_TYPES,
            {
                "TASK",
                "RESULT",
                "BLOCKED RESULT",
                "ADVISORY REVIEW",
                "REVIEW",
                "DECISION",
                "RECORD",
                "GOVERNANCE PROPOSAL",
                "CONTEXT PACK",
            },
        )

    def test_all_runtime_artifact_combinations(self) -> None:
        producer_by_runtime = {
            "ChatGPT Review Runtime": "ChatGPT Review",
            "Codex Executor Runtime": "Codex Executor",
            "External Advisory Runtime": "External Advisory Reviewer",
            "Automation Runtime": "Automation",
        }

        for runtime_identity, policy in simulator.RUNTIME_POLICIES.items():
            for artifact_type in simulator.KNOWN_ARTIFACT_TYPES:
                with self.subTest(runtime_identity=runtime_identity, artifact_type=artifact_type):
                    result = simulator.evaluate_fixture(
                        self.fixture(
                            runtime_identity,
                            producer_by_runtime[runtime_identity],
                            artifact_type,
                        )
                    )
                    expected = (
                        simulator.PASS
                        if artifact_type in policy.allowed_artifact_types
                        else simulator.DENY
                    )
                    self.assertEqual(result.result, expected)
                    self.assertEqual(result.allowed, expected == simulator.PASS)

    def test_chatgpt_producer_alias_is_valid(self) -> None:
        result = simulator.evaluate_fixture(
            self.fixture("ChatGPT Review Runtime", "ChatGPT", "TASK")
        )
        self.assertEqual(result.result, simulator.PASS)

    def test_producer_binding_mismatch_is_denied(self) -> None:
        result = simulator.evaluate_fixture(
            self.fixture("Codex Executor Runtime", "ChatGPT", "RESULT")
        )
        self.assertEqual(result.result, simulator.DENY)
        self.assertFalse(result.allowed)

    def test_unknown_runtime_is_blocked(self) -> None:
        result = simulator.evaluate_fixture(
            self.fixture("Unknown Runtime", "Unknown", "RESULT")
        )
        self.assertEqual(result.result, simulator.BLOCKED)

    def test_unknown_artifact_is_blocked(self) -> None:
        result = simulator.evaluate_fixture(
            self.fixture("Codex Executor Runtime", "Codex Executor", "UNKNOWN")
        )
        self.assertEqual(result.result, simulator.BLOCKED)

    def test_missing_field_is_blocked(self) -> None:
        result = simulator.evaluate_fixture(
            {
                "case_id": "missing-producer",
                "runtime_identity": "Codex Executor Runtime",
                "artifact_type": "RESULT",
            }
        )
        self.assertEqual(result.result, simulator.BLOCKED)

    def test_all_repository_fixtures_match_expectations(self) -> None:
        fixture_paths = sorted(FIXTURE_ROOT.glob("*.json"))
        self.assertGreater(len(fixture_paths), 0)
        results = [simulator.load_fixture(path) for path in fixture_paths]
        mismatches = [item.case_id for item in results if not item.expectation_met]
        self.assertEqual(mismatches, [])


if __name__ == "__main__":
    unittest.main()

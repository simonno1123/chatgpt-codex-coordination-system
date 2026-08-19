import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "schema-validation-2.0"
CONTRACT = ROOT / "docs" / "acos-w1-versioned-contract.md"
VALIDATOR_PATH = ROOT / "scripts" / "acos-schema-shadow-validator.py"

SPEC = importlib.util.spec_from_file_location("acos_schema_shadow_validator", VALIDATOR_PATH)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)

ARTIFACT_TYPES = [
    "USER DECISION",
    "GOVERNANCE PROPOSAL",
    "TASK",
    "RESULT",
    "BLOCKED RESULT",
    "ADVISORY REQUEST",
    "ADVISORY REVIEW",
    "REVIEW",
    "DECISION",
    "AUTHORIZATION",
    "RECORD",
    "AUDIT EVENT",
    "EXECUTION RECEIPT",
    "ERROR/BLOCKER RECORD",
    "CONTEXT PACK",
]

IMPORT_CLASSES = [
    "VALID_NATIVE",
    "VALID_LEGACY",
    "REPRODUCED_EVIDENCE",
    "NON_CONSUMABLE",
    "UNTRUSTED_IMPORT",
    "SUPERSEDED",
    "REVOKED",
    "EXPIRED",
    "PROVENANCE_EXCEPTION",
]

LEGACY_HASHES = {
    "fixtures/schemas/envelope.schema.json": "ea0843f1e14754d75aa83bd9a7888d42c2cb073da54ac4ab254157a5148dbbc6",
    "fixtures/schemas/policy.schema.json": "0df66330b0e1e0bf6f1ab8c9b0330c8bbb65c3428dbc8df385273676ec3e26bb",
    "scripts/acos-schema-validator.py": "e8b720b6870433838573394e6ecbb0ae90200e613461b6658cab746b47626664",
}


def load_json(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def evaluate(data):
    candidate = copy.deepcopy(data)
    candidate.pop("expected_result", None)
    return gate.evaluate_fixture(candidate)


class ShadowValidatorTests(unittest.TestCase):
    def setUp(self):
        self.envelope = load_json("valid-envelope.json")
        self.policy = load_json("valid-policy.json")

    def assert_result(self, data, expected):
        result = evaluate(data)
        self.assertEqual(result.result, expected, result.reason)
        self.assertEqual(result.authority_effect, "NONE")
        self.assertIn("schema validity does not authenticate", result.notice)
        return result

    def test_valid_envelope_and_policy_pass(self):
        self.assert_result(self.envelope, gate.PASS)
        self.assert_result(self.policy, gate.PASS)

    def test_repeated_evaluation_is_deterministic(self):
        first = gate.asdict(evaluate(self.envelope))
        second = gate.asdict(evaluate(self.envelope))
        self.assertEqual(first, second)

    def test_version_selectors_fail_closed(self):
        for key in ("contract_version", "schema_version"):
            missing = copy.deepcopy(self.envelope)
            missing.pop(key)
            self.assert_result(missing, gate.BLOCKED)

            malformed = copy.deepcopy(self.envelope)
            malformed[key] = "2.x"
            self.assert_result(malformed, gate.BLOCKED)

        unsupported = copy.deepcopy(self.envelope)
        unsupported["contract_version"] = "3.0"
        unsupported["schema_version"] = "3.0"
        self.assert_result(unsupported, gate.DENY)

        mixed = copy.deepcopy(self.envelope)
        mixed["schema_version"] = "2.1"
        self.assert_result(mixed, gate.DENY)

        legacy = copy.deepcopy(self.envelope)
        legacy["contract_version"] = "1.0"
        legacy["schema_version"] = "1.0"
        result = self.assert_result(legacy, gate.DENY)
        self.assertIn("no fallback or downgrade", result.reason)

    def test_policy_version_selectors_are_explicit(self):
        missing = copy.deepcopy(self.policy)
        missing["policy_metadata"].pop("contract_version")
        self.assert_result(missing, gate.BLOCKED)

        unsupported = copy.deepcopy(self.policy)
        unsupported["policy_metadata"]["contract_version"] = "3.0"
        unsupported["policy_metadata"]["schema_version"] = "3.0"
        self.assert_result(unsupported, gate.DENY)

    def test_closed_top_level_schemas(self):
        envelope = copy.deepcopy(self.envelope)
        envelope["unknown_property"] = True
        self.assert_result(envelope, gate.DENY)

        policy = copy.deepcopy(self.policy)
        policy["unknown_property"] = True
        self.assert_result(policy, gate.DENY)

    def test_artifact_type_compatibility_union(self):
        for artifact_type in ARTIFACT_TYPES:
            candidate = copy.deepcopy(self.envelope)
            candidate["artifact_type"] = artifact_type
            with self.subTest(artifact_type=artifact_type):
                self.assert_result(candidate, gate.PASS)

        unknown = copy.deepcopy(self.envelope)
        unknown["artifact_type"] = "MAGIC APPROVAL"
        self.assert_result(unknown, gate.DENY)

    def test_import_classification_is_exactly_w0(self):
        for import_class in IMPORT_CLASSES:
            candidate = copy.deepcopy(self.envelope)
            candidate["historical_import_class"] = import_class
            with self.subTest(import_class=import_class):
                result = self.assert_result(candidate, gate.PASS)
                if import_class == "NON_CONSUMABLE":
                    self.assertEqual(result.authority_effect, "NONE")

        invalid = copy.deepcopy(self.envelope)
        invalid["historical_import_class"] = "IMPLICITLY_TRUSTED"
        self.assert_result(invalid, gate.DENY)

    def test_typed_scope_and_path_safety(self):
        self.assert_result(self.envelope, gate.PASS)

        missing_target = copy.deepcopy(self.envelope)
        missing_target["scope"][0].pop("target")
        self.assert_result(missing_target, gate.DENY)

        unknown_type = copy.deepcopy(self.envelope)
        unknown_type["scope"][0]["scope_type"] = "EVERYTHING"
        self.assert_result(unknown_type, gate.DENY)

        traversal = copy.deepcopy(self.envelope)
        traversal["scope"][0]["target"] = "../secret"
        self.assert_result(traversal, gate.DENY)

    def test_multi_parent_lineage_constraints(self):
        self.assertGreaterEqual(len(self.envelope["lineage"]), 2)
        self.assert_result(self.envelope, gate.PASS)

        malformed = copy.deepcopy(self.envelope)
        malformed["lineage"][0]["artifact_id"] = ""
        self.assert_result(malformed, gate.DENY)

        duplicate = copy.deepcopy(self.envelope)
        duplicate["lineage"].append(
            {"artifact_id": duplicate["lineage"][0]["artifact_id"], "relation": "REVIEWS"}
        )
        self.assert_result(duplicate, gate.DENY)

        self_reference = copy.deepcopy(self.envelope)
        self_reference["lineage"][0]["artifact_id"] = self_reference["artifact_id"]
        self.assert_result(self_reference, gate.DENY)

    def test_digest_constraints(self):
        self.assert_result(self.envelope, gate.PASS)
        malformed = copy.deepcopy(self.envelope)
        malformed["content_digest"] = "sha256:not-a-digest"
        self.assert_result(malformed, gate.DENY)

    def test_lifecycle_structure_does_not_enact_transition(self):
        result = self.assert_result(self.envelope, gate.PASS)
        self.assertEqual(result.authority_effect, "NONE")

        unknown_family = copy.deepcopy(self.envelope)
        unknown_family["lifecycle"]["family"] = "DEPLOYMENT"
        self.assert_result(unknown_family, gate.DENY)

        mismatched_state = copy.deepcopy(self.envelope)
        mismatched_state["lifecycle"] = {"family": "ACTIVATION", "state": "COMMITTED"}
        self.assert_result(mismatched_state, gate.DENY)

    def test_authority_fields_do_not_self_confer_authority(self):
        result = self.assert_result(self.envelope, gate.PASS)
        self.assertEqual(result.authority_effect, "NONE")
        contract = CONTRACT.read_text(encoding="utf-8")
        required_rules = [
            "STRUCTURAL REPRESENTATION != AUTHENTICATED AUTHORITY",
            "Schema validity != authenticated authority",
            "Producer attribution != governance authority",
            "Reviewer status != Decision Authority",
            "Runtime Identity reference != authenticated runtime",
            "Signature syntax != verified signature",
            "Grant != Authorization",
            "Grant reference != issued or consumed Grant",
            "Authorization reference != valid Authorization",
            "Receipt reference != proof of operation",
            "Lifecycle structure != enacted transition",
        ]
        for rule in required_rules:
            with self.subTest(rule=rule):
                self.assertIn(rule, contract)
        self.assertEqual(self.envelope["signature_metadata"]["verification_status"], "NOT_VERIFIED_BY_W1")
        self.assertEqual(self.envelope["authorization_claim"]["claimed_state"], "DECLARED")

    def test_payload_content_is_non_governing(self):
        candidate = copy.deepcopy(self.envelope)
        candidate["payload"] = {
            "artifact_type": "AUTHORIZATION",
            "contract_version": "999.0",
            "schema_version": "999.0",
            "lifecycle": {"family": "ACTIVATION", "state": "ACTIVE"},
        }
        result = self.assert_result(candidate, gate.PASS)
        self.assertEqual(result.authority_effect, "NONE")

        contract = " ".join(CONTRACT.read_text(encoding="utf-8").split())
        self.assertIn("`payload` is an extensible data container only.", contract)
        self.assertIn("Payload content is non-governing.", contract)
        self.assertIn("cannot override, redefine, supersede, shadow, or otherwise", contract)

    def test_compatibility_tuple_does_not_enable_unsupported_version(self):
        policy = copy.deepcopy(self.policy)
        policy["supported_contract_schema_tuples"].append(
            {"contract_version": "3.0", "schema_version": "3.0"}
        )
        self.assert_result(policy, gate.PASS)

        unsupported = copy.deepcopy(self.envelope)
        unsupported["contract_version"] = "3.0"
        unsupported["schema_version"] = "3.0"
        result = self.assert_result(unsupported, gate.DENY)
        self.assertIn("no fallback or downgrade", result.reason)

        contract = " ".join(CONTRACT.read_text(encoding="utf-8").split())
        self.assertIn(
            "`supported_contract_schema_tuples` is a compatibility declaration",
            contract,
        )
        self.assertIn("does not become acceptable to the W1 shadow validator", contract)
        self.assertIn("policy metadata alone does not implement or activate them", contract)

    def test_legacy_assets_are_byte_identical(self):
        for relative, expected in LEGACY_HASHES.items():
            digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            with self.subTest(path=relative):
                self.assertEqual(digest, expected)

    def test_legacy_validator_has_no_w1_dispatch(self):
        legacy = (ROOT / "scripts" / "acos-schema-validator.py").read_text(encoding="utf-8")
        self.assertNotIn("schema-validation-2.0", legacy)
        self.assertNotIn('"2.0" / "envelope.schema.json"', legacy)
        shadow = VALIDATOR_PATH.read_text(encoding="utf-8")
        self.assertNotIn("acos-schema-validator.py", shadow)

    def test_parser_and_schema_boundaries_fail_closed(self):
        with self.assertRaises(gate.DuplicateKey):
            gate.reject_duplicate_keys([("duplicate", 1), ("duplicate", 2)])

        nested = value = {}
        for _ in range(gate.MAX_JSON_DEPTH + 1):
            value["nested"] = {}
            value = value["nested"]
        with self.assertRaises(gate.Blocked):
            gate.json_depth(nested)

        with self.assertRaises(gate.Blocked):
            gate.assert_local_references({"$ref": "https://example.invalid/schema.json"})

        outside = ROOT / "fixtures" / "schemas" / "2.0" / "envelope.schema.json"
        with self.assertRaises(gate.Blocked):
            gate.confined_path(outside, require_json=True)

    def test_cli_valid_targets_exit_zero(self):
        targets = [FIXTURES / "valid-envelope.json", FIXTURES / "valid-policy.json"]
        for target in targets:
            with self.subTest(target=target.name), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main([str(target)]), 0)

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main([str(target) for target in targets]), 0)

    def test_cli_valid_plus_missing_target_exits_two(self):
        valid = FIXTURES / "valid-envelope.json"
        missing = FIXTURES / "missing-fixture.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main([str(valid), str(missing)]), 2)

    def test_cli_valid_plus_out_of_root_target_exits_two(self):
        valid = FIXTURES / "valid-envelope.json"
        outside = ROOT / "fixtures" / "schemas" / "2.0" / "envelope.schema.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main([str(valid), str(outside)]), 2)

    def test_cli_expectation_mismatch_exits_one(self):
        mismatch = gate.make_result(
            {"case_id": "mismatch", "expected_result": gate.DENY},
            "<synthetic>",
            gate.PASS,
            "synthetic expectation mismatch",
        )
        synthetic_path = Path("synthetic.json")
        with (
            mock.patch.object(gate, "discover_paths", return_value=([synthetic_path], [])),
            mock.patch.object(gate, "load_fixture", return_value=mismatch),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(gate.main([str(synthetic_path)]), 1)

    def test_cli_operational_blocker_precedes_expectation_mismatch(self):
        mismatch = gate.make_result(
            {"case_id": "mismatch", "expected_result": gate.DENY},
            "<synthetic>",
            gate.PASS,
            "synthetic expectation mismatch",
        )
        blocker = gate.make_result(
            {"case_id": "missing"},
            "<missing>",
            gate.BLOCKED,
            "synthetic operational blocker",
        )
        synthetic_path = Path("synthetic.json")
        with (
            mock.patch.object(gate, "discover_paths", return_value=([synthetic_path], [blocker])),
            mock.patch.object(gate, "load_fixture", return_value=mismatch),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(gate.main([str(synthetic_path)]), 2)


if __name__ == "__main__":
    unittest.main()

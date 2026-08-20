import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "schema-validation-w2" / "1.0"
SCHEMAS = ROOT / "fixtures" / "schemas" / "w2" / "1.0"
PROFILE = ROOT / "docs" / "acos-w2-identity-evidence-persistence-shadow-profile.md"
VERIFIER_PATH = ROOT / "scripts" / "acos-w2-shadow-verifier.py"

RUNTIME_FIXTURE = FIXTURES / "valid-runtime-registry.json"
EVIDENCE_FIXTURE = FIXTURES / "valid-evidence-record.json"
RECEIPT_FIXTURE = FIXTURES / "valid-persistence-receipt.json"

SPEC = importlib.util.spec_from_file_location("acos_w2_shadow_verifier", VERIFIER_PATH)
gate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = gate
SPEC.loader.exec_module(gate)

PROTECTED_HASHES = {
    "docs/acos-w0-baseline-and-canonical-vocabulary.md": "22195f331bcd63cb89655a027067e348608e97f1c7451975d8f7390d391c86b6",
    "docs/acos-w0-lifecycle-storage-authority-semantics.md": "4302e9e852be1e6c91b85cbab6e49369ae686a9f9861f1908aea49cba4addfd3",
    "docs/acos-w0-historical-import-taxonomy.md": "8d4d4ce9e129685482664957d4e5da45fe5fee3097dcc1862e7962922880b1f3",
    "docs/acos-w1-versioned-contract.md": "bb55f5e5d89595788a9740518410ec1a34f6682cc08192b0a97e60c1441deb6a",
    "fixtures/schemas/2.0/envelope.schema.json": "915ca3fabbc76bd56c67a3c6e5c7598dfbe94c3fe15b6cfb209edea384ef3110",
    "fixtures/schemas/2.0/policy.schema.json": "71d0be6b806056202d90f7df3d55b010d49c4920255846648878a1c9238bca47",
    "scripts/acos-schema-shadow-validator.py": "faf6531beb4c884c2e11fed88b9261c13d03f5226e017d04b3414d4db88eba79",
    "tests/test_acos_schema_shadow_validator.py": "40c58de9f88a2d012ee711c3e73c62a524b202848a609a77fb56a005ab497d8d",
    "fixtures/schemas/envelope.schema.json": "ea0843f1e14754d75aa83bd9a7888d42c2cb073da54ac4ab254157a5148dbbc6",
    "fixtures/schemas/policy.schema.json": "0df66330b0e1e0bf6f1ab8c9b0330c8bbb65c3428dbc8df385273676ec3e26bb",
    "scripts/acos-schema-validator.py": "e8b720b6870433838573394e6ecbb0ae90200e613461b6658cab746b47626664",
    "tests/test_acos_schema_validator.py": "2dcf3481213eb949e13e395937952f83ece0ded2fc58c62de97a418163ea046e",
    "scripts/acos-linter.py": "5ec6a34b27d693b69d20769c1608d2ffed516690252e983978380ac9b2104fce",
    "scripts/acos-validation-scenario-runner.py": "3dede33fcc86babe77cda80edbce0c4b34c086391ab65d63e1e703fee3685494",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def strings(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


class W2ShadowVerifierTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_json(RUNTIME_FIXTURE)
        self.evidence = load_json(EVIDENCE_FIXTURE)
        self.receipt = load_json(RECEIPT_FIXTURE)

    def assert_result(self, data, expected, **kwargs):
        result = gate.evaluate_document(copy.deepcopy(data), **kwargs)
        self.assertEqual(result.result, expected, result.reason)
        self.assertEqual(result.governance_status, "UNAUTHENTICATED_SHADOW")
        self.assertEqual(result.authority_effect, "NONE")
        self.assertEqual(result.identity_effect, "NONE")
        self.assertEqual(result.execution_effect, "NONE")
        self.assertEqual(result.activation_effect, "NONE")
        self.assertFalse(result.eligible_for_execution)
        self.assertIn("does not authenticate runtime identity", result.notice)
        self.assertEqual(result.replay_notice, "W2 has no durable replay registry.")
        return result

    def test_three_positive_fixtures_pass(self):
        self.assert_result(self.registry, gate.PASS)
        self.assert_result(self.evidence, gate.PASS)
        self.assert_result(self.receipt, gate.PASS)

    def test_repeated_verification_is_deterministic(self):
        first = gate.asdict(gate.evaluate_document(copy.deepcopy(self.registry)))
        second = gate.asdict(gate.evaluate_document(copy.deepcopy(self.registry)))
        self.assertEqual(first, second)

    def test_profile_and_contract_versions_fail_closed(self):
        wrong_profile = copy.deepcopy(self.registry)
        wrong_profile["profile_version"] = "2.0"
        self.assert_result(wrong_profile, gate.DENY)

        wrong_contract = copy.deepcopy(self.registry)
        wrong_contract["contract_binding"]["contract_version"] = "2.1"
        result = self.assert_result(wrong_contract, gate.DENY)
        self.assertIn("schema validation failed", result.reason)

    def test_missing_structure_denies_and_unknown_mode_blocks(self):
        missing = copy.deepcopy(self.registry)
        missing.pop("runtime_entries")
        self.assert_result(missing, gate.DENY)

        unknown = copy.deepcopy(self.registry)
        unknown["mode"] = "activate_runtime"
        self.assert_result(unknown, gate.BLOCKED)

    def test_top_level_schemas_are_closed(self):
        for document in (self.registry, self.evidence, self.receipt):
            candidate = copy.deepcopy(document)
            candidate["unexpected"] = True
            self.assert_result(candidate, gate.DENY)

    def test_runtime_provider_model_separation(self):
        first, second = self.registry["runtime_entries"]
        self.assertNotEqual(first["runtime_id"], first["provider_id"])
        self.assertNotEqual(first["runtime_id"], first["model_id"])
        self.assertEqual(first["provider_id"], second["provider_id"])
        self.assertEqual(first["model_id"], second["model_id"])
        self.assertNotEqual(first["runtime_id"], second["runtime_id"])
        self.assertNotEqual(first["session_id"], second["session_id"])

        provider_collision = copy.deepcopy(self.registry)
        provider_collision["runtime_entries"][0]["runtime_id"] = provider_collision["runtime_entries"][0]["provider_id"]
        self.assert_result(provider_collision, gate.DENY)

        model_collision = copy.deepcopy(self.registry)
        model_collision["runtime_entries"][0]["runtime_id"] = model_collision["runtime_entries"][0]["model_id"]
        self.assert_result(model_collision, gate.DENY)

    def test_duplicate_runtime_and_session_bindings_deny(self):
        duplicate_runtime = copy.deepcopy(self.registry)
        duplicate_runtime["runtime_entries"][1]["runtime_id"] = duplicate_runtime["runtime_entries"][0]["runtime_id"]
        self.assert_result(duplicate_runtime, gate.DENY)

        duplicate_session = copy.deepcopy(self.registry)
        duplicate_session["runtime_entries"][1]["session_id"] = duplicate_session["runtime_entries"][0]["session_id"]
        self.assert_result(duplicate_session, gate.DENY)

    def test_registry_and_shadow_verified_do_not_authenticate_or_authorize(self):
        result = self.assert_result(self.registry, gate.PASS)
        self.assertEqual(result.authority_effect, "NONE")
        schema = load_json(SCHEMAS / "runtime-registry.schema.json")
        schema_values = set(strings(schema))
        self.assertNotIn("AUTHENTICATED", schema_values)
        self.assertNotIn("AUTHORIZED", schema_values)
        self.assertNotIn("ACTIVE_AUTHORIZATION", schema_values)
        self.assertNotIn("PRODUCTION_TRUSTED", schema_values)

    def test_unknown_and_production_trust_domains_deny(self):
        unknown = copy.deepcopy(self.registry)
        unknown["runtime_entries"][0]["trust_domain_id"] = "trust:missing"
        self.assert_result(unknown, gate.DENY)

        production = copy.deepcopy(self.registry)
        production["trust_domains"][0]["environment_class"] = "PRODUCTION"
        self.assert_result(production, gate.DENY)

    def test_revoked_domain_and_runtime_deny(self):
        domain = copy.deepcopy(self.registry)
        domain["trust_domains"][0]["revocation_state"] = "REVOKED"
        self.assert_result(domain, gate.DENY)

        runtime = copy.deepcopy(self.registry)
        runtime["runtime_entries"][0]["identity_state"] = "REVOKED"
        self.assert_result(runtime, gate.DENY)

    def test_runtime_expiry_requires_explicit_time_and_denies_when_expired(self):
        candidate = copy.deepcopy(self.registry)
        candidate["runtime_entries"][0]["expires_at"] = "2026-08-20T00:00:00Z"
        self.assert_result(candidate, gate.BLOCKED)
        self.assert_result(candidate, gate.PASS, verifier_time="2026-08-19T12:00:00Z")
        self.assert_result(candidate, gate.DENY, verifier_time="2026-08-20T00:00:00Z")

    def test_evidence_expiry_and_revocation_deny(self):
        expired = copy.deepcopy(self.evidence)
        expired["expires_at"] = "2026-08-20T00:00:00Z"
        self.assert_result(expired, gate.BLOCKED)
        self.assert_result(expired, gate.DENY, verifier_time="2026-08-21T00:00:00Z")

        revoked = copy.deepcopy(self.evidence)
        revoked["revocation_state"] = "REVOKED"
        self.assert_result(revoked, gate.DENY)

    def test_evidence_and_receipt_never_confer_authority(self):
        for document in (self.evidence, self.receipt):
            result = self.assert_result(document, gate.PASS)
            self.assertEqual(result.authority_effect, "NONE")

    def test_w2_dual_role_same_actor_success(self):
        same_actor = copy.deepcopy(self.receipt)
        same_actor["materializer_attribution"]["actor"] = same_actor["producer_attribution"]["actor"]
        self.assertEqual(
            same_actor["producer_attribution"]["actor"],
            same_actor["materializer_attribution"]["actor"],
        )
        self.assertIsNot(
            same_actor["producer_attribution"],
            same_actor["materializer_attribution"],
        )
        result = self.assert_result(same_actor, gate.PASS)
        self.assertEqual(result.governance_status, "UNAUTHENTICATED_SHADOW")
        self.assertEqual(result.authority_effect, "NONE")
        self.assertEqual(result.identity_effect, "NONE")
        self.assertEqual(result.execution_effect, "NONE")
        self.assertEqual(result.activation_effect, "NONE")
        self.assertFalse(result.eligible_for_execution)

    def test_w2_missing_materializer_attribution_deny(self):
        candidate = copy.deepcopy(self.receipt)
        candidate.pop("materializer_attribution")
        self.assert_result(candidate, gate.DENY)

    def test_w2_missing_producer_attribution_deny(self):
        candidate = copy.deepcopy(self.receipt)
        candidate.pop("producer_attribution")
        self.assert_result(candidate, gate.DENY)

    def test_w2_conflated_single_attribution_deny(self):
        candidate = copy.deepcopy(self.receipt)
        attribution = candidate.pop("producer_attribution")
        candidate.pop("materializer_attribution")
        candidate["attribution"] = attribution
        self.assert_result(candidate, gate.DENY)

    def test_all_result_classes_preserve_taint(self):
        denied = copy.deepcopy(self.registry)
        denied["profile_version"] = "2.0"
        blocked = copy.deepcopy(self.registry)
        blocked["mode"] = "unknown_mode"

        results = [
            self.assert_result(self.receipt, gate.PASS),
            self.assert_result(denied, gate.DENY),
            self.assert_result(blocked, gate.BLOCKED),
        ]
        boundary = {
            (
                result.governance_status,
                result.authority_effect,
                result.identity_effect,
                result.execution_effect,
                result.activation_effect,
                result.eligible_for_execution,
            )
            for result in results
        }
        self.assertEqual(
            boundary,
            {("UNAUTHENTICATED_SHADOW", "NONE", "NONE", "NONE", "NONE", False)},
        )

    def test_digest_match_mismatch_and_malformed(self):
        self.assert_result(self.receipt, gate.PASS)

        mismatch = copy.deepcopy(self.receipt)
        mismatch["exact_byte_verification"]["observed_digest"] = "sha256:" + "0" * 64
        self.assert_result(mismatch, gate.DENY)

        malformed = copy.deepcopy(self.receipt)
        malformed["content_digest"] = "sha256:not-a-digest"
        self.assert_result(malformed, gate.DENY)

    def test_evidence_parent_duplicate_and_self_reference_deny(self):
        duplicate = copy.deepcopy(self.evidence)
        duplicate["parent_evidence_ids"].append(duplicate["parent_evidence_ids"][0])
        self.assert_result(duplicate, gate.DENY)

        self_parent = copy.deepcopy(self.evidence)
        self_parent["parent_evidence_ids"][0] = self_parent["evidence_id"]
        self.assert_result(self_parent, gate.DENY)

    def test_nonce_uniqueness_within_supplied_set(self):
        seen = set()
        self.assert_result(self.evidence, gate.PASS, seen_nonces=seen)
        self.assert_result(self.evidence, gate.DENY, seen_nonces=seen)

    def test_cross_run_replay_without_durable_state_blocks(self):
        result = self.assert_result(self.evidence, gate.BLOCKED, cross_run_replay=True)
        self.assertIn("durable state", result.reason)

    def test_exact_byte_repository_target_match_and_mismatch(self):
        self.assert_result(
            self.receipt,
            gate.PASS,
            exact_target=EVIDENCE_FIXTURE,
            exact_target_requested=True,
        )
        self.assert_result(
            self.receipt,
            gate.DENY,
            exact_target=RUNTIME_FIXTURE,
            exact_target_requested=True,
        )

    def test_missing_exact_byte_target_blocks(self):
        self.assert_result(self.receipt, gate.BLOCKED, exact_target_requested=True)

    def test_parent_traversal_and_path_escape_block(self):
        result = self.assert_result(
            self.receipt,
            gate.BLOCKED,
            exact_target=Path("../outside.json"),
            exact_target_requested=True,
        )
        self.assertIn("parent traversal", result.reason)

    def test_symlink_target_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / "evidence-link.json"
            link.symlink_to(EVIDENCE_FIXTURE)
            self.assert_result(
                self.receipt,
                gate.BLOCKED,
                exact_target=link,
                exact_target_requested=True,
            )

    def test_unsupported_evidence_method_denies(self):
        candidate = copy.deepcopy(self.evidence)
        candidate["verification_method"] = "REMOTE_AUTHORITY_LOOKUP"
        self.assert_result(candidate, gate.DENY)

    def test_no_active_authorization_grant_default_cutover_or_activation(self):
        schemas = [load_json(path) for path in sorted(SCHEMAS.glob("*.json"))]
        schema_values = set(value for schema in schemas for value in strings(schema))
        forbidden_states = {
            "AUTHENTICATED",
            "AUTHORIZED",
            "ACTIVE_AUTHORIZATION",
            "PRODUCTION_TRUSTED",
            "AUTHORIZATION_EVIDENCE",
            "GRANT_ISSUANCE",
            "AUTHORITY_PROOF",
        }
        self.assertTrue(forbidden_states.isdisjoint(schema_values))

        profile = PROFILE.read_text(encoding="utf-8")
        self.assertIn("Default Consumption: NONE", profile)
        self.assertIn("Cutover: NONE", profile)
        self.assertIn("Activation: LOCKED", profile)
        self.assertIn("Operational Entry: LOCKED", profile)

    def test_profile_preserves_version_and_authority_boundaries(self):
        profile = PROFILE.read_text(encoding="utf-8")
        required = [
            "W2 SHADOW PROFILE / NON-PRODUCTION / NON-DEFAULT / NON-CUTOVER",
            "ACOS Contract 2.0",
            "W2 AUXILIARY SCHEMA FAMILY:\n1.0",
            "Runtime Identity != Provider/Model",
            "Producer != Materializer",
            "Dual-role declaration != dual-role authority",
            "same actor may appear",
            "Evidence != Authority",
            "Persistence Receipt != Persistence Grant",
            "PARTIALLY ADDRESSED / NOT RESOLVED",
            "does not create an independently governed native ChatGPT governance persistence channel",
            "DEFER CRYPTO",
            "NON-ACTIVATING",
        ]
        for item in required:
            with self.subTest(item=item):
                self.assertIn(item, profile)

    def test_verifier_has_no_operational_capability(self):
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)

        forbidden_imports = {
            "subprocess", "socket", "requests", "urllib.request", "http.client",
            "ftplib", "paramiko", "dulwich", "git", "cryptography", "nacl", "keyring",
        }
        forbidden_calls = {
            "system", "popen", "write_text", "write_bytes", "mkdir", "unlink",
            "rename", "replace", "touch",
        }
        self.assertTrue(forbidden_imports.isdisjoint(imported))
        self.assertTrue(forbidden_calls.isdisjoint(calls))
        self.assertNotIn("datetime.now", source)

    def test_parser_schema_and_path_guards_fail_closed(self):
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

        outside = ROOT / "fixtures" / "schemas" / "w2" / "1.0" / "runtime-registry.schema.json"
        with self.assertRaises(gate.Blocked):
            gate.confined_path(outside, gate.FIXTURE_ROOT, require_json=True, label="fixture target")

    def test_cli_positive_fixtures_exit_zero(self):
        targets = [str(RUNTIME_FIXTURE), str(EVIDENCE_FIXTURE), str(RECEIPT_FIXTURE)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main(targets), 0)

    def test_cli_unknown_or_missing_target_exits_two(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main([str(FIXTURES / "missing.json")]), 2)

    def test_protected_assets_are_byte_identical(self):
        for relative, expected in PROTECTED_HASHES.items():
            digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            with self.subTest(path=relative):
                self.assertEqual(digest, expected)


if __name__ == "__main__":
    unittest.main()

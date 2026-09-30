#!/usr/bin/env python3
"""Logical test inventory for ACOS W3B-B-P1.

Category A is non-mutating and authorized by IMPLEMENTATION-02.
Category B is implemented but skipped unless a separate mutation-test task
sets ACOS_W3B_B_P1_MUTATION_TESTS_AUTHORIZED=1.
"""

from __future__ import annotations

import importlib.util
import hashlib
import inspect
import json
import os
import sqlite3
import sys
import threading
import unittest
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from jsonschema import Draft7Validator, ValidationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
def load_module(name: str, relative_path: str):
    path = REPOSITORY_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    module.__acos_canonical_source_sha256__ = (
        f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    )
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module(
    "acos_w3b_b_p1_single_index_repair",
    "scripts/acos-w3b-b-p1-single-index-repair.py",
)
factory = runner.factory_module
mutator = runner.mutator_module
verifier = runner.verifier_module

RESEARCH_SCHEMA_PATH = REPOSITORY_ROOT / (
    "fixtures/schemas/w3b-b-p1/1.0/"
    "disposable-fixture-research-binding.schema.json"
)
RESULT_SCHEMA_PATH = REPOSITORY_ROOT / (
    "fixtures/schemas/w3b-b-p1/1.0/"
    "disposable-fixture-repair-result.schema.json"
)
RESEARCH_EXAMPLE_PATH = REPOSITORY_ROOT / (
    "fixtures/schema-validation-w3b-b-p1/1.0/"
    "valid-disposable-fixture-research-binding.json"
)
RESULT_EXAMPLE_PATH = REPOSITORY_ROOT / (
    "fixtures/schema-validation-w3b-b-p1/1.0/"
    "valid-disposable-fixture-repair-result.json"
)

RESEARCH_SCHEMA = json.loads(RESEARCH_SCHEMA_PATH.read_text(encoding="utf-8"))
RESULT_SCHEMA = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
RESEARCH_EXAMPLE = json.loads(RESEARCH_EXAMPLE_PATH.read_text(encoding="utf-8"))
RESULT_EXAMPLE = json.loads(RESULT_EXAMPLE_PATH.read_text(encoding="utf-8"))
MUTATION_TESTS_AUTHORIZED = (
    os.environ.get("ACOS_W3B_B_P1_MUTATION_TEST_TASK_ID")
    == "ACOS-MIG-W3B-B-P1-MUTATION-TEST"
    and os.environ.get("ACOS_W3B_B_P1_MUTATION_TEST_BINDING_DIGEST")
    == RESEARCH_EXAMPLE["binding_digest"]
)


def resign_binding(value):
    value["binding_digest"] = runner.mutator_module.digest_without(
        value, "binding_digest"
    )
    return value


def synthetic_handle(
    state,
    *,
    registry=None,
    fixture_instance_id="id",
    reusable=True,
    mutation_attempt_count=0,
    generation=0,
):
    handle = object.__new__(factory.FixtureHandle)
    values = {
        "fixture_instance_id": fixture_instance_id,
        "root": Path("/nonexistent/root"),
        "database": Path("/nonexistent/db"),
        "root_identity": factory.FileIdentity(1, 2, 1, 0o700),
        "database_identity": factory.FileIdentity(1, 3, 1, 0o600),
        "lifecycle_state": state,
        "reusable": reusable,
        "mutation_attempt_count": mutation_attempt_count,
        "generation": generation,
        "_factory_token": factory._HANDLE_TOKEN,
        "_registry_token": (
            registry._registry_token if registry is not None else object()
        ),
    }
    for key, value in values.items():
        object.__setattr__(handle, key, value)
    return handle


def registered_synthetic_handle(state, **kwargs):
    registry = factory.FixtureRegistry()
    handle = synthetic_handle(state, registry=registry, **kwargs)
    registry._register(handle)
    return registry, handle


class SchemaAndFixtureTests(unittest.TestCase):
    def test_research_example_validates(self):
        Draft7Validator(RESEARCH_SCHEMA).validate(RESEARCH_EXAMPLE)

    def test_result_example_validates(self):
        Draft7Validator(RESULT_SCHEMA).validate(RESULT_EXAMPLE)

    def test_runner_pre_mutation_deny_result_validates(self):
        binding = deepcopy(RESEARCH_EXAMPLE)
        orchestrator = runner.DisposableSingleIndexRepairRunner(REPOSITORY_ROOT)
        ready = synthetic_handle(
            factory.STATE_READY, registry=orchestrator.registry,
            fixture_instance_id=binding["fixture_instance_id"],
        )
        orchestrator.registry._register(ready)
        orchestrator.factory.create = mock.Mock(return_value=ready)
        orchestrator.seed_initializer = mock.Mock()
        orchestrator._inject_fixed_fault = mock.Mock()
        orchestrator.repair_mutator = mock.Mock()
        orchestrator.repair_mutator.execute.return_value = factory.WriterOutcome(
            profile=factory.PROFILE_REPAIR, mutation_attempted=False,
            rollback_proven=False, commit_proven=False,
            outcome_uncertain=False, callbacks=(), authorization_denied=True,
        )
        orchestrator.verifier = mock.Mock()
        orchestrator.verifier.verify.return_value = mock.Mock(index_present=False)
        with mock.patch.multiple(
            runner, validate_research_binding=mock.DEFAULT,
            observe_mutation_test_gate=mock.Mock(return_value=mock.Mock()),
            validate_current_fixture_binding=mock.Mock(
                return_value=binding["pre_mutation_fixture_digest"]
            ),
        ), mock.patch.object(factory, "verify_identity_checkpoint"):
            result = orchestrator.run(binding)
        self.assertIs(type(result), mutator.RepairResult)
        self.assertEqual(result.result, mutator.RESULT_DENY)
        self.assertEqual(result.reason_code, "REPAIR_AUTHORIZATION_DENIED")
        self.assertEqual(result.transaction_outcome, mutator.OUTCOME_NOT_STARTED)
        self.assertEqual(result.mutation_effect, mutator.EFFECT_NONE)
        self.assertEqual(result.poststate_status, "NOT_EVALUATED")
        self.assertIsNone(result.poststate_digest)
        self.assertEqual(result.state, factory.STATE_QUARANTINED)
        orchestrator.repair_mutator.execute.assert_called_once()
        orchestrator.verifier.verify.assert_called_once_with(ready.database)
        document = json.loads(result.to_canonical_json())
        self.assertEqual(document["poststate_status"], "NOT_EVALUATED")
        Draft7Validator(RESULT_SCHEMA).validate(document)
        with self.assertRaises(ValidationError):
            Draft7Validator(RESULT_SCHEMA).validate(
                dict(document, poststate_status="NOT_CHECKED")
            )

    def test_research_schema_is_closed(self):
        self.assertFalse(RESEARCH_SCHEMA["additionalProperties"])

    def test_result_schema_is_closed(self):
        self.assertFalse(RESULT_SCHEMA["additionalProperties"])

    def test_research_schema_requires_full_taint(self):
        required = set(RESEARCH_SCHEMA["required"])
        self.assertTrue(
            {
                "scope", "evidence_class", "governance_status", "effects",
                "eligible_for_execution", "fixture_mutation_scope",
                "production_repair_effect", "production_eligibility",
                "operational_entry_effect",
            }.issubset(required)
        )

    def test_result_schema_requires_full_taint(self):
        required = set(RESULT_SCHEMA["required"])
        self.assertTrue(
            {
                "scope", "evidence_class", "governance_status", "effects",
                "eligible_for_execution", "fixture_mutation_scope",
                "production_repair_effect", "production_eligibility",
                "operational_entry_effect",
            }.issubset(required)
        )

    def test_research_digest_pattern_is_canonical(self):
        self.assertEqual(
            RESEARCH_SCHEMA["definitions"]["digest"]["pattern"],
            "^sha256:[0-9a-f]{64}$",
        )

    def test_result_digest_pattern_is_canonical(self):
        self.assertEqual(
            RESULT_SCHEMA["definitions"]["digest"]["pattern"],
            "^sha256:[0-9a-f]{64}$",
        )

    def test_allowed_action_is_fixed(self):
        self.assertEqual(
            RESEARCH_SCHEMA["properties"]["allowed_action"]["const"],
            "RECREATE_MISSING_CANONICAL_INDEX",
        )

    def test_maximum_mutation_count_is_one(self):
        self.assertEqual(
            RESEARCH_SCHEMA["properties"]["maximum_mutation_count"]["const"], 1
        )

    def test_research_scope_is_disposable_only(self):
        self.assertEqual(
            RESEARCH_SCHEMA["properties"]["scope"]["const"],
            "DISPOSABLE_FIXTURE_ONLY",
        )

    def test_result_scope_is_disposable_only(self):
        self.assertEqual(
            RESULT_SCHEMA["properties"]["scope"]["const"],
            "DISPOSABLE_FIXTURE_ONLY",
        )

    def test_research_binding_cannot_be_execution_eligible(self):
        self.assertFalse(
            RESEARCH_SCHEMA["properties"]["eligible_for_execution"]["const"]
        )

    def test_result_cannot_be_execution_eligible(self):
        self.assertFalse(
            RESULT_SCHEMA["properties"]["eligible_for_execution"]["const"]
        )

    def test_result_vocabulary_is_exact(self):
        self.assertEqual(
            set(RESULT_SCHEMA["properties"]["result"]["enum"]),
            {
                "PASS", "DENY", "BLOCKED", "FAILED_MUTATION",
                "FAILED_POSTSTATE", "FAILED_DISPOSAL",
            },
        )

    def test_mutation_effect_vocabulary_is_exact(self):
        self.assertEqual(
            set(RESULT_SCHEMA["properties"]["mutation_effect"]["enum"]),
            {
                "NONE", "ATTEMPTED_AND_ROLLED_BACK",
                "COMMITTED_TEST_ONLY_DISPOSABLE_FIXTURE",
                "UNKNOWN_TEST_ONLY_DISPOSABLE_FIXTURE_EFFECT",
            },
        )

    def test_unknown_outcome_state_is_represented(self):
        self.assertIn(
            "MUTATION_OUTCOME_UNKNOWN",
            RESULT_SCHEMA["properties"]["state"]["enum"],
        )

    def test_examples_have_expected_object_types(self):
        self.assertEqual(
            (
                RESEARCH_EXAMPLE["object_type"],
                RESULT_EXAMPLE["object_type"],
            ),
            (
                "disposable_fixture_research_binding",
                "disposable_fixture_repair_result",
            ),
        )

    def test_examples_remain_unauthenticated_shadow(self):
        self.assertEqual(
            (
                RESEARCH_EXAMPLE["governance_status"],
                RESULT_EXAMPLE["governance_status"],
            ),
            ("UNAUTHENTICATED_SHADOW", "UNAUTHENTICATED_SHADOW"),
        )

    def test_unknown_example_property_is_rejected(self):
        invalid = dict(RESEARCH_EXAMPLE, authority_upgrade=True)
        with self.assertRaises(ValidationError):
            Draft7Validator(RESEARCH_SCHEMA).validate(invalid)


class DigestAndSerializationTests(unittest.TestCase):
    def test_digest_parses_canonical_value(self):
        value = "sha256:" + ("ab" * 32)
        self.assertEqual(mutator.Digest256.parse(value).serialize(), value)

    def test_digest_serializes_lowercase_prefix(self):
        value = mutator.Digest256(bytes.fromhex("AB" * 32)).serialize()
        self.assertEqual(value, "sha256:" + ("ab" * 32))

    def test_digest_rejects_uppercase_serialization(self):
        with self.assertRaises(ValueError):
            mutator.Digest256.parse("sha256:" + ("AB" * 32))

    def test_digest_rejects_missing_prefix(self):
        with self.assertRaises(ValueError):
            mutator.Digest256.parse("ab" * 32)

    def test_digest_rejects_whitespace(self):
        with self.assertRaises(ValueError):
            mutator.Digest256.parse(" sha256:" + ("ab" * 32))

    def test_digest_rejects_double_prefix(self):
        with self.assertRaises(ValueError):
            mutator.Digest256.parse("sha256:sha256:" + ("ab" * 32))

    def test_digest_rejects_short_value(self):
        with self.assertRaises(ValueError):
            mutator.Digest256.parse("sha256:00")

    def test_digest_rejects_non_32_byte_raw_value(self):
        with self.assertRaises(ValueError):
            mutator.Digest256(b"short")

    def test_digest_constant_time_equality(self):
        left = mutator.Digest256.of_bytes(b"same")
        right = mutator.Digest256.of_bytes(b"same")
        self.assertTrue(left.constant_time_equals(right))

    def test_digest_constant_time_inequality(self):
        left = mutator.Digest256.of_bytes(b"left")
        right = mutator.Digest256.of_bytes(b"right")
        self.assertFalse(left.constant_time_equals(right))

    def test_digest_of_bytes_known_vector(self):
        self.assertEqual(
            mutator.Digest256.of_bytes(b"").serialize(),
            "sha256:e3b0c44298fc1c149afbf4c8996fb924"
            "27ae41e4649b934ca495991b7852b855",
        )

    def test_typed_null_is_unambiguous(self):
        self.assertEqual(verifier._typed_value(None), ["null", None])

    def test_typed_integer_is_unambiguous(self):
        self.assertEqual(verifier._typed_value(7), ["integer", 7])

    def test_typed_float_uses_hex_representation(self):
        self.assertEqual(verifier._typed_value(1.5), ["real", float.hex(1.5)])

    def test_typed_blob_uses_hex_representation(self):
        self.assertEqual(verifier._typed_value(b"\x00\xff"), ["blob", "00ff"])

    def test_canonical_json_sorts_keys(self):
        self.assertEqual(
            verifier.canonical_json_bytes({"b": 2, "a": 1}),
            b'{"a":1,"b":2}',
        )

    def test_canonical_rows_digest_is_deterministic(self):
        rows = [(1, "x", b"y")]
        self.assertEqual(
            verifier.canonical_rows_digest(rows),
            verifier.canonical_rows_digest(rows),
        )


class PolicyAndMappingTests(unittest.TestCase):
    def test_fault_statement_is_exact(self):
        self.assertEqual(
            factory.FAULT_SQL, "DROP INDEX idx_audit_events_aggregate;"
        )

    def test_repair_statement_is_exact(self):
        self.assertEqual(
            factory.REPAIR_SQL,
            "CREATE INDEX idx_audit_events_aggregate\n"
            "ON audit_events(aggregate_type, aggregate_id, sequence);",
        )

    def test_privileged_reindex_statement_is_exact(self):
        self.assertEqual(
            factory.PRIVILEGED_REINDEX_SQL,
            "REINDEX main.idx_audit_events_aggregate",
        )

    def test_canonical_repair_sql_identity_drift_is_rejected(self):
        with mock.patch.object(factory, "REPAIR_SQL", "CREATE INDEX other ON x(y)"):
            with self.assertRaisesRegex(
                factory.FixtureSecurityError, "SQL identity drift"
            ):
                factory._verify_canonical_repair_operation_digest()

    def test_repair_statement_has_no_if_not_exists(self):
        self.assertNotIn("IF NOT EXISTS", factory.REPAIR_SQL.upper())

    def test_writer_profile_names_are_distinct(self):
        self.assertEqual(
            len(
                {
                    factory.SeedInitializer.profile,
                    factory.FaultInjector.profile,
                    factory.RepairMutator.profile,
                }
            ),
            3,
        )

    def test_candidate_profiles_are_not_characterized(self):
        self.assertTrue(
            all(
                not profile.characterized
                for profile in mutator.CANDIDATE_PROFILES.values()
            )
        )

    def test_seed_profile_allows_only_canonical_reindex_on_main(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_SEED]
        for index_name in mutator.CANONICAL_SEED_INDEX_NAMES:
            self.assertEqual(
                profile.decide(
                    sqlite3.SQLITE_REINDEX,
                    index_name,
                    None,
                    "main",
                    None,
                ),
                sqlite3.SQLITE_OK,
            )

    def test_seed_profile_denies_unknown_reindex_name(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_SEED]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_REINDEX, "caller_index", None, "main", None
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_seed_profile_denies_canonical_reindex_on_wrong_database(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_SEED]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_REINDEX,
                mutator.FIXED_INDEX,
                None,
                "temp",
                None,
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_fault_profile_denies_seed_reindex(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_REINDEX,
                mutator.FIXED_INDEX,
                None,
                "main",
                None,
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_repair_profile_denies_seed_reindex(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_REINDEX,
                mutator.FIXED_INDEX,
                None,
                "main",
                None,
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_unknown_profile_denies_seed_reindex(self):
        profile = mutator.CandidateAuthorizerProfile(
            "UNKNOWN", frozenset({sqlite3.SQLITE_REINDEX})
        )
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_REINDEX,
                mutator.FIXED_INDEX,
                None,
                "main",
                None,
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_caller_cannot_inject_canonical_seed_index_names(self):
        self.assertEqual(
            mutator.CANONICAL_SEED_INDEX_NAMES,
            frozenset(
                {
                    "idx_grant_observations_grant_id",
                    "idx_authorization_events_authorization",
                    "idx_workflow_state_events_task",
                    "idx_audit_events_aggregate",
                }
            ),
        )
        profile = mutator.CandidateAuthorizerProfile(
            mutator.PROFILE_SEED, frozenset({sqlite3.SQLITE_REINDEX})
        )
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_REINDEX, "injected", None, "main", None
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_fault_profile_allows_fixed_index(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_DROP_INDEX,
                mutator.FIXED_INDEX,
                mutator.FIXED_TABLE,
                "main",
                None,
            ),
            sqlite3.SQLITE_OK,
        )

    def test_fault_profile_denies_other_index(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_DROP_INDEX, "other", mutator.FIXED_TABLE, "main", None
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_fault_profile_denies_table_dml(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_INSERT, mutator.FIXED_TABLE, None, "main", None
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_fault_profile_denies_pragma(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(sqlite3.SQLITE_PRAGMA, "journal_mode", None, "main", None),
            sqlite3.SQLITE_DENY,
        )

    def test_fault_profile_denies_drop_table(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_DROP_TABLE, mutator.FIXED_TABLE, None, "main", None
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_repair_profile_allows_fixed_index(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_CREATE_INDEX,
                mutator.FIXED_INDEX,
                mutator.FIXED_TABLE,
                "main",
                None,
            ),
            sqlite3.SQLITE_OK,
        )

    def test_repair_profile_denies_other_index(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_CREATE_INDEX, "other", mutator.FIXED_TABLE, "main", None
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_repair_profile_denies_table_dml(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_UPDATE, mutator.FIXED_TABLE, "event_type", "main", None
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_repair_profile_denies_pragma(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertEqual(
            profile.decide(sqlite3.SQLITE_PRAGMA, "user_version", None, "main", None),
            sqlite3.SQLITE_DENY,
        )

    def test_unexpected_authorizer_action_denies(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertEqual(
            profile.decide(999999, None, None, None, None),
            sqlite3.SQLITE_DENY,
        )

    def test_authorizer_recorder_records_synthetic_callback(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        recorder = mutator.AuthorizerRecorder(profile)
        recorder(sqlite3.SQLITE_PRAGMA, "x", None, "main", None)
        self.assertEqual(len(recorder.callbacks), 1)

    def test_effect_mapping_none(self):
        value = mutator.classify_mutation_effect(
            mutation_attempted=False, rollback_proven=False, commit_proven=False
        )
        self.assertEqual((value.transaction_outcome, value.mutation_effect),
                         (mutator.OUTCOME_NOT_STARTED, mutator.EFFECT_NONE))

    def test_effect_mapping_rolled_back(self):
        value = mutator.classify_mutation_effect(
            mutation_attempted=True, rollback_proven=True, commit_proven=False
        )
        self.assertEqual(value.mutation_effect, mutator.EFFECT_ROLLED_BACK)

    def test_effect_mapping_committed(self):
        value = mutator.classify_mutation_effect(
            mutation_attempted=True, rollback_proven=False, commit_proven=True
        )
        self.assertEqual(value.mutation_effect, mutator.EFFECT_COMMITTED)

    def test_effect_mapping_unknown_attempt(self):
        value = mutator.classify_mutation_effect(
            mutation_attempted=True, rollback_proven=False, commit_proven=False
        )
        self.assertEqual(value.mutation_effect, mutator.EFFECT_UNKNOWN)

    def test_conflicting_transaction_proof_is_unknown(self):
        value = mutator.classify_mutation_effect(
            mutation_attempted=True, rollback_proven=True, commit_proven=True
        )
        self.assertEqual(value.transaction_outcome, mutator.OUTCOME_UNKNOWN)

    def test_unknown_effect_is_non_reusable(self):
        value = mutator.classify_mutation_effect(
            mutation_attempted=True, rollback_proven=False, commit_proven=False
        )
        self.assertFalse(value.reusable)

    def test_unknown_effect_is_execution_terminal(self):
        value = mutator.classify_mutation_effect(
            mutation_attempted=True, rollback_proven=False, commit_proven=False
        )
        self.assertEqual(value.terminal_state, mutator.STATE_UNKNOWN)

    def test_commit_exception_with_active_transaction_is_not_rollback(self):
        self.assertEqual(
            mutator.classify_commit_exception(connection_in_transaction=True),
            "ACTIVE_TRANSACTION",
        )

    def test_commit_exception_without_active_transaction_is_unknown(self):
        self.assertEqual(
            mutator.classify_commit_exception(connection_in_transaction=False),
            mutator.OUTCOME_UNKNOWN,
        )


class BoundaryAndPreflightTests(unittest.TestCase):
    def _attempted_fixture(self):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        task_bound = registry.transition(
            ready,
            factory.STATE_READY,
            factory.STATE_MUTATION_TASK_BOUND,
        )
        attempted = registry.transition(
            task_bound,
            factory.STATE_MUTATION_TASK_BOUND,
            factory.STATE_MUTATION_ATTEMPTED,
        )
        return registry, ready, task_bound, attempted

    def _overlapping_claim_evidence(self):
        registry, _ready, _bound, attempted = self._attempted_fixture()
        owner_active = threading.Event()
        release_owner = threading.Event()
        observations = []

        def owner():
            registry._claim_privileged_repair(attempted)
            observations.append(
                ("owner-active", len(registry._active_privileged_repairs))
            )
            owner_active.set()
            release_owner.wait(timeout=2)
            registry._release_privileged_repair(attempted)

        def contender():
            owner_active.wait(timeout=2)
            try:
                registry._claim_privileged_repair(attempted)
            except factory.FixtureSecurityError as exc:
                observations.append(("contender-denied", str(exc)))
            else:
                observations.append(("contender-admitted", "unexpected"))
            finally:
                release_owner.set()

        owner_thread = threading.Thread(target=owner)
        contender_thread = threading.Thread(target=contender)
        owner_thread.start()
        contender_thread.start()
        owner_thread.join(timeout=2)
        contender_thread.join(timeout=2)
        self.assertFalse(owner_thread.is_alive())
        self.assertFalse(contender_thread.is_alive())
        return registry, observations

    def _pure_seed_failure(self, disposition_outcome):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        events = []

        class FailingConnection:
            def executescript(self, _source):
                raise sqlite3.DatabaseError("synthetic seed failure")

        @contextmanager
        def fake_writer(*_args):
            events.append("OPEN")
            try:
                yield FailingConnection(), object()
            finally:
                events.append("CLOSE")

        def contain(*_args):
            events.append("CONTAIN")
            return factory.SeedConstructionDisposition(disposition_outcome)

        initializer = factory.SeedInitializer(REPOSITORY_ROOT)
        with mock.patch.object(
            factory, "_internal_writer_connection", fake_writer
        ), mock.patch.object(
            initializer, "source_bytes", return_value=b"canonical seed"
        ), mock.patch.object(
            factory, "_contain_failed_seed_failure", side_effect=contain
        ):
            with self.assertRaises(factory.SeedConstructionFailure) as caught:
                initializer.initialize(ready, registry)
        return caught.exception, events

    def test_seed_failure_closes_writer_before_containment(self):
        _failure, events = self._pure_seed_failure(
            factory.SEED_CONSTRUCTION_FAILED_DISPOSED
        )
        self.assertEqual(events, ["OPEN", "CLOSE", "CONTAIN"])

    def test_seed_failure_returns_no_usable_handle_or_repair_effect(self):
        failure, _events = self._pure_seed_failure(
            factory.SEED_CONSTRUCTION_FAILED_DISPOSED
        )
        self.assertEqual(
            failure.disposition.outcome,
            factory.SEED_CONSTRUCTION_FAILED_DISPOSED,
        )
        self.assertEqual(failure.disposition.authority_effect, "NONE")
        self.assertEqual(failure.disposition.production_effect, "NONE")
        self.assertFalse(failure.disposition.eligible_for_execution)
        self.assertFalse(hasattr(failure.disposition, "mutation_effect"))

    def test_failed_seed_safe_cleanup_disposes_once(self):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        disposed = replace(
            ready,
            lifecycle_state=factory.STATE_DISPOSED,
            reusable=False,
            generation=ready.generation + 2,
        )
        with mock.patch.object(
            factory.DisposableFixtureFactory,
            "dispose",
            return_value=disposed,
        ) as dispose, mock.patch.object(
            factory.DisposableFixtureFactory, "quarantine"
        ) as quarantine:
            outcome = factory._contain_failed_seed_failure(ready, registry)
        dispose.assert_called_once_with(ready)
        quarantine.assert_not_called()
        self.assertEqual(
            outcome.outcome, factory.SEED_CONSTRUCTION_FAILED_DISPOSED
        )

    def test_failed_seed_identity_uncertainty_quarantines(self):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        quarantined = replace(
            ready,
            lifecycle_state=factory.STATE_QUARANTINED,
            reusable=False,
            generation=ready.generation + 1,
        )
        with mock.patch.object(
            factory.DisposableFixtureFactory,
            "dispose",
            side_effect=factory.FixtureSecurityError("identity uncertainty"),
        ) as dispose, mock.patch.object(
            factory.DisposableFixtureFactory,
            "quarantine",
            return_value=quarantined,
        ) as quarantine:
            outcome = factory._contain_failed_seed_failure(ready, registry)
        dispose.assert_called_once_with(ready)
        quarantine.assert_called_once_with(ready)
        self.assertEqual(
            outcome.outcome, factory.SEED_CONSTRUCTION_FAILED_QUARANTINED
        )

    def test_failed_seed_cleanup_failure_quarantines_without_retry(self):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        quarantined = replace(
            ready,
            lifecycle_state=factory.STATE_QUARANTINED,
            reusable=False,
            generation=ready.generation + 1,
        )
        with mock.patch.object(
            factory.DisposableFixtureFactory,
            "dispose",
            side_effect=OSError("cleanup failed"),
        ) as dispose, mock.patch.object(
            factory.DisposableFixtureFactory,
            "quarantine",
            return_value=quarantined,
        ) as quarantine:
            outcome = factory._contain_failed_seed_failure(ready, registry)
        self.assertEqual(dispose.call_count, 1)
        self.assertEqual(quarantine.call_count, 1)
        self.assertEqual(
            outcome.outcome, factory.SEED_CONSTRUCTION_FAILED_QUARANTINED
        )

    def test_seed_failure_stops_runner_before_fault_and_repair(self):
        orchestrator = runner.DisposableSingleIndexRepairRunner(REPOSITORY_ROOT)
        runner_factory = runner.factory_module
        ready = object.__new__(runner_factory.FixtureHandle)
        values = {
            "fixture_instance_id": "seed-failure",
            "root": Path("/nonexistent/root"),
            "database": Path("/nonexistent/db"),
            "root_identity": runner_factory.FileIdentity(1, 2, 1, 0o700),
            "database_identity": runner_factory.FileIdentity(1, 3, 1, 0o600),
            "lifecycle_state": runner_factory.STATE_READY,
            "reusable": True,
            "mutation_attempt_count": 0,
            "generation": 0,
            "_factory_token": runner_factory._HANDLE_TOKEN,
            "_registry_token": orchestrator.registry._registry_token,
        }
        for key, value in values.items():
            object.__setattr__(ready, key, value)
        orchestrator.registry._register(ready)

        def fail_seed(*_args):
            orchestrator.registry.transition(
                ready,
                runner_factory.STATE_READY,
                runner_factory.STATE_QUARANTINED,
            )
            raise runner_factory.SeedConstructionFailure(
                runner_factory.SeedConstructionDisposition(
                    runner_factory.SEED_CONSTRUCTION_FAILED_QUARANTINED
                )
            )

        gate = mock.Mock()
        with mock.patch.object(
            runner, "validate_research_binding"
        ), mock.patch.object(
            runner, "observe_mutation_test_gate", return_value=gate
        ), mock.patch.object(
            runner.mutator_module, "runtime_preflight"
        ), mock.patch.object(
            orchestrator.factory, "create", return_value=ready
        ), mock.patch.object(
            orchestrator.seed_initializer, "initialize", side_effect=fail_seed
        ), mock.patch.object(
            orchestrator, "_inject_fixed_fault"
        ) as fault, mock.patch.object(
            orchestrator.repair_mutator, "execute"
        ) as repair:
            with self.assertRaises(runner_factory.SeedConstructionFailure):
                orchestrator.run({"fixture_instance_id": "seed-failure"})
        gate.require.assert_called_once()
        fault.assert_not_called()
        repair.assert_not_called()

    def test_database_leaf_is_fixed(self):
        self.assertEqual(
            factory.FIXED_DATABASE_LEAF,
            "acos-w3b-b-p1-disposable.sqlite3",
        )

    def test_root_mode_is_0700(self):
        self.assertEqual(factory.EXPECTED_ROOT_MODE, 0o700)

    def test_database_mode_is_0600(self):
        self.assertEqual(factory.EXPECTED_DATABASE_MODE, 0o600)

    def test_factory_create_accepts_no_path(self):
        self.assertNotIn(
            "path", inspect.signature(factory.DisposableFixtureFactory.create).parameters
        )

    def test_expected_sidecars_are_fixed(self):
        self.assertEqual(
            set(factory.EXPECTED_SIDECAR_SUFFIXES),
            {"-journal", "-wal", "-shm"},
        )

    def test_ready_can_transition_to_task_bound(self):
        registry, handle = registered_synthetic_handle(factory.STATE_READY)
        next_handle = registry.transition(
            handle,
            factory.STATE_READY,
            factory.STATE_MUTATION_TASK_BOUND,
        )
        self.assertEqual(next_handle.lifecycle_state, factory.STATE_MUTATION_TASK_BOUND)

    def test_attempt_latch_is_consumed_before_mutation(self):
        registry, handle = registered_synthetic_handle(
            factory.STATE_MUTATION_TASK_BOUND
        )
        attempted = registry.transition(
            handle,
            factory.STATE_MUTATION_TASK_BOUND,
            factory.STATE_MUTATION_ATTEMPTED,
        )
        self.assertEqual(attempted.mutation_attempt_count, 1)
        self.assertFalse(attempted.reusable)
        self.assertEqual(attempted.generation, handle.generation + 1)

    def test_attempt_latch_cannot_be_consumed_twice(self):
        registry, _ready, task_bound, attempted = self._attempted_fixture()
        with self.assertRaises(factory.FixtureSecurityError):
            registry.transition(
                task_bound,
                factory.STATE_MUTATION_TASK_BOUND,
                factory.STATE_MUTATION_ATTEMPTED,
            )
        self.assertEqual(registry.get(attempted.fixture_instance_id), attempted)

    def test_current_attempted_state_cannot_start_second_attempt(self):
        registry, _ready, _task_bound, attempted = self._attempted_fixture()
        with self.assertRaises(factory.FixtureSecurityError):
            registry.transition(
                attempted,
                factory.STATE_MUTATION_ATTEMPTED,
                factory.STATE_MUTATION_ATTEMPTED,
            )
        self.assertEqual(registry.get(attempted.fixture_instance_id), attempted)

    def test_mutation_attempted_transition_is_exact(self):
        self.assertIn(
            factory.STATE_MUTATION_ATTEMPTED,
            factory._ALLOWED_TRANSITIONS[factory.STATE_MUTATION_TASK_BOUND],
        )
        self.assertNotIn(
            "MUTATING",
            factory._ALLOWED_TRANSITIONS[factory.STATE_MUTATION_TASK_BOUND],
        )

    def test_invalid_lifecycle_transition_is_blocked(self):
        registry, handle = registered_synthetic_handle(factory.STATE_READY)
        with self.assertRaises(factory.FixtureSecurityError):
            registry.transition(
                handle, factory.STATE_READY, factory.STATE_DISPOSED
            )

    def test_registry_has_no_caller_state_update_primitive(self):
        self.assertFalse(hasattr(factory.FixtureRegistry, "update"))

    def test_forged_mutation_attempted_clone_is_rejected(self):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        forged = replace(
            ready,
            lifecycle_state=factory.STATE_MUTATION_ATTEMPTED,
            reusable=True,
            mutation_attempt_count=0,
        )
        with self.assertRaisesRegex(
            factory.FixtureSecurityError, "differs from canonical"
        ):
            registry.require_current(forged)

    def test_mutation_attempted_with_reusable_true_is_rejected(self):
        registry, _ready, _task_bound, attempted = self._attempted_fixture()
        forged = replace(attempted, reusable=True)
        with self.assertRaises(factory.FixtureSecurityError):
            registry.require_current(forged)

    def test_mutation_attempted_with_zero_count_is_rejected(self):
        registry, _ready, _task_bound, attempted = self._attempted_fixture()
        forged = replace(attempted, mutation_attempt_count=0)
        with self.assertRaises(factory.FixtureSecurityError):
            registry.require_current(forged)

    def test_stale_ready_handle_cannot_overwrite_newer_state(self):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        registry.transition(
            ready,
            factory.STATE_READY,
            factory.STATE_MUTATION_TASK_BOUND,
        )
        with self.assertRaisesRegex(factory.FixtureSecurityError, "stale"):
            registry.transition(
                ready,
                factory.STATE_READY,
                factory.STATE_MUTATION_TASK_BOUND,
            )

    def test_stale_task_bound_handle_cannot_replay_attempt(self):
        registry, _ready, task_bound, _attempted = self._attempted_fixture()
        with self.assertRaisesRegex(factory.FixtureSecurityError, "stale"):
            registry.transition(
                task_bound,
                factory.STATE_MUTATION_TASK_BOUND,
                factory.STATE_MUTATION_ATTEMPTED,
            )

    def test_stale_attempted_handle_cannot_replay_after_commit(self):
        registry, _ready, _task_bound, attempted = self._attempted_fixture()
        registry.transition(
            attempted,
            factory.STATE_MUTATION_ATTEMPTED,
            factory.STATE_MUTATION_COMMITTED,
        )
        with self.assertRaisesRegex(factory.FixtureSecurityError, "stale"):
            registry.transition(
                attempted,
                factory.STATE_MUTATION_ATTEMPTED,
                factory.STATE_MUTATION_COMMITTED,
            )

    def test_generation_advances_for_each_transition(self):
        registry, ready, task_bound, attempted = self._attempted_fixture()
        committed = registry.transition(
            attempted,
            factory.STATE_MUTATION_ATTEMPTED,
            factory.STATE_MUTATION_COMMITTED,
        )
        self.assertEqual(
            [ready.generation, task_bound.generation, attempted.generation,
             committed.generation],
            [0, 1, 2, 3],
        )

    def test_reusable_never_restored_after_commit(self):
        registry, _ready, _task_bound, attempted = self._attempted_fixture()
        committed = registry.transition(
            attempted,
            factory.STATE_MUTATION_ATTEMPTED,
            factory.STATE_MUTATION_COMMITTED,
        )
        verifying = registry.transition(
            committed,
            factory.STATE_MUTATION_COMMITTED,
            factory.STATE_VERIFYING,
        )
        self.assertFalse(committed.reusable)
        self.assertFalse(verifying.reusable)

    def test_rollback_does_not_restore_attempt_capacity(self):
        registry, _ready, _task_bound, attempted = self._attempted_fixture()
        rolled_back = registry.transition(
            attempted,
            factory.STATE_MUTATION_ATTEMPTED,
            factory.STATE_MUTATION_ROLLED_BACK,
        )
        self.assertEqual(rolled_back.mutation_attempt_count, 1)
        self.assertFalse(rolled_back.reusable)

    def test_unknown_outcome_does_not_restore_attempt_capacity(self):
        registry, _ready, _task_bound, attempted = self._attempted_fixture()
        unknown = registry.transition(
            attempted,
            factory.STATE_MUTATION_ATTEMPTED,
            factory.STATE_MUTATION_OUTCOME_UNKNOWN,
        )
        self.assertEqual(unknown.mutation_attempt_count, 1)
        self.assertFalse(unknown.reusable)

    def test_illegal_direct_lifecycle_jumps_are_rejected(self):
        for target in (
            factory.STATE_MUTATION_COMMITTED,
            factory.STATE_VERIFYING,
            factory.STATE_MUTATION_OUTCOME_UNKNOWN,
        ):
            registry, ready = registered_synthetic_handle(factory.STATE_READY)
            with self.assertRaises(factory.FixtureSecurityError):
                registry.transition(ready, factory.STATE_READY, target)
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        task_bound = registry.transition(
            ready,
            factory.STATE_READY,
            factory.STATE_MUTATION_TASK_BOUND,
        )
        with self.assertRaises(factory.FixtureSecurityError):
            registry.transition(
                task_bound,
                factory.STATE_MUTATION_TASK_BOUND,
                factory.STATE_MUTATION_COMMITTED,
            )
        attempted = registry.transition(
            task_bound,
            factory.STATE_MUTATION_TASK_BOUND,
            factory.STATE_MUTATION_ATTEMPTED,
        )
        for target in (factory.STATE_READY, factory.STATE_MUTATION_TASK_BOUND):
            with self.assertRaises(factory.FixtureSecurityError):
                registry.transition(
                    attempted, factory.STATE_MUTATION_ATTEMPTED, target
                )

    def test_unknown_transition_is_default_denied(self):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        with self.assertRaises(factory.FixtureSecurityError):
            registry.transition(ready, factory.STATE_READY, "UNKNOWN")

    def test_repair_mutator_rejects_stale_generation_before_connection(self):
        registry, _ready, _task_bound, attempted = self._attempted_fixture()
        registry.transition(
            attempted,
            factory.STATE_MUTATION_ATTEMPTED,
            factory.STATE_MUTATION_COMMITTED,
        )
        with mock.patch.object(factory, "_internal_writer_connection") as writer:
            with self.assertRaisesRegex(factory.FixtureSecurityError, "stale"):
                factory.RepairMutator().execute(attempted, registry)
            writer.assert_not_called()

    def test_repair_mutator_uses_canonical_registry_state(self):
        registry, _ready, task_bound, _attempted = self._attempted_fixture()
        forged = replace(
            task_bound,
            lifecycle_state=factory.STATE_MUTATION_ATTEMPTED,
            reusable=False,
            mutation_attempt_count=1,
        )
        with mock.patch.object(factory, "_internal_writer_connection") as writer:
            with self.assertRaises(factory.FixtureSecurityError):
                factory.RepairMutator().execute(forged, registry)
            writer.assert_not_called()

    def test_cloned_token_valid_object_has_no_state_authority(self):
        registry, ready = registered_synthetic_handle(factory.STATE_READY)
        clone = replace(
            ready,
            lifecycle_state=factory.STATE_MUTATION_COMMITTED,
            reusable=False,
            mutation_attempt_count=1,
        )
        with self.assertRaises(factory.FixtureSecurityError):
            registry.require_current(clone)

    def test_fixture_handle_is_not_caller_constructible(self):
        with self.assertRaises(factory.FixtureSecurityError):
            factory.FixtureHandle(
                "id", Path("/root"), Path("/db"),
                factory.FileIdentity(1, 2, 1, 0o700),
                factory.FileIdentity(1, 3, 1, 0o600),
            )

    def test_quarantined_lifecycle_is_terminal(self):
        self.assertEqual(factory._ALLOWED_TRANSITIONS[factory.STATE_QUARANTINED], set())

    def test_expected_index_sql_normalizes(self):
        self.assertTrue(
            verifier.validate_expected_index_sql(
                factory.REPAIR_SQL.rstrip(";")
            )
        )

    def test_rev_01_attached_and_non_main_reindex_rejected(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        for database in ("attached", "temp", None):
            self.assertEqual(
                profile.decide(
                    sqlite3.SQLITE_REINDEX,
                    mutator.FIXED_INDEX,
                    None,
                    database,
                    None,
                ),
                sqlite3.SQLITE_DENY,
            )

    def test_rev_02_reindex_near_misses_denied_and_action_mutation_is_non_reindex(self):
        canonical = mutator._REPAIR_REINDEX_CALLBACK
        reindex_near_misses = (
            (sqlite3.SQLITE_REINDEX, "other", None, "main", None),
            (sqlite3.SQLITE_REINDEX, mutator.FIXED_INDEX, "unexpected", "main", None),
            (sqlite3.SQLITE_REINDEX, mutator.FIXED_INDEX, None, "temp", None),
            (sqlite3.SQLITE_REINDEX, mutator.FIXED_INDEX, None, "main", "trigger"),
        )
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        for callback in reindex_near_misses:
            self.assertNotEqual(callback, canonical)
            self.assertEqual(profile.decide(*callback), sqlite3.SQLITE_DENY)

        # Ordinary policy eligibility is separate from privileged REINDEX admission.
        action_mutation = (
            sqlite3.SQLITE_CREATE_INDEX, mutator.FIXED_INDEX, None, "main", None
        )
        self.assertNotEqual(action_mutation[0], sqlite3.SQLITE_REINDEX)
        self.assertNotEqual(action_mutation, canonical)
        self.assertEqual(profile.decide(*action_mutation), sqlite3.SQLITE_OK)

    def test_rev_03_context_lifecycle_and_callback_sequence_are_exact(self):
        public_recorder = mutator.AuthorizerRecorder(
            mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR],
            connection_identity=id(object()),
        )
        self.assertEqual(
            public_recorder(*mutator._REPAIR_REINDEX_CALLBACK),
            sqlite3.SQLITE_DENY,
        )
        self.assertFalse(hasattr(mutator, "PrivilegedRepairContext"))
        self.assertFalse(hasattr(mutator, "_new_privileged_repair_context"))

    def test_rev_04_fake_class_cannot_cross_canonical_type_boundary(self):
        registry, _handle = registered_synthetic_handle(factory.STATE_READY)

        class FakeHandle:
            @property
            def __class__(self):
                return factory.FixtureHandle

        with self.assertRaisesRegex(
            factory.FixtureSecurityError, "type is not canonical"
        ):
            registry.require_current(FakeHandle())

        self.assertFalse(hasattr(mutator, "_PrivilegedAuthorizerRecorder"))

        class FakeConnection:
            def set_authorizer(self, _callback):
                self.callback = _callback

        with self.assertRaisesRegex(
            mutator.MutationPolicyError, "internal privileged lifecycle"
        ):
            mutator.install_candidate_authorizer(
                FakeConnection(), mutator.PROFILE_REPAIR
            )

    def test_rev_05_concurrent_claim_cannot_consume_same_fixture_privilege(self):
        _registry, observations = self._overlapping_claim_evidence()
        self.assertIn(
            ("contender-denied", "privileged repair lifecycle is already active"),
            observations,
        )
        self.assertNotIn(("contender-admitted", "unexpected"), observations)

    def test_rev_06_privileged_connection_disables_statement_cache(self):
        source = inspect.getsource(factory._internal_writer_connection)
        self.assertIn('"cached_statements": 0', source)
        self.assertIn("profile == PROFILE_REPAIR", source)

    def test_rev_07_expired_prepare_context_cannot_authorize_execution(self):
        source = Path(mutator.__file__).read_text(encoding="utf-8")
        self.assertIn("or self.expired", source)
        self.assertIn("self.active = False", source)

    def test_rev_08_preprivilege_prepare_is_not_retroactively_authorized(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        recorder = mutator.AuthorizerRecorder(profile)
        self.assertEqual(recorder(*mutator._REPAIR_REINDEX_CALLBACK), sqlite3.SQLITE_DENY)
        other_public_recorder = mutator.AuthorizerRecorder(profile)
        self.assertEqual(recorder(*mutator._REPAIR_REINDEX_CALLBACK), sqlite3.SQLITE_DENY)
        self.assertEqual(
            other_public_recorder(*mutator._REPAIR_REINDEX_CALLBACK),
            sqlite3.SQLITE_DENY,
        )

    def test_rev_09_automatic_reprepare_cannot_reuse_consumed_admission(self):
        source = Path(mutator.__file__).read_text(encoding="utf-8")
        self.assertIn("or self.callback_consumed", source)
        self.assertIn("self.callback_consumed = True", source)

    def test_rev_10_only_canonical_main_index_qualifies(self):
        self.assertEqual(
            mutator._REPAIR_REINDEX_CALLBACK,
            (
                sqlite3.SQLITE_REINDEX,
                mutator.FIXED_INDEX,
                None,
                "main",
                None,
            ),
        )
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        for index_name, database in (
            ("other", "main"),
            (mutator.FIXED_INDEX, "temp"),
        ):
            self.assertEqual(
                profile.decide(
                    sqlite3.SQLITE_REINDEX,
                    index_name,
                    None,
                    database,
                    None,
                ),
                sqlite3.SQLITE_DENY,
            )

    def test_rev_11_unqualified_and_collation_reindex_are_rejected(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        for ambiguous_name in (None, "NOCASE"):
            self.assertEqual(
                profile.decide(
                    sqlite3.SQLITE_REINDEX,
                    ambiguous_name,
                    None,
                    "main",
                    None,
                ),
                sqlite3.SQLITE_DENY,
            )

    def test_rev_12_unauthorized_attached_schema_blocks_topology(self):
        connection = mock.Mock()
        connection.execute.return_value = (
            (0, "main", "/fixture.sqlite3"),
            (2, "other", "/other.sqlite3"),
        )
        handle = mock.Mock()
        handle.database = Path("/fixture.sqlite3")
        with self.assertRaisesRegex(
            factory.FixtureSecurityError, "unauthorized attached"
        ):
            factory._verify_connection_topology(connection, handle)
        source = inspect.getsource(factory._internal_writer_connection)
        self.assertLess(
            source.index("_verify_connection_topology"),
            source.index("recorder, repair_context = repair_authorizer_installer"),
        )

    def test_rev_13_privileged_repair_is_exclusive_per_fixture(self):
        registry, observations = self._overlapping_claim_evidence()
        self.assertIn(("owner-active", 1), observations)
        self.assertEqual(registry._active_privileged_repairs, set())

    def test_rev_14_fingerprint_drift_blocks_before_writable_open(self):
        registry, _ready, _bound, attempted = self._attempted_fixture()
        expected = "sha256:" + ("1" * 64)
        observed = "sha256:" + ("2" * 64)
        with mock.patch.object(
            factory,
            "capture_runtime_compatibility_fingerprint",
            return_value=observed,
        ), mock.patch.object(factory.sqlite3, "connect") as connect:
            with self.assertRaisesRegex(
                factory.FixtureSecurityError, "fingerprint drift"
            ):
                with factory._internal_writer_connection(
                    attempted,
                    registry,
                    factory.PROFILE_REPAIR,
                    expected_runtime_fingerprint=expected,
                ):
                    self.fail("fingerprint drift must block before writer open")
        connect.assert_not_called()

    def test_privileged_context_rejects_each_wrong_activation_binding(self):
        source = Path(mutator.__file__).read_text(encoding="utf-8")
        for field in (
            "canonical_sql_digest",
            "connection_identity",
            "fixture_identity",
            "runtime_fingerprint",
            "authorization_phase",
        ):
            self.assertIn(field, source)
        self.assertIn("privileged repair context binding mismatch", source)

    def test_privileged_context_rejects_noncanonical_callback_definition(self):
        self.assertFalse(hasattr(mutator, "PrivilegedRepairContext"))
        self.assertFalse(hasattr(mutator, "_PRIVILEGED_CONTEXT_TOKEN"))
        self.assertFalse(hasattr(mutator, "_new_privileged_repair_context"))
        self.assertFalse(
            hasattr(mutator, "_claim_internal_repair_authorizer_installer")
        )

    def test_caller_context_cannot_enter_public_authorizer_install_path(self):
        connection = mock.Mock()
        with self.assertRaises(TypeError):
            mutator.install_candidate_authorizer(
                connection,
                mutator.PROFILE_REPAIR,
                repair_context=object(),
            )
        connection.set_authorizer.assert_not_called()

    def test_canonical_security_module_universe_is_process_unique(self):
        self.assertIs(
            sys.modules["acos_w3b_b_p1_fixture_factory"], factory
        )
        self.assertIs(
            sys.modules["acos_w3b_b_p1_disposable_mutator"], mutator
        )

    def test_self_declared_cached_module_metadata_does_not_establish_provenance(self):
        module_name = "acos_w3b_b_p1_disposable_mutator"
        path = Path(mutator.__file__).resolve()
        fake = type(mutator)(module_name)
        fake.__file__ = str(path)
        fake.__acos_canonical_source_sha256__ = factory._module_source_digest(path)
        fake.__acos_canonical_loader_provenance__ = (
            factory._CANONICAL_SIBLING_PROVENANCE
        )
        canonical = sys.modules[module_name]
        sys.modules[module_name] = fake
        try:
            with self.assertRaisesRegex(
                factory.FixtureSecurityError, "identity collision"
            ):
                factory.load_canonical_sibling(
                    module_name, "acos-w3b-b-p1-disposable-mutator.py"
                )
        finally:
            sys.modules[module_name] = canonical

    def test_authorizer_teardown_failure_cannot_report_clean_success(self):
        registry, _ready, _bound, attempted = self._attempted_fixture()

        class SuccessfulConnection:
            in_transaction = False

            def execute(self, _statement):
                return self

            def commit(self):
                return None

        recorder = mutator.AuthorizerRecorder(
            mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        )
        recorder.privileged_admission_consumed = True

        @contextmanager
        def fake_writer(*_args, teardown_status, **_kwargs):
            yield SuccessfulConnection(), recorder
            teardown_status["authorizer_removal"] = "OperationalError"

        with mock.patch.object(factory, "_internal_writer_connection", fake_writer):
            repair = factory.RepairMutator()
            repair._expected_runtime_fingerprint = "sha256:" + ("1" * 64)
            outcome = repair.execute(attempted, registry)
        self.assertFalse(outcome.commit_proven)
        self.assertTrue(outcome.outcome_uncertain)
        self.assertEqual(
            outcome.security_lifecycle_failure, "authorizer_removal"
        )

    def test_authorizer_deny_before_admission_does_not_invoke_ds_01(self):
        registry, _ready, _bound, attempted = self._attempted_fixture()

        class DeniedConnection:
            in_transaction = False
            calls = 0

            def execute(self, _statement):
                self.calls += 1
                if self.calls == 2:
                    raise sqlite3.DatabaseError("not authorized")
                return self

            def rollback(self):
                self.in_transaction = False

        recorder = mutator.AuthorizerRecorder(
            mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        )
        recorder.denied_callbacks.append(mutator._REPAIR_REINDEX_CALLBACK)
        recorder.privileged_admission_consumed = False

        @contextmanager
        def fake_writer(*_args, **_kwargs):
            yield DeniedConnection(), recorder

        with mock.patch.object(factory, "_internal_writer_connection", fake_writer):
            repair = factory.RepairMutator()
            repair._expected_runtime_fingerprint = "sha256:" + ("1" * 64)
            outcome = repair.execute(attempted, registry)
        self.assertTrue(outcome.authorization_denied)
        self.assertFalse(outcome.mutation_attempted)
        self.assertFalse(outcome.outcome_uncertain)

    def test_begin_authorizer_deny_before_admission_does_not_invoke_ds_01(self):
        registry, _ready, _bound, attempted = self._attempted_fixture()

        class BeginDeniedConnection:
            in_transaction = False

            def execute(self, _statement):
                raise sqlite3.DatabaseError("not authorized")

        recorder = mutator.AuthorizerRecorder(
            mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        )
        recorder.denied_callbacks.append(
            (sqlite3.SQLITE_TRANSACTION, "BEGIN", None, None, None)
        )
        recorder.privileged_admission_consumed = False

        @contextmanager
        def fake_writer(*_args, **_kwargs):
            yield BeginDeniedConnection(), recorder

        with mock.patch.object(factory, "_internal_writer_connection", fake_writer):
            repair = factory.RepairMutator()
            repair._expected_runtime_fingerprint = "sha256:" + ("1" * 64)
            outcome = repair.execute(attempted, registry)
        self.assertTrue(outcome.authorization_denied)
        self.assertFalse(outcome.mutation_attempted)
        self.assertFalse(outcome.outcome_uncertain)

    def test_repair_execution_uses_canonical_sql_not_instance_state(self):
        repair = factory.RepairMutator()
        self.assertFalse(hasattr(repair, "statement"))
        source = inspect.getsource(factory.RepairMutator.execute)
        self.assertIn(
            "repair_statement = _verify_canonical_repair_operation_digest()",
            source,
        )
        self.assertIn("connection.execute(repair_statement)", source)
        self.assertNotIn("connection.execute(self.statement)", source)


    def test_other_index_sql_is_rejected(self):
        self.assertFalse(
            verifier.validate_expected_index_sql(
                "CREATE INDEX other ON audit_events(sequence)"
            )
        )

    def test_runner_has_no_command_line_entrypoint(self):
        source = (
            REPOSITORY_ROOT / "scripts/acos-w3b-b-p1-single-index-repair.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('__name__ == "__main__"', source)

    def test_gate_observation_absent_blocks(self):
        observation = runner.observe_mutation_test_gate(RESEARCH_EXAMPLE)
        with self.assertRaises(runner.OrchestrationBlocked):
            observation.require(RESEARCH_EXAMPLE)

    def test_gate_object_is_not_caller_constructible(self):
        with self.assertRaises(TypeError):
            runner.MutationTestGateObservation(
                object(),
                "ACOS-MIG-W3B-B-P1-MUTATION-TEST",
                RESEARCH_EXAMPLE["binding_digest"],
                True,
            )

    def test_mutation_capabilities_accept_no_connection(self):
        for method in (
            factory.SeedInitializer.initialize,
            factory.FaultInjector.inject,
            factory.RepairMutator.execute,
        ):
            self.assertNotIn("connection", inspect.signature(method).parameters)

    def test_arbitrary_or_cross_profile_connection_argument_is_rejected(self):
        for method in (
            factory.FaultInjector.inject,
            factory.RepairMutator.execute,
        ):
            with self.assertRaises(TypeError):
                inspect.signature(method).bind(
                    object(), object(), object(), object()
                )

    def test_writer_profiles_are_hard_bound(self):
        self.assertEqual(factory.SeedInitializer.profile, mutator.PROFILE_SEED)
        self.assertEqual(factory.FaultInjector.profile, mutator.PROFILE_FAULT)
        self.assertEqual(factory.RepairMutator.profile, mutator.PROFILE_REPAIR)

    def test_positive_binding_passes_static_validation(self):
        runner.validate_research_binding(
            deepcopy(RESEARCH_EXAMPLE),
            now=datetime(2026, 8, 30, tzinfo=timezone.utc),
        )

    def test_binding_authority_upgrade_is_rejected(self):
        invalid = dict(RESEARCH_EXAMPLE, eligible_for_execution=True)
        with self.assertRaises(runner.OrchestrationBlocked):
            runner.validate_research_binding(invalid)

    def test_unknown_binding_capability_field_is_rejected(self):
        invalid = deepcopy(RESEARCH_EXAMPLE)
        invalid["real_store_path"] = "/forbidden"
        resign_binding(invalid)
        with self.assertRaisesRegex(
            runner.OrchestrationBlocked, "field set is not closed"
        ):
            runner.validate_research_binding(
                invalid, now=datetime(2026, 8, 30, tzinfo=timezone.utc)
            )

    def test_recomputed_plan_digest_mismatch_is_rejected(self):
        invalid = deepcopy(RESEARCH_EXAMPLE)
        invalid["repair_plan"]["created_at"] = "2026-08-25T10:00:01Z"
        resign_binding(invalid)
        with self.assertRaisesRegex(
            runner.OrchestrationBlocked, "recomputed digest mismatch: plan_digest"
        ):
            runner.validate_research_binding(
                invalid, now=datetime(2026, 8, 30, tzinfo=timezone.utc)
            )

    def test_recomputed_evidence_set_digest_mismatch_is_rejected(self):
        invalid = deepcopy(RESEARCH_EXAMPLE)
        invalid["repair_evidence"]["findings"][0]["summary"] = "changed"
        resign_binding(invalid)
        with self.assertRaisesRegex(
            runner.OrchestrationBlocked,
            "recomputed digest mismatch: evidence_set_digest",
        ):
            runner.validate_research_binding(
                invalid, now=datetime(2026, 8, 30, tzinfo=timezone.utc)
            )

    def test_cross_object_snapshot_mismatch_is_rejected(self):
        invalid = deepcopy(RESEARCH_EXAMPLE)
        invalid["repair_plan"]["snapshot_digest"] = "sha256:" + ("ab" * 32)
        invalid["repair_plan"]["plan_digest"] = (
            mutator.digest_without(invalid["repair_plan"], "plan_digest")
        )
        invalid["plan_digest"] = invalid["repair_plan"]["plan_digest"]
        invalid["plan_verification"]["plan_digest"] = invalid["plan_digest"]
        resign_binding(invalid)
        with self.assertRaisesRegex(
            runner.OrchestrationBlocked, "snapshot binding mismatch"
        ):
            runner.validate_research_binding(
                invalid, now=datetime(2026, 8, 30, tzinfo=timezone.utc)
            )

    def test_expired_binding_is_rejected(self):
        with self.assertRaisesRegex(
            runner.OrchestrationBlocked, "not currently valid"
        ):
            runner.validate_research_binding(
                deepcopy(RESEARCH_EXAMPLE),
                now=datetime(2027, 1, 1, tzinfo=timezone.utc),
            )

    def test_reversed_binding_lifetime_is_rejected(self):
        invalid = deepcopy(RESEARCH_EXAMPLE)
        invalid["issued_at"], invalid["expires_at"] = (
            invalid["expires_at"],
            invalid["issued_at"],
        )
        resign_binding(invalid)
        with self.assertRaisesRegex(
            runner.OrchestrationBlocked, "empty or reversed"
        ):
            runner.validate_research_binding(
                invalid, now=datetime(2026, 8, 30, tzinfo=timezone.utc)
            )


@unittest.skipUnless(
    MUTATION_TESTS_AUTHORIZED,
    "separate disposable-fixture mutation-test authorization required",
)
class MutationAuthorizedTests(unittest.TestCase):
    """Category B: implemented, but not executable under IMPLEMENTATION-02."""

    def setUp(self):
        self.registry = factory.FixtureRegistry()
        self.fixture_factory = factory.DisposableFixtureFactory(self.registry)

    def _create(self):
        return self.fixture_factory.create("future-authorized-fixture")

    def _dispose_if_safe(self, handle):
        if handle.root.exists() and handle.database.exists():
            try:
                current = self.registry.get(handle.fixture_instance_id)
                if current.lifecycle_state in {
                    factory.STATE_READY,
                    factory.STATE_MUTATION_TASK_BOUND,
                    factory.STATE_MUTATION_COMMITTED,
                    factory.STATE_VERIFYING,
                }:
                    self.fixture_factory.dispose(current)
            except Exception:
                pass

    def _seeded(self):
        handle = self._create()
        outcome = factory.SeedInitializer(REPOSITORY_ROOT).initialize(
            handle, self.registry
        )
        factory.verify_identity_checkpoint("C", handle, self.registry)
        return handle, outcome

    def _faulted(self):
        handle, seed_outcome = self._seeded()
        fault_outcome = factory.FaultInjector().inject(handle, self.registry)
        self.assertTrue(fault_outcome.commit_proven)
        factory.verify_identity_checkpoint("C", handle, self.registry)
        return handle, seed_outcome, fault_outcome

    def _repaired(self):
        handle, seed_outcome, fault_outcome = self._faulted()
        bound = self.registry.transition(
            handle,
            factory.STATE_READY,
            factory.STATE_MUTATION_TASK_BOUND,
        )
        attempted = self.registry.transition(
            bound,
            factory.STATE_MUTATION_TASK_BOUND,
            factory.STATE_MUTATION_ATTEMPTED,
        )
        repair = factory.RepairMutator()
        repair.prime_runtime_compatibility()
        repair_outcome = repair.execute(attempted, self.registry)
        classification = mutator.classify_mutation_effect(
            mutation_attempted=repair_outcome.mutation_attempted,
            rollback_proven=repair_outcome.rollback_proven,
            commit_proven=repair_outcome.commit_proven,
        )
        committed = self.registry.transition(
            attempted,
            factory.STATE_MUTATION_ATTEMPTED,
            factory.STATE_MUTATION_COMMITTED,
        )
        factory.verify_identity_checkpoint("C", committed, self.registry)
        return (
            committed,
            classification,
            seed_outcome,
            fault_outcome,
            repair_outcome,
        )

    def test_fixture_factory_creates_secure_root(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        self.assertEqual(handle.root_identity.mode, 0o700)

    def test_fixture_factory_creates_secure_leaf(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        self.assertEqual(handle.database_identity.mode, 0o600)

    def test_seed_initializer_applies_canonical_seed(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        initializer = factory.SeedInitializer(REPOSITORY_ROOT)
        initializer.initialize(handle, self.registry)
        evidence = verifier.PoststateVerifier().verify(handle.database)
        self.assertTrue(evidence.index_present)

    def test_seed_connection_uses_seed_profile(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        outcome = factory.SeedInitializer(REPOSITORY_ROOT).initialize(
            handle, self.registry
        )
        self.assertEqual(outcome.profile, mutator.PROFILE_SEED)

    def test_fault_injector_drops_only_fixed_index(self):
        handle, _seed, outcome = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        actions = [callback[0] for callback in outcome.callbacks]
        self.assertIn(sqlite3.SQLITE_DROP_INDEX, actions)
        self.assertNotIn(sqlite3.SQLITE_DROP_TABLE, actions)

    def test_fault_prestate_has_missing_fixed_index(self):
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        self.assertFalse(verifier.PoststateVerifier().verify(handle.database).index_present)

    def test_repair_mutator_recreates_fixed_index(self):
        handle, classification, *_rest = self._repaired()
        self.addCleanup(self._dispose_if_safe, handle)
        self.assertEqual(
            classification.transaction_outcome, mutator.OUTCOME_COMMITTED
        )

    def test_poststate_verifier_accepts_repair(self):
        handle, _classification, *_rest = self._repaired()
        self.addCleanup(self._dispose_if_safe, handle)
        evidence = verifier.PoststateVerifier().verify(handle.database)
        self.assertTrue(evidence.expected)

    def test_stale_fixture_snapshot_blocks_before_repair(self):
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        with self.assertRaisesRegex(
            runner.OrchestrationBlocked, "current fixture digest"
        ):
            runner.validate_current_fixture_binding(
                RESEARCH_EXAMPLE, handle, self.registry
            )

    def test_end_to_end_stale_binding_fails_closed(self):
        environment = {
            "ACOS_W3B_B_P1_MUTATION_TEST_TASK_ID":
                "ACOS-MIG-W3B-B-P1-MUTATION-TEST",
            "ACOS_W3B_B_P1_MUTATION_TEST_BINDING_DIGEST":
                RESEARCH_EXAMPLE["binding_digest"],
        }
        with mock.patch.dict(os.environ, environment, clear=False):
            with self.assertRaises(runner.OrchestrationBlocked):
                runner.DisposableSingleIndexRepairRunner(
                    REPOSITORY_ROOT
                ).run(deepcopy(RESEARCH_EXAMPLE))

    def test_verified_disposal_removes_fixture(self):
        handle = self._create()
        disposed = self.fixture_factory.dispose(handle)
        self.assertEqual(disposed.lifecycle_state, factory.STATE_DISPOSED)
        self.assertFalse(handle.root.exists())

    def test_path_substitution_at_checkpoint_blocks(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        substituted = replace(handle, database=handle.root / "other.sqlite3")
        with self.assertRaises(factory.FixtureSecurityError):
            factory.verify_identity_checkpoint("B1", substituted, self.registry)

    def test_sidecar_at_checkpoint_blocks(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        sidecar = Path(f"{handle.database}-wal")
        sidecar.touch()
        self.addCleanup(sidecar.unlink, missing_ok=True)
        with self.assertRaises(factory.FixtureSecurityError):
            factory.verify_identity_checkpoint("B1", handle, self.registry)

    def test_hardlink_at_checkpoint_blocks(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        alias = handle.root / "alias.sqlite3"
        os.link(handle.database, alias)
        self.addCleanup(alias.unlink, missing_ok=True)
        with self.assertRaises(factory.FixtureSecurityError):
            factory.verify_identity_checkpoint("B1", handle, self.registry)

    def test_binding_fixture_identity_mismatch_blocks(self):
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        invalid = deepcopy(RESEARCH_EXAMPLE)
        invalid["fixture_instance_id"] = "other"
        with self.assertRaisesRegex(
            runner.OrchestrationBlocked, "fixture_instance_id"
        ):
            runner.validate_current_fixture_binding(
                invalid, handle, self.registry
            )

    def test_commit_ioerr_sets_outcome_unknown_and_terminal(self):
        class CommitFailure:
            in_transaction = True
            def execute(self, _statement):
                return self
            def commit(self):
                raise sqlite3.OperationalError("simulated commit I/O failure")
            def rollback(self):
                self.in_transaction = False
        recorder = mutator.AuthorizerRecorder(
            mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        )
        recorder.privileged_admission_consumed = True
        @contextmanager
        def fake_writer(*_args, **_kwargs):
            yield CommitFailure(), recorder
        registry = factory.FixtureRegistry()
        handle = synthetic_handle(
            factory.STATE_MUTATION_ATTEMPTED,
            registry=registry,
            fixture_instance_id="synthetic",
            reusable=False,
            mutation_attempt_count=1,
        )
        registry._register(handle)
        with mock.patch.object(
            factory, "_internal_writer_connection", fake_writer
        ):
            repair = factory.RepairMutator()
            repair.prime_runtime_compatibility()
            outcome = repair.execute(handle, registry)
        value = mutator.classify_mutation_effect(
            mutation_attempted=outcome.mutation_attempted,
            rollback_proven=outcome.rollback_proven,
            commit_proven=outcome.commit_proven,
        )
        self.assertTrue(outcome.outcome_uncertain)
        self.assertEqual(
            (value.mutation_effect, value.terminal_state),
            (mutator.EFFECT_UNKNOWN, mutator.STATE_UNKNOWN),
        )

    def test_fault_injection_commit_uncertainty_is_terminal(self):
        class CommitFailure:
            in_transaction = True
            def execute(self, _statement):
                return self
            def commit(self):
                raise sqlite3.OperationalError("simulated fault commit failure")
            def rollback(self):
                self.in_transaction = False
        recorder = mutator.AuthorizerRecorder(
            mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        )
        @contextmanager
        def fake_writer(*_args):
            yield CommitFailure(), recorder
        registry = factory.FixtureRegistry()
        handle = synthetic_handle(
            factory.STATE_READY,
            registry=registry,
            fixture_instance_id="synthetic-fault",
        )
        registry._register(handle)
        with mock.patch.object(
            factory, "_internal_writer_connection", fake_writer
        ):
            outcome = factory.FaultInjector().inject(handle, registry)
        self.assertTrue(outcome.outcome_uncertain)
        self.assertFalse(outcome.commit_proven)
        self.assertFalse(outcome.rollback_proven)

    def test_commit_busy_maintains_active_transaction(self):
        self.assertEqual(
            mutator.classify_commit_exception(connection_in_transaction=True),
            "ACTIVE_TRANSACTION",
        )

    def test_failed_rollback_never_asserts_rolled_back(self):
        class RollbackFailure:
            in_transaction = True
            calls = 0
            def execute(self, _statement):
                self.calls += 1
                if self.calls == 2:
                    raise sqlite3.OperationalError("simulated statement failure")
                return self
            def rollback(self):
                raise sqlite3.OperationalError("simulated rollback failure")
        recorder = mutator.AuthorizerRecorder(
            mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        )
        recorder.privileged_admission_consumed = True
        @contextmanager
        def fake_writer(*_args, **_kwargs):
            yield RollbackFailure(), recorder
        registry = factory.FixtureRegistry()
        handle = synthetic_handle(
            factory.STATE_MUTATION_ATTEMPTED,
            registry=registry,
            fixture_instance_id="synthetic",
            reusable=False,
            mutation_attempt_count=1,
        )
        registry._register(handle)
        with mock.patch.object(
            factory, "_internal_writer_connection", fake_writer
        ):
            repair = factory.RepairMutator()
            repair.prime_runtime_compatibility()
            outcome = repair.execute(handle, registry)
        self.assertFalse(outcome.rollback_proven)
        self.assertTrue(outcome.outcome_uncertain)

    def test_unknown_outcome_fixture_quarantined_without_reuse(self):
        handle = self._create()
        quarantined = self.fixture_factory.quarantine(handle)
        self.assertFalse(quarantined.reusable)
        self.assertEqual(quarantined.lifecycle_state, factory.STATE_QUARANTINED)

    def test_unknown_commit_never_pass(self):
        value = mutator.classify_mutation_effect(
            mutation_attempted=True, rollback_proven=False, commit_proven=False
        )
        self.assertEqual(value.terminal_state, mutator.STATE_UNKNOWN)
        self.assertNotEqual(value.mutation_effect, mutator.RESULT_PASS)

    def test_fault_injector_generic_drop_table_denied(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(sqlite3.SQLITE_DROP_TABLE, "x", None, "main", None),
            sqlite3.SQLITE_DENY,
        )

    def test_fault_injector_other_index_drop_denied(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(sqlite3.SQLITE_DROP_INDEX, "x", "audit_events", "main", None),
            sqlite3.SQLITE_DENY,
        )

    def test_fault_injector_dml_forbidden(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(sqlite3.SQLITE_DELETE, "audit_events", None, "main", None),
            sqlite3.SQLITE_DENY,
        )

    def test_fault_injector_pragma_denied(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertEqual(
            profile.decide(sqlite3.SQLITE_PRAGMA, "journal_mode", None, "main", None),
            sqlite3.SQLITE_DENY,
        )

    def test_repair_authorizer_callback_sequence_characterized(self):
        handle, _classification, _seed, _fault, outcome = self._repaired()
        self.addCleanup(self._dispose_if_safe, handle)
        actions = [callback[0] for callback in outcome.callbacks]
        self.assertIn(sqlite3.SQLITE_CREATE_INDEX, actions)
        repair_reindex = [
            callback
            for callback in outcome.callbacks
            if callback[0] == sqlite3.SQLITE_REINDEX
        ]
        self.assertEqual(repair_reindex, [mutator._REPAIR_REINDEX_CALLBACK])
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertTrue(
            all(
                callback[0] == sqlite3.SQLITE_REINDEX
                or profile.decide(*callback) == sqlite3.SQLITE_OK
                for callback in outcome.callbacks
            )
        )

    def test_rev_15_canonical_privileged_repair_positive_closure(self):
        committed, classification, _seed, _fault, outcome = self._repaired()
        verifying = self.registry.transition(
            committed,
            factory.STATE_MUTATION_COMMITTED,
            factory.STATE_VERIFYING,
        )
        self.addCleanup(self._dispose_if_safe, verifying)
        self.assertTrue(outcome.commit_proven)
        self.assertEqual(
            classification.transaction_outcome, mutator.OUTCOME_COMMITTED
        )
        self.assertEqual(
            [
                callback
                for callback in outcome.callbacks
                if callback[0] == sqlite3.SQLITE_REINDEX
            ],
            [mutator._REPAIR_REINDEX_CALLBACK],
        )
        self.assertTrue(verifier.PoststateVerifier().verify(verifying.database).expected)

    @contextmanager
    def _pending_privileged_explain(self, handle):
        """Keep an EXPLAIN cursor unfinished across the real writer lifetime."""
        repair = factory.RepairMutator()
        runtime_fingerprint = repair.prime_runtime_compatibility()
        with factory._internal_writer_connection(
            handle,
            self.registry,
            factory.PROFILE_REPAIR,
            expected_runtime_fingerprint=runtime_fingerprint,
        ) as (connection, recorder):
            cursor = connection.cursor()
            cursor.execute("EXPLAIN " + factory.REPAIR_SQL)
            first_opcode = cursor.fetchone()
            self.assertIsNotNone(first_opcode)
            self.assertEqual(first_opcode[0], 0)
            self.assertTrue(recorder.privileged_admission_consumed)
            self.assertFalse(recorder.privileged_context_expired)
            yield connection, cursor, recorder

    def _before_first_step_parameters(self, action):
        """CPython binds this empty sequence after prepare, before sqlite3_step."""
        self.assertEqual(sys.implementation.name, "cpython")

        class BeforeFirstStep:
            calls = 0

            def __len__(self):
                self.calls += 1
                if self.calls != 1:
                    raise AssertionError("prepare/step boundary invoked twice")
                action()
                return 0

            def __getitem__(self, _index):
                raise IndexError("the canonical EXPLAIN has no SQL parameters")

        return BeforeFirstStep()

    def test_rev_06_prepared_statement_cannot_cross_privileged_lifecycle(self):
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        with self._pending_privileged_explain(handle) as (connection, cursor, recorder):
            self.assertIs(cursor.connection, connection)
            callbacks = tuple(recorder.callbacks)
        with self.assertRaises(sqlite3.ProgrammingError):
            cursor.fetchone()
        self.assertEqual(tuple(recorder.callbacks), callbacks)
        self.assertTrue(recorder.privileged_context_expired)
        later = sqlite3.connect(handle.database, cached_statements=0)
        try:
            self.assertIsNot(later, connection)
            public = mutator.AuthorizerRecorder(
                mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR],
                connection_identity=id(later),
            )
            later.set_authorizer(public)
            with self.assertRaises(sqlite3.DatabaseError) as caught:
                later.execute("EXPLAIN " + factory.REPAIR_SQL)
            self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_AUTH)
            self.assertIn(mutator._REPAIR_REINDEX_CALLBACK, public.denied_callbacks)
        finally:
            later.close()

    def test_rev_05_and_rev_13_overlapping_physical_repair_is_exclusive(self):
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        repair = factory.RepairMutator()
        runtime_fingerprint = repair.prime_runtime_compatibility()
        owner_active = threading.Event()
        release_owner = threading.Event()
        observations = []

        def owner():
            with factory._internal_writer_connection(
                handle,
                self.registry,
                factory.PROFILE_REPAIR,
                expected_runtime_fingerprint=runtime_fingerprint,
            ) as (connection, _recorder):
                observations.append(("owner-connection", id(connection)))
                owner_active.set()
                release_owner.wait(timeout=2)

        def contender():
            owner_active.wait(timeout=2)
            try:
                with factory._internal_writer_connection(
                    handle,
                    self.registry,
                    factory.PROFILE_REPAIR,
                    expected_runtime_fingerprint=runtime_fingerprint,
                ):
                    observations.append(("contender", "admitted"))
            except factory.FixtureSecurityError as exc:
                observations.append(("contender", str(exc)))
            finally:
                release_owner.set()

        owner_thread = threading.Thread(target=owner)
        contender_thread = threading.Thread(target=contender)
        owner_thread.start()
        contender_thread.start()
        owner_thread.join(timeout=2)
        contender_thread.join(timeout=2)
        self.assertFalse(owner_thread.is_alive())
        self.assertFalse(contender_thread.is_alive())
        self.assertIn(
            ("contender", "privileged repair lifecycle is already active"),
            observations,
        )
        self.assertNotIn(("contender", "admitted"), observations)

    def test_rev_07_prepared_under_privilege_cannot_execute_after_expiry(self):
        # Public sqlite3 exposes no detached prepared handle. Observe unfinished
        # EXPLAIN continuation plus closed connection, not open-handle revocation.
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        with self._pending_privileged_explain(handle) as (connection, cursor, recorder):
            second_opcode = cursor.fetchone()
            self.assertIsNotNone(second_opcode)
            self.assertEqual(second_opcode[0], 1)
            callbacks = tuple(recorder.callbacks)
        self.assertTrue(recorder.privileged_context_expired)
        with self.assertRaises(sqlite3.ProgrammingError):
            cursor.fetchone()
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("BEGIN")
        self.assertEqual(tuple(recorder.callbacks), callbacks)

    def test_rev_08_preprivilege_statement_does_not_inherit_privilege(self):
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        preprivilege = sqlite3.connect(handle.database, cached_statements=0)
        self.addCleanup(preprivilege.close)
        public_recorder = mutator.AuthorizerRecorder(
            mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR],
            connection_identity=id(preprivilege),
        )
        initial_callbacks = []

        def observe_explain_compile(*callback):
            # Test-only observation of fixed EXPLAIN, never a DDL execution.
            initial_callbacks.append(callback)
            if callback == mutator._REPAIR_REINDEX_CALLBACK:
                return sqlite3.SQLITE_OK
            return public_recorder.profile.decide(*callback)

        preprivilege.set_authorizer(observe_explain_compile)
        repair = factory.RepairMutator()
        runtime_fingerprint = repair.prime_runtime_compatibility()
        events = []
        with ExitStack() as lifecycle:
            privileged_recorders = []

            def after_preprivilege_prepare():
                self.assertEqual(
                    initial_callbacks.count(mutator._REPAIR_REINDEX_CALLBACK), 1
                )
                self.assertEqual(public_recorder.callbacks, [])
                events.append("PREPRIVILEGE_EXPLAIN_PREPARED")
                privileged, recorder = lifecycle.enter_context(
                    factory._internal_writer_connection(
                        handle, self.registry, factory.PROFILE_REPAIR,
                        expected_runtime_fingerprint=runtime_fingerprint,
                    )
                )
                self.assertIsNot(preprivilege, privileged)
                self.assertFalse(recorder.privileged_admission_consumed)
                privileged_recorders.append(recorder)
                events.append("SEPARATE_PRIVILEGED_LIFECYCLE_ACTIVE")
                # Expire the already-prepared EXPLAIN on its own connection.
                preprivilege.set_authorizer(public_recorder)
                events.append("PREPRIVILEGE_STATEMENT_EXPIRED")

            parameters = self._before_first_step_parameters(after_preprivilege_prepare)
            cursor = preprivilege.cursor()
            # Exactly one execute: compilation precedes the parameter hook;
            # its first step must reprepare under the public deny policy.
            with self.assertRaises(sqlite3.DatabaseError) as caught:
                cursor.execute("EXPLAIN " + factory.REPAIR_SQL, parameters)
            self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_AUTH)
            self.assertEqual(parameters.calls, 1)
            self.assertEqual(events, [
                "PREPRIVILEGE_EXPLAIN_PREPARED",
                "SEPARATE_PRIVILEGED_LIFECYCLE_ACTIVE",
                "PREPRIVILEGE_STATEMENT_EXPIRED",
            ])
            self.assertEqual(len(privileged_recorders), 1)
            recorder = privileged_recorders[0]
            self.assertEqual(recorder.callbacks, [])
            self.assertFalse(recorder.privileged_admission_consumed)
            preprivilege.execute("BEGIN")
            preprivilege.rollback()
        self.assertEqual(initial_callbacks.count(mutator._REPAIR_REINDEX_CALLBACK), 1)
        self.assertIn(mutator._REPAIR_REINDEX_CALLBACK, public_recorder.denied_callbacks)

    def test_rev_09_runtime_reprepare_requires_fresh_one_shot_admission(self):
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        repair = factory.RepairMutator()
        runtime_fingerprint = repair.prime_runtime_compatibility()
        with factory._internal_writer_connection(
            handle, self.registry, factory.PROFILE_REPAIR,
            expected_runtime_fingerprint=runtime_fingerprint,
        ) as (connection, recorder):
            events = []

            def expire_after_prepare():
                self.assertEqual(
                    recorder.callbacks.count(mutator._REPAIR_REINDEX_CALLBACK), 1
                )
                self.assertTrue(recorder.privileged_admission_consumed)
                self.assertFalse(recorder.privileged_context_expired)
                self.assertEqual(recorder.denied_callbacks, [])
                events.append("INITIAL_PREPARE_ADMITTED")
                # SQLite expires prepared statements even when reinstalling
                # the same authorizer; first step must now automatically reprepare.
                connection.set_authorizer(recorder)
                events.append("AUTHORIZER_ENVIRONMENT_INVALIDATED_STATEMENT")

            parameters = self._before_first_step_parameters(expire_after_prepare)
            cursor = connection.cursor()
            with self.assertRaises(sqlite3.DatabaseError) as caught:
                cursor.execute("EXPLAIN " + factory.REPAIR_SQL, parameters)
            self.assertEqual(caught.exception.sqlite_errorcode, sqlite3.SQLITE_AUTH)
            self.assertEqual(parameters.calls, 1)
            self.assertEqual(events, [
                "INITIAL_PREPARE_ADMITTED",
                "AUTHORIZER_ENVIRONMENT_INVALIDATED_STATEMENT",
            ])
            repair_reindex = [
                callback
                for callback in recorder.callbacks
                if callback[0] == sqlite3.SQLITE_REINDEX
            ]
            self.assertEqual(repair_reindex, [mutator._REPAIR_REINDEX_CALLBACK] * 2)
            self.assertEqual(recorder.denied_callbacks, [mutator._REPAIR_REINDEX_CALLBACK])
            self.assertTrue(recorder.privileged_admission_consumed)
            self.assertFalse(recorder.privileged_context_expired)
            connection.execute("BEGIN")
            connection.rollback()

    def test_rev_12_runtime_attach_blocks_before_privileged_preparation(self):
        handle, _seed, _fault = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        repair = factory.RepairMutator()
        runtime_fingerprint = repair.prime_runtime_compatibility()
        connection = sqlite3.connect(handle.database, cached_statements=0)
        connection.execute("ATTACH DATABASE ':memory:' AS other")

        class ConnectionProxy:
            def __init__(self, delegate):
                self.delegate = delegate
                self.authorizer_installations = []

            def execute(self, statement):
                return self.delegate.execute(statement)

            def set_authorizer(self, callback):
                self.authorizer_installations.append(callback)
                return self.delegate.set_authorizer(callback)

            def close(self):
                return self.delegate.close()

        proxy = ConnectionProxy(connection)
        with mock.patch.object(
            factory, "capture_runtime_compatibility_fingerprint",
            return_value=runtime_fingerprint,
        ), mock.patch.object(
            factory.sqlite3, "connect", return_value=proxy
        ):
            with self.assertRaisesRegex(
                factory.FixtureSecurityError, "unauthorized attached"
            ):
                with factory._internal_writer_connection(
                    handle,
                    self.registry,
                    factory.PROFILE_REPAIR,
                    expected_runtime_fingerprint=runtime_fingerprint,
                ):
                    self.fail("attached topology must block privileged preparation")
        self.assertEqual(proxy.authorizer_installations, [None])

    def test_fault_authorizer_callback_sequence_characterized(self):
        handle, _seed, outcome = self._faulted()
        self.addCleanup(self._dispose_if_safe, handle)
        actions = [callback[0] for callback in outcome.callbacks]
        self.assertIn(sqlite3.SQLITE_DROP_INDEX, actions)
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_FAULT]
        self.assertTrue(
            all(profile.decide(*callback) == sqlite3.SQLITE_OK
                for callback in outcome.callbacks)
        )

    def test_unexpected_authorizer_action_code_fails_closed(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertEqual(
            profile.decide(2**31, None, None, None, None),
            sqlite3.SQLITE_DENY,
        )

    def test_mutation_phase_pragma_unconditionally_denied(self):
        for name in (mutator.PROFILE_FAULT, mutator.PROFILE_REPAIR):
            profile = mutator.CANDIDATE_PROFILES[name]
            self.assertEqual(
                profile.decide(sqlite3.SQLITE_PRAGMA, "x", None, "main", None),
                sqlite3.SQLITE_DENY,
            )

    def test_journal_mode_change_during_mutation_denied(self):
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_REPAIR]
        self.assertEqual(
            profile.decide(
                sqlite3.SQLITE_PRAGMA, "journal_mode", "wal", "main", None
            ),
            sqlite3.SQLITE_DENY,
        )

    def test_inode_change_before_writer_open_blocks_execution(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        handle.database.unlink()
        handle.database.touch(mode=0o600)
        with self.assertRaises(factory.FixtureSecurityError):
            factory.verify_identity_checkpoint("B1", handle, self.registry)

    def test_inode_change_post_prestate_before_begin_blocks(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        original = handle.database
        replacement = handle.root / "replacement.sqlite3"
        replacement.touch(mode=0o600)
        original.unlink()
        replacement.rename(original)
        with self.assertRaises(factory.FixtureSecurityError):
            factory.verify_identity_checkpoint("B2", handle, self.registry)

    def test_b2_occurs_after_open_and_before_seed_execution(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        events = []
        real_connect = factory.sqlite3.connect
        real_verify = factory.verify_identity_checkpoint
        def recording_connect(*args, **kwargs):
            events.append("OPEN")
            return real_connect(*args, **kwargs)
        def recording_verify(checkpoint, *args, **kwargs):
            events.append(checkpoint)
            return real_verify(checkpoint, *args, **kwargs)
        with mock.patch.object(
            factory.sqlite3, "connect", side_effect=recording_connect
        ), mock.patch.object(
            factory, "verify_identity_checkpoint", side_effect=recording_verify
        ):
            factory.SeedInitializer(REPOSITORY_ROOT).initialize(
                handle, self.registry
            )
        self.assertLess(events.index("B1"), events.index("OPEN"))
        self.assertLess(events.index("OPEN"), events.index("B2"))

    def test_hardlink_count_increase_blocks_operation(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        alias = handle.root / "hardlink.sqlite3"
        os.link(handle.database, alias)
        self.addCleanup(alias.unlink, missing_ok=True)
        with self.assertRaises(factory.FixtureSecurityError):
            factory.verify_identity_checkpoint("C", handle, self.registry)

    def test_failed_disposal_preserves_prior_mutation_effect_record(self):
        result = mutator.RepairResult(
            operation_id="op", result=mutator.RESULT_FAILED_DISPOSAL,
            reason_code="DISPOSAL_FAILED", reason="preserved",
            state=factory.STATE_VERIFYING, fixture_instance_id="fixture",
            binding_id="binding", plan_id="plan", prestate_digest=None,
            poststate_digest=None, mutation_attempt_count=1,
            transaction_outcome=mutator.OUTCOME_COMMITTED,
            mutation_effect=mutator.EFFECT_COMMITTED,
            poststate_status="EXPECTED", disposal_state="FAILED",
            started_at="2026-08-29T00:00:00Z",
            completed_at="2026-08-29T00:00:01Z",
        )
        self.assertEqual(result.mutation_effect, mutator.EFFECT_COMMITTED)
        self.assertEqual(result.disposal_state, "FAILED")

    def test_seed_authorizer_callback_sequence_characterized(self):
        handle, outcome = self._seeded()
        self.addCleanup(self._dispose_if_safe, handle)
        actions = [callback[0] for callback in outcome.callbacks]
        self.assertIn(sqlite3.SQLITE_CREATE_TABLE, actions)
        self.assertIn(sqlite3.SQLITE_REINDEX, actions)
        reindex_callbacks = [
            callback
            for callback in outcome.callbacks
            if callback[0] == sqlite3.SQLITE_REINDEX
        ]
        self.assertTrue(reindex_callbacks)
        self.assertTrue(
            all(
                callback[1] in mutator.CANONICAL_SEED_INDEX_NAMES
                and callback[2] is None
                and callback[3] == "main"
                and callback[4] is None
                for callback in reindex_callbacks
            )
        )
        profile = mutator.CANDIDATE_PROFILES[mutator.PROFILE_SEED]
        self.assertTrue(
            all(profile.decide(*callback) == sqlite3.SQLITE_OK
                for callback in outcome.callbacks)
        )

    def test_runtime_seed_failure_disposes_fresh_fixture(self):
        handle = self._create()
        policy = factory._load_fixed_policy_module()
        original_decide = policy.CandidateAuthorizerProfile.decide

        def deny_seed_create(profile, action, *args):
            if profile.name == mutator.PROFILE_SEED and action == sqlite3.SQLITE_CREATE_TABLE:
                return sqlite3.SQLITE_DENY
            return original_decide(profile, action, *args)

        with mock.patch.object(
            policy.CandidateAuthorizerProfile,
            "decide",
            new=deny_seed_create,
        ):
            with self.assertRaises(factory.SeedConstructionFailure) as caught:
                factory.SeedInitializer(REPOSITORY_ROOT).initialize(
                    handle, self.registry
                )
        self.assertEqual(
            caught.exception.disposition.outcome,
            factory.SEED_CONSTRUCTION_FAILED_DISPOSED,
        )
        self.assertFalse(handle.root.exists())
        with self.assertRaises(factory.FixtureSecurityError):
            self.registry.get(handle.fixture_instance_id)

    def test_writer_connection_is_never_reused_across_capability_profiles(self):
        real_connect = factory.sqlite3.connect
        connections = []
        def recording_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            connections.append(connection)
            return connection
        with mock.patch.object(
            factory.sqlite3, "connect", side_effect=recording_connect
        ):
            handle, *_rest = self._repaired()
        self.addCleanup(self._dispose_if_safe, handle)
        self.assertEqual(len(connections), 3)
        self.assertEqual(len({id(connection) for connection in connections}), 3)

    def test_cross_profile_repair_on_ready_fixture_is_rejected(self):
        handle = self._create()
        self.addCleanup(self._dispose_if_safe, handle)
        with self.assertRaises(factory.FixtureSecurityError):
            factory.RepairMutator().execute(handle, self.registry)

    def test_runtime_preflight_authorizer_api_present(self):
        self.assertTrue(mutator.runtime_preflight().authorizer_api_present)

    def test_runtime_preflight_authorizer_installation_proven(self):
        self.assertTrue(
            mutator.runtime_preflight().authorizer_installation_proven
        )

    def test_runtime_preflight_bounded_deny_self_check(self):
        self.assertTrue(mutator.runtime_preflight().bounded_deny_self_check)

    def test_runtime_preflight_does_not_permit_mutation(self):
        self.assertFalse(mutator.runtime_preflight().mutation_permitted)

    def test_runtime_preflight_records_compile_options(self):
        self.assertIsInstance(
            mutator.runtime_preflight().compile_options, tuple
        )


def _count_logical_tests() -> tuple[int, int]:
    category_a = sum(
        name.startswith("test_")
        for cls in (
            SchemaAndFixtureTests,
            DigestAndSerializationTests,
            PolicyAndMappingTests,
            BoundaryAndPreflightTests,
        )
        for name in cls.__dict__
    )
    category_b = sum(
        name.startswith("test_") for name in MutationAuthorizedTests.__dict__
    )
    return category_a, category_b


CATEGORY_A_LOGICAL_TESTS, CATEGORY_B_LOGICAL_TESTS = _count_logical_tests()
LOGICAL_TEST_TOTAL = CATEGORY_A_LOGICAL_TESTS + CATEGORY_B_LOGICAL_TESTS

if LOGICAL_TEST_TOTAL < 114:
    raise RuntimeError(
        "logical test coverage fell below the frozen 114-test floor: "
        f"A={CATEGORY_A_LOGICAL_TESTS}, "
        f"B={CATEGORY_B_LOGICAL_TESTS}, total={LOGICAL_TEST_TOTAL}"
    )


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import threading
from dataclasses import replace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("acos_v2_core_substrate", ROOT / "scripts" / "acos-v2-core-substrate.py")
core = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = core
SPEC.loader.exec_module(core)


class CoreSubstrateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="acos-v2-core-test-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "core.sqlite"
        self.baseline = "304eb1e0d58b1c1b3185b093047c0d9859c4866c"
        self.scope = core.WorkflowScope("ACOS", "initial-core", "test-task")
        self.credential = object()
        self.submission_credential = object()
        self.authenticate = lambda supplied: "fixture-writer" if supplied is self.credential else None
        self.store = self.open_store(create=True)
        self.writer = self.store.writer(self.credential)
        self.engine = self.store.transition_engine(self.resolve, self.authenticate_submission)

    def open_store(self, **overrides):
        arguments = dict(path=self.path, scope=self.scope, baseline=self.baseline,
                         writer_principal="fixture-writer", authenticate_writer=self.authenticate)
        arguments.update(overrides)
        store = core.StateStore(**arguments)
        self.addCleanup(store.close)
        return store

    def candidate(self, **overrides):
        snapshot = self.store.snapshot()
        identity = core.ExecutionIdentity("ACOS", "initial-core", "test-task", "fixture-authority",
                                          "Codex Executor", "fixture-attempt", self.baseline)
        values = dict(transition_id=f"transition-{snapshot.last_applied_seq + 1}", candidate_id="fixture-candidate",
                      expected_parent_event_hash=snapshot.head_event_hash, expected_journal_seq=snapshot.last_applied_seq,
                      validated_baseline=self.baseline, authority_reference=core.AuthorityReference("fixture-authority", "sha256:" + "1" * 64),
                      execution_identity=identity, from_state=snapshot.state, to_state="REVIEW_PENDING")
        values.update(overrides)
        return core.CandidateTransition(**values)

    def resolve(self, reference):
        candidate = self.current_candidate
        return core.AuthorityEvidence(reference, candidate.execution_identity, candidate.candidate_id,
                                      candidate.from_state, candidate.to_state, "ChatGPT Review", True,
                                      ("fixture-scope-review",), ("fixture-scope-review",))

    def authenticate_submission(self, supplied):
        if supplied is self.submission_credential:
            return core.ExecutionIdentity("ACOS", "initial-core", "test-task", "fixture-authority",
                                          "Codex Executor", "fixture-attempt", self.baseline)
        return None

    def accept(self, candidate=None):
        self.current_candidate = candidate or self.candidate()
        return self.engine.validate(self.current_candidate, self.submission_credential)

    def sql(self, statement, parameters=()):
        # Fault injection and readback affect only this test's new temporary DB.
        with closing(sqlite3.connect(self.path)) as connection, connection:
            return connection.execute(statement, parameters).fetchall()

    def test_t01_normal_append_and_projection_update(self):
        record = self.accept()
        before = self.store.snapshot()
        self.assertEqual(before.last_applied_seq, 0)
        after = self.writer.append(record)
        self.assertEqual(after.state, "REVIEW_PENDING")
        self.assertEqual(after.last_applied_seq, 1)
        self.assertNotEqual(after.head_event_hash, core.GENESIS_HASH)
        self.assertEqual(self.sql("SELECT state, last_applied_seq, head_event_hash FROM derived_projection"),
                         [(after.state, 1, after.head_event_hash)])
        body = json.loads(self.sql("SELECT record_json FROM state_journal")[0][0])
        self.assertEqual(body["candidate_id"], record.candidate_id)
        self.assertEqual(body["execution_identity"]["execution_attempt_id"], "fixture-attempt")

    def test_t02_stale_expected_seq_rejected_at_writer(self):
        first = self.accept()
        stale = self.accept(self.candidate(transition_id="stale"))
        self.writer.append(first)
        with self.assertRaisesRegex(core.TransitionDenied, "stale expected sequence"):
            self.writer.append(stale)
        self.assertEqual(self.store.snapshot().last_applied_seq, 1)

    def test_t03_stale_parent_hash_rejected(self):
        with self.assertRaisesRegex(core.TransitionDenied, "stale predecessor hash"):
            self.accept(self.candidate(expected_parent_event_hash="sha256:" + "2" * 64))
        self.assertEqual(self.store.snapshot().last_applied_seq, 0)

    def test_t04_duplicate_transition_id_rejected(self):
        record = self.accept()
        self.writer.append(record)
        with self.assertRaisesRegex(core.TransitionDenied, "duplicate transition_id"):
            self.writer.append(record)
        with self.assertRaisesRegex(core.TransitionDenied, "duplicate transition_id"):
            self.accept(self.candidate(transition_id=record.transition_id, to_state="AUTHORIZED"))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(1,)])

    def test_t05_failed_append_does_not_advance_projection(self):
        record = self.accept()
        with mock.patch.object(self.store, "_insert_journal", side_effect=sqlite3.OperationalError("fixture append failure")):
            with self.assertRaises(core.StoreBlocked):
                self.writer.append(record)
        self.assertEqual(self.store.snapshot().last_applied_seq, 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(0,)])

    def test_t06_failed_projection_rolls_back_journal_and_survives_reopen(self):
        record = self.accept()
        with mock.patch.object(self.store, "_update_projection", side_effect=sqlite3.OperationalError("fixture projection failure")):
            with self.assertRaises(core.StoreBlocked):
                self.writer.append(record)
        reopened = self.open_store()
        self.assertEqual(reopened.snapshot().last_applied_seq, 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(0,)])

    def test_t07_deterministic_rebuild_and_mismatch_blocks_acceptance(self):
        original = self.writer.append(self.accept())
        self.sql("UPDATE derived_projection SET state = 'ACCEPTED', last_applied_seq = 99")
        with self.assertRaisesRegex(core.StoreBlocked, "journal/projection mismatch"):
            self.store.snapshot()
        with self.assertRaises(core.StoreBlocked):
            self.engine.validate(core.CandidateTransition(**{**self.current_candidate.__dict__, "transition_id": "next"}))
        self.assertEqual(self.writer.rebuild_projection(), original)
        self.assertEqual(self.writer.rebuild_projection(), original)
        self.assertEqual(self.open_store().snapshot(), original)

    def test_t08_missing_malformed_or_unresolved_authority_rejected(self):
        for reference in (None, "ChatGPT Review", core.AuthorityReference("", "sha256:" + "1" * 64),
                          core.AuthorityReference("fixture-authority", "invalid")):
            with self.subTest(reference=reference), self.assertRaises(core.TransitionDenied):
                self.accept(self.candidate(authority_reference=reference))
        engine = self.store.transition_engine(lambda reference: None, self.authenticate_submission)
        with self.assertRaises(core.TransitionDenied):
            engine.validate(self.candidate(), self.submission_credential)

    def test_t09_engine_cannot_persist_and_store_has_no_generic_write_api(self):
        self.accept()
        self.assertEqual(self.store.snapshot().last_applied_seq, 0)
        for name in ("append", "persist", "execute", "connection", "writer", "rebuild_projection"):
            self.assertFalse(hasattr(self.engine, name), name)
        for name in ("append", "persist", "execute", "connection", "rebuild_projection"):
            self.assertFalse(hasattr(self.store, name), name)

    def test_t10_audit_cannot_reconstruct_authoritative_state(self):
        self.sql("CREATE TABLE audit_events (state TEXT)")
        self.sql("INSERT INTO audit_events VALUES ('ACCEPTED')")
        self.sql("UPDATE derived_projection SET state = 'ACCEPTED'")
        rebuilt = self.writer.rebuild_projection()
        self.assertEqual(rebuilt.state, "DRAFT")
        self.assertEqual(rebuilt.last_applied_seq, 0)
        self.assertEqual(self.sql("SELECT * FROM audit_events"), [("ACCEPTED",)])

    def test_writer_identity_not_inferred_from_role_or_producer(self):
        for claimed in (None, "fixture-writer", "State Journal Writer", {"PRODUCER": "ChatGPT Review"}):
            with self.subTest(claimed=claimed), self.assertRaises(core.TransitionDenied):
                self.store.writer(claimed)
        with self.assertRaises(core.TransitionDenied):
            core.StateJournalWriter(self.store, self.credential)

    def test_writer_authentication_checked_again_at_append(self):
        record = self.accept()
        with mock.patch.object(self.store, "_authenticate_writer", return_value=None):
            with self.assertRaises(core.TransitionDenied):
                self.writer.append(record)
        self.assertEqual(self.store.snapshot().last_applied_seq, 0)

    def test_missing_authentication_or_resolver_fails_closed(self):
        with self.assertRaises(core.StoreBlocked):
            self.open_store(authenticate_writer=None)
        with self.assertRaises(core.StoreBlocked):
            self.store.transition_engine(None, self.authenticate_submission).validate(self.candidate(), self.submission_credential)
        with self.assertRaises(core.StoreBlocked):
            self.store.transition_engine(self.resolve).validate(self.candidate(), self.submission_credential)

    def test_submission_identity_not_inferred_from_claim_or_role(self):
        self.current_candidate = self.candidate()
        for claimed in (None, "Codex Executor", self.current_candidate.execution_identity, {"PRODUCER": "Codex Executor"}):
            with self.subTest(claimed=claimed), self.assertRaises(core.TransitionDenied):
                self.engine.validate(self.current_candidate, claimed)
        self.assertEqual(self.store.snapshot().last_applied_seq, 0)

    def test_forged_altered_foreign_or_candidate_records_rejected(self):
        record = self.accept()
        for supplied in (self.current_candidate, replace(record, _issuance=None), replace(record, to_state="QUARANTINED")):
            with self.subTest(supplied=supplied), self.assertRaises(core.TransitionDenied):
                self.writer.append(supplied)
        foreign = self.open_store()
        with self.assertRaises(core.TransitionDenied):
            foreign.writer(self.credential).append(record)

    def test_exact_authority_identity_candidate_state_and_gates_binding(self):
        self.current_candidate = self.candidate()
        evidence = self.resolve(self.current_candidate.authority_reference)
        changes = [dict(authenticated=False), dict(candidate_id="different"), dict(to_state="ACCEPTED"),
                   dict(governance_source="Codex Executor"), dict(governance_source="Audit Writer"),
                   dict(execution_identity=replace(evidence.execution_identity, execution_attempt_id="another")),
                   dict(authority_reference=replace(evidence.authority_reference, content_digest="sha256:" + "2" * 64)),
                   dict(verified_gates=())]
        for change in changes:
            engine = self.store.transition_engine(lambda reference, change=change: replace(evidence, **change), self.authenticate_submission)
            with self.subTest(change=change), self.assertRaises((core.TransitionDenied, core.StoreBlocked)):
                engine.validate(self.current_candidate, self.submission_credential)

    def test_baseline_scope_and_authorization_linkage_fail_closed(self):
        candidate = self.candidate()
        variants = [replace(candidate, validated_baseline="f" * 40),
                    replace(candidate, execution_identity=replace(candidate.execution_identity, task_id="other")),
                    replace(candidate, execution_identity=replace(candidate.execution_identity, baseline_revision="f" * 40)),
                    replace(candidate, execution_identity=replace(candidate.execution_identity, authorization_id="other"))]
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(core.TransitionDenied):
                self.accept(changed)

    def test_result_does_not_select_acceptance_or_checkpoint(self):
        for target in ("ACCEPTED", "STAGE_CLOSED", "CHECKPOINTED"):
            with self.subTest(target=target), self.assertRaises(core.TransitionDenied):
                self.accept(self.candidate(to_state=target))
        self.assertEqual(self.store.snapshot().state, "DRAFT")

    def test_single_writer_transaction_rechecks_concurrent_accepted_predecessors(self):
        other = self.open_store()
        candidate = self.candidate(transition_id="other")
        self.current_candidate = candidate
        accepted = other.transition_engine(self.resolve, self.authenticate_submission).validate(candidate, self.submission_credential)
        self.writer.append(self.accept())
        with self.assertRaises(core.TransitionDenied):
            other.writer(self.credential).append(accepted)
        self.assertEqual(other.snapshot().last_applied_seq, 1)

    def test_two_connections_compete_for_one_predecessor_exactly_one_commits(self):
        barrier = threading.Barrier(2)

        def compete(candidate):
            store = core.StateStore(self.path, self.scope, self.baseline, "fixture-writer", self.authenticate)
            try:
                resolver = lambda reference: core.AuthorityEvidence(
                    reference, candidate.execution_identity, candidate.candidate_id, candidate.from_state,
                    candidate.to_state, "ChatGPT Review", True, ("fixture-gate",), ("fixture-gate",))
                engine = store.transition_engine(resolver, self.authenticate_submission)
                accepted = engine.validate(candidate, self.submission_credential)
                barrier.wait(timeout=5)
                try:
                    store.writer(self.credential).append(accepted)
                    return "committed"
                except core.TransitionDenied:
                    return "denied"
            finally:
                store.close()

        candidates = [self.candidate(transition_id=identifier) for identifier in ("race-a", "race-b")]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(compete, candidate) for candidate in candidates]
            outcomes = [future.result(timeout=10) for future in futures]
        self.assertCountEqual(outcomes, ["committed", "denied"])
        self.assertEqual(self.store.snapshot().last_applied_seq, 1)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(1,)])

    def test_append_receipt_does_not_read_a_later_projection(self):
        accepted = self.accept()
        with mock.patch.object(self.store, "snapshot", side_effect=AssertionError("post-commit snapshot must not redefine receipt")):
            receipt = self.writer.append(accepted)
        self.assertEqual(receipt.state, accepted.to_state)
        self.assertEqual(receipt.last_applied_seq, 1)
        self.assertEqual(receipt, self.store.snapshot())

    def test_journal_update_and_delete_are_rejected(self):
        self.writer.append(self.accept())
        for statement in ("UPDATE state_journal SET record_json = '{}'", "DELETE FROM state_journal"):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                self.sql(statement)
        self.assertEqual(self.store.snapshot().last_applied_seq, 1)

    def test_corrupt_journal_blocks_rebuild_without_repair(self):
        self.sql("INSERT INTO state_journal VALUES (1, 'forged', ?, ?, '{}')", (core.GENESIS_HASH, "sha256:" + "3" * 64))
        with self.assertRaises(core.StoreBlocked):
            self.writer.rebuild_projection()
        self.assertEqual(self.sql("SELECT state FROM derived_projection"), [("DRAFT",)])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(1,)])

    def test_stop_quarantine_preserve_only_cannot_exit_via_rebuild(self):
        for state in ("STOPPED", "QUARANTINED", "PRESERVE_ONLY"):
            with self.subTest(state=state):
                path = self.path.parent / (state + ".sqlite")
                store = self.open_store(path=path, create=True)
                candidate = self.candidate(to_state=state)
                self.current_candidate = candidate
                writer = store.writer(self.credential)
                writer.append(store.transition_engine(self.resolve, self.authenticate_submission).validate(candidate, self.submission_credential))
                self.assertEqual(writer.rebuild_projection().state, state)
                stopped = replace(candidate, transition_id="exit", expected_journal_seq=1,
                                  expected_parent_event_hash=store.snapshot().head_event_hash,
                                  from_state=state, to_state="REVIEW_PENDING")
                with self.assertRaises(core.TransitionDenied):
                    store.transition_engine(self.resolve).validate(stopped)

    def test_unknown_is_not_a_valid_workflow_target_state(self):
        self.assertNotIn("UNKNOWN", core.TERMINAL)
        self.assertNotIn("UNKNOWN", core.STATES)
        with self.assertRaisesRegex(core.TransitionDenied, "^unknown workflow state$"):
            self.accept(self.candidate(to_state="UNKNOWN"))
        self.assertEqual(self.store.snapshot().state, "DRAFT")

    def test_unknown_is_not_a_valid_workflow_source_state(self):
        self.assertNotIn("UNKNOWN", core.STATES)
        with self.assertRaisesRegex(core.TransitionDenied, "^unknown workflow state$"):
            self.accept(self.candidate(from_state="UNKNOWN"))
        self.assertEqual(self.store.snapshot().state, "DRAFT")

    def test_commit_acknowledgement_failure_blocks_current_store_without_retry(self):
        record = self.accept()
        with mock.patch.object(self.store, "_commit_transaction", side_effect=sqlite3.OperationalError("unknown acknowledgement")):
            with self.assertRaises(core.MutationOutcomeUnknown):
                self.writer.append(record)
        for operation in (self.store.snapshot, self.writer.rebuild_projection, lambda: self.writer.append(record)):
            with self.assertRaises(core.StoreBlocked):
                operation()

    def test_u01_uncertain_store_blocks_acceptance_and_cannot_self_reconcile(self):
        record = self.accept()
        with mock.patch.object(self.store, "_commit_transaction", side_effect=sqlite3.OperationalError("before commit")):
            with self.assertRaises(core.MutationOutcomeUnknown):
                self.writer.append(record)
        for operation in (
            lambda: self.engine.validate(self.current_candidate, self.submission_credential),
            lambda: self.writer.append(record),
            lambda: self.store.reconcile(record.transition_id),
            self.writer.rebuild_projection,
        ):
            with self.subTest(operation=operation), self.assertRaises(core.StoreBlocked):
                operation()

    def test_u02_reopen_requires_durable_reconciliation_before_acceptance(self):
        record = self.accept()
        with mock.patch.object(self.store, "_commit_transaction", side_effect=sqlite3.OperationalError("before commit")):
            with self.assertRaises(core.MutationOutcomeUnknown):
                self.writer.append(record)
        self.store.close()
        original = core.StateStore._consistent_snapshot
        observations = []

        def observe_pending_gate(store):
            self.assertFalse(store._reconciled)
            self.assertTrue(store._db.in_transaction)
            with self.assertRaisesRegex(core.StoreBlocked, "durable reconciliation required"):
                store._require_available()
            observations.append("durable read before acceptance")
            return original(store)

        with mock.patch.object(core.StateStore, "_consistent_snapshot", new=observe_pending_gate):
            reopened = self.open_store()
        self.assertEqual(observations, ["durable read before acceptance"])
        self.assertEqual(reopened.snapshot().last_applied_seq, 0)
        self.assertEqual(reopened.reconcile(record.transition_id).transition_outcome, "NOT_COMMITTED")

    def test_u03_commit_landed_ack_lost_reconciles_committed_without_replay(self):
        record = self.accept()
        real_commit = self.store._commit_transaction

        def commit_then_lose_acknowledgement():
            # Real SQLite commit; simulated acknowledgement loss, not power loss.
            real_commit()
            raise sqlite3.OperationalError("fixture lost acknowledgement after commit")

        with mock.patch.object(self.store, "_commit_transaction", side_effect=commit_then_lose_acknowledgement):
            with self.assertRaises(core.MutationOutcomeUnknown):
                self.writer.append(record)
        with self.assertRaises(core.StoreBlocked):
            self.store.snapshot()
        self.store.close()
        reopened = self.open_store()
        reconciliation = reopened.reconcile(record.transition_id)
        self.assertTrue(reconciliation.consistent)
        self.assertEqual(reconciliation.transition_outcome, "COMMITTED")
        self.assertEqual(reconciliation.snapshot.last_applied_seq, 1)
        self.assertIn(record.transition_id, reconciliation.snapshot.transition_ids)
        with self.assertRaisesRegex(core.TransitionDenied, "duplicate transition_id"):
            reopened.writer(self.credential).append(record)
        self.assertEqual(reopened.reconcile(record.transition_id), reconciliation)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(1,)])

    def test_u04_commit_did_not_land_reconciles_not_committed(self):
        record = self.accept()
        with mock.patch.object(self.store, "_commit_transaction", side_effect=sqlite3.OperationalError("fixture before commit")):
            with self.assertRaises(core.MutationOutcomeUnknown):
                self.writer.append(record)
        self.store.close()
        reopened = self.open_store()
        reconciliation = reopened.reconcile(record.transition_id)
        self.assertTrue(reconciliation.consistent)
        self.assertEqual(reconciliation.transition_outcome, "NOT_COMMITTED")
        self.assertEqual(reconciliation.snapshot.state, "DRAFT")
        self.assertEqual(reconciliation.snapshot.head_event_hash, core.GENESIS_HASH)
        self.assertEqual(reconciliation.snapshot.last_applied_seq, 0)
        self.assertNotIn(record.transition_id, reconciliation.snapshot.transition_ids)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(0,)])

    def test_u05_projection_mismatch_keeps_reconciliation_and_reopen_fail_closed(self):
        candidate = self.candidate()
        self.sql("UPDATE derived_projection SET last_applied_seq = 99")
        before = self.sql("SELECT * FROM derived_projection")
        reconciliation = self.store.reconcile(candidate.transition_id)
        self.assertFalse(reconciliation.consistent)
        self.assertEqual(reconciliation.transition_outcome, "UNRESOLVED")
        self.assertIsNone(reconciliation.snapshot)
        with self.assertRaises(core.StoreBlocked):
            self.engine.validate(candidate, self.submission_credential)
        with self.assertRaisesRegex(core.StoreBlocked, "journal/projection mismatch"):
            self.open_store()
        self.assertEqual(self.sql("SELECT * FROM derived_projection"), before)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(0,)])

    def test_u06_unreadable_or_corrupt_journal_remains_unresolved(self):
        with mock.patch.object(core.StateStore, "_replay_journal", side_effect=sqlite3.DatabaseError("fixture unreadable journal")):
            reconciliation = self.store.reconcile("unknown-transition")
            self.assertFalse(reconciliation.consistent)
            self.assertEqual(reconciliation.transition_outcome, "UNRESOLVED")
            with self.assertRaisesRegex(core.StoreBlocked, "fixture unreadable journal"):
                self.open_store()
        with self.assertRaises(core.StoreBlocked):
            self.store.snapshot()
        self.assertTrue(self.store.reconcile().consistent)
        candidate = self.candidate()
        self.sql("INSERT INTO state_journal VALUES (1, 'forged', ?, ?, '{}')", (core.GENESIS_HASH, "sha256:" + "3" * 64))
        reconciliation = self.store.reconcile("forged")
        self.assertFalse(reconciliation.consistent)
        self.assertEqual(reconciliation.transition_outcome, "UNRESOLVED")
        self.assertIsNone(reconciliation.snapshot)
        with self.assertRaises(core.StoreBlocked):
            self.engine.validate(candidate, self.submission_credential)
        with self.assertRaisesRegex(core.StoreBlocked, "journal invalid"):
            self.open_store()
        self.assertEqual(self.sql("SELECT COUNT(*) FROM state_journal"), [(1,)])

    def test_u07_reconciliation_is_read_only_and_does_not_issue_retry_authority(self):
        record = self.accept()
        with mock.patch.object(self.store, "_commit_transaction", side_effect=sqlite3.OperationalError("before commit")):
            with self.assertRaises(core.MutationOutcomeUnknown):
                self.writer.append(record)
        self.store.close()
        reopened = self.open_store()
        before = reopened.snapshot()
        changes = reopened._db.total_changes
        resolver = mock.Mock(side_effect=AssertionError("reconciliation must not consult governance"))
        engine = reopened.transition_engine(resolver, self.authenticate_submission)
        with mock.patch.object(reopened._issuer, "issue", side_effect=AssertionError("reconciliation must not issue records")), \
                mock.patch.object(reopened, "_authenticate_writer", side_effect=AssertionError("read-only facts need no writer")):
            reconciliation = reopened.reconcile(record.transition_id)
        self.assertEqual(reconciliation.transition_outcome, "NOT_COMMITTED")
        self.assertEqual(reconciliation.snapshot, before)
        self.assertEqual(reopened._db.total_changes, changes)
        self.assertEqual(reopened._issuer._issued, {})
        self.assertNotIsInstance(reconciliation, core.AcceptedTransitionRecord)
        with self.assertRaisesRegex(core.TransitionDenied, "unissued"):
            reopened.writer(self.credential).append(record)
        with self.assertRaises(core.TransitionDenied):
            engine.validate(self.current_candidate, None)
        resolver.assert_not_called()
        self.assertEqual(reopened.snapshot(), before)

    def test_u08_audit_cannot_resolve_transition_commit_outcome(self):
        record = self.accept()
        with mock.patch.object(self.store, "_commit_transaction", side_effect=sqlite3.OperationalError("before commit")):
            with self.assertRaises(core.MutationOutcomeUnknown):
                self.writer.append(record)
        self.store.close()
        self.sql("CREATE TABLE audit_events (transition_id TEXT, outcome TEXT)")
        self.sql("INSERT INTO audit_events VALUES (?, 'COMMITTED')", (record.transition_id,))
        reopened = self.open_store()
        self.assertEqual(reopened.reconcile(record.transition_id).transition_outcome, "NOT_COMMITTED")
        self.sql("UPDATE audit_events SET outcome = 'NOT_COMMITTED'")
        fresh = reopened.transition_engine(self.resolve, self.authenticate_submission).validate(
            self.current_candidate, self.submission_credential)
        reopened.writer(self.credential).append(fresh)
        reconciliation = reopened.reconcile(record.transition_id)
        self.assertEqual(reconciliation.transition_outcome, "COMMITTED")
        self.assertEqual(reconciliation.snapshot.last_applied_seq, 1)
        self.assertEqual(self.sql("SELECT * FROM audit_events"), [(record.transition_id, "NOT_COMMITTED")])

    def test_existing_store_not_initialized_migrated_or_rebound(self):
        with self.assertRaises(core.StoreBlocked):
            self.open_store(create=True)
        with self.assertRaises(core.StoreBlocked):
            self.open_store(baseline="f" * 40)
        with self.assertRaises(core.StoreBlocked):
            self.open_store(writer_principal="other")
        self.sql("DROP TRIGGER state_journal_no_delete")
        with self.assertRaises(core.StoreBlocked):
            self.open_store()
        self.assertEqual(self.sql("SELECT name FROM sqlite_schema WHERE name = 'state_journal_no_delete'"), [])


if __name__ == "__main__":
    unittest.main()

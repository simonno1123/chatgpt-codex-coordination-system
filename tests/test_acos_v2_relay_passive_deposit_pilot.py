"""RP-01--RP-40: isolated, non-agent PASSIVE_DEPOSIT pilot contract.

Only harness-owned temporary SQLite/files are changed. The sink is a local
fixture, and network/process endpoint entry points are blocked during runtime
checks. These tests make no production authentication or exactly-once claim.
The existing /1 test suite and canonical implementation remain read-only.
"""

import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/acos-v2-relay-passive-deposit-pilot.py"
spec = importlib.util.spec_from_file_location("acos_v2_relay_passive_pilot", SOURCE)
p = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = p
spec.loader.exec_module(p)
v0 = p.v0


class SimulatedProcessCrash(BaseException):
    pass


class RelayPassiveDepositPilotTests(unittest.TestCase):
    def setUp(self):
        owned = tempfile.TemporaryDirectory(prefix="acos-relay-rp-")
        self.addCleanup(owned.cleanup)
        self.root = Path(owned.name)
        self.path = self.root / "pilot.db"
        self.custodian = p.PilotCustodian.init(self.path, project_id="ACOS")
        self.publisher = v0.LocalIdentity(
            "Codex Executor", "executor-fixture", "executor-consumer",
            "local-publisher", "opaque-codex-chat", "publisher-session")
        self.recipient = v0.LocalIdentity(
            "ChatGPT Review", "review-fixture", "review-consumer",
            "local-recipient", "opaque-chatgpt-chat", "recipient-session")
        self.artifact = self.make_artifact()
        self._fact_counter = 0

    def fact(self, label="test"):
        self._fact_counter += 1
        return f"{label}-{self._fact_counter}"

    def make_artifact(self, **overrides):
        fields = dict(
            artifact_id="artifact-1", artifact_type="AUTHORIZATION",
            project_id="ACOS", stage_id="isolated-pilot", task_id="fixture-task",
            from_role="Codex Executor", to_role="ChatGPT Review",
            receiver_id="review-fixture", correlation_id="fixture-exchange",
            created_at="2026-10-05T00:00:00Z",
            payload={"FROM": "ChatGPT Review", "TO": "real-agent-secret-target",
                     "command": "DO NOT EXECUTE", "body": ["inert", 7]},
            execution_attempt_id="opaque-execution-attempt",
            authority_reference="opaque-not-a-grant", baseline_revision="opaque-baseline")
        fields.update(overrides)
        return v0.CoordinationArtifact.build(**fields)

    @staticmethod
    def field(value, name):
        if isinstance(value, str) and name == "delivery_id":
            return value
        return value[name] if isinstance(value, dict) else getattr(value, name)

    def sql(self, statement, parameters=()):
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(statement, parameters).fetchall()
            connection.commit()
            return rows

    def journal(self):
        return self.sql("SELECT * FROM coordination_events ORDER BY seq")

    def unchanged(self, action, errors=None):
        before = self.path.read_bytes()
        with self.assertRaises(errors or (p.Rejected, p.ScopeDenied, p.StoreBlocked)):
            action()
        self.assertEqual(self.path.read_bytes(), before)

    def publish(self, artifact=None, recipient=None):
        return self.custodian.publish(
            self.artifact if artifact is None else artifact,
            publisher=self.publisher,
            recipient=self.recipient if recipient is None else recipient,
            fact_id=self.fact("publish"))

    def ready(self, *, suffix="", artifact=None, recipient=None):
        recipient = self.recipient if recipient is None else recipient
        artifact = self.artifact if artifact is None else artifact
        receipt = self.publish(artifact, recipient)
        delivery_id = self.field(receipt, "delivery_id")
        binding_id = "fixture-binding" + suffix
        self.custodian.create_binding(
            binding_id, recipient, generation=1, fact_id=self.fact("binding"))
        self.custodian.bind_delivery(
            delivery_id, binding_id, 1, fact_id=self.fact("delivery-bound"))
        recipient_digest = v0.digest(recipient.to_dict())
        scope = p.ReadScope("ACOS", recipient_digest, binding_id, 1,
                            effects=(p.PASSIVE_DEPOSIT,))
        reader = self.custodian.reader(scope)
        recorder = self.custodian.recorder(scope, reporting_principal="fixture-relay")
        directory = self.root / ("sink" + suffix)
        sink = p.LocalPassiveSink.init(directory, binding_id, 1, recipient_digest)
        permit = p.TransportPermit(
            "ACOS", binding_id, 1, recipient_digest,
            expires_at="2099-01-01T00:00:00Z", effect_class=p.PASSIVE_DEPOSIT,
            max_attempts=2, allow_retry=True)
        worker = p.RelayWorker(reader, recorder, sink, permit)
        return dict(delivery_id=delivery_id, binding_id=binding_id,
                    recipient_digest=recipient_digest, scope=scope, reader=reader,
                    recorder=recorder, sink=sink, directory=directory,
                    permit=permit, worker=worker)

    @staticmethod
    def snapshot(fixture):
        return fixture["reader"].read_delivery(fixture["delivery_id"])

    def prepare_dispatch(self, fixture, attempt="attempt-1"):
        prepared = fixture["recorder"].prepare(
            self.snapshot(fixture), attempt, fixture["permit"],
            fact_id=self.fact("prepare"))
        dispatched = fixture["recorder"].dispatch(
            prepared, attempt, fixture["permit"], fact_id=self.fact("dispatch"))
        return dispatched

    def positive_rejection(self, fixture, attempt="attempt-1"):
        with mock.patch.object(fixture["sink"], "_before_deposit",
                               side_effect=p.SinkRejected("terminal pre-effect rejection")):
            fixture["worker"].deliver(fixture["delivery_id"], attempt)
        self.assertEqual(self.snapshot(fixture).state, "KNOWN_NOT_DELIVERED")
        self.assertEqual(fixture["sink"].effect_count, 0)

    def assert_no_dispatch(self, fixture, operation, expected_state=None):
        before = fixture["sink"].effect_count
        with mock.patch.object(fixture["sink"], "deposit", wraps=fixture["sink"].deposit) as deposit:
            try:
                operation()
            except (p.Rejected, p.ScopeDenied, p.StoreBlocked, p.OutcomeUnknown):
                pass
            deposit.assert_not_called()
        self.assertEqual(fixture["sink"].effect_count, before)
        if expected_state is not None:
            self.assertEqual(self.snapshot(fixture).state, expected_state)

    def deposit_bytes(self, fixture, snapshot):
        path = fixture["sink"].deposit_path(snapshot.stable_adapter_request_id)
        wrapper = json.loads(path.read_text(encoding="ascii"))
        self.assertEqual(wrapper["deposit"]["envelope_json"], snapshot.envelope_json)
        self.assertEqual(wrapper["deposit"]["envelope_digest"], snapshot.envelope_digest)
        self.assertEqual(wrapper["receipt"]["envelope_digest"], snapshot.envelope_digest)
        self.assertEqual(path.read_bytes(), v0.canonical(wrapper).encode("ascii"))
        self.assertEqual(len(list(fixture["directory"].glob("*.deposit.json"))), 1)
        return path

    def test_RP01_explicit_fixture_init_only(self):
        missing = self.root / "absent" / "pilot.db"
        with self.assertRaises(p.StoreBlocked):
            p.PilotCustodian(missing, project_id="ACOS")
        self.assertFalse(missing.parent.exists())
        self.assertTrue(self.path.is_file())

    def test_RP02_existing_path_overwrite_denied(self):
        self.unchanged(lambda: p.PilotCustodian.init(self.path, project_id="ACOS"))
        occupied = self.root / "occupied.db"
        occupied.write_bytes(b"historical content")
        with self.assertRaises((p.Rejected, p.StoreBlocked)):
            p.PilotCustodian.init(occupied, project_id="ACOS")
        self.assertEqual(occupied.read_bytes(), b"historical content")

    def test_RP03_fresh_store_reports_2(self):
        self.assertEqual(p.STORE_FORMAT, "acos-v2-coordination/2")
        self.assertEqual(self.sql("PRAGMA user_version"), [(2,)])
        self.assertEqual(self.sql("SELECT value FROM store_meta WHERE key='format'"), [(p.STORE_FORMAT,)])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_RP04_artifact_schema_remains_1(self):
        fixture = self.ready()
        snapshot = self.snapshot(fixture)
        self.assertEqual(snapshot.artifact.schema_version, 1)
        self.assertEqual(snapshot.envelope_json, self.artifact.to_json())
        self.assertEqual(snapshot.envelope_digest, self.artifact.envelope_digest)
        self.assertEqual(v0.SCHEMA_VERSION, 1)

    def test_RP05_existing_1_store_is_not_migrated(self):
        legacy_path = self.root / "legacy" / "coordination.db"
        legacy_path.parent.mkdir()
        legacy = v0.CoordinationStore.init(legacy_path, project_id="ACOS")
        receipt = legacy.writer().publish(self.artifact, publisher=self.publisher, recipient=self.recipient)
        before = legacy_path.read_bytes()
        for operation in (lambda: p.PilotCustodian(legacy_path, project_id="ACOS"),
                          lambda: p.PilotCustodian.init(legacy_path, project_id="ACOS")):
            with self.subTest(operation=operation), self.assertRaises((p.StoreBlocked, p.Rejected)):
                operation()
            self.assertEqual(legacy_path.read_bytes(), before)
        reopened = v0.CoordinationStore(legacy_path, project_id="ACOS")
        self.assertEqual(reopened.read(receipt.artifact_id), self.artifact)

    def test_RP06_reopen_verifies_journal_and_projections(self):
        fixture = self.ready()
        fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        before = self.path.read_bytes()
        expected = self.snapshot(fixture)
        reopened = p.PilotCustodian(self.path, project_id="ACOS")
        self.assertEqual(reopened.reader(fixture["scope"]).read_delivery(fixture["delivery_id"]), expected)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertGreater(len(self.journal()), 4)

    def test_RP07_journal_tamper_fails_closed(self):
        self.ready()
        for (name,) in self.sql("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='coordination_events'"):
            self.sql('DROP TRIGGER "' + name.replace('"', '""') + '"')
        self.sql("UPDATE coordination_events SET event_hash=? WHERE seq=1", ("sha256:" + "f" * 64,))
        for definition in p.SCHEMA:
            if definition.startswith("CREATE TRIGGER events_"):
                self.sql(definition)
        actual = {row[0] for row in self.sql("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")}
        self.assertEqual(actual, set(p.SCHEMA))
        with self.assertRaisesRegex(p.StoreBlocked, "journal hash/sequence/canonical mismatch"):
            p.PilotCustodian(self.path, project_id="ACOS")
        self.unchanged(lambda: p.PilotCustodian(self.path, project_id="ACOS"), (p.StoreBlocked,))

    def test_RP08_projection_tamper_fails_closed(self):
        self.ready()
        self.sql("UPDATE transport_projection SET body_json='{}' WHERE singleton=1")
        self.unchanged(lambda: p.PilotCustodian(self.path, project_id="ACOS"), (p.StoreBlocked,))

    def test_RP09_reader_project_scope_enforced(self):
        fixture = self.ready()
        wrong = replace(fixture["scope"], project_id="OTHER")
        self.unchanged(lambda: self.custodian.reader(wrong).read_delivery(fixture["delivery_id"]))

    def test_RP10_recipient_binding_scope_enforced(self):
        fixture = self.ready()
        wrong = replace(fixture["scope"], recipient_digest="sha256:" + "a" * 64)
        self.unchanged(lambda: self.custodian.reader(wrong).read_delivery(fixture["delivery_id"]))

    def test_RP11_effect_allowlist_enforced(self):
        fixture = self.ready()
        for effects in ((), ("CONTEXT_MUTATION",), (p.PASSIVE_DEPOSIT, "MODEL_OR_AGENT_INVOCATION")):
            with self.subTest(effects=effects):
                self.unchanged(lambda: self.custodian.reader(replace(fixture["scope"], effects=effects)))

    def test_RP12_reader_returns_immutable_detached_content(self):
        fixture = self.ready()
        snapshot = self.snapshot(fixture)
        with self.assertRaises(FrozenInstanceError):
            snapshot.envelope_json = "changed"
        with self.assertRaises(FrozenInstanceError):
            snapshot.attempt_ids = ("forged",)
        snapshot.artifact.payload["body"].append("changed copy")
        self.assertEqual(self.snapshot(fixture).artifact.payload["body"], ["inert", 7])
        status = fixture["reader"].status()
        status["caller_mutation"] = True
        self.assertNotIn("caller_mutation", fixture["reader"].status())
        self.assertIsInstance(snapshot.attempt_ids, tuple)

    def test_RP13_read_has_no_ack_claim_or_write_side_effect(self):
        fixture = self.ready()
        before = self.path.read_bytes()
        journal_before = self.journal()
        for _ in range(3):
            self.snapshot(fixture)
            fixture["reader"].status()
            fixture["reader"].lookup_fact("does-not-exist")
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.journal(), journal_before)
        self.assertEqual(self.snapshot(fixture).attempt_ids, ())
        self.assertEqual(fixture["sink"].effect_count, 0)

    def test_RP14_explicit_endpoint_binding_required(self):
        receipt = self.publish()
        self.unchanged(lambda: self.custodian.bind_delivery(
            self.field(receipt, "delivery_id"), "not-created", 1, fact_id=self.fact("bind")))

    def test_RP15_prose_cannot_choose_destination(self):
        fixture = self.ready()
        snapshot = self.snapshot(fixture)
        self.assertEqual(snapshot.binding_id, fixture["binding_id"])
        self.assertEqual(snapshot.recipient_json, v0.canonical(self.recipient.to_dict()))
        self.assertEqual(snapshot.artifact.payload["TO"], "real-agent-secret-target")
        fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        self.assertEqual(fixture["sink"].effect_count, 1)
        self.deposit_bytes(fixture, snapshot)
        self.assertFalse((self.root / "real-agent-secret-target").exists())

    def test_RP16_delivery_tuple_is_immutable(self):
        fixture = self.ready()
        snapshot = self.snapshot(fixture)
        alternative = "alternative-binding"
        self.custodian.create_binding(alternative, self.recipient, generation=1, fact_id=self.fact("binding"))
        self.unchanged(lambda: self.custodian.bind_delivery(
            fixture["delivery_id"], alternative, 1, fact_id=self.fact("rebind")))
        for forged in (replace(snapshot, envelope_digest="sha256:" + "b" * 64),
                       replace(snapshot, semantic_effect_request_digest="sha256:" + "c" * 64),
                       replace(snapshot, stable_adapter_request_id="other-request")):
            with self.subTest(forged=forged):
                self.unchanged(lambda: fixture["recorder"].prepare(
                    forged, "forged-attempt", fixture["permit"], fact_id=self.fact("prepare")))
        self.assertEqual(self.snapshot(fixture), snapshot)

    def test_RP17_generation_change_does_not_rewrite_history(self):
        fixture = self.ready()
        before = self.snapshot(fixture)
        self.custodian.revoke_binding(fixture["binding_id"], 1, fact_id=self.fact("revoke"))
        self.custodian.create_binding(fixture["binding_id"], self.recipient,
                                      generation=2, fact_id=self.fact("new-generation"))
        self.unchanged(lambda: self.custodian.bind_delivery(
            fixture["delivery_id"], fixture["binding_id"], 2, fact_id=self.fact("rebind-old-delivery")))
        historical = self.snapshot(fixture)
        self.assertEqual(historical.envelope_json, before.envelope_json)
        self.assertEqual(historical.envelope_digest, before.envelope_digest)
        self.assertEqual(historical.binding_id, before.binding_id)
        self.assertEqual(historical.generation, 1)
        self.assertEqual(historical.semantic_effect_request_digest, before.semantic_effect_request_digest)
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-1"))

    def test_RP18_revoked_binding_blocks_new_dispatch(self):
        fixture = self.ready()
        self.custodian.revoke_binding(fixture["binding_id"], 1, fact_id=self.fact("revoke"))
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-1"))

    def test_RP19_stale_revision_blocks_dispatch(self):
        fixture = self.ready()
        stale = self.snapshot(fixture)
        fresh = fixture["recorder"].prepare(stale, "attempt-1", fixture["permit"], fact_id=self.fact("prepare"))
        self.assertGreater(fresh.revision, stale.revision)
        self.unchanged(lambda: fixture["recorder"].dispatch(
            stale, "attempt-1", fixture["permit"], fact_id=self.fact("stale-dispatch")))
        self.assertEqual(fixture["sink"].effect_count, 0)

    def test_RP20_concurrent_attempt_is_rejected_or_serialized(self):
        fixture = self.ready()
        snapshot = self.snapshot(fixture)
        def prepare(attempt):
            local = p.PilotCustodian(self.path, project_id="ACOS")
            recorder = local.recorder(fixture["scope"], reporting_principal="fixture-relay")
            try:
                recorder.prepare(snapshot, attempt, fixture["permit"], fact_id="concurrent-" + attempt)
                return "accepted"
            except (p.Rejected, p.ScopeDenied, p.StoreBlocked):
                return "blocked"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(prepare, ("attempt-A", "attempt-B")))
        self.assertEqual(sorted(results), ["accepted", "blocked"])
        self.assertEqual(len(self.snapshot(fixture).attempt_ids), 1)
        self.assertEqual(fixture["sink"].effect_count, 0)

    def test_RP21_dispatch_intent_durable_before_sink_effect(self):
        fixture = self.ready()
        observed = []
        def before_deposit(*args, **kwargs):
            reopened = p.PilotCustodian(self.path, project_id="ACOS")
            snapshot = reopened.reader(fixture["scope"]).read_delivery(fixture["delivery_id"])
            observed.append(snapshot)
            self.assertIn("attempt-1", snapshot.attempt_ids)
            durable_intent = reopened.reader(fixture["scope"]).lookup_fact("attempt-1:intent")
            self.assertEqual(durable_intent["kind"], "DISPATCH_INTENT")
            self.assertEqual(durable_intent["body"]["data"]["delivery_id"], fixture["delivery_id"])
            self.assertEqual(fixture["sink"].effect_count, 0)
        with mock.patch.object(fixture["sink"], "_before_deposit", side_effect=before_deposit):
            fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        self.assertEqual(len(observed), 1)
        self.assertEqual(fixture["sink"].effect_count, 1)

    def test_RP22_intent_commit_unknown_prevents_sink_call(self):
        fixture = self.ready()
        original = self.custodian._writer._commit
        commits = []
        def commit_then_lose_ack(connection):
            original(connection)
            commits.append(True)
            if len(commits) == 2:
                raise sqlite3.OperationalError("injected dispatch-intent commit acknowledgement loss")
        with mock.patch.object(self.custodian._writer, "_commit", side_effect=commit_then_lose_ack):
            self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-1"))
        self.assertGreaterEqual(len(commits), 2, "fault must follow the dispatch-intent commit, not preparation")
        reopened = p.PilotCustodian(self.path, project_id="ACOS")
        self.assertEqual(len(reopened.reader(fixture["scope"]).read_delivery(fixture["delivery_id"]).attempt_ids), 1)
        self.assertEqual(reopened.reader(fixture["scope"]).lookup_fact("attempt-1:intent")["kind"], "DISPATCH_INTENT")

    def test_RP23_sink_exact_deposit_produces_exact_content_receipt(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        self.assertEqual(receipt["artifact_id"], snapshot.artifact_id)
        self.assertEqual(receipt["delivery_id"], snapshot.delivery_id)
        self.assertEqual(receipt["envelope_digest"], snapshot.envelope_digest)
        self.assertEqual(receipt["generation"], snapshot.generation)
        self.assertEqual(receipt["stable_adapter_request_id"], snapshot.stable_adapter_request_id)
        self.assertEqual(receipt["semantic_effect_request_digest"], snapshot.semantic_effect_request_digest)
        self.assertEqual(receipt["receipt_stage"], "ENDPOINT_CONTENT_ACCEPTED")
        self.assertEqual(receipt["authority"], "NONE")
        self.assertTrue(receipt["endpoint_receipt_id"])
        self.deposit_bytes(fixture, snapshot)
        self.assertEqual(fixture["sink"].effect_count, 1)

    def test_RP24_exact_sink_replay_is_idempotent(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        before = {f.relative_to(fixture["directory"]): hashlib.sha256(f.read_bytes()).hexdigest()
                  for f in fixture["directory"].rglob("*") if f.is_file()}
        self.assertEqual(fixture["sink"].deposit(snapshot, "attempt-1"), receipt)
        self.assertEqual(fixture["sink"].effect_count, 1)
        after = {f.relative_to(fixture["directory"]): hashlib.sha256(f.read_bytes()).hexdigest()
                 for f in fixture["directory"].rglob("*") if f.is_file()}
        self.assertEqual(after, before)

    def test_RP25_conflicting_stable_request_reuse_is_rejected(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        original = fixture["sink"].deposit(snapshot, "attempt-1")
        forged = replace(snapshot, envelope_digest="sha256:" + "d" * 64)
        with self.assertRaises((p.Rejected, p.SinkRejected, p.ReceiptConflict)):
            fixture["sink"].deposit(forged, "attempt-1")
        self.assertEqual(fixture["sink"].effect_count, 1)
        self.assertEqual(fixture["sink"].status(snapshot.stable_adapter_request_id), original)

    def test_RP26_receipt_validates_protected_tuple(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        changes = {
            "artifact_id": "wrong-artifact", "delivery_id": "wrong-delivery",
            "envelope_digest": "sha256:" + "e" * 64, "generation": 2,
            "binding_id": "other-binding", "relay_attempt_id": "other-attempt",
            "recipient_json": v0.canonical(replace(self.recipient, session_id="other-session").to_dict()),
            "recipient_digest": "sha256:" + "d" * 64,
            "stable_adapter_request_id": "wrong-key",
            "semantic_effect_request_digest": "sha256:" + "f" * 64,
            "receipt_stage": "INVOCATION_STARTED", "authority": "APPROVED",
            "reporting_principal": "ChatGPT Review", "assurance": "PRODUCTION_AUTHENTICATED",
        }
        for key, value in changes.items():
            with self.subTest(key=key):
                self.unchanged(lambda: fixture["recorder"].record_receipt(
                    fixture["delivery_id"], "attempt-1", dict(receipt, **{key: value}),
                    fact_id=self.fact("bad-receipt")))
        self.assertEqual(fixture["sink"].effect_count, 1)

    def test_RP27_duplicate_exact_receipt_is_idempotent(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        first = fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", receipt,
                                                      fact_id="exact-receipt")
        journal_before = self.journal()
        again = fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", receipt,
                                                      fact_id="exact-receipt")
        self.assertEqual({key: value for key, value in again.items() if key != "recorded_now"},
                         {key: value for key, value in first.items() if key != "recorded_now"})
        self.assertEqual(self.journal(), journal_before)
        self.assertEqual(self.snapshot(fixture).state, "KNOWN_DELIVERED")

    def test_RP28_conflicting_receipt_is_quarantined(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", receipt,
                                          fact_id=self.fact("receipt"))
        before = self.journal()
        conflicting = dict(receipt, endpoint_receipt_id="another-valid-looking-receipt")
        with self.assertRaises(p.ReceiptConflict):
            fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", conflicting,
                                              fact_id=self.fact("conflicting-receipt"))
        self.assertGreater(len(self.journal()), len(before))
        self.assertEqual(self.snapshot(fixture).state, "QUARANTINED")
        self.assertEqual(fixture["sink"].effect_count, 1)
        self.assertIn(receipt["endpoint_receipt_id"], v0.canonical(fixture["reader"].status()))

    def test_RP29_known_delivered_never_redispatches(self):
        fixture = self.ready()
        fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        self.assertEqual(self.snapshot(fixture).state, "KNOWN_DELIVERED")
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"),
                                "KNOWN_DELIVERED")
        self.assertEqual(self.snapshot(fixture).attempt_ids, ("attempt-1",))

    def test_RP30_unknown_never_redispatches(self):
        fixture = self.ready()
        self.prepare_dispatch(fixture)
        fixture["recorder"].outcome(fixture["delivery_id"], "attempt-1", "UNKNOWN", "LOCAL_SINK_OUTCOME_UNRESOLVED",
                                   fact_id=self.fact("unknown"))
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"),
                                "UNKNOWN")
        self.unchanged(lambda: fixture["recorder"].schedule_retry(
            fixture["delivery_id"], fixture["permit"], fact_id=self.fact("retry")))

    def test_RP31_missing_receipt_is_not_known_not_delivered(self):
        fixture = self.ready()
        self.prepare_dispatch(fixture)
        self.assertIsNone(fixture["sink"].status(self.snapshot(fixture).stable_adapter_request_id))
        fixture["worker"].reconcile(fixture["delivery_id"])
        self.assertEqual(self.snapshot(fixture).state, "UNKNOWN")
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"), "UNKNOWN")

    def test_RP32_lease_expiry_does_not_authorize_resend(self):
        fixture = self.ready()
        prepared = fixture["recorder"].prepare(self.snapshot(fixture), "attempt-1", fixture["permit"],
                                                  fact_id=self.fact("prepare"))
        dispatched = fixture["recorder"].dispatch(prepared, "attempt-1", fixture["permit"],
                                                   fact_id=self.fact("dispatch"))
        self.custodian.expire_ownership(fixture["delivery_id"], fact_id=self.fact("expire"))
        self.unchanged(lambda: fixture["recorder"].dispatch(dispatched, "attempt-1", fixture["permit"],
                                                          fact_id=self.fact("old-worker")))
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"))
        self.assertEqual(self.snapshot(fixture).attempt_ids, ("attempt-1",))

    def test_RP33_crash_after_sink_acceptance_reconciles_without_second_effect(self):
        fixture = self.ready()
        with mock.patch.object(fixture["worker"], "_after_deposit", side_effect=SimulatedProcessCrash):
            with self.assertRaises(SimulatedProcessCrash):
                fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        self.assertEqual(fixture["sink"].effect_count, 1)
        reopened = p.PilotCustodian(self.path, project_id="ACOS")
        reader = reopened.reader(fixture["scope"])
        recorder = reopened.recorder(fixture["scope"], reporting_principal="fixture-relay")
        sink = p.LocalPassiveSink(fixture["directory"], fixture["binding_id"], 1, fixture["recipient_digest"])
        recovered = p.RelayWorker(reader, recorder, sink, fixture["permit"])
        with mock.patch.object(sink, "deposit", wraps=sink.deposit) as deposit:
            recovered.reconcile(fixture["delivery_id"])
            deposit.assert_not_called()
        self.assertEqual(reader.read_delivery(fixture["delivery_id"]).state, "KNOWN_DELIVERED")
        self.assertEqual(sink.effect_count, 1)

    def test_RP34_commit_ack_loss_uses_fact_lookup_without_second_effect(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        original = self.custodian._writer._commit
        def commit_then_lose_ack(connection):
            original(connection)
            raise sqlite3.OperationalError("receipt commit ack lost")
        with mock.patch.object(self.custodian._writer, "_commit", side_effect=commit_then_lose_ack):
            with self.assertRaises((p.OutcomeUnknown, p.StoreBlocked)):
                fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", receipt,
                                                  fact_id="lost-commit-ack")
        self.assertIsNotNone(fixture["reader"].lookup_fact("lost-commit-ack"))
        before = self.journal()
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].reconcile(fixture["delivery_id"]), "KNOWN_DELIVERED")
        fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", receipt,
                                          fact_id="lost-commit-ack")
        self.assertEqual(self.journal(), before)
        self.assertEqual(fixture["sink"].effect_count, 1)

    def test_RP35_safe_retry_requires_full_frozen_predicate(self):
        fixture = self.ready()
        self.positive_rejection(fixture)
        denied = (
            replace(fixture["permit"], allow_retry=False),
            replace(fixture["permit"], expires_at="2000-01-01T00:00:00Z"),
            replace(fixture["permit"], max_attempts=1),
            replace(fixture["permit"], generation=2),
            replace(fixture["permit"], recipient_digest="sha256:" + "a" * 64),
        )
        for permit in denied:
            with self.subTest(permit=permit):
                self.unchanged(lambda: fixture["recorder"].schedule_retry(
                    fixture["delivery_id"], permit, fact_id=self.fact("denied-retry")))
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"))
        self.assertEqual(fixture["sink"].effect_count, 0)
        fixture["recorder"].schedule_retry(fixture["delivery_id"], fixture["permit"],
                                          fact_id=self.fact("allowed-retry"))
        self.custodian.revoke_binding(fixture["binding_id"], 1, fact_id=self.fact("revoke"))
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"))

    def test_RP36_safe_retry_uses_new_relay_attempt_only(self):
        fixture = self.ready()
        original = self.snapshot(fixture)
        self.positive_rejection(fixture)
        fixture["recorder"].schedule_retry(fixture["delivery_id"], fixture["permit"],
                                          fact_id=self.fact("retry"))
        fixture["worker"].deliver(fixture["delivery_id"], "attempt-2")
        current = self.snapshot(fixture)
        self.assertEqual(current.state, "KNOWN_DELIVERED")
        for name in ("artifact_id", "delivery_id", "envelope_digest", "binding_id", "generation",
                     "semantic_effect_request_digest", "stable_adapter_request_id", "envelope_json"):
            self.assertEqual(getattr(current, name), getattr(original, name), name)
        self.assertEqual(current.attempt_ids, ("attempt-1", "attempt-2"))
        self.assertEqual(current.artifact.execution_attempt_id, "opaque-execution-attempt")
        self.assertEqual(fixture["sink"].effect_count, 1)

    def test_RP37_context_mutation_rejected(self):
        fixture = self.ready()
        self.unchanged(lambda: p.RelayWorker(
            fixture["reader"], fixture["recorder"], fixture["sink"],
            replace(fixture["permit"], effect_class="CONTEXT_MUTATION")))
        self.assertEqual(fixture["sink"].effect_count, 0)

    def test_RP38_model_or_agent_invocation_rejected(self):
        fixture = self.ready()
        self.unchanged(lambda: p.RelayWorker(
            fixture["reader"], fixture["recorder"], fixture["sink"],
            replace(fixture["permit"], effect_class="MODEL_OR_AGENT_INVOCATION")))
        self.assertEqual(fixture["sink"].effect_count, 0)

    def test_RP39_no_governance_or_state_journal_authority_path(self):
        fixture = self.ready()
        fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        tables = {row[0] for row in self.sql("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("state_journal", tables)
        self.assertNotIn("governance_projection", tables)
        boundary = fixture["reader"].status()["boundary"]
        self.assertEqual(boundary["authority"], "NONE")
        self.assertFalse(boundary["execution_admission"])
        self.assertFalse(boundary["governance_acceptance"])
        self.assertEqual(boundary["activation"], "LOCKED")
        self.assertEqual(boundary["operational_entry"], "LOCKED")
        for component in (fixture["reader"], fixture["recorder"], fixture["worker"]):
            for name in ("execute", "invoke", "accept", "authorize", "state_writer", "writer", "_writer", "sql"):
                self.assertFalse(hasattr(component, name), (type(component).__name__, name))

    def test_RP40_no_network_or_real_agent_endpoint_path(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        forbidden = {"openai", "socket", "requests", "httpx", "urllib", "subprocess", "websockets", "grpc"}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported & forbidden)
        fixture = self.ready()
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
                mock.patch.object(urllib.request, "urlopen", side_effect=AssertionError("network forbidden")), \
                mock.patch.object(subprocess, "Popen", side_effect=AssertionError("process endpoint forbidden")):
            fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        self.assertEqual(fixture["sink"].effect_count, 1)
        self.deposit_bytes(fixture, self.snapshot(fixture))

    def test_regression_canonical_v0_is_loaded_without_semantic_copy(self):
        canonical = (ROOT / "scripts/acos-v2-coordination.py").resolve()
        self.assertEqual(Path(v0.__file__).resolve(), canonical.resolve())
        self.assertEqual(v0.FORMAT, "acos-v2-coordination/1")
        value = self.artifact.to_dict()
        self.assertEqual(v0.CoordinationArtifact.from_dict(value).to_json(), self.artifact.to_json())
        value["payload"]["body"].append("tampered")
        with self.assertRaises(v0.ArtifactRejected):
            v0.CoordinationArtifact.from_dict(value)

    def test_regression_v0_delivery_id_preserved(self):
        legacy_path = self.root / "legacy-comparison" / "coordination.db"
        legacy_path.parent.mkdir()
        legacy = v0.CoordinationStore.init(legacy_path, project_id="ACOS")
        expected = legacy.writer().publish(self.artifact, publisher=self.publisher, recipient=self.recipient)
        actual = self.publish()
        self.assertEqual(self.field(actual, "delivery_id"), expected.delivery_id)
        self.assertEqual(self.artifact.envelope_digest, expected.envelope_digest)

    def test_regression_unverified_local_receipt_cannot_be_legacy_ack(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        legacy_ack = dict(artifact_id=snapshot.artifact_id, delivery_id=snapshot.delivery_id,
                          envelope_digest=snapshot.envelope_digest, meaning="EXACT_CONTENT_RECEIPT",
                          authority="NONE", event_seq=99, event_hash="sha256:" + "a" * 64)
        self.unchanged(lambda: fixture["recorder"].record_receipt(
            fixture["delivery_id"], "attempt-1", legacy_ack, fact_id=self.fact("legacy-ack")))
        self.assertEqual(fixture["sink"].effect_count, 0)

    def test_regression_local_sink_reopen_and_detached_query(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        receipt["authority"] = "forged by caller"
        reopened = p.LocalPassiveSink(fixture["directory"], fixture["binding_id"], 1, fixture["recipient_digest"])
        queried = reopened.status(snapshot.stable_adapter_request_id)
        self.assertEqual(queried["authority"], "NONE")
        queried["endpoint_receipt_id"] = "caller changed copy"
        self.assertNotEqual(reopened.status(snapshot.stable_adapter_request_id)["endpoint_receipt_id"], queried["endpoint_receipt_id"])
        self.assertEqual(reopened.effect_count, 1)
        self.deposit_bytes(fixture, snapshot)

    def test_regression_transport_fact_lookup_is_detached(self):
        fixture = self.ready()
        fixture["recorder"].prepare(self.snapshot(fixture), "attempt-1", fixture["permit"], fact_id="lookup-test")
        fact = fixture["reader"].lookup_fact("lookup-test")
        self.assertIsInstance(fact, dict)
        fact["caller_mutation"] = "no durable effect"
        self.assertNotIn("caller_mutation", fixture["reader"].lookup_fact("lookup-test"))
        self.assertIsNone(fixture["reader"].lookup_fact("missing-fact"))

    def test_regression_fixture_sink_requires_explicit_empty_local_directory(self):
        missing = self.root / "absent-sink"
        with self.assertRaises((p.SinkRejected, p.StoreBlocked, p.Rejected)):
            p.LocalPassiveSink(missing, "b", 1, v0.digest(self.recipient.to_dict()))
        self.assertFalse(missing.exists())
        occupied = self.root / "occupied-sink"
        occupied.mkdir()
        historical = occupied / "keep.txt"
        historical.write_bytes(b"preserve me")
        with self.assertRaises((p.SinkRejected, p.StoreBlocked, p.Rejected)):
            p.LocalPassiveSink.init(occupied, "b", 1, v0.digest(self.recipient.to_dict()))
        self.assertEqual(historical.read_bytes(), b"preserve me")

    def test_regression_scoped_status_and_fact_lookup_do_not_leak_other_destination(self):
        fixture = self.ready()
        other_recipient = replace(
            self.recipient, receiver_id="other-fixture", consumer_id="other-consumer",
            principal_id="other-principal", conversation_id="other-chat", session_id="other-session")
        other_artifact = self.make_artifact(
            artifact_id="other-artifact", receiver_id=other_recipient.receiver_id,
            payload={"private-other-destination": "must not leak through scoped read"})
        other = self.ready(suffix="-other", artifact=other_artifact, recipient=other_recipient)
        other["recorder"].prepare(self.snapshot(other), "other-attempt", other["permit"],
                                  fact_id="private-other-fact")
        scoped = v0.canonical(fixture["reader"].status())
        self.assertNotIn("other-artifact", scoped)
        self.assertNotIn("private-other-destination", scoped)
        try:
            fact = fixture["reader"].lookup_fact("private-other-fact")
        except p.ScopeDenied:
            pass
        else:
            self.assertIsNone(fact)

    def test_regression_sink_status_detects_exact_deposit_corruption(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        fixture["sink"].deposit(snapshot, "attempt-1")
        deposit = self.deposit_bytes(fixture, snapshot)
        deposit.write_bytes(b"tampered exact-content deposit")
        before = deposit.read_bytes()
        with self.assertRaises((p.SinkRejected, p.StoreBlocked, p.Rejected)):
            fixture["sink"].status(snapshot.stable_adapter_request_id)
        self.assertEqual(deposit.read_bytes(), before)

    def test_regression_sink_reopen_rejects_target_substitution(self):
        fixture = self.ready()
        for arguments in (("other-binding", 1, fixture["recipient_digest"]),
                          (fixture["binding_id"], 2, fixture["recipient_digest"]),
                          (fixture["binding_id"], 1, "sha256:" + "b" * 64)):
            with self.subTest(arguments=arguments), self.assertRaises((p.SinkRejected, p.StoreBlocked, p.Rejected)):
                p.LocalPassiveSink(fixture["directory"], *arguments)

    def test_regression_late_unknown_from_old_attempt_blocks_fresh_new_dispatch(self):
        fixture = self.ready()
        self.positive_rejection(fixture, "attempt-1")
        fixture["recorder"].schedule_retry(fixture["delivery_id"], fixture["permit"],
                                          fact_id=self.fact("retry"))
        fixture["recorder"].prepare(self.snapshot(fixture), "attempt-2", fixture["permit"],
                                   fact_id=self.fact("prepare-second"))
        fixture["recorder"].reconcile(fixture["delivery_id"], "attempt-1", "UNKNOWN",
                                      fact_id=self.fact("old-attempt-unknown"))
        current = self.snapshot(fixture)
        self.assertEqual(current.state, "UNKNOWN")
        self.assertEqual(current.attempt_ids, ("attempt-1", "attempt-2"))
        self.unchanged(lambda: fixture["recorder"].dispatch(
            current, "attempt-2", fixture["permit"], fact_id=self.fact("new-intent")))
        self.assertFalse(fixture["reader"].read_attempt("attempt-2")["intent"])
        self.assertEqual(fixture["sink"].effect_count, 0)

    def test_regression_late_old_receipt_blocks_fresh_new_dispatch(self):
        fixture = self.ready()
        original = self.prepare_dispatch(fixture, "attempt-1")
        fixture["recorder"].outcome(
            fixture["delivery_id"], "attempt-1", "KNOWN_NOT_DELIVERED",
            "LOCAL_SINK_PRE_EFFECT_REJECTION", fact_id=self.fact("negative-evidence"))
        fixture["recorder"].schedule_retry(fixture["delivery_id"], fixture["permit"],
                                          fact_id=self.fact("retry"))
        fixture["recorder"].prepare(self.snapshot(fixture), "attempt-2", fixture["permit"],
                                   fact_id=self.fact("prepare-second"))
        # A controlled late observation contradicts the earlier negative fact.
        # Preserve both contradictory observations and block the new effect.
        receipt = fixture["sink"].deposit(original, "attempt-1")
        with self.assertRaises(p.ReceiptConflict):
            fixture["recorder"].reconcile(fixture["delivery_id"], "attempt-1", "KNOWN_DELIVERED",
                                          receipt=receipt, fact_id=self.fact("late-receipt"))
        current = self.snapshot(fixture)
        self.assertEqual(current.state, "QUARANTINED")
        evidence = fixture["reader"].status()["deliveries"][fixture["delivery_id"]]
        self.assertIn(receipt, evidence["quarantine"])
        self.unchanged(lambda: fixture["recorder"].dispatch(
            current, "attempt-2", fixture["permit"], fact_id=self.fact("new-intent")))
        self.assertFalse(fixture["reader"].read_attempt("attempt-2")["intent"])
        self.assertEqual(fixture["sink"].effect_count, 1)
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"),
                                "QUARANTINED")

    def test_regression_receipt_conflict_blocks_all_new_intents(self):
        fixture = self.ready()
        fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        receipt = fixture["sink"].status(self.snapshot(fixture).stable_adapter_request_id)
        self.assertEqual(self.snapshot(fixture).state, "KNOWN_DELIVERED")
        conflicting = dict(receipt, endpoint_receipt_id="receipt:conflicting-evidence")
        with self.assertRaises(p.ReceiptConflict):
            fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", conflicting,
                                              fact_id=self.fact("receipt-conflict"))
        current = self.snapshot(fixture)
        self.assertEqual(current.state, "QUARANTINED")
        original_intents = self.sql("SELECT COUNT(*) FROM coordination_events WHERE kind='DISPATCH_INTENT'")[0][0]
        self.unchanged(lambda: fixture["recorder"].prepare(
            current, "attempt-2", fixture["permit"], fact_id=self.fact("new-prepare")))
        self.unchanged(lambda: fixture["recorder"].dispatch(
            current, "attempt-1", fixture["permit"], fact_id=self.fact("new-intent")))
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"),
                                "QUARANTINED")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM coordination_events WHERE kind='DISPATCH_INTENT'")[0][0],
                         original_intents)
        evidence = fixture["reader"].status()["deliveries"][fixture["delivery_id"]]
        self.assertEqual(evidence["receipt"], receipt)
        self.assertIn(conflicting, evidence["quarantine"])
        self.assertEqual(fixture["sink"].effect_count, 1)

    def test_regression_exact_dispatch_fact_replay_is_not_fresh_permission(self):
        fixture = self.ready()
        initial = self.snapshot(fixture)
        self.assertFalse(initial.dispatch_committed_now)
        prepared = fixture["recorder"].prepare(initial, "attempt-1", fixture["permit"],
                                               fact_id="replay-prepare")
        committed = fixture["recorder"].dispatch(prepared, "attempt-1", fixture["permit"],
                                                 fact_id="replay-intent")
        self.assertTrue(committed.dispatch_committed_now)
        self.assertFalse(self.snapshot(fixture).dispatch_committed_now)
        self.custodian.revoke_binding(fixture["binding_id"], 1, fact_id=self.fact("revoke"))
        before = self.journal()
        replayed = fixture["recorder"].dispatch(prepared, "attempt-1", fixture["permit"],
                                                fact_id="replay-intent")
        self.assertFalse(replayed.dispatch_committed_now)
        self.assertEqual(self.journal(), before)
        self.assertEqual(fixture["reader"].lookup_fact("replay-intent")["kind"], "DISPATCH_INTENT")
        self.assertEqual(replayed.delivery_id, committed.delivery_id)
        self.assertEqual(replayed.semantic_effect_request_digest, committed.semantic_effect_request_digest)
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-1"))

    def test_regression_receipt_commit_rollback_reconciles_without_second_deposit(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        journal_before = self.journal()
        def fail_before_commit(connection):
            self.assertTrue(connection.in_transaction)
            raise sqlite3.OperationalError("receipt commit never reached durable commit")
        with mock.patch.object(self.custodian._writer, "_commit", side_effect=fail_before_commit):
            with self.assertRaises((p.OutcomeUnknown, p.StoreBlocked)):
                fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", receipt,
                                                  fact_id="rolled-back-receipt")
        self.assertIsNone(fixture["reader"].lookup_fact("rolled-back-receipt"))
        self.assertEqual(self.journal(), journal_before)
        self.assertEqual(self.snapshot(fixture).state, "UNKNOWN")
        self.assertEqual(fixture["sink"].effect_count, 1)
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].reconcile(fixture["delivery_id"]), "KNOWN_DELIVERED")
        observed = fixture["reader"].status()["deliveries"][fixture["delivery_id"]]["receipt"]
        self.assertEqual(observed, receipt)
        self.assertEqual(fixture["sink"].effect_count, 1)

    def test_regression_cross_delivery_endpoint_receipt_conflict_preserves_evidence(self):
        first = self.ready()
        first["worker"].deliver(first["delivery_id"], "attempt-first")
        first_receipt = first["sink"].status(self.snapshot(first).stable_adapter_request_id)
        second_artifact = self.make_artifact(artifact_id="artifact-2", payload={"body": "second inert artifact"})
        second = self.ready(suffix="-second", artifact=second_artifact)
        second_snapshot = self.prepare_dispatch(second, "attempt-second")
        second_receipt = second["sink"].deposit(second_snapshot, "attempt-second")
        conflicting = dict(second_receipt, endpoint_receipt_id=first_receipt["endpoint_receipt_id"])
        with self.assertRaises(p.ReceiptConflict):
            second["recorder"].record_receipt(second["delivery_id"], "attempt-second", conflicting,
                                             fact_id="cross-delivery-receipt-conflict")
        second_state = second["reader"].status()["deliveries"][second["delivery_id"]]
        self.assertEqual(second_state["state"], "QUARANTINED")
        self.assertIsNone(second_state["receipt"])
        self.assertIn(conflicting, second_state["quarantine"])
        self.assertEqual(second["reader"].lookup_fact("cross-delivery-receipt-conflict")["kind"],
                         "RECEIPT_CONFLICT_QUARANTINED")
        first_state = first["reader"].status()["deliveries"][first["delivery_id"]]
        self.assertEqual(first_state["state"], "KNOWN_DELIVERED")
        self.assertEqual(first_state["receipt"], first_receipt)
        self.assertEqual(first["sink"].effect_count, 1)
        self.assertEqual(second["sink"].effect_count, 1)
        self.assert_no_dispatch(second, lambda: second["worker"].deliver(second["delivery_id"], "another-attempt"),
                                "QUARANTINED")

    def test_regression_rehashed_illegal_effect_fact_is_semantically_blocked(self):
        self.ready()
        events = [v0.CoordinationEvent(*row) for row in self.journal()]
        for (name,) in self.sql("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='coordination_events'"):
            self.sql('DROP TRIGGER "' + name.replace('"', '""') + '"')
        previous = v0.GENESIS_HASH
        for event in events:
            body = event.body
            if event.kind == "BINDING_CREATED":
                body["data"]["effect_class"] = "MODEL_OR_AGENT_INVOCATION"
            changed = replace(event, body_json=v0.canonical(body), previous_hash=previous)
            changed = replace(changed, event_hash=changed.calculated_hash())
            self.sql("UPDATE coordination_events SET body_json=?,previous_hash=?,event_hash=? WHERE seq=?",
                     (changed.body_json, changed.previous_hash, changed.event_hash, changed.seq))
            previous = changed.event_hash
        for definition in p.SCHEMA:
            if definition.startswith("CREATE TRIGGER events_"):
                self.sql(definition)
        with self.assertRaisesRegex(p.StoreBlocked, "semantic replay failed"):
            p.PilotCustodian(self.path, project_id="ACOS")
        self.unchanged(lambda: p.PilotCustodian(self.path, project_id="ACOS"), (p.StoreBlocked,))

    def test_regression_revoked_historical_receipt_preserved_without_new_effect(self):
        fixture = self.ready()
        snapshot = self.prepare_dispatch(fixture)
        receipt = fixture["sink"].deposit(snapshot, "attempt-1")
        self.custodian.revoke_binding(fixture["binding_id"], 1, fact_id=self.fact("revoke"))
        self.assertEqual(self.snapshot(fixture).state, "UNKNOWN")
        fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", receipt,
                                          fact_id=self.fact("late-receipt"))
        evidence = fixture["reader"].status()["deliveries"][fixture["delivery_id"]]
        self.assertEqual(evidence["state"], "KNOWN_DELIVERED")
        self.assertTrue(evidence["late_receipt"])
        self.assertEqual(evidence["receipt"], receipt)
        binding = next(iter(fixture["reader"].status()["bindings"].values()))
        self.assertTrue(binding["revoked"])
        self.assert_no_dispatch(fixture, lambda: fixture["worker"].deliver(fixture["delivery_id"], "attempt-2"),
                                "KNOWN_DELIVERED")
        self.assertEqual(fixture["sink"].effect_count, 1)

    def test_regression_quarantine_exact_replay_returns_original_evidence(self):
        fixture = self.ready()
        fixture["worker"].deliver(fixture["delivery_id"], "attempt-1")
        receipt = fixture["sink"].status(self.snapshot(fixture).stable_adapter_request_id)
        conflicting = dict(receipt, endpoint_receipt_id="receipt:conflicting-evidence")
        with self.assertRaises(p.ReceiptConflict) as first:
            fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", conflicting,
                                              fact_id="conflict-identity")
        before = self.journal()
        for fact_id in ("conflict-identity", "same-observation-new-fact-id"):
            with self.subTest(fact_id=fact_id), self.assertRaises(p.ReceiptConflict) as replay:
                fixture["recorder"].record_receipt(fixture["delivery_id"], "attempt-1", conflicting,
                                                  fact_id=fact_id)
            self.assertEqual(replay.exception.original_fact, first.exception.original_fact)
            self.assertEqual(self.journal(), before)
        self.assertEqual(self.snapshot(fixture).state, "QUARANTINED")
        self.assertEqual(fixture["sink"].effect_count, 1)


if __name__ == "__main__":
    unittest.main()

"""CO-01--CO-50 and regressions: isolated non-authoritative local transport.

All stores and JSON files live under harness-owned TemporaryDirectory roots.
Fault injection tests simulate interruptions and unknown commit acknowledgements;
no test claims production authentication, real power-loss proof or execution
admission. This suite neither loads nor changes existing ACOS implementations.
"""

import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stdout, redirect_stderr
from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
import importlib.util
import io
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/acos-v2-coordination.py"
spec = importlib.util.spec_from_file_location("acos_v2_coordination", SOURCE)
c = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = c
spec.loader.exec_module(c)


class InterruptedWrite(BaseException):
    pass


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        owned = tempfile.TemporaryDirectory(prefix="acos-coordination-test-")
        self.addCleanup(owned.cleanup)
        self.root = Path(owned.name)
        self.path = self.root / "coordination.db"
        self.store = c.CoordinationStore.init(self.path, project_id="ACOS")
        self.writer = self.store.writer()
        self.publisher = c.LocalIdentity("Codex Executor", "executor-endpoint", "executor-consumer", "test-executor", "codex-chat", "session-e")
        self.recipient = c.LocalIdentity("ChatGPT Review", "review-endpoint", "review-consumer", "test-reviewer", "review-chat", "session-r")
        self.artifact = self.make_artifact()

    def make_artifact(self, **overrides):
        values = dict(artifact_id="artifact-1", artifact_type="RESULT", project_id="ACOS", stage_id="stage-test",
                      task_id="task-test", from_role="Codex Executor", to_role="ChatGPT Review", receiver_id="review-endpoint",
                      correlation_id="exchange-1", created_at="2026-10-04T00:00:00Z", payload={"result": "test only", "n": 7},
                      execution_attempt_id="opaque-attempt", authority_reference="opaque-reference", baseline_revision="opaque-revision")
        values.update(overrides)
        return c.CoordinationArtifact.build(**values)

    def publish(self, artifact=None, **overrides):
        return self.writer.publish(self.artifact if artifact is None else artifact,
                                   publisher=overrides.get("publisher", self.publisher), recipient=overrides.get("recipient", self.recipient))

    def ack(self, receipt=None, **overrides):
        receipt = self.publish() if receipt is None else receipt
        values = dict(artifact_id=receipt.artifact_id, delivery_id=receipt.delivery_id, consumer_id=self.recipient.consumer_id,
                      envelope_digest=receipt.envelope_digest, consumer=self.recipient)
        values.update(overrides)
        return self.writer.ack(**values)

    def reopen(self):
        return c.CoordinationStore(self.path, project_id="ACOS")

    def sql(self, statement, parameters=()):
        with closing(sqlite3.connect(self.path)) as connection:
            result = connection.execute(statement, parameters).fetchall()
            connection.commit()
            return result

    def bytes(self):
        return self.path.read_bytes()

    def child(self, parent=None, **overrides):
        parent = self.artifact if parent is None else parent
        values = dict(artifact_id="reply-1", reply_to_artifact_id=parent.artifact_id, reply_to_digest=parent.envelope_digest,
                      predecessor_artifact_id=parent.artifact_id, artifact_type="RESULT")
        values.update(overrides)
        return self.make_artifact(**values)

    def assert_rejected_without_write(self, operation):
        before = self.bytes()
        with self.assertRaises((c.ArtifactRejected, c.StoreBlocked)):
            operation()
        self.assertEqual(before, self.bytes())

    def cli(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = c.main(["--db", str(self.path), "--project-id", "ACOS", *args])
        return result, stdout.getvalue(), stderr.getvalue()

    def identity_file(self, name, identity):
        path = self.root / name
        path.write_text(c.canonical(identity.to_dict()), encoding="utf-8")
        return str(path)

    def test_CO01_canonical_artifact_construction(self):
        a = self.artifact
        self.assertEqual(c.CoordinationArtifact.from_json(a.to_json()), a)
        self.assertEqual(c.canonical(a.to_dict()), a.to_json())
        with self.assertRaises(FrozenInstanceError):
            a.artifact_id = "mutable"
        a.payload["result"] = "mutated detached copy"
        self.assertEqual(a.payload["result"], "test only")

    def test_CO02_malformed_artifact_rejected(self):
        for values in (dict(artifact_id=""), dict(schema_version=True), dict(created_at="yesterday"),
                       dict(delivery_policy="EXECUTE"), dict(reply_to_artifact_id="unknown"),
                       dict(expires_at="2026-10-03T00:00:00Z"), dict(metadata=[])):
            with self.subTest(values=values), self.assertRaises(c.ArtifactRejected):
                self.make_artifact(**values)
        value = self.artifact.to_dict()
        value["authority"] = "APPROVED"
        with self.assertRaises(c.ArtifactRejected):
            c.CoordinationArtifact.from_dict(value)

    def test_CO03_duplicate_json_keys_rejected(self):
        for text in ('{"artifact_id":"a","artifact_id":"a"}', '{"payload":{"x":1,"x":1}}'):
            with self.subTest(text=text), self.assertRaises(c.ArtifactRejected):
                c.CoordinationArtifact.from_json(text)

    def test_CO04_payload_digest_deterministic(self):
        self.assertEqual(self.make_artifact(payload={"a": 1, "b": [2]}).payload_digest,
                         self.make_artifact(payload={"b": [2], "a": 1}).payload_digest)
        self.assertNotEqual(self.artifact.payload_digest, self.make_artifact(payload={"result": "different"}).payload_digest)

    def test_CO05_envelope_digest_covers_routing_payload(self):
        for change in (dict(receiver_id="another-endpoint"), dict(to_role="Other"), dict(payload={"new": 1}),
                       dict(authority_reference="other"), dict(metadata={"x": 1}), dict(session_note="invalid")):
            if "session_note" in change:
                with self.assertRaises(TypeError):
                    self.make_artifact(**change)
            else:
                self.assertNotEqual(self.artifact.envelope_digest, self.make_artifact(**change).envelope_digest)

    def test_CO06_explicit_init_creates_store(self):
        self.assertTrue(self.path.is_file())
        self.assertEqual(self.sql("PRAGMA user_version"), [(c.SCHEMA_VERSION,)])
        self.assertEqual(self.sql("SELECT format,assurance,authentication FROM coordination_metadata"),
                         [(c.FORMAT, c.ASSURANCE, c.AUTHENTICATION)])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_CO07_read_does_not_create_missing_store(self):
        missing = self.root / "missing" / "coordination.db"
        with self.assertRaises(c.StoreBlocked):
            c.CoordinationStore(missing, project_id="ACOS")
        self.assertFalse(missing.parent.exists())
        self.path.unlink()
        with self.assertRaises(c.StoreBlocked):
            self.store.read("artifact-1")
        self.assertFalse(self.path.exists())

    def test_CO08_reopen_validates_metadata_schema(self):
        receipt = self.publish()
        self.assertEqual(self.reopen().read(receipt.artifact_id), self.artifact)
        self.sql("PRAGMA user_version=2")
        before = self.bytes()
        with self.assertRaises(c.StoreBlocked):
            self.reopen()
        self.assertEqual(before, self.bytes())

    def test_CO09_corrupt_metadata_fails_closed(self):
        self.sql("DROP TRIGGER coordination_metadata_no_update")
        self.sql("UPDATE coordination_metadata SET assurance='AUTHENTICATED'")
        self.sql(c.SCHEMA[6])
        self.assert_rejected_without_write(self.reopen)

    def test_CO10_projection_mismatch_fails_closed(self):
        self.publish()
        self.sql("UPDATE artifact_projection SET reply_state='LINKED'")
        self.assert_rejected_without_write(self.reopen)
        self.assert_rejected_without_write(lambda: self.publish(self.make_artifact(artifact_id="new")))

    def test_CO11_publish_appends_event(self):
        receipt = self.publish()
        self.assertEqual(receipt.event_seq, 1)
        self.assertEqual(self.sql("SELECT kind FROM coordination_events"), [("PUBLISHED",)])
        self.assertEqual(self.store.status()["journal_head"], receipt.event_hash)

    def test_CO12_publish_creates_artifact_projection(self):
        receipt = self.publish()
        row = self.store.status()["artifacts"][0]
        self.assertEqual(row["envelope_json"], self.artifact.to_json())
        self.assertEqual(row["published_hash"], receipt.event_hash)
        self.assertEqual(row["publisher_json"], c.canonical(self.publisher.to_dict()))

    def test_CO13_publish_creates_delivery_projection(self):
        receipt = self.publish()
        row = self.store.inbox(self.recipient.receiver_id)[0]
        self.assertEqual(row["delivery_id"], receipt.delivery_id)
        self.assertEqual(row["envelope_digest"], receipt.envelope_digest)
        self.assertEqual(row["transport_state"], "AVAILABLE")
        self.assertEqual(row["recipient_json"], c.canonical(self.recipient.to_dict()))

    def test_CO14_exact_replay_returns_prior_receipt(self):
        receipt = self.publish()
        before = self.bytes()
        self.assertEqual(self.publish(), receipt)
        self.assertEqual(self.reopen().writer().publish(self.artifact, publisher=self.publisher, recipient=self.recipient), receipt)
        self.assertEqual(self.store.status()["event_count"], 1)
        self.assertEqual(before, self.bytes())

    def test_CO15_same_id_different_payload_conflict(self):
        self.publish()
        with self.assertRaises(c.PublicationConflict) as caught:
            self.publish(self.make_artifact(payload={"changed": True}))
        self.assertEqual(caught.exception.reason, "ARTIFACT_ID_CONFLICT")
        self.assertEqual(self.store.read("artifact-1"), self.artifact)

    def test_CO16_same_id_different_envelope_conflict(self):
        self.publish()
        with self.assertRaises(c.PublicationConflict):
            self.publish(self.make_artifact(task_id="changed-task"))
        self.assertEqual(self.store.status()["event_count"], 2)

    def test_CO17_inbox_scoped_by_receiver(self):
        self.publish()
        other = replace(self.recipient, receiver_id="other-receiver")
        self.publish(self.make_artifact(artifact_id="other", receiver_id=other.receiver_id), recipient=other)
        self.assertEqual(len(self.store.inbox(self.recipient.receiver_id)), 1)
        self.assertEqual(self.store.inbox("unknown"), [])
        self.assertEqual(self.store.inbox(self.recipient.receiver_id, consumer=replace(self.recipient, principal_id="other")), [])

    def test_CO18_outbox_scoped_by_publisher(self):
        self.publish()
        other = replace(self.publisher, principal_id="other-publisher")
        self.publish(self.make_artifact(artifact_id="other"), publisher=other)
        self.assertEqual(len(self.store.outbox(self.publisher)), 1)
        self.assertEqual(len(self.store.outbox(other)), 1)

    def test_CO19_read_is_side_effect_free(self):
        self.publish()
        before = self.bytes()
        entries = sorted(p.name for p in self.root.iterdir())
        self.store.read("artifact-1")
        self.store.read("missing")
        self.store.inbox(self.recipient.receiver_id)
        self.store.outbox(self.publisher)
        self.store.status()
        self.assertEqual(self.bytes(), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), entries)
        self.assertEqual(self.store.status()["deliveries"][0]["transport_state"], "AVAILABLE")

    def test_CO20_status_transport_only(self):
        self.publish()
        state = self.store.status()
        self.assertEqual(state["boundary"]["authority"], "NONE")
        self.assertFalse(state["boundary"]["execution_admission"])
        self.assertNotIn("governance_state", state)
        self.assertEqual(state["boundary"]["delivery_semantics"], "LOCAL_AVAILABILITY")

    def test_CO21_exact_digest_ack_succeeds(self):
        receipt = self.publish()
        ack = self.ack(receipt)
        self.assertEqual((ack.artifact_id, ack.delivery_id, ack.consumer_id, ack.envelope_digest),
                         (receipt.artifact_id, receipt.delivery_id, self.recipient.consumer_id, receipt.envelope_digest))
        self.assertEqual(self.store.status()["deliveries"][0]["transport_state"], "ACKED")
        self.assertEqual(self.store.inbox(self.recipient.receiver_id), [])
        self.assertEqual(len(self.store.inbox(self.recipient.receiver_id, include_acked=True)), 1)

    def test_CO22_wrong_consumer_ack_rejected(self):
        receipt = self.publish()
        other = replace(self.recipient, consumer_id="wrong")
        self.assert_rejected_without_write(lambda: self.ack(receipt, consumer_id="wrong", consumer=other))

    def test_CO23_wrong_digest_ack_rejected(self):
        receipt = self.publish()
        self.assert_rejected_without_write(lambda: self.ack(receipt, envelope_digest="sha256:" + "f" * 64))

    def test_CO24_exact_ack_idempotent(self):
        receipt = self.publish()
        ack = self.ack(receipt)
        before = self.bytes()
        self.assertEqual(self.ack(receipt), ack)
        self.assertEqual(self.bytes(), before)
        self.assertEqual(self.store.status()["event_count"], 2)

    def test_CO25_ACK_artifact_is_not_receipt(self):
        self.publish(self.make_artifact(artifact_type="ACK", payload={"accepted": True}))
        self.assertEqual(self.store.status()["deliveries"][0]["transport_state"], "AVAILABLE")
        self.assertEqual(self.sql("SELECT kind FROM coordination_events"), [("PUBLISHED",)])

    def test_CO26_reply_links_direct_parent(self):
        self.publish()
        child = self.child()
        receipt = self.writer.reply(child, publisher=self.publisher, recipient=self.recipient)
        status = self.store.status(receipt.artifact_id)
        self.assertEqual(status["artifacts"][0]["reply_state"], "LINKED")
        self.assertEqual(self.store.read(receipt.artifact_id).reply_to_digest, self.artifact.envelope_digest)

    def test_CO27_correlation_chain_preserved(self):
        self.publish()
        child = self.child()
        self.publish(child)
        grandchild = self.child(child, artifact_id="reply-2", predecessor_artifact_id=self.artifact.artifact_id)
        self.publish(grandchild)
        actual = self.store.read("reply-2")
        self.assertEqual((actual.correlation_id, actual.reply_to_artifact_id, actual.predecessor_artifact_id),
                         ("exchange-1", "reply-1", "artifact-1"))
        self.assertNotEqual(actual.reply_to_artifact_id, actual.predecessor_artifact_id)

    def test_CO28_missing_parent_pending_no_fabrication(self):
        self.publish(self.child())
        status = self.store.status()
        self.assertEqual(status["artifacts"][0]["reply_state"], "PENDING")
        self.assertEqual(status["artifacts"][0]["predecessor_state"], "PENDING")
        self.assertIsNone(self.store.read("artifact-1"))
        self.assertEqual(len(status["artifacts"]), 1)

    def test_CO29_parent_arrival_resolves_pending(self):
        child = self.child()
        original = self.publish(child)
        self.publish()
        row = self.reopen().status(child.artifact_id)["artifacts"][0]
        self.assertEqual((row["reply_state"], row["predecessor_state"]), ("LINKED", "LINKED"))
        self.assertEqual(self.publish(child), original)
        self.assertEqual(self.store.read(child.artifact_id), child)

    def test_CO30_cross_project_parent_rejected(self):
        foreign_dir = self.root / "foreign"
        foreign_dir.mkdir()
        foreign = c.CoordinationStore.init(foreign_dir / "coordination.db", project_id="OTHER")
        parent = self.make_artifact(project_id="OTHER")
        foreign.writer().publish(parent, publisher=self.publisher, recipient=self.recipient)
        self.assert_rejected_without_write(lambda: self.publish(self.child(parent, project_id="OTHER")))
        self.assert_rejected_without_write(lambda: c.CoordinationStore(self.path, project_id="OTHER"))
        self.publish()
        # A foreign parent digest cannot bind to a same-ID local artifact.
        with self.assertRaises(c.PublicationConflict):
            self.publish(self.child(parent, project_id="ACOS"))
        self.assertIsNone(self.store.read("reply-1"))

    def test_CO31_duplicate_delivery_no_new_attempt(self):
        first = self.publish()
        self.assertEqual(self.publish().delivery_id, first.delivery_id)
        self.assertEqual(self.store.read(first.artifact_id).execution_attempt_id, "opaque-attempt")
        self.assertEqual(len(self.store.status()["deliveries"]), 1)

    def test_CO32_redelivery_not_reexecution(self):
        receipt = self.publish()
        self.ack(receipt)
        self.assertEqual(self.publish(), receipt)
        self.assertEqual(self.store.status()["event_count"], 2)
        self.assertFalse(self.store.status()["boundary"]["redelivery_is_reexecution"])

    def test_CO33_ACK_not_ACCEPT(self):
        ack = self.ack()
        self.assertEqual(ack.meaning, "EXACT_CONTENT_RECEIPT")
        self.assertEqual(ack.authority, "NONE")
        self.assertFalse(self.store.status()["boundary"]["ack_is_acceptance"])

    def test_CO34_DELIVERED_not_AUTHORIZED(self):
        receipt = self.publish(self.make_artifact(artifact_type="AUTHORIZATION", payload={"authorized": True}))
        self.ack(receipt)
        self.assertFalse(self.store.status()["boundary"]["delivery_is_authorization"])
        self.assertFalse(self.store.status()["boundary"]["governance_acceptance"])

    def test_CO35_RESULT_RECEIVED_not_ACCEPTED(self):
        self.ack()
        self.assertFalse(self.store.status()["boundary"]["result_is_acceptance"])
        self.assertEqual(self.store.read("artifact-1").artifact_type, "RESULT")

    def boundary_flow(self):
        receipt = self.publish()
        self.store.read(receipt.artifact_id)
        self.store.inbox(self.recipient.receiver_id)
        self.store.outbox(self.publisher)
        self.ack(receipt)
        self.publish(self.child())
        self.reopen().status()

    def forbidden_imports(self, names):
        tree = ast.parse(SOURCE.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    self.assertFalse(any(name in (node.module if isinstance(node, ast.ImportFrom) else alias.name) for name in names))
        with mock.patch("builtins.__import__", wraps=__import__) as imports:
            self.boundary_flow()
        self.assertFalse(any(any(name in call.args[0] for name in names) for call in imports.call_args_list))
        for name in names:
            self.assertNotIn(name, vars(c))

    def test_CO36_no_StateJournalWriter(self):
        self.forbidden_imports(("StateJournalWriter", "acos_v2_core", "acos-v2-core"))

    def test_CO37_no_TransitionEngine(self):
        self.forbidden_imports(("TransitionEngine", "StateStore"))

    def test_CO38_no_capability_issuance_consumption(self):
        self.forbidden_imports(("acos_v2_capability", "acos-v2-capability", "CapabilityIssuer", "CapabilityValidator"))
        self.assertFalse(hasattr(self.writer, "admit_execution"))

    def test_CO39_no_Git_invocation(self):
        with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("process invocation")) as popen, \
             mock.patch.object(subprocess, "run", side_effect=AssertionError("process invocation")) as run, \
             mock.patch.object(c.os, "system", side_effect=AssertionError("shell invocation")) as system:
            self.boundary_flow()
            self.cli("status")
        popen.assert_not_called()
        run.assert_not_called()
        system.assert_not_called()

    def test_CO40_no_network_invocation(self):
        with mock.patch.object(socket, "socket", side_effect=AssertionError("socket invocation")) as sock, \
             mock.patch.object(socket, "create_connection", side_effect=AssertionError("network invocation")) as conn:
            self.boundary_flow()
            self.cli("status")
        sock.assert_not_called()
        conn.assert_not_called()
        imported = {alias.name for node in ast.walk(ast.parse(SOURCE.read_text())) if isinstance(node, ast.Import) for alias in node.names}
        self.assertTrue(imported.isdisjoint({"socket", "urllib", "requests", "http", "subprocess"}))

    def test_CO41_interruption_before_commit_no_artifact(self):
        before = self.bytes()
        with mock.patch.object(c.CoordinationStore, "_commit", side_effect=InterruptedWrite):
            with self.assertRaises(InterruptedWrite):
                self.publish()
        self.assertEqual(self.bytes(), before)
        self.assertIsNone(self.reopen().read("artifact-1"))
        self.assertEqual(self.store.status()["event_count"], 0)

    def test_CO42_committed_publish_rediscovered_after_reopen(self):
        receipt = self.publish()
        self.assertEqual(self.reopen().writer().publish(self.artifact, publisher=self.publisher, recipient=self.recipient), receipt)

    def test_CO43_ACK_receipt_survives_reopen(self):
        receipt = self.publish()
        ack = self.ack(receipt)
        self.assertEqual(self.reopen().writer().ack(artifact_id=receipt.artifact_id, delivery_id=receipt.delivery_id,
            consumer_id=self.recipient.consumer_id, envelope_digest=receipt.envelope_digest, consumer=self.recipient), ack)

    def test_CO44_conflict_cannot_overwrite_original(self):
        receipt = self.publish()
        ack = self.ack(receipt)
        with self.assertRaises(c.PublicationConflict):
            self.publish(self.make_artifact(payload={"conflict": "new"}))
        self.assertEqual(self.reopen().read("artifact-1"), self.artifact)
        self.assertEqual(self.ack(receipt), ack)

    def test_CO45_quarantined_conflict_observable(self):
        self.publish()
        candidate = self.make_artifact(payload={"conflict": True})
        with self.assertRaises(c.PublicationConflict):
            self.publish(candidate)
        conflict = self.reopen().status("artifact-1")["conflicts"][0]
        self.assertEqual(conflict["candidate"]["artifact"], candidate.to_dict())
        self.assertEqual(conflict["reason"], "ARTIFACT_ID_CONFLICT")
        self.assertEqual(self.sql("SELECT kind FROM coordination_events ORDER BY seq"), [("PUBLISHED",), ("CONFLICT_QUARANTINED",)])

    def test_CO46_role_string_does_not_authenticate(self):
        self.publish(self.make_artifact(payload={"FROM": "ChatGPT Review", "authenticated": True}, metadata={"assurance": "PRODUCTION"}))
        row = self.store.status()["artifacts"][0]
        self.assertEqual(c.strict_json(row["publisher_json"])["principal_id"], "test-executor")
        self.assertEqual(c.strict_json(row["publisher_json"])["assurance"], "UNVERIFIED_LOCAL")
        with self.assertRaises(c.ArtifactRejected):
            replace(self.publisher, assurance="AUTHENTICATED")

    def test_CO47_UNVERIFIED_LOCAL_explicit(self):
        receipt = self.publish()
        self.assertEqual(receipt.assurance, "UNVERIFIED_LOCAL")
        self.assertEqual(self.store.status()["boundary"]["authentication"], "NOT PRODUCTION AUTHENTICATED")
        self.assertEqual(self.sql("SELECT authentication FROM coordination_metadata"), [("NOT PRODUCTION AUTHENTICATED",)])

    def test_CO48_payload_digest_creates_no_authority(self):
        receipt = self.publish(self.make_artifact(payload={"authority": "GRANTED"}))
        self.assertEqual(receipt.authority, "NONE")
        self.assertFalse(self.store.status()["boundary"]["execution_admission"])

    def test_CO49_receipt_no_execution_admission(self):
        receipt = self.publish()
        ack = self.ack(receipt)
        self.assertEqual(receipt.authority, ack.authority)
        self.assertFalse(self.store.status()["boundary"]["execution_admission"])
        self.assertFalse(hasattr(receipt, "capability"))

    def test_CO50_D08_boundary_explicit(self):
        parent = self.make_artifact(artifact_type="AUTHORIZATION")
        self.publish(parent)
        child = self.child(parent)
        self.publish(child)
        boundary = self.store.status()["boundary"]
        self.assertEqual(boundary["decision"], "D-08")
        self.assertEqual(boundary["activation"], "LOCKED")
        self.assertEqual(boundary["operational_entry"], "LOCKED")
        self.assertEqual(boundary["authority"], "NONE")
        self.assertNotIn("authorization", asdict(self.publish(child)))

    def test_R01_publisher_binding_drift_quarantined(self):
        self.publish()
        with self.assertRaises(c.PublicationConflict):
            self.publish(publisher=replace(self.publisher, principal_id="other"))
        self.assertEqual(self.reopen().status()["artifacts"][0]["publisher_json"], c.canonical(self.publisher.to_dict()))

    def test_R02_exact_replay_never_rebinds_recipient(self):
        original = self.publish()
        other = replace(self.recipient, session_id="new-session")
        before = self.bytes()
        self.assertEqual(self.publish(recipient=other), original)
        self.assertEqual(self.bytes(), before)
        self.assertEqual(len(self.store.status()["deliveries"]), 1)
        self.assertEqual(original.recipient_binding_digest, c.digest(self.recipient.to_dict()))
        self.assert_rejected_without_write(lambda: self.ack(original, consumer=other))

    def test_R03_all_consumer_binding_components_required(self):
        receipt = self.publish()
        for field in ("role", "receiver_id", "consumer_id", "principal_id", "conversation_id", "session_id"):
            other = replace(self.recipient, **{field: "wrong-binding"})
            with self.subTest(field=field):
                self.assert_rejected_without_write(lambda: self.ack(receipt, consumer_id=other.consumer_id, consumer=other))

    def test_R04_wrong_artifact_or_delivery_ack_rejected(self):
        receipt = self.publish()
        for override in (dict(artifact_id="wrong"), dict(delivery_id="wrong"), dict(consumer_id="wrong")):
            self.assert_rejected_without_write(lambda: self.ack(receipt, **override))

    def test_R05_direct_reply_digest_mismatch_quarantined(self):
        self.publish()
        with self.assertRaises(c.PublicationConflict) as caught:
            self.publish(self.child(reply_to_digest="sha256:" + "0" * 64))
        self.assertEqual(caught.exception.reason, "REPLY_DIGEST_MISMATCH")
        self.assertIsNone(self.store.read("reply-1"))

    def test_R06_late_wrong_parent_quarantines_relation(self):
        child = self.child(reply_to_digest="sha256:" + "0" * 64)
        receipt = self.publish(child)
        self.publish()
        row = self.reopen().status(child.artifact_id)["artifacts"][0]
        self.assertEqual(row["reply_state"], "QUARANTINED")
        self.assertEqual(row["predecessor_state"], "LINKED")
        self.assertEqual(self.store.read(child.artifact_id), child)
        self.assertEqual(self.publish(child), receipt)

    def test_R07_correlation_mismatch_quarantined(self):
        self.publish()
        with self.assertRaises(c.PublicationConflict) as caught:
            self.publish(self.child(correlation_id="different-chain"))
        self.assertEqual(caught.exception.reason, "REPLY_CORRELATION_MISMATCH")

    def test_R08_self_relation_rejected(self):
        with self.assertRaises(c.ArtifactRejected):
            self.make_artifact(predecessor_artifact_id="artifact-1")

    def test_R09_cycle_does_not_become_linked(self):
        first = self.make_artifact(predecessor_artifact_id="artifact-2")
        self.publish(first)
        with self.assertRaises(c.PublicationConflict) as caught:
            self.publish(self.make_artifact(artifact_id="artifact-2", predecessor_artifact_id="artifact-1"))
        self.assertEqual(caught.exception.reason, "RELATION_CYCLE")
        self.assertEqual(self.reopen().status("artifact-1")["artifacts"][0]["predecessor_state"], "PENDING")

    def test_R10_event_update_delete_append_only(self):
        self.publish()
        for statement in ("UPDATE coordination_events SET kind='ACK_RECORDED'", "DELETE FROM coordination_events"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.sql(statement)
        self.assertEqual(self.reopen().status()["event_count"], 1)

    def test_R11_journal_digest_tampering_fails_closed(self):
        self.publish()
        self.sql("DROP TRIGGER coordination_events_no_update")
        self.sql("UPDATE coordination_events SET event_hash=?", ("sha256:" + "0" * 64,))
        self.sql(c.SCHEMA[4])
        self.assert_rejected_without_write(self.reopen)

    def test_R12_journal_sequence_gap_fails_closed(self):
        self.publish()
        self.sql("DROP TRIGGER coordination_events_no_update")
        self.sql("UPDATE coordination_events SET seq=2")
        self.sql(c.SCHEMA[4])
        self.assert_rejected_without_write(self.reopen)

    def test_R13_delivery_projection_tampering_fails_closed(self):
        self.publish()
        self.sql("UPDATE delivery_projection SET transport_state='ACKED'")
        self.assert_rejected_without_write(self.reopen)

    def test_R14_extra_schema_objects_no_migration(self):
        self.sql("CREATE TABLE unexpected (x TEXT)")
        self.assert_rejected_without_write(self.reopen)

    def test_R15_missing_schema_trigger_no_repair(self):
        self.sql("DROP TRIGGER coordination_events_no_delete")
        self.assert_rejected_without_write(self.reopen)

    def test_R16_damaged_database_preserved(self):
        self.path.write_bytes(b"this is not SQLite")
        self.assert_rejected_without_write(self.reopen)

    def test_R17_init_never_overwrites_existing(self):
        self.publish()
        self.assert_rejected_without_write(lambda: c.CoordinationStore.init(self.path, project_id="ACOS"))

    def test_R18_reject_shared_or_symlink_database(self):
        with self.assertRaises(c.StoreBlocked):
            c.CoordinationStore.init(self.root / "state.db", project_id="ACOS")
        directory = self.root / "alias"
        directory.mkdir()
        alias = directory / "coordination.db"
        alias.symlink_to(self.path)
        with self.assertRaises(c.StoreBlocked):
            c.CoordinationStore(alias, project_id="ACOS")
        self.assertFalse((self.root / "state.db").exists())

    def test_R19_numeric_and_Unicode_rejections(self):
        for payload in ({"x": float("nan")}, {"x": 1.5}, {1: "invalid key"}, {"x": "\ud800"}):
            with self.subTest(payload=repr(payload)), self.assertRaises(c.ArtifactRejected):
                self.make_artifact(payload=payload)
        for text in ('{"x":NaN}', '{"x":Infinity}', '{"x":1.0}'):
            with self.assertRaises(c.ArtifactRejected):
                c.strict_json(text)

    def test_R20_claimed_digest_mismatch_rejected(self):
        for field in ("payload_digest", "envelope_digest"):
            data = self.artifact.to_dict()
            data[field] = "sha256:" + "0" * 64
            with self.assertRaises(c.ArtifactRejected):
                c.CoordinationArtifact.from_dict(data)

    def test_R21_unknown_commit_ack_reconciliation(self):
        def lost_ack(connection):
            connection.commit()
            raise c.MutationOutcomeUnknown("test commit acknowledgement lost")
        with mock.patch.object(c.CoordinationStore, "_commit", side_effect=lost_ack):
            with self.assertRaises(c.MutationOutcomeUnknown):
                self.publish()
        store = self.reopen()
        self.assertEqual(store.read("artifact-1"), self.artifact)
        self.assertEqual(store.status()["event_count"], 1)
        self.assertEqual(store.writer().publish(self.artifact, publisher=self.publisher, recipient=self.recipient).event_seq, 1)

    def test_R22_ACK_interruption_rollback(self):
        receipt = self.publish()
        before = self.bytes()
        with mock.patch.object(c.CoordinationStore, "_commit", side_effect=InterruptedWrite):
            with self.assertRaises(InterruptedWrite):
                self.ack(receipt)
        self.assertEqual(self.bytes(), before)
        self.assertEqual(self.reopen().status()["deliveries"][0]["transport_state"], "AVAILABLE")

    def test_R23_concurrent_publish_single_receipt(self):
        def publish(_):
            return c.CoordinationStore(self.path, project_id="ACOS").writer().publish(self.artifact, publisher=self.publisher, recipient=self.recipient)
        with ThreadPoolExecutor(max_workers=4) as executor:
            receipts = list(executor.map(publish, range(4)))
        self.assertTrue(all(receipt == receipts[0] for receipt in receipts))
        self.assertEqual(self.reopen().status()["event_count"], 1)

    def test_R24_concurrent_ACK_single_receipt(self):
        published = self.publish()
        def ack(_):
            return c.CoordinationStore(self.path, project_id="ACOS").writer().ack(artifact_id=published.artifact_id,
                delivery_id=published.delivery_id, envelope_digest=published.envelope_digest,
                consumer_id=self.recipient.consumer_id, consumer=self.recipient)
        with ThreadPoolExecutor(max_workers=4) as executor:
            receipts = list(executor.map(ack, range(4)))
        self.assertTrue(all(receipt == receipts[0] for receipt in receipts))
        self.assertEqual(self.reopen().status()["event_count"], 2)

    def test_R25_readonly_connection_query_only_settings(self):
        with self.store._transaction(False) as (connection, _):
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA synchronous").fetchone()[0], 2)
            self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], c.BUSY_TIMEOUT_MS)
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("DELETE FROM delivery_projection")

    def test_R26_writer_begins_immediate_and_rollback_atomic(self):
        original = c.CoordinationStore._connect
        trace = []
        def tracked(*args):
            connection = original(*args)
            connection.set_trace_callback(trace.append)
            return connection
        with mock.patch.object(c.CoordinationStore, "_connect", side_effect=tracked):
            self.publish()
        self.assertIn("BEGIN IMMEDIATE", trace)
        self.assertIn("COMMIT", trace)

    def test_R27_cli_init_publish_read_inbox_outbox_status_ack_reply(self):
        publisher = self.identity_file("publisher.json", self.publisher)
        recipient = self.identity_file("recipient.json", self.recipient)
        artifact_file = self.root / "artifact.json"
        artifact_file.write_text(self.artifact.to_json(), encoding="utf-8")
        self.path.unlink()
        self.assertEqual(self.cli("init")[0], 0)
        exit_code, output, error = self.cli("publish", "--artifact", str(artifact_file), "--publisher", publisher, "--recipient", recipient)
        self.assertEqual((exit_code, error), (0, ""))
        receipt = c.strict_json(output)["result"]
        before = self.bytes()
        for args in (("read", "artifact-1"), ("inbox", "--receiver-id", self.recipient.receiver_id),
                     ("outbox", "--publisher", publisher), ("status",)):
            code, out, err = self.cli(*args)
            self.assertEqual((code, err), (0, ""))
            self.assertEqual(c.strict_json(out)["boundary"]["authentication"], c.AUTHENTICATION)
        self.assertEqual(self.bytes(), before)
        self.assertEqual(self.cli("ack", "--artifact-id", receipt["artifact_id"], "--delivery-id", receipt["delivery_id"],
            "--consumer-id", self.recipient.consumer_id, "--envelope-digest", receipt["envelope_digest"], "--consumer", recipient)[0], 0)
        artifact_file.write_text(self.child().to_json(), encoding="utf-8")
        self.assertEqual(self.cli("reply", "--artifact", str(artifact_file), "--publisher", publisher, "--recipient", recipient)[0], 0)
        self.assertEqual(self.reopen().status()["event_count"], 3)

    def test_R28_cli_failure_diagnostic_preserves(self):
        self.sql("CREATE TABLE alien (x)")
        before = self.bytes()
        code, output, diagnostic = self.cli("status")
        self.assertEqual((code, output), (2, ""))
        self.assertEqual(c.strict_json(diagnostic)["error"], "StoreBlocked")
        self.assertEqual(before, self.bytes())

    def test_R29_partial_projection_write_rolls_back(self):
        original = c.CoordinationJournalWriter._persist
        def interrupted(connection, *args):
            original(connection, *args)
            raise InterruptedWrite()
        before = self.bytes()
        with mock.patch.object(c.CoordinationJournalWriter, "_persist", side_effect=interrupted):
            with self.assertRaises(InterruptedWrite):
                self.publish()
        self.assertEqual(before, self.bytes())
        self.assertEqual(self.reopen().status()["event_count"], 0)

    def test_R30_expired_reference_has_no_execution_semantics(self):
        artifact = self.make_artifact(expires_at="2026-10-04T00:00:01Z")
        self.publish(artifact)
        self.assertEqual(self.store.read("artifact-1").expires_at, artifact.expires_at)
        self.assertFalse(self.store.status()["boundary"]["execution_admission"])

    def test_R31_noncanonical_serialized_payload_rejected(self):
        with self.assertRaises(c.ArtifactRejected):
            replace(self.artifact, payload_json='{"b": 1, "a": 2}')

    def test_R32_size_and_depth_bounded(self):
        with self.assertRaises(c.ArtifactRejected):
            self.make_artifact(payload={"x": "a" * c.MAX_JSON_BYTES})
        value = 0
        for _ in range(66):
            value = [value]
        with self.assertRaises(c.ArtifactRejected):
            self.make_artifact(payload=value)

    def test_R33_metadata_and_session_immutable(self):
        artifact = self.make_artifact(metadata={"nested": {"session": "test"}})
        artifact.metadata["nested"]["session"] = "edited copy"
        self.assertEqual(artifact.metadata["nested"]["session"], "test")
        with self.assertRaises(FrozenInstanceError):
            self.recipient.session_id = "changed"

    def test_R34_busy_store_fails_closed_without_retry(self):
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            before = self.bytes()
            with self.assertRaises(c.StoreBlocked):
                self.publish()
            self.assertEqual(before, self.bytes())
            connection.rollback()
        self.assertEqual(self.reopen().status()["event_count"], 0)

    def test_R35_both_pending_relations_resolve_independently(self):
        parent = self.make_artifact(artifact_id="parent")
        child = self.child(parent, predecessor_artifact_id="dependency")
        self.publish(child)
        self.publish(parent)
        row = self.store.status(child.artifact_id)["artifacts"][0]
        self.assertEqual((row["reply_state"], row["predecessor_state"]), ("LINKED", "PENDING"))
        self.publish(self.make_artifact(artifact_id="dependency"))
        self.assertEqual(self.reopen().status(child.artifact_id)["artifacts"][0]["predecessor_state"], "LINKED")

    def test_R36_event_semantic_tampering_rehashed_still_blocked(self):
        self.publish()
        original = c.strict_json(self.sql("SELECT body_json FROM coordination_events")[0][0])
        original["delivery_id"] = "fabricated"
        row = self.sql("SELECT seq,kind,recorded_at,body_json,previous_hash,event_hash FROM coordination_events")[0]
        event = c.CoordinationEvent(row[0], row[1], row[2], c.canonical(original), row[4], row[5])
        self.sql("DROP TRIGGER coordination_events_no_update")
        self.sql("UPDATE coordination_events SET body_json=?,event_hash=?", (event.body_json, event.calculated_hash()))
        self.sql(c.SCHEMA[4])
        self.assert_rejected_without_write(self.reopen)

    def test_R37_init_failure_preserves_no_automatic_repair(self):
        directory = self.root / "partial"
        directory.mkdir()
        path = directory / "coordination.db"
        with mock.patch.object(c.CoordinationStore, "_commit", side_effect=InterruptedWrite):
            with self.assertRaises(InterruptedWrite):
                c.CoordinationStore.init(path, project_id="ACOS")
        self.assertTrue(path.exists())
        before = path.read_bytes()
        with self.assertRaises(c.StoreBlocked):
            c.CoordinationStore(path, project_id="ACOS")
        self.assertEqual(before, path.read_bytes())

    def test_R38_unknown_ACK_commit_does_not_auto_retry(self):
        receipt = self.publish()
        def lost_ack(connection):
            connection.commit()
            raise c.MutationOutcomeUnknown("test ACK acknowledgement lost")
        with mock.patch.object(c.CoordinationStore, "_commit", side_effect=lost_ack) as commit:
            with self.assertRaises(c.MutationOutcomeUnknown):
                self.ack(receipt)
            self.assertEqual(commit.call_count, 1)
        store = self.reopen()
        self.assertEqual(store.status()["event_count"], 2)
        self.assertEqual(store.status()["deliveries"][0]["transport_state"], "ACKED")


    def test_R39_SQL_replace_cannot_bypass_append_only(self):
        self.publish()
        before = self.bytes()
        for statement in (
            "INSERT OR REPLACE INTO coordination_events SELECT * FROM coordination_events",
            "INSERT OR REPLACE INTO coordination_metadata SELECT * FROM coordination_metadata",
        ):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                self.sql(statement)
        self.assertEqual(self.bytes(), before)
        self.assertEqual(self.reopen().status()["event_count"], 1)


if __name__ == "__main__":
    unittest.main()

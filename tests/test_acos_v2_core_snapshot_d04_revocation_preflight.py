"""DRI-01--06: unchanged verified Core with independent D04 invalidation.

Run only in a fresh pinned Python process with -I -S -B. The accepted Core
witness loads its guard-first harness before canonical modules/dependencies.
Fixture grant/state/clock are synthetic; no production issuer is implemented.
"""
from pathlib import Path
from contextlib import contextmanager, ExitStack
from dataclasses import replace
from datetime import timedelta
import copy
import importlib.util
import json
import sqlite3
import sys
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("dri_frozen_core_witness",
    ROOT / "tests/test_acos_v2_core_snapshot_host_preflight.py")
cs = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cs
exec(compile(Path(_spec.origin).read_bytes(), _spec.origin, "exec"), cs.__dict__)
h, p, a, core, launcher = cs.h, cs.p, cs.a, cs.core, cs.launcher
cap = a._cap
AUDITS = []


class D04Audit(cs.WindowAudit):
    """Core never changes; synthetic D04 faults are explicit, separate events.

    SQL authorizers cover connections opened in this window, not every
    pre-existing connection. Persistent-byte checks also cover the D09 store.
    """
    def sources(self):
        return copy.deepcopy((self.f.values, self.f.versions, self.f.s.now))

    def inject(self, change):
        before = self.sources()
        durable = (cs.files(self.c.directory.name), cs.files(self.f.s.directory.name))
        change()
        after = self.sources()
        if before == after or durable != (
                cs.files(self.c.directory.name), cs.files(self.f.s.directory.name)):
            raise AssertionError("synthetic D04 fault must change only fixture sources")
        self.injections.append((before, after))

    @contextmanager
    def observe(self, test):
        before_core = cs.files(self.c.directory.name)
        before_effect = cs.files(self.f.s.directory.name)
        before_state = self.f.s.store.verify()
        before_grants = copy.deepcopy(self.f.s.grants)
        before_envelope = self.f.envelope
        before_sources = self.sources()
        original_connect = sqlite3.connect
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sqlite3, "connect",
                side_effect=lambda *args, **kwargs: self.connect(original_connect, *args, **kwargs)))
            for owner, name in ((a.LiveEvidenceStore, "create"), (a.LiveEvidenceStore, "append"),
                    (a.LiveEvidenceStore, "bind_target"), (core.StateJournalWriter, "append"),
                    (core.StateJournalWriter, "rebuild_projection"), (core._RecordIssuer, "issue"),
                    (core._RecordIssuer, "consume"), (a.CredentialLease, "validate"),
                    (a.LiveWorker, "_dispatch"), (a.LiveNetworkAdapter, "_dispatch"),
                    (launcher, "run_bound"), (launcher, "read_frame")):
                stack.enter_context(mock.patch.object(owner, name, self.forbidden(name)))
            yield self
        expected = before_sources
        for before, after in self.injections:
            test.assertEqual(before, expected, "fixture source changed outside fault injection")
            expected = after
        test.assertEqual(self.sources(), expected)
        test.assertEqual(cs.files(self.c.directory.name), before_core)
        test.assertEqual(cs.files(self.f.s.directory.name), before_effect)
        test.assertEqual(self.f.s.store.verify(), before_state)
        test.assertEqual(self.f.s.grants, before_grants)
        test.assertEqual(self.f.envelope, before_envelope)
        test.assertFalse(self.f.values["capability_state"]["consumed"])
        test.assertEqual(before_state["counts"], {})
        test.assertEqual(before_state["reservations"], {})
        test.assertEqual(self.f.s.peer.connects, 0)
        test.assertEqual(self.f.s.peer.requests, [])
        test.assertEqual(self.forbidden_attempts, [])
        test.assertEqual(self.sql_writes, [])
        AUDITS.append({"test": test.id(), "synthetic_fault_injections": len(self.injections),
            "core_bytes_unchanged": True, "d09_bytes_unchanged": True,
            "sql_writes_on_observed_connections": self.sql_writes,
            "forbidden_effect_attempts": self.forbidden_attempts})


class D04RevocationPreflightTests(unittest.TestCase):
    # Reuse setup/helpers, without inheriting or rerunning the closed L tests.
    setUp = cs.CoreSnapshotHostPreflightTests.setUp
    tearDown = cs.CoreSnapshotHostPreflightTests.tearDown
    replace_reader = cs.CoreSnapshotHostPreflightTests.replace_reader
    denied = cs.CoreSnapshotHostPreflightTests.denied

    def audit(self):
        return D04Audit(self.f, self.c)

    def assert_core(self):
        snapshot = self.reader.snapshot()
        self.assertEqual((snapshot.state, snapshot.last_applied_seq), ("AUTHORIZED", 2))
        self.assertIs(core, a._core)
        self.assertIs(core, cap._core)
        self.assertIs(sys.modules["acos_v2_core_substrate"], core)
        self.assertNotEqual(self.c.identity, self.f.envelope.execution_identity)
        self.assertTrue(all(state == "AUTHORIZED" and seq == 2
            for _, state, seq in self.reader.observations))

    def validate_d04(self, boundary, expected):
        identity = self.f.envelope.execution_identity
        request = cap.ValidationRequest(self.f.envelope.capability_class,
            self.f.profile.scope_operation, self.f.profile.selector, identity,
            self.f.envelope.authority_reference,
            core.WorkflowScope(identity.project_id, identity.stage_id, identity.task_id),
            self.s.runtime.implementation_commit, self.f.envelope.cancellation_binding)
        validator = cap.CapabilityValidator(trusted_grant_resolver=boundary.grant,
            trusted_state_reader=boundary.state, trusted_clock=boundary.clock)
        result = validator.validate(self.f.envelope, request)
        self.assertEqual((result.status, result.reason), ("DENY", expected))
        self.assertFalse(result.execution_authorized)
        self.assertEqual(result.consumption_effect, "NONE")
        return result

    def reject_semantic(self, expected):
        with self.f.channels() as (boundary, errors):
            self.validate_d04(boundary, expected)
            with self.assertRaises(p.Unavailable) as caught:
                self.f.preflight(boundary)
            self.assertEqual(caught.exception.reason, "CAPABILITY")
            # Validly framed evidence can still deny at the canonical D04 layer.
            self.assertFalse(boundary.host.invalid)
            self.assertGreater(boundary.host.sequence, 0)
        self.assertEqual(errors, [])

    def test_DRI01_valid_core_and_independent_d04_framed_preflight(self):
        with self.audit().observe(self):
            self.assert_core()
            with self.f.channels() as (boundary, errors):
                self.assertTrue(self.f.preflight(boundary))
                self.assertGreater(boundary.host.sequence, 0)
                self.assertGreater(boundary.control.sequence, 0)
                self.assertEqual(boundary.host._last_versions["governance_projection"], 3)
                self.assertEqual(boundary.host._last_versions["capability_state"], 1)
            self.assertEqual(errors, [])
            self.assert_core()
        threads = {thread for thread, _, _ in self.reader.observations}
        self.assertIn(threading.get_ident(), threads)
        self.assertTrue(threads - {threading.get_ident()})

    def test_DRI02_initial_revoked_core_cannot_restore_capability(self):
        self.f.values["capability_state"]["runtime_state"] = "REVOKED"
        with self.audit().observe(self):
            self.reject_semantic("runtime capability state is not ACTIVE")
            self.assert_core()

    def test_DRI02_initial_cancelled_core_cannot_restore_capability(self):
        self.f.values["capability_state"]["runtime_state"] = "CANCELLED"
        with self.audit().observe(self):
            self.reject_semantic("runtime capability state is not ACTIVE")
            self.assert_core()

    def test_DRI03_success_then_revocation_terminates_original_client(self):
        audit = self.audit()
        def revoke():
            self.f.values["capability_state"]["runtime_state"] = "REVOKED"
            self.f.versions["capability_state"] += 1
        with audit.observe(self):
            with self.f.channels() as (boundary, errors):
                self.assertTrue(self.f.preflight(boundary))
                client, sequence = boundary.host, boundary.host.sequence
                versions = dict(client._last_versions)
                audit.inject(revoke)
                with self.assertRaises(p.Unavailable) as caught:
                    self.f.preflight(boundary)
                self.assertEqual(caught.exception.reason, "CROSS_SOURCE_DRIFT")
                self.assertIs(boundary.host, client)
                self.assertTrue(client.invalid)
                self.assertEqual(client.sequence, sequence)
                self.assertEqual(client._last_versions, versions)
                with self.assertRaises(p.Unavailable) as terminal:
                    client.accept({}, "dri_terminal_nonce")
                self.assertEqual(terminal.exception.reason, "HOST_TERMINAL")
            self.assertEqual(errors, [])
            self.assert_core()
        self.assertEqual(len(audit.injections), 1)
        self.assertEqual(self.f.versions["capability_state"], 2)

    def test_DRI03_independent_revoked_session_proves_d04_semantics(self):
        # A separate fixture/test session, never a replacement for the terminal
        # client above. It begins revoked at the already advanced source version.
        self.f.values["capability_state"]["runtime_state"] = "REVOKED"
        self.f.versions["capability_state"] = 2
        with self.audit().observe(self):
            self.reject_semantic("runtime capability state is not ACTIVE")
            self.assert_core()

    def test_DRI04_governance_clock_crosses_unchanged_expiry(self):
        expiry = self.s.now + timedelta(seconds=0.2)
        # Short, matching synthetic grant is set before the observation window.
        self.f.envelope = replace(self.f.envelope, not_after=expiry)
        self.f.values["grant"]["not_after"] = expiry.isoformat()
        self.f.packet["envelope"]["not_after"] = expiry.isoformat()
        self.s.grants[self.f.envelope.capability_id] = self.f.envelope
        audit = self.audit()
        def advance_governance_time():
            self.s.now = expiry + timedelta(microseconds=1)
            self.f.values["clock"]["trusted_now"] = self.s.now.isoformat()
        with audit.observe(self):
            with self.f.channels() as (boundary, errors):
                self.assertTrue(self.f.preflight(boundary))
                client = boundary.host
                audit.inject(advance_governance_time)
                self.validate_d04(boundary, "capability expired")
                with self.assertRaises(p.Unavailable) as caught:
                    self.f.preflight(boundary)
                self.assertEqual(caught.exception.reason, "CAPABILITY")
                self.assertIs(boundary.host, client)
                self.assertFalse(client.invalid)
            self.assertEqual(errors, [])
            self.assert_core()
        self.assertEqual(self.f.envelope.not_after, expiry)
        self.assertGreater(self.s.now, expiry)
        self.assertEqual(len(audit.injections), 1)

    def test_DRI05_unavailable_state_callback_no_fallback_or_retry(self):
        calls = []
        def unavailable():
            calls.append(threading.get_ident())
            raise RuntimeError("synthetic D04 source unavailable")
        self.f.readers["capability_state"] = replace(self.f.readers["capability_state"],
            sample=unavailable)
        self.f.sources = self.f.make_sources()
        with self.audit().observe(self):
            self.denied("HOST_SOURCE_UNAVAILABLE")
            self.assert_core()
        self.assertEqual(len(calls), 1)
        self.assertIs(self.f.readers["capability_state"].sample, unavailable)

    def test_DRI05_invalid_state_schema_fails_closed(self):
        self.f.values["capability_state"]["runtime_state"] = "UNKNOWN"
        with self.audit().observe(self):
            self.denied("CAPABILITY_STATE")
            self.assert_core()

    def test_DRI05_valid_schema_wrong_state_binding_denied_by_d04(self):
        self.f.values["capability_state"]["cancellation_binding"] = "other_cancellation"
        with self.audit().observe(self):
            self.reject_semantic("runtime state evidence binding mismatch")
            self.assert_core()

    def test_DRI06_positive_fixture_leaves_production_factory_closed(self):
        with self.audit().observe(self):
            with self.f.channels() as (boundary, errors):
                self.assertTrue(self.f.preflight(boundary))
            self.assertEqual(errors, [])
            for operation in (p.production_sources, lambda: p.establish(self.f.packet)):
                with self.assertRaises(p.Unavailable) as caught:
                    operation()
                self.assertEqual(caught.exception.reason, "PRODUCTION_SOURCES_NOT_ESTABLISHED")
            with self.assertRaises(launcher.Rejected) as caught:
                launcher.establish_boundaries(self.f.packet)
            self.assertEqual(caught.exception.code, 66)
            self.assert_core()
        for module in (p, launcher, a, cap, core):
            self.assertNotIn(sys.modules[__name__], vars(module).values())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(D04RevocationPreflightTests)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    print(json.dumps({"acceptance_conditions": 6, "tests": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "audits": AUDITS,
        "real_credential_attempts": len(h.REAL_CREDENTIAL_ATTEMPTS),
        "real_network_attempts": len(h.REAL_NETWORK_ATTEMPTS), "guard_violations": h.VIOLATIONS,
        "credential_worker_sender_client_construction_attempts": cs.CONSTRUCTION_ATTEMPTS,
        "production_sources_established": False, "execution_admission": "NONE"}))
    raise SystemExit(0 if result.wasSuccessful() and not h.VIOLATIONS else 1)

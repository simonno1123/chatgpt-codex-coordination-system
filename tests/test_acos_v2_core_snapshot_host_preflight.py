"""L01--L07: temporary Core snapshot -> framed HOST -> offline preflight.

Only this test file is added. The frozen Producer harness installs guards before
canonical modules/dependencies are loaded. All other sources remain synthetic;
no successful launcher/worker dispatch, credential lease read or sender exists
in this witness. Store incarnation is independent of the TEST-LOCAL seq+1 map.
Run in a fresh process with the existing fixed Python and -I -S -B flags.
"""
from pathlib import Path
from dataclasses import replace
from contextlib import contextmanager, ExitStack
import copy
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("core_snapshot_frozen_producer_harness",
    ROOT / "tests/test_acos_v2_production_host_control_producer.py")
hp = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = hp
exec(compile(Path(_spec.origin).read_bytes(), _spec.origin, "exec"), hp.__dict__)
h, p = hp.h, hp.p
core, a, launcher = h.core, h.a, h.launcher
CONSTRUCTION_ATTEMPTS = []


class PreflightScenario(h.Scenario):
    """Reuse synthetic store/facts, without constructing lease/worker/sender."""
    def configure(self, phase, run_id="run_fixture"):
        self.run = a.RunBinding(run_id, phase, self.runtime.digest, self.network.digest,
            self.store.handle.store_id, h.os.getpid(), "process_fixture", h.os.getppid(),
            self.runtime.parent_chain_digest, self.network_generation, self.lifecycle_generation,
            time.monotonic() + 120)


def files(directory):
    """Persistent bytes, including any SQLite sidecar; metadata is not content."""
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in Path(directory).iterdir() if path.is_file()}


class CoreFixture:
    """Explicit fixture authority/writer; never exposed to the HOST reader."""
    incarnation = 37

    def __init__(self, baseline):
        self.directory = tempfile.TemporaryDirectory(prefix="acos-core-host-")
        self.path = Path(self.directory.name) / "core.sqlite"
        self.baseline = baseline
        self.scope = core.WorkflowScope("ACOS", "core-host-fixture", "integration")
        self.identity = core.ExecutionIdentity("ACOS", "core-host-fixture", "integration",
            "core_fixture_authority", "fixture_executor", "core_fixture_attempt", baseline)
        self.reference = core.AuthorityReference("core_fixture_authority", "sha256:" + "4" * 64)
        self._writer_credential, self._submission_credential = object(), object()
        with self.open(create=True) as store:
            if store.snapshot().state != "DRAFT":
                raise AssertionError("Core initialization must not authorize")
        # Existing writer + independent fixture evidence only. AUTHORIZED here
        # deliberately does NOT supply the separate D04 grant/state/authority.
        self.advance("REVIEW_PENDING")
        self.advance("AUTHORIZED")

    @contextmanager
    def open(self, create=False):
        store = core.StateStore(self.path, self.scope, self.baseline,
            "core_fixture_writer", lambda supplied: "core_fixture_writer"
            if supplied is self._writer_credential else None, create=create)
        try:
            yield store
        finally:
            store.close()

    def advance(self, to_state):
        with self.open() as store:
            before = store.snapshot()
            candidate = core.CandidateTransition("core_transition_" + str(before.last_applied_seq + 1),
                "core_fixture_candidate", before.head_event_hash, before.last_applied_seq,
                self.baseline, self.reference, self.identity, before.state, to_state)
            evidence = core.AuthorityEvidence(self.reference, self.identity, candidate.candidate_id,
                candidate.from_state, candidate.to_state, "ChatGPT Review", True,
                ("core_fixture_review",), ("core_fixture_review",))
            engine = store.transition_engine(lambda reference: evidence if reference == self.reference else None,
                lambda supplied: self.identity if supplied is self._submission_credential else None)
            accepted = engine.validate(candidate, self._submission_credential)
            return store.writer(self._writer_credential).append(accepted)

    def reader(self):
        # Bind only immutable location/binding data. The callback holds no
        # fixture object, writer credential, submission credential or resolver.
        path, scope, baseline = self.path, self.scope, self.baseline
        observations = []

        def snapshot():
            before = files(path.parent)
            thread = threading.get_ident()
            store = None
            try:
                # Default create=False: missing/corrupt stores cannot bootstrap.
                # Both open and close execute in this actual reader thread.
                store = core.StateStore(path, scope, baseline, "core_fixture_writer", lambda supplied: None)
                result = store.snapshot()
                observations.append((thread, result.state, result.last_applied_seq))
                return result
            finally:
                if store is not None:
                    store.close()
                if files(path.parent) != before:
                    raise AssertionError("snapshot callback changed persistent Core bytes")

        return SnapshotReader(snapshot, self.incarnation, observations)


class SnapshotReader:
    """Test-local adaptation; no new HOST fields or production registration."""
    def __init__(self, snapshot, incarnation, observations):
        self.snapshot, self.incarnation, self.observations = snapshot, incarnation, observations

    def version(self):
        return self.snapshot().last_applied_seq + 1

    def sample(self):
        self.snapshot()  # Must verify actual journal/projection before reporting.
        return {"authority_effect": "NONE", "execution_admission": "NONE",
                "journal_generation": self.incarnation}


class WindowAudit:
    """Observe writes without blocking/masking SQL; separate lawful injections."""
    writes = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
              sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
              sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_TRIGGER,
              sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_CREATE_INDEX,
              sqlite3.SQLITE_DROP_INDEX}

    def __init__(self, fixture, core_fixture):
        self.f, self.c = fixture, core_fixture
        self.local = threading.local()
        self.sql_writes, self.forbidden_attempts, self.injections = [], [], []

    def connect(self, original, database, *args, **kwargs):
        connection = original(database, *args, **kwargs)
        def authorizer(action, first, second, db, trigger):
            if action in self.writes:
                self.sql_writes.append((getattr(self.local, "phase", "OBSERVATION"),
                                        str(database), action, first))
            return sqlite3.SQLITE_OK
        connection.set_authorizer(authorizer)
        return connection

    def forbidden(self, name):
        def deny(*args, **kwargs):
            self.forbidden_attempts.append(name)
            raise AssertionError("unexpected effect path: " + name)
        return deny

    @contextmanager
    def injection(self):
        before, prior = files(self.c.directory.name), getattr(self.local, "phase", "OBSERVATION")
        self.local.phase = "AUTHORIZED_FIXTURE_INJECTION"
        try:
            yield
        finally:
            self.local.phase = prior
            self.injections.append((before, files(self.c.directory.name)))

    @contextmanager
    def observe(self, test):
        before_core = files(self.c.directory.name)
        before_effect = files(self.f.s.directory.name)
        before_state = self.f.s.store.verify()
        before_grants = copy.deepcopy(self.f.s.grants)
        before_capability = copy.deepcopy(self.f.values["capability_state"])
        before_guard = (len(h.VIOLATIONS), len(h.REAL_NETWORK_ATTEMPTS), len(h.REAL_CREDENTIAL_ATTEMPTS))
        original_connect = sqlite3.connect
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(sqlite3, "connect",
                side_effect=lambda *args, **kwargs: self.connect(original_connect, *args, **kwargs)))
            # Count even attempts. Passing because a guard swallowed a bad call
            # is not sufficient. No positive launcher execution is used.
            for owner, name in ((a.LiveEvidenceStore, "create"), (a.LiveEvidenceStore, "append"),
                    (a.LiveEvidenceStore, "bind_target"), (core.StateJournalWriter, "rebuild_projection"),
                    (a.CredentialLease, "validate"), (a.httpx.AsyncClient, "__init__"),
                    (a.LiveWorker, "_dispatch"), (a.LiveNetworkAdapter, "_dispatch"),
                    (launcher, "run_bound"), (launcher, "read_frame")):
                stack.enter_context(mock.patch.object(owner, name, self.forbidden(name)))
            yield self
        expected = before_core
        for pre, post in self.injections:
            test.assertEqual(pre, expected, "Core changed outside the authorized injection window")
            test.assertNotEqual(pre, post, "injection must actually change durable Core bytes")
            expected = post
        test.assertEqual(files(self.c.directory.name), expected)
        test.assertEqual(files(self.f.s.directory.name), before_effect)
        test.assertEqual(self.f.s.store.verify(), before_state)
        test.assertEqual(self.f.s.grants, before_grants)
        test.assertEqual(self.f.values["capability_state"], before_capability)
        test.assertFalse(self.f.values["capability_state"]["consumed"])
        test.assertEqual(before_state["counts"], {})
        test.assertEqual(before_state["reservations"], {})
        test.assertEqual(self.f.s.peer.connects, 0)
        test.assertEqual(self.f.s.peer.requests, [])
        test.assertEqual(self.forbidden_attempts, [])
        test.assertEqual([write for write in self.sql_writes if write[0] == "OBSERVATION"], [])
        test.assertEqual((len(h.VIOLATIONS), len(h.REAL_NETWORK_ATTEMPTS),
                          len(h.REAL_CREDENTIAL_ATTEMPTS)), before_guard)


class CoreSnapshotHostPreflightTests(unittest.TestCase):
    def setUp(self):
        self.guard_before = (len(h.VIOLATIONS), len(h.REAL_NETWORK_ATTEMPTS), len(h.REAL_CREDENTIAL_ATTEMPTS))
        self.constructions_before = len(CONSTRUCTION_ATTEMPTS)
        stack = ExitStack()
        self.addCleanup(stack.close)
        def construction(name):
            def deny(*args, **kwargs):
                CONSTRUCTION_ATTEMPTS.append(name)
                raise AssertionError("preflight fixture must not construct " + name)
            return deny
        for owner in (a.CredentialLease, a.LiveWorker, a.LiveNetworkAdapter, a.httpx.AsyncClient):
            stack.enter_context(mock.patch.object(owner, "__init__", construction(owner.__name__)))
        launcher._STOP, launcher._STOP_CODE = False, None
        self.s = PreflightScenario()
        self.addCleanup(self.s.close)
        self.f = hp.Fixture(self.s)
        self.c = CoreFixture(self.s.runtime.implementation_commit)
        self.addCleanup(self.c.directory.cleanup)
        self.reader = self.c.reader()
        self.replace_reader(self.reader.sample, self.reader.version)

    def tearDown(self):
        self.assertEqual((len(h.VIOLATIONS), len(h.REAL_NETWORK_ATTEMPTS),
                          len(h.REAL_CREDENTIAL_ATTEMPTS)), self.guard_before)
        self.assertEqual(CONSTRUCTION_ATTEMPTS[self.constructions_before:], [])

    def replace_reader(self, sample, version):
        self.f.readers["governance_projection"] = replace(self.f.readers["governance_projection"],
            sample=sample, version=version)
        self.f.sources = self.f.make_sources()

    def audit(self):
        return WindowAudit(self.f, self.c)

    def denied(self, test_reason=None):
        with self.f.channels() as (boundary, errors):
            with self.assertRaises(p.Unavailable) as caught:
                self.f.preflight(boundary)
            if test_reason is not None:
                self.assertTrue(boundary.host.invalid)
        if test_reason is not None:
            self.assertIn(test_reason, errors)
        return caught.exception.reason

    def test_L01_verified_snapshot_through_framed_host_preflight(self):
        main_thread = threading.get_ident()
        with self.audit().observe(self):
            with self.f.channels() as (boundary, errors):
                self.assertTrue(self.f.preflight(boundary))
                self.assertGreater(boundary.host.sequence, 0)
                self.assertGreater(boundary.control.sequence, 0)
                value = boundary.host.observe()["governance_projection"]
                self.assertEqual(value, {"authority_effect": "NONE", "execution_admission": "NONE",
                                         "journal_generation": 37})
                self.assertEqual(boundary.host._last_versions["governance_projection"], 3)
            self.assertEqual(errors, [])
        threads = {thread for thread, state, seq in self.reader.observations}
        self.assertIn(main_thread, threads)  # Client's independent version reads.
        self.assertTrue(threads - {main_thread})  # Actual HOST producer thread.
        self.assertTrue(all(state == "AUTHORIZED" and seq == 2 for _, state, seq in self.reader.observations))
        self.assertIs(core, a._core)

    def test_L02_core_projection_corruption_rejects_without_repair(self):
        # Deliberate Core fault before observation, not D09 projection damage.
        connection = sqlite3.connect(self.c.path)
        try:
            connection.execute("UPDATE derived_projection SET state='ACCEPTED', last_applied_seq=99")
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(core.StoreBlocked, "journal/projection mismatch"):
            self.reader.snapshot()
        with self.audit().observe(self):
            self.denied("HOST_SOURCE_UNAVAILABLE")

    def test_L03_transition_between_version_and_sample_is_deterministic(self):
        audit, injected = self.audit(), []
        def sample_after_transition():
            self.assertEqual(len(injected), 0, "no retry/further injection")
            with audit.injection():
                result = self.c.advance("EXECUTING")
                injected.append(result.last_applied_seq)
            return self.reader.sample()
        self.replace_reader(sample_after_transition, self.reader.version)
        with audit.observe(self):
            self.denied("SOURCE_CHANGED_DURING_SNAPSHOT")
        self.assertEqual(injected, [3])
        self.assertEqual(len(audit.injections), 1)
        self.assertTrue(audit.sql_writes)
        self.assertTrue(all(write[0] == "AUTHORIZED_FIXTURE_INJECTION" for write in audit.sql_writes))
        self.assertEqual({seq for _, _, seq in self.reader.observations}, {2, 3})

    def test_L04_same_host_client_rejects_cross_observation_drift(self):
        audit = self.audit()
        with audit.observe(self):
            with self.f.channels() as (boundary, errors):
                self.assertTrue(self.f.preflight(boundary))
                client = boundary.host
                first_sequence = client.sequence
                self.assertEqual(client._last_versions["governance_projection"], 3)
                with audit.injection():
                    result = self.c.advance("EXECUTING")
                self.assertEqual(result.last_applied_seq, 3)
                with self.assertRaises(p.Unavailable) as caught:
                    self.f.preflight(boundary)
                self.assertEqual(caught.exception.reason, "CROSS_SOURCE_DRIFT")
                self.assertIs(boundary.host, client)
                self.assertTrue(client.invalid)
                self.assertEqual(client.sequence, first_sequence)
                with self.assertRaises(p.Unavailable) as terminal:
                    client.accept({}, "terminal_fixture_nonce")
                self.assertEqual(terminal.exception.reason, "HOST_TERMINAL")
            self.assertEqual(errors, [])
        self.assertEqual(len(audit.injections), 1)
        self.assertTrue(all(write[0] == "AUTHORIZED_FIXTURE_INJECTION" for write in audit.sql_writes))

    def test_L05_authorized_core_does_not_replace_independent_authority(self):
        self.assertEqual(self.reader.snapshot().state, "AUTHORIZED")
        self.f.values["authority"]["authorized"] = False
        with self.audit().observe(self):
            self.assertEqual(self.denied(), "AUTHORITY")

    def test_L05_authorized_core_does_not_replace_independent_grant(self):
        self.assertEqual(self.reader.snapshot().state, "AUTHORIZED")
        self.f.values["grant"]["capability_id"] = "absent_grant_fixture"
        with self.audit().observe(self):
            self.assertEqual(self.denied(), "CAPABILITY")

    def test_L05_authorized_core_does_not_replace_independent_provenance(self):
        self.assertEqual(self.reader.snapshot().state, "AUTHORIZED")
        self.f.host_valid = False
        with self.audit().observe(self):
            with self.assertRaises(p.Unavailable) as caught:
                with self.f.channels():
                    self.fail("unqualified boundary must not become available")
            self.assertEqual(caught.exception.reason, "SYNTHETIC_QUALIFICATION_LOST")

    def test_L06_snapshot_callback_error_rejects_without_fallback(self):
        calls = []
        def unavailable():
            calls.append(threading.get_ident())
            raise core.StoreBlocked("synthetic snapshot unavailable")
        self.reader.snapshot = unavailable
        with self.audit().observe(self):
            self.denied("HOST_SOURCE_UNAVAILABLE")
        self.assertEqual(len(calls), 1)

    def test_L06_missing_existing_core_store_is_not_created(self):
        self.c.path.unlink()  # Explicit fixture removal, before observation.
        self.assertEqual(files(self.c.directory.name), {})
        with self.audit().observe(self):
            self.denied("HOST_SOURCE_UNAVAILABLE")
        self.assertFalse(self.c.path.exists())

    def test_L07_explicit_test_success_does_not_open_production_factory(self):
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
        for module in (p, launcher, a):
            self.assertNotIn(sys.modules[__name__], vars(module).values())
            self.assertNotIn(SnapshotReader, vars(module).values())


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CoreSnapshotHostPreflightTests)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    print(json.dumps({"acceptance_conditions": 7, "tests": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "real_credential_attempts": len(h.REAL_CREDENTIAL_ATTEMPTS),
        "real_network_attempts": len(h.REAL_NETWORK_ATTEMPTS), "guard_violations": h.VIOLATIONS,
        "credential_worker_sender_client_construction_attempts": CONSTRUCTION_ATTEMPTS,
        "production_sources_established": False, "execution_admission": "NONE"}))
    raise SystemExit(0 if result.wasSuccessful() and not h.VIOLATIONS else 1)

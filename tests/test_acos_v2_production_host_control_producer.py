"""HP-T01--HP-T52 plus regressions. All positive sources are synthetic.

Load the frozen live-test harness FIRST: its guards precede producer/launcher/
client imports and forbid DNS/TCP/TLS/proxy, credentials and external commands.
The only network IO below is inherited/local AF_UNIX protocol fixtures. Existing
HTTPX sender emulation retains the frozen worker's reservation/header fences.
Nothing in these tests establishes production source registrations or G2.
"""
from pathlib import Path
from dataclasses import asdict, replace
from datetime import timedelta
from contextlib import contextmanager
import ast
import copy
import hashlib
import importlib.util
import json
import os
import socket
import sqlite3
import sys
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("hp_frozen_live_harness",
    ROOT / "tests/test_acos_v2_remote_context_live_adapter.py")
h = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = h
exec(compile(Path(_spec.origin).read_bytes(), _spec.origin, "exec"), h.__dict__)
# The guard installation above happened BEFORE these modules are accessible.
a, cap, core, launcher = h.a, h.cap, h.core, h.launcher
p = launcher._load_producer()


def pin(path):
    return p.Pin(**asdict(h.file_pin(path)))


def reseal(value):
    return p.seal({k: v for k, v in value.items() if k != "package_digest"})


class Fixture:
    """Independent test host: registrations/facts are outside candidate payload."""
    def __init__(self, scenario):
        self.s = scenario
        self.profile, self.envelope = scenario.grant()
        self.packet = h.runtime_packet(scenario)
        self.packet["profile"] = json.loads(a._canonical(asdict(self.profile)))
        self.packet["envelope"] = {**asdict(self.envelope), "not_after": self.envelope.not_after.isoformat()}
        self.context = {"run_id": scenario.run.run_id,
            "process_incarnation": scenario.run.process_incarnation,
            "runtime_binding_digest": scenario.runtime.digest,
            "baseline": scenario.runtime.implementation_commit,
            "phase": scenario.run.phase, "profile_digest": p.digest(self.packet["profile"])}
        app = h.file_pin(p.PYTHON_APP)
        self.identity = {"process_id": os.getppid(), "uid": os.getuid(),
            "process_incarnation": "parent_fixture_incarnation", "boot_identity": "boot_fixture",
            "parent_id": 1, "parent_chain_digest": "sha256:" + "a"*64,
            "binary_path": p.PYTHON_APP, "binary_digest": "sha256:" + app.sha256}
        self.host = p.Registration("HOST", "host_fixture", "host_qualification_fixture", "host_epoch",
            scenario.runtime.digest, scenario.runtime.implementation_commit,
            scenario.run.run_id, scenario.run.process_incarnation, scenario.run.phase,
            pin(p.SELF), pin(p.PYTHON), "sha256:" + "b"*64, dict(self.identity),
            "FD4_HOST_OBSERVATION", "host_custody_fixture", "continuous_fixture", 1)
        self.control = replace(self.host, role="CONTROL", reference="control_fixture",
            qualification_reference="control_qualification_fixture", epoch="control_epoch",
            channel_role="FD6_LIFECYCLE", custody_reference="control_custody_fixture")
        self.host_valid, self.control_valid, self.kernel_valid = True, True, True
        self.observed_identity = dict(self.identity)
        self.control_facts = {k: v for k, v in scenario.observation().items()
            if k not in {"run_id", "process_incarnation", "lease_until"}}
        self.control_facts["sleep_wake_generation"] = 1
        self.continuous = time.monotonic_ns()
        self.monotonic = time.monotonic_ns()
        self.real_time = False
        self.versions = {slot: 1 for slot in p.SLOTS}
        self.values = {
            "authority": {"authority_reference": asdict(scenario.reference),
                "execution_identity": asdict(scenario.identity), "selector": self.profile.selector, "authorized": True},
            "grant": {**asdict(self.envelope), "not_after": self.envelope.not_after.isoformat()},
            "capability_state": asdict(cap.CapabilityStateEvidence(self.envelope.capability_id,
                scenario.identity, scenario.reference, "cancel_fixture", "ACTIVE", False)),
            "clock": {"trusted_now": scenario.now.isoformat(), "clock_reference": "D04_clock_fixture", "certain": True},
            "baseline": {"baseline": scenario.runtime.implementation_commit},
            "target": asdict(scenario.binding),
            "revocation": {"status": "ACTIVE", "binding_digest": scenario.binding.digest},
            "credential_reference": {"reference": "credential_fixture", "version": 1,
                "organization": "org_fixture", "project": "proj_fixture"},
            "caller": {"caller_id": "caller_fixture", "execution_identity": asdict(scenario.identity)},
            "runtime_reference": {"runtime_binding_digest": scenario.runtime.digest},
            "network_handoff": {"producer_reference": scenario.network.producer_reference,
                "evidence_reference": scenario.network.evidence_reference, "qualification_digest": scenario.network.digest},
            "governance_projection": {"authority_effect": "NONE", "execution_admission": "NONE", "journal_generation": 1}}
        self.readers = {slot: p.SourceReader(p.SOURCE_CLASSES[slot], "source_" + slot,
            "sha256:" + hashlib.sha256(slot.encode()).hexdigest(), "identity_" + slot, 1,
            lambda slot=slot: copy.deepcopy(self.values[slot]), lambda slot=slot: self.versions[slot])
            for slot in p.SLOTS}
        self.sources = self.make_sources()

    def make_sources(self):
        return p.ExternalSources(self.host, self.control, self.readers, self.provenance,
            self.kernel, lambda: self.s.now,
            lambda: time.monotonic_ns() if self.real_time else self.continuous,
            lambda: time.monotonic_ns() if self.real_time else self.monotonic,
            lambda producer, evidence: self.s.network if self.s.network_source else None,
            p.SourceReader("CONTROL_LIFECYCLE", "control_reader_fixture", "sha256:"+"c"*64,
                "control_identity_fixture", 1, lambda: dict(self.control_facts), lambda: 1))

    def provenance(self, role, registration, context, fd):
        if not (self.host_valid if role == "HOST" else self.control_valid):
            p.fail("SYNTHETIC_QUALIFICATION_LOST")
        return {"registration_reference": registration.reference,
            "qualification_reference": registration.qualification_reference,
            "channel_role": registration.channel_role, "custody_reference": registration.custody_reference,
            "catalog_digest": self.sources.catalog_digest if role == "HOST" else self.sources.control_catalog_digest,
            "runtime_digest": registration.runtime_digest}

    def kernel(self, registration, fd):
        if not self.kernel_valid:
            p.fail("SYNTHETIC_PRODUCER_DEAD")
        return dict(self.observed_identity)

    def query(self, nonce="nonce_fixture"):
        return {**self.context, "schema": p.QUERY_SCHEMA, "kind": "OBSERVE_BOUND_FACTS",
                "request_nonce": nonce}

    def response(self, nonce="nonce_fixture"):
        return p.HostObservationProducer(self.sources, self.context).observe(self.query(nonce))

    def accept(self, response=None, nonce="nonce_fixture"):
        return p.HostObservationClient(self.sources, self.context).accept(response or self.response(nonce), nonce)

    def control_package(self):
        return p.ControlObservationProducer(self.sources, self.context).sample()

    def control_client(self):
        return p.ControlObservationClient(self.sources, self.context, self.packet["run"])

    @contextmanager
    def channels(self):
        """Actual framing over AF_UNIX; no TCP socket or external listener."""
        worker, host = socket.socketpair(socket.AF_UNIX)
        reader, writer = os.pipe()
        stopped = threading.Event()
        errors = []
        self.real_time = True
        hp = p.HostObservationProducer(self.sources, self.context, host.fileno())
        cp = p.ControlObservationProducer(self.sources, self.context, writer)
        def host_loop():
            while not stopped.is_set():
                try:
                    hp.serve_once()
                except p.Unavailable as error:
                    if not stopped.is_set():
                        errors.append(error.reason)
                    break
        def control_loop():
            while not stopped.is_set():
                try:
                    cp.emit_once()
                except p.Unavailable as error:
                    if not stopped.is_set():
                        errors.append(error.reason)
                    break
                stopped.wait(0.05)
        ht, ct = threading.Thread(target=host_loop), threading.Thread(target=control_loop)
        ht.start(); ct.start()
        try:
            boundary = p.ObservationBoundary(self.sources, self.packet, worker.fileno(), reader)
            boundary.bind_canonical(a, self.s.runtime)
            yield boundary, errors
        finally:
            stopped.set()
            ht.join(0.4); ct.join(0.4)
            worker.close(); host.close(); os.close(reader); os.close(writer)
            if ht.is_alive() or ct.is_alive():
                raise AssertionError("fixture channel thread did not terminate")

    def preflight(self, boundary):
        return p.credential_free_preflight(a, self.profile, self.envelope, self.s.runtime,
            self.s.network, self.s.run, self.s.binding, self.s.store, boundary)


class ProducerTests(unittest.TestCase):
    def setUp(self):
        self.scenarios = []
        self.before = len(h.VIOLATIONS)
        launcher._STOP, launcher._STOP_CODE = False, None

    def tearDown(self):
        try:
            self.assertEqual(h.VIOLATIONS[self.before:], [])
        finally:
            for s in self.scenarios:
                s.close()

    def fixture(self, replies=()):
        s = h.Scenario(replies)
        self.scenarios.append(s)
        return Fixture(s)

    def deny_accept(self, fixture, changed):
        with self.assertRaises(p.Unavailable):
            fixture.accept(reseal(changed))

    def denied_preflight(self, fixture):
        with fixture.channels() as (boundary, errors):
            with self.assertRaises(p.Unavailable):
                fixture.preflight(boundary)
        self.assertEqual(fixture.s.peer.connects, 0)
        self.assertEqual(fixture.s.store.verify()["counts"], {})

    def launcher_denied(self, fixture):
        reads, clients = [], []
        # Store was created solely by the fixture; release its lock so the real
        # launcher can reopen it. No fixture provider is installed in main().
        fixture.s.store.close()
        with fixture.channels() as (boundary, errors):
            def read(*args, **kwargs):
                reads.append(args[0])
                raise AssertionError("FD5 must remain unread")
            def client(*args, **kwargs):
                clients.append(True)
                raise AssertionError("client must not be constructed")
            with mock.patch.object(launcher, "read_frame", read), \
                    mock.patch.object(a.httpx.AsyncClient, "__init__", client):
                with self.assertRaises(launcher.Rejected):
                    launcher.run_bound(a, fixture.packet, boundary)
        return reads, clients

    def test_HP_T01_wrong_producer_interpreter_binary(self):
        f = self.fixture()
        f.host = replace(f.host, interpreter=replace(f.host.interpreter, path="/usr/bin/python3"))
        f.sources = f.make_sources()
        with self.assertRaises(p.Unavailable):
            f.sources.qualify("HOST", f.context, 4)
        f.host = replace(f.host, interpreter=pin(p.PYTHON), identity={**f.identity, "binary_path": "/tmp/wrapper"})
        f.sources = f.make_sources()
        with self.assertRaises(p.Unavailable):
            f.sources.qualify("HOST", f.context, 4)

    def test_HP_T02_producer_digest_drift(self):
        f = self.fixture()
        f.host = replace(f.host, implementation=replace(f.host.implementation, sha256="0"*64))
        f.sources = f.make_sources()
        with self.assertRaises(p.Unavailable):
            f.response()
        with mock.patch.object(launcher, "PRODUCER_SHA", "0"*64):
            with self.assertRaises(launcher.Rejected):
                launcher._load_producer()

    def test_HP_T03_wrong_kernel_pid(self):
        f = self.fixture()
        f.observed_identity["process_id"] += 1
        with self.assertRaises(p.Unavailable):
            f.accept()

    def test_HP_T04_pid_reuse_incarnation(self):
        f = self.fixture()
        f.observed_identity["process_incarnation"] = "reused_PID"
        with self.assertRaises(p.Unavailable):
            f.accept()

    def test_HP_T05_wrong_parent_chain(self):
        f = self.fixture()
        f.observed_identity["parent_chain_digest"] = "sha256:" + "0"*64
        with self.assertRaises(p.Unavailable):
            f.accept()

    def test_HP_T06_wrong_run_id(self):
        f = self.fixture()
        value = f.response()
        value["run_id"] = "another_run"
        self.deny_accept(f, value)

    def test_HP_T07_baseline_mismatch(self):
        f = self.fixture()
        value = f.response()
        value["baseline"] = "0"*40
        self.deny_accept(f, value)

    def test_HP_T08_runtime_binding_mismatch(self):
        f = self.fixture()
        value = f.response()
        value["runtime_binding_digest"] = "sha256:" + "0"*64
        self.deny_accept(f, value)

    def test_HP_T09_role_string_impersonation(self):
        f = self.fixture()
        f.host = replace(f.host, role="CONTROL")
        with self.assertRaises(p.Unavailable):
            f.make_sources()
        self.assertEqual(f.s.store.verify()["counts"], {})

    def test_HP_T10_self_qualified_flag(self):
        f = self.fixture()
        value = f.response()
        value["qualified"] = True
        self.deny_accept(f, value)
        with self.assertRaises(p.Unavailable):
            p.production_sources()

    def test_HP_T11_fd3_fd4_circular_trust(self):
        f = self.fixture()
        f.packet["producer"]["qualified"] = True
        f.packet["producer"]["registration"] = asdict(f.host)
        with self.assertRaises(launcher.Rejected) as caught:
            launcher.establish_boundaries(f.packet)
        self.assertEqual(caught.exception.code, 66)
        with self.assertRaises(p.Unavailable):
            p.ObservationBoundary(object(), f.packet)

    def test_HP_T12_unknown_source_class(self):
        f = self.fixture()
        f.readers["authority"] = replace(f.readers["authority"], source_class="SELF_AUTHORITY")
        with self.assertRaises(p.Unavailable):
            f.make_sources()

    def test_HP_T13_wrong_source_reference_reader(self):
        for field, new in (("source_reference", "forged_reader"), ("reader_implementation_digest", "sha256:" + "0"*64)):
            f = self.fixture()
            value = f.response()
            value["observations"]["authority"][field] = new
            self.deny_accept(f, value)

    def test_HP_T14_fd4_duplicate_keys(self):
        with self.assertRaises(p.Unavailable):
            p.strict_json(b'{"schema":"a","schema":"b"}')

    def test_HP_T15_invalid_utf8(self):
        with self.assertRaises(p.Unavailable):
            p.strict_json(b'{"x":"\xff"}')

    def test_HP_T16_size_depth_numeric_types(self):
        for raw in (b" "*(p.HOST_MAX+1), b'{"x":NaN}', b'{"x":1.5}',
                    p.canonical({"x": 2**63})):
            with self.assertRaises(p.Unavailable):
                p.strict_json(raw)
        value = {"x": {}}
        for _ in range(9):
            value = {"x": value}
        with self.assertRaises(p.Unavailable):
            p.strict_json(p.canonical(value))
        f = self.fixture()
        value = f.response()
        value["observation_sequence"] = True
        self.deny_accept(f, value)

    def test_HP_T17_truncation_stall(self):
        for close in (True, False):
            reader, writer = os.pipe()
            try:
                os.write(writer, (8).to_bytes(4, "big") + b"{}")
                if close:
                    os.close(writer); writer = None
                started = time.monotonic()
                with self.assertRaises(p.Unavailable):
                    p.read_frame(reader, p.HOST_MAX)
                self.assertLess(time.monotonic() - started, 0.5)
            finally:
                os.close(reader)
                if writer is not None:
                    os.close(writer)

    def test_HP_T18_wrong_fd4_producer(self):
        f = self.fixture()
        value = f.response()
        value["producer_reference"] = "other_host"
        self.deny_accept(f, value)

    def test_HP_T19_replay_nonce(self):
        f = self.fixture()
        producer = p.HostObservationProducer(f.sources, f.context)
        response = producer.observe(f.query())
        client = p.HostObservationClient(f.sources, f.context)
        client.accept(response, "nonce_fixture")
        with self.assertRaises(p.Unavailable):
            client.accept(response, "nonce_fixture")
        with self.assertRaises(p.Unavailable):
            producer.observe(f.query())

    def test_HP_T20_epoch_sequence_reordering(self):
        for field, new in (("observation_epoch", "old_epoch"), ("observation_sequence", 2)):
            f = self.fixture()
            value = f.response()
            value[field] = new
            self.deny_accept(f, value)
        f = self.fixture()
        producer = p.HostObservationProducer(f.sources, f.context)
        client = p.HostObservationClient(f.sources, f.context)
        client.accept(producer.observe(f.query("nonce_one")), "nonce_one")
        value = producer.observe(f.query("nonce_two"))
        value["observation_sequence"] = 1
        with self.assertRaises(p.Unavailable):
            client.accept(reseal(value), "nonce_two")

    def test_HP_T21_expired_observation(self):
        f = self.fixture()
        value = f.response()
        f.s.now += timedelta(seconds=1)
        self.deny_accept(f, value)

    def test_HP_T22_source_changes_during_snapshot(self):
        f = self.fixture()
        old = f.readers["grant"].sample
        def changed():
            f.versions["authority"] += 1
            return old()
        f.readers["grant"] = replace(f.readers["grant"], sample=changed)
        f.sources = f.make_sources()
        with self.assertRaises(p.Unavailable) as caught:
            f.response()
        self.assertEqual(caught.exception.reason, "SOURCE_CHANGED_DURING_SNAPSHOT")

    def test_HP_T23_missing_authority(self):
        f = self.fixture()
        f.values["authority"]["authorized"] = False
        self.denied_preflight(f)

    def test_HP_T24_missing_or_different_grant(self):
        for missing in (True, False):
            f = self.fixture()
            if missing:
                f.values["grant"] = None
            else:
                f.values["grant"]["capability_id"] = "other_cap"
            self.denied_preflight(f)

    def test_HP_T25_revoked_cancelled_consumed(self):
        for changes in ({"runtime_state": "REVOKED"}, {"runtime_state": "CANCELLED"}, {"consumed": True}):
            f = self.fixture()
            f.values["capability_state"].update(changes)
            self.denied_preflight(f)
        f = self.fixture()
        f.values["revocation"]["status"] = "UNKNOWN"
        self.denied_preflight(f)

    def test_HP_T26_trusted_clock_missing_stale_uncertain(self):
        for value in (None, "not-a-clock", (h.datetime(2100,1,1,tzinfo=h.timezone.utc)).isoformat(),
                      (h.datetime(2020,1,1,tzinfo=h.timezone.utc)).isoformat()):
            f = self.fixture()
            f.values["clock"]["trusted_now"] = value
            self.denied_preflight(f)
        f = self.fixture()
        f.values["clock"]["certain"] = False
        self.denied_preflight(f)

    def test_HP_T27_caller_mismatch(self):
        f = self.fixture()
        f.values["caller"]["caller_id"] = "different_executor"
        self.denied_preflight(f)
        f = self.fixture()
        f.values["caller"]["execution_identity"]["execution_attempt_id"] = "different_attempt"
        self.denied_preflight(f)

    def test_HP_T28_target_generation_provenance(self):
        for field, value in (("generation", 2), ("provenance_digest", "sha256:"+"0"*64)):
            f = self.fixture()
            f.values["target"][field] = value
            self.denied_preflight(f)

    def test_HP_T29_credential_reference_version_project(self):
        for field, value in (("version", 2), ("project", "different_project")):
            f = self.fixture()
            f.values["credential_reference"][field] = value
            self.denied_preflight(f)

    def test_HP_T30_network_missing_unknown(self):
        f = self.fixture()
        f.s.network_source = False
        self.denied_preflight(f)
        f = self.fixture()
        f.packet["network"]["replay_boundary"] = ((f.s.network.replay_boundary[0][0], "UNKNOWN"),) + f.s.network.replay_boundary[1:]
        reads, clients = self.launcher_denied(f)
        self.assertEqual((reads, clients), ([], []))

    def test_HP_T31_fd6_eof(self):
        f = self.fixture()
        reader, writer = os.pipe()
        os.close(writer)
        try:
            client = p.ControlObservationClient(f.sources, f.context, f.packet["run"], reader)
            with self.assertRaises(p.Unavailable):
                client.observe()
            self.assertTrue(client.invalid)
            with self.assertRaises(p.Unavailable):
                client.accept(f.control_package())
        finally:
            os.close(reader)

    def test_HP_T32_writer_death_retained_descriptor(self):
        f = self.fixture()
        client = f.control_client()
        producer = p.ControlObservationProducer(f.sources, f.context)
        client.accept(producer.sample())
        retained_frame = producer.sample()
        f.kernel_valid = False
        with self.assertRaises(p.Unavailable):
            client.accept(retained_frame)
        self.assertTrue(client.invalid)

    def test_HP_T33_control_lease_expiry(self):
        f = self.fixture()
        value = f.control_package()
        f.continuous += p.LEASE_NS + 1
        f.monotonic += p.LEASE_NS + 1
        with self.assertRaises(p.Unavailable):
            f.control_client().accept(value)

    def test_HP_T34_fd6_epoch_generation_sequence(self):
        for field, value in (("observation_epoch", "old_epoch"), ("network_generation", 2),
                             ("lifecycle_generation", 2), ("sequence", 2)):
            f = self.fixture()
            package = f.control_package()
            package[field] = value
            with self.assertRaises(p.Unavailable):
                f.control_client().accept(reseal(package))

    def test_HP_T35_wrong_channel_role_custody(self):
        f = self.fixture()
        f.control = replace(f.control, channel_role="FD4_HOST_OBSERVATION")
        with self.assertRaises(p.Unavailable):
            f.sources = f.make_sources()
            f.sources.qualify("CONTROL", f.context, 6)
        f = self.fixture()
        original = f.sources._provenance
        def wrong(*args):
            proof = original(*args)
            return {**proof, "custody_reference": "unqualified_transfer"}
        f.sources._provenance = wrong
        with self.assertRaises(p.Unavailable):
            f.accept()

    def test_HP_T36_foreground_terminal_group(self):
        f = self.fixture()
        f.control_facts["foreground"] = False
        package = f.control_package()
        self.assertEqual(package["kind"], "INVALIDATE")
        with self.assertRaises(p.Unavailable):
            f.control_client().accept(package)

    def test_HP_T37_sleep_wake_invalidates(self):
        f = self.fixture()
        f.control_facts["sleep_wake_generation"] += 1
        client = f.control_client()
        with self.assertRaises(p.Unavailable):
            client.accept(f.control_package())
        f.control_facts["sleep_wake_generation"] = 1
        with self.assertRaises(p.Unavailable):
            client.accept(f.control_package())

    def test_HP_T38_terminal_close_parent_loss(self):
        for field, value in (("terminal_open", False), ("parent_id", 12345)):
            f = self.fixture()
            f.control_facts[field] = value
            with self.assertRaises(p.Unavailable):
                f.control_client().accept(f.control_package())

    def test_HP_T39_illegal_control_commands(self):
        for kind in ("RETRY", "RESTART", "NEW_TARGET", "CREDENTIAL", "CAPABILITY"):
            f = self.fixture()
            value = f.control_package()
            value["kind"] = kind
            with self.assertRaises(p.Unavailable):
                f.control_client().accept(reseal(value))
        f = self.fixture()
        value = f.control_package()
        value["credential"] = "fake"
        with self.assertRaises(p.Unavailable):
            f.control_client().accept(reseal(value))

    def test_HP_T40_producer_state_write_attempt(self):
        f = self.fixture()
        before = f.s.store.verify()
        f.values["governance_projection"]["authority_effect"] = "STATE_WRITE"
        with self.assertRaises(p.Unavailable):
            f.response()
        self.assertEqual(f.s.store.verify(), before)
        tree = ast.parse(p.SELF.read_text())
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"append", "execute", "commit"}
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "store"
            for node in ast.walk(tree)))

    def test_HP_T41_capability_issuance_attempt(self):
        f = self.fixture()
        for method in ("issue", "activate", "consume", "refund", "retry", "state_journal_write"):
            self.assertFalse(hasattr(p.HostObservationProducer, method))
            self.assertFalse(hasattr(p.ObservationBoundary, method))
        query = f.query()
        query["kind"] = "ISSUE_CAPABILITY"
        with self.assertRaises(p.Unavailable):
            p.HostObservationProducer(f.sources, f.context).observe(query)
        self.assertFalse(f.values["capability_state"]["consumed"])

    def test_HP_T42_corrupt_readonly_journal_no_repair(self):
        f = self.fixture()
        with sqlite3.connect(f.s.store.handle.path) as conn:
            conn.execute("UPDATE projection SET body=?", (b"{}",))
        before = Path(f.s.store.handle.path).read_bytes()
        with f.channels() as (boundary, _):
            with self.assertRaises(p.Unavailable):
                f.preflight(boundary)
        self.assertEqual(Path(f.s.store.handle.path).read_bytes(), before)
        with self.assertRaises(a.StoreBlocked):
            f.s.store.verify()

    def test_HP_T43_cross_source_version_drift(self):
        f = self.fixture()
        producer = p.HostObservationProducer(f.sources, f.context)
        client = p.HostObservationClient(f.sources, f.context)
        client.accept(producer.observe(f.query("nonce_one")), "nonce_one")
        f.versions["grant"] += 1
        with self.assertRaises(p.Unavailable) as caught:
            client.accept(producer.observe(f.query("nonce_two")), "nonce_two")
        self.assertEqual(caught.exception.reason, "CROSS_SOURCE_DRIFT")

    def test_HP_T44_producer_crash(self):
        f = self.fixture()
        producer = p.HostObservationProducer(f.sources, f.context)
        def crash():
            raise RuntimeError("secret-bearing-provider-diagnostic")
        f.readers["authority"] = replace(f.readers["authority"], sample=crash)
        f.sources = f.make_sources()
        producer = p.HostObservationProducer(f.sources, f.context)
        with self.assertRaises(p.Unavailable) as caught:
            producer.observe(f.query())
        self.assertTrue(producer.invalid)
        self.assertNotIn("secret-bearing", str(caught.exception))
        with self.assertRaises(p.Unavailable):
            producer.observe(f.query("after_crash"))

    def test_HP_T45_launcher_crash(self):
        f = self.fixture()
        reader, writer = os.pipe()
        os.write(writer, (10).to_bytes(4,"big") + b"partial")
        os.close(writer)
        try:
            with self.assertRaises(launcher.Rejected):
                launcher.read_frame(reader, 4096)
        finally:
            os.close(reader)
        with mock.patch.object(launcher, "read_frame", side_effect=RuntimeError("secret crash")), \
                mock.patch.object(os, "write") as output:
            code = launcher.main(["--phase","MUTATION","--run-id","run_fixture",
                "--binding-digest","sha256:"+"0"*64])
        self.assertEqual(code, 65)
        self.assertNotIn("secret crash", repr(output.call_args))
        self.assertIn(b'"automatic_restart":false', output.call_args.args[1])

    def test_HP_T46_restart_no_trust_no_refund(self):
        f = self.fixture([h.created()])
        f.s.mutation(f.profile, f.envelope)
        state = f.s.store.verify()
        handle = f.s.store.handle
        f.s.store.close()
        exit_code, report = h.isolated_child("--reopen-budget-child", {"handle": asdict(handle)})
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["count"], 1)
        self.assertTrue(report["replacement_reserve_denied"])
        self.assertEqual(report["network_attempts"], 0)
        f.s.store = a.LiveEvidenceStore(handle)
        f.s.worker.store = f.s.store
        f.context["run_id"] = "replacement_run"
        with self.assertRaises(p.Unavailable):
            f.accept()
        # The frozen worker itself enforces durable budget despite fresh IDs.
        f.s.configure("MUTATION", run_id="replacement_run")
        new_profile, new_envelope = f.s.grant()
        with self.assertRaises((a.Denied, h.shared.Denied)):
            f.s.mutation(new_profile, new_envelope)
        self.assertEqual(f.s.store.verify()["counts"], state["counts"])
        self.assertEqual(f.s.peer.headers, 1)

    def test_HP_T47_host_failure_zero_fd5(self):
        f = self.fixture()
        f.host_valid = False
        # Qualification is before channel/FD5 exposure, including boundary init.
        reads, clients = [], []
        with mock.patch.object(launcher, "read_frame", side_effect=lambda *args: reads.append(args[0])), \
                mock.patch.object(a.httpx.AsyncClient, "__init__", side_effect=lambda *args: clients.append(True)):
            with self.assertRaises(p.Unavailable):
                p.ObservationBoundary(f.sources, f.packet)
        self.assertEqual((reads, clients), ([], []))
        f.host_valid = True
        f.values["authority"]["authorized"] = False
        reads, clients = self.launcher_denied(f)
        self.assertEqual((reads, clients), ([], []))

    def test_HP_T48_control_failure_zero_client(self):
        f = self.fixture()
        f.control_facts["alive"] = False
        reads, clients = self.launcher_denied(f)
        self.assertEqual((reads, clients), ([], []))
        self.assertEqual(f.s.peer.connects, 0)

    def test_HP_T49_network_failure_zero_fd5(self):
        f = self.fixture()
        f.s.network_source = False
        reads, clients = self.launcher_denied(f)
        self.assertEqual((reads, clients), ([], []))

    def test_HP_T50_source_loss_after_exposure_no_second_post(self):
        f = self.fixture([h.created()])
        original = h.Stream.read
        async def loss(stream, *args, **kwargs):
            await h.asyncio.sleep(0.05)
            f.host_valid = False
            await h.asyncio.sleep(0.4)
            return await original(stream, *args, **kwargs)
        with f.channels() as (boundary, errors):
            validator = cap.CapabilityValidator(trusted_grant_resolver=boundary.grant,
                trusted_state_reader=boundary.state, trusted_clock=boundary.clock)
            host = a.LiveHostReads(boundary.authority, validator, boundary.baseline, boundary.target,
                boundary.revocation, boundary.credential_reference, boundary.caller, boundary.clock,
                boundary.runtime, boundary.network, boundary.lifecycle, boundary.source_qualified)
            worker = a.LiveWorker(f.s.store, host, f.s.credential, f.s.runtime, f.s.network, f.s.run)
            with h.native_emulator(f.s.peer), mock.patch.object(h.Stream, "read", loss):
                outcome = worker.mutate_one_item(f.profile, f.envelope, f.s.binding)
            self.assertEqual(outcome.knowledge, "UNKNOWN")
            self.assertEqual(outcome.control, "STOPPED")
            with self.assertRaises(a.Denied):
                worker.mutate_one_item(f.profile, f.envelope, f.s.binding)
        self.assertEqual(f.s.store.verify()["counts"]["MUTATION"], 1)
        self.assertEqual(f.s.peer.headers, 1)
        self.assertEqual([r["method"] for r in f.s.peer.requests], ["POST"])

    def test_HP_T51_unsupported_native_api_unqualified_foreground(self):
        with mock.patch.object(sys, "platform", "unsupported"):
            with self.assertRaises(p.Unavailable):
                p.DarwinReadOnlyObservations()
        with mock.patch.object(p.ctypes, "CDLL", side_effect=OSError("not available")):
            with self.assertRaises(p.Unavailable):
                p.DarwinReadOnlyObservations()
        native = object.__new__(p.DarwinReadOnlyObservations)
        with mock.patch.object(native, "process", return_value={"process_group":1, "terminal_foreground_group":1}), \
                mock.patch.object(os, "isatty", return_value=False):
            with self.assertRaises(p.Unavailable):
                native.foreground(os.getpid(), 0)
        self.assertFalse(launcher._native_primitives())

    def test_HP_T52_synthetic_positive_no_authority_admission(self):
        f = self.fixture()
        with f.channels() as (boundary, errors):
            self.assertTrue(f.preflight(boundary))
            self.assertEqual(boundary.baseline(), f.s.runtime.implementation_commit)
            self.assertEqual(boundary.caller(), "caller_fixture")
        self.assertEqual(f.s.store.verify()["counts"], {})
        self.assertFalse(f.values["capability_state"]["consumed"])
        self.assertEqual(f.values["governance_projection"]["authority_effect"], "NONE")
        self.assertEqual(f.values["governance_projection"]["execution_admission"], "NONE")
        with self.assertRaises(launcher.Rejected):
            launcher.establish_boundaries(f.packet)

    def test_HP_R01_preflight_no_cap_budget_reservation_consumption(self):
        f = self.fixture()
        before_state = f.s.store.verify()
        before_db = Path(f.s.store.handle.path).read_bytes()
        before_grants = copy.deepcopy(f.s.grants)
        before_cap = copy.deepcopy(f.values["capability_state"])
        with f.channels() as (boundary, errors):
            self.assertTrue(f.preflight(boundary))
            self.assertTrue(f.preflight(boundary))
        self.assertEqual(f.s.store.verify(), before_state)
        self.assertEqual(Path(f.s.store.handle.path).read_bytes(), before_db)
        self.assertEqual(f.s.grants, before_grants)
        self.assertEqual(f.values["capability_state"], before_cap)
        self.assertEqual(before_state["counts"], {})
        self.assertEqual(before_state["reservations"], {})
        self.assertEqual(f.s.peer.connects, 0)

    def test_HP_R02_real_framed_launcher_positive_offline(self):
        f = self.fixture([h.created()])
        lease = {**asdict(f.s.credential), "not_after": f.s.credential.not_after.isoformat(),
                 "material": f.s.credential.material.decode()}
        reads = []
        def injected(fd, maximum, timeout=1):
            reads.append(fd)
            self.assertEqual(fd, 5)
            return a._canonical(lease)
        f.s.store.close()
        with f.channels() as (boundary, errors), mock.patch.object(launcher, "read_frame", injected), h.native_emulator(f.s.peer):
            code = launcher.run_bound(a, f.packet, boundary)
        self.assertEqual(code, 0)
        self.assertEqual(reads, [5])
        reopened = a.LiveEvidenceStore(f.s.store.handle)
        try:
            self.assertEqual(reopened.verify()["counts"]["MUTATION"], 1)
        finally:
            reopened.close()
        self.assertEqual(f.s.peer.headers, 1)
        self.assertFalse(a.shared.Outcome.__dataclass_fields__["execution_admission"].default)

    def test_HP_R03_fd4_no_generic_rpc(self):
        f = self.fixture()
        for field in ("url", "sql", "path", "module", "config", "operation"):
            query = f.query()
            query[field] = "caller_override"
            with self.assertRaises(p.Unavailable):
                p.validate_query(query)

    def test_HP_R04_clock_domains_cannot_extend_governance(self):
        f = self.fixture()
        f.values["grant"]["not_after"] = (f.s.now - timedelta(seconds=1)).isoformat()
        f.envelope = replace(f.envelope, not_after=f.s.now-timedelta(seconds=1))
        f.continuous, f.monotonic = 1, 1
        self.denied_preflight(f)

    def test_HP_R05_control_heartbeat_gap_terminal(self):
        f = self.fixture()
        producer = p.ControlObservationProducer(f.sources, f.context)
        producer.sample()
        f.continuous += p.HEARTBEAT_NS + 1
        with self.assertRaises(p.Unavailable):
            producer.sample()
        f.continuous -= p.HEARTBEAT_NS + 1
        with self.assertRaises(p.Unavailable):
            producer.sample()

    def test_HP_R06_secret_bearing_source_failure_redacted(self):
        f = self.fixture()
        f.values["credential_reference"]["material"] = "forbidden"
        with self.assertRaises(p.Unavailable) as caught:
            f.response()
        self.assertNotIn("forbidden", str(caught.exception))
        self.assertEqual(f.s.store.verify()["counts"], {})


    def test_HP_R07_invalid_operation_zero_fd5(self):
        f = self.fixture()
        f.packet["operation"] = {"name": "ARBITRARY_POST", "url": "synthetic.invalid"}
        reads, clients = self.launcher_denied(f)
        self.assertEqual((reads, clients), ([], []))

    def test_HP_R08_reusable_mutation_grant_zero_fd5(self):
        f = self.fixture()
        f.envelope = replace(f.envelope, consumption_policy=cap.REUSABLE)
        f.values["grant"]["consumption_policy"] = cap.REUSABLE
        f.packet["envelope"]["consumption_policy"] = cap.REUSABLE
        reads, clients = self.launcher_denied(f)
        self.assertEqual((reads, clients), ([], []))

    def test_HP_R09_clock_sample_cannot_extend_expiry(self):
        f = self.fixture()
        f.values["clock"]["trusted_now"] = (f.s.now-timedelta(seconds=0.5)).isoformat()
        f.envelope = replace(f.envelope, not_after=f.s.now-timedelta(seconds=0.25))
        f.values["grant"]["not_after"] = f.envelope.not_after.isoformat()
        self.denied_preflight(f)

    def test_HP_R10_production_bootstrap_rejects_test_runtime(self):
        f = self.fixture()
        args = {"--phase": f.s.run.phase, "--run-id": f.s.run.run_id,
                "--binding-digest": launcher._digest(f.packet["runtime"])}
        with self.assertRaises(launcher.Rejected) as caught:
            launcher.bootstrap(f.packet, args)
        self.assertEqual(caught.exception.code, 65)
        self.assertFalse(launcher._native_primitives())

    def test_HP_R11_fd6_numeric_boolean_confusion_rejected(self):
        for field, value in (("network_generation", True), ("lifecycle_generation", True),
                             ("foreground", 1), ("alive", 1), ("terminal_open", 1)):
            f = self.fixture()
            package = f.control_package()
            package[field] = value
            with self.assertRaises(p.Unavailable):
                f.control_client().accept(reseal(package))
        f = self.fixture()
        response = f.response()
        response["observations"]["authority"]["source_generation"] = True
        self.deny_accept(f, response)

    def test_HP_R12_partial_frame_has_single_deadline(self):
        reader, writer = os.pipe()
        done = threading.Event()
        second_half_sent = threading.Event()
        def delayed():
            os.write(writer, b"\x00\x00")
            done.wait(0.14)
            os.write(writer, b"\x00\x08")
            second_half_sent.set()
        thread = threading.Thread(target=delayed)
        thread.start()
        start = time.monotonic()
        try:
            with self.assertRaises(p.Unavailable) as caught:
                p.read_frame(reader, p.HOST_MAX)
            elapsed = time.monotonic() - start
            self.assertTrue(second_half_sent.is_set())
            self.assertEqual(caught.exception.reason, "FRAME_TIMEOUT")
            self.assertGreaterEqual(elapsed, 0.16)
            self.assertLess(elapsed, 0.30)
        finally:
            done.set(); thread.join(0.4)
            os.close(reader); os.close(writer)


    def test_HP_R13_same_pid_keeps_independent_reader_provenance(self):
        f = self.fixture()
        self.assertEqual(f.host.identity, f.control.identity)
        self.assertNotEqual(f.sources.catalog_digest, f.sources.control_catalog_digest)
        self.assertNotEqual(f.host.epoch, f.control.epoch)
        self.assertNotEqual(f.host.channel_role, f.control.channel_role)
        self.assertTrue(f.sources.qualify("HOST", f.context, 4))
        self.assertTrue(f.sources.qualify("CONTROL", f.context, 6))
        def host_proof_for_control(role, reg, context, fd):
            proof = f.provenance(role, reg, context, fd)
            proof["catalog_digest"] = f.sources.catalog_digest
            return proof
        f.sources._provenance = host_proof_for_control
        with self.assertRaises(p.Unavailable):
            f.control_client().accept(f.control_package())

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProducerTests)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    methods = [name for name in dir(ProducerTests) if name.startswith("test_HP_T")]
    print(json.dumps({"mandatory_methods": len(methods), "tests": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "real_credential_attempts": len(h.REAL_CREDENTIAL_ATTEMPTS),
        "real_network_attempts": len(h.REAL_NETWORK_ATTEMPTS),
        "violations": h.VIOLATIONS, "production_sources_established": False,
        "execution_admission": "NONE"}))
    raise SystemExit(0 if result.wasSuccessful() and len(methods) == 52 and not h.VIOLATIONS else 1)

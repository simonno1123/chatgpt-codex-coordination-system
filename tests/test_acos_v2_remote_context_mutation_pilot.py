"""T01-T48 plus independent offline regressions. No real network is permitted.

The guard is installed before loading pilot/dependency modules and retained for
the entire suite. Any accidental DNS/connect/TLS or credential lookup becomes
a test failure; the suite stops on its first failure. Fixture HTTP streams never
perform those operations. Temporary databases are the only runtime artifacts.
"""

import asyncio
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timezone
import importlib.util
import io
import logging
import multiprocessing
import os
from pathlib import Path
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
VIOLATIONS = []
_SECRET_ENV = {"OPENAI_API_KEY", "OPENAI_ADMIN_KEY", "AZURE_OPENAI_API_KEY"}
_PATCHES = []


def _blocked(name):
    def block(*args, **kwargs):
        VIOLATIONS.append(name)
        raise AssertionError("offline boundary violation: " + name)
    return block


def _install_guard():
    for owner, name in [(socket, "getaddrinfo"), (socket, "gethostbyname"),
                        (socket, "gethostbyname_ex"), (socket, "create_connection"),
                        (socket.socket, "connect"), (socket.socket, "connect_ex"),
                        (ssl.SSLContext, "wrap_socket"), (urllib.request, "getproxies"),
                        (urllib.request, "getproxies_environment"), (urllib.request, "proxy_bypass")]:
        patch = mock.patch.object(owner, name, _blocked(name))
        patch.start()
        _PATCHES.append(patch)
    old_getitem = os._Environ.__getitem__

    def getenv(self, key):
        if type(key) is str and key.upper() in _SECRET_ENV:
            VIOLATIONS.append("credential environment lookup")
            raise AssertionError("offline credential boundary violation")
        return old_getitem(self, key)
    patch = mock.patch.object(os._Environ, "__getitem__", getenv)
    patch.start()
    _PATCHES.append(patch)
    old_open = io.open
    def guarded_open(file, *args, **kwargs):
        if isinstance(file, (str, os.PathLike)):
            name = Path(file).name.lower()
            if name.startswith(".env") or name.endswith(".keychain") or name.endswith(".keychain-db"):
                VIOLATIONS.append("credential file lookup")
                raise AssertionError("offline credential file boundary violation")
        return old_open(file, *args, **kwargs)
    patch = mock.patch.object(io, "open", guarded_open)
    patch.start()
    _PATCHES.append(patch)
    for name in ("Popen",):
        patch = mock.patch.object(subprocess, name, _blocked("external command"))
        patch.start()
        _PATCHES.append(patch)


_install_guard()


def _load(name, filename):
    existing = sys.modules.get(name)
    path = ROOT / "scripts" / filename
    if existing is not None:
        if existing.__file__ != str(path):
            raise RuntimeError("canonical module path mismatch")
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


core = _load("acos_v2_core_substrate", "acos-v2-core-substrate.py")
cap = _load("acos_v2_capability", "acos-v2-capability.py")
m = _load("acos_v2_remote_context_mutation_pilot", "acos-v2-remote-context-mutation-pilot.py")


def message(item_id="msg_fixture_1", text=m.FIXTURE_TEXT):
    return {"id": item_id, "type": "message", "role": "user", "status": "completed",
            "content": [{"type": "input_text", "text": text}]}


def created(*items):
    return m.Reply(body={"object": "list", "data": list(items or (message(),)),
                         "has_more": False})


def listed(*items, more=False):
    return m.Reply(body={"object": "list", "data": list(items), "has_more": more})


class Scenario:
    def __init__(self, replies=(), *, bind=True):
        directory = tempfile.TemporaryDirectory(prefix="acos-remote-context-offline-",
            dir=str(Path(tempfile.gettempdir()).resolve()))
        self.directory = directory
        self.store = m.FixtureStore.create(Path(directory.name))
        self.binding = m.TargetBinding("binding_fixture", 1, "org_fixture", "proj_fixture",
            "conv_fixture_1", "sha256:" + "1" * 64, "credential_fixture", 1)
        if bind:
            self.store.bind_fixture(self.binding)
        self.authority = True
        self.baseline = m.BASELINE
        self.revocation = "ACTIVE"
        self.credential_version = 1
        self.credential_available = True
        self.current_binding = self.binding
        self.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.grants = {}
        self.reference = core.AuthorityReference("auth_fixture", "sha256:" + "2" * 64)
        self.identity = core.ExecutionIdentity("acos_fixture", "offline", "pilot",
            "auth_fixture", "fixture_executor", "attempt_fixture", m.BASELINE)
        self.validator = cap.CapabilityValidator(
            trusted_grant_resolver=self.grants.get,
            trusted_state_reader=lambda cid: cap.CapabilityStateEvidence(cid,
                self.identity, self.reference, "cancel_fixture", "ACTIVE", False),
            trusted_clock=lambda: self.now)
        self.host = m.HostReads(
            authority_reader=lambda reference, identity, profile: self.authority
                and reference == self.reference and identity == self.identity,
            capability_validator=self.validator, baseline_reader=lambda: self.baseline,
            binding_reader=lambda bid: self.current_binding,
            revocation_reader=lambda digest: self.revocation,
            credential_reference_reader=lambda ref: (self.credential_version,
                "org_fixture", "proj_fixture") if self.credential_available else None,
            caller_reader=lambda: "caller_fixture", clock=lambda: self.now)
        self.credential = m.SyntheticCredential("credential_fixture", 1, "fixture-only-secret")
        self.peer = m.FixturePeer(replies)
        self.worker = m.OfflineWorker(self.store, self.host, self.credential, self.peer)

    def grant(self, phase="MUTATION", **changes):
        profile = m.Profile(phase, self.store.handle.store_id, "org_fixture",
            "proj_fixture", "credential_fixture", 1,
            "UNBOUND" if phase == "SETUP" else self.binding.digest,
            0 if phase == "SETUP" else self.binding.generation,
            "submission_fixture", "delivery_fixture", "caller_fixture", **changes)
        envelope = cap.CapabilityEnvelope("cap_" + str(len(self.grants)), "REMOTE_CONTEXT_PILOT_" + phase,
            profile.scope_operation, profile.selector, self.identity, self.reference,
            datetime(2099, 1, 1, tzinfo=timezone.utc),
            cap.SINGLE_USE if phase != "READ_RECONCILIATION" else cap.REUSABLE,
            "cancel_fixture")
        self.grants[envelope.capability_id] = envelope
        return profile, envelope

    def mutation(self, **kwargs):
        profile, envelope = self.grant()
        return self.worker.mutate(profile, envelope, self.binding, **kwargs)

    def read(self, **kwargs):
        profile, envelope = self.grant("READ_RECONCILIATION")
        return self.worker.read(profile, envelope, self.binding, **kwargs)

    def close(self):
        self.directory.cleanup()


class OfflinePilotTests(unittest.TestCase):
    def setUp(self):
        self.scenarios = []
        self.violation_count = len(VIOLATIONS)

    def tearDown(self):
        try:
            self.assertEqual(len(VIOLATIONS), self.violation_count, "unexpected real I/O or credential lookup")
        finally:
            for scenario in self.scenarios:
                scenario.close()

    def fixture(self, replies=(), **kwargs):
        scenario = Scenario(replies, **kwargs)
        self.scenarios.append(scenario)
        return scenario

    def denied_mutation(self, scenario, profile=None, envelope=None):
        if profile is None:
            profile, envelope = scenario.grant()
        with self.assertRaises(m.Denied):
            scenario.worker.mutate(profile, envelope, scenario.binding)
        self.assertEqual(scenario.peer.requests, [])

    def test_T01_authority_missing(self):
        s = self.fixture()
        s.authority = False
        self.denied_mutation(s)
        self.assertEqual(s.store.verify()["counts"], {})

    def test_T02_capability_missing(self):
        s = self.fixture()
        p, _ = s.grant()
        self.denied_mutation(s, p, None)

    def test_T03_stale_baseline(self):
        s = self.fixture()
        s.baseline = "0" * 40
        self.denied_mutation(s)

    def test_T04_stale_generation(self):
        s = self.fixture()
        p, e = s.grant()
        changed = replace(p, generation=2)
        self.denied_mutation(s, changed, e)

    def test_T05_revoked_target(self):
        s = self.fixture()
        s.store.revoke(s.binding)
        self.denied_mutation(s)

    def test_T06_payload_digest_mismatch(self):
        s = self.fixture()
        p, _ = s.grant()
        with self.assertRaises(m.Denied):
            replace(p, payload_sha256="0" * 64)
        self.assertEqual(s.peer.requests, [])

    def test_T07_wire_digest_mismatch(self):
        s = self.fixture()
        p, _ = s.grant()
        with self.assertRaises(m.Denied):
            replace(p, wire_sha256="0" * 64)

    def test_T08_wrong_role_content_profile(self):
        s = self.fixture()
        with self.assertRaises(m.Denied):
            replace(s.binding, content_profile="ASSISTANT_OUTPUT_TEXT")
        p, e = s.grant()
        with self.assertRaises(TypeError):
            s.worker.mutate(p, e, s.binding, role="assistant")
        self.assertEqual(s.peer.requests, [])

    def test_T09_retry_option_is_not_an_input(self):
        s = self.fixture()
        with self.assertRaises(TypeError):
            m.OfflineWorker(s.store, s.host, s.credential, s.peer, retries=1)
        self.assertEqual(s.peer.connects, 0)

    def test_T10_hidden_second_POST(self):
        s = self.fixture([created(), created(message("msg_fixture_2"))])
        original = m.httpx.AsyncClient.send
        async def retry(client, request, **kwargs):
            await original(client, request, **kwargs)
            return await original(client, request, **kwargs)
        with mock.patch.object(m.httpx.AsyncClient, "send", retry):
            result = s.mutation()
        self.assertEqual(len(s.peer.requests), 1)
        self.assertEqual(s.peer.header_sends, 1)
        self.assertEqual(result.knowledge, "UNKNOWN")
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_T11_reservation_commit_failure(self):
        s = self.fixture([created()])
        with self.assertRaises(m.StoreBlocked):
            s.mutation(reservation_fault="FAIL")
        self.assertEqual(s.peer.connects, 0)
        self.assertEqual(s.store.verify()["counts"], {})

    def test_T12_reservation_ACK_loss(self):
        s = self.fixture([created()])
        with self.assertRaises(m.CommitUnknown):
            s.mutation(reservation_fault="ACK_LOSS")
        self.assertEqual(s.peer.connects, 0)
        reopened = m.FixtureStore(s.store.handle)
        self.assertEqual(reopened.verify()["counts"]["MUTATION"], 1)
        with self.assertRaises(m.Denied):
            s.mutation()
        self.assertEqual(s.peer.requests, [])

    def test_T13_connect_failure_no_refund(self):
        s = self.fixture([m.Reply(failure="CONNECT")])
        result = s.mutation()
        self.assertEqual(result.knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual((s.peer.connects, s.peer.header_sends), (1, 0))
        with self.assertRaises(m.Denied):
            s.mutation()

    def test_T14_write_timeout(self):
        s = self.fixture([m.Reply(failure="WRITE")])
        result = s.mutation()
        self.assertEqual(result.knowledge, "UNKNOWN")
        self.assertEqual(s.peer.header_sends, 1)
        self.assertEqual(s.peer.connects, 1)

    def test_T15_response_loss(self):
        s = self.fixture([m.Reply(failure="RESPONSE_LOSS")])
        self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assertEqual(len(s.peer.requests), 1)

    def test_T16_receipt_commit_loss(self):
        s = self.fixture([created()])
        result = s.mutation(receipt_fault="ACK_LOSS")
        self.assertEqual(result.knowledge, "KNOWN_MUTATED")
        self.assertIn("unresolved", result.reason)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)
        with self.assertRaises(m.Denied):
            s.mutation()

    def test_T17_independent_positive_readback(self):
        s = self.fixture([created(), m.Reply(body=message())])
        created_result = s.mutation()
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", created_result.stages)
        result = s.read(item_id="msg_fixture_1")
        self.assertIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", result.stages)
        self.assertFalse(result.execution_admission)
        self.assertEqual([r["method"] for r in s.peer.requests], ["POST", "GET"])

    def test_T18_readback_mismatch(self):
        s = self.fixture([created(), m.Reply(body=message(text=m.FIXTURE_TEXT.rstrip("\n")))])
        s.mutation()
        self.assertEqual(s.read(item_id="msg_fixture_1").control, "QUARANTINED")

    def test_T19_item_ID_lost_reconciliation(self):
        s = self.fixture([m.Reply(failure="RESPONSE_LOSS"), listed(message())])
        s.mutation()
        result = s.read()
        self.assertIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", result.stages)
        self.assertNotIn("REMOTE_REQUEST_ACCEPTED", result.stages)
        stages = [r["stage"] for r in s.store.verify()["receipts"]]
        self.assertNotIn("REMOTE_REQUEST_ACCEPTED", stages)

    def test_T20_zero_matches_remain_unknown(self):
        s = self.fixture([m.Reply(failure="RESPONSE_LOSS"), listed()])
        s.mutation()
        self.assertEqual(s.read().knowledge, "UNKNOWN")

    def test_T21_multiple_matches_quarantine(self):
        s = self.fixture([m.Reply(failure="RESPONSE_LOSS"),
                          listed(message(), message("msg_fixture_2"))])
        s.mutation()
        self.assertEqual(s.read().control, "QUARANTINED")

    def test_T22_duplicate_created_items(self):
        s = self.fixture([created(message(), message("msg_fixture_2")), listed(message())])
        result = s.mutation()
        self.assertEqual(result.control, "QUARANTINED")
        self.assertEqual(len(result.item_ids), 2)
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", s.read().stages)

    def test_T23_read_budget_exhaustion(self):
        s = self.fixture([listed(), listed(), listed()])
        for _ in range(3):
            s.read()
        with self.assertRaises(m.Denied):
            s.read()
        self.assertEqual(len(s.peer.requests), 3)

    def test_T24_credential_unavailable(self):
        s = self.fixture()
        s.credential_available = False
        self.denied_mutation(s)

    def test_T25_target_disappeared(self):
        s = self.fixture([m.Reply(failure="RESPONSE_LOSS"), m.Reply(status=404, body={})])
        s.mutation()
        result = s.read()
        self.assertEqual((result.knowledge, result.presence), ("UNKNOWN", "UNAVAILABLE"))

    def test_T26_redirect_not_followed(self):
        s = self.fixture([m.Reply(status=307, body={}, headers=(
            ("Location", "https://api.openai.com/v1/responses"),))])
        self.assertEqual(s.mutation().control, "QUARANTINED")
        self.assertEqual(len(s.peer.requests), 1)

    def test_T27_wrong_provider_origin(self):
        s = self.fixture()
        with self.assertRaises(m.Denied):
            replace(s.binding, origin="https://other.invalid")
        for bad in ["conv_fixture/../../responses", "conv_x?route=agents",
                    "conv_%2fresponses", "conv_x\nHost: other"]:
            with self.subTest(identifier=bad), self.assertRaises(m.Denied):
                replace(s.binding, conversation_id=bad)

    def test_T28_Responses_route_denied(self):
        s = self.fixture()
        with self.assertRaises(AttributeError):
            s.worker.responses()
        permit = m._OneShot("POST", "/v1/responses", s.peer)
        with self.assertRaises(m.FenceDenied):
            asyncio.run(s.worker._sender.send("POST", "/v1/responses", b"{}", permit, 1))
        self.assertEqual(s.peer.connects, 0)

    def test_T29_Agents_invocation_denied(self):
        s = self.fixture()
        for path in ["/v1/agents", "/v1/codex/turn", "/mcp", "/workspace/agent"]:
            permit = m._OneShot("POST", path, s.peer)
            with self.subTest(path=path), self.assertRaises(m.FenceDenied):
                asyncio.run(s.worker._sender.send("POST", path, b"{}", permit, 1))
        self.assertEqual(s.peer.connects, 0)

    def test_T30_setup_grant_cannot_mutate(self):
        s = self.fixture()
        p, e = s.grant("SETUP")
        self.denied_mutation(s, p, e)

    def test_T31_mutation_grant_cannot_read(self):
        s = self.fixture()
        p, e = s.grant()
        with self.assertRaises(m.Denied):
            s.worker.read(p, e, s.binding)
        self.assertEqual(s.peer.requests, [])

    def test_T32_read_grant_cannot_delete(self):
        s = self.fixture([created(), m.Reply(body=message())])
        s.mutation()
        s.read(item_id="msg_fixture_1")
        p, e = s.grant("READ_RECONCILIATION")
        with self.assertRaises(m.Denied):
            s.worker.dispose(p, e, s.binding, item_id="msg_fixture_1")
        self.assertEqual(len(s.peer.requests), 2)

    def test_T33_disposal_is_not_rollback(self):
        s = self.fixture()
        p, e = s.grant("DISPOSAL", item_ids=("msg_fixture_1",))
        with self.assertRaises(m.Denied):
            s.worker.dispose(p, e, s.binding, item_id="msg_fixture_1", rollback=True)
        self.assertEqual(s.peer.requests, [])

    def test_T34_worker_restart_cannot_refund(self):
        s = self.fixture([created()])
        s.mutation()
        restarted = m.OfflineWorker(s.store, s.host, s.credential, m.FixturePeer([created()]))
        p, e = s.grant()
        with self.assertRaises(m.Denied):
            restarted.mutate(p, e, s.binding)
        self.assertEqual(restarted.peer.connects, 0)

    def test_R67_reopen_preserves_consumption(self):
        s = self.fixture([created()])
        s.mutation()
        reopened = m.FixtureStore(s.store.handle)
        restarted = m.OfflineWorker(reopened, s.host, s.credential, m.FixturePeer([created()]))
        p, e = s.grant()
        with self.assertRaises(m.Denied):
            restarted.mutate(p, e, s.binding)

    def test_T35_new_submission_ID_cannot_restore_budget(self):
        s = self.fixture([created()])
        s.mutation()
        p, e = s.grant()
        p = replace(p, submission_id="submission_new")
        e = replace(e, target=p.selector)
        s.grants[e.capability_id] = e
        with self.assertRaises(m.Denied):
            s.worker.mutate(p, e, s.binding)
        self.assertEqual(len(s.peer.requests), 1)

    def test_R68_new_delivery_ID_cannot_restore_budget(self):
        s = self.fixture([created()])
        s.mutation()
        p, e = s.grant()
        p = replace(p, delivery_id="delivery_new")
        e = replace(e, target=p.selector)
        s.grants[e.capability_id] = e
        with self.assertRaises(m.Denied):
            s.worker.mutate(p, e, s.binding)

    def test_R69_expiry_never_refunds(self):
        s = self.fixture([created()])
        s.mutation()
        s.now = datetime(2100, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(m.Denied):
            s.mutation()
        s.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(m.Denied):
            s.mutation()
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_R70_second_headers_send_fence(self):
        s = self.fixture()
        permit = m._OneShot("POST", "/v1/conversations/conv_fixture_1/items", s.peer)
        request = m.httpcore.Request("POST", m.ORIGIN + permit.path)
        asyncio.run(permit.trace("http11.send_request_headers.started", {"request": request}))
        with self.assertRaises(m.FenceDenied):
            asyncio.run(permit.trace("http11.send_request_headers.started", {"request": request}))
        self.assertEqual(s.peer.header_sends, 1)

    def test_R75_proxy_override_not_supported(self):
        s = self.fixture()
        with self.assertRaises(TypeError):
            m.OfflineWorker(s.store, s.host, s.credential, s.peer, proxy="http://127.0.0.1:1")

    def test_T37_per_request_overrides_fenced(self):
        s = self.fixture([created()])
        original = m.httpx.AsyncClient
        calls = []
        def observed(*args, **kwargs):
            calls.append(kwargs)
            return original(*args, **kwargs)
        with mock.patch.object(m.httpx, "AsyncClient", observed):
            s.mutation()
        self.assertFalse(calls[0]["trust_env"])
        self.assertFalse(calls[0]["follow_redirects"])
        self.assertIsNone(calls[0]["proxy"])
        self.assertIsNone(calls[0]["mounts"])
        with self.assertRaises(TypeError):
            m.OfflineWorker(s.store, s.host, s.credential, s.peer, trust_env=True)

        replay = self.fixture([m.Reply(status=307, body={}, headers=(
            ("Location", m.ORIGIN + "/v1/conversations/conv_fixture_1/items"),)), created()])
        original_send = m.httpx.AsyncClient.send
        async def override(client, request, **kwargs):
            kwargs["follow_redirects"] = True
            return await original_send(client, request, **kwargs)
        with mock.patch.object(m.httpx.AsyncClient, "send", override):
            self.assertEqual(replay.mutation().knowledge, "UNKNOWN")
        self.assertEqual(replay.peer.header_sends, 1)
        self.assertEqual(len(replay.peer.requests), 1)

    def test_T38_proxy_auth_replay_blocked(self):
        s = self.fixture([created(), created()])
        with self.assertRaises(TypeError):
            m.OfflineWorker(s.store, s.host, s.credential, s.peer, proxy="http://127.0.0.1:1")
        class ReplayAuth(m.httpx.Auth):
            def auth_flow(self, request):
                yield request
                yield request
        with mock.patch.object(m.httpx.AsyncClient, "_build_request_auth",
                               lambda *args, **kwargs: ReplayAuth()):
            self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assertEqual(s.peer.header_sends, 1)
        self.assertEqual(len(s.peer.requests), 1)

    def test_T36_store_reset_corruption_and_foreign_format(self):
        s = self.fixture([created()])
        s.mutation()
        with closing(sqlite3.connect(s.store.handle.path)) as c, c:
            c.execute("UPDATE projection SET body=?", (b"{}",))
        with self.assertRaises(m.StoreBlocked):
            m.FixtureStore(s.store.handle)
        t = self.fixture()
        Path(t.store.handle.path).unlink()
        with self.assertRaises(m.StoreBlocked):
            m.FixtureStore(t.store.handle)
        u = self.fixture()
        with closing(sqlite3.connect(u.store.handle.path)) as c, c:
            c.execute("DROP TRIGGER metadata_no_update")
            c.execute("UPDATE metadata SET format='acos-v2-coordination/2'")
        with self.assertRaises(m.StoreBlocked):
            m.FixtureStore(u.store.handle)

    def test_T40_exact_bytes_shapes_and_strict_JSON(self):
        variants = [m.FIXTURE_TEXT.rstrip("\n"), m.FIXTURE_TEXT.replace("\n", "\r\n"),
                    m.FIXTURE_TEXT.upper(), m.FIXTURE_TEXT + " ", "é", "e\u0301"]
        for text in variants:
            self.assertFalse(m.exact_item(message(text=text)))
        wrong = [dict(message(), type="other"), dict(message(), role="assistant"),
                 dict(message(), status="in_progress"), dict(message(), content=[]),
                 dict(message(), content=message()["content"] * 2),
                 dict(message(), content=[{"type": "output_text", "text": m.FIXTURE_TEXT}])]
        for item in wrong:
            self.assertFalse(m.exact_item(item))
        with self.assertRaises(m.Denied):
            m._strict_json(b'{"id":"msg_x","id":"msg_y"}')
        with self.assertRaises(m.Denied):
            m._strict_json(b'{"value":NaN}')

    def test_R73_no_auto_pagination_or_GET_retry(self):
        s = self.fixture([listed(more=True), m.Reply(failure="RESPONSE_LOSS"), listed()])
        s.read()
        self.assertEqual(len(s.peer.requests), 1)
        s.read()
        self.assertEqual(len(s.peer.requests), 2)
        p, e = s.grant("READ_RECONCILIATION")
        s.worker.read(p, e, s.binding, after="msg_page_cursor")
        self.assertEqual(len(s.peer.requests), 3)
        self.assertEqual(s.store.verify()["counts"]["READ"], 3)

    def test_R71_target_revoked_during_connect(self):
        s = self.fixture([created()])
        original = m.FixturePeer._next
        def revoke(peer):
            s.revocation = "REVOKED"
            return original(peer)
        with mock.patch.object(m.FixturePeer, "_next", revoke):
            result = s.mutation()
        self.assertEqual(result.knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual(s.peer.header_sends, 0)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_R72_credential_version_changes_before_headers(self):
        s = self.fixture([created()])
        original = m.FixturePeer._next
        def rotate(peer):
            s.credential_version = 2
            return original(peer)
        with mock.patch.object(m.FixturePeer, "_next", rotate):
            result = s.mutation()
        self.assertEqual(result.knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual(s.peer.requests, [])

    def test_T47_secret_bearing_exception_not_recorded_or_logged(self):
        s = self.fixture([m.Reply(failure="SECRET_ERROR")])
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root = logging.getLogger()
        old_level = root.level
        root.setLevel(logging.DEBUG)
        root.addHandler(handler)
        try:
            s.mutation()
        finally:
            root.removeHandler(handler)
            root.setLevel(old_level)
        serialized = m._canonical(s.store.verify())
        self.assertNotIn(b"fixture-only-secret", serialized)
        self.assertNotIn("fixture-only-secret", stream.getvalue())
        self.assertNotIn("fixture-only-secret", repr(s.credential))

    def test_T43_setup_empty_body_and_lost_ACK_no_replacement(self):
        s = self.fixture([m.Reply(body={"id": "conv_created_fixture"})], bind=False)
        p, e = s.grant("SETUP")
        result = s.worker.setup(p, e, binding_id="created_binding")
        self.assertEqual(result.binding.conversation_id, "conv_created_fixture")
        self.assertEqual(s.peer.requests, [{"method": "POST", "path": "/v1/conversations"}])
        self.assertEqual(s.store.verify()["counts"], {"SETUP": 1})
        t = self.fixture([m.Reply(failure="RESPONSE_LOSS")], bind=False)
        p, e = t.grant("SETUP")
        self.assertEqual(t.worker.setup(p, e, binding_id="created_binding").knowledge, "UNKNOWN")
        with self.assertRaises(m.Denied):
            t.worker.setup(p, e, binding_id="created_binding")

    def test_T44_separate_item_container_disposal_and_history(self):
        s = self.fixture([created(), m.Reply(body=message()),
            m.Reply(body={"id": "conv_fixture_1", "object": "conversation"}),
            m.Reply(status=404, body={}),
            m.Reply(body={"id": "conv_fixture_1", "deleted": True})])
        s.mutation()
        s.read(item_id="msg_fixture_1")
        p, e = s.grant("DISPOSAL", item_ids=("msg_fixture_1",))
        with self.assertRaises(m.Denied):
            s.worker.dispose(p, e, s.binding, container=True)
        item = s.worker.dispose(p, e, s.binding, item_id="msg_fixture_1")
        self.assertEqual(item.reason, "DISPOSAL_UNRESOLVED")
        s.read(item_id="msg_fixture_1")
        container_profile, container_envelope = s.grant("DISPOSAL", allow_container_delete=True)
        container = s.worker.dispose(container_profile, container_envelope, s.binding, container=True)
        self.assertEqual(container.reason, "CONTAINER_DELETED_ITEMS_NOT_PURGED")
        state = s.store.verify()
        self.assertEqual((state["counts"]["DELETE_ITEM"], state["counts"]["DELETE_CONTAINER"]), (1, 1))
        self.assertFalse(state["tombstones"][0]["item_purge_proven"])
        self.assertEqual(container.knowledge, "KNOWN_MUTATED")

    def test_T48_later_absence_preserves_confirmed_history(self):
        s = self.fixture([created(), m.Reply(body=message()), m.Reply(status=404, body={})])
        s.mutation()
        s.read(item_id="msg_fixture_1")
        result = s.read(item_id="msg_fixture_1")
        self.assertEqual((result.knowledge, result.presence), ("KNOWN_MUTATED", "UNAVAILABLE"))
        self.assertTrue(any(r["stage"] == "REMOTE_CONTEXT_MUTATION_CONFIRMED"
                            for r in s.store.verify()["receipts"]))

    def test_T46_absolute_deadline_and_response_size(self):
        s = self.fixture([m.Reply(failure="DEADLINE")])
        with mock.patch.object(m, "REQUEST_DEADLINE", 0.01):
            self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assertEqual(s.peer.header_sends, 1)
        t = self.fixture([m.Reply(raw_body=b" " * (m.MAX_RESPONSE_BYTES + 1))])
        self.assertEqual(t.mutation().knowledge, "UNKNOWN")
        u = self.fixture()
        u.worker._started -= m.FOREGROUND_DEADLINE + 1
        with self.assertRaises(m.Denied):
            u.mutation()
        self.assertEqual(u.peer.connects, 0)

    def test_R53_competing_workers_share_durable_budget(self):
        s = self.fixture([created()])
        p, e = s.grant()
        peers = [s.peer, m.FixturePeer([created()])]
        workers = [s.worker, m.OfflineWorker(m.FixtureStore(s.store.handle),
                                            s.host, s.credential, peers[1])]
        outcomes = []
        def run(worker):
            try:
                outcomes.append(worker.mutate(p, e, s.binding).knowledge)
            except m.Denied:
                outcomes.append("DENIED")
        threads = [threading.Thread(target=run, args=(w,)) for w in workers]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(outcomes), ["DENIED", "KNOWN_MUTATED"])
        self.assertEqual(sum(len(peer.requests) for peer in peers), 1)

    def test_R54_process_restart_does_not_restore_permission(self):
        s = self.fixture([created()])
        s.mutation()
        read_fd, write_fd = os.pipe()
        def child():
            os.close(read_fd)
            try:
                worker = m.OfflineWorker(m.FixtureStore(s.store.handle), s.host,
                                         s.credential, m.FixturePeer([created()]))
                p, e = s.grant()
                worker.mutate(p, e, s.binding)
                result = b"UNEXPECTED_SEND"
            except m.Denied:
                result = b"DENIED"
            except BaseException:
                result = b"ERROR"
            os.write(write_fd, result)
            os.close(write_fd)
        process = multiprocessing.get_context("fork").Process(target=child)
        process.start()
        os.close(write_fd)
        process.join(5)
        self.assertFalse(process.is_alive())
        self.assertEqual(process.exitcode, 0)
        result = os.read(read_fd, 100)
        os.close(read_fd)
        self.assertEqual(result, b"DENIED")

    def test_R55_network_guard_and_proxy_environment_ignored(self):
        s = self.fixture([created()])
        self.assertNotEqual(socket.getaddrinfo.__module__, "socket")
        self.assertNotEqual(socket.socket.connect.__module__, "socket")
        self.assertEqual(VIOLATIONS, [])
        # Only non-secret proxy names are set, and restored without credential reads.
        previous = os.environ.get("HTTPS_PROXY")
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:1"
        try:
            result = s.mutation()
        finally:
            if previous is None:
                del os.environ["HTTPS_PROXY"]
            else:
                os.environ["HTTPS_PROXY"] = previous
        self.assertEqual(result.knowledge, "KNOWN_MUTATED")
        self.assertEqual(VIOLATIONS, [])

    def test_R56_no_arbitrary_URL_transport_or_auth(self):
        s = self.fixture()
        for keyword in ("url", "transport", "auth", "fallback"):
            with self.subTest(keyword=keyword), self.assertRaises(TypeError):
                m.OfflineWorker(s.store, s.host, s.credential, s.peer, **{keyword: object()})
        with self.assertRaises(m.Denied):
            m.SyntheticCredential("credential_fixture", 1, "sk-not-a-fixture-key")

    def test_R57_readback_commit_ack_loss_not_confirmed_to_caller(self):
        s = self.fixture([created(), m.Reply(body=message())])
        s.mutation()
        result = s.read(item_id="msg_fixture_1", receipt_fault="ACK_LOSS")
        self.assertEqual(result.knowledge, "KNOWN_MUTATED")
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", result.stages)
        self.assertIn("unresolved", result.reason)

    def test_T45_disposal_loss_does_not_retry_or_expand(self):
        s = self.fixture([created(), m.Reply(body=message()), m.Reply(failure="RESPONSE_LOSS")])
        s.mutation()
        s.read(item_id="msg_fixture_1")
        p, e = s.grant("DISPOSAL", item_ids=("msg_fixture_1",))
        result = s.worker.dispose(p, e, s.binding, item_id="msg_fixture_1")
        self.assertEqual(result.reason, "DISPOSAL_UNRESOLVED")
        with self.assertRaises(m.Denied):
            s.worker.dispose(p, e, s.binding, item_id="msg_fixture_1")
        with self.assertRaises(m.Denied):
            s.worker.dispose(p, e, s.binding, container=True)
        self.assertEqual(len(s.peer.requests), 3)

    def test_R59_append_only_and_identity_cross_store(self):
        s = self.fixture()
        p, e = s.grant()
        with closing(sqlite3.connect(s.store.handle.path)) as c, c:
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute("DELETE FROM journal")
        t = self.fixture()
        with self.assertRaises(m.Denied):
            t.worker.mutate(p, e, t.binding)
        self.assertEqual(t.peer.requests, [])

    def test_R60_read_without_mutation_reservation_is_observation_only(self):
        s = self.fixture([listed(message())])
        result = s.read()
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", result.stages)
        self.assertEqual(result.knowledge, "NOT_DISPATCHED")
        self.assertFalse(s.store.verify()["receipts"])

    def test_R61_known_item_identity_conflict(self):
        s = self.fixture([created(), listed(message("msg_unrelated"))])
        s.mutation()
        self.assertEqual(s.read().control, "QUARANTINED")

    def test_R62_incomplete_page_does_not_hide_multiplicity(self):
        s = self.fixture([m.Reply(failure="RESPONSE_LOSS"),
                          listed(message(), more=True),
                          listed(message(), message("msg_duplicate"))])
        s.mutation()
        first = s.read()
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", first.stages)
        self.assertEqual(s.read().control, "QUARANTINED")
        self.assertEqual(s.store.verify()["counts"]["READ"], 2)

    def test_R63_provider_trace_identity_is_evidence_only(self):
        response = created()
        s = self.fixture([replace(response, headers=(("x-request-id", "req_fixture_1"),))])
        s.mutation()
        observations = s.store.verify()["observations"]
        self.assertTrue(any(o.get("provider_request_id") == "req_fixture_1" for o in observations))
        self.assertFalse(any(r["stage"] == "REMOTE_CONTEXT_MUTATION_CONFIRMED"
                             for r in s.store.verify()["receipts"]))

    def test_R64_single_use_read_scope_and_exact_disposal_operation(self):
        s = self.fixture([listed()])
        p, e = s.grant("READ_RECONCILIATION")
        e = replace(e, consumption_policy=cap.SINGLE_USE)
        s.grants[e.capability_id] = e
        s.worker.read(p, e, s.binding)
        with self.assertRaises(m.Denied):
            s.worker.read(p, e, s.binding)
        self.assertEqual(len(s.peer.requests), 1)
        t = self.fixture([created(), m.Reply(body=message())])
        t.mutation()
        t.read(item_id="msg_fixture_1")
        p, e = t.grant("DISPOSAL", allow_container_delete=True)
        with self.assertRaises(m.Denied):
            t.worker.dispose(p, e, t.binding, item_id="msg_fixture_1")
        self.assertEqual(len(t.peer.requests), 2)

    def test_R65_new_relay_attempt_and_foreground_expiry_cannot_refund(self):
        s = self.fixture([created()])
        s.mutation()
        worker = m.OfflineWorker(m.FixtureStore(s.store.handle), s.host,
                                  s.credential, m.FixturePeer([created()]))
        p, e = s.grant()
        with self.assertRaises(m.Denied):
            worker.mutate(p, e, s.binding)
        worker._started -= m.FOREGROUND_DEADLINE + 1
        with self.assertRaises(m.Denied):
            worker.mutate(p, e, s.binding)
        self.assertEqual(worker.peer.requests, [])
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_R66_security_scope_headers_are_pinned(self):
        s = self.fixture([created()])
        s.mutation()
        self.assertEqual(s.peer.observed_scopes, [{
            "openai-organization": "org_fixture", "openai-project": "proj_fixture"}])
        self.assertEqual(VIOLATIONS, [])
        self.assertNotEqual(urllib.request.getproxies.__module__, "urllib.request")

    def test_T39_HTTP_pool_reassignment_before_headers(self):
        s = self.fixture([created(), created()])
        native = sys.modules["httpcore._async.http11"].AsyncHTTP11Connection
        original = native.handle_async_request
        invocations = []
        async def unavailable_once(connection, request):
            invocations.append(request.method)
            if len(invocations) == 1:
                raise sys.modules["httpcore._exceptions"].ConnectionNotAvailable()
            return await original(connection, request)
        with mock.patch.object(native, "handle_async_request", unavailable_once):
            result = s.mutation()
        self.assertEqual(result.knowledge, "KNOWN_MUTATED")
        self.assertEqual(len(invocations), 2)
        self.assertEqual(s.peer.header_sends, 1)
        self.assertEqual(len(s.peer.requests), 1)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_T41_duplicate_JSON_cannot_confirm(self):
        s = self.fixture([created(), m.Reply(raw_body=b'{"id":"msg_a","id":"msg_b"}')])
        s.mutation()
        result = s.read(item_id="msg_fixture_1")
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", result.stages)
        self.assertEqual(s.store.verify()["counts"]["READ"], 1)

    def test_T42_extra_content_and_oversize_response(self):
        s = self.fixture([created(), m.Reply(body=dict(message(),
                             content=message()["content"] * 2))])
        s.mutation()
        self.assertEqual(s.read(item_id="msg_fixture_1").control, "QUARANTINED")
        t = self.fixture([created(), m.Reply(raw_body=b" " * (m.MAX_RESPONSE_BYTES + 1))])
        t.mutation()
        result = t.read(item_id="msg_fixture_1")
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", result.stages)
        self.assertEqual(result.knowledge, "KNOWN_MUTATED")

    def test_R74_unexpected_provider_role_quarantined(self):
        s = self.fixture([created(dict(message(), role="assistant"))])
        result = s.mutation()
        self.assertEqual((result.knowledge, result.control), ("KNOWN_MUTATED", "QUARANTINED"))
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", result.stages)


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2, failfast=True)
    finally:
        print("OFFLINE_BOUNDARY: " + ("PASS" if not VIOLATIONS else "FAIL")
              + "; real_network_or_credential_attempts=" + str(len(VIOLATIONS)))
        for patch in reversed(_PATCHES):
            patch.stop()

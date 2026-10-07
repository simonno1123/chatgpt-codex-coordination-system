"""LA-T01--LA-T52 and regressions; guards precede adapter/client import.

All credentials, host observations and network evidence are synthetic. Test-only
transport instrumentation does not qualify a live runtime. Only temporary SQLite
stores and explicitly isolated launcher-test children are runtime artifacts.
"""
from pathlib import Path
from dataclasses import replace, asdict
from datetime import datetime, timezone
from contextlib import contextmanager
import asyncio
import hashlib
import importlib.util
import io
import json
import logging
import os
import pickle
import select
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
DEPENDENCY_ROOT = "/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages"
VIOLATIONS, PATCHES = [], []
REAL_NETWORK_ATTEMPTS, REAL_CREDENTIAL_ATTEMPTS = [], []
SECRET = b"fixture-only-secret"
_ORIGINAL_POPEN = subprocess.Popen

def blocked(name, credential=False):
    def deny(*args, **kwargs):
        VIOLATIONS.append(name)
        (REAL_CREDENTIAL_ATTEMPTS if credential else REAL_NETWORK_ATTEMPTS).append(name)
        raise AssertionError("offline external-effect boundary")
    return deny

def install_guards():
    for owner, name in [(socket, "getaddrinfo"), (socket, "gethostbyname"),
            (socket, "gethostbyname_ex"), (socket, "create_connection"),
            (socket.socket, "connect"), (socket.socket, "connect_ex"),
            (ssl.SSLContext, "wrap_socket"), (ssl.SSLContext, "wrap_bio"),
            (urllib.request, "getproxies"), (urllib.request, "getproxies_environment"),
            (urllib.request, "proxy_bypass")]:
        p = mock.patch.object(owner, name, blocked(name))
        p.start(); PATCHES.append(p)
    old_get = os._Environ.__getitem__
    def environment(self, key):
        if type(key) is str and key.upper() in {"OPENAI_API_KEY", "OPENAI_ADMIN_KEY", "AZURE_OPENAI_API_KEY"}:
            return blocked("credential environment", True)()
        return old_get(self, key)
    p = mock.patch.object(os._Environ, "__getitem__", environment)
    p.start(); PATCHES.append(p)
    for owner, name in [(io, "open"), (__import__("builtins"), "open"), (os, "open")]:
        original = getattr(owner, name)
        def guarded_open(file, *args, _original=original, **kwargs):
            if isinstance(file, (str, os.PathLike)):
                n = Path(file).name.lower()
                if n.startswith(".env") or "keychain" in n or n in {"cookies", "login data"}:
                    return blocked("credential file", True)()
            return _original(file, *args, **kwargs)
        p = mock.patch.object(owner, name, guarded_open)
        p.start(); PATCHES.append(p)
    for owner, name in [(subprocess, "Popen"), (os, "system"), (os, "popen")]:
        p = mock.patch.object(owner, name, blocked("external command"))
        p.start(); PATCHES.append(p)

install_guards()

def load_module(name, path):
    old = sys.modules.get(name)
    if old is not None:
        if old.__file__ != str(path):
            raise RuntimeError("canonical test module conflict")
        return old
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    exec(compile(path.read_bytes(), str(path), "exec"), m.__dict__)
    return m

# Child guards have already been installed. No dependency/client import occurs
# before invoking the real fixed launcher with inherited synthetic FD protocols.
if len(sys.argv) > 1 and sys.argv[1] == "--guarded-launcher-child":
    read_fd, result_fd = int(sys.argv[2]), int(sys.argv[3])
    os.dup2(read_fd, 3); os.dup2(result_fd, 7)
    launcher = load_module("launcher_child", ROOT/"scripts/acos-v2-remote-context-live-launcher.py")
    cli = sys.argv[4:]
    if cli[:1] == ["--signal-wait"]:
        cli = cli[1:]
        original_read = launcher.read_frame
        def signal_wait(fd, maximum, timeout=1.0):
            ready = launcher._canonical({"ready": True})
            os.write(7, len(ready).to_bytes(4, "big")+ready)
            return original_read(fd, maximum, timeout=10)
        launcher.read_frame = signal_wait
    code = launcher.main(cli)
    if VIOLATIONS:
        raise SystemExit(99)
    raise SystemExit(code)

# Test-process-only path exposure, after all external-effect guards.
sys.path.append(DEPENDENCY_ROOT)
core = load_module("acos_v2_core_substrate", ROOT/"scripts/acos-v2-core-substrate.py")
cap = load_module("acos_v2_capability", ROOT/"scripts/acos-v2-capability.py")
shared = load_module("acos_v2_remote_context_mutation_pilot", ROOT/"scripts/acos-v2-remote-context-mutation-pilot.py")
a = load_module("acos_v2_remote_context_live_adapter", ROOT/"scripts/acos-v2-remote-context-live-adapter.py")
launcher = load_module("acos_v2_remote_context_live_launcher", ROOT/"scripts/acos-v2-remote-context-live-launcher.py")

def file_pin(path):
    p = Path(path).resolve()
    s = p.stat()
    return a.FilePin(str(p), hashlib.sha256(p.read_bytes()).hexdigest(), s.st_size, s.st_dev, s.st_ino)

_RUNTIME = None
def runtime_fixture():
    global _RUNTIME
    if _RUNTIME is None:
        deps = []
        for name, version in a.DEPENDENCIES.items():
            dist = a.importlib.metadata.distribution(name)
            files = tuple(file_pin(dist.locate_file(f)) for f in (dist.files or ())
                          if Path(dist.locate_file(f)).is_file())
            deps.append(a.DependencyPin(name, version, DEPENDENCY_ROOT, files))
        _RUNTIME = a.RuntimeBinding(1, a.DESIGN_BASELINE,
            tuple(file_pin(ROOT/"scripts"/f) for f, h in a.SOURCE_PINS.values()),
            file_pin(ROOT/"scripts/acos-v2-remote-context-live-launcher.py"),
            file_pin(ROOT/"scripts/acos-v2-remote-context-live-adapter.py"),
            file_pin(ROOT/"requirements-acos-v2-remote-context-mutation-pilot.txt"),
            file_pin("/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13"),
            file_pin("/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python"),
            file_pin("/Library/Frameworks/Python.framework/Versions/3.13/Python"),
            "3.13.12", "arm64", DEPENDENCY_ROOT, tuple(deps),
            file_pin(Path(DEPENDENCY_ROOT)/"certifi/cacert.pem"), "sha256:" + "3"*64)
    return _RUNTIME

def message(item_id="msg_fixture_1", text=shared.FIXTURE_TEXT):
    return {"id": item_id, "type": "message", "role": "user", "status": "completed",
            "content": [{"type": "input_text", "text": text}]}

def created(*items, **kwargs):
    return shared.Reply(body={"object": "list", "data": list(items or (message(),)), "has_more": False}, **kwargs)

def listed(*items, more=False):
    return shared.Reply(body={"object": "list", "data": list(items), "has_more": more})

class Peer:
    def __init__(self, replies=()):
        self.replies = list(replies)
        self.connects, self.headers, self.requests, self.bodies = 0, 0, [], []
        self.on_connect = None
        self.transport_settings = []

class Stream(a.httpcore.AsyncNetworkStream):
    def __init__(self, peer, reply):
        self.peer, self.reply = peer, reply
        self.buffer, self.response = b"", None
        self.recorded, self.body_recorded = False, False
    async def write(self, data, timeout=None):
        if self.reply.failure == "WRITE":
            raise a.httpcore.WriteTimeout("synthetic write failure")
        self.buffer += data
        if b"\r\n\r\n" in self.buffer:
            head, body = self.buffer.split(b"\r\n\r\n", 1)
            if not self.recorded:
                method, path, protocol = head.split(b"\r\n", 1)[0].decode().split()
                headers = dict(x.split(b":", 1) for x in head.split(b"\r\n")[1:])
                self.expected_length = int(next((v for k, v in headers.items()
                                                if k.lower() == b"content-length"), b"0"))
                self.peer.headers += 1
                self.peer.requests.append({"method": method, "path": path, "protocol": protocol})
                self.recorded = True
            if len(body) == self.expected_length and not self.body_recorded:
                self.peer.bodies.append(body)
                self.body_recorded = True
                self.response = b""
        if self.reply.failure == "SECRET_ERROR":
            raise RuntimeError(SECRET.decode())
    async def read(self, max_bytes, timeout=None):
        if self.reply.failure in {"RESPONSE_LOSS", "READ"}:
            raise a.httpcore.ReadTimeout("synthetic response failure")
        if self.response == b"":
            body = self.reply.raw_body if self.reply.raw_body is not None else a._canonical(self.reply.body)
            headers = self.reply.headers + (("Content-Length", str(len(body))), ("Content-Type", "application/json"))
            head = "HTTP/1.1 " + str(self.reply.status) + " Fixture\r\n"
            head += "".join(k + ": " + v + "\r\n" for k, v in headers) + "\r\n"
            self.response = head.encode() + body
        result, self.response = self.response[:max_bytes], self.response[max_bytes:]
        return result
    async def aclose(self):
        pass
    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        if self.reply.failure == "TLS":
            raise a.httpcore.ConnectError("synthetic TLS failure")
        if (server_hostname != "api.openai.com" or not ssl_context.check_hostname
                or ssl_context.verify_mode != ssl.CERT_REQUIRED):
            raise AssertionError("TLS policy")
        return self
    def get_extra_info(self, info):
        return None

class Backend(a.httpcore.AsyncNetworkBackend):
    def __init__(self, peer):
        self.peer = peer
    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if (host, port, local_address) != ("api.openai.com", 443, None):
            raise AssertionError("sealed destination")
        self.peer.connects += 1
        if self.peer.on_connect:
            self.peer.on_connect()
        reply = self.peer.replies.pop(0) if self.peer.replies else shared.Reply(body={})
        if reply.failure == "CONNECT":
            raise a.httpcore.ConnectError("synthetic connect failure")
        return Stream(self.peer, reply)
    async def connect_unix_socket(self, *args, **kwargs):
        raise AssertionError("no unix route")
    async def sleep(self, *args):
        raise AssertionError("retry path forbidden")

@contextmanager
def native_emulator(peer):
    original = a.httpx.AsyncHTTPTransport.__init__
    def instrument(transport, *args, **kwargs):
        peer.transport_settings.append(dict(kwargs))
        original(transport, *args, **kwargs)
        transport._pool._network_backend = Backend(peer)
    with mock.patch.object(a.httpx.AsyncHTTPTransport, "__init__", instrument):
        yield

class Scenario:
    def __init__(self, replies=(), bind=True):
        self.directory = tempfile.TemporaryDirectory(prefix="acos-remote-context-live-",
            dir=str(Path(tempfile.gettempdir()).resolve()))
        self.store = a.LiveEvidenceStore.create(Path(self.directory.name))
        self.binding = a.TargetBinding("binding_fixture", 1, "org_fixture", "proj_fixture",
            "conv_fixture_1", "sha256:"+"1"*64, "credential_fixture", 1)
        if bind:
            self.store.bind_target(self.binding)
        self.runtime = runtime_fixture()
        self.now = datetime(2030, 1, 1, tzinfo=timezone.utc)
        self.network = a.NetworkQualificationBinding(1, "en_fixture", "synthetic_route", "DISABLED",
            "DIRECT_TLS", "evidence_fixture", "producer_fixture", self.now,
            datetime(2099, 1, 1, tzinfo=timezone.utc),
            tuple((k, "NO") for k in ("TLSTermination", "HTTPRegeneration", "POSTReplayCapability",
                                      "AutomaticRetry", "FallbackHTTPGateway")))
        self.authority, self.source, self.network_source, self.alive = True, True, True, True
        self.revocation, self.credential_version, self.network_generation, self.lifecycle_generation = "ACTIVE", 1, 1, 1
        self.credential_available, self.restart_policy, self.terminal_open = True, "NONE", True
        self.current_binding, self.observed_runtime = self.binding, self.runtime
        self.grants = {}
        self.reference = core.AuthorityReference("auth_fixture", "sha256:"+"2"*64)
        self.identity = core.ExecutionIdentity("acos_fixture", "offline", "live_pilot",
            "auth_fixture", "fixture_executor", "attempt_fixture", a.DESIGN_BASELINE)
        self.peer = Peer(replies)
        self.validator = cap.CapabilityValidator(trusted_grant_resolver=self.grants.get,
            trusted_state_reader=lambda cid: cap.CapabilityStateEvidence(cid, self.identity,
                self.reference, "cancel_fixture", "ACTIVE", False), trusted_clock=lambda: self.now)
        self.host = a.LiveHostReads(
            lambda ref, identity, profile: self.authority and ref == self.reference and identity == self.identity,
            self.validator, lambda: self.runtime.implementation_commit, lambda bid: self.current_binding,
            lambda digest: self.revocation, lambda ref: (self.credential_version, "org_fixture", "proj_fixture")
                if self.credential_available else None, lambda: "caller_fixture", lambda: self.now,
            lambda: self.observed_runtime, lambda producer, evidence: self.network if self.network_source else None,
            self.observation, lambda kind, run: self.source)
        self.configure("MUTATION")

    def observation(self):
        return {"run_id": self.run.run_id, "process_id": self.run.process_id,
                "process_incarnation": self.run.process_incarnation, "parent_id": os.getppid(),
                "parent_chain_digest": self.run.parent_chain_digest,
                "network_generation": self.network_generation, "lifecycle_generation": self.lifecycle_generation,
                "foreground": True, "alive": self.alive, "restart_policy": self.restart_policy,
                "terminal_open": self.terminal_open, "lease_until": time.monotonic() + 0.8}

    def configure(self, phase, run_id="run_fixture"):
        self.run = a.RunBinding(run_id, phase, self.runtime.digest, self.network.digest,
            self.store.handle.store_id, os.getpid(), "process_fixture", os.getppid(),
            self.runtime.parent_chain_digest, self.network_generation, self.lifecycle_generation,
            time.monotonic()+120)
        self.credential = a.CredentialLease("credential_fixture", 1, "org_fixture", "proj_fixture",
            run_id, os.getpid(), datetime(2099, 1, 1, tzinfo=timezone.utc), SECRET)
        self.worker = a.LiveWorker(self.store, self.host, self.credential, self.runtime, self.network, self.run)

    def grant(self, phase=None, **changes):
        phase = phase or self.run.phase
        read_after = changes.pop("read_after", None)
        contract = shared.Profile(phase, self.store.handle.store_id, "org_fixture", "proj_fixture",
            "credential_fixture", 1, "UNBOUND" if phase == "SETUP" else self.binding.digest,
            0 if phase == "SETUP" else 1, "submission_fixture", "delivery_fixture", "caller_fixture", **changes)
        profile = a.LiveProfile(contract, self.runtime.digest, self.network.digest, self.run.run_id, read_after)
        envelope = cap.CapabilityEnvelope("cap_" + str(len(self.grants)), "REMOTE_CONTEXT_PILOT_" + phase,
            profile.scope_operation, profile.selector, self.identity, self.reference,
            datetime(2099, 1, 1, tzinfo=timezone.utc), cap.REUSABLE if phase == "READ_RECONCILIATION"
            else cap.SINGLE_USE, "cancel_fixture")
        self.grants[envelope.capability_id] = envelope
        return profile, envelope

    def mutation(self, profile=None, envelope=None):
        if profile is None:
            profile, envelope = self.grant()
        with native_emulator(self.peer):
            return self.worker.mutate_one_item(profile, envelope, self.binding)

    def read(self, item_id=None, after=None):
        self.configure("READ_RECONCILIATION")
        profile, envelope = self.grant(item_ids=(item_id,) if item_id else (), read_after=after)
        with native_emulator(self.peer):
            if item_id:
                return self.worker.retrieve_item_once(profile, envelope, self.binding, item_id=item_id)
            return self.worker.list_items_once(profile, envelope, self.binding, after=after)

    def close(self):
        self.store.close()
        self.directory.cleanup()

def runtime_packet(s):
    network = {**asdict(s.network), "observed_at": s.network.observed_at.isoformat(),
               "not_after": s.network.not_after.isoformat()}
    return {"runtime": json.loads(a._canonical(asdict(s.runtime))), "run": asdict(s.run),
        "network": network, "profile": {}, "envelope": {}, "target": asdict(s.binding),
        "store": asdict(s.store.handle), "operation": {"name": "MUTATION"},
        "producer": {"host_reference": "host_fixture", "control_reference": "control_fixture",
                     "network_reference": "producer_fixture"}}

class LiveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.scenarios = []
        self.before = len(VIOLATIONS)
    def tearDown(self):
        try:
            self.assertEqual(len(VIOLATIONS), self.before)
        finally:
            for s in self.scenarios:
                s.close()
    def fixture(self, replies=(), **kwargs):
        s = Scenario(replies, **kwargs)
        self.scenarios.append(s)
        return s
    def deny_mutation(self, s, p=None, e=None):
        with self.assertRaises((a.Denied, a.StoreBlocked, shared.Denied, shared.StoreBlocked)):
            s.mutation(p, e)
        self.assertEqual(s.peer.headers, 0)
    def assert_one_mutation(self, s):
        self.assertEqual([r["method"] for r in s.peer.requests], ["POST"])
        self.assertEqual(s.peer.headers, 1)
        self.assertEqual(s.peer.bodies, [a.BODY_BYTES])
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_LA_T01_runtime_binding_mismatch(self):
        s = self.fixture()
        s.observed_runtime = replace(s.runtime, generation=2)
        self.deny_mutation(s)
        self.assertEqual(s.store.verify()["counts"], {})

    def test_LA_T02_wrong_interpreter(self):
        r = runtime_fixture()
        with self.assertRaises(a.Denied):
            replace(r, python_pin=replace(r.python_pin, path="/usr/bin/python3")).verify()
        with self.assertRaises(a.Denied):
            replace(r, python_pin=replace(r.python_pin, sha256="0"*64)).verify()

    def test_LA_T03_source_launcher_drift(self):
        r = runtime_fixture()
        for name in ("adapter_pin", "launcher_pin", "requirements_pin"):
            with self.subTest(name=name), self.assertRaises(a.Denied):
                replace(r, **{name: replace(getattr(r, name), sha256="0"*64)}).verify()

    def test_LA_T04_dependency_drift(self):
        r = runtime_fixture()
        with self.assertRaises(a.Denied):
            replace(r, dependencies=(replace(r.dependencies[0], version="0"),)+r.dependencies[1:]).verify()
        with self.assertRaises(a.Denied):
            replace(r, dependency_location="/tmp/unapproved").verify()

    def test_LA_T05_launcher_wrapper(self):
        s = self.fixture()
        s.run = replace(s.run, parent_chain_digest="sha256:"+"9"*64)
        s.worker.run = s.run
        self.deny_mutation(s)

    def test_LA_T06_restart_policy(self):
        s = self.fixture()
        s.restart_policy = "AUTO"
        self.deny_mutation(s)

    def test_LA_T07_environment_proxy(self):
        s = self.fixture()
        p = runtime_packet(s)
        args = {"--phase": "MUTATION", "--run-id": s.run.run_id,
                "--binding-digest": launcher._digest(p["runtime"])}
        with mock.patch.object(launcher, "_native_primitives", return_value=True), \
                mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://synthetic.invalid"}):
            with self.assertRaises(launcher.Rejected) as caught:
                launcher.bootstrap(p, args)
        self.assertEqual(caught.exception.code, 65)

    def test_LA_T08_caller_url(self):
        s = self.fixture()
        p, e = s.grant()
        with self.assertRaises(TypeError):
            s.worker.mutate_one_item(p, e, s.binding, url="https://synthetic.invalid")
        with self.assertRaises(a.FenceDenied):
            a._operation("POST", "https://synthetic.invalid", a.BODY_BYTES)
        self.assertEqual(s.peer.connects, 0)

    def test_LA_T09_caller_transport(self):
        s = self.fixture()
        with self.assertRaises(TypeError):
            a.LiveNetworkAdapter(s.credential, s.runtime, transport=Backend(s.peer))
        with self.assertRaises(TypeError):
            a.LiveWorker(s.store, s.host, s.credential, s.runtime, s.network, s.run, backend=Backend(s.peer))

    def test_LA_T10_caller_auth_hooks(self):
        s = self.fixture()
        for option in ("auth", "event_hooks", "follow_redirects", "proxy", "retries"):
            with self.subTest(option=option), self.assertRaises(TypeError):
                a.LiveNetworkAdapter(s.credential, s.runtime, **{option: object()})

    def test_LA_T11_redirect(self):
        s = self.fixture([shared.Reply(302, {}, headers=(("Location", "https://synthetic.invalid"),))])
        out = s.mutation()
        self.assertEqual(out.control, "QUARANTINED")
        self.assert_one_mutation(s)
        self.assertEqual(s.peer.connects, 1)

    def test_LA_T12_auth_errors(self):
        for status in (401, 403):
            with self.subTest(status=status):
                s = self.fixture([shared.Reply(status, {})])
                self.assertEqual(s.mutation().knowledge, "UNKNOWN")
                self.assert_one_mutation(s)
                self.assertEqual(s.credential.version, 1)

    def test_LA_T13_rate_limit(self):
        s = self.fixture([shared.Reply(429, {})])
        self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assert_one_mutation(s)

    def test_LA_T14_server_error(self):
        s = self.fixture([shared.Reply(503, {})])
        self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assert_one_mutation(s)

    def test_LA_T15_connect_failure_no_refund(self):
        s = self.fixture([shared.Reply(failure="CONNECT")])
        self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual((s.peer.connects, s.peer.headers), (1, 0))
        self.deny_mutation(s)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)
        self.assertEqual(s.peer.connects, 1)

    def test_LA_T16_tls_failure_no_downgrade(self):
        s = self.fixture([shared.Reply(failure="TLS")])
        self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual((s.peer.connects, s.peer.headers), (1, 0))
        self.deny_mutation(s)

    def test_LA_T17_write_timeout(self):
        s = self.fixture([shared.Reply(failure="WRITE")])
        self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)
        self.assertEqual(len(s.store.verify()["exposure_arms"]), 1)
        self.assertEqual(s.peer.connects, 1)

    def test_LA_T18_response_timeout(self):
        s = self.fixture([shared.Reply(failure="READ")])
        self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assert_one_mutation(s)

    def test_LA_T19_response_loss(self):
        s = self.fixture([shared.Reply(failure="RESPONSE_LOSS")])
        self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assert_one_mutation(s)
        self.assertNotIn("REMOTE_REQUEST_ACCEPTED", [x["stage"] for x in s.store.verify()["receipts"]])

    def test_LA_T20_second_native_headers(self):
        s = self.fixture([created(), created(message("msg_fixture_2"))])
        original = a.httpx.AsyncClient.send
        async def hidden_replay(client, request, **kwargs):
            first = await original(client, request, **kwargs)
            await first.aread()
            await first.aclose()
            return await original(client, request, **kwargs)
        with mock.patch.object(a.httpx.AsyncClient, "send", hidden_replay):
            self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assert_one_mutation(s)
        self.assertEqual(len(s.store.verify()["exposure_arms"]), 1)

    def test_LA_T21_concurrent_native_permit(self):
        s = self.fixture([created(), created()])
        original = a.LiveNetworkAdapter._dispatch
        blocked_results = []
        async def concurrent(sender, operation, permit, remaining):
            results = await asyncio.gather(original(sender, operation, permit, remaining),
                original(sender, operation, permit, remaining), return_exceptions=True)
            blocked_results.extend(x for x in results if isinstance(x, BaseException))
            return next(x for x in results if not isinstance(x, BaseException))
        with mock.patch.object(a.LiveNetworkAdapter, "_dispatch", concurrent):
            self.assertEqual(s.mutation().knowledge, "KNOWN_MUTATED")
        self.assert_one_mutation(s)
        self.assertEqual(len(blocked_results), 1)
        self.assertIsInstance(blocked_results[0], a.FenceDenied)

    def test_LA_T22_altered_native_request(self):
        original = a.httpx.AsyncClient.send
        for alteration in ("method", "path", "body"):
            with self.subTest(alteration=alteration):
                s = self.fixture([created()])
                async def alter(client, request, **kwargs):
                    if alteration == "method":
                        request.method = "PUT"
                    elif alteration == "path":
                        request.url = a.httpx.URL(a.ORIGIN + "/v1/responses")
                    else:
                        request.stream = a.httpx.ByteStream(b"altered")
                    return await original(client, request, **kwargs)
                with mock.patch.object(a.httpx.AsyncClient, "send", alter):
                    self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
                self.assertEqual(s.peer.headers, 0)
                self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_LA_T23_credential_rotation(self):
        s = self.fixture([created()])
        s.peer.on_connect = lambda: setattr(s, "credential_version", 2)
        self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual((s.peer.connects, s.peer.headers), (1, 0))
        self.assertEqual(s.credential.version, 1)

    def test_LA_T24_target_revocation_generation(self):
        s = self.fixture()
        s.store.revoke(s.binding)
        self.deny_mutation(s)
        s2 = self.fixture()
        p, e = s2.grant()
        with self.assertRaises(a.Denied):
            s2.worker.mutate_one_item(p, e, replace(s2.binding, generation=2))
        self.assertEqual(s2.peer.headers, 0)

    def test_LA_T25_real_process_reopen_budget(self):
        s = self.fixture([created()])
        s.mutation()
        handle = asdict(s.store.handle)
        s.store.close()
        payload = {"handle": handle}
        exit_code, report = isolated_child("--reopen-budget-child", payload)
        self.assertEqual(exit_code, 0)
        self.assertEqual(report, {"count": 1, "replacement_reserve_denied": True, "network_attempts": 0})
        s.store = a.LiveEvidenceStore(a.LiveStoreHandle(**handle))
        s.configure("MUTATION", "new_run_fixture")
        with self.assertRaises((a.Denied, shared.Denied)):
            s.mutation()
        self.assertEqual(s.peer.headers, 1)

    def test_LA_T26_new_ids_capability_wrapper(self):
        s = self.fixture([created()])
        s.mutation()
        s.configure("MUTATION", "new_run_fixture")
        p, e = s.grant()
        p = replace(p, contract=replace(p.contract, submission_id="new_submission", delivery_id="new_delivery"))
        e = replace(e, target=p.selector)
        s.grants[e.capability_id] = e
        with self.assertRaises((a.Denied, shared.Denied)):
            s.mutation(p, e)
        self.assertEqual(s.peer.headers, 1)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_LA_T27_sleep_wake(self):
        s = self.fixture([created()])
        s.peer.on_connect = lambda: setattr(s, "lifecycle_generation", 2)
        self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual(s.peer.headers, 0)

    def test_LA_T28_network_transition(self):
        s = self.fixture([created()])
        s.peer.on_connect = lambda: setattr(s, "network_generation", 2)
        self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual(s.peer.headers, 0)

    def test_LA_T29_unknown_gateway_evidence(self):
        s = self.fixture()
        values = dict(s.network.replay_boundary)
        values["FallbackHTTPGateway"] = "UNKNOWN"
        s.network = replace(s.network, replay_boundary=tuple(values.items()))
        s.configure("MUTATION")
        self.deny_mutation(s)
        s2 = self.fixture()
        s2.network_source = False
        self.deny_mutation(s2)

    def test_LA_T30_tls_termination(self):
        s = self.fixture()
        values = dict(s.network.replay_boundary)
        values["TLSTermination"] = "YES"
        s.network = replace(s.network, replay_boundary=tuple(values.items()))
        s.configure("MUTATION")
        self.deny_mutation(s)

    def test_LA_T31_http_regeneration_replay(self):
        for field in ("HTTPRegeneration", "POSTReplayCapability", "AutomaticRetry"):
            s = self.fixture()
            values = dict(s.network.replay_boundary)
            values[field] = "YES"
            s.network = replace(s.network, replay_boundary=tuple(values.items()))
            s.configure("MUTATION")
            self.deny_mutation(s)

    def test_LA_T32_fake_ip_non_failure(self):
        s = self.fixture([created()])
        s.network = replace(s.network, transport_mode="FAKE_IP_TLS")
        s.configure("MUTATION")
        self.assertEqual(s.mutation().knowledge, "KNOWN_MUTATED")
        self.assert_one_mutation(s)

    def test_LA_T33_tun_non_failure(self):
        s = self.fixture([created()])
        s.network = replace(s.network, transport_mode="TUN_TLS")
        s.configure("MUTATION")
        self.assertEqual(s.mutation().knowledge, "KNOWN_MUTATED")
        self.assert_one_mutation(s)

    def test_LA_T34_secret_exception_logging(self):
        s = self.fixture([shared.Reply(failure="SECRET_ERROR")])
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        root = logging.getLogger()
        old_level = root.level
        root.addHandler(handler); root.setLevel(logging.DEBUG)
        try:
            with mock.patch("sys.stdout", output), mock.patch("sys.stderr", output):
                out = s.mutation()
        finally:
            root.removeHandler(handler); root.setLevel(old_level)
        self.assertEqual(out.knowledge, "UNKNOWN")
        self.assertNotIn(SECRET.decode(), output.getvalue())
        self.assertNotIn(SECRET.decode(), repr(s.credential))
        with sqlite3.connect(s.store.handle.path) as c:
            self.assertNotIn(SECRET.decode(), "\n".join(c.iterdump()))
        self.assertEqual(logging.root.manager.disable, 0)

    def test_LA_T35_invocation_routes(self):
        s = self.fixture()
        for path in ("/v1/responses", "/v1/agents", "/v1/codex", "/v1/mcp"):
            with self.assertRaises(a.FenceDenied):
                a._operation("POST", path, a.BODY_BYTES)
        for name in ("request", "send_any", "generic_api_call", "responses", "agents", "codex", "mcp"):
            self.assertFalse(hasattr(s.worker._sender, name))
        self.assertEqual(s.peer.connects, 0)

    def test_LA_T36_unapproved_provider_paths(self):
        for path in ("/v1/files", "/v1/uploads", "/v1/batch", "/v1/anything",
                     "/v1/conversations/conv_fixture_1", "/v1/conversations/conv_x/items?include=secret"):
            with self.assertRaises(a.FenceDenied):
                a._operation("POST", path, a.BODY_BYTES)

    def test_LA_T37_reservation_failure(self):
        s = self.fixture([created()])
        original = s.store.append
        def failure(kind, data):
            if kind == "RESERVE":
                raise a.StoreBlocked("synthetic")
            return original(kind, data)
        with mock.patch.object(s.store, "append", failure):
            self.deny_mutation(s)
        self.assertEqual(s.peer.connects, 0)
        self.assertEqual(s.store.verify()["counts"], {})

    def test_LA_T38_reservation_ack_unknown(self):
        s = self.fixture([created()])
        original = s.store.append
        def ack_loss(kind, data):
            original(kind, data)
            if kind == "RESERVE":
                raise a.CommitUnknown("synthetic")
        with mock.patch.object(s.store, "append", ack_loss):
            self.deny_mutation(s)
        self.assertEqual(s.peer.connects, 0)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)
        self.deny_mutation(s)

    def test_LA_T39_final_preconnect_drift(self):
        s = self.fixture([created()])
        original = s.store.append
        def change(kind, data):
            original(kind, data)
            if kind == "RESERVE":
                s.observed_runtime = replace(s.runtime, generation=2)
        with mock.patch.object(s.store, "append", change):
            self.deny_mutation(s)
        self.assertEqual(s.peer.connects, 0)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_LA_T40_headers_fence_after_handshake(self):
        s = self.fixture([created()])
        s.peer.on_connect = lambda: setattr(s, "observed_runtime", replace(s.runtime, generation=2))
        self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual((s.peer.connects, s.peer.headers), (1, 0))

    def test_LA_T41_exposure_arm_ack_loss(self):
        s = self.fixture([created()])
        original = s.store.append
        def ack_loss(kind, data):
            original(kind, data)
            if kind == "EXPOSURE_ARM":
                raise a.CommitUnknown("synthetic")
        with mock.patch.object(s.store, "append", ack_loss):
            out = s.mutation()
        self.assertEqual(out.knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual(s.peer.headers, 0)
        self.assertEqual(len(s.store.verify()["exposure_arms"]), 1)
        self.deny_mutation(s)

    def test_LA_T42_receipt_persistence_fault(self):
        s = self.fixture([created()])
        original = s.store.append
        def receipt_fault(kind, data):
            if kind == "RECEIPT":
                raise a.CommitUnknown("synthetic")
            return original(kind, data)
        with mock.patch.object(s.store, "append", receipt_fault):
            out = s.mutation()
        self.assertEqual(out.knowledge, "KNOWN_MUTATED")
        self.assertIn("unresolved", out.reason)
        self.assert_one_mutation(s)
        with self.assertRaises((a.Denied, shared.Denied)):
            s.mutation()

    def test_LA_T43_store_integrity_no_repair(self):
        for fault in ("missing", "replaced", "projection", "format", "trigger"):
            with self.subTest(fault=fault):
                s = self.fixture()
                p = Path(s.store.handle.path)
                if fault == "missing":
                    p.unlink()
                elif fault == "replaced":
                    raw = p.read_bytes()
                    p.unlink()
                    p.write_bytes(raw)
                else:
                    with sqlite3.connect(p) as c:
                        if fault == "projection":
                            c.execute("UPDATE projection SET body=?", (b"{}",))
                        elif fault == "format":
                            c.execute("DROP TRIGGER metadata_no_update")
                            c.execute("UPDATE metadata SET format='acos-v2-coordination/2'")
                        else:
                            c.execute("DROP TRIGGER journal_no_update")
                self.deny_mutation(s)
                self.assertEqual(s.peer.connects, 0)
                if fault == "missing":
                    self.assertFalse(p.exists())

    def test_LA_T44_phase_capability_crossing(self):
        for source_phase, requested_phase in (("SETUP", "MUTATION"), ("MUTATION", "READ_RECONCILIATION"),
                                               ("READ_RECONCILIATION", "DISPOSAL")):
            s = self.fixture()
            p_source, e = s.grant(source_phase)
            s.configure(requested_phase)
            p, unused = s.grant()
            with self.assertRaises(a.Denied):
                s.worker._validate(p, e, requested_phase, s.binding)
            self.assertEqual(s.store.verify()["counts"], {})

    def test_LA_T45_read_budget_pagination(self):
        s = self.fixture([listed(), listed(), listed(), listed()])
        for _ in range(3):
            s.read()
        with self.assertRaises((a.Denied, shared.Denied)):
            s.read()
        self.assertEqual([r["method"] for r in s.peer.requests], ["GET"]*3)
        self.assertEqual(s.store.verify()["counts"]["READ"], 3)
        s2 = self.fixture([shared.Reply(failure="RESPONSE_LOSS"), listed(message(), more=True)])
        s2.mutation()
        out = s2.read()
        self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", out.stages)
        self.assertEqual([r["method"] for r in s2.peer.requests], ["POST", "GET"])

    def test_LA_T46_exact_utf8(self):
        for text in (shared.FIXTURE_TEXT.rstrip(), shared.FIXTURE_TEXT.replace("\n", "\r\n"),
                     shared.FIXTURE_TEXT.lower(), shared.FIXTURE_TEXT+" ",
                     shared.FIXTURE_TEXT.replace("fixture", "fixtur\u0065\u0301")):
            self.assertFalse(a.exact_item(message(text=text)))
        s = self.fixture([created(), shared.Reply(body=message(text=shared.FIXTURE_TEXT.rstrip()))])
        s.mutation()
        self.assertEqual(s.read(item_id="msg_fixture_1").control, "QUARANTINED")

    def test_LA_T47_readback_ambiguity(self):
        cases = [listed(), listed(message(), message("msg_fixture_2")),
                 listed(message(), message()), listed(message(), more=True)]
        for reply in cases:
            s = self.fixture([shared.Reply(failure="RESPONSE_LOSS"), reply])
            s.mutation()
            out = s.read()
            if not reply.body["data"]:
                self.assertEqual(out.knowledge, "UNKNOWN")
            if len(reply.body["data"]) > 1:
                self.assertEqual(out.control, "QUARANTINED")
            if reply.body["has_more"]:
                self.assertNotIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", out.stages)
            self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_LA_T48_disposal_separation_no_rollback(self):
        s = self.fixture([created(), shared.Reply(body=message()),
            shared.Reply(body={"id": "conv_fixture_1"}), shared.Reply(404, {}),
            shared.Reply(body={"id": "conv_fixture_1", "deleted": True})])
        s.mutation()
        s.read(item_id="msg_fixture_1")
        s.configure("DISPOSAL")
        p, e = s.grant(item_ids=("msg_fixture_1",))
        with self.assertRaises(TypeError):
            s.worker.delete_item_once(p, e, s.binding, item_id="msg_fixture_1", rollback=True)
        with native_emulator(s.peer):
            s.worker.delete_item_once(p, e, s.binding, item_id="msg_fixture_1")
        s.read(item_id="msg_fixture_1")
        s.configure("DISPOSAL")
        p, e = s.grant(allow_container_delete=True)
        with native_emulator(s.peer):
            out = s.worker.delete_container_once(p, e, s.binding)
        self.assertIn("NOT_PURGED", out.reason)
        state = s.store.verify()
        self.assertEqual(state["counts"], {"MUTATION": 1, "READ": 2, "DELETE_ITEM": 1, "DELETE_CONTAINER": 1})
        self.assertFalse(state["tombstones"][0]["item_purge_proven"])
        self.assertTrue(state["tombstones"][0]["history_preserved"])

    def test_LA_T49_lifetime_signals_isolated_launcher(self):
        s = self.fixture()
        for field in ("alive", "terminal_open"):
            old = getattr(s, field)
            setattr(s, field, False)
            self.deny_mutation(s)
            setattr(s, field, old)
        import signal
        for number, code in ((signal.SIGINT, 130), (signal.SIGTERM, 143), (signal.SIGHUP, 129)):
            with self.assertRaises(launcher.Rejected) as caught:
                launcher._signal(number, None)
            self.assertEqual(caught.exception.code, code)
            launcher._STOP = False
        code, result = isolated_child("--guarded-launcher-child", {},
            cli=["--phase", "MUTATION", "--run-id", "fixture_run", "--binding-digest", "sha256:"+"0"*64])
        self.assertEqual(code, 64)
        self.assertFalse(result["automatic_restart"])
        self.assertEqual(result["authority_effect"], "NONE")

    def test_LA_T50_no_self_certification(self):
        s = self.fixture()
        s.source = False
        self.deny_mutation(s)
        s.source, s.authority = True, False
        self.deny_mutation(s)
        with self.assertRaises(launcher.Rejected) as caught:
            launcher.establish_boundaries(runtime_packet(s))
        self.assertEqual(caught.exception.code, 66)
        s2 = self.fixture()
        p, e = s2.grant()
        s2.grants[e.capability_id] = replace(e, operation="FORGED")
        self.deny_mutation(s2, p, e)

    def test_LA_T51_canonical_identity_instrumentation(self):
        s = self.fixture()
        from types import ModuleType
        duplicate = ModuleType("duplicate_core")
        duplicate.__file__ = core.__file__
        with mock.patch.dict(sys.modules, {"duplicate_core": duplicate}):
            self.deny_mutation(s)
        with mock.patch.object(cap.CapabilityValidator, "validate", lambda *_: cap.ValidationResult("PASS", "fake")):
            self.deny_mutation(s)
        self.assertFalse(launcher._native_primitives())
        p = runtime_packet(s)
        args = {"--phase": "MUTATION", "--run-id": s.run.run_id, "--binding-digest": launcher._digest(p["runtime"])}
        with self.assertRaises(launcher.Rejected):
            launcher.bootstrap(p, args)

    def test_LA_T52_non_authoritative_evidence(self):
        s = self.fixture([created(), shared.Reply(body=message())])
        out = s.mutation()
        confirm = s.read(item_id="msg_fixture_1")
        self.assertFalse(out.execution_admission)
        self.assertIn("REMOTE_CONTEXT_MUTATION_CONFIRMED", confirm.stages)
        state = s.store.verify()
        self.assertTrue(all(r["authority_effect"] == "NONE" for r in state["receipts"]))
        self.assertEqual(len(state["exposure_arms"]), 2)
        self.assertFalse(any(hasattr(s.store, n) for n in ("issue", "accept_result", "state_journal_write")))
        with sqlite3.connect(s.store.handle.path) as c:
            self.assertEqual(c.execute("SELECT format FROM metadata").fetchone()[0], a.FORMAT)
            self.assertNotIn(SECRET.decode(), "\n".join(c.iterdump()))

    def test_R01_native_positive_and_sender_policy(self):
        s = self.fixture([created()])
        out = s.mutation()
        self.assertEqual(out.knowledge, "KNOWN_MUTATED")
        self.assert_one_mutation(s)
        settings = s.peer.transport_settings[0]
        self.assertEqual(settings["retries"], 0)
        self.assertFalse(settings["http2"])
        self.assertTrue(settings["http1"])
        self.assertFalse(settings["trust_env"])
        self.assertIsNone(settings["proxy"])
        self.assertTrue(settings["verify"].check_hostname)

    def test_R02_single_logical_writer(self):
        s = self.fixture()
        with self.assertRaises(a.StoreBlocked):
            a.LiveEvidenceStore(s.store.handle)
        self.assertEqual(s.store.verify()["counts"], {})

    def test_R03_append_only_metadata(self):
        s = self.fixture([created()])
        s.mutation()
        with sqlite3.connect(s.store.handle.path) as c:
            for sql in ("UPDATE journal SET kind='REVOKE'", "DELETE FROM journal",
                        "UPDATE metadata SET store_id='other'", "DELETE FROM metadata"):
                with self.assertRaises(sqlite3.DatabaseError):
                    c.execute(sql)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

    def test_R04_offline_fixture_not_live_boundary(self):
        s = self.fixture()
        with self.assertRaises(a.Denied):
            a.LiveWorker(object.__new__(shared.FixtureStore), s.host, s.credential, s.runtime, s.network, s.run)
        with self.assertRaises(a.Denied):
            a.LiveNetworkAdapter(shared.SyntheticCredential("credential_fixture", 1, SECRET.decode()), s.runtime)
        self.assertNotEqual(shared.FORMAT, a.FORMAT)
        self.assertFalse(hasattr(shared.OfflineWorker, "live"))

    def test_R05_permit_not_serializable(self):
        s = self.fixture([created()])
        permits = []
        original = a._HeaderPermit.__init__
        def capture(permit, *args, **kwargs):
            original(permit, *args, **kwargs); permits.append(permit)
        with mock.patch.object(a._HeaderPermit, "__init__", capture):
            s.mutation()
        with self.assertRaises(a.FenceDenied):
            pickle.dumps(permits[0])
        self.assertEqual(permits[0].count, 1)

    def test_R06_later_absence_preserves_mutation(self):
        s = self.fixture([created(), shared.Reply(404, {})])
        s.mutation()
        out = s.read(item_id="msg_fixture_1")
        self.assertEqual(out.knowledge, "KNOWN_MUTATED")
        self.assertEqual(out.presence, "UNAVAILABLE")
        self.assertTrue(any(r["stage"] == "REMOTE_ITEM_CREATED" for r in s.store.verify()["receipts"]))

    def test_R07_strict_json(self):
        for raw in (b'{"object":"list","object":"list","data":[]}', b'{"x":NaN}'):
            s = self.fixture([shared.Reply(raw_body=raw)])
            self.assertEqual(s.mutation().knowledge, "UNKNOWN")
            self.assert_one_mutation(s)

    def test_R08_response_size_bound(self):
        s = self.fixture([shared.Reply(body={"data": "x"*(a.MAX_RESPONSE_BYTES+1)})])
        self.assertEqual(s.mutation().knowledge, "UNKNOWN")
        self.assert_one_mutation(s)

    def test_R09_setup_does_not_mutate(self):
        s = self.fixture([shared.Reply(body={"id": "conv_fixture_created"})], bind=False)
        s.configure("SETUP")
        p, e = s.grant()
        with native_emulator(s.peer):
            out = s.worker.setup_conversation(p, e, binding_id="new_binding_fixture")
        self.assertEqual(out.binding.conversation_id, "conv_fixture_created")
        self.assertEqual(s.store.verify()["counts"], {"SETUP": 1})
        self.assertEqual(s.peer.bodies, [b"{}"])
        self.assertEqual(s.peer.headers, 1)

    def test_R10_disposal_loss_no_container_fallback(self):
        s = self.fixture([created(), shared.Reply(body=message()),
                          shared.Reply(failure="RESPONSE_LOSS")])
        s.mutation(); s.read(item_id="msg_fixture_1")
        s.configure("DISPOSAL")
        p, e = s.grant(item_ids=("msg_fixture_1",))
        with native_emulator(s.peer):
            out = s.worker.delete_item_once(p, e, s.binding, item_id="msg_fixture_1")
        self.assertEqual(out.reason, "DISPOSAL_UNRESOLVED")
        p, e = s.grant(allow_container_delete=True)
        with self.assertRaises(a.Denied):
            s.worker.delete_container_once(p, e, s.binding)
        self.assertEqual([r["method"] for r in s.peer.requests], ["POST", "GET", "DELETE"])
        self.assertNotIn("DELETE_CONTAINER", s.store.verify()["counts"])

    def test_R11_scope_header_tampering(self):
        original = a.httpx.AsyncClient.send
        for field in ("OpenAI-Project", "OpenAI-Organization", "Authorization", "Host"):
            s = self.fixture([created()])
            async def tamper(client, request, **kwargs):
                request.headers[field] = "synthetic_changed"
                return await original(client, request, **kwargs)
            with mock.patch.object(a.httpx.AsyncClient, "send", tamper):
                self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
            self.assertEqual(s.peer.headers, 0)

    def test_R12_bootstrap_cli_no_import_or_secret(self):
        s = self.fixture()
        for args in ([], ["--module", "arbitrary"], ["--phase", "MUTATION"]*3,
                     ["--phase", "MUTATION", "--run-id", "bad/id", "--binding-digest", "sha256:"+"0"*64]):
            with self.assertRaises(launcher.Rejected) as caught:
                launcher.parse_cli(args)
            self.assertEqual(caught.exception.code, 64)
        packet = runtime_packet(s)
        code, result = isolated_child("--guarded-launcher-child", packet,
            cli=["--phase", "MUTATION", "--run-id", s.run.run_id,
                 "--binding-digest", launcher._digest(packet["runtime"])])
        self.assertEqual(code, 65)
        self.assertEqual(result["execution_admission"], "NONE")

    def test_R13_exact_read_cursor_selector(self):
        s = self.fixture()
        s.configure("READ_RECONCILIATION")
        p, e = s.grant(read_after="msg_approved_cursor")
        self.assertIn("READ_RECONCILIATION", p.phase)
        with self.assertRaises(a.Denied):
            s.worker.list_items_once(p, e, s.binding, after="msg_other_cursor")
        self.assertEqual(s.store.verify()["counts"], {})
        self.assertEqual(s.peer.connects, 0)
        p2, _ = s.grant(read_after="msg_other_cursor")
        self.assertNotEqual(p.selector, p2.selector)

    def test_R14_real_child_signal_exit_codes(self):
        import signal
        cli = ["--signal-wait", "--phase", "MUTATION", "--run-id", "fixture_run",
               "--binding-digest", "sha256:"+"0"*64]
        for number, code in ((signal.SIGINT, 130), (signal.SIGTERM, 143), (signal.SIGHUP, 129)):
            actual, result = isolated_child("--guarded-launcher-child", {}, cli=cli, signal_number=number)
            self.assertEqual(actual, code)
            self.assertEqual(result["exit_code"], code)
            self.assertFalse(result["automatic_restart"])

    def test_R15_inflight_network_change_stops_without_retry(self):
        s = self.fixture([created()])
        original = Stream.read
        async def changed(stream, *args, **kwargs):
            await asyncio.sleep(0.05)
            s.network_generation += 1
            await asyncio.sleep(0.5)
            return await original(stream, *args, **kwargs)
        with mock.patch.object(Stream, "read", changed):
            out = s.mutation()
        self.assertEqual(out.knowledge, "UNKNOWN")
        self.assertEqual(out.control, "STOPPED")
        self.assert_one_mutation(s)
        self.assertEqual(s.peer.connects, 1)

    def test_R16_provider_echo_never_persists_credential(self):
        for in_body in (False, True):
            s = self.fixture()
            material = b"req_synthetic_credential_echo"
            s.credential = replace(s.credential, material=material)
            s.worker = a.LiveWorker(s.store, s.host, s.credential, s.runtime, s.network, s.run)
            s.peer.replies = [created(raw_body=a._canonical({"id":material.decode()})) if in_body
                              else created(headers=(("X-Request-Id", material.decode()),))]
            out = s.mutation()
            self.assertEqual(out.knowledge, "UNKNOWN" if in_body else "KNOWN_MUTATED")
            with sqlite3.connect(s.store.handle.path) as c:
                self.assertNotIn(material.decode(), "\n".join(c.iterdump()))
            self.assert_one_mutation(s)

    def test_R17_bound_launcher_synthetic_producer_and_credential_gate(self):
        s = self.fixture([created()])
        p, e = s.grant()
        packet = runtime_packet(s)
        packet["profile"] = json.loads(a._canonical(asdict(p)))
        packet["envelope"] = asdict(e)
        packet["envelope"]["not_after"] = e.not_after.isoformat()
        class SyntheticBoundary(launcher.EstablishedBoundary):
            # Explicit test-process instrumentation; never a production trust source.
            def authority(self, *args): return s.host.authority_reader(*args)
            def grant(self, cid): return s.grants.get(cid)
            def state(self, cid): return cap.CapabilityStateEvidence(cid, s.identity, s.reference,
                                                                    "cancel_fixture", "ACTIVE", False)
            def clock(self): return s.now
            def baseline(self): return s.runtime.implementation_commit
            def target(self, bid): return s.current_binding
            def revocation(self, digest): return s.revocation
            def credential_reference(self, ref): return (1, "org_fixture", "proj_fixture")
            def caller(self): return "caller_fixture"
            def runtime(self): return s.runtime
            def network(self, producer, evidence): return s.network
            def lifecycle(self): return s.observation()
            def source_qualified(self, kind, run): return s.source
        lease = {**asdict(s.credential), "not_after":s.credential.not_after.isoformat(),
                 "material":s.credential.material.decode()}
        reads = []
        def injected(fd, maximum, timeout=1):
            reads.append(fd)
            self.assertEqual(fd, 5)
            return a._canonical(lease)
        launcher._STOP, launcher._STOP_CODE = False, None
        s.source = False
        with mock.patch.object(launcher, "read_frame", injected):
            with self.assertRaises(launcher.Rejected) as denied:
                launcher.run_bound(a, packet, SyntheticBoundary())
            self.assertEqual(denied.exception.code, 66)
            self.assertEqual(reads, [])
            self.assertEqual(s.peer.connects, 0)
            s.source = True
            s.store.close()
            with native_emulator(s.peer):
                code = launcher.run_bound(a, packet, SyntheticBoundary())
        self.assertEqual(code, 0)
        self.assertEqual(reads, [5])
        reopened = a.LiveEvidenceStore(s.store.handle)
        try:
            self.assertEqual(reopened.verify()["counts"]["MUTATION"], 1)
        finally:
            reopened.close()
        self.assertEqual(s.peer.headers, 1)

    def test_R18_duplicate_authorization_headers_denied(self):
        s = self.fixture([created()])
        original = a.httpx.AsyncClient.send
        async def duplicate(client, request, **kwargs):
            request.headers = a.httpx.Headers(list(request.headers.multi_items())+
                                             [("Authorization", "Bearer "+SECRET.decode())])
            return await original(client, request, **kwargs)
        with mock.patch.object(a.httpx.AsyncClient, "send", duplicate):
            self.assertEqual(s.mutation().knowledge, "KNOWN_NOT_MUTATED")
        self.assertEqual(s.peer.headers, 0)
        self.assertEqual(s.store.verify()["counts"]["MUTATION"], 1)

def isolated_child(mode, packet, cli=(), signal_number=None):
    """Only the fixed test script/interpreter; no shell/arbitrary command."""
    reader, writer = os.pipe()
    result_reader, result_writer = os.pipe()
    raw = a._canonical(packet)
    args = ["/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13",
            "-I", "-S", "-B", str(SELF), mode, str(reader), str(result_writer), *cli]
    process = _ORIGINAL_POPEN(args, cwd=ROOT, pass_fds=(reader, result_writer),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.close(reader); os.close(result_writer)
    try:
        if signal_number is None:
            # Spawn the reader BEFORE sending: RuntimeBinding exceeds pipe capacity.
            # A finite non-blocking writer also makes an early child exit safe.
            framed, offset = len(raw).to_bytes(4, "big")+raw, 0
            deadline = time.monotonic()+10
            os.set_blocking(writer, False)
            while offset < len(framed):
                remaining = deadline-time.monotonic()
                if remaining <= 0 or not select.select([], [writer], [], remaining)[1]:
                    raise AssertionError("isolated child input deadline")
                try:
                    offset += os.write(writer, framed[offset:])
                except BlockingIOError:
                    continue
            os.close(writer)
            writer = None
        else:
            ready = launcher._strict_json(launcher.read_frame(result_reader, 4096, timeout=10))
            if ready != {"ready": True}:
                raise AssertionError("isolated child not ready")
            process.send_signal(signal_number)
        stdout, stderr = process.communicate(timeout=15)
        report = launcher._strict_json(launcher.read_frame(result_reader, 4096))
        if SECRET in stdout or SECRET in stderr or stderr:
            raise AssertionError("isolated child diagnostic leakage")
        return process.returncode, report
    finally:
        if process.poll() is None:
            process.kill(); process.wait()
        if writer is not None:
            os.close(writer)
        os.close(result_reader)

def reopened_child():
    # Guards and fixed pinned modules were installed/loaded before this point.
    reader, result_writer = int(sys.argv[2]), int(sys.argv[3])
    payload = launcher._strict_json(launcher.read_frame(reader, 4096))
    store = a.LiveEvidenceStore(a.LiveStoreHandle(**payload["handle"]))
    try:
        state = store.verify()
        old = next(r for r in state["reservations"].values() if r["operation"] == "MUTATION")
        row = {**old, "reservation_id": "child_reservation", "submission_id": "child_submission",
               "delivery_id": "child_delivery", "run_id": "child_run", "capability_id": "child_cap"}
        denied = False
        try:
            store.append("RESERVE", row)
        except (a.Denied, shared.Denied):
            denied = True
        report = {"count": store.verify()["counts"]["MUTATION"],
                  "replacement_reserve_denied": denied, "network_attempts": len(REAL_NETWORK_ATTEMPTS)}
        raw = a._canonical(report)
        os.write(result_writer, len(raw).to_bytes(4, "big")+raw)
    finally:
        store.close()
    if VIOLATIONS:
        raise SystemExit(99)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reopen-budget-child":
        reopened_child()
    else:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(LiveAdapterTests)
        result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
        print(json.dumps({"tests": result.testsRun, "failures": len(result.failures),
              "errors": len(result.errors), "real_network_attempts": len(REAL_NETWORK_ATTEMPTS),
              "real_credential_attempts": len(REAL_CREDENTIAL_ATTEMPTS)}))
        raise SystemExit(0 if result.wasSuccessful() and not VIOLATIONS else 1)

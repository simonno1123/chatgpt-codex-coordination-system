"""D-09 bounded remote-context pilot, OFFLINE fixture implementation only.

There is no live mode, credential discovery, invocation adapter or authority
issuer. Canonical D-04 validation is supplied by the integrating host through
read-only boundaries; fixtures are not authenticated production principals.
The dedicated journal stores non-authoritative transport/provider observations.
Python custody and digests do not protect against a host controlling the process.
A consumed reservation permits at most one application-level mutation POST
from this worker. Provider multiplicity and remote atomicity are not guaranteed.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import asyncio
import hashlib
import importlib.metadata
import json
import logging
from contextlib import contextmanager
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import threading
import time
from types import ModuleType
import uuid

import httpx
import httpcore


BASELINE = "22d0ea5da27760785a6ede40b3dd8dc47b624643"
ORIGIN = "https://api.openai.com"
FORMAT = "acos-v2-remote-context-offline-fixture/1"
SCHEMA_VERSION = 1
PHASES = ("SETUP", "MUTATION", "READ_RECONCILIATION", "DISPOSAL")
FIXTURE_TEXT = ("ACOS remote context pilot fixture v1.\n"
                "marker=rp-fixture-0001\nsynthetic-non-sensitive\n")
WIRE_BYTES = FIXTURE_TEXT.encode("utf-8")
WIRE_SHA256 = "7f61d14848a5892a6f1d298e246f6329ff84ec8a49be036975156525f4d5b119"
BODY_SHA256 = "8ce080e5da4e9cbadf3ff52f71b9f7847112c1c032eea5cdcf47ce58e4b04b4b"
MAX_READS = 3
MAX_RESPONSE_BYTES = 1024 * 1024
REQUEST_DEADLINE = 30.0
FOREGROUND_DEADLINE = 120.0
DEPENDENCIES = {"httpx": "0.28.1", "httpcore": "1.0.9", "h11": "0.16.0",
                "anyio": "4.13.0", "sniffio": "1.3.1", "certifi": "2026.4.22",
                "idna": "3.13", "typing_extensions": "4.15.0"}
_DIRECTORY = Path(__file__).resolve().parent


class Denied(ValueError):
    """Fail closed; messages must not contain provider or credential content."""


class StoreBlocked(RuntimeError):
    """Preserve the fixture; never recreate or repair it."""


class CommitUnknown(StoreBlocked):
    """No dependent send may follow an unconfirmed local commit."""


class FenceDenied(Denied):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


BODY_BYTES = _canonical({"items": [{"type": "message", "role": "user",
    "content": [{"type": "input_text", "text": FIXTURE_TEXT}]}]})
if len(WIRE_BYTES) != 85 or len(BODY_BYTES) != 176 or (
        _sha(WIRE_BYTES), _sha(BODY_BYTES)) != (WIRE_SHA256, BODY_SHA256):
    raise ImportError("frozen fixture identity mismatch")


def _identifier(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise Denied("invalid opaque identifier")
    return value


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise Denied("invalid digest")
    return value


def _strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Denied("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              Denied("non-finite JSON")))
    except Denied:
        raise
    except Exception:
        raise Denied("invalid JSON") from None


def _canonical_module(name, filename):
    module = sys.modules.get(name)
    if not isinstance(module, ModuleType) or vars(module).get("__file__") != str(_DIRECTORY / filename):
        raise ImportError("preload one canonical repository module")
    if any(m is not module and isinstance(m, ModuleType)
           and vars(m).get("__file__") == module.__file__
           for m in tuple(sys.modules.values())):
        raise ImportError("duplicate canonical module")
    return module


_core = _canonical_module("acos_v2_core_substrate", "acos-v2-core-substrate.py")
_cap = _canonical_module("acos_v2_capability", "acos-v2-capability.py")
if not _cap._canonical_core_intact():
    raise ImportError("canonical Core identity changed")
_MODULE_PINS = tuple((name, module, module.__file__, _sha(Path(module.__file__).read_bytes()))
                     for name, module in (("acos_v2_core_substrate", _core),
                                          ("acos_v2_capability", _cap)))
_VALIDATE = _cap.CapabilityValidator.validate


def _modules_intact():
    return all(sys.modules.get(n) is m and m.__file__ == p
               and _sha(Path(p).read_bytes()) == h
               for n, m, p, h in _MODULE_PINS) and _cap._canonical_core_intact() and (
                   _cap.CapabilityValidator.validate is _VALIDATE)


@dataclass(frozen=True)
class TargetBinding:
    binding_id: str
    generation: int
    organization: str
    project: str
    conversation_id: str
    provenance_digest: str
    credential_ref: str
    credential_version: int
    provider: str = "OPENAI"
    origin: str = ORIGIN
    effect: str = "REMOTE_CONTEXT_MUTATION"
    content_profile: str = "ONE_USER_INPUT_TEXT"
    nonproduction_disposable_exclusive: bool = True
    revocation_at_binding: str = "ACTIVE"

    def __post_init__(self):
        for name in ("binding_id", "organization", "project", "conversation_id", "credential_ref"):
            _identifier(getattr(self, name))
        _hash(self.provenance_digest)
        if (type(self.generation) is not int or self.generation < 1
                or type(self.credential_version) is not int or self.credential_version < 1
                or self.provider != "OPENAI" or self.origin != ORIGIN
                or self.effect != "REMOTE_CONTEXT_MUTATION"
                or self.content_profile != "ONE_USER_INPUT_TEXT"
                or self.nonproduction_disposable_exclusive is not True
                or self.revocation_at_binding != "ACTIVE"):
            raise Denied("invalid pinned binding")

    @property
    def digest(self):
        return _digest(asdict(self))


@dataclass(frozen=True)
class Profile:
    """Candidate restriction under D-04, never a grant or authority source."""
    phase: str
    store_id: str
    organization: str
    project: str
    credential_ref: str
    credential_version: int
    binding_digest: str
    generation: int
    submission_id: str
    delivery_id: str
    caller_id: str
    item_ids: tuple = ()
    allow_container_delete: bool = False
    payload_sha256: str = BODY_SHA256
    wire_sha256: str = WIRE_SHA256

    def __post_init__(self):
        if self.phase not in PHASES:
            raise Denied("phase denied")
        for name in ("store_id", "organization", "project", "credential_ref",
                     "submission_id", "delivery_id", "caller_id"):
            _identifier(getattr(self, name))
        if type(self.credential_version) is not int or self.credential_version < 1:
            raise Denied("credential version denied")
        if type(self.item_ids) is not tuple or len(set(self.item_ids)) != len(self.item_ids):
            raise Denied("invalid item scope")
        for item in self.item_ids:
            _identifier(item)
        if len(self.item_ids) > 1 or type(self.allow_container_delete) is not bool:
            raise Denied("bounded disposal scope required")
        if self.phase == "SETUP":
            if self.binding_digest != "UNBOUND" or self.generation != 0 or self.item_ids or self.allow_container_delete:
                raise Denied("setup scope denied")
        else:
            _hash(self.binding_digest)
            if type(self.generation) is not int or self.generation < 1:
                raise Denied("generation denied")
        if self.phase != "DISPOSAL" and self.allow_container_delete:
            raise Denied("container scope denied")
        if (self.payload_sha256, self.wire_sha256) != (BODY_SHA256, WIRE_SHA256):
            raise Denied("frozen payload identity denied")

    @property
    def selector(self):
        return "remote-context-offline/1:" + _digest(asdict(self))

    @property
    def scope_operation(self):
        if self.phase == "DISPOSAL":
            return "DELETE_CONTAINER" if self.allow_container_delete else "DELETE_ITEM"
        return self.phase

    @property
    def semantic_digest(self):
        return _digest({"domain": "acos-remote-context-semantic/1",
                        "effect": "REMOTE_CONTEXT_MUTATION",
                        "phase": self.phase, "operation": self.scope_operation, "binding": self.binding_digest,
                        "generation": self.generation,
                        "submission": self.submission_id, "delivery": self.delivery_id,
                        "payload": (self.payload_sha256 if self.phase == "MUTATION" else
                                    _sha(b"{}" if self.phase == "SETUP" else b"")),
                        "wire": self.wire_sha256})


@dataclass(frozen=True)
class SyntheticCredential:
    """Only test material, no lookup or future live credential provider."""
    reference: str
    version: int
    material: str = field(repr=False)

    def __post_init__(self):
        _identifier(self.reference)
        if type(self.version) is not int or self.version < 1 or (
                type(self.material) is not str or not re.fullmatch(
                    r"fixture-only-[A-Za-z0-9_-]{1,128}", self.material)):
            raise Denied("synthetic credential contract required")


@dataclass(frozen=True)
class HostReads:
    """Independently established read-only host boundaries; no default trust."""
    authority_reader: object
    capability_validator: object
    baseline_reader: object
    binding_reader: object
    revocation_reader: object
    credential_reference_reader: object
    caller_reader: object
    clock: object


@dataclass(frozen=True)
class FixtureHandle:
    path: str
    store_id: str
    device: int
    inode: int


def _empty():
    return {"bindings": {}, "revoked": [], "reservations": {}, "counts": {},
            "receipts": [], "observations": [], "tombstones": []}


def _apply(state, kind, data):
    if kind == "BINDING":
        binding = TargetBinding(**data)
        if state["bindings"] and binding.digest not in state["bindings"]:
            raise StoreBlocked("one pinned fixture target only")
        state["bindings"][binding.digest] = data
    elif kind == "REVOKE":
        if data["binding"] not in state["bindings"]:
            raise StoreBlocked("unknown revocation binding")
        if data["binding"] not in state["revoked"]:
            state["revoked"].append(data["binding"])
    elif kind == "RESERVE":
        operation = data["operation"]
        limit = {"SETUP": 1, "MUTATION": 1, "READ": MAX_READS,
                 "DELETE_ITEM": 1, "DELETE_CONTAINER": 1}.get(operation)
        if limit is None or state["counts"].get(operation, 0) >= limit:
            raise Denied("budget consumed")
        if data["consumption_policy"] == "SINGLE_USE" and any(
                r["capability_id"] == data["capability_id"] for r in state["reservations"].values()):
            raise Denied("single-use D-04 scope already consumed in fixture")
        reservation_id = data["reservation_id"]
        if reservation_id in state["reservations"]:
            raise StoreBlocked("duplicate reservation")
        if operation != "SETUP" and data["binding"] not in state["bindings"]:
            raise StoreBlocked("unbound reservation")
        if data["binding"] in state["revoked"]:
            raise Denied("target revoked")
        state["counts"][operation] = state["counts"].get(operation, 0) + 1
        state["reservations"][reservation_id] = data
    elif kind == "RECEIPT":
        if data["reservation_id"] not in state["reservations"]:
            raise StoreBlocked("unattributable receipt")
        state["receipts"].append(data)
    elif kind == "OBSERVATION":
        if data["reservation_id"] not in state["reservations"]:
            raise StoreBlocked("unattributable observation")
        state["observations"].append(data)
    elif kind == "TOMBSTONE":
        state["tombstones"].append(data)
    else:
        raise StoreBlocked("unknown journal kind")


class FixtureStore:
    """One logical fixture writer. Projection never confers governance authority."""
    def __init__(self, handle):
        if type(handle) is not FixtureHandle:
            raise StoreBlocked("explicit original fixture handle required")
        self.handle = handle
        self._check_identity()
        self.verify()

    @classmethod
    def create(cls, directory):
        root = Path(directory)
        temp = Path(tempfile.gettempdir()).resolve()
        if root.is_symlink() or root.resolve() != root or temp not in root.parents or (
                not root.name.startswith("acos-remote-context-offline-")):
            raise StoreBlocked("fresh dedicated temporary fixture directory required")
        path = root / "pilot.sqlite"
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        sid = uuid.uuid4().hex
        c = sqlite3.connect(str(path))
        try:
            c.execute("PRAGMA synchronous=FULL")
            c.executescript("""
                CREATE TABLE metadata(format TEXT, version INTEGER, store_id TEXT);
                CREATE TABLE journal(seq INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                  body BLOB NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TABLE projection(id INTEGER PRIMARY KEY CHECK(id=1), body BLOB NOT NULL);
                CREATE TRIGGER journal_no_update BEFORE UPDATE ON journal BEGIN
                  SELECT RAISE(ABORT, 'append-only'); END;
                CREATE TRIGGER journal_no_delete BEFORE DELETE ON journal BEGIN
                  SELECT RAISE(ABORT, 'append-only'); END;
                CREATE TRIGGER metadata_no_update BEFORE UPDATE ON metadata BEGIN
                  SELECT RAISE(ABORT, 'immutable'); END;
                CREATE TRIGGER metadata_no_delete BEFORE DELETE ON metadata BEGIN
                  SELECT RAISE(ABORT, 'immutable'); END;
            """)
            c.execute("INSERT INTO metadata VALUES(?,?,?)", (FORMAT, SCHEMA_VERSION, sid))
            c.execute("INSERT INTO projection VALUES(1,?)", (_canonical(_empty()),))
            c.commit()
        finally:
            c.close()
        s = path.stat()
        return cls(FixtureHandle(str(path), sid, s.st_dev, s.st_ino))

    def _check_identity(self):
        p = Path(self.handle.path)
        try:
            s = p.stat()
            if p.is_symlink() or (s.st_dev, s.st_ino) != (self.handle.device, self.handle.inode):
                raise StoreBlocked("fixture identity changed")
        except OSError:
            raise StoreBlocked("fixture unavailable; no replacement") from None

    def _connect(self, readonly=False):
        self._check_identity()
        c = sqlite3.connect(Path(self.handle.path).as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
                            uri=True, timeout=1.0, isolation_level=None)
        if not readonly:
            c.execute("PRAGMA synchronous=FULL")
        return c

    def _replay(self, c):
        try:
            if c.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise StoreBlocked("integrity failure")
            if c.execute("SELECT * FROM metadata").fetchall() != [
                    (FORMAT, SCHEMA_VERSION, self.handle.store_id)]:
                raise StoreBlocked("fixture format or identity mismatch")
            triggers = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
            if triggers != {"journal_no_update", "journal_no_delete",
                            "metadata_no_update", "metadata_no_delete"}:
                raise StoreBlocked("append-only schema mismatch")
            state = _empty()
            predecessor = "sha256:" + "0" * 64
            for expected, row in enumerate(c.execute(
                    "SELECT seq,kind,body,previous,digest FROM journal ORDER BY seq"), 1):
                seq, kind, raw, prev, current = row
                body = _strict_json(raw)
                if seq != expected or prev != predecessor or current != _digest(
                        {"seq": seq, "kind": kind, "body": body, "previous": prev}):
                    raise StoreBlocked("journal chain mismatch")
                _apply(state, kind, body)
                predecessor = current
            projection = c.execute("SELECT id,body FROM projection").fetchall()
            if len(projection) != 1 or projection[0][0] != 1 or projection[0][1] != _canonical(state):
                raise StoreBlocked("projection mismatch; no repair")
            return state, predecessor
        except StoreBlocked:
            raise
        except Exception:
            raise StoreBlocked("fixture replay failed") from None

    def verify(self):
        try:
            c = self._connect(readonly=True)
            try:
                return self._replay(c)[0]
            finally:
                c.close()
        except StoreBlocked:
            raise
        except Exception:
            raise StoreBlocked("fixture unavailable") from None

    def append(self, kind, data, *, fault=None):
        """Commit faults are synthetic; failed/unknown ACK never grants a permit."""
        c = self._connect()
        committed = False
        try:
            c.execute("BEGIN IMMEDIATE")
            state, prev = self._replay(c)
            _apply(state, kind, data)
            seq = c.execute("SELECT count(*) FROM journal").fetchone()[0] + 1
            digest = _digest({"seq": seq, "kind": kind, "body": data, "previous": prev})
            c.execute("INSERT INTO journal VALUES(?,?,?,?,?)",
                      (seq, kind, _canonical(data), prev, digest))
            c.execute("UPDATE projection SET body=? WHERE id=1", (_canonical(state),))
            if fault == "FAIL":
                raise StoreBlocked("synthetic commit failure")
            c.execute("COMMIT")
            committed = True
            if fault == "ACK_LOSS":
                raise CommitUnknown("local commit acknowledgement unresolved")
            self._check_identity()
        except (StoreBlocked, Denied):
            if not committed:
                c.execute("ROLLBACK")
            raise
        except Exception:
            if not committed:
                try:
                    c.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
            raise CommitUnknown("local write outcome unresolved") from None
        finally:
            c.close()

    def bind_fixture(self, binding):
        if type(binding) is not TargetBinding:
            raise Denied("binding required")
        self.append("BINDING", asdict(binding))

    def revoke(self, binding):
        self.append("REVOKE", {"binding": binding.digest})


@dataclass(frozen=True)
class Reply:
    status: int = 200
    body: object = None
    failure: str | None = None
    headers: tuple = ()
    raw_body: bytes | None = None


class FixturePeer:
    """Scripted data peer, not a caller-provided HTTP transport or network backend."""
    def __init__(self, replies=()):
        if type(replies) not in (tuple, list) or any(type(r) is not Reply for r in replies):
            raise Denied("fixture replies required")
        self.replies = list(replies)
        self.requests = []
        self.connects = 0
        self.header_sends = 0
        self.observed_scopes = []

    def _next(self):
        self.connects += 1
        reply = self.replies.pop(0) if self.replies else Reply(body={})
        if reply.failure == "CONNECT":
            raise httpcore.ConnectError("synthetic connection failure")
        return reply


class _FixtureStream(httpcore.AsyncNetworkStream):
    def __init__(self, peer, reply):
        self.peer, self.reply = peer, reply
        self.buffer = b""
        self.response = None
        self.closed = False

    async def write(self, buffer, timeout=None):
        if self.reply.failure == "WRITE":
            raise httpcore.WriteTimeout("synthetic write timeout")
        self.buffer += buffer
        if b"\r\n\r\n" in self.buffer and self.response is None:
            header, body = self.buffer.split(b"\r\n\r\n", 1)
            method, path, protocol = header.split(b"\r\n", 1)[0].decode("ascii").split()
            fields = {}
            for line in header.split(b"\r\n")[1:]:
                key, value = line.split(b":", 1)
                if key.lower() in (b"openai-organization", b"openai-project"):
                    fields[key.lower().decode()] = value.strip().decode("ascii")
            self.peer.observed_scopes.append(fields)
            self.peer.requests.append({"method": method, "path": path})
            self.response = b""
        if self.reply.failure == "SECRET_ERROR":
            raise RuntimeError("fixture-only-secret-in-exception")

    async def read(self, max_bytes, timeout=None):
        if self.reply.failure == "RESPONSE_LOSS":
            raise httpcore.ReadTimeout("synthetic response loss")
        if self.reply.failure == "DEADLINE":
            await asyncio.sleep(3600)
        if self.response == b"":
            body = self.reply.raw_body if self.reply.raw_body is not None else _canonical(self.reply.body)
            headers = list(self.reply.headers) + [("Content-Length", str(len(body))),
                                                 ("Content-Type", "application/json")]
            head = "HTTP/1.1 " + str(self.reply.status) + " Fixture\r\n"
            head += "".join(k + ": " + v + "\r\n" for k, v in headers) + "\r\n"
            self.response = head.encode("ascii") + body
        result, self.response = self.response[:max_bytes], self.response[max_bytes:]
        return result

    async def aclose(self):
        self.closed = True

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        if server_hostname != "api.openai.com" or ssl_context.check_hostname is not True:
            raise FenceDenied("TLS fixture boundary denied")
        return self

    def get_extra_info(self, info):
        return None


class _FixtureBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, peer):
        self.peer = peer

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != "api.openai.com" or port != 443 or local_address is not None:
            raise FenceDenied("fixture destination denied")
        return _FixtureStream(self.peer, self.peer._next())

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise FenceDenied("unix transport denied")

    async def sleep(self, seconds):
        raise FenceDenied("transport retry denied")


class _OneShot:
    def __init__(self, method, path, peer, organization=None, project=None):
        self.method, self.path, self.peer = method, path, peer
        self.organization, self.project = organization, project
        self.count = 0
        self.lock = threading.Lock()

    async def trace(self, name, info):
        if name == "http11.send_request_headers.started":
            request = info.get("request")
            with self.lock:
                if self.count or request is None or (
                        request.method.decode() != self.method
                        or request.url.target.decode() != self.path
                        or request.url.origin.host != b"api.openai.com"):
                    raise FenceDenied("second or altered application request denied")
                self.count += 1
                self.peer.header_sends += 1


_LOG_LOCK = threading.Lock()
_LOG_USERS = 0
_LOG_SNAPSHOT = []


@contextmanager
def _quiet_transport_logs():
    # Preserve secrecy even when two fixture workers overlap in this process.
    global _LOG_USERS, _LOG_SNAPSHOT
    with _LOG_LOCK:
        if _LOG_USERS == 0:
            names = [n for n in logging.root.manager.loggerDict
                     if n == "httpx" or n.startswith("httpx.")
                     or n == "httpcore" or n.startswith("httpcore.")]
            _LOG_SNAPSHOT = [(logging.getLogger(n), logging.getLogger(n).disabled) for n in names]
            for logger, _ in _LOG_SNAPSHOT:
                logger.disabled = True
        _LOG_USERS += 1
    try:
        yield
    finally:
        with _LOG_LOCK:
            _LOG_USERS -= 1
            if _LOG_USERS == 0:
                for logger, disabled in _LOG_SNAPSHOT:
                    logger.disabled = disabled
                _LOG_SNAPSHOT = []


class _OfflineSender:
    """Sealed HTTPX path with an internal non-network backend; no live variant."""
    def __init__(self, peer, credential):
        if type(peer) is not FixturePeer or type(credential) is not SyntheticCredential:
            raise Denied("offline fixture inputs required")
        for name, version in DEPENDENCIES.items():
            if importlib.metadata.version(name) != version:
                raise Denied("dependency version drift")
        self._peer, self._credential = peer, credential

    async def send(self, method, path, body, permit, remaining):
        if type(permit) is not _OneShot or permit.method != method or permit.path != path:
            raise FenceDenied("one-shot permit required")
        allowed = ((method == "POST" and path == "/v1/conversations" and body == b"{}")
                   or (method == "POST" and re.fullmatch(r"/v1/conversations/[A-Za-z0-9_-]+/items", path)
                       and body == BODY_BYTES)
                   or (method == "GET" and re.fullmatch(
                       r"/v1/conversations/[A-Za-z0-9_-]+/items(?:/[A-Za-z0-9_-]+|\?limit=100&order=asc(?:&after=[A-Za-z0-9_-]+)?)", path)
                       and body == b"")
                   or (method == "DELETE" and re.fullmatch(
                       r"/v1/conversations/[A-Za-z0-9_-]+(?:/items/[A-Za-z0-9_-]+)?", path)
                       and body == b""))
        if not allowed:
            raise FenceDenied("method/path/body whitelist denied")
        _identifier(permit.organization)
        _identifier(permit.project)
        transport = httpx.AsyncHTTPTransport(retries=0, trust_env=False, proxy=None,
                                             http1=True, http2=False)
        # Internal offline backend only; callers cannot supply a transport.
        transport._pool._network_backend = _FixtureBackend(self._peer)
        with _quiet_transport_logs():
            return await self._send_quiet(transport, method, path, body, permit, remaining)

    async def _send_quiet(self, transport, method, path, body, permit, remaining):
        async with httpx.AsyncClient(transport=transport, trust_env=False,
                                     follow_redirects=False, auth=None, proxy=None,
                                     mounts=None, event_hooks={}) as client:
            request = httpx.Request(method, ORIGIN + path, content=body,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + self._credential.material,
                         "OpenAI-Organization": permit.organization,
                         "OpenAI-Project": permit.project},
                extensions={"trace": permit.trace, "timeout": {
                    "connect": REQUEST_DEADLINE, "read": REQUEST_DEADLINE,
                    "write": REQUEST_DEADLINE, "pool": REQUEST_DEADLINE}})
            async with asyncio.timeout(min(REQUEST_DEADLINE, remaining)):
                async with client.stream(method, request.url, content=body,
                        headers=request.headers, extensions=request.extensions,
                        auth=None, follow_redirects=False) as response:
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        chunks.extend(chunk)
                        if len(chunks) > MAX_RESPONSE_BYTES:
                            raise Denied("response size bound exceeded")
                    provider_request_id = response.headers.get("x-request-id")
                    if not isinstance(provider_request_id, str) or not re.fullmatch(
                            r"req_[A-Za-z0-9_-]{1,120}", provider_request_id):
                        provider_request_id = None
                    return response.status_code, _strict_json(bytes(chunks)), provider_request_id


@dataclass(frozen=True)
class Outcome:
    knowledge: str
    control: str
    presence: str = "NOT_OBSERVED"
    stages: tuple = ()
    item_ids: tuple = ()
    reason: str = ""
    binding: TargetBinding | None = None
    authority_effect: str = field(default="NONE", init=False)
    execution_admission: bool = field(default=False, init=False)


def exact_item(item, item_id=None):
    """Compare decoded UTF-8 bytes; never normalize content."""
    if type(item) is not dict:
        return False
    try:
        identity = _identifier(item["id"])
        if not identity.startswith("msg_") or item_id is not None and identity != item_id:
            return False
        blocks = item["content"]
        return (item.get("type") == "message" and item.get("role") == "user"
                and item.get("status") == "completed" and type(blocks) is list
                and len(blocks) == 1 and type(blocks[0]) is dict
                and set(blocks[0]) == {"type", "text"}
                and blocks[0]["type"] == "input_text"
                and type(blocks[0]["text"]) is str
                and blocks[0]["text"].encode("utf-8") == WIRE_BYTES)
    except (KeyError, Denied, UnicodeError):
        return False


class OfflineWorker:
    """No live mode or generic request method. A new worker cannot refund a budget."""
    def __init__(self, store, host, credential, peer):
        if (type(store) is not FixtureStore or type(host) is not HostReads
                or type(credential) is not SyntheticCredential or type(peer) is not FixturePeer):
            raise Denied("offline-only worker boundary required")
        self.store, self.host, self.credential, self.peer = store, host, credential, peer
        self._sender = _OfflineSender(peer, credential)
        self._started = time.monotonic()

    def _validate(self, profile, envelope, phase, binding):
        if not _modules_intact() or type(profile) is not Profile or profile.phase != phase:
            raise Denied("canonical phase validation failed")
        if type(envelope) is not _cap.CapabilityEnvelope:
            raise Denied("D-04 capability missing")
        h = self.host
        try:
            if not callable(h.authority_reader) or h.authority_reader(
                    envelope.authority_reference, envelope.execution_identity, profile) is not True:
                raise Denied("independent authority validation failed")
            if type(h.capability_validator) is not _cap.CapabilityValidator:
                raise Denied("canonical D-04 validator missing")
            identity = envelope.execution_identity
            scope = _core.WorkflowScope(identity.project_id, identity.stage_id, identity.task_id)
            request = _cap.ValidationRequest("REMOTE_CONTEXT_PILOT_" + phase, profile.scope_operation,
                profile.selector, identity, envelope.authority_reference, scope,
                BASELINE, envelope.cancellation_binding)
            result = _VALIDATE(h.capability_validator, envelope, request)
            if type(result) is not _cap.ValidationResult or result.status != "PASS":
                raise Denied("independent capability validation failed")
            if not callable(h.baseline_reader) or h.baseline_reader() != BASELINE:
                raise Denied("baseline validation failed")
            if profile.store_id != self.store.handle.store_id:
                raise Denied("store binding failed")
            if binding is not None:
                if type(binding) is not TargetBinding or (
                        binding.digest != profile.binding_digest
                        or binding.generation != profile.generation
                        or (binding.organization, binding.project, binding.credential_ref,
                            binding.credential_version) != (profile.organization, profile.project,
                                profile.credential_ref, profile.credential_version)):
                    raise Denied("target generation validation failed")
                if not callable(h.binding_reader) or h.binding_reader(binding.binding_id) != binding:
                    raise Denied("independent binding validation failed")
                state = self.store.verify()
                if state["bindings"].get(binding.digest) != asdict(binding):
                    raise Denied("fixture target not pinned")
                if binding.digest in state["revoked"] or not callable(h.revocation_reader) or (
                        h.revocation_reader(binding.digest) != "ACTIVE"):
                    raise Denied("target revoked or revocation unknown")
            if not callable(h.credential_reference_reader) or h.credential_reference_reader(
                    profile.credential_ref) != (profile.credential_version,
                                                profile.organization, profile.project):
                raise Denied("credential reference changed or unavailable")
            if (self.credential.reference, self.credential.version) != (
                    profile.credential_ref, profile.credential_version):
                raise Denied("synthetic credential reference mismatch")
            if not callable(h.caller_reader) or h.caller_reader() != profile.caller_id:
                raise Denied("independent caller validation failed")
            if not callable(h.clock):
                raise Denied("trusted clock missing")
            current = h.clock()
            if type(current) is not datetime or current.tzinfo is None or current >= envelope.not_after:
                raise Denied("profile expired")
        except (Denied, StoreBlocked):
            raise
        except Exception:
            raise Denied("independent validation unavailable") from None

    def _knowledge(self):
        state = self.store.verify()
        if any(r["stage"] in ("REMOTE_ITEM_CREATED", "REMOTE_CONTEXT_MUTATION_CONFIRMED")
               for r in state["receipts"]):
            return "KNOWN_MUTATED"
        return "UNKNOWN" if state["counts"].get("MUTATION", 0) else "NOT_DISPATCHED"

    def _known_items(self):
        state = self.store.verify()
        return set(i for r in state["receipts"] for i in r.get("item_ids", []))

    def _quarantined(self):
        return any(r.get("control") == "QUARANTINED"
                   for r in self.store.verify()["receipts"] + self.store.verify()["observations"])

    def _evidence(self, reservation, stage, item_ids=(), control="STOPPED", presence="PRESENT", fault=None):
        # Only bounded non-secret data is recorded, never raw responses/errors/headers.
        data = {"reservation_id": reservation, "stage": stage, "item_ids": list(item_ids),
                "control": control, "presence": presence, "observed_at": datetime.now(
                    timezone.utc).isoformat(), "authority_effect": "NONE"}
        self.store.append("RECEIPT", data, fault=fault)

    def _observe(self, reservation, control, presence, error_class):
        self.store.append("OBSERVATION", {"reservation_id": reservation,
            "control": control, "presence": presence, "error_class": error_class,
            "observed_at": datetime.now(timezone.utc).isoformat()})

    def _dispatch(self, profile, envelope, phase, binding, operation, path, body=b"",
                  *, reservation_fault=None):
        self._validate(profile, envelope, phase, binding)
        if phase == "DISPOSAL" and operation != profile.scope_operation:
            raise Denied("separate disposal operation grant required")
        if phase in ("SETUP", "MUTATION", "DISPOSAL") and envelope.consumption_policy != _cap.SINGLE_USE:
            raise Denied("single-use effect scope required")
        if time.monotonic() - self._started >= FOREGROUND_DEADLINE:
            raise Denied("foreground deadline exhausted")
        rid = uuid.uuid4().hex
        data = {"reservation_id": rid, "operation": operation,
                "binding": profile.binding_digest, "generation": profile.generation,
                "authority_reference": asdict(envelope.authority_reference),
                "capability_id": envelope.capability_id,
                "consumption_policy": envelope.consumption_policy,
                "capability_profile_digest": _digest(asdict(profile)),
                "execution_identity": asdict(envelope.execution_identity),
                "baseline": BASELINE, "caller_id": profile.caller_id,
                "credential_ref": profile.credential_ref,
                "credential_version": profile.credential_version,
                "submission_id": profile.submission_id, "delivery_id": profile.delivery_id,
                "relay_attempt_id": uuid.uuid4().hex,
                "http_attempt_ordinal": self.store.verify()["counts"].get(operation, 0) + 1,
                "method": {"SETUP": "POST", "MUTATION": "POST", "READ": "GET",
                           "DELETE_ITEM": "DELETE", "DELETE_CONTAINER": "DELETE"}[operation],
                "path": path, "payload_sha256": _sha(body),
                "semantic_digest": profile.semantic_digest, "wire_sha256": WIRE_SHA256,
                "budget_consumed": True, "reserved_at": datetime.now(timezone.utc).isoformat()}
        # Atomic append/replay/consumption is local to this fixture only.
        self.store.append("RESERVE", data, fault=reservation_fault)
        method = data["method"]
        permit = _OneShot(method, path, self.peer, profile.organization, profile.project)
        original_trace = permit.trace

        async def final_trace(name, info):
            if name == "http11.send_request_headers.started":
                self._validate(profile, envelope, phase, binding)
            await original_trace(name, info)
        permit.trace = final_trace
        remaining = FOREGROUND_DEADLINE - (time.monotonic() - self._started)
        if remaining <= 0:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "DEADLINE_BEFORE_SEND")
            return rid, None, None, Outcome("KNOWN_NOT_MUTATED", "STOPPED",
                                           reason="no headers exposure")
        try:
            status, response, request_id = asyncio.run(self._sender.send(method, path, body, permit, remaining))
            self.store.append("OBSERVATION", {"reservation_id": rid,
                "control": "STOPPED", "presence": "NOT_OBSERVED",
                "error_class": "RESPONSE_OBSERVED", "provider_request_id": request_id,
                "provider_response_digest": _digest(response),
                "observed_at": datetime.now(timezone.utc).isoformat()})
            if 300 <= status < 400:
                self._observe(rid, "QUARANTINED", "NOT_OBSERVED", "REDIRECT_DENIED")
                return rid, None, None, Outcome(self._knowledge(), "QUARANTINED",
                                                reason="redirect denied; no follow")
            return rid, status, response, None
        except Exception:
            # Counter zero positively proves this fixed path never began headers.
            knowledge = "KNOWN_NOT_MUTATED" if permit.count == 0 else self._knowledge()
            if knowledge == "NOT_DISPATCHED":
                knowledge = "UNKNOWN"
            self._observe(rid, "STOPPED", "NOT_OBSERVED",
                          "BEFORE_HEADERS" if permit.count == 0 else "REQUEST_OUTCOME_UNRESOLVED")
            return rid, None, None, Outcome(knowledge, "STOPPED", reason="request outcome unresolved")

    def setup(self, profile, envelope, *, binding_id, reservation_fault=None, receipt_fault=None):
        rid, status, body, failed = self._dispatch(profile, envelope, "SETUP", None,
            "SETUP", "/v1/conversations", b"{}", reservation_fault=reservation_fault)
        if failed:
            return failed
        if status != 200 or type(body) is not dict or not str(body.get("id", "")).startswith("conv_"):
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "SETUP_UNRESOLVED")
            return Outcome("UNKNOWN", "STOPPED")
        try:
            cid = _identifier(body["id"])
            binding = TargetBinding(binding_id, 1, profile.organization, profile.project, cid,
                _digest({"setup_reservation": rid, "conversation_id": cid,
                         "organization": profile.organization, "project": profile.project}),
                profile.credential_ref, profile.credential_version)
            self._evidence(rid, "SETUP_ID_OBSERVED", fault=receipt_fault)
            self.store.bind_fixture(binding)
            return Outcome("NOT_DISPATCHED", "STOPPED", stages=("SETUP_ID_OBSERVED",), binding=binding)
        except CommitUnknown:
            return Outcome("UNKNOWN", "STOPPED", reason="setup local evidence unresolved")

    def mutate(self, profile, envelope, binding, *, reservation_fault=None, receipt_fault=None):
        if self._quarantined():
            raise Denied("quarantined fixture cannot mutate")
        rid, status, body, failed = self._dispatch(profile, envelope, "MUTATION", binding,
            "MUTATION", "/v1/conversations/" + binding.conversation_id + "/items", BODY_BYTES,
            reservation_fault=reservation_fault)
        if failed:
            return failed
        items = body.get("data", []) if type(body) is dict else []
        if not 200 <= status < 300 or type(body) is not dict or body.get("object") != "list" or type(items) is not list:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "CREATE_UNRESOLVED")
            return Outcome("UNKNOWN", "STOPPED")
        ids = tuple(i["id"] for i in items if type(i) is dict
                    and type(i.get("id")) is str and re.fullmatch(r"msg_[A-Za-z0-9_-]{1,120}", i["id"]))
        stages = ("REMOTE_REQUEST_ACCEPTED",)
        control = "STOPPED" if len(items) == 1 and len(ids) == 1 and exact_item(items[0]) else "QUARANTINED"
        try:
            self._evidence(rid, "REMOTE_REQUEST_ACCEPTED", control=control)
            if ids:
                self._evidence(rid, "REMOTE_ITEM_CREATED", ids, control=control, fault=receipt_fault)
                stages += ("REMOTE_ITEM_CREATED",)
            return Outcome("KNOWN_MUTATED" if ids else "UNKNOWN", control, stages=stages, item_ids=ids)
        except (CommitUnknown, StoreBlocked):
            return Outcome("KNOWN_MUTATED" if ids else "UNKNOWN", "STOPPED",
                           stages=stages, item_ids=ids, reason="local receipt persistence unresolved")

    def read(self, profile, envelope, binding, *, item_id=None, after=None, receipt_fault=None):
        if item_id is not None:
            _identifier(item_id)
            if item_id not in set(profile.item_ids) | self._known_items():
                raise Denied("read item outside pinned scope")
            path = "/v1/conversations/" + binding.conversation_id + "/items/" + item_id
        else:
            path = "/v1/conversations/" + binding.conversation_id + "/items?limit=100&order=asc"
            if after is not None:
                _identifier(after)
                path += "&after=" + after
        rid, status, body, failed = self._dispatch(profile, envelope, "READ_RECONCILIATION",
                                                   binding, "READ", path)
        if failed:
            return Outcome(self._knowledge(), failed.control, reason=failed.reason)
        if status == 404:
            self._observe(rid, "STOPPED", "UNAVAILABLE", "ITEM_ABSENT" if item_id else "TARGET_UNAVAILABLE")
            return Outcome(self._knowledge(), "STOPPED", "UNAVAILABLE")
        if status != 200:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "READ_UNRESOLVED")
            return Outcome(self._knowledge(), "STOPPED")
        if item_id is not None:
            candidates = [body] if exact_item(body, item_id) else []
            conflict = not candidates
        else:
            data = body.get("data") if type(body) is dict else None
            if type(data) is not list or len(data) > 100 or type(body.get("has_more")) is not bool:
                self._observe(rid, "QUARANTINED", "NOT_OBSERVED", "LIST_SHAPE_INVALID")
                return Outcome(self._knowledge(), "QUARANTINED")
            candidates = [i for i in data if exact_item(i)]
            conflict = len(candidates) > 1
        if conflict:
            self._observe(rid, "QUARANTINED", "PRESENT", "READ_CONFLICT")
            return Outcome(self._knowledge(), "QUARANTINED", "PRESENT")
        if not candidates:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "ZERO_MATCHES")
            return Outcome(self._knowledge(), "STOPPED")
        ids = (candidates[0]["id"],)
        state = self.store.verify()
        mutation = [r for r in state["reservations"].values() if r["operation"] == "MUTATION"]
        attributable = len(mutation) == 1 and (
            mutation[0]["binding"] == profile.binding_digest
            and mutation[0]["generation"] == profile.generation
            and mutation[0]["submission_id"] == profile.submission_id
            and mutation[0]["delivery_id"] == profile.delivery_id)
        if not attributable:
            self._observe(rid, "STOPPED", "PRESENT", "UNATTRIBUTED_CONTEXT")
            return Outcome(self._knowledge(), "STOPPED", "PRESENT",
                           reason="observation not correlated to mutation reservation")
        known = self._known_items()
        if known and ids[0] not in known:
            self._observe(rid, "QUARANTINED", "PRESENT", "ITEM_ID_CONFLICT")
            return Outcome(self._knowledge(), "QUARANTINED", "PRESENT")
        if item_id is None and body.get("has_more") is True:
            self._evidence(rid, "REMOTE_ITEM_READBACK_VERIFIED", ids)
            return Outcome("KNOWN_MUTATED", "STOPPED", "PRESENT",
                           ("REMOTE_ITEM_READBACK_VERIFIED",), ids, "enumeration incomplete")
        if self._quarantined():
            self._observe(rid, "QUARANTINED", "PRESENT", "PRIOR_CONFLICT_PRESERVED")
            return Outcome(self._knowledge(), "QUARANTINED", "PRESENT", item_ids=ids)
        try:
            self._evidence(rid, "REMOTE_ITEM_READBACK_VERIFIED", ids)
            self._evidence(rid, "REMOTE_CONTEXT_MUTATION_CONFIRMED", ids, fault=receipt_fault)
            return Outcome("KNOWN_MUTATED", "STOPPED", "PRESENT",
                ("REMOTE_ITEM_READBACK_VERIFIED", "REMOTE_CONTEXT_MUTATION_CONFIRMED"), ids)
        except (CommitUnknown, StoreBlocked):
            return Outcome("KNOWN_MUTATED", "STOPPED", "PRESENT",
                           ("REMOTE_ITEM_READBACK_VERIFIED",), ids,
                           "local confirmation acknowledgement unresolved")

    def dispose(self, profile, envelope, binding, *, item_id=None, container=False, rollback=False):
        if rollback or type(container) is not bool or (container and item_id is not None):
            raise Denied("disposal cannot roll back history")
        state = self.store.verify()
        confirmed = any(r["stage"] == "REMOTE_CONTEXT_MUTATION_CONFIRMED" for r in state["receipts"])
        if not confirmed or self._quarantined():
            raise Denied("disposal unresolved; no scope expansion")
        if container:
            if not profile.allow_container_delete or not any(
                    o["error_class"] == "ITEM_ABSENT"
                    and state["reservations"][o["reservation_id"]]["path"] in {
                        "/v1/conversations/" + binding.conversation_id + "/items/" + i
                        for r in state["receipts"] if r["stage"] == "ITEM_DELETE_ACK"
                        for i in r["item_ids"]}
                    for o in state["observations"]) or not any(
                    r["stage"] == "ITEM_DELETE_ACK" for r in state["receipts"]):
                raise Denied("container disposal preconditions unresolved")
            operation = "DELETE_CONTAINER"
            path = "/v1/conversations/" + binding.conversation_id
        else:
            _identifier(item_id)
            if item_id not in profile.item_ids or item_id not in self._known_items():
                raise Denied("delete item outside approved known set")
            operation = "DELETE_ITEM"
            path = "/v1/conversations/" + binding.conversation_id + "/items/" + item_id
        rid, status, body, failed = self._dispatch(profile, envelope, "DISPOSAL",
                                                  binding, operation, path)
        if failed:
            return Outcome(self._knowledge(), "STOPPED", reason="DISPOSAL_UNRESOLVED")
        matches = status == 200 and type(body) is dict and body.get("id") == binding.conversation_id
        if container:
            matches = matches and body.get("deleted") is True
        if not matches:
            self._observe(rid, "STOPPED", "NOT_OBSERVED", "DISPOSAL_UNRESOLVED")
            return Outcome(self._knowledge(), "STOPPED", reason="DISPOSAL_UNRESOLVED")
        self._evidence(rid, "CONTAINER_DELETE_ACK" if container else "ITEM_DELETE_ACK", () if container else (item_id,))
        if container:
            self.store.append("TOMBSTONE", {"binding": binding.digest,
                "container_deleted": True, "item_purge_proven": False,
                "history_preserved": True})
        return Outcome(self._knowledge(), "STOPPED",
                       reason="CONTAINER_DELETED_ITEMS_NOT_PURGED" if container else "DISPOSAL_UNRESOLVED")


if __name__ == "__main__":
    raise SystemExit("Offline import-only pilot. Live execution is unavailable.")

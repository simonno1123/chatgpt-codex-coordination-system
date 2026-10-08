"""Fixed foreground bootstrap. FD possession and JSON are never authority.

No production host-source/trust provider is implemented by this offline tranche.
Unestablished FD4/FD6 producers fail closed before FD5 is read or any network
client is constructed. Qualification and real execution require separate review.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import importlib.util
import json
import os
import platform
import select
import signal
import socket
import ssl
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
SELF = ROOT / "scripts/acos-v2-remote-context-live-launcher.py"
ADAPTER = ROOT / "scripts/acos-v2-remote-context-live-adapter.py"
PRODUCER = ROOT / "scripts/acos-v2-production-host-control-producer.py"
PRODUCER_SHA = "d092f5062dc016b5d47d279727b7258c8799b49c763807b758e7cb3a15578d2b"
_PRODUCER_MODULE = None
PYTHON = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13"
DEPENDENCY_ROOT = "/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages"
DEPENDENCIES = {"httpx": "0.28.1", "httpcore": "1.0.9", "h11": "0.16.0",
                "anyio": "4.13.0", "sniffio": "1.3.1", "certifi": "2026.4.22",
                "idna": "3.13", "typing_extensions": "4.15.0"}
FROZEN = {
 "acos_v2_core_substrate": ("acos-v2-core-substrate.py", "fb2cdec2a8d3aaeb1c4a1c293f4f8c92120ff576e1309d7c88b10bc419407c7b"),
 "acos_v2_capability": ("acos-v2-capability.py", "884efc61d934e1c361bb9e7a97b4e8ee7807c3adc64fff6114088ad3f9817d40"),
 "acos_v2_remote_context_mutation_pilot": ("acos-v2-remote-context-mutation-pilot.py", "c0f54646059e85813463dbeb46adc389f1f9e54bdb251f4cfef5516210168829")}
MAX_PACKET = 1048576
EXIT_CODES = {"USAGE": 64, "RUNTIME": 65, "HOST": 66, "CREDENTIAL": 67, "STORE": 68,
              "NETWORK": 69, "UNKNOWN": 70, "QUARANTINE": 71, "DISPOSAL": 72,
              "LIFETIME": 73, "EVIDENCE": 74}
_STOP = False
_STOP_CODE = None

class Rejected(Exception):
    def __init__(self, code):
        self.code = code

def _fail(label):
    raise Rejected(EXIT_CODES[label])

def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")

def _digest(value):
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()

def _strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                _fail("USAGE")
            result[k] = v
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: _fail("USAGE"))
    except Rejected:
        raise
    except Exception:
        _fail("USAGE")

def parse_cli(argv):
    # Fixed grammar, including no duplicated flags; never echo caller arguments.
    if len(argv) != 6:
        _fail("USAGE")
    keys = argv[::2]
    if set(keys) != {"--phase", "--run-id", "--binding-digest"} or len(set(keys)) != 3:
        _fail("USAGE")
    args = dict(zip(keys, argv[1::2]))
    if args["--phase"] not in ("SETUP", "MUTATION", "READ_RECONCILIATION", "DISPOSAL"):
        _fail("USAGE")
    import re
    if (not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", args["--run-id"])
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", args["--binding-digest"])):
        _fail("USAGE")
    return args

def _file_pin(pin, exact=None):
    if type(pin) is not dict or set(pin) != {"path", "sha256", "size", "device", "inode"}:
        _fail("RUNTIME")
    p = Path(pin["path"])
    if not p.is_absolute() or p.is_symlink() or str(p.resolve()) != str(p) or (
            exact is not None and str(p) != str(exact)):
        _fail("RUNTIME")
    try:
        s = p.stat()
        if (s.st_size, s.st_dev, s.st_ino) != (pin["size"], pin["device"], pin["inode"]):
            _fail("RUNTIME")
        if hashlib.sha256(p.read_bytes()).hexdigest() != pin["sha256"]:
            _fail("RUNTIME")
    except Rejected:
        raise
    except Exception:
        _fail("RUNTIME")

def read_frame(fd, maximum, timeout=1.0):
    """Bounded inherited-channel read, never a path/socket discovery operation."""
    try:
        os.fstat(fd)
        deadline, raw = time.monotonic() + timeout, bytearray()
        while len(raw) < 4:
            if _STOP or time.monotonic() >= deadline:
                _fail("LIFETIME")
            ready, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
            if not ready:
                _fail("LIFETIME")
            chunk = os.read(fd, 4 - len(raw))
            if not chunk:
                _fail("HOST")
            raw.extend(chunk)
        size = int.from_bytes(raw, "big")
        if size < 1 or size > maximum:
            _fail("USAGE")
        raw = bytearray()
        while len(raw) < size:
            if _STOP or time.monotonic() >= deadline:
                _fail("LIFETIME")
            ready, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
            if not ready:
                _fail("LIFETIME")
            chunk = os.read(fd, size - len(raw))
            if not chunk:
                _fail("HOST")
            raw.extend(chunk)
        return bytes(raw)
    except Rejected:
        raise
    except Exception:
        _fail("HOST")

def _native_primitives():
    # Test instrumentation is not an eligible live runtime.
    import _socket
    return (socket.socket.__module__ == "socket"
            and _socket.getaddrinfo.__module__ == "_socket"
            and socket.getaddrinfo.__module__ == "socket"
            and ssl.SSLContext.__module__ == "ssl"
            and sys.gettrace() is None and sys.getprofile() is None)

def bootstrap(packet, args):
    """All third-party imports and path exposure occur AFTER this validation."""
    required = {"runtime", "run", "network", "profile", "envelope", "target",
                "store", "operation", "producer"}
    if type(packet) is not dict or set(packet) != required:
        _fail("USAGE")
    runtime = packet["runtime"]
    if type(runtime) is not dict or _digest(runtime) != args["--binding-digest"]:
        _fail("RUNTIME")
    if (str(Path(sys.executable).resolve()) != PYTHON or not sys.flags.isolated
            or not sys.flags.no_site or not sys.dont_write_bytecode
            or Path.cwd() != ROOT or runtime.get("flags") != ["-I", "-S", "-B"]
            or runtime.get("cwd") != str(ROOT)
            or runtime.get("design_baseline") != "182e42d9578972798c43f998a9f7f1243edf28a1"
            or runtime.get("python_version") != platform.python_version()
            or runtime.get("architecture") != platform.machine() or not _native_primitives()):
        _fail("RUNTIME")
    _file_pin(runtime.get("launcher_pin"), SELF)
    _file_pin(runtime.get("adapter_pin"), ADAPTER)
    _file_pin(runtime.get("python_pin"), PYTHON)
    _file_pin(runtime.get("python_app_pin"),
              "/Library/Frameworks/Python.framework/Versions/3.13/Resources/Python.app/Contents/MacOS/Python")
    _file_pin(runtime.get("framework_pin"), "/Library/Frameworks/Python.framework/Versions/3.13/Python")
    _file_pin(runtime.get("requirements_pin"), ROOT/"requirements-acos-v2-remote-context-mutation-pilot.txt")
    if runtime["requirements_pin"]["sha256"] != "fe11dc0a5dcd7695c49e577e055bac2afa17dfdba79b2b132ded338897fcdb75":
        _fail("RUNTIME")
    source = runtime.get("source_pins", [])
    expected = {str(ROOT/"scripts"/f): h for f, h in FROZEN.values()}
    if {p.get("path"): p.get("sha256") for p in source} != expected or len(source) != 3:
        _fail("RUNTIME")
    for pin in source:
        _file_pin(pin)
    location = runtime.get("dependency_location")
    if location != DEPENDENCY_ROOT or Path(location).is_symlink() or str(Path(location).resolve()) != location:
        _fail("RUNTIME")
    deps = runtime.get("dependencies", [])
    if len(deps) != len(DEPENDENCIES) or {d.get("name"): d.get("version") for d in deps} != DEPENDENCIES:
        _fail("RUNTIME")
    for dep in deps:
        if dep.get("location") != location or not dep.get("files"):
            _fail("RUNTIME")
        for pin in dep["files"]:
            if not Path(pin["path"]).is_relative_to(Path("/Library/Frameworks/Python.framework/Versions/3.13")):
                _fail("RUNTIME")
            _file_pin(pin)
    _file_pin(runtime.get("ca_pin"), Path(location)/"certifi/cacert.pem")
    if runtime["ca_pin"]["sha256"] != "16be3f6feb15408195dcfe3aa1a75ef9db72f646b96ebbefdc68f56255f799f8":
        _fail("RUNTIME")
    if packet["run"].get("run_id") != args["--run-id"] or packet["run"].get("phase") != args["--phase"]:
        _fail("USAGE")
    # No sensitive value lookup: only approved non-secret proxy/debug policy names.
    forbidden = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy",
                 "SSLKEYLOGFILE", "PYTHONPATH", "PYTHONHOME", "DYLD_INSERT_LIBRARIES",
                 "SSL_CERT_FILE", "SSL_CERT_DIR")
    if any(name in os.environ for name in forbidden):
        _fail("RUNTIME")
    if any(Path(location).glob("*.pth")) or (Path(location)/"sitecustomize.py").exists() or (
            Path(location)/"usercustomize.py").exists():
        _fail("RUNTIME")
    # A caller-labelled qualification packet is still untrusted.
    if set(packet["producer"]) != {"host_reference", "control_reference", "network_reference"}:
        _fail("HOST")
    return location

def _load_source(name, path, expected_sha):
    """No caller module/path inputs reach this function."""
    verified_bytes = path.read_bytes()
    if name in sys.modules or hashlib.sha256(verified_bytes).hexdigest() != expected_sha:
        _fail("RUNTIME")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # Execute the verified bytes, avoiding unbound cached bytecode.
    exec(compile(verified_bytes, str(path), "exec"), module.__dict__)
    return module

def load_bound_modules(packet):
    location = packet["runtime"]["dependency_location"]
    if any("site-packages" in str(p) for p in sys.path):
        _fail("RUNTIME")
    sys.path.append(location)  # Only after bootstrap has verified the complete packet.
    for name, (filename, digest) in FROZEN.items():
        _load_source(name, ROOT/"scripts"/filename, digest)
    return _load_source("acos_v2_remote_context_live_adapter", ADAPTER,
                        packet["runtime"]["adapter_pin"]["sha256"])

def decode_runtime(a, raw):
    try:
        raw = dict(raw)
        for name in ("launcher_pin", "adapter_pin", "requirements_pin", "python_pin",
                     "python_app_pin", "framework_pin", "ca_pin"):
            raw[name] = a.FilePin(**raw[name])
        raw["source_pins"] = tuple(a.FilePin(**p) for p in raw["source_pins"])
        raw["dependencies"] = tuple(a.DependencyPin(
            name=d["name"], version=d["version"], location=d["location"],
            files=tuple(a.FilePin(**p) for p in d["files"])) for d in raw["dependencies"])
        raw["flags"] = tuple(raw["flags"])
        return a.RuntimeBinding(**raw)
    except Exception:
        _fail("RUNTIME")

def decode_network(a, raw):
    try:
        raw = dict(raw)
        raw["observed_at"], raw["not_after"] = (datetime.fromisoformat(raw[k]) for k in ("observed_at", "not_after"))
        raw["replay_boundary"] = tuple(tuple(p) for p in raw["replay_boundary"])
        return a.NetworkQualificationBinding(**raw)
    except Exception:
        _fail("NETWORK")

class EstablishedBoundary:
    """Read-only injection contract; no built-in authentication/trust provider."""
    def authority(self, reference, identity, profile):
        raise Rejected(66)
    def grant(self, capability_id):
        raise Rejected(66)
    def state(self, capability_id):
        raise Rejected(66)
    def clock(self):
        raise Rejected(66)
    def baseline(self):
        raise Rejected(66)
    def target(self, binding_id):
        raise Rejected(66)
    def revocation(self, digest):
        raise Rejected(66)
    def credential_reference(self, reference):
        raise Rejected(66)
    def caller(self):
        raise Rejected(66)
    def runtime(self):
        raise Rejected(66)
    def network(self, producer_reference, evidence_reference):
        raise Rejected(69)
    def lifecycle(self):
        raise Rejected(73)
    def source_qualified(self, kind, run):
        return False

def _load_producer():
    """Fixed reviewed implementation before any external-source establishment."""
    global _PRODUCER_MODULE
    try:
        if PRODUCER.is_symlink() or PRODUCER.resolve() != PRODUCER:
            _fail("RUNTIME")
        raw = PRODUCER.read_bytes()
        if hashlib.sha256(raw).hexdigest() != PRODUCER_SHA:
            _fail("RUNTIME")
        if _PRODUCER_MODULE is None:
            _PRODUCER_MODULE = _load_source("acos_v2_production_host_control_producer",
                                           PRODUCER, PRODUCER_SHA)
        if (sys.modules.get("acos_v2_production_host_control_producer") is not _PRODUCER_MODULE
                or _PRODUCER_MODULE.__file__ != str(PRODUCER)):
            _fail("RUNTIME")
        return _PRODUCER_MODULE
    except Rejected:
        raise
    except Exception:
        _fail("RUNTIME")

def establish_boundaries(packet):
    # Factory inputs do not establish sources. No credentials/third-party
    # exposure precede this fixed pin and external provenance qualification.
    producer = _load_producer()
    try:
        return producer.establish(packet)
    except producer.Unavailable:
        _fail("HOST")

def _credential(a, profile, run, boundary):
    # Called only after every source/runtime/network gate and a qualified producer.
    raw = _strict_json(read_frame(5, 16384))
    if type(raw) is not dict or set(raw) != {
            "reference", "version", "organization", "project", "run_id", "process_id", "not_after", "material"}:
        _fail("CREDENTIAL")
    try:
        raw["not_after"] = datetime.fromisoformat(raw["not_after"])
        raw["material"] = raw["material"].encode("ascii")
        lease = a.CredentialLease(**raw)
        lease.validate(profile, run, boundary.clock())
        return lease
    except Exception:
        _fail("CREDENTIAL")

def _envelope(a, raw):
    try:
        raw = dict(raw)
        raw["execution_identity"] = a._core.ExecutionIdentity(**raw["execution_identity"])
        raw["authority_reference"] = a._core.AuthorityReference(**raw["authority_reference"])
        raw["not_after"] = datetime.fromisoformat(raw["not_after"])
        return a._cap.CapabilityEnvelope(**raw)
    except Exception:
        _fail("HOST")

def run_bound(a, packet, boundary):
    """Already-established producer injection only; this is not a CLI alternate."""
    runtime = decode_runtime(a, packet["runtime"])
    runtime.verify()
    network = decode_network(a, packet["network"])
    try:
        run = a.RunBinding(**packet["run"])
        contract = dict(packet["profile"]["contract"])
        contract["item_ids"] = tuple(contract["item_ids"])
        profile = a.LiveProfile(a.shared.Profile(**contract),
            packet["profile"]["runtime_digest"], packet["profile"]["network_digest"],
            packet["profile"]["run_id"], packet["profile"].get("read_after"))
        envelope = _envelope(a, packet["envelope"])
        target = a.TargetBinding(**packet["target"]) if packet["target"] is not None else None
        handle = a.LiveStoreHandle(**packet["store"])
    except Rejected:
        raise
    except Exception:
        _fail("USAGE")
    producer = _load_producer()
    if type(boundary) is producer.ObservationBoundary:
        boundary.bind_canonical(a, runtime)
    if (boundary.source_qualified("HOST", run) is not True
            or boundary.source_qualified("CONTROL", run) is not True):
        _fail("HOST")
    # Existing store only: opening verifies replay and takes the existing writer
    # lock but creates/appends/consumes nothing. Close on every failure path.
    store = a.LiveEvidenceStore(handle)
    try:
        try:
            producer.credential_free_preflight(a, profile, envelope, runtime,
                                               network, run, target, store, boundary, packet["operation"])
        except producer.Unavailable:
            _fail("HOST")
        if _STOP:
            _fail("LIFETIME")
        # ALL non-secret preflight checks have passed before the first FD5 read.
        lease = _credential(a, profile, run, boundary)
        host = a.LiveHostReads(boundary.authority,
            a._cap.CapabilityValidator(trusted_grant_resolver=boundary.grant,
                trusted_state_reader=boundary.state, trusted_clock=boundary.clock),
            boundary.baseline, boundary.target, boundary.revocation, boundary.credential_reference,
            boundary.caller, boundary.clock, boundary.runtime, boundary.network,
            boundary.lifecycle, boundary.source_qualified)
        worker = a.LiveWorker(store, host, lease, runtime, network, run)
        worker._validate(profile, envelope, run.phase, target)
        op = packet["operation"]
        if type(op) is not dict or not set(op) <= {"name", "item_id", "after"}:
            _fail("USAGE")
        name = op.get("name")
        if run.phase == "SETUP" and name == "SETUP" and set(op) == {"name"}:
            outcome = worker.setup_conversation(profile, envelope, binding_id=packet["profile"]["contract"]["submission_id"])
        elif run.phase == "MUTATION" and name == "MUTATION" and set(op) == {"name"}:
            outcome = worker.mutate_one_item(profile, envelope, target)
        elif run.phase == "READ_RECONCILIATION" and name == "LIST_ITEMS" and set(op) <= {"name", "after"}:
            outcome = worker.list_items_once(profile, envelope, target, after=op.get("after"))
        elif run.phase == "READ_RECONCILIATION" and name == "RETRIEVE_ITEM" and set(op) == {"name", "item_id"}:
            outcome = worker.retrieve_item_once(profile, envelope, target, item_id=op["item_id"])
        elif run.phase == "DISPOSAL" and name == "DELETE_ITEM" and set(op) == {"name", "item_id"}:
            outcome = worker.delete_item_once(profile, envelope, target, item_id=op["item_id"])
        elif run.phase == "DISPOSAL" and name == "DELETE_CONTAINER" and set(op) == {"name"}:
            outcome = worker.delete_container_once(profile, envelope, target)
        else:
            _fail("USAGE")
        if outcome.control == "QUARANTINED":
            return 71
        if outcome.reason and "DISPOSAL_UNRESOLVED" in outcome.reason:
            return 72
        return 70 if outcome.knowledge == "UNKNOWN" else 0
    finally:
        store.close()

def _signal(number, frame):
    global _STOP, _STOP_CODE
    _STOP = True
    _STOP_CODE = {signal.SIGINT: 130, signal.SIGTERM: 143, signal.SIGHUP: 129}[number]
    raise Rejected(_STOP_CODE)

def main(argv=None):
    """No relaunch, subprocess, scheduler, discovery or fallback path."""
    try:
        # Fixed failures only; never a secret-bearing exception traceback.
        sys.excepthook = lambda *_: None
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(number, _signal)
        args = parse_cli(sys.argv[1:] if argv is None else argv)
        packet = _strict_json(read_frame(3, MAX_PACKET))
        bootstrap(packet, args)
        # Producer pin and independently established Host/Control sources precede
        # third-party loading. Missing production registrations still deny.
        boundary = establish_boundaries(packet)
        a = load_bound_modules(packet)
        code = run_bound(a, packet, boundary)
        if _STOP:
            code = _STOP_CODE or 73
    except KeyboardInterrupt:
        code = 130
    except Rejected as error:
        code = error.code
    except BaseException:
        code = 65
    result = _canonical({"exit_code": code, "authority_effect": "NONE",
                         "execution_admission": "NONE", "automatic_restart": False})
    try:
        os.write(7, len(result).to_bytes(4, "big") + result)
    except OSError:
        pass
    return code

if __name__ == "__main__":
    raise SystemExit(main())

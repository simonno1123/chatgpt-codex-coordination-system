#!/usr/bin/env python3
"""Disposable fixture construction and fixed writer capabilities.

Importing this module has no filesystem or SQLite side effects. Every writer
creates and closes its own profile-bound connection from a verified fixture
handle. Raw SQLite connections are never accepted from callers.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import stat
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import ModuleType
from typing import Iterator, Mapping

PROFILE_VERSION = "w3b-b-p1/1.0"
FIXED_DATABASE_LEAF = "acos-w3b-b-p1-disposable.sqlite3"
EXPECTED_ROOT_MODE = 0o700
EXPECTED_DATABASE_MODE = 0o600
CANONICAL_SEED_RELATIVE_PATH = Path("fixtures/state-store-w3/1.0/state-store.sql")
CANONICAL_SEED_DIGEST = (
    "sha256:a9efb6b932eb2a45e9be2cb89c364ef02c20ac2de96771f38b3aecff4244c60d"
)
FAULT_SQL = "DROP INDEX idx_audit_events_aggregate;"
REPAIR_SQL = (
    "CREATE INDEX idx_audit_events_aggregate\n"
    "ON audit_events(aggregate_type, aggregate_id, sequence);"
)
PRIVILEGED_REINDEX_SQL = "REINDEX main.idx_audit_events_aggregate"
EXPECTED_SIDECAR_SUFFIXES = ("-journal", "-wal", "-shm")

PROFILE_SEED = "SEED_INITIALIZER"
PROFILE_FAULT = "FAULT_INJECTOR"
PROFILE_REPAIR = "REPAIR_MUTATOR"

SEED_CONSTRUCTION_FAILED_DISPOSED = "SEED_CONSTRUCTION_FAILED_DISPOSED"
SEED_CONSTRUCTION_FAILED_QUARANTINED = "SEED_CONSTRUCTION_FAILED_QUARANTINED"

STATE_INITIALIZING = "INITIALIZING"
STATE_READY = "READY"
STATE_MUTATION_TASK_BOUND = "MUTATION_TASK_BOUND"
STATE_MUTATION_ATTEMPTED = "MUTATION_ATTEMPTED"
STATE_MUTATION_COMMITTED = "MUTATION_COMMITTED"
STATE_MUTATION_ROLLED_BACK = "MUTATION_ROLLED_BACK"
STATE_MUTATION_OUTCOME_UNKNOWN = "MUTATION_OUTCOME_UNKNOWN"
STATE_VERIFYING = "VERIFYING"
STATE_DISPOSING = "DISPOSING"
STATE_DISPOSED = "DISPOSED"
STATE_QUARANTINED = "QUARANTINED"

_ALLOWED_TRANSITIONS = {
    STATE_INITIALIZING: {STATE_READY, STATE_QUARANTINED},
    STATE_READY: {STATE_MUTATION_TASK_BOUND, STATE_DISPOSING, STATE_QUARANTINED},
    STATE_MUTATION_TASK_BOUND: {
        STATE_MUTATION_ATTEMPTED,
        STATE_DISPOSING,
        STATE_QUARANTINED,
    },
    STATE_MUTATION_ATTEMPTED: {
        STATE_MUTATION_COMMITTED,
        STATE_MUTATION_ROLLED_BACK,
        STATE_MUTATION_OUTCOME_UNKNOWN,
        STATE_QUARANTINED,
    },
    STATE_MUTATION_COMMITTED: {STATE_VERIFYING, STATE_QUARANTINED},
    STATE_MUTATION_ROLLED_BACK: {STATE_QUARANTINED},
    STATE_MUTATION_OUTCOME_UNKNOWN: {STATE_QUARANTINED},
    STATE_VERIFYING: {STATE_DISPOSING, STATE_QUARANTINED},
    STATE_DISPOSING: {STATE_DISPOSED, STATE_QUARANTINED},
    STATE_QUARANTINED: set(),
    STATE_DISPOSED: set(),
}


class FixtureSecurityError(RuntimeError):
    """Identity or capability evidence failed closed."""


@dataclass(frozen=True)
class SeedConstructionDisposition:
    outcome: str
    authority_effect: str = "NONE"
    production_effect: str = "NONE"
    eligible_for_execution: bool = False


class SeedConstructionFailure(FixtureSecurityError):
    """Seed construction failed and yielded no usable fixture handle."""

    def __init__(self, disposition: SeedConstructionDisposition) -> None:
        self.disposition = disposition
        super().__init__(f"seed construction failed: {disposition.outcome}")


@dataclass(frozen=True)
class FileIdentity:
    st_dev: int
    st_ino: int
    st_nlink: int
    mode: int

    @classmethod
    def from_stat(cls, value: os.stat_result) -> "FileIdentity":
        return cls(
            st_dev=value.st_dev,
            st_ino=value.st_ino,
            st_nlink=value.st_nlink,
            mode=stat.S_IMODE(value.st_mode),
        )


@dataclass(frozen=True)
class FixtureHandle:
    fixture_instance_id: str
    root: Path
    database: Path
    root_identity: FileIdentity
    database_identity: FileIdentity
    lifecycle_state: str = STATE_INITIALIZING
    reusable: bool = True
    mutation_attempt_count: int = 0
    generation: int = 0
    _factory_token: object = field(default=None, repr=False, compare=False)
    _registry_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._factory_token is not _HANDLE_TOKEN:
            raise FixtureSecurityError("FixtureHandle is factory-created only")
        if self._registry_token is None:
            raise FixtureSecurityError("FixtureHandle lacks registry attestation")


@dataclass(frozen=True)
class WriterOutcome:
    profile: str
    mutation_attempted: bool
    rollback_proven: bool
    commit_proven: bool
    outcome_uncertain: bool
    callbacks: tuple[
        tuple[int, str | None, str | None, str | None, str | None], ...
    ]
    authorization_denied: bool = False
    security_lifecycle_failure: str | None = None


class FixtureRegistry:
    """Canonical process-local fixture state; it is not authorization."""

    def __init__(self) -> None:
        self._entries: dict[str, FixtureHandle] = {}
        self._registry_token = object()
        self._state_lock = threading.RLock()
        self._active_privileged_repairs: set[str] = set()

    def _register(self, handle: FixtureHandle) -> None:
        if type(handle) is not FixtureHandle:
            raise FixtureSecurityError("fixture handle type is not canonical")
        with self._state_lock:
            if handle._registry_token is not self._registry_token:
                raise FixtureSecurityError("fixture registry attestation mismatch")
            if handle.fixture_instance_id in self._entries:
                raise FixtureSecurityError("duplicate fixture_instance_id")
            self._entries[handle.fixture_instance_id] = handle

    def get(self, fixture_instance_id: str) -> FixtureHandle:
        with self._state_lock:
            try:
                return self._entries[fixture_instance_id]
            except KeyError as exc:
                raise FixtureSecurityError("fixture is not registered") from exc

    def require_current(self, handle: FixtureHandle) -> FixtureHandle:
        """Return canonical state only for an exact, fresh registry reference."""

        if type(handle) is not FixtureHandle:
            raise FixtureSecurityError("fixture handle type is not canonical")
        with self._state_lock:
            current = self.get(handle.fixture_instance_id)
            if type(current) is not FixtureHandle:
                raise FixtureSecurityError("registry contains non-canonical handle type")
            if handle._factory_token is not _HANDLE_TOKEN:
                raise FixtureSecurityError("fixture factory attestation mismatch")
            if handle._registry_token is not self._registry_token:
                raise FixtureSecurityError("fixture registry attestation mismatch")
            if handle.generation != current.generation:
                raise FixtureSecurityError("stale fixture generation")
            if handle != current:
                raise FixtureSecurityError("caller handle differs from canonical registry state")
            return current

    def transition(
        self,
        handle: FixtureHandle,
        expected_current_state: str,
        target_state: str,
    ) -> FixtureHandle:
        """Atomically derive and install one exact default-deny transition."""

        with self._state_lock:
            current = self.require_current(handle)
            if current.fixture_instance_id in self._active_privileged_repairs:
                raise FixtureSecurityError(
                    "fixture lifecycle is locked by active privileged repair"
                )
            if current.lifecycle_state != expected_current_state:
                raise FixtureSecurityError("canonical lifecycle prestate mismatch")
            if target_state not in _ALLOWED_TRANSITIONS.get(
                current.lifecycle_state, set()
            ):
                raise FixtureSecurityError(
                    "invalid lifecycle transition: "
                    f"{current.lifecycle_state} -> {target_state}"
                )
            if current.mutation_attempt_count > 0 and current.reusable:
                raise FixtureSecurityError("canonical mutation latch is inconsistent")

            if target_state == STATE_MUTATION_ATTEMPTED:
                if not current.reusable or current.mutation_attempt_count != 0:
                    raise FixtureSecurityError("mutation attempt latch is already consumed")
                next_handle = replace(
                    current,
                    lifecycle_state=target_state,
                    reusable=False,
                    mutation_attempt_count=1,
                    generation=current.generation + 1,
                )
            else:
                reusable = current.reusable and target_state not in {
                    STATE_QUARANTINED,
                    STATE_DISPOSED,
                }
                next_handle = replace(
                    current,
                    lifecycle_state=target_state,
                    reusable=reusable,
                    generation=current.generation + 1,
                )

            if next_handle.mutation_attempt_count > 0 and next_handle.reusable:
                raise FixtureSecurityError("mutation reuse latch cannot be restored")
            self._entries[current.fixture_instance_id] = next_handle
            return next_handle

    def _remove_current(self, handle: FixtureHandle) -> None:
        with self._state_lock:
            current = self.require_current(handle)
            self._entries.pop(current.fixture_instance_id, None)

    def snapshot(self) -> Mapping[str, FixtureHandle]:
        with self._state_lock:
            return dict(self._entries)

    def _claim_privileged_repair(self, handle: FixtureHandle) -> None:
        with self._state_lock:
            current = self.require_current(handle)
            key = current.fixture_instance_id
            if key in self._active_privileged_repairs:
                raise FixtureSecurityError("privileged repair lifecycle is already active")
            self._active_privileged_repairs.add(key)

    def _release_privileged_repair(self, handle: FixtureHandle) -> None:
        with self._state_lock:
            self._active_privileged_repairs.discard(handle.fixture_instance_id)

    def _contain_active_privileged_repair_failure(
        self, handle: FixtureHandle
    ) -> FixtureHandle:
        """Quarantine canonical state while retaining an unclosed repair claim."""

        with self._state_lock:
            current = self.require_current(handle)
            if current.fixture_instance_id not in self._active_privileged_repairs:
                raise FixtureSecurityError("privileged repair claim is not active")
            if current.lifecycle_state == STATE_QUARANTINED:
                return current
            if STATE_QUARANTINED not in _ALLOWED_TRANSITIONS.get(
                current.lifecycle_state, set()
            ):
                raise FixtureSecurityError("active repair failure cannot quarantine")
            quarantined = replace(
                current,
                lifecycle_state=STATE_QUARANTINED,
                reusable=False,
                generation=current.generation + 1,
            )
            self._entries[current.fixture_instance_id] = quarantined
            return quarantined


def _identity_from_lstat(path: Path) -> FileIdentity:
    value = path.lstat()
    if stat.S_ISLNK(value.st_mode):
        raise FixtureSecurityError(f"symlink is forbidden: {path}")
    return FileIdentity.from_stat(value)


_HANDLE_TOKEN = object()


def _open_flags(*, writable: bool) -> int:
    flags = os.O_RDWR if writable else os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _verify_descriptor_identity(path: Path, expected: FileIdentity) -> None:
    descriptor = os.open(path, _open_flags(writable=False))
    try:
        observed = FileIdentity.from_stat(os.fstat(descriptor))
    finally:
        os.close(descriptor)
    if observed != expected:
        raise FixtureSecurityError("lstat/fstat fixture identity mismatch")


def canonical_sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


REPAIR_SQL_DIGEST = canonical_sha256(REPAIR_SQL.encode("utf-8"))
PRIVILEGED_REINDEX_SQL_DIGEST = canonical_sha256(
    PRIVILEGED_REINDEX_SQL.encode("utf-8")
)
CANONICAL_REPAIR_OPERATION_DIGEST = canonical_sha256(
    json.dumps(
        {
            "repair_sql_digest": REPAIR_SQL_DIGEST,
            "privileged_reindex_sql_digest": PRIVILEGED_REINDEX_SQL_DIGEST,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
)


def _verify_canonical_repair_operation_digest() -> str:
    repair_sql = REPAIR_SQL
    privileged_reindex_sql = PRIVILEGED_REINDEX_SQL
    observed = canonical_sha256(
        json.dumps(
            {
                "repair_sql_digest": canonical_sha256(repair_sql.encode("utf-8")),
                "privileged_reindex_sql_digest": canonical_sha256(
                    privileged_reindex_sql.encode("utf-8")
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    if observed != CANONICAL_REPAIR_OPERATION_DIGEST:
        raise FixtureSecurityError("canonical repair SQL identity drift")
    return repair_sql


def verify_identity_checkpoint(
    checkpoint: str,
    handle: FixtureHandle,
    registry: FixtureRegistry,
    *,
    require_no_sidecars: bool = True,
) -> None:
    """Verify path/registry identity at A, B1, B2, or C.

    B2 is a post-SQLite-open revalidation immediately before BEGIN. It binds
    the registered path and observed inode; it does not claim visibility into
    or proof of SQLite's internal file descriptor.
    """

    if checkpoint not in {"A", "B1", "B2", "C"}:
        raise FixtureSecurityError("unknown identity checkpoint")
    registered = registry.require_current(handle)
    if registered.fixture_instance_id != handle.fixture_instance_id:
        raise FixtureSecurityError("fixture_instance_id mismatch")
    if registered.root != handle.root or registered.database != handle.database:
        raise FixtureSecurityError("registered fixture path mismatch")
    if registered.database_identity != handle.database_identity:
        raise FixtureSecurityError("registered fixture identity mismatch")
    if handle.database.name != FIXED_DATABASE_LEAF:
        raise FixtureSecurityError("database leaf is not fixed")

    root_identity = _identity_from_lstat(handle.root)
    database_identity = _identity_from_lstat(handle.database)
    if root_identity != handle.root_identity:
        raise FixtureSecurityError("fixture root identity changed")
    if database_identity != handle.database_identity:
        raise FixtureSecurityError("database identity changed")
    if root_identity.mode != EXPECTED_ROOT_MODE:
        raise FixtureSecurityError("fixture root mode is not 0700")
    if database_identity.mode != EXPECTED_DATABASE_MODE:
        raise FixtureSecurityError("database mode is not 0600")
    if database_identity.st_nlink != 1:
        raise FixtureSecurityError("database hard-link count is not one")

    _verify_descriptor_identity(handle.database, database_identity)

    if require_no_sidecars:
        unexpected = [
            Path(f"{handle.database}{suffix}")
            for suffix in EXPECTED_SIDECAR_SUFFIXES
            if Path(f"{handle.database}{suffix}").exists()
        ]
        if unexpected:
            raise FixtureSecurityError(
                "unexpected lifecycle sidecar: "
                + ", ".join(str(path) for path in unexpected)
            )


def fixture_byte_digest(
    handle: FixtureHandle, registry: FixtureRegistry
) -> tuple[str, int]:
    """Hash the verified fixture through a no-follow descriptor."""

    verify_identity_checkpoint("A", handle, registry)
    descriptor = os.open(handle.database, _open_flags(writable=False))
    try:
        observed = FileIdentity.from_stat(os.fstat(descriptor))
        if observed != handle.database_identity:
            raise FixtureSecurityError("fixture digest descriptor identity mismatch")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
    finally:
        os.close(descriptor)
    verify_identity_checkpoint("A", handle, registry)
    return f"sha256:{digest.hexdigest()}", size


class DisposableFixtureFactory:
    """Creates only a fresh, exclusive, fixed-leaf disposable fixture."""

    def __init__(self, registry: FixtureRegistry | None = None) -> None:
        self.registry = registry or FixtureRegistry()

    def create(self, fixture_instance_id: str | None = None) -> FixtureHandle:
        if fixture_instance_id is not None and not fixture_instance_id.strip():
            raise FixtureSecurityError("fixture_instance_id must be non-empty")
        root = Path(tempfile.mkdtemp(prefix="acos-w3b-b-p1-"))
        os.chmod(root, EXPECTED_ROOT_MODE)
        database = root / FIXED_DATABASE_LEAF
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(database, flags, EXPECTED_DATABASE_MODE)
        try:
            os.fchmod(descriptor, EXPECTED_DATABASE_MODE)
            database_identity = FileIdentity.from_stat(os.fstat(descriptor))
        finally:
            os.close(descriptor)

        handle = FixtureHandle(
            fixture_instance_id=fixture_instance_id or str(uuid.uuid4()),
            root=root,
            database=database,
            root_identity=_identity_from_lstat(root),
            database_identity=database_identity,
            _factory_token=_HANDLE_TOKEN,
            _registry_token=self.registry._registry_token,
        )
        self.registry._register(handle)
        verify_identity_checkpoint("A", handle, self.registry)
        ready = self.registry.transition(
            handle, STATE_INITIALIZING, STATE_READY
        )
        return ready

    def quarantine(self, handle: FixtureHandle) -> FixtureHandle:
        current = self.registry.require_current(handle)
        if current.lifecycle_state == STATE_QUARANTINED:
            return current
        quarantined = self.registry.transition(
            current, current.lifecycle_state, STATE_QUARANTINED
        )
        return quarantined

    def dispose(self, handle: FixtureHandle) -> FixtureHandle:
        """Dispose only after identity checkpoint C proves the target."""

        verify_identity_checkpoint("C", handle, self.registry)
        current = self.registry.require_current(handle)
        disposing = self.registry.transition(
            current, current.lifecycle_state, STATE_DISPOSING
        )
        os.unlink(disposing.database)
        os.rmdir(disposing.root)
        disposed = self.registry.transition(
            disposing, STATE_DISPOSING, STATE_DISPOSED
        )
        self.registry._remove_current(disposed)
        return disposed


def _contain_failed_seed_failure(
    handle: FixtureHandle,
    registry: FixtureRegistry,
) -> SeedConstructionDisposition:
    """Attempt safe disposal once; otherwise retain a quarantined fixture."""

    fixture_factory = DisposableFixtureFactory(registry)
    try:
        current = registry.require_current(handle)
        if (
            current.lifecycle_state != STATE_READY
            or not current.reusable
            or current.mutation_attempt_count != 0
        ):
            raise FixtureSecurityError(
                "failed seed fixture lacks safe construction preconditions"
            )
        fixture_factory.dispose(current)
    except Exception:
        current = registry.get(handle.fixture_instance_id)
        if current.lifecycle_state != STATE_QUARANTINED:
            fixture_factory.quarantine(current)
        return SeedConstructionDisposition(SEED_CONSTRUCTION_FAILED_QUARANTINED)
    return SeedConstructionDisposition(SEED_CONSTRUCTION_FAILED_DISPOSED)


_CANONICAL_FACTORY_MODULE_NAME = "acos_w3b_b_p1_fixture_factory"
_CANONICAL_MODULES: dict[str, ModuleType] = {}
_CANONICAL_SIBLING_PROVENANCE = object()


def _module_source_digest(path: Path) -> str:
    return canonical_sha256(path.read_bytes())


def load_canonical_sibling(module_name: str, filename: str) -> ModuleType:
    """Load or reuse one exact module object for one exact source file."""

    path = Path(__file__).resolve().with_name(filename)
    source_digest = _module_source_digest(path)
    existing = sys.modules.get(module_name)
    if existing is not None:
        existing_path = Path(str(getattr(existing, "__file__", ""))).resolve()
        if (
            _CANONICAL_MODULES.get(module_name) is not existing
            or getattr(existing, "__acos_canonical_loader_provenance__", None)
            is not _CANONICAL_SIBLING_PROVENANCE
            or existing_path != path
            or getattr(existing, "__acos_canonical_source_sha256__", None)
            != source_digest
            or _module_source_digest(existing_path) != source_digest
        ):
            raise FixtureSecurityError("canonical module identity collision")
        _CANONICAL_MODULES[module_name] = existing
        return existing

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise FixtureSecurityError("canonical sibling module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    module.__acos_canonical_source_sha256__ = source_digest
    module.__acos_canonical_loader_provenance__ = _CANONICAL_SIBLING_PROVENANCE
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    if sys.modules.get(module_name) is not module:
        raise FixtureSecurityError("canonical module object was replaced during load")
    _CANONICAL_MODULES[module_name] = module
    return module


def canonical_module_fingerprint() -> str:
    """Bind the current process to one canonical W3B-B-P1 module universe."""

    factory = sys.modules.get(_CANONICAL_FACTORY_MODULE_NAME)
    if factory is not sys.modules.get(__name__):
        raise FixtureSecurityError("fixture factory is not the canonical module object")
    factory_path = Path(__file__).resolve()
    factory_digest = _module_source_digest(factory_path)
    if getattr(factory, "__acos_canonical_source_sha256__", None) != factory_digest:
        raise FixtureSecurityError("canonical fixture-factory source drift")

    records = [
        {
            "name": _CANONICAL_FACTORY_MODULE_NAME,
            "path": str(factory_path),
            "source_digest": factory_digest,
            "object_identity": id(factory),
        }
    ]
    for module_name in sorted(_CANONICAL_MODULES):
        module = _CANONICAL_MODULES[module_name]
        path = Path(str(module.__file__)).resolve()
        source_digest = _module_source_digest(path)
        if (
            sys.modules.get(module_name) is not module
            or getattr(module, "__acos_canonical_loader_provenance__", None)
            is not _CANONICAL_SIBLING_PROVENANCE
            or getattr(module, "__acos_canonical_source_sha256__", None)
            != source_digest
        ):
            raise FixtureSecurityError("canonical sibling module drift")
        records.append(
            {
                "name": module_name,
                "path": str(path),
                "source_digest": source_digest,
                "object_identity": id(module),
            }
        )
    return canonical_sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def capture_runtime_compatibility_fingerprint() -> str:
    _verify_canonical_repair_operation_digest()
    policy = _load_fixed_policy_module()
    evidence = policy.runtime_preflight(
        canonical_sql_digest=CANONICAL_REPAIR_OPERATION_DIGEST,
        canonical_module_fingerprint=canonical_module_fingerprint(),
    )
    return str(evidence.runtime_fingerprint)


def _fixture_identity_tuple(handle: FixtureHandle) -> tuple[object, ...]:
    return (
        handle.fixture_instance_id,
        str(handle.database.resolve()),
        handle.database_identity.st_dev,
        handle.database_identity.st_ino,
        handle.generation,
    )


def _verify_connection_topology(
    connection: sqlite3.Connection, handle: FixtureHandle
) -> None:
    rows = tuple(connection.execute("PRAGMA database_list"))
    main_rows = [row for row in rows if str(row[1]) == "main"]
    if len(main_rows) != 1:
        raise FixtureSecurityError("connection topology lacks one canonical main")
    main_path = Path(str(main_rows[0][2])).resolve()
    if main_path != handle.database.resolve():
        raise FixtureSecurityError("connection main database is not the fixture target")
    unauthorized = [str(row[1]) for row in rows if str(row[1]) not in {"main", "temp"}]
    if unauthorized:
        raise FixtureSecurityError("unauthorized attached application database")


def _build_internal_writer_connection():
    repair_authorizer_installer = None
    installer_lock = threading.Lock()

    def load_fixed_policy_module() -> ModuleType:
        nonlocal repair_authorizer_installer
        policy = load_canonical_sibling(
            "acos_w3b_b_p1_disposable_mutator",
            "acos-w3b-b-p1-disposable-mutator.py",
        )
        with installer_lock:
            if repair_authorizer_installer is None:
                claim = getattr(
                    policy, "_claim_internal_repair_authorizer_installer", None
                )
                if claim is None:
                    raise FixtureSecurityError(
                        "canonical repair installer is unavailable"
                    )
                repair_authorizer_installer = claim(
                    _CANONICAL_SIBLING_PROVENANCE
                )
                delattr(policy, "_claim_internal_repair_authorizer_installer")
        return policy

    @contextmanager
    def internal_writer_connection(
        handle: FixtureHandle,
        registry: FixtureRegistry,
        profile: str,
        *,
        expected_runtime_fingerprint: str | None = None,
        teardown_status: dict[str, str] | None = None,
    ) -> Iterator[tuple[sqlite3.Connection, object]]:
        """Create one fixed-profile connection without exposing it to callers."""

        policy = load_fixed_policy_module()
        repair_context = None
        connection: sqlite3.Connection | None = None
        claimed = False
        close_failure: Exception | None = None
        if profile == PROFILE_REPAIR:
            if expected_runtime_fingerprint is None:
                raise FixtureSecurityError("repair runtime fingerprint is not primed")
            observed_fingerprint = capture_runtime_compatibility_fingerprint()
            if not policy.digests_equal(
                observed_fingerprint, expected_runtime_fingerprint
            ):
                raise FixtureSecurityError("runtime compatibility fingerprint drift")
            registry._claim_privileged_repair(handle)
            claimed = True
        try:
            verify_identity_checkpoint("B1", handle, registry)
            connect_options = (
                {"cached_statements": 0} if profile == PROFILE_REPAIR else {}
            )
            connection = sqlite3.connect(handle.database, **connect_options)
            if profile == PROFILE_REPAIR:
                _verify_connection_topology(connection, handle)
                if repair_authorizer_installer is None:
                    raise FixtureSecurityError(
                        "canonical repair installer is unavailable"
                    )
                recorder, repair_context = repair_authorizer_installer(
                    connection,
                    canonical_sql_digest=CANONICAL_REPAIR_OPERATION_DIGEST,
                    fixture_identity=_fixture_identity_tuple(handle),
                    runtime_fingerprint=expected_runtime_fingerprint,
                    authorization_phase="REPAIR_STATEMENT_PREPARE_EXECUTE",
                )
            else:
                recorder = policy.install_candidate_authorizer(connection, profile)
            verify_identity_checkpoint("B2", handle, registry)
            if repair_context is not None:
                repair_context.activate(
                    canonical_sql_digest=CANONICAL_REPAIR_OPERATION_DIGEST,
                    connection_identity=id(connection),
                    fixture_identity=_fixture_identity_tuple(handle),
                    runtime_fingerprint=expected_runtime_fingerprint,
                    authorization_phase="REPAIR_STATEMENT_PREPARE_EXECUTE",
                )
            yield connection, recorder
        finally:
            try:
                if connection is not None:
                    try:
                        connection.set_authorizer(None)
                    except Exception as exc:
                        if teardown_status is not None:
                            teardown_status["authorizer_removal"] = type(exc).__name__
            finally:
                try:
                    if repair_context is not None:
                        try:
                            repair_context.expire()
                        except Exception as exc:
                            if teardown_status is not None:
                                teardown_status["context_expiration"] = type(exc).__name__
                finally:
                    try:
                        if connection is not None:
                            try:
                                connection.close()
                            except Exception as exc:
                                close_failure = exc
                                if teardown_status is not None:
                                    teardown_status["connection_close"] = type(exc).__name__
                    finally:
                        if claimed and close_failure is None:
                            registry._release_privileged_repair(handle)
            if close_failure is not None:
                if claimed:
                    registry._contain_active_privileged_repair_failure(handle)
                    message = (
                        "writer connection close failed; "
                        "active repair claim retained"
                    )
                else:
                    message = "writer connection close failed"
                raise FixtureSecurityError(message) from close_failure

    return load_fixed_policy_module, internal_writer_connection


_load_fixed_policy_module, _internal_writer_connection = (
    _build_internal_writer_connection()
)
del _build_internal_writer_connection


def _writer_outcome(
    profile: str,
    recorder: object,
    *,
    attempted: bool,
    rollback_proven: bool,
    commit_proven: bool,
    uncertain: bool,
    authorization_denied: bool = False,
    security_lifecycle_failure: str | None = None,
) -> WriterOutcome:
    return WriterOutcome(
        profile=profile,
        mutation_attempted=attempted,
        rollback_proven=rollback_proven,
        commit_proven=commit_proven,
        outcome_uncertain=uncertain,
        callbacks=tuple(getattr(recorder, "callbacks", ())),
        authorization_denied=authorization_denied,
        security_lifecycle_failure=security_lifecycle_failure,
    )


class SeedInitializer:
    """Fixed canonical seed writer; accepts neither path, SQL, nor connection."""

    profile = PROFILE_SEED

    def __init__(self, repository_root: Path) -> None:
        self._source = repository_root / CANONICAL_SEED_RELATIVE_PATH

    def source_bytes(self) -> bytes:
        data = self._source.read_bytes()
        if canonical_sha256(data) != CANONICAL_SEED_DIGEST:
            raise FixtureSecurityError("canonical seed digest mismatch")
        return data

    def initialize(
        self, handle: FixtureHandle, registry: FixtureRegistry
    ) -> WriterOutcome:
        current = registry.require_current(handle)
        if current.lifecycle_state != STATE_READY:
            raise FixtureSecurityError("seed writer requires READY fixture")
        try:
            with _internal_writer_connection(current, registry, self.profile) as (
                connection,
                recorder,
            ):
                connection.executescript(self.source_bytes().decode("utf-8"))
                return _writer_outcome(
                    self.profile,
                    recorder,
                    attempted=True,
                    rollback_proven=False,
                    commit_proven=True,
                    uncertain=False,
                )
        except Exception as exc:
            disposition = _contain_failed_seed_failure(current, registry)
            raise SeedConstructionFailure(disposition) from exc


class FaultInjector:
    """Fixed DROP INDEX writer with an internal, single-use connection."""

    profile = PROFILE_FAULT
    statement = FAULT_SQL

    def inject(
        self, handle: FixtureHandle, registry: FixtureRegistry
    ) -> WriterOutcome:
        current = registry.require_current(handle)
        if current.lifecycle_state != STATE_READY:
            raise FixtureSecurityError("fault writer requires READY fixture")
        with _internal_writer_connection(current, registry, self.profile) as (
            connection,
            recorder,
        ):
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.Error:
                return _writer_outcome(
                    self.profile,
                    recorder,
                    attempted=False,
                    rollback_proven=False,
                    commit_proven=False,
                    uncertain=False,
                )
            try:
                connection.execute(self.statement)
            except sqlite3.Error:
                rollback_proven = False
                try:
                    connection.rollback()
                    rollback_proven = not connection.in_transaction
                except sqlite3.Error:
                    pass
                return _writer_outcome(
                    self.profile,
                    recorder,
                    attempted=True,
                    rollback_proven=rollback_proven,
                    commit_proven=False,
                    uncertain=not rollback_proven,
                )
            try:
                connection.commit()
            except sqlite3.Error:
                try:
                    connection.rollback()
                except sqlite3.Error:
                    pass
                return _writer_outcome(
                    self.profile,
                    recorder,
                    attempted=True,
                    rollback_proven=False,
                    commit_proven=False,
                    uncertain=True,
                )
            return _writer_outcome(
                self.profile,
                recorder,
                attempted=True,
                rollback_proven=False,
                commit_proven=True,
                uncertain=False,
            )


class RepairMutator:
    """Fixed CREATE INDEX writer with an internal, single-use connection."""

    profile = PROFILE_REPAIR

    def __init__(self) -> None:
        self._expected_runtime_fingerprint: str | None = None

    def prime_runtime_compatibility(self) -> str:
        observed = capture_runtime_compatibility_fingerprint()
        if (
            self._expected_runtime_fingerprint is not None
            and self._expected_runtime_fingerprint != observed
        ):
            raise FixtureSecurityError("runtime compatibility fingerprint drift")
        self._expected_runtime_fingerprint = observed
        return observed

    def execute(
        self, handle: FixtureHandle, registry: FixtureRegistry
    ) -> WriterOutcome:
        current = registry.require_current(handle)
        if current.lifecycle_state != STATE_MUTATION_ATTEMPTED:
            raise FixtureSecurityError(
                "repair writer requires MUTATION_ATTEMPTED fixture"
            )
        if current.mutation_attempt_count != 1 or current.reusable:
            raise FixtureSecurityError("repair writer requires consumed attempt latch")
        if self._expected_runtime_fingerprint is None:
            raise FixtureSecurityError("repair runtime fingerprint is not primed")
        _verify_canonical_repair_operation_digest()
        teardown_status: dict[str, str] = {}
        outcome: WriterOutcome
        with _internal_writer_connection(
            current,
            registry,
            self.profile,
            expected_runtime_fingerprint=self._expected_runtime_fingerprint,
            teardown_status=teardown_status,
        ) as (
            connection,
            recorder,
        ):
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.Error:
                authorization_denied = bool(
                    getattr(recorder, "denied_callbacks", ())
                )
                outcome = _writer_outcome(
                    self.profile,
                    recorder,
                    attempted=False,
                    rollback_proven=False,
                    commit_proven=False,
                    uncertain=False,
                    authorization_denied=authorization_denied,
                )
            else:
                repair_statement = _verify_canonical_repair_operation_digest()
                try:
                    connection.execute(repair_statement)
                except sqlite3.Error:
                    admission_consumed = bool(
                        getattr(recorder, "privileged_admission_consumed", False)
                    )
                    authorization_denied = bool(
                        getattr(recorder, "denied_callbacks", ())
                    ) and not admission_consumed
                    mutation_attempted = admission_consumed or not authorization_denied
                    rollback_proven = False
                    try:
                        connection.rollback()
                        rollback_proven = not connection.in_transaction
                    except sqlite3.Error:
                        pass
                    outcome = _writer_outcome(
                        self.profile,
                        recorder,
                        attempted=mutation_attempted,
                        rollback_proven=rollback_proven and mutation_attempted,
                        commit_proven=False,
                        uncertain=mutation_attempted and not rollback_proven,
                        authorization_denied=authorization_denied,
                    )
                else:
                    if not getattr(
                        recorder, "privileged_admission_consumed", False
                    ):
                        rollback_proven = False
                        try:
                            connection.rollback()
                            rollback_proven = not connection.in_transaction
                        except sqlite3.Error:
                            pass
                        outcome = _writer_outcome(
                            self.profile,
                            recorder,
                            attempted=True,
                            rollback_proven=rollback_proven,
                            commit_proven=False,
                            uncertain=not rollback_proven,
                            security_lifecycle_failure=(
                                "PRIVILEGED_ADMISSION_NOT_OBSERVED"
                            ),
                        )
                    else:
                        try:
                            connection.commit()
                        except sqlite3.Error:
                            try:
                                connection.rollback()
                            except sqlite3.Error:
                                pass
                            outcome = _writer_outcome(
                                self.profile,
                                recorder,
                                attempted=True,
                                rollback_proven=False,
                                commit_proven=False,
                                uncertain=True,
                            )
                        else:
                            outcome = _writer_outcome(
                                self.profile,
                                recorder,
                                attempted=True,
                                rollback_proven=False,
                                commit_proven=True,
                                uncertain=False,
                            )

        if teardown_status:
            failure = ",".join(sorted(teardown_status))
            return _writer_outcome(
                self.profile,
                recorder,
                attempted=outcome.mutation_attempted,
                rollback_proven=False,
                commit_proven=False,
                uncertain=outcome.mutation_attempted or outcome.commit_proven,
                authorization_denied=outcome.authorization_denied,
                security_lifecycle_failure=failure,
            )
        return outcome

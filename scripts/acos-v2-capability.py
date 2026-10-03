"""Bounded capability model and read-only validation, never execution admission.

The integrating host must preload Core once as ``acos_v2_core_substrate`` and
independently establish the three trusted, read-only callbacks. This module
does not load another Core copy, issue grants, authenticate callers, or install
a production trust anchor. Test callbacks are not production authentication.

A caller-created envelope is only a candidate. Its full contents must match
the independent grant resolver, and fresh state evidence must bind the same
identity, authority, and cancellation context. These reads are not an atomic
consume-and-execute protocol: PASS is not safe admission for an irreversible
operation. Python objects do not protect against a host controlling the process.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import sys
from types import ModuleType


_CORE_NAME = "acos_v2_core_substrate"
_CORE_PATH = str(Path(__file__).resolve().with_name("acos-v2-core-substrate.py"))
_core = sys.modules.get(_CORE_NAME)
if not isinstance(_core, ModuleType) or vars(_core).get("__file__") != _CORE_PATH:
    raise ImportError("preload canonical acos_v2_core_substrate from its repository path")

ExecutionIdentity = _core.ExecutionIdentity
AuthorityReference = _core.AuthorityReference
WorkflowScope = _core.WorkflowScope

SINGLE_USE = "SINGLE_USE"
REUSABLE = "REUSABLE"
ACTIVE = "ACTIVE"
CANCELLED = "CANCELLED"
REVOKED = "REVOKED"
UNKNOWN = "UNKNOWN"


def _canonical_core_intact():
    if sys.modules.get(_CORE_NAME) is not _core:
        return False
    core_namespace = vars(_core)
    if (
        core_namespace.get("ExecutionIdentity") is not ExecutionIdentity
        or core_namespace.get("AuthorityReference") is not AuthorityReference
        or core_namespace.get("WorkflowScope") is not WorkflowScope
        or core_namespace.get("__file__") != _CORE_PATH
    ):
        return False
    return not any(
        module is not _core
        and isinstance(module, ModuleType)
        and vars(module).get("__file__") == _CORE_PATH
        for module in tuple(sys.modules.values())
    )


@dataclass(frozen=True)
class CapabilityEnvelope:
    capability_id: str
    capability_class: str
    operation: str
    target: str
    execution_identity: ExecutionIdentity
    authority_reference: AuthorityReference
    not_after: datetime
    consumption_policy: str
    cancellation_binding: str


@dataclass(frozen=True)
class ValidationRequest:
    """Exact comparison context, not proof of an authenticated submitting actor."""

    capability_class: str
    operation: str
    target: str
    execution_identity: ExecutionIdentity
    authority_reference: AuthorityReference
    scope: WorkflowScope
    baseline_revision: str
    cancellation_binding: str


@dataclass(frozen=True)
class CapabilityStateEvidence:
    """Return type of an independently established read-only state boundary.

    Constructing this object, including ACTIVE, is not authority. Only the
    host-configured trusted state reader may supply it to this validator.
    """

    capability_id: str
    execution_identity: ExecutionIdentity
    authority_reference: AuthorityReference
    cancellation_binding: str
    runtime_state: str
    consumed: bool


@dataclass(frozen=True)
class ValidationResult:
    status: str
    reason: str
    validation_only: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    authority_effect: str = field(default="NONE", init=False)
    execution_effect: str = field(default="NONE", init=False)
    consumption_effect: str = field(default="NONE", init=False)
    reservation_effect: str = field(default="NONE", init=False)


def _text(value):
    return type(value) is str and bool(value) and value == value.strip()


def _exact_selector(value):
    return _text(value) and "*" not in value


def _identity_error(identity, reference):
    if type(identity) is not ExecutionIdentity:
        return "non-canonical execution identity"
    if type(reference) is not AuthorityReference:
        return "non-canonical authority reference"
    if not all(_text(getattr(identity, name)) for name in ExecutionIdentity.__dataclass_fields__):
        return "invalid execution identity"
    if not _core.REVISION.fullmatch(identity.baseline_revision):
        return "invalid identity baseline"
    if not _text(reference.authorization_id) or not _text(reference.content_digest):
        return "invalid authority reference"
    if not _core.DIGEST.fullmatch(reference.content_digest):
        return "invalid authority digest"
    if identity.authorization_id != reference.authorization_id:
        return "authorization linkage mismatch"
    return None


def _aware_time(value):
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _envelope_error(envelope):
    if type(envelope) is not CapabilityEnvelope:
        return "expected a capability envelope"
    if not _text(envelope.capability_id) or not _text(envelope.cancellation_binding):
        return "invalid capability or cancellation binding"
    if not all(_exact_selector(getattr(envelope, name)) for name in ("capability_class", "operation", "target")):
        return "invalid exact capability selector"
    error = _identity_error(envelope.execution_identity, envelope.authority_reference)
    if error:
        return error
    if type(envelope.consumption_policy) is not str or envelope.consumption_policy not in (SINGLE_USE, REUSABLE):
        return "explicit consumption policy required"
    try:
        if not _aware_time(envelope.not_after):
            return "invalid expiry"
    except Exception:
        return "invalid expiry"
    return None


class CapabilityValidator:
    """Only validate(); no writers, execution token, adapters, or default trust.

    Trusted callbacks are supplied by the integrating host, not per-request
    data. They must authenticate their own sources and perform read-only
    observations. This model does not implement their production providers.
    """

    def __init__(self, *, trusted_grant_resolver=None, trusted_state_reader=None, trusted_clock=None):
        self._trusted_grant_resolver = trusted_grant_resolver
        self._trusted_state_reader = trusted_state_reader
        self._trusted_clock = trusted_clock

    def validate(self, envelope, request):
        if not _canonical_core_intact():
            return ValidationResult("DENY", "canonical Core module identity changed or duplicated")
        error = _envelope_error(envelope)
        if error:
            return ValidationResult("DENY", error)
        if type(request) is not ValidationRequest:
            return ValidationResult("DENY", "expected an exact validation request")
        error = _identity_error(request.execution_identity, request.authority_reference)
        if error:
            return ValidationResult("DENY", error)
        if type(request.scope) is not WorkflowScope or not all(
            _text(getattr(request.scope, name)) for name in WorkflowScope.__dataclass_fields__
        ):
            return ValidationResult("DENY", "invalid workflow scope")
        if not _text(request.baseline_revision) or not _core.REVISION.fullmatch(request.baseline_revision):
            return ValidationResult("DENY", "invalid requested baseline")
        if request.execution_identity.baseline_revision != request.baseline_revision:
            return ValidationResult("DENY", "baseline mismatch")
        if (
            request.execution_identity.project_id,
            request.execution_identity.stage_id,
            request.execution_identity.task_id,
        ) != (request.scope.project_id, request.scope.stage_id, request.scope.task_id):
            return ValidationResult("DENY", "scope mismatch")
        if request.execution_identity != envelope.execution_identity:
            return ValidationResult("DENY", "execution identity or attempt mismatch")
        if request.authority_reference != envelope.authority_reference:
            return ValidationResult("DENY", "authority reference mismatch")
        if not _text(request.cancellation_binding) or request.cancellation_binding != envelope.cancellation_binding:
            return ValidationResult("DENY", "cancellation binding mismatch")
        for name in ("capability_class", "operation", "target"):
            if not _exact_selector(getattr(request, name)) or getattr(request, name) != getattr(envelope, name):
                return ValidationResult("DENY", f"exact {name} mismatch")

        if not callable(self._trusted_grant_resolver):
            return ValidationResult("DENY", "trusted grant resolver unavailable")
        try:
            grant = self._trusted_grant_resolver(envelope.capability_id)
        except Exception:
            return ValidationResult("DENY", "trusted grant resolution failed")
        error = _envelope_error(grant)
        if error:
            return ValidationResult("DENY", "trusted grant invalid: " + error)
        if grant != envelope:
            return ValidationResult("DENY", "candidate does not match the trusted grant")

        if not callable(self._trusted_state_reader):
            return ValidationResult("DENY", "trusted state reader unavailable")
        try:
            state = self._trusted_state_reader(envelope.capability_id)
        except Exception:
            return ValidationResult("DENY", "trusted state observation failed")
        if type(state) is not CapabilityStateEvidence:
            return ValidationResult("DENY", "trusted state evidence unavailable")
        error = _identity_error(state.execution_identity, state.authority_reference)
        if error:
            return ValidationResult("DENY", "trusted state invalid: " + error)
        if (
            not _text(state.capability_id)
            or not _text(state.cancellation_binding)
            or state.capability_id != envelope.capability_id
            or state.execution_identity != envelope.execution_identity
            or state.authority_reference != envelope.authority_reference
            or state.cancellation_binding != envelope.cancellation_binding
        ):
            return ValidationResult("DENY", "runtime state evidence binding mismatch")
        if type(state.runtime_state) is not str or state.runtime_state != ACTIVE:
            return ValidationResult("DENY", "runtime capability state is not ACTIVE")
        if type(state.consumed) is not bool:
            return ValidationResult("DENY", "invalid consumption evidence")
        if envelope.consumption_policy == SINGLE_USE and state.consumed:
            return ValidationResult("DENY", "single-use capability already consumed")

        if not callable(self._trusted_clock):
            return ValidationResult("DENY", "trusted clock unavailable")
        try:
            current_time = self._trusted_clock()
            if not _aware_time(current_time):
                return ValidationResult("DENY", "invalid trusted clock reading")
            if current_time >= envelope.not_after:
                return ValidationResult("DENY", "capability expired")
        except Exception:
            return ValidationResult("DENY", "trusted clock failed")
        if not _canonical_core_intact():
            return ValidationResult("DENY", "canonical Core module identity changed or duplicated")
        return ValidationResult("PASS", "exact capability constraints validated; no execution authority")

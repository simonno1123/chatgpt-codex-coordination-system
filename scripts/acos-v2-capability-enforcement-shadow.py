"""R0 capability integration reference, not admission or execution mediation.

The host preloads canonical Core and Capability modules and independently
establishes the read-only validator callbacks and current-baseline reader.
The reader's revision is an observation, not caller authentication or authority.
No production reader, dispatcher, writer, adapter, or consumption ledger exists
here. PASS cannot be used as an execution token. Existing runtime paths remain
outside this observer; current full-path mediation is NO. IC-03/IC-04 are not
fully closed by a successful shadow observation.

Callbacks must be read-only. This module cannot sandbox a host-controlled
callback or defend against a host controlling Python objects or the process.
"""

from dataclasses import dataclass, field
from pathlib import Path
import sys
from types import ModuleType


_CAPABILITY_NAME = "acos_v2_capability"
_CAPABILITY_PATH = str(Path(__file__).resolve().with_name("acos-v2-capability.py"))
_capability = sys.modules.get(_CAPABILITY_NAME)
if not isinstance(_capability, ModuleType) or vars(_capability).get("__file__") != _CAPABILITY_PATH:
    raise ImportError("preload canonical acos_v2_capability from its repository path")
if not _capability._canonical_core_intact():
    raise ImportError("preload one intact canonical Core module")

_core = sys.modules["acos_v2_core_substrate"]
_Envelope = _capability.CapabilityEnvelope
_Request = _capability.ValidationRequest
_Validator = _capability.CapabilityValidator
_ValidationResult = _capability.ValidationResult


def _canonical_modules_intact():
    if sys.modules.get(_CAPABILITY_NAME) is not _capability:
        return False
    namespace = vars(_capability)
    if (
        namespace.get("__file__") != _CAPABILITY_PATH
        or namespace.get("CapabilityEnvelope") is not _Envelope
        or namespace.get("ValidationRequest") is not _Request
        or namespace.get("CapabilityValidator") is not _Validator
        or namespace.get("ValidationResult") is not _ValidationResult
        or not _capability._canonical_core_intact()
    ):
        return False
    return not any(
        module is not _capability
        and isinstance(module, ModuleType)
        and vars(module).get("__file__") == _CAPABILITY_PATH
        for module in tuple(sys.modules.values())
    )


@dataclass(frozen=True)
class ShadowObservation:
    validation_status: str
    baseline_match: bool
    reason: str
    observation_only: bool = field(default=True, init=False)
    admission_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    authority_effect: str = field(default="NONE", init=False)
    execution_effect: str = field(default="NONE", init=False)
    consumption_effect: str = field(default="NONE", init=False)
    reservation_effect: str = field(default="NONE", init=False)


def _input_error(envelope, request):
    # Reuse the frozen model's structural rules, not a second capability model.
    error = _capability._envelope_error(envelope)
    if error:
        return error
    if type(request) is not _Request:
        return "expected a canonical validation request"
    error = _capability._identity_error(request.execution_identity, request.authority_reference)
    if error:
        return error
    if type(request.scope) is not _core.WorkflowScope or not all(
        _capability._text(getattr(request.scope, name))
        for name in _core.WorkflowScope.__dataclass_fields__
    ):
        return "invalid workflow scope"
    if not _capability._text(request.baseline_revision) or not _core.REVISION.fullmatch(request.baseline_revision):
        return "invalid requested baseline"
    if not all(
        _capability._exact_selector(getattr(request, name))
        for name in ("capability_class", "operation", "target")
    ):
        return "invalid exact request selector"
    if not _capability._text(request.cancellation_binding):
        return "invalid request cancellation binding"
    return None


class CapabilityEnforcementShadowObserver:
    """Only observe(); trusted dependencies are host-bound, never request grants."""

    def __init__(self, *, validator=None, trusted_current_baseline_reader=None):
        self._validator = validator
        self._baseline_reader = trusted_current_baseline_reader

    def observe(self, envelope, request):
        if not _canonical_modules_intact():
            return ShadowObservation("DENY", False, "canonical module identity changed or duplicated")
        if type(self._validator) is not _Validator:
            return ShadowObservation("DENY", False, "canonical capability validator unavailable")
        error = _input_error(envelope, request)
        if error:
            return ShadowObservation("DENY", False, error)
        if not callable(self._baseline_reader):
            return ShadowObservation("DENY", False, "trusted current-baseline reader unavailable")
        try:
            observed_baseline = self._baseline_reader()
        except Exception:
            return ShadowObservation("DENY", False, "trusted current-baseline observation failed")
        if not _canonical_modules_intact():
            return ShadowObservation("DENY", False, "canonical module identity changed during baseline observation")
        if type(observed_baseline) is not str or not _core.REVISION.fullmatch(observed_baseline):
            return ShadowObservation("DENY", False, "invalid observed baseline")
        if not (
            observed_baseline == request.baseline_revision
            == request.execution_identity.baseline_revision
        ):
            return ShadowObservation("DENY", False, "observed/request/identity baseline mismatch")
        try:
            validation = self._validator.validate(envelope, request)
        except Exception:
            return ShadowObservation("DENY", True, "capability validation failed")
        if not _canonical_modules_intact():
            return ShadowObservation("DENY", True, "canonical module identity changed during validation")
        if (
            type(validation) is not _ValidationResult
            or type(validation.status) is not str
            or validation.status not in ("PASS", "DENY")
            or not _capability._text(validation.reason)
            or validation.validation_only is not True
            or validation.execution_authorized is not False
            or any(
                type(getattr(validation, name)) is not str or getattr(validation, name) != "NONE"
                for name in ("authority_effect", "execution_effect", "consumption_effect", "reservation_effect")
            )
        ):
            return ShadowObservation("DENY", True, "invalid non-admission validation result")
        return ShadowObservation(validation.status, True, validation.reason)

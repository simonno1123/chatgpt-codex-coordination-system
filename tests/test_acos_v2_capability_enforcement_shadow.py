import builtins
from contextlib import ExitStack
from dataclasses import FrozenInstanceError, asdict, make_dataclass, replace
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_once(name, path):
    existing = sys.modules.get(name)
    if existing is not None:
        if vars(existing).get("__file__") != str(path):
            raise ImportError("foreign canonical module")
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[name]
        raise
    return module


core = None
capability = None
shadow = None


class CapabilityEnforcementShadowTests(unittest.TestCase):
    """S-01--S-30 use in-memory reader doubles, not production authentication."""

    @classmethod
    def setUpClass(cls):
        global core, capability, shadow
        core = load_once("acos_v2_core_substrate", ROOT / "scripts" / "acos-v2-core-substrate.py")
        capability = load_once("acos_v2_capability", ROOT / "scripts" / "acos-v2-capability.py")
        shadow = load_once("acos_v2_capability_enforcement_shadow",
                           ROOT / "scripts" / "acos-v2-capability-enforcement-shadow.py")

    def setUp(self):
        self.baseline = "6a9d3193744ae8b9828f0190f3759a9c2f635ac9"
        self.identity = core.ExecutionIdentity(
            "ACOS", "initial-shadow", "fixture-task", "fixture-authorization",
            "Codex Executor", "fixture-attempt", self.baseline,
        )
        self.authority = core.AuthorityReference("fixture-authorization", "sha256:" + "1" * 64)
        self.scope = core.WorkflowScope("ACOS", "initial-shadow", "fixture-task")
        self.now = datetime(2026, 10, 3, 0, 0, tzinfo=timezone.utc)
        self.envelope = capability.CapabilityEnvelope(
            "fixture-capability", "git", "git.stage", "repo:fixture/exact-path",
            self.identity, self.authority, self.now + timedelta(seconds=1),
            capability.SINGLE_USE, "fixture-cancellation-context",
        )
        self.request = capability.ValidationRequest(
            self.envelope.capability_class, self.envelope.operation, self.envelope.target,
            self.identity, self.authority, self.scope, self.baseline,
            self.envelope.cancellation_binding,
        )
        self.state = capability.CapabilityStateEvidence(
            self.envelope.capability_id, self.identity, self.authority,
            self.envelope.cancellation_binding, capability.ACTIVE, False,
        )
        self.baseline_reader = mock.Mock(return_value=self.baseline)
        self.grant_reader = mock.Mock(return_value=self.envelope)
        self.state_reader = mock.Mock(return_value=self.state)
        self.clock = mock.Mock(return_value=self.now)
        self.validator = self.make_validator()
        self.observer = self.make_observer()

    def make_validator(self, **overrides):
        values = dict(trusted_grant_resolver=self.grant_reader,
                      trusted_state_reader=self.state_reader, trusted_clock=self.clock)
        values.update(overrides)
        return capability.CapabilityValidator(**values)

    def make_observer(self, **overrides):
        values = dict(validator=self.validator, trusted_current_baseline_reader=self.baseline_reader)
        values.update(overrides)
        return shadow.CapabilityEnforcementShadowObserver(**values)

    def observe(self, *, envelope=None, request=None, observer=None):
        return (self.observer if observer is None else observer).observe(
            self.envelope if envelope is None else envelope,
            self.request if request is None else request,
        )

    def assert_non_admission(self, result):
        self.assertTrue(result.observation_only)
        self.assertFalse(result.admission_authorized)
        self.assertFalse(result.execution_authorized)
        self.assertEqual((result.authority_effect, result.execution_effect,
                          result.consumption_effect, result.reservation_effect), ("NONE",) * 4)

    def assert_denied(self, **arguments):
        result = self.observe(**arguments)
        self.assertEqual(result.validation_status, "DENY")
        self.assert_non_admission(result)
        return result

    def assert_guarded_observations(self, forbidden):
        with ExitStack() as stack:
            guards = [stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError(name)))
                      for owner, name in forbidden]
            result = self.observe()
            self.assertEqual(result.validation_status, "PASS")
            self.assert_non_admission(result)
            self.assert_denied(request=replace(self.request, operation="git.push"))
            for guard in guards:
                guard.assert_not_called()

    def shadow_copy(self, instance):
        copied = make_dataclass("Copied" + type(instance).__name__,
                                [(name, str) for name in instance.__dataclass_fields__], frozen=True)
        return copied(**asdict(instance))

    def test_s01_canonical_envelope_input(self):
        self.assertIs(shadow._Envelope, capability.CapabilityEnvelope)
        self.assertEqual(self.observe().validation_status, "PASS")
        self.assert_denied(envelope=self.shadow_copy(self.envelope))

    def test_s02_canonical_request_input(self):
        self.assertIs(shadow._Request, capability.ValidationRequest)
        self.assertEqual(self.observe().validation_status, "PASS")
        self.assert_denied(request=self.shadow_copy(self.request))

    def test_s03_missing_baseline_reader_denies_before_validator(self):
        result = self.assert_denied(observer=self.make_observer(trusted_current_baseline_reader=None))
        self.assertFalse(result.baseline_match)
        self.grant_reader.assert_not_called()
        self.state_reader.assert_not_called()
        self.clock.assert_not_called()

    def test_s04_baseline_reader_exception_denies_before_validator(self):
        self.baseline_reader.side_effect = RuntimeError("unavailable")
        self.assertFalse(self.assert_denied().baseline_match)
        self.grant_reader.assert_not_called()

    def test_s05_invalid_observed_baseline_denies(self):
        for value in (None, 0, True, "", "HEAD", "a" * 39, "A" * 40, self.baseline + "\n"):
            with self.subTest(value=value):
                self.baseline_reader.return_value = value
                self.assertFalse(self.assert_denied().baseline_match)
        self.grant_reader.assert_not_called()

    def test_s06_observed_baseline_mismatch_denies(self):
        self.baseline_reader.return_value = "a" * 40
        self.assertFalse(self.assert_denied().baseline_match)
        self.grant_reader.assert_not_called()

    def test_s07_request_identity_baseline_mismatch_denies(self):
        identity = replace(self.identity, baseline_revision="a" * 40)
        result = self.assert_denied(request=replace(self.request, execution_identity=identity))
        self.assertFalse(result.baseline_match)
        self.baseline_reader.assert_called_once_with()
        self.grant_reader.assert_not_called()

    def test_s08_matching_baselines_continue_to_validator(self):
        with mock.patch.object(self.validator, "validate", wraps=self.validator.validate) as validate:
            result = self.observe()
            self.assertTrue(result.baseline_match)
            validate.assert_called_once_with(self.envelope, self.request)
        self.baseline_reader.assert_called_once_with()

    def test_s09_validator_pass_is_observation_only(self):
        result = self.observe()
        self.assertEqual(result.validation_status, "PASS")
        self.assert_non_admission(result)

    def test_s10_validator_deny_propagates(self):
        result = self.assert_denied(request=replace(self.request, operation="git.commit"))
        self.assertTrue(result.baseline_match)
        self.assertEqual(result.reason, "exact operation mismatch")

    def test_s11_expired_capability_denies(self):
        self.clock.return_value = self.envelope.not_after
        self.assertEqual(self.assert_denied().reason, "capability expired")

    def test_s12_cancelled_capability_denies(self):
        self.state_reader.return_value = replace(self.state, runtime_state=capability.CANCELLED)
        self.assert_denied()

    def test_s13_revoked_capability_denies(self):
        self.state_reader.return_value = replace(self.state, runtime_state=capability.REVOKED)
        self.assert_denied()

    def test_s14_unknown_capability_state_denies(self):
        for value in (capability.UNKNOWN, None, "PASS", "active"):
            with self.subTest(value=value):
                self.state_reader.return_value = replace(self.state, runtime_state=value)
                self.assert_denied()

    def test_s15_grant_state_clock_failures_propagate_deny(self):
        for name, reader in (("trusted_grant_resolver", self.grant_reader),
                             ("trusted_state_reader", self.state_reader),
                             ("trusted_clock", self.clock)):
            with self.subTest(boundary=name, failure="missing"):
                validator = self.make_validator(**{name: None})
                self.assert_denied(observer=self.make_observer(validator=validator))
            with self.subTest(boundary=name, failure="exception"):
                reader.side_effect = RuntimeError("unavailable")
                self.assert_denied()
                reader.side_effect = None

    def test_s16_pass_has_no_admission(self):
        result = self.observe()
        self.assertEqual(result.validation_status, "PASS")
        self.assertIs(result.admission_authorized, False)

    def test_s17_pass_has_no_execution_authorization(self):
        result = self.observe()
        self.assertEqual(result.validation_status, "PASS")
        self.assertIs(result.execution_authorized, False)

    def test_s18_pass_has_no_authority_or_execution_effect(self):
        result = self.observe()
        self.assertEqual(result.validation_status, "PASS")
        self.assertEqual((result.authority_effect, result.execution_effect), ("NONE", "NONE"))

    def test_s19_pass_has_no_consumption_effect(self):
        result = self.observe()
        self.assertEqual(result.validation_status, "PASS")
        self.assertEqual(result.consumption_effect, "NONE")

    def test_s20_pass_has_no_reservation_effect(self):
        result = self.observe()
        self.assertEqual(result.validation_status, "PASS")
        self.assertEqual(result.reservation_effect, "NONE")

    def test_s21_no_journal_append_or_accepted_record_issuance(self):
        self.assert_guarded_observations(((core.StateJournalWriter, "append"),
                                          (core.TransitionEngine, "validate"),
                                          (core._RecordIssuer, "issue")))

    def test_s22_no_store_or_sqlite_creation(self):
        self.assert_guarded_observations(((core.StateStore, "__init__"), (core.sqlite3, "connect")))

    def test_s23_no_filesystem_mutation(self):
        self.assert_guarded_observations((
            (builtins, "open"), (io, "open"), (os, "open"), (os, "remove"),
            (os, "unlink"), (os, "rename"), (os, "replace"), (os, "mkdir"),
            (os, "rmdir"), (os, "chmod"), (Path, "write_text"),
            (Path, "write_bytes"), (Path, "touch"),
        ))

    def test_s24_no_git_or_subprocess_invocation(self):
        self.assert_guarded_observations(((os, "system"), (subprocess, "run"),
                                          (subprocess, "Popen"), (subprocess, "call"),
                                          (subprocess, "check_call"), (subprocess, "check_output")))

    def test_s25_no_network_invocation(self):
        self.assert_guarded_observations(((socket, "socket"), (socket, "create_connection")))

    def test_s26_no_adapter_dispatch_api(self):
        result = self.observe()
        self.assertEqual([name for name in dir(self.observer)
                          if not name.startswith("_") and callable(getattr(self.observer, name))], ["observe"])
        for name in ("adapter", "dispatch", "invoke", "token"):
            self.assertFalse(hasattr(self.observer, name))
            self.assertFalse(hasattr(result, name))

    def test_s27_no_consume_reserve_execute_api(self):
        result = self.observe()
        for name in ("consume", "reserve", "execute", "commit", "append"):
            self.assertFalse(hasattr(self.observer, name))
            self.assertFalse(hasattr(result, name))

    def test_s28_inputs_and_results_are_not_mutated(self):
        before = (asdict(self.envelope), asdict(self.request), asdict(self.state))
        validation = self.validator.validate(self.envelope, self.request)
        validation_before = asdict(validation)
        with mock.patch.object(self.validator, "validate", return_value=validation):
            result = self.observe()
        self.assertEqual(result.validation_status, "PASS")
        self.assertEqual((asdict(self.envelope), asdict(self.request), asdict(self.state)), before)
        self.assertEqual(asdict(validation), validation_before)
        with self.assertRaises(FrozenInstanceError):
            result.admission_authorized = True
        with self.assertRaises(FrozenInstanceError):
            result.execution_authorized = True
        with self.assertRaises(TypeError):
            shadow.ShadowObservation("PASS", True, "fixture", execution_authorized=True)

    def test_s29_role_producer_and_shadow_pass_do_not_create_authority(self):
        for role in ("ChatGPT Review", "User Decision", "Codex Executor"):
            with self.subTest(role=role):
                identity = replace(self.identity, executor_role=role)
                envelope = replace(self.envelope, execution_identity=identity)
                request = replace(self.request, execution_identity=identity)
                validator = self.make_validator(trusted_grant_resolver=None)
                self.assert_denied(envelope=envelope, request=request,
                                   observer=self.make_observer(validator=validator))
        self.grant_reader.return_value = {"PRODUCER": "ChatGPT Review", "status": "PASS",
                                         "authenticated": True, "envelope": self.envelope}
        self.assert_denied()
        self.grant_reader.return_value = self.envelope
        result = self.observe()
        self.assertEqual(result.validation_status, "PASS")
        self.assert_denied(envelope=result)
        with self.assertRaises(TypeError):
            self.observer.observe(self.envelope, self.request, PRODUCER="ChatGPT Review")

    def test_s30_repeated_success_remains_non_admission(self):
        before = (asdict(self.envelope), asdict(self.state))
        for _ in range(2):
            result = self.observe()
            self.assertEqual(result.validation_status, "PASS")
            self.assert_non_admission(result)
        self.assertEqual((asdict(self.envelope), asdict(self.state)), before)
        self.assertFalse(self.state.consumed)
        self.assertEqual(self.state_reader.call_args_list, [mock.call(self.envelope.capability_id)] * 2)

    def test_existing_validation_result_execution_authorized_is_never_rewritten(self):
        for request in (self.request, replace(self.request, operation="git.push")):
            with self.subTest(operation=request.operation):
                validation = self.validator.validate(self.envelope, request)
                before = asdict(validation)
                self.assertIs(validation.execution_authorized, False)
                with mock.patch.object(self.validator, "validate", return_value=validation):
                    result = self.observe(request=request)
                self.assertEqual(result.validation_status, validation.status)
                self.assert_non_admission(result)
                self.assertEqual(asdict(validation), before)
                with self.assertRaises(FrozenInstanceError):
                    validation.execution_authorized = True

    def test_observation_order_is_baseline_then_validation_then_readers(self):
        events = []
        self.baseline_reader.side_effect = lambda: events.append("baseline") or self.baseline
        self.grant_reader.side_effect = lambda _id: events.append("grant") or self.envelope
        self.state_reader.side_effect = lambda _id: events.append("state") or self.state
        self.clock.side_effect = lambda: events.append("clock") or self.now
        original = self.validator.validate
        def recorded_validate(envelope, request):
            events.append("validate")
            return original(envelope, request)
        with mock.patch.object(self.validator, "validate", side_effect=recorded_validate):
            self.assertEqual(self.observe().validation_status, "PASS")
        self.assertEqual(events, ["baseline", "validate", "grant", "state", "clock"])

    def test_malformed_inputs_stop_before_baseline_reader(self):
        variants = (
            ("envelope", replace(self.envelope, execution_identity=self.shadow_copy(self.identity))),
            ("envelope", replace(self.envelope, authority_reference=self.shadow_copy(self.authority))),
            ("envelope", replace(self.envelope, not_after=self.now.replace(tzinfo=None))),
            ("request", replace(self.request, execution_identity=self.shadow_copy(self.identity))),
            ("request", replace(self.request, scope=self.shadow_copy(self.scope))),
            ("request", replace(self.request, baseline_revision="HEAD")),
            ("request", replace(self.request, operation="git.*")),
            ("request", replace(self.request, cancellation_binding="")),
        )
        with mock.patch.object(self.validator, "validate", wraps=self.validator.validate) as validate:
            for argument, value in variants:
                with self.subTest(argument=argument, value=value):
                    self.assert_denied(**{argument: value})
            validate.assert_not_called()
        self.baseline_reader.assert_not_called()

    def test_missing_and_noncanonical_validator_deny_before_baseline_reader(self):
        class ValidatorSubclass(capability.CapabilityValidator):
            pass
        for value in (None, mock.Mock(), ValidatorSubclass()):
            with self.subTest(value=value):
                self.assert_denied(observer=self.make_observer(validator=value))
        self.baseline_reader.assert_not_called()

    def test_validator_exception_and_invalid_output_fail_closed(self):
        with mock.patch.object(self.validator, "validate", side_effect=RuntimeError("failure")):
            self.assert_denied()
        for value in (None, {"status": "PASS"}, capability.ValidationResult("UNKNOWN", "fixture")):
            with self.subTest(value=value):
                with mock.patch.object(self.validator, "validate", return_value=value):
                    self.assert_denied()
        compromised = capability.ValidationResult("PASS", "fixture")
        object.__setattr__(compromised, "execution_authorized", True)
        with mock.patch.object(self.validator, "validate", return_value=compromised):
            self.assert_denied()

    def test_replaced_or_duplicate_canonical_modules_deny(self):
        for name, module in (("acos_v2_capability", capability), ("acos_v2_core_substrate", core)):
            with self.subTest(module=name):
                replacement = ModuleType(name)
                replacement.__file__ = module.__file__
                with mock.patch.dict(sys.modules, {name: replacement}):
                    self.assert_denied()
                duplicate = ModuleType("fixture_duplicate")
                duplicate.__file__ = module.__file__
                with mock.patch.dict(sys.modules, {duplicate.__name__: duplicate}):
                    self.assert_denied()
                with mock.patch.dict(sys.modules, {"fixture_same_module_alias": module}):
                    self.assertEqual(self.observe().validation_status, "PASS")

    def test_baseline_callback_module_replacement_denies_before_validator(self):
        replacement = ModuleType("acos_v2_capability")
        replacement.__file__ = capability.__file__
        with mock.patch.dict(sys.modules):
            def changed_baseline():
                sys.modules["acos_v2_capability"] = replacement
                return self.baseline
            self.baseline_reader.side_effect = changed_baseline
            with mock.patch.object(self.validator, "validate", wraps=self.validator.validate) as validate:
                self.assert_denied()
                validate.assert_not_called()

    def test_validator_callback_module_replacement_cannot_produce_shadow_pass(self):
        replacement = ModuleType("acos_v2_capability")
        replacement.__file__ = capability.__file__
        with mock.patch.dict(sys.modules):
            def changed_clock():
                sys.modules["acos_v2_capability"] = replacement
                return self.now
            self.clock.side_effect = changed_clock
            result = self.assert_denied()
            self.assertTrue(result.baseline_match)


if __name__ == "__main__":
    unittest.main()

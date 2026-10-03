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


class CapabilityTests(unittest.TestCase):
    """C-01--C-30 use explicit in-memory trusted-boundary test doubles only."""

    @classmethod
    def setUpClass(cls):
        global core, capability
        # Reuse Core after discovery, including an existing Core test loader.
        core = load_once("acos_v2_core_substrate", ROOT / "scripts" / "acos-v2-core-substrate.py")
        capability = load_once("acos_v2_capability", ROOT / "scripts" / "acos-v2-capability.py")

    def setUp(self):
        self.baseline = "569470d941a6a34d2dc4ecdb7d0f258a8f10ee0c"
        self.identity = core.ExecutionIdentity(
            "ACOS", "initial-capability", "fixture-task", "fixture-authorization",
            "Codex Executor", "fixture-attempt", self.baseline,
        )
        self.authority = core.AuthorityReference("fixture-authorization", "sha256:" + "1" * 64)
        self.scope = core.WorkflowScope("ACOS", "initial-capability", "fixture-task")
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
        self.grant_reader = mock.Mock(return_value=self.envelope)
        self.state_reader = mock.Mock(return_value=self.state)
        self.clock = mock.Mock(return_value=self.now)
        self.validator = self.make_validator()

    def make_validator(self, **overrides):
        values = dict(trusted_grant_resolver=self.grant_reader,
                      trusted_state_reader=self.state_reader, trusted_clock=self.clock)
        values.update(overrides)
        return capability.CapabilityValidator(**values)

    def validate(self, envelope=None, request=None, validator=None):
        return (validator or self.validator).validate(
            self.envelope if envelope is None else envelope,
            self.request if request is None else request,
        )

    def assert_denied(self, **arguments):
        result = self.validate(**arguments)
        self.assertEqual(result.status, "DENY")
        self.assertFalse(result.execution_authorized)
        self.assertEqual(result.consumption_effect, "NONE")
        return result

    def shadow_copy(self, instance):
        shadow = make_dataclass("Shadow" + type(instance).__name__,
                                [(name, str) for name in instance.__dataclass_fields__], frozen=True)
        return shadow(**asdict(instance))

    def test_c01_canonical_execution_identity_accepted(self):
        self.assertIs(capability.ExecutionIdentity, core.ExecutionIdentity)
        self.assertEqual(self.validate().status, "PASS")

    def test_c02_copied_shadow_identity_type_rejected(self):
        shadow = self.shadow_copy(self.identity)
        for argument in ("envelope", "request"):
            with self.subTest(argument=argument):
                value = replace(getattr(self, argument), execution_identity=shadow)
                self.assert_denied(**{argument: value})
        class IdentitySubclass(core.ExecutionIdentity):
            pass
        self.assert_denied(envelope=replace(
            self.envelope, execution_identity=IdentitySubclass(**asdict(self.identity))))

    def test_c03_canonical_authority_reference_accepted(self):
        self.assertIs(capability.AuthorityReference, core.AuthorityReference)
        self.assertEqual(self.validate().status, "PASS")

    def test_c04_shadow_authority_type_rejected(self):
        shadow = self.shadow_copy(self.authority)
        for argument in ("envelope", "request"):
            with self.subTest(argument=argument):
                value = replace(getattr(self, argument), authority_reference=shadow)
                self.assert_denied(**{argument: value})

    def test_c05_execution_attempt_mismatch_rejected(self):
        wrong = replace(self.identity, execution_attempt_id="different-attempt")
        result = self.assert_denied(request=replace(self.request, execution_identity=wrong))
        self.assertIn("attempt mismatch", result.reason)

    def test_c06_authorization_linkage_mismatch_rejected(self):
        wrong = replace(self.authority, authorization_id="other-authorization")
        result = self.assert_denied(envelope=replace(self.envelope, authority_reference=wrong))
        self.assertEqual(result.reason, "authorization linkage mismatch")
        wrong_digest = replace(self.authority, content_digest="sha256:" + "2" * 64)
        self.assert_denied(request=replace(self.request, authority_reference=wrong_digest))

    def test_c07_baseline_mismatch_rejected(self):
        result = self.assert_denied(request=replace(self.request, baseline_revision="a" * 40))
        self.assertEqual(result.reason, "baseline mismatch")
        wrong_identity = replace(self.identity, baseline_revision="a" * 40)
        self.assert_denied(envelope=replace(self.envelope, execution_identity=wrong_identity))

    def test_c08_scope_mismatch_rejected(self):
        for name in ("project_id", "stage_id", "task_id"):
            with self.subTest(field=name):
                scope = replace(self.scope, **{name: "different"})
                result = self.assert_denied(request=replace(self.request, scope=scope))
                self.assertEqual(result.reason, "scope mismatch")

    def test_c09_capability_class_exact_match_enforcement(self):
        for value in ("git.*", "*", "git.admin", "g", "Git"):
            with self.subTest(value=value):
                self.assert_denied(request=replace(self.request, capability_class=value))
        self.assert_denied(envelope=replace(self.envelope, capability_class="*"))

    def test_c10_operation_exact_match_enforcement(self):
        for value in ("git", "git.*", "git.stage.extra", "GIT.STAGE", "git.stage "):
            with self.subTest(value=value):
                self.assert_denied(request=replace(self.request, operation=value))
        self.assert_denied(envelope=replace(self.envelope, operation="git.*"))

    def test_c11_target_exact_match_enforcement(self):
        for value in ("repo:fixture/*", "repo:fixture", "repo:fixture/exact-path/child",
                      "repo:fixture/./exact-path", "REPO:fixture/exact-path"):
            with self.subTest(value=value):
                self.assert_denied(request=replace(self.request, target=value))
        self.assert_denied(envelope=replace(self.envelope, target="*"))

    def test_c12_git_stage_does_not_imply_git_commit(self):
        self.assertEqual(self.validate().status, "PASS")
        self.assert_denied(request=replace(self.request, operation="git.commit"))

    def test_c13_git_commit_does_not_imply_git_push(self):
        envelope = replace(self.envelope, operation="git.commit")
        self.grant_reader.return_value = envelope
        request = replace(self.request, operation="git.commit")
        self.assertEqual(self.validate(envelope=envelope, request=request).status, "PASS")
        self.assert_denied(envelope=envelope, request=replace(request, operation="git.push"))

    def test_c14_filesystem_read_does_not_imply_filesystem_write(self):
        envelope = replace(self.envelope, capability_class="filesystem", operation="filesystem.read")
        self.grant_reader.return_value = envelope
        request = replace(self.request, capability_class="filesystem", operation="filesystem.read")
        self.assertEqual(self.validate(envelope=envelope, request=request).status, "PASS")
        self.assert_denied(envelope=envelope, request=replace(request, operation="filesystem.write"))

    def test_c15_current_time_before_expiry_accepted(self):
        self.assertLess(self.now, self.envelope.not_after)
        self.assertEqual(self.validate().status, "PASS")
        self.clock.assert_called_once_with()

    def test_c16_current_time_equal_expiry_rejected(self):
        self.clock.return_value = self.envelope.not_after
        self.assertEqual(self.assert_denied().reason, "capability expired")

    def test_c17_current_time_after_expiry_rejected(self):
        self.clock.return_value = self.envelope.not_after + timedelta(microseconds=1)
        self.assertEqual(self.assert_denied().reason, "capability expired")

    def test_c18_missing_or_failing_trusted_clock_rejected(self):
        self.assert_denied(validator=self.make_validator(trusted_clock=None))
        self.clock.side_effect = RuntimeError("clock unavailable")
        self.assert_denied()
        self.clock.side_effect = None
        for value in (None, self.now.replace(tzinfo=None), "2026-10-03", 0):
            with self.subTest(value=value):
                self.clock.return_value = value
                self.assert_denied()

    def test_c19_single_use_consumed_rejected(self):
        self.state_reader.return_value = replace(self.state, consumed=True)
        self.assertEqual(self.assert_denied().reason, "single-use capability already consumed")

    def test_c20_single_use_unconsumed_may_validate(self):
        self.assertEqual(self.envelope.consumption_policy, capability.SINGLE_USE)
        self.assertFalse(self.state.consumed)
        self.assertEqual(self.validate().status, "PASS")

    def test_c21_reusable_requires_explicit_reusable_policy(self):
        self.state_reader.return_value = replace(self.state, consumed=True)
        self.assert_denied()
        for value in (None, "", "reusable", "DEFAULT", True):
            with self.subTest(value=value):
                self.assert_denied(envelope=replace(self.envelope, consumption_policy=value))
        reusable = replace(self.envelope, consumption_policy=capability.REUSABLE)
        self.assert_denied(envelope=reusable)
        self.grant_reader.return_value = reusable
        self.assertEqual(self.validate(envelope=reusable).status, "PASS")

    def test_c22_revoked_rejected(self):
        self.state_reader.return_value = replace(self.state, runtime_state=capability.REVOKED)
        self.assert_denied()

    def test_c23_cancelled_rejected(self):
        self.state_reader.return_value = replace(self.state, runtime_state=capability.CANCELLED)
        self.assert_denied()

    def test_c24_unknown_runtime_state_rejected(self):
        for value in (capability.UNKNOWN, "", "PASS", None, "active"):
            with self.subTest(value=value):
                self.state_reader.return_value = replace(self.state, runtime_state=value)
                self.assert_denied()

    def test_c25_cancellation_state_evidence_binding_mismatch_rejected(self):
        variants = (
            replace(self.state, capability_id="other-capability"),
            replace(self.state, execution_identity=replace(self.identity, execution_attempt_id="other")),
            replace(self.state, authority_reference=replace(self.authority, content_digest="sha256:" + "2" * 64)),
            replace(self.state, cancellation_binding="other-context"),
            replace(self.state, execution_identity=self.shadow_copy(self.identity)),
            replace(self.state, authority_reference=self.shadow_copy(self.authority)),
        )
        for value in variants:
            with self.subTest(value=value):
                self.state_reader.return_value = value
                self.assert_denied()
        self.assert_denied(request=replace(self.request, cancellation_binding="other-context"))

    def test_c26_caller_self_report_cannot_substitute_trusted_state(self):
        self.assert_denied(validator=self.make_validator(trusted_state_reader=None))
        caller_report = {**asdict(self.state), "runtime_state": "ACTIVE", "authenticated": True}
        self.state_reader.return_value = caller_report
        self.assert_denied()
        with self.assertRaises(TypeError):
            self.validator.validate(self.envelope, self.request, state=self.state)

    def test_c27_role_producer_shadow_pass_cannot_create_capability(self):
        for role in ("ChatGPT Review", "User Decision", "Codex Executor"):
            with self.subTest(role=role):
                identity = replace(self.identity, executor_role=role)
                envelope = replace(self.envelope, execution_identity=identity)
                request = replace(self.request, execution_identity=identity)
                self.assert_denied(envelope=envelope, request=request,
                                   validator=self.make_validator(trusted_grant_resolver=None))
        self.grant_reader.return_value = {
            "PRODUCER": "ChatGPT Review", "status": "PASS", "authenticated": True,
            "envelope": self.envelope,
        }
        self.assert_denied()
        with self.assertRaises(TypeError):
            self.validator.validate(self.envelope, self.request, PRODUCER="ChatGPT Review")

    def test_c28_validator_performs_no_journal_mutation(self):
        before = asdict(self.state)
        with mock.patch.object(core.StateStore, "__init__", side_effect=AssertionError("store creation")) as store:
            with mock.patch.object(core.StateJournalWriter, "append", side_effect=AssertionError("journal write")) as append:
                self.assertEqual(self.validate().status, "PASS")
                self.assert_denied(request=replace(self.request, operation="git.push"))
                store.assert_not_called()
                append.assert_not_called()
        self.assertEqual(asdict(self.state), before)

    def test_c29_validator_performs_no_git_network_filesystem_side_effect(self):
        forbidden = (
            (builtins, "open"), (io, "open"), (os, "open"), (os, "system"),
            (os, "remove"), (os, "unlink"), (os, "rename"), (os, "replace"),
            (os, "mkdir"), (os, "rmdir"), (Path, "write_text"), (Path, "write_bytes"),
            (Path, "touch"), (subprocess, "run"), (subprocess, "Popen"),
            (socket, "socket"), (socket, "create_connection"), (core.sqlite3, "connect"),
        )
        with ExitStack() as stack:
            guards = [stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError(name)))
                      for owner, name in forbidden]
            self.assertEqual(self.validate().status, "PASS")
            self.assert_denied(request=replace(self.request, target="other"))
            for guard in guards:
                guard.assert_not_called()

    def test_c30_successful_validation_does_not_consume_capability(self):
        before = (asdict(self.envelope), asdict(self.state))
        for _ in range(2):
            result = self.validate()
            self.assertEqual(result.status, "PASS")
            self.assertEqual(result.consumption_effect, "NONE")
            self.assertEqual(result.reservation_effect, "NONE")
        self.assertEqual((asdict(self.envelope), asdict(self.state)), before)
        self.assertFalse(self.state.consumed)
        self.assertEqual(self.state_reader.call_args_list, [mock.call(self.envelope.capability_id)] * 2)

    def test_api_boundary_validation_result_is_not_execution_authorization(self):
        self.assertEqual([name for name in dir(self.validator)
                          if not name.startswith("_") and callable(getattr(self.validator, name))], ["validate"])
        for result in (self.validate(), self.assert_denied(request=replace(self.request, operation="git.push"))):
            self.assertTrue(result.validation_only)
            self.assertFalse(result.execution_authorized)
            self.assertEqual((result.authority_effect, result.execution_effect,
                              result.consumption_effect, result.reservation_effect), ("NONE",) * 4)
            for name in ("execute", "consume", "reserve", "commit", "dispatch", "adapter", "token"):
                self.assertFalse(hasattr(self.validator, name))
                self.assertFalse(hasattr(result, name))
        with self.assertRaises(FrozenInstanceError):
            self.validate().execution_authorized = True

    def test_candidate_must_match_entire_independent_grant(self):
        for value in (
            replace(self.envelope, capability_id="other"),
            replace(self.envelope, not_after=self.envelope.not_after + timedelta(days=1)),
            replace(self.envelope, consumption_policy=capability.REUSABLE),
        ):
            with self.subTest(value=value):
                self.assertEqual(self.assert_denied(envelope=value).reason,
                                 "candidate does not match the trusted grant")
        self.grant_reader.assert_called_with(self.envelope.capability_id)

    def test_trusted_boundary_failures_deny_without_default_authority(self):
        self.assert_denied(validator=capability.CapabilityValidator())
        for reader in (self.grant_reader, self.state_reader):
            with self.subTest(reader=reader):
                reader.side_effect = RuntimeError("unavailable")
                self.assert_denied()
                reader.side_effect = None
        self.state_reader.return_value = None
        self.assert_denied()

    def test_malformed_metadata_denied(self):
        for value in (
            replace(self.envelope, capability_id=""),
            replace(self.envelope, cancellation_binding=""),
            replace(self.envelope, not_after=self.now.replace(tzinfo=None)),
            replace(self.envelope, authority_reference=replace(self.authority, content_digest="PASS")),
            replace(self.envelope, execution_identity=replace(self.identity, task_id="")),
            replace(self.envelope, execution_identity=replace(self.identity, baseline_revision="HEAD")),
        ):
            with self.subTest(value=value):
                self.assert_denied(envelope=value)
        self.state_reader.return_value = replace(self.state, consumed=0)
        self.assert_denied()
        self.assert_denied(request=replace(self.request, scope=asdict(self.scope)))

    def test_canonical_core_missing_or_replaced_fails_closed(self):
        with mock.patch.dict(sys.modules):
            del sys.modules["acos_v2_core_substrate"]
            self.assert_denied()
        replacement = ModuleType("acos_v2_core_substrate")
        replacement.__file__ = core.__file__
        with mock.patch.dict(sys.modules, {"acos_v2_core_substrate": replacement}):
            self.assert_denied()
        with mock.patch.object(core, "ExecutionIdentity", None):
            self.assert_denied()

    def test_duplicate_core_module_detected_without_loading_second_copy(self):
        duplicate = ModuleType("fixture_duplicate_core")
        duplicate.__file__ = core.__file__
        with mock.patch.dict(sys.modules, {duplicate.__name__: duplicate}):
            self.assert_denied()
        with mock.patch.dict(sys.modules, {"fixture_core_alias": core}):
            self.assertEqual(self.validate().status, "PASS")

    def test_trusted_callback_cannot_replace_canonical_core_mid_validation(self):
        replacement = ModuleType("fixture_replaced_core")
        replacement.__file__ = core.__file__
        with mock.patch.dict(sys.modules):
            def changed_clock():
                sys.modules["acos_v2_core_substrate"] = replacement
                return self.now
            result = self.assert_denied(validator=self.make_validator(trusted_clock=changed_clock))
            self.assertIn("canonical Core", result.reason)


if __name__ == "__main__":
    unittest.main()

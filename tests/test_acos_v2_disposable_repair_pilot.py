"""P-01--P-50: isolated test-harness lifecycle, never production authority.

Only this harness prepares and removes its own freshly created fixture roots.
The pilot receives an already faulted fixture and has no disposal permission.
Reader doubles are independently configured test boundaries, not production
authentication. Failure/outcome doubles never replace a public adapter API.
"""

from contextlib import ExitStack
from dataclasses import FrozenInstanceError, asdict, make_dataclass, replace
from datetime import datetime, timedelta, timezone
import builtins
import importlib.util
import inspect
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
from types import ModuleType
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_once(name, filename):
    path = ROOT / "scripts" / filename
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


core = capability = runner = factory = pilot = None


class DisposableRepairPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global core, capability, runner, factory, pilot
        core = load_once("acos_v2_core_substrate", "acos-v2-core-substrate.py")
        capability = load_once("acos_v2_capability", "acos-v2-capability.py")
        runner = load_once("acos_w3b_b_p1_single_index_repair", "acos-w3b-b-p1-single-index-repair.py")
        factory = runner.factory_module
        pilot = load_once("acos_v2_disposable_repair_pilot", "acos-v2-disposable-repair-pilot.py")

    def setUp(self):
        self.registry = factory.FixtureRegistry()
        self.fixture_factory = factory.DisposableFixtureFactory(self.registry)
        self.handle = self.fixture_factory.create()
        self.owned_root = self.handle.root
        self.owned_root_identity = self.handle.root_identity
        self.addCleanup(self.cleanup_owned_fixture)
        self.assertTrue(factory.SeedInitializer(ROOT).initialize(self.handle, self.registry).commit_proven)
        self.assertTrue(factory.FaultInjector().inject(self.handle, self.registry).commit_proven)
        self.target = pilot.observe_fixture_target(self.handle, self.registry)
        self.before = pilot._snapshot(self.handle, self.registry)
        self.assertFalse(self.before.evidence.index_present)
        self.baseline = "3ecde33763c543630c093ffb75351ff365f966e6"
        self.identity = core.ExecutionIdentity("ACOS", "selected-r1-test", "repair-pilot-test",
                                               "test-repair-authorization", "Codex Executor",
                                               "test-attempt", self.baseline)
        self.authority = core.AuthorityReference("test-repair-authorization", "sha256:" + "1" * 64)
        self.scope = core.WorkflowScope("ACOS", "selected-r1-test", "repair-pilot-test")
        self.now = datetime(2026, 10, 4, tzinfo=timezone.utc)
        self.envelope = capability.CapabilityEnvelope(
            "test-capability", pilot.CAPABILITY_CLASS, pilot.OPERATION, self.target.canonical_target(),
            self.identity, self.authority, self.now + timedelta(seconds=60),
            capability.SINGLE_USE, "test-cancellation-binding")
        self.request = capability.ValidationRequest(pilot.CAPABILITY_CLASS, pilot.OPERATION,
                                                    self.envelope.target, self.identity, self.authority,
                                                    self.scope, self.baseline, self.envelope.cancellation_binding)
        self.state = capability.CapabilityStateEvidence(self.envelope.capability_id, self.identity,
                                                       self.authority, self.envelope.cancellation_binding,
                                                       capability.ACTIVE, False)
        self.grant_reader = mock.Mock(return_value=self.envelope)
        self.state_reader = mock.Mock(return_value=self.state)
        self.clock = mock.Mock(return_value=self.now)
        self.baseline_reader = mock.Mock(return_value=self.baseline)
        self.target_reader = mock.Mock(return_value=self.target)
        self.validator = self.make_validator()
        self.instance = self.make_pilot()

    def cleanup_owned_fixture(self):
        # Separate harness lifecycle permission: never call pilot cleanup.
        if self.owned_root.exists():
            observed = factory.FileIdentity.from_stat(self.owned_root.lstat())
            self.assertEqual(observed, self.owned_root_identity)
            shutil.rmtree(self.owned_root)

    def make_validator(self, **overrides):
        values = dict(trusted_grant_resolver=self.grant_reader, trusted_state_reader=self.state_reader,
                      trusted_clock=self.clock)
        values.update(overrides)
        return capability.CapabilityValidator(**values)

    def make_pilot(self, **overrides):
        values = dict(registry=self.registry, validator=self.validator,
                      trusted_current_baseline_reader=self.baseline_reader,
                      trusted_target_observer=self.target_reader)
        values.update(overrides)
        return pilot.DisposableRepairPilot(**values)

    def execute(self, **overrides):
        values = dict(envelope=self.envelope, request=self.request, handle=self.handle)
        values.update(overrides)
        return self.instance.execute(**values)

    def assert_denied(self, *, expected_outcome=None, **overrides):
        before = factory.fixture_byte_digest(self.handle, self.registry)[0]
        with mock.patch.object(pilot, "_invoke_repair", side_effect=AssertionError("repair before admission")) as invocation:
            result = self.execute(**overrides)
            invocation.assert_not_called()
        self.assertEqual(result.status, "DENY")
        self.assertFalse(result.pilot_admitted)
        self.assertEqual(result.transition_outcome, pilot.NOT_COMMITTED if expected_outcome is None else expected_outcome)
        self.assertEqual(factory.fixture_byte_digest(self.handle, self.registry)[0], before)
        self.assertFalse(pilot._snapshot(self.handle, self.registry).evidence.index_present)
        return result

    def assert_committed(self):
        result = self.execute()
        self.assertEqual(result.status, "PASS", result.reason)
        self.assertTrue(result.pilot_admitted)
        self.assertEqual(result.transition_outcome, pilot.COMMITTED)
        current = self.registry.get(self.handle.fixture_instance_id)
        self.assertEqual(current.lifecycle_state, factory.STATE_VERIFYING)
        self.assertFalse(current.reusable)
        self.assertEqual(current.mutation_attempt_count, 1)
        return result, pilot._snapshot(current, self.registry)

    def use_target(self, **changes):
        target = replace(self.target, **changes)
        self.target_reader.return_value = target
        self.envelope = replace(self.envelope, target=target.canonical_target())
        self.request = replace(self.request, target=self.envelope.target)
        self.grant_reader.return_value = self.envelope

    def copied_type(self, value):
        copied = make_dataclass("Copied" + type(value).__name__,
                                [(name, str) for name in value.__dataclass_fields__], frozen=True)
        return copied(**asdict(value))

    def writer_outcome(self, **changes):
        values = dict(profile=factory.PROFILE_REPAIR, mutation_attempted=True, rollback_proven=False,
                      commit_proven=False, outcome_uncertain=False, callbacks=())
        values.update(changes)
        return factory.WriterOutcome(**values)

    def test_p01_canonical_modules_required(self):
        with mock.patch.dict(sys.modules, {"acos_v2_capability": ModuleType("foreign")}):
            self.assert_denied()
        self.assertTrue(pilot._canonical_intact())

    def test_p02_canonical_identity_and_authority_required(self):
        for field in ("execution_identity", "authority_reference"):
            with self.subTest(field=field):
                self.instance = self.make_pilot()
                self.assert_denied(request=replace(self.request, **{field: self.copied_type(getattr(self.request, field))}))

    def test_p03_canonical_envelope_required(self):
        self.assertIs(pilot._Envelope, capability.CapabilityEnvelope)
        self.assert_denied(envelope=self.copied_type(self.envelope))

    def test_p04_canonical_request_required(self):
        self.assertIs(pilot._Request, capability.ValidationRequest)
        self.assert_denied(request=self.copied_type(self.request))

    def test_p05_missing_baseline_observation_denies(self):
        self.instance = self.make_pilot(trusted_current_baseline_reader=None)
        self.assert_denied()
        self.target_reader.assert_not_called()

    def test_p06_baseline_reader_exception_denies(self):
        self.baseline_reader.side_effect = RuntimeError("unavailable")
        self.assert_denied()
        self.target_reader.assert_not_called()

    def test_p07_baseline_mismatch_denies_before_mutation(self):
        self.baseline_reader.return_value = "a" * 40
        self.assert_denied()
        self.grant_reader.assert_not_called()

    def test_p08_missing_target_observation_denies(self):
        self.instance = self.make_pilot(trusted_target_observer=None)
        self.assert_denied()

    def test_p09_target_observer_exception_denies(self):
        self.target_reader.side_effect = RuntimeError("unavailable")
        self.assert_denied()

    def test_p10_fixture_uuid_mismatch_denies(self):
        self.use_target(fixture_uuid="11111111-1111-4111-8111-111111111111")
        self.assert_denied()

    def test_p11_path_mismatch_denies(self):
        self.use_target(database_path=str(self.handle.root / "different.sqlite3"))
        self.assert_denied()

    def test_p12_device_mismatch_denies(self):
        self.use_target(device_id=self.target.device_id + 1)
        self.assert_denied()

    def test_p13_inode_mismatch_denies(self):
        self.use_target(inode=self.target.inode + 1)
        self.assert_denied()

    def test_p14_generation_mismatch_denies(self):
        self.use_target(fixture_generation=self.target.fixture_generation + 1)
        self.assert_denied()

    def test_p15_prestate_digest_mismatch_denies(self):
        self.use_target(prestate_digest="sha256:" + "2" * 64)
        self.assert_denied()

    def test_p16_sql_digest_mismatch_denies(self):
        self.use_target(fixed_sql_digest="sha256:" + "3" * 64)
        self.assert_denied()

    def test_p17_capability_exact_target_mismatch_denies(self):
        self.assert_denied(envelope=replace(self.envelope, target="other-exact-target"))

    def test_p18_arbitrary_sql_impossible(self):
        self.assertNotIn("sql", inspect.signature(self.instance.execute).parameters)
        with self.assertRaises(TypeError):
            self.instance.execute(self.envelope, self.request, self.handle, sql="DELETE FROM audit_events")
        self.assertFalse(pilot._snapshot(self.handle, self.registry).evidence.index_present)

    def test_p19_drop_index_impossible(self):
        self.assert_denied(request=replace(self.request, operation="DROP INDEX idx_audit_events_aggregate"))

    def test_p20_reindex_impossible(self):
        self.assert_denied(request=replace(self.request, operation="REINDEX main.idx_audit_events_aggregate"))

    def test_p21_seed_fault_operation_impossible(self):
        for operation in (factory.PROFILE_SEED, factory.PROFILE_FAULT):
            with self.subTest(operation=operation):
                self.instance = self.make_pilot()
                self.assert_denied(request=replace(self.request, operation=operation))

    def test_p22_missing_capability_grant_denies(self):
        self.grant_reader.return_value = None
        self.assert_denied()
        self.assertEqual(self.instance.claim_state, "FINISHED")

    def test_p23_expired_capability_denies(self):
        self.clock.return_value = self.envelope.not_after
        self.assert_denied()

    def test_p24_cancelled_capability_denies(self):
        self.state_reader.return_value = replace(self.state, runtime_state=capability.CANCELLED)
        self.assert_denied()

    def test_p25_revoked_capability_denies(self):
        self.state_reader.return_value = replace(self.state, runtime_state=capability.REVOKED)
        self.assert_denied()

    def test_p26_unknown_capability_state_denies(self):
        self.state_reader.return_value = replace(self.state, runtime_state=capability.UNKNOWN)
        self.assert_denied()

    def test_p27_capability_deny_no_repair_invocation(self):
        self.state_reader.return_value = replace(self.state, consumed=True)
        self.assert_denied()
        self.assertEqual(self.registry.get(self.handle.fixture_instance_id).lifecycle_state, factory.STATE_READY)

    def test_p28_successful_final_validation_reaches_admission(self):
        result, after = self.assert_committed()
        self.assertTrue(after.evidence.index_present)
        self.assertTrue(result.pilot_admitted)
        self.baseline_reader.assert_called_once_with()
        self.target_reader.assert_called_once_with(self.handle)
        self.grant_reader.assert_called_once_with(self.envelope.capability_id)
        self.state_reader.assert_called_once_with(self.envelope.capability_id)

    def test_p29_admission_creates_no_governance_authority(self):
        result, _ = self.assert_committed()
        self.assertFalse(result.governance_authority)
        self.assertFalse(result.capability_issued)
        self.assertFalse(result.general_execution_permission)
        self.assertEqual(result.authority_effect, "NONE")

    def test_p30_one_attempt_claim_only(self):
        def clock_at_claim():
            self.assertEqual(self.instance.claim_state, "CLAIMED")
            return self.now
        self.clock.side_effect = clock_at_claim
        self.assert_committed()
        self.assertEqual(self.instance.claim_state, "FINISHED")
        self.assertEqual(self.execute().status, "DENY")

    def test_p31_sequential_duplicate_denied(self):
        with mock.patch.object(pilot, "_invoke_repair", wraps=pilot._invoke_repair) as invocation:
            self.assert_committed()
            result = self.execute()
            self.assertEqual(result.status, "DENY")
            self.assertFalse(result.pilot_admitted)
            self.assertEqual(result.transition_outcome, pilot.UNRESOLVED)
            self.assertEqual(invocation.call_count, 1)

    def test_p32_concurrent_duplicate_at_most_one_invocation(self):
        entered, release = threading.Event(), threading.Event()
        results = []
        errors = []
        def blocked_clock():
            entered.set()
            if not release.wait(10):
                raise RuntimeError("test synchronization timeout")
            return self.now
        def execute():
            try:
                results.append(self.execute())
            except BaseException as exc:
                errors.append(exc)
        self.clock.side_effect = blocked_clock
        with mock.patch.object(pilot, "_invoke_repair", wraps=pilot._invoke_repair) as invocation:
            first, second = threading.Thread(target=execute), threading.Thread(target=execute)
            first.start()
            try:
                self.assertTrue(entered.wait(10))
                second.start()
                second.join(10)
                self.assertFalse(second.is_alive())
            finally:
                release.set()
                first.join(10)
                if second.ident is not None:
                    second.join(10)
            self.assertFalse(first.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(sorted(result.status for result in results), ["DENY", "PASS"])
            self.assertEqual(invocation.call_count, 1)

    def test_p33_failure_does_not_reopen_claim(self):
        with mock.patch.object(pilot, "_invoke_repair", return_value=self.writer_outcome(rollback_proven=True)) as invocation:
            result = self.execute()
            self.assertEqual(result.transition_outcome, pilot.NOT_COMMITTED)
            self.assertEqual(result.fixture_state, factory.STATE_QUARANTINED)
            self.assertEqual(self.execute().status, "DENY")
            self.assertEqual(invocation.call_count, 1)
        self.assertEqual(self.instance.claim_state, "FINISHED")

    def test_p34_unresolved_does_not_reopen_claim(self):
        with mock.patch.object(pilot, "_invoke_repair", return_value=self.writer_outcome(outcome_uncertain=True)) as invocation:
            self.assertEqual(self.execute().transition_outcome, pilot.UNRESOLVED)
            self.assertEqual(self.execute().status, "DENY")
            self.assertEqual(invocation.call_count, 1)

    def test_p35_committed_requires_independent_evidence(self):
        outcome = self.writer_outcome(commit_proven=True, callbacks=(runner.mutator_module._REPAIR_REINDEX_CALLBACK,))
        self.assertEqual(pilot.classify_outcome(outcome, self.before, self.before), pilot.UNRESOLVED)
        _, after = self.assert_committed()
        self.assertEqual(pilot.classify_outcome(outcome, self.before, after), pilot.COMMITTED)
        self.assertEqual(pilot.classify_outcome(replace(outcome, callbacks=()), self.before, after), pilot.UNRESOLVED)
        self.assertEqual(pilot.classify_outcome(replace(outcome, security_lifecycle_failure="authorizer_removal"),
                                              self.before, after), pilot.UNRESOLVED)

    def test_p36_not_committed_requires_rollback_and_unchanged_evidence(self):
        outcome = self.writer_outcome(rollback_proven=True)
        self.assertEqual(pilot.classify_outcome(outcome, self.before, self.before), pilot.NOT_COMMITTED)
        self.assertEqual(pilot.classify_outcome(replace(outcome, rollback_proven=False),
                                              self.before, self.before), pilot.UNRESOLVED)
        changed = replace(self.before, byte_digest="sha256:" + "f" * 64)
        self.assertEqual(pilot.classify_outcome(outcome, self.before, changed), pilot.UNRESOLVED)

    def test_p37_exception_alone_cannot_imply_not_committed(self):
        with mock.patch.object(pilot, "_invoke_repair", side_effect=RuntimeError("lost acknowledgement")):
            result = self.execute()
        self.assertEqual(result.transition_outcome, pilot.UNRESOLVED)
        self.assertEqual(result.fixture_state, factory.STATE_QUARANTINED)
        self.assertTrue(self.handle.database.exists())

    def test_p38_uncertain_effect_unresolved_even_if_index_exists(self):
        canonical = pilot._invoke_repair
        def uncertain(handle, registry):
            return replace(canonical(handle, registry), outcome_uncertain=True)
        with mock.patch.object(pilot, "_invoke_repair", side_effect=uncertain):
            result = self.execute()
        self.assertEqual(result.transition_outcome, pilot.UNRESOLVED)
        self.assertEqual(result.fixture_state, factory.STATE_QUARANTINED)
        current = self.registry.get(self.handle.fixture_instance_id)
        self.assertTrue(pilot._snapshot(current, self.registry).evidence.index_present)

    def test_p39_unresolved_does_not_cleanup_fixture(self):
        with mock.patch.object(pilot, "_invoke_repair", return_value=self.writer_outcome(outcome_uncertain=True)), \
                mock.patch.object(factory.DisposableFixtureFactory, "dispose", side_effect=AssertionError("disposal")) as dispose:
            result = self.execute()
            self.assertEqual(result.transition_outcome, pilot.UNRESOLVED)
            dispose.assert_not_called()
        self.assertTrue(self.handle.root.exists())
        self.assertTrue(self.handle.database.exists())

    def test_p40_unresolved_does_not_retry(self):
        with mock.patch.object(pilot, "_invoke_repair", side_effect=RuntimeError("unknown")) as invocation:
            self.assertEqual(self.execute().transition_outcome, pilot.UNRESOLVED)
            self.assertEqual(self.execute().status, "DENY")
            self.assertEqual(invocation.call_count, 1)

    def test_p41_pilot_never_creates_seeds_or_faults_fixture(self):
        with ExitStack() as stack:
            guards = [stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError(name)))
                      for owner, name in ((factory.DisposableFixtureFactory, "create"),
                                          (factory.SeedInitializer, "initialize"), (factory.FaultInjector, "inject"))]
            self.assert_committed()
            for guard in guards:
                guard.assert_not_called()

    def test_p42_pilot_never_disposes_fixture(self):
        with mock.patch.object(factory.DisposableFixtureFactory, "dispose", side_effect=AssertionError("dispose")) as dispose:
            self.assert_committed()
            dispose.assert_not_called()
        self.assertTrue(self.handle.database.exists())

    def test_p43_no_git_invocation(self):
        # Preserve canonical preflight's read-only host fingerprinting; deny Git.
        original = subprocess.Popen
        def guarded(command, *args, **kwargs):
            parts = command if isinstance(command, (tuple, list)) else str(command).split()
            if any(Path(str(part)).name == "git" for part in parts):
                raise AssertionError("Git invocation")
            return original(command, *args, **kwargs)
        with mock.patch.object(subprocess, "Popen", side_effect=guarded) as calls:
            self.assert_committed()
        for call in calls.call_args_list:
            parts = call.args[0] if isinstance(call.args[0], (tuple, list)) else str(call.args[0]).split()
            self.assertNotIn("git", [Path(str(part)).name for part in parts])

    def test_p44_no_network_invocation(self):
        with mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network")) as connect, \
                mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")) as create:
            self.assert_committed()
            connect.assert_not_called()
            create.assert_not_called()

    def test_p45_no_unrelated_filesystem_mutation(self):
        original_open = builtins.open
        def read_only_open(file, mode="r", *args, **kwargs):
            if any(flag in mode for flag in "wax+"):
                raise AssertionError("unrelated filesystem write")
            return original_open(file, mode, *args, **kwargs)
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(builtins, "open", side_effect=read_only_open))
            guards = [stack.enter_context(mock.patch.object(owner, name, side_effect=AssertionError(name)))
                      for owner, name in ((os, "mkdir"), (os, "unlink"), (os, "remove"), (os, "rmdir"),
                                          (Path, "write_text"), (Path, "write_bytes"), (Path, "touch"))]
            self.assert_committed()
            for guard in guards:
                guard.assert_not_called()

    def test_p46_no_core_journal_append(self):
        with mock.patch.object(core.StateJournalWriter, "append", side_effect=AssertionError("journal")) as append:
            self.assert_committed()
            append.assert_not_called()

    def test_p47_success_affects_only_exact_fixed_index(self):
        _, after = self.assert_committed()
        added = tuple(row for row in after.schema_rows if row not in self.before.schema_rows)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0][:3], ("index", "idx_audit_events_aggregate", "audit_events"))
        self.assertTrue(runner.verifier_module.validate_expected_index_sql(added[0][3]))
        self.assertEqual(tuple(row for row in after.schema_rows if row not in added), self.before.schema_rows)
        self.assertEqual(after.evidence.audit_events_digest, self.before.evidence.audit_events_digest)
        self.assertEqual(after.evidence.user_version, self.before.evidence.user_version)

    def test_p48_no_arbitrary_adapter_dispatch(self):
        self.assertNotIn("adapter", inspect.signature(pilot.DisposableRepairPilot).parameters)
        self.assertNotIn("adapter", inspect.signature(self.instance.execute).parameters)
        injected = mock.Mock(side_effect=AssertionError("arbitrary adapter"))
        with self.assertRaises(TypeError):
            pilot.DisposableRepairPilot(adapter=injected)
        injected.assert_not_called()

    def test_p49_capability_validation_result_remains_non_authorizing(self):
        validation = self.validator.validate(self.envelope, self.request)
        self.assertEqual(validation.status, "PASS")
        self.assertTrue(validation.validation_only)
        self.assertFalse(validation.execution_authorized)
        self.assertEqual((validation.authority_effect, validation.execution_effect,
                          validation.consumption_effect, validation.reservation_effect), ("NONE",) * 4)

    def test_p50_full_path_mediation_explicitly_false(self):
        self.assertFalse(pilot.FULL_PATH_MEDIATION)
        result, _ = self.assert_committed()
        self.assertFalse(result.full_path_mediation)
        self.assertFalse(result.durable_consumption)
        self.assertFalse(result.cross_process_replay_protection)
        self.assertFalse(result.restart_resume_supported)

    def test_target_is_frozen_and_encoding_is_deterministic(self):
        equivalent = pilot.PilotTargetDescriptor(**asdict(self.target))
        self.assertEqual(equivalent.canonical_target(), self.target.canonical_target())
        self.assertTrue(self.target.canonical_target().startswith("acos-v2-disposable-repair/1:sha256:"))
        self.assertEqual(len(self.target.canonical_target().rsplit(":", 1)[1]), 64)
        with self.assertRaises(FrozenInstanceError):
            self.target.inode = 0

    def test_invalid_target_uuid_path_and_integer_types_deny(self):
        changes = (dict(fixture_uuid="not-a-uuid"), dict(database_path="relative.db"),
                   dict(database_path=str(self.handle.root) + "/*"), dict(inode=True),
                   dict(device_id=-1), dict(fixture_generation=True))
        for change in changes:
            with self.subTest(change=change):
                self.instance = self.make_pilot()
                self.target_reader.return_value = replace(self.target, **change)
                self.assert_denied()

    def test_module_duplicate_denies(self):
        duplicate = ModuleType("duplicate")
        duplicate.__file__ = capability.__file__
        with mock.patch.dict(sys.modules, {"pilot_test_duplicate": duplicate}):
            self.assert_denied()

    def test_repair_method_replacement_denies(self):
        with mock.patch.object(factory.RepairMutator, "execute", side_effect=AssertionError("foreign writer")) as foreign:
            self.assert_denied()
            foreign.assert_not_called()

    def test_missing_trusted_state_or_clock_denies(self):
        for field in ("trusted_state_reader", "trusted_clock", "trusted_grant_resolver"):
            with self.subTest(field=field):
                self.instance = self.make_pilot(validator=self.make_validator(**{field: None}))
                self.assert_denied()

    def test_target_observation_is_not_grant_authority(self):
        self.grant_reader.return_value = None
        result = self.assert_denied()
        self.assertFalse(result.governance_authority)
        self.target_reader.assert_called_once_with(self.handle)

    def test_failure_before_claim_still_closes_instance(self):
        self.baseline_reader.return_value = "a" * 40
        self.assert_denied()
        self.baseline_reader.return_value = self.baseline
        self.assert_denied(expected_outcome=pilot.UNRESOLVED)
        self.assertEqual(self.baseline_reader.call_count, 1)

    def test_post_admission_cancellation_does_not_claim_instant_revocation(self):
        canonical = pilot._invoke_repair
        def cancellation_after_admission(handle, registry):
            self.assertEqual(handle.lifecycle_state, factory.STATE_MUTATION_ATTEMPTED)
            self.assertEqual(self.instance.claim_state, "CLAIMED")
            self.state_reader.return_value = replace(self.state, runtime_state=capability.CANCELLED)
            return canonical(handle, registry)
        with mock.patch.object(pilot, "_invoke_repair", side_effect=cancellation_after_admission):
            result, _ = self.assert_committed()
        self.assertTrue(result.pilot_admitted)
        self.state_reader.assert_called_once_with(self.envelope.capability_id)
        self.assertFalse(result.durable_consumption)

    def test_contract_rejects_reusable_capability(self):
        self.assert_denied(envelope=replace(self.envelope, consumption_policy=capability.REUSABLE))

    def test_real_deny_preserves_absent_index_and_fixture(self):
        self.state_reader.return_value = replace(self.state, runtime_state=capability.CANCELLED)
        result = self.assert_denied()
        self.assertEqual(result.fixture_disposition, "PRESERVE_FOR_EXTERNAL_LIFECYCLE")
        self.assertTrue(self.handle.root.exists())
        self.assertTrue(self.handle.database.exists())

    def test_commit_classification_rejects_other_schema_or_audit_changes(self):
        _, after = self.assert_committed()
        outcome = self.writer_outcome(commit_proven=True, callbacks=(runner.mutator_module._REPAIR_REINDEX_CALLBACK,))
        extra_schema = replace(after, schema_rows=after.schema_rows + (("table", "other", "other", "CREATE TABLE other(x)"),))
        changed_audit = replace(after, evidence=replace(after.evidence, audit_events_digest="sha256:" + "e" * 64))
        for snapshot in (extra_schema, changed_audit):
            with self.subTest(snapshot=snapshot):
                self.assertEqual(pilot.classify_outcome(outcome, self.before, snapshot), pilot.UNRESOLVED)

    def test_every_target_binding_field_changes_canonical_target(self):
        changes = (dict(fixture_uuid="22222222-2222-4222-8222-222222222222"),
                   dict(database_path=str(self.handle.root / "other.sqlite3")),
                   dict(device_id=self.target.device_id + 1), dict(inode=self.target.inode + 1),
                   dict(fixture_generation=self.target.fixture_generation + 1),
                   dict(prestate_digest="sha256:" + "b" * 64), dict(fixed_sql_digest="sha256:" + "c" * 64))
        for change in changes:
            with self.subTest(change=change):
                self.assertNotEqual(replace(self.target, **change).canonical_target(), self.target.canonical_target())


if __name__ == "__main__":
    unittest.main()

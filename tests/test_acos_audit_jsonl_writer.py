from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "acos-audit-jsonl-writer.py"
FIXTURES = ROOT / "fixtures" / "audit-jsonl"
SPEC = importlib.util.spec_from_file_location("acos_audit_jsonl_writer", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def event_for(event_type: str, sequence: int = 1) -> dict[str, object]:
    policy: dict[str, tuple[str, str, str | None]] = {
        "task_created": ("ChatGPT Review Runtime", "ChatGPT", "TASK"),
        "result_received": ("Codex Executor Runtime", "Codex Executor", "RESULT"),
        "blocked_result_received": (
            "Codex Executor Runtime",
            "Codex Executor",
            "BLOCKED RESULT",
        ),
        "review_completed": ("ChatGPT Review Runtime", "ChatGPT Review", "REVIEW"),
        "advisory_requested": (
            "ChatGPT Review Runtime",
            "ChatGPT Review",
            "ADVISORY REVIEW REQUEST",
        ),
        "advisory_review_received": (
            "External Advisory Runtime",
            "External Advisory Reviewer",
            "ADVISORY REVIEW",
        ),
        "decision_issued": ("ChatGPT Review Runtime", "ChatGPT Review", "DECISION"),
        "operation_requested": ("Codex Executor Runtime", "Codex Executor", "RESULT"),
        "operation_authorized": (
            "ChatGPT Review Runtime",
            "ChatGPT Review",
            "DECISION",
        ),
        "operation_denied": ("Automation Runtime", "Automation", "RECORD"),
        "operation_blocked": ("Automation Runtime", "Automation", "RECORD"),
        "operation_completed": ("Codex Executor Runtime", "Codex Executor", "RESULT"),
        "commit_created": ("Codex Executor Runtime", "Codex Executor", "RESULT"),
        "push_completed": ("Codex Executor Runtime", "Codex Executor", "RESULT"),
        "release_completed": ("Codex Executor Runtime", "Codex Executor", "RESULT"),
        "policy_violation_detected": ("Automation Runtime", "Automation", "RECORD"),
        "validation_completed": ("Automation Runtime", "Automation", "RECORD"),
        "task_closed": ("ChatGPT Review Runtime", "ChatGPT Review", "DECISION"),
    }
    runtime, producer, artifact_type = policy[event_type]
    event: dict[str, object] = {
        "schema_version": "1.0",
        "event_id": f"evt-{event_type}",
        "sequence": sequence,
        "timestamp": f"2026-07-11T05:{sequence:02d}:00Z",
        "event_type": event_type,
        "project": "ACOS",
        "task_id": "TASK_054",
        "producer": producer,
        "runtime_identity": runtime,
        "artifact_type": artifact_type,
        "status": "completed",
        "details": {},
    }
    if event_type.startswith("operation_"):
        event["operation"] = "fixture check"
    if event_type == "operation_authorized":
        event["authorization_id"] = "DEC-054"
        event["authorization_source"] = "ChatGPT Review DECISION"
    if event_type in {"commit_created", "push_completed", "release_completed"}:
        event["commit_hash"] = "abc1234"
    if event_type == "push_completed":
        event["remote"] = "origin/master"
    if event_type == "release_completed":
        event["target"] = "v2-shadow"
    return event


def fixture(events: list[dict[str, object]], mode: str = "generate") -> dict[str, object]:
    return {
        "case_id": "memory-case",
        "mode": mode,
        "events": events,
        "expected_result": audit.PASS,
    }


class AuditJsonlWriterTests(unittest.TestCase):
    def test_all_required_event_types_pass_with_authorized_runtime(self) -> None:
        self.assertEqual(len(audit.EVENT_TYPES), 18)
        for event_type in sorted(audit.EVENT_TYPES):
            with self.subTest(event_type=event_type):
                result = audit.evaluate_fixture(fixture([event_for(event_type)]))
                self.assertEqual(result.result, audit.PASS, result.reason)

    def test_runtime_and_producer_binding_fail_closed(self) -> None:
        wrong_producer = event_for("result_received")
        wrong_producer["producer"] = "Automation"
        self.assertEqual(
            audit.evaluate_fixture(fixture([wrong_producer])).result,
            audit.DENY,
        )
        wrong_runtime = event_for("decision_issued")
        wrong_runtime["runtime_identity"] = "Codex Executor Runtime"
        wrong_runtime["producer"] = "Codex Executor"
        self.assertEqual(
            audit.evaluate_fixture(fixture([wrong_runtime])).result,
            audit.DENY,
        )

    def test_deterministic_event_id(self) -> None:
        raw = event_for("task_created")
        raw.pop("event_id")
        case = fixture([raw])
        case["auto_event_id"] = True
        first = audit.evaluate_fixture(case)
        second = audit.evaluate_fixture(case)
        self.assertEqual(first.result, audit.PASS)
        self.assertEqual(first.event["event_id"], second.event["event_id"])
        self.assertTrue(first.event["event_id"].startswith("evt-"))

    def test_canonical_hash_is_deterministic_and_includes_previous_hash(self) -> None:
        result = audit.evaluate_fixture(fixture([event_for("task_created")]))
        self.assertEqual(result.result, audit.PASS)
        event = result.event
        self.assertEqual(audit.calculate_event_hash(event), event["event_hash"])
        self.assertEqual(audit.calculate_event_hash(event), audit.calculate_event_hash(event))
        changed = dict(event)
        changed["previous_event_hash"] = "0" * 64
        self.assertNotEqual(audit.calculate_event_hash(event), audit.calculate_event_hash(changed))

    def test_canonical_json_unicode_and_key_order(self) -> None:
        left = {"z": "中文", "a": {"b": 2, "a": 1}}
        right = {"a": {"a": 1, "b": 2}, "z": "中文"}
        self.assertEqual(audit.canonical_json(left), audit.canonical_json(right))
        self.assertIn("中文", audit.canonical_json(left))
        self.assertNotIn("\\u", audit.canonical_json(left))

    def test_sequence_continuity_and_previous_hash_linkage(self) -> None:
        result = audit.evaluate_fixture(
            fixture([event_for("task_created", 1), event_for("result_received", 2)])
        )
        self.assertEqual(result.result, audit.PASS)
        self.assertIsNone(result.events[0]["previous_event_hash"])
        self.assertEqual(
            result.events[1]["previous_event_hash"], result.events[0]["event_hash"]
        )

    def test_duplicate_id_sequence_gap_and_regression_are_denied(self) -> None:
        for name in (
            "invalid-duplicate-event-id.json",
            "invalid-duplicate-sequence.json",
            "invalid-sequence-gap.json",
            "invalid-sequence-regression.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(audit.load_fixture(FIXTURES / name).result, audit.DENY)

    def test_tamper_payload_hash_link_and_structure_are_denied(self) -> None:
        names = (
            "invalid-payload-old-hash.json",
            "invalid-event-hash-replaced.json",
            "invalid-previous-hash-replaced.json",
            "invalid-middle-event-deleted.json",
            "invalid-middle-event-inserted.json",
            "invalid-event-order-rearranged.json",
            "invalid-timestamp-modified.json",
            "invalid-details-modified.json",
            "invalid-genesis-replaced.json",
        )
        for name in names:
            with self.subTest(name=name):
                result = audit.load_fixture(FIXTURES / name)
                self.assertEqual(result.result, audit.DENY)
                self.assertTrue(result.tamper_detected)

    def test_unknown_hash_algorithm_is_denied(self) -> None:
        result = audit.load_fixture(FIXTURES / "invalid-unknown-hash-algorithm.json")
        self.assertEqual(result.result, audit.DENY)
        self.assertIn("unknown hash algorithm", result.reason)

    def test_missing_unknown_and_wrong_types_are_blocked(self) -> None:
        names = (
            "blocked-missing-schema-version.json",
            "blocked-missing-event-id.json",
            "blocked-missing-sequence.json",
            "blocked-missing-timestamp.json",
            "blocked-missing-event-type.json",
            "blocked-missing-producer.json",
            "blocked-missing-runtime-identity.json",
            "blocked-sequence-string.json",
            "blocked-sequence-bool.json",
            "blocked-timestamp-number.json",
            "blocked-invalid-timestamp.json",
            "blocked-unknown-event-type.json",
            "blocked-unknown-runtime.json",
            "blocked-artifact-type-number.json",
            "blocked-details-array.json",
            "blocked-previous-hash-number.json",
            "blocked-event-hash-number.json",
            "blocked-event-hash-format.json",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(audit.load_fixture(FIXTURES / name).result, audit.BLOCKED)

    def test_malformed_json_root_and_jsonl_are_blocked(self) -> None:
        for name in (
            "blocked-malformed-json.json",
            "blocked-root-array.json",
            "blocked-malformed-line.jsonl",
            "blocked-explanatory-text.jsonl",
        ):
            with self.subTest(name=name):
                self.assertEqual(audit.load_fixture(FIXTURES / name).result, audit.BLOCKED)

    def test_jsonl_output_is_one_object_per_line_with_trailing_newline(self) -> None:
        result = audit.load_fixture(FIXTURES / "valid-two-event-chain.json")
        output = audit.events_to_jsonl(result.events)
        self.assertTrue(output.endswith("\n"))
        lines = output.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(isinstance(json.loads(line), dict) for line in lines))
        self.assertNotIn("\n ", output)

    def test_static_jsonl_chain_verifies(self) -> None:
        result = audit.load_fixture(FIXTURES / "valid-two-event-chain.jsonl")
        self.assertEqual(result.result, audit.PASS, result.reason)
        self.assertEqual(result.event_count, 2)

    def test_roundtrip_is_repeatable(self) -> None:
        first = audit.load_fixture(FIXTURES / "valid-canonical-unicode-roundtrip.json")
        second = audit.load_fixture(FIXTURES / "valid-canonical-unicode-roundtrip.json")
        self.assertEqual(audit.events_to_jsonl(first.events), audit.events_to_jsonl(second.events))

    def test_audit_record_never_grants_authorization(self) -> None:
        names = (
            "invalid-audit-as-commit-authorization.json",
            "invalid-commit-as-push-authorization.json",
            "invalid-push-as-release-authorization.json",
            "invalid-advisory-as-operation-authorization.json",
        )
        for name in names:
            with self.subTest(name=name):
                result = audit.load_fixture(FIXTURES / name)
                self.assertEqual(result.result, audit.DENY)
                self.assertIn("cannot be treated", result.reason)

    def test_role_authority_violations_are_denied(self) -> None:
        for name in (
            "invalid-external-advisory-authorization-event.json",
            "invalid-automation-decision-event.json",
            "invalid-codex-decision-event.json",
            "invalid-event-runtime-mismatch.json",
        ):
            with self.subTest(name=name):
                self.assertEqual(audit.load_fixture(FIXTURES / name).result, audit.DENY)

    def test_text_json_and_jsonl_cli_formats(self) -> None:
        for output_format, expected_fragment in (
            ("text", "SUMMARY:"),
            ("json", '"case_id"'),
            ("jsonl", '"event_hash"'),
        ):
            args = [str(FIXTURES / "valid-two-event-chain.json")]
            if output_format != "text":
                args[:0] = ["--format", output_format]
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                code = audit.main(args)
            self.assertEqual(code, 0)
            self.assertIn(expected_fragment, stream.getvalue())

    def test_single_fixture_and_directory_cli_exit_codes(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main([str(FIXTURES / "valid-genesis-event.json")]), 0)
            self.assertEqual(audit.main([str(FIXTURES)]), 0)

    def test_expectation_mismatch_returns_nonzero(self) -> None:
        data = json.loads((FIXTURES / "valid-genesis-event.json").read_text(encoding="utf-8"))
        data["expected_result"] = "DENY"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mismatch.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(audit.main([str(path)]), 1)

    def test_missing_path_returns_nonzero(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(audit.main(["/private/tmp/acos-no-such-fixture.json"]), 1)

    def test_every_repository_fixture_matches_expected_result(self) -> None:
        paths, errors = audit.discover_paths([str(FIXTURES)])
        self.assertFalse(errors)
        results = [audit.load_fixture(path) for path in paths]
        mismatches = [item.case_id for item in results if not item.expectation_met]
        self.assertEqual(mismatches, [])
        self.assertGreaterEqual(sum(item.result == audit.PASS for item in results), 12)
        self.assertGreaterEqual(sum(item.result == audit.DENY for item in results), 22)
        self.assertGreaterEqual(sum(item.result == audit.BLOCKED for item in results), 26)


if __name__ == "__main__":
    unittest.main()

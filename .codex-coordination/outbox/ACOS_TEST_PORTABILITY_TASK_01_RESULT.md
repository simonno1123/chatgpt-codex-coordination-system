# ACOS Result

ARTIFACT TYPE:
RESULT

PRODUCER:
Codex Executor

TO:
ChatGPT Review

MODE:
TEST

PROJECT:
chatgpt-codex-coordination-system

CURRENT RECEIVER:
Codex Executor

ROLE:
Bounded executor (performed by Claude Code acting in the executor role)

TASK STATUS:
DONE

TASK FILE REQUIRED:
NO

TARGET PATH:
tests/test_acos_v2_remote_context_live_adapter.py; scripts/acos-run-tests.py; README.md; .codex-coordination/outbox/ACOS_TEST_PORTABILITY_TASK_01_RESULT.md

CAN:
Make the test suite runnable off the pinned macOS host; add a per-file test runner; document how to run tests; write this RESULT.

CANNOT:
Loosen the RuntimeBinding pin in scripts; change production scripts; stage, commit, push, reset or clean; produce REVIEW, DECISION or self-acceptance.

ACTION REQUIRED:
ChatGPT Review reviews this RESULT and decides ACCEPTED / REWORK / BLOCKED.

AUTHORITY LIMIT:
User chat authorization on 2026-10-30 for one TEST/MAINTENANCE task: test portability. Local working-tree edits only.

FORBIDDEN:
git add / commit / push / reset / clean; edits to scripts other than the new runner; changes to scope rules, lifecycle state, EC09/GR01 or Stage status.

OUTPUT:
RESULT

---

## 1. Task ID

ACOS_TEST_PORTABILITY_TASK_01

## 2. Status

DONE

## 3. Summary

On Linux (WSL Ubuntu 24.04, Python 3.12.3), 21 of 25 test files passed. The other 4 errored in fixture setup because the live adapter harness pins `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13`. The live adapter test module now raises `unittest.SkipTest` before installing any guard when that pinned interpreter is absent. The three frozen-harness importers inherit the skip. On the pinned host behaviour is unchanged. A per-file runner and a README section were added.

## 4. Files Created

- `scripts/acos-run-tests.py`
- `.codex-coordination/outbox/ACOS_TEST_PORTABILITY_TASK_01_RESULT.md`

## 5. Files Modified

- `tests/test_acos_v2_remote_context_live_adapter.py` (module-level skip when the pinned runtime is absent)
- `README.md` (new section 16A. Running Tests)

## 6. Files Deleted

- None

## 7. Commands Run

- `python scripts/acos-run-tests.py` (as non-root user, WSL Ubuntu 24.04)
- `python scripts/acos-linter.py .codex-coordination/outbox/ACOS_TEST_PORTABILITY_TASK_01_RESULT.md`
- `git status --short`, `git diff --stat`

## 8. Verification Method

Full per-file run before and after the change on the same host and commit `5b7ff4d`. The working tree was checked with `git status` to confirm only the listed files changed.

## 9. Test Results

Before: 21/25 files passed; 156 failures in the 4 pinned-host files, all `FileNotFoundError` on the pinned macOS interpreter.

After: 25/25 files ok. 21 files pass in full; the 4 pinned-host files report `1 skipped` with the reason. No pass count changed in the other 21 files.

Not verified: the pinned macOS host itself. The skip condition is `not os.path.isfile(PINNED_PYTHON)`, so that host takes the original code path.

## 10. Authorization Check

1. Yes. Only the four target paths were touched.
2. Yes. No script other than the new runner was edited; the RuntimeBinding pin is unchanged.
3. No git add / commit / push was executed.
4. No REVIEW, DECISION or self-acceptance was produced.
5. Not applicable; no task file was required.

## 11. Risks

1. The skip also hides the 9 tests in these files that previously passed off-host. They depended on the same harness module, so they cannot be split out without changing the frozen harness.
2. The runner depends on pytest, which is not listed in the requirements files.

## 12. Questions for ChatGPT Review

Should pytest be added as a pinned test-only requirement?

NEXT RECEIVER:
ChatGPT Review

Reason:
Codex RESULT or BLOCKED RESULT must be reviewed by ChatGPT Review before ACCEPTED, REWORK, BLOCKED, commit, push, or next task.

# ACOS Result

ARTIFACT TYPE:
RESULT

PRODUCER:
Codex Executor

TO:
ChatGPT Review

MODE:
MAINTENANCE

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
acos-v2-host-runtime-profiles.json; scripts/acos-v2-remote-context-live-adapter.py; scripts/acos-v2-remote-context-live-launcher.py; scripts/acos-v2-production-host-control-producer.py; scripts/acos-host-runtime-profile.py; scripts/acos-run-tests.py; tests/test_acos_v2_remote_context_live_adapter.py; tests/test_acos_v2_production_host_control_producer.py; README.md; .codex-coordination/outbox/ACOS_HOST_RUNTIME_PROFILE_TASK_01_RESULT.md

CAN:
Replace the hardcoded macOS runtime in the live adapter, launcher and producer with a reviewed repository host profile at equal strictness; update the dependent hash pin; make the four live-runtime test files run on any POSIX host; document the change; write this RESULT.

CANNOT:
Loosen channel timing limits, capability, credential or network gates; establish production sources; change scope rules, lifecycle state, EC09/GR01 or Stage status; stage, commit or push before user review.

ACTION REQUIRED:
ChatGPT Review reviews this RESULT, including the two security-relevant changes in section 11, and decides ACCEPTED / REWORK / BLOCKED.

AUTHORITY LIMIT:
User chat decision on 2026-10-30: the system must not be limited to any operating system; scope chosen: remove the macOS hardcoding, Linux and macOS native, Windows through WSL. Local working-tree edits only.

FORBIDDEN:
git add / commit / push / reset / clean before user review; edits outside the target paths; native Windows support (not chosen).

OUTPUT:
RESULT

---

## 1. Task ID

ACOS_HOST_RUNTIME_PROFILE_TASK_01

## 2. Status

DONE

## 3. Summary

The adapter, launcher and producer hardcoded the python.org macOS 3.13 framework. They now read approved host runtimes from `acos-v2-host-runtime-profiles.json`, which ships only the original macOS profile.

RuntimeBinding replaces `python_app_pin` and `framework_pin` with three fields: `host_profile`, `host_profile_pin` and an ordered `runtime_file_pins`. Each profile pins the interpreter, the OS process binary, the extra runtime files, the version, the architecture and the dependency root. The launcher's dependency-scope check now uses the same rule as the adapter's DependencyPin: the dependency root's `parents[2]`. `LD_PRELOAD` and `LD_AUDIT` were added to the forbidden environment, alongside `DYLD_INSERT_LIBRARIES`.

The launcher's `PRODUCER_SHA` was updated to the edited producer. On a host whose interpreter matches the repository profile, such as the original Mac, the tests use the repository file. On other hosts they use a synthetic profile in a temporary file. The four harness files now run under `-I -S -B` on Linux instead of being skipped.

## 4. Files Created

- `acos-v2-host-runtime-profiles.json`
- `scripts/acos-host-runtime-profile.py` (prints a candidate profile; writes nothing)
- `.codex-coordination/outbox/ACOS_HOST_RUNTIME_PROFILE_TASK_01_RESULT.md`

## 5. Files Modified

- `scripts/acos-v2-remote-context-live-adapter.py`
- `scripts/acos-v2-remote-context-live-launcher.py`
- `scripts/acos-v2-production-host-control-producer.py`
- `scripts/acos-run-tests.py` (runs the four harness files isolated; module-skip leniency removed)
- `tests/test_acos_v2_remote_context_live_adapter.py` (host-derived profile, `sys.executable` child, T43 inode-safe replacement, new R19)
- `tests/test_acos_v2_production_host_control_producer.py` (profile-derived pins, new HP_R14 and HP_R15)
- `README.md` (16A updated, new 16B)

## 6. Files Deleted

- None

## 7. Commands Run

- Isolated runs: `python -I -S -B tests/<file>.py` for the four harness files, repeated
- `python scripts/acos-run-tests.py` (three full-suite runs)
- Timing probes with in-process timing and cProfile (scratch scripts outside the repository)
- `python -I -S -B scripts/acos-host-runtime-profile.py <name>`
- `git status --short`, `git diff --stat`, `acos-linter.py` on this RESULT

## 8. Verification Method

Before: on Linux the four harness files could not run; they were skipped, and 156 tests failed without the skip. After: each file ran in full, without failfast, on WSL Ubuntu 24.04, Python 3.12.3, x86_64. No hardcoded macOS path remains in `scripts/` or `tests/`.

## 9. Test Results

Full runs without failfast, one at a time: live adapter 71/71, producer 67/67, Core snapshot host preflight 10/10, D04 revocation preflight 10/10. The other 21 files are unchanged and pass.

Timing-sensitive files on this host (Intel N100 under WSL), five isolated runs each:

- Producer: 5/5 passed.
- Core snapshot host preflight: 3/5 passed.
- D04 revocation preflight: 1/5 passed.
- Untouched mutation pilot: 4/5 passed.

The failures were `FRAME_TIMEOUT` (the 0.2 s host frame), apart from one assertion flake in the untouched mutation pilot. Full suite: 23/25, 24/25, 25/25 and, in the final run, 23/25. In that final run the producer also hit `FRAME_TIMEOUT` (HP_R01, HP_R02), so it is not reliably stable on this host either.

Root cause, measured: RuntimeBinding.verify takes 120–170 ms on this CPU, mostly per-file `Path.resolve()`, stat and inventory checks over 313 dependency files. The test harness runs producers as threads sharing the GIL, so a gap above 0.2 s between host queries fails closed. Timing limits were not changed.

Not verified: the macOS host. By construction, that host matches the repository profile and binds the same files as before.

## 10. Authorization Check

1. Yes. Only the target paths were touched.
2. Yes. Timing limits, capability, credential and network gates are unchanged; production sources remain unestablished.
3. No git add / commit / push was executed.
4. No REVIEW, DECISION or self-acceptance was produced.
5. Not applicable; no task file was required.

## 11. Risks

1. Security-relevant change: FilePin (adapter) and Pin (producer) now cache a successful content hash, keyed by the pin and the full stat identity (device, inode, size, mtime_ns, ctime_ns). A file is re-hashed when any of these changes; rewriting content updates ctime. Without this cache, an 8 MB Linux interpreter was re-hashed on every qualify, about 8 ms each, and the real-time windows failed. Residual risk: a writer able to restore ctime, which requires root or raw device access.
2. Security-relevant change: the producer selects the one approved profile whose interpreter matches its registration. It no longer requires the producer's interpreter to be literally the same constant as the worker's; the worker is still bound by its own RuntimeBinding profile.
3. RuntimeBinding field names and shape changed. Any stored or external packet using `python_app_pin` and `framework_pin` must be regenerated.
4. The four harness tests are flaky on slow hardware, as measured above. Further speedups would mean rewriting path handling in frozen security modules; that is not done.
5. `DarwinReadOnlyObservations` remains macOS-only. It is a fail-closed candidate that is never wired into production, and there is no Linux counterpart.

## 12. Questions for ChatGPT Review

1. Accept the stat-identity hash cache in risk 1?
2. Should an approved profile for a non-Mac host be added to the repository file now, or only when a specific host is qualified?

NEXT RECEIVER:
ChatGPT Review

Reason:
Codex RESULT or BLOCKED RESULT must be reviewed by ChatGPT Review before ACCEPTED, REWORK, BLOCKED, commit, push, or next task.

# ACOS Validation Scenario Fixtures

These fixtures exercise the TASK_051 through TASK_056 shadow prototypes as a
single deterministic governance chain. The runner imports the existing Python
modules in-process, sends them static fixture data, normalizes their public
results, and aggregates those results without copying component policy rules.

## Safety Boundary

The runner is fixture-only, dry-run, and non-enforcing. It does not:

- authenticate a live runtime identity;
- inspect or mutate a live project, filesystem permission, or Git state;
- write a real audit log;
- contact an External Advisory Reviewer or consume a real User Decision;
- authorize task execution, commit, push, release, or a later task;
- invoke a model, API, MCP server, network service, shell, or subprocess.

A scenario `PASS` is evidence that static inputs agree with the current shadow
components. It is not production authorization or enforcement.

## Components

| Identifier | Existing shadow component |
| --- | --- |
| `runtime_identity` | Runtime Identity Simulator |
| `filesystem_permission` | Filesystem Permission Checker |
| `git_operation` | Git Operation Gate |
| `audit_jsonl` | Audit JSONL Writer |
| `advisory_gate` | External Advisory Gate Checker |
| `user_decision_gate` | User Decision Gate Checker |

The default governance order is runtime identity, User Decision, filesystem
scope, advisory gate, Git gate, and audit record. A fixture may declare another
order, but declared dependency reversals are denied and unknown or cyclic
dependencies are blocked.

## Modes

- `validate_scenario`: validates fixture schema, references, order, and inputs.
- `run_pipeline`: evaluates components in the declared static order.
- `verify_component_contracts`: checks normalized component result contracts.
- `compare_results`: detects unresolved fixture/component result conflicts.
- `detect_policy_drift`: compares explicit policy versions and mapping digests.

All modes remain in-memory evaluations.

## Aggregation Matrix

The runner uses deterministic fail-closed aggregation over required components:

| Required component outcomes | Overall result |
| --- | --- |
| One or more `BLOCKED` | `BLOCKED` |
| No `BLOCKED`, one or more `DENY` | `DENY` |
| Every required component `PASS` | `PASS` |

`BLOCKED` therefore takes precedence when `DENY` and `BLOCKED` coexist. A
component exception, import failure, adapter failure, malformed contract,
missing critical input, unknown value, unresolved result conflict, or
indeterminate policy state is never converted to `PASS`. Optional components
may be skipped with an explicit warning; optional failures are ignored only
when the fixture explicitly enables that behavior.

## Result Contract

Each normalized component result contains:

```text
component
invoked
input_valid
result
allowed
reason
lifecycle_state
warnings
source
contract_version
```

`result` must be `PASS`, `DENY`, or `BLOCKED`, and `allowed` must be true only
for `PASS`. The scenario output includes component lists, flow-specific flags,
policy drift details, lifecycle details, the expected result, and whether the
expectation matched.

## Fixture Matrix

The directory intentionally contains:

- 21 `valid-*.json` fixtures expected to `PASS`;
- 41 `invalid-*.json` fixtures expected to `DENY`;
- 41 `blocked-*.json` fixtures expected to `BLOCKED`.

DENY fixtures represent known violations such as role spoofing, scope escape,
authorization inheritance, skipped advisory review, stale User Decisions,
unsafe Git operations, and audit tampering. BLOCKED fixtures represent missing,
unknown, malformed, contradictory, or otherwise indeterminate inputs.

## CLI

Run the complete fixture matrix:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/acos-validation-scenario-runner.py \
  fixtures/validation-scenarios/
```

Run one fixture with JSON output:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/acos-validation-scenario-runner.py \
  --format json \
  fixtures/validation-scenarios/valid-end-to-end-shadow-flow.json
```

The exit code is zero when every fixture matches its declared expectation, one
for expectation mismatches, and nonzero for CLI or input-path failures. DENY
and BLOCKED fixtures do not fail a batch when those outcomes are expected.

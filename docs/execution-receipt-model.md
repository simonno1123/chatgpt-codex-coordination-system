# ACOS Execution Receipt Model

## 1. Purpose

The ACOS Execution Receipt Model defines the structured governance record
produced after an authorized execution activity.

```text
Execution Receipt != Runtime Log
```

An Execution Receipt is a structured governance claim about one authorized
execution attempt. It binds the task, executor, authorized boundary, actual
effects, and validation outcome so that ChatGPT Review can evaluate what
happened.

A receipt is not proof merely because it exists. It does not authenticate a
live runtime, grant authority, approve its producer, or replace independent
review.

## 2. Relationship Model

The receipt connects the ready task and its execution boundary to reviewable
evidence:

```text
TASK_READY
    |
    v
Execution Boundary
    |
    v
Execution Activity
    |
    v
Execution Receipt
    |
    v
Review Evidence
    |
    v
ChatGPT Review
```

The receipt is downstream of execution authority. It cannot create, expand, or
renew that authority.

The receipt contributes evidence to review. It is not itself a `REVIEW`,
`DECISION`, User Decision, commit authorization, push authorization, or task
closure record.

## 3. Receipt Definition

An Execution Receipt describes:

```text
What was authorized?
Who reports executing it?
What activity was attempted?
What effects were observed?
What validation was performed?
Did the effects remain within the authorized boundary?
Which review consumes the receipt?
```

The receipt is bound to a single task and execution attempt. Multiple attempts
require distinct receipt identities so that later activity cannot be silently
merged into earlier evidence.

### 3.1 Receipt Versus Runtime Log

A Runtime Log is typically a chronological stream of operational events. It
may be verbose, incomplete, implementation-specific, or unrelated to a
governance decision.

An Execution Receipt is a bounded summary with explicit governance references
and a declared boundary comparison.

| Property | Execution Receipt | Runtime Log |
| --- | --- | --- |
| Primary purpose | Governance review | Operational observation or diagnosis |
| Scope | One authorized execution attempt | Potentially many runtime events |
| Required task binding | Yes | Not necessarily |
| Required boundary binding | Yes | Not necessarily |
| Required actual-effect summary | Yes | May be distributed across events |
| Grants authorization | No | No |
| Constitutes acceptance | No | No |
| Proves authenticity by itself | No | No |

A receipt may cite an authorized log or validation output, but copying log text
does not make the log a receipt.

## 4. Receipt Identity And Components

Every receipt should have a stable `receipt_id` and include the following
required components.

| Component | Required Meaning |
| --- | --- |
| `task_id` | The materialized task that authorized the execution lifecycle. |
| `executor_identity` | The governance identity claiming the execution; not proof of authenticated runtime identity. |
| `execution_scope` | The authorized project, paths, actions, commands, outputs, prohibitions, and authorization references. |
| `execution_time` | The reported start and end time, including timezone or offset when available. |
| `changed_artifacts` | A manifest of created, modified, moved, renamed, deleted, generated, or cleaned artifacts. |
| `validation_result` | The checks performed, their outcomes, and material limitations or mismatches. |
| `boundary_check` | The comparison of Actual Change with Authorized Scope, including `PASS`, `VIOLATION`, or `BLOCKED`. |
| `review_reference` | The ChatGPT Review artifact or pending review reference that consumes the receipt. |

### 4.1 Recommended Identity References

The receipt should also identify:

- `receipt_id`
- `execution_attempt_id`
- task artifact path
- task content digest
- project
- receiver
- applicable Decision or User Decision reference
- execution boundary version or digest
- result artifact reference

These references prevent a receipt from being detached from the task and reused
for another project, attempt, or authorization.

### 4.2 `executor_identity`

`executor_identity` records the role or runtime identity represented by the
receipt. In this governance model it is a declaration, not cryptographic
authentication.

Provider or model name is not sufficient executor identity. A future runtime
may bind the receipt to an authenticated session, but this document does not
provide that mechanism.

### 4.3 `execution_scope`

`execution_scope` records the boundary in force before execution. It should
include:

- allowed files and permitted change types
- allowed actions
- allowed commands or command classes
- permitted side effects
- required outputs
- forbidden files and actions
- whether network or external-system access was allowed
- whether stage, commit, push, or release was authorized

The scope must come from the ready task and applicable authorization. It cannot
be reconstructed solely from what the executor happened to do.

### 4.4 `execution_time`

`execution_time` should report the execution interval and timezone. If the time
source is not trusted, the receipt must not describe it as a trusted timestamp.

Time metadata helps review sequence and freshness. It does not prove that the
activity occurred at the declared time.

### 4.5 `changed_artifacts`

`changed_artifacts` should report every known execution effect, including:

- path or external target
- change type
- before and after identity or digest when available
- tracked, untracked, generated, or external status
- whether the effect was retained, reverted, or cleaned
- uncertainty or attribution limitation

An empty manifest must be explicit. It cannot be inferred from omitted data.

### 4.6 `validation_result`

`validation_result` should identify:

- validation command or check
- purpose
- outcome
- exit status when applicable
- relevant summary
- generated side effects
- skipped checks and reasons
- limitations

A passing validation does not override a boundary violation.

### 4.7 `boundary_check`

`boundary_check` compares all known Actual Change with the authorized Execution
Boundary.

Allowed values:

- `PASS`: every known effect is within Authorized Scope.
- `VIOLATION`: at least one known effect is outside Authorized Scope.
- `BLOCKED`: the comparison cannot be completed safely because required scope
  or execution evidence is missing, ambiguous, or contradictory.

`PASS` is a claim for review, not self-acceptance.

### 4.8 `review_reference`

At `GENERATED`, `review_reference` may identify the intended review route as
pending. When the receipt reaches `REVIEWED`, it must reference the actual
ChatGPT Review artifact that consumed it.

An External Advisory artifact may be referenced separately when required, but
it cannot replace `review_reference` or accept the receipt.

## 5. Boundary Binding

An Execution Receipt must bind to Authorized Scope, not merely list Actual
Change.

An actual-change-only report answers:

```text
What appears to have changed?
```

A boundary-bound receipt also answers:

```text
Was each effect authorized under the verified task boundary?
```

The minimum comparison is:

```text
Authorization Basis
        +
Execution Boundary Snapshot
        +
Actual Effects
        +
Validation Results
        =
Reviewable Boundary Claim
```

For a `PASS` boundary claim:

```text
Every Actual Change must be within Authorized Scope.
```

If Authorized Scope is missing, stale, changed after readiness, or cannot be
identified, the receipt cannot claim `PASS`.

### 5.1 Boundary Mismatch

The receipt must disclose:

- an unlisted path or output
- an unauthorized action or command
- an unexpected side effect
- a different task digest or project
- a missing or stale authorization
- a mismatch between declared and observed repository state
- incomplete attribution

The executor must not edit the scope after execution to make the receipt appear
compliant.

### 5.2 No Authorization Transfer

A receipt for one action does not authorize a later action.

Examples:

- an edit receipt does not authorize staging
- a stage receipt does not authorize commit
- a commit receipt does not authorize push
- a push receipt does not authorize release

Each later operation requires its own lifecycle and separate authorization.

## 6. Receipt Lifecycle

The canonical lifecycle is:

```text
GENERATED
    |
    v
VALIDATED
    |
    v
REVIEWED
    |
    v
ACCEPTED
```

Exceptional states:

```text
INVALID
BLOCKED
```

Receipt state is distinct from task state. A receipt transition does not
transition the task by itself.

### 6.1 `GENERATED`

The executor has produced the receipt and bound it to a task and execution
attempt.

Generation proves only that a receipt artifact exists. It does not prove that
the receipt is complete, accurate, validated, reviewed, or accepted.

### 6.2 `VALIDATED`

Required fields, references, internal consistency, and boundary comparison have
been checked.

Validation may use a deterministic check when separately implemented and
authorized, but deterministic validation cannot accept the receipt or decide
the task.

### 6.3 `REVIEWED`

ChatGPT Review has consumed the receipt with the related task, result, boundary,
and available execution evidence.

Review must address material mismatches, limitations, and advisory findings
when an advisory review is required.

### 6.4 `ACCEPTED`

ChatGPT Review has accepted the receipt as usable review evidence.

```text
Receipt ACCEPTED != Task ACCEPTED
Receipt ACCEPTED != Commit Authorized
Receipt ACCEPTED != Push Authorized
```

Receipt acceptance does not prove cryptographic authenticity or make an
incorrect execution valid.

### 6.5 `INVALID`

A receipt is `INVALID` when it is malformed, internally contradictory,
misbound, falsely classified, or missing information required to support its
claim.

An invalid receipt cannot serve as acceptance evidence. It routes to ChatGPT
Review for disposition or bounded rework.

### 6.6 `BLOCKED`

A receipt is `BLOCKED` when safe generation or validation cannot complete, for
example because:

- the authorized boundary is unavailable or ambiguous
- actual effects cannot be determined
- task or authorization references conflict
- evidence needed for boundary comparison is unavailable
- the execution attempt has uncertain side effects

`BLOCKED` must preserve uncertainty. It must not be converted to `PASS` through
assumption.

## 7. Receipt Validation

Receipt validation checks:

1. Required components are present.
2. Task and execution attempt references are unique and consistent.
3. The task digest, project, receiver, and authorization references match the
   ready execution context.
4. Authorized Scope is recorded independently from Actual Change.
5. Changed artifacts and other side effects are complete to the known extent.
6. Validation outcomes and limitations are disclosed.
7. The boundary result follows from the recorded comparison.
8. The receipt does not claim review, decision, or later-operation authority.
9. `review_reference` identifies the correct route or consuming review.

Validation failure yields `INVALID` or `BLOCKED`; it does not silently omit the
missing evidence.

## 8. Role Boundary

### 8.1 `CODEX_EXECUTOR`

Codex Executor may generate an Execution Receipt for its authorized execution
attempt and report known limitations.

It cannot:

- expand Authorized Scope
- authenticate its own runtime identity by declaration
- accept its own receipt
- issue `REVIEW` or `DECISION`
- infer commit, push, or release authority

### 8.2 `CHATGPT_REVIEW`

ChatGPT Review:

- evaluates receipt completeness and boundary binding
- consumes the receipt with other review evidence
- marks the receipt reviewed
- determines whether the receipt is accepted, invalid, or blocked
- issues or routes the governed task decision

ChatGPT Review does not rewrite executor provenance or turn a receipt into proof
of an event that cannot be verified.

### 8.3 `EXTERNAL_ADVISORY`

External Advisory may provide non-binding observations about receipt risks,
inconsistencies, or omissions when requested.

It cannot generate the executor receipt, change receipt or task state, accept
the receipt, grant authorization, or route instructions directly to Codex.

### 8.4 `AUTOMATION`

Automation may perform separately authorized deterministic structure or
consistency checks. It cannot accept the receipt, decide the task, or broaden
the recorded scope.

## 9. Relationship To Result, Review, And Audit

An Execution Receipt may accompany an executor `RESULT`, but the artifacts have
different purposes:

- `RESULT` communicates the executor's task outcome and next route.
- Execution Receipt structures the authorization, activity, effects, and
  boundary comparison for one attempt.
- `REVIEW` evaluates the result and receipt.
- `DECISION` determines the governed outcome.

An Execution Receipt is also not an audit trail. A future audit system may
record receipt events or hashes, but the receipt neither creates durable audit
storage nor replaces the existing audit specification.

## 10. Fail-Closed Handling

Receipt handling fails closed when:

- the task or boundary cannot be identified
- required components are missing
- receipt references conflict
- Actual Change is incomplete or uncertain
- a `PASS` claim is unsupported
- review provenance is absent or mismatched

The workflow retains the last verified state and routes the receipt to ChatGPT
Review as `INVALID` or `BLOCKED`. No role may infer permission to repair,
repeat, commit, push, or close the task from the receipt failure itself.

## 11. Non-Implementation Boundary

This model is a governance specification only. It does not implement:

- a Runtime Log system
- an automatic audit platform
- a trusted execution environment
- cryptographic proof or digital signatures
- trusted timestamping
- authenticated runtime identity
- a persistent database or receipt store
- automatic receipt generation
- automatic validation or boundary enforcement
- automatic authorization
- an orchestrator
- a policy engine, schema, or validator
- a Git hook or wrapper

It does not modify runtime behavior, grant repository access, or authorize
stage, commit, push, release, or cross-project activity.

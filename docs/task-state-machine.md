# ACOS Task State Machine

## 1. Purpose

The ACOS State Layer defines how a governed task moves from a logical proposal
to verified closure.

```text
Logical Task Existence != Physical Artifact Existence
```

The model prevents a task definition in conversation from being treated as a
repository artifact or as execution authority. It is a governance lifecycle,
not a runtime engine or durable state service.

## 2. State Model Principles

1. State transitions are explicit and verification-based.
2. Definition, materialization, readiness, and execution are distinct states.
3. A later state cannot be inferred from intent or prose alone.
4. A producer cannot approve its own output.
5. Result production does not imply review, acceptance, or closure.
6. Repository actions require their own authorization even after a task is ready.
7. Invalid or unsupported transitions fail closed.

## 3. State Definitions

| State | Meaning | Transition Owner | Required Verification |
| --- | --- | --- | --- |
| `DRAFT` | A logical proposal that is not a formal executable task. | `CHATGPT_REVIEW` | Draft text or discussion context. |
| `TASK_DEFINED` | Objective, scope, receiver, forbidden actions, and acceptance criteria are settled; a task file may not exist. | `CHATGPT_REVIEW` | Complete task specification. |
| `TASK_MATERIALIZED` | The task artifact exists in managed storage with an exact path, unique reference, and named receiver. | `CHATGPT_REVIEW`, based on a materialization record | Readable artifact, exact path, task ID, receiver, and content digest. |
| `TASK_READY` | Materialization is verified, the receiver is confirmed, scope is validated, and required execution authorization is active. | `CHATGPT_REVIEW` | Materialization record plus explicit ready handoff. |
| `TASK_EXECUTING` | The executor has accepted the ready task and is performing only its authorized actions. | `CODEX_EXECUTOR` | Ready task reference and execution-start report or active run context. |
| `TASK_RESULT` | The executor has produced `RESULT` or `BLOCKED RESULT` with verification and scope records. | `CODEX_EXECUTOR` | Result artifact bound to the task ID and materialized task reference. |
| `TASK_REVIEW` | The result is being evaluated for completeness, correctness, scope, and authority compliance. | `CHATGPT_REVIEW` | Consumed result and reviewed verification records. |
| `TASK_DECISION` | ChatGPT Review has issued a governed outcome after review. | `CHATGPT_REVIEW` | Decision artifact with outcome, rationale, and next receiver. |
| `TASK_CLOSED` | The accepted lifecycle is complete and all required closure conditions are satisfied. | `CHATGPT_REVIEW` | Accepted decision and verification records for required post-decision actions. |

### 3.1 Materialized Task Identity

A materialized task is identified by at least:

```text
task_id
target_path
content_digest
receiver
```

Changing the task content after materialization changes its digest and requires
the revised task to be verified again before it can return to `TASK_READY`.

### 3.2 Materialization Does Not Grant Execution

```text
TASK_MATERIALIZED != TASK_READY
```

The presence of a file proves only that the artifact exists at the verified
location. It does not prove that the receiver accepted it, that scope is valid,
or that execution, commit, or push is authorized.

## 4. Canonical Lifecycle

```text
DRAFT
  |
  v
TASK_DEFINED
  |
  v
TASK_MATERIALIZED
  |
  v
TASK_READY
  |
  v
TASK_EXECUTING
  |
  v
TASK_RESULT
  |
  v
TASK_REVIEW
  |
  v
TASK_DECISION
  |
  v
TASK_CLOSED
```

## 5. Transition Rules

| From | To | Required Condition |
| --- | --- | --- |
| `DRAFT` | `TASK_DEFINED` | Objective, scope, receiver, forbidden actions, acceptance criteria, and output route are complete. |
| `TASK_DEFINED` | `TASK_MATERIALIZED` | The exact artifact exists, is readable, matches the approved definition, has a unique reference, and names its receiver. |
| `TASK_MATERIALIZED` | `TASK_READY` | Receiver is confirmed, scope is validated, and required execution authorization is explicit. |
| `TASK_READY` | `TASK_EXECUTING` | The named executor consumes the ready task and accepts only its stated scope. |
| `TASK_EXECUTING` | `TASK_RESULT` | The executor stops work and produces a result bound to the task. |
| `TASK_RESULT` | `TASK_REVIEW` | ChatGPT Review receives and begins evaluation of the result. |
| `TASK_REVIEW` | `TASK_DECISION` | Review is complete and material findings are dispositioned. |
| `TASK_DECISION` | `TASK_CLOSED` | Outcome is `ACCEPTED` and all required closure actions have verified records. |

### 5.1 Required Materialization Transition

Allowed:

```text
TASK_DEFINED
      -> TASK_MATERIALIZED
      -> TASK_READY
      -> TASK_EXECUTING
```

Forbidden:

```text
TASK_DEFINED
      -> TASK_EXECUTING
```

Reason: the direct transition skips physical artifact verification, receiver
confirmation, scope validation, and the ready handoff.

### 5.2 Required Review And Decision Gate

Allowed:

```text
TASK_RESULT
      -> TASK_REVIEW
      -> TASK_DECISION
```

Forbidden:

```text
TASK_RESULT
      -> TASK_CLOSED
```

Reason: an executor result is input for review, not acceptance or closure.

## 6. Decision Outcomes

`TASK_DECISION` records one of these governed outcomes:

### `ACCEPTED`

The reviewed result satisfies the task. The lifecycle may move to
`TASK_CLOSED` only after any required commit, push, publication, or record action
is separately authorized and verified.

### `REWORK`

The result requires bounded revision. ChatGPT Review issues a revised task or
rework instruction. If the materialized task content changes, the lifecycle
returns to `TASK_DEFINED` and must pass materialization and readiness again.

### `BLOCKED`

The lifecycle cannot safely advance. The decision must name the blocker and
next receiver. No role may infer permission to resolve the blocker by expanding
scope.

Neither `REWORK` nor `BLOCKED` automatically transitions to `TASK_CLOSED`.

## 7. Invalid Transitions

The following transitions are invalid:

| Invalid Transition | Reason |
| --- | --- |
| `DRAFT -> TASK_MATERIALIZED` | A draft is not an approved task definition. |
| `DRAFT -> TASK_READY` | Definition, materialization, and readiness checks are missing. |
| `TASK_DEFINED -> TASK_EXECUTING` | Physical materialization and ready authorization are missing. |
| `TASK_MATERIALIZED -> TASK_EXECUTING` | Receiver confirmation and scope validation are missing. |
| `TASK_READY -> TASK_RESULT` without execution | The result lacks an execution lifecycle and provenance. |
| `TASK_EXECUTING -> TASK_CLOSED` | Result, review, and decision are missing. |
| `TASK_RESULT -> TASK_DECISION` | Independent review is missing. |
| `TASK_RESULT -> TASK_CLOSED` | Review and decision are missing. |
| `TASK_REVIEW -> TASK_CLOSED` | A formal decision is missing. |
| `TASK_DECISION(REWORK) -> TASK_CLOSED` | Required rework has not been completed and accepted. |
| `TASK_DECISION(BLOCKED) -> TASK_CLOSED` | The blocker remains unresolved or undispositioned. |

An attempted invalid transition must fail closed. The current valid state is
retained, the reason is recorded, and the artifact routes to
`CHATGPT_REVIEW` or `USER_DECISION_SOURCE` as appropriate.

## 8. State Ownership And Verification

State ownership means authority to recognize or issue a lifecycle transition.
It does not imply authority to perform every action associated with that state.

- `CHATGPT_REVIEW` owns definition, readiness, review, decision, and closure.
- An explicitly authorized repository-capable actor may create the physical task
  artifact, but `CHATGPT_REVIEW` recognizes `TASK_MATERIALIZED` from a
  verification record.
- `CODEX_EXECUTOR` owns its execution and result reporting, not review or
  decision.
- `USER_DECISION_SOURCE` may provide required human authorization or override,
  but does not rewrite artifact provenance.
- `AUTOMATION` may report deterministic observations but does not own lifecycle
  transitions.

## 9. External Advisory Relationship

External Advisory is a cross-cutting process. It is not a task state and
`EXTERNAL_ADVISORY` is not a state owner.

Where advisory review is required, the advisory artifact is consumed during the
governed review and decision process. It cannot move the task, approve it,
close it, or route execution directly to `CODEX_EXECUTOR`.

## 10. Domain Boundary

ACOS Capability and State Model is domain-independent and shall not contain
domain-specific workflow semantics.

Task states describe reusable collaboration governance only. Project-instance
workflows remain inside their own project and do not extend this lifecycle.

## 11. Non-Implementation Boundary

This document does not create or modify:

- a runtime state engine
- persistent state storage
- authenticated runtime identity
- automatic transition logic
- schemas or validators
- enforcement controls
- orchestration
- project-instance workflow

It does not authorize repository mutation, staging, commit, or push.

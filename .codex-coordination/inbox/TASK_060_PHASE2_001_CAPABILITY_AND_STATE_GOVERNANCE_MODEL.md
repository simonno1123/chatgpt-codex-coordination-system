# TASK_060 Phase 2-A Capability And State Governance Model

ARTIFACT TYPE:
TASK

TASK ID:
TASK_060_PHASE2_001_CAPABILITY_AND_STATE_GOVERNANCE_MODEL

STATUS:
TASK_MATERIALIZED

PRODUCER:
ChatGPT Review

TO:
Codex Executor

NEXT RECEIVER:
ChatGPT Review

MODE:
DOCUMENTATION ONLY

PROJECT:
/Users/zhang/Documents/chatgpt-codex-coordination-system

CURRENT RECEIVER:
ChatGPT Review

ROLE:
Review / Decision Coordination Layer

TASK FILE REQUIRED:
YES

TARGET PATH:
.codex-coordination/inbox/TASK_060_PHASE2_001_CAPABILITY_AND_STATE_GOVERNANCE_MODEL.md

CAN:
Verify this materialized task artifact and, after review, transition it to
`TASK_READY`.

CANNOT:
Treat materialization as execution, commit, push, or closure authorization.

ACTION REQUIRED:
ChatGPT Review must verify the artifact and issue an explicit `TASK_READY`
handoff before Codex creates the deliverables.

AUTHORITY LIMIT:
After `TASK_READY`, Codex may create only `docs/capability-model.md` and
`docs/task-state-machine.md`. No other file may be created or modified.

FORBIDDEN:
- Do not modify Python files.
- Do not modify schemas or validators.
- Do not modify tests.
- Do not implement runtime identity or runtime enforcement.
- Do not create a database, orchestrator, policy engine, sandbox, or adapter.
- Do not modify `claude-for-legal-cn`.
- Do not create another TASK_060 artifact.
- Do not stage, commit, or push without separate authorization.

OUTPUT:
RESULT or BLOCKED RESULT only

## 1. Objective

Create the first two ACOS Phase 2-A governance documents:

1. Agent Capability Model
2. Task State Machine Model

The documents must establish these distinctions:

```text
Role != Capability
Task Definition != Task Existence
```

This is a documentation-only governance task. It is not ACOS v2 full
implementation and does not authorize runtime or enforcement work.

## 2. Allowed Deliverables

Create only:

```text
docs/capability-model.md
docs/task-state-machine.md
```

## 3. Capability Model Requirements

### 3.1 Purpose

Define the ACOS Capability Layer as the governance description of actions an
agent role is allowed to attempt.

State explicitly that a capability is not:

- operating-system permission
- Git permission
- API permission
- authenticated identity
- proof that an action can be performed

### 3.2 Roles

Define these domain-independent roles:

```text
USER_DECISION_SOURCE
CHATGPT_REVIEW
CODEX_EXECUTOR
EXTERNAL_ADVISORY
AUTOMATION
```

### 3.3 Capabilities

Define at least:

```text
task_define
task_review
decision_issue
authorization_issue
file_modify
git_commit
git_push
advisory_generate
```

### 3.4 Role-Capability Matrix

The matrix must include at least:

| Role | Allowed Capability |
| --- | --- |
| USER_DECISION_SOURCE | authorization_issue |
| CHATGPT_REVIEW | task_define, task_review, decision_issue |
| CODEX_EXECUTOR | file_modify, git_commit, git_push, each when authorized |
| EXTERNAL_ADVISORY | advisory_generate |
| AUTOMATION | explicitly bounded automation actions only |

The document must distinguish standing role authority from task-scoped action
authorization. In particular, `git_commit` and `git_push` remain separately
authorized operations.

### 3.5 Negative Capabilities

External Advisory must be forbidden from:

```text
file_modify
task_approve
state_transition
git_operation
```

Codex Executor must be forbidden from:

```text
decision_issue
advisory_override
```

Automation must not receive review, decision, or self-authorization authority.

## 4. Task State Machine Requirements

### 4.1 Purpose

Define the State Layer around this distinction:

```text
Logical Task Existence != Physical Artifact Existence
```

### 4.2 States

Define:

```text
DRAFT
TASK_DEFINED
TASK_MATERIALIZED
TASK_READY
TASK_EXECUTING
TASK_RESULT
TASK_REVIEW
TASK_DECISION
TASK_CLOSED
```

### 4.3 Required Meanings

`DRAFT` is a logical proposal and is not a formal executable task.

`TASK_DEFINED` means the objective, scope, receiver, and acceptance criteria
are settled, but the task file may not exist.

`TASK_MATERIALIZED` means the task artifact exists in managed storage with an
exact path, unique reference, and receiver.

`TASK_READY` requires:

```text
TASK_MATERIALIZED
+ Receiver Confirmed
+ Scope Validated
```

The remaining states must cover execution, result production, review, decision,
and closure without allowing self-review or implicit authorization.

### 4.4 Transition Rules

Allow:

```text
TASK_DEFINED
      -> TASK_MATERIALIZED
      -> TASK_READY
      -> TASK_EXECUTING
```

Forbid:

```text
TASK_DEFINED
      -> TASK_EXECUTING
```

Reason: the transition skips physical materialization and readiness checks.

Allow:

```text
TASK_RESULT
      -> TASK_REVIEW
      -> TASK_DECISION
```

Forbid:

```text
TASK_RESULT
      -> TASK_CLOSED
```

Reason: closure requires review and decision.

The document must identify transition conditions, the role responsible for
issuing or verifying each transition, and invalid transition handling.

### 4.5 Decision Gate

`TASK_DECISION` must record one of the governed outcomes, including:

```text
ACCEPTED
REWORK
BLOCKED
```

Only an accepted decision and any required closure conditions may lead to
`TASK_CLOSED`.

## 5. Domain Boundary

The documents must state:

> ACOS Capability and State Model is domain-independent and shall not contain
> domain-specific workflow semantics.

Do not introduce legal-domain concepts or workflows. In particular, do not use
Evidence, Matter, Litigation, Case, or Legal Research as ACOS model elements.

## 6. External Advisory Relationship

External Advisory is a cross-cutting process referenced by the model. It is not
a task state, not a state owner, not an executor, and not a source of workflow
authority.

This task does not implement or modify the External Advisory mechanism.

## 7. Acceptance Criteria

### Capability Model

- Role and capability are separate concepts.
- Required roles and capabilities are defined.
- A role-capability matrix is present.
- Negative capabilities are explicit.
- Task-scoped authorization remains distinct from role authority.
- No domain binding is introduced.

### Task State Machine

- All required states are defined.
- Materialization is explicit and distinct from definition and readiness.
- Transition conditions and owners are identified.
- Invalid transitions are defined.
- Result cannot bypass review and decision.
- No domain binding is introduced.

## 8. Validation And Result

Codex must report:

- created files
- scope check
- forbidden-changes check
- documentation validation performed
- Git status
- whether staging, commit, or push occurred
- risks or limitations

After implementation, the result must return to ChatGPT Review. Because this
task changes governance capability mapping and artifact lifecycle definitions,
commit authorization requires Mandatory External Advisory Review under the
existing trigger policy.

NEXT RECEIVER:
ChatGPT Review

Reason:
The materialized task must be verified and explicitly transitioned to
`TASK_READY` before documentation implementation begins.

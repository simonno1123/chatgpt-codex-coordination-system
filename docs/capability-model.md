# ACOS Capability Model

## 1. Purpose

The ACOS Capability Layer describes the governance actions that an agent role
is allowed to attempt.

```text
Role != Capability
```

A role identifies a participant's governance responsibility. A capability is a
named governance permission associated with that role. Possessing a capability
does not prove that an action is technically available or authorized for a
specific task.

A capability is not:

- operating-system permission
- Git permission
- API permission
- authenticated identity
- a credential
- proof that an action was performed
- permission to bypass a task, review, decision, or user gate

This document is a governance model only. Runtime identity, filesystem access,
technical enforcement, and durable authorization remain outside its scope.

## 2. Role Model

### 2.1 `USER_DECISION_SOURCE`

The human authority for project direction, explicit overrides, credentials,
risk acceptance, and actions that ACOS reserves for human judgment.

### 2.2 `CHATGPT_REVIEW`

The coordination and review authority that defines bounded tasks, evaluates
results, issues reviews and decisions, and routes the next governed action.

### 2.3 `CODEX_EXECUTOR`

The execution role that consumes a ready task, performs only authorized
repository actions, validates its work, and produces `RESULT` or
`BLOCKED RESULT`.

### 2.4 `EXTERNAL_ADVISORY`

The independent, read-only advisory role that provides non-binding
`ADVISORY REVIEW` output to `CHATGPT_REVIEW`.

### 2.5 `AUTOMATION`

The deterministic support role for explicitly configured checks and records.
Automation has no independent review, decision, or self-authorization power.

## 3. Capability Definition

```text
Capability:
A governance permission describing what an agent role is allowed to attempt.
```

Every capability is subject to all applicable task scope, lifecycle state,
receiver, review, decision, and user-authorization requirements.

### 3.1 Core Capabilities

| Capability | Governance Meaning |
| --- | --- |
| `task_define` | Define a bounded task specification and its intended receiver. |
| `task_review` | Evaluate a task or executor result and issue a governed review. |
| `decision_issue` | Issue the final ACOS decision for a reviewed lifecycle step. |
| `authorization_issue` | Provide an explicit human authorization or override within the stated scope. |
| `file_modify` | Modify only files named by a ready task. |
| `git_commit` | Create a commit containing only separately reviewed and authorized paths. |
| `git_push` | Push an authorized commit after a separate push authorization. |
| `advisory_generate` | Produce a non-binding, read-only advisory artifact for ChatGPT Review. |
| `deterministic_check` | Run a preconfigured non-decision check without expanding its input or authority. |
| `record_append` | Append a bounded deterministic record without rewriting governance history. |

### 3.2 Standing Capability And Action Authorization

A role-capability mapping states which kind of action the role may be eligible
to perform. It does not activate that action.

```text
Standing Capability
        +
Valid Task State
        +
Task Scope
        +
Required Review / Decision / User Gate
        =
Eligible Governed Action
```

For example, `CODEX_EXECUTOR` may be mapped to `git_commit` and `git_push`, but
commit and push remain separate operations with separate authorization. An edit
authorization does not imply either operation.

## 4. Role-Capability Matrix

| Role | Allowed Capability | Conditions |
| --- | --- | --- |
| `USER_DECISION_SOURCE` | `authorization_issue` | Limited to the explicit scope, duration, and risk accepted by the user. |
| `CHATGPT_REVIEW` | `task_define`, `task_review`, `decision_issue` | Must preserve producer identity, lifecycle order, and independent review boundaries. |
| `CODEX_EXECUTOR` | `file_modify`, `git_commit`, `git_push` | Each action must be task-scoped; commit and push require separate authorization. |
| `EXTERNAL_ADVISORY` | `advisory_generate` | Read-only, non-binding, and routed only to `CHATGPT_REVIEW`. |
| `AUTOMATION` | `deterministic_check`, `record_append` | Preconfigured and bounded; no discretionary approval or state ownership. |

Unlisted capabilities are denied by default. A role cannot acquire a capability
by declaring it in its own output.

## 5. Negative Capabilities

Negative capabilities state actions that a role must not attempt, even when the
action might be technically possible.

### 5.1 `EXTERNAL_ADVISORY`

The role is forbidden from:

```text
file_modify
task_approve
state_transition
git_operation
```

It also cannot create `TASK`, `RESULT`, `REVIEW`, or `DECISION`, route directly
to `CODEX_EXECUTOR`, or convert its recommendation into authorization.

### 5.2 `CODEX_EXECUTOR`

The role is forbidden from:

```text
decision_issue
advisory_override
```

It also cannot define its own executable scope, approve its own result, create
or alter governance decisions, or infer commit or push authority.

### 5.3 `CHATGPT_REVIEW`

The role cannot impersonate an executor verification record, produce a Codex
`RESULT`, or claim that a repository action occurred without repository
verification.

### 5.4 `AUTOMATION`

The role cannot create `REVIEW`, `ADVISORY REVIEW`, or `DECISION`, approve its
own output, expand configured scope, or perform discretionary state transitions.

### 5.5 `USER_DECISION_SOURCE`

Human authorization does not rewrite artifact provenance or transform another
role's output into proof that the role performed an action.

## 6. External Advisory Relationship

External Advisory is a cross-cutting process. The
`EXTERNAL_ADVISORY` role has the single role-specific capability
`advisory_generate`, but the advisory flow itself is not a capability, a task
state, an executor, or a state owner.

An advisory artifact remains non-binding and must return to
`CHATGPT_REVIEW` for evaluation and decision.

## 7. Relationship To Existing Permission Models

This governance model is upstream of runtime and filesystem permission models.
It answers:

```text
What may this role be authorized to attempt?
```

It does not answer:

```text
Can this runtime technically perform the action now?
```

Any future implementation must map the governance capability to an authenticated
runtime, scoped technical permission, and auditable authorization without
silently broadening the capability.

## 8. Domain Boundary

ACOS Capability and State Model is domain-independent and shall not contain
domain-specific workflow semantics.

Roles and capabilities must describe reusable collaboration governance. A
project-specific action remains inside the project instance and cannot become
an ACOS capability merely because one project requires it.

## 9. Non-Implementation Boundary

This document does not create or modify:

- runtime identity
- credentials
- filesystem permissions
- Git configuration
- schemas or validators
- enforcement components
- orchestration
- persistent capability storage

It grants no repository action and does not authorize commit or push.

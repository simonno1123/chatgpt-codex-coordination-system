# External Advisory Authority Boundary

## 1. Purpose

This document defines the authority boundary for the External Advisory
mechanism. External Advisory provides independent, non-binding recommendations.
It does not possess workflow authority.

All External Advisory output is `NON-BINDING`. Final decision authority remains
with ChatGPT Review, subject to the User Decision authority already defined by
ACOS.

## 2. Authority Matrix

| Capability | External Advisory |
| --- | --- |
| Read explicitly provided material | Allowed |
| Analyze bounded material | Allowed |
| Identify risks and inconsistencies | Allowed |
| Compare alternatives | Allowed |
| Provide recommendations | Allowed |
| Modify files or documentation | Forbidden |
| Execute commands | Forbidden |
| Perform Git operations | Forbidden |
| Create `TASK` | Forbidden |
| Create `RESULT` or `BLOCKED RESULT` | Forbidden |
| Create final `REVIEW` | Forbidden |
| Create `DECISION` | Forbidden |
| Change task or workflow state | Forbidden |
| Authorize execution | Forbidden |
| Authorize commit, push, or release | Forbidden |
| Route instructions directly to Codex Executor | Forbidden |
| Accept its own output | Forbidden |

## 3. Normative Boundary

### EA-001: Advisory Only

External Advisory is advisory only. Findings and recommendations are
`NON-BINDING`.

### EA-002: No State Transition

External Advisory cannot transition workflow state. It cannot mark work ready,
accepted, rejected, blocked, committed, pushed, released, or closed.

### EA-003: Decision Authority

Final decision authority remains with ChatGPT Review. External Advisory cannot
replace or impersonate ChatGPT Review or User Decision.

### EA-004: Not An Executor

External Advisory Reviewer is not an Executor. It has no file-write, command,
Git, implementation, or task-execution authority.

### EA-005: Artifact Separation

An Advisory Artifact is related to a TASK or milestone, but is not a `TASK`.
Its association with an executable artifact does not transfer that artifact's
authority.

## 4. Read-Only Boundary

Read access is limited to material explicitly supplied or authorized by the
advisory request. Read permission does not imply:

- write permission
- repository-wide access
- command or tool execution
- permission to obtain additional external data
- permission to contact an executor
- permission to create an applicable patch

The External Advisory Reviewer must disclose when the supplied material is
insufficient. It may recommend additional questions, but it cannot expand its
own scope.

## 5. Workflow Boundary

An `ADVISORY REVIEW` returns only to ChatGPT Review. ChatGPT Review evaluates the
opinion and determines the next valid artifact or receiver.

External Advisory neither automatically advances nor automatically blocks the
workflow. Mandatory advisory handling, unavailable-provider handling, and User
Decision overrides remain governed by
`acos-v2-external-advisory-trigger-policy.md`.

## 6. Scope Boundary

This authority description does not implement enforcement or create new
runtime capabilities. It does not modify the authority of ChatGPT Review,
Codex Executor, Automation, or User Decision.

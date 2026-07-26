# ACOS Execution Boundary Model

## 1. Purpose

The ACOS Execution Boundary Model defines how an authorized task scope limits
actual executor behavior.

Phase 2 established role capabilities and the task lifecycle. This Phase 3
model adds the governance boundary between a ready task and the activity
performed for that task.

```text
Governance Definition != Technical Enforcement
```

This document specifies boundary meaning, verification, violation handling, and
review responsibility. It does not implement runtime controls.

## 2. Core Principle

An Execution Boundary is the governance control boundary between Task
Authorization Scope and Actual Execution.

```text
Task Authorization
        |
        v
Execution Boundary
        |
        v
Execution Activity
        |
        v
Review Evidence
```

The boundary is derived from a materialized, ready task and any separately
required authorization. It cannot be expanded by executor preference,
technical access, successful command execution, or an advisory recommendation.

A role capability states what a role may be eligible to attempt. The Execution
Boundary states what that role may attempt for one governed task.

## 3. Boundary Source And Identity

The authoritative boundary must be traceable to:

```text
task_id
task_artifact_path
task_content_digest
project
receiver
allowed_files
allowed_actions
allowed_commands or command classes
required_output
forbidden_actions
applicable decision or user authorization
```

The boundary is valid only while these references remain consistent. A change
to the materialized task content, project, receiver, allowed scope, or required
authorization requires renewed validation before execution continues.

An authorization for one task, project, path, action, or lifecycle step does
not transfer to another.

## 4. Boundary Dimensions

The Execution Boundary has four required dimensions. Every intended operation
must satisfy all applicable dimensions.

### 4.1 File Boundary

The File Boundary identifies where changes may occur and what kind of change is
allowed.

It should define:

- repository or managed project root
- exact allowed files or bounded path patterns
- permitted change types: create, modify, move, rename, or delete
- explicitly excluded files and directories
- treatment of generated, temporary, cache, or untracked files
- cross-project restrictions

Permission to modify one path does not authorize modification of a parent,
sibling, destination, linked target, or similarly named path. Moving or
renaming a file requires authority for both its source and destination.

If the task authorizes only a new file, existing files remain outside the File
Boundary.

### 4.2 Action Boundary

The Action Boundary identifies the governance actions allowed for the current
task.

Actions are independent:

```text
read
test
create
modify
move
delete
stage
commit
push
release
```

Authority for one action does not imply authority for another. In particular,
edit, stage, commit, push, and release remain separately governed actions.

The executor must not infer an action from a broad objective such as "finish,"
"publish," or "sync." The action must be explicitly available under the ready
task and any required decision or user authorization.

### 4.3 Command Boundary

The Command Boundary identifies which commands or command classes may be run,
for what purpose, and with what permitted side effects.

It should constrain:

- command purpose
- target project and working directory
- path arguments
- expected local side effects
- whether network access is allowed
- whether external systems may be contacted
- whether a command is inspection, validation, mutation, or publication
- commands or patterns that are explicitly forbidden

A command is not authorized merely because its intended file output is within
the File Boundary. The command itself and its side effects must also fit the
Action and Command Boundaries.

Unexpected command prerequisites, prompts, generated files, network access, or
repository mutations require execution to stop unless already covered.

### 4.4 Output Boundary

The Output Boundary identifies the artifacts and reports that the task may
produce.

It should define:

- required artifact type
- allowed output files and locations
- expected format and required fields
- intended receiver and next receiver
- validation evidence to report
- whether a `RESULT` or `BLOCKED RESULT` is required
- whether staging, commit, push, or publication is excluded

A correct implementation with an unauthorized output remains a boundary
violation. Producing additional files, artifacts, decisions, or workflow state
changes is not allowed unless they are explicitly included.

## 5. Authorized Scope And Scope Drift

### 5.1 Authorized Scope

Authorized Scope is the intersection of all active boundary dimensions:

```text
Authorized Scope
    =
File Boundary
    AND
Action Boundary
    AND
Command Boundary
    AND
Output Boundary
    AND
Task State / Required Authorization
```

The most restrictive applicable rule controls. Missing permission is not
permission.

### 5.2 Actual Change

Actual Change includes all observable task effects, not only the intended
document or code diff. It may include:

- created, modified, moved, renamed, or deleted files
- index, branch, commit, tag, or remote-reference changes
- generated caches, logs, build artifacts, or temporary files
- commands and tests executed
- network or external-system effects
- artifacts and workflow outputs produced

### 5.3 Boundary Outcomes

`PASS`:

```text
Every Actual Change is within Authorized Scope.
```

Conceptually:

```text
Actual Change is a subset of Authorized Scope.
```

`VIOLATION`:

```text
At least one Actual Change is outside Authorized Scope.
```

A partly compliant execution is still a violation when any effect is outside
the boundary. A beneficial or harmless-looking extra change is not exempt.

### 5.4 Scope Drift

Scope Drift occurs when intended or actual execution moves beyond, differs
from, or cannot be proven to remain within Authorized Scope.

Examples include:

- touching an unlisted file
- using an unapproved mutating action
- running a command with undeclared side effects
- producing an additional artifact
- mixing another workstream into the task
- inferring commit or push authority from edit authority
- continuing after the materialized task digest changes

Scope Drift cannot be cured by the executor retroactively broadening its own
interpretation of the task.

## 6. Boundary Verification

Boundary Verification compares the ready task and active authorization with
planned and actual execution.

### 6.1 Before Execution

The executor verifies:

1. The task is `TASK_READY`.
2. The task ID, artifact path, content digest, project, and receiver match the
   ready handoff.
3. Allowed files, actions, commands, outputs, and forbidden areas are explicit.
4. Required decisions or user authorizations are active.
5. Repository or project state does not contain an unexplained conflict with
   the task boundary.
6. The planned execution fits every boundary dimension.

If any check is missing, ambiguous, stale, or contradictory, execution does not
start.

### 6.2 During Execution

The executor continuously treats the verified boundary as fixed.

If actual work reveals a required path, action, command, output, or side effect
outside the boundary, the executor must stop. It must not perform the extra
action first and request approval afterward.

### 6.3 After Execution

The executor compares Actual Change with Authorized Scope and reports:

- created, modified, moved, renamed, and deleted files
- commands and validations executed
- generated or cleaned side effects
- output artifacts
- forbidden-area checks
- repository status
- whether stage, commit, push, release, or external action occurred
- any unresolved ambiguity or deviation

The executor then produces `RESULT` or `BLOCKED RESULT` for ChatGPT Review.
Execution success does not constitute acceptance.

## 7. Role Boundary

### 7.1 `CHATGPT_REVIEW`

ChatGPT Review:

- defines Task Authorization Scope
- validates readiness and intended boundary
- reviews Actual Change and boundary evidence
- determines whether findings require acceptance, rework, or blocking
- issues or routes the next governed decision

ChatGPT Review does not create executor evidence or claim unverified repository
effects.

### 7.2 `CODEX_EXECUTOR`

Codex Executor:

- consumes the verified ready task
- plans and executes only within the boundary
- stops when the boundary is insufficient or contradicted
- reports Actual Change and validation evidence
- produces `RESULT` or `BLOCKED RESULT`

Codex Executor does not define or expand its own executable scope, approve its
own result, or infer later Git authority.

### 7.3 `EXTERNAL_ADVISORY`

External Advisory:

- observes supplied material
- identifies boundary risks or inconsistencies
- provides independent, non-binding recommendations

External Advisory has Risk Observation Only. It does not define scope, grant
authority, execute work, transition state, approve a result, or issue the final
decision.

## 8. Fail-Closed Handling

The Execution Boundary fails closed when:

- scope is missing or ambiguous
- boundary dimensions conflict
- task identity or digest does not match
- receiver or project is uncertain
- required authorization is absent, stale, or mismatched
- planned or actual effects exceed the boundary
- an unexpected dirty worktree or unrelated workstream creates attribution risk
- command side effects cannot be bounded
- required output does not match the task
- post-execution evidence is incomplete

The required response is:

```text
STOP
  |
  v
BLOCKED RESULT
  |
  v
CHATGPT REVIEW
```

Fail-closed handling retains the last verified task state. It does not authorize
cleanup, rollback, file restoration, scope expansion, or another repository
operation. Any such action requires its own governed instruction.

An External Advisory finding may inform ChatGPT Review, but it does not
automatically block or advance the lifecycle.

## 9. Relationship To Capability And State Models

The Capability Model answers:

```text
What kind of governance action may this role be eligible to attempt?
```

The Task State Machine answers:

```text
Is the task in a verified state that may permit execution?
```

The Execution Boundary Model answers:

```text
What exactly may the named executor do for this ready task?
```

All three conditions are required. None substitutes for the others.

## 10. Non-Implementation Boundary

This model is a governance specification only. It does not create or modify:

- runtime enforcement
- filesystem sandboxing
- operating-system permissions
- an authorization service
- a policy engine or validator
- an orchestrator
- a database or durable state machine
- a Git wrapper or hook
- automatic blocking
- authenticated runtime identity
- project-instance behavior

It does not grant permission to modify files, run commands, stage, commit, push,
release, or contact external systems. Those actions remain subject to their own
task state, capability, scope, and authorization requirements.

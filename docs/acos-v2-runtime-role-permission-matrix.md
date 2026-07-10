# ACOS v2.0 Runtime Role Permission Matrix

## 1. Purpose And Relationship To TASK_040

This document is the role-level permission matrix for ACOS v2.0 runtime isolation.

```text
TASK_040 defines runtime isolation architecture.
TASK_041 defines the role-level permission matrix.
```

TASK_040 established the runtime identities, isolation goals, Git operation separation, and auditability model. This document refines those concepts into permissions that can later be checked, implemented, and audited.

This document does not change the ACOS v1.5 authority model. It does not implement runtime controls, containers, credentials, hooks, wrappers, or launchers.

## 2. Normative Principles

The permission model follows these principles:

1. Default deny: a permission not explicitly granted is forbidden.
2. Runtime identity is independent of model or provider.
3. Artifact creation authority does not imply file, Git, routing, or acceptance authority.
4. Read access does not imply authority to consume an artifact or act on it.
5. Edit, stage, commit, push, and release are separate permissions.
6. Push requires authorization separate from commit authorization.
7. No runtime may approve its own output.
8. Runtime policy changes are governance-only.
9. Temporary permissions must be task-scoped, time-bounded, and auditable.
10. A denied operation must fail closed and produce an auditable record.

## 3. Runtime Identity And Model Provider

```text
Runtime Identity != Model Name
```

A runtime identity defines:

- authority boundaries
- filesystem capabilities
- Git capabilities
- artifact production permissions
- artifact consumption permissions
- audit identity

A model or provider is the implementation that supplies reasoning or generation capability, such as ChatGPT, Codex, Gemini, or another provider.

Changing a provider must not silently change runtime permissions. A provider may act only through the runtime identity assigned to it.

## 4. Runtime Identities

### 4.1 ChatGPT Review Runtime

Primary responsibilities:

- create bounded `TASK` artifacts
- create `REVIEW` artifacts
- create `DECISION` artifacts
- create or review `GOVERNANCE PROPOSAL` artifacts
- create non-authorizing `CONTEXT PACK` artifacts
- route accepted work to the next authorized receiver

It must not create Codex `RESULT` or `BLOCKED RESULT` artifacts, impersonate another producer, or directly modify business project code.

### 4.2 Codex Executor Runtime

Primary responsibilities:

- consume authorized `TASK` and `CONTEXT PACK` artifacts
- edit only authorized paths
- run authorized commands and tests
- create `RESULT` or `BLOCKED RESULT` artifacts
- perform separately authorized Git operations

It must not create `REVIEW` or `DECISION`, write decisions, approve its own output, or expand task scope.

### 4.3 External Advisory Runtime

Primary responsibilities:

- perform read-only analysis
- create non-binding `ADVISORY REVIEW`
- return advisory output to ChatGPT Review

It must not edit project files, execute Git operations, create executable tasks, create results, make decisions, or route work directly to Codex Executor.

### 4.4 Automation Runtime

Primary responsibilities:

- run deterministic or scheduled checks
- create `RESULT` or `RECORD` artifacts
- append logs and audit events
- report validation outcomes to an authorized receiver

It must not create `REVIEW`, `ADVISORY REVIEW`, or `DECISION`, and it must not accept its own output.

### 4.5 Planned Runtime Identities

The following identities are reserved as design candidates only:

- Release Runtime
- ACOS Maintainer Runtime

They are not implemented, active, or authorized by this document. They receive no permissions from the matrices below. Introducing either identity requires a separate governance proposal, review, task, implementation result, and decision.

## 5. Permission Vocabulary

Artifact permissions use these values:

- `create`: may produce the artifact under its own runtime identity.
- `read`: may inspect the artifact but may not act on it solely because it was read.
- `consume`: may use the artifact as input to an authorized next lifecycle step.
- `forbidden`: may not create or consume the artifact; access is denied unless a separate `read` permission is stated.
- `governance-only`: requires an accepted governance chain and does not itself authorize execution.

Operation and directory permissions use these additional values:

- `task-scoped`: allowed only for paths and actions named in a valid task.
- `decision-gated`: requires a valid review and decision for the specific operation.
- `separate authorization`: requires authorization distinct from the preceding operation.
- `append`: may add records but may not rewrite or delete existing records.
- `governance-only write`: may write only through an accepted governance workflow.
- `no access`: may neither read nor write under the normal runtime profile.

Composite values such as `create, read` grant only the listed permissions. All omitted permissions remain denied.

## 6. Artifact Permission Matrix

| Artifact | ChatGPT Review Runtime | Codex Executor Runtime | External Advisory Runtime | Automation Runtime |
| --- | --- | --- | --- | --- |
| `TASK` | create, read | read, consume | read, consume only for an explicit advisory request | read, consume only for an explicit automation task |
| `RESULT` | read, consume | create, read | read only when routed for advice | create, read |
| `BLOCKED RESULT` | read, consume | create, read | read only when routed for advice | read only; create forbidden |
| `ADVISORY REVIEW` | read, consume | read only; direct advisory-to-Codex routing forbidden | create, read | read only |
| `REVIEW` | create, read | read, consume | read only | read, consume only as an instruction input |
| `DECISION` | create, read | read, consume | read only | read, consume only for an authorized action |
| `RECORD` | create, read, consume | read | read | create, read |
| `GOVERNANCE PROPOSAL` | governance-only create, read, consume | read only; execution forbidden | read, consume only when ChatGPT requests advisory review | read only |
| `CONTEXT PACK` | create, read | read, consume | read, consume when explicitly routed | read, consume when explicitly routed |

### 6.1 Artifact Matrix Constraints

1. Codex Executor cannot create `REVIEW` or `DECISION`.
2. External Advisory Runtime cannot create `TASK`, `RESULT`, `BLOCKED RESULT`, `REVIEW`, or `DECISION`.
3. Automation Runtime cannot create `REVIEW`, `ADVISORY REVIEW`, or `DECISION`.
4. ChatGPT Review Runtime cannot create Codex `RESULT` or `BLOCKED RESULT`.
5. `ADVISORY REVIEW` must return to ChatGPT Review and cannot route directly to Codex Executor.
6. `GOVERNANCE PROPOSAL` cannot authorize edits, commits, pushes, releases, or final decisions.
7. `CONTEXT PACK` is an auxiliary context artifact. It cannot replace `TASK`, `REVIEW`, `DECISION`, or User Decision.
8. `BLOCKED RESULT` is a constrained executor outcome and does not authorize the executor to resolve the blocker by expanding scope.
9. Artifact producer metadata must match the authenticated runtime identity.
10. Consumption is allowed only when `TO`, `NEXT RECEIVER`, project, task, and authority metadata are valid.

## 7. Operation Permission Matrix

| Operation | ChatGPT Review Runtime | Codex Executor Runtime | External Advisory Runtime | Automation Runtime |
| --- | --- | --- | --- | --- |
| read context | allowed | allowed | task-scoped read | task- or policy-scoped read |
| write task | allowed | forbidden | forbidden | forbidden |
| edit project files | forbidden | task-scoped | forbidden | forbidden |
| run tests | forbidden | task-scoped | forbidden | task- or policy-scoped |
| create result | forbidden | allowed for `RESULT` and `BLOCKED RESULT` | forbidden | allowed for `RESULT` only |
| create advisory review | forbidden | forbidden | allowed | forbidden |
| create review | allowed | forbidden | forbidden | forbidden |
| create decision | allowed | forbidden | forbidden | forbidden |
| create record | allowed | forbidden | forbidden | allowed |
| stage files | forbidden | decision-gated and path-scoped | forbidden | forbidden |
| commit | forbidden | decision-gated; scope must match reviewed files | forbidden | forbidden |
| push | authorization owner only; no direct Git execution | separate authorization after commit | forbidden | forbidden |
| release | authorization owner only; no direct release execution | separate release authorization; not implied by push | forbidden | forbidden |
| modify ACOS core rules | governance-only authorization; no business-code edit authority | governance-only and task-scoped execution | forbidden | forbidden |
| modify runtime policy | governance-only authorization | governance-only and task-scoped execution | forbidden | forbidden |

### 7.1 Git Separation Rules

The following permissions are independent:

```text
edit != stage != commit != push != release
```

Required controls:

1. Edit authority must name the project and allowed paths.
2. Stage authority must be limited to reviewed paths.
3. Commit authority requires a valid review and decision.
4. Push authority must be separate from commit authority.
5. Release authority must be separate from push authority.
6. No runtime may perform `edit -> commit -> push` in one unreviewed chain.
7. A runtime that performed an operation cannot treat its own result as acceptance.
8. Failed or denied Git operations must not trigger automatic pull, rebase, force push, or scope expansion.

## 8. Directory Permission Matrix

This matrix defines the intended baseline profile. Temporary grants must be narrower than the associated task and must be recorded in the audit trail.

| Path | ChatGPT Review Runtime | Codex Executor Runtime | External Advisory Runtime | Automation Runtime |
| --- | --- | --- | --- | --- |
| `.codex-coordination/inbox/` | governance-only write | read | task-scoped read | append |
| `.codex-coordination/outbox/` | read | task-scoped write | no access | append |
| `.codex-coordination/reviews/` | write | read | task-scoped write for `ADVISORY REVIEW` only | read |
| `.codex-coordination/decisions/` | governance-only write | read | no access | read |
| `.codex-coordination/templates/` | governance-only write | read | read | read |
| `docs/` | governance-only write | task-scoped write | read | read |
| `scripts/` | governance-only write | read | read | read |
| `.githooks/` | governance-only write | read | no access | read |
| `agents/` | governance-only write | read | read | read |
| `skills/` | governance-only write | read | read | read |
| business project code | no access | task-scoped write | read | task- or policy-scoped read |

### 8.1 Directory Matrix Constraints

1. `write` never includes delete, move, or permission changes unless explicitly granted.
2. `task-scoped write` is restricted to the project and paths in the accepted task.
3. `governance-only write` requires a governance proposal, ChatGPT Review, a bounded task, executor result, and final decision as applicable.
4. Codex Executor may read decisions but cannot create or alter them.
5. External Advisory Runtime may write only its own advisory artifact in the designated review path.
6. Automation Runtime may append deterministic records but cannot rewrite task, review, or decision history.
7. Business project code is not ACOS core. Access must be granted per project instance and per task.
8. Core source maintenance that exceeds these baseline profiles requires a future ACOS Maintainer Runtime proposal; this document does not activate that runtime.

## 9. Violation Examples And Expected Handling

| Violation | Why Forbidden | Expected Handling |
| --- | --- | --- |
| Codex writes `DECISION` | Codex Executor may create only `RESULT` or `BLOCKED RESULT`; a decision would be self-approval or producer spoofing. | Reject the artifact, deny the decisions-path write, record an authority violation, and route a blocked result to ChatGPT Review. |
| Codex stages unrelated files | Stage permission is path-scoped to files reviewed and authorized for commit. | Reject the staging operation, leave unrelated files unstaged, record the attempted path set, and require a corrected task or User Decision. |
| External Advisory edits project code | External Advisory Runtime is read-only and has no edit or Git authority. | Deny the filesystem write, preserve the project unchanged, record the violation, and return advisory output to ChatGPT Review only. |
| Automation approves its own output | Automation cannot create `REVIEW` or `DECISION` and cannot be its own acceptance receiver. | Mark the approval artifact invalid, retain the automation result as unaccepted, and route it to ChatGPT Review. |
| ChatGPT Review writes Codex `RESULT` | The producer would not match the authenticated runtime identity and would forge executor evidence. | Reject the artifact as producer spoofing and require an actual Codex Executor `RESULT` or `BLOCKED RESULT`. |
| Any runtime performs `edit -> commit -> push` without review | The chain collapses separate permissions and bypasses independent review and push authorization. | Stop before commit or push, record the denied transition, require review and decision, then require separate push authorization. |

Additional fail-closed examples:

- A missing runtime identity must block artifact creation and Git operations.
- A mismatch between `PRODUCER` and authenticated runtime must invalidate the artifact.
- A valid artifact sent to an unauthorized receiver must not enter the execution chain.
- An expired or already-consumed capability must not be reusable.
- A governance proposal sent directly to Codex must be treated as non-executable.

## 10. Enforcement Mapping

The permission matrix is intended to map to future controls as follows. These controls are design targets, not implementations created by TASK_041.

| Policy Area | Primary Enforcement | Supporting Enforcement | Audit Evidence |
| --- | --- | --- | --- |
| Runtime identity binding | runtime launcher | isolated credentials and environment profile | runtime identity, launch event, profile identifier |
| Artifact creation authority | artifact linter | producer signature or runtime credential | artifact type, producer, validation result |
| Artifact routing | artifact linter | runtime launcher receiver policy | receiver, next receiver, routing decision |
| Directory read/write boundary | filesystem permissions | read-only mounts and scoped workspaces | path, operation, allow or deny result |
| Task-scoped project edits | filesystem permissions | runtime launcher capability grant | task ID, allowed paths, changed paths |
| Stage and commit scope | Git wrapper | artifact linter and reviewed file manifest | staged paths, commit hash, decision ID |
| Separate push authorization | Git wrapper | human decision gate | push target, authorization ID, commit hash |
| Release separation | Git or release wrapper | human decision gate | release target, version, authorization ID |
| Self-approval prevention | artifact linter | receiver policy and human decision gate | producer, reviewer, decision maker |
| Append-only history | audit trail | filesystem append controls | event ID, prior event link, write result |

### 10.1 Enforcement Components

Future implementation may use:

- filesystem permissions for static path isolation
- a Git wrapper for stage, commit, push, and release gates
- the artifact linter for metadata, authority, and routing validation
- a runtime launcher for authenticated runtime identity and scoped capabilities
- an audit trail for append-only event evidence
- a human decision gate for credentials, push, release, and exceptional authorization

No component may infer missing authorization. If an authorization artifact is absent, invalid, expired, mismatched, or out of scope, the operation must be denied.

## 11. Audit Requirements

Every permission check should be traceable to the TASK_040 audit model, including:

- event ID
- task ID
- artifact type
- producer and receiver
- next receiver
- authenticated runtime identity
- project and path scope
- requested operation
- authorization or decision ID
- commit hash or push target when applicable
- allow, deny, blocked, or failed result
- timestamp

Audit records do not grant authority and do not replace `REVIEW`, `DECISION`, or User Decision.

## 12. Non-Implementation Boundary

TASK_041 creates documentation only. It does not create or modify:

- runtime code
- container configuration
- Dockerfile
- `docker-compose.yml`
- API keys or provider credentials
- runtime launcher
- Git wrapper
- audit service
- artifact linter behavior
- pre-commit hook behavior
- ACOS v1.5 role definitions
- business project files

Implementation requires separate tasks and reviews.

## 13. Summary

The ACOS v2.0 permission model separates runtime identity from provider identity, defaults to denial, and assigns artifact, operation, directory, Git, and governance permissions independently.

The matrix preserves the current authority model:

```text
ChatGPT Review Runtime -> TASK, REVIEW, DECISION, governance authority
Codex Executor Runtime -> authorized execution, RESULT, BLOCKED RESULT
External Advisory Runtime -> read-only analysis, ADVISORY REVIEW
Automation Runtime -> deterministic RESULT, RECORD, and audit support
```

The next design tasks may refine filesystem enforcement, Git operation separation, audit trail structure, and local prototype planning. This document does not authorize those tasks or their implementation.

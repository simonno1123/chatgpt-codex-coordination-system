# ACOS v2.0 Runtime Isolation Architecture

## 1. Purpose

ACOS v2.0 defines the runtime isolation architecture for moving ACOS from policy-level enforcement toward technical separation.

ACOS v1.5 provides:

```text
Policy + Linter + Pre-commit Enforcement
```

ACOS v2.0 targets:

```text
Runtime Isolation + Permission Separation + Auditability
```

The v1.5 goal is:

```text
Violation can be detected.
```

The v2.0 goal is:

```text
Violation should be technically impossible or strongly isolated.
```

This document is architecture only. It does not implement containers, hooks, API clients, runtime services, or business project migration.

## 2. Runtime Identity Model

ACOS v2.0 separates roles by runtime identity.

Runtime is not the same as model.

```text
Runtime != Model
Runtime = execution identity / permission boundary
```

A model provider may change without changing the ACOS authority model. A runtime identity defines what that execution context may read, write, invoke, and report.

ACOS v2.0 defines four runtime identities:

1. ChatGPT Review Runtime
2. Codex Executor Runtime
3. External Advisory Runtime
4. Automation Runtime

## 3. Runtime Roles And Authority

### ChatGPT Review Runtime

Allowed:

- produce `TASK`
- produce `REVIEW`
- produce `DECISION`
- review `GOVERNANCE PROPOSAL`
- route accepted work to the next authorized receiver

Forbidden:

- directly modify business project code
- forge Codex `RESULT`
- forge Codex `BLOCKED RESULT`
- forge External Advisory `ADVISORY REVIEW`
- bypass the required receiver chain

### Codex Executor Runtime

Allowed:

- execute authorized tasks
- modify authorized paths
- run authorized commands and tests
- produce `RESULT`
- produce `BLOCKED RESULT`

Forbidden:

- produce `REVIEW`
- produce `DECISION`
- write `.codex-coordination/decisions/`
- self-approve or self-accept work
- expand task scope without a new authorized task
- perform unreviewed edit to commit to push chains

### External Advisory Runtime

Allowed:

- perform read-only analysis
- produce `ADVISORY REVIEW`
- provide non-binding risk observations and second opinions

Forbidden:

- modify code or project files
- execute Git operations
- produce `TASK`
- produce `RESULT`
- produce `BLOCKED RESULT`
- produce `DECISION`
- route directly to Codex Executor
- bypass ChatGPT Review

### Automation Runtime

Allowed:

- produce `RESULT`
- produce `RECORD`
- run scheduled checks
- record logs and audit events
- report deterministic validation outcomes

Forbidden:

- produce `REVIEW`
- produce `DECISION`
- self-approve automated output
- change role authority rules
- silently modify task routing

## 4. Filesystem Isolation Model

The runtime isolation model should use separate filesystem permissions for each runtime identity.

Permission labels:

- `read`: runtime may read the path.
- `write`: runtime may write the path when authorized.
- `no access`: runtime should not read or write the path.
- `governance-only write`: runtime may write only governance artifacts authorized by ChatGPT Review or User Decision.

Initial permission matrix:

| Path | ChatGPT Review Runtime | Codex Executor Runtime | External Advisory Runtime | Automation Runtime |
| --- | --- | --- | --- | --- |
| `.codex-coordination/inbox/` | governance-only write | read | read | write |
| `.codex-coordination/outbox/` | read | write | no access | write |
| `.codex-coordination/reviews/` | write | read | write | read |
| `.codex-coordination/decisions/` | write | read | no access | read |
| `.codex-coordination/templates/` | governance-only write | read | read | read |
| `scripts/` | governance-only write | read | read | read |
| `.githooks/` | governance-only write | read | no access | read |
| `docs/` | governance-only write | authorized write | read | read |
| business project code | no access | authorized write | read | read |

Notes:

- Codex Executor Runtime may write business project code only when a task explicitly authorizes the project, path, mode, and forbidden actions.
- ChatGPT Review Runtime owns governance decisions, not code edits.
- External Advisory Runtime should be read-only except for advisory review output paths.
- Automation Runtime may write logs and deterministic records, not decisions.
- `governance-only write` does not mean unrestricted write access. It requires a valid governance task or decision artifact.

## 5. Git Operation Separation Model

ACOS v2.0 separates Git operations into distinct authority layers.

Operation categories:

1. `diff/test`
2. `edit`
3. `commit`
4. `push`
5. `release`

### diff/test

Allowed when a task authorizes read-only inspection or validation.

Typical runtime:

- Codex Executor Runtime
- Automation Runtime

### edit

Allowed only when a task explicitly authorizes the target paths and mode.

Typical runtime:

- Codex Executor Runtime

### commit

Allowed only when the edited scope has been reviewed and a valid `DECISION` authorizes commit.

Typical runtime:

- Codex Executor Runtime

### push

Push requires separate User Decision or ChatGPT Review authorization.

Push must not be implied by commit authorization.

### release

Release requires explicit release authorization and should remain separate from ordinary push authorization.

Release may require additional checks, tags, changelog review, or user approval.

### Chain Separation Rule

No role may perform:

```text
edit -> commit -> push
```

in one unreviewed chain.

Each transition must be authorized by the appropriate artifact and receiver:

```text
TASK -> RESULT -> REVIEW -> DECISION -> next authorized operation
```

## 6. Audit Trail Model

ACOS v2.0 audit trail records runtime events for traceability.

Audit trail does not replace `DECISION`. It records what happened after authority was granted or denied.

Every event should include:

- `event_id`
- `task_id`
- `artifact_type`
- `producer`
- `receiver`
- `next_receiver`
- `runtime_identity`
- `project`
- `timestamp`
- `decision_id`
- `commit_hash`
- `push_target`
- `result`

Optional implementation fields may include:

- command class
- changed path summary
- linter result
- hook result
- sandbox profile
- runtime image or environment identifier
- error summary

Audit events should be append-only. Corrections should be new events, not silent rewrites.

## 7. v2.0 First Phase Exclusions

This architecture document does not authorize implementation.

The first v2.0 phase does not include:

- real multi-container deployment
- real API key management
- automatic ChatGPT, Codex, Gemini, or model-provider API calls
- Web UI
- cloud permission systems
- business project migration
- Dockerfile creation
- `docker-compose.yml` creation
- runtime secrets management
- changes to ACOS v1.5 linter behavior
- changes to ACOS v1.5 pre-commit hook behavior

Any implementation requires a separate task, review, and decision.

## 8. Future Task Candidates

The following tasks may be considered after this architecture is reviewed.

Do not create these task files from this document alone.

```text
TASK_041 Runtime Role Permission Matrix
TASK_042 Filesystem Permission Model
TASK_043 Git Operation Separation Policy
TASK_044 Audit Trail Specification
TASK_045 Local Runtime Prototype Plan
```

## 9. Summary

ACOS v1.5 makes violations visible before commit.

ACOS v2.0 should make role drift, unauthorized writes, forged artifacts, and unreviewed Git chains technically difficult or impossible through runtime identity separation, filesystem permissions, Git operation separation, and append-only auditability.

The immediate next step is review of this architecture document, not implementation.

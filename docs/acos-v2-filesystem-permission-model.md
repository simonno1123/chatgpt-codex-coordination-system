# ACOS v2.0 Filesystem Permission Model

## 1. Scope And Purpose

This document defines the ACOS v2.0 filesystem permission model for runtime isolation.

Its purpose is to translate ACOS role authority into path-level read and write boundaries that can later be implemented and audited.

The target is:

```text
Policy authority
        +
Runtime identity
        +
Canonical project and path scope
        +
Validated TASK and DECISION
        =
Narrow filesystem capability
```

This document is design only. It does not change permissions on the local machine, implement a sandbox, create containers, or modify ACOS v1.5 rules.

## 2. Relationship To TASK_040 And TASK_041

```text
TASK_040 defines runtime isolation architecture.
TASK_041 defines the role-level permission matrix.
TASK_042 defines the filesystem permission model.
```

TASK_042 refines the directory matrix introduced by TASK_040 and TASK_041. It does not expand any runtime's artifact authority or Git authority.

If this document appears to conflict with the established ACOS authority model, the more restrictive interpretation applies and the conflict must return to ChatGPT Review as a governance issue.

## 3. Filesystem Permission Principles

### 3.1 Default Deny

All filesystem access is denied unless the runtime identity, canonical project root, path class, operation, and authorization are explicitly valid.

Missing or ambiguous permission must fail closed.

### 3.2 Runtime Identity Is Not A Model Name

Filesystem access is granted to an authenticated runtime identity, not to a provider name.

Changing ChatGPT, Codex, Gemini, or another provider must not change filesystem permissions.

### 3.3 Canonical Root First

Every path must be resolved against one canonical project root before access is evaluated.

Relative paths, symbolic links, mount points, aliases, and parent-directory references must not escape the authorized root.

### 3.4 Least Privilege

A capability must be limited by:

- runtime identity
- project root
- allowed path or path set
- operation type
- task ID
- decision or authorization ID
- validity window
- expected output

Broad repository-wide write access is not the default.

### 3.5 Read Does Not Imply Write

Read access does not permit create, modify, delete, move, rename, chmod, ownership changes, staging, commit, or push.

### 3.6 Write Does Not Imply Git Authority

Filesystem write authority is separate from:

- staging
- commit
- push
- release

A runtime that may edit a file may still be forbidden from staging or committing it.

### 3.7 Artifact Authority Still Applies

Directory access does not override artifact authority.

For example, read or write access to a coordination directory never permits:

- Codex Executor to create `REVIEW` or `DECISION`
- External Advisory Runtime to create `TASK`, `RESULT`, or `DECISION`
- Automation Runtime to create `REVIEW` or `DECISION`
- ChatGPT Review Runtime to create Codex `RESULT` or `BLOCKED RESULT`

### 3.8 Filesystem Isolation Does Not Replace Review

Filesystem controls prevent or constrain access. They do not replace:

- ChatGPT Review
- ChatGPT Decision
- User Decision
- artifact validation
- scope review
- Git authorization

## 4. Permission Vocabulary

The filesystem model uses these permission values:

- `read`: may inspect existing content within the permitted root.
- `write`: may create or modify role-owned artifacts in the designated path.
- `append-only`: may add new records but may not replace, truncate, rename, or delete existing records.
- `task-scoped write`: may create or modify only paths named by a valid task and activated authorization.
- `governance-only write`: may write only through an accepted ACOS governance workflow.
- `no access`: may neither read nor write under the normal runtime profile.

Additional qualifiers:

- `explicit local-mode grant`: available only when User Decision enables local ACOS instance mode for the named instance.
- `read only`: shorthand for `read` with every write operation denied.
- `role-owned artifact only`: write access is restricted to artifact types the runtime may produce.

Permission values do not include delete, move, rename, link creation, chmod, chown, mount, Git staging, commit, push, or release unless separately authorized.

## 5. Directory Classification

### 5.1 Coordination Input Paths

Examples:

- `.codex-coordination/inbox/`

Purpose:

- hold bounded tasks or coordination inputs
- provide read-only execution context to receiving runtimes

These paths are not general-purpose workspaces.

### 5.2 Coordination Output Paths

Examples:

- `.codex-coordination/outbox/`

Purpose:

- hold `RESULT`, `BLOCKED RESULT`, or authorized automation output

An output path does not permit self-review or decision creation.

### 5.3 Review And Decision Paths

Examples:

- `.codex-coordination/reviews/`
- `.codex-coordination/decisions/`

These are authority-sensitive paths.

Review writes are limited by producer authority. Decision writes are governance-only and must not be available to Codex Executor, External Advisory Runtime, or Automation Runtime.

### 5.4 Governance Template Paths

Examples:

- `.codex-coordination/templates/`

Templates define artifact shape and routing expectations. They are protected ACOS core material and require governance-only maintenance.

### 5.5 ACOS Core Documentation Paths

Examples:

- `docs/`
- root governance documents

Documentation may define architecture, policy interpretation, onboarding, or operational boundaries. Writes require explicit ACOS scope and must not be authorized by a business-instance task.

### 5.6 ACOS Enforcement Paths

Examples:

- `scripts/`
- `.githooks/`

These paths may affect enforcement. They are protected core paths and require governance-only maintenance.

### 5.7 ACOS Role And Skill Paths

Examples:

- `agents/`
- `skills/`

These paths affect task generation, execution coordination, review behavior, and role boundaries. They are protected core paths.

### 5.8 Business Project Code

Business project code belongs to a project instance, not to ACOS core.

It may be written only by Codex Executor under a bounded project-specific task and authorization. Domain code, tests, documentation, configuration, skills, MCP integrations, and project assets remain inside the instance.

### 5.9 Instance-Local Coordination Paths

Example:

- `<instance-root>/.codex-coordination/`

An instance-local coordination directory is not ACOS core by default.

Its presence does not:

- activate local ACOS instance mode
- make the instance an ACOS authority source
- copy ACOS governance into the instance
- authorize runtime access
- override ACOS role boundaries
- require the directory to be tracked, deleted, or migrated

Without explicit User Decision enabling local ACOS instance mode, the directory is treated as instance-local data or history under a default-deny profile.

## 6. Runtime-To-Directory Permission Matrix

The matrix below defines the intended baseline. A narrower task may reduce access further. It may not silently expand access.

| Path | ChatGPT Review Runtime | Codex Executor Runtime | External Advisory Runtime | Automation Runtime |
| --- | --- | --- | --- | --- |
| `.codex-coordination/inbox/` | governance-only write, role-owned `TASK` only | read | task-scoped read | append-only for authorized input records |
| `.codex-coordination/outbox/` | read | task-scoped write, `RESULT` or `BLOCKED RESULT` only | no access | append-only, `RESULT` or `RECORD` only |
| `.codex-coordination/reviews/` | write, role-owned `REVIEW` only | read | task-scoped write, `ADVISORY REVIEW` only | read; write forbidden |
| `.codex-coordination/decisions/` | governance-only write, role-owned `DECISION` only | read; write forbidden | no access | read; write forbidden |
| `.codex-coordination/templates/` | governance-only write | read | read | read |
| `docs/` | governance-only write | task-scoped write | read | read |
| `scripts/` | governance-only write | read | read | read |
| `.githooks/` | governance-only write | read | no access | read |
| `agents/` | governance-only write | read | read | read |
| `skills/` | governance-only write | read | read | read |
| business project code | no access | task-scoped write | read; write forbidden | task- or policy-scoped read; write forbidden |
| instance-local `.codex-coordination/` | read; governance-only write only with explicit local-mode grant | task-scoped read; task-scoped write only with explicit local-mode grant | no access by default; task-scoped read for advisory use | no access by default; append-only only with explicit local-mode grant |

### 6.1 Matrix Interpretation Rules

1. Codex Executor must never write `.codex-coordination/decisions/`.
2. External Advisory Runtime must never write business project code.
3. Automation Runtime must never write `REVIEW` or `DECISION` paths.
4. ChatGPT Review Runtime must never write Codex `RESULT` or `BLOCKED RESULT` artifacts.
5. Access to a directory is constrained by artifact producer authority.
6. `append-only` must reject truncate, overwrite, rename, and delete operations.
7. `task-scoped write` must reject paths not named by the validated task and decision.
8. `governance-only write` must reject business-instance tasks as authority sources.
9. No runtime may use a writable parent directory to bypass a protected child directory.
10. No runtime may use a symbolic link or alternate mount to reach a denied path.

## 7. Protected ACOS Core Paths

The following paths are protected ACOS core by default:

- `CODEX_WORKFLOW.md`
- `SCOPE_POLICY.md`
- `README.md` sections that define ACOS governance or authority
- `.codex-coordination/templates/`
- `docs/` architecture and governance documents
- `scripts/`
- `.githooks/`
- `agents/`
- `skills/`

Protected core rules:

1. A business project task cannot authorize writes to ACOS core.
2. An instance-local file cannot override an ACOS core rule.
3. Core writes require an ACOS project task, accepted governance basis, and applicable decision.
4. Core write scope must list exact files or a narrowly bounded path.
5. Core writes must return to ChatGPT Review before commit.
6. Core commit, push, and release remain separately authorized operations.
7. A provider change does not grant core write access.
8. A local ACOS instance mode decision does not turn the instance into the upstream ACOS source.

## 8. Project Instance Path Handling

### 8.1 External Instance Mode

External instance mode is the default.

ACOS generates and reviews artifacts from the ACOS governance context while Codex Executor operates inside the explicitly named business project root.

The instance task must identify:

- canonical project path
- project identity
- allowed paths
- forbidden paths
- operation mode
- expected output
- authority limit
- next receiver

ACOS core files are not copied into the business project.

### 8.2 Local ACOS Instance Mode

Local ACOS instance mode requires explicit User Decision for a named project.

Authorization must state:

- why local mode is required
- which local coordination paths may exist
- which runtime may read or write them
- whether records are tracked or remain local
- which upstream ACOS rules remain authoritative
- how local records are audited and retired

Local mode does not grant permission to copy or modify upstream ACOS core material unless separately authorized.

### 8.3 Instance-Local History

An instance-local `.codex-coordination/` directory may be retained as local history by User Decision.

When retained as local history:

- it is not an ACOS core source
- it does not authorize execution
- it need not be committed
- it must not be deleted or cleaned without authorization
- it must not be mixed into unrelated business commits
- it must not silently influence routing or runtime permissions

### 8.4 Cross-Project Access

A capability for one project must not be reusable in another project.

ACOS core and each project instance require separate canonical roots and separate path scopes. Cross-project moves, copies, links, or writes require explicit authorization naming both source and destination.

## 9. Write Authorization Rules

### 9.1 Two-Part Authorization

A runtime filesystem write capability must be backed by both:

1. a valid `TASK` that defines the exact project, operation, and path scope; and
2. an applicable `DECISION` or explicit authorization artifact that activates the write capability.

Role-owned governance artifact creation remains governed by artifact authority and routing. It does not grant broader project-file write access.

### 9.2 Required Authorization Fields

Before granting write access, the runtime controller must be able to validate:

- task ID
- decision or authorization ID
- producer
- receiver
- next receiver
- authenticated runtime identity
- canonical project root
- allowed path set
- forbidden path set
- operation type
- mode
- validity window
- expected result artifact

### 9.3 Operation-Specific Grants

Write grants must distinguish:

- create file
- modify file
- append file
- delete file
- move or rename file
- create directory
- change permissions
- create link

Authorization to create or modify does not authorize delete, move, rename, permission changes, or link creation.

### 9.4 Capability Lifetime

A write capability should expire when the earliest of these occurs:

- the task produces `RESULT` or `BLOCKED RESULT`
- the task validity window ends
- the decision is revoked
- the runtime exits
- the project root changes
- the path manifest changes
- a violation is detected

Capabilities must not be silently reused for a later task.

### 9.5 No Implied Escalation

The following must never imply broader write access:

- successful read access
- a clean Git status
- a prior accepted task
- a prior commit authorization
- provider authentication
- an advisory review
- an automation result
- an instance-local coordination directory

## 10. Path Resolution And Escape Prevention

Before every protected access, the future enforcement layer should validate:

1. The project root is canonical and exists.
2. The requested path resolves inside that root.
3. No `..` traversal escapes the root.
4. No symbolic link resolves to a denied path or another project.
5. No writable ancestor bypasses a protected child path.
6. Case normalization does not change the selected path.
7. Mount boundaries do not expose another project or secret store.
8. Generated or temporary files inherit the same scope.
9. Backup, swap, lock, and rename targets remain inside the allowed path set.
10. A path denied at validation cannot become writable through a fallback location.

The restrictive result applies when canonicalization is uncertain.

## 11. Violation Handling

Filesystem violations must fail closed.

Expected handling sequence:

```text
Requested access
        ↓
Validate runtime, task, decision, project, path, and operation
        ↓
Allow narrowly OR deny before mutation
        ↓
Record audit event
        ↓
Return RESULT or BLOCKED RESULT to ChatGPT Review
```

Required behavior:

1. Deny the operation before any partial write where technically possible.
2. Preserve the existing file and Git state.
3. Do not retry with broader permissions.
4. Do not change ownership or mode to bypass denial.
5. Do not redirect output to an unapproved path.
6. Do not auto-stage, auto-commit, auto-push, pull, rebase, or force push.
7. Record the requested path, canonical path, operation, runtime identity, task ID, decision ID, and denial reason.
8. Return a valid blocked or failure artifact to the authorized receiver.
9. Require ChatGPT Review or User Decision before any scope change.

### 11.1 Violation Examples

| Violation | Expected Handling |
| --- | --- |
| Codex Executor attempts to write `decisions/` | Deny before write, record role and path violation, return `BLOCKED RESULT` to ChatGPT Review. |
| External Advisory Runtime attempts to edit business code | Deny write, preserve the project, record the violation, allow only advisory output in its authorized review path. |
| Automation Runtime attempts to write `reviews/` or `decisions/` | Deny write and route its existing `RESULT` or `RECORD` to ChatGPT Review. |
| ChatGPT Review Runtime attempts to place a Codex `RESULT` in `outbox/` | Reject producer spoofing and require an authenticated Codex Executor result. |
| A business-instance task targets ACOS `scripts/` | Deny cross-project core write and require an ACOS governance task. |
| An instance-local `.codex-coordination/` is treated as ACOS core | Reject the authority assumption and require explicit local-mode User Decision. |
| A symbolic link points from an allowed path to `decisions/` | Resolve the canonical target, deny access, and record path-escape evidence. |
| A stale task capability is reused | Deny the write and require a new task and authorization. |

## 12. Audit Requirements

Every filesystem permission check should be auditable with:

- event ID
- task ID
- decision or authorization ID
- runtime identity
- producer identity
- project root
- requested path
- canonical path
- directory classification
- requested operation
- granted permission class
- allow or deny result
- timestamp
- resulting artifact ID
- related commit hash when applicable

Audit records do not grant authority. They provide evidence of how an operation was evaluated.

## 13. Future Enforcement Mapping

This design may later map to:

| Requirement | Future Control |
| --- | --- |
| canonical project isolation | runtime launcher and scoped workspace |
| protected read/write paths | filesystem permissions, ACLs, or read-only mounts |
| task-scoped write | capability manifest validated by runtime launcher |
| append-only records | append-only storage or restricted file descriptor |
| protected decisions path | dedicated governance write channel |
| path escape prevention | canonical path validation and mount isolation |
| artifact producer enforcement | artifact linter and runtime identity binding |
| violation evidence | append-only audit trail |
| exceptional access | ChatGPT Review or User Decision gate |

These controls are not implemented by TASK_042.

## 14. Non-Implementation Boundary

TASK_042 creates documentation only.

It does not create or modify:

- runtime code
- sandbox profiles
- filesystem ACLs
- file ownership or modes
- containers
- Dockerfile
- `docker-compose.yml`
- API key or provider configuration
- runtime launcher
- Git wrapper
- artifact linter
- pre-commit hook
- ACOS v1.5 governance rules
- ACOS agents or skills
- business project files
- instance-local coordination history

No permission described here is active until a later implementation task is separately authorized, reviewed, and accepted.

## 15. Summary

The ACOS v2.0 filesystem model protects ACOS core, separates coordination artifact paths by runtime identity, constrains business-project writes to Codex Executor, and treats instance-local coordination data as non-core by default.

The central rule is:

```text
No authenticated runtime identity
or no canonical project root
or no authorized path
or no valid TASK + DECISION
        =
No write
```

Filesystem isolation reduces the technical opportunity for role drift and unauthorized mutation, but final review and human authorization remain part of the ACOS lifecycle.

# ACOS v2.0 Shadow Implementation Roadmap

## 1. Scope And Purpose

This document defines the future shadow implementation roadmap for ACOS v2.0.

The roadmap converts the accepted v2.0 design documents into separately reviewable implementation candidates without authorizing implementation now.

Shadow implementation means:

```text
observe
        +
evaluate
        +
report
        +
compare with approved outcomes
        !=
enforce or mutate production state
```

The first implementation batch must be dry-run or warning-only unless a later task explicitly authorizes a narrower behavior.

TASK_050 creates this roadmap document only. It does not create code, fixtures, task files, runtime tools, or enforcement.

## 2. Relationship To The v2.0 Design Phase

The v2.0 design phase established:

- runtime isolation architecture
- runtime role permission matrix
- filesystem permission model
- Git operation separation policy
- audit trail specification
- local runtime prototype plan
- external advisory trigger policy

The relationship is:

```text
v2.0 design documents
        -> TASK_050 shadow implementation roadmap
        -> separately authorized candidate phases
        -> fixture and dry-run evidence
        -> later User Decision on controlled enforcement
```

TASK_050 does not convert the design into active policy enforcement. Existing v1.5 linter and pre-commit protections remain unchanged.

## 3. Shadow Implementation Principles

### 3.1 Shadow First

The first implementation of every new decision component must default to one of:

- fixture-only evaluation
- dry-run evaluation
- warning-only observation
- report-only comparison

It must not control a real operation until a later task authorizes enforcement.

### 3.2 No Physical Enforcement In TASK_050

TASK_050 provides no runtime launcher, filesystem sandbox, Git wrapper, audit writer, advisory checker, User Decision checker, or scenario runner.

### 3.3 No Production Repository Mutation

No roadmap phase is active merely because it is described here.

Future fixture phases must use disposable workspaces. Future ACOS self-test and instance shadow phases begin read-only.

### 3.4 Provider-Neutral And Offline First

The shadow roadmap must not require automatic provider invocation.

The first fixtures use static artifacts and deterministic inputs. No real ChatGPT, Codex, Gemini, or other model API call is required.

### 3.5 No API Key Handling

No phase before separate secrets governance may collect, store, transmit, validate, or rotate API keys.

Provider labels in fixtures are non-secret metadata only.

### 3.6 No Container Isolation Yet

The roadmap may preserve container isolation as a later research option, but TASK_050 and the initial candidate phases do not create containers, images, compose files, or production sandboxing.

### 3.7 Preserve v1.5 Protections

The roadmap must not replace, weaken, or bypass:

- `scripts/acos-linter.py`
- `.githooks/pre-commit`
- current manual ChatGPT Review
- current User Decision boundaries
- current path-limited Git tasks

Shadow results are supplemental evidence.

### 3.8 Separate Authorization Per Phase

Every future phase requires its own bounded task, allowed paths, forbidden actions, result, review, and decision.

No candidate task is authorized by this roadmap.

### 3.9 Mutation Requires TASK And DECISION

Any future mutation, including fixture mutation, requires a valid `TASK` and applicable ChatGPT Review `DECISION` or explicit authorization.

Real repository mutation requires additional risk review and User Decision when appropriate.

### 3.10 Mandatory Advisory Review

Governance, runtime identity, filesystem, Git, audit, advisory, User Decision, instance-boundary, and enforcement changes are Level 2 under TASK_046 unless ChatGPT Review documents a narrower classification.

Level 2 work must complete mandatory External Advisory Review before commit authorization.

### 3.11 Git Operations Stay Separate

Future Git work must preserve:

```text
inspect != test != edit != stage != commit != push != release
```

Shadow observation must not be used to bundle these permissions.

### 3.12 Audit Does Not Authorize

An audit event records a decision or operation. It does not grant the next operation.

### 3.13 Instance Boundaries Remain Explicit

An instance-local `.codex-coordination/` is not ACOS core unless User Decision explicitly activates local ACOS instance mode for that project.

## 4. Roadmap Phases

| Phase | Candidate | Primary Mode | Initial Target | Mutation Allowed By Roadmap |
| --- | --- | --- | --- | --- |
| Phase 0 | Baseline and fixture inventory | docs / inventory | policy snapshots and fixture catalog | No |
| Phase 1 | `TASK_051` Runtime Identity Simulator Candidate | fixture dry-run | static identity and capability fixtures | No |
| Phase 2 | `TASK_052` Filesystem Permission Checker Dry-run Candidate | fixture dry-run | canonical fixture paths | No |
| Phase 3 | `TASK_053` Git Operation Gate Dry-run Candidate | fixture dry-run | Git request descriptions and manifests | No |
| Phase 4 | `TASK_054` Audit JSONL Writer Prototype Candidate | fixture append | temporary audit fixture stream | Only if separately authorized in a disposable fixture |
| Phase 5 | `TASK_055` Advisory Gate Checker Candidate | fixture dry-run | static advisory artifacts | No |
| Phase 6 | `TASK_056` User Decision Gate Checker Candidate | fixture dry-run | static User Decision references | No |
| Phase 7 | `TASK_057` Validation Scenario Runner Candidate | fixture orchestration | prior candidate fixtures | Only separately authorized fixture setup/output |
| Phase 8 | `TASK_058` Controlled ACOS Self-Test Candidate | read-only shadow | live ACOS observations | No initial mutation |
| Phase 9 | `TASK_059` Controlled Instance Shadow Test Candidate | read-only shadow | explicitly authorized instance | No initial mutation |

These names are future task candidates only. TASK_050 does not create task files or authorize any candidate.

## 5. Phase 0: Baseline And Fixture Inventory

### 5.1 Objective

Establish a versioned baseline before any prototype component is written.

### 5.2 Planned Inputs

- accepted TASK_040 through TASK_046 documents
- current v1.5 linter behavior
- current pre-commit hook behavior
- artifact templates
- current role and routing rules
- current Git authorization examples
- TASK_045 validation scenarios

### 5.3 Planned Inventory

The future baseline task should inventory:

- policy document paths and commit hashes
- artifact types and producers
- runtime identities
- path classes
- Git operation classes
- audit event types and fields
- mandatory advisory categories
- User Decision override fields
- instance mode states
- expected allow and deny examples

### 5.4 Fixture Catalog

The catalog should plan static fixtures for:

- valid task
- malformed task
- producer spoofing
- valid result and blocked result
- valid and invalid advisory review
- accepted, rework, and blocked review
- valid and expired decision
- valid and replayed User Decision override
- allowed and protected paths
- symlink and traversal attempts
- exact and unrelated staged manifests
- commit and push authorization sequences
- audit hash chain and tamper evidence
- external and local instance modes

### 5.5 Restrictions

Phase 0 must not:

- write runtime code
- call providers
- create credentials
- mutate a repository
- change linter or hook behavior
- create enforcement

### 5.6 Evidence

Expected future evidence:

- baseline inventory document
- fixture manifest
- policy-to-fixture traceability matrix
- unresolved ambiguity list
- phase-entry recommendation

## 6. Phase 1: Runtime Identity Simulator

Future candidate:

```text
TASK_051 Runtime Identity Simulator Plan / Prototype Candidate
```

### 6.1 Objective

Evaluate runtime identity and artifact authority using static fixture profiles.

### 6.2 Planned Behavior

The simulator would receive:

- runtime identity fixture
- provider label as non-authorizing context
- session ID
- task and decision references
- project root
- requested artifact or operation
- capability issue and expiry time

It would return:

- `ALLOW`, `DENY`, or `BLOCKED` recommendation
- matched policy rule
- reason
- expected audit event

### 6.3 Required Identity Cases

- ChatGPT Review produces task, review, and decision.
- Codex produces result or blocked result.
- External Advisory produces advisory review only.
- Automation produces result or record only.
- Provider label changes without authority change.
- Producer differs from authenticated runtime.
- Capability is expired, revoked, or replayed.
- Runtime attempts self-acceptance.

### 6.4 Shadow Boundary

The simulator must not launch a model, command, or runtime. It evaluates fixtures only.

## 7. Phase 2: Filesystem Permission Checker Dry-Run

Future candidate:

```text
TASK_052 Filesystem Permission Checker Dry-run Candidate
```

### 7.1 Objective

Evaluate filesystem access requests without performing filesystem mutation.

### 7.2 Planned Inputs

- runtime identity
- canonical fixture root
- requested path
- operation type
- task and decision scope
- allowed and forbidden paths
- instance mode status
- capability expiry

### 7.3 Planned Checks

- canonical root match
- path normalization
- traversal rejection
- symlink destination
- writable-parent bypass
- protected ACOS core classification
- business project classification
- instance-local coordination classification
- cross-project capability replay
- role-to-path permission

### 7.4 Planned Output

The dry-run output reports:

- would allow
- would deny
- would block for missing information
- policy reference
- canonical path
- expected audit event

It must not create, modify, move, rename, or delete a file.

## 8. Phase 3: Git Operation Gate Dry-Run

Future candidate:

```text
TASK_053 Git Operation Gate Dry-run Candidate
```

### 8.1 Objective

Evaluate a proposed Git operation without executing Git mutation.

### 8.2 Operation Classes

- inspect
- test
- edit
- stage
- commit
- push
- release

### 8.3 Planned Checks

- runtime authority
- operation-specific decision
- reviewed predecessor result
- exact allowed path manifest
- actual fixture staged manifest
- commit message
- commit hash or range
- remote and branch
- mandatory advisory completion
- reused or expired authorization

### 8.4 Required Denials

- `git add .`
- `git add -A`
- `git commit -a`
- hook bypass
- unreviewed commit
- push under commit authorization
- force push
- release under ordinary push authorization
- unrelated staged paths
- pull, rebase, merge, reset, clean, or stash as implicit remediation

### 8.5 Shadow Boundary

The dry-run consumes request descriptions and fixture manifests. It does not invoke Git.

## 9. Phase 4: Audit JSONL Writer Prototype Plan

Future candidate:

```text
TASK_054 Audit JSONL Writer Prototype Candidate
```

### 9.1 Objective

Prototype append-only audit records in a disposable fixture stream.

JSON Lines is a prototype option, not a production storage decision.

### 9.2 Planned Capabilities

- validate TASK_044 required fields
- append a new event
- compute source artifact hash
- compute prior-event and current-event hashes
- detect duplicate event ID
- append correction event
- report sequence gap or tamper evidence
- write bounded failure evidence

### 9.3 Planned Event Coverage

- artifact lifecycle events
- runtime session events
- filesystem allow and deny results
- stage, commit, push, and release events
- advisory request, receipt, and consumption
- User Decision and override events
- violation and audit failure events
- instance mode events

### 9.4 Safety Boundary

Any future writer must target a temporary fixture directory only.

It must not become the ACOS production audit source, modify recorded fixture events, store secrets, or grant authority.

## 10. Phase 5: Advisory Gate Checker Plan

Future candidate:

```text
TASK_055 Advisory Gate Checker Candidate
```

### 10.1 Objective

Evaluate TASK_046 trigger classification and advisory completion with static artifacts.

### 10.2 Planned Checks

- Level 0, Level 1, or Level 2 classification
- conservative handling of ambiguity
- valid advisory producer
- artifact type is `ADVISORY REVIEW`
- receiver and next receiver are ChatGPT Review
- no direct route to Codex
- advisory request and response match
- material findings were consumed
- final decision references advisory or valid override

### 10.3 Unavailable Advisory Cases

- blocked
- deferred
- explicit bounded User Decision override
- invalid silent downgrade to optional

### 10.4 Shadow Boundary

The checker uses static fixtures and does not invoke an advisory provider.

## 11. Phase 6: User Decision Gate Checker Plan

Future candidate:

```text
TASK_056 User Decision Gate Checker Candidate
```

### 11.1 Objective

Validate a bounded User Decision reference without impersonating the user or storing credentials.

### 11.2 Planned Checks

- user decision reference exists
- project and task match
- decision scope covers the request
- reason and accepted risk are present
- validity period is active
- override is not replayed
- remaining forbidden actions are preserved
- ChatGPT Review relationship is explicit
- retrospective review requirement is recorded

### 11.3 Required Denials

- fabricated user reference
- decision for another project
- expired or revoked decision
- broader requested scope
- reused one-time override
- secret embedded in fixture
- assumption that User Decision silently replaces ChatGPT Review

### 11.4 Shadow Boundary

No user identity system, credential store, or interactive approval service is created.

## 12. Phase 7: Validation Scenario Runner Plan

Future candidate:

```text
TASK_057 Validation Scenario Runner Candidate
```

### 12.1 Objective

Run deterministic fixture scenarios across the prior shadow components.

### 12.2 Planned Inputs

- versioned policy snapshot
- fixture catalog
- expected outcomes
- component adapters
- scenario manifest
- temporary output path

### 12.3 Planned Outputs

- scenario ID
- expected result
- observed result
- matched policy rules
- generated fixture audit events
- changed fixture paths, if separately authorized
- pass, fail, blocked, or inconclusive
- reproducibility metadata

### 12.4 Runner Restrictions

The first runner must not:

- call providers
- mutate the live ACOS repository
- mutate a project instance
- stage, commit, push, or release
- create enforcement
- auto-approve a scenario result

### 12.5 Coverage

The runner should cover all TASK_045 scenarios and add regression cases for every defect discovered in TASK_051 through TASK_056.

## 13. Phase 8: Controlled ACOS Self-Test

Future candidate:

```text
TASK_058 Controlled ACOS Self-Test Candidate
```

### 13.1 Objective

Observe selected real ACOS workflows in warning-only shadow mode.

### 13.2 Entry Boundary

Before connection to the live ACOS repository, require:

- accepted fixture evidence from prior phases
- no unresolved high-severity false allow
- mandatory External Advisory Review
- ChatGPT Review decision
- User Decision for live-repository observation
- read-only capability profile
- disable procedure

### 13.3 Initial Scope

The initial self-test may observe:

- artifact metadata validation
- runtime identity labels
- path classification
- staged-manifest evidence from an already authorized workflow
- expected audit event generation

It must not:

- block the live workflow
- write repository files
- change the Git index
- commit
- push
- alter linter or hook output
- create decisions

### 13.4 Comparison

Compare shadow recommendations with actual ChatGPT Review decisions.

Disagreement creates a report, not an enforcement action.

## 14. Phase 9: Controlled Instance Shadow Test

Future candidate:

```text
TASK_059 Controlled Instance Shadow Test Candidate
```

### 14.1 Objective

Test read-only shadow classification against one explicitly authorized project instance.

### 14.2 Preconditions

- ACOS self-test exit criteria passed
- instance named by User Decision
- canonical instance root verified
- dirty-worktree state classified
- read-only scope declared
- no provider or credential requirement
- mandatory advisory review completed
- rollback or disable path confirmed

### 14.3 Instance Boundary Rules

- ACOS core remains the governance source.
- Domain work remains in the instance.
- No ACOS core file is copied into the instance.
- Instance-local `.codex-coordination/` remains non-core by default.
- Local ACOS instance mode requires separate User Decision.
- Shadow findings do not authorize business changes.

### 14.4 Initial Observations

The initial test may observe:

- project identity
- canonical root
- task scope
- path classification
- Git status classification
- expected artifact routing
- expected audit events

It must not edit, stage, commit, push, clean, reset, migrate, or reorganize the instance.

## 15. Exit Criteria For Each Phase

| Phase | Minimum Exit Criteria |
| --- | --- |
| Phase 0 | Policy snapshot and fixture inventory reviewed; ambiguities documented; no implementation performed. |
| Phase 1 | Every runtime allow/deny case is deterministic; identity spoofing and expired capability are denied; no provider invoked. |
| Phase 2 | Canonical path and boundary cases are classified correctly; traversal, symlink, protected core, and cross-project escapes are denied in dry-run. |
| Phase 3 | All Git classes remain distinct; blanket staging, unreviewed commit, push without separate authorization, and release-as-push are denied in dry-run. |
| Phase 4 | Required event schema validates; append, hash-chain, correction, duplicate, and failure cases pass in fixture storage; audit never grants authority. |
| Phase 5 | Mandatory advisory classification, routing, receipt, consumption, unavailable, and override cases produce expected results. |
| Phase 6 | User Decision references are bounded, non-secret, non-replayable, and do not silently replace ChatGPT Review. |
| Phase 7 | Scenario suite is deterministic and reproducible; every high-risk negative case fails closed; no live repository is mutated. |
| Phase 8 | Read-only ACOS shadow results are compared with actual reviews; disagreements are recorded; zero live mutation occurs. |
| Phase 9 | Read-only instance test preserves project and local-history boundaries; no business or Git mutation occurs. |

### 15.1 Universal Exit Gate

No phase may advance with:

- unresolved critical or high-severity false allow
- runtime identity spoofing accepted
- protected path escape accepted
- Git authorization collapse
- skipped mandatory advisory gate
- unbounded User Decision override
- audit failure hidden
- instance boundary confusion
- real secret in fixtures or logs
- unreviewed mutation

### 15.2 Evidence Review

Phase completion requires:

- Codex or Automation result
- ChatGPT Review
- mandatory External Advisory Review when TASK_046 applies
- User Decision when risk or live scope requires it
- explicit decision to advance

## 16. Rollback And Disable Strategy

### 16.1 Shadow Disable

Every future component should have a simple disable state that returns ACOS to the existing v1.5 workflow.

Disabling shadow mode must not disable the existing linter or pre-commit hook.

### 16.2 Stop Triggers

Stop the current phase when:

- a false allow affects role, path, Git, advisory, user, or instance authority
- a prototype writes outside its fixture root
- shadow mode influences a live decision without review
- audit evidence is incomplete or silently rewritten
- secrets appear in output
- a provider is invoked unexpectedly
- performance or failure behavior disrupts live ACOS work
- disable behavior is unavailable

### 16.3 Rollback Actions

Future rollback may:

- stop the shadow process
- revoke the prototype session
- disable the candidate adapter
- preserve audit and scenario evidence
- return to manual v1.5 review and Git flow
- mark the phase blocked

Rollback must not:

- run `git reset --hard`
- run `git clean -fd`
- delete user work
- rewrite audit history
- broaden runtime permissions
- convert denied actions into accepted actions
- remove linter or hook protection

### 16.4 Fixture Cleanup

Fixture cleanup requires a separate bounded task. It must inventory disposable paths and preserve required evidence before deletion.

No cleanup is authorized by TASK_050.

## 17. Risk Register

| ID | Risk | Impact | Mitigation | Stop Condition |
| --- | --- | --- | --- | --- |
| `R01` | Shadow output is mistaken for authority | Unauthorized execution | Label every output non-authorizing; require ChatGPT Review | Shadow recommendation triggers action without decision |
| `R02` | Runtime identity is self-declared or spoofed | Role drift and false authority | Bind identity to fixture session and compare producer | Spoofed identity is allowed |
| `R03` | Path canonicalization is incorrect | Protected or cross-project write | Test traversal, symlink, parent, case, and mount cases | Any protected escape is allowed |
| `R04` | Git operation grants collapse | Unreviewed commit or push | Separate states, authorizations, and audit events | Stage, commit, push, or release is implied |
| `R05` | Audit record is treated as authorization | Lifecycle bypass | Enforce evidence-only semantics | Audit event enables operation |
| `R06` | Audit history can be rewritten | Evidence loss | Append-only fixture and hash-chain checks | Silent rewrite is not detected |
| `R07` | Advisory gate can be skipped | Unreviewed governance change | Validate request, receipt, consumption, and decision | Level 2 reaches commit without advisory or override |
| `R08` | User Decision is fabricated or replayed | False human authorization | Stable reference, project scope, expiry, one-time use | Invalid reference is accepted |
| `R09` | Instance-local history is treated as ACOS core | Project contamination | Default non-core classification | Local folder grants core authority |
| `R10` | Prototype reaches real project mutation early | User work damage | Fixture-only and read-only gates | Any unapproved live mutation occurs |
| `R11` | v1.5 protections are replaced or bypassed | Regression in current safety | Keep linter and hook unchanged | Existing control behavior changes |
| `R12` | Secrets enter fixtures or logs | Credential exposure | Non-secret fixtures, redaction, no API keys | Secret-like value detected |
| `R13` | Warning-only mode blocks live work | Operational disruption | Report-only integration and disable switch | Live task is blocked by shadow output |
| `R14` | Race or time-of-check/time-of-use gap | Scope changes after validation | Snapshot manifests and session expiry in later design | Request changes after allow decision |
| `R15` | Platform-specific path or Git behavior differs | Non-portable decisions | Record platform and use cross-platform fixtures later | Unexplained platform divergence |
| `R16` | Candidate scope expands during implementation | Unreviewed feature growth | One task per phase and exact allowed files | Implementation includes later phase |
| `R17` | False positives create pressure to bypass policy | Governance erosion | Record disagreements and tune in shadow only | Bypass becomes normal response |
| `R18` | False negatives remain hidden | Unsafe promotion | High-risk negative suite and advisory review | Critical false allow unresolved |

### 17.1 Risk Ownership

ChatGPT Review owns risk disposition. External Advisory Reviewer provides non-binding second opinion. User Decision owns explicit human risk acceptance. Codex and Automation report evidence but do not accept risk on behalf of others.

## 18. Mandatory Advisory Review Points

TASK_046 applies to this roadmap and likely applies to each candidate because they concern runtime identity, filesystem, Git, audit, advisory, User Decision, validation, or instance boundaries.

Mandatory advisory review is required before final acceptance or commit authorization for:

- TASK_050 roadmap changes
- runtime identity simulator policy or prototype
- filesystem permission checker rules
- Git operation gate rules
- audit writer schema, append-only, or integrity behavior
- advisory trigger or consumption logic
- User Decision validation or override behavior
- scenario runner governance decisions
- connection to the live ACOS repository
- connection to any project instance
- transition from report-only to warning-only when behavior changes materially
- transition from warning-only to blocking or enforcement
- physical isolation, container, ACL, user, or credential design
- release or production deployment design

### 18.1 Required Advisory Flow

```text
Codex RESULT
        -> ChatGPT Review preliminary acceptance
        -> External Advisory Reviewer ADVISORY REVIEW
        -> ChatGPT Review consumes material findings
        -> ChatGPT Review DECISION
        -> next operation authorization, if accepted
```

External Advisory Reviewer:

- remains read-only
- produces `ADVISORY REVIEW` only
- does not execute implementation
- does not authorize commit, push, or release
- does not route directly to Codex

### 18.2 Unavailable Advisory

When mandatory advisory is unavailable, use TASK_046 outcomes:

- blocked
- deferred
- explicit bounded User Decision override

The reason and residual risk must be recorded.

## 19. Relationship To TASK_040, TASK_041, TASK_042, TASK_043, TASK_044, TASK_045, And TASK_046

```text
TASK_040 -> runtime isolation architecture
TASK_041 -> runtime role permission matrix
TASK_042 -> filesystem permission model
TASK_043 -> Git operation separation policy
TASK_044 -> audit trail specification
TASK_045 -> local runtime prototype plan
TASK_046 -> external advisory trigger policy
TASK_050 -> shadow implementation roadmap
```

TASK_050 applies the upstream documents as follows:

- TASK_040 defines runtime identities and isolation goals.
- TASK_041 defines artifact, operation, and directory permissions.
- TASK_042 defines canonical roots, protected paths, and instance boundaries.
- TASK_043 defines independent Git operation gates.
- TASK_044 defines audit events, integrity, failures, and evidence semantics.
- TASK_045 defines local fixtures, simulation components, scenarios, and migration stages.
- TASK_046 defines mandatory advisory triggers, routing, consumption, unavailable handling, and overrides.

TASK_050 does not override or amend those documents.

### 19.1 Candidate Traceability

| Candidate | Primary Design Sources |
| --- | --- |
| `TASK_051` | TASK_040, TASK_041, TASK_045 |
| `TASK_052` | TASK_041, TASK_042, TASK_045 |
| `TASK_053` | TASK_041, TASK_043, TASK_045 |
| `TASK_054` | TASK_040, TASK_044, TASK_045 |
| `TASK_055` | TASK_041, TASK_046, TASK_045 |
| `TASK_056` | TASK_041, TASK_044, TASK_045 |
| `TASK_057` | TASK_042, TASK_043, TASK_044, TASK_045 |
| `TASK_058` | TASK_040 through TASK_046 |
| `TASK_059` | TASK_040 through TASK_046 plus instance onboarding |

This table does not authorize or create candidate tasks.

## 20. Non-Implementation Boundary

TASK_050 creates documentation only.

It does not create or modify:

- TASK_051 through TASK_059 files
- runtime identity simulator
- runtime launcher
- filesystem permission checker or sandbox
- Git operation gate or wrapper
- audit JSONL writer or logger
- advisory gate checker
- User Decision gate checker
- validation scenario runner
- ACOS self-test tool
- instance shadow test tool
- fixture catalog
- fixture workspace
- policy snapshot
- executable code
- shell script
- runtime profile
- capability manifest
- filesystem ACL
- operating-system user
- container configuration
- Dockerfile
- `docker-compose.yml`
- API keys, credentials, or provider configuration
- `scripts/acos-linter.py`
- `.githooks/pre-commit`
- ACOS v1.5 or v2.0 rule files
- agents or skills
- project-instance files

It does not execute:

- provider or API calls
- runtime simulation
- filesystem mutation
- Git add
- Git commit
- Git push
- Git pull
- Git reset
- Git clean
- release operations

Every candidate phase requires a separately authorized task. Governance and enforcement candidates must complete TASK_046 mandatory advisory review before commit authorization.

TASK_050 itself must return to ChatGPT Review, then External Advisory Reviewer, before commit authorization is considered.

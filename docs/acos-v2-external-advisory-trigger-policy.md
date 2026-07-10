# ACOS v2.0 External Advisory Trigger Policy

## 1. Purpose

This document defines when ACOS should request an `ADVISORY REVIEW` from the External Advisory Reviewer.

The policy exists to add an independent, non-executing second opinion to higher-risk governance work without changing final authority or creating another executor.

It answers four questions:

1. Which changes require advisory review?
2. Which changes may use advisory review optionally?
3. How must advisory output be routed and consumed?
4. What happens when mandatory advisory capability is unavailable?

This policy is provider-neutral. A model or provider may supply the External Advisory Runtime, but provider identity does not change role authority.

## 2. External Advisory Reviewer Role

The External Advisory Reviewer is a temporary, non-executing second-opinion role.

Its only permitted output artifact is:

```text
ADVISORY REVIEW
```

The role may:

- perform read-only analysis
- identify governance risks
- compare alternatives
- test assumptions and internal consistency
- identify missing questions or controls
- provide non-binding recommendations to ChatGPT Review

The role does not own tasks, execution, acceptance, decisions, Git operations, or project direction.

### 2.1 Runtime And Provider Separation

```text
External Advisory Runtime != Provider Name
```

The runtime identity defines authority. The current or future provider must operate within the same read-only boundary.

A provider change must not silently expand advisory permissions or reduce mandatory trigger requirements.

## 3. Advisory Review Trigger Levels

ACOS uses three trigger levels.

### Level 0: Not Required

Use when the change is operational, routine, and does not affect governance, role authority, routing, enforcement, release authority, or instance boundaries.

No advisory request is required.

### Level 1: Optional Advisory Review

Use when a second opinion may improve clarity or consistency, but the change does not alter authority, enforcement, protected paths, or lifecycle behavior.

ChatGPT Review may request advisory review at its discretion.

### Level 2: Mandatory Advisory Review

Use when the change affects ACOS governance architecture, runtime isolation, authority boundaries, enforcement, protected paths, Git separation, auditability, release authority, or disputed instance mode.

A Level 2 change must not be treated as having completed mandatory advisory review unless a valid `ADVISORY REVIEW` has been received and consumed, or an explicit User Decision override has been recorded.

### 3.1 Conservative Classification

If a change could reasonably fall into both Level 1 and Level 2, classify it as Level 2.

Splitting a high-risk governance change into smaller files or commits does not downgrade its trigger level.

## 4. Mandatory Advisory Review

The following changes require Level 2 advisory review:

1. ACOS governance architecture changes.
2. Runtime isolation architecture changes.
3. Runtime role permission changes.
4. Filesystem permission model changes.
5. Git operation separation policy changes.
6. Audit trail specification changes.
7. Linter, hook, runtime launcher, Git wrapper, sandbox, or enforcement changes.
8. Role boundary changes.
9. Release authorization model changes.
10. Instance mode disputes.

### 4.1 Mandatory Trigger Details

#### Governance Architecture

Mandatory when a proposal changes:

- artifact lifecycle
- authority ownership
- review or decision flow
- governance proposal handling
- self-approval prevention
- producer or receiver rules

#### Runtime Isolation And Permissions

Mandatory when a proposal changes:

- runtime identity definitions
- runtime permissions
- filesystem access
- protected ACOS core paths
- project-instance access
- capability duration or scope

#### Git And Release Authority

Mandatory when a proposal changes:

- staging authority
- commit authorization
- push authorization
- release authorization
- force-push policy
- edit-to-commit-to-push separation

#### Enforcement And Auditability

Mandatory when a proposal changes:

- linter rules
- pre-commit behavior
- runtime enforcement
- audit fields
- audit retention or append-only guarantees
- violation handling
- override logging

#### Role And Instance Boundaries

Mandatory when a proposal changes:

- ChatGPT Review authority
- Codex Executor authority
- External Advisory Reviewer authority
- Automation authority
- local ACOS instance mode
- whether an instance-local coordination directory is authoritative
- ACOS core versus project-instance ownership

### 4.2 Mandatory Review Timing

Mandatory advisory review should occur after enough design material exists for meaningful review and before final acceptance authorizes commit, push, release, or implementation of the affected governance change.

A draft may be produced before advisory review. Draft existence does not satisfy the advisory gate.

## 5. Optional Advisory Review

Level 1 advisory review may be used for:

1. Ordinary documentation wording adjustments.
2. Non-governance README updates.
3. Additional project-instance onboarding examples.
4. Low-risk explanatory reorganization of existing rules.

Optional classification applies only when the change does not alter:

- role authority
- artifact types
- producer or receiver rules
- mandatory metadata
- protected paths
- Git authority
- enforcement behavior
- release authority
- audit requirements
- instance mode status

If any of these boundaries may change, the work is Level 2.

ChatGPT Review may still request advisory review for a Level 0 or Level 1 task when ambiguity, accumulated complexity, conflicting evidence, or unusual risk warrants a second opinion.

## 6. Forbidden Advisory Actions

The External Advisory Reviewer must not:

1. Modify code.
2. Modify documentation.
3. Create, modify, move, or delete files.
4. Execute shell commands.
5. Execute Git commands.
6. Generate `TASK`.
7. Generate `RESULT` or `BLOCKED RESULT`.
8. Generate `REVIEW`.
9. Generate `DECISION`.
10. Authorize commit.
11. Authorize push.
12. Authorize release.
13. Send a task directly to Codex Executor.
14. Route advisory output directly to Codex Executor.
15. Accept or approve its own output.
16. Expand approved scope.
17. Impersonate ChatGPT Review, Codex Executor, Automation, or User Decision.
18. Produce a directly applicable patch or execution instruction.

An advisory opinion may recommend that ChatGPT Review consider a task, rework, decision, or user question. The recommendation itself grants no authority.

## 7. Advisory Review Routing

### 7.1 Request Route

ChatGPT Review determines the trigger level and initiates any advisory request.

The relevant governance proposal, draft, result, decision question, or context may be routed to External Advisory Reviewer as read-only input.

The request must identify:

- project
- reviewed artifact or draft
- advisory question
- trigger level
- authority limit
- forbidden actions
- expected output
- return receiver

It must state:

```text
OUTPUT:
ADVISORY REVIEW only
```

### 7.2 Required Advisory Output Metadata

A valid advisory output must include:

```text
ARTIFACT TYPE:
ADVISORY REVIEW

PRODUCER:
External Advisory Reviewer

TO:
ChatGPT Review

NEXT RECEIVER:
ChatGPT Review

MODE:
ADVISORY / READONLY

PROJECT:
[ACOS project or explicitly authorized review target]

AUTHORITY LIMIT:
Non-binding second opinion only

FORBIDDEN:
No execution, file modification, Git operation, TASK, RESULT, REVIEW, or DECISION

OUTPUT:
ADVISORY REVIEW only
```

### 7.3 Return Route

The only normal return route is:

```text
External Advisory Reviewer
        -> ADVISORY REVIEW
        -> ChatGPT Review
```

The following route is invalid:

```text
External Advisory Reviewer
        -> Codex Executor
```

ChatGPT Review must assess and route any resulting task or rework instruction under its own authenticated authority.

## 8. Relationship To ChatGPT Review And User Decision

### 8.1 ChatGPT Review Must Consume The Opinion

For a valid mandatory advisory review, ChatGPT Review must consume the advisory opinion before issuing the final governance decision.

Consumption means ChatGPT Review must:

1. read the advisory artifact;
2. identify materially relevant findings;
3. state whether each material finding is accepted, rejected, deferred, or already mitigated; and
4. record the reasoning in the resulting `REVIEW` or `DECISION`.

Consumption does not mean automatic acceptance.

### 8.2 Final Authority Does Not Move

The advisory role remains non-binding.

Final authority remains with:

- ChatGPT Review for ACOS `REVIEW` and `DECISION`; and
- User Decision for project direction, credentials, explicit overrides, or human authorization.

User Decision does not become an External Advisory artifact. External Advisory Reviewer cannot imitate or replace User Decision.

### 8.3 Commit And Push Authority

An `ADVISORY REVIEW` cannot authorize:

- edit
- staging
- commit
- push
- release
- implementation

Any such action requires the normal ACOS task, review, decision, and separate authorization chain.

## 9. Retrospective Review Handling

TASK_040, TASK_041, and TASK_042 form part of the ACOS v2.0 governance architecture sequence.

The External Advisory Trigger Policy did not exist when that sequence began. Therefore:

1. Existing TASK_040, TASK_041, or TASK_042 artifacts and commits do not automatically become invalid.
2. Their prior acceptance is not silently revoked.
3. ChatGPT Review or User Decision may require retrospective `ADVISORY REVIEW` for any of them.
4. Retrospective review is read-only and does not itself rewrite files or Git history.
5. Findings that require changes must enter ACOS as a governance proposal or bounded rework task.
6. Codex Executor may act only after ChatGPT Review creates the required task and decision chain.
7. A retrospective opinion cannot directly authorize amend, revert, reset, commit, or push.

After TASK_046 becomes effective, later Level 2 governance tasks must be classified under this policy.

The policy becomes effective for later work only after TASK_046 is reviewed and accepted. Commit or push is not implied by acceptance.

## 10. Failure Or Unavailable Advisory Handling

If the provider assigned to mandatory advisory review is unavailable, mandatory advisory review is not complete.

Unavailability must not be silently treated as:

- successful advisory review
- optional advisory review
- approval
- consent
- permission to continue

The allowed outcomes are:

1. `BLOCKED`: pause the affected governance decision until advisory capability is available.
2. User Decision override: proceed without completed advisory only when the user explicitly accepts the risk.
3. Defer advisory review: continue only work that does not depend on final advisory completion, while withholding final acceptance or action authorization.

### 10.1 Required Override Record

A User Decision override must explicitly record:

- affected task or governance proposal
- mandatory trigger category
- unavailable runtime or provider condition
- attempts made to obtain advisory review
- reason for proceeding
- accepted residual risk
- scope and duration of the override
- whether retrospective advisory review remains required
- which actions remain forbidden

ChatGPT Review must reference the override in its final ACOS decision unless the user explicitly suspends ACOS governance for that task.

### 10.2 Failure During Advisory Review

If advisory output is malformed, identity-spoofed, incomplete, routed to the wrong receiver, or outside authority:

- mark the artifact invalid;
- do not count it as completed advisory review;
- retain evidence of the failure;
- request corrected advisory output, block, defer, or seek User Decision override; and
- do not forward the invalid artifact to Codex Executor.

## 11. Audit Requirements

Each advisory trigger assessment should record:

- event ID
- task or governance proposal ID
- project
- trigger level
- trigger category
- classification rationale
- classifier identity
- advisory request artifact ID
- External Advisory Runtime identity
- provider identifier, if applicable
- request timestamp
- availability status
- advisory artifact ID
- advisory completion timestamp
- material findings
- ChatGPT Review disposition of each material finding
- final decision ID
- User Decision override ID, if any
- deferred or retrospective review requirement
- related commit or push target, if applicable

Audit records do not grant authority and do not replace advisory review, ChatGPT Review, ChatGPT Decision, or User Decision.

## 12. Non-Implementation Boundary

TASK_046 creates policy documentation only.

It does not:

- invoke an external model
- invoke an API
- select or configure a provider
- implement External Advisory Runtime
- create runtime code
- create containers
- create Dockerfile
- create `docker-compose.yml`
- create API keys or secrets
- modify the artifact linter
- modify the pre-commit hook
- modify agents or skills
- modify ACOS v1.5 rules
- modify TASK_040, TASK_041, or TASK_042 documents
- modify any project instance
- authorize staging, commit, push, release, or implementation

Future enforcement of trigger levels requires a separate task, review, result, and decision.

## 13. Summary

The External Advisory Trigger Policy introduces a risk-based second-opinion gate without transferring execution or decision authority.

```text
High-risk governance change
        -> mandatory advisory classification
        -> read-only ADVISORY REVIEW
        -> ChatGPT Review consumes and records disposition
        -> ChatGPT Review / User Decision retains final authority
```

External Advisory Reviewer produces `ADVISORY REVIEW` only, never routes directly to Codex Executor, and never authorizes commit, push, release, or implementation.

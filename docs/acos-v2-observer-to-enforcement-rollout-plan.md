# ACOS v2 Observer-To-Enforcement Rollout Plan

## 1. Purpose And Status

This plan defines how ACOS may move from the TASK_051-057 fixture-only shadow
baseline toward controlled runtime operation. It is a planning artifact only.
No phase is activated by this document, and progression always requires a new
bounded task, evidence, review, and decision.

```text
Observer recommendation != authorization
Phase exit evidence != next-phase authorization
Design completion != enforcement enablement
```

## 2. Rollout Principles

1. Observer-first: evaluate copies of events before controlling any event.
2. Default deny: ambiguity blocks promotion and, once enforcing, blocks action.
3. One capability per phase: read, edit, stage, commit, push, release, and
   deployment are introduced independently.
4. Human authority remains explicit. Automation may draft but not sign or accept
   User Decisions, ChatGPT Decisions, advisory reviews, or high-risk authority.
5. Evidence before expansion: every phase has measurable exit criteria and
   negative tests.
6. Single-project before multi-project: ACOS core is the first controlled scope.
7. Reversible activation: every component has a kill switch and a manual fallback.
8. Existing v1.5 controls remain active until separately retired after evidence.
9. Policy, schema, adapter, state, sandbox, and audit changes are independently
   versioned and reviewed.
10. No phase may normalize bypasses to meet delivery targets.

## 3. Operating Modes

### 3.1 Fixture Mode

Static inputs only. No live events, identities, repositories, or decisions.

### 3.2 Observer Mode

Receives read-only copies of real artifacts/events, evaluates policy, records a
shadow recommendation, and compares it with the actual human-controlled result.
It cannot block, mutate, route execution, issue capability, or authorize.

### 3.3 Human-Approved Semi-Automation

May validate schemas, route artifacts, run static/read-only checks, classify
requirements, create advisory requests, record audit events, detect blockers,
and draft TASK/DECISION artifacts. A human confirms task start, live connection,
scope expansion, edit, commit, push, release, destructive action, exceptions,
enforcement activation, and phase closure.

### 3.4 Blocking Enforcement

Technically blocks actions that violate a signed policy and bounded capability.
It is available only after the entry criteria in Section 9 and a separate User
Decision. TASK_058 does not activate it.

## 4. Metrics And Evidence

### 4.1 Core Metrics

| Metric | Definition |
| --- | --- |
| true allow | shadow/enforcement allows and accepted human outcome agrees |
| true deny/block | shadow/enforcement rejects and accepted human outcome agrees |
| false positive | system denies/blocks an action later accepted under the same facts and policy |
| false negative | system allows an action later determined to violate the same policy |
| indeterminate rate | BLOCKED because facts, identity, state, or policy cannot be established |
| policy drift | component result differs because policy version/digest/contract is inconsistent |
| decision latency | time from complete request to governed outcome |
| recovery success | interrupted workflows restored without duplicate effect or lost evidence |
| provenance confidence | strength of actor/session/authorization/remote attribution |

### 4.2 Recommended Observer Evidence Window

Before any blocking promotion, observe at least 30 consecutive days and 500
classified events, whichever is later. The sample should include at minimum:

- 100 actionable lifecycle events;
- 50 filesystem scope decisions;
- 50 Git operation decisions across stage, commit, and push;
- 30 mandatory-advisory cases or synthetic production-equivalent replays;
- 30 User Decision consumption cases;
- 50 DENY/BLOCKED cases; and
- all critical abuse and recovery scenarios in the accepted test catalog.

If normal operations cannot supply a category safely, deterministic replay may
supplement but must be reported separately from live observation.

### 4.3 False-Positive And False-Negative Promotion Thresholds

Recommended minimum thresholds are:

- zero unresolved critical or high-severity false allows;
- zero identity, scope, commit/push, advisory, User Decision, or audit authority
  substitution false allows;
- false-positive rate at or below 2% overall and 1% for mutating gates;
- indeterminate rate at or below 5%, with no repeated unknown root cause;
- zero unresolved policy/contract drift at the promoted version;
- 100% successful duplicate/replay prevention in the validation catalog;
- 100% successful rollback/kill-switch exercises;
- 100% attribution for orchestrator-executed mutations and explicit provenance
  exceptions for every externally completed operation; and
- accepted independent security review.

These are proposed governance thresholds, not automatic promotion rules. ChatGPT
Review and User Decision may require stricter thresholds; lowering them requires
an explicit, audited risk decision.

## 5. Phase Overview

| Phase | Name | Highest Capability | Activation |
| --- | --- | --- | --- |
| 0 | Architecture and schemas | documents and offline schemas | separate design task |
| 1 | Local single-project observer | read-only event copies | User Decision for observation |
| 2 | Authenticated artifact exchange | signed test/observer artifacts | identity and key review |
| 3 | Durable workflow state and audit | persistent non-authorizing state | storage/recovery review |
| 4 | Read-only cross-agent orchestration | routed read-only requests | adapter and privacy review |
| 5 | Human-approved edit execution | bounded file edits | per-edit User/ChatGPT authority |
| 6 | Human-approved commit/push | separate commit and push capabilities | per-operation authorization |
| 7 | Limited blocking enforcement | selected technical denials | explicit enforcement User Decision |
| 8 | Controlled multi-project operation | isolated registered projects | per-project onboarding decision |

## 6. Phase 0: Architecture And Schemas Only

### Scope

Define artifact envelope/payload schemas, machine policy schema, state model,
runtime identity profile, adapter contracts, audit schema, and threat controls.

### Preconditions

- TASK_040-058 design baseline accepted.
- TASK_051-057 limitations and policy-copy risks recorded.
- no unresolved role or authority ambiguity.

### Deliverables

- versioned schemas and examples;
- policy-to-governance traceability matrix;
- state transition and authorization-consumption specification;
- adapter and sandbox interface specifications;
- test and migration plans.

### Prohibited Capabilities

No live event ingestion, provider call, credentials, database service, adapter,
sandbox, repository mutation, or enforcement.

### Validation And Exit

Schema negative tests, threat review, compatibility review, and Mandatory
External Advisory Review pass. Every authority field has a producer, verifier,
consumer, and revocation path. Exit requires ChatGPT Review; Phase 1 still needs
a separate User Decision.

### Rollback

Withdraw the schema release and retain fixture-only TASK_051-057 operation.

## 7. Phase 1: Local Single-Project Observer Mode

### Scope

Observe ACOS core artifact and Git lifecycle event copies on one host. Generate
shadow decisions and comparison reports only.

### Preconditions

- accepted Phase 0 schemas and policy snapshot;
- exact ACOS project registration;
- read-only observer capability and kill switch;
- privacy/redaction review; and
- User Decision naming the observation period and data scope.

### Deliverables

- local observer process design/implementation under a later task;
- shadow recommendation store;
- human-outcome comparison report;
- discrepancy and incident queue;
- daily disable/health evidence.

### Prohibited Capabilities

No artifact routing to production agents, write access, Git index access,
authorization issuance, blocking, or automatic action.

### Validation And Exit

Meet the observation window and sample mix, zero live mutation, 100% kill-switch
tests, and no unresolved critical false allow. Mandatory advisory and ChatGPT
Review are required before proposing Phase 2.

### Rollback

Stop observer ingestion, revoke its read capability, preserve evidence, and
return to fixture-only validation without changing v1.5 controls.

## 8. Phase 2: Authenticated Artifact Exchange

### Scope

Exchange signed, versioned artifacts among local test/observer runtime adapters.
No actionable capability is issued.

### Preconditions

- runtime registry and trust-root design accepted;
- key custody, rotation, revocation, and session expiry tested;
- canonicalization and replay tests pass; and
- Phase 1 discrepancy thresholds satisfied.

### Deliverables

- authenticated adapter transport;
- runtime registration/session evidence;
- signature, digest, nonce, replay, supersession, and revocation tests;
- untrusted-import separation.

### Prohibited Capabilities

No live execution, repository mutation, User Decision inference, or unsigned
artifact authority.

### Validation And Exit

Reject every spoofed runtime, modified artifact, replay, stale key, wrong project,
and unsupported schema in tests. Complete key-loss and rotation exercises.

### Rollback

Revoke adapter sessions and keys, disable exchange, and retain observer event
copies without treating them as trusted artifacts.

## 9. Phase 3: Durable Workflow State And Audit

### Scope

Persist workflows, artifacts, decisions, authorization reservations/consumption,
runtime sessions, execution attempts, blockers, recovery, and append-only audit.

### Preconditions

- authenticated artifact exchange stable;
- schema migrations and backups tested;
- transactional outbox and audit failure behavior accepted; and
- recovery objectives defined.

### Deliverables

- local durable state service;
- append-only audit store with signatures and hash chain;
- idempotency and optimistic-concurrency controls;
- restart, duplicate, race, backup, and restore tests.

### Prohibited Capabilities

State and audit remain non-authorizing. No sandbox mutation or production agent
command is allowed.

### Validation And Exit

Demonstrate no duplicate authorization consumption under concurrency, complete
restart recovery, detected audit tampering/fork, and fail-closed audit outage.

### Rollback

Freeze writes, export signed evidence, restore the last accepted backup, reconcile
without deleting conflicting records, and resume in observer-only mode.

## 10. Phase 4: Read-Only Cross-Agent Orchestration

### Scope

Route signed read-only TASK/REQUEST artifacts to registered adapters and collect
RESULT or ADVISORY REVIEW artifacts through the control plane.

### Preconditions

- Phase 2 identity and Phase 3 durable state/audit accepted;
- adapter timeouts, cancellation, rate limits, privacy, and idempotency tested;
- no direct adapter-to-adapter route; and
- User Decision authorizes named read-only runtimes and data.

### Deliverables

- read-only orchestration path;
- adapter health/retry controls;
- advisory request/review binding;
- execution-free receipts and provenance.

### Prohibited Capabilities

No file edit, command execution, Git write, capability issuance, or automatic
acceptance. External Advisory remains read-only and routes to ChatGPT Review.

### Validation And Exit

All runtime/producer mismatches, duplicate results, stale reviews, unavailable
adapters, cancellation races, and direct-route attempts fail closed.

### Rollback

Disable adapter routing and continue manual artifact exchange with durable audit.

## 11. Phase 5: Human-Approved Edit Execution

### Scope

Permit a sandboxed Codex Executor to perform one bounded edit/test attempt using
an exact project/path capability after human approval.

### Preconditions

- sandbox confinement and resource limits independently tested;
- canonical path, symlink, parent replacement, credential, network, and process
  controls verified;
- execution receipt and partial-edit recovery tested; and
- exact edit User/ChatGPT authorization issued.

### Deliverables

- isolated edit/test sandbox;
- filesystem capability enforcement;
- before/after manifest and signed receipt;
- partial edit, timeout, revocation, and cleanup recovery.

### Prohibited Capabilities

No stage, commit, push, release, deployment, destructive cleanup, or implicit
scope extension.

### Validation And Exit

Zero writes outside authorized paths; every attempted effect appears in the
receipt/audit; revocation and kill switch terminate safely; review remains manual.

### Rollback

Revoke the edit capability, terminate the sandbox, preserve the diff, and use a
separately authorized recovery task. Never reset or clean user work automatically.

## 12. Phase 6: Human-Approved Commit And Push

### Scope

Introduce separate stage, commit, and push capabilities for one protected ACOS
repository. Push and release remain distinct.

### Preconditions

- Phase 5 edits and reviews stable;
- exact staged-tree, branch, HEAD, upstream, remote, and expected-tip gates tested;
- server-side branch protection active;
- commit receipt, push receipt, and remote reconciliation accepted; and
- remote-sync provenance exception exercises pass.

### Deliverables

- path-limited stage gate;
- separately authorized commit and push gates;
- one-time capability consumption;
- remote receipt and provenance reconciliation.

### Prohibited Capabilities

No blanket staging, commit `-a`, amend, pull, merge, rebase, reset, clean, force
push, release under push authority, or bundled edit-to-push authority.

### Validation And Exit

Every negative Git scenario is denied; concurrent remote changes block; outside-
orchestrator pushes create provenance exceptions without false attribution; all
operations remain recoverable and auditable.

### Rollback

Revoke Git capabilities, disable the wrapper/gate, retain server protection, and
return to manually executed Git under existing reviewed ACOS workflow.

## 13. Phase 7: Limited Blocking Enforcement

### Scope

Enable blocking only for a small, accepted set of high-confidence controls such
as invalid signatures, replayed authorization, protected-path escape, forbidden
runtime/artifact combinations, blanket staging, and force push.

### Preconditions

All enforcement entry criteria in Section 15 pass, independent security review
is accepted, and User Decision explicitly names controls, project, duration,
kill switch, and rollback owner.

### Deliverables

- signed enforcement policy release;
- canary activation and real-time dashboard;
- incident/on-call and override process;
- periodic false-positive/negative and drift reports.

### Prohibited Capabilities

No unlisted blocking rule, silent policy update, automatic exception acceptance,
multi-project effect, or removal of human commit/push/release gates.

### Validation And Exit

Canary and rollback drills pass; thresholds remain satisfied for another full
observation window; zero unreviewed mutation or authority substitution occurs.

### Rollback

Activate kill switch, revert to observer-only policy, preserve event evidence,
revoke capabilities, and require incident review before reactivation.

## 14. Phase 8: Controlled Multi-Project Operation

### Scope

Onboard individually registered project instances with isolated roots, policy
overlays, state tenancy, credentials, audit partitions, and explicit User
Decision. ACOS core remains the governance source.

### Preconditions

- Phase 7 stable;
- tenant/project isolation and cross-project replay tests pass;
- each project has canonical ownership, root, risk class, and rollback plan; and
- instance-local `.codex-coordination/` classification is explicit.

### Deliverables

- project registry and isolation controls;
- per-project capabilities and audit views;
- onboarding/offboarding process;
- cross-project incident and revocation process.

### Prohibited Capabilities

No global capability, implicit project discovery, ACOS core copying, business
policy promotion into ACOS, or reuse of one project's authorization in another.

### Validation And Exit

Cross-project isolation tests, credential separation, audit partitioning,
revocation, backup/restore, and project offboarding all pass. Each project remains
separately authorized.

### Rollback

Disable one project without affecting others, revoke its sessions/capabilities,
preserve audit evidence, and return that project to manual operation.

## 15. Enforcement Entry Criteria

Blocking enforcement cannot start until all are true:

- artifact schemas are stable and compatibility-tested;
- runtime identities are mutually authenticated and revocable;
- durable workflow state and one-time consumption are operational;
- audit store, integrity checks, backup, and recovery are operational;
- machine policy is signed, versioned, traceable, and rollback-capable;
- replay protection and nonce/idempotency handling are operational;
- sandbox confinement and resource/credential/network controls are verified;
- filesystem and Git gates pass independent negative testing;
- advisory and User Decision paths pass lifecycle/recovery testing;
- adapter, state, audit, policy, and remote failure recovery is tested;
- observer thresholds in Section 4 are satisfied;
- independent security review and Mandatory External Advisory Review are accepted;
- a named human owns kill switch and incident response; and
- User Decision explicitly authorizes enforcement scope and duration.

TASK_058 completion satisfies none of these operational criteria by itself.

## 16. Human Approval Gates

| Action | Automation May Do | Required Human Gate |
| --- | --- | --- |
| classify requirement | recommend | User Decision for required human category |
| draft TASK/DECISION | draft only | ChatGPT Review signs/issues |
| start new task | present exact summary | User Decision |
| connect live runtime/project | validate readiness | User Decision |
| expand scope | detect and draft request | User Decision and new bounded task |
| edit files | validate capability | task-specific User/ChatGPT authority |
| stage/commit | validate manifest and draft authorization | separate ChatGPT Review decision |
| push | validate exact commit/remote state | separate push authorization |
| release/deploy | validate release evidence | independent release User Decision |
| destructive action | classify and block by default | explicit high-assurance User Decision |
| accept exception | record options/risks | User Decision or designated governance authority |
| enable enforcement | report thresholds | explicit User Decision |
| close phase | compile evidence | ChatGPT Review and required User Decision |

## 17. Rollback Strategy

Every future component must support:

- configuration/state that defaults to disabled;
- a tested kill switch independent of the component being disabled;
- capability/session revocation;
- observer-only fallback;
- preservation of state and audit evidence;
- bounded draining/cancellation of in-flight work;
- manual ACOS workflow fallback; and
- restoration without destructive Git or filesystem cleanup.

Rollback is triggered by any critical false allow, identity or scope bypass,
authorization inheritance, audit integrity loss, unattributed mutation,
unavailable kill switch, secret exposure, or unexplained policy drift.

## 18. Incident Handling

### Severity

- SEV-1: unauthorized mutation, key compromise, cross-project escape, audit loss,
  or false attribution of a high-risk operation.
- SEV-2: critical false allow caught before effect, repeated policy drift,
  enforcement outage, or recovery failure.
- SEV-3: bounded false positive, adapter outage, delayed audit, or malformed input.
- SEV-4: documentation, dashboard, or non-authorizing observer defect.

### Response

1. stop affected capabilities and preserve evidence;
2. revoke sessions/keys/authorizations as needed;
3. classify actual and possible effects;
4. open immutable incident and provenance records;
5. return to observer/manual mode;
6. require ChatGPT Review and, for material risk, User Decision;
7. correct through a new bounded task; and
8. replay validation before reactivation.

An override never rewrites the original denial or incident.

## 19. Change Management

- Schemas, policy, adapters, state migrations, sandbox profiles, and gates use
  independent versions and compatibility declarations.
- Policy changes run fixture tests, observer replay, traceability checks, and
  Mandatory External Advisory Review before promotion.
- Canary policy release is pinned per workflow; active workflows do not silently
  switch versions.
- Rollback releases are signed and tested, not ad hoc edits.
- Metrics distinguish live observation from synthetic replay.
- Every phase has an owner, expiry/review date, and accepted evidence package.
- Emergency changes remain time-bounded and require retrospective review.

## 20. Recommended Future Implementation Candidates

The next implementation work should remain separately authorized and small:

1. machine-readable artifact envelope and policy schema package with negative
   fixtures only;
2. local observer event-copy interface with no adapter or execution output;
3. durable state schema and restart/idempotency test harness;
4. runtime registry and signed artifact exchange prototype using test keys;
5. append-only audit store prototype with failure injection; and
6. observer comparison dashboard/report with no action controls.

These are candidates, not created tasks. This plan does not assign task IDs,
authorize implementation, or start TASK_059.

## 21. Phase Closure Acceptance

A phase closes only when its deliverables, prohibited-capability checks, metrics,
negative tests, recovery drills, audit evidence, open risks, and rollback evidence
are reviewed. Mandatory advisory and User Decision requirements are evaluated
under the active policy. Closure does not authorize the next phase.

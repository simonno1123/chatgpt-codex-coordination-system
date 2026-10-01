# ACOS v2 Controlled Runtime Integration Architecture

## 1. Status And Scope

This document defines the target architecture for moving ACOS from fixture-only
shadow validation to controlled cross-agent operation. It is an architecture
baseline, not an implementation or deployment authorization.

The design is observer-first and non-executing. It does not create a workflow
engine, database, adapter, identity service, sandbox, Git wrapper, signing
service, provider connection, or enforcement path.

The central rule is:

```text
Agent message != trusted artifact
Trusted artifact != execution authorization
Validation PASS != real execution
```

## 2. Executive Summary

ACOS should use a central governance control plane to mediate every artifact,
state transition, and execution request. Agents never call one another or the
execution layer directly. Authenticated runtime adapters exchange signed,
versioned artifact envelopes with the orchestration engine. The engine validates
identity, policy, workflow state, and bounded authority before routing an
artifact or issuing a short-lived, one-time capability to an isolated sandbox.

The initial operational target is Observer Mode. It consumes copies of real
events, evaluates the same machine policy intended for future enforcement, and
compares shadow recommendations with human decisions. It cannot block, mutate,
authorize, or send execution commands. Human-approved Semi-Automation follows
only after durable state, identity, audit, recovery, and error-rate evidence are
accepted. Blocking enforcement remains a later, separately authorized phase.

## 3. Existing Baseline

### 3.1 Design Baseline

This architecture refines, and does not replace:

- TASK_040 Runtime Isolation Architecture
- TASK_041 Runtime Role Permission Matrix
- TASK_042 Filesystem Permission Model
- TASK_043 Git Operation Separation Policy
- TASK_044 Audit Trail Specification
- TASK_045 Local Runtime Prototype Plan
- TASK_046 External Advisory Trigger Policy
- TASK_050 Shadow Implementation Roadmap

### 3.2 Shadow Component Baseline

TASK_051 through TASK_057 provide deterministic fixture-only evidence for:

- runtime identity and artifact authority;
- filesystem path classification;
- Git operation separation;
- audit event validation and hash chaining;
- mandatory advisory review gates;
- User Decision gates; and
- cross-component scenario aggregation.

These tools are shadow prototypes. Their PASS results are not live identities,
authorizations, durable state, or production enforcement.

### 3.3 Authority Invariants

The runtime architecture must preserve:

```text
User Decision to start task != edit authorization
Edit authorization != stage authorization
Stage authorization != commit authorization
Commit authorization != push authorization
Push authorization != release authorization
Advisory accepted != ChatGPT final decision
Audit recorded != operation authorized
Observer Mode != Enforcement Mode
```

## 4. Target Architecture

```text
User Decision Interface
        |
        v
Governance / Orchestration Engine
        |
        +--> Artifact Validator + Policy Engine
        |
        +--> Durable Workflow State Store
        |
        +--> Audit Event Store / Provenance Ledger
        |
        v
Runtime Adapter Boundary
  +----------------+----------------+-------------------+
  | ChatGPT Review | Codex Executor | External Advisory |
  +----------------+----------------+-------------------+
        |
        v
Execution Authorization Broker
        |
        v
Execution Sandbox + Filesystem/Git Gates
        |
        v
Execution Receipt -> Orchestrator -> Audit / Review
```

No adapter may bypass the orchestration engine. No sandbox accepts an agent
message as authority. Every mutating operation requires an unexpired,
operation-specific capability bound to workflow, project, task, runtime,
session, paths, repository state, and expected predecessor artifacts.

## 5. Trust Boundaries

| Boundary | Trusted Input | Untrusted Until Validated | Required Control |
| --- | --- | --- | --- |
| User interface to control plane | authenticated user session | displayed text, client metadata | explicit confirmation receipt, anti-CSRF/session binding, action summary |
| Adapter to control plane | registered runtime credential | agent output and model claims | mutual authentication, signed envelope, schema and policy validation |
| Control plane to state store | authenticated service identity | retries and duplicate requests | transaction, idempotency key, optimistic lock |
| Control plane to sandbox | one-time capability | commands, paths, environment requests | capability verification, default deny, resource limits |
| Sandbox to repository | canonical project binding | paths, symlinks, Git state | realpath checks, path manifest, repository and HEAD binding |
| Sandbox to remote Git | push-specific capability | remote response and concurrent changes | remote binding, non-force policy, receipt and reconciliation |
| Audit writer to audit store | append credential | event payload | append-only policy, signature, sequence and hash-chain checks |
| Observer plane to production | read-only event copy | shadow recommendation | no write route, no execution route, explicit non-authorizing label |

Compromise of one adapter must not grant another runtime identity or direct
access to the state store, signing keys, audit history, or execution sandbox.

## 6. Component Model

| Component | Responsibility | Must Not Do |
| --- | --- | --- |
| Artifact Gateway | receive, size-limit, canonicalize, and validate envelopes | infer missing authority or repair unsigned content |
| Policy Engine | evaluate one signed policy release against facts | generate User Decisions or expand scope |
| Workflow Engine | enforce state transitions and idempotency | skip DENY/BLOCKED gates |
| Authorization Broker | mint bounded one-time capabilities after valid decisions | combine edit, commit, push, or release authority |
| Runtime Registry | bind runtime, role, credential, session, environment, and capabilities | trust provider/model labels as identity |
| Runtime Adapters | translate provider transport to artifact protocol | decide governance outcomes |
| Sandbox Controller | create and terminate constrained execution attempts | accept free-form messages as capabilities |
| Filesystem Gate | enforce canonical path capabilities | infer parent, prefix, or symlink authority |
| Git Gate | enforce operation-specific repository capabilities | remediate with pull, rebase, reset, clean, or force push |
| State Store | persist workflows, artifacts, decisions, consumption, and attempts | treat audit records as authority |
| Audit Writer | append signed events and integrity links | alter workflow decisions or rewrite history |
| Reconciler | compare execution receipts, local state, and remote evidence | claim attribution without evidence |
| Observer Evaluator | shadow-evaluate real event copies | block, mutate, authorize, or route execution |

## 7. Artifact Protocol

### 7.1 Envelope

Every artifact uses a machine-readable envelope. Payload schemas are selected by
`artifact_type` and `schema_version`.

| Field | Requirement | Purpose |
| --- | --- | --- |
| `artifact_id` | required, immutable | globally unique artifact identity |
| `artifact_type` | required | USER DECISION, TASK, RESULT, BLOCKED RESULT, REVIEW, ADVISORY REQUEST, ADVISORY REVIEW, DECISION, AUTHORIZATION, AUDIT EVENT, EXECUTION RECEIPT, ERROR/BLOCKER RECORD |
| `schema_version` | required | selects envelope and payload validation rules |
| `producer` | required | human-readable producer role |
| `producer_runtime_id` | required except offline import | authenticated runtime binding |
| `project_id` | required | canonical project registry identity |
| `task_id` | required for task-scoped artifacts | task binding |
| `workflow_id` | required | durable workflow binding |
| `parent_artifact_id` | conditional | immediate lifecycle predecessor |
| `correlation_id` | required | groups retries and related artifacts |
| `created_at` | required | trusted service timestamp or declared untrusted timestamp |
| `expires_at` | conditional | limits time-sensitive authority |
| `sequence` | required per workflow stream | ordering and replay detection |
| `scope` | required for actionable artifacts | exact project, paths, operation, branch, HEAD, and constraints |
| `requested_action` | conditional | one action class only |
| `authority_type` | required for decisions/authorizations | user, review, commit, push, release, exception, or none |
| `authorization_id` | conditional | references a durable authorization record |
| `policy_version` | required | exact evaluated machine policy release |
| `content_digest` | required | digest of canonical envelope-without-signature plus payload |
| `signature` | required for trusted ingestion | signature and key identifier |
| `nonce` | required for actionable artifacts | uniqueness and replay defense |
| `replay_protection` | required for actionable artifacts | one-time/reusable class and consumption constraints |
| `to` | required | immediate receiver identity or control-plane endpoint |
| `next_receiver` | required | expected next lifecycle receiver |
| `status` | required | draft, pending, accepted, denied, blocked, revoked, superseded, consumed, or completed |
| `payload` | required object | artifact-specific content |

### 7.2 Parsing And Compatibility

1. Parsing is fail-closed for missing fields, duplicate JSON keys, invalid UTF-8,
   excessive size/depth, unsupported versions, non-canonical numbers, or unknown
   critical extensions.
2. Unknown fields are rejected by default. A versioned `extensions` object may
   carry explicitly non-authorizing data; policy ignores it unless registered.
3. Minor schema versions may add optional non-authorizing fields. Required-field,
   authority, signature, canonicalization, or lifecycle changes require a new
   incompatible version and migration.
4. Compatibility is declared by the policy release, not inferred by adapters.
5. Deprecated versions may be read for audit but cannot create new authority.

### 7.3 Canonicalization, Digest, And Signature

- Canonicalization uses one published deterministic JSON profile.
- `content_digest` covers the canonical envelope excluding `signature`, plus the
  canonical payload and referenced target digests when required.
- The signature covers the digest, artifact ID, workflow ID, sequence, nonce,
  policy version, and expiry.
- Signature verification occurs at the Artifact Gateway against Runtime Registry
  keys. Adapters never mark their own signature as trusted.
- Observer Mode may ingest unsigned historical copies only as `UNTRUSTED_IMPORT`;
  they cannot enter an authorization state.

### 7.4 Replay, Revocation, And Supersession

- `(artifact_id, nonce, producer_runtime_id)` is unique.
- Actionable artifacts are recorded before routing.
- One-time authorization consumption is atomic with execution-attempt creation.
- A retry with the same idempotency key returns the prior outcome.
- A duplicate with different content is blocked and audited.
- Revocation prevents new consumption and attempts to cancel unstarted work.
- Supersession creates a new artifact linked to the old one; history is retained.
- Expired, stale, revoked, superseded, or consumed authority cannot be refreshed
  by an adapter or agent.

## 8. Durable Workflow State

### 8.1 Core Records

The state model persists Workflow, Project, Task, Artifact, Authorization,
AuthorizationConsumption, RuntimeSession, AdvisoryLifecycle,
UserDecisionLifecycle, ExecutionAttempt, Commit, Push, Release, AuditEvent,
Blocker, RecoveryDecision, and ProvenanceException.

Every mutable record carries `version`, `created_at`, `updated_at`, and immutable
identity fields. State transitions reference the triggering artifact and policy
release. Chat history may be attached as context but is not workflow state.

### 8.2 State Machines

```text
Task: proposed -> user_authorized -> issued -> executing -> result_received
      -> review_pending -> accepted|rework|blocked -> closed

Authorization: proposed -> issued -> reserved -> consumed|released
               -> expired|revoked|superseded

ExecutionAttempt: created -> capability_issued -> running
                  -> succeeded|denied|blocked|failed|cancelled|unknown

Push: authorized -> reserved -> attempted -> confirmed|rejected|unknown
      -> reconciled_external
```

Illegal transitions are blocked. State changes and audit appends occur in one
transaction or through a transactional outbox that fails closed before any
mutating external action.

### 8.3 Concurrency And Idempotency

- Initial deployment uses optimistic concurrency with row versions and a single
  workflow owner lease.
- Authorization reservation uses a uniqueness constraint and atomic compare-and-
  set; only one execution attempt can consume a one-time authorization.
- Every inbound request has an idempotency key scoped to runtime and workflow.
- Multi-client races return the winning durable result rather than replaying the
  operation.
- Long operations use leases with bounded renewal and explicit `unknown` state
  after loss of contact.
- Remote reconciliation never rewrites the original attempt; it appends evidence
  and a RecoveryDecision.

### 8.4 Initial Storage Recommendation

Use SQLite in WAL mode for a local, single-host, single-project observer pilot,
with one state-writer process and explicit backups. Move to PostgreSQL before
multi-host, multi-project, or concurrent enforcement. The data-access contract,
migrations, constraints, and transaction tests must be database-independent.

## 9. Runtime Identity

### 9.1 Identity Record

A runtime identity record includes runtime instance ID, agent role, session ID,
environment ID, project binding, credential/key binding, allowed capabilities,
allowed paths, network policy, issued/expiry times, attestation level, software
digest, and revocation state.

`allowed capabilities` and `credential/key binding` are identity-associated
binding/metadata, not operation authority. Identity or credential possession
does not authorize an operation. Capability authority requires an explicit
authorization reference, execution identity, CapabilityEnvelope, exact scope,
baseline, and expiry/consumption constraints under Section 24.

Required identities are:

- ChatGPT Review Runtime
- Codex Executor Runtime
- External Advisory Runtime
- Automation Runtime
- User Decision Source
- Governance Engine
- Sandbox Executor
- Audit Writer

Model or provider name is descriptive metadata, not identity.

### 9.2 Authentication And Sessions

- Local adapters use Unix-domain sockets with operating-system peer credentials
  plus application mutual authentication.
- Cross-host adapters require mutually authenticated encrypted transport.
- Runtime registration is approved by governance and binds role, key, software
  digest, environment, and project scope.
- Sessions are short-lived and receive narrower capabilities than registration.
- Heartbeats prove liveness, not authority. Expired sessions cannot sign new
  actionable artifacts.
- Runtime, session, and key revocation propagate to the Artifact Gateway,
  Authorization Broker, and Sandbox Controller.

### 9.3 Key Lifecycle And Impersonation Detection

- Separate signing keys by runtime identity and environment.
- Store private keys outside agent-visible project files.
- Rotate keys with overlap for verification only; new signatures use the latest
  active key.
- Audit unknown keys, role/key mismatches, impossible session overlap, invalid
  attestation, nonce reuse, and producer/runtime mismatch.
- A compromised provider cannot select a more privileged runtime role.

## 10. Governance And Orchestration Engine

For each artifact, the engine:

1. authenticates the transport and runtime;
2. parses and verifies the envelope;
3. loads the exact signed policy release;
4. validates producer, authority, scope, and lifecycle state;
5. records the artifact and idempotency result;
6. evaluates advisory and User Decision requirements;
7. returns DENY/BLOCKED without routing when a gate fails;
8. routes to the authorized next receiver;
9. issues a bounded capability only after all gates pass;
10. records audit events through the transactional outbox; and
11. reconciles an execution receipt without treating it as acceptance.

It cannot generate User Decisions, forge advisory output, enlarge a ChatGPT
Decision, auto-authorize commit/push/release, or continue past an unsatisfied
gate. Drafting an artifact is separate from signing or accepting it.

## 11. Runtime Adapters

| Adapter | Inbound | Outbound | Authentication | Retry And Idempotency | Boundary |
| --- | --- | --- | --- | --- | --- |
| ChatGPT Review | RESULT, BLOCKED RESULT, ADVISORY REVIEW, decision request | TASK, REVIEW, DECISION, advisory request draft | registered runtime key and session | retry reads/drafts; signed artifact ID is idempotent | cannot impersonate Codex, advisory, or user |
| Codex Executor | signed TASK and operation capability | RESULT, BLOCKED RESULT, execution receipt | runtime key plus sandbox session | retry only before consumption or by same attempt ID | cannot self-review or broaden paths/actions |
| External Advisory | signed read-only request bundle | ADVISORY REVIEW | advisory runtime key and session | same request/review ID returns same result | no write, Git, task, decision, or direct Codex route |
| User Decision | exact confirmation request | USER DECISION or denial receipt | user session with assurance level | duplicate submission resolves to one decision | no inferred consent or advisory substitution |
| Automation | deterministic check TASK | RESULT or RECORD | service identity | bounded retry with idempotency key | no review, decision, commit, or push |

Every adapter defines timeout, cancellation, rate limit, maximum artifact size,
error mapping, capability list, and audit events. Adapter timeout yields unknown
or blocked state; it never yields implicit success.

## 12. Execution Sandbox

The sandbox is created for one execution attempt from a verified capability.
Its profile includes:

- canonical project root and immutable project identity;
- read-only and writable path manifests;
- process and command-class allowlists;
- network deny-by-default with explicit destinations when separately approved;
- credential isolation and environment-variable filtering;
- CPU, memory, wall-time, process-count, file-count, and output-size limits;
- filesystem and Git gates in front of mutating operations;
- subprocess monitoring and termination;
- no access to control-plane signing or state-store credentials; and
- a signed execution receipt with attempted and actual effects.

Separate profiles exist for read-only validation, edit, test, stage, commit,
push, release, and deployment. A capability for one profile cannot activate a
later profile. Cleanup preserves evidence and never deletes user work without a
separate destructive-action authorization.

## 13. Filesystem And Git Enforcement

### 13.1 Filesystem Capability

A path capability binds project ID, canonical root, exact paths or safe glob
semantics, operation, runtime/session, task, authorization, expiry, inode or
snapshot information where feasible, and a nonce. Enforcement performs
realpath normalization after opening paths, rejects traversal and prefix
confusion, verifies symlink targets, prevents writable-parent replacement, and
rechecks before commit.

Submodules and linked worktrees are separate registered project roots. `.git/`,
hooks, credentials, and protected ACOS paths are denied unless a dedicated
governance task and profile explicitly allows them.

### 13.2 Git Capabilities

Each operation has a separate capability:

- stage: exact reviewed path manifest and expected worktree identity;
- commit: exact staged-tree digest, branch, HEAD, message digest, and review;
- push: exact commit/range, remote URL, upstream, branch, expected remote tip,
  non-force policy, and one-time authorization;
- release: exact release target and independent release authorization.

The gate verifies repository root, worktree identity, branch, HEAD, upstream,
ahead/behind/divergence, dirty state, hidden files, submodules, staged manifest,
commit message, and authorization consumption. It never auto-runs pull, merge,
rebase, reset, clean, amend, or force push.

### 13.3 Hook, Wrapper, And Server Boundaries

- A local hook is defense in depth and cannot be the sole authority source.
- A controlled Git wrapper or sandbox syscall/process gate enforces local
  operation capabilities.
- Server-side branch protection prevents force push and unreviewed updates where
  supported.
- The orchestrator reconciles local receipts with independently observed remote
  state before marking push complete.

### 13.4 Remote-Sync Provenance Exception

When a commit appears remotely before the authorized runtime reports success:

1. mark the push attempt `UNKNOWN` and open a ProvenanceException;
2. do not repeat the push or claim Codex attribution;
3. record local HEAD, remote tip, ancestry, observation time, and available
   server-side actor/session evidence;
4. compare the remote commit with the authorized commit/range;
5. determine whether the authorization was reserved or consumed;
6. require ChatGPT Review or User Decision for disposition when attribution is
   incomplete; and
7. classify the outcome as `CONFIRMED_AUTHORIZED`, `RECONCILED_EXTERNAL`,
   `DUPLICATE_NO_OP`, `UNAUTHORIZED_REMOTE_CHANGE`, or `BLOCKED_UNKNOWN`.

Reliable attribution requires both a signed sandbox receipt and independent
remote evidence. Matching commit hashes alone prove content presence, not who
performed the push.

## 14. Audit And Provenance

The production audit store is append-only and records event ID, sequence,
workflow/task/artifact IDs, actor/runtime/session, authorization, state before
and after, requested and actual action, result, commit, remote receipt, trusted
timestamp source, error/blocker, previous hash, event hash, signature, and
provenance confidence.

Audit events are written through a narrow Audit Writer identity. The writer may
append but cannot authorize, alter workflow decisions, or delete history.

Audit availability is fail-closed for capability issuance, authorization
consumption, mutating sandbox start, commit, push, release, and policy change.
Read-only observer ingestion may continue into a bounded local spool when the
primary store is unavailable, but its output is marked incomplete and cannot
support enforcement decisions.

Deletion, reorder, modification, insertion, duplicate sequence, chain fork, and
signature failure create integrity incidents. External anchoring or periodic
signed checkpoints may raise provenance confidence but do not become authority.

## 15. User Decision Integration

The User Decision interface displays the exact action, project, task, paths,
branch, HEAD, remote, expiry, one-time/reusable status, risk classification,
forbidden actions, and consequence summary. Confirmation produces a signed
receipt bound to the authenticated user session and assurance level.

The interface must prevent default consent, silent consent, broad interpretation
of "continue," cross-project/session reuse, task-start-to-Git inheritance, stale
decision reuse, and presentation of advisory recommendations as user choices.
Revocation and supersession are first-class records. A decision can authorize
only its exact declared action and scope.

## 16. External Advisory Integration

The engine evaluates mandatory triggers from the signed machine policy and
generates an ADVISORY REQUEST containing request ID, project/task, read-only
target bundle, reference bundle, target/reference digests, questions, and the
required declaration. The External Advisory Adapter returns a signed ADVISORY
REVIEW bound to the request, reviewer runtime, targets, references, and policy.

Stale, duplicate, superseded, wrong-target, wrong-project, or executing reviews
are denied or blocked. ChatGPT Review records consumption and addresses material
findings before a final decision. Advisory output cannot modify files, generate
User Decisions or ChatGPT Decisions, authorize Git/release, start another task,
or route directly to Codex.

## 17. Unified Policy Engine

ACOS should replace duplicated component mappings with one versioned,
machine-readable policy release containing runtime roles, artifact authority,
requirement and advisory categories, User Decision mappings, path policies, Git
policies, lifecycle order, aggregation precedence, contract versions, and risk
levels.

Each release has a schema version, semantic policy version, canonical digest,
signing key, compatibility range, effective time, migration notes, and rollback
target. Components declare the exact compatible range and refuse unsupported or
unsigned policy. Rollout is observer-first, then canary, then explicit promotion.

Governance Markdown remains the human-reviewable normative explanation. The
machine policy is the executable source for runtime evaluation. A policy release
is accepted only when generated/reviewed together with traceability tests that
map every machine rule to its governance section. CI blocks digest drift,
unmapped rules, stale fixtures, unsupported contracts, and documentation/policy
version divergence. Markdown alone cannot silently change enforcement.

TASK_051-057 migrate incrementally from embedded maps to injected, signed policy
snapshots after separate tasks and compatibility tests. TASK_058 does not modify
them.

## 18. Failure And Recovery

| Failure | Detection / Classification | Stop Or Continue | Required Authority / Recovery | Audit And Idempotency |
| --- | --- | --- | --- | --- |
| Agent timeout | adapter deadline | block actionable step | ChatGPT Review chooses retry/cancel | same attempt ID; no duplicate action |
| Adapter unavailable | health and transport failure | block dependent route | retry policy or User Decision defer | record outage and retries |
| Duplicate RESULT | artifact/idempotency collision | return prior result or block conflict | ChatGPT Review for content conflict | preserve both digests |
| Lost DECISION | durable state lacks accepted decision | block | re-display/reissue through proper producer | never infer from chat |
| Workflow restart | lease expiry and recovery scan | pause mutations | engine resumes from durable state | idempotent transition replay |
| Expired authorization | trusted time check | deny | new decision/authorization | record expiration, no refresh |
| Revocation during execution | revocation event/heartbeat | terminate when safe; mark uncertain effects | RecoveryDecision | receipt records partial effects |
| Partial file edit | before/after manifest mismatch | block later Git steps | bounded recovery task | preserve diff and sandbox evidence |
| Test failure | signed test receipt | stop commit path | REWORK or explicit bounded exception | same test attempt is immutable |
| Commit succeeded, receipt lost | Git object exists but attempt unknown | no repeat commit | reconcile tree/message/parent, ChatGPT Review | mark reconciled, not newly executed |
| Push outside orchestrator | remote tip differs without receipt | no repeat push | provenance exception disposition | append remote evidence/confidence |
| Concurrent remote change | expected-tip mismatch | block push | new review and push authorization | old capability consumed or revoked |
| Audit write failure | outbox/store error | block mutations | restore audit service or explicit recovery | no authority from local logs |
| Policy update mid-workflow | version mismatch | pin existing safe version or block | policy migration decision | record old/new policy and migration |
| Advisory unavailable | adapter failure/timeout | block mandatory path | defer or explicit User Decision override per policy | no silent downgrade |
| User Decision pending | state remains pending | wait; no actionable route | user responds, expires, or cancels | idempotent confirmation request |
| Conflicting User Decisions | overlapping active scopes | block | user clarification and supersession | preserve both decisions |

Recovery never uses destructive Git commands, silently widens scope, rewrites
audit history, or treats evidence as authority.

## 19. Deployment Topology

### 19.1 Initial Local Observer Topology

- one local orchestration process;
- one SQLite state database with single writer;
- separate local Unix-socket adapter endpoints;
- read-only copies of artifacts/events;
- append-only audit prototype store;
- no sandbox execution route; and
- a physical observer kill switch.

### 19.2 Later Controlled Topology

- PostgreSQL state store and transactional outbox;
- isolated control-plane, audit, and sandbox identities;
- mutually authenticated adapters;
- short-lived authorization capabilities;
- container sandbox for mutating operations;
- independent remote reconciliation; and
- server-side Git protections.

Production topology requires separate implementation, security review, and User
Decision. No provider credential belongs in the repository.

## 20. Legacy Architecture Recommendations (Non-Frozen)

LEGACY / NON-FROZEN RECOMMENDATIONS. The historical recommendations below are
retained as architecture context. A specific recommendation has normative
force only when expressly incorporated by a frozen decision under Section 24.
The table does not independently freeze WAL, PostgreSQL migration, Unix
sockets, mTLS, lease algorithms, polling, container topology, manual approval
UI, or a specific Git enforcement stack.

| Decision | Recommendation | Alternatives | Rationale / Security Impact | Complexity / Migration |
| --- | --- | --- | --- | --- |
| Initial durable state | SQLite, WAL, single writer for local observer | PostgreSQL immediately | minimizes pilot operations while preserving transactions; not suitable for multi-host concurrency | low initially; repository/data layer must support migration to PostgreSQL before enforcement |
| Production durable state | PostgreSQL | SQLite, distributed KV | strong constraints, locking, recovery, and operational tooling | medium; migrate via versioned schema and reconciliation |
| Local adapter transport | Unix socket plus peer credentials and app mutual auth | loopback HTTP, gRPC | narrows local network exposure and supports OS identity | low-medium; retain transport-neutral envelope for later mTLS HTTP/gRPC |
| Cross-host transport | mTLS HTTP/gRPC | raw TCP, message queue first | authenticated encryption and explicit contracts | medium; adapter interface hides transport change |
| Coordination model | central orchestrator | distributed peer coordination | one state machine and policy point prevents agents trusting peers | medium; scale central service before considering partitioning |
| Artifact format | signed canonical JSON envelope | JWT, PASETO-style token only | inspectable payload and flexible references; authorization capability may use a compact token | medium; define canonicalization/signing profile, later add token projection |
| Authorization token | short-lived signed capability referencing durable record | full artifact as bearer token, JWT-only state | bounded claims plus server-side revocation/consumption | medium; start opaque local capability, add signed portable form later |
| Sandbox | process isolation for observer/read-only; container isolation before mutation | process-only production, VM | staged complexity; container adds filesystem/network/credential separation | medium-high; validate process prototype, then require container security gate |
| Git enforcement | sandbox wrapper + server-side protection; hook as defense in depth | hook-only, wrapper-only | hook alone is bypassable; server controls remote integrity | high; observer checks, local wrapper, then protected remote |
| Audit store | database-backed append log with hash chain and signed checkpoints | JSONL file, external ledger | transactions and queryability; integrity evidence remains separate from authority | medium; JSONL export/import for prototype, migrate before enforcement |
| Project rollout | single ACOS project first | multi-project immediately | limits blast radius and policy ambiguity | low; add project registry and isolation before controlled instances |
| Adapter activation | polling in initial observer, event-driven later | event-driven immediately | easier recovery and no production coupling during observation | low initially; introduce transactional outbox/events after state is stable |
| User approval | manual dedicated approval UI first | chat-only approval, fully integrated UI | exact scope and anti-spoofing are clearer than ambiguous chat text | medium; local UI, then integrated identity-aware approval surface |

## 21. Open Decisions

1. Exact canonical JSON and signature algorithms, key custody, and trust roots.
2. User identity assurance requirements for start, commit, push, release, and
   destructive actions.
3. Minimum remote Git provider evidence required for high-confidence attribution.
4. Container runtime and host operating-system support matrix.
5. Policy language and compiler/tooling ownership.
6. Observer sample sizes and acceptable false-positive/false-negative thresholds.
7. Audit retention, privacy, redaction, backup, and external checkpoint policy.
8. Disaster-recovery objectives for state and audit stores.
9. Whether push/release execution needs a future dedicated Release Runtime.
10. Multi-project tenancy, data isolation, and operator roles.

Each open decision requires a separate governance artifact and, where required,
External Advisory Review and User Decision.

## 22. Acceptance Criteria

This architecture is acceptable when reviewers confirm that:

- no agent can directly invoke another agent or execution layer;
- artifacts, identity, policy, state, authorization, execution, and audit are
  separate trust domains;
- User Decision, ChatGPT Decision, Advisory Review, audit, and execution receipt
  cannot substitute for one another;
- edit, stage, commit, push, release, and deployment remain separately gated;
- one-time consumption, replay prevention, restart recovery, and race handling
  are durable and fail-closed;
- remote-sync provenance exceptions do not create false attribution;
- Observer Mode has no mutation or execution route;
- policy duplication has a concrete migration path to one signed source;
- every mutating phase has rollback, audit, and independent review; and
- implementation and enforcement require later explicit authorization.

## 23. Non-Goals

TASK_058 does not implement any component described here. It does not connect a
real agent, repository, instance, Git remote, user identity, advisory provider,
or audit service. It does not modify TASK_051-057 and does not authorize TASK_059.

## 24. Frozen Runtime Integration Design Baseline

This section materializes User Decision
`ACOS-V2-RUNTIME-INTEGRATION-DESIGN-BASELINE-01-DECISION-01`. It is a design
baseline only. It narrows the initial runtime integration path without
implementing, deploying, activating, or authorizing any component. D-07 is
bound to User Decision
`ACOS-V2-RUNTIME-INTEGRATION-DESIGN-D07-STATE-JOURNAL-WRITER-DECISION-01`.

Section 24 Frozen Runtime Integration Design Baseline, together with
subsequently approved numbered frozen decisions, takes normative precedence
over Sections 1-23. Sections 1-23 remain background, candidate design,
recommendation, or historical architecture context unless expressly
incorporated by a frozen decision. Normative-looking legacy wording does not
itself create implementation authority, capability authority, transition
authority, or additional frozen decisions. Choices outside D-01 through D-07
remain subject to their own later review and authorization.

### 24.1 Objective And Architectural Position

The proposed integration places durable task state and capability checks
between governance decisions and executor-side effects. The runtime enforces
already-established authority; it cannot manufacture governance authority from
an agent message, schema-valid artifact, advisory opinion, or execution result.

### 24.2 Role And Authority Model

| Role | Owns | Does not own |
| --- | --- | --- |
| User Decision | Explicit decisions for reserved user gates, including Activation and Operational Entry | Executor identity or automatic task execution |
| ChatGPT Review | Bounded TASK, REVIEW, and DECISION judgment and handoff within its established scope | Executor-side capability expansion or unapproved external mutation |
| Codex Executor | Execution of a received, bounded task and RESULT or BLOCKED RESULT production | REVIEW, DECISION, self-acceptance, or state-transition authority |
| External Advisory Reviewer | Non-binding advisory evaluation returned to ChatGPT Review | Blocking, execution, decision, or transition authority |

Role labels alone prove neither identity nor authority. The runtime must bind
each actor to an independently established authorization source and the exact
action being attempted.

### 24.3 Runtime Identity Model

An execution attempt is bound to `project_id`, `stage_id`, `task_id`,
`authorization_id`, `executor_role`, `execution_attempt_id`,
`baseline_revision`, and `capability_scope`. The attempt ID identifies one
materialization attempt, including retries only where explicitly authorized.
The identity record must be attributable to the actual executor, not merely to
a declared `PRODUCER` field. Missing or conflicting bindings fail closed.

### 24.4 Durable State Architecture

D-01 freezes an append-only event journal plus a derived current-state
projection. The journal preserves ordered events and their authority/evidence
references; the projection is rebuildable and cannot invent authority. D-02
freezes SQLite with a single logical state writer for the initial durable
store. This keeps journal append and projection update under one transactional
ordering boundary. SQLite is an initial storage choice, not a grant to create a
database in this design-materialization task or to enable multi-writer runtime
use.

D-07 places State Journal Writer, a narrow authenticated persistence identity,
inside the governed State Store boundary. It is not an additional top-level
runtime component. State Journal Writer alone appends accepted authoritative
transitions and updates the derived projection in the same durable transaction
under the single-logical-writer rule. Audit Writer remains a separate
audit/provenance writer.

The only authoritative state-event write path is:

```text
candidate event
-> authentication
-> authority/state/scope/baseline/gate validation
-> accepted transition record
-> State Journal Writer
-> atomic journal append + projection update
```

Event submission, authority validation, authoritative append, and projection
derivation are distinct operations and authorities. Generic datastore access
does not grant access to this authoritative append path.

### 24.5 State Ownership Rules

- Authority is owned by the applicable User Decision or ChatGPT Review
  decision source, never by an executor receipt or database row alone.
- Durable state is owned by the governed state store; its journal is evidence
  of transitions, and its projection is a derived view. State Journal Writer
  is its only logical authoritative append authority.
- External systems may be mutated only by an executor holding an exact,
  unexpired capability for that operation and execution identity.
- The transition engine may advance task state only on a valid, separately
  attributable governance event and satisfied gates. Codex Result is evidence
  to be recorded and reviewed, not state-transition authority.

State Journal Writer has no governance decision authority,
transition-selection authority, or capability-expansion authority. Codex
Executor, Runtime Adapter, Orchestrator, Transition Engine, Audit Writer, and
generic datastore access cannot bypass its accepted-transition write path.

### 24.6 Transition Engine And Orchestrator Boundary

D-03 freezes the orchestrator as an enforcement and routing component only. It
checks identity, predecessor state, authority reference, scope, and baseline
before routing. It cannot author REVIEW or DECISION, accept its own result, or
promote a task after RESULT receipt without the required review/decision event.
A failed check records a blocked outcome without widening the requested action.

Transition Engine validates candidate transitions, including submitting
identity, governance authority reference, predecessor state, scope, baseline,
and required gates. It does not directly persist authoritative state
transitions. Only the accepted transition record may enter State Journal
Writer's append path. `Transition Engine != authoritative journal writer`;
`State Journal Writer != governance decision source`.

### 24.7 CapabilityEnvelope Model

D-04 requires explicit grants per execution identity and default deny. A
CapabilityEnvelope binds the authorization reference, attempt identity,
project, stage, task, exact operation, exact target paths/resources, baseline,
expiry, and consumption conditions. Candidate operation classes are
`filesystem.read`, `filesystem.write`, `test.execute`, `git.stage`,
`git.commit`, `git.push`, `sandbox.execute`, `network.read`, and
`external.write`. Listing a class here grants none of them. Read never implies
write; test never implies Git; stage, commit, and push require separate exact
grants. A broader parent path or role name cannot substitute for exact scope.

### 24.8 Materialization Boundary

Materialization requires one authenticated execution identity and an exact
artifact/action authorization. A physical writer cannot claim another role's
producer authority through metadata or a TASK. Governance artifacts remain
governed by their artifact-type authority rules. Repository durability, local
file presence, and governance persistence are distinct; none alone grants an
execution capability or resolves the governance-owned writer gap.

### 24.9 Baseline And Drift Gate

Before an effect, compare the bound `baseline_revision` with the current
repository or target-state revision and verify the exact approved manifest.
Missing, stale, diverged, or ambiguous baselines fail closed. Drift triggers a
new review/authorization path; the executor does not self-rebase, reset, or
silently substitute a newer baseline.

### 24.10 Failure Taxonomy

Distinguish `DENIED` (authority/scope rejection), `BLOCKED` (missing gate or
unavailable dependency), `FAILED` (known unsuccessful attempt), `STOPPED`
(terminated current attempt), and `UNKNOWN` (effect or attribution cannot be
proven). `QUARANTINED` and `PRESERVE_ONLY` constrain evidence handling. None
of these outcomes may be promoted to success by inference from a partial
receipt, timeout, or valid schema.

### 24.11 STOP And Retry Semantics

STOP terminates the current execution attempt and consumes no implied next
step. A retry requires new authority or an explicit retry scope bound to the
same governed action, baseline, and evidence. Unknown effects are reconciled
before any retry; the executor cannot use an idempotency label to justify a new
external mutation.

### 24.12 Evidence Preservation Model

Historical and failed scenes retain their original attribution and lifecycle
classification. `PRESERVE_ONLY` evidence cannot become disposable by default,
cleanup convenience, or a later PASS. Corrections append new evidence rather
than rewriting the old event. A digest or Git commit proves content identity
or repository presence, not actor authority or governance acceptance.

### 24.13 Git Adapter Design

D-05 ties a GitHub checkpoint to an accepted stage-closure event; there is no
scheduled automatic push. Stage closure and repository checkpoint are
separate states. The adapter requires an approved exact-path checkpoint
manifest and distinct stage, commit, and push capabilities. Push checks the
expected remote tip and verifies the observed remote ref afterward. It never
uses force, pull/rebase/reset, or hidden restaging as recovery. `CHECKPOINTED`
is repository durability, not Activation.

### 24.14 Codex And Agent Integration Model

An Execution Package carries task identity, authority reference, baseline,
capability scope, inputs, output contract, stop conditions, and next receiver.
Only an explicitly granted package can start an attempt. A Result Package
returns actual effects, evidence digests, failures, and `TO` / `NEXT RECEIVER`
to ChatGPT Review. `RESULT` and `BLOCKED RESULT` do not select the next
governance state or acquire REVIEW/DECISION authority.

### 24.15 External Advisory Layer

Advisory material is a non-binding input to ChatGPT Review. It may identify
risks, but External Advisory is not blocking authority, execution authority,
or decision authority. The transition engine checks any separately required
review gate; it does not treat the advisor's output itself as a grant.

### 24.16 Rollout Model

D-06 freezes R0 Observer followed by selected R1 Guarded Semi-Automation,
subject to separate gates. R0 observes and compares without authorizing or
mutating. R1 may only perform individually approved, bounded actions with
enforced capabilities and review gates. R2 full enforcement is not an initial
rollout step and is not authorized by this baseline.

### 24.17 Minimal Runtime Components

The design names six logical responsibilities: Authority Resolver validates
the referenced decision; State Store owns journal and projection; Transition
Engine checks allowed state moves; Orchestrator enforces gates and routing;
Capability Broker binds exact operation grants to attempts; Adapter Layer
connects agents and external systems without inheriting their authority.
Naming a component does not authorize its implementation or deployment.

### 24.18 Runtime Invariants

| ID | Frozen invariant |
| --- | --- |
| RI-01 | No execution without explicit authority reference. |
| RI-02 | No authority expansion by executor. |
| RI-03 | No state transition from execution result alone. |
| RI-04 | Every materialization has one execution identity. |
| RI-05 | Baseline mismatch is fail-closed. |
| RI-06 | STOP terminates the current attempt. |
| RI-07 | Retry requires new authority or explicit retry scope. |
| RI-08 | Evidence scene cannot implicitly become disposable. |
| RI-09 | Advisory artifact has zero transition authority. |
| RI-10 | Git push requires approved checkpoint manifest. |
| RI-11 | Stage closure and repository checkpoint are separate. |
| RI-12 | Activation / Operational Entry require User Decision. |

### 24.19 State Skeleton

The governed path retains the following state skeleton; each arrow requires
its own authorized transition event, and the two `REVIEW_PENDING` positions
represent different review gates:

```text
DRAFT
-> REVIEW_PENDING
-> AUTHORIZED
-> EXECUTING
-> RESULT_RECORDED
-> REVIEW_PENDING
-> ACCEPTED / RETURNED / BLOCKED
-> STAGE_CLOSED
-> CHECKPOINT_PENDING
-> CHECKPOINTED
```

Independent exceptional states are `STOPPED`, `QUARANTINED`, and
`PRESERVE_ONLY`. A recorded executor result can supply evidence for review but
cannot itself authorize the arrow to acceptance or stage closure.
`STAGE_CLOSED != CHECKPOINTED`.
`CHECKPOINTED != ACTIVATED`.

Codex RESULT may provide execution evidence or a candidate event;
`RESULT_RECORDED` does not automatically produce `ACCEPTED`. ChatGPT Review
and User Decision supply governance decisions according to the applicable
gate. Where a particular transition issuer is not uniquely determined by the
frozen rules, the authority condition remains
`REQUIRES APPLICABLE GOVERNANCE EVENT`.

| Transition | Candidate input / evidence source | Authority condition |
| --- | --- | --- |
| DRAFT -> first REVIEW_PENDING | Candidate event | REQUIRES APPLICABLE GOVERNANCE EVENT |
| REVIEW_PENDING -> AUTHORIZED | ChatGPT Review / User Decision according to the applicable gate | REQUIRES APPLICABLE GOVERNANCE EVENT |
| AUTHORIZED -> EXECUTING | Codex Executor's bounded execution request | Explicit authority reference and capability; REQUIRES APPLICABLE GOVERNANCE EVENT |
| EXECUTING -> RESULT_RECORDED | Codex RESULT execution evidence / candidate event | RESULT is not transition authority; REQUIRES APPLICABLE GOVERNANCE EVENT |
| RESULT_RECORDED -> second REVIEW_PENDING | Recorded execution evidence | REQUIRES APPLICABLE GOVERNANCE EVENT |
| REVIEW_PENDING -> ACCEPTED | ChatGPT Review / User Decision according to the applicable gate | REQUIRES APPLICABLE GOVERNANCE EVENT |
| REVIEW_PENDING -> RETURNED | ChatGPT Review / User Decision according to the applicable gate | REQUIRES APPLICABLE GOVERNANCE EVENT |
| REVIEW_PENDING -> BLOCKED | Candidate gate/decision evidence | REQUIRES APPLICABLE GOVERNANCE EVENT |
| ACCEPTED -> STAGE_CLOSED | Governance closure evidence | REQUIRES APPLICABLE GOVERNANCE EVENT |
| STAGE_CLOSED -> CHECKPOINT_PENDING | Stage-closure evidence triggering checkpoint consideration | REQUIRES APPLICABLE GOVERNANCE EVENT |
| CHECKPOINT_PENDING -> CHECKPOINTED | Git execution and remote verification evidence | Approved checkpoint manifest and separate Git capabilities; REQUIRES APPLICABLE GOVERNANCE EVENT |

Every accepted transition in this skeleton is persisted only through State
Journal Writer after Transition Engine validation. State Journal Writer
appends it and updates the derived projection atomically; neither a candidate
event nor an execution Result can bypass that validation and persistence path.

### 24.20 Frozen Decisions

| ID | Frozen decision |
| --- | --- |
| D-01 | Append-only event journal plus derived current-state projection. |
| D-02 | Initial durable store is SQLite with one logical state writer. |
| D-03 | Orchestrator enforces only; it has no REVIEW or DECISION authority. |
| D-04 | Capability is explicitly granted per execution identity; default deny. |
| D-05 | GitHub checkpoint is triggered by stage closure, not scheduled automatic push. |
| D-06 | Initial rollout is R0 Observer plus selected R1 Guarded Semi-Automation, not direct R2 full enforcement. |
| D-07 | State Journal Writer is the only logical authoritative state-journal append authority inside the governed State Store boundary. |

#### D-07: Authoritative State Journal Write Ownership

1. Authoritative workflow/state event journal has exactly one
   logical append authority: State Journal Writer.

2. State Journal Writer is a narrow authenticated persistence
   identity inside the governed State Store boundary.

3. State Journal Writer has:
   - NO governance decision authority;
   - NO transition-selection authority;
   - NO capability-expansion authority.

4. Transition Engine validates candidate transitions but does not
   directly persist authoritative state transitions.

5. A transition may be appended only after validation of:
   - submitting identity;
   - governance authority reference;
   - predecessor state;
   - scope;
   - baseline;
   - required gates.

6. The accepted transition record is the only input that may enter
   the authoritative state-journal append path.

7. State Journal Writer alone persists that accepted transition and
   updates the derived projection in the same durable transaction,
   subject to the single-logical-writer rule.

8. Codex Executor, Runtime Adapter, Orchestrator, Transition Engine,
   Audit Writer, or generic datastore access cannot bypass this path.

9. Audit Writer remains a separate audit/provenance writer and is
   not the authoritative workflow/state journal writer.

10. Candidate-event submission, authority validation,
    authoritative append, and projection derivation are distinct
    operations and authorities.

No D-08 or later architectural choice is frozen by this materialization.

### 24.21 Explicit Non-Goals

This baseline does not implement a runtime, state store, journal, orchestrator,
broker, adapter, sandbox, Git automation, or persistence writer. It does not
create a database, credential, grant, trust anchor, governance root, or
Constitution. It does not change schema, contract, fixture, source, or tests;
deploy to a real environment; enable default consumption; or authorize
Activation or Operational Entry.

### 24.22 Implementation Entry Criteria

Implementation requires a later, separate User Decision and bounded TASK with
an exact manifest, baseline, role/identity binding, security review, test plan,
rollback/preservation rules, and operation-specific capabilities. The design
stage must first receive ChatGPT architecture review and closure, followed by
a separately approved GitHub checkpoint. Neither this document's existence
nor a checkpoint satisfies implementation, Activation, or Operational Entry
authority.

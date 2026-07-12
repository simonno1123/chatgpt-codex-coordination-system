# ACOS v2 Runtime Threat Model

## 1. Purpose And Status

This threat model evaluates the proposed controlled runtime integration
architecture. It covers observer, semi-automation, and future enforcement
boundaries. It does not claim that any control is implemented, tested, or
production-ready.

The security objective is to prevent an untrusted message, compromised agent,
stale artifact, ambiguous human action, or external state change from becoming
broader authority or an unattributed mutation.

## 2. Security Properties

ACOS must preserve:

- authenticated and non-interchangeable runtime identities;
- artifact integrity, origin, freshness, ordering, and scope binding;
- explicit and separately consumed User, review, edit, commit, push, release,
  and deployment authority;
- project-root, path, process, network, and credential confinement;
- durable, idempotent, race-safe workflow state;
- append-only, tamper-evident, attributable audit evidence;
- fail-closed behavior for unknown identity, policy, state, or external outcome;
- independent human review and rollback; and
- isolation between ACOS core and every project instance.

## 3. Assets

| Asset | Security Need |
| --- | --- |
| User Decisions and confirmation receipts | authenticity, exact scope, freshness, revocation, non-replay |
| ChatGPT TASK/REVIEW/DECISION artifacts | producer integrity, lifecycle and scope binding |
| External Advisory requests/reviews | read-only provenance, target/reference binding, non-authority |
| Runtime identities, sessions, and signing keys | confidentiality, integrity, revocation, role separation |
| Machine policy releases | authenticity, version integrity, rollback safety, traceability |
| Workflow and authorization state | consistency, availability, atomic consumption, recovery |
| Project files and repositories | path confinement, integrity, availability, provenance |
| Git history, branches, remotes, tags, and releases | exact authorization, non-force integrity, attribution |
| Sandbox credentials and environment | confidentiality, least privilege, isolation |
| Audit and provenance ledger | append-only integrity, completeness, actor attribution |
| Adapter and orchestration software | supply-chain integrity, configuration correctness |
| Observer results and metrics | non-authorizing labeling, integrity, separation from enforcement |

## 4. Actors

### Authorized Actors

- User Decision Source: explicitly accepts human risk/action within exact scope.
- ChatGPT Review Runtime: creates TASK, REVIEW, and DECISION artifacts.
- Codex Executor Runtime: performs separately authorized execution and returns
  RESULT or BLOCKED RESULT.
- External Advisory Runtime: performs read-only analysis and returns ADVISORY
  REVIEW to ChatGPT Review.
- Automation Runtime: performs deterministic checks and writes RESULT/RECORD.
- Governance Engine: verifies, routes, and enforces lifecycle state.
- Sandbox Executor: enforces one bounded execution capability.
- Audit Writer: appends evidence without governance authority.
- Human operator/security reviewer: maintains infrastructure and investigates
  incidents without silently acquiring workflow authority.

### Adversarial Or Faulted Actors

- external attacker with network, account, or host access;
- compromised or prompt-injected agent/provider;
- malicious or mistaken user/client;
- compromised adapter, orchestrator, sandbox, or audit writer;
- repository collaborator or other client racing Git operations;
- dependency or build-system attacker; and
- insider with partial operational access.

## 5. Trust Boundaries

1. Human browser/client to User Decision service.
2. Provider/model process to its registered runtime adapter.
3. Runtime adapter to Artifact Gateway.
4. Artifact Gateway/Policy Engine to durable state.
5. Orchestration Engine to Authorization Broker.
6. Authorization Broker to Sandbox Controller.
7. Sandbox to project filesystem, process namespace, network, and credentials.
8. Sandbox Git gate to local repository and remote provider.
9. Workflow transaction/outbox to Audit Writer and audit store.
10. Observer event-copy plane to live production plane.
11. ACOS core to each project instance.
12. Local control plane to future cross-host adapters and storage.

Crossing a boundary requires authenticated identity, explicit schema, bounded
data, policy evaluation, and audit. A role name inside text is never sufficient.

## 6. Attack Surfaces

- artifact parsers, canonicalizers, schema validators, and extension handling;
- signatures, key registry, nonce/replay store, and session management;
- adapter prompts, context bundles, provider outputs, retries, and cancellation;
- User Decision UI, session binding, summaries, and confirmation receipts;
- policy compiler, release pipeline, rollback, and compatibility handling;
- workflow APIs, idempotency keys, concurrency, leases, and recovery jobs;
- sandbox command parser, process launcher, filesystem mounts, and environment;
- path normalization, symlinks, hard links, submodules, and linked worktrees;
- Git command gate, hooks, wrapper, credentials, remotes, and server settings;
- audit ingestion, sequence/hash chain, checkpointing, backup, and query access;
- observer ingestion, comparison labeling, dashboard, and export;
- dependencies, packages, container images, CI, and deployment artifacts.

## 7. Threat Matrix

| ID | Threat | Preconditions | Impact | Detection | Prevention | Residual Risk |
| --- | --- | --- | --- | --- | --- | --- |
| T01 | Agent impersonation | attacker controls message/provider output or runtime label | forged TASK/RESULT/REVIEW/DECISION and role drift | transport/runtime mismatch, invalid signature, impossible session, producer mismatch | registered runtime keys, mutual authentication, short sessions, role-bound signing, default deny | stolen runtime key can act until revocation; attestation strength varies |
| T02 | Artifact forgery | attacker can inject or modify envelope/payload | false authority, routing, or execution | digest/signature failure, schema mismatch, audit anomaly | canonical signed artifacts, key registry, target/scope binding, size/type limits | compromised signing key or canonicalization defect |
| T03 | Replay attack | valid artifact/capability is captured | repeated edit, commit, push, or decision consumption | duplicate nonce/artifact/idempotency key, consumed authorization | atomic one-time consumption, expiry, nonce store, session binding | durable-store outage or cross-region race before mature deployment |
| T04 | Authorization escalation | narrow authority interpreted broadly | unauthorized operation or scope | requested/authorized action mismatch, capability diff | action-specific capabilities, deny inheritance, policy tests, exact scope | policy-model error or human approval of overly broad scope |
| T05 | Scope widening | paths/project/task/branch changed after approval | cross-file/project mutation | before/after manifest and state mismatch | immutable scope claims, canonical project registry, recheck at use | TOCTOU on complex filesystems or external repository changes |
| T06 | Path traversal | attacker supplies `..`, absolute, encoded, or special path | escape from project root | canonical path differs, denied path class | open-after-realpath checks, root confinement, safe path API | platform-specific path semantics and mount behavior |
| T07 | Symlink/hard-link escape | writable path redirects to protected/external target | protected or cross-project write | inode/target change, mount/path audit | no-follow/openat-style controls, mount isolation, recheck, deny writable parents | hard-link and filesystem race complexity |
| T08 | Command injection | untrusted text enters shell/command construction | arbitrary process, network, or file action | command parser mismatch, unexpected process tree | no shell composition, structured argv, command allowlist, sandbox/seccomp where available | allowed tools may expose powerful subcommands |
| T09 | Prompt injection into agent | repository/artifact content contains malicious instructions | agent proposes scope bypass, leaks data, or forges authority | output/artifact policy mismatch, unusual requested action | treat model output as untrusted, separate system policy, capability gate, minimal context | model may still produce deceptive content requiring review |
| T10 | Malicious fixture/artifact | deeply nested, oversized, duplicate-key, path-reading, or contradictory input | parser denial, data exposure, policy confusion | parser limits, duplicate-key detection, contract conflict | strict schema, size/depth limits, fixture-root confinement, fail closed | parser/library implementation defects |
| T11 | Policy downgrade | old/weaker policy selected or rollback abused | forbidden action becomes allowed | signed version/digest/effective-range mismatch | signed releases, minimum version, explicit rollback decision, pinned workflow policy | emergency rollback pressure or compromised policy signer |
| T12 | Stale policy use | long workflow or offline adapter uses obsolete policy | inconsistent component outcomes and drift | compatibility check, observer comparison, policy age alert | pin safe version, expiry, migration gate, CI contract tests | active workflows may require careful migration rather than immediate stop |
| T13 | Audit tampering | attacker can modify/delete/reorder audit data | hidden action, false attribution, failed investigation | hash/signature/sequence/checkpoint mismatch, replica comparison | append-only writer, separate credentials, signed checkpoints, backup | privileged storage compromise can cause availability loss |
| T14 | Remote Git race | another client updates branch between validation and push | wrong commit/range pushed or misleading result | expected-tip mismatch, divergence, remote receipt mismatch | push capability binds expected remote tip, server protection, reconciliation | provider evidence may not fully identify actor/session |
| T15 | Compromised runtime | agent host/session/key is controlled | authorized-looking malicious artifacts/actions | attestation change, behavior anomaly, key/session misuse | least privilege, short sessions, sandbox, revocation, separate keys | validly signed malicious requests within granted scope |
| T16 | Compromised adapter | translation/routing layer alters content or result | forged or dropped artifacts, wrong receiver | end-to-end signature mismatch, missing sequence, health anomaly | adapters cannot sign as producers, minimal transform, reproducible canonical payload | availability attacks and context omission remain possible |
| T17 | Compromised credential | user, runtime, Git, or service secret stolen | impersonation, repository/audit access | unusual session/location, key use, failed attestation, provider logs | secret isolation, no repo storage, scoped tokens, rotation, revocation, MFA for users | detection delay and provider-specific controls |
| T18 | User-interface spoofing | attacker controls UI, browser, or display context | user approves different action/scope | confirmation receipt differs from displayed digest, session anomaly | trusted origin, exact action summary, anti-CSRF, re-auth for high risk, receipt verification | compromised endpoint can mislead user before signing |
| T19 | External reviewer spoofing | forged advisory identity or wrong request binding | false comfort or governance bypass | reviewer key/request/target/reference mismatch | registered advisory runtime, signed request/review, ChatGPT consumption gate | compromised advisory key; advisory quality remains non-cryptographic |
| T20 | Cross-project authorization reuse | valid decision/capability copied to another project | instance contamination or unauthorized mutation | project/root/task mismatch, nonce already used | canonical project IDs, per-project keys/capabilities/state partitions | registry misconfiguration or shared filesystem ambiguity |
| T21 | Supply-chain compromise | dependency, image, CI, or update channel is malicious | control-plane or sandbox compromise | provenance/SBOM mismatch, signature failure, behavior anomaly | pinned verified dependencies, signed builds/images, minimal base, reproducible checks | trusted upstream compromise and zero-days |

## 8. Abuse Cases

### 8.1 Forged Codex Decision

A compromised Codex adapter emits `DECISION: ACCEPTED`. The Artifact Gateway
verifies the Codex runtime identity, rejects the forbidden artifact type, records
an authority violation, and does not route or issue capability.

### 8.2 Advisory Recommendation Becomes Push

An ADVISORY REVIEW recommends commit and push. The policy allows ChatGPT Review
to consume findings only. No Git authorization is created. A direct route to
Codex or a push capability request is denied and audited.

### 8.3 Ambiguous "Continue" Reused Broadly

A client attempts to treat a prior user message as task-start, edit, commit, and
push authority. The User Decision service requires an exact displayed action,
scope, expiry, and receipt for each required gate. Missing exact authority blocks.

### 8.4 Hidden Staged File

An authorized source file is staged with an unrelated hidden file. The stage
manifest differs from the capability; commit is denied. The gate never unstages,
resets, or cleans files automatically.

### 8.5 External Push Appears First

The remote already contains the authorized commit but no sandbox receipt exists.
The reconciler opens a provenance exception, avoids duplicate push, records
remote evidence, and refuses to claim Codex attribution from hash equality alone.

### 8.6 Prompt-Injection Scope Expansion

A repository document instructs the executor to ignore the task and alter policy.
The agent may repeat the instruction in output, but the sandbox capability lacks
those paths/actions. The write is denied and the attempt becomes evidence.

### 8.7 Audit Record Used As Authority

A client supplies a valid signed audit event claiming a push was approved. The
policy recognizes Audit Writer identity and `AUDIT EVENT`, not an authorization
producer/type. The request is denied even when the hash chain is valid.

### 8.8 Policy Downgrade During Workflow

An operator deploys an older policy while a commit workflow is active. The
workflow remains pinned to its accepted compatible version or blocks for a
migration decision. It never silently adopts weaker policy.

## 9. Defense-In-Depth Controls

### Identity And Artifact

- mutual authentication and role-bound keys;
- short-lived runtime sessions and revocation;
- canonical signed envelopes and target digests;
- nonce, sequence, idempotency, expiry, and one-time consumption;
- explicit producer/runtime/project/task correlation.

### State And Policy

- transactional state transitions and audit outbox;
- optimistic locks, workflow leases, and unique constraints;
- one signed machine-policy source with traceability tests;
- pinned policy versions and compatibility ranges;
- observer comparison and drift alerts.

### Execution

- separate sandbox identities for read, edit, test, Git, and release;
- canonical roots and exact path manifests;
- structured command invocation and process allowlists;
- network deny-by-default and credential isolation;
- resource limits, monitoring, termination, and signed receipts.

### Git And Remote

- operation-specific capabilities;
- exact staged tree, branch, HEAD, remote, and expected-tip binding;
- local wrapper/sandbox gate plus server-side protection;
- no force, implicit remediation, or authorization inheritance;
- independent remote reconciliation and provenance exceptions.

### Audit And Recovery

- append-only events, sequence, hash chain, signatures, and checkpoints;
- separate Audit Writer and storage credentials;
- fail-closed mutation when required audit is unavailable;
- backup/restore and fork detection;
- kill switch, capability revocation, and observer/manual fallback.

## 10. Detection And Alerting

Alert immediately on:

- invalid or unknown runtime signature;
- producer/runtime or role/artifact mismatch;
- repeated nonce, artifact ID, or consumed authorization;
- path/root/symlink escape attempt;
- forbidden Git command or unrelated staged path;
- expected HEAD/remote-tip mismatch;
- advisory or User Decision binding/consumption failure;
- audit chain break, fork, sequence regression, or checkpoint mismatch;
- policy downgrade, unsigned policy, contract drift, or stale policy;
- sandbox process/network/credential policy violation;
- kill-switch failure or mutation without execution receipt; and
- remote operation without attributable authorized attempt.

Alerts include severity, affected project/workflow/runtime, immutable evidence
references, containment status, and required human receiver. Alert delivery is
not itself an authorization or incident closure.

## 11. Residual Risk

Even with the target controls:

- authenticated runtimes can act maliciously within granted scope;
- users can approve risky or overly broad actions;
- prompt injection can influence proposals and review quality;
- canonicalization, policy, sandbox, database, or cryptographic software may have
  defects or zero-days;
- remote providers may supply incomplete provenance;
- host compromise can undermine process/container isolation;
- audit integrity does not guarantee event completeness when all writers or trust
  roots are compromised;
- model/advisory correctness remains probabilistic; and
- operational pressure may encourage unsafe exceptions.

Residual risk must be explicit in the User Decision and phase evidence. It cannot
be silently converted into acceptance by PASS metrics.

## 12. Security Review Requirements

Before authenticated exchange:

- cryptographic/canonicalization review;
- key custody, rotation, revocation, and compromise drills;
- parser fuzzing and schema negative tests; and
- runtime registration and impersonation tests.

Before durable state/audit:

- transaction, concurrency, idempotency, backup, restore, migration, and audit
  integrity review;
- privacy, redaction, retention, and access-control review; and
- failure injection for state/audit outage.

Before mutating sandbox:

- independent sandbox escape and path-race review;
- command/process/network/credential boundary tests;
- supply-chain and image/build provenance review; and
- partial-effect and kill-switch drills.

Before Git push/release:

- server-side protection review;
- expected-tip race and provenance exception exercises;
- credential scope and remote-provider audit review; and
- commit/push/release separation penetration tests.

Before blocking enforcement or multi-project use:

- accepted Mandatory External Advisory Review;
- independent security assessment;
- observer threshold evidence;
- cross-project isolation and replay tests;
- incident response exercise; and
- explicit User Decision.

## 13. Production Blockers

Production enforcement is blocked while any of the following remains:

- self-declared or unauthenticated runtime identity;
- unsigned or ambiguously canonicalized actionable artifacts;
- missing durable workflow/authorization-consumption state;
- policy copies without accepted signed source and drift controls;
- inability to revoke runtime sessions or authorizations;
- sandbox path, process, network, credential, or resource confinement unverified;
- Git stage/commit/push/release authority collapse;
- audit store not append-only, unavailable without fail-closed behavior, or not
  recoverable;
- unattributed remote mutation treated as successful authorized execution;
- unresolved critical/high false allow;
- untested restart, race, partial-effect, recovery, and kill switch;
- advisory or User Decision path can be bypassed or substituted;
- cross-project capability reuse possible;
- unaccepted independent security review; or
- no explicit User Decision authorizing enforcement.

## 14. Acceptance Criteria

This threat model is ready for review when every required threat has documented
preconditions, impact, detection, prevention, and residual risk; abuse cases
exercise authority substitution and provenance failures; production blockers map
to rollout entry criteria; and no control is represented as already implemented.

TASK_058 does not start implementation, enforcement, project onboarding, or
TASK_059.

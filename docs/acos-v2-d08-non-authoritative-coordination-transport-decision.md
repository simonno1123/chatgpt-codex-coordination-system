# ACOS v2 D-08 — Non-Authoritative Coordination Transport Separation

## 1. Decision Identification

| Field | Value |
| --- | --- |
| Decision | D-08 |
| Name | Non-Authoritative Coordination Transport Separation |
| Status | FROZEN |
| Governance review | ACOS-V2-SHARED-COORDINATION-LAYER-ARCHITECTURE-REVIEW-DECISION-01 |
| Repository materialization authorization | ACOS-V2-D08-NON-AUTHORITATIVE-COORDINATION-TRANSPORT-REPOSITORY-MATERIALIZATION-AUTHORIZATION-01 |

This document materializes an already frozen architecture decision. It does
not create a new decision, reopen the design, or authorize implementation.

## 2. Status

```text
DECISION: D-08
NAME: Non-Authoritative Coordination Transport Separation
STATUS: FROZEN

Shared Coordination Substrate v0:
GITHUB CHECKPOINT CLOSED / MATERIALIZED

This repository document:
MATERIALIZED IN WORKING TREE
DOCUMENT REVIEW AND SEPARATE GITHUB CHECKPOINT PENDING
```

Document creation does not constitute document acceptance, staging, commit,
push, or checkpoint closure. Activation and Operational Entry remain LOCKED.

## 3. Context

Coordination requires durable artifact exchange, delivery facts, receipts,
reply links, and recovery evidence. These transport facts have a different
meaning and persistence boundary from authoritative governance state.

A transported TASK, AUTHORIZATION, RESULT, REVIEW, DECISION, CHECKPOINT, or
ADVISORY remains an artifact. Its presence in a transport store cannot decide
its governance validity, accept a result, advance a workflow, or admit execution.

D-08 records this separation as an independent durable subsystem. It preserves
the frozen D-01 — D-07 baseline and the existing authoritative validation paths.

## 4. Decision

ACOS Coordination Transport SHALL be a distinct, durable, non-authoritative
subsystem.

It MAY persist and transport:

- coordination artifacts
- delivery facts
- acknowledgements
- correlation / reply links
- receipts
- transport recovery evidence

It SHALL NOT create, infer, expand, or exercise:

- governance authority
- workflow transition authority
- capability authority
- execution authority
- User Decision authority
- ChatGPT Review authority

Its journal, writer, projections, receipts, ACKs, delivery states, relay metadata,
and transport recovery semantics SHALL remain separate from the authoritative
Governance State Journal and State Journal Writer.

Coordination delivery or acknowledgement SHALL NOT constitute governance
acceptance, authorization, execution admission, capability consumption, stage
progression, or task completion.

Any transition from a transported artifact to governance or execution action
MUST be revalidated through the existing authoritative governance and execution
paths. Transport persistence does not supply a substitute validation path.

## 5. Architectural Position

The Coordination Transport Domain is a separate persistence and recovery domain.
Its event journal records transport facts; artifact and delivery projections are
derived transport views. Neither projections nor receipts are an authoritative
source of governance state.

The Coordination Journal Writer owns coordination transport persistence only.
It does not become an additional authoritative State Journal Writer. No
governance, capability, or execution authority is acquired by sharing storage,
publishing content, linking a reply, or recovering a transport receipt.

## 6. Domain Separation

### A. Authoritative Governance Domain

- Transition Engine
- State Journal Writer
- StateStore
- Governance Projection

This domain validates and durably records authoritative governance transitions
under the existing frozen governance contract.

### B. Coordination Transport Domain

- CoordinationArtifact
- CoordinationEvent
- CoordinationJournalWriter
- CoordinationStore
- Artifact Projection
- Delivery Projection
- ACK / Receipt
- Correlation / Reply

This domain persists transport content and facts. It has no authority to select
or append governance transitions or admit execution.

### C. Execution / Evidence Domain

- TASK
- AUTHORIZATION
- RESULT
- REVIEW
- DECISION
- CHECKPOINT
- ADVISORY
- execution evidence

Artifact types and execution evidence retain their existing governance meaning
and validation requirements. Transporting them does not execute that meaning.

## 7. Writer Ownership

D-07 remains authoritative for governance state. State Journal Writer remains
the sole logical writer of authoritative governance state inside the governed
State Store boundary. Transition Engine validation precedes that authoritative
append path; transport artifacts and receipts cannot bypass it.

D-08 introduces a separate logical writer only for coordination transport
persistence. Coordination Journal Writer has:

```text
TRANSPORT PERSISTENCE AUTHORITY ONLY

NO governance write authority
NO transition authority
NO capability authority
NO execution authority
```

The two writers own different data domains. Neither writer is a new governance
decision source. A transport journal entry is not an accepted governance
transition record and cannot be submitted as one merely because it was durable.

## 8. Authority Boundaries

```text
Transporting a governance artifact does not execute its governance meaning.

Artifact delivery != Artifact acceptance
Artifact receipt != Authorization
Artifact type != Authority
Relay != Governance Decision
```

Role declarations, payload prose, hashes, and receipts cannot authenticate a
principal or elevate trust. Publisher and consumer bindings are recorded
separately from artifact role labels; v0 bindings are explicitly UNVERIFIED_LOCAL
and NOT PRODUCTION AUTHENTICATED.

`authority_reference`, `baseline_revision`, and `execution_attempt_id` are opaque
transport references. A RESULT replying to an AUTHORIZATION does not inherit
that authorization's authority. A payload claiming `FROM: ChatGPT Review` does
not acquire ChatGPT Review authority.

An artifact with `artifact_type=ACK` is content, not an internal transport
receipt operation. Valid ACK means exact-content receipt, never acceptance,
approval, review, authorization, or execution.

## 9. Mandatory Invariants

```text
CoordinationStore != StateStore
CoordinationEvent != GovernanceTransition
CoordinationJournalWriter != StateJournalWriter

ACK != ACCEPT
DELIVERED != AUTHORIZED
RESULT_RECEIVED != RESULT_ACCEPTED
REDELIVERY != REEXECUTION

role string != authenticated principal
payload digest != authority
transport receipt != execution admission
```

These invariants apply independently of the names used by a transport
implementation for its local availability or receipt states.

## 10. Relationship to D-01 — D-07

The existing frozen decisions remain recorded in
[the controlled runtime integration architecture, section 24.20](acos-v2-controlled-runtime-integration-architecture.md#2420-frozen-decisions).
This additive document does not edit or reinterpret that materialization.

| Decision | Preserved relationship |
| --- | --- |
| D-01 | Authoritative event journal and derived governance projection remain separate from coordination events and projections. |
| D-02 | The initial SQLite governance store retains its single logical state writer. A separate coordination store and writer do not add a governance writer. |
| D-03 | The orchestrator remains an enforcement/routing component without REVIEW or DECISION authority. Transport and relay add no such authority. |
| D-04 | Explicit capability grants per execution identity and default deny remain unchanged. Transport content and receipts neither issue nor consume capabilities. |
| D-05 | Governance stage closure and separately authorized Git operations govern checkpoints. Transport events do not schedule or authorize automatic push. |
| D-06 | R0 Observer and selected R1 Guarded Semi-Automation remain the rollout baseline. D-08 does not authorize R2 or unlock activation. |
| D-07 | State Journal Writer remains the only logical authoritative state-journal append authority; Coordination Journal Writer persists transport facts only. |

D-08 does not modify submitting-identity, authority-reference, predecessor,
scope, baseline, or required-gate validation in the authoritative append path.

## 11. Shared Coordination Substrate v0

| Field | Recorded implementation |
| --- | --- |
| Implementation | Shared Coordination Substrate v0 |
| Checkpoint Commit | `89c976cdf6abbb6a194aa79c736e9bb4f8d13717` |
| Status | GITHUB CHECKPOINT CLOSED / MATERIALIZED |
| Source | [scripts/acos-v2-coordination.py](../scripts/acos-v2-coordination.py) |
| Tests | [tests/test_acos_v2_coordination.py](../tests/test_acos_v2_coordination.py) |
| Prior accepted test evidence | 89 / 89 PASS: CO-01 — CO-50 plus 39 regressions; no tests rerun by this document task. |

The current v0 implementation includes:

- CoordinationArtifact
- SQLite CoordinationStore
- CoordinationJournalWriter
- append-only coordination journal
- artifact projection
- delivery projection
- publish
- read
- inbox
- outbox
- status
- ACK
- reply / correlation, including pending-parent handling
- idempotency
- conflict quarantine
- reopen verification

Read, inbox, outbox, and status do not implicitly ACK. Publish and ACK replay
return prior durable receipts without creating an execution attempt. Reopen
verification fails closed on metadata, schema, journal, or projection mismatch;
it does not automatically migrate, repair, or rebuild projections.

## 12. V0 Implementation Choices

Every entry below is classified as:

```text
V0 IMPLEMENTATION CHOICE
NOT ARCHITECTURE FREEZE
CATEGORY B: REVERSIBLE V0 IMPLEMENTATION CHOICE
```

| Choice | Current v0 value |
| --- | --- |
| Event vocabulary | PUBLISHED; ACK_RECORDED; CONFLICT_QUARANTINED |
| Delivery states | AVAILABLE; ACKED |
| SQLite journal mode | SQLite rollback journal |
| Busy timeout | 1000 ms |
| Payload/envelope bound | 1 MiB local JSON size bound |
| Canonical JSON | integer-only canonical JSON |
| Recipient topology | single local receiver binding |

AVAILABLE means local durable availability; it does not claim actual external
delivery. ACKED means an exact-content receipt was recorded; it does not mean
governance acceptance. This document records these implementation choices
without promoting them to new frozen architecture decisions.

## 13. Explicit Non-Capabilities

| Capability | Current status |
| --- | --- |
| Production Authentication | NOT IMPLEMENTED |
| Production Trust Anchor | NOT IMPLEMENTED |
| Network Relay | NOT IMPLEMENTED |
| Automatic ChatGPT Invocation | NOT IMPLEMENTED |
| Automatic Codex Invocation | NOT IMPLEMENTED |
| Automatic Cross-Conversation Delivery | NOT IMPLEMENTED |
| Background Daemon | NOT IMPLEMENTED |
| Capability Issuance / Consumption | NONE |
| Execution Admission | NONE |
| Governance Transition | NONE |
| Exactly-Once Execution | NOT CLAIMED |
| Cross-Host Coordination | NOT IMPLEMENTED |
| Activation | LOCKED |
| Operational Entry | LOCKED |

Durable transport idempotency and recovery evidence are not an exactly-once
execution guarantee. UNVERIFIED_LOCAL bindings are not production authentication.

## 14. Future Layering

```text
Shared Coordination Substrate
        ↓
Future Coordination Relay
        ↓
Future Invocation Adapter
        ↓
Target Agent / Conversation
```

The following boundaries remain mandatory:

```text
Durable Store != Relay
Relay != Invocation Adapter
Invocation Adapter != Governance Authority
Successful Delivery != Execution Admission
```

A durable store alone does not wake an agent or conversation. Relay and
invocation adapter work remain separate future studies and authorizations.
This document does not specify a relay protocol, polling algorithm,
authentication mechanism, or adapter implementation.

## 15. Escalation Boundary

If future Relay work needs any of the following, it MUST return to Architecture
Review before implementation:

- production authentication
- network listener
- automatic agent invocation
- cross-host durable delivery
- background service
- execution admission
- capability consumption
- State Journal integration
- cross-store atomic transaction
- autonomous governance decision

DO NOT predeclare D-09. A D-09 candidate may be proposed only if a future concrete
design actually introduces a new architecture-level decision. This
materialization introduces no D-09 candidate or additional execution authority.

## 16. Repository Materialization Record

| Field | Value |
| --- | --- |
| Artifact purpose | GOVERNANCE DOCUMENT MATERIALIZATION ONLY |
| Repository | `/Users/zhang/Documents/chatgpt-codex-coordination-system` |
| Authorized new path | `docs/acos-v2-d08-non-authoritative-coordination-transport-decision.md` |
| Baseline branch | master |
| Baseline HEAD | `89c976cdf6abbb6a194aa79c736e9bb4f8d13717` |
| Expected local origin/master | `89c976cdf6abbb6a194aa79c736e9bb4f8d13717` |
| Materialization date | 2026-10-04 (Asia/Shanghai) |
| Authorization | ACOS-V2-D08-NON-AUTHORITATIVE-COORDINATION-TRANSPORT-REPOSITORY-MATERIALIZATION-AUTHORIZATION-01 |
| Issuer / reviewer | ChatGPT Review |
| Executor | Codex Executor |
| Next receiver | ChatGPT Review |
| Existing tracked files | READ-ONLY |
| Source / test / existing-doc edits | NOT AUTHORIZED |
| Test execution | NOT AUTHORIZED |
| git add / commit / push | NOT AUTHORIZED |
| Network / Relay / adapter implementation | NOT AUTHORIZED |
| This document's checkpoint | PENDING: Document Review, exact-path staging, commit, push, independent remote verification |

The prior controlled runtime integration architecture and substrate source/tests
remain unchanged. This record authorizes no Git action or future Relay work;
their applicable review and execution gates remain separate.

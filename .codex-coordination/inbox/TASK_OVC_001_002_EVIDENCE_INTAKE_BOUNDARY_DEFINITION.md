ARTIFACT TYPE:
TASK

PRODUCER:
ChatGPT Review

TO:
Codex Executor

NEXT RECEIVER:
ChatGPT Review

PROJECT:
/Users/zhang/Documents/chatgpt-codex-coordination-system

MODE:
TASK DEFINITION / NON-EXECUTION

TASK ID:
TASK_OVC_001_002

TASK NAME:
Evidence Intake Boundary Definition

STATUS:
TASK_MATERIALIZED

MATTER ID:
MATTER_OVC_001_LEGAL_EXECUTION_ANALYSIS

TASK TYPE:
GOVERNANCE PREPARATION TASK

CAPABILITY CONTEXT:
Evidence Analysis

OBJECTIVE:
Define the governance boundary for how information may become an Evidence
Artifact in a future separately authorized Matter workflow, without accessing,
importing, analyzing, or judging any actual Matter material.

AUTHORITY LIMIT:
This Artifact defines and materializes TASK_OVC_001_002 only.

It does not authorize:

- transition to `TASK_READY` or `TASK_EXECUTING`;
- task execution;
- external project or Matter workspace access;
- information or Evidence intake;
- source retrieval, copying, OCR, transcription, classification, or analysis;
- Evidence Artifact creation;
- authenticity, relevance, weight, or admissibility judgment;
- fact construction;
- legal analysis, conclusions, or litigation strategy;
- file creation other than this Task Definition;
- creation of another task;
- ACOS Core modification;
- cross-project changes;
- Git operations.

OUTPUT:
Task Definition Record only.


## 1. Governance Basis

TASK_OVC_001_002 uses existing ACOS governance records. It does not create a
new Evidence Model or Governance Model.

### Capability Model

Path:
`docs/capability-model.md`

SHA-256:
`45a6b60605d4940cb04af94de4829eca5adf42029d130a328ea54c8fbc7f8664`

### Task State Machine

Path:
`docs/task-state-machine.md`

SHA-256:
`1f5d81c8ffe3d44cb1bc7908552a6a0853dd5e54a60065ad30e773b1ac1abf16`

### Execution Boundary Model

Path:
`docs/execution-boundary-model.md`

SHA-256:
`ebf64d7031bd8db9c3b84594854c6f8b6ba6c116156308e344464058aab60a8d`

### Execution Receipt Model

Path:
`docs/execution-receipt-model.md`

SHA-256:
`032077a434ba63b5c5e1163c9eb6e99c5aed56925764d1ee350c17ecc1d4e78b`

### Review Evidence Model

Path:
`docs/review-evidence-model.md`

SHA-256:
`2ffe82d5c39127fc7da4f734c4ddd893645bd11f191ff88fb9a832918330c0f0`

### Matter Onboarding Boundary

Path:
`.codex-coordination/inbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS_MATTER_ONBOARDING_BOUNDARY.md`

SHA-256:
`9a83ab5d813ce102202401224e33bc54e6a282d1f23207d8eb656cd434e40f19`

### Matter Activation Record

Path:
`.codex-coordination/outbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS_MATTER_ACTIVATION_RECORD.md`

SHA-256:
`530b4df4dab3c157d49778f596879f6c8ae944444853ea263ca553a6b3e7a5f8`

### Capability Mapping

Path:
`.codex-coordination/inbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS_CAPABILITY_MAPPING.md`

SHA-256:
`7089df75c96091585625449a328bb30b0a9d768f18d09bfb22ffcace01b9e41c`

### Capability Mapping Decision

Path:
`.codex-coordination/inbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS_CAPABILITY_MAPPING_DECISION.md`

SHA-256:
`7e30f88d3116a81424546f76b9d8e58fd51d8f79c59b90eb133ce3cd86218016`

### Matter Information Boundary Result

Path:
`.codex-coordination/outbox/TASK_OVC_001_001_MATTER_INFORMATION_BOUNDARY_DEFINITION_RESULT.md`

SHA-256:
`78d8cac9b2409cb7f022c7aa213798661e5ce6ce6167c771cb05727c6990383f`

### TASK_OVC_001_001 Closure Decision

Path:
`.codex-coordination/inbox/TASK_OVC_001_001_MATTER_INFORMATION_BOUNDARY_DEFINITION_CLOSURE_DECISION.md`

SHA-256:
`d459aacc98563250b13e8aea9f54de7a64f16c474d8c444a39bf23a36c9b00f0`


## 2. Capability Boundary

`Evidence Analysis` is a Matter-local workstream label. It is not a new ACOS
Core capability and is not activated by this Task.

Current governance capability:

```text
task_define
```

A future separately authorized execution may use:

```text
file_modify
```

only for the exact Result path named in this Task and a later execution
authorization.

No capability to access, ingest, analyze, judge, or transform actual Evidence
is granted.


## 3. Allowed Inputs For Future Execution

A future separately authorized execution may read only:

- the eleven governance artifacts listed in Section 1;
- this Task Definition;
- a future Task Review and Task Readiness Decision;
- a future Task Execution Authorization.

These inputs contain governance definitions and records only.


## 4. Inputs Not Allowed

Future execution must not read, receive, copy, or infer from:

- external case files;
- bank or transaction records;
- communications or chat records;
- contracts, scans, images, audio, or OCR output;
- court documents;
- corporate records;
- property or asset records;
- personal or sensitive data;
- client instructions;
- Matter workspace contents;
- external network, provider, model, API, or search results;
- any actual or purported Evidence item.


## 5. Expected Future Output

Expected Artifact:

```text
RESULT
```

Expected record:

```text
Evidence Intake Boundary Definition Result
```

Proposed exact output path:

`.codex-coordination/outbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_RESULT.md`

The Result must define governance structure only. It must not create an
Evidence Artifact or contain actual Matter information.

The Result must contain:

1. Evidence identity fields;
2. Evidence intake prerequisites;
3. Evidence lifecycle states and transition rules;
4. source, integrity, authenticity, relevance, and human-acceptance gates;
5. Evidence-versus-Fact separation;
6. dispute and contradiction handling;
7. fail-closed conditions;
8. review and Decision checkpoints;
9. a non-implementation boundary;
10. a structured Execution Receipt.


## 6. Evidence Identity Boundary

The future Result must define, at minimum:

| Required Field | Required Meaning |
| --- | --- |
| `evidence_id` | Stable Matter-local identity for a future Evidence Artifact. |
| `source_reference` | Exact governed source reference. |
| `provider_or_custodian` | Declared provider, owner, or custodian. |
| `acquisition_method` | Declared authorized acquisition method. |
| `acquisition_time` | Reported acquisition time with timezone when available. |
| `original_location_reference` | Governed source-location reference without exposing unauthorized contents. |
| `integrity_reference` | Hash or other integrity reference when available. |
| `original_or_copy_status` | Declared original, copy, derivative, excerpt, or unknown status. |
| `authorization_reference` | Exact Decision permitting intake. |
| `known_limitations` | Missing context, uncertain origin, transformation, or other limitation. |

The future Result must state that identity metadata supports traceability but
does not prove authenticity, relevance, admissibility, weight, or truth.


## 7. Evidence Lifecycle Boundary

The future Result must define these lifecycle states:

```text
RECEIVED
REVIEWING
VERIFIED
DISPUTED
ARCHIVED
BLOCKED
```

The lifecycle is not an unconditional linear pipeline.

Minimum permitted transitions:

```text
RECEIVED
  -> REVIEWING

REVIEWING
  -> VERIFIED

REVIEWING
  -> DISPUTED

REVIEWING
  -> BLOCKED

VERIFIED
  -> DISPUTED

VERIFIED
  -> ARCHIVED

DISPUTED
  -> REVIEWING

DISPUTED
  -> ARCHIVED
```

Every transition must identify the reviewer, basis, referenced material,
timestamp, unresolved limitations, and Decision reference.

`VERIFIED` must mean only that defined verification checks were completed. It
must not mean that the material is true, conclusive, admissible, or sufficient
to establish a fact.


## 8. Evidence And Fact Boundary

The future Result must preserve:

```text
Information
  != Evidence Review Candidate
  != Evidence Artifact
  != Fact Candidate
  != Legal Fact
```

Prohibited:

```text
Evidence Artifact
  -> Automatic Fact
```

Required governed path:

```text
Evidence Artifact
  -> Evidence Review
  -> Fact Candidate
  -> Human Review
  -> Decision
  -> Legal Fact
```

No Evidence lifecycle state may automatically create a Fact Candidate or Legal
Fact.


## 9. Review Gates

The future Result must define separate gates for:

### 9.1 Source Review

Checks source identity, custody, acquisition authority, provenance, and known
limitations.

### 9.2 Integrity And Authenticity Review

Checks integrity references, original-versus-copy status, transformations, and
authenticity claims. A successful integrity check must not be equated with
authenticity.

### 9.3 Relevance And Permitted-Use Review

Checks Matter relationship, purpose limitation, disclosure restrictions, and
whether the requested use is authorized. Relevance must not be equated with
truth or legal weight.

### 9.4 Human Acceptance

Requires a named human reviewer and Decision reference before a reviewed item
may become an Evidence Artifact or advance to another governed use.


## 10. Fail-Closed Conditions

The future Result must require `BLOCKED` when:

- source identity or custody is unknown;
- access or intake authorization is absent, stale, revoked, or contradictory;
- acquisition method is unauthorized or unclear;
- integrity or transformation history is materially incomplete;
- authenticity, relevance, permitted use, or disclosure boundary is unresolved;
- a required human reviewer or Decision reference is absent;
- the item is disputed and the proposed action assumes the dispute is resolved;
- the requested action would create a Fact or legal conclusion automatically;
- the input, output, side effect, or path exceeds the authorized boundary.

No unknown field, state, source, identity, or authorization receives default
permission.


## 11. Execution Boundary

A future execution may:

- read only the authorized governance inputs;
- define generic Evidence identity fields;
- define lifecycle states and transition conditions;
- define review, Decision, dispute, and fail-closed gates;
- create only the exact Result path.

A future execution may not:

- connect to or access an external Matter project;
- create a Matter workspace;
- import, copy, OCR, transcribe, classify, summarize, or analyze actual material;
- create an Evidence Artifact;
- verify or dispute an actual item;
- create a Fact Candidate or Legal Fact;
- perform legal analysis;
- select litigation strategy;
- create another task or output;
- modify an existing artifact.


## 12. Acceptance Criteria

The future Result is acceptable only if:

1. it contains no external Matter content or actual Evidence;
2. it defines all required Evidence identity fields;
3. it defines lifecycle states and explicit transition conditions;
4. it distinguishes integrity checks from authenticity judgments;
5. it distinguishes relevance from truth, weight, and admissibility;
6. it separates Evidence Artifact, Fact Candidate, and Legal Fact;
7. it requires human Review and a Decision before governed advancement;
8. it defines dispute handling and fail-closed conditions;
9. it adds no Evidence Model or Governance Model to ACOS Core;
10. it creates no Evidence Artifact, Fact, legal analysis, or additional task;
11. it modifies no existing file;
12. it includes a structured Execution Receipt and returns to ChatGPT Review.


## 13. Review Requirement

The future Result must return to `ChatGPT Review`.

Required review checks:

- exact Task and authorization binding;
- scope and output-path compliance;
- absence of external project and Matter data access;
- absence of actual Evidence;
- identity, lifecycle, dispute, and fail-closed completeness;
- Evidence-versus-Fact separation;
- no ACOS Core modification;
- complete structured Execution Receipt;
- no unauthorized file or Git operation.

The Result cannot self-accept or close the Task.


## 14. Task State And Required Next Gates

Current state:

```text
TASK_MATERIALIZED
```

Not current:

```text
TASK_READY
EXECUTION_AUTHORIZED
TASK_EXECUTING
TASK_RESULT
TASK_CLOSED
```

Required sequence:

```text
TASK_MATERIALIZED
  -> Task Definition Review
  -> Task Readiness Decision
  -> TASK_READY
  -> Task Execution Authorization
  -> EXECUTION_AUTHORIZED
  -> TASK_EXECUTING
  -> TASK_RESULT
  -> TASK_REVIEW
  -> TASK_DECISION
  -> TASK_CLOSED
```

Each transition requires its own governed evidence. This Task Definition does
not authorize any later transition.


FORBIDDEN:

- Executing TASK_OVC_001_002
- Transitioning to `TASK_READY`, `EXECUTION_AUTHORIZED`, or `TASK_EXECUTING`
- Creating the expected Result or Execution Receipt
- Accessing the external project, Matter workspace, or any case material
- Reading, importing, copying, OCR processing, or analyzing actual Evidence
- Creating an Evidence Artifact, Fact Candidate, or Legal Fact
- Generating legal analysis, legal conclusions, or litigation strategy
- Creating TASK_OVC_001_003, TASK_064, or any other task
- Creating or modifying a Governance Model or Evidence Model
- Modifying ACOS Core, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


FINAL STATUS:

```text
TASK_OVC_001_002 MATERIALIZED
TASK EXECUTION NOT AUTHORIZED
EVIDENCE INTAKE NOT AUTHORIZED
EXTERNAL INFORMATION ACCESS NOT AUTHORIZED
```


NEXT RECEIVER:

ChatGPT Review


REASON:

TASK_OVC_001_002 is materialized as a governance-only Evidence intake boundary
definition. It preserves the distinction between Matter information, Evidence,
Fact Candidates, Legal Facts, and Decisions while keeping all external data,
Evidence operations, and execution separately gated.

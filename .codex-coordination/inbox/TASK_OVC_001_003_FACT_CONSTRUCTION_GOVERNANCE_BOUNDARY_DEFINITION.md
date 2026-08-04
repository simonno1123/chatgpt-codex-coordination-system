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
TASK_OVC_001_003

TASK NAME:
Fact Construction Governance Boundary Definition

STATUS:
TASK_MATERIALIZED

MATTER ID:
MATTER_OVC_001_LEGAL_EXECUTION_ANALYSIS

TASK TYPE:
GOVERNANCE DEFINITION TASK

CAPABILITY CONTEXT:
Fact Construction Governance

OBJECTIVE:
Define the governance boundary for how governed Evidence references may support
a Fact Candidate and how a Fact Candidate may be reviewed for acceptance as a
Legal Fact, without reading Evidence or constructing any actual Matter fact.

AUTHORITY LIMIT:
This Artifact defines and materializes TASK_OVC_001_003 only.

It does not authorize:

- transition to `TASK_READY` or `TASK_EXECUTING`;
- task execution;
- external project or Matter workspace access;
- information or Evidence access;
- Evidence Artifact creation or lifecycle changes;
- Fact Candidate or Legal Fact creation;
- responsibility or liability determination;
- legal analysis, conclusions, or litigation strategy;
- file creation other than this Task Definition;
- creation of another task;
- ACOS Core modification;
- cross-project changes;
- Git operations.

OUTPUT:
Task Definition Record only.


## 1. Governance Basis

TASK_OVC_001_003 uses existing ACOS governance records. It does not create a
new Fact Model, Evidence Model, legal reasoning model, or ACOS Core capability.

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

### Matter Activation Record

Path:
`.codex-coordination/outbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS_MATTER_ACTIVATION_RECORD.md`

SHA-256:
`530b4df4dab3c157d49778f596879f6c8ae944444853ea263ca553a6b3e7a5f8`

### Evidence Intake Boundary Result

Path:
`.codex-coordination/outbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_RESULT.md`

SHA-256:
`67d0cb212222a980334711096737c930a482b1c373dc75671f9fd7ab3668e0dc`

### Evidence Intake Boundary Review

Path:
`.codex-coordination/outbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_REVIEW.md`

SHA-256:
`a2c144ebb5d05fb149f9483de4f0106e44ccfabd9a4306a502c2c13a3e026bb6`

### Evidence Intake Boundary Decision

Path:
`.codex-coordination/inbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_DECISION.md`

SHA-256:
`1c21d64b39fe6324204d949dd8bc3b0d42f5b595ff4142e399b10de10ab8d801`

### Evidence Intake Boundary Closure Decision

Path:
`.codex-coordination/inbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_CLOSURE_DECISION.md`

SHA-256:
`b8c9379c0ae8c6b38cd571d8d7736d3ddd735e5a1956d79b536b01166afe2c67`


## 2. Capability Boundary

`Fact Construction Governance` is a Matter-workflow boundary label. It is not a
new ACOS Core capability and is not activated by this Task.

Current governance capability:

```text
task_define
```

A future separately authorized execution may use:

```text
file_modify
```

only for the exact Result path named in this Task and a later Execution
Authorization.

No capability to read Evidence, generate facts, accept Legal Facts, determine
liability, or make legal Decisions is granted.


## 3. Allowed Inputs For Future Execution

A future separately authorized execution may read only:

- the ten governance artifacts listed in Section 1;
- this Task Definition;
- a future Task Review and Task Readiness Decision;
- a future Task Execution Authorization.

These inputs contain governance definitions and records only.


## 4. Inputs Not Allowed

Future execution must not read, receive, copy, or infer from:

- actual or purported Evidence;
- external case files;
- bank or transaction records;
- communications or chat records;
- contracts, scans, images, audio, or OCR output;
- court documents;
- corporate records;
- investigation material;
- property or asset records;
- personal or sensitive data;
- client instructions;
- Matter workspace contents;
- legal opinions or strategy material;
- external network, provider, model, API, or search results.


## 5. Expected Future Output

Expected Artifact:

```text
RESULT
```

Expected record:

```text
Fact Construction Governance Boundary Definition Result
```

Proposed exact output path:

`.codex-coordination/outbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION_RESULT.md`

The Result must define governance structure only. It must not include an actual
Evidence item, factual proposition, Fact Candidate, Legal Fact, legal
conclusion, or strategy.

The Result must contain:

1. Fact Candidate identity and traceability fields;
2. formation-rule and transformation-path requirements;
3. supporting, contradicting, and alternative-explanation requirements;
4. Fact Candidate lifecycle states and transition rules;
5. Evidence sufficiency and permitted-use gates;
6. human Review and Legal Fact Decision gates;
7. confidence and uncertainty limitations;
8. dispute, rejection, archival, and fail-closed handling;
9. a non-implementation boundary;
10. a structured Execution Receipt.


## 6. Fact Candidate Identity Boundary

The future Result must define, at minimum:

| Required Field | Required Meaning |
| --- | --- |
| `fact_candidate_id` | Stable Matter-local identity for a proposed factual proposition. |
| `matter_id` | Exact governed Matter reference. |
| `candidate_proposition` | One bounded proposition stated without embedding a real Matter fact in this Task. |
| `source_evidence_references` | Exact governed Evidence references supporting formation. |
| `contradicting_evidence_references` | Exact governed references that conflict with or limit the proposition. |
| `formation_rule` | Declared rule used to derive the candidate from Evidence. |
| `transformation_path` | Traceable sequence from Evidence references to the proposed statement. |
| `alternative_explanations` | Material competing explanations or interpretations. |
| `confidence_assessment` | Declared assessment with basis and limitations; not a substitute for Review. |
| `known_limitations` | Missing Evidence, uncertainty, ambiguity, or unresolved contradiction. |
| `human_review_status` | Pending, completed, disputed, rejected, or other governed status. |
| `reviewer_identity` | Named human reviewer when Review occurs. |
| `decision_reference` | Exact Decision accepting, disputing, rejecting, or archiving the candidate. |
| `created_at` | Reported materialization time with timezone when available. |
| `version_or_revision_reference` | Stable reference preserving later changes without rewriting history. |

Assignment of a `fact_candidate_id` creates a traceable proposal only. It does
not establish that the proposition is true, complete, legally relevant,
accepted, or a Legal Fact.


## 7. Fact Candidate Lifecycle Boundary

The future Result must define:

```text
GENERATED
UNDER_REVIEW
ACCEPTED
DISPUTED
REJECTED
ARCHIVED
BLOCKED
```

The lifecycle is not an unconditional linear pipeline.

Minimum permitted transitions:

```text
GENERATED
  -> UNDER_REVIEW

UNDER_REVIEW
  -> ACCEPTED

UNDER_REVIEW
  -> DISPUTED

UNDER_REVIEW
  -> REJECTED

UNDER_REVIEW
  -> BLOCKED

ACCEPTED
  -> DISPUTED

ACCEPTED
  -> ARCHIVED

DISPUTED
  -> UNDER_REVIEW

DISPUTED
  -> REJECTED

DISPUTED
  -> ARCHIVED

REJECTED
  -> ARCHIVED
```

Every transition must identify the reviewer, basis, Evidence references,
contradictions, limitations, timestamp, and Decision reference.

`ACCEPTED` means the Fact Candidate passed its defined human Review. It does
not automatically make the candidate a Legal Fact.


## 8. Evidence Foundation Boundary

A future Fact Candidate may reference only Evidence Artifacts that:

- have stable Evidence identities;
- have governed source, custody, provenance, and integrity records;
- have completed the required Review gates;
- are authorized for the proposed use;
- disclose disputed status and material limitations;
- are traceable to the applicable Evidence Decision.

An Evidence Artifact in `BLOCKED`, unresolved `DISPUTED`, or unauthorized-use
status cannot silently support an accepted Fact Candidate.

Evidence quantity does not establish fact quality, truth, sufficiency, or legal
effect.


## 9. Formation And Transformation Boundary

The future Result must require every candidate to show:

```text
Evidence References
  + Formation Rule
  + Transformation Path
  + Contradictions
  + Alternative Explanations
  + Limitations
  = Reviewable Fact Candidate
```

The formation rule must state whether the candidate relies on direct
observation, aggregation, chronology, inference, attribution, calculation, or
another separately reviewed method.

An inferred proposition must remain explicitly identified as inferred.
Formatting, summarization, extraction, or model generation cannot convert an
inference into an observed fact.


## 10. Legal Fact Gate

Prohibited:

```text
Fact Candidate
  -> Automatic Legal Fact
```

Required governed path:

```text
Fact Candidate
  -> Human Review
  -> Review Evidence
  -> Decision
  -> Legal Fact
```

The Legal Fact Decision must identify:

- the exact Fact Candidate;
- the Evidence and contradiction references;
- the applied review or decision standard;
- reviewer identity;
- findings and residual uncertainty;
- accepted scope and permitted use;
- Decision time and reference.

An accepted Fact Candidate remains distinct from a Legal Fact until this gate
is completed.


## 11. Review Gates

The future Result must define separate Review gates for:

### 11.1 Evidence Eligibility

Checks that every cited Evidence Artifact is governed, traceable, reviewed, and
authorized for the proposed use.

### 11.2 Formation Rule

Checks that the transformation from Evidence to proposition is explicit,
reproducible at the governance-record level, and does not conceal inference.

### 11.3 Contradictions And Alternatives

Checks supporting and contradicting references, competing explanations, and
unresolved uncertainty.

### 11.4 Human Acceptance

Requires a named human reviewer before a candidate can enter `ACCEPTED`.

### 11.5 Legal Fact Decision

Requires a separate Decision before an accepted Fact Candidate can become a
Legal Fact or support legal analysis.


## 12. Confidence And Uncertainty Boundary

A confidence assessment:

- must state its basis and limitations;
- must not replace Evidence references;
- must not override contradictions;
- must not trigger automatic acceptance;
- must not be described as a probability unless the method supports that claim;
- must remain review evidence rather than Decision authority.

Unknown or unresolved uncertainty receives no default favorable interpretation.


## 13. Fail-Closed Conditions

The future Result must require `BLOCKED` when:

- a source Evidence reference is missing, stale, disputed without disposition,
  or unauthorized for the proposed use;
- Evidence provenance, integrity, or permitted-use records are incomplete;
- the formation rule or transformation path is absent or ambiguous;
- supporting and contradicting material is not identified;
- material alternative explanations are omitted;
- confidence lacks a disclosed basis;
- human Review is incomplete;
- reviewer identity or Decision reference is missing;
- the proposed transition would create a Legal Fact automatically;
- any input, output, path, side effect, or external access exceeds the
  authorized boundary.

No unknown Evidence status, proposition, inference, confidence value, reviewer,
state, or authorization receives default permission.


## 14. Execution Boundary

A future execution may:

- read only the authorized governance inputs;
- define generic Fact Candidate fields;
- define lifecycle states and transition conditions;
- define formation, contradiction, Review, Decision, and fail-closed gates;
- create only the exact Result path.

A future execution may not:

- connect to or access an external Matter project;
- read an Evidence Artifact or Evidence content;
- create an actual factual proposition;
- create or change a Fact Candidate or Legal Fact;
- determine responsibility or liability;
- perform legal analysis;
- select litigation strategy;
- create another task or output;
- modify an existing artifact.


## 15. Acceptance Criteria

The future Result is acceptable only if:

1. it contains no external Matter content, actual Evidence, or factual
   proposition;
2. it defines all required Fact Candidate identity and traceability fields;
3. it defines lifecycle states and explicit transition conditions;
4. it requires governed Evidence references and permitted use;
5. it exposes formation rules, transformations, contradictions, alternatives,
   confidence basis, and limitations;
6. it separates Evidence, Fact Candidate, and Legal Fact;
7. it requires human Review before candidate acceptance;
8. it requires a separate Decision before Legal Fact status;
9. it defines dispute, rejection, archival, and fail-closed handling;
10. it adds no Fact Model, Evidence Model, or Governance Model to ACOS Core;
11. it creates no Fact, Legal Fact, legal analysis, or additional task;
12. it modifies no existing file;
13. it includes a structured Execution Receipt and returns to ChatGPT Review.


## 16. Review Requirement

The future Result must return to `ChatGPT Review`.

Required Review checks:

- exact Task and authorization binding;
- scope and output-path compliance;
- absence of external project, Matter data, and Evidence access;
- absence of actual Fact Candidate or Legal Fact content;
- identity, lifecycle, formation, contradiction, and fail-closed completeness;
- Evidence, Fact Candidate, and Legal Fact separation;
- no ACOS Core modification;
- complete structured Execution Receipt;
- no unauthorized file or Git operation.

The Result cannot self-accept or close the Task.


## 17. Task State And Required Next Gates

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

- Executing TASK_OVC_001_003
- Transitioning to `TASK_READY`, `EXECUTION_AUTHORIZED`, or `TASK_EXECUTING`
- Creating the expected Result or Execution Receipt
- Accessing the external project, Matter workspace, case material, or Evidence
- Reading, importing, copying, OCR processing, or analyzing actual Evidence
- Creating a Fact Candidate, Legal Fact, responsibility finding, or legal
  conclusion
- Generating legal analysis or litigation strategy
- Creating TASK_OVC_001_004, TASK_064, or any other task
- Creating or modifying a Governance Model, Evidence Model, or Fact Model
- Modifying ACOS Core, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


FINAL STATUS:

```text
TASK_OVC_001_003 MATERIALIZED
TASK EXECUTION NOT AUTHORIZED
EVIDENCE ACCESS LOCKED
FACT CONSTRUCTION LOCKED
LEGAL FACT GATE LOCKED
LEGAL ANALYSIS LOCKED
```


NEXT RECEIVER:

ChatGPT Review


REASON:

TASK_OVC_001_003 is materialized as a governance-only Fact Construction
boundary definition. It preserves Evidence, Fact Candidate, Legal Fact, Review,
and Decision separation while keeping all Evidence access, factual
construction, legal work, and execution separately gated.

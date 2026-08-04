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
TASK_OVC_001_004

TASK NAME:
Legal Fact Gate and Human Decision Boundary Definition

STATUS:
TASK_MATERIALIZED

MATTER ID:
MATTER_OVC_001_LEGAL_EXECUTION_ANALYSIS

TASK TYPE:
GOVERNANCE DEFINITION TASK

CAPABILITY CONTEXT:
Legal Fact Governance

OBJECTIVE:
Define the governance boundary for how an accepted Fact Candidate may undergo
human Review for confirmation as a Legal Fact and how a Legal Fact remains
separate from legal reasoning and the final Decision Layer, without reading
Evidence or creating any actual legal fact, analysis, or Decision.

AUTHORITY LIMIT:
This Artifact defines and materializes TASK_OVC_001_004 only.

It does not authorize:

- transition to `TASK_READY` or `TASK_EXECUTING`;
- task execution;
- external project or Matter workspace access;
- information or Evidence access;
- Evidence Artifact or Fact Candidate creation;
- Legal Fact creation, confirmation, adoption, or lifecycle change;
- legal reasoning, responsibility determination, or liability determination;
- legal analysis, conclusions, or litigation strategy;
- Decision generation or Decision authority;
- file creation other than this Task Definition;
- creation of another task;
- ACOS Core modification;
- cross-project changes;
- Git operations.

OUTPUT:
Task Definition Record only.


## 1. Governance Basis

TASK_OVC_001_004 uses existing ACOS governance records. It does not create a
new Legal Fact Model, Fact Model, Evidence Model, legal reasoning model, or ACOS
Core capability.

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

### Fact Construction Governance Result

Path:
`.codex-coordination/outbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION_RESULT.md`

SHA-256:
`4faaa8c14edf00a35158bb80bdf9a7dd9725045f2b6ad5df156362c5a1ea204f`

### Fact Construction Governance Review

Path:
`.codex-coordination/outbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION_REVIEW.md`

SHA-256:
`c77726fbb5f825a31e0fdbb38c5d69d797cd72dc2d1d5d4338023722d68e06a2`

### Fact Construction Governance Decision

Path:
`.codex-coordination/inbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION_DECISION.md`

SHA-256:
`8cb2c23a3d8ca705ec4c16f5f33a5d7e5b25193e98217ceae590f8faae824e13`

### Fact Construction Governance Closure Decision

Path:
`.codex-coordination/inbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION_CLOSURE_DECISION.md`

SHA-256:
`9a89505d425b13daf346259799c83ab112b4fafd9f10dea9d5e10339aa98dc24`


## 2. Capability Boundary

`Legal Fact Governance` is a Matter-workflow boundary label. It is not a new
ACOS Core capability and is not activated by this Task.

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

No capability to read Evidence, create a Fact Candidate, confirm a Legal Fact,
perform legal reasoning, or issue a legal Decision is granted.


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
- actual Fact Candidates or Legal Facts;
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
- legal opinions, reasoning, conclusions, or strategy;
- external network, provider, model, API, or search results.


## 5. Expected Future Output

Expected Artifact:

```text
RESULT
```

Expected record:

```text
Legal Fact Gate and Human Decision Boundary Definition Result
```

Proposed exact output path:

`.codex-coordination/outbox/TASK_OVC_001_004_LEGAL_FACT_GATE_AND_HUMAN_DECISION_BOUNDARY_DEFINITION_RESULT.md`

The Result must define governance structure only. It must not include an actual
Evidence item, Fact Candidate, Legal Fact, legal analysis, Decision, or
Matter-specific legal conclusion.

The Result must contain:

1. LF-G-001;
2. Legal Fact identity and traceability fields;
3. Fact Candidate completeness prerequisites;
4. human Legal Fact Review requirements;
5. reviewer and Decision-maker role separation;
6. Legal Fact lifecycle states and transition rules;
7. Legal Fact, legal reasoning, and Decision separation;
8. contradiction, supersession, and fail-closed handling;
9. a non-implementation boundary;
10. a structured Execution Receipt.


## 6. LF-G-001

The future Result must define:

```text
Legal Fact
  != Legal Analysis
  != Legal Decision
```

A Legal Fact is a governed factual statement confirmed for a defined Matter
context and use.

A Legal Analysis applies legal reasoning to governed facts and authorities.

A Legal Decision records an authorized outcome, choice, approval, rejection,
or action.

No Legal Fact may automatically produce a legal conclusion or Decision.


## 7. Governance Chain

The future Result must preserve:

```text
Evidence
  -> Fact Candidate
  -> Human Fact Review
  -> Legal Fact
  -> Legal Reasoning
  -> Decision
```

Each arrow is a separately governed gate. No step inherits authority from the
preceding artifact merely because the prior step was accepted.


## 8. Legal Fact Identity Boundary

The future Result must define, at minimum:

| Required Field | Required Meaning |
| --- | --- |
| `legal_fact_id` | Stable Matter-local identity for one confirmed factual statement. |
| `matter_id` | Exact governed Matter reference. |
| `legal_fact_statement` | One bounded statement; no actual statement is created by this Task. |
| `source_fact_candidate_references` | Exact accepted Fact Candidate identifiers and versions. |
| `source_evidence_references` | Traceable governed Evidence references inherited through the candidates. |
| `human_review_record` | Exact Review Artifact or record confirming the fact. |
| `confirmation_basis` | Stated basis, review standard, findings, and limitations. |
| `contradiction_disposition` | Treatment of supporting, contradicting, and alternative records. |
| `legal_context_reference` | Exact context in which the fact is confirmed; not a legal conclusion. |
| `reviewer_identity` | Human reviewer responsible for factual confirmation. |
| `review_time` | Reported Review time with timezone when available. |
| `status` | Current governed lifecycle state. |
| `permitted_use` | Defined purpose and downstream-use boundary. |
| `decision_reference` | Exact factual-confirmation Decision reference. |
| `version_or_revision_reference` | Stable reference preserving later changes. |
| `supersession_reference` | Later record that replaces or limits the Legal Fact, when applicable. |
| `known_limitations` | Residual uncertainty and unresolved limitation. |

Assignment of a `legal_fact_id` creates identity only. It does not establish a
legal conclusion, remedy, responsibility, liability, or litigation outcome.


## 9. Fact Candidate Completeness Gate

A future Legal Fact Review may begin only when the source Fact Candidate:

- has a stable identity and version;
- cites governed Evidence references;
- records its formation rule and transformation path;
- identifies supporting and contradicting material;
- records material alternative explanations;
- discloses confidence basis, uncertainty, and limitations;
- completed the required Human Review;
- has an accepted Fact Candidate Decision;
- is authorized for the proposed Legal Fact context and use.

A candidate in `BLOCKED`, `DISPUTED`, `REJECTED`, stale, superseded, or
unauthorized-use status cannot silently enter the Legal Fact Gate.


## 10. Human Legal Fact Review

The future Result must require:

- `reviewer_identity`;
- `review_time`;
- exact Fact Candidate and Evidence references;
- `review_basis`;
- applied factual-confirmation standard;
- supporting and contradicting findings;
- alternative-explanation treatment;
- residual uncertainty and limitations;
- `review_outcome`;
- permitted-use scope;
- Decision route.

The Review outcome may recommend confirmation, dispute, rejection, blocking,
or supersession. It cannot itself issue the downstream legal Decision.


## 11. Reviewer And Decision-Maker Separation

The future Result must distinguish:

```text
Human Fact Reviewer
  != Legal Decision Maker
```

The roles, artifacts, actions, and authority references must be separately
identified.

The same action or Artifact cannot simultaneously:

- confirm the factual record;
- perform legal reasoning;
- issue the final legal Decision.

If required role separation cannot be demonstrated, the process must be
`BLOCKED`.


## 12. Legal Fact Lifecycle Boundary

The future Result must define:

```text
PROPOSED
HUMAN_REVIEW
CONFIRMED
ADOPTED
DISPUTED
REJECTED
SUPERSEDED
ARCHIVED
BLOCKED
```

The lifecycle is not an unconditional linear pipeline.

Minimum permitted transitions:

```text
PROPOSED
  -> HUMAN_REVIEW

HUMAN_REVIEW
  -> CONFIRMED

HUMAN_REVIEW
  -> DISPUTED

HUMAN_REVIEW
  -> REJECTED

HUMAN_REVIEW
  -> BLOCKED

CONFIRMED
  -> ADOPTED

CONFIRMED
  -> DISPUTED

CONFIRMED
  -> SUPERSEDED

ADOPTED
  -> DISPUTED

ADOPTED
  -> SUPERSEDED

DISPUTED
  -> HUMAN_REVIEW

DISPUTED
  -> REJECTED

REJECTED
  -> ARCHIVED

SUPERSEDED
  -> ARCHIVED
```

Every transition must identify the reviewer or Decision maker, basis,
references, limitations, reported time, permitted-use effect, and Decision
record.

`CONFIRMED` means Human Fact Review accepted the bounded statement.

`ADOPTED` means a separate authorized Decision selected the confirmed Legal
Fact for a stated analytical or decisional context. Adoption is not itself the
legal conclusion.


## 13. Legal Fact And Decision Boundary

Prohibited:

```text
Legal Fact
  -> Automatic Legal Conclusion
```

Required:

```text
Legal Fact Set
  + Legal Authorities
  + Legal Reasoning
  + Review Evidence
  -> Legal Decision
```

The Decision must separately identify:

- legal Decision maker;
- accepted Legal Fact references and versions;
- applicable authorities and reasoning;
- contrary facts, authorities, and arguments;
- uncertainty and limitations;
- outcome and scope;
- Decision time and reference.

This Task may define the boundary but cannot perform legal reasoning or issue a
Decision.


## 14. Contradiction And Supersession Boundary

A later contradiction must:

1. preserve the prior Legal Fact and status history;
2. identify the challenged statement or field;
3. cite supporting and contradicting references;
4. suspend unauthorized downstream reliance;
5. route the fact to Human Review;
6. record the resulting Decision;
7. supersede rather than rewrite prior history when replacement is required.

`SUPERSEDED` does not mean the prior record never existed. It records that a
later governed record controls for the identified scope.


## 15. Fail-Closed Conditions

The future Result must require `BLOCKED` when:

- the source Fact Candidate is incomplete, stale, unresolved `DISPUTED`,
  `REJECTED`, `BLOCKED`, superseded, or unauthorized for the proposed use;
- Evidence, formation, transformation, contradiction, or alternative records
  are missing;
- Human Fact Review is incomplete;
- reviewer identity, Review time, basis, outcome, or Decision reference is
  missing;
- reviewer and legal Decision-maker roles are not separately identifiable;
- permitted use or legal context is ambiguous;
- residual uncertainty is concealed or overstated;
- the proposed transition would create a legal conclusion automatically;
- any input, output, path, side effect, or external access exceeds the
  authorized boundary.

No unknown candidate state, Evidence reference, reviewer, role, context,
authority, Decision, or uncertainty receives default permission.


## 16. Execution Boundary

A future execution may:

- read only the authorized governance inputs;
- define generic Legal Fact fields;
- define completeness, Human Review, role-separation, lifecycle, Decision, and
  fail-closed gates;
- create only the exact Result path.

A future execution may not:

- connect to or access an external Matter project;
- read Evidence or an actual Fact Candidate;
- create, confirm, adopt, dispute, reject, supersede, or archive a Legal Fact;
- perform legal reasoning;
- determine responsibility or liability;
- issue a legal Decision;
- select litigation strategy;
- create another task or output;
- modify an existing artifact.


## 17. Acceptance Criteria

The future Result is acceptable only if:

1. it contains no external Matter content, Evidence, Fact Candidate, Legal Fact,
   legal analysis, or Decision;
2. it defines LF-G-001;
3. it defines all required Legal Fact identity and traceability fields;
4. it defines Fact Candidate completeness prerequisites;
5. it defines Human Fact Review requirements;
6. it separates Human Fact Reviewer and Legal Decision Maker roles;
7. it defines lifecycle states and explicit transition conditions;
8. it separates Legal Fact, legal reasoning, and Legal Decision;
9. it defines contradiction, supersession, and fail-closed handling;
10. it adds no Legal Fact Model, Fact Model, Evidence Model, or Governance Model
    to ACOS Core;
11. it creates no Legal Fact, legal analysis, Decision, or additional task;
12. it modifies no existing file;
13. it includes a structured Execution Receipt and returns to ChatGPT Review.


## 18. Review Requirement

The future Result must return to `ChatGPT Review`.

Required Review checks:

- exact Task and authorization binding;
- scope and output-path compliance;
- absence of external project, Matter data, Evidence, and Fact Candidate
  access;
- absence of actual Legal Fact, legal analysis, or Decision content;
- LF-G-001;
- Legal Fact identity, completeness, Human Review, role-separation, lifecycle,
  contradiction, supersession, and fail-closed completeness;
- no ACOS Core modification;
- complete structured Execution Receipt;
- no unauthorized file or Git operation.

The Result cannot self-accept, issue a legal Decision, or close the Task.


## 19. Task State And Required Next Gates

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

- Executing TASK_OVC_001_004
- Transitioning to `TASK_READY`, `EXECUTION_AUTHORIZED`, or `TASK_EXECUTING`
- Creating the expected Result or Execution Receipt
- Accessing the external project, Matter workspace, case material, Evidence,
  or an actual Fact Candidate
- Creating, confirming, adopting, or changing a Legal Fact
- Generating legal reasoning, legal analysis, legal conclusions, or strategy
- Issuing a legal Decision
- Creating TASK_OVC_001_005, TASK_064, or any other task
- Creating or modifying a Governance Model, Evidence Model, Fact Model, or
  Legal Fact Model
- Modifying ACOS Core, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


FINAL STATUS:

```text
TASK_OVC_001_004 MATERIALIZED
TASK EXECUTION NOT AUTHORIZED
EVIDENCE ACCESS LOCKED
FACT CANDIDATE ACCESS LOCKED
LEGAL FACT CREATION LOCKED
LEGAL ANALYSIS LOCKED
DECISION LAYER LOCKED
```


NEXT RECEIVER:

ChatGPT Review


REASON:

TASK_OVC_001_004 is materialized as a governance-only Legal Fact Gate and Human
Decision boundary definition. It preserves Fact Candidate, Human Review, Legal
Fact, legal reasoning, and Decision separation while keeping all actual
Evidence, factual, legal, Decision, and execution activity separately gated.

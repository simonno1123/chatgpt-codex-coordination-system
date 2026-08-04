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
TASK_OVC_001_005

TASK NAME:
Decision Governance Boundary Definition

STATUS:
TASK_MATERIALIZED

MATTER ID:
MATTER_OVC_001_LEGAL_EXECUTION_ANALYSIS

TASK TYPE:
GOVERNANCE DEFINITION TASK

CAPABILITY CONTEXT:
Decision Governance

OBJECTIVE:
Define the governance boundary for how governed Legal Facts, legal authorities,
reasoning traces, options, risk assessments, Human Review, and explicit human
authority may support a traceable Legal Decision without reading Matter data,
performing legal analysis, selecting a strategy, or creating an actual
Decision.

AUTHORITY LIMIT:
This Artifact defines and materializes TASK_OVC_001_005 only.

It does not authorize:

- transition to `TASK_READY` or `TASK_EXECUTING`;
- task execution;
- external project or Matter workspace access;
- information, Evidence, Fact Candidate, or Legal Fact access;
- Evidence Artifact, Fact Candidate, or Legal Fact creation;
- legal research or legal reasoning;
- responsibility, liability, remedy, claim, or strategy determination;
- risk, probability, or outcome assessment for an actual Matter;
- Legal Decision proposal, approval, implementation, or lifecycle change;
- file creation other than this Task Definition;
- creation of another task;
- ACOS Core modification;
- cross-project changes;
- Git operations.

OUTPUT:
Task Definition Record only.


## 1. Governance Basis

TASK_OVC_001_005 uses existing ACOS governance records. It does not create a
new Decision Model, Legal Reasoning Model, Legal Fact Model, Fact Model,
Evidence Model, Policy Engine, or ACOS Core capability.

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

### Legal Fact Governance Result

Path:
`.codex-coordination/outbox/TASK_OVC_001_004_LEGAL_FACT_GATE_AND_HUMAN_DECISION_BOUNDARY_DEFINITION_RESULT.md`

SHA-256:
`3d6e3a4ad02a4dd06c513adaffa75ac3cf5e7e734f237c82e5eb2c556f126911`

### Legal Fact Governance Review

Path:
`.codex-coordination/outbox/TASK_OVC_001_004_LEGAL_FACT_GATE_AND_HUMAN_DECISION_BOUNDARY_DEFINITION_REVIEW.md`

SHA-256:
`17aa454a6a68bac77fc02b160280095235ee87015373a8afeb60a69a24786e6e`

### Legal Fact Governance Decision

Path:
`.codex-coordination/inbox/TASK_OVC_001_004_LEGAL_FACT_GATE_AND_HUMAN_DECISION_BOUNDARY_DEFINITION_DECISION.md`

SHA-256:
`5e876e9fe33f5d68cb55e8782058bd8890b1e6c6bd489d153f3c29695f084a6c`

### Legal Fact Governance Closure Decision

Path:
`.codex-coordination/inbox/TASK_OVC_001_004_LEGAL_FACT_GATE_AND_HUMAN_DECISION_BOUNDARY_DEFINITION_CLOSURE_DECISION.md`

SHA-256:
`7ec9dc65e214b820e070d2a8247c60651b7e50bb16829b71884ec815a2e91964`


## 2. Decision Terminology Boundary

This Task distinguishes:

### ACOS Governance Decision

An ACOS Artifact governing Task, Review, authorization, closure, maintenance,
or lifecycle state.

### Legal Decision

A future Matter-level human Decision that selects or rejects an authorized
legal or strategic course after considering governed Legal Facts, authorities,
reasoning, options, risks, and Review Evidence.

This Task defines the boundary of a future Legal Decision. It does not convert
an ACOS Task Decision into a Legal Decision and does not grant legal
Decision-making authority.


## 3. Capability Boundary

`Decision Governance` is a Matter-workflow boundary label. It is not a new
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

No capability to read Matter data, access Legal Facts, perform legal reasoning,
assess an actual risk, select an option, or issue a Legal Decision is granted.


## 4. Allowed Inputs For Future Execution

A future separately authorized execution may read only:

- the ten governance artifacts listed in Section 1;
- this Task Definition;
- a future Task Review and Task Readiness Decision;
- a future Task Execution Authorization.

These inputs contain governance definitions and records only.


## 5. Inputs Not Allowed

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
- legal authorities selected for an actual Matter;
- legal opinions, analyses, conclusions, or strategies;
- actual Decision options, risk assessments, probabilities, or outcomes;
- external network, provider, model, API, or search results.


## 6. Expected Future Output

Expected Artifact:

```text
RESULT
```

Expected record:

```text
Decision Governance Boundary Definition Result
```

Proposed exact output path:

`.codex-coordination/outbox/TASK_OVC_001_005_DECISION_GOVERNANCE_BOUNDARY_DEFINITION_RESULT.md`

The Result must define governance structure only. It must not include an actual
Evidence item, Fact Candidate, Legal Fact, legal analysis, Legal Decision,
Matter recommendation, claim selection, remedy selection, or litigation
strategy.

The Result must contain:

1. DG-G-001;
2. DG-G-002;
3. Decision identity and traceability fields;
4. Legal Fact readiness requirements;
5. legal authority and reasoning-trace requirements;
6. option and risk comparison requirements;
7. Human Decision Authority requirements;
8. Review and Decision separation;
9. Decision lifecycle states and transition rules;
10. audit-trail and supersession requirements;
11. fail-closed conditions;
12. a non-implementation boundary;
13. a structured Execution Receipt.


## 7. DG-G-001

The future Result must define:

```text
Legal Fact
  != Legal Reasoning
  != Legal Decision
```

A Legal Fact is a governed factual statement confirmed for an exact context
and permitted use.

Legal Reasoning applies legal rules, authorities, interpretation, and analysis
to governed inputs.

A Legal Decision records an authorized human choice, approval, rejection, or
course of action.

Prohibited:

```text
Legal Fact
  -> Automatic Legal Decision
```


## 8. DG-G-002

The future Result must define:

```text
Legal Reasoning
  != Human Decision
```

Legal Reasoning may support a future human decision by presenting:

- applicable authority references;
- reasoning paths;
- competing interpretations;
- available options;
- risk and uncertainty;
- limitations;
- unresolved questions.

It may not:

- choose the final option;
- bind the Decision Maker;
- conceal alternatives or uncertainty;
- convert model confidence into authority;
- issue or implement a Legal Decision.

Prohibited:

```text
AI Analysis
  -> Automatic Legal Decision
```


## 9. Decision Identity Boundary

The future Result must define, at minimum:

| Required Field | Required Meaning |
| --- | --- |
| `decision_id` | Stable Matter-local identity for one Legal Decision record. |
| `matter_id` | Exact governed Matter reference. |
| `decision_subject` | Bounded question or choice; no actual subject is created by this Task. |
| `input_legal_fact_references` | Exact governed Legal Fact identifiers and versions. |
| `legal_authority_references` | Exact authorities used by the reasoning record. |
| `legal_reasoning_reference` | Traceable legal analysis Artifact or record. |
| `decision_options` | Material options considered, including no-action when applicable. |
| `risk_assessment_reference` | Traceable risk and uncertainty record. |
| `review_evidence_reference` | Independent Review Evidence consumed by the Decision. |
| `decision_maker_identity` | Human authority responsible for the Decision. |
| `authority_reference` | Record proving the Decision Maker's governance authority. |
| `decision_basis` | Stated factual, legal, analytical, and practical basis. |
| `decision_outcome` | Selected, rejected, deferred, blocked, or withdrawn outcome. |
| `decision_time` | Reported Decision time with timezone when available. |
| `status` | Current governed lifecycle state. |
| `scope_and_permitted_use` | Exact scope, audience, purpose, and use boundary. |
| `known_limitations` | Residual factual, legal, procedural, or operational uncertainty. |
| `implementation_reference` | Separately authorized implementation record, when applicable. |
| `audit_trail_reference` | Complete immutable transition and Review history. |
| `version_or_revision_reference` | Stable reference preserving later changes. |
| `supersession_reference` | Later Decision that replaces or limits this Decision. |

Assignment of a `decision_id` creates a traceable Decision record identity only.
It does not grant authority, approve an option, implement an action, or
establish legal correctness.


## 10. Legal Fact Readiness Gate

A future Legal Decision Review may begin only when every input Legal Fact:

- has a stable identity and version;
- is in an authorized lifecycle state;
- cites the required Fact Candidate and Evidence trace;
- completed Human Fact Review;
- has a factual-confirmation Decision;
- identifies context, permitted use, uncertainty, and limitations;
- is not stale, unresolved `DISPUTED`, `REJECTED`, `BLOCKED`, or superseded;
- is authorized for the proposed Decision purpose.

Prohibited:

```text
Unconfirmed Fact
  -> Legal Decision
```

Unknown or incomplete factual readiness receives no favorable default.


## 11. Legal Reasoning Trace Gate

The future Result must require a reviewable reasoning trace containing:

- exact input Legal Fact references and versions;
- exact legal authority references and versions or effective dates;
- issue framing;
- applicable rules and interpretive assumptions;
- ordered reasoning steps;
- contrary authorities and arguments;
- factual and legal uncertainty;
- alternative reasoning paths;
- conclusions limited to the analysis scope;
- author or executor identity;
- Review status and Review Evidence;
- reported creation and Review times;
- authorization references.

A conclusory, opaque, stale, unsupported, or unreviewed analysis must produce
`BLOCKED`.

The reasoning trace supports a Decision but does not issue it.


## 12. Options And Risk Boundary

The future Result must require:

- all material Decision options identified;
- a separately stated no-action or defer option when applicable;
- benefits, burdens, dependencies, and reversibility for each option;
- factual, legal, procedural, operational, and timing risks;
- uncertainty and missing information;
- assumptions and sensitivity to changed facts or authorities;
- consequences of each option;
- reasons for excluding a known material option;
- Review Evidence for the comparison.

Risk analysis may compare uncertainty. It must not present unsupported
probability as fact or automatically select an option.


## 13. Human Decision Authority Gate

Before a Legal Decision may enter an approved state, the future Result must
require:

- `decision_maker_identity`;
- an explicit authority reference;
- Decision scope and permitted use;
- confirmation that the Decision Maker reviewed the Legal Facts, reasoning,
  options, risks, contrary material, and limitations;
- `decision_basis`;
- `decision_outcome`;
- `decision_time`;
- Decision status;
- audit-trail reference.

Human Decision Authority cannot be inferred from:

- model identity;
- executor identity;
- reviewer identity alone;
- document authorship;
- system access;
- confidence;
- prior similar Decisions.

If authority is missing, ambiguous, expired, conflicted, or outside scope, the
Decision must be `BLOCKED`.


## 14. Review And Decision Separation

The future Result must preserve:

```text
Legal Analysis
  -> Review Evidence
  -> Human Legal Decision
```

and:

```text
Review Evidence
  != Legal Decision
```

The reviewer may assess facts, reasoning, options, risks, and completeness.
The reviewer cannot silently issue the Decision unless separately identified
and authorized as the Decision Maker under a distinct Decision action and
record.

An Advisory observation remains non-binding and cannot transition Decision
state.


## 15. Decision Lifecycle Boundary

The future Result must define:

```text
PROPOSED
UNDER_REVIEW
APPROVED
REJECTED
DEFERRED
BLOCKED
IMPLEMENTATION_AUTHORIZED
IMPLEMENTED
WITHDRAWN
SUPERSEDED
ARCHIVED
```

The lifecycle is not an unconditional linear pipeline.

Minimum permitted transitions:

```text
PROPOSED
  -> UNDER_REVIEW

UNDER_REVIEW
  -> APPROVED

UNDER_REVIEW
  -> REJECTED

UNDER_REVIEW
  -> DEFERRED

UNDER_REVIEW
  -> BLOCKED

APPROVED
  -> IMPLEMENTATION_AUTHORIZED

APPROVED
  -> WITHDRAWN

APPROVED
  -> SUPERSEDED

IMPLEMENTATION_AUTHORIZED
  -> IMPLEMENTED

IMPLEMENTATION_AUTHORIZED
  -> WITHDRAWN

DEFERRED
  -> UNDER_REVIEW

BLOCKED
  -> UNDER_REVIEW

IMPLEMENTED
  -> SUPERSEDED

REJECTED
  -> ARCHIVED

WITHDRAWN
  -> ARCHIVED

SUPERSEDED
  -> ARCHIVED
```

Every transition must identify:

- `decision_id`;
- prior and target state;
- Decision Maker or reviewer identity;
- authority reference;
- Legal Fact, authority, reasoning, Review, option, and risk references;
- basis, outcome, limitations, and unresolved uncertainty;
- reported transition time;
- scope and permitted-use effect;
- implementation or supersession effect when applicable.


## 16. Decision And Implementation Separation

The future Result must prohibit:

```text
APPROVED
  -> Automatic Implementation
```

Required:

```text
APPROVED
  -> Separate Implementation Authorization
  -> IMPLEMENTATION_AUTHORIZED
  -> Governed Implementation
  -> IMPLEMENTED
```

Approval records a human Decision. It does not by itself authorize a command,
filing, communication, payment, external action, or system change.


## 17. Audit Trail Boundary

The future Result must require an append-preserving audit trail containing:

- every Decision version;
- source Legal Fact versions;
- authority and reasoning references;
- options and risk records;
- Review Evidence;
- Decision Maker and authority records;
- status transitions;
- implementation authorization and receipt references;
- contradiction, withdrawal, and supersession records;
- timestamps and known limitations.

Later changes must supersede rather than rewrite prior Decisions.


## 18. Fail-Closed Conditions

The future Result must require `BLOCKED` when:

- a required Legal Fact is missing, stale, unresolved `DISPUTED`, `REJECTED`,
  `BLOCKED`, superseded, or unauthorized for the proposed use;
- an authority reference, reasoning step, contrary authority, option, risk,
  limitation, or Review record is missing;
- the Decision Maker identity or authority is missing, ambiguous, expired,
  conflicted, or outside scope;
- the Decision question, outcome, audience, or permitted use is ambiguous;
- uncertainty is concealed or overstated;
- the proposed transition would create an automatic Legal Decision;
- the proposed transition would implement an unimplemented Decision
  automatically;
- any input, output, path, side effect, or external access exceeds the
  authorized boundary.

No unknown fact, authority, reasoning step, option, risk, reviewer, Decision
Maker, scope, implementation authority, or uncertainty receives default
permission.


## 19. Execution Boundary

A future execution may:

- read only the authorized governance inputs;
- define generic Decision fields;
- define Legal Fact readiness, reasoning trace, option, risk, Human Authority,
  Review, lifecycle, implementation, audit, and fail-closed gates;
- create only the exact Result path.

A future execution may not:

- connect to or access an external Matter project;
- read Evidence, a Fact Candidate, or an actual Legal Fact;
- conduct legal research or legal reasoning;
- propose or select an actual Decision option;
- assess actual responsibility, liability, remedy, probability, or outcome;
- approve, reject, implement, withdraw, or supersede a Legal Decision;
- create a legal opinion or litigation strategy;
- create another task or output;
- modify an existing artifact.


## 20. Acceptance Criteria

The future Result is acceptable only if:

1. it contains no external Matter content, Evidence, Fact Candidate, Legal
   Fact, legal analysis, Legal Decision, recommendation, or strategy;
2. it defines DG-G-001;
3. it defines DG-G-002;
4. it distinguishes ACOS governance Decisions from Matter-level Legal
   Decisions;
5. it defines all required Decision identity and traceability fields;
6. it defines Legal Fact readiness requirements;
7. it defines legal reasoning-trace requirements;
8. it defines option and risk comparison requirements;
9. it defines Human Decision Authority requirements;
10. it separates Review, Decision, and implementation;
11. it defines lifecycle states and explicit transition conditions;
12. it defines audit, withdrawal, supersession, and fail-closed handling;
13. it adds no Decision Model, Legal Reasoning Model, or Governance Model to
    ACOS Core;
14. it creates no Legal Decision, legal analysis, implementation, or additional
    task;
15. it modifies no existing file;
16. it includes a structured Execution Receipt and returns to ChatGPT Review.


## 21. Review Requirement

The future Result must return to `ChatGPT Review`.

Required Review checks:

- exact Task and authorization binding;
- scope and output-path compliance;
- absence of external project, Matter data, Evidence, Fact Candidate, and Legal
  Fact access;
- absence of actual legal reasoning, Decision, implementation, or strategy;
- DG-G-001 and DG-G-002;
- Decision identity, Legal Fact readiness, reasoning trace, options, risks,
  Human Authority, Review separation, lifecycle, implementation separation,
  audit, and fail-closed completeness;
- no ACOS Core modification;
- complete structured Execution Receipt;
- no unauthorized file or Git operation.

The Result cannot self-accept, issue a Legal Decision, implement an action, or
close the Task.


## 22. Task State And Required Next Gates

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

- Executing TASK_OVC_001_005
- Transitioning to `TASK_READY`, `EXECUTION_AUTHORIZED`, or `TASK_EXECUTING`
- Creating the expected Result or Execution Receipt
- Accessing the external project, Matter workspace, case material, Evidence,
  a Fact Candidate, or a Legal Fact
- Performing legal research, legal reasoning, risk assessment, or probability
  assessment for an actual Matter
- Proposing, approving, rejecting, implementing, or superseding a Legal
  Decision
- Generating a legal conclusion, legal opinion, recommendation, claim choice,
  remedy choice, or litigation strategy
- Creating TASK_OVC_001_006, TASK_064, or any other task
- Creating or modifying a Governance Model, Decision Model, Legal Reasoning
  Model, Legal Fact Model, Fact Model, or Evidence Model
- Modifying ACOS Core, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


FINAL STATUS:

```text
TASK_OVC_001_005 MATERIALIZED
TASK EXECUTION NOT AUTHORIZED
EVIDENCE ACCESS LOCKED
FACT CANDIDATE ACCESS LOCKED
LEGAL FACT ACCESS LOCKED
LEGAL REASONING LOCKED
LEGAL DECISION CREATION LOCKED
DECISION IMPLEMENTATION LOCKED
```


NEXT RECEIVER:

ChatGPT Review


REASON:

TASK_OVC_001_005 is materialized as a governance-only Decision boundary
definition. It preserves Legal Fact, legal reasoning, Human Review, Human
Decision Authority, Legal Decision, and implementation separation while
keeping all actual Matter, factual, legal, decisional, implementation, and
execution activity separately gated.

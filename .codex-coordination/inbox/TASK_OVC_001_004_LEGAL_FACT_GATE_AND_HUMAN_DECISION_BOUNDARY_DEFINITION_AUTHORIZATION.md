ARTIFACT TYPE:
DECISION

PRODUCER:
ChatGPT Review

TO:
ChatGPT Review

NEXT RECEIVER:
ChatGPT Review

PROJECT:
/Users/zhang/Documents/chatgpt-codex-coordination-system

MODE:
TASK READINESS AUTHORIZATION / NON-EXECUTION

SUBJECT:
TASK_OVC_001_004_LEGAL_FACT_GATE_AND_HUMAN_DECISION_BOUNDARY_DEFINITION

TASK ID:
TASK_OVC_001_004

TASK NAME:
Legal Fact Gate and Human Decision Boundary Definition

MATTER ID:
MATTER_OVC_001_LEGAL_EXECUTION_ANALYSIS

SOURCE:
`.codex-coordination/inbox/TASK_OVC_001_004_LEGAL_FACT_GATE_AND_HUMAN_DECISION_BOUNDARY_DEFINITION.md`

SOURCE SHA-256:
`7eb6295825b9d7b26df859d18211ba9b143e8930ee22caa4bf01c0966074dfed`

OBJECTIVE:
Decide whether TASK_OVC_001_004 may transition from `TASK_MATERIALIZED` to
`TASK_READY` without beginning execution, accessing Evidence or a Fact
Candidate, creating a Legal Fact, performing legal analysis, or generating a
Decision.

AUTHORITY LIMIT:
This Decision authorizes the Task readiness state transition only.

It does not authorize:

- transition to `EXECUTION_AUTHORIZED` or `TASK_EXECUTING`;
- creation of the expected Result or Execution Receipt;
- external project or Matter workspace access;
- information, Evidence, or Fact Candidate access;
- Evidence Artifact or Fact Candidate creation;
- Legal Fact creation, confirmation, adoption, or lifecycle change;
- legal reasoning, responsibility determination, or liability determination;
- legal analysis, conclusions, or litigation strategy;
- legal or Matter Decision generation;
- modification of an Evidence Model, Fact Model, Legal Fact Model, or
  Governance Model;
- modification of existing artifacts;
- creation of another task;
- ACOS Core modification;
- cross-project changes;
- Git operations.

OUTPUT:
Task Readiness Authorization Decision Record only.


DECISION:

AUTHORIZED


CURRENT STATE:

```text
TASK_MATERIALIZED
```


TARGET STATE:

```text
TASK_READY
```


AUTHORIZED STATE TRANSITION:

```text
TASK_MATERIALIZED
  -> TASK_READY
```


NOT AUTHORIZED:

```text
TASK_MATERIALIZED
  -> TASK_EXECUTING
```

or:

```text
TASK_READY
  -> EXECUTION_AUTHORIZED
```

or:

```text
TASK_READY
  -> TASK_EXECUTING
```

Readiness, execution authorization, execution, Legal Fact Review, legal
reasoning, and Decision generation remain separate governance actions.


## 1. Task Definition Review

The reviewed Task Definition:

- identifies one exact Task ID and Matter ID;
- defines a governance-definition objective;
- binds existing ACOS governance and completed TASK_OVC_001_003 records by
  path and digest;
- treats `Legal Fact Governance` as a Matter-workflow boundary label;
- creates no ACOS Core capability, Evidence Model, Fact Model, Legal Fact
  Model, legal reasoning model, or Decision model;
- excludes all external Matter, Evidence, Fact Candidate, and case inputs;
- proposes one exact future Result path;
- defines LF-G-001;
- defines Legal Fact identity and traceability requirements;
- defines Fact Candidate completeness prerequisites;
- defines Human Legal Fact Review requirements;
- separates Human Fact Reviewer and Legal Decision Maker roles;
- defines Legal Fact lifecycle states and transition requirements;
- separates Legal Fact, legal reasoning, and Legal Decision;
- defines contradiction, supersession, and fail-closed handling;
- requires a structured Execution Receipt and ChatGPT Review;
- prohibits factual, legal, Decision, follow-on task, and ACOS Core activity.


## 2. Readiness Conditions

| Condition | Result |
| --- | --- |
| Task Artifact exists at one unique path | PASS |
| Task ID and Matter ID are explicit | PASS |
| Objective and Task type are explicit | PASS |
| Existing governance basis is bound | PASS |
| Completed Fact Construction Governance records are bound | PASS |
| External, Matter, Evidence, and Fact Candidate inputs are prohibited | PASS |
| Expected future Result path is explicit | PASS |
| LF-G-001 is explicit | PASS |
| Legal Fact identity and traceability requirements are explicit | PASS |
| Human Review and role-separation gates are explicit | PASS |
| Lifecycle and transition requirements are explicit | PASS |
| Legal Fact, legal reasoning, and Decision separation is explicit | PASS |
| Fail-closed and acceptance criteria are explicit | PASS |
| Execution remains separately gated | PASS |


## 3. Authorized Readiness Scope

This Decision allows:

- recognition that the Task Definition is complete enough for execution
  planning;
- verification of the proposed Result boundary;
- preparation of a separate Execution Authorization;
- read-only review of the exact governance inputs named by the Task.

This Decision does not allow creation of any execution output, Evidence
Artifact, Fact Candidate, Legal Fact, legal analysis, or Decision.


## 4. Authorized Future Execution Inputs

If a separate Task Execution Authorization is later issued, execution may use
only:

- the existing governance artifacts named by the Task Definition;
- the Task Definition;
- this Readiness Authorization;
- the future Execution Authorization.

No external Matter content, Evidence content, actual Fact Candidate, actual
Legal Fact, legal opinion, or Matter-specific proposition is included.


## 5. Authorized Future Output Boundary

If execution is separately authorized, the only permitted output is:

`.codex-coordination/outbox/TASK_OVC_001_004_LEGAL_FACT_GATE_AND_HUMAN_DECISION_BOUNDARY_DEFINITION_RESULT.md`

The future Artifact type must be:

```text
RESULT
```

It must define governance structure only and include a structured Execution
Receipt. This Decision does not create that file or authorize its creation.


## 6. Legal Fact And Decision Boundary

The Task preserves:

```text
Evidence
  -> Fact Candidate
  -> Human Fact Review
  -> Legal Fact
  -> Legal Reasoning
  -> Decision
```

Each transition remains a separately governed gate.

LF-G-001 remains:

```text
Legal Fact
  != Legal Analysis
  != Legal Decision
```

Prohibited:

```text
Legal Fact
  -> Automatic Legal Conclusion
```

Moving the Task to `TASK_READY` does not apply this chain to any actual
Evidence, Fact Candidate, Legal Fact, analysis, or Decision.


## 7. Current Locks

Current Task execution state:

```text
LOCKED
```

Current Evidence access state:

```text
LOCKED
```

Current Fact Candidate access and creation state:

```text
LOCKED
```

Current Legal Fact creation state:

```text
LOCKED
```

Current legal analysis state:

```text
LOCKED
```

Current Decision generation state:

```text
LOCKED
```

Current Matter state remains:

```text
ACTIVATED
```

No lock is removed by this Decision.


## 8. Capability Boundary

Current active governance capability:

```text
task_review
```

Candidate future executor capability:

```text
file_modify
```

remains inactive until a separate Task Execution Authorization is
materialized.

`Legal Fact Governance` remains Matter-workflow context and does not grant
Evidence, Fact Candidate, Legal Fact, legal analysis, Decision, or execution
capability.


## 9. Execution Lock

To unlock execution, a separate Decision must:

- name TASK_OVC_001_004;
- bind the exact Task and Readiness Authorization hashes;
- name every permitted governance input;
- name the exact Result path;
- preserve the prohibition on external project, Matter, Evidence, and Fact
  Candidate access;
- authorize only `file_modify` for the one Result;
- require a structured Execution Receipt and post-execution Review;
- keep Legal Fact creation, legal analysis, Decision generation, and Git
  operations unauthorized.

Until that separate Decision is materialized, no Result or Receipt may be
created.


## 10. Fail-Closed Conditions

Execution must remain blocked if:

- the Task Definition hash changes;
- an authorized governance input is missing or stale;
- any external, Matter, Evidence, Fact Candidate, or factual input is
  requested;
- an input path is outside the Task Definition;
- the output path changes;
- the requested output contains an actual Legal Fact, legal analysis, or
  Decision;
- factual confirmation, legal reasoning, liability determination, or
  litigation work is requested;
- another task or Artifact is proposed;
- required Review routing is absent;
- an Execution Authorization is not materialized.


FORBIDDEN:

- Executing TASK_OVC_001_004
- Transitioning to `EXECUTION_AUTHORIZED` or `TASK_EXECUTING`
- Creating the expected Result or Execution Receipt
- Accessing the external project, Matter workspace, case material, Evidence,
  or an actual Fact Candidate
- Creating, confirming, adopting, or changing a Legal Fact
- Generating legal reasoning, legal analysis, legal conclusions, or strategy
- Issuing a legal or Matter Decision
- Creating TASK_OVC_001_005, TASK_064, or any other task
- Creating or modifying a Governance Model, Evidence Model, Fact Model, or
  Legal Fact Model
- Modifying ACOS Core, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


FINAL STATUS:

```text
TASK_OVC_001_004 READY
TASK EXECUTION LOCKED
EVIDENCE ACCESS LOCKED
FACT CANDIDATE ACCESS LOCKED
LEGAL FACT CREATION LOCKED
LEGAL ANALYSIS LOCKED
DECISION LAYER LOCKED
```


NEXT RECEIVER:

ChatGPT Review


REASON:

TASK_OVC_001_004 has a complete, bounded, governance-only definition and may
enter `TASK_READY`. A separate Execution Authorization is still required before
Codex may create the Result, and no Evidence, Fact Candidate, Legal Fact,
legal analysis, Decision, or execution activity is authorized.

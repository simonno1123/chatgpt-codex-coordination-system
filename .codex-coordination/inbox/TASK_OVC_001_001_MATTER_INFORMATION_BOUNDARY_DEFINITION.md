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
TASK_OVC_001_001

TASK NAME:
Matter Information Boundary Definition

STATUS:
TASK_MATERIALIZED

MATTER ID:
MATTER_OVC_001_LEGAL_EXECUTION_ANALYSIS

OBJECTIVE:
Define the information-boundary structure for the activated governance Matter
so that any future information intake can be separately scoped, reviewed, and
authorized without accessing the external project or its contents.

AUTHORITY LIMIT:
This Artifact defines and materializes TASK_OVC_001_001 only.

It does not authorize:

- transition to `TASK_READY`;
- task execution;
- external project or workspace access;
- Matter information or evidence intake;
- evidence reading, copying, classification, or judgment;
- fact construction;
- legal analysis, conclusions, or litigation strategy;
- file creation other than this Task Definition;
- ACOS Core modification;
- cross-project changes;
- Git operations.

OUTPUT:
Task Definition Record only.


## 1. Source References

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


## 2. Task Type

```text
GOVERNANCE PREPARATION TASK
```

This task is intended to define a future information boundary. It is not an
Evidence Intake task, Evidence Analysis task, legal-analysis task, or
litigation-strategy task.


## 3. Capability References

### Current Governance Capability

`CHATGPT_REVIEW` uses the existing ACOS capability:

```text
task_define
```

to define this bounded task.

### Candidate Future Executor Capability

If execution is separately authorized, `CODEX_EXECUTOR` may become eligible to
use:

```text
file_modify
```

only for the exact future output path and inputs named by a Task Readiness
Decision.

### Matter Workstream Context

```text
Evidence Analysis
```

is a Matter-local workstream requirement, not an ACOS Core capability. It is not
activated by this Task.


## 4. Allowed Inputs For Future Execution

Only the following existing ACOS governance artifacts may be read during a
future separately authorized execution:

- `docs/capability-model.md`
- `docs/task-state-machine.md`
- `docs/execution-boundary-model.md`
- `docs/execution-receipt-model.md`
- `docs/review-evidence-model.md`
- the four source artifacts listed in Section 1;
- this Task Definition;
- a future Task Review and Task Readiness Decision.

Allowed inputs contain governance metadata only.


## 5. Inputs Not Allowed

Future execution must not read or receive:

- external case files;
- evidence materials;
- personal data;
- court documents;
- corporate records;
- transaction records;
- communication records;
- property information;
- Matter workspace contents;
- client instructions;
- legal opinions or strategy materials;
- external network or provider data.


## 6. Expected Future Output

Expected Artifact:

```text
RESULT
```

Expected record:

```text
Matter Information Boundary Definition Record
```

Proposed exact output path:

`.codex-coordination/outbox/TASK_OVC_001_001_MATTER_INFORMATION_BOUNDARY_DEFINITION_RESULT.md`

The output must define structure only and include:

- information category schema at the label level;
- source and ownership/custody boundary fields;
- provenance requirements;
- sensitivity and access-control labels;
- future intake prerequisites;
- future intake prohibited conditions;
- evidence-versus-fact separation;
- review checkpoints;
- Decision checkpoints;
- fail-closed conditions;
- non-implementation statement.

It must not include actual Matter information or evidence.


## 7. Execution Boundary

A future execution may:

- read only authorized governance artifacts;
- define generic Matter information categories;
- define required metadata fields;
- define future intake and review gates;
- create only the exact future output Artifact.

A future execution may not:

- access or connect an external project;
- create a Matter workspace;
- intake, copy, summarize, classify, or judge actual information;
- create an Evidence Artifact;
- create a Fact Candidate or Legal Fact;
- perform legal analysis;
- select litigation strategy;
- create a second task or output;
- modify existing artifacts.


## 8. Required Information Boundary Components

The future output must address:

### 8.1 Information Categories

Generic category labels only, such as:

- identity and party information;
- procedural and court information;
- corporate and organizational information;
- transaction information;
- communication information;
- property and asset information;
- legal research material;
- governance and decision records.

No actual value, name, date, amount, document, or allegation may be included.

### 8.2 Ownership And Custody Boundary

Required fields:

- source owner or custodian;
- access authority reference;
- storage location class;
- copy permission;
- permitted users or roles;
- retention status;
- external disclosure restriction.

### 8.3 Provenance Boundary

Required fields:

- source identifier;
- acquisition method;
- acquisition date, when later available;
- materialization date;
- hash or integrity reference, when later available;
- original-versus-copy status;
- known limitations.

### 8.4 Evidence And Fact Boundary

```text
Information
  != Evidence
  != Fact Candidate
  != Legal Fact
```

No transition is automatic.

### 8.5 Future Intake Requirements

Future intake must require:

- Matter workspace authorization;
- exact source and path boundary;
- access authorization;
- copy and retention rules;
- sensitivity classification;
- evidence handling Decision;
- human Review route;
- audit or receipt requirements.

### 8.6 Review Checkpoints

Review must occur before:

- information is accepted as an Evidence Artifact;
- an Evidence Artifact supports a Fact Candidate;
- a Fact Candidate is accepted as a Legal Fact;
- information is used in legal analysis;
- information is disclosed or exported.


## 9. Acceptance Criteria

The future Result is acceptable only if:

1. It contains no external Matter content.
2. It defines information categories without case-specific values.
3. It separates Information, Evidence, Fact Candidate, and Legal Fact.
4. It defines ownership, custody, provenance, access, and sensitivity fields.
5. It requires separate authorization before intake.
6. It requires human review before legal use.
7. It identifies fail-closed conditions.
8. It does not add a Governance Model to ACOS Core.
9. It creates no Evidence Artifact, Fact, legal analysis, or task.
10. It modifies no existing file.


## 10. Review Requirement

The future Result must return to `ChatGPT Review`.

Required review checks:

- exact task and source binding;
- scope compliance;
- output-path compliance;
- boundary preservation;
- absence of external data access;
- absence of actual Matter information;
- Evidence-versus-Fact separation;
- no ACOS Core modification;
- no unauthorized file or Git operation.

The Result cannot self-accept.


## 11. Task State And Required Next Gate

Current state:

```text
TASK_MATERIALIZED
```

Not current:

```text
TASK_READY
TASK_EXECUTING
TASK_RESULT
```

Required sequence:

```text
TASK_MATERIALIZED
  -> Task Definition Review
  -> Task Authorization Decision
  -> TASK_READY
  -> Execution
```

Execution remains locked until a separate Decision names the exact permitted
inputs, output path, and execution authority.


FORBIDDEN:

- Executing TASK_OVC_001_001
- Transitioning the task to `TASK_READY` or `TASK_EXECUTING`
- Accessing the external project, Matter workspace, or any case material
- Reading, importing, copying, or judging evidence
- Creating an Evidence Artifact, Fact Candidate, or Legal Fact
- Generating legal analysis, legal conclusions, or litigation strategy
- Creating TASK_064 or another task
- Creating or modifying a Governance Model or Evidence Model
- Modifying ACOS Core, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


FINAL STATUS:

```text
TASK_OVC_001_001 MATERIALIZED
TASK EXECUTION NOT AUTHORIZED
EXTERNAL INFORMATION ACCESS NOT AUTHORIZED
```


NEXT RECEIVER:

ChatGPT Review


REASON:

The first Operational Validation task is now defined with explicit inputs,
outputs, review requirements, and fail-closed boundaries. It remains
unreviewed for readiness and cannot execute.

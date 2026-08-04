ARTIFACT TYPE:
REVIEW

PRODUCER:
ChatGPT Review

TO:
Codex Executor

NEXT RECEIVER:
ChatGPT Review

PROJECT:
/Users/zhang/Documents/chatgpt-codex-coordination-system

MODE:
MATTER ONBOARDING BOUNDARY DEFINITION

SUBJECT:
OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS

OBJECTIVE:
Define how an external Validation Case may later enter an ACOS-governed Matter
boundary without activating, importing, or executing the external project.

SOURCE:

- `.codex-coordination/inbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS.md`
- `.codex-coordination/inbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS_DECISION.md`

AUTHORITY LIMIT:
This Artifact defines a Matter Onboarding Boundary only.

It does not authorize:

- Matter creation or activation;
- access to an external project;
- evidence import, copying, classification, or judgment;
- case analysis or fact construction;
- legal reasoning, conclusions, or strategy;
- capability assignment;
- task creation, materialization, or execution;
- modification of ACOS core;
- cross-project changes;
- Git operations.

OUTPUT:
Matter Onboarding Boundary Definition only.


## 1. Boundary Principles

```text
External Project
  != ACOS Core
```

```text
Matter Workspace
  != Governance Model
```

```text
Matter Onboarding Boundary
  != Matter Activation
  != Matter Execution
```

```text
Project Exists
  -> Boundary Exists
  -> Separate Authorization Exists
  -> Matter May Be Activated
```

The selected legal project remains external. This Artifact neither identifies
nor creates its filesystem workspace, coordination directory, evidence store,
or task tree.


## 2. Project Isolation Boundary

ACOS core may contain:

- generic governance models;
- this Validation Case Definition;
- this Boundary Definition;
- later governance Decisions and validation records.

ACOS core must not contain:

- case files;
- evidence copies;
- client communications;
- court documents;
- corporate records;
- transaction records;
- property records;
- matter-specific legal work product.

Any future external Matter workspace must remain outside ACOS core and requires
a separate User Decision or ChatGPT Review Decision, as applicable, before
Codex may access it.


## 3. Matter Identity Requirements

A future Matter Activation record must identify:

- `matter_id`
- `project_reference`
- `validation_case_reference`
- `owner`
- `matter_workspace_reference`
- `lifecycle_status`
- `activation_decision_reference`
- `evidence_boundary_reference`
- `task_boundary_reference`
- `review_boundary_reference`

This Boundary Definition does not assign any value to those fields and does not
create a Matter identity.


## 4. Matter Lifecycle

Permitted lifecycle model:

```text
DEFINED
  -> ONBOARDING_PENDING
  -> ACTIVATION_REVIEW
  -> ACTIVATED
  -> SUSPENDED or CLOSED
```

Transition requirements:

| Transition | Required Condition |
|---|---|
| `DEFINED -> ONBOARDING_PENDING` | Boundary Definition is materialized and reviewed. |
| `ONBOARDING_PENDING -> ACTIVATION_REVIEW` | Proposed identity, owner, workspace, and isolation evidence are available without unauthorized project access. |
| `ACTIVATION_REVIEW -> ACTIVATED` | A separate Matter Activation Decision explicitly authorizes activation. |
| `ACTIVATED -> SUSPENDED` | A blocker, authority conflict, evidence-boundary violation, or User Decision requires suspension. |
| `ACTIVATED or SUSPENDED -> CLOSED` | Closure evidence and a separate closure Decision exist. |

`TASK_READY` is not a Matter lifecycle state. After Matter activation, each
task must independently follow the ACOS Task State Machine:

```text
TASK_DEFINED
  -> TASK_MATERIALIZED
  -> TASK_READY
  -> TASK_EXECUTING
  -> TASK_RESULT
  -> TASK_REVIEW
  -> TASK_DECISION
  -> TASK_CLOSED
```


## 5. Matter Activation Boundary

A future Matter Activation Decision must specify:

- exact Matter identity;
- owner and decision authority;
- external project reference;
- permitted workspace access mode;
- allowed and forbidden paths;
- evidence handling boundary;
- allowed capabilities;
- prohibited capabilities;
- task creation boundary;
- review and decision routes;
- audit and closure expectations.

Activation must fail closed when:

- the project reference is ambiguous;
- owner or decision authority is unknown;
- workspace boundaries cannot be verified;
- ACOS core and project files are mixed;
- evidence access scope is absent;
- a requested action exceeds the Validation Case scope.

This Artifact does not provide the Activation Decision.


## 6. Evidence Boundary

Evidence may enter an activated Matter only after a separate Evidence Intake
authorization.

Required relationship:

```text
External Material
  -> Evidence Artifact
  -> Evidence Review
  -> Fact Candidate
  -> Human Review
  -> Legal Fact, if accepted
```

Core rules:

- `Evidence != Fact`
- source material must retain provenance and location;
- copying must be explicitly authorized;
- evidence access must be least-privilege and matter-scoped;
- conflicting, incomplete, or unverified evidence must remain visible;
- no Evidence Artifact automatically becomes a Fact Candidate;
- no AI-generated Fact Candidate automatically becomes a Legal Fact;
- legal facts require authorized human review.

No Evidence Artifact, Fact Candidate, or Legal Fact is created here.


## 7. Task Boundary

Matter onboarding and activation do not automatically create a task.

Every future task requires:

```text
Capability Mapping
  -> Task Definition
  -> Task Materialization
  -> Scope Validation
  -> Task Ready Decision
  -> Execution
```

A task must identify:

- task ID and Matter reference;
- objective and acceptance criteria;
- executor and reviewer;
- allowed evidence and paths;
- forbidden evidence and paths;
- allowed actions and commands;
- output Artifact;
- human review requirement;
- decision route.

No task may inherit unrestricted access from Matter activation.


## 8. Capability Boundary

Candidate capability categories remain:

- Evidence Analysis
- Corporate Liability Analysis
- Asset Investigation
- Litigation Strategy

These labels do not grant capability. A future task must bind only the minimum
capability required for its objective.

Prohibited implications:

- Evidence Analysis does not grant Evidence import or fact acceptance.
- Corporate Liability Analysis does not grant a legal conclusion.
- Asset Investigation does not grant external search, account access, or data
  acquisition.
- Litigation Strategy does not grant a final strategy Decision.


## 9. Review Boundary

All future AI output remains execution output until reviewed:

```text
AI Output
  -> Execution Receipt
  -> Review Evidence
  -> Human Review
  -> Accepted Output, Rework, or Blocked
```

Review must identify:

- reviewer identity;
- reviewed task and output;
- reviewed evidence references;
- boundary check result;
- findings and limitations;
- required rework;
- separate Decision reference.

AI output must not self-accept.


## 10. Decision Boundary

Material legal judgments and project choices require a separate Decision Record
containing:

- Decision;
- decision authority;
- basis and reasoning trace;
- evidence references;
- known limitations;
- review reference;
- next receiver;
- allowed and forbidden follow-up actions.

No legal or project Decision is issued by this Artifact.


## 11. Required Future Gates

The external project cannot advance from this Boundary Definition directly to
evidence or task execution.

Required sequence:

```text
Boundary Definition
  -> ChatGPT Review
  -> Matter Activation Decision
  -> Matter Activation Record
  -> Evidence Intake or Task Definition Decision
  -> Separately Materialized Evidence or Task Artifact
  -> Execution
```

Each transition requires its own evidence and authority.


## 12. Boundary Validation Criteria

This Definition is valid only if:

- the external project remains unaccessed;
- no Matter identity or workspace is created;
- no evidence is imported or evaluated;
- no fact or legal conclusion is generated;
- no task is created;
- ACOS core remains free of matter content;
- future activation remains separately gated;
- task and Matter lifecycle states remain distinct;
- existing ACOS models are sufficient.


FORBIDDEN:

- Creating or activating a Matter
- Accessing the selected external project or its files
- Importing, reading, copying, or judging evidence
- Creating Fact Candidates, Legal Facts, legal analysis, or litigation strategy
- Creating, materializing, or executing a task
- Creating TASK_064
- Creating or modifying a Governance Model or Evidence Model
- Modifying ACOS architecture, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


NEXT RECEIVER:

ChatGPT Review


REASON:

The Operational Validation Case requires an explicit boundary between ACOS core
governance and any future external Matter before activation, evidence access,
task creation, or legal work can be considered.

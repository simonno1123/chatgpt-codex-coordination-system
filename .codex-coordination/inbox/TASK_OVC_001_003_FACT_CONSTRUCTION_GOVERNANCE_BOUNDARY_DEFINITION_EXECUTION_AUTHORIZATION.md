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
TASK EXECUTION AUTHORIZATION / NON-EXECUTION

SUBJECT:
TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION

TASK ID:
TASK_OVC_001_003

TASK NAME:
Fact Construction Governance Boundary Definition

MATTER ID:
MATTER_OVC_001_LEGAL_EXECUTION_ANALYSIS

SOURCE:
`.codex-coordination/inbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION.md`

SOURCE SHA-256:
`05affa0d5ed6201e9ea370aab7746125badf4a8ea909a4cf4830ce37772765f4`

RELATED AUTHORIZATION:
`.codex-coordination/inbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION_AUTHORIZATION.md`

RELATED AUTHORIZATION SHA-256:
`832ae611098b38dbc9ba1c7689246ef07ef4e254c4bede5e5b5537505d489cc3`

OBJECTIVE:
Authorize TASK_OVC_001_003 to become eligible for one bounded future execution
that defines a Fact Construction Governance boundary without beginning that
execution or creating any Fact Candidate or Legal Fact.

AUTHORITY LIMIT:
This Decision authorizes execution eligibility for TASK_OVC_001_003 only.

It does not authorize execution during this materialization action.

A later execution action may use only the explicitly listed governance inputs
and may create only the explicitly listed Result artifact.

It does not authorize:

- external project or Matter workspace access;
- information or Evidence access;
- Evidence Artifact creation or lifecycle changes;
- Fact Candidate or Legal Fact creation;
- factual chain construction;
- authenticity, relevance, weight, admissibility, sufficiency, or truth
  judgment;
- responsibility or liability determination;
- legal analysis, conclusions, or litigation strategy;
- modification of existing artifacts;
- creation of another task;
- ACOS Core modification;
- cross-project changes;
- Git operations.

OUTPUT:
Task Execution Authorization Decision Record only.


DECISION:

AUTHORIZED


CURRENT STATE:

```text
TASK_READY
```


TARGET STATE:

```text
EXECUTION_AUTHORIZED
```


AUTHORIZED STATE TRANSITION:

```text
TASK_READY
  -> EXECUTION_AUTHORIZED
```


NOT AUTHORIZED:

```text
TASK_READY
  -> TASK_EXECUTING
```

or:

```text
EXECUTION_AUTHORIZED
  -> TASK_EXECUTING
```

Authorization and execution remain separate.


## 1. Execution Scope

One future execution may define the generic governance structure for Fact
Candidate formation and Legal Fact acceptance.

The future Result may define only:

- Fact Candidate identity and traceability fields;
- Evidence reference eligibility requirements;
- formation rules and transformation-path requirements;
- supporting, contradicting, and alternative-explanation requirements;
- confidence and uncertainty limitations;
- Fact Candidate lifecycle states and transition rules;
- human Review and Legal Fact Decision gates;
- dispute, rejection, archival, and fail-closed conditions;
- non-implementation limitations;
- a structured Execution Receipt.

The future Result must not contain or act upon actual Matter information,
Evidence, factual propositions, Fact Candidates, Legal Facts, responsibility
findings, legal conclusions, or strategy.


## 2. Authorized Future Inputs

A separately started execution may read only:

- `docs/capability-model.md`;
- `docs/task-state-machine.md`;
- `docs/execution-boundary-model.md`;
- `docs/execution-receipt-model.md`;
- `docs/review-evidence-model.md`;
- `.codex-coordination/outbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS_MATTER_ACTIVATION_RECORD.md`;
- `.codex-coordination/outbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_RESULT.md`;
- `.codex-coordination/outbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_REVIEW.md`;
- `.codex-coordination/inbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_DECISION.md`;
- `.codex-coordination/inbox/TASK_OVC_001_002_EVIDENCE_INTAKE_BOUNDARY_DEFINITION_CLOSURE_DECISION.md`;
- `.codex-coordination/inbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION.md`;
- `.codex-coordination/inbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION_AUTHORIZATION.md`;
- this Execution Authorization Decision.

No external project, Matter workspace, Evidence, factual, network, provider,
model, API, or search input is authorized.


## 3. Authorized Future Output

The only permitted future output path is:

`.codex-coordination/outbox/TASK_OVC_001_003_FACT_CONSTRUCTION_GOVERNANCE_BOUNDARY_DEFINITION_RESULT.md`

The Artifact type must be:

```text
RESULT
```

That Result must contain:

1. the Fact Construction Governance Boundary Definition; and
2. a structured Execution Receipt section.

This Decision does not create the Result or a separate Receipt artifact.


## 4. Future Execution Receipt Requirements

The structured Execution Receipt section must include:

- `task_id`;
- `executor_identity`;
- `authorization_reference`;
- `execution_scope`;
- `execution_time`;
- `input_reference`;
- `output_reference`;
- `changed_artifacts`;
- `validation_result`;
- `boundary_check`;
- `review_reference`.

Before review, `review_reference` must be marked pending. The Result cannot
approve itself, create a Fact, or transition directly to closure.


## 5. FC-G-001 Boundary

The future Result must preserve:

```text
Evidence
  != Fact Candidate
  != Legal Fact
```

and prohibit:

```text
Fact Candidate
  -> Automatic Legal Fact
```

The Legal Fact path must require:

```text
Fact Candidate
  -> Human Review
  -> Review Evidence
  -> Decision
  -> Legal Fact
```

This Decision authorizes definition of that boundary only. It does not activate
or apply the boundary to an actual proposition.


## 6. Capability Boundary

The future execution may activate only:

```text
file_modify
```

for the single authorized Result path.

It does not activate Evidence access, Fact construction, Legal Fact
acceptance, legal analysis, decision authority, task creation, Git operations,
or any cross-project capability.

`Fact Construction Governance` remains a Matter-workflow boundary label rather
than a new ACOS Core capability.


## 7. Fact Governance Lock

Evidence access remains:

```text
LOCKED
```

Fact Candidate creation remains:

```text
LOCKED
```

Legal Fact creation remains:

```text
LOCKED
```

Legal analysis remains:

```text
LOCKED
```

The future execution defines governance rules only and cannot create or
evaluate an actual factual proposition.


## 8. Execution Start Gate

Current execution status:

```text
NOT STARTED
```

Before execution begins, the executor must:

- verify both bound source hashes;
- verify every authorized governance input exists;
- verify the Result path does not exist;
- verify no external, Matter, Evidence, or factual input is required;
- transition separately from `EXECUTION_AUTHORIZED` to `TASK_EXECUTING`;
- preserve the one-output boundary.


## 9. Fail-Closed Conditions

Execution must remain blocked if:

- either bound source hash changes;
- an authorized governance input is missing or stale;
- any external, Matter, Evidence, or factual input is requested;
- the output path differs;
- the requested output contains or evaluates an actual Fact Candidate or Legal
  Fact;
- Evidence interpretation, factual determination, liability assessment, or
  legal work is requested;
- another task or Artifact is proposed;
- the execution scope is ambiguous or conflicts with this Decision;
- the separate execution-start transition has not occurred.


FORBIDDEN:

- Starting or executing TASK_OVC_001_003 during this materialization action
- Creating the Result or Execution Receipt during this materialization action
- Accessing the external project, Matter workspace, case material, or Evidence
- Creating a Fact Candidate, Legal Fact, responsibility finding, or legal
  conclusion
- Generating legal analysis or litigation strategy
- Creating TASK_OVC_001_004, TASK_064, or any other task
- Creating a separate Execution Receipt Artifact
- Creating or modifying a Governance Model, Evidence Model, or Fact Model
- Modifying existing ACOS artifacts, Core, Runtime, Schema, Validator, or Policy
- Cross-project changes
- Git add, commit, or push


FINAL STATUS:

```text
TASK_OVC_001_003 EXECUTION AUTHORIZED
TASK EXECUTION NOT STARTED
EVIDENCE ACCESS LOCKED
FACT CANDIDATE LOCKED
LEGAL FACT LOCKED
LEGAL ANALYSIS LOCKED
```


NEXT RECEIVER:

ChatGPT Review


REASON:

TASK_OVC_001_003 is eligible for one bounded future governance-only execution
that may create one Result with a structured Execution Receipt. Execution and
all Evidence, Fact Candidate, Legal Fact, and legal operations remain separate,
locked actions.

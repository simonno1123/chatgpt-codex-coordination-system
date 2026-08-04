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
OPERATIONAL CAPABILITY MAPPING DEFINITION

SUBJECT:
OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS

MATTER:
MATTER_OVC_001_LEGAL_EXECUTION_ANALYSIS

OBJECTIVE:
Map the selected Matter's future domain work requirements to the existing ACOS
Capability Model without adding a legal-domain capability to ACOS core.

SOURCE:

- `docs/capability-model.md`
- `.codex-coordination/outbox/OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS_MATTER_ACTIVATION_RECORD.md`

SOURCE HASHES:

- `docs/capability-model.md`:
  `45a6b60605d4940cb04af94de4829eca5adf42029d130a328ea54c8fbc7f8664`
- Matter Activation Record:
  `530b4df4dab3c157d49778f596879f6c8ae944444853ea263ca553a6b3e7a5f8`

AUTHORITY LIMIT:
This Artifact defines a governance mapping for future Matter work only.

It does not authorize:

- creation of a new ACOS capability;
- capability assignment or execution;
- task creation, materialization, or execution;
- external project or workspace access;
- evidence access, import, copying, or judgment;
- fact construction;
- legal analysis, conclusions, or strategy;
- ACOS core modification;
- cross-project changes;
- Git operations.

OUTPUT:
Capability Mapping Definition only.


## 1. Core Mapping Principle

```text
Matter Work Requirement
  -> Existing ACOS Governance Capability
  -> Future Task Scope
```

Not:

```text
Matter Name
  -> New ACOS Core Capability
```

The labels in this Artifact describe future domain workstreams inside one
external Matter. They are not additions to the ACOS Core Capability Model.


## 2. Existing ACOS Capabilities

This mapping uses only the capabilities already defined in
`docs/capability-model.md`:

- `task_define`
- `task_review`
- `decision_issue`
- `authorization_issue`
- `file_modify`
- `git_commit`
- `git_push`
- `advisory_generate`
- `deterministic_check`
- `record_append`

Standing role-capability eligibility does not activate any action:

```text
Standing Capability
  + Valid Task State
  + Task Scope
  + Required Review / Decision / User Gate
  = Eligible Governed Action
```


## 3. Domain Workstream Status

The following four labels are:

```text
MATTER WORKSTREAM REQUIREMENTS
```

They are not:

```text
ACOS CORE CAPABILITIES
```

| Workstream Requirement | Core Status | Current Execution Status |
|---|---|---|
| Evidence Analysis | Not an ACOS Core capability | NOT AUTHORIZED |
| Corporate Liability Analysis | Not an ACOS Core capability | NOT AUTHORIZED |
| Asset Investigation | Not an ACOS Core capability | NOT AUTHORIZED |
| Litigation Strategy Review | Not an ACOS Core capability | NOT AUTHORIZED |


## 4. Mapping: Evidence Analysis

Purpose:

Govern future handling and analysis of explicitly authorized Evidence
Artifacts.

Not included:

- evidence import;
- source authentication;
- fact acceptance;
- legal conclusion;
- unrestricted file access.

Required governance mapping:

| Lifecycle Function | Role | Existing Capability | Condition |
|---|---|---|---|
| Define a bounded evidence-analysis task | `CHATGPT_REVIEW` | `task_define` | Matter and Evidence Intake boundaries are separately authorized. |
| Authorize sensitive access when reserved for the user | `USER_DECISION_SOURCE` | `authorization_issue` | Exact evidence scope and risk are explicit. |
| Produce a scoped analysis Result | `CODEX_EXECUTOR` | `file_modify` | A materialized `TASK_READY` identifies allowed evidence and output paths. |
| Review the Result and evidence boundary | `CHATGPT_REVIEW` | `task_review` | Review Evidence identifies sources, gaps, and conflicts. |
| Issue the governed outcome | `CHATGPT_REVIEW` | `decision_issue` | Decision remains separate from evidence and AI output. |
| Run a configured format or integrity check | `AUTOMATION` | `deterministic_check` | No discretionary evidence judgment. |

Boundary:

```text
Evidence Analysis
  != Evidence Import
  != Fact Acceptance
  != Legal Fact
```


## 5. Mapping: Corporate Liability Analysis

Purpose:

Govern future preparation of a reviewable analysis concerning potential
corporate or controller liability.

Not included:

- automatic liability determination;
- legal fact acceptance;
- final legal opinion;
- litigation claim authorization.

Required governance mapping:

| Lifecycle Function | Role | Existing Capability | Condition |
|---|---|---|---|
| Define the legal-analysis question and evidence boundary | `CHATGPT_REVIEW` | `task_define` | The task names accepted and disputed facts separately. |
| Produce a draft analysis Artifact | `CODEX_EXECUTOR` | `file_modify` | Scope is limited to authorized evidence and stated legal questions. |
| Review reasoning, sources, and uncertainty | `CHATGPT_REVIEW` | `task_review` | Human legal review is mandatory before matter use. |
| Record the governed disposition | `CHATGPT_REVIEW` | `decision_issue` | The Decision does not impersonate client or court authority. |
| Authorize reserved legal-risk direction | `USER_DECISION_SOURCE` | `authorization_issue` | Explicit user scope and risk acceptance are recorded. |

Boundary:

```text
Corporate Liability Analysis
  != Automatic Liability Conclusion
  != Final Legal Decision
```


## 6. Mapping: Asset Investigation

Purpose:

Govern future review of explicitly authorized asset-related information.

Not included:

- external search or provider access;
- account login;
- data acquisition;
- ownership confirmation;
- enforcement action.

Required governance mapping:

| Lifecycle Function | Role | Existing Capability | Condition |
|---|---|---|---|
| Authorize any external access or sensitive-data source | `USER_DECISION_SOURCE` | `authorization_issue` | Provider, source, scope, and handling risk are explicit. |
| Define a bounded investigation task | `CHATGPT_REVIEW` | `task_define` | Exact source and permitted actions are named. |
| Process authorized information into a Result | `CODEX_EXECUTOR` | `file_modify` | No standing external-access capability is implied. |
| Review provenance and ownership uncertainty | `CHATGPT_REVIEW` | `task_review` | Findings distinguish records, inference, and verified ownership. |
| Issue a governed next-step Decision | `CHATGPT_REVIEW` | `decision_issue` | No execution or enforcement authority is inferred. |

Boundary:

```text
Asset Information
  != Verified Ownership
  != Enforcement Authority
```

The current ACOS Capability Model contains no standing capability that grants
external asset investigation. A future task requires separate access authority.


## 7. Mapping: Litigation Strategy Review

Purpose:

Govern review and decision support concerning possible litigation paths.

Not included:

- AI-selected litigation strategy;
- client instruction;
- filing authority;
- legal representation;
- automatic approval.

Required governance mapping:

| Lifecycle Function | Role | Existing Capability | Condition |
|---|---|---|---|
| Define the strategy-review question | `CHATGPT_REVIEW` | `task_define` | Options, evidence, uncertainty, and prohibited actions are explicit. |
| Produce a comparison or draft recommendation | `CODEX_EXECUTOR` | `file_modify` | Output is reviewable analysis, not a Decision. |
| Review the analysis and evidence | `CHATGPT_REVIEW` | `task_review` | Human legal review is mandatory. |
| Issue an ACOS workflow Decision | `CHATGPT_REVIEW` | `decision_issue` | The Decision routes governance only and does not replace client authority. |
| Authorize reserved project direction | `USER_DECISION_SOURCE` | `authorization_issue` | The user's selected scope and risk acceptance are explicit. |
| Provide independent non-binding risk observation | `EXTERNAL_ADVISORY` | `advisory_generate` | Advisory cannot approve, execute, or transition state. |

Boundary:

```text
Litigation Strategy Review
  != AI Decision
  != Client Instruction
  != Filing Authorization
```


## 8. Role And Negative Capability Boundary

### `CODEX_EXECUTOR`

May become eligible to produce a task-scoped Result through `file_modify`.

Must not:

- issue the final Decision;
- define its own task scope;
- infer evidence access;
- accept facts;
- select litigation strategy;
- create a task from this mapping.

### `CHATGPT_REVIEW`

May define and review a future bounded task and issue an ACOS governance
Decision.

Must not:

- impersonate execution evidence;
- claim external evidence was reviewed without access evidence;
- replace authorized human legal judgment.

### `USER_DECISION_SOURCE`

May issue explicit authorization for reserved access, risk, or project
direction.

Human authorization does not rewrite provenance or prove that an action was
performed.

### `EXTERNAL_ADVISORY`

May provide non-binding observations through `advisory_generate`.

Must not:

- access Matter files;
- modify artifacts;
- approve or create tasks;
- issue a final Decision;
- activate capabilities.

### `AUTOMATION`

May run only preconfigured `deterministic_check` or `record_append` actions.

Must not perform legal judgment, review, approval, or state transition.


## 9. Future Task Mapping Gate

No task is created by this Artifact.

A future task may reference one workstream requirement only after:

1. Matter Activation Record review is complete.
2. Required project or evidence access boundary is separately authorized.
3. ChatGPT Review defines exact objective, inputs, outputs, and forbidden
   actions.
4. The task is materialized at an approved path.
5. Scope and receiver are validated.
6. A separate readiness Decision advances the task to `TASK_READY`.


## 10. Mapping Validation Criteria

The mapping passes only if:

- all core capabilities come from `docs/capability-model.md`;
- no matter name appears in an ACOS Core capability identifier;
- domain workstream labels remain Matter-local requirements;
- each workstream has explicit negative boundaries;
- evidence, facts, review, and Decision remain separate;
- human review is required for legal work;
- no capability is activated;
- no external project or evidence is accessed;
- no task is created;
- no ACOS Core file is modified.


FORBIDDEN:

- Creating or adding a legal-domain ACOS Core capability
- Assigning or activating a capability
- Creating, materializing, or executing a TASK
- Accessing the external project, Matter workspace, or evidence
- Generating facts, legal analysis, legal conclusions, or litigation strategy
- Creating TASK_064
- Creating or modifying a Governance Model or Evidence Model
- Modifying ACOS architecture, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


FINAL STATUS:

```text
CAPABILITY MAPPING DEFINED
CORE CAPABILITY MODEL UNCHANGED
CAPABILITIES NOT ACTIVATED
TASK CREATION NOT AUTHORIZED
```


NEXT RECEIVER:

ChatGPT Review


REASON:

The Matter's four future legal-work requirements are mapped to existing ACOS
governance capabilities and negative boundaries without creating domain-specific
Core capabilities or authorizing project access, tasks, or legal work.

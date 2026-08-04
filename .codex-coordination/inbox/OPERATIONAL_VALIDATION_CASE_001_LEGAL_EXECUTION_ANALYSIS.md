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
OPERATIONAL VALIDATION CASE DEFINITION

CASE:
OPERATIONAL_VALIDATION_CASE_001_LEGAL_EXECUTION_ANALYSIS

VALIDATION SUBJECT:
Legal Execution Analysis Project

SELECTED MATTER:
耿长权 / 塑博坊实控人责任分析项目

OBJECTIVE:
Define the first external operational validation case for ACOS without
onboarding, executing, or modifying the selected external matter.

PURPOSE:
Validate whether ACOS Operational Governance can govern the onboarding and
lifecycle design of a complex knowledge-work project.

AUTHORITY LIMIT:
This Artifact defines an operational validation case only.

It does not authorize:

- case or matter analysis;
- legal conclusion generation;
- evidence judgment or fact determination;
- litigation strategy selection;
- task creation;
- matter onboarding or implementation;
- access to external project files;
- cross-project changes;
- modification of ACOS architecture or implementation.

OUTPUT:
Validation Case Definition only.


## 1. Validation Boundary

This Definition evaluates whether the selected matter can be represented within
existing ACOS governance. It does not evaluate the merits of the matter.

```text
Validation Case Definition
  != Matter Onboarding
  != Task Creation
  != Legal Analysis
```

No external evidence, case file, communication, corporate record, transaction
record, court document, or property record is accessed or incorporated by this
Artifact.


## 2. Capability Governance

Validation question:

Can the project objective later be decomposed into explicit, separately
authorized capabilities without treating a role label as permission?

Candidate capability categories for future onboarding review:

- Evidence Analysis
- Corporate Liability Analysis
- Asset Investigation
- Litigation Strategy

These categories are validation subjects only. They are not granted
capabilities, executable tasks, or legal instructions.

Success conditions:

- each required capability is named and bounded;
- capability does not imply runtime, repository, or legal decision authority;
- prohibited actions are explicit;
- human and AI roles remain distinguishable;
- no capability is inferred from access to source material.


## 3. Task Governance

Validation question:

Can future matter work follow the existing lifecycle:

```text
Capability
  -> Task Definition
  -> Task Materialization
  -> Task Ready
  -> Execution
  -> Result
  -> Review
  -> Decision
```

Success conditions:

- no execution begins from an unmaterialized task;
- each task has an explicit receiver, scope, allowed files or evidence, and
  forbidden actions;
- implementation, commit, push, and external delivery remain separately
  authorized where applicable;
- task state cannot advance from an AI assertion alone.


## 4. Evidence Governance

Core rule:

```text
Evidence != Fact
```

Candidate evidence categories for future onboarding review:

- Court Documents
- Corporate Records
- Transaction Records
- Communication Records
- Property Information

Validation questions:

- can each source retain provenance, date, custodian, and scope?
- can source content be distinguished from interpretation?
- can contradictory and incomplete evidence remain visible?
- can access and handling remain limited to separately authorized matter tasks?

This Definition does not inspect, classify, authenticate, or judge any actual
evidence.


## 5. Fact Construction Governance

Core rule:

```text
Evidence
  -> Fact Candidate
  -> Human Review
  -> Legal Fact, if accepted
```

Validation questions:

- can raw material remain separate from a proposed fact?
- can every Fact Candidate reference its supporting and conflicting evidence?
- can uncertainty and missing evidence be preserved?
- can only an authorized human reviewer accept a Legal Fact for matter use?

No Fact Candidate or Legal Fact is created by this Definition.


## 6. Review Governance

Validation question:

Can future AI-generated analysis be treated as reviewable work product rather
than an accepted legal conclusion?

Success conditions:

- AI output is clearly identified as an execution result;
- the reviewer identity and reviewed evidence are recorded;
- findings remain separate from the final Decision;
- incomplete evidence causes a fail-closed route;
- External Advisory remains independent and non-binding.


## 7. Decision Governance

Validation question:

Can material legal-path choices be represented by a separate Decision record
with:

- Decision outcome;
- reasoning trace;
- evidence references;
- known limitations;
- decision authority;
- next receiver?

This Definition does not select a litigation strategy or issue a matter
Decision.


## 8. Operational Validation Questions

1. Can the selected matter be onboarded without embedding legal-domain
   semantics into ACOS core?
2. Can matter-specific capabilities be bounded without changing the existing
   Capability Model?
3. Can evidence remain separate from facts and conclusions?
4. Can task and review gates prevent premature analysis or action?
5. Can human review and decision authority remain explicit?
6. Can project isolation prevent legal files from being placed in the ACOS core
   repository?
7. Can the validation complete without a new Governance Model?


## 9. Success Criteria

The Definition may proceed to a later review only if:

- the case remains an external validation subject;
- no matter file has been accessed or copied;
- no legal analysis or conclusion has been generated;
- no task has been created;
- no ACOS model change is required merely to define the case;
- future onboarding remains separately authorized;
- project isolation remains explicit.


## 10. Required Next Gate

The next permitted step is ChatGPT Review of this Definition.

A later Decision would be required before any:

- matter onboarding;
- evidence inventory;
- capability assignment;
- task materialization;
- legal analysis;
- cross-project action.

No later action is authorized by this Artifact.


FORBIDDEN:

- Creating TASK_064 or any other task
- Accessing or modifying the selected legal project
- Reading, copying, or analyzing matter evidence
- Generating legal facts, conclusions, or litigation strategy
- Creating a new Governance Model or Evidence Model
- Modifying ACOS architecture, Runtime, Schema, Validator, Policy, or Artifact Contract
- Cross-project changes
- Git add, commit, or push


NEXT RECEIVER:

ChatGPT Review


REASON:

ACOS is in Operational Governance mode and requires a bounded external
validation entrypoint before any real project onboarding. This Artifact defines
that entrypoint without performing matter work or expanding ACOS.

# ACOS Review Evidence Model

## 1. Purpose

The ACOS Review Evidence Model defines the structured evidence set used by
ChatGPT Review when evaluating an execution result and issuing a governed
decision.

```text
Review Evidence != Execution Output
Review Evidence != Raw Log
Review Evidence != Decision
```

Review Evidence is a structured, task-bound collection of sources, validation
records, boundary findings, and review findings that supports a Review
Decision.

The model defines evidence organization, lifecycle, and role responsibility. It
does not implement evidence collection, automated review, or decision logic.

## 2. Evidence Relationship Model

The canonical relationship is:

```text
Execution Result
        +
Execution Receipt
        +
Validation Information
        |
        v
Review Evidence
        |
        v
Review
        |
        v
Decision
```

The source artifacts remain distinct:

- Execution Result reports the executor's task outcome.
- Execution Receipt binds one execution attempt to Authorized Scope and Actual
  Change.
- Validation Information records checks, outcomes, limitations, and side
  effects.
- Review Evidence organizes the sources and review findings.
- Review evaluates the evidence.
- Decision records the governed outcome and next receiver.

No earlier artifact automatically creates a later artifact or grants its
authority.

## 3. Review Evidence Definition

Review Evidence is not every available byte, log line, or executor claim. It is
a bounded evidence set whose sources are identified, related to the task, and
assessed for relevance, traceability, completeness, and contradiction.

A valid evidence set answers:

```text
Which task and execution attempt are being reviewed?
Which artifacts and effects were examined?
Which validations were performed?
Did execution remain within the authorized boundary?
Who performed the review?
What findings remain?
Which Decision consumes this evidence?
```

### 3.1 Execution Output

Execution Output is produced by the executor or an execution process. It may
include a `RESULT`, changed files, command output, validation summaries, and an
Execution Receipt.

Execution Output is a source for Review Evidence. It is not independently
accepted merely because execution completed or a command returned success.

### 3.2 Raw Log

A Raw Log is an unstructured or implementation-specific event stream. It may
contain useful observations, but it can be incomplete, noisy, excessive,
misordered, or detached from the task boundary.

A Raw Log becomes a review source only when its provenance, scope, relevance,
and limitations are recorded. It does not become Review Evidence through
volume alone.

### 3.3 Structured Evidence Set

A structured evidence set:

- has a stable evidence-set identity
- is bound to one task and reviewed execution scope
- references its source artifacts
- distinguishes source claims from reviewer findings
- records missing or conflicting information
- identifies the reviewer
- remains separate from the final Decision

Structure improves reviewability. It does not prove authenticity, correctness,
or completeness by itself.

## 4. Evidence Identity And Components

Each evidence set should have an `evidence_set_id` and contain the following
required components.

| Component | Required Meaning |
| --- | --- |
| `task_reference` | The task ID, artifact path, content digest, project, receiver, and reviewed lifecycle state. |
| `execution_receipt_reference` | The receipt ID, execution attempt ID, receipt digest, and receipt lifecycle state. |
| `reviewed_artifacts` | The exact artifacts, changes, outputs, or external effects examined during review. |
| `validation_results` | The validation checks, outcomes, side effects, omissions, and limitations considered. |
| `boundary_check_result` | The reviewed comparison between Authorized Scope and Actual Change. |
| `reviewer_identity` | The governance identity responsible for the review, distinct from the executor and provider label. |
| `findings` | Structured review observations, risks, mismatches, limitations, and required dispositions. |
| `decision_reference` | The intended or actual Decision that consumes the evidence set. |

### 4.1 `task_reference`

`task_reference` should identify:

- `task_id`
- materialized task path
- task content digest
- project
- receiver
- state at execution and review
- applicable authorization or Decision references

If the task digest or project does not match the reviewed execution, the
evidence set cannot claim complete task binding.

### 4.2 `execution_receipt_reference`

`execution_receipt_reference` should identify:

- receipt ID and digest
- execution attempt ID
- receipt producer
- receipt lifecycle state
- boundary-check claim
- known receipt limitations

A missing, invalid, or blocked receipt must be recorded as such. Review Evidence
must not silently represent it as accepted.

### 4.3 `reviewed_artifacts`

`reviewed_artifacts` should provide an exact manifest of the material reviewed,
including as applicable:

- file path or external target
- artifact type
- change type
- before and after digest or identity
- tracked, untracked, generated, or external status
- source reference
- whether content was inspected
- known attribution or completeness limitation

An artifact listed by the executor is not necessarily an artifact verified by
the reviewer. The evidence set must distinguish declaration from observation.

### 4.4 `validation_results`

`validation_results` should identify:

- validation name or command
- purpose
- relevant input scope
- outcome and exit status when applicable
- material output summary
- side effects
- skipped checks and reasons
- environment or dependency limitation

A passing check is evidence about that check only. It does not erase a scope
violation, missing artifact, or contradictory result.

### 4.5 `boundary_check_result`

`boundary_check_result` should include:

- Authorized Scope reference
- Actual Change manifest reference
- File, Action, Command, and Output Boundary outcomes
- `PASS`, `VIOLATION`, or `BLOCKED`
- every identified deviation or uncertainty
- reviewer disposition of the executor's boundary claim

The reviewer must not accept a `PASS` claim solely because the executor declared
it.

### 4.6 `reviewer_identity`

`reviewer_identity` identifies the ChatGPT Review governance identity
responsible for assessing the evidence set.

Provider or model name alone is not sufficient reviewer identity. This
governance field does not implement authenticated runtime identity.

The executor cannot appear as the accepting reviewer of its own output.

### 4.7 `findings`

Each material finding should identify:

- finding ID
- evidence source or sources
- classification or severity
- observation
- governance impact
- required resolution or accepted limitation
- current disposition

Conflicting evidence must be retained and dispositioned. It must not be removed
only to make the evidence set appear consistent.

### 4.8 `decision_reference`

Before a Decision exists, `decision_reference` may identify the intended
Decision route as pending. The later Decision must reference the evidence set
it consumed.

Any reverse association added after Decision must preserve the original
evidence provenance. It must not rewrite source evidence or imply that the
Decision existed earlier.

## 5. Evidence Quality And Completeness

Review Evidence should be evaluated against these qualities:

| Quality | Review Question |
| --- | --- |
| Relevance | Does the source bear directly on the task, boundary, result, or finding? |
| Traceability | Can the source be identified and related to the reviewed execution attempt? |
| Scope | Is the project, path, action, command, and output scope explicit? |
| Completeness | Are required sources and known effects represented? |
| Consistency | Do sources agree, or are contradictions recorded and dispositioned? |
| Freshness | Does the evidence correspond to the current task digest and repository state? |
| Attribution | Is the source producer or observer identified with stated limitations? |
| Reproducibility | Can a stated check be repeated when the task requires it, or is the limitation disclosed? |

No evidence set is presumed complete. Completeness is a reviewed claim with a
defined scope.

### 5.1 Missing Evidence

Missing evidence must be explicit. Examples include:

- unavailable receipt
- unverified changed artifact
- skipped validation
- unknown side effect
- missing authorization reference
- uncertain executor identity
- unavailable external observation

The reviewer must classify whether the omission makes the evidence set
`INCOMPLETE` or the review `BLOCKED`.

### 5.2 Conflicting Evidence

When sources conflict, Review Evidence must preserve:

- each conflicting source
- the nature of the conflict
- confidence and attribution limitations
- attempted verification
- reviewer disposition

Material conflict cannot be resolved by selecting the more convenient source
without rationale.

## 6. Evidence And Decision Separation

Review Evidence provides the basis for judgment. Decision exercises governance
authority.

```text
Evidence provides basis.
Decision provides outcome.
```

The separation is mandatory:

```text
Review Evidence != Decision
Evidence PASS != Automatic Approval
Validation PASS != Task ACCEPTED
Evidence ACCEPTED != Commit Authorized
Evidence ACCEPTED != Push Authorized
```

An evidence set cannot:

- approve itself
- change task state
- authorize rework, commit, push, release, or closure
- infer User Decision
- convert an advisory recommendation into authority

A Decision must identify its outcome, rationale, material findings,
authorization scope, next receiver, and the Review Evidence it consumed.

## 7. Role Boundary

### 7.1 `CHATGPT_REVIEW`

ChatGPT Review holds Review and Decision Authority.

It:

- defines the review scope
- collects and structures the evidence set
- evaluates completeness, consistency, and boundary compliance
- records findings and limitations
- accepts, rejects, or blocks the evidence set
- issues or routes the separate governed Decision

ChatGPT Review must not fabricate executor output, rewrite provenance, or treat
unverified claims as observed facts.

### 7.2 `CODEX_EXECUTOR`

Codex Executor is the Execution Evidence Provider.

It:

- produces `RESULT` or `BLOCKED RESULT`
- provides the Execution Receipt and changed-artifact manifest
- reports validation outcomes and side effects
- discloses uncertainty and scope deviations

It cannot review or accept its own evidence, issue the final Decision, or infer
authority for another operation.

### 7.3 `EXTERNAL_ADVISORY`

External Advisory provides Independent Non-binding Observation.

Its `ADVISORY REVIEW` may be referenced as an additional evidence source when
requested. It cannot:

- create or modify executor evidence
- become the accepting reviewer
- issue the final Decision
- authorize an action
- transition task or evidence state
- route instructions directly to Codex

### 7.4 `AUTOMATION`

Automation may provide separately authorized deterministic validation
information. It cannot perform discretionary review, accept the evidence set,
or issue a Decision.

## 8. Evidence Lifecycle

The canonical lifecycle is:

```text
GENERATED
    |
    v
COLLECTED
    |
    v
REVIEWED
    |
    v
ACCEPTED
```

Exceptional states:

```text
INCOMPLETE
BLOCKED
```

Evidence lifecycle state is distinct from task, receipt, commit, and push
state.

### 8.1 `GENERATED`

The evidence-set record exists and is bound to a task and intended review.
Candidate sources may still be pending.

Generation does not establish completeness, review, or acceptance.

### 8.2 `COLLECTED`

Expected sources have been gathered or their absence has been explicitly
recorded.

Collection does not mean the sources are correct, sufficient, consistent, or
accepted.

### 8.3 `REVIEWED`

ChatGPT Review has assessed source identity, relevance, scope, completeness,
contradictions, boundary compliance, validation, and material findings.

Review must disposition material gaps and advisory findings when advisory
review is required.

### 8.4 `ACCEPTED`

ChatGPT Review has accepted the evidence set as a sufficient basis for issuing
a Decision within the reviewed scope.

```text
Evidence ACCEPTED != Decision ACCEPTED
```

The Decision remains a separate artifact and may produce `ACCEPTED`, `REWORK`,
or `BLOCKED` according to the reviewed evidence and governance rules.

### 8.5 `INCOMPLETE`

The evidence set is `INCOMPLETE` when a required component or material source
is absent but the deficiency can be identified and routed for bounded
completion.

An incomplete evidence set cannot silently advance to acceptance.

### 8.6 `BLOCKED`

The evidence set or review is `BLOCKED` when a safe decision cannot proceed,
for example because:

- task or receipt identity conflicts
- Authorized Scope cannot be established
- material Actual Change is unknown
- source provenance is materially unreliable
- contradictions cannot be dispositioned
- required evidence cannot be obtained within authority

`BLOCKED` preserves the last verified state and routes the issue to ChatGPT
Review or User Decision as appropriate. It does not authorize cleanup, repeat
execution, scope expansion, or another repository operation.

## 9. Review Procedure

ChatGPT Review should:

1. Confirm the task reference, digest, project, receiver, and reviewed state.
2. Confirm the Execution Receipt reference and attempt identity.
3. Inventory reviewed artifacts and execution effects.
4. Evaluate validation results and their limitations.
5. Compare the reviewed boundary result with Authorized Scope and Actual
   Change.
6. Record missing, conflicting, stale, or unverified evidence.
7. Record findings and required dispositions.
8. Determine whether the evidence set is `ACCEPTED`, `INCOMPLETE`, or
   `BLOCKED`.
9. Issue or route a separate Decision that references the evidence set.

Review scope must remain bounded to the task. Review does not grant authority
to inspect or modify unrelated projects or workstreams.

## 10. Relationship To Phase 3 Models

The Execution Boundary Model defines what the executor may do.

The Execution Receipt Model structures what the executor reports about one
authorized attempt.

The Review Evidence Model structures what ChatGPT Review considers when
evaluating the result and receipt.

```text
Execution Boundary
        |
        v
Execution Activity
        |
        v
Execution Receipt
        |
        v
Review Evidence
        |
        v
Review
        |
        v
Decision
```

Each model remains distinct. None substitutes for the others.

## 11. Fail-Closed Handling

Evidence handling fails closed when:

- required references or components are missing
- the evidence set is detached from the task or execution attempt
- source identity or provenance is materially uncertain
- Actual Change cannot be reconciled with Authorized Scope
- validation claims cannot be evaluated
- material contradictions remain unresolved
- an evidence set claims automatic approval

The response is `INCOMPLETE` or `BLOCKED`, followed by an explicit route to
ChatGPT Review or User Decision. No role may infer implementation, commit,
push, release, or closure authority from the failure.

## 12. Non-Implementation Boundary

This model is a governance specification only. It does not implement:

- a Runtime Evidence Collector
- log ingestion or monitoring
- a database or durable evidence store
- automatic evidence collection
- an Automatic Reviewer
- an AI Judge
- an Approval Engine
- automatic task-state transition
- schemas or validators
- an orchestrator
- runtime enforcement
- authenticated reviewer identity
- cryptographic proof or digital signatures

It does not modify runtime behavior, authorize repository actions, access
project instances, or create an automated path from evidence to approval.

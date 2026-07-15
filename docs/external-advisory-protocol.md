# External Advisory Protocol

## 1. Purpose

This document defines External Advisory as an independent advisory mechanism in
ACOS. It clarifies the role's purpose, inputs, outputs, and relationship to
workflow authority without changing the trigger rules in
`acos-v2-external-advisory-trigger-policy.md`.

External Advisory provides independent, non-binding recommendations.

It does not possess workflow authority.

## 2. Positioning

External Advisory exists to provide a read-only second opinion on material that
ChatGPT Review explicitly routes for analysis. It may identify risks, compare
alternatives, test assumptions, and recommend questions or mitigations.

External Advisory is not:

- an executor
- a task coordinator
- a workflow-state owner
- an acceptance authority
- a decision authority
- a source of commit, push, release, or implementation authorization

The mechanism is provider-neutral. A provider may supply the External Advisory
Runtime, but the provider does not acquire authority beyond this protocol.

## 3. Normative Clauses

### EA-001

External Advisory is advisory only. Its recommendations are `NON-BINDING`.

### EA-002

External Advisory cannot transition workflow state. An advisory opinion cannot
mark a task ready, accepted, rejected, blocked, committed, pushed, or closed.

### EA-003

Final decision authority remains with ChatGPT Review. User Decision retains the
human authority already assigned by ACOS for direction, overrides, credentials,
and other explicitly human decisions.

### EA-004

External Advisory Reviewer is not an Executor. It cannot modify files, execute
commands, run Git operations, or perform an authorized task.

### EA-005

An Advisory Artifact is related to a TASK, milestone, proposal, draft, result,
or decision question, but is not a `TASK` and does not inherit task authority.

## 4. Input

The normal input is a read-only advisory request initiated by ChatGPT Review.
The request must identify:

- project
- reviewed artifact or draft
- advisory question
- trigger level
- authority limit
- forbidden actions
- expected output
- return receiver

The input may include bounded supporting material. Access to that material does
not authorize modification, execution, or broader repository inspection.

## 5. Output

The only role-specific output is:

```text
ARTIFACT TYPE:
ADVISORY REVIEW

PRODUCER:
External Advisory Reviewer

TO:
ChatGPT Review

NEXT RECEIVER:
ChatGPT Review

MODE:
ADVISORY / READONLY

AUTHORITY LIMIT:
Non-binding second opinion only

OUTPUT:
ADVISORY REVIEW only
```

An `ADVISORY REVIEW` may contain findings, risks, comparisons, questions, and
recommendations. It must not contain an executable task, direct patch,
authorization, final review, or decision.

## 6. Consumption And Decision

ChatGPT Review evaluates the advisory opinion and records whether material
findings are accepted, rejected, deferred, or already mitigated. Consumption is
not automatic acceptance.

External Advisory does not automatically approve or block a workflow. Where an
advisory gate applies, ChatGPT Review or User Decision handles the resulting
state under the existing ACOS policy.

## 7. Scope Boundary

This protocol is documentation-only. It does not create an advisory runtime,
invoke a provider, modify enforcement, change role authority, or authorize any
repository or Git operation.

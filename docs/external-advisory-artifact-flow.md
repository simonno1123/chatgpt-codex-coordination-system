# External Advisory Artifact Flow

## 1. Purpose

This document defines how External Advisory artifacts move through ACOS. The
flow preserves an independent, `NON-BINDING` second opinion while keeping final
decision authority with ChatGPT Review.

External Advisory provides independent, non-binding recommendations.

It does not possess workflow authority.

## 2. Canonical Flow

```text
ADVISORY REQUEST
        |
        v
EXTERNAL REVIEW
        |
        v
ADVISORY REVIEW
        |
        v
CHATGPT EVALUATION
        |
        v
DECISION
```

The `ADVISORY REQUEST` carries bounded read-only material and a specific
question. `EXTERNAL REVIEW` is the read-only analysis activity, not an ACOS task
execution state. `ADVISORY REVIEW` is the resulting non-binding artifact.

## 3. Request Route

ChatGPT Review initiates the request and defines:

- the target artifact or draft
- the advisory question
- the trigger level
- the read-only scope
- forbidden actions
- the required return route

The request routes to External Advisory Reviewer for analysis only. It is not a
`TASK`, does not authorize execution, and does not change the target task's
status.

## 4. Return Route

The only normal return route is:

```text
External Advisory Reviewer
        -> ADVISORY REVIEW
        -> ChatGPT Review
```

ChatGPT Review must evaluate the opinion before it affects a subsequent review
or decision. The opinion must not route directly to Codex Executor.

## 5. Invalid And Valid Transitions

The following transition is invalid:

```text
ADVISORY REVIEW
        |
        v
TASK APPROVED
```

An advisory artifact cannot approve a task or authorize action.

The valid transition is:

```text
ADVISORY REVIEW
        |
        v
CHATGPT EVALUATION
        |
        v
DECISION
```

Final decision authority remains with ChatGPT Review. User Decision remains the
authority for matters ACOS reserves for explicit human judgment.

## 6. State And Authorization Separation

External Advisory cannot transition workflow state. Creating or receiving an
`ADVISORY REVIEW` does not by itself change a task to `READY`, `ACCEPTED`,
`REWORK`, `BLOCKED`, `COMMITTED`, `PUSHED`, or `CLOSED`.

An advisory finding also does not automatically block a workflow. If existing
policy requires an advisory gate, ChatGPT Review records the gate outcome and
issues the applicable review, decision, deferral, or request for User Decision.

No `ADVISORY REVIEW` can authorize:

- file modification
- command execution
- task execution
- staging or commit
- push or release
- creation of another `TASK`

## 7. Artifact Relationship

An Advisory Artifact may reference a task, milestone, proposal, draft, result,
or decision question. That relationship provides context only.

```text
Advisory Artifact != TASK
Advisory Artifact != REVIEW
Advisory Artifact != DECISION
```

## 8. Scope Boundary

This flow is documentation-only and non-enforcing. It does not implement an
advisory connector, runtime, orchestrator, policy engine, state store, or
automatic workflow transition.

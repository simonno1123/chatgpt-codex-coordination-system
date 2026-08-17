# ACOS W0 Lifecycle, Storage, And Authority Semantics

## Lifecycle Separation

ACOS keeps the following lifecycle families independent:

| Lifecycle | Concern | Non-implication |
|---|---|---|
| Artifact | Creation, validation, preservation, and consumability | A valid artifact does not authorize execution. |
| Task | Definition, materialization, readiness, execution, and result | Task readiness does not grant Git or operational authority. |
| Authorization | Issuance, validity, consumption, expiry, and revocation | Authorization state does not imply task completion. |
| Git | Stage, commit, push, and release | A Git state is not governance acceptance. |
| Activation | Enabling an enforcement capability | Activation does not imply Operational Entry. |
| Operational Entry | Admission into live operational use | Operational Entry requires its own authority and evidence. |

A transition in one family must not silently transition another family.

## Target Task Storage Semantics

The accepted future semantic shape is:

```text
TASK_MATERIALIZED(
    storage_class =
        REPOSITORY |
        MANAGED_CONVERSATION
)
```

```text
MANAGED_CONVERSATION:
TARGET GOVERNANCE SEMANTIC /
NOT CURRENTLY OPERATIONALLY SUFFICIENT FOR CANONICAL TASK_MATERIALIZED
SEMANTICS
```

Any future managed-conversation storage class requires an immutable reference,
content digest, receiver binding, retention guarantee, availability contract,
and recovery procedure.

## Current-Source Tension

Current sources are not fully harmonized:

- `docs/task-state-machine.md` treats physical materialization in managed
  storage, with an exact path or reference and content digest, as part of the
  canonical task-readiness path; and
- `CODEX_WORKFLOW.md` permits `TASK FILE REQUIRED:NO` for conversation-native
  tasks.

```text
W0 DOES NOT RETROACTIVELY RESOLVE THIS CURRENT-SOURCE TENSION BY
REINTERPRETATION.

W0 DOES NOT RETROACTIVELY INVALIDATE OR RECLASSIFY PRE-W0 ACCEPTED TASK
CHAINS.
```

The repository/managed-conversation model above is target governance
semantics. It does not silently amend `CODEX_WORKFLOW.md` or
`docs/task-state-machine.md`. Actual harmonization belongs to a separately
authorized implementation. Ambiguous or unverifiable storage, reference,
digest, or authority conditions must fail closed.

In the target model, repository persistence is mandatory for at minimum:

- mutating tasks;
- high-risk tasks;
- cross-session tasks;
- long-lived tasks;
- regulated tasks; and
- policy-designated tasks.

This target rule is not represented as already uniformly implemented or
enforced.

Storage, reference, or digest uncertainty must `FAIL CLOSED`. Missing storage
evidence must not be inferred from conversation history, declared metadata, or
the existence of a related Git record.

## Authority-Source Boundaries

The following inequalities are normative:

```text
Git history != governance authority
Audit evidence != authorization
Schema validity != authenticated authority
Linter PASS != authenticated authority
Declared PRODUCER != authenticated Producer
Persistence Receipt != Decision Authority
User Decision != provenance rewrite
```

Each item on the left may be relevant evidence, but none independently grants
the authority named on the right.

## Preferred Future Persistence Architecture

```text
authenticated logical Producer
        +
frozen exact content/digest
        +
independent governed Materializer
        +
one-time Persistence Grant
        +
exact-byte Persistence Receipt
        +
append-only Audit
        +
separately authorized Git durability
```

```text
DOCUMENTARY TARGET SEMANTICS ONLY
```

No runtime, writer, grant, receipt service, credential, key, registry, or
authorization broker is created by W0. Current Contract, schema, and linter
files remain unchanged. Versioned Contract/schema compatibility belongs to W1;
runtime identity, evidence services, and persistence runtime belong to W2.

# ACOS W0 Baseline And Canonical Vocabulary

## Status

This document is the documentary semantic baseline for ACOS-MIG-W0.

```text
BASELINE COMMIT:
45709e17c58b94d8f95ae2b881ef887d8728584d

WAVE:
ACOS-MIG-W0

SCOPE:
BASELINE, VOCABULARY, AND IMPORT-RULE FOUNDATION
```

W0 freezes terminology and compatibility meaning only. It does not change an
existing Contract, schema, linter, runtime, authorization mechanism, or
repository record.

## Canonical Vocabulary

| Term | Canonical meaning |
|---|---|
| `Artifact Type` | The declared semantic class of an ACOS artifact. |
| `Producer` | The logical actor attributable as responsible for producing the artifact's content and Artifact Type. |
| `Materializer` | The independently authorized actor or mechanism that writes frozen bytes to approved storage. |
| `Runtime Identity` | The authenticated identity of a concrete runtime instance or session. |
| `Executor` | A runtime authorized to perform a bounded task and return its permitted output type. |
| `Reviewer` | An actor or role attributable as evaluating evidence, a Result, or another governed object within a defined review scope. |
| `Decision Authority` | An authority permitted to determine a governed state or disposition. |
| `Verifier` | An actor or mechanism that checks evidence and reports results without granting authority. |
| `Signer` | The authenticated identity controlling a signing operation and its key boundary. |
| `Authority` | A recognized source entitled to make a specific governed determination. |
| `Capability` | A bounded class of action that a subject could be permitted to perform. |
| `Grant` | A scoped, attributable, time-bounded conveyance of a capability. |
| `Authorization` | The governed permission state or process by which a specific action is determined to be permitted under a valid authority source, applicable Grant, scope, state, and conditions. |
| `Evidence` | Information used to support verification, review, or decision-making. |
| `Receipt` | Evidence that a bounded operation occurred against identified content and conditions. |
| `State` | A value in one named lifecycle family at one point in time. |
| `Lifecycle` | The allowed states and transitions for one governed concern. |
| `NON_CONSUMABLE` | A preserved record that cannot serve as authority, authorization, or a transition prerequisite. |
| `LEGACY` | An artifact or semantic form originating before the current canonical baseline. |
| `IMPORTED` | A preserved artifact admitted through an explicit import process and classification. |
| `Activation` | The separately governed enabling of an enforcement or operational capability. |
| `Operational Entry` | The separately governed admission of ACOS into live operational use. |

## Mandatory Separations

The following inequalities are normative W0 semantics:

```text
Producer != Materializer
Runtime Identity != Provider/Model
Executor != Reviewer
Executor != Decision Authority
Producer attribution != governance authority
Reviewer status != governance authority
Reviewer status != Decision Authority
Authority != Capability
Capability != Grant
Grant != Authorization
Governance Decision != Authorization
Evidence != Authority
Receipt != Authority
Activation != Operational Entry
```

Producer attribution identifies responsibility for artifact content and type;
it does not create a governance role. Producer status alone does not confer
Authority, Review authority, Decision authority, execution authority, or
authorization. An authenticated Producer is a future identity-bound form of
Producer attribution; W0 does not establish authenticated runtime identity.

`Governance Decision != Authorization` is a semantic separation. A Decision
may establish or supply an authority source, but Authorization remains scoped
to the specific permitted action, applicable Grant, state, and conditions.
Authorization does not always require a standalone governance Decision
artifact.

Reviewer attribution identifies responsibility for an evaluation; it does not
self-create a governance role or permission. A governance Reviewer may possess
bounded review authority only where that authority is independently
established. An External Advisory Reviewer may evaluate evidence and produce
non-binding advisory output without possessing governance authority. Reviewer
status alone does not confer execution authority. Reviewer status alone does
not confer state-transition authority. Reviewer status alone does not confer
Decision authority.

These are status and role separations, not permanent actor exclusions. The
same actor may hold different roles at different times where each role is
independently established and appropriately scoped.

```text
ROLE ATTRIBUTION DOES NOT SELF-CONFER AUTHORITY.
```

Declared metadata alone does not establish authenticated identity or
authority. A provider name, model name, path, schema result, linter result,
Git record, or declared role is evidence only unless a separately authorized
mechanism establishes the corresponding identity and authority.

## Compatibility And Preservation

Historical terminology remains preserved through compatibility mapping and is
not rewritten. A compatibility mapping may explain an old term in current
vocabulary, but it must not alter historical bytes, provenance, authority, or
lifecycle state.

The W0 baseline is documentary. Current Contract and schema files, the ACOS
linter, runtime identity, and persistence runtime remain outside W0
implementation. Versioned Contract/schema work belongs to W1. Authenticated
identity, evidence receipts, and persistence runtime work belong to W2.

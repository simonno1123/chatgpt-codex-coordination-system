# ACOS W1 Versioned Contract

STATUS:
W1 SHADOW CONTRACT / NON-DEFAULT / NON-CUTOVER

BASELINE:
f7102e8d62cc6bdf68c53c515599241dda9f84f6

## 1. Scope

This document defines the ACOS-MIG-W1 versioned Contract and schema shadow.
It binds, without redefining, the canonical vocabulary, namespace registry,
historical import taxonomy, and lifecycle/storage/authority boundaries in the
four `docs/acos-w0-*.md` records at the baseline above.

W1 adds a parallel structural profile and fixture-only validator. It does not
change the current workflow, legacy schemas, legacy validator, linter,
runtime, policy selection, or authority model.

## 2. Independent Version Dimensions

- Contract version identifies the semantic ACOS Contract/profile.
- Schema version identifies a concrete machine-schema revision.
- Policy version identifies independently versioned policy content.

```text
CONTRACT VERSION != SCHEMA VERSION != POLICY VERSION
```

The W1 profile uses the literal `2.0` for both `contract_version` and
`schema_version`. Equal values do not make them the same semantic dimension.
`policy_version` is selected and evolved independently.

## 3. Version Handling

| Condition | Outcome |
|---|---|
| Missing contract or schema selector | `BLOCKED` |
| Malformed selector | `BLOCKED` |
| Explicit unsupported selector | `DENY` |
| Mixed recognized version tuple | `DENY` |
| Explicit `2.0` / `2.0` tuple | Continue shadow validation |

Silent fallback is `FORBIDDEN`. Silent downgrade is `FORBIDDEN`. Legacy
auto-dispatch is not part of W1. An unsupported document is never sent to the
legacy validator by the W1 shadow validator.

A tuple in `supported_contract_schema_tuples` is a compatibility declaration
only. It does not prove that the referenced Contract, schema, validator,
runtime, dispatcher, or consumer exists. An unsupported version does not
become acceptable to the W1 shadow validator merely because the tuple appears
in policy metadata. Future native versions require their own versioned
Contract and schema artifacts plus independent authorization; policy metadata
alone does not implement or activate them.

## 4. Legacy Preservation

The following remain immutable legacy/current artifacts in W1:

- `fixtures/schemas/envelope.schema.json`
- `fixtures/schemas/policy.schema.json`
- `scripts/acos-schema-validator.py`
- `fixtures/schema-validation/`

The 2.0 profile is additive and parallel. Compatibility never rewrites
historical bytes, provenance, classification, or authority.

## 5. Shadow State

W1 completion may establish only:

```text
SHADOW AVAILABLE
```

It does not establish `DEFAULT CONSUMPTION`, `CUTOVER`, `ACTIVATION`, or
`OPERATIONAL ENTRY`. Each later state requires an independent decision and
authorization.

## 6. Authority Non-Implication

```text
STRUCTURAL REPRESENTATION != AUTHENTICATED AUTHORITY
Schema validity != authenticated authority
Producer attribution != governance authority
Reviewer status != governance authority
Reviewer status != Decision Authority
Authority != Capability
Capability != Grant
Grant != Authorization
Governance Decision != Authorization
Evidence != Authority
Receipt != Authority
Runtime Identity reference != authenticated runtime
Signature syntax != verified signature
Grant reference != issued or consumed Grant
Authorization reference != valid Authorization
Receipt reference != proof of operation
Lifecycle structure != enacted transition
```

A schema field describing an identity, authority source, Grant,
Authorization, signature, receipt, acknowledgment, revocation, or runtime
identity is data representation only in W1. Schema validation does not
authenticate, issue, consume, verify, persist, acknowledge, revoke, or enact
any represented object.

## 7. Artifact Type Source Reconciliation

Current sources are not fully harmonized:

- `CURRENT WORKFLOW-RECOGNIZED` labels come from current workflow rules.
- `LEGACY MACHINE-SCHEMA-RECOGNIZED` labels come from the 1.0 schema.
- `LINTER / COMPATIBILITY-RECOGNIZED` labels come from current linter and
  compatibility surfaces.

No one existing source defines a complete universal registry. The W1 schema
uses the approved compatibility union only for structural shadow validation.

```text
SCHEMA RECOGNITION != CURRENT WORKFLOW AUTHORIZATION
```

Inclusion of a label in the 2.0 schema does not authorize any role to produce
it and does not amend `CODEX_WORKFLOW.md`, `SCOPE_POLICY.md`, or the linter.

## 8. Structural Boundaries

Typed scopes are descriptions, not permissions. Multi-parent lineage is a
claimed relationship, not authenticated provenance. `MANAGED_CONVERSATION`
is a target storage semantic; schema acceptance does not establish its
reference, retention, availability, or recovery infrastructure.

`payload` is an extensible data container only. Payload content is
non-governing. It cannot override, redefine, supersede, shadow, or otherwise
change governed top-level envelope semantics, including version selectors,
routing, lifecycle, storage, scope, or authority boundaries.

Historical import classes are exactly those defined by W0. In particular,
`NON_CONSUMABLE` remains prohibited as authority input even when structurally
valid.

## 9. Migration States

1. `SHADOW AVAILABLE`: isolated schemas, fixtures, validator, and tests exist.
2. `DEFAULT CONSUMPTION`: separately authorized consumers select the profile.
3. `CUTOVER`: separately authorized compatibility policy changes the active
   contract path.

No state implies the next. W1 implements only the first state.

# ACOS W0 Namespace Registry

## Purpose

This registry establishes canonical, non-conflicting names for W0 planning.
Registration provides semantic identity only. Namespace registration does not
itself grant authority, execution permission, or lifecycle status.

## Program Namespaces

| Canonical namespace | Meaning |
|---|---|
| `ACOS-IPS-*` | Implementation Planning Study |
| `ACOS-MIG-*` | Migration Program / Migration Waves |
| `ACOS-OER-*` | Observer-to-Enforcement Rollout |
| `ACOS-OPE-*` | Operational Entry governance/readiness |

The canonical short namespace keys are `ACOS-IPS`, `ACOS-MIG`, `ACOS-OER`,
and `ACOS-OPE`.

Bare "Phase N" is non-canonical where ambiguity can arise. A phase reference
must be qualified by its registered program namespace or by an unambiguous
artifact identifier.

## Lifecycle Namespace Families

| Canonical family | Governed concern |
|---|---|
| `ARTIFACT.*` | Artifact creation, validation, preservation, and consumability |
| `TASK.*` | Task definition, materialization, readiness, execution, and result |
| `AUTHORIZATION.*` | Authorization issuance, validity, consumption, expiry, and revocation |
| `GIT.*` | Stage, commit, push, release, and related repository states |
| `ACTIVATION.*` | Enforcement activation states |
| `OPERATIONAL_ENTRY.*` | Operational readiness and entry states |

State values in different families do not imply one another. For example,
`GIT.COMMITTED` does not imply `AUTHORIZATION.VALID`, and
`ACTIVATION.ENABLED` does not imply `OPERATIONAL_ENTRY.ENTERED`.

## Registration Rules

1. Each canonical namespace key has exactly one meaning.
2. Two meanings must not share one canonical namespace key.
3. New aliases must not silently become canonical identifiers.
4. Namespace uniqueness is a semantic requirement.
5. Existing historical identifiers are not renamed.
6. Historical aliases may be mapped for interpretation without changing their
   original bytes, identifiers, provenance, or authority.

This registry is documentary W0 semantics. It does not modify the current
Contract, schema, linter, runtime registry, or lifecycle engine.


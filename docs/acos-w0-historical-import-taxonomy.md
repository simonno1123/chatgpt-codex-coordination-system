# ACOS W0 Historical Import Taxonomy

## Status And Boundary

```text
DEFINES FUTURE CLASSIFICATION SEMANTICS ONLY

DOES NOT OPERATIONALLY RECLASSIFY EXISTING REPOSITORY ARTIFACTS.
```

Classification preserves historical evidence while separating evidentiary
value from current governance authority.

```text
EVIDENTIARY USABILITY
!=
AUTHORITY CONSUMABILITY
```

## Canonical Classes

The following table is the complete W0 classification set.

| Canonical class | Evidentiary usability | Authority consumability | Lineage behavior | Migration behavior | Historical byte preservation | Supersession semantics |
|---|---|---|---|---|---|---|
| `VALID_NATIVE` | Usable as native evidence | Consumable only under independently valid authority rules | Native lineage retained | Remains native under compatible versions | Required | Replaced only by explicit governed supersession |
| `VALID_LEGACY` | Usable as legacy evidence | Consumable only where an explicit compatibility rule permits it | Original lineage retained | Imported without upgrading authority | Required | A successor may supersede use, never history |
| `REPRODUCED_EVIDENCE` | Usable as newly reproduced evidence | Not authority by reproduction alone | Links new evidence to the historical source | Stored as a distinct current record | Required for both records | May supersede evidentiary conclusions, not provenance |
| `NON_CONSUMABLE` | Preserved and inspectable as evidence | Prohibited as authorization input, execution authority, state-transition authority, or Decision authority | Lineage remains visible | Retained for audit; rejected by authority consumers | Required | A valid replacement may supersede reliance, not erase the record |
| `UNTRUSTED_IMPORT` | Usable only as untrusted contextual evidence | Not consumable | Source and import event remain explicit | Quarantined until independently classified | Required | Later classification is additive and attributable |
| `SUPERSEDED` | Usable as historical evidence | Not consumable for actions governed by its successor | Links to the superseding record | Preserved outside the active path | Required | Supersession is explicit and non-destructive |
| `REVOKED` | Usable as evidence of prior state and revocation | Not consumable after effective revocation | Revocation event and target remain linked | Preserved with revocation status | Required | Revocation does not rewrite prior existence |
| `EXPIRED` | Usable as historical evidence | Not consumable after expiry | Expiry remains attributable to the original record | Preserved with temporal status | Required | A replacement requires separate authority |
| `PROVENANCE_EXCEPTION` | Usable only with the stated provenance limitation | Not consumable unless a future explicit policy permits the exact exception | Missing or conflicting provenance is retained | Isolated for review; no implicit normalization | Required | Replacement does not repair history retroactively |

## Mandatory Preservation Rules

The import and classification process permits:

- preserving exact bytes and digests;
- adding attributable classification evidence;
- linking a replacement or reproduced record; and
- refusing authority consumption when provenance is incomplete.

It prohibits:

- retroactive signing;
- retroactive authentication;
- silent authority upgrade;
- provenance rewriting;
- historical byte rewriting; and
- deletion-based repair.

No classification label is itself a grant, authorization, acceptance,
Activation, or Operational Entry decision. Current repository artifacts retain
their existing status until a separately authorized process classifies them.


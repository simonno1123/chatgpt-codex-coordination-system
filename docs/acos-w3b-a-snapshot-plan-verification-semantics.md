# ACOS W3B-A Snapshot And Plan Verification Semantics

STATUS:
READ-ONLY SNAPSHOT ANALYSIS / DECLARATIVE PLAN VERIFICATION

## 1. Acquisition Boundary

W3B-A operates on a caller-supplied frozen snapshot only. A secure acquisition
observation binds the confined path observation, device/inode observation,
exact-byte SHA-256 digest, byte size, and pre/post inspection fingerprint.
These are physical observations, not authenticated logical identity.

One source descriptor remains open for the entire inspection. Its exact bytes
are hashed and copied into a private transient image; SQLite opens only that
image. The same source descriptor is re-read after inspection, and the original
pathname binding is checked for persistent replacement. Any source descriptor,
private image, path, inode, size, timestamp, or digest change is `BLOCKED`.

The transient image carries exact bytes for inspection only. It is not a repair
copy, dry-run target, restore image, durable snapshot, or source of authority.

## 2. SQLite Boundary

The snapshot URI is opened with `mode=ro&immutable=1`. The connection enables
query-only behavior, disables extension loading, disables trusted schema where
supported, applies a bounded progress handler, and uses an authorizer to deny
write-capable operations.

No W3B-A operation executes transaction mutation, schema creation, schema
repair, `ATTACH`, `DETACH`, `VACUUM`, `REINDEX`, data mutation, restore, or
reconciliation.

## 3. Inspection Invariants

Inspection compares the supplied snapshot against the frozen W3A 1.0 model:

- canonical SQL digest;
- SQLite `user_version` 100;
- exact W3A metadata values;
- required tables, indexes, and append-only triggers;
- bounded SQLite integrity result;
- bounded audit-chain consistency using W3A `GENESIS` and hash semantics;
- observable state/event consistency;
- absence of unexpected non-internal schema objects.

An invariant match is evidence only. It is not proof of authenticity,
freshness, authority, or fitness for production.

## 4. Source-Of-Truth Boundary

W3B-A does not encode a winner among current state, event history, audit
history, timestamps, W2 evidence, repository evidence, or governance artifacts.
When deterministic invariants do not resolve a conflict, the classification is
`MANUAL_DECISION_REQUIRED` or `AMBIGUOUS_FAIL_CLOSED`.

## 5. Evidence Digest

Repair evidence contains bounded findings derived from trusted invariant code.
The evidence-set digest is SHA-256 over canonical JSON excluding the digest
field itself. Raw store-controlled payload never becomes a proposed action.
Unexpected schema names, unexpected metadata keys, and authorization IDs are
represented by bounded opaque digests before they may become plan subjects.
Canonical expected names may remain readable.

## 6. Plan Digest

The plan digest is SHA-256 over canonical JSON excluding `plan_digest`.
Declarative proposed differences use a closed vocabulary:

```text
DECLARE_CANONICAL_INDEX_GAP
REQUEST_MANUAL_DECISION
PRESERVE_AND_BLOCK
REPORT_AMBIGUITY
```

These labels describe evidence handling; none is executable.

## 7. Verification Boundary

Plan verification validates four independent bindings:

```text
plan -> snapshot digest and size
plan -> evidence-set digest
plan -> observed store version
plan -> canonical plan digest
```

It also rejects unknown actions, executable directive content, destructive
proposals, authority-bearing taint, execution eligibility, and mutation effect.

```text
PLAN_VERIFY = DECLARATIVE INVARIANT CHECK
PLAN_VERIFY != DRY-RUN APPLY
```

## 8. Terminal State

Successful static verification emits `PLAN_VERIFIED` while preserving
`SHADOW_ONLY`, `EXECUTION_INELIGIBLE`, `AUTHORITY_NONE`, and `MUTATION_NONE`.
There is no successor state in W3B-A.

```text
PLAN_VERIFIED != AUTHORIZED
PLAN_VERIFIED != APPLY
PLAN_VERIFIED != REPAIRED
```

## 9. Failure Semantics

- `PASS`: bounded read-only inspection, plan generation, or static verification completed.
- `DENY`: a supplied declarative claim is contradicted or violates the closed model.
- `BLOCKED`: evidence, safe path topology, resource bounds, SQLite readability, or deterministic inspection is unavailable.

All outcomes preserve the complete non-authority and non-mutation taint.
JSON input is walked iteratively for depth, cardinality, and text limits before
canonical serialization. Parser recursion and CLI input-loading exceptions are
also contained by the machine-readable `BLOCKED` boundary.

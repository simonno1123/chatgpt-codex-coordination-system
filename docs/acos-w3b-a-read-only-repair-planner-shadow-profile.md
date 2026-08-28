# ACOS W3B-A Read-Only Repair Planner Shadow Profile

STATUS:
W3B-A SHADOW / NON-PRODUCTION / READ-ONLY / NON-AUTHORIZING / NON-MUTATING / NON-ACTIVATING

BASELINE:
13ad7b433daea52d3ffde8c5de93b4d82e89b0fc

CONTRACT BINDING:
ACOS Contract 2.0

W3A AUXILIARY AND STATE-STORE FAMILY:
1.0

CANONICAL W3A STATE-STORE SQL SHA-256:
a9efb6b932eb2a45e9be2cb89c364ef02c20ac2de96771f38b3aecff4244c60d

## 1. Architectural Identity

W3B-A inspects an already supplied frozen W3A SQLite snapshot and produces
bounded repair evidence, declarative plans, and static plan-verification
results. It is not a Repair Executor, Repair Authorization Broker, Restore
Engine, Reconciliation Engine, Migration Engine, or Governance Authority.

```text
Repair Inspection != Repair Authorization
Repair Plan != Repair Grant
Plan Verification != Permission To Execute
PLAN_VERIFIED != EXECUTION_READY
Deterministic Plan != Authorized Mutation
Plan Persistence != Plan Authority
```

The lifecycle terminates at `PLAN_VERIFIED`. There is no transition from that
state to `AUTHORIZATION_VALIDATED`, `AUTHORIZED`, `APPLY`, `EXECUTING`,
`REPAIRED`, `RESTORED`, `RECONCILED`, or `ACCEPTED`.

## 2. Exact Operation Vocabulary

```text
shadow_snapshot_inspect
shadow_repair_inspect
shadow_repair_plan
shadow_repair_plan_verify
```

No apply, execute, restore, reconcile, authorize, or accept operation exists.

## 3. Snapshot-Only Input

W3B-A accepts only an explicitly supplied `--snapshot-path` confined beneath
an explicit permitted root. It never acquires or opens an original/live store
as its operating input. WAL checkpointing, backup orchestration, source-store
acquisition, and live-store repair are outside W3B-A.

A supplied snapshot does not establish freshness, authenticity, logical store
identity, governance authority, or permission to mutate anything.

```text
path != stable identity
inode != stable identity
digest != logical identity
```

`logical_store_claim` remains an unauthenticated claim.

## 4. Snapshot Safety

Before SQLite parsing W3B-A requires a regular non-symlink file, rejects parent
traversal and symlink-parent escape, confines the resolved path to an explicit
root, and opens one read-only source descriptor. That descriptor remains open
for the complete inspection lifetime. Exact bytes are bounded and hashed while
being copied into a private transient inspection image. SQLite reads only that
image and never reopens the caller-supplied snapshot pathname. After inspection,
the same source descriptor is re-read and the original pathname binding is
checked for persistent replacement.

The private image is an exact-byte inspection carrier only. It is not a repair
copy, dry-run repair target, restore target, reconciliation target, or durable
artifact. An `A -> B -> A` pathname replacement cannot make SQLite inspect `B`
while evidence remains bound to the digest of `A`.

SQLite is opened using read-only immutable URI semantics. The connection uses
`query_only`, disables extension loading, disables trusted schema where
supported, installs a bounded VM progress handler, and denies write-capable
authorizer actions including data mutation, schema mutation, transaction
mutation, `ATTACH`, `DETACH`, and reindex operations.

W3B-A performs no schema initialization, no writable open, no WAL-producing
operation, and no temporary database mutation for plan verification.

## 5. Resource Bounds

Snapshot bytes, JSON bytes, JSON depth, collection cardinality, schema objects,
rows inspected, extracted text/blob size, and SQLite VM steps have fixed hard
ceilings. JSON structure is checked with an iterative bounded walk before
canonical serialization. JSON parser recursion and CLI input-loading failures
are converted to machine-readable `BLOCKED`. User input cannot raise those
ceilings.

## 6. Classification

Only these classifications are emitted:

```text
DETERMINISTIC_PLAN_CANDIDATE
MANUAL_DECISION_REQUIRED
NON_REPAIRABLE_PRESERVE_AND_BLOCK
AMBIGUOUS_FAIL_CLOSED
```

`AUTHORIZED_LOCAL_MUTATION_CANDIDATE` is not part of W3B-A.

```text
insufficient evidence -> AMBIGUOUS_FAIL_CLOSED
```

No table, event stream, audit stream, timestamp, or current-state row is a
universal source of truth. Technical consistency is not governance truth.

## 7. Declarative Plan Boundary

A repair plan contains symbolic, invariant-oriented differences only. It
contains no executable SQL, shell command, Python code, callable mutation
directive, restore instruction, or reconciliation instruction. Store-controlled
payload is evidence only and cannot select plan behavior.

Store-derived unexpected metadata keys, unexpected schema names, and
authorization identifiers may enter evidence identity only as opaque SHA-256
references. Canonical expected object names may remain readable.

Plan semantics derive exclusively from canonical implementation invariants.
Every plan binds its identifier, logical store claim, snapshot digest and size,
observed version, anomaly classifications, evidence-set digest, declarative
proposed differences, expected invariants, creation time, and plan digest.

Every generated or verified plan remains:

```text
SHADOW_ONLY
EXECUTION_INELIGIBLE
AUTHORITY_NONE
MUTATION_NONE
```

## 8. Static Plan Verification

`shadow_repair_plan_verify` checks schemas, canonical digests, snapshot and
evidence binding, classification and proposed-difference vocabulary, healthy
key protection, destructive-proposal exclusion, expected invariants, and the
complete non-authority taint.

```text
PLAN_VERIFY = DECLARATIVE INVARIANT CHECK
PLAN_VERIFY != DRY-RUN APPLY
```

## 9. Audit Corruption

Audit inconsistency may be inspected and preserved as evidence. It may produce
`MANUAL_DECISION_REQUIRED` or `NON_REPAIRABLE_PRESERVE_AND_BLOCK`. W3B-A never
rewrites hashes, creates a replacement chain, creates a recovery epoch, accepts
a new genesis, or repairs provenance.

Audit verification uses the frozen W3A hash semantics exactly, including
`previous_hash = "GENESIS"` for the first event.

```text
Corrupted Audit Chain cannot bootstrap trust for its own repair.
```

## 10. Result Taint

Every `PASS`, `DENY`, and `BLOCKED` result contains:

```text
governance_status = UNAUTHENTICATED_SHADOW
authority_effect = NONE
identity_effect = NONE
execution_effect = NONE
activation_effect = NONE
eligible_for_execution = false
plan_effect = NONE
mutation_effect = NONE
```

## 11. Exclusions

W3B-A creates no repair authorization, attempt, receipt, epoch, restore plan,
or reconciliation result. It changes no W3A/W2/W1/W0 source, Contract, schema,
state-store SQL, trust anchor, Governance Root, default-consumption policy,
Activation state, or Operational Entry state.

```text
W3B-B: NOT AUTHORIZED
W3B-C: NOT AUTHORIZED
Default Consumption: NOT AUTHORIZED
Activation: LOCKED
Operational Entry: LOCKED
```

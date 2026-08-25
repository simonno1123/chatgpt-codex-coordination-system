# ACOS W3A State And Transaction Semantics

STATUS:
W3A SHADOW TRANSACTION MODEL / NON-AUTHORIZING

## 1. Store Model

The W3A SQLite store contains these logical structures:

```text
store_metadata
grant_observations
authorization_state
authorization_events
workflow_state_events
audit_events
```

`store_metadata` binds the state-store family to version `1.0` and the ACOS
Contract to `2.0`. No compatibility fallback or Contract 2.1 dispatch exists.

`grant_observations` stores supplied Grant claims and observed state.
`authorization_state` stores the current observer state and optimistic version.
The remaining event tables are append-only evidence, not governance authority.

A new database path may execute the canonical W3A state-store schema and must
then pass verification. An existing database is never initialized before
verification and is not repaired by W3A.

```text
NEW STORE -> INITIALIZE -> VERIFY
EXISTING STORE -> VERIFY WITHOUT REPAIR
W3A Detection != W3B Repair
```

## 2. Connection Invariants

Every connection sets and reads back:

```text
PRAGMA journal_mode = WAL
PRAGMA synchronous = FULL
PRAGMA foreign_keys = ON
PRAGMA busy_timeout >= 5000
```

An ineffective setting is BLOCKED. W3A never downgrades synchronous durability
to NORMAL.

Connection hardening is distinct from schema or state repair. Existing-store
verification does not set `user_version`, insert metadata, or create a missing
table, index, or trigger.

## 3. Transaction Invariant

Every mutation begins with `BEGIN IMMEDIATE`. The transaction then re-reads
state and replay bindings before changing anything. Lock or timeout failures
are BLOCKED. State or optimistic-version conflicts are DENY.

Reservation uses a conditional transition from `OBSERVED` to `RESERVED`.
Consumption uses:

```sql
UPDATE authorization_state
SET current_observer_state = 'CONSUMED',
    version = version + 1,
    updated_at = ?
WHERE authorization_id = ?
  AND current_observer_state = 'RESERVED'
  AND version = ?;
```

Success requires `affected_rows == 1`. W3A does not retry a zero-row conflict
into a later success.

A known state, optimistic-version, or replay-binding conflict is DENY. A
generic SQLite integrity or infrastructure failure is BLOCKED. Busy and lock
timeout remain `BLOCKED / SQLITE_BUSY`. These classifications do not grant
authority.

Every public observer operation converts ordinary bounded failures to a
machine-readable `PASS`, `DENY`, or `BLOCKED` result carrying the complete
non-authority taint. Unexpected ordinary exceptions become
`BLOCKED / UNEXPECTED_OPERATION_ERROR`; they do not escape as authorization
outcomes.

## 4. Replay And Uniqueness

The store freezes both constraints:

```text
UNIQUE(authorization_id, operation_id)
UNIQUE(authorization_id, nonce)
```

The full idempotency identity is:

```text
authorization_id
operation_id
nonce
canonical_request_digest
```

An exact already-committed replay is `PASS / IDEMPOTENT_REPLAY` and creates no
second state, event, or audit effect. Reuse of the same authorization and
operation with a changed nonce or digest is DENY. Reuse of the same
authorization and nonce with a changed operation or digest is DENY. A nonce
may occur under a different authorization in W3A shadow scope.

## 5. Atomic Event And Audit Boundary

Reservation and consumption write the conditional state mutation, one
authorization event, and one audit event before one COMMIT. Workflow
observation writes one workflow event and one audit event in the same
transaction. Grant observation follows the same evidence-plus-audit rule.

Any failure before COMMIT rolls back every write in that operation.

## 6. Audit Hash Input

Audit sequence is monotonically increasing. The deterministic hash input is
the previous event hash plus sequence, event type, aggregate type, aggregate
identifier, payload digest, and supplied observation timestamp. Canonical JSON
uses sorted keys and compact separators.

The chain is verified on reopen. It is local consistency evidence only:

```text
Hash Chain != Signature
Hash Chain != Authenticated Producer
Hash Chain != Nonrepudiation
Hash Chain != Trust Anchor
Hash Chain != Host-Compromise Resistance
```

## 7. Restart And Failure Boundary

A clean reopen retains observer state, versions, replay bindings, events, and
audit evidence. Rollback leaves a valid reopenable store. Reopen verifies
`PRAGMA user_version == 100`, exact metadata, required canonical schema
objects, SQLite integrity, and the audit chain without first running schema
initialization. Unsupported version, missing object, SQLite integrity failure,
or audit inconsistency is BLOCKED and is not repaired by W3A.

Detection belongs to W3A. Detection is not repair. Repair and reconciliation
remain deferred to W3B.

## 8. Authority Boundary

```text
BEGIN IMMEDIATE != Authorization
RESERVED != Permission To Execute
CONSUMED != Execution Authorized
PASS != Governance Transition
Durable State != Governance Authority
```

All operation results retain no authority, identity, execution, or activation
effect and remain ineligible for execution.

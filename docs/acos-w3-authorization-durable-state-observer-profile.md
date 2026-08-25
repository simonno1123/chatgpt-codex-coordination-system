# ACOS W3A Authorization Durable-State Observer Profile

STATUS:
W3A SHADOW / NON-PRODUCTION / OBSERVER-ONLY / NON-AUTHORIZING / NON-ACTIVATING

BASELINE:
052490239bb6030f7fee1f963ef80e7aca48ab58

CONTRACT BINDING:
ACOS Contract 2.0

W3 AUXILIARY SCHEMA FAMILY:
1.0

W3 STATE-STORE SCHEMA:
1.0

```text
W3 auxiliary version 1.0
!=
ACOS Contract version 2.0

W3 state-store version 1.0
!=
ACOS Contract version 2.0
```

W3A does not create or imply Contract 2.1 and does not modify W0, W1, or W2.

## 1. Architectural Identity

W3A is a local durable-state observation kernel for Grant claims, shadow
authorization state, reservation and one-time consumption observations,
workflow-state observations, and append-only audit evidence.

```text
W3A Migration Shadow Kernel
!=
OER Phase 3 Operational Durable-State Entry
```

W3A is not an Authorization Broker. It does not issue permission, route an
executor, enforce policy, enact governance transitions, or establish an
authenticated Runtime Identity, Trust Anchor, Governance Root, Activation, or
Operational Entry.

## 2. State Separation

Claimed governance state is supplied evidence. Durable observer state is a
local record of what W3A observed or recorded. Neither is operational authority.

Claimed Grant lifecycle vocabulary may include `DEFINED`, `ISSUED`,
`VALIDATED`, `ACTIVE`, `CONSUMED`, `DENIED`, `REVOKED`, `EXPIRED`,
`SUPERSEDED`, and `FAILED`. In particular, claimed `ACTIVE` is not execution
authority.

Durable observer state is bounded to `OBSERVED`, `RESERVED`, `CONSUMED`,
`REVOKED`, `EXPIRED`, `SUPERSEDED`, and `CONFLICTED`.

```text
Governance State != Stored Runtime State
Observed Authorization != Authorization
Reservation Success != Permission To Execute
Consumption Recorded != Execution Authorized
Durable State != Governance Authority
```

## 3. Observer Operations

The only operation vocabulary is:

```text
shadow_observe
shadow_reserve
shadow_consume
```

No operation result grants authority. Every machine-readable result preserves:

```text
governance_status = UNAUTHENTICATED_SHADOW
authority_effect = NONE
identity_effect = NONE
execution_effect = NONE
activation_effect = NONE
eligible_for_execution = false
```

PASS means only that the bounded observer operation completed. PASS does not
mean Authorization valid, execution permitted, task approved, governance
transition enacted, Activation permitted, or Operational Entry permitted.

Every public observer operation has a total machine-readable boundary for
ordinary bounded failures. `shadow_observe`, `shadow_reserve`, and
`shadow_consume` return a tainted `PASS`, `DENY`, or `BLOCKED` result rather
than leaking an ordinary operation exception. `KeyboardInterrupt` and
`SystemExit` are not converted into successful observer results.

## 4. W2 Taint Consumption

A W2 result may be observed only when the complete W2 shadow boundary is
present. Naked PASS or missing taint is BLOCKED. A non-`NONE` authority,
execution, or activation effect, or `eligible_for_execution=true`, is DENY.

```text
W2 PASS != W3 Authorization
```

W3A does not repair, authenticate, or upgrade W2 evidence.

## 5. Durable Store

W3A uses an explicitly selected local SQLite database. Every connection must
set and verify WAL journal mode, FULL synchronous durability, foreign keys ON,
and a busy timeout of at least 5000 milliseconds. Failure is BLOCKED.

A genuinely new state path may initialize the unchanged canonical W3A schema
and must then pass the same bounded verification used for reopening. An
existing store is verified without running schema initialization first. W3A
must not overwrite `user_version`, recreate missing metadata, tables, indexes,
or append-only triggers, or otherwise repair an existing store before deciding
PASS or BLOCKED.

```text
NEW STORE -> INITIALIZE -> VERIFY
EXISTING STORE -> VERIFY WITHOUT REPAIR
W3A Detection != W3B Repair
```

The state path and permitted root are explicit. Parent traversal, an outside
path, a symlink target, a symlink-parent escape, and unresolved or unsafe path
topology are rejected. The database is restricted to mode `0600` where the
platform supports POSIX modes. These controls reduce local accident and
misconfiguration risk; they do not resist host compromise, root, or a
malicious local administrator.

## 6. Reservation And Consumption

State-changing operations use `BEGIN IMMEDIATE`. This is necessary for local
serialization but is not proof of one-time consumption.

Reservation and consumption additionally require a conditional state change,
an optimistic version predicate, and exactly one affected row. Zero affected
rows due to state or version drift is DENY. SQLite busy or lock timeout is
BLOCKED and is never treated as an authorization denial or success.

A positively identified state, version, or replay-binding conflict is DENY.
A generic SQLite integrity or infrastructure failure is BLOCKED. Infrastructure
failure does not become an authorization or state denial merely because SQLite
reported an integrity exception.

Idempotency binds `authorization_id`, `operation_id`, `nonce`, and
`canonical_request_digest`. Exact replay returns `PASS / IDEMPOTENT_REPLAY`
with no second state effect. Conflicting operation or nonce reuse under one
authorization is DENY. The same nonce under a different authorization remains
permitted within this shadow scope.

## 7. Atomic Evidence

Each state-changing observer operation commits its state mutation,
authorization or workflow event, and audit event in one SQLite transaction.
Audit insertion failure rolls the entire transaction back.

```text
State Commit without Audit Commit is forbidden.
```

Authorization, workflow, and audit events are append-only in the W3A model.

## 8. Audit Chain

Audit events use a deterministic SHA-256 chain for local consistency and
tamper indication only.

```text
Hash Chain != Signature
Hash Chain != Authenticated Producer
Hash Chain != Nonrepudiation
Hash Chain != Trust Anchor
Hash Chain != Host-Compromise Resistance
```

An actor able to rewrite the database may rewrite records and recompute the
chain. W3A makes no stronger claim.

## 9. Workflow Observation

W3A may record an allowed supplied lifecycle edge and may DENY an invalid
supplied edge. It does not own or enact the lifecycle transition.

```text
workflow_state_event observed
!=
governance state transition enacted
```

ChatGPT Review remains the Review and Decision authority under existing ACOS
governance sources.

## 10. Restart And W3B Boundary

On reopen W3A verifies SQLite `user_version`, exact store metadata, required
tables, indexes, and append-only triggers, bounded SQLite integrity, and the
audit chain. Verification occurs without schema initialization or repair.
Reservation and consumption evidence persists across a clean restart.
Unsupported version, missing canonical object, detectable corruption, or audit
inconsistency is BLOCKED and remains unmodified by W3A.

W3A detects; it does not repair. Detection is not repair. Automatic repair, reconstruction, conflict
repair, backup/restore orchestration, authoritative reconciliation,
distributed recovery, and cross-node recovery are deferred to W3B.

## 11. Crypto And Operational Exclusions

W3A implements no Ed25519, RFC8785/JCS signing, keys, credentials,
certificates, trust decisions, production Trust Anchor, Governance Root,
authenticated adapter identity, or signed artifact exchange. SHA-256 is used
only for bounded content and audit integrity evidence.

```text
Default Consumption: NOT AUTHORIZED
Cutover: NOT AUTHORIZED
Activation: LOCKED
Operational Entry: LOCKED
```

W3A remains SHADOW, NON-PRODUCTION, NON-DEFAULT, NON-CUTOVER,
NON-AUTHORIZING, and NON-ACTIVATING.

# ACOS W3B-B-P1 Disposable Fixture Single-Index Repair Design

## Status and Scope

This document defines a test-only shadow implementation for repairing one
missing canonical index in a factory-created disposable SQLite fixture. It
does not authorize repair of an existing store, production consumption,
activation, operational entry, or any mutation outside a separately
authorized disposable-fixture test run.

The only fault statement is:

    DROP INDEX idx_audit_events_aggregate;

The only repair statement is:

    CREATE INDEX idx_audit_events_aggregate
    ON audit_events(aggregate_type, aggregate_id, sequence);

IF NOT EXISTS, caller-provided SQL, caller-provided object names, and
caller-provided paths are forbidden.

## Fixed Capability Profiles

The implementation keeps three independent writer profiles:

    SEED_INITIALIZER != FAULT_INJECTOR != REPAIR_MUTATOR

- SEED_INITIALIZER may initialize only a fresh factory-created fixture from
  the pinned W3A seed source and digest. Its SQLITE_REINDEX allowance is
  restricted to database main and the four index names frozen by that source:
  idx_grant_observations_grant_id, idx_authorization_events_authorization,
  idx_workflow_state_events_task, and idx_audit_events_aggregate. It has no
  caller-extensible index set, fault capability, or repair capability.
- FAULT_INJECTOR may issue exactly the fixed DROP INDEX statement. It has no
  seed, DML, generic DDL, or repair capability.
- REPAIR_MUTATOR may issue exactly the fixed CREATE INDEX statement. It has no
  seed, fault, DML, generic DDL, or caller-SQL capability. SQLite may emit the
  callback-facing operation `REINDEX main.idx_audit_events_aggregate` while
  preparing that fixed CREATE INDEX. That canonical REINDEX identity is owned
  only by the fixture factory and is not a second caller-executable repair
  statement.

The repair writer has no mutable per-instance SQL field. Immediately before
execution it snapshots the module-owned `REPAIR_SQL`, revalidates the combined
canonical operation digest over that exact value, and passes the returned value
to SQLite. The validated statement and executed statement are therefore the
same bound string and cannot diverge through instance or intervening global
mutation.

A connection established for one profile is never reused for another.
Each writer accepts only a registered FixtureHandle and registry. It creates,
profiles, uses, and closes its own dedicated SQLite connection internally.
No mutation-capable method accepts or returns sqlite3.Connection, a database
path, SQL text, or a target object. A fault writer therefore cannot borrow a
repair writer connection or capability, and the converse is also true.

The privileged repair connection is short-lived, uses `cached_statements=0`,
and is never pooled. The registry admits at most one active privileged repair
lifecycle for a fixture identity. Before privileged preparation, the factory
checks `PRAGMA database_list`: `main` must resolve to the exact fixture target,
and no non-reserved attached application database may be present. Temporary
schema semantics do not become a privileged target; ATTACH and DETACH remain
default denied.

The general candidate-authorizer installation API rejects the repair profile
and accepts no privileged-context argument. Context creation, recorder
construction, authorizer installation, activation, consumption, expiration,
and connection closure occur within the same internal factory-controlled
repair lifecycle. The privileged context class, construction token, recorder
class, and recorder token are closure-private rather than module exports. The
factory claims the installer once as part of the controlled canonical load,
deletes the claim entry point, and retains the installer only inside the
internal writer closure. Context creation and authorizer installation still
occur only after runtime, fixture, and topology checks. The internal installer
also requires a non-null controlled canonical-module loader provenance. This is
process-local containment, not authenticated authority.

The registry, not a caller-held handle, owns canonical lifecycle state,
mutation_attempt_count, reusable, and generation. There is no public
full-state update primitive. A transition accepts an exact current reference,
an expected current state, and one target from the closed transition graph;
the registry derives and installs the resulting state atomically. A cloned
token-valid object is only caller data and cannot become canonical state.

## Lifecycle and Identity

The fixture lifecycle is:

    INITIALIZING -> READY -> MUTATION_TASK_BOUND -> MUTATION_ATTEMPTED
                 -> MUTATION_COMMITTED -> VERIFYING
                 -> DISPOSING -> DISPOSED

Alternative terminal branches after MUTATION_ATTEMPTED are
MUTATION_ROLLED_BACK and MUTATION_OUTCOME_UNKNOWN, each followed only by
QUARANTINED. The attempt transition increments mutation_attempt_count and
permanently sets reusable=false before the writer can begin a transaction.
No later rollback, commit, verification, or quarantine path restores reuse.
Every accepted transition increments generation. Older READY,
MUTATION_TASK_BOUND, or MUTATION_ATTEMPTED handles are stale and cannot replay
a transition, overwrite canonical state, or enter a writer. Repair requires
the exact current generation with MUTATION_ATTEMPTED, attempt count one, and
reusable=false before a connection may be opened.

Any identity uncertainty, authorizer failure, or unknown mutation outcome is
terminal for execution and may progress only through bookkeeping to
QUARANTINED. Such a fixture is never retried or reused.

A seed exception is a construction failure, not a repair mutation effect. The
seed writer closes before containment begins. If checkpoint C and the fresh
READY/reusable/zero-attempt preconditions prove the exact object, disposal is
attempted once and the internal outcome is
SEED_CONSTRUCTION_FAILED_DISPOSED. Any identity uncertainty or disposal
failure retains the fixture as QUARANTINED with outcome
SEED_CONSTRUCTION_FAILED_QUARANTINED. No usable handle is returned, and fault,
plan binding, mutation-task binding, repair, retry, rename, and authority
effects remain unavailable.

The factory creates an exclusive temporary root with mode 0700 and a fixed
database leaf with mode 0600. It does not accept a caller path and does not
change the process-global umask. Its process-local registry binds the fixture
instance identifier to root and leaf device/inode identities.

Identity checkpoints are mandatory:

- A: before prestate verification.
- B1: immediately before writable SQLite open.
- B2: post-SQLite-open registry/path/inode revalidation immediately before
  BEGIN IMMEDIATE.
- C: after writer close and before a verifier trusts the reopened fixture.

Every checkpoint verifies registry membership, fixture instance identifier,
root identity, fixed leaf, st_dev, st_ino, st_nlink == 1, root mode, leaf mode,
lstat/fstat consistency where a descriptor is available, and the absence of
unexpected lifecycle sidecars. On uncertainty: do not mutate, retry, delete,
or rename the uncertain object.

B2 does not claim visibility into or proof of SQLite's internal file
descriptor. It is the bounded post-open path/registry/inode observation
approved for this disposable-fixture scope.

Registry canonical state is process-local integrity evidence only:

    REGISTRY CANONICAL STATE != AUTHENTICATED AUTHORITY
    PROCESS-LOCAL STATE INTEGRITY != USER AUTHORIZATION
    OPAQUE HANDLE != TRUST ANCHOR

## Mutation Result and Physical Effect

Application result and physical mutation effect are orthogonal. The physical
effect vocabulary is exactly:

- NONE
- ATTEMPTED_AND_ROLLED_BACK
- COMMITTED_TEST_ONLY_DISPOSABLE_FIXTURE
- UNKNOWN_TEST_ONLY_DISPOSABLE_FIXTURE_EFFECT

A commit exception is not proof of rollback. A rollback attempt is not proof
of rollback. Observing exact prestate after an exception is not proof of
rollback. If transaction state or physical effect cannot be proven, the
operation is MUTATION_OUTCOME_UNKNOWN, its effect is
UNKNOWN_TEST_ONLY_DISPOSABLE_FIXTURE_EFFECT, and the fixture is quarantined.
A later state observation must never convert that operation to PASS.

Fault injection is itself physical fixture construction mutation. A fault
statement or commit failure that does not prove rollback is construction-level
UNKNOWN_TEST_ONLY_DISPOSABLE_FIXTURE_EFFECT. The fixture is quarantined before
prestate acceptance, plan binding, repair, or retry.

## Candidate Authorizer Policy

Authorizer policies in this package are candidate profiles. Synthetic
callback tests may exercise their predicates, but that evidence is not an
engine-characterized callback profile:

    CANDIDATE AUTHORIZER PROFILE
    != RUNTIME-CHARACTERIZED CALLBACK PROFILE

Policies default deny. Mutation-phase PRAGMA is unconditionally denied.
Unexpected action codes fail closed. Seed, fault, and repair phases have
separate candidate profiles and separate connections.
Direct profile evaluation denies repair SQLITE_REINDEX. The recorder may admit
exactly one repair callback only when all of the following match: the canonical
operation digest, physical connection identity, fixture identity, pre-open
runtime fingerprint, exact callback tuple, and
`REPAIR_STATEMENT_PREPARE_EXECUTE` phase. The context must be active and
unconsumed. Missing, stale, expired, consumed, cross-connection, cross-fixture,
wrong-SQL, wrong-fingerprint, wrong-phase, or near-miss callback state denies.
Context possession is process-local admission state, not authenticated
authority, and callers cannot provide a privilege credential.

The one repair callback tuple is exactly:

    (SQLITE_REINDEX, idx_audit_events_aggregate, null, main, null)

Unqualified names, collations, alternate indexes, non-main databases,
secondary arguments, and triggers deny. SEED_INITIALIZER retains its separate
frozen canonical index-name allowance. No generic SQLITE_REINDEX allowance is
created.

The authorizer remains installed from privileged preparation through callback
validation, execution, any automatic reprepare, and outcome determination. It
is removed before the one-shot context expires and the physical connection
closes. A repeated callback, including an automatic reprepare, cannot reuse a
consumed admission and fails closed.

Authorizer-removal failure is recorded rather than swallowed. Context
expiration and connection closure still proceed. If closure succeeds, the
fixture claim is released only after closure and the writer returns no clean
commit proof; a possibly commenced effect is classified unknown and routed to
quarantine. Context-expiration failure follows the same no-clean-success rule.
If connection closure fails, canonical fixture state is quarantined, the active
claim remains held, and execution fails closed.

## Canonical Security-Type Universe

The fixture factory is the sole canonical source of `FileIdentity`,
`FixtureHandle`, `FixtureRegistry`, and `FixtureSecurityError`. The runner and
its security-sensitive siblings load or reuse one exact module object bound to
one exact source path and digest. Module-name claims, class-name equality,
structural equivalence, duck typing, `isinstance`, and caller-controlled
`.__class__` values do not establish identity. Registry entry and consumption
require exact `type(value) is FixtureHandle` identity.

An already occupied module-cache name is reusable only when the exact object
was previously recorded by the controlled loader with its process-local
provenance token and current source digest. Matching self-declared path or
digest metadata alone is rejected. A newly loaded object is registered before
execution and rejected if replaced during execution.

## Runtime Preflight

Before a future authorized mutation run, the implementation records Python,
SQLite, adapter, platform, and compile-option information; proves the
authorizer API is present; installs a bounded authorizer; and performs a
non-mutating deny self-check. It combines those facts with the canonical SQL
operation digest and canonical module/source fingerprint. The runner primes
that fingerprint before fixture construction and the repair writer recomputes
it before opening the target writable repair connection. A mismatch blocks
before writable open and before a mutation attempt. Compile options alone are
not evidence that enforcement works. Failure of any enforcement check blocks
execution.

## Digest and W3B-A Boundary

SHA-256 values are compared as decoded 32-byte values and serialized only as
sha256:<64 lowercase hex>. W3B-A canonical JSON uses sorted keys, compact
separators, UTF-8, and ensure_ascii=true. The evidence-set digest is recomputed
from the actual repair-evidence object excluding evidence_set_digest; the plan
digest is recomputed from the actual repair-plan object excluding plan_digest;
and the research binding digest is recomputed from the binding excluding
binding_digest.

The current fixture is hashed through a verified no-follow descriptor before
repair. Its exact-byte digest and size must match pre_mutation_fixture_digest,
snapshot_reference, repair_evidence, repair_plan, and plan_verification.
Task evidence, the fixed fault profile, and expected postconditions also bind
their actual canonical objects rather than digest-shaped placeholders.

issued_at and expires_at are parsed as timezone-aware instants. The interval
must be ordered and current at use. A plan digest is evidence binding, not a
signature. PLAN_VERIFIED is not mutation authorization. This package creates
no trust anchor, authenticated nonce, Merkle authority, capability grant, or
authorization broker.

## Mutation-Test Gate Observation

The process-local mutation-test gate is observed from an exact separate task
identifier plus the exact research-binding digest. Its object cannot be
constructed with a public authorization boolean. This is accidental-use
containment only:

    GATE OBSERVATION != AUTHORITY

It neither authenticates the user nor creates mutation permission.

## Test Authorization Split

Category A covers schemas, serialization, canonical evidence recomputation,
digest normalization, pure policy mappings, fixed SQL, imports, synthetic
callbacks, and static capability separation. It creates no SQLite fixture,
writable connection, or mutation characterization.

Category B covers fixture creation, seeding, fault injection, repair,
runtime preflight, transaction mutation, actual callback characterization,
mutated poststate verification, and end-to-end disposal. Category B is
implemented but requires a separate mutation-test authorization and must not
run in this task.

The frozen runtime-compatibility regression catalog is:

- REV-01: attached and non-main schema rejection.
- REV-02: rejection of every one-field callback-tuple near miss.
- REV-03: authorizer lifecycle and callback-sequence drift.
- REV-04: non-canonical and caller-controlled `.__class__` rejection.
- REV-05: an actually overlapping thread cannot consume fixture privilege.
- REV-06: an unfinished EXPLAIN cursor cannot resume after writer disposal;
  a later independent connection does not inherit its privileged admission.
- REV-07: continuation of the same unfinished cursor fails after context expiry
  and connection close. This is the public-API lifetime equivalent, not a claim
  to revoke a detached prepared handle on a still-open connection.
- REV-08: the same EXPLAIN is compiled before a separate privileged lifecycle
  starts; an authorizer environment change forces that statement to reprepare
  under its own unprivileged connection's policy, which rejects it.
- REV-09: reinstalling the same internal authorizer after compilation but before
  first step expires the prepared statement. SQLite's automatic reprepare in
  that single execute encounters the consumed one-shot admission and denies.
- REV-10: only the canonical main index qualifies.
- REV-11: unqualified and collation-ambiguous REINDEX rejects.
- REV-12: an actual attached application schema blocks before privileged
  authorizer preparation.
- REV-13: overlapping physical repair ownership is exclusive per fixture.
- REV-14: compatibility-fingerprint drift blocks before writable open.
- REV-15: the canonical privileged repair completes positively.

REV-15 must prove the narrow positive case; a policy that denies every REINDEX
does not satisfy the design.

### Prepared-Statement Evidence Boundary

Python's public sqlite3 API does not expose a detachable sqlite3_stmt handle.
REV-06/07 therefore leave the fixed EXPLAIN cursor partially consumed, prove
admission and a live cursor inside the real writer lifecycle, and call fetchone
on that same cursor after teardown, without issuing another execute. The
observed ProgrammingError is explicitly attributed to connection closure. It
does not independently prove revocation on a still-open connection. Together
with the dedicated connection, cached_statements=0, observed context expiry,
and denial on a later unprivileged connection, it checks the implemented
no-carryover boundary. EXPLAIN does not perform the CREATE INDEX operation;
REV-15 remains the separate physical positive-closure obligation.

REV-08/09 use a test-local, empty parameter sequence. CPython compiles a statement
before asking that sequence for its length, then calls sqlite3_step. The length
hook establishes an explicit after-prepare/before-first-step boundary, without
a second execute, native pointer access, SQL changes, or a production test hook.
REV-08 first records a real compilation callback on its fixed EXPLAIN using a
test-only observer with no repair context. The boundary hook requires that
callback before starting the separate privileged lifecycle, then installs the
public deny policy on the original connection. The observer is used only for
EXPLAIN and grants no permission for actual DDL. REV-09 instead
asserts the initial engine callback has consumed admission, then reinstalls the
same internal authorizer. SQLite expires prepared statements on set_authorizer;
the next step automatically recompiles and must consult that current recorder.
Two exact engine callbacks within one execute, one denied callback, SQLITE_AUTH,
and a still-live connection distinguish reprepare denial from closure and
ordinary separate preparation. Neither test calls the recorder directly.

This test mechanism depends on the CPython adapter order and SQLite invalidation
behavior. Its definition asserts that boundary was reached exactly once;
unsupported ordering or missing reauthorization fails rather than being counted
as evidence or silently skipped. No runtime confirmation is claimed here.
The definitions remain Category B and require separate execution authorization.
Relevant primary sources are CPython's
[cursor implementation](https://github.com/python/cpython/blob/3.12/Modules/_sqlite/cursor.c),
SQLite's [authorizer implementation](https://github.com/sqlite/sqlite/blob/version-3.45.3/src/auth.c),
and [step/reprepare implementation](https://github.com/sqlite/sqlite/blob/version-3.45.3/src/vdbeapi.c).

The mutation-attempt registry latch is distinct from evidence that
mutation-capable execution commenced. BEGIN alone is not physical mutation.
Deterministic authorization denial before the privileged callback admission is
DENY with effect NONE and does not invoke DS-01. Once privileged admission is
consumed or a physical effect cannot otherwise be affirmatively excluded,
DS-01 remains
mandatory: `MUTATION_OUTCOME_UNKNOWN` proceeds only to `QUARANTINED`, never to
retry, reuse, or PASS.

## Explicit Exclusions

No real-store connector, generic repair engine, caller path, caller SQL,
production hook, default consumption, activation, operational entry, W3B-C,
Git staging, commit, or push is provided or authorized.

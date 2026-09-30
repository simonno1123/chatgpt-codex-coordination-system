# ACOS W3B-B-P1 Security and Threat Model

## Security Objective

W3B-B-P1 demonstrates a narrowly bounded, fail-closed repair experiment on a
factory-created disposable fixture. It is not a production repair mechanism
and does not confer governance or execution authority.

## Assets and Trust Boundaries

Protected assets are the canonical W3A seed, fixed index definition, fixture
identity, research binding, plan/evidence digests, mutation effect record, and
poststate evidence. The process-local registry and exclusive temporary root
form a test-only trust boundary. Caller paths, caller SQL, existing databases,
real stores, credentials, grants, and production identities are outside scope.

## Threats and Controls

| Threat | Required control |
| --- | --- |
| Path substitution or symlink swap | Fixed leaf, exclusive creation, root and leaf lstat, descriptor fstat, device/inode binding at A/B1/B2/C |
| Hard-link aliasing | Require st_nlink == 1 at every checkpoint |
| Sidecar substitution | Reject unexpected -wal, -shm, or -journal lifecycle sidecars |
| Capability conflation | Separate seed, fault, and repair classes, profiles, and connections |
| Arbitrary connection escape | Writer methods accept only registered fixture handles; connection creation and closure are internal |
| Generic SQL injection | Fixed SQL constants only; no caller SQL or object names |
| Authorizer ambiguity | Default deny, reject unknown action codes, non-mutating installation self-check, candidate profile label |
| Transaction ambiguity | Four-valued physical effect; unknown outcome is terminal and quarantined |
| False rollback claim | Rollback must be proven independently; exceptions and exact prestate are insufficient |
| Digest confusion | Parse canonical lowercase prefixed SHA-256, compare decoded bytes, and recompute W3B-A evidence, plan, binding, task, fault-profile, and postcondition digests from actual objects |
| Stale snapshot binding | Hash current fixture bytes through a verified descriptor and require digest/size equality across the complete W3B-A snapshot chain |
| Expired binding | Parse issued_at/expires_at, require an ordered timezone-aware interval, and reject use outside it |
| Self-asserted gate | Observe exact task and binding digest without a caller-provided authorization boolean; observation is not authority |
| Cloned or stale handle state injection | Registry owns canonical lifecycle/count/reuse/generation, exposes no full-state update, and rejects non-current references before transition or writer entry |
| Seed REINDEX capability expansion | Allow only SEED_INITIALIZER, main, null secondary/trigger arguments, and one of four index names frozen by the canonical seed; deny every other profile/name/database/combination |
| Repair REINDEX overbreadth | Direct repair-profile evaluation denies REINDEX; admit one exact callback tuple only through an active, bound, one-shot context |
| Caller-supplied privilege | Public authorizer installation rejects the repair profile and accepts no context; context, recorder, and tokens are closure-private, and the controlled factory lifecycle claims the installer once with non-null canonical-loader provenance before creating and consuming its own context |
| Attached-schema target substitution | Before privileged preparation require main to resolve to the fixture and reject every non-reserved attached application database; ATTACH/DETACH remain denied |
| Privilege replay or concurrent repair | Bind context to connection, fixture, SQL digest, fingerprint, phase, and consumption state; allow one active repair lifecycle per fixture |
| Prepared-statement privilege carryover | Use a dedicated repair connection with cached_statements=0; keep the authorizer active through outcome determination and expire context before close |
| Duplicate security-type universe | Reuse one canonical module object per exact source path/digest and require exact type identity at registry boundaries |
| Self-declared module provenance | Accept a cached object only when the controlled loader already owns that exact object and provenance token; matching metadata alone is insufficient |
| Runtime compatibility drift | Recompute the bound runtime/module/SQL fingerprint before writable repair open and block on mismatch |
| Mutable executed SQL | Execute the module-owned canonical repair SQL directly after revalidating its combined operation digest |
| Authorizer teardown failure | Record failure, invalidate clean success, expire context, close the connection, and retain the fixture claim if closure cannot be proven |
| Partial seed returned as usable fixture | Close the writer, attempt one identity-proven disposal, otherwise quarantine; return no handle and never enter fault, plan binding, or repair |
| Authority upgrade | Full taint fields, eligible_for_execution=false, no production or operational effect |
| Unsafe cleanup | On identity uncertainty do not delete or rename; preserve evidence and quarantine |

## Fail-Closed Invariants

1. No mutation starts unless runtime preflight and identity checkpoints pass.
2. A writer connection is created internally, single-profile,
   single-operation, never pooled, never returned, and never supplied by a
   caller.
3. Mutation-phase PRAGMA, DML, attachment, and generic DDL are denied.
4. An unexpected callback action blocks the operation.
5. MUTATION_OUTCOME_UNKNOWN cannot be retried or reused and cannot become PASS
   through later observation.
6. Failed disposal does not erase the previously recorded mutation effect.
7. Repository durability, governance persistence, plan verification, and
   mutation authorization remain distinct.
8. The mutation-attempt latch is consumed before BEGIN and can never be reset.
9. B2 is post-open registry/path/inode revalidation, not proof of SQLite's
   internal descriptor.
10. Fault-construction commit uncertainty quarantines before prestate
    acceptance or repair.
11. MUTATION_ATTEMPTED is one atomic registry transition that sets attempt
    count to one and reusable to false while advancing generation.
12. Token validity does not establish freshness or transition authority; a
    stale or cloned handle cannot overwrite canonical registry state.
13. Seed construction failure is not a repair mutation effect and never
    yields a usable fixture, execution eligibility, or production effect.
14. Failed-seed disposal is attempted once only after exact identity and fresh
    construction-state checks; uncertainty or cleanup failure quarantines
    without retry, rename, fault injection, or repair.
15. Repair SQLITE_REINDEX is not generally allowed. The only positive case is
    `(SQLITE_REINDEX, idx_audit_events_aggregate, null, main, null)` under the
    exact active one-shot context; every near miss denies.
16. One callback admission consumes the repair context. A repeated callback,
    including automatic reprepare, denies while the authorizer remains active.
17. A repair context is process-local admission state, not authenticated
    authority, and cannot cross connection, fixture, fingerprint, SQL, phase,
    lifecycle, or capability-profile boundaries.
18. One fixture may have at most one active privileged repair lifecycle and
    one dedicated physical repair connection. Pooling is absent.
19. The target topology is `main` bound to the exact fixture. Reserved temp
    semantics are not privileged; attached application schemas are rejected.
20. Runtime compatibility is primed before fixture construction and checked
    again before target writable open. Drift blocks without mutation attempt.
21. Security-sensitive fixture objects require the canonical factory module's
    exact type identity; `.__class__`, `isinstance`, duck typing, and naming
    equivalence do not substitute for that identity.
22. Deterministic pre-mutation denial is DENY, not DS-01. If physical effect
    cannot be excluded, DS-01 requires quarantine and forbids reuse or PASS.
23. A transaction BEGIN and a consumed registry attempt latch do not themselves
    prove mutation-capable execution. A pre-admission authorizer denial remains
    effect NONE; consumed admission or uncertain execution invokes DS-01.
24. Privileged context and recorder constructors and their tokens are not module
    exports. Authority creation and consumption remain inside one repair
    lifecycle and its once-claimed factory closure.
25. Teardown failure cannot preserve a clean success classification. Connection
    closure precedes claim release; failed closure retains the claim.

## Runtime and Filesystem Preconditions

The preflight records runtime facts and proves authorizer installation through
a bounded non-mutating denial. It binds Python, SQLite, adapter, platform,
compile options, canonical SQL identity, and canonical module/source identity
into a compatibility fingerprint. The factory checks the fingerprint before
opening the writable repair connection. It then verifies connection topology,
uses a zero-cache dedicated connection, and installs the one-shot authorizer
context before privileged preparation. The factory also uses exclusive OS
primitives, 0700 root mode, 0600 leaf mode, immediate identity verification,
and no process-global umask mutation. Any mismatch blocks further execution.

## Residual Risks

Candidate authorizer action sequences have not been characterized against a
mutating SQLite run in this task. B2 cannot observe SQLite's internal file
descriptor, and the process-local gate is not authenticated authority.
Filesystem and SQLite behavior can vary by platform. Category B tests
therefore remain a separate authorization gate.
The pre-open fingerprint detects compatibility drift but is not remote
attestation, a trust anchor, or proof of authority. The process-local module
registry and repair lock do not coordinate separate processes. A callback
sequence requiring automatic reprepare fails closed after the single admission
rather than gaining a generic retry privilege.
No inference from Category A results may authorize mutation, production use,
default consumption, activation, or operational entry.
Registry canonical state remains process-local integrity evidence, not
authenticated governance authority, user authorization, or a trust anchor.
Controlled-loader provenance is likewise process-local containment, not
cryptographic executed-code attestation and not protection from an interpreter
administrator capable of arbitrary reflective mutation.

REV-06/07 exercise the public sqlite3 lifetime boundary through an unfinished
EXPLAIN cursor and its post-close fetchone, not a detached native prepared
handle or revocation on an open connection. The observed close error must be
read together with zero statement caching, context expiry, and independent
connection denial; it is not evidence of authorizer checks on every step.
REV-08/09 depend on CPython compiling before binding the empty parameter
sequence. Their test-only boundary hook changes the authorizer environment,
which invalidates the same already-prepared statement before its first step.
The subsequent engine callbacks and SQLITE_AUTH must demonstrate automatic
reprepare under the current policy; repeated execute calls alone do not count.
An adapter that does not expose this ordering must fail the definition's
assertions and return for compatibility review. These definitions have not
been executed by the second narrow correction and provide no test PASS claim.

# ACOS W2 Identity, Evidence, and Persistence Shadow Profile

STATUS:
W2 SHADOW PROFILE / NON-PRODUCTION / NON-DEFAULT / NON-CUTOVER

BASELINE:
b665cfe54a5226694e735683d7440233f41132f5

CONTRACT BINDING:
ACOS Contract 2.0

W2 AUXILIARY SCHEMA FAMILY:
1.0

The version relationship is normative:

```text
W2 auxiliary version 1.0
!=
ACOS Contract version 2.0
!=
Artifact Envelope schema version 2.0
```

W2 adds auxiliary shadow representations under the already accepted Contract
2.0 boundary. It does not change the Artifact Envelope or policy schema and
does not create, announce, or imply ACOS Contract 2.1.

## A. Scope

W2 defines a static Runtime Registry representation, typed Evidence Records,
Persistence Receipts, positive fixtures, and a deterministic read-only shadow
verifier. These artifacts support planning and local evidence evaluation only.
They are non-production, non-default, and non-cutover.

## B. Contract And Version Relationship

Every W2 object declares `profile_version` 1.0 and binds
`contract_binding.contract_version` to 2.0. The W2 verifier accepts only that
tuple and performs no fallback or downgrade. W2 auxiliary schemas do not
replace, extend, dispatch, or modify the Contract 2.0 schemas.

## C. Identity Model

The identity model preserves these separations:

```text
Runtime Identity != Provider/Model
Runtime Identifier != Provider ID
Runtime Identifier != Model ID
Runtime Registry Entry != Authenticated Runtime Identity
Identity Claim != Authenticated Identity
SHADOW_VERIFIED != Authenticated
SHADOW_VERIFIED != Authorized Runtime
```

Provider and model identifiers are optional descriptive attributes. They do
not derive a runtime identifier or session identifier. An identity state is a
bounded shadow observation, not authentication or authorization.

## D. Runtime Registry

The Runtime Registry is a static supplied document. The verifier does not
mutate it or persist state. Runtime and session identifiers must be unique in
one registry, each referenced trust domain must exist, and revoked or expired
entries are denied. Expiry checks require an explicit verifier time.

## E. Non-Production Trust-Domain Representation

Trust domains are limited to LOCAL, TEST, and SHADOW environments. Their
verification methods, issuer references, key references, validity windows,
rotation state, and revocation state are structural declarations only.
`claim_status` is always `DECLARED_ONLY`. No production trust decision,
Trust Anchor, Governance Root, key custody, or certificate authority is
established.

```text
Key Reference != Key Material
Key Material != Key Custody
Key Custody != Signature Verification
Signature Verification != Trust Decision
Trust Decision != Governance Authority
```

## F. Evidence Model

Evidence Records represent bounded observations: identity, digest, reference
binding, revocation, expiry, or persistence verification. Evidence lineage may
have multiple unique parents. Self-parenting and duplicate parents are denied.
Nonce uniqueness can be checked only within a supplied in-memory verification
set.

```text
Evidence != Authority
Evidence Verification PASS != Authority
Producer attribution != governance authority
```

## G. Persistence Receipt Model

A Persistence Receipt records declared Producer attribution, independently
declared Materializer attribution, a materialization target, and exact-byte
digest evidence. The two attributions remain separate.

```text
Producer != Materializer
Persistence Receipt != Persistence Grant
Persistence Receipt != Decision Authority
Persistence Receipt != Authorization
Git reference != verified remote durability unless separately verified
```

`MANAGED_CONVERSATION` is representation only and does not establish an
operationally sufficient persistence channel. Optional Git durability fields
are structural claims with `DECLARED_ONLY` status.

## H. Deterministic Verification Semantics

The verifier returns PASS, DENY, or BLOCKED. Invalid or refuted claims are
DENY. A fact that cannot be established from supplied bounded inputs is
BLOCKED. A valid shadow representation or comparison is PASS. Every result
has `authority_effect` equal to `NONE`.

Expiry evaluation uses only an explicit verifier time. Exact-byte checks use
only an explicitly supplied repository-local target, reject traversal and
symlink paths, and never infer a missing target. Duplicate nonces are detected
inside one supplied set. A cross-run replay claim without durable state is
BLOCKED. W2 has no durable replay registry.

## I. Crypto Deferral

DEFER CRYPTO. Ed25519 plus RFC8785/JCS remains a future candidate requiring a
separate Security Review and authorization. W2 generates no keys,
certificates, signatures, or cryptographic trust decisions and adds no crypto
dependency.

## J. Governance Persistence Gap

GOVERNANCE PERSISTENCE GAP:
PARTIALLY ADDRESSED / NOT RESOLVED

W2 can represent and verify local persistence evidence, but it does not create an independently governed native ChatGPT governance persistence channel.
It creates no Persistence Writer, Persistence Grant, Git enforcement
mechanism, or durable cross-run state.

## K. W3 Boundary

W3 remains outside this package. W2 does not issue, validate as authority,
reserve, consume, revoke, or enforce Grants or Authorizations. It does not
create an Authorization Broker, transactional reservation, durable
authorization state, policy enforcement, or state-transition enforcement. A
reference or observation remains representation only and never becomes active
state.

## L. Failure Semantics

- PASS: the supplied shadow representation or comparison satisfies W2.
- DENY: a supplied claim is structurally invalid, contradicted, revoked,
  expired, duplicated, unsafe, unsupported, or digest-mismatched.
- BLOCKED: required evidence, deterministic time, local target, dependency, or
  durable replay state is unavailable.

No result authenticates a runtime or changes project state.

## M. Authority Non-Implication

The following rules are immutable:

```text
Executor != Reviewer
Executor != Decision Authority
Reviewer status != governance authority
Reviewer status != Decision Authority
Authority != Capability
Capability != Grant
Grant != Authorization
Governance Decision != Authorization
Receipt != Authority
Lifecycle representation != enacted transition
```

Role attribution does not self-confer authority. W2 validation does not grant
execution, review, decision, transition, persistence, or operational power.

## N. Activation And Operational Entry Exclusion

```text
Default Consumption: NONE
Cutover: NONE
Activation: LOCKED
Operational Entry: LOCKED
```

Activation remains distinct from Operational Entry. This profile authorizes
neither and cannot be consumed as authority for either state.

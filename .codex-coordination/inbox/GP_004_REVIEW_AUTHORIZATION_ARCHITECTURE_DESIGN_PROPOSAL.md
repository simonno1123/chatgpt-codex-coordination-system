ARTIFACT TYPE:
GOVERNANCE PROPOSAL

PRODUCER:
ChatGPT Review

TO:
Codex Executor

NEXT RECEIVER:
ChatGPT Review

PROJECT:
/Users/zhang/Documents/chatgpt-codex-coordination-system

MODE:
REVIEW AUTHORIZATION ARCHITECTURE DESIGN PROPOSAL DEFINITION

PROPOSAL ID:
GP-004

TITLE:
Review Authorization Architecture Design Proposal

STATUS:
MATERIALIZED FOR REVIEW

OBJECTIVE:
Study and define the design scope for a provable, non-recursive, target-bound
Review Authorization Architecture.

GP-004 asks how Review is authorized, constrained, and proven. It does not
implement a Review Authorization Layer.

BACKGROUND BINDING:

SOURCE VALIDATION:
OPERATIONAL_VALIDATION_CASE_001

CONFIRMED DEFECT:
M-003 / Producer Materializer Traceability

PARTIALLY CONFIRMED FINDING:
M-007 / Review Authorization Traceability

M-007 STATUS:
PARTIALLY CONFIRMED

PREDECESSOR DECISION:
`.codex-coordination/inbox/GP_003_REVIEW_AUTHORIZATION_GOVERNANCE_MODEL_PROPOSAL_DECISION.md`

PREDECESSOR DECISION SHA-256:
`afe4aae6a9872d3921da27229e0d469f83f33812d071d459038de8f303b695a5`

PREDECESSOR FORMAL REVIEW:
`.codex-coordination/outbox/GP_003_REVIEW_AUTHORIZATION_GOVERNANCE_MODEL_FORMAL_REVIEW.md`

PREDECESSOR FORMAL REVIEW SHA-256:
`9c52c1190b459448ddb3f553e29dcdde82fb3bb66281290480d551d900227000`

PREDECESSOR STATUS:
GP-003 PROPOSAL_DECISION_ACCEPTED / NOT IMPLEMENTED

DESIGN PROBLEM:

ACOS requires a design that can establish:

```text
How is Review authorized?
How is Review constrained?
How is Review authorization proven?
```

The design must preserve standing role capability for routine activity while
adding sufficient target and scope traceability for high-risk, cross-role,
multi-model, or external Review.

DESIGN PRINCIPLES:

1. Authorization must be traceable to an explicit trust source.
2. Review grants must bind the intended target and target content.
3. Review authority must be narrower than Decision or implementation authority.
4. Authorization recursion must terminate at a governed trust anchor.
5. Role labels alone do not prove runtime identity or target authority.
6. Missing or conflicting authority evidence must fail closed.

DESIGN SCOPE 1: AUTHORIZATION CHAIN

Study the following authorization chain:

```text
Trust Anchor
        |
Governance Authority
        |
Role Authority
        |
Review Grant
        |
Reviewer
        |
Review Artifact
```

The design should define:

- the identity and evidence required at each stage;
- permitted delegation boundaries;
- grant scope and validity;
- revocation and supersession;
- audit references;
- fail-closed conditions;
- separation from execution, Decision, and implementation authority.

DESIGN SCOPE 2: TARGET BINDING

A Review grant should be evaluated for binding to:

```text
Target Artifact
        +
Target SHA-256
        +
Review Scope
        +
Review Objective
```

The design must prevent a Review of one draft from being represented as a
Review of a different or later artifact.

Target-binding research should include:

- immutable target identifiers;
- content SHA-256;
- version or supersession references;
- stale-target detection;
- multi-artifact Review sets;
- target changes during Review;
- authorization expiry after target mutation.

DESIGN SCOPE 3: SCOPE LIMITATION

A Review authorization should evaluate explicit allowed actions such as:

```text
READ
ANALYZE
REPORT
```

and explicit forbidden actions such as:

```text
MODIFY
EXECUTE
DECIDE
IMPLEMENT
```

The final vocabulary remains a design question. Scope constraints must be
machine-verifiable where feasible and must not rely solely on narrative intent.

DESIGN SCOPE 4: REVIEW GRANT CONTENT

Study whether a Review grant must include:

- Grant Identifier;
- Grantor Identity;
- Governance Authority Reference;
- Reviewer Identity;
- Reviewer Role;
- Reviewer Runtime Identity;
- Target Identifier;
- Target SHA-256;
- Review Objective;
- Allowed Scope;
- Allowed Finding or Disposition Vocabulary;
- Forbidden Actions;
- Validity Period or Single-Use Condition;
- Audit Trace Reference;
- Revocation or Supersession Status.

GP-004 does not establish a schema or require these exact field names.

RECURSIVE AUTHORIZATION PROBLEM:

GP-004 must evaluate:

```text
Who authorizes Authorization?
```

The architecture must prevent:

```text
Authorization
    |
Authorization of Authorization
    |
Authorization of Authorization of Authorization
```

The authority chain must terminate at a defined trust anchor and preserve an
auditable path from that anchor to the specific Review grant.

TRUST ANCHOR MODEL 1: USER ROOT AUTHORITY

Concept:

```text
User Root
    |
Governance Rules
    |
Operational Roles
```

Research questions:

- how User Root identity is established;
- how authority is constrained and recorded;
- how delegation is revoked;
- how governance authority is separated from operational authority;
- how user instructions are bound to target hashes and scope.

Potential risk:
User Root must not become an implicit grant of unlimited repository, execution,
or implementation authority.

TRUST ANCHOR MODEL 2: CONTRACT ROOT AUTHORITY

Concept:

```text
ACOS Contract
    |
Role Definition
    |
Action Permission
```

Research questions:

- whether the Contract can provide standing Review authority;
- how Contract version and integrity are proven;
- how exceptions and target-specific grants are governed;
- how Contract changes are authorized without circular dependence.

Potential risk:
A static Contract may be too broad, stale, or unable to bind a specific Review
target and runtime.

TRUST ANCHOR MODEL 3: HYBRID TRUST MODEL

Concept:

```text
User Root Authority
        +
ACOS Contract Constraint
        |
Governance Authority
        |
Target-Bound Review Grant
```

This model is the primary research baseline inherited from GP-003. It combines
an explicit user trust source with contract-defined role and scope constraints.

Potential benefits:

- terminates authorization recursion;
- constrains root authority through accepted governance rules;
- supports standing role permission and target-specific binding;
- improves traceability for external and high-risk Review.

Potential risks:

- unclear conflict resolution between user instruction and Contract;
- complexity of authority-chain validation;
- risk of treating user identity as unlimited operational authority;
- migration and backward-compatibility requirements.

No Trust Anchor model is selected or implemented by GP-004.

GOVERNANCE AND OPERATIONAL AUTHORITY SEPARATION:

Any future design must preserve:

```text
Governance Authority
        !=
Operational Authority
```

Authority to authorize or review a governance action must not silently grant:

- filesystem write authority;
- task execution authority;
- Git authority;
- Decision implementation authority;
- access to external Matter data;
- schema, linter, or Core modification authority.

EXTERNAL ADVISORY BOUNDARY:

External Advisory Reviewer may possess:

```text
Advisory Capability
```

External Advisory Reviewer does not possess:

```text
Decision Authority
Execution Authority
State Transition Authority
Implementation Authority
```

The governed flow remains:

```text
External Advisory
        |
ChatGPT Review
        |
Decision
```

An Advisory Review is non-binding input. It cannot authorize its own
consumption, select a Decision, or change system state.

REVIEW INDEPENDENCE DESIGN:

The architecture should evaluate evidence that:

- the artifact Author and Reviewer are distinguishable;
- the Materializer is identified separately;
- Reviewer authority is valid for the bound target;
- Reviewer runtime is distinguishable from the creation runtime;
- Review does not silently exercise Decision or implementation authority;
- advisory, formal Review, Audit, and Decision roles remain distinct.

FAIL-CLOSED DESIGN REQUIREMENTS:

The architecture should block Review when:

- trust-anchor evidence is missing;
- the authority chain cannot be validated;
- target SHA-256 does not match;
- the Review grant is expired, revoked, or superseded;
- Review scope is absent or exceeded;
- reviewer identity or runtime identity is unavailable where required;
- role conflict is undisclosed;
- the target changes after authorization;
- the Review attempts to decide, modify, execute, or implement without separate
  authority.

DESIGN QUESTIONS:

1. Which Trust Anchor model best terminates recursion without creating unlimited
   authority?
2. How should conflicts between User Root instructions and Contract constraints
   be resolved?
3. Which Reviews may rely on standing role authority?
4. Which Reviews require target-bound grants?
5. Can existing `DECISION` artifacts express Review grants without a new
   artifact type?
6. Must a Review grant be embedded, append-only, or both?
7. How is Runtime Identity represented and validated?
8. How are grant expiry, revocation, and target mutation handled?
9. How are External Advisory and Formal Review authorizations distinguished?
10. What migration and regression validation are required before GP-002 Review
    may resume?

EXPECTED FUTURE DESIGN OUTPUTS:

Subject to separate Review and Decision, later work may define:

- Review Authorization Chain design;
- Review Grant model;
- Trust Anchor model;
- target and scope binding rules;
- authority-chain validation rules;
- independence evidence rules;
- fail-closed behavior;
- audit trace requirements;
- compatibility and migration requirements;
- regression validation criteria.

No such output is implemented or accepted through GP-004 materialization.

IDENTITY ATTRIBUTION:

Logical Author:
ChatGPT Review

Logical Author Source:
Current GP-004 definition and materialization instruction

Physical Materializer:
Codex Executor

Materializer Action:
Create `.codex-coordination/inbox/GP_004_REVIEW_AUTHORIZATION_ARCHITECTURE_DESIGN_PROPOSAL.md` only

Runtime Identity:
Current Codex desktop task; no stable machine-verifiable runtime identifier is
exposed to this Artifact

Reviewer:
NOT ASSIGNED

Auditor:
NOT ASSIGNED

Decision Authority:
NOT EXERCISED

Author and Materializer are explicitly distinct. The current required
`PRODUCER` field is not treated as the only identity evidence.

NON-IMPLEMENTATION BOUNDARY:

GP-004 does not authorize:

- Review Authorization Layer implementation;
- Review grant creation for an operational Review;
- artifact type addition or modification;
- Contract, schema, linter, validator, state-machine, or Core modification;
- existing artifact rewrite or retrospective re-attribution;
- GP-002 Review or Decision;
- M-003 closure;
- M-007 remediation closure;
- Operational Validation Case progression or closure;
- Matter closure or modification;
- Git operations.

CURRENT LOCKS:

- GP-002 Review: LOCKED
- GP-002 Decision: LOCKED
- GP-004 Decision: LOCKED
- Review Authorization Layer: NOT CREATED
- Matter Data Access: LOCKED
- Evidence Access: LOCKED
- Fact Candidate Access/Creation: LOCKED
- Legal Fact Access/Creation: LOCKED
- Legal Reasoning: LOCKED
- Legal Decision Creation: LOCKED
- Decision Implementation: LOCKED
- ACOS Core Modification: LOCKED
- Artifact Contract Modification: LOCKED
- Schema Modification: LOCKED
- Linter Modification: LOCKED
- Artifact Type Addition: LOCKED
- Git Operations: LOCKED

POST-MATERIALIZATION STATE:

- GP-003: PROPOSAL_DECISION_ACCEPTED / NOT IMPLEMENTED
- M-007: PARTIALLY CONFIRMED
- GP-004: MATERIALIZED / REVIEW PENDING
- Review Authorization Architecture: NOT IMPLEMENTED
- Operational Validation Case 001: ACTIVE / REMEDIATION BLOCKED
- Case Decision: LOCKED
- Validation Case Closure: LOCKED

AUTHORITY LIMIT:
This Proposal defines the Review Authorization Architecture design scope only.

It does not authorize architecture acceptance, implementation, Review grant
creation, Contract or schema changes, Core modification, Validation Case
progression, or Git operations.

FORBIDDEN:

- treating GP-004 as an accepted or implemented architecture;
- creating a Review Authorization Layer or operational Review grant;
- modifying ACOS Core, Artifact Contract, schema, linter, validator, or state
  machine;
- adding or changing an artifact type;
- modifying or re-attributing any existing artifact;
- creating GP-002 Review or Decision;
- accepting or closing Operational Validation Case 001;
- closing or modifying the Matter;
- accessing external Matter data;
- creating Review, Decision, Closure, or implementation artifacts through this
  materialization action;
- executing Git add, commit, or push.

OUTPUT:
Review Authorization Architecture Design Proposal only.

NEXT RECEIVER:
ChatGPT Review

REASON:
Independent Review is required before any architecture Decision or
implementation proposal may be considered.

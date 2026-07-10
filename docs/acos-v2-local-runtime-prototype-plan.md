# ACOS v2.0 Local Runtime Prototype Plan

## 1. Scope And Purpose

This document defines a design-only plan for a future ACOS v2.0 local runtime prototype.

The prototype would test whether the v2.0 governance model can be represented as local runtime identities, scoped capabilities, filesystem boundaries, Git operation gates, append-only audit events, advisory review gates, User Decision gates, and project-instance boundaries.

The plan does not implement those controls.

The first-stage intent is:

```text
design-only prototype plan
        +
manual or scripted future simulation plan
        +
fixture-based validation
        =
evidence for a later implementation decision
```

The first stage explicitly provides:

```text
no active runtime enforcement yet
no real container isolation yet
no real API key management yet
no automatic provider invocation yet
```

## 2. Prototype Goals

### 2.1 Validate Runtime Identity Separation

Demonstrate, using future local fixtures, that these identities have distinct authority:

- ChatGPT Review Runtime
- Codex Executor Runtime
- External Advisory Runtime
- Automation Runtime

The prototype should prove that runtime identity is independent of model or provider name.

### 2.2 Validate Default-Deny Capabilities

Demonstrate that an operation is denied unless all required context is valid:

- authenticated runtime identity
- project root
- task ID
- applicable decision or authorization
- path scope
- operation class
- validity window
- required advisory or User Decision gate

### 2.3 Validate Filesystem Isolation Decisions

Demonstrate that future controls can distinguish:

- ACOS core paths
- coordination artifact paths
- protected review and decision paths
- business project code
- external project instances
- instance-local `.codex-coordination/`

### 2.4 Validate Git Operation Separation

Demonstrate that:

```text
inspect != test != edit != stage != commit != push != release
```

No prior operation should imply authority for the next.

### 2.5 Validate Auditability

Demonstrate that allowed, denied, failed, blocked, overridden, and completed outcomes can produce linked audit events without turning audit records into authority.

### 2.6 Validate Advisory And User Gates

Demonstrate that mandatory advisory work cannot advance to final governance acceptance without a valid `ADVISORY REVIEW` and ChatGPT Review consumption, unless an explicit User Decision override is present.

### 2.7 Validate Fail-Closed Behavior

Demonstrate that missing, ambiguous, expired, misrouted, or spoofed authority causes denial without broader fallback.

### 2.8 Preserve v1.5 Safety During Migration

Keep the existing linter and pre-commit hook unchanged while the prototype operates in future shadow or fixture mode.

## 3. Non-Goals

The local prototype first stage will not:

- deploy real multi-container isolation
- create real operating-system users
- create production filesystem ACLs
- manage real API keys or secrets
- call ChatGPT, Codex, Gemini, or another provider automatically
- change provider selection
- implement a production runtime launcher
- implement a production filesystem sandbox
- implement a production Git wrapper
- implement a production audit service
- implement a Web UI
- implement cloud permission infrastructure
- migrate a business project
- modify `claude-for-legal-cn` or another instance
- replace ChatGPT Review or User Decision
- bypass the current artifact linter or hook
- authorize unattended commit, push, or release
- claim security equivalence with containers or operating-system isolation

The prototype is not a production security boundary.

## 4. Runtime Components

The future prototype should plan, but not yet implement, the following components.

### 4.1 Runtime Launcher

Purpose:

- start one bounded runtime session
- bind a runtime identity
- load a validated capability manifest
- select one canonical project root
- issue a session ID and expiry
- invoke only the permitted simulation adapter
- end or revoke the session

The launcher must not infer missing authority.

### 4.2 Filesystem Permission Wrapper

Purpose:

- canonicalize requested paths
- classify ACOS core, artifact, instance, and local-history paths
- compare the request with task and decision scope
- allow a simulated operation or deny it
- detect traversal, symlink, writable-parent, and cross-project escape attempts

### 4.3 Git Operation Wrapper

Purpose:

- classify inspect, test, edit, stage, commit, push, and release
- enforce independent operation grants
- require exact staged manifests
- prevent blanket staging and destructive patterns
- require separate push and release authorization

The first prototype should not contact a real remote.

### 4.4 Audit Record Writer

Purpose:

- append canonical audit events
- link events by task, decision, artifact, and prior event hash
- record allow, deny, blocked, failed, completed, and overridden results
- reject silent rewrites
- expose fixture records for validation

### 4.5 Advisory Review Gate

Purpose:

- classify whether TASK_046 requires mandatory advisory review
- validate a fixture `ADVISORY REVIEW`
- require return to ChatGPT Review
- require ChatGPT Review disposition of material findings
- block direct advisory-to-Codex routing

### 4.6 User Decision Gate

Purpose:

- consume an explicit User Decision reference
- validate project, task, scope, duration, and override reason
- prevent reuse outside the bounded task
- distinguish user direction from ChatGPT Review decision
- avoid recording credentials or secrets

### 4.7 Instance Boundary Checker

Purpose:

- distinguish ACOS core from project instances
- validate canonical project roots
- reject cross-project capability replay
- treat instance-local `.codex-coordination/` as non-core by default
- require explicit User Decision for local ACOS instance mode

### 4.8 Artifact Validation Adapter

Purpose:

- reuse or model existing linter rules in future dry-run mode
- verify artifact metadata, producer authority, and routing
- reject identity spoofing and self-acceptance

The prototype must not modify `scripts/acos-linter.py` or `.githooks/pre-commit` during the planning phase.

## 5. Local Directory Layout

The following is a conceptual future layout. TASK_045 does not create these directories.

```text
<temporary-prototype-root>/
├── control/
│   ├── policy-snapshot/
│   ├── capability-manifests/
│   └── decision-fixtures/
├── sessions/
│   ├── review-runtime/<session-id>/
│   ├── executor-runtime/<session-id>/
│   ├── advisory-runtime/<session-id>/
│   └── automation-runtime/<session-id>/
├── workspaces/
│   ├── acos-core-fixture/
│   └── project-instance-fixture/
├── artifacts/
│   ├── inbox/
│   ├── outbox/
│   ├── reviews/
│   └── decisions/
├── audit/
│   ├── events/
│   ├── integrity/
│   └── failures/
├── git-fixtures/
│   ├── working-repository/
│   └── local-bare-remote/
└── reports/
    ├── scenario-results/
    └── validation-summary/
```

### 5.1 Layout Principles

1. Use a temporary fixture root, not a real business project.
2. Keep ACOS core and project-instance fixtures separate.
3. Give each runtime session a separate state directory.
4. Keep decisions and audit evidence outside executor-writable paths.
5. Keep secrets out of the prototype layout.
6. Treat any local bare Git remote as a fixture only.
7. Remove fixture cleanup from the first implementation unless cleanup is separately authorized and safe.
8. Do not copy ACOS core rules into a real project instance.

## 6. Runtime Identity Simulation

### 6.1 Simulated Identity Profile

A future prototype may represent each runtime with a non-secret fixture profile containing:

- `runtime_identity`
- `runtime_session_id`
- `provider_label` for context only
- `project_root`
- allowed artifact types
- allowed operation classes
- readable paths
- writable paths
- capability issue time
- capability expiry time
- task and decision references

The profile must not contain real credentials.

### 6.2 Runtime Profiles

#### ChatGPT Review Runtime

Simulated abilities:

- produce fixture `TASK`, `REVIEW`, and `DECISION`
- consume `RESULT`, `BLOCKED RESULT`, and `ADVISORY REVIEW`
- authorize bounded next operations

Simulated denials:

- project code edit
- Codex `RESULT` production
- External Advisory impersonation
- Git execution

#### Codex Executor Runtime

Simulated abilities:

- consume bounded tasks and context
- request simulated filesystem or Git operations
- produce `RESULT` or `BLOCKED RESULT`

Simulated denials:

- `REVIEW` or `DECISION` production
- decisions-path writes
- self-acceptance
- scope expansion

#### External Advisory Runtime

Simulated abilities:

- read explicitly provided fixture context
- produce `ADVISORY REVIEW`
- return it to ChatGPT Review

Simulated denials:

- file edits
- shell or Git execution
- `TASK`, `RESULT`, `REVIEW`, or `DECISION`
- direct route to Codex

#### Automation Runtime

Simulated abilities:

- run deterministic fixture checks
- produce `RESULT` or `RECORD`
- append audit fixture events

Simulated denials:

- review or decision
- commit, push, or release
- self-acceptance

### 6.3 Identity Binding Test

The future launcher should compare:

```text
authenticated runtime identity
        vs
artifact producer
        vs
requested operation
```

Any mismatch should be denied and audited.

### 6.4 Session Expiry

A runtime capability should become invalid when:

- its time window expires
- the task completes
- the project root changes
- the decision is revoked
- a violation occurs
- the runtime session ends

The prototype should test replay after expiry and expect denial.

## 7. Filesystem Permission Simulation

### 7.1 Simulation Stages

The filesystem simulation should advance only through separately approved future tasks.

#### Stage A: Decision-Only Dry Run

Input:

- runtime profile
- canonical fixture root
- requested path
- operation
- task and decision fixtures

Output:

- allow or deny decision
- reason
- expected audit event

No filesystem mutation occurs.

#### Stage B: Temporary Fixture Mutation

Use only a temporary fixture workspace after Stage A is accepted.

Simulate create, modify, append, rename, and delete requests against fixture files. Each operation remains independently scoped.

#### Stage C: Operating-System Boundary Experiment

Consider read-only mounts, ACLs, separate users, or containers only after a separate governance proposal, mandatory advisory review, and User Decision.

Stage C is outside the first local prototype.

### 7.2 Required Checks

The future wrapper should validate:

- canonical project root
- canonical requested path
- path classification
- runtime identity
- task ID
- decision ID
- allowed and forbidden paths
- operation type
- capability expiry
- symlink destination
- parent directory permissions
- cross-project boundary
- instance mode status

### 7.3 Fixture Path Classes

At minimum, fixtures should model:

- `.codex-coordination/inbox/`
- `.codex-coordination/outbox/`
- `.codex-coordination/reviews/`
- `.codex-coordination/decisions/`
- `.codex-coordination/templates/`
- `docs/`
- `scripts/`
- `.githooks/`
- `agents/`
- `skills/`
- business project code
- instance-local `.codex-coordination/`

### 7.4 Expected Boundaries

The simulation must demonstrate:

- Codex cannot write decisions.
- External Advisory cannot write project code.
- Automation cannot write reviews or decisions.
- ChatGPT Review cannot write Codex results.
- ACOS core paths are protected by default.
- Instance-local coordination is non-core by default.
- A task and applicable decision are required for writes.
- Filesystem decisions do not replace ChatGPT Review or User Decision.

## 8. Git Operation Gate Simulation

### 8.1 Fixture Repository Only

The first Git simulation should use a temporary fixture repository.

It must not use the live ACOS repository or a real project instance for mutating tests.

### 8.2 Operation State Machine

The future Git gate should model:

```text
INSPECT_AUTHORIZED
        -> inspect result
TEST_AUTHORIZED
        -> test result
EDIT_AUTHORIZED
        -> edit result
STAGE_AUTHORIZED
        -> exact staged manifest
COMMIT_AUTHORIZED
        -> commit result
PUSH_AUTHORIZED
        -> local fixture remote update
RELEASE_AUTHORIZED
        -> simulated release only
```

Each transition requires a separate authorization event and review of the prior result.

### 8.3 Stage Simulation

Validate that:

- only exact paths may be staged
- `git add .` and `git add -A` requests are denied
- unrelated dirty paths remain unchanged
- existing staged files trigger comparison or blocking
- deleted and renamed paths require explicit manifest entries

### 8.4 Commit Simulation

Validate that commit is denied when:

- ChatGPT Review authorization is missing
- mandatory advisory review is incomplete
- staged paths differ from authorization
- the message differs from authorization
- hook bypass is requested
- content is modified during the commit task

### 8.5 Push Simulation

The first push simulation should target a local bare fixture remote only, after separate approval of that simulation stage.

Validate that push is denied when:

- push authorization is missing
- the commit is unreviewed
- remote or branch differs
- force is requested
- pull, rebase, or merge would be required
- the authorization was already consumed

### 8.6 Release Simulation

The first prototype should model release as an authorization decision without publishing any artifact.

No package registry, hosted release, deployment target, or production environment is used.

## 9. Audit Trail Simulation

### 9.1 Planned Record Format

A future prototype may use versioned JSON Lines fixture records for local testing.

This plan does not select the production storage format.

Each fixture event should include the required TASK_044 fields, including:

- event ID and type
- timestamp
- project and runtime identity
- artifact and task references
- decision and advisory references
- authorized and staged paths
- commit and push references
- result and violation data
- source artifact hash

### 9.2 Planned Append-Only Behavior

The simulation should:

- append new records
- reject in-place corrections
- append correction events
- compute a previous-event hash and event hash
- detect sequence gaps or duplicate event IDs
- separate ordinary append from audit administration

Hash chaining provides tamper evidence, not authorization.

### 9.3 Required Event Scenarios

The future prototype should emit or model:

- `TASK_CREATED`
- `RESULT_RECEIVED`
- `BLOCKED_RESULT_RECEIVED`
- `ADVISORY_REVIEW_REQUESTED`
- `ADVISORY_REVIEW_RECEIVED`
- `ADVISORY_REVIEW_CONSUMED`
- `REVIEW_ACCEPTED`
- `REVIEW_REWORK`
- `REVIEW_BLOCKED`
- `DECISION_ISSUED`
- `USER_DECISION_RECEIVED`
- `FILES_STAGED`
- `COMMIT_CREATED`
- `PUSH_AUTHORIZED`
- `PUSH_COMPLETED`
- `VIOLATION_DETECTED`
- `OVERRIDE_GRANTED`
- `AUDIT_WRITE_FAILED`
- `TAMPER_EVIDENCE_DETECTED`

### 9.4 Audit Writer Failure

If a required event cannot be appended, a future mutating simulation must fail closed.

The prototype should model a fallback `AUDIT_WRITE_FAILED` signal without claiming that the primary event was recorded successfully.

## 10. External Advisory Review Simulation

### 10.1 No Automatic Provider Invocation

The first prototype must not call an external advisory provider.

Use manually prepared, non-executing fixture artifacts to simulate:

- valid advisory review
- missing advisory review
- malformed advisory review
- identity-spoofed advisory review
- wrong receiver
- direct advisory-to-Codex route
- advisory provider unavailable

### 10.2 Trigger Classification

The advisory gate should classify TASK_046 levels:

- Level 0: not required
- Level 1: optional
- Level 2: mandatory

Ambiguous governance work should be Level 2.

### 10.3 Mandatory Completion

A mandatory advisory gate is complete only when:

1. ChatGPT Review requested advisory review.
2. A valid `ADVISORY REVIEW` returned to ChatGPT Review.
3. ChatGPT Review recorded disposition of material findings.
4. The final decision references the advisory review or valid override.

Receipt alone is insufficient.

### 10.4 Unavailability

The simulation should model:

- blocked
- deferred advisory review
- explicit User Decision override

It must reject silent downgrade from mandatory to optional.

### 10.5 Advisory Authority Boundary

The simulated External Advisory Runtime must never:

- edit files
- execute shell or Git operations
- create task, result, review, or decision artifacts
- authorize commit, push, or release
- route directly to Codex

## 11. User Decision Gate Simulation

### 11.1 Fixture User Decision

The first prototype may use a manually supplied fixture reference representing an actual test decision.

The fixture should include:

- user decision reference
- project
- task
- exact choice or override
- scope
- reason
- risk accepted
- validity window
- remaining forbidden actions
- whether retrospective review remains required

The runtime must not fabricate the user identity.

### 11.2 Decision Validation

The future gate should validate:

- reference exists
- project and task match
- scope covers the requested exception
- decision is unexpired
- decision has not been consumed or revoked
- required reason and risk fields exist
- no secret is embedded

### 11.3 Relationship To ChatGPT Review

User Decision may provide direction, credentials boundary, or bounded override.

The gate must preserve whether ChatGPT Review subsequently issued the ACOS decision. User Decision does not silently replace ChatGPT Review unless the user explicitly suspends ACOS governance for that task.

### 11.4 Negative Tests

The simulation should deny:

- missing user reference
- expired override
- override for another project
- override replay
- scope broader than the decision
- fabricated user decision
- credential value stored in the fixture

## 12. Fail-Closed Behavior

### 12.1 Denial Conditions

The prototype should deny or block when any required element is missing or invalid, including:

- runtime identity
- task
- decision or authorization
- project root
- path manifest
- operation class
- artifact metadata
- advisory review when mandatory
- advisory consumption
- User Decision override when relied upon
- audit append capability
- unexpired capability

### 12.2 Denial Sequence

Future simulation behavior should be:

```text
request
  -> validate identity
  -> validate project and path
  -> validate task and decision
  -> validate advisory or user gate
  -> validate operation state
  -> reserve audit append
  -> allow fixture action OR deny before mutation
  -> append outcome event
  -> route RESULT or BLOCKED RESULT
```

### 12.3 No Broad Fallback

On denial or failure, the prototype must not:

- retry with broader filesystem permissions
- substitute a different runtime identity
- change project root
- stage additional paths
- bypass hooks
- pull, rebase, merge, force push, reset, clean, or stash
- mark missing advisory as optional
- fabricate User Decision
- drop the audit event

### 12.4 Partial Failure

The plan should favor validation before mutation.

If a fixture mutation partially succeeds, the prototype must record the partial result and block further operations. It must not claim atomic rollback unless rollback is actually implemented and verified.

## 13. Prototype Validation Scenarios

The future prototype should execute the scenarios below only in fixture workspaces under separately authorized implementation tasks.

| ID | Scenario | Expected Result |
| --- | --- | --- |
| `P01` | Valid docs-only Codex edit with matching task, decision, and path | Allow fixture edit; create result and audit evidence; no stage implied. |
| `P02` | Codex attempts to create `DECISION` | Deny artifact; record role authority violation. |
| `P03` | ChatGPT Review attempts to create Codex `RESULT` | Deny producer spoofing. |
| `P04` | External Advisory attempts project file edit | Deny write; permit only advisory artifact return path. |
| `P05` | External Advisory routes directly to Codex | Reject routing; require return to ChatGPT Review. |
| `P06` | Automation attempts commit | Deny Git operation. |
| `P07` | Codex targets `.codex-coordination/decisions/` | Deny filesystem write. |
| `P08` | Allowed path uses symlink to protected core path | Resolve canonical target and deny escape. |
| `P09` | Cross-project capability replay | Deny project mismatch. |
| `P10` | Instance-local `.codex-coordination/` treated as ACOS core | Deny authority assumption absent local-mode User Decision. |
| `P11` | `git add .` requested | Deny blanket staging. |
| `P12` | Staged manifest contains unrelated dirty file | Reject staging or block before commit. |
| `P13` | Commit requested without ChatGPT Review authorization | Deny commit. |
| `P14` | Push requested under commit authorization | Deny push; require separate authorization. |
| `P15` | Force push requested | Deny operation. |
| `P16` | Release requested as ordinary push | Deny and require independent release boundary. |
| `P17` | Level 2 task has no advisory review | Block final acceptance and commit authorization. |
| `P18` | Valid advisory received but not consumed | Keep mandatory gate incomplete. |
| `P19` | Advisory unavailable with no override | Block or defer according to TASK_046. |
| `P20` | Valid bounded User Decision override | Permit only the stated exception; audit reason and expiry. |
| `P21` | Expired or replayed User Decision override | Deny operation. |
| `P22` | Audit append fails before mutation | Deny mutating action and emit fallback failure evidence when possible. |
| `P23` | Audit event hash chain mismatch | Record tamper evidence and block lifecycle. |
| `P24` | Runtime capability used after session end | Deny replay. |
| `P25` | Provider label changes but runtime profile stays constant | Preserve identical authority. |
| `P26` | Multiple dirty workstreams with exact reviewed manifest | Allow only separately authorized fixture staging; preserve other paths. |

### 13.1 Scenario Evidence

Each scenario should produce:

- input fixture manifest
- expected result
- observed result
- relevant audit events
- changed fixture paths
- Git fixture state when applicable
- policy references
- pass, fail, or blocked conclusion

### 13.2 Exit Criteria

The first prototype phase should not advance unless:

- all high-risk negative scenarios fail closed;
- role identity spoofing is rejected;
- protected path escapes are rejected;
- Git operation grants remain separate;
- mandatory advisory gates cannot be skipped;
- User Decision overrides remain bounded;
- audit failures block mutation;
- instance boundaries remain distinct; and
- no test requires a real provider, credential, remote, or business project.

## 14. Migration Path From v1.5 To v2.0

Migration should be incremental, reversible where possible, and evidence-driven.

### Phase 0: Baseline Snapshot

Document existing v1.5 behavior:

- artifact linter results
- pre-commit hook behavior
- current task lifecycle
- current manual review and Git authorization
- known false positives and gaps

No behavior changes.

### Phase 1: Policy And Fixture Alignment

Create fixture cases from TASK_040–044 and TASK_046.

Validate expected allow and deny outcomes manually. No runtime enforcement.

### Phase 2: Shadow Decision Simulation

Run a future decision engine in dry-run mode against fixture requests.

The engine reports allow or deny but cannot mutate files or Git state.

Compare its result with manual ChatGPT Review.

### Phase 3: Temporary Fixture Enforcement

Allow bounded mutations only inside disposable fixture workspaces.

Keep real ACOS and instance repositories read-only to the prototype.

### Phase 4: ACOS Read-Only Observation

Observe real ACOS tasks in shadow mode without controlling execution.

Record differences between policy decisions and actual approved workflow.

### Phase 5: Selected ACOS Operation Gate

After governance approval and mandatory advisory review, consider gating one low-risk operation class in the ACOS repository.

Example candidates may include read-only artifact validation or exact staged-manifest verification. No operation is selected by this plan.

### Phase 6: Controlled Instance Validation

Only after ACOS core validation, test read-only behavior against a dedicated fixture instance or explicitly authorized project instance.

Do not migrate business workflows or copy ACOS core into the instance.

### Phase 7: Stronger Runtime Isolation Evaluation

Evaluate separate users, ACLs, read-only mounts, or containers under a new governance proposal.

This phase requires its own threat model, mandatory advisory review, User Decision, implementation tasks, and rollback plan.

### 14.1 Migration Gates

Each phase requires:

- prior phase evidence
- ChatGPT Review
- mandatory External Advisory Review when TASK_046 applies
- User Decision for material risk or external impact
- explicit implementation task
- rollback or disable procedure
- no unresolved high-severity boundary failure

### 14.2 Rollback And Disable Principles

Future prototype controls should support disabling the prototype without removing v1.5 linter and hook protections.

Rollback must not:

- rewrite audit history
- delete user work
- broaden runtime permissions
- bypass pending review
- convert a denied operation into approval

## 15. Relationship To TASK_040, TASK_041, TASK_042, TASK_043, TASK_044, And TASK_046

```text
TASK_040 -> runtime isolation architecture
TASK_041 -> runtime role permission matrix
TASK_042 -> filesystem permission model
TASK_043 -> Git operation separation policy
TASK_044 -> audit trail specification
TASK_046 -> external advisory trigger policy
TASK_045 -> local runtime prototype plan
```

TASK_045 applies the upstream documents as follows:

- TASK_040 supplies the runtime isolation architecture and four runtime identities.
- TASK_041 supplies artifact, operation, and directory permissions.
- TASK_042 supplies path classification, canonical roots, protected core, and instance boundaries.
- TASK_043 supplies independent inspect, test, edit, stage, commit, push, and release gates.
- TASK_044 supplies auditable events, fields, append-only history, tamper evidence, and failure recording.
- TASK_046 requires mandatory advisory review for this prototype plan and later runtime enforcement work.

TASK_045 does not override or amend those documents.

### 15.1 TASK_045 Advisory Gate

This plan is a Level 2 mandatory advisory task.

Required flow:

```text
Codex docs draft
        -> ChatGPT Review preliminary acceptance
        -> External Advisory Reviewer ADVISORY REVIEW
        -> ChatGPT Review consumes material findings
        -> ChatGPT Review DECISION
        -> commit authorization, if accepted
```

This draft and its Codex `RESULT` do not satisfy the advisory gate.

## 16. Non-Implementation Boundary

TASK_045 creates documentation only.

It does not create or modify:

- runtime launcher
- filesystem permission wrapper or sandbox
- Git operation wrapper
- audit record writer or logger
- advisory review gate
- User Decision gate
- instance boundary checker
- artifact validation adapter
- shell script
- executable code
- runtime profile
- capability manifest
- fixture workspace
- temporary Git repository
- local bare remote
- filesystem ACL
- operating-system user
- container configuration
- Dockerfile
- `docker-compose.yml`
- API key, credential, or provider configuration
- `scripts/acos-linter.py`
- `.githooks/pre-commit`
- ACOS v1.5 governance rules
- agents or skills
- project-instance files

It does not execute:

- external model calls
- API calls
- filesystem permission changes
- Git add
- Git commit
- Git push
- Git pull
- release operations
- prototype simulation

Any implementation requires a new bounded task, TASK_046 mandatory advisory review where applicable, ChatGPT Review decision, and operation-specific authorization.

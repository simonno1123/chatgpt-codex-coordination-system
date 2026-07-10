# ACOS v2.0 Git Operation Separation Policy

## 1. Scope And Purpose

This document defines the ACOS v2.0 policy for separating Git operations by authority, runtime identity, lifecycle state, repository scope, and audit evidence.

The policy prevents a runtime from turning one permission into an unreviewed chain of broader operations.

The central rule is:

```text
diff / status / log
        !=
test
        !=
edit
        !=
stage
        !=
commit
        !=
push
        !=
release
```

Each operation is evaluated independently. Authority for one operation does not imply authority for the next.

This policy is documentation only. It does not implement a Git wrapper, change hooks, execute Git operations, or modify ACOS v1.5 rules.

## 2. Git Operation Classes

### 2.1 Inspect: Diff, Status, And Log

Inspection includes read-only repository operations such as:

- status inspection
- unstaged diff inspection
- staged diff inspection
- commit history inspection
- branch-name inspection
- remote inspection
- object and tree inspection

Inspection must not update repository state, fetch remote state, create lock files beyond normal read behavior, or modify the working tree.

Codex inspection requires a valid `TASK` and applicable `DECISION` or explicit authorization for the repository and inspection scope.

Examples:

```text
git status --short --branch
git diff -- <authorized-path>
git diff --cached --name-only
git log --oneline -5
git branch --show-current
git remote -v
```

Network operations such as fetch, pull, or remote API calls are not inspection under this policy.

### 2.2 Test

Test includes commands that validate the project or artifact without intentionally changing tracked source.

Tests may still create temporary, cache, coverage, build, or log files. A valid task must identify or constrain those side effects.

Codex test execution requires a valid `TASK` and applicable `DECISION` or explicit authorization.

Test authority does not imply edit, stage, commit, push, or release authority.

### 2.3 Edit

Edit includes creating, modifying, moving, renaming, or deleting project files.

Edit authority must be constrained by a valid `TASK` and applicable `DECISION` or explicit authorization, including exact project and path scope.

An edit result must return to ChatGPT Review before staging or commit can proceed.

### 2.4 Stage

Stage changes the Git index.

Staging is a repository mutation and requires explicit, path-limited authority. It must never be inferred from edit authority.

Stage authority must identify:

- repository
- branch
- allowed path manifest
- expected additions, modifications, deletions, or renames
- excluded workstreams
- related review and decision

### 2.5 Commit

Commit creates a repository object and advances a branch reference.

Commit requires explicit ChatGPT Review authorization after the staged scope has been verified. Commit authority must not modify file contents.

Commit authority does not imply push authority.

### 2.6 Push

Push changes a configured remote reference.

Push requires authorization separate from edit, stage, and commit. It must identify the remote, branch, and reviewed commit set.

Push authority does not imply release authority.

### 2.7 Release

Release is a higher-authority operation that may include:

- creating or pushing a version tag
- publishing a package or artifact
- creating a hosted release
- deploying a build
- promoting an environment
- updating a release channel

Release is not an ordinary push. It requires an independent release decision, destination, immutable commit reference, validation evidence, and rollback or recovery expectations.

## 3. Runtime-To-Git Operation Matrix

Permission values:

- `read-only`: may inspect local repository state.
- `task-scoped`: requires a valid task and bounded scope.
- `decision-gated`: requires explicit ChatGPT Review decision or authorization.
- `separate authorization`: cannot be inferred from the preceding operation.
- `forbidden`: operation must be denied.
- `authorization only`: may authorize but must not execute the Git operation.

| Operation | ChatGPT Review Runtime | Codex Executor Runtime | External Advisory Runtime | Automation Runtime |
| --- | --- | --- | --- | --- |
| diff / status / log | review evidence only; no direct Git execution | task-scoped and decision-gated read-only | forbidden | task- or policy-scoped read-only |
| test | review evidence only; no direct test execution | task-scoped and decision-gated | forbidden | task- or policy-scoped |
| edit | authorization only | task-scoped and decision-gated | forbidden | forbidden |
| stage | authorization only | decision-gated and path-limited | forbidden | forbidden |
| commit | explicit commit authorization only | decision-gated with verified staged manifest | forbidden | forbidden |
| push | explicit push authorization only | separate authorization after commit review | forbidden | forbidden |
| release | explicit release authorization only | separate release authorization; not implied by push | forbidden | forbidden |

### 3.1 Matrix Constraints

1. Codex Executor is the only current runtime that may execute authorized edit, stage, commit, push, or release operations.
2. External Advisory Runtime must not execute any Git operation.
3. Automation Runtime must not edit, stage, commit, push, or release.
4. ChatGPT Review owns authorization and review, not Git execution.
5. A provider identity does not grant Git authority.
6. No runtime may approve its own Git result.
7. No runtime may use a successful lower-level operation as evidence of authority for a higher-level operation.

## 4. Stage, Commit, And Push Separation

### 4.1 Independent Grants

The following are independent permissions:

```text
edit permission
stage permission
commit permission
push permission
release permission
```

Each permission must be explicitly named and evaluated through a separate authorization event. One artifact may describe the planned sequence, but it must not activate more than one mutating Git operation at the same time. Completion and review of the current operation are required before the next grant becomes active. No permission is implied by adjacency or convenience.

### 4.2 Required Lifecycle

The normal lifecycle is:

```text
TASK + applicable authorization
        -> Codex edit or test
        -> RESULT
        -> ChatGPT Review
        -> mandatory ADVISORY REVIEW when TASK_046 applies
        -> ChatGPT Review DECISION
        -> path-limited stage authorization
        -> staged-scope verification
        -> explicit commit authorization
        -> commit RESULT
        -> ChatGPT Review
        -> separate push authorization
        -> push RESULT
        -> ChatGPT Review
```

Release adds a separate release review and authorization after the reviewed commit or push state.

### 4.3 Prohibited Chain Collapse

No runtime may perform:

```text
edit -> stage -> commit -> push
```

as one unreviewed or implicitly authorized chain.

No task instruction such as "finish everything" or "sync changes" overrides this separation unless the artifact explicitly enumerates every operation and all required independent reviews and decisions already exist.

## 5. Commit Authorization Rules

### 5.1 Preconditions

Commit authorization requires:

1. The project and current branch are known.
2. The relevant edit task is complete.
3. Codex has produced a valid `RESULT` or `BLOCKED RESULT`.
4. ChatGPT Review has reviewed the actual change scope.
5. Mandatory advisory review has been completed when TASK_046 classifies the change as Level 2, or an explicit User Decision override is recorded.
6. ChatGPT Review has produced explicit commit authorization.
7. The allowed files are listed exactly or represented by an approved immutable manifest.
8. The staged file list matches the approved list.
9. The staged diff contains no unrelated workstream.
10. The commit message is specified.
11. Any required test or validation result is available.
12. Pre-commit validation is expected to run normally.

### 5.2 Commit Authorization Content

A commit authorization must identify:

- task ID
- review or decision ID
- advisory artifact ID or override ID when required
- repository root
- branch
- exact staged paths
- expected change types
- exact commit message
- forbidden paths
- whether hooks must run
- expected result receiver

### 5.3 Commit-Time Verification

Before commit, Codex Executor must verify:

```text
git diff --cached --name-only
git diff --cached --stat
```

The actual staged diff should also be reviewed when file content or rename behavior is material.

If the staged file list differs from authorization, commit must stop.

### 5.4 Commit Restrictions

Commit authorization does not authorize:

- modifying file content
- adding another file to the index
- changing the commit message
- bypassing hooks
- amending an earlier commit
- changing branches
- rebasing or merging
- pushing
- tagging
- releasing

An empty commit is forbidden unless a separate task explicitly requires and justifies it.

## 6. Push Authorization Rules

### 6.1 Separate Authorization

Push requires a new authorization after the commit result has been reviewed.

Commit authorization must never be interpreted as push authorization.

### 6.2 Push Preconditions

Before push, Codex Executor must verify:

1. The repository root is correct.
2. The branch is correct.
3. The remote URL is the expected destination.
4. The worktree and staged state match the push task's expectations.
5. The local branch contains only the reviewed commit set to be pushed.
6. The local branch is not behind the target remote branch based on known local remote state.
7. No force push is required.
8. The push authorization names the remote and branch.
9. The authorization has not expired or already been consumed.

### 6.3 Push Scope

Push authorization must identify:

- remote name and URL
- local branch
- remote branch
- commit hash or contiguous reviewed commit range
- expected remote update
- whether tags are excluded
- forbidden flags
- next receiver

### 6.4 Push Failure

If push is rejected or requires pull, fetch, rebase, merge, force, credential changes, or remote modification, Codex must stop and return `BLOCKED RESULT`.

Push failure does not authorize corrective repository mutation.

## 7. Release Operation Boundary

Release is governed separately from push.

Release authorization should require:

- explicit User Decision when human direction or production impact is involved
- ChatGPT Review decision
- immutable source commit
- target version or release identifier
- destination registry, service, or release channel
- validation evidence
- artifact inventory
- release notes or changelog expectations
- rollback or recovery plan
- credential boundary
- audit destination

The planned Release Runtime described in TASK_041 is not active. This policy does not activate it.

Until a release runtime is separately approved and implemented, release execution remains a distinct, explicitly authorized Codex operation and must never be inferred from ordinary push authority.

## 8. Forbidden Git Patterns

The following patterns are forbidden unless a separate, explicit, risk-reviewed maintenance task authorizes the exact operation. Several remain prohibited under normal ACOS operation even when convenient.

### 8.1 Blanket Staging

```text
git add .
git add -A
git add --all
git add -u
```

Reason: these commands may stage unrelated modified, deleted, generated, or untracked files.

### 8.2 Implicit Commit Staging

```text
git commit -a
git commit --all
```

Reason: commit and stage permissions are collapsed and the reviewed manifest can be bypassed.

### 8.3 Force Or Broad Remote Mutation

```text
git push --force
git push --force-with-lease
git push --mirror
git push --delete
```

Reason: these operations may rewrite or remove remote history and require specialized authorization beyond ordinary push.

### 8.4 Destructive Local Mutation

```text
git reset --hard
git clean -fd
git clean -fdx
```

Reason: these operations may destroy tracked or untracked user work.

### 8.5 Review Or Hook Bypass

Examples:

- `git commit --no-verify`
- `git push --no-verify`
- amending without explicit authorization
- changing the authorized commit message
- manually altering the index after staged-scope verification

Reason: validation evidence no longer matches the resulting commit or push.

### 8.6 Workflow Violations

Forbidden workflow patterns include:

- unreviewed `edit -> commit -> push`
- staging unrelated dirty files
- pushing local commits that were not reviewed
- treating a clean worktree as commit or push authority
- treating an advisory review as commit or push authority
- treating a Codex `RESULT` as self-acceptance
- pulling, rebasing, or merging to make a rejected push succeed without a new task
- switching branches to avoid task scope
- changing remote configuration during a push task
- stashing user changes to make a worktree appear clean without authorization

## 9. Path-Limited Staging Requirements

### 9.1 Exact Path Staging

Staging must use explicit path-limited commands, for example:

```text
git add -- docs/example.md
git add -- path/to/file-a path/to/file-b
```

The `--` separator should be used to prevent path names from being interpreted as command options.

### 9.2 Approved Manifest

Before staging, the authorization must provide an approved path manifest.

The manifest should identify:

- path
- expected status: added, modified, deleted, renamed, or copied
- workstream or task ownership
- whether the path is tracked or untracked
- whether deletion or rename is intentional

### 9.3 Directory Pathspecs

A directory pathspec may be used only when:

- the task explicitly authorizes the entire bounded directory;
- the pre-stage file inventory is reviewed;
- excluded paths are identified; and
- post-stage verification confirms the exact file manifest.

Directory authorization must not silently include generated, local-history, secret, or unrelated files.

### 9.4 Existing Staged State

If files are already staged before a commit task begins:

- compare the staged set with the authorized set;
- do not assume the staged files belong to the current task;
- do not unstage or overwrite them without authorization; and
- return `BLOCKED RESULT` when ownership or scope is unclear.

### 9.5 Post-Stage Verification

After staging and before commit, verify at minimum:

```text
git diff --cached --name-only
git diff --cached --stat
git status --short
```

The verified staged manifest becomes part of commit audit evidence.

## 10. Dirty Worktree Handling

### 10.1 Classification Before Mutation

When a dirty worktree contains more than one workstream, classify changes before staging or committing.

Classification should distinguish:

- modified tracked files
- deleted tracked files
- added or untracked files
- renamed or moved files
- generated output
- local coordination history
- user-owned changes
- task-owned changes
- unknown-origin changes

### 10.2 Workstream Separation

Each changed path should be mapped to:

- task or workstream
- owner or source, when known
- review status
- intended commit batch
- excluded batch
- unresolved risk

Unknown-origin changes must be treated as user-owned and preserved.

### 10.3 Limited Commit In A Dirty Worktree

A limited commit may proceed only when ChatGPT Review explicitly accepts the dirty-worktree classification and the approved path manifest can be isolated safely.

Unrelated changes must remain unstaged and unchanged.

If isolation cannot be verified, the commit is blocked.

### 10.4 Prohibited Cleanup

Dirty worktree handling does not authorize:

- reset
- clean
- checkout or restore of user changes
- stash
- delete
- move
- overwrite
- blanket staging

The goal is classification and isolation, not cosmetic cleanliness.

### 10.5 Push With A Dirty Worktree

Push authorization should normally require a clean worktree and empty index. If a push is allowed while unrelated local changes remain, the authorization must explicitly record that condition and verify that the reviewed commit set is unaffected.

## 11. Advisory Review Requirement For Git Policy Changes

TASK_046 classifies Git operation separation policy changes as Level 2 mandatory advisory review.

Therefore, this TASK_043 draft must follow:

```text
Codex docs draft
        -> ChatGPT Review
        -> External Advisory Reviewer ADVISORY REVIEW
        -> ChatGPT Review consumes material findings
        -> ChatGPT Review DECISION
        -> commit authorization, if accepted
```

The draft and this Codex `RESULT` do not satisfy mandatory advisory review.

The External Advisory Reviewer:

- performs read-only analysis;
- produces `ADVISORY REVIEW` only;
- returns the opinion to ChatGPT Review;
- performs no shell or Git operation;
- does not authorize stage, commit, push, or release; and
- does not route directly to Codex Executor.

If advisory capability is unavailable, the task must use the TASK_046 outcomes: `BLOCKED`, explicit User Decision override, or deferred advisory review with the reason recorded in the decision.

## 12. Violation Handling

Git authority violations must fail closed.

Expected handling:

1. Stop before the unauthorized operation.
2. Preserve the worktree, index, branch, and remote configuration.
3. Do not retry with broader flags or alternate commands.
4. Do not pull, rebase, merge, reset, clean, stash, switch branches, or change remotes as an implicit remedy.
5. Record the attempted operation, runtime identity, repository, branch, path set, and authorization state.
6. Produce `BLOCKED RESULT` or a failed `RESULT` as appropriate.
7. Route the result to ChatGPT Review.
8. Require a new decision before changing scope or attempting a different mutation.

Examples:

| Violation | Expected Handling |
| --- | --- |
| `git add .` requested for a limited commit | Deny blanket staging and require an exact path manifest. |
| Unrelated file appears in the staged set | Stop before commit, preserve the index, and return to ChatGPT Review. |
| Commit attempted without accepted review | Deny commit and record the missing decision. |
| Push attempted under commit authorization | Deny push and require separate push authorization. |
| Push requires force or pull | Stop and return `BLOCKED RESULT`; do not repair automatically. |
| Automation attempts commit | Deny operation because Automation Runtime has no commit authority. |
| External Advisory Runtime invokes Git | Deny operation and treat the advisory runtime boundary as violated. |
| Release attempted as an ordinary push | Deny release and require independent release authorization. |

## 13. Audit Requirements

Every Git operation decision should record:

- event ID
- task ID
- review and decision ID
- advisory artifact or override ID when required
- runtime identity
- repository root
- branch
- remote name and URL when applicable
- HEAD before the operation
- HEAD after the operation
- operation class
- exact command class without secrets
- allowed path manifest
- actual staged path manifest
- dirty worktree classification
- commit hash and message
- push commit range and target
- release identifier and destination when applicable
- hook and linter result
- allow, deny, blocked, failed, or completed result
- timestamp
- next receiver

Audit records do not grant Git authority and do not replace ChatGPT Review, User Decision, or mandatory advisory review.

## 14. Relationship To TASK_040, TASK_041, TASK_042, And TASK_046

```text
TASK_040 -> runtime isolation architecture
TASK_041 -> runtime role permission matrix
TASK_042 -> filesystem permission model
TASK_046 -> external advisory trigger policy
TASK_043 -> Git operation separation policy
```

TASK_043 applies those upstream rules as follows:

- TASK_040 supplies the independent Git operation categories and chain-separation principle.
- TASK_041 supplies runtime-level Git authority and default-deny behavior.
- TASK_042 supplies canonical repository roots, path-limited write scope, and filesystem boundaries.
- TASK_046 requires mandatory advisory review before TASK_043 can receive final governance acceptance and commit authorization.

TASK_043 does not override or amend those documents.

## 15. Non-Implementation Boundary

TASK_043 creates documentation only.

It does not create or modify:

- Git wrapper
- shell script
- runtime code
- artifact linter
- pre-commit hook
- repository configuration
- remote configuration
- branch configuration
- filesystem permissions
- container configuration
- Dockerfile
- `docker-compose.yml`
- API keys or credentials
- ACOS v1.5 governance rules
- agents or skills
- project-instance files

It does not execute:

- Git add
- Git commit
- Git push
- Git pull
- Git reset
- Git clean
- release operations

Implementation or enforcement requires separate tasks, mandatory advisory review when applicable, ChatGPT Review decisions, and operation-specific authorization.

## 16. Summary

ACOS v2.0 treats Git as a sequence of independent authority transitions rather than one developer convenience workflow.

```text
Inspect
  -> Test
  -> Edit
  -> Review
  -> Advisory Review when mandatory
  -> Stage exact paths
  -> Verify staged manifest
  -> Commit under explicit authorization
  -> Review commit result
  -> Push under separate authorization
  -> Release only under a higher independent boundary
```

No runtime may collapse this chain, stage unrelated work, push unreviewed commits, or treat its own result as acceptance.

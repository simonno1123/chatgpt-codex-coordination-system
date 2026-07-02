# Codex Workflow Manual

## 1. Purpose

This project uses a controlled ChatGPT-Codex coordination workflow.

ChatGPT acts as the planner, reviewer, and decision maker. Codex acts as the controlled executor. The goal is to make repeated work stable, convenient, and auditable without requiring the user to restate the whole background for every task.

Current scope:

- ChatGPT-Codex coordination agents
- Coordination skills
- File-based task protocol
- Git-based review and rollback

Out of current scope unless explicitly authorized:

- Any capability that is not necessary for ChatGPT-Codex coordination.
- Any file, directory, integration, workflow, agent, skill, template, configuration, or automation that serves non-coordination work.

## 2. Standard Workflow

The standard workflow is:

```text
ChatGPT plans and writes a task
  -> .codex-coordination/inbox/
Codex executes the task
  -> .codex-coordination/outbox/
ChatGPT reviews the result
  -> .codex-coordination/decisions/
Next task is created only after review
```

Short form:

```text
inbox -> outbox -> decisions
```

Codex must not automatically move to the next task after reporting DONE. ChatGPT or the user must explicitly approve the next step.

## 3. Roles

### ChatGPT

ChatGPT is responsible for:

1. Understanding the user goal.
2. Splitting work into small executable tasks.
3. Writing Codex task instructions.
4. Defining allowed files and forbidden actions.
5. Reviewing Codex DONE reports.
6. Handling Codex BLOCKED reports.
7. Deciding ACCEPTED, REWORK, BLOCKED, or CANCELLED.
8. Maintaining project direction and scope.

### Codex

Codex is responsible for:

1. Creating authorized files.
2. Modifying authorized files.
3. Running authorized commands.
4. Reporting created, modified, and deleted files.
5. Reporting verification steps and results.
6. Reporting risks.
7. Stopping with BLOCKED when scope or safety is unclear.

Codex must not:

1. Decide project direction.
2. Expand task scope.
3. Modify unauthorized files.
4. Delete files unless explicitly authorized.
5. Stage or commit files unless explicitly authorized.
6. Add historical untracked files unless explicitly authorized.
7. Start non-coordination work unless explicitly authorized.

## 4. Task Types

All future Codex tasks should use one of these task types.

### CREATE

Creates new files only.

Examples:

- CREATE_AGENT
- CREATE_SKILL
- CREATE_TEMPLATE
- CREATE_PROTOCOL_FILE
- CREATE_WORKFLOW_MANUAL

Default rule: do not modify existing files.

### UPDATE

Modifies explicitly listed files only.

Examples:

- UPDATE_PROJECT_BRIEF
- UPDATE_TASKS
- UPDATE_SKILL
- UPDATE_TEMPLATE

Default rule: only the files named in the task may be modified.

### REVIEW

Reads files, summarizes state, or runs read-only checks.

Examples:

- REVIEW_GIT_STATUS
- REVIEW_PROJECT_TREE
- REVIEW_FILE_CONTENT
- REVIEW_SKILL_CONTENT

Default rule: no file modifications.

### GIT

Runs narrowly scoped Git operations.

Examples:

- STAGE_SELECTED_FILES
- COMMIT_SELECTED_FILES
- CHECK_DIFF
- CHECK_LOG

Default rule: never use full-repository staging.

## 5. Task Numbering

Use sequential task numbers:

```text
TASK_001
TASK_002
TASK_003
```

Use letter suffixes for scoped fixes:

```text
TASK_011A
TASK_011B
```

Use explicit prefixes for rework or decisions:

```text
REWORK_TASK_021
DECISION_TASK_021
```

## 6. File Naming

Use these paths and names for protocol files.

### Inbox

```text
.codex-coordination/inbox/TASK_021_CREATE_XXX.md
```

### Outbox

```text
.codex-coordination/outbox/TASK_021_RESULT.md
.codex-coordination/outbox/TASK_021_BLOCKED.md
```

### Decisions

```text
.codex-coordination/decisions/TASK_021_DECISION.md
```

### Logs

```text
.codex-coordination/logs/TASK_021_TEST.log
```

## 7. Codex Task Structure

Each Codex task should include:

1. Task background.
2. Task goal.
3. Allowed scope.
4. Forbidden actions.
5. Requirements.
6. Acceptance criteria.
7. BLOCKED rules.
8. DONE report format.

The task must be small enough to review with `git diff` and `git status`.

## 8. DONE Report Format

Codex should report completed work with this structure:

```markdown
# Codex Execution Result

## 1. Status

DONE

## 2. Summary

## 3. Files Created

## 4. Files Modified

## 5. Files Deleted

## 6. Commands Run

## 7. Verification Method

## 8. Test Results

## 9. Risks

## 10. Suggested Next Step
```

DONE means Codex finished execution. It does not mean ChatGPT accepted the result.

## 9. BLOCKED Report Format

Codex should stop and report BLOCKED when it cannot proceed safely.

```markdown
# Codex Execution Blocker

## 1. Current Task

## 2. Completed Work

## 3. Blocker Description

## 4. Related Files or Commands

## 5. Options

### Option A

### Option B

### Option C

## 6. Codex Preliminary Assessment

## 7. Decision Needed from ChatGPT
```

## 10. ChatGPT Review Format

ChatGPT should review Codex output and choose one result:

```text
ACCEPTED
REWORK
BLOCKED
CANCELLED
```

The review should check:

1. Whether the goal was completed.
2. Whether only authorized files were changed.
3. Whether files were deleted.
4. Whether forbidden actions occurred.
5. Whether verification was run.
6. Whether risks remain.
7. Whether the next action is safe.

## 11. Git Rules

Git operations must be narrow and explicit.

Allowed only when a task explicitly authorizes them:

```text
git status --short
git diff -- <file>
git diff --cached --name-only
git diff --cached --stat
git add <explicit-file>
git commit -m "<explicit-message>"
git log --oneline -n
```

Forbidden by default:

```text
git add .
git add -A
git add *
git reset
git clean
git push
git remote add
git remote remove
git remote set-url
```

Historical untracked files must not be staged unless a task explicitly lists them.

## 12. Safety Rules

These rules apply to every task unless explicitly overridden:

1. Do not modify unauthorized files.
2. Do not delete files.
3. Do not create non-coordination modules.
4. Do not add dependencies.
5. Do not write real API keys, tokens, passwords, or credentials.
6. Do not connect external services unless explicitly authorized.
7. Do not run destructive commands.
8. Do not use full-repository Git staging.
9. Stop with BLOCKED when scope is unclear.
10. Wait for ChatGPT review after DONE.

## 13. Daily Usage Examples

Ask ChatGPT to create a Codex task:

```text
Generate a Codex CREATE task to add a workflow note. Only allow creating one file.
```

Ask ChatGPT to review a result:

```text
Review this Codex DONE report and decide ACCEPTED or REWORK.
```

Ask ChatGPT to handle a blocker:

```text
Codex returned BLOCKED for TASK_021. Decide the next safe instruction.
```

Ask ChatGPT to create an inbox task:

```text
Write this as an inbox task using the coordination protocol.
```

Ask Codex to run a narrow Git step:

```text
Only stage CODEX_WORKFLOW.md and do not commit.
```

## 14. Current Operating Principle

The current project stage is complete enough for repeated coordination use:

- The coordination agent and skills exist.
- The protocol folders exist.
- The minimal flow test was completed and committed.
- Git baseline and line ending rules exist.

Future work should improve convenience and automation without weakening the control model.

## 15. Standard General Coordination Scope

This project is the Standard General ChatGPT-Codex Coordination System.

The core system is responsible for how ChatGPT and Codex collaborate. It is not responsible for non-coordination work.

All future tasks should include a Scope Classification:

```text
CORE
MAINTENANCE
TEST
DOCS
EXTENSION
OUT_OF_SCOPE
```

Only CORE, MAINTENANCE, TEST, and DOCS tasks may directly enter the current core system.

EXTENSION and OUT_OF_SCOPE tasks require explicit user approval and should be handled separately. Codex must not silently add non-coordination capability to the core system.

Refer to `SCOPE_POLICY.md` and `skills/scope_guardian.md` before approving any task that introduces functionality not required for ChatGPT-Codex coordination.

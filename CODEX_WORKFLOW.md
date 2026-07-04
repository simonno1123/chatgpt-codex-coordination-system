# Codex Workflow Manual

## 1. Purpose

This project uses a controlled ChatGPT-Codex coordination workflow.

ChatGPT acts as the planner, reviewer, and decision maker. Codex acts as the controlled executor. The goal is to make repeated work stable, convenient, and auditable without requiring the user to restate the whole background for every task.

This project is an AI Collaboration Operating System (ACOS). ACOS is the primary coordination system for developing any project. A business or domain repository is an ACOS instance or user, not the owner of the core collaboration protocol.

Current scope:

- ChatGPT-Codex coordination agents
- Coordination skills
- File-based task protocol
- Git-based review and rollback
- ACOS task lifecycle and instance boundary rules
- Explicit next handoff target rules

Out of current scope unless explicitly authorized:

- Any capability that is not necessary for ChatGPT-Codex coordination.
- Any file, directory, integration, workflow, agent, skill, template, configuration, or automation that serves non-coordination work.

## 2. ACOS and Business Project Boundary

ACOS owns collaboration mechanics:

1. Task protocols.
2. Task lifecycle rules.
3. Inbox / outbox / decisions / reviews flow.
4. DONE / BLOCKED / REVIEW formats.
5. Task templates.
6. Multi-agent role boundaries.
7. scope_guardian rules.
8. Git safety rules.
9. Project invocation guidance.

Business projects are ACOS instances or users. They own domain capability, implementation, data, and business workflows.

For example, `claude-for-legal-cn` is a China legal capability project. It owns China legal skills, legal MCP integration, legal references, legal workflows, and faithful localization work. It must not be used as the home for ACOS protocol upgrades, reviews, decisions, inbox / outbox lifecycle files, or multi-agent coordination rules unless a task explicitly authorizes local ACOS instance mode.

When a task concerns how AI agents collaborate, how tasks are assigned, how review decisions are recorded, or how protocol lifecycle files work, place it in ACOS. When a task concerns China legal capability, legal skills, legal MCP, legal references, or legal workflows, place it in `claude-for-legal-cn`.

## 3. Standard Workflow

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

## 4. Roles

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

## Temporary Claude Advisory Role

Claude may be used only as a temporary non-executing advisory reviewer or second-opinion source.

The primary workflow remains:

```text
ChatGPT -> Codex -> ChatGPT
```

The role model is:

```text
ChatGPT = planning / judgment / review / final decision
Codex = the only executor
Claude = non-executing advisory reviewer only
```

Claude may only provide:

1. Second opinions on task clarity.
2. Non-binding review comments.
3. Risk observations.
4. Alternative reasoning for ChatGPT to consider.
5. Questions that ChatGPT may decide to use.

Claude must not:

1. Modify files.
2. Create files.
3. Delete files.
4. Run commands.
5. Perform Git operations.
6. Generate directly applicable patches.
7. Act as default or backup executor.
8. Make final project decisions.
9. Replace ChatGPT review.
10. Bypass scope_guardian.
11. Expand approved scope.

Claude output is advisory only. ChatGPT remains responsible for all final ACCEPTED / REWORK / BLOCKED decisions. Codex remains the only execution agent.

## 5. Task Types

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

## 6. Task Numbering

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

## 7. File Naming

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

## 8. Codex Task Structure

Each Codex task should include:

1. Task background.
2. Task goal.
3. Allowed scope.
4. Forbidden actions.
5. Requirements.
6. Acceptance criteria.
7. BLOCKED rules.
8. DONE report format.
9. Next handoff target.

The task must be small enough to review with `git diff` and `git status`.

## 9. Explicit Handoff Target Rule

Every task transition must explicitly state who receives the next step.

Required fields:

```text
Next Handoff Target: <ChatGPT Review | Codex Executor | User Decision | External Advisory Reviewer | None>
Reason: <why this party receives the next step>
```

Use `ChatGPT Review` when Codex reports DONE or BLOCKED and the result needs review, acceptance, rework, or a decision.

Use `Codex Executor` only when ChatGPT has already produced an approved bounded task or rework instruction for Codex to execute.

Use `User Decision` when the next step requires user approval, project direction, credentials, repository choice, or another decision ChatGPT cannot safely make.

Use `External Advisory Reviewer` only for non-executing second opinions. Advisory output is non-binding and must return to ChatGPT Review before it affects execution.

Use `None` only when the workflow is complete and no further action is required.

The handoff target must appear in Codex task instructions, DONE reports, BLOCKED reports, ChatGPT review decisions, rework instructions, and next-step recommendations.

## 10. DONE Report Format

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

## 11. Next Handoff Target

## 12. Reason
```

DONE means Codex finished execution. It does not mean ChatGPT accepted the result.

## 11. BLOCKED Report Format

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

## 8. Next Handoff Target

## 9. Reason
```

## 12. ChatGPT Review Format

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
8. Whether the next handoff target is explicit and correct.

The review should name the next handoff target and reason. ACCEPTED may hand off to `None`, `Codex Executor`, or `User Decision` depending on the next step. REWORK should hand off to `Codex Executor`. BLOCKED should hand off to `User Decision` or `ChatGPT Review` depending on who must resolve the blocker.

## 13. Git Rules

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

## 14. Safety Rules

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
11. Include an explicit next handoff target and reason in task transition outputs.

## 15. Daily Usage Examples

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

## 16. Current Operating Principle

The current project stage is complete enough for repeated coordination use:

- The coordination agent and skills exist.
- The protocol folders exist.
- The minimal flow test was completed and committed.
- Git baseline and line ending rules exist.

Future work should improve convenience and automation without weakening the control model.

## 17. Standard General Coordination Scope

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

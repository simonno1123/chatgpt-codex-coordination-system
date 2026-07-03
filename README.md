# Standard ChatGPT-Codex Coordination System

## 1. Purpose

This project is a standard general-purpose coordination system for ChatGPT-Codex collaboration.

It defines how ChatGPT plans, decomposes, reviews, and decides tasks, while Codex performs bounded execution and reports results.

The system is designed to make ChatGPT-Codex collaboration stable, auditable, and scope-controlled.

## 2. What This System Does

This system provides:

1. ChatGPT-Codex role separation.
2. Bounded Codex task generation.
3. Allowed scope and forbidden action control.
4. DONE report handling.
5. BLOCKED report handling.
6. ChatGPT review decisions.
7. REWORK task generation.
8. Context compression support.
9. Git safety rules.
10. Optional inbox / outbox / decisions workflow.
11. Scope classification and scope guarding.

## 3. What This System Does Not Do

This system does not implement non-coordination functionality.

Any capability that is not necessary for ChatGPT-Codex coordination is outside the current system.

Non-coordination functionality must not be added unless the user gives explicit instruction in a separate task.

## 4. Core Workflow

The standard workflow is:

```text
User goal
  ->
ChatGPT performs scope classification
  ->
ChatGPT writes a bounded Codex task
  ->
Codex executes only the authorized scope
  ->
Codex reports DONE or BLOCKED
  ->
ChatGPT reviews the result
  ->
ACCEPTED / REWORK / BLOCKED
```

## 5. Standard User Entry Points

Use the following prompts when working with this system:

```text
Use the standard ChatGPT-Codex coordination system. First perform scope_guardian classification, then generate a Codex task.
```

```text
Use the standard ChatGPT-Codex coordination system to review this Codex DONE report.
```

```text
Use the standard ChatGPT-Codex coordination system to resolve this Codex BLOCKED report.
```

```text
Use the standard ChatGPT-Codex coordination system to generate a bounded REWORK task.
```

## 6. Scope Classification

Every new request should be classified as one of:

```text
CORE
MAINTENANCE
TEST
DOCS
EXTENSION
OUT_OF_SCOPE
```

Only coordination-system tasks should be handled inside this project.

If a request introduces non-coordination functionality, it must be treated as EXTENSION or OUT_OF_SCOPE unless the user explicitly authorizes a separate task.

## 7. Main Files

### agents/

Contains the main coordination agent.

### skills/

Contains reusable coordination skills:

- `skills/codex_task_writer.md` - writes bounded Codex tasks.
- `skills/codex_output_reviewer.md` - reviews Codex DONE reports.
- `skills/codex_blocker_resolver.md` - resolves Codex BLOCKED reports.
- `skills/project_context_compressor.md` - compresses project context.
- `skills/scope_guardian.md` - classifies scope and prevents unauthorized expansion.

### .codex-coordination/

Optional file-based coordination protocol using inbox, outbox, decisions, logs, and templates.

### CODEX_WORKFLOW.md

Operational guide for using the coordination system.

### SCOPE_POLICY.md

Defines the scope boundary and prevents uncontrolled expansion.

### PROJECT_BRIEF.md

Project-level context and current system definition.

### TASKS.md

Task history, task queue, and coordination-system planning record.

## 8. Codex Task Requirements

Every Codex task should include:

1. Scope Classification.
2. Background.
3. Goal.
4. Allowed Scope.
5. Forbidden Actions.
6. Requirements.
7. Acceptance Criteria.
8. BLOCKED Rules.
9. DONE Report Format.

Tasks should be small, bounded, and independently reviewable.

## 9. Codex DONE Review

A Codex DONE report does not mean the task is accepted.

ChatGPT must review:

1. Whether the goal was completed.
2. Whether scope was respected.
3. Whether unauthorized files were modified.
4. Whether files were deleted.
5. Whether Git operations were safe.
6. Whether scope expanded beyond the coordination system.

The review result must be one of:

```text
ACCEPTED
REWORK
BLOCKED
```

## 10. Codex BLOCKED Handling

When Codex reports BLOCKED, it must stop.

ChatGPT then decides whether to:

1. Continue.
2. Continue with limited scope.
3. Expand scope.
4. Request more information.
5. Ask the user for a decision.
6. Cancel.
7. Issue a rework task.

Codex must not continue after BLOCKED without a ChatGPT decision.

## 11. Git Safety Rules

The default Git rule is:

```text
Only stage explicitly listed files.
```

Codex must not run these commands unless explicitly authorized:

```text
git add .
git add -A
git commit
git push
git reset
git clean
```

When staging or committing is authorized, the task must list exact files and the exact commit message.

## 12. Optional File-Based Workflow

When file-based coordination is needed, use:

```text
.codex-coordination/inbox/
.codex-coordination/outbox/
.codex-coordination/decisions/
```

Recommended flow:

```text
inbox -> outbox -> decisions
```

This workflow is optional. The system can also be used directly in chat.

## 13. Current Boundary

The current project is limited to the ChatGPT-Codex coordination system.

It should not absorb non-coordination functionality.

If the user requests non-coordination capability, classify the request first and handle it only after explicit authorization.

## 14. Maintenance Rule

For future maintenance:

1. Classify the request first.
2. Keep tasks small.
3. Restrict Codex scope.
4. Review DONE reports before acceptance.
5. Require BLOCKED when scope is unclear.
6. Never stage historical untracked files accidentally.
7. Do not add non-coordination functionality silently.

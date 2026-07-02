# Codex Task

## 1. Task ID

TASK_017_MINIMAL_COORDINATION_FLOW_TEST

## 2. Status

READY

## 3. Background

This is a minimal flow test for the ChatGPT-Codex coordination protocol.

The purpose is to verify that a task can be placed in `.codex-coordination/inbox/`, executed by Codex, and reported in `.codex-coordination/outbox/`.

This task does not involve legal business modules.

## 4. Goal

Create a matching result file in:

```text
.codex-coordination/outbox/TASK_017_RESULT.md
```

## 5. Allowed Scope

Allowed to create:

```text
.codex-coordination/outbox/TASK_017_RESULT.md
```

## 6. Forbidden Actions

1. Do not modify agents.
2. Do not modify skills.
3. Do not modify PROJECT_BRIEF.md.
4. Do not modify TASKS.md.
5. Do not create legal business modules.
6. Do not execute git add.
7. Do not execute git commit.
8. Do not delete files.

## 7. Requirements

1. Create the result file.
2. Record that the inbox -> outbox flow was tested.
3. Do not create a decision file.
4. Report the created files.

## 8. Acceptance Criteria

1. Inbox test task file exists.
2. Outbox result file exists.
3. No existing files are modified.
4. No legal business files are created.
5. No git add or commit is executed.

## 9. BLOCKED Rules

If either target file already exists, stop and report BLOCKED.

## 10. DONE Report Format

Codex should report:

1. Status
2. Files created
3. Files modified
4. Files deleted
5. Verification method
6. Risks

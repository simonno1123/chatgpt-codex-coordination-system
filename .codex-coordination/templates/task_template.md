# ACOS Task Template

ARTIFACT TYPE:
TASK

PRODUCER:
ChatGPT

TO:
Codex Executor

MODE:
[EDIT / READONLY / GIT / TEST / DOCS / MAINTENANCE]

PROJECT:
[Project path or repository name]

AUTHORITY LIMIT:
[Exactly what Codex may do for this task]

FORBIDDEN:
[Actions, files, directories, roles, or workflows Codex must not touch]

OUTPUT:
RESULT or BLOCKED RESULT only

---

## 1. Task ID

[TASK_ID]

## 2. Status

READY

## 3. Background

[Describe the current project phase, accepted prior decisions, source of this task, and task boundary.]

## 4. Goal

This task only completes:

- [Single explicit goal]

## 5. Allowed Scope

Allowed files or directories:

- [Specific file or directory]

Allowed commands:

- [Specific command, if authorized]

## 6. Requirements

1. [Requirement one]
2. [Requirement two]
3. [Requirement three]

## 7. Acceptance Criteria

1. The stated goal is completed.
2. Only authorized files are modified.
3. No unauthorized files are created, deleted, staged, committed, or pushed.
4. Artifact Routing metadata is preserved.
5. Role authority remains unchanged.
6. Risks and verification method are reported.

## 8. BLOCKED Rules

Codex must stop and output BLOCKED RESULT if:

1. Current directory or project identity is unclear.
2. Required files are missing or conflict with the task description.
3. Completing the task requires modifying unauthorized files.
4. Multiple implementation paths would change architecture or authority boundaries.
5. External tools, services, credentials, or environment configuration are unclear.
6. Domain-specific rules, project strategy, or acceptance standards are not authorized.
7. Tests or checks fail and the fix is outside the authorized scope.
8. The task would require Codex to produce REVIEW, DECISION, or self-acceptance.

## 9. RESULT Format

Codex must produce RESULT or BLOCKED RESULT only.

Required fields:

```markdown
ARTIFACT TYPE:
RESULT / BLOCKED RESULT

PRODUCER:
Codex Executor

TO:
ChatGPT Review

MODE:
[Same mode as the task]

PROJECT:
[Project path or repository name]

AUTHORITY LIMIT:
[Restate the task authority limit]

FORBIDDEN:
[Restate forbidden actions]

OUTPUT:
RESULT / BLOCKED RESULT

Status:
DONE / BLOCKED

Modified files:
- [File path]

Summary:
- [What changed or why blocked]

Verification:
- [Commands, checks, or static review performed]

Risks:
- [Known risks]

NEXT RECEIVER:
ChatGPT Review

Reason:
[Why ChatGPT Review is the next receiver]
```

## 10. Role Boundary Reminder

Allowed artifact authorities:

- ChatGPT: TASK, REVIEW, DECISION
- Codex Executor: RESULT, BLOCKED RESULT
- External Advisory Reviewer: ADVISORY REVIEW only
- Automation: RESULT, RECORD only

Forbidden authority drift:

- Codex must not produce REVIEW or DECISION.
- Codex must not self-accept work.
- External Advisory Reviewer must not execute tasks or produce DECISION.
- Automation must not produce REVIEW or DECISION.

NEXT RECEIVER:
ChatGPT Review

Reason:
After Codex executes the TASK, the RESULT or BLOCKED RESULT must return to ChatGPT Review.

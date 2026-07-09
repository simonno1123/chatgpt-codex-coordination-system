# ACOS Context Pack Template

ARTIFACT TYPE:
CONTEXT PACK

PRODUCER:
ChatGPT

TO:
Codex Executor

MODE:
CONTEXT

PROJECT:
[Project path or repository name]

AUTHORITY LIMIT:
This context pack provides background only and does not authorize additional execution.

FORBIDDEN:
[Actions that remain forbidden despite this context]

OUTPUT:
CONTEXT PACK

---

## 1. Project Goal

[Project goal]

## 2. Project / Instance Boundary

1. [What belongs to this project]
2. [What belongs to another project or instance]
3. [What must not be mixed into this task]

## 3. Current Phase

[Current phase]

## 4. Completed and Accepted Tasks

- [TASK_ID]: [Result]

## 5. Current Task

[TASK_ID + what this turn does only]

## 6. Relevant Files

- [Relevant file]

## 7. Key Decisions

1. [Decision]
2. [Decision]
3. [Decision]

## 8. Artifact Routing and Authority Context

1. ChatGPT produces TASK, REVIEW, and DECISION.
2. Codex Executor produces RESULT and BLOCKED RESULT only.
3. External Advisory Reviewer produces ADVISORY REVIEW only.
4. Automation produces RESULT or RECORD only.
5. NEXT RECEIVER and Reason must appear at the end of executable artifacts.

## 9. Allowed Scope for Current Task

- [Allowed scope]

## 10. Forbidden Actions

1. [Forbidden action]
2. [Forbidden action]
3. [Forbidden action]

## 11. Known Risks

1. [Risk]
2. [Risk]
3. [Risk]

## 12. What Codex Should Ignore

1. [Out-of-scope history or file]
2. [Out-of-scope discussion]
3. [Out-of-scope future task]

## 13. Expected Output

[What Codex should output this turn]

NEXT RECEIVER:
Codex Executor

Reason:
This context pack is background for Codex Executor and does not itself authorize work beyond the paired TASK.

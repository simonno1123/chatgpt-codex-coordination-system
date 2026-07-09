# ACOS Review Template

ARTIFACT TYPE:
REVIEW

PRODUCER:
ChatGPT Review

TO:
User Decision / Codex Executor / None

MODE:
REVIEW

PROJECT:
[Project path or repository name]

AUTHORITY LIMIT:
This review may accept, request rework, block, cancel, or ask for user decision. It does not authorize Codex beyond the explicit next task or decision.

FORBIDDEN:
[Actions that remain forbidden after this review]

OUTPUT:
REVIEW

---

## 1. Related Task

[TASK_ID]

## 2. Review Result

ACCEPTED / REWORK / BLOCKED / CANCELLED

## 3. Review Basis

1. Original task:
2. Codex RESULT or BLOCKED RESULT:
3. File scope:
4. Verification result:
5. Known risks:

## 4. Accepted Items

1. [Accepted item]
2. [Accepted item]
3. [Accepted item]

## 5. Issues or Risks

1. [Issue or risk]
2. [Issue or risk]
3. [Issue or risk]

## 6. Required Fixes

[If none, write "None".]

## 7. Approved Scope for Next Action

- [Exact next action, or "None"]

## 8. Forbidden Actions

1. Codex must not produce REVIEW or DECISION.
2. Codex must not self-accept work.
3. External Advisory Reviewer must not execute tasks or produce DECISION.
4. Automation must not produce REVIEW or DECISION.
5. [Additional task-specific forbidden action]

## 9. Next Instruction

[If ACCEPTED, state whether to commit, push, start next task, stop, or ask User Decision.]
[If REWORK, provide the rework task boundary.]
[If BLOCKED, state what information or authorization is required.]
[If CANCELLED, state the stop reason.]

NEXT RECEIVER:
[Codex Executor / User Decision / ChatGPT Review / None]

Reason:
[Why this receiver gets the next artifact or why no further action is needed.]

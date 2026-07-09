# ACOS Decision Template

ARTIFACT TYPE:
DECISION

PRODUCER:
ChatGPT Review

TO:
Relevant Receiver

MODE:
[GOVERNANCE / REVIEW RESOLUTION / USER AUTHORIZATION / STOP]

PROJECT:
[Project path or repository name]

AUTHORITY LIMIT:
[What this decision authorizes, rejects, or stops]

FORBIDDEN:
[Actions that remain forbidden after this decision]

OUTPUT:
DECISION

---

## 1. Decision ID

[DECISION_ID]

## 2. Related Task or Artifact

[TASK_ID / RESULT / REVIEW / GOVERNANCE PROPOSAL]

## 3. Decision

ACCEPTED / REWORK / BLOCKED / CANCELLED / USER_DECISION_REQUIRED / NO_FURTHER_ACTION

## 4. Basis

1. Original task or proposal:
2. Result or evidence reviewed:
3. File scope:
4. Verification result:
5. Known risks:

## 5. Authorized Next Action

- [Exact next action, or "None"]

## 6. Forbidden Actions

1. Codex must not produce REVIEW or DECISION.
2. Codex must not self-accept work.
3. External Advisory Reviewer must not execute tasks or produce DECISION.
4. Automation must not produce REVIEW or DECISION.
5. [Additional task-specific forbidden action]

## 7. Receiver Instructions

[Instruction for Codex Executor, User Decision, External Advisory Reviewer, Automation, or None.]

## 8. Record Notes

[What should be recorded for lifecycle traceability.]

NEXT RECEIVER:
[Codex Executor / User Decision / ChatGPT Review / External Advisory Reviewer / Automation / None]

Reason:
[Why this receiver gets the next artifact or why no further action is needed.]

# ACOS Result Template

ARTIFACT TYPE:
RESULT / BLOCKED RESULT

PRODUCER:
Codex Executor

TO:
ChatGPT Review

MODE:
[EDIT / READONLY / GIT / TEST / DOCS / MAINTENANCE]

PROJECT:
[Project path or repository name]

AUTHORITY LIMIT:
[Restate the authority granted by the TASK]

FORBIDDEN:
[Restate the actions that remained forbidden]

OUTPUT:
RESULT / BLOCKED RESULT

---

## 1. Task ID

[TASK_ID]

## 2. Status

DONE / BLOCKED

## 3. Summary

[Briefly explain what was completed or why execution was blocked.]

## 4. Files Created

- [Created file, or "None"]

## 5. Files Modified

- [Modified file, or "None"]

## 6. Files Deleted

- [Deleted file, or "None"]

## 7. Commands Run

- [Command, or "None"]

## 8. Verification Method

[Explain how the result was verified.]

## 9. Test Results

[Explain test or check results. If no tests were run, explain why.]

## 10. Authorization Check

1. Were only authorized files touched?
2. Were forbidden files or directories left untouched?
3. Was any git add / commit / push executed?
4. Was any REVIEW, DECISION, or self-acceptance produced by Codex?

## 11. Risks

1. [Risk one]
2. [Risk two]

## 12. Questions for ChatGPT Review

[If none, write "None". If blocked, state the exact decision needed.]

NEXT RECEIVER:
ChatGPT Review

Reason:
Codex RESULT or BLOCKED RESULT must be reviewed by ChatGPT Review before ACCEPTED, REWORK, BLOCKED, commit, push, or next task.

# Codex Task

## 1. Task ID

TASK_016_REVIEW_COORDINATION_SKILLS

## 2. Status

ARCHIVED / CLOSED

Original dispatch status: READY

Lifecycle closure:

```text
COMPLETED
ACCEPTED
COMMITTED
PUSHED
```

Closure note:

- TASK_016 audit was completed and reviewed.
- TASK_016A-D REWORK tasks were completed and accepted.
- Skill layer changes were committed in `037d257 docs: generalize ACOS skill layer`.
- The commit was pushed to `origin/master`.
- This task record is retained as an ACOS archive artifact and must not be re-executed.

## 3. Background

The standard ChatGPT-Codex coordination system has transitioned its temporary non-executing advisory reviewer role from Claude to Gemini 3.5 Flash (current provider). The general-purpose rules and role boundaries have been updated in `agents/codex_execution_coordinator.md` and `SCOPE_POLICY.md`.
The five files in `skills/` (codex_task_writer.md, codex_output_reviewer.md, codex_blocker_resolver.md, project_context_compressor.md, scope_guardian.md) need to be reviewed to ensure their descriptions, constraints, and instructions are fully aligned with the Gemini 3.5 Flash advisory reviewer role and ACOS boundaries.

This task is READ ONLY for code review and does not authorize file modifications. Codex should only identify discrepancies and report them.

## 4. Goal

Perform a comprehensive audit of all five files in `skills/` and report any misaligned role references, obsolete domain language, or structural gaps.

## 5. Allowed Scope

Read-only access to:
- `skills/` directory and all markdown files inside it.

## 6. Forbidden Actions

1. Do not modify any files (including the files under `skills/`, agents, or configs).
2. Do not delete files.
3. Do not run any modification commands.
4. Do not stage or commit files.

## 7. Requirements

1. Scan all files in `skills/` to check for any references to Claude or outdated role descriptions.
2. Check if the descriptions match the External Advisory Reviewer and Gemini 3.5 Flash provider definitions in ACOS.
3. Identify if any of the skills contain business or domain-specific language (e.g., U.S. or China legal rules) that should be removed or generalized.
4. Produce a detailed Audit Result table in the outbox.

## 8. Acceptance Criteria

1. Task results file is created in `.codex-coordination/outbox/TASK_016_RESULT.md`.
2. The results file contains a checklist of all 5 skills, specifying for each file whether it contains Claude references, domain language, or gaps.
3. No files are modified or created outside of `.codex-coordination/outbox/`.

## 9. BLOCKED Rules

If any unauthorized write or modification is needed to fulfill the review, stop and report BLOCKED.

## 10. DONE Report Format

Codex should report:

1. Status
2. Files created
3. Files modified
4. Files deleted
5. Verification method
6. Risks
7. Audit results table

## 11. Next Handoff Target

ChatGPT Review

## 12. Reason

To allow ChatGPT to review the audit results and decide whether to spawn specific REWORK tasks.

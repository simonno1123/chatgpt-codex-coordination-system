# Standard ChatGPT-Codex Coordination System

## 1. Purpose

This project is a standard general-purpose coordination system for ChatGPT-Codex collaboration.

It defines how ChatGPT plans, decomposes, reviews, and decides tasks, while Codex performs bounded execution and reports results.

The system is designed to make ChatGPT-Codex collaboration stable, auditable, and scope-controlled.

This project is an AI Collaboration Operating System (ACOS).

ACOS is the primary coordination system. A business or domain repository is an ACOS instance or user, not the owner of the core protocol.

For example, `claude-for-legal-cn` is a China legal capability project that may use ACOS. It should not carry ACOS protocol upgrades, reviews, decisions, inbox / outbox lifecycle files, or multi-agent coordination rules unless a task explicitly authorizes a local instance mode.

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
12. Explicit next handoff target rules.
13. Artifact routing and authority control.

## 3. ACOS and Instance Boundary

ACOS owns the collaboration method used to develop any project.

ACOS owns:

1. Task protocols.
2. Task lifecycle rules.
3. Inbox / outbox / decisions / reviews flow.
4. DONE / BLOCKED / REVIEW formats.
5. Task templates.
6. Multi-agent role boundaries.
7. Scope guarding.
8. Git safety rules.
9. Project invocation guidance.

Business or domain projects are ACOS instances or users. They own their domain capability, implementation, data, and workflows.

`claude-for-legal-cn` is a legal capability project. It owns China legal skills, legal MCP integration, legal references, legal workflows, and faithful localization work. It is not the home for ACOS protocol upgrades.

Coordination-system changes must go into ACOS first. Domain capability changes must go into the relevant business project.

Protocol files such as `PROTOCOL.md`, task lifecycle records, reviews, decisions, inbox, outbox, and coordination logs must not be embedded into a business project unless the user explicitly authorizes local ACOS instance mode for that project.

## 4. What This System Does Not Do

This system does not implement non-coordination functionality.

Any capability that is not necessary for ChatGPT-Codex coordination is outside the current system.

Non-coordination functionality must not be added unless the user gives explicit instruction in a separate task.

## 5. Core Workflow

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

## 6. Standard User Entry Points

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

## 7. Scope Classification

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

## 8. Main Files

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

## 9. Codex Task Requirements

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

## 10. Codex DONE Review

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

## 11. Temporary Claude Advisory Role

Claude may be used temporarily only as a non-executing advisory reviewer or second-opinion source.

The default workflow remains:

```text
ChatGPT -> Codex -> ChatGPT
```

Codex is the only execution agent.

Claude must not modify files, create files, delete files, run commands, perform Git operations, generate directly applicable patches, or make final decisions.

Claude output is advisory only and must be reviewed by ChatGPT before it affects the project.

## 12. Codex BLOCKED Handling

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

## 13. Explicit Handoff Target Rule

Every task transition must name the next recipient.

Required fields:

```text
Next Handoff Target: <ChatGPT Review | Codex Executor | User Decision | External Advisory Reviewer | None>
Reason: <why this party receives the next step>
```

Use `ChatGPT Review` when Codex reports DONE or BLOCKED and the result needs review, acceptance, rework, or a decision.

Use `Codex Executor` only when ChatGPT has already produced an approved bounded task or rework instruction for Codex to execute.

Use `User Decision` when the next step requires user approval, project direction, credentials, repository choice, or another decision ChatGPT cannot safely make.

Use `External Advisory Reviewer` only for non-executing second opinions. External advisory output is non-binding and must return to ChatGPT Review before it affects execution.

Use `None` only when the workflow is complete and no further action is required.

Task instructions, DONE reports, BLOCKED reports, review decisions, rework instructions, and next-step recommendations should include these fields.

## 14. Artifact Routing and Authority Rule

Every artifact must declare:

```text
TASK ID:
ARTIFACT TYPE:
PRODUCER:
TO:
NEXT RECEIVER:
MODE:
PROJECT:
AUTHORITY LIMIT:
FORBIDDEN:
OUTPUT:
DO NOT SEND TO:
```

Allowed artifact types:

1. `TASK`
2. `RESULT`
3. `ADVISORY REVIEW`
4. `REVIEW`
5. `DECISION`
6. `RECORD`

Role authority:

1. ChatGPT may produce `TASK`, `REVIEW`, `DECISION`, and `RECORD`.
2. Codex may produce `RESULT` or `BLOCKED RESULT` only.
3. Claude may produce `ADVISORY REVIEW` only.
4. Automation may produce `RESULT` or `RECORD` only.
5. Automation must not produce `REVIEW`, `ADVISORY REVIEW`, or `DECISION`.
6. Automation must not route output to itself for acceptance.
7. Automation output must return to ChatGPT Review unless the task explicitly routes it to User Decision for missing credentials, authorization, or human judgment.

Identity rule:

1. No agent may produce an artifact under another agent's identity.
2. Codex must never write `FROM: Claude` or `PRODUCER: Claude`.
3. Codex must never write `FROM: ChatGPT` or `PRODUCER: ChatGPT`.

Acceptance rule:

1. No agent may route an artifact to itself for acceptance.
2. Codex cannot accept its own `RESULT`.
3. Claude cannot make a final `DECISION`.
4. Automation cannot make a final `DECISION`.
5. ChatGPT Review is the authorized final reviewer under ACOS.
6. User Decision may authorize direction, scope, credentials, or whether to proceed, but User Decision does not replace ChatGPT Review unless the user explicitly suspends ACOS governance for that task.

Commit rule:

No commit may proceed unless a valid `DECISION` artifact has been produced by ChatGPT Review. User Decision may authorize whether to proceed, but Codex still requires a ChatGPT Review `DECISION` artifact before commit unless the user explicitly suspends ACOS governance for that task. A Codex `RESULT` alone is insufficient for commit.

Routing rule:

1. Every artifact must specify `NEXT RECEIVER`.
2. Missing `NEXT RECEIVER` makes the artifact invalid or BLOCKED.
3. If Claude is used, Claude output must return to ChatGPT Review.
4. Claude must not route directly to Codex Executor.

Invalid artifacts include identity-spoofed artifacts, missing receiver artifacts, self-acceptance artifacts, Codex-authored review or decision artifacts, and Claude-authored final decision artifacts.

## 15. Git Safety Rules

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

## 16. Optional File-Based Workflow

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

## 17. Current Boundary

The current project is limited to the ChatGPT-Codex coordination system.

It should not absorb non-coordination functionality.

If the user requests non-coordination capability, classify the request first and handle it only after explicit authorization.

ACOS protocol changes belong in this repository. Domain projects, including `claude-for-legal-cn`, should receive only domain-specific work unless explicitly configured as local ACOS instances.

## 18. Maintenance Rule

For future maintenance:

1. Classify the request first.
2. Keep tasks small.
3. Restrict Codex scope.
4. Review DONE reports before acceptance.
5. Require BLOCKED when scope is unclear.
6. Never stage historical untracked files accidentally.
7. Do not add non-coordination functionality silently.

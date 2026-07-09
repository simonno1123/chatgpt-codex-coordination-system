# ACOS Instance Onboarding Guide

## 1. Purpose

This guide explains how a project instance should use ACOS without copying ACOS into the project.

ACOS is the general collaboration system. A project instance is a concrete repository or workspace managed through ACOS tasks, reviews, and decisions.

Use this guide when ChatGPT needs to route work from ACOS into a separate project such as a product repository, operations repository, research workspace, or domain capability project.

## 2. Definitions

### ACOS

ACOS is the system of record for collaboration mechanics:

- Artifact Routing
- Authority Model
- Role Boundary
- Handoff Lifecycle
- Task / Result / Review / Decision templates
- Linter / Hook enforcement
- Governance Proposal flow

ACOS is not the business project itself.

### Project Instance

A Project Instance is a concrete project managed by ACOS.

A Project Instance owns its own implementation, data, domain knowledge, tests, configuration, and documentation. It does not own ACOS core protocol rules and must not become the source of ACOS governance.

## 3. Do Not Copy ACOS Core Into Project Instances

By default, a business or domain project must not copy ACOS core files or directories into itself.

Do not copy these into a project instance by default:

- `CODEX_WORKFLOW.md`
- `SCOPE_POLICY.md`
- `agents/`
- `skills/`
- `scripts/acos-linter.py`
- `.githooks/`
- `.codex-coordination/templates/`

Exception: local ACOS instance mode may be used only when the user explicitly authorizes that mode for a specific project. Without that authorization, the project remains an external instance managed from ACOS.

## 4. Recommended External Invocation Mode

The recommended mode is external invocation:

```text
ChatGPT uses ACOS rules to generate TASK
        ↓
Codex executes inside the project instance directory
        ↓
Codex outputs RESULT or BLOCKED RESULT
        ↓
ChatGPT Review accepts, requests rework, blocks, or asks User Decision
```

The project instance only needs to provide the execution facts required for a bounded task:

- project path
- goal
- allowed files
- forbidden actions
- mode
- expected output

The ACOS repository remains the source of collaboration protocol, authority rules, routing rules, and governance changes.

## 5. Standard Instance Invocation Template

Copy this template when invoking work in a project instance:

```text
ARTIFACT TYPE:
TASK
PRODUCER:
ChatGPT
TO:
Codex Executor
NEXT RECEIVER:
ChatGPT Review
MODE:
READONLY / EDIT / COMMIT
PROJECT:
/path/to/project-instance
AUTHORITY LIMIT:
[exact scope Codex may execute]
FORBIDDEN:
[files, directories, commands, roles, and workflows Codex must not touch]
OUTPUT:
RESULT only

TASK ID:
[task id]

GOAL:
[one bounded goal]

ALLOWED FILES:
[explicit files or directories]

BLOCKED IF:
[conditions requiring Codex to stop]

DONE RESULT MUST INCLUDE:
1. Status
2. Current directory
3. Files modified
4. Verification performed
5. Git status
6. Whether git add / commit / push was executed
7. NEXT RECEIVER: ChatGPT Review
8. Reason
```

## 6. Instance Boundary Rules

### Belongs To The Project Instance

The following belong inside the project instance:

- business code
- business documentation
- business skills
- business MCP configuration
- domain knowledge
- project README
- project tests
- project configuration

### Belongs To ACOS

The following belong inside ACOS:

- Artifact Routing
- Authority Model
- Role Boundary
- Handoff Lifecycle
- Task / Result / Review / Decision templates
- Linter / Hook enforcement
- Governance Proposal

Do not move ACOS protocol changes into the project instance. Do not move instance-specific business rules into ACOS.

## 7. Feedback Return Rule

When a project instance reveals a problem, classify it before changing any repository.

If the problem is specific to the project instance, keep it in the project instance.

Examples:

- domain behavior
- project-specific configuration
- tests
- local workflows
- project documentation

If the problem is about collaboration mechanics, return it to ACOS as a `GOVERNANCE PROPOSAL`.

Examples:

- unclear artifact routing
- unclear producer or receiver authority
- missing task lifecycle state
- missing template field
- linter or hook enforcement gap
- role boundary ambiguity

Do not write business rules back into ACOS. Do not use project instance work to silently change ACOS governance.

## 8. Example: claude-for-legal-cn

`claude-for-legal-cn` is an ACOS project instance.

It uses ACOS for task routing, execution boundaries, and review lifecycle.

Its legal skills, MCP integrations, domain references, and domain workflows remain inside the instance project.

ACOS may generate a bounded TASK that targets the `claude-for-legal-cn` project path, but ACOS protocol upgrades, role definitions, templates, linter rules, and governance decisions stay in the ACOS repository unless the user explicitly authorizes local ACOS instance mode.

## 9. Onboarding Checklist

Before invoking Codex in a project instance, confirm:

1. The target project path is explicit.
2. The task goal is bounded.
3. Allowed files are listed.
4. Forbidden actions are listed.
5. The mode is declared.
6. Expected output is declared.
7. ACOS core files are not being copied into the instance.
8. Any governance issue is routed back to ACOS as `GOVERNANCE PROPOSAL`.

## 10. Summary

ACOS governs collaboration. Project instances own project work.

Keep protocol in ACOS. Keep domain work in the project instance. Use explicit TASK artifacts to cross the boundary.

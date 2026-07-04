# Scope Policy

## 1. Purpose

This document defines the scope boundary of the standard general-purpose ChatGPT-Codex coordination system.

The system exists only to coordinate work between ChatGPT and Codex. It must not absorb non-coordination functionality unless the user explicitly authorizes a separate task.

This project is an AI Collaboration Operating System (ACOS). ACOS is the primary system for collaboration rules, task protocols, review flows, and decision records. Domain projects are ACOS instances or users.

## 2. ACOS and Instance Boundary

ACOS owns coordination-system scope:

1. Task protocols.
2. Task lifecycle rules.
3. Inbox / outbox / decisions / reviews flow.
4. DONE / BLOCKED / REVIEW formats.
5. Task templates.
6. Multi-agent role boundaries.
7. Scope guarding.
8. Git safety rules.
9. Project invocation guidance.
10. Explicit next handoff target rules.

Business and domain repositories own domain capability, implementation, data, and domain workflows.

`claude-for-legal-cn` is an ACOS instance or user for China legal capability. It owns China legal skills, legal MCP integration, legal references, legal workflows, and faithful localization work. It must not receive ACOS protocol upgrades, task lifecycle files, reviews, decisions, inbox / outbox files, or multi-agent coordination rules unless explicitly authorized as a local ACOS instance mode.

If a task is about how AI agents collaborate, how Codex tasks are written, how reviews or decisions are recorded, how inbox / outbox lifecycle works, or how scope_guardian operates, it belongs in ACOS.

If a task is about China legal skills, legal MCP, legal references, legal retrieval, legal workflow behavior, or faithful localization, it belongs in `claude-for-legal-cn`.

## 3. Core System Scope

The following belong to the core coordination system:

1. ChatGPT-Codex role separation.
2. Codex task generation.
3. Allowed scope and forbidden action control.
4. DONE report format.
5. BLOCKED report format.
6. ChatGPT review decisions.
7. REWORK task generation.
8. Context compression.
9. Git safety rules.
10. Optional inbox / outbox / decisions flow.
11. Task state tracking.
12. Scope guarding.
13. ACOS instance boundary rules.
14. Explicit handoff target rules.

## 4. Non-Core Scope

Any capability that is not necessary for coordinating ChatGPT-Codex work is outside the core system.

Non-core functionality must not be added to this project unless the user gives explicit instruction for a separate task.

## 5. Extension Rule

Any non-core functionality requires explicit user instruction in a separate task.

Non-core functionality must not be added silently to the core system.

## 6. Temporary Non-Executing Advisory Tools

Temporary advisory tools may be used only for second opinions or non-binding review support.

They do not become part of the core coordination system unless explicitly authorized.

Claude, when used temporarily, is a non-executing advisory reviewer only.

Claude must not:

1. Modify files.
2. Create files.
3. Delete files.
4. Run commands.
5. Perform Git operations.
6. Generate directly applicable patches.
7. Act as default or backup executor.
8. Make final decisions.
9. Expand approved scope.
10. Bypass scope classification.

Any Claude output must be reviewed by ChatGPT before it affects a task, review, or decision.

## 7. Scope Classification

Every Codex task should be classified as one of:

- CORE
- MAINTENANCE
- TEST
- DOCS
- EXTENSION
- OUT_OF_SCOPE

Tasks classified as EXTENSION or OUT_OF_SCOPE require explicit user approval before implementation.

## 8. Default Forbidden Expansion

Unless explicitly authorized, Codex must not create files, directories, integrations, workflows, agents, skills, templates, configurations, or automation that are not required for ChatGPT-Codex coordination.

Codex must not place ACOS protocol upgrades into a business project unless the user explicitly authorizes local ACOS instance mode for that project.

## 9. Review Requirement

When reviewing Codex output, ChatGPT must check whether the task expanded beyond the approved system scope.

If unauthorized expansion occurred, the review result must be REWORK or BLOCKED.

ChatGPT must also check whether the output names an explicit next handoff target and reason. Missing or ambiguous handoff targets should be treated as REWORK unless the task is otherwise BLOCKED.

Valid handoff targets are:

1. `ChatGPT Review`
2. `Codex Executor`
3. `User Decision`
4. `External Advisory Reviewer`
5. `None`

External advisory reviewers are non-executing only. Their output must return to ChatGPT Review before it can affect execution.

## 10. Final Rule

The coordination system governs collaboration.

It does not become the business system.

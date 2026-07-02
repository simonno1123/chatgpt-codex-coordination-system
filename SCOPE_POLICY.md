# Scope Policy

## 1. Purpose

This document defines the scope boundary of the standard general-purpose ChatGPT-Codex coordination system.

The system exists only to coordinate work between ChatGPT and Codex. It must not absorb non-coordination functionality unless the user explicitly authorizes a separate task.

## 2. Core System Scope

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

## 3. Non-Core Scope

Any capability that is not necessary for coordinating ChatGPT-Codex work is outside the core system.

Non-core functionality must not be added to this project unless the user gives explicit instruction for a separate task.

## 4. Extension Rule

Any non-core functionality requires explicit user instruction in a separate task.

Non-core functionality must not be added silently to the core system.

## 5. Scope Classification

Every Codex task should be classified as one of:

- CORE
- MAINTENANCE
- TEST
- DOCS
- EXTENSION
- OUT_OF_SCOPE

Tasks classified as EXTENSION or OUT_OF_SCOPE require explicit user approval before implementation.

## 6. Default Forbidden Expansion

Unless explicitly authorized, Codex must not create files, directories, integrations, workflows, agents, skills, templates, configurations, or automation that are not required for ChatGPT-Codex coordination.

## 7. Review Requirement

When reviewing Codex output, ChatGPT must check whether the task expanded beyond the approved system scope.

If unauthorized expansion occurred, the review result must be REWORK or BLOCKED.

## 8. Final Rule

The coordination system governs collaboration.

It does not become the business system.

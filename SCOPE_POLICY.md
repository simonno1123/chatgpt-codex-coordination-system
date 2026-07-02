# Scope Policy

## 1. Purpose

This document defines the scope boundary of the standard general-purpose ChatGPT-Codex coordination system.

The system exists only to coordinate work between ChatGPT and Codex. It must not absorb business-specific functionality unless the user explicitly creates a separate extension.

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

The following do not belong to the core coordination system:

1. Legal business modules.
2. Legal research tools.
3. Case retrieval tools.
4. MCP integrations.
5. Network management modules.
6. PDF/OCR workflows.
7. Word/Excel document automation.
8. Database integrations.
9. Browser automation.
10. GitHub issue or PR automation.
11. External API integrations.
12. Industry knowledge bases.
13. Business templates.
14. Domain-specific agents or skills.

## 4. Extension Rule

Any non-core functionality must be created as a separate extension after explicit user instruction.

Extensions must not be added silently to the core system.

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

Unless explicitly authorized, Codex must not create:

1. Business modules.
2. Legal modules.
3. MCP configuration.
4. PDF/OCR modules.
5. Database integrations.
6. External API integrations.
7. Domain-specific templates.
8. Industry-specific agents or skills.

## 7. Review Requirement

When reviewing Codex output, ChatGPT must check whether the task expanded beyond the approved system scope.

If unauthorized expansion occurred, the review result must be REWORK or BLOCKED.

## 8. Final Rule

The coordination system governs collaboration.

It does not become the business system.

# Skill: Scope Guardian

## 1. Purpose

This skill prevents the general ChatGPT-Codex coordination system from expanding into unrelated non-coordination work.

It determines whether a requested task belongs to the core coordination system, system maintenance, testing, documentation, a separate extension, or is out of scope.

## 2. Scope Categories

Use the following categories:

```text
CORE
MAINTENANCE
TEST
DOCS
EXTENSION
OUT_OF_SCOPE
```

## 3. CORE

A task is CORE when it directly improves the coordination system itself, such as:

1. Improving task format.
2. Improving DONE/BLOCKED formats.
3. Improving review rules.
4. Improving Git safety.
5. Improving context compression.
6. Improving inbox/outbox/decisions protocol.
7. Improving scope guarding.

## 4. MAINTENANCE

A task is MAINTENANCE when it fixes or updates existing coordination files without adding business capability.

## 5. TEST

A task is TEST when it verifies coordination behavior, such as a protocol smoke test or Git safety test.

## 6. DOCS

A task is DOCS when it documents how to use or maintain the coordination system.

## 7. EXTENSION

A task is EXTENSION when it introduces functionality that is not required for ChatGPT-Codex coordination itself.

EXTENSION tasks require explicit user approval and must be handled separately from the core coordination system.

## 8. OUT_OF_SCOPE

A task is OUT_OF_SCOPE when it conflicts with the current project purpose, creates unrelated functionality, or cannot be safely bounded.

## 9. Decision Format

When classifying a task, use:

```markdown
# Scope Review

## 1. Classification

CORE / MAINTENANCE / TEST / DOCS / EXTENSION / OUT_OF_SCOPE

## 2. Reason

## 3. Allowed Path

## 4. Required User Approval

YES / NO

## 5. Risk of Scope Expansion

LOW / MEDIUM / HIGH

## 6. Recommendation
```

## 10. Default Rule

If a task introduces functionality that is not necessary for ChatGPT-Codex coordination, classify it as EXTENSION unless the user explicitly states it is part of the core coordination system.

## 11. Final Rule

Protect the coordination system from becoming a business application.

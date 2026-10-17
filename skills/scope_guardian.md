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

## 9A. Scope Review Field Interpretation

### SG-P01 — Overlapping classifications
If the same supplied facts support both EXTENSION and OUT_OF_SCOPE and neither is excluded by facts, withhold a unique classification; name both clauses, describe the specific conflict and request ChatGPT Review's disposition.
This procedure establishes no priority between §§7, 8 and 10. If disposition requires a new normative choice, ChatGPT Review must refer that choice to Human rather than establish a new priority itself.

### SG-P02 — Scope consent and execution authority
Required User Approval states whether explicit Human consent to the proposed scope is required, not whether consent has been received or whether an action is authorized.
Use YES for EXTENSION, including when consent was already supplied.
Use NO for CORE, MAINTENANCE, TEST or DOCS only when facts establish a bounded coordination purpose without an unresolved policy exception.
For OUT_OF_SCOPE, withheld classification or insufficient facts for that mapping, leave the field blank and explain the undecided scope-disposition question outside the six fields.
For a withheld overlap, retain §7's explicit-consent requirement for any EXTENSION branch in the external diagnostics; a blank field never waives it.
Record actual consent separately with its source, subject and limits. Silence, an Executor RESULT or consent to another subject is not consent to this scope.
NO means no additional scope consent is required under this mapping; it waives no task, Review, file, Git or other action requirement.
YES does not make an OUT_OF_SCOPE request admissible. Neither value supplies actual execution authorization.

### SG-P03 — Scope-expansion risk
Assess the requested scope, including proposed placement, rather than action-security risk or the category name.
HIGH: supplied facts demonstrate a purpose-conflicting or unrelated goal, request non-coordination functionality inside core, or explicitly refuse finite boundaries.
MEDIUM: facts establish a bounded nonessential addition handled separately, and none of the HIGH conditions applies.
LOW: facts establish a bounded coordination-only goal with no non-coordination capability added, and neither HIGH nor MEDIUM applies.
Use the highest evidenced condition. If facts needed for an applicable band are missing, leave the field blank and identify them; lack of information alone is not HIGH.
The rating is a scope advisory judgment, not approval, an automatic block or proof an action is safe.

### SG-P04 — Missing facts and incomplete output
Ask for the object, intended outcome, relationship to coordination, finite actions and proposed scope only to the extent needed for an undecided field.
If no supported unique category is available, leave Classification blank. Never put UNRESOLVED or another diagnostic in the category enum.
Leave other unsupported native fields blank too; explain each omission outside the six fields and mark the record INCOMPLETE NATIVE SCOPE REVIEW.
Use the external diagnostic CLASSIFICATION WITHHELD when applicable; it is not a category.
Reason and Recommendation state what can be concluded, identify missing facts and give the next necessary clarification.
Missing facts are not proof of a permanently unbounded request; an explicitly refused boundary is a supplied fact.
The six-field structure remains unchanged. This procedure does not promise every request will produce a complete record.

### SG-P05 — Human Core declarations
A Core declaration alone does not settle classification. If it is in tension with §§3, 8 or 11, withhold a unique classification and request ChatGPT Review's explicit policy disposition.
Record the declaration's actual source and the conflicting clauses; do not treat a simulated declaration as real consent or an Executor claim as a Human statement.
This procedure establishes no priority among §§3, 8, 10 and 11 and does not rewrite project purpose. New normative choices must be referred to Human.
Any later project-purpose change requires its own explicit decision and task. A declaration or classification never grants file, Git or production authority.

### SG-P06 — Allowed Path as a handling boundary
Allowed Path records a recommended handling boundary, not an already-authorized filesystem path or access-control result.
State the supported activity, separation boundary and excluded actions. For classification-only input, state classification only; no file operation is proposed or authorized by this record.
For an EXTENSION, recommend separate handling without inventing a directory. For OUT_OF_SCOPE, recommend no implementation of the current request and a bounded replacement proposal.
If facts do not support a handling boundary, leave the field blank and identify what is missing outside the template.
When referring to an independently authorized path, cite the real task or approval and its limits; never infer authority from this field.
No Markdown field performs filesystem enforcement. A scope classification, approval value, risk rating or handling boundary cannot replace actual action authorization.

## 10. Default Rule

If a task introduces functionality that is not necessary for ChatGPT-Codex coordination, classify it as EXTENSION unless the user explicitly states it is part of the core coordination system.

## 11. Final Rule

Protect the coordination system from becoming a business application.

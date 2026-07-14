# ACOS Schema Validation Fixtures

This directory contains deterministic, fixture-only examples for validating ACOS Artifact Envelopes and Unified Policies.

## Target Schemas

- `fixtures/schemas/envelope.schema.json`: JSON Schema defining valid metadata envelopes.
- `fixtures/schemas/policy.schema.json`: JSON Schema defining unified policy structure.

## Fixture Categories

- `valid-*.json`: Correctly structured documents that must pass schema validation.
- `invalid-*.json`: Structural metadata violations that must fail schema validation (result in `DENY`).
- `blocked-*.json`: Malformed JSON or schema-checking errors that must result in `BLOCKED`.

## Safety Boundary

The validator performs offline structural and bounded semantic checks only. It does not authenticate a runtime, verify a cryptographic signature, consume an authorization, mutate a repository, or grant execution authority. A `PASS` result means only that the supplied fixture satisfies the supported schema checks.

`producer_role` is a stable ACOS governance classification. `producer_runtime_id` is a bounded, extensible identifier for one concrete runtime instance; it is not a model or provider name. The schema can validate their syntax and artifact-role constraints, but only a future Runtime Registry, Policy Engine, and authentication layer can prove that a runtime actually holds a declared role.

Structural validation includes required fields, role enums, runtime-ID syntax, string patterns, RFC 3339 format checks, conditional fields, and bounded arrays or objects. Cross-artifact authorization binding, active-policy selection, digest-to-file comparison, cryptographic verification, authenticated runtime identity, replay prevention, durable authorization consumption, filesystem enforcement, Git enforcement, and trusted time are not implemented.

CLI targets must be JSON files or directories under this fixture directory. Parent traversal, targets outside the fixture root, symbolic-link files, oversized input, excessive nesting, duplicate JSON keys, invalid UTF-8, malformed schemas, and non-local schema references fail closed as `BLOCKED`.

## Dependency And Exit Codes

Install the single pinned direct dependency from `requirements-schema-validator.txt`. Transitive locking, distribution hashes, vendoring, and package installation are outside TASK_059. The validator uses JSON Schema Draft-07 with a deterministic RFC 3339 `FormatChecker`.

- Exit `0`: every fixture matched its expected `PASS`, `DENY`, or `BLOCKED` result.
- Exit `1`: at least one fixture result differed from its declared expectation.
- Exit `2`: an operational blocker occurred without an expected `BLOCKED` classification.

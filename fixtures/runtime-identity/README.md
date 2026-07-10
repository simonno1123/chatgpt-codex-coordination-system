# Runtime Identity Fixtures

These static fixtures exercise the ACOS v2 runtime identity simulator. They do
not authorize execution or mutate a repository.

Each fixture uses this schema:

```json
{
  "case_id": "valid-codex-result",
  "runtime_identity": "Codex Executor Runtime",
  "producer": "Codex Executor",
  "artifact_type": "RESULT",
  "expected_result": "PASS"
}
```

Required input fields are `runtime_identity`, `producer`, and `artifact_type`.
`case_id` is optional but recommended. `expected_result` is test metadata and
must be one of `PASS`, `DENY`, or `BLOCKED` when present.

Result meanings:

- `PASS`: the known runtime, producer, and artifact binding is allowed.
- `DENY`: the identity is known, but the producer binding or artifact authority
  is forbidden.
- `BLOCKED`: required data is missing or an identity/artifact is unknown.

An expected `DENY` or `BLOCKED` only verifies rejection behavior. It never
grants the denied authority.

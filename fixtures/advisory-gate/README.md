# Advisory Gate Fixtures

These fixtures exercise the fixture-only ACOS External Advisory Gate checker.
The checker classifies declared changes and validates static request, review,
consumption, and lifecycle facts. It does not contact an advisory provider,
create or consume a real review, grant authority, or change Git state.

Trigger levels follow the TASK_046 policy:

- `advisory_not_required`
- `advisory_optional`
- `advisory_mandatory`

Fixture filename prefixes define expected results when omitted from content:

- `valid-`: `PASS`
- `invalid-`: `DENY`
- `blocked-`: `BLOCKED`

`PASS` means only that declared fixture facts match current policy. It never
means ChatGPT Review issued a decision, User Decision exists, or commit, push,
release, or a next task is authorized.

Fixtures may name a deterministic built-in template and then override or omit
specific fields. Expansion occurs in memory before validation; it does not
relax required-field checks or create files.

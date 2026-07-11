# Audit JSONL Fixtures

These fixtures exercise the ACOS v2 fixture-only audit writer. The writer emits
canonical JSONL to stdout and never writes a production log or grants authority.

Fixture modes:

- `generate`: validate raw events, create deterministic linkage and hashes.
- `roundtrip`: generate JSONL in memory, parse it, and verify the chain.
- `verify`: verify events that already contain hashes.
- `simulate_tamper`: generate a valid chain, mutate it in memory, and verify
  that the mutation is detected.

Canonical profile:

- schema version: `1.0`
- hash: SHA-256 over canonical UTF-8 JSON
- `sort_keys=true`, separators `(",", ":")`, `ensure_ascii=false`
- hash payload includes `previous_event_hash` and excludes `event_hash`
- genesis `previous_event_hash`: JSON `null`
- sequence starts at 1 and increments without gaps
- JSONL contains exactly one object per line and ends with one newline

An audit record is evidence only. It never replaces TASK, REVIEW, DECISION,
User Decision, advisory review, or operation-specific authorization.

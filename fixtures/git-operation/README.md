# Git Operation Gate Fixtures

These static fixtures exercise the ACOS v2 Git operation gate. The gate parses
declared command strings and repository state but never invokes Git or a shell.

Every fixture declares an independent operation authorization. A typical
mutation fixture includes:

```json
{
  "case_id": "valid-codex-stage-authorized",
  "runtime_identity": "Codex Executor Runtime",
  "producer": "Codex Executor",
  "requested_operation": "stage",
  "authorized_operation": "stage",
  "repository_scope": "ACOS CORE",
  "branch": "master",
  "head": "abc123",
  "worktree_state": "dirty_staged",
  "staged_paths": ["scripts/tool.py"],
  "changed_paths": ["scripts/tool.py"],
  "authorization_id": "AUTH-STAGE-1",
  "authorization_runtime": "Codex Executor Runtime",
  "authorization_scope": "ACOS CORE",
  "authorization_branch": "master",
  "authorization_head": "abc123",
  "authorization_source": "CHATGPT REVIEW DECISION",
  "authorized_paths": ["scripts/tool.py"],
  "pathspecs": ["scripts/tool.py"],
  "command": "git add -- scripts/tool.py",
  "expected_result": "PASS"
}
```

Result meanings:

- `PASS`: declared state matches one independent authorization; no live Git
  operation is executed or granted.
- `DENY`: known state violates runtime, command, path, or authorization policy.
- `BLOCKED`: input is missing, unknown, contradictory, or unsafe to parse.

Files prefixed `valid-`, `invalid-`, or `blocked-` infer PASS, DENY, or
BLOCKED when malformed/non-object JSON cannot contain `expected_result`.

Command strings are parsed with `shlex` only. Compound shell syntax, command
substitution, pipes, redirection, and unknown commands fail closed.

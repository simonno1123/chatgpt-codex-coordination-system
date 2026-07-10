# Filesystem Permission Fixtures

These fixtures drive the ACOS v2 fixture-only filesystem permission checker.
They describe hypothetical paths and capabilities; they never grant live
filesystem, Git, release, or runtime authority.

Minimal schema:

```json
{
  "case_id": "valid-codex-create-script",
  "runtime_identity": "Codex Executor Runtime",
  "producer": "Codex Executor",
  "operation": "create",
  "target_path": "scripts/acos-filesystem-permission-checker.py",
  "repository_scope": "ACOS CORE",
  "task_allowed_paths": ["scripts/acos-filesystem-permission-checker.py"],
  "governance_authorized": true,
  "expected_result": "PASS"
}
```

Supported virtual roots are `/acos-core` and `/project-instance`. Relative
paths are interpreted inside the declared `repository_scope`. The checker does
not inspect path existence or follow real symbolic links.

Optional capability fields:

- `task_allowed_paths`: exact paths or directory grants ending in `/`.
- `automation_allowed_paths`: narrowly scoped Automation output/read paths.
- `governance_authorized`: static ACOS governance authorization signal.
- `business_task_authorized`: static bounded instance-task signal.
- `local_mode_enabled`: explicit local ACOS instance mode signal.
- `delete_authorized`: separate delete capability.
- `artifact_type`, `path_class`, `expected_path_class`, and
  `expected_allowed`: artifact, classification, and test metadata.

Result meanings:

- `PASS`: no path-level policy violation was found; no live operation is
  authorized.
- `DENY`: known identity and operation violate an explicit path policy.
- `BLOCKED`: input is missing, unknown, contradictory, illegal, or unsafe to
  classify.

Files prefixed `valid-`, `invalid-`, or `blocked-` infer PASS, DENY, or
BLOCKED when malformed/non-object JSON cannot carry `expected_result`.

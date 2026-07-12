# User Decision Gate Fixtures

These fixtures exercise a deterministic, fixture-only User Decision Gate. The
checker never authenticates a user, creates a decision, executes an action, or
changes Git or external state.

`User Decision Runtime` is a shadow fixture identity only. It does not modify
the TASK_041 permission matrix or prove a real user's identity.

Fixtures may use deterministic in-memory templates with explicit overrides or
omissions. `PASS` means only that declared fixture facts match current policy;
it never starts work or authorizes commit, push, release, or later tasks.

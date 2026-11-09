# Configuration

## Per repo: `.tmn-fdekit.json`

Commit it at the repo root so people, agents and CI share the same commands
and limits. Every key is optional.

```json
{
  "mode": "standard",
  "lint": "make lint",
  "types": "npm run typecheck",
  "test": "make test",
  "build": "make build",
  "up": "docker compose up -d --build --wait",
  "down": "docker compose down",
  "pr": {
    "warn_lines": 300, "max_lines": 500,
    "warn_files": 10,  "max_files": 15,
    "one_commit": true,
    "ticket_re": "\\b[A-Z][A-Z0-9]+-\\d+\\b"
  }
}
```

## Per session: environment variables

Set them in the `env` block of `settings.json` (or your shell) before the
agent starts. The agent can't change them from inside its own commands.

| Variable | Default | Effect |
|---|---|---|
| `TMN_FDEKIT_MODE` | `standard` | `yolo` runs the skills' checkpoints without stopping; see [Run modes](#run-modes) |
| `TMN_FDEKIT_GUARD_OFF` | empty | comma-separated guard rules to turn off, or `all` |
| `TMN_FDEKIT_PROTECTED` | `main master prod production release` | branch names you can't push to directly |
| `TMN_FDEKIT_ALLOW_NO_CHECKS` | unset | `1` lets a merge go ahead on a PR with no checks |
| `TMN_FDEKIT_COMMS` | `block` | `warn` reports slop without blocking; `off` disables |
| `TMN_FDEKIT_VOICE` | unset | file of the author's own messages; relaxes dash and emoji rules to match |
| `TMN_FDEKIT_DATA` | `$CLAUDE_PLUGIN_DATA` or `~/.tmn-fdekit` | where traces, receipts and logs go |
| `TMN_FDEKIT_GATE_TAIL` | `25` | lines of a failing step shown by `gate.py` |
| `TMN_FDEKIT_HEALTH_URL` / `_TRIES` | unset / `60` | default health URL and seconds `stack.sh up` waits |
| `TMN_FDEKIT_TEST_RE` | built-in | regex for which changed files count as tests in `redgreen.sh` |

Telemetry variables for Langfuse, Phoenix or a collector come from
`scripts/otel_env.sh`. See the `tmn-trace` skill.

## Run modes

The skills run in one of two modes. `scripts/mode.py` prints the current one.

| Mode | What happens at a checkpoint |
|---|---|
| `standard` (default) | The agent stops, says what's ready and what the next step does, and waits for a yes. |
| `yolo` | The agent takes the step and keeps going, then reports every step with links at the end. |

A checkpoint is a push, a PR, a review or comment, a Slack message, a merge or
deploy, or the hand-off to the next skill (`tmn-debug` → `tmn-verify` →
`tmn-ship-pr` → `tmn-respond`).

Set it with `TMN_FDEKIT_MODE` for a session, or `"mode"` in `.tmn-fdekit.json`
for a repo. The environment wins. Saying "yolo" or "check with me first" in a
session overrides both for that session. An unknown value is an error, not a
quiet fallback.

Yolo removes pauses, not rules. The hooks block the same things in both
modes: self-approval, merging on red or pending checks, `--admin`, force
pushes to protected branches, and secrets in output. Read
[DISCLAIMER.md](../DISCLAIMER.md) before turning it on.

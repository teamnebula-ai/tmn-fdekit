# Configuration

Every limit, mode and rule in the kit can be changed. The easiest way is to
ask your agent to "set up the kit": the `tmn-setup` skill asks a few
questions and writes the file for you. This page is the reference.

## Where settings come from

Later layers win:

1. **Built-in defaults**, listed below.
2. **Your own file**, `~/.tmn-fdekit/config.json` (or the path in
   `TMN_FDEKIT_CONFIG`). For personal taste on your machine.
3. **The repo's file**, `.tmn-fdekit.json` at the repo root. Commit it so
   people, agents and CI share the same rules.
4. **Environment variables** set when the agent starts (table below).

Team rules (`rules`) add up across the two files instead of replacing each
other. `python3 scripts/config.py show` prints every setting and which layer
it came from.

## The settings file

Every key is optional. This shows the defaults, plus example commands and rules:

```json
{
  "mode": "standard",
  "pr": {
    "warn_lines": 400, "max_lines": 1000,
    "warn_files": 25,  "max_files": 50,
    "one_commit": false,
    "ticket_re": "\\b[A-Z][A-Z0-9]{1,9}-\\d+\\b|(?:closes|fixes|resolves|refs)\\s+#\\d+"
  },
  "guard": {
    "off": [],
    "protected": ["main", "master", "prod", "production", "release"],
    "allow_no_checks": false
  },
  "comms": { "mode": "block", "voice": null },
  "rules": {
    "all": ["Say 'shipped', not 'deployed'."],
    "tmn-slack": ["Up to eight sentences is fine in #eng."]
  },
  "lint": "make lint",
  "test": "make test",
  "up": "docker compose up -d --build --wait",
  "down": "docker compose down"
}
```

| Key | What it changes |
|---|---|
| `mode` | `standard` or `yolo`; see [Run modes](#run-modes) |
| `pr.warn_lines` / `pr.max_lines` | changed lines (lockfiles and generated files excluded) before `pr_check.py` warns or fails |
| `pr.warn_files` / `pr.max_files` | the same, for changed files |
| `pr.one_commit` | fail a PR with more than one commit |
| `pr.ticket_re` | the pattern that counts as a linked ticket |
| `guard.off` | guard rules to turn off: `merge-bypass`, `merge-unready`, `self-approve`, `approve-blind`, `approve-empty`, `comment-spam`, `force-push`, `protected-push`, `no-verify`, or `all` |
| `guard.protected` | branches nobody pushes to directly |
| `guard.allow_no_checks` | let a merge go ahead on a PR with no checks at all |
| `comms.mode` | `block`, `warn` (report AI-sounding text, don't block) or `off` |
| `comms.voice` | a file of your own messages; the lint matches its dashes and emoji |
| `rules.<skill>` / `rules.all` | plain-sentence team rules that win over a skill's own text |
| `lint`, `types`, `test`, `build`, `up`, `down` | the repo's commands, used by `gate.py` and `stack.sh` |

The size defaults follow published review research. Google's engineering
practices call about 100 changed lines reasonable and 1,000 usually too
large. SmartBear's study of code review at Cisco found defect detection drops
past 200 to 400 lines. Raise them if your team works differently.

### Changing settings from the command line

```bash
python3 scripts/config.py set pr.max_lines 1500 --scope repo
python3 scripts/config.py set guard.protected '["main","release"]' --scope repo
python3 scripts/config.py add-rule tmn-ship-pr "Squash-merge only." --scope repo
python3 scripts/config.py rules tmn-ship-pr     # what that skill will follow
python3 scripts/config.py validate
```

`set` refuses unknown keys, wrong types and a warn limit above its max, and
writes nothing when it refuses. A broken file is reported, never quietly
ignored.

### When a change takes effect

The guard and the comms lint read a copy of the settings taken when the
session starts. A change to `guard` or `comms` applies from the **next**
session, so an agent can't loosen its own guard halfway through a task by
editing a file. Limits, the mode and team rules, which the skills read
through `config.py`, apply right away.

If a file is broken when a session starts, the session uses the strict
defaults and the reason shows at the top of the session.

Team rules can't lift what the hooks block. Only `guard.off`, set by a
person, does that.

## Per session: environment variables

Set them in the `env` block of `settings.json` (or your shell) before the
agent starts. The agent can't change them from inside its own commands.
Each one overrides the matching setting in the files above.

| Variable | Default | Effect |
|---|---|---|
| `TMN_FDEKIT_CONFIG` | `~/.tmn-fdekit/config.json` | where your own settings file lives |
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

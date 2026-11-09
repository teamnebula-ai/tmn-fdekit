# tmn-fdekit

Staff-level engineering discipline for coding agents, from Team Nebula.

Agents don't usually fail by writing bad code. They fail by saying something
untrue with confidence: "tests pass", "merged", "reviewed". They also approve
their own work, post ten comments where one would do, and call a diff-only
read a review. This plugin makes the good habits the easy path, and makes the
amateur ones impossible.

- **Skills** hold the judgement: how to review adversarially, prove a change
  works, ship a small honest PR, answer review, debug from evidence, harden,
  write for people, and design UI that doesn't look generated.
- **Hooks and scripts** hold every rule that is a yes/no on data, so no model
  has to remember it and no prompt can talk its way past it.
- **Tracing** records everything the agent did at zero model-token cost, and
  can send Claude Code's own telemetry to Langfuse, Phoenix or any
  OpenTelemetry backend.

> **Use at your own judgement.** Agents with these skills push code, post
> reviews and send messages. You're responsible for what they do. Read
> [DISCLAIMER.md](DISCLAIMER.md) first.

## Install (for people)

You need `git`, `python3` 3.10+ and, for the installer, `node` 18+. `gh` is
needed for the GitHub checks, and `docker` only for compose projects.

**Claude Code** gets everything: skills, review agents and every hook.

```bash
claude plugin marketplace add teamnebula-ai/tmn-fdekit
claude plugin install tmn-fdekit@tmn-fdekit
```

Restart Claude Code, then type `/tmn-fdekit:` to see the skills. To update
later: `claude plugin marketplace update tmn-fdekit && claude plugin update tmn-fdekit@tmn-fdekit`.

**Codex, Cursor, Gemini CLI, Copilot, Windsurf/Devin, OpenCode or Amp:**

```bash
npx -y github:teamnebula-ai/tmn-fdekit install            # finds the agents on this machine
npx -y github:teamnebula-ai/tmn-fdekit install --target codex,cursor --project   # into this repo only
npx -y github:teamnebula-ai/tmn-fdekit hooks --target codex   # Codex runs the guard hooks too
```

**Claude.ai or Claude Desktop:** run `npx -y github:teamnebula-ai/tmn-fdekit zip`,
then upload each zip in Customize › Skills.

**Check it worked:** `npx -y github:teamnebula-ai/tmn-fdekit doctor` lists the
tools it found and where the skills are installed. Then ask your agent to
"review PR #12" or "make docs for this repo" and it picks the matching skill.

To pin a version, add the tag: `github:teamnebula-ai/tmn-fdekit#v0.5.0`. To
remove it: `npx -y github:teamnebula-ai/tmn-fdekit uninstall` (and
`hooks --remove`), which only deletes what it installed.

## Install (for agents)

If you're an agent asked to set this kit up, follow these steps in order and
report the output of the last one.

1. Check the prerequisites: `git --version`, `python3 --version` (3.10 or
   newer) and `node --version` (18 or newer). If one is missing, stop and
   tell the user which one.
2. Pick the install for the harness you're running in:
   - **Claude Code:** run `claude plugin marketplace add teamnebula-ai/tmn-fdekit`,
     then `claude plugin install tmn-fdekit@tmn-fdekit`. Tell the user to
     restart Claude Code, because skills load at startup.
   - **Anything else:** run `npx -y github:teamnebula-ai/tmn-fdekit install --target <agent>`,
     where `<agent>` is one of `claude`, `codex`, `cursor`, `gemini`,
     `copilot`, `devin`, `opencode`, `amp` or `agents`. Add `--project` only
     if the user wants it in this repo instead of their home folder.
   - **Codex:** also run `npx -y github:teamnebula-ai/tmn-fdekit hooks --target codex`.
3. Don't change the user's settings beyond that. Don't turn on `yolo` mode
   unless the user asks for it by name.
4. Run `npx -y github:teamnebula-ai/tmn-fdekit doctor` (Claude Code:
   `claude plugin list`) and show the user the result. Say "installed" only
   if that output shows the skills.

Once installed, load `tmn-staff-bar` at the start of real engineering work.
It sets the ground rules and the run mode the other skills follow.

| Doc | Covers |
|---|---|
| [Getting started](docs/getting-started.md) | install to first receipt in ten minutes |
| [Platforms](docs/platforms.md) | where skills go and what runs on each agent |
| [Hooks](docs/hooks.md) | every guard rule, the claims check, data on disk |
| [Scripts](docs/scripts.md) | gate, redgreen, stack, pr_check, slop, ui_lint, receipt, mode |
| [Configuration](docs/configuration.md) | `.tmn-fdekit.json`, environment variables, run modes |

## Skills, by tier

`tmn-fdekit` is Team Nebula's forward-deployed engineering kit: the version of
our engineering bar that we take to client work. Every skill is named
`tmn-<skill>` and every description starts with `(tmn)`, so it's clear which
skills come from the kit. In Claude Code the plugin shows them as
`/tmn-fdekit:tmn-<skill>`, for example `/tmn-fdekit:tmn-pr-review`. Four names
carry an extra word (`tmn-pr-review`, `tmn-ship-pr`, `tmn-harden-prod`,
`tmn-ui-design`) so they never clash with Team Nebula's internal `tmn-review`,
`tmn-ship`, `tmn-harden` and `tmn-design`.

| Tier | Skill | Use it to |
|---|---|---|
| 0 | `tmn-staff-bar` | the ground rules every other skill assumes |
| 1 | `tmn-verify` | prove your change works before saying "done" |
| 1 | `tmn-pr-review` | review someone else's PR: ticket first, lenses, run it, refute every finding, one comment |
| 1 | `tmn-ship-pr` | open and merge your own PR the right way |
| 1 | `tmn-respond` | handle review feedback without thrashing |
| 1 | `tmn-debug` | reproduce, narrow, explain, then fix with a failing test |
| 1 | `tmn-harden-prod` | security and failure modes, every finding proven |
| 2 | `tmn-write` | PRs, commits, tickets, docs and comments people actually read |
| 2 | `tmn-slack` | Slack messages a busy teammate reads once and acts on |
| 2 | `tmn-ui-design` | UI with a deliberate direction, an accessibility floor, no AI tells |
| 2 | `tmn-docs-site` | docs, guides and reference built as a one-file docs site (sidebar, search, Copy for LLM) to publish as an artifact |
| 3 | `tmn-trace` | read the session trace and receipts; set up Langfuse or OTel |
| 3 | `tmn-enforce` | put the same checks in a repo's CI, git hooks and GitHub rules |

Review agents: `lens-correctness`, `lens-security`, `lens-failure`,
`lens-tests`, and `verifier`, which tries to refute each finding before it's
reported.

The skills use only the open Agent Skills fields, so the same folder works in
every agent above. The hooks run in Claude Code and (beta) Codex. Everywhere
else, the `tmn-enforce` skill puts the same rules in CI and git hooks.

## Run modes: standard or yolo

Each skill has checkpoints: a push, a PR, a review or comment, a Slack
message, a merge, or the hand-off to the next skill (`tmn-debug` →
`tmn-verify` → `tmn-ship-pr` → `tmn-respond`).

| Mode | At a checkpoint |
|---|---|
| `standard` (default) | the agent stops, says what's ready, and waits for your yes |
| `yolo` | the agent keeps going and reports every step, with links, at the end |

Turn yolo on for a session with `TMN_FDEKIT_MODE=yolo`, for a repo with
`"mode": "yolo"` in `.tmn-fdekit.json`, or just say "yolo" to the agent.
Yolo removes the pauses, not the rules: the hooks below block the same things
in both modes.

## What the hooks enforce

| Hook | Blocks or records |
|---|---|
| guard (before Bash) | `--admin` or `--auto` merges; merging with red, pending or no checks, an open change request, or no approval on the head commit from someone who didn't write or push it; approving your own PR; approving with no passing test in the session; empty approvals; a second review comment in one session; plain `--force`; pushing to a protected branch; `--no-verify` |
| comms (before Bash and Slack sends) | PR bodies, review comments, commits and Slack messages with strong AI-slop tells |
| claims (on stop) | finishing with "tests pass", "merged" or "pushed" when the trace shows no such command succeeding after the last edit (one push back, then it lets go) |
| trace (every event, async) | one compact, secret-redacted line per tool call; no output, no tokens |
| receipt (on stop and session end) | a receipt per session: tests and results, edits, subagents, tokens |

A rule that's wrong for a repo can be turned off for the session in the
environment that launches the agent: `TMN_FDEKIT_GUARD_OFF=rule1,rule2`,
`TMN_FDEKIT_COMMS=warn|off`. A prefix typed into the agent's own command is
ignored, so the agent can't waive its own guard.

## Scripts you can run yourself

All in `scripts/`, standard library only:

```bash
python3 scripts/gate.py            # the repo's own lint/types/tests/build, short output, logs on disk
scripts/redgreen.sh origin/main 'python3 -m pytest -q {tests}'   # new tests fail on main, pass here
python3 scripts/pr_check.py --base origin/main --pr 42           # size, ticket, tests, secrets, paths, env
scripts/stack.sh up http://localhost:8000/health                 # start, wait for healthy; later: stack.sh down
python3 scripts/slop.py --target slack draft.txt                 # lint a message before sending
python3 scripts/ui_lint.py src/components/*.tsx                  # a11y footguns and design tells
python3 scripts/docs_site.py my-docs/ -o docs.html --style dark  # markdown folder -> one-file docs site
python3 scripts/receipt.py                                       # what this session actually ran
python3 scripts/mode.py --explain                                # standard or yolo, and where it came from
scripts/otel_env.sh langfuse https://cloud.langfuse.com          # telemetry env, never prints a secret
```

Per-repo settings live in `.tmn-fdekit.json`:

```json
{ "test": "make test", "up": "docker compose up -d --wait",
  "pr": { "max_lines": 500, "one_commit": true, "ticket_re": "[A-Z]+-\\d+" } }
```

## Develop

```bash
make check    # shellcheck, tests, plugin validation
```

See [AGENTS.md](AGENTS.md) for the rules on changing this repo.

## Prior art

Built on lessons from our own review history and on public work we learned
from: Anthropic's `code-review` and `pr-review-toolkit` plugins (parallel
lenses, one verifier per finding), obra/superpowers (verification before
completion, receiving review), Google's engineering practices guide, the
Claude Code OpenTelemetry docs, Langfuse and Arize Phoenix, impeccable,
Anthropic's `frontend-design`, Vercel's web interface guidelines, and the
humanizer and stop-slop writing skills. The text and code here are our own.

## License

[MIT](LICENSE). Provided as is; see [DISCLAIMER.md](DISCLAIMER.md).
Issues and pull requests are welcome. [AGENTS.md](AGENTS.md) has the rules for changes.

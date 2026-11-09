# Getting started

Ten minutes from install to your first receipt.

## 1. Install

Claude Code:

```bash
claude plugin marketplace add teamnebula-ai/tmn-fdekit
claude plugin install tmn-fdekit@tmn-fdekit
```

Any other agent: `npx -y github:teamnebula-ai/tmn-fdekit install`. See
[platforms.md](platforms.md) for each one.

Then check the tools the scripts need:

```bash
npx -y github:teamnebula-ai/tmn-fdekit doctor
```

## 2. Fit it to your team

Ask your agent to **"set up the kit"**. The `tmn-setup` skill asks about your
run mode, PR size limits, tickets, protected branches and writing style, plus
any skill rule that doesn't fit how you work. It writes the answers to your
settings file (`~/.tmn-fdekit/config.json`) or to the repo's
`.tmn-fdekit.json`. Every key is in [Configuration](configuration.md).

The scripts find your lint, test and run commands on their own. If they guess
wrong, add them to the same file:

```json
{ "test": "make test", "up": "docker compose up -d --wait", "pr": { "max_lines": 1500, "one_commit": true } }
```

Check what it found: `python3 <plugin>/scripts/gate.py --list`.

## 3. Use it

Ask the way you normally would. The skills trigger from the request:

| You say | Skill |
|---|---|
| "fix the login timeout" | `tmn-debug`, then `tmn-verify` |
| "review #128" | `tmn-pr-review` |
| "open a PR for this" | `tmn-ship-pr` |
| "address the review comments" | `tmn-respond` |
| "is this endpoint safe?" | `tmn-harden-prod` |
| "tell the team it's live" | `tmn-slack` |
| "make the settings page look better" | `tmn-ui-design` |
| "write docs for this CLI we can share" | `tmn-docs-site` |
| "what did the agent actually run?" | `tmn-trace` |

## 4. Read the receipt

After any session:

```bash
python3 <plugin>/scripts/receipt.py
```

It lists the tests that ran with their real results, the files edited,
subagents, guard blocks and token totals. It warns if code changed after the
last test run. Paste it under "How it was tested" in the PR.

## 5. Put the rules in the repo

Hooks only cover agents running the plugin. To hold every contributor, human
or agent, to the same checks, ask for the `tmn-enforce` skill. It adds a CI
workflow (PR hygiene, gate, red/green), git hooks, and a GitHub ruleset for
you to review and apply.

## When a hook blocks you

The message says which rule fired and what to do instead. Fix the cause, not
the rule. If a rule really doesn't fit a repo, turn it off in the launch
environment (`TMN_FDEKIT_GUARD_OFF=rule`). See
[configuration.md](configuration.md) and [hooks.md](hooks.md).

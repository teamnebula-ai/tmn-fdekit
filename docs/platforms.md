# Platforms

The skills use the open Agent Skills format, so one `skills/` folder works in
every agent below. What changes per platform is where the files go and
whether the hooks can run there.

| Agent | Skills (user) | Skills (project) | Hooks | Install |
|---|---|---|---|---|
| **Claude Code** | `$CLAUDE_CONFIG_DIR/skills` or `~/.claude/skills` | `.claude/skills` | full: guard, comms, trace, claims, receipts | the plugin, or `install --target claude` then `hooks` |
| **OpenAI Codex** | `~/.agents/skills` | `.agents/skills` | guard, trace, claims via `~/.codex/hooks.json` (beta) | `install --target codex`, then `hooks --target codex` |
| **Cursor** | `~/.cursor/skills` | `.cursor/skills` | not yet; use CI and git hooks | `install --target cursor` |
| **Gemini CLI** | `~/.gemini/skills` | `.gemini/skills` | not yet; use CI and git hooks | `install --target gemini` |
| **GitHub Copilot** | `~/.copilot/skills` | `.github/skills` | not yet; use CI and git hooks | `install --target copilot` |
| **Windsurf / Devin Desktop** | `~/.config/devin/skills` | `.devin/skills` | not yet; use CI and git hooks | `install --target devin` |
| **OpenCode** | `~/.config/opencode/skills` | `.opencode/skills` | not yet; use CI and git hooks | `install --target opencode` |
| **Amp** | `~/.config/amp/skills` | `.agents/skills` | not yet; use CI and git hooks | `install --target amp` |
| **Anything else that reads `~/.agents/skills`** | `~/.agents/skills` | `.agents/skills` | CI and git hooks | `install --target agents` |
| **Claude.ai / Claude Desktop** | upload in Customize › Skills | n/a | none | `zip`, then upload each zip |

Skills install as `tmn-<skill>` (for example `tmn-pr-review`), and every
description starts with `(tmn)`. In Claude Code the plugin gives them as
`/tmn-fdekit:tmn-<skill>`. Installing over an older version removes the
`tmn-fdekit-<skill>` folders it left behind, and never touches a folder the
installer didn't create.

Folders were checked against each vendor's docs on 2026-11-06. Agents move
their folders; if one stops picking the skills up, run `tmn-fdekit doctor`
and compare it with the vendor's current docs.

## Claude Code

The plugin is the complete install: skills, the review agents, and all hooks.

```bash
claude plugin marketplace add teamnebula-ai/tmn-fdekit
claude plugin install tmn-fdekit@tmn-fdekit
```

The repo is public, so no GitHub access is needed. If cloning over SSH fails
because there's no key on the machine, set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`.

Can't use plugins (a managed machine, or you want the files in the repo)? Use
the installer and add the hooks to `settings.json`:

```bash
npx -y github:teamnebula-ai/tmn-fdekit install --target claude
npx -y github:teamnebula-ai/tmn-fdekit hooks                # or --project for .claude/settings.json
```

Don't run both the plugin and `hooks`, or every hook fires twice.

## Codex

```bash
npx -y github:teamnebula-ai/tmn-fdekit install --target codex
npx -y github:teamnebula-ai/tmn-fdekit hooks --target codex
```

Codex hooks use the same shape as Claude Code's. Codex asks you to approve
each new hook: open `/hooks` in Codex and approve them. The guard reads any
tool that carries a `command`, so it works with Codex's shell tool. Codex
support for the comms and trace hooks is beta, so check the receipt after your
first session.

## Cursor, Gemini, Copilot, Devin, OpenCode, Amp

```bash
npx -y github:teamnebula-ai/tmn-fdekit install                    # finds the agents on this machine
npx -y github:teamnebula-ai/tmn-fdekit install --target cursor,gemini --project
```

These agents load the skills, and the skills call the same scripts (`gate.py`,
`redgreen.sh`, `pr_check.py` and the rest). The guard and trace hooks don't
run in them yet, so the rules reach them through the repo instead. Use the
`tmn-enforce` skill to add the CI workflow and git hooks, and those rules hold for
every contributor on every tool.

## Claude.ai and Claude Desktop

```bash
npx -y github:teamnebula-ai/tmn-fdekit zip --out dist
```

That builds one zip per skill, each carrying its own copy of the scripts, with
descriptions trimmed to Claude.ai's 200-character limit. Upload them in
Customize › Skills. The scripts run in Claude's sandbox there,
so steps that need your machine (`gh`, `docker`, your repo) only work where
the sandbox can reach them.

## Updating and removing

```bash
npx -y github:teamnebula-ai/tmn-fdekit install            # re-run to update; it replaces only what it installed
npx -y github:teamnebula-ai/tmn-fdekit uninstall           # removes only what it installed
npx -y github:teamnebula-ai/tmn-fdekit hooks --remove
npx -y github:teamnebula-ai/tmn-fdekit doctor              # tools, and where skills are installed
```

The installer never overwrites a skill folder it didn't create unless you pass
`--force`. Pin a version for repeatable installs:
`npx -y github:teamnebula-ai/tmn-fdekit#v0.5.0 install`.

## Requirements

- `python3` 3.10 or newer, and `git`, for every hook and script
- `gh`, authenticated, for review, merge and PR checks
- `node` 18 or newer, only for the installer
- `docker`, only for `stack.sh` on compose projects

# Install tmn-fdekit (for agents)

You're an agent, and someone asked you to add this kit to their setup. Follow
these steps in order. They work in any agent that reads Agent Skills (folders
with a `SKILL.md`): Claude Code, Codex, Antigravity, Cursor, OpenCode, Gemini
CLI, Copilot, Windsurf/Devin, Amp, and anything that reads `~/.agents/skills`.

## 1. Check what's on the machine

```bash
git --version
python3 --version   # 3.10 or newer: every script and hook needs it
node --version      # 18 or newer: only the installer needs it
```

If one is missing, stop and tell the person which one. `gh` (signed in) is
needed later for reviews and merges, but not to install.

## 2. Work out which agent you are

You usually know. If you don't, ask the person. Then find your row:

| You are running in | Target | Hooks too? |
|---|---|---|
| Claude Code | use the plugin (step 3a) | included in the plugin |
| OpenAI Codex | `--target codex` | yes, `hooks --target codex` |
| Google Antigravity | `--target antigravity` | no |
| Cursor | `--target cursor` | no |
| OpenCode | `--target opencode` | no |
| Gemini CLI | `--target gemini` | no |
| GitHub Copilot | `--target copilot` | no |
| Windsurf / Devin Desktop | `--target devin` | no |
| Amp | `--target amp` | no |
| Claude Code without plugins | `--target claude` | yes, `hooks` |
| Anything else that reads `~/.agents/skills` | `--target agents` | no |
| Claude.ai or Claude Desktop | `zip --out dist`, then the person uploads each zip in Customize › Skills | no |

Ask one question before installing: **for you on this machine, or for this
repo?** For this machine, install as shown. For this repo, add `--project`
so the skills land in the repo and the team gets them through git.

## 3. Install

**3a. Claude Code**

```bash
claude plugin marketplace add teamnebula-ai/tmn-fdekit
claude plugin install tmn-fdekit@tmn-fdekit
```

If cloning fails over SSH, set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` and run it again.

**3b. Every other agent**

```bash
npx -y github:teamnebula-ai/tmn-fdekit#v0.6.1 install --target <target>
npx -y github:teamnebula-ai/tmn-fdekit#v0.6.1 hooks --target codex     # Codex only
```

`--target` takes a comma-separated list (`--target cursor,opencode`), `auto`
(the agents found on this machine) or `all`. The installer never overwrites a
skill folder it didn't create.

## 4. Check it took

```bash
npx -y github:teamnebula-ai/tmn-fdekit#v0.6.1 doctor     # Claude Code: claude plugin list
```

Show the person the output. Say "installed" only if it lists the skills in
the folder for their agent. Then tell them what to do next:

- **Claude Code, Codex, Cursor, Antigravity:** restart the agent or open a new
  session, because skills load at startup. The Antigravity CLI can use
  `/skills reload` instead.
- **Codex:** open `/hooks` and approve the new hooks.
- **Agents without hooks** (every row marked "no" above): the guard and trace
  hooks don't run there. Offer the `tmn-enforce` skill, which adds the CI
  workflow and git hooks so the same rules hold on every tool.

## 5. Offer setup, change nothing yet

Offer to run the `tmn-setup` skill so the PR limits, run mode and team rules
fit how the person works. Don't change a setting without their answers, and
don't turn on `yolo` mode unless they ask for it by name. Point them to
`DISCLAIMER.md` first if they do.

## What you get

14 skills, each named `tmn-<skill>` with a description that starts with
`(tmn)`. Load `tmn-staff-bar` at the start of real engineering work: it sets
the ground rules, the run mode and the team rules the other skills follow.
Every skill reads team rules from `config.py rules <skill>` and follows them
over its own text.

## Updating and removing

```bash
npx -y github:teamnebula-ai/tmn-fdekit install --target <target>     # re-run to update
npx -y github:teamnebula-ai/tmn-fdekit uninstall --target <target>   # removes only what it installed
claude plugin update tmn-fdekit@tmn-fdekit                           # Claude Code
```

Folders per agent, and what runs where: `docs/platforms.md`.

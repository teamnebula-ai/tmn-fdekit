---
name: tmn-setup
description: (tmn) Onboard a person or a team to the kit and tailor it to how they work - run mode (standard or yolo), PR size limits, one-commit and ticket rules, protected branches, comms lint, the repo's own commands, and team rules that override any skill's defaults - then write and validate the settings file. Use after installing tmn-fdekit, or when someone says "set up the kit", "onboard me", "customize the skills", "our PRs are bigger than that", "turn off this rule", "change the limits", "we don't use tickets", "make it yolo", or when a kit rule keeps getting in the way of how the team works.
---

# Set up the kit

The skills ship with sensible defaults, and every team is different. This
skill learns how the team works and writes it down once, in a settings file
the skills and hooks all read. Nothing about the kit is meant to be static.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both.

Scripts are in `${CLAUDE_PLUGIN_ROOT}/scripts/`. The settings tool is
`config.py`; run it with `--help` for every command.

## 1. See where things stand

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py show       # every setting and where it came from
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py path       # the user file and this repo's file
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/detect.py            # the repo's own lint, test, build, run commands
```

If `show` fails, a file is broken. Read the error out to the person and fix
that first.

## 2. Ask, in two short rounds

Ask plainly, offer the default as the first choice, and accept "defaults are
fine" as an answer to everything. Don't ask what you can read from the repo.

**Round 1: scope and pace**

- **Who is this for?** Just them (the user file, on this machine) or the
  whole team on this repo (`.tmn-fdekit.json`, committed so people, agents
  and CI share it). Personal taste goes in the user file; team rules go in
  the repo.
- **Run mode.** `standard` stops before each push, PR, review, message and
  hand-off. `yolo` runs the chain and reports at the end. Suggest standard
  for a new team or a production repo, and point to `DISCLAIMER.md` before
  anyone picks yolo.

**Round 2: the rules that vary most between teams**

| Setting | Default | Ask |
|---|---|---|
| `pr.warn_lines` / `pr.max_lines` | 400 / 1000 | "How big do your PRs usually get? Past the max, the PR check fails." |
| `pr.warn_files` / `pr.max_files` | 25 / 50 | only if they said PRs touch many files |
| `pr.one_commit` | false | "Do you squash to one commit per PR?" |
| `pr.ticket_re` | Jira/Linear keys, `closes #12`, Linear and Jira URLs | "Where do tickets live?" Set a pattern that matches their keys. |
| `guard.protected` | main, master, prod, production, release | "Which branches should nobody push to directly?" |
| `comms.mode` | block | `warn` reports AI-sounding text without blocking; `off` turns the lint off |
| `comms.voice` | none | "Is there a file of your own messages I can match your style to?" |
| `guard.off` | none | only when a guard rule is wrong for them; say what the rule protects first |

The defaults come from published review research. Google's guide calls about
100 changed lines a reasonable change and 1,000 usually too large. SmartBear's
study at Cisco found reviewers catch fewer defects past 200 to 400 lines.
If a team wants bigger, set it and say that once; it's their call.

Then ask: **"Is there anything a skill does that doesn't fit how you work?"**
Each answer becomes a team rule (step 3).

## 3. Turn their answers into settings

Prefer a setting when one exists; use a team rule for everything else.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py set mode standard --scope repo
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py set pr.max_lines 1500 --scope repo
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py set guard.protected '["main","release"]' --scope repo
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py add-rule tmn-slack "Up to eight sentences is fine in #eng." --scope repo
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py add-rule all "Say 'shipped', not 'deployed'." --scope user
```

- `set` refuses an unknown key, a wrong type, or a warn limit above its max,
  and writes nothing when it refuses. Read the error and fix the value.
- A team rule is one plain sentence a skill can follow. Name the skill
  (`tmn-ship-pr`, `tmn-slack`...) or use `all`. Every skill reads its rules
  through `config.py rules <skill>` and follows them over its own text.
- Team rules can't remove the hard lines in `tmn-staff-bar`: no self-approval,
  no `--admin`, no secrets, no production data. If a request needs one of
  those gone, say which line it is and that only a guard setting
  (`guard.off`), chosen by a person, can change what the hooks block.
- In standard mode, show the planned settings as a short list and wait for a
  yes before running `set`.

## 4. Check it took

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py validate
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py show
```

Tell the person three things:

1. What changed, as a short list in plain words.
2. **Guard and comms changes apply from the next session.** The hooks read
   the settings frozen when a session starts, so an agent can't loosen its
   own guard partway through a task. Limits, mode and team rules that skills
   read through `config.py` apply right away.
3. For the repo file: it should go in through a normal PR (`tmn-ship-pr`) so
   the team sees and approves its own rules.

## Done means

- `config.py validate` prints "settings OK".
- `config.py show` lists every changed setting with the right source.
- The person heard what changed and when it takes effect.

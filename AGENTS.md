# AGENTS.md

Instructions for any agent (Claude Code, Codex, Cursor) changing this repo.

## What this is

`tmn-fdekit` is a Claude Code plugin, and a set of portable Agent Skills,
that hold coding agents to a staff-engineer bar: review that runs the code,
proof before "done", small honest PRs, plain-language comms, and a zero-token
trace of what the agent did. Skills hold judgement. Scripts and hooks hold
every rule that can be checked mechanically.

## Layout

| Path | What lives there |
|---|---|
| `skills/<name>/SKILL.md` | one skill per use case; frontmatter uses only Agent Skills standard fields |
| `agents/*.md` | review lens agents and the finding verifier |
| `hooks/hooks.json` | guard, comms lint, trace, claims check, receipts |
| `scripts/` | standard-library Python and bash; no dependencies |
| `templates/` | CI workflow, lefthook config, GitHub ruleset to copy into a repo |
| `cli/tmn-fdekit.mjs` | zero-dependency installer behind `npx github:teamnebula-ai/tmn-fdekit` |
| `docs/` | getting started, platforms, hooks, scripts, configuration (incl. run modes) |
| `tests/` | `unittest` suites; fake `gh` on PATH, throwaway git repos |

## Rules for changes

1. **A yes/no rule goes in a script or hook, with a test.** Prose is for
   judgement. If you add a rule to a skill that a script could check, write
   the script instead.
2. **Test first.** Add the failing case to `tests/`, then make it pass.
   `make check` must be green: shellcheck, Python and Node tests, `claude plugin validate --strict`.
   When an agent changes where it reads skills, update `TARGETS` in the CLI and `docs/platforms.md` together.
3. **Hooks never spend tokens by accident.** Trace hooks are async, print
   nothing and exit 0. Blocking hooks print one actionable reason to stderr
   and exit 2. A hook must never be waivable by text the agent types into its
   own command.
4. **Nothing private ships.** No client, project or person names, no machine
   paths, no internal URLs or IDs. `tests/test_repo.py` enforces the common
   ones. Examples use invented names.
5. **Skills stay under 500 lines.** Push detail into `references/`, and say
   when to read it.
6. **Write like the `tmn-write` skill says.** The skill examples must pass
   `scripts/slop.py`, and a test checks this.

## Workflow

```bash
git checkout -b <type>/<short-name>
make check
claude --plugin-dir .        # try it live in a session
gh pr create                 # a reviewer who did not write it approves
```

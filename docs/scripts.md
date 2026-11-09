# Scripts reference

Standard-library Python 3.10+ and bash. Run from inside the repo you're
working on. Each one keeps output short on purpose: full logs go to disk, and
the terminal gets the verdict.

| Script | What it does | Exit code |
|---|---|---|
| `detect.py [dir]` | JSON of the repo's lint, types, test, build, up and down commands, with where each came from | 0 |
| `gate.py [steps] [--list]` | runs lint → types → test → build; one line per step, a failure tail and a log path | 0 only if all pass; a missing test step fails |
| `redgreen.sh <base> '<cmd {tests}>'` | runs the changed tests on the base branch (must fail) and here (must pass) | 0 red-then-green, 1 not proven, 2 usage |
| `stack.sh up [url] \| check url \| logs [n] \| down` | starts the app, waits for a 2xx/3xx, stops exactly what it started | 1 if it never answers |
| `pr_check.py [--base ref] [--body f \| --pr n] [--json]` | size, commits, ticket, tests, secrets, personal paths, env parity, unbacked claims | 1 on any FAIL |
| `slop.py [--target t] [--voice f] [file]` | AI-slop lint for slack, pr, review, commit, ticket, doc, chat | 1 on a strong finding or 3+ medium |
| `docs_site.py <folder> -o <file>` | a markdown folder becomes one self-contained docs-site page: sidebar, search, "On this page", Copy for LLM, light and dark; styles `clean`, `warm`, `dark` | 1 when the nav names a missing page |
| `ui_lint.py <files>` | accessibility footguns (errors) and AI design tells (warnings) in html/css/jsx/tsx/vue/svelte | 1 on errors |
| `receipt.py [--session id] [--json]` | what a session actually ran, from the trace | 0 |
| `mode.py [--explain]` | the run mode the skills follow: `standard` or `yolo` (env, then `.tmn-fdekit.json`) | 0, or 1 on an unknown value |
| `otel_env.sh langfuse\|collector\|phoenix\|off [url]` | shell lines that send Claude Code telemetry to a backend; never prints a secret | 0 |

## How commands are discovered

`detect.py` takes the first match for each step:

1. `.tmn-fdekit.json` in the repo root
2. `.claude/project.json` (`lint`, `typecheck`, `test`, `build`, `run`)
3. `Makefile` targets (`lint`; `typecheck`/`types`; `test`/`check`; `build`; `up`/`dev`/`run`; `down`)
4. `package.json` scripts, with the package manager taken from the lockfile
5. Python, Go and Rust conventions (ruff, mypy, pytest; go vet/test; clippy, cargo test)
6. A compose file (`docker compose up -d --build --wait`)

The repo's own command always wins over a convention.

## Examples

```bash
python3 scripts/gate.py --list
python3 scripts/gate.py test
scripts/redgreen.sh origin/main 'npx vitest run {tests}'
scripts/redgreen.sh origin/main 'go test ./...'
scripts/stack.sh up http://localhost:3000/api/health && curl -s localhost:3000/api/orders/41 && scripts/stack.sh down
python3 scripts/pr_check.py --base origin/dev --pr 128
python3 scripts/slop.py --target slack --voice ~/.config/my-voice.txt draft.txt
```

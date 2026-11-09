---
name: tmn-staff-bar
description: (tmn) The ground rules a staff engineer holds an agent to on any code change - evidence before claims, scoped work, separation of duties, receipts, cleanup. Load this at the start of any non-trivial engineering task (building, fixing, reviewing, shipping, debugging) and whenever you are about to say something is done, passing, merged or safe. The other tmn-fdekit skills assume it.
---

# The staff bar

Most damage an agent does is not bad code. It is a confident sentence that
isn't true: "tests pass", "merged", "fixed", "safe to ship". A staff engineer
is trusted because their claims check out. These rules exist to make yours
check out too.

## 1. Evidence, not vibes

Every claim names the thing that proves it: the command and its real output,
the line of code, the URL you loaded, the row you read back.

- Run it, then say it. Never report a result before the tool that proves it
  has returned. If you didn't run it, say "not run".
- Prove the right property. A green suite that can't see the failure mode is a
  pass on the wrong question. Ask "would this test fail if the bug came back?"
  and check with `scripts/redgreen.sh`.
- Read the end state after any action with a visible result (push, merge,
  deploy, comment that triggers a bot). Unchecked means "sent, not confirmed".
- When you were wrong earlier, say "Correction:" early and plainly.

The plugin's Stop hook compares your final message with what the session trace
recorded. If you claim the tests pass and no passing run follows your last
edit, it sends you back to run them. That hook is the backstop; this rule is
the habit.

## 2. Do the job you were given

- Stay inside the ticket. Anything else you find becomes a note or a new
  ticket, not a bigger diff.
- Small PRs: one thing each, under the repo's limits (`config.py show`; by
  default a warning past 400 changed lines and a failure past 1,000). Big
  PRs get skimmed, not reviewed.
- If the spec is thin, ask before building on a guess you can't cheaply undo.
  Ask one or two sharp questions, not ten.

## 3. Separation of duties

- The author never approves their own work, whether it's a human, an agent, or
  an agent pushing as a human's account. A second agent instance reviewing the
  first one's PR under the same account is still self-review.
- Never bypass protection: no `--admin`, no `--auto`, no `--no-verify`, no
  plain `--force`. If a required review or check blocks you, leave it blocked
  and say so.
- Wait for every check, including the non-required ones, before merging.
  Pending is not green.

The guard hook enforces these. Don't look for a way around it. If a rule is
genuinely wrong for a repo, the human turns it off in the launch environment.

## 4. Fail loudly

- No hardcoded fallback for a person, key, org, URL or path. A missing
  required setting stops the program with a clear message.
- Never treat a failure as "no data". A dead token returning an empty list is
  an error, not an empty result.
- Every write names the exact row and its owner (tenant, org, user). Never
  write by name or by re-running a loose filter.

## 5. Keep the receipts, not the noise

- Run the repo's gate through `scripts/gate.py`. It writes full logs to disk
  and gives you one line per step, so a 4,000-line test log doesn't sit in
  your context for the rest of the session.
- The trace hooks record every tool call at zero model cost.
  `scripts/receipt.py` turns that into the "How it was tested" block for a PR.
  Paste it instead of retyping results from memory.
- Read big outputs in bounded slices (`head`, `tail`, `rg`), never whole.

## 6. Leave the machine as you found it

Stop every process you started (`scripts/stack.sh down`), remove worktrees
and scratch files you created, run one test suite at a time, never in watch
mode. Before you report done, list anything you started that is still running.
The target is an empty list.

## 7. Modes: standard or yolo

Every skill runs in one of two modes. Check it once per task with
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/mode.py`. The user's own words in this
session win over the setting: "yolo", "don't stop" or "run it end to end"
mean yolo, and "check with me first" means standard.

A **checkpoint** is any step that acts outside this machine, or hands the
work to the next skill:

- pushing a branch, opening or updating a PR, requesting reviewers
- posting a review or a comment, sending a Slack message
- merging, deploying, or anything a bot reacts to
- moving to the next skill in the chain: `tmn-debug` → `tmn-verify` →
  `tmn-ship-pr` → `tmn-respond`

| | standard (default) | yolo |
|---|---|---|
| At a checkpoint | stop, say what's ready and what the next step does, wait for a yes | take it and keep going |
| A yes covers | that one step | the whole chain |
| A decision that belongs to someone else (a reviewer, the code's owner) | name them and hand it over | name them and hand it over |
| At the end | report what was done | report every step taken, with links |

Yolo removes the pauses, not the rules. In both modes the hooks still block,
nobody approves their own work, nothing merges on a red or pending check,
there's no `--admin` or force push, no secret is printed, production data is
never touched, and every result is read back before it's reported. If yolo
hits one of those lines, stop and say so; that's not a checkpoint to skip.

## 8. Team settings and rules win

The kit's defaults are a starting point, not a fixed policy. Teams change
them with the `tmn-setup` skill, and the result lives in one settings file
(`config.py` explains the layers).

- Before following any skill, run
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/config.py rules <skill>`. A team rule
  wins over the skill's own text.
- Limits (PR size, protected branches, ticket pattern) come from
  `config.py show`, not from numbers written in a skill.
- Team rules can't lift the hard lines in section 7. Only a person, through
  the guard settings, changes what the hooks block, and that takes effect
  from the next session.
- If a rule keeps getting in the way of how the team works, say so and offer
  `tmn-setup`, rather than working around it.

## Where things are

The scripts live in this plugin's `scripts/` folder, `${CLAUDE_PLUGIN_ROOT}/scripts/`.
If that variable isn't expanded in your harness, it is two folders above this
file. Each script prints its usage with `--help` or no arguments:

| Script | Use it to |
|---|---|
| `detect.py` | find the repo's own lint, type, test, build and run commands |
| `gate.py` | run them with short output and logs on disk |
| `redgreen.sh` | prove new tests fail on the base branch and pass on yours |
| `stack.sh` | start the app, wait until it answers, stop it |
| `pr_check.py` | size, commits, ticket, tests, secrets, paths, env parity |
| `slop.py` | lint a PR body, review comment, commit or Slack message |
| `receipt.py` | print what this session actually ran |
| `mode.py` | print the run mode: standard or yolo |
| `config.py` | show or change the settings and team rules (`show`, `rules`, `set`) |

## Skill tiers

Pick the narrowest skill that fits. Each one loads only what it needs.

- **Tier 0, always:** `tmn-staff-bar` (this file).
- **Tier 1, the work:** `tmn-verify` (prove it works), `tmn-pr-review` (someone else's
  PR), `tmn-ship-pr` (open your own PR), `tmn-respond` (answer review on your PR),
  `tmn-debug` (find a root cause), `tmn-harden-prod` (security and failure modes).
- **Tier 2, the craft:** `tmn-write` (anything a person reads), `tmn-slack` (send a
  Slack message), `tmn-ui-design` (UI work), `tmn-docs-site` (docs people browse and share).
- **Tier 3, setup:** `tmn-setup` (onboard and customize the kit), `tmn-trace`
  (observability backend, receipts), `tmn-enforce` (wire the same checks into a
  repo's git hooks and CI).

---
name: tmn-enforce
description: (tmn) Wire the plugin's deterministic checks into a repository so they hold for every contributor, human or agent - a CI job for PR hygiene and the test gate, local git hooks, and GitHub rules that stop self-approval, stale approvals and merges on red. Use when setting up a repo, when asked to "enforce" review or test rules, add a PR check, add pre-commit or pre-push hooks, set branch protection or rulesets, or when you notice a rule that only lives in a prompt.
---

# Enforce

If a rule can be answered yes or no from data, it belongs in a check, not in a
prompt. Prompts get skipped under pressure; checks don't. The plugin's hooks
cover agents running Claude Code. This skill puts the same rules where
everyone hits them: in git and in CI.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-enforce` override anything else in this skill.

Templates are in `${CLAUDE_PLUGIN_ROOT}/templates/`. Copy them into the repo,
don't link to them, so the repo stands alone.

## 1. Look before adding

Read what the repo already has: `.github/workflows/`, `lefthook.yml`,
`.pre-commit-config.yaml`, `.husky/`, `Makefile`, CONTRIBUTING.md. Extend the
existing runner. Don't add a second one.

## 2. CI: the check nobody can skip

Copy the plugin's `scripts/` folder to `.github/tmn-fdekit/scripts/` and
`templates/github/tmn-fdekit.yml` to `.github/workflows/`. Vendoring the
scripts means CI needs no token and pins the exact version the repo reviewed.
Add the repo's own setup steps (language runtime, dependency install) to the
`gate` and `redgreen` jobs. On every PR it runs:

- `pr_check.py`: size, one commit (when configured), ticket link, a changed
  test or a `Why no tests:` line, secrets, personal paths, env vars missing
  from `.env.example`.
- `gate.py`: the repo's own lint, types and tests, found by `detect.py`.
- `redgreen.sh` on the new tests, as a separate job, so "tests prove nothing"
  shows up as its own red check.

Repo-specific limits go in `.tmn-fdekit.json` at the root (see the comment at
the top of `scripts/pr_check.py`). Commit the file so humans and CI share the
same limits.

## 3. Local hooks: fast feedback

Copy `templates/lefthook.yml` (or add the same commands to the existing
pre-commit config). It runs the PR hygiene check and the gate before each push. Local hooks are a convenience, because anyone can skip them. CI is
the control.

## 4. Server rules: separation of duties

On GitHub, add a ruleset for the default and release branches
(`templates/github/ruleset.json`, applied with
`gh api -X POST repos/<owner>/<repo>/rulesets --input ruleset.json`):

- a pull request is required, with at least 1 approval
- **"Require approval of the most recent reviewable push"**: whoever pushed
  last can't be the approver. This stops an author's agent approving its own
  final push.
- dismiss stale approvals when new commits are pushed
- code owner review on sensitive paths (auth, migrations, CI config, CODEOWNERS)
- required status checks: the workflow above plus the repo's tests
- resolve all review threads before merge
- an empty bypass list

Rulesets and branch protection on **private** repos need a paid GitHub plan
(Team or above). Without one, the API answers "Upgrade to GitHub Pro" and
nothing is enforced on the server. If that's the case, say so plainly to the
owner. Until it's fixed, the CI check and the agent-side guard are the only
controls, and a person can still merge around them.

Changing rulesets, CODEOWNERS or who may approve is the repo owner's call.
Prepare the change, and let them apply it.

## 5. Agents get their own identity

Agents that open PRs should push as a bot or GitHub App identity, not a
person's account, and a different identity (or a person) approves. Exempt
bots by app id or `user.type == "Bot"`, never by a branch or user name that
anyone could pick.

## 6. Prove the checks work

Open a throwaway PR that breaks each rule once: no ticket, no test, a fake key
(`AKIA` plus 16 capitals), an approval by the author. Watch each one go red,
then close the PR and delete the branch. A check you haven't seen fail is a
check you're only hoping works.

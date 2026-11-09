---
name: tmn-pr-review
description: (tmn) Staff-level adversarial review of a pull request or diff - resolve the ticket, run the deterministic checks, review through independent lenses, run the code and drive the changed path, try to refute every finding before reporting it, then post one calibrated comment. Use whenever asked to review a PR, check a diff, decide if something is safe to merge, re-review after changes, or approve anything, even if the user just says "take a look at #123" or "is this good to go".
---

# Review

The job is to find the bug before production does, prove it, and say it once,
clearly. It is not to look thorough. A review with three confirmed findings
beats one with twenty guesses, and "no issues found, here is what I ran" is a
good review.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-pr-review` override anything else in this skill.

Read `tmn-staff-bar` first if it isn't loaded. Scripts are in `${CLAUDE_PLUGIN_ROOT}/scripts/`.

## Step 0: should this review happen at all?

Stop, or change mode, when:

- **The PR is a draft or closed.** Don't review it unless the user asks.
- **You already reviewed this exact head commit.** Say so. On a re-review,
  review only what changed since the commit you last reviewed
  (`git diff <last-reviewed-sha>..HEAD`), and edit your earlier comment
  instead of posting a new one.
- **You (or the account you act as) wrote it.** You may review it to find
  problems, but you will not approve it. Report the findings in chat, or as
  one comment, and say it needs another reviewer.
- **It is over the repo's PR limit** (`pr.max_lines` in `config.py show`,
  1,000 by default). Say it should be split, and review it anyway if asked.
  Note that a review at this size is shallower.
- **The work is still in flight.** Uncommitted or unpushed work isn't yours
  to review yet. Ask the author.
- **You can't get what a review needs.** If the ticket won't load, the diff
  fetch fails, or the API returns an error, the result is "not reviewed:
  <reason>". Tell the user and post nothing on the PR. A tool error is never a
  finding: a review bot that reported "the base branch no longer exists" off
  a failed API call, and re-posted it every hour, taught a team to ignore
  every bot comment after it.

## Step 1: build the context pack

Give the review the same facts the author had, and nothing from the author's
own reasoning.

1. **The ticket.** Find it from the PR body, branch or commits. Read every
   acceptance criterion and every spec or design doc it links. If the PR cites
   another ticket to justify skipping scope, open that ticket and check it says
   so. No ticket: ask for one before going further.
2. **The PR body, the diff, the changed-file list, and CI state**
   (`gh pr view <n> --json title,body,headRefOid,statusCheckRollup,files`,
   `gh pr diff <n>`).
3. **The repo's rules**: AGENTS.md, CLAUDE.md, CONTRIBUTING.md in the changed
   directories and the root.
4. **A worktree at the PR head**, so you read whole files, not diff hunks:
   `git worktree add <scratch>/pr-<n> <head-sha>`. A diff hides the missing
   mechanism; the file shows it.

Never review from the author's transcript or summary. Reviewers who share the
author's reasoning miss the author's blind spots.

## Step 2: run the facts first

These checks cost no judgement, so run them before you form opinions:

```bash
cd <worktree>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr_check.py" --base origin/<base> --pr <n>   # size, ticket, tests, secrets, paths, env
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py"                                     # the repo's own lint/types/tests
"${CLAUDE_PLUGIN_ROOT}/scripts/redgreen.sh" origin/<base> '<test cmd> {tests}'       # do the new tests catch anything?
```

A red gate is a finding, not a reason to skip the rest. A redgreen failure
("the new tests pass on the old code too") is one of the most valuable
findings you can make, because it means the tests prove nothing.

## Step 3: review through lenses

Each lens is a narrow question asked of the whole change. Narrow questions
find things a single "review this" pass skims over. The lenses and what each
looks for are in [references/lenses.md](references/lenses.md).

- **Small change** (under ~150 lines, one area): work the lenses yourself in
  one pass. Spawning agents costs more than it finds here.
- **Larger or risky change** (auth, data writes, migrations, money, anything
  customer-facing): run the lens agents in parallel, each with the context
  pack and the worktree path: `tmn-fdekit:lens-correctness`,
  `tmn-fdekit:lens-security`, `tmn-fdekit:lens-failure`,
  `tmn-fdekit:lens-tests`. Each returns findings in the schema below.

Always check the acceptance criteria yourself. That lens needs the whole
picture.

## Step 4: run it

Reading isn't reviewing behaviour. For anything that changes what runs:

- Start it: `scripts/stack.sh up <health-url>`, or the repo's own command.
- Drive the changed path the way a user or caller would. Hit the endpoint with
  `curl`, run the CLI with the new flag, click the flow in a browser. Try the
  empty case, the wrong-tenant case, and the failure case, not just the happy
  path.
- Write down what you saw. That goes in the comment.
- Stop it: `scripts/stack.sh down`.

If you can't run it (no environment, missing secrets), say exactly that in the
review and don't approve. You can still comment.

## Step 5: try to break every finding

Every candidate finding goes through a refutation pass before anyone else
sees it. The finder is biased toward its own finding; the verifier's job is to
prove it wrong.

- For each finding, ask: can I make it happen? Write the smallest repro (a
  failing test, a curl, a script) and run it. If it reproduces, it's
  confirmed, and the repro is the evidence.
- If you can't reproduce it but the code clearly shows it (a missing tenant
  filter on a write, a secret in the diff), it's confirmed by reading. Quote
  the line.
- If you can't do either, it isn't a finding. Make it a question
  ("What happens if `items` is empty here?") or drop it.
- On larger reviews, give each finding to `tmn-fdekit:verifier` in parallel.
  It returns confirmed, refuted, or unprovable, and re-scores severity.

Drop all of these without posting:

- Problems that existed before this PR (unless the PR makes them worse).
- Anything a linter or type checker in the repo would catch.
- Style preferences the repo's rules don't state.
- Generic advice ("consider adding tests", "think about security") with no
  specific line and failure.
- Anything already discussed and answered in the PR thread. Read the thread first.

## Step 6: calibrate and cap

Severity, set after verification:

| Severity | Means | Effect |
|---|---|---|
| **blocker** | wrong behaviour, data loss or leak, security hole, unmet acceptance criterion, red gate, tests that prove nothing | request changes |
| **major** | likely bug in a realistic case, missing failure handling, a risky default | request changes, or comment if the author can't fix it here |
| **minor** | real but low-impact; clarity that will cost the next reader | comment |
| **nit** | taste | one line at the end, or nothing |

Post at most 7 findings, blockers first. Merge duplicates by root cause. If
you have more than 7, the PR is probably too big. Say that instead of listing
them all.

## Step 7: write one comment

One review, one comment, using the format in
[references/comment.md](references/comment.md). It carries the verdict, the
acceptance-criteria table, the findings, and what was run (the "Checked" block). Lint it before
posting: `scripts/slop.py --target review <file>`.

```bash
gh pr review <n> --request-changes --body-file review.md   # confirmed blocker
gh pr review <n> --comment        --body-file review.md    # questions or minor issues only
gh pr review <n> --approve        --body-file review.md    # you ran it, it meets the ticket, you are not the author
```

On a re-review, update the earlier comment (`gh pr comment <n> --edit-last
--body-file review.md`). Name the new head commit, and go through every
earlier finding marked resolved, still open, or withdrawn (and why). The guard blocks a second
comment in the same session for this reason: a reviewer who posts ten
comments makes the author do the work of merging them.

Approval is a claim: "I ran this, it does what the ticket says, and I'd defend
it." The guard won't let you approve without a passing test run in the
session, or approve your own PR.

## Step 8: clean up

Remove the worktree, stop anything you started, and give the user the verdict
in one line, plus the PR link.

## Reviewing a whole queue

When asked to review all open PRs: list them (`gh pr list --json
number,title,author,isDraft,reviewDecision,headRefOid`), skip drafts, skip
ones you've reviewed at their current head, skip your own (list them
separately as "needs another reviewer"), then run this skill once per PR.
Report a table with PR, verdict and the one-line reason. Post nothing on a PR
unless the user asked you to post.

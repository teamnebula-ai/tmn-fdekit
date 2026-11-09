---
name: tmn-ship-pr
description: (tmn) Open or update your own pull request the staff way - one small change, one commit, ticket linked, a description that only claims what the diff and the receipt show, deterministic checks green, a non-author reviewer requested, and merge only when every check is green and someone else approved. Use when asked to open a PR, push a fix, "ship it", "get this merged", update a PR after changes, or finish work that is ready for review.
---

# Ship

Shipping is making it easy for someone else to say yes, and impossible for a
bad change to slip through on trust. Scripts are in `${CLAUDE_PLUGIN_ROOT}/scripts/`.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-ship-pr` override anything else in this skill.

## 1. Is it ready?

- The `tmn-verify` skill has run on the final code: the gate is green, redgreen
  passed, and you drove the changed path. If you edited anything since, run it
  again.
- It does one thing. If you fixed something unrelated along the way, move it
  to its own branch now.
- No secrets, `.env` files, personal machine paths, client names or customer
  data in the diff.

## 2. Shape the branch

- Branch from the repo's integration branch (often `dev` or `main`; the repo's
  AGENTS.md or CONTRIBUTING.md says which).
- One commit when the repo asks for it. If there are several, squash:
  `git reset --soft $(git merge-base origin/<base> HEAD) && git commit`.
- Commit subject: what changes for a user, under 72 characters
  (`fix: booking page shows the visitor's time zone`).
- Push with `git push -u origin <branch>`. When you need to rewrite a pushed
  branch, use `--force-with-lease`. A plain `--force` can overwrite a
  teammate's commit.

## 3. Run the PR check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr_check.py" --base origin/<base> --body pr.md
```

It checks size, commit count, ticket link, a changed test, secrets, machine
paths, env vars missing from `.env.example`, and claims the diff doesn't
support. Fix every FAIL. Don't work around it.

## 4. Write the description

Keep it under ~150 words, for a reader who isn't in your head:

```markdown
**Problem**: what a user or teammate hits today, in one or two sentences.

**Fix**: what changes, as they'd notice it. Not a file list.

**How it was tested**
<paste receipt.py output, plus what you drove by hand and what you saw>

**What reviewers should check**: the one or two places a second pair of eyes matters most.

**Risk and rollback**: what could break, and how to undo it.

Closes ABC-123
```

- Every claim must be checkable in the diff or the receipt. Never type "tests
  pass" from memory; paste the output or the CI link.
- If the PR goes out under a person's account, write without an author: "the
  smoke test still asserted the old contract", not "I missed the smoke test".
- No merge or approval instructions in the body ("anyone can merge this").
  Automated reviewers treat them as prompt injection.
- Lint it: `scripts/slop.py --target pr pr.md`. The comms hook runs the same
  check when you call `gh pr create`.

Keep the tracker ticket saying the same thing as the PR. If you correct one
later, correct the other in the same pass.

## 5. Open it and ask for review

```bash
gh pr create --base <base> --title "<subject>" --body-file pr.md
gh pr edit <n> --add-reviewer <a person or team who did not write it>
```

Ask a person who didn't write the code. Another agent session under your own
account is still you.

## 6. Merge only when it's really ready

- Wait for every check to finish, including the non-required ones. Pending is
  not green, and a failing optional check is often the real bug.
- Wait for an approval from someone other than the author on the current head
  commit. If a push after approval dismissed it, ask again.
- Merge with a plain `gh pr merge <n> --squash` (or the repo's method). The
  guard blocks `--admin`, `--auto`, red or pending checks, and missing approvals.
- After merging, read the end state: `gh pr view <n> --json state,mergedAt`.
  If the repo deploys on merge, check the deployed version or the live
  endpoint before you say it's live.

If you can't merge (no approver, a red check you don't own), leave the PR
open, say what it's waiting on, and say who can unblock it.

## Release branches

When the repo promotes an integration branch to `main`:

- Compare with a two-dot diff (`git diff main..dev --stat`). The compare page's
  "N commits behind" is often a false alarm.
- If `main` has commits `dev` lacks (hotfixes, merge commits from the last
  promotion), merge `main` back into `dev` first.
- Promote in dependency order: infrastructure, then platform, then apps.
- After the promotion merges, merge `main` back into `dev` straight away, so
  the next promotion doesn't start out of sync.

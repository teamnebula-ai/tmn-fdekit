---
name: tmn-respond
description: (tmn) Handle review feedback on your own PR without thrashing - verify each comment before acting, fix what's real with a test, push back on what's wrong with evidence, reply once per round, and never void an approval with a careless push. Use when a PR you wrote has review comments, requested changes, a failing check, or a bot review, or when asked to "address the review", "fix the comments" or "respond to feedback".
---

# Respond to review

A review comment is a claim, not an order. Treat it the way a reviewer should
treat your code: check it before you act on it. Agreeing with everything
("Great catch! Fixed!") without checking is how wrong fixes ship.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-respond` override anything else in this skill.

## 1. Gather the whole round first

Read all of it before changing anything: review bodies, inline comments, bot
findings, and the failing checks.

```bash
gh pr view <n> --json reviews,comments,statusCheckRollup,headRefOid
gh api repos/{owner}/{repo}/pulls/<n>/comments --jq '.[] | {path, line, body, user: .user.login}'
```

List each point once, even if several reviewers raised it.

## 2. Check each point

For each one, decide with evidence:

- **Real:** you can reproduce it, or the code clearly shows it. Fix it.
- **Wrong:** the reviewer missed something, like a guard one layer up or a
  constraint in the ticket. Reply with the line or the repro that shows it.
  Politely, once.
- **Unclear:** ask one specific question. Don't guess at what they meant and
  build that.
- **Out of scope:** real but not this PR's job. Open a ticket and link it in
  the reply.

A reviewer with seniority isn't automatically right, and a bot finding isn't
automatically noise. Check both.

## 3. Fix properly

- Each real bug gets a test that fails without the fix (`scripts/redgreen.sh`).
- Fix the cause, not the symptom the reviewer pointed at. Look for the same
  mistake elsewhere in the change, because reviewers rarely list every instance.
- Re-run the `tmn-verify` skill on the final code.

## 4. Push without breaking the review

- Collect all fixes for the round, then push once. Five pushes trigger five CI
  runs and five notifications.
- If the repo wants one commit per PR, amend or squash, then push with
  `git push --force-with-lease`. Know that a new commit can dismiss existing
  approvals. If the PR was already approved and the change is cosmetic, ask
  whether it's worth re-requesting review.
- If an approval landed while you were working, don't rebase or push just to
  tidy up. That can void it. Merge as it stands if it's green.

## 5. Reply once

One reply per round, linting it first with `scripts/slop.py --target review`:

```markdown
Thanks for the review. Changes in <short sha or "the latest push">:

1. **Tenant filter on delete** fixed in `orders.py:88`, with a wrong-tenant test.
2. **Retry on 401** kept as is: the client already refreshes the token one
   layer up (`auth/client.py:52`), and a retry here would double-send. Happy to
   revisit if that's not the case you meant.
3. **Rename `fetch_all`** moved to ABC-131, out of scope here.

How it was tested: <receipt.py output>
```

Resolve threads you fixed. Leave threads you pushed back on open for the
reviewer to close.

## 6. Re-request and wait

Re-request review from the people who asked for changes. Then wait for green
checks and a fresh approval, as in the `tmn-ship-pr` skill. Don't merge on an approval
from before your latest push unless the repo's rules allow it.

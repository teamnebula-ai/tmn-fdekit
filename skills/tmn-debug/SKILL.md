---
name: tmn-debug
description: (tmn) Find the root cause of a bug or incident before changing code - reproduce it, narrow it with evidence, explain the mechanism, then fix it with a test that fails first. Use when something is broken, a test is failing, prod behaves differently from local, an error or stack trace appears, a deploy went wrong, or the user says "why is this happening", "it's flaky" or "this used to work".
---

# Debug

The expensive bug fix is the one that makes the symptom go away without
explaining it. It comes back, usually somewhere worse. Debugging is done when
you can say "X happens because Y, and here is the run that shows it", and
there is a test that fails without the fix.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-debug` override anything else in this skill.

## 1. Reproduce first

- Get the exact failure: the error text, the input, the environment, the time.
  Read logs in bounded slices (`tail -n 200`, `rg -n 'ERROR' | head`).
- Make it happen on demand: a failing test, a curl, a script. If you can't
  reproduce it, you're guessing. Say so, and gather more evidence before
  touching code.
- Flaky? Run it 20 times and count (`for i in $(seq 20); do <cmd> >/dev/null
  2>&1 && echo ok || echo FAIL; done | sort | uniq -c`). A rate is evidence; a
  single failure isn't.

## 2. Narrow it

Work from evidence, one variable at a time:

- **What changed?** `git log --since=<when it last worked>`, the deploy
  history, dependency bumps (`git diff <good>..<bad> -- '*lock*'`), config and
  secret changes. `git bisect run <repro>` finds the commit for you when the
  repro is scriptable.
- **Where does it diverge?** Compare a working and a failing case side by
  side: inputs, config, versions, data. The difference is the lead.
- **Check what the code actually receives**, not what you assume. Log or print
  the real value at the boundary, then remove the print.

Write each hypothesis down with the test that would rule it out. Run that test
before forming the next one. Three untested hypotheses at once is how a
two-hour bug takes two days.

## 3. Explain the mechanism

Before fixing, state the chain: trigger → path → wrong result. If part of the
chain is "somehow", you aren't done. Common real causes, worth checking early:

- an error turned into "no data" (a dead token returning an empty list)
- a fallback default that hides a missing setting
- state left behind by a previous run (cache, temp file, migration half-applied)
- two environments that differ in one setting nobody listed
- a test that mocks the very thing that broke

## 4. Fix the cause

- Write the test that reproduces it, watch it fail, then fix. Check with
  `scripts/redgreen.sh`.
- Look for the same mistake elsewhere. The same pattern usually exists in more
  than one place.
- Keep the fix as small as the cause. A refactor goes in its own PR.
- Run the `tmn-verify` skill, then the `tmn-ship-pr` skill.

## 5. Write it down

In the PR or incident note, in plain words: what users saw, the cause, the
fix, how you know it's fixed, and what would catch it sooner next time (a test,
an alert, a check). If the cause was a missing guard, add the guard. A lesson
in a doc is weaker than a check that runs.

## During an incident

Stabilise first, then diagnose. Roll back or turn off the flag if that's safe
and fast. Say what you're doing before you do it, in the incident channel, in
one line. Never run a destructive command (drop, delete, force-push, scale to
zero) to make an alert stop without the owner's go-ahead.

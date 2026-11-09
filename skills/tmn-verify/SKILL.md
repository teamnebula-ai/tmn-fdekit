---
name: tmn-verify
description: (tmn) Prove a change works before calling it done - run the repo's gate, check that the new tests fail without the change, start the app and drive the changed path like a user, then report what was actually seen. Use after writing or fixing code, before opening or updating a PR, before saying "done", "fixed", "works" or "tests pass", and whenever a user asks "does it work?" or "did you test it?".
---

# Verify

"Done" means you watched it work, on the path the change touched, and you can
show the output. This skill is the author's side of the review: the same
checks a good reviewer will run, done first so the review finds nothing.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-verify` override anything else in this skill.

Scripts are in `${CLAUDE_PLUGIN_ROOT}/scripts/`.

## 1. Know what "works" means here

Write one or two sentences before running anything: what should be true now
that wasn't before, for whom, and how you'd see it. Take it from the ticket's
acceptance criteria when there is one. "The booking page shows times in the
visitor's time zone" is checkable; "fix time zones" isn't.

## 2. Run the gate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py" --list   # see what it found and where from
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gate.py"          # lint, types, tests, build
```

Read a failure from its log tail and fix the cause. Don't weaken the test,
skip it, or widen a timeout to get green. If the repo has no test command,
that is a gap to report, not a pass.

Run one suite at a time and never in watch mode. A second suite running in
parallel fights the first for ports and databases, and a watcher outlives you.

## 3. Prove the tests can fail

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/redgreen.sh" origin/main '<test command> {tests}'
```

It runs your new or changed tests against the base branch (they should fail)
and against your tree (they should pass). If they pass on the base too, they
don't test your change: tighten the assertion or test the real path. Read the
red output to be sure it fails for the right reason, not an import error.
When the code under test is brand new, red only proves the tests run. The
script says so. Then break the new code once (drop the owner check, skip the
write) and confirm a test goes red. That is mutation testing at the scale of
one change, and it takes a minute.

No test changed? Write one that fails without the change. If a test truly
isn't possible (a copy fix, a config value), say why in one line.

## 4. Drive the real path

Tests check what the author thought of. Running it checks what the user will hit.

- **Service or API:** `scripts/stack.sh up http://localhost:<port>/health`,
  then `curl` the changed endpoint with real-shaped input: the normal case, an
  empty case, a wrong-owner case, a failure case. Look at the status and the
  body.
- **Web UI:** open the page in a browser tool and do the task a user would.
  Check the empty, loading and error states, and a narrow viewport.
- **CLI:** run the command with the new flag and with bad input.
- **Job or pipeline:** run one pass in dry-run against real-shaped data, then
  read the output or the row it wrote.
- **Migration:** run it forward on a copy or a fresh database, then read the
  schema back.

Then `scripts/stack.sh down`. Leave nothing running.

## 5. Report what you saw

Get the receipt and use it as written:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/receipt.py"
```

The report says what passed, what you exercised and what you saw, plus
anything you could not check and why. If the receipt warns that files changed
after the last test run, run the gate again. Your last edit is the one that
ships.

## When you can't verify

Missing credentials, no environment, a paid API you shouldn't call: say
exactly which check didn't happen and what it would take. "Unit tests pass;
not run against the real payment provider (no sandbox key)" is a useful
sentence. "Should work" is not.

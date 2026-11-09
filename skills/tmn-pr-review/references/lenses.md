# Review lenses

Each lens asks one narrow question of the whole change. Work them in order;
stop and write it up the moment you've confirmed a blocker.

Every finding, from any lens, uses this shape:

```json
{"lens": "security", "file": "api/orders.py", "line": 88,
 "claim": "DELETE removes any order with this id, from any tenant",
 "evidence": "query filters on id only (line 88); repro: tenant B deleted tenant A's order 41, see test below",
 "severity": "blocker", "confidence": "confirmed|likely|question"}
```

No `file:line`, no evidence: not a finding.

## 1. Acceptance criteria (always yours, never delegated)

- List every criterion in the ticket. For each: **met**, **not met**, or
  **can't tell**, with the line or the observed behaviour that proves it.
- Check every mechanism the spec names (an algorithm, a threshold, a required
  check) against the code. Green tests are not evidence that a criterion is
  met; they test what the author thought of.
- A clean diff that skips a required deliverable is still a blocker.

## 2. Correctness

- Trace each changed function with real inputs: empty, one, many, the limit,
  one past the limit. Null and missing fields.
- Callers and callees: does every caller still pass what this now expects? Did
  a rename or a deleted file leave a straggler? `rg` for the old name.
- Contracts: does the response match the published schema and the client's
  expectations? One error shape?
- Concurrency and repeats: can it run twice (retry, double-click, cron
  overlap)? Is it idempotent? Can two writers race?
- Time: time zones, DST, "now" captured once vs per row, clocks in tests.

## 3. Security and tenancy

- Every read and write is scoped to the caller's owner (tenant, org, user),
  and that owner comes from the server-side identity, never from the request
  body or a name.
- Every path to the same action is guarded, not just the one in the diff:
  bulk endpoints, upserts, background jobs, admin tools, agent tool calls.
- Exemptions key on identity (a bot's app id), never on a name a user can
  choose (a branch name, a display name, an email prefix).
- Injection, SSRF, path traversal and template injection on anything a user
  or an external system controls. Secrets and tokens: none in code or logs,
  least privilege.
- New tables or collections have access control (row-level security,
  policies) in the same change.

## 4. Failure modes

- What happens when the dependency is down, slow, or returns garbage? Fail
  closed (refuse, alert) or fail open (send, allow, leak)?
- Is an error ever read as "no data"? An empty result from a dead token is
  the classic one.
- Hardcoded fallbacks for a person, org, key, URL or path. A missing setting
  should stop startup with a clear message.
- Partial failure: if it dies halfway, what state is left, and does a retry
  fix it or make it worse?
- Is the risky behaviour on by default? Anything that sends, deploys, spends
  or deletes should be opt-in.

## 5. Tests prove it

- Would the new tests fail without the change? Run `redgreen.sh`; don't guess.
- Do they test the real code path, or a hand-built stand-in? Mocking the
  outside world (APIs, email, clock) is right; mocking the thing being changed
  proves nothing.
- Is there a test for the failure case and the wrong-owner case, not only the
  happy path?
- Config and migrations: does a fresh environment get the new setting, and
  does the migration run forward on real-shaped data? Is it a new migration
  file rather than an edit to one that already ran?

## 6. The description matches the diff

- Every claim in the PR body ("adds RLS", "fixes X", "tests pass") is visible
  in the diff or the CI run. Find the line for each.
- "Tests pass" with no output or run link is unverified. Check CI yourself.
- Scope: does the diff do things the description doesn't mention? Unrelated
  reformatting hides real changes.

## 7. Will the next person understand it

Only raise this when it will cost someone real time:

- Duplicated logic that already exists elsewhere (name the existing function).
- One function doing two jobs that will change for different reasons, such as
  authorization mixed with attribution.
- Names that say something different from what the code does.
- "Temporary" hacks with no ticket to remove them.

## The naive questions

Ask these out loud when you can't answer them from the code. They catch what
cleverness skips:

- What happens if this list is empty?
- Who is allowed to call this, and what stops everyone else?
- Does "no data on file" look the same as "approved"?
- What re-runs this, and can it fire twice?
- If the network dies halfway, what state are we in?
- Where does this id, secret or URL actually come from?

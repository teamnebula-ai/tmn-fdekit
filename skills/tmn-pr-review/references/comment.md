# The review comment

One comment per review round. Plain words, no jokes, no emoji, no praise
padding. Say what's good once if it is specific ("the retry test is the right
shape"). Ask rather than accuse when you aren't certain.

## Template

```markdown
<!-- tmn-fdekit:review sha=<head-sha> -->
**Verdict: <Request changes | Comment | Approve>** at `<short head sha>`. <One sentence: the main reason.>

**Ticket <ID>**
| Acceptance criterion | Status | Evidence |
|---|---|---|
| <criterion 1> | met | `orders.py:88` filters by tenant; tried tenant B, got 404 |
| <criterion 2> | not met | no retry on timeout; spec section 3 requires 3 attempts |

**Findings**
1. **Blocker · `api/orders.py:88`** DELETE removes an order from any tenant.
   The query filters on `id` only. Repro: as tenant B, `DELETE /orders/41`
   (tenant A's order) returns 204 and the row is gone.
   Fix: add `tenant_id = :caller_tenant` to the filter, and a test where
   tenant B tries tenant A's id.
2. **Major · `jobs/sync.py:40`** A 401 from the upstream API is treated as
   "no new records", so a dead token looks like a quiet day. Raise instead.

**Questions**
- What should happen when `items` is empty? Right now the job reports success.

Nit: `fetch_all` returns a generator; the name suggests a list.

**Checked**
- `gate.py`: lint pass, types pass, tests pass (212 passed)
- `redgreen.sh origin/main`: new tests fail on main, pass here
- Started the stack, called `DELETE /orders/41` as tenant B: 204 (the bug above)

**Not checked**: the email template change (no mail sandbox here).
```

## Rules for the comment

- **Verdict first.** The author should know in one line whether they can merge.
- **Every finding has a location, the failure, and the fix.** "Consider
  error handling" isn't a finding.
- **Questions are labelled as questions.** They don't block unless the answer
  turns out to be a bug.
- **Nits go in one line at the end**, or nowhere.
- **Name what you didn't check.** A reviewer who says what wasn't exercised
  is trusted on the rest.
- **"Checked" is real.** Paste from `gate.py`, `redgreen.sh` and
  `receipt.py`, never from memory.
- **No author voice in someone else's name.** When the comment is posted from
  a person's account, describe the defect, not yourself: "the query filters on
  id only", not "I noticed I think maybe".
- **Under ~40 lines.** If it needs more, the PR needs splitting. Say so.

## Inline comments

Use inline comments only for a blocker or major finding where the line itself
is the point, and only alongside the one summary comment, never instead of it.
Most reviews need none.

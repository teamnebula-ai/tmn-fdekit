---
name: tmn-write
description: (tmn) Write anything a person will read - PR descriptions, review comments, commit messages, tickets, docs, status updates, Slack posts - so it reads like a capable human wrote it - outcome first, plain words, short, no AI tells - then lint it with the slop checker before it goes out. Use whenever drafting or rewriting text for a teammate, client or manager, when asked to "deslop", "make this less AI", "tighten this", "make it shorter", or before posting any comment, PR or message. For a Slack message use tmn-slack; for a browsable docs site use tmn-docs-site.
---

# Write for people

Busy readers decide in the first line whether to keep reading. Most AI-written
text fails there: it warms up, explains what the reader already knows, and
proves it did work instead of saying what happened.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-write` override anything else in this skill.

## The shape

1. **Outcome or answer first, in one line.** "Fixed the login timeout. Sessions
   now last eight hours." The reader should be able to stop there.
2. **Then only what the reader needs to act on.** The problem in plain words,
   what changed, how we know it works, and what they have to do. Skip whatever
   they don't need.
3. **One reference at most** (a PR link or ticket) in messages. No commit
   hashes, command names or tool output unless the reader must act on them.
4. **Stop.** No summary of what you just said, no "hope this helps".

For replies to a question, use problem → fix → steps: answer in one line,
then the numbered problems, the fix for each and where it lives, how you'll
know it works, and what the reader needs to do.

## Plain words

- Short sentences, one idea each, about 20 words or fewer. Paragraphs of two
  to four sentences.
- Concrete words. "is", not "serves as". A number instead of "significantly".
  Name the thing ("the nightly import job"), not the category ("the pipeline").
- Active voice with a named actor. "The job skips rows with no email", not
  "rows are skipped".
- Use a list only for three or more parallel items. Bold only names, dates
  and asks.
- Sentence-case headings. No emoji in headings or bullets.

## Tells to cut

These make a reader stop trusting the text. One strong tell is enough to rewrite:

- **Staging:** "Here's the thing", "Let's dive in", "Quick note", "Honestly?"
- **Fake contrast:** "It's not just X, it's Y", "not only... but also".
- **Closers:** "That's the real win.", "Let that sink in.", "Full stop."
- **Chatbot residue:** "Great question!", "I hope this helps", "Certainly!",
  "Would you like me to...", "Is there anything else...".
- **Inflated words:** delve, pivotal, robust, seamless, leverage, testament,
  tapestry, elevate, unlock, streamline, game-changer.
- **-ing riders:** ", highlighting the...", ", ensuring that...".
- **Proof-of-work:** "I checked X, then ran Y, then verified Z". Give the
  result. Keep the receipts for when someone asks, or for the "How it was
  tested" section.
- **Decoration:** emoji bullets, arrows in prose, a horizontal rule between
  every section, bold labels on every bullet.

Leave quotes, names and titles alone even when they contain a watched word.

## Whose voice

- **Text published under a person's name** (PRs, commits, reviews, Slack from
  their account) has no author voice. Describe the defect and the evidence:
  "the smoke test still asserted the old contract", never "I missed the smoke
  test" or "I ran the tests". Flag judgement calls to the person in chat, not
  in the published text.
- **When writing as someone**, match their voice if you have samples. Their
  habits (dashes, emoji, sign-offs) beat these rules. Keep a sample file and
  point `TMN_FDEKIT_VOICE` at it so the linter allows their habits.
- **When the person is the sender and it's to a teammate:** acknowledge them,
  credit their work specifically, take ownership, and hand off with trust.
  An open-door last line ("let me know if you hit any blockers") is fine once,
  at the end.

## Formats

| Where | Shape |
|---|---|
| Commit | `type: what changes for a user`, under 72 characters; a body only if the why isn't obvious |
| PR | Problem → Fix → How it was tested (the receipt) → What reviewers should check → Risk → `Closes ABC-123`; under ~150 words |
| Review comment | the `tmn-pr-review` skill's comment format: verdict first, then findings with location, failure and fix |
| Ticket | the problem a user has, acceptance criteria someone can check, links; no solution essay |
| Status update | what shipped, what's blocked and on whom, what's next; five sentences max |
| Doc | a title that says what it is, a one-paragraph summary, then sections someone can skim |

## Check it before it goes

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/slop.py" --target pr|review|commit|ticket|slack|doc draft.md
```

Fix every strong finding. Then reread it once as the recipient: would a
teammate need to read it twice? If yes, cut it further. The comms hook runs
the same lint when you call `gh pr create`, `gh pr comment` or a Slack send
tool, and it blocks text with strong tells.

Check that the facts survived the rewrite. Every number, name, date and link
in the draft should still be there, unchanged, and nothing new should appear.

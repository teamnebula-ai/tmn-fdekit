---
name: tmn-slack
description: (tmn) Draft and send a Slack message that a busy teammate reads once and acts on - outcome or ask in the first line, five sentences max, threaded correctly, no AI slop - and lint it before sending. Use whenever asked to post, send, reply or announce something in Slack, update a channel, ping someone, or "let the team know", and before calling any Slack send or draft tool.
---

# Slack

Only the first line shows in a notification, and people read Slack between
other things. Write for someone glancing at their phone.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both.

## Before you write

- **Who is it for, and what should they do after reading?** If the answer is
  "nothing", it may not need sending, or it belongs in a thread, not the channel.
- **Where does it go?** Reply in the existing thread when there is one.
  Broadcast to the channel only for a decision, a deadline change or something
  everyone must see. DM for one person's ask.
- **Is it one message?** Send the whole thing at once. Never a lone "hi" and
  then the real message.

## The shape

```
<Outcome or ask, one line, with the name of whoever must act.>
<One or two sentences of context they don't already have.>
<What happens next, or what you need from them, and by when.>
<One link, if they need it.>
```

Examples:

> Booking page shows the right time zone again, Priya. Nice find on the
> offset bug. It's live now; let me know if any customer still sees the old
> times.

> Need a go/no-go from you on Friday's release by 3pm, Sam. Two fixes are
> still in review; everything else is green. Checklist is here: <link>

- Five sentences max, one short list max. Longer means it's a doc; link it.
- No commit hashes, command names, tool output or verification steps. Say
  the result.
- Bold only names, dates and the ask. `@here` and `@channel` only when every
  person must act now.
- Credit people for specific things. Ownership in the first person is fine
  when the person sending it really did the work. When you send on someone's
  behalf, write it in their voice, not yours.

## Lint, then send

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/slop.py" --target slack draft.txt
```

Fix every strong finding. The comms hook re-checks the text when the Slack
send tool is called and blocks strong tells. If it blocks you, rewrite. Don't
reword just enough to slip past it.

Prefer saving a draft (the Slack draft tool, or show the text in chat) when:

- the message speaks for a person who hasn't seen it,
- it goes to a client or a large channel,
- it reports something not yet confirmed.

After sending, read it back (the message link or the channel history) to
confirm it landed where you meant, then give the user the link.

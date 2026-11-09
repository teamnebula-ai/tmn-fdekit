# Disclaimer

tmn-fdekit is a set of instructions, scripts and hooks for AI coding agents.
It is provided "as is", without warranty of any kind, under the
[MIT License](LICENSE). Read this before you use it.

## You stay in charge

- **Use your own judgement.** The skills describe how a careful engineer
  works. They don't replace one. Whoever runs an agent with these skills is
  responsible for what that agent does, and for checking its work before
  relying on it.
- **Agents make mistakes.** They can misread code, report a result they
  didn't check, or act on the wrong branch, repo, ticket or person. The
  checks here reduce that risk. They don't remove it.
- **Review before it leaves your machine.** Pushes, pull requests, review
  comments, merges, deploys and messages are visible to other people and can
  be hard to undo.

## Yolo mode

In `yolo` mode the agent takes those steps without stopping to ask. Turn it
on only in repos and channels where a mistake is cheap to undo, and only if
you're ready to review everything it did afterwards. The hooks block the
same things in both modes, but they can't judge whether a change is a good
idea.

## What this is not

- Not a security audit, a compliance control or legal advice. A clean
  `tmn-harden-prod` pass doesn't mean a system is secure.
- Not a guarantee that code works, is correct, or is fit for any purpose.
- Not affiliated with or endorsed by Anthropic, OpenAI, GitHub, Slack or any
  other vendor named in the docs. Their products have their own terms.

## Your data

The trace hooks write session records to your own machine
(`~/.tmn-fdekit` by default). Nothing is sent anywhere unless you set up an
observability backend yourself with `tmn-trace`. You're responsible for what
your agent and that backend store, and for keeping secrets and personal data
out of them.

## Liability

To the extent the law allows, Team Nebula and the contributors aren't liable
for any loss or damage that comes from using this software, including lost
code, data, time or money, or harm from actions an agent took. If you don't
accept these terms, don't use it.

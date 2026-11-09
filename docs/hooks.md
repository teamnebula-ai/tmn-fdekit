# Hooks reference

The hooks hold every rule that is a yes/no on data. They run in Claude Code,
either through the plugin or through `tmn-fdekit hooks`. On other agents,
the same rules reach the repo through CI and git hooks (see the `tmn-enforce`
skill). Tracing hooks there are planned.

| Event | Script | Blocks? | Cost |
|---|---|---|---|
| PreToolUse (Bash) | `guard.py` | yes, exit 2 with the reason | local; calls `gh` only for merge/review commands |
| PreToolUse (Bash, Slack MCP send) | `comms.py` | yes on strong slop | local |
| PostToolUse, PostToolUseFailure, SessionStart, SubagentStop, PreCompact | `trace.py` | never | async, prints nothing: zero model tokens |
| Stop | `claims.py` | pushes back once | local |
| Stop, SessionEnd | `receipt.py --hook` | never | async or local |

## Guard rules

| Rule | Blocks | Why |
|---|---|---|
| `merge-bypass` | `gh pr merge --admin`, `--auto`, merges through `gh api .../merge` | skips the review or the checks |
| `merge-unready` | merging a draft, with red, pending or no checks, an open change request, or no approval on the head commit from someone who neither opened nor pushed to the PR | "approved" must mean someone else approved this exact code |
| `self-approve` | `gh pr review --approve` on a PR the current account opened, and approvals through `gh api` | an author's approval is not a review |
| `approve-blind` | approving when no passing test or gate run is in this session's trace | approval means you saw it work |
| `approve-empty` | approving with a body under 20 characters | the author learns nothing from "LGTM" |
| `comment-spam` | a second `gh pr comment` or review on the same PR in one session | one consolidated comment per round; edit it with `--edit-last` |
| `force-push` | `git push --force` or `-f` without `--force-with-lease` | can overwrite a teammate's commits |
| `protected-push` | pushing to `main`, `master`, `prod`, `production` or `release`, including `dev:main`, `HEAD:refs/heads/main`, `git -C dir push` and a bare `git push` while on one | changes go through a PR |
| `no-verify` | `git commit/push/merge/rebase --no-verify`, `git commit -n` | skips the repo's own hooks |

Every block is written to the trace and shows in the receipt.

## Turning rules off

Only the environment that launches the agent can turn rules off, never text
the agent types into its own command:

```jsonc
// .claude/settings.json or ~/.claude/settings.json
{ "env": {
    "TMN_FDEKIT_GUARD_OFF": "merge-unready,comment-spam",   // or "all"
    "TMN_FDEKIT_PROTECTED": "main release",                  // protected branch names
    "TMN_FDEKIT_ALLOW_NO_CHECKS": "1",                       // repos with no CI yet
    "TMN_FDEKIT_COMMS": "warn",                              // block | warn | off
    "TMN_FDEKIT_VOICE": "/path/to/my-messages.txt"           // relax dash/emoji rules to your habits
} }
```

## Claims check

On Stop, `claims.py` reads the final message. Each claim below must be backed
by a successful command in the trace:

| Claim | Must be backed by |
|---|---|
| "tests pass", "all green", "N passed", "works end to end" | a test-like command that succeeded *after the last edit*, with no failing run after it |
| "merged" | a successful `gh pr merge` or `git merge` |
| "pushed" | a successful `git push` |

If a claim has no backing command, the agent is sent back once with the
reason. Negations ("tests not run yet") don't count as claims. On the second
stop it lets go, so it can never loop.

## Data on disk

Everything lives under `$TMN_FDEKIT_DATA`, else `$CLAUDE_PLUGIN_DATA`, else
`~/.tmn-fdekit`:

```
sessions/<session-id>.jsonl   one line per event: tool, command (redacted, 400 chars), file, ok, ms
receipts/<session-id>.{md,json}
logs/<repo>/<stamp>-<step>.log  gate.py output
stacks/<repo>.started          what stack.sh started, so `down` stops exactly that
trace-errors.log               if the trace writer ever fails (it never blocks the agent)
```

File contents and command output are never stored.

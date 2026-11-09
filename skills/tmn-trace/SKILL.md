---
name: tmn-trace
description: (tmn) See exactly what an agent did - every command, edit, test run, subagent and token count - without spending model tokens, and optionally send Claude Code's own telemetry to Langfuse, Phoenix or an OpenTelemetry Collector. Use when asked what an agent ran, to audit or replay a session, to set up agent observability, tracing, Langfuse or OTel, to check cost or token use per session, or to attach proof of testing to a PR.
---

# Trace

Two layers. The first is always on and free. The second is for teams that
want sessions in a dashboard.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-trace` override anything else in this skill.

## Layer 1: the local trace (on with the plugin)

Hooks write one line per event to `~/.tmn-fdekit/sessions/<session-id>.jsonl`
(or `$CLAUDE_PLUGIN_DATA`): tool, command, file path, pass or fail, duration,
subagent. Commands are secret-redacted and truncated. File contents and
command output are never stored. The hooks run async and print nothing, so
the model's context and token bill don't change.

At each stop, a receipt is written next to it in `receipts/<session-id>.md`.
To read one:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/receipt.py"                 # the newest session in this directory
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/receipt.py" --session <id>  # a specific one
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/receipt.py" --json          # for scripts and CI
```

It shows tests and lint runs with their real results, files edited, uncommitted
files according to git, subagents, failed tool calls, and token totals parsed
from the transcript. It warns when files changed after the last test run.

Answer "what did the agent do?" from the trace, not from the agent's summary.
For a detail the trace doesn't hold, open the session transcript it points to,
but only the lines you need (`rg -n '<tool_use_id or command>' <transcript> |
head`). Never load a whole transcript into context.

## Layer 2: a team backend (opt in)

Claude Code emits OpenTelemetry itself: spans per prompt, model call and tool
call (with subagents nested), events for every tool result and API request,
and cost and token metrics per agent, skill and plugin. Point it at a backend:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/otel_env.sh" langfuse  https://cloud.langfuse.com >> ~/.zshrc   # or your self-hosted URL
"${CLAUDE_PLUGIN_ROOT}/scripts/otel_env.sh" collector http://127.0.0.1:4317       >> .envrc
"${CLAUDE_PLUGIN_ROOT}/scripts/otel_env.sh" phoenix   http://127.0.0.1:6006
```

The output is shell lines that never contain a secret. Langfuse keys are read
from `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` at shell start, so keep
them in your secret manager. Start a new Claude Code session afterwards;
telemetry settings are read at launch.

Choosing a backend:

| Backend | Good for | Notes |
|---|---|---|
| **Langfuse** | LLM-focused trace UI, cost per session, self-hostable (MIT core) | OTLP over HTTP, traces only. Send metrics and events through a collector if you want them too |
| **OTel Collector** | fanning out: traces to Langfuse, events to your log store, metrics to Prometheus | the place to drop prompt text and scrub commands before anything leaves the machine |
| **Phoenix** | local trace UI in one Docker container | Elastic License 2.0, not OSI open source |

Privacy defaults in the generated env: commands and file paths are sent (that
is the audit trail); prompt text, response text and file contents are not.
Turning on `OTEL_LOG_USER_PROMPTS` or `OTEL_LOG_TOOL_CONTENT` sends customer
data off the machine. Do it only with the data owner's agreement.

To check it works: run one short session, then find it in the backend by
session id. It's in the receipt header. Langfuse can take a minute to show it.

## Linking a PR to its session

Put the receipt in the PR's "How it was tested" section. For a permanent link,
add the session id as a commit trailer (`Agent-Session: <id>`). Anyone can then
open the trace in the backend, or ask the author for the local receipt.

## What this is not

- Not a replacement for CI. CI re-runs the tests on a clean machine. The
  receipt says what ran on the agent's machine.
- Not proof the code is right. It proves what was run, which is what a
  reviewer needs in order to know what is still unchecked.

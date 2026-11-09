#!/usr/bin/env python3
"""PreToolUse hook: lint human-facing text before it leaves the machine.

Catches the text in:
  gh pr create|edit|comment|review  --body / -b / --body-file / -F, --title / -t
  gh issue create|comment           same flags
  git commit -m / -F
  Slack MCP send tools (any tool whose name has "slack" and "send"/"post"/"reply"/"draft")

Strong slop findings block the send (exit 2) with the list, so the agent
rewrites before a teammate reads it. Set TMN_FDEKIT_COMMS=warn in the launch
environment to report without blocking, or =off to disable. A voice sample at
$TMN_FDEKIT_VOICE (a file of the author's own messages) relaxes the dash and
emoji rules to their habits.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import read_hook_input, segments  # noqa: E402
from slop import lint, verdict  # noqa: E402
import config  # noqa: E402


def texts_from_bash(command: str, cwd: str | None) -> list[tuple[str, str]]:
    found = []
    for toks in segments(command):
        target = None
        if toks[0] == "gh" and len(toks) > 2 and toks[1] in ("pr", "issue") and toks[2] in ("create", "edit", "comment", "review"):
            target = "review" if toks[2] in ("comment", "review") else ("pr" if toks[1] == "pr" else "ticket")
            flags_body, flags_file = ("--body", "-b"), ("--body-file", "-F")
        elif toks[0] == "git" and "commit" in toks:
            target = "commit"
            flags_body, flags_file = ("-m", "--message"), ("-F", "--file")
        if not target:
            continue
        for i, t in enumerate(toks[:-1]):
            val = toks[i + 1]
            if t in flags_body:
                found.append((target, val))
            elif t in flags_file and val != "-":
                p = Path(val) if os.path.isabs(val) else Path(cwd or ".") / val
                if p.exists() and p.stat().st_size < 200_000:
                    found.append((target, p.read_text(errors="ignore")))
        for t in toks:
            for flag in flags_body:
                if t.startswith(flag + "=") and flag.startswith("--"):
                    found.append((target, t.split("=", 1)[1]))
    return found


def texts_from_mcp(tool: str, ti: dict) -> list[tuple[str, str]]:
    low = tool.lower()
    if "slack" not in low or not any(k in low for k in ("send", "post", "reply", "draft", "schedule")):
        return []
    return [("slack", ti[k]) for k in ("text", "message", "markdown_text", "content") if isinstance(ti.get(k), str)]


def main() -> int:
    ev = read_hook_input()
    settings = config.for_session(ev).get("comms", {})
    mode = settings.get("mode") or "block"
    if mode == "off":
        return 0
    tool = ev.get("tool_name") or ""
    ti = ev.get("tool_input") or {}
    cmd = ti.get("command") if isinstance(ti, dict) else None
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    if isinstance(cmd, str):
        items = texts_from_bash(cmd, ev.get("cwd"))
    else:
        items = texts_from_mcp(tool, ti)
    if not items:
        return 0
    vp = settings.get("voice")
    voice = Path(vp).read_text() if vp and Path(vp).exists() else None
    report = []
    for target, text in items:
        findings = lint(text, target, voice)
        if not verdict(findings):
            shown = [f for f in findings if f[2] != "weak"][:10]
            report.append(f"{target} text:\n" + "\n".join(f"  - {r} [{s}]: {m}" for _, r, s, m in shown))
    if not report:
        return 0
    msg = ("tmn-fdekit comms: this reads like AI slop to a teammate. Rewrite it: outcome first, plain words, "
           "no filler, then send again.\n" + "\n".join(report) +
           "\nRun scripts/slop.py --target <slack|pr|review|commit> on the draft to check it.")
    print(msg, file=sys.stderr)
    return 2 if mode == "block" else 0


if __name__ == "__main__":
    sys.exit(main())

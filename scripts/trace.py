#!/usr/bin/env python3
"""Zero-token trace writer. Wired as an async command hook on every event.

Appends one compact JSON line per event to <data>/sessions/<session_id>.jsonl.
It prints nothing and always exits 0, so it never adds to the model's context
and never blocks the agent. Commands and errors are secret-redacted and
truncated; file contents and tool output are never stored.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import now_iso, read_hook_input, redact, sessions_dir  # noqa: E402


def row_for(ev: dict) -> dict | None:
    sid = ev.get("session_id")
    if not sid:
        return None
    name = ev.get("hook_event_name")
    ti = ev.get("tool_input") or {}
    if not isinstance(ti, dict):
        ti = {}
    ok = None
    if name == "PostToolUse":
        ok = True
        resp = ev.get("tool_response")
        # Bash reports a non-zero exit inside a "successful" tool call.
        if isinstance(resp, dict):
            code = resp.get("exit_code", resp.get("exitCode", resp.get("returncode")))
            if isinstance(code, int) and code != 0:
                ok = False
            if resp.get("interrupted") is True or resp.get("is_error") is True:
                ok = False
    elif name == "PostToolUseFailure":
        ok = False
    row = {
        "ts": now_iso(),
        "ev": name,
        "sid": sid,
        "pid": ev.get("prompt_id"),
        "agent": ev.get("agent_id"),
        "agent_type": ev.get("agent_type"),
        "tool": ev.get("tool_name"),
        "ms": ev.get("duration_ms"),
        "file": ti.get("file_path") or ti.get("notebook_path") or ti.get("path"),
        "cmd": redact(ti.get("command")),
        "desc": redact(ti.get("description") or ti.get("subagent_type"), 160),
        "ok": ok,
        "err": redact(ev.get("error"), 300),
        "source": ev.get("source"),
        "reason": ev.get("reason"),
        "sub_transcript": ev.get("agent_transcript_path"),
        "transcript": ev.get("transcript_path"),
        "cwd": ev.get("cwd"),
    }
    return {k: v for k, v in row.items() if v is not None}


def main() -> int:
    try:
        ev = read_hook_input()
        row = row_for(ev)
        if row:
            with (sessions_dir() / f"{row['sid']}.jsonl").open("a") as fh:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except Exception as exc:  # a trace must never break the agent, but the failure is logged
        try:
            from _common import data_dir
            with (data_dir() / "trace-errors.log").open("a") as fh:
                fh.write(f"{now_iso()} {type(exc).__name__}: {exc}\n")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

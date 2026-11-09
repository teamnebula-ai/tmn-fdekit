#!/usr/bin/env python3
"""Build a receipt from a session trace: what the agent actually did.

    receipt.py                 # latest session, markdown to stdout
    receipt.py --session ID    # a specific session
    receipt.py --json          # machine-readable
    receipt.py --hook          # read a Stop/SessionEnd hook payload on stdin, write
                               # <data>/receipts/<sid>.{json,md}, print nothing

The receipt is what goes under "How it was tested" in a PR: commands run with
their real exit status, tests run, files changed (and whether git agrees),
subagents launched. It is built from the trace, not from the agent's memory,
so it cannot claim a test that never ran.
"""
from __future__ import annotations

import argparse
import os
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    EDIT_TOOLS,
    LINT_CMD_RE,
    data_dir,
    evidence_since_last_edit,
    is_test_command,
    latest_session_id,
    load_trace,
    read_hook_input,
)


def git(cwd: str | None, *args: str) -> str:
    if not cwd:
        return ""
    try:
        out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def usage_from_transcript(path: str | None) -> dict:
    """Sum token usage from the session transcript. A plain parse, no model call."""
    tot = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "requests": 0}
    if not path or not Path(path).exists():
        return tot
    seen = set()
    with open(path, errors="ignore") as fh:
        for line in fh:
            if '"usage"' not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = row.get("message") or {}
            u = msg.get("usage") if isinstance(msg, dict) else None
            mid = msg.get("id") if isinstance(msg, dict) else None
            if not u or (mid and mid in seen):
                continue
            seen.add(mid)
            tot["requests"] += 1
            tot["input"] += u.get("input_tokens", 0) or 0
            tot["output"] += u.get("output_tokens", 0) or 0
            tot["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
            tot["cache_write"] += u.get("cache_creation_input_tokens", 0) or 0
    return tot


def build(sid: str) -> dict:
    rows = load_trace(sid)
    tool_rows = [r for r in rows if r.get("ev") in ("PostToolUse", "PostToolUseFailure")]
    cwd = next((r["cwd"] for r in reversed(rows) if r.get("cwd")), None)
    files = sorted({r["file"] for r in tool_rows if r.get("tool") in EDIT_TOOLS and r.get("file")})
    bash = [r for r in tool_rows if r.get("tool") == "Bash" and r.get("cmd")]
    tests = [r for r in bash if is_test_command(r["cmd"])]
    lints = [r for r in bash if LINT_CMD_RE.search(r["cmd"]) and r not in tests]
    failures = [r for r in tool_rows if r.get("ok") is False]
    subagents = [
        {"type": r.get("agent_type"), "id": r.get("agent"), "transcript": r.get("sub_transcript")}
        for r in rows
        if r.get("ev") == "SubagentStop"
    ]
    blocked = [{"rule": r.get("rule"), "cmd": r.get("cmd")} for r in rows if r.get("ev") == "Blocked"]
    git_changed = git(cwd, "status", "--porcelain")
    git_files = sorted({line[3:] for line in git_changed.splitlines() if len(line) > 3})
    return {
        "session": sid,
        "cwd": cwd,
        "head": git(cwd, "rev-parse", "--short", "HEAD") or None,
        "started": rows[0]["ts"] if rows else None,
        "ended": rows[-1]["ts"] if rows else None,
        "tool_calls": len(tool_rows),
        "failed_calls": len(failures),
        "files_edited": files,
        "git_uncommitted": git_files,
        "tests": [{"cmd": r["cmd"], "ok": r.get("ok")} for r in tests],
        "lint": [{"cmd": r["cmd"], "ok": r.get("ok")} for r in lints],
        "subagents": subagents,
        "blocked": blocked,
        "evidence": evidence_since_last_edit(tool_rows),
        "tokens": usage_from_transcript(next((r["transcript"] for r in reversed(rows) if r.get("transcript")), None)),
    }


def mark(ok) -> str:
    return "pass" if ok is True else "FAIL" if ok is False else "?"


def to_markdown(rc: dict) -> str:
    ev = rc["evidence"]
    lines = [f"**Agent receipt** · session `{rc['session'][:8]}` · HEAD `{rc['head'] or 'n/a'}`", ""]
    if rc["tests"]:
        lines.append("Tests run:")
        lines += [f"- `{t['cmd']}` → {mark(t['ok'])}" for t in rc["tests"][-8:]]
    else:
        lines.append("Tests run: **none recorded**")
    if rc["lint"]:
        lines.append("Lint / types:")
        lines += [f"- `{t['cmd']}` → {mark(t['ok'])}" for t in rc["lint"][-5:]]
    if ev["edited"] and ev["tests_after_edit"] == 0:
        lines.append("")
        lines.append("⚠️ Files were edited after the last test run. Nothing here proves the final code passes.")
    if rc["files_edited"]:
        lines.append(f"Files edited ({len(rc['files_edited'])}): " + ", ".join(f"`{Path(f).name}`" for f in rc["files_edited"][:12]))
    if rc["subagents"]:
        lines.append(f"Subagents: {len(rc['subagents'])} (" + ", ".join(sorted({s['type'] or '?' for s in rc['subagents']})) + ")")
    if rc.get("blocked"):
        lines.append("Blocked by the guard: " + ", ".join(f"{b['rule']} (`{(b['cmd'] or '')[:60]}`)" for b in rc["blocked"][-5:]))
    lines.append(f"Tool calls: {rc['tool_calls']} ({rc['failed_calls']} failed)")
    t = rc.get("tokens") or {}
    if t.get("requests"):
        lines.append(f"Model: {t['requests']} requests, {t['input'] + t['cache_read'] + t['cache_write']:,} input tokens "
                     f"({t['cache_read']:,} from cache), {t['output']:,} output")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--hook", action="store_true")
    a = ap.parse_args()

    if a.hook:
        try:
            sid = read_hook_input().get("session_id")
            if sid:
                rc = build(sid)
                out = data_dir() / "receipts"
                out.mkdir(exist_ok=True)
                (out / f"{sid}.json").write_text(json.dumps(rc, indent=1))
                (out / f"{sid}.md").write_text(to_markdown(rc) + "\n")
        except Exception:
            pass
        return 0

    sid = a.session or latest_session_id(os.getcwd())
    if not sid:
        print("No trace found. Is the tmn-fdekit plugin enabled? (hooks write to ~/.tmn-fdekit or $CLAUDE_PLUGIN_DATA)", file=sys.stderr)
        return 1
    rc = build(sid)
    print(json.dumps(rc, indent=1) if a.json else to_markdown(rc))
    return 0


if __name__ == "__main__":
    sys.exit(main())

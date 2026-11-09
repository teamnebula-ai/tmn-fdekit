#!/usr/bin/env python3
"""Stop hook: no claim without a receipt.

When the agent is about to finish, read its final message. If it claims the
tests pass (or that something is merged/pushed) but the session trace has no
matching command that succeeded after the last edit, block the stop once and
tell the agent to run it or take the claim back.

Exit 2 on Stop = "keep going" with the stderr text as the reason. When
`stop_hook_active` is set we already pushed back once, so we let it stop:
the goal is a nudge, not a loop.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import EDIT_TOOLS, is_test_command, load_trace, read_hook_input  # noqa: E402

NEG = r"(?:not|n't|never|no|without|couldn't|unable to|haven't|didn't|wasn't|un)"
CLAIMS = {
    "tests": re.compile(
        r"\b(?:all |the )?(?:tests?|suite|specs?|checks?|gate)\s+(?:all\s+)?(?:pass(?:es|ed)?|(?:are|is)\s+(?:green|passing))\b"
        r"|\ball green\b|\b\d+\s*(?:/\s*\d+\s*)?(?:tests?\s+)?passed\b|\bverified (?:it )?works\b|\bworks end[- ]to[- ]end\b",
        re.I,
    ),
    "merged": re.compile(r"\b(?:PR|pull request|it|this)(?:\s+#?\d+)?\s+(?:is|was|has been|got)\s+(?:now\s+)?merged\b|\bmerged (?:it|the PR|#\d+)\b", re.I),
    "pushed": re.compile(r"\b(?:pushed (?:it|the (?:branch|fix|change)s?)|is pushed|has been pushed)\b", re.I),
}


def claimed(kind: str, text: str) -> bool:
    for m in CLAIMS[kind].finditer(text):
        before = text[max(0, m.start() - 40) : m.start()]
        if re.search(NEG + r"\W+(?:\w+\W+){0,3}$", before, re.I):
            continue
        return True
    return False


def main() -> int:
    ev = read_hook_input()
    if ev.get("stop_hook_active"):
        return 0
    msg = ev.get("last_assistant_message") or ""
    if isinstance(msg, dict):
        msg = msg.get("text") or ""
    if not msg:
        return 0
    rows = [r for r in load_trace(ev.get("session_id") or "") if r.get("ev") in ("PostToolUse", "PostToolUseFailure")]
    if not rows:
        return 0  # plugin installed mid-session or tracing off: nothing to compare against

    last_edit = max((i for i, r in enumerate(rows) if r.get("tool") in EDIT_TOOLS), default=-1)
    after = rows[last_edit + 1 :]
    bash_ok = lambda pat: any(r.get("tool") == "Bash" and r.get("ok") is True and re.search(pat, r.get("cmd") or "") for r in rows)  # noqa: E731

    problems = []
    if claimed("tests", msg):
        passing_after = [r for r in after if r.get("tool") == "Bash" and is_test_command(r.get("cmd")) and r.get("ok") is True]
        failing_after = [r for r in after if r.get("tool") == "Bash" and is_test_command(r.get("cmd")) and r.get("ok") is False]
        if not passing_after:
            if last_edit >= 0:
                problems.append("you say the tests pass, but no passing test run is recorded after your last edit")
            else:
                problems.append("you say the tests pass, but no passing test run is recorded in this session")
        elif failing_after and rows.index(failing_after[-1]) > rows.index(passing_after[-1]):
            problems.append("you say the tests pass, but the most recent test run failed")
    if claimed("merged", msg) and not bash_ok(r"\bgh pr merge\b|\bgit merge\b"):
        problems.append("you say it is merged, but no successful merge command is recorded; read the PR state before reporting it")
    if claimed("pushed", msg) and not bash_ok(r"\bgit push\b"):
        problems.append("you say it is pushed, but no successful git push is recorded")

    if problems:
        print(
            "tmn-fdekit receipts: " + "; ".join(problems) + ". Run the command now and report its real result, "
            "or rewrite the claim as \"not run\" / \"sent, not confirmed\".",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

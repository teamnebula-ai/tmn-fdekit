#!/usr/bin/env python3
"""PreToolUse guard for Bash. Blocks the moves a staff engineer never makes.

Exit 0 = allow. Exit 2 = block; the reason on stderr goes back to the agent so
it can correct course. Every rule is a yes/no on data, which is why it lives
in a hook and not in prompt text.

Rules (each names the habit it stops):
  merge-bypass     gh pr merge --admin / --auto           skips required review or checks
  merge-unready    gh pr merge with red/pending/no checks, an open change request, or no
                   approval on the head commit from someone who didn't write or push it
  self-approve     gh pr review --approve on a PR the current account wrote
  approve-blind    gh pr review --approve when this session never ran a passing test
  approve-empty    an approval with no body saying what was checked
  comment-spam     a second review comment on the same PR in one session (edit the first)
  force-push       git push --force / -f without --force-with-lease
  protected-push   git push straight to a protected branch
  no-verify        git commit/push --no-verify (skips the repo's hooks)

Turn a rule off with "guard": {"off": [...]} in the settings (scripts/config.py),
or TMN_FDEKIT_GUARD_OFF=rule1,rule2 in the environment that launches the agent.
The guard reads the settings frozen when the session started, so editing a file
mid-session changes nothing until the next one, and a prefix typed into the
command itself is ignored. The agent must not be able to waive its own guard.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import is_test_command, load_trace, read_hook_input, segments  # noqa: E402
import config  # noqa: E402

# Filled from the session's settings in main().
PROTECTED: set[str] = set(config.DEFAULTS["guard"]["protected"])
OFF: set[str] = set()
ALLOW_NO_CHECKS = False


def apply_settings(cfg: dict) -> None:
    global PROTECTED, OFF, ALLOW_NO_CHECKS
    g = cfg.get("guard", {})
    PROTECTED = set(g.get("protected", config.DEFAULTS["guard"]["protected"]))
    off = set(g.get("off", []))
    OFF = {"*"} if "all" in off else off
    ALLOW_NO_CHECKS = bool(g.get("allow_no_checks"))


class Block(Exception):
    def __init__(self, rule: str, msg: str):
        super().__init__(msg)
        self.rule = rule
        self.msg = msg


def gh_json(args: list[str], cwd: str | None) -> dict | list | None:
    try:
        r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=20, cwd=cwd or None)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def pr_target(toks: list[str]) -> tuple[list[str], list[str]]:
    """Return (positional PR ref as a list of 0..1 items, ['-R', repo] if given)."""
    repo: list[str] = []
    pos: list[str] = []
    skip_next = False
    value_flags = {"-R", "--repo", "-b", "--body", "-F", "--body-file", "-t", "--subject", "--match-head-commit", "--author-email"}
    for i, t in enumerate(toks):
        if skip_next:
            skip_next = False
            continue
        if t in ("-R", "--repo") and i + 1 < len(toks):
            repo = ["-R", toks[i + 1]]
            skip_next = True
            continue
        if t.startswith("--repo="):
            repo = ["-R", t.split("=", 1)[1]]
            continue
        if t in value_flags:
            skip_next = True
            continue
        if t.startswith("-"):
            continue
        pos.append(t)
    return pos[:1], repo


def check(rule: str, cond: bool, msg: str) -> None:
    if cond and rule not in OFF and "*" not in OFF:
        raise Block(rule, msg)


def guard_gh_pr(toks: list[str], ev: dict) -> None:
    sub = toks[2] if len(toks) > 2 else ""
    rest = toks[3:]
    cwd = ev.get("cwd")
    ref, repo = pr_target(rest)

    if sub == "merge":
        check("merge-bypass", any(t in ("--admin", "--auto") for t in rest),
              "Merging with --admin or --auto skips the review or the checks that protect main. "
              "Wait for green checks and a non-author approval, then merge plainly. If an approval is "
              "missing, say so and leave the PR open.")
        if "merge-unready" in OFF or "*" in OFF:
            return
        info = gh_json(["pr", "view", *ref, *repo, "--json", "number,reviewDecision,statusCheckRollup,isDraft,author,reviews,headRefOid,commits"], cwd)
        if info is None:
            raise Block("merge-unready", "Could not read the PR's review and check state with `gh pr view`, so the merge "
                        "is blocked rather than guessed. Fix gh auth or the PR reference and retry.")
        bad = [c for c in info.get("statusCheckRollup") or []
               if (c.get("conclusion") or c.get("state") or "").upper() not in ("SUCCESS", "NEUTRAL", "SKIPPED")]
        check("merge-unready", bool(info.get("isDraft")), "The PR is a draft. Mark it ready and get it reviewed first.")
        author = ((info.get("author") or {}).get("login") or "").lower()
        head = info.get("headRefOid") or ""
        pushers = {((a.get("login") or "")).lower() for c in info.get("commits") or [] for a in c.get("authors") or []}
        latest: dict[str, dict] = {}
        for r in info.get("reviews") or []:
            who = ((r.get("author") or {}).get("login") or "").lower()
            if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
                latest[who] = r
        holds = [w for w, r in latest.items() if r.get("state") == "CHANGES_REQUESTED"]
        approvals = [w for w, r in latest.items() if r.get("state") == "APPROVED" and w != author and w not in pushers
                     and (not head or not (r.get("commit") or {}).get("oid") or (r.get("commit") or {}).get("oid") == head)]
        check("merge-unready", bool(holds),
              f"Changes are still requested by {', '.join(holds)}. That reviewer must approve or dismiss their review first.")
        check("merge-unready", not approvals,
              "No approval covers the current head commit from someone who neither opened the PR nor pushed to it. "
              "A push after approval needs a fresh one. Leave the PR open and say who it is waiting on.")
        checks = info.get("statusCheckRollup") or []
        check("merge-unready", not checks and not ALLOW_NO_CHECKS,
              "No checks ran on this PR, so nothing shows it builds or passes tests. Add CI (see the enforce skill) "
              "or have a human set guard.allow_no_checks to true in the settings for this repo.")
        check("merge-unready", bool(bad),
              "Checks are not all green: " + ", ".join(sorted({(c.get('name') or c.get('context') or '?') + '=' + (c.get('conclusion') or c.get('state') or 'PENDING') for c in bad}))[:400]
              + ". Wait for every check, including non-required ones, or fix the red one.")

    if sub == "review":
        approving = any(t in ("--approve", "-a") for t in rest)
        if approving:
            if "self-approve" not in OFF and "*" not in OFF:
                info = gh_json(["pr", "view", *ref, *repo, "--json", "author"], cwd)
                me = gh_json(["api", "user"], cwd)
                author = ((info or {}).get("author") or {}).get("login")
                login = (me or {}).get("login")
                check("self-approve", bool(author and login and author.lower() == login.lower()),
                      f"This PR was opened by {author}, the account you are acting as. An author approving "
                      "their own work is not a review. Ask another person or a separate reviewer identity to approve.")
            body_i = next((i for i, t in enumerate(rest) if t in ("-b", "--body", "-F", "--body-file")), None)
            body = rest[body_i + 1] if body_i is not None and body_i + 1 < len(rest) else ""
            if body_i is not None and rest[body_i] in ("-F", "--body-file") and body != "-":
                bp = body if os.path.isabs(body) else os.path.join(cwd or os.getcwd(), body)
                try:
                    body = open(bp, errors="ignore").read()
                except OSError:
                    body = "x" * 20  # gh will fail on a missing file itself; don't double-report
            elif body_i is not None and rest[body_i] in ("-F", "--body-file"):
                body = "x" * 20  # stdin: can't see it, let it through
            check("approve-empty", len(body.strip()) < 20,
                  "An approval with no body tells the author nothing. Say what you checked and ran "
                  "(--body-file review.md, see the review skill's comment format).")
            rows = load_trace(ev.get("session_id") or "")
            ran = [r for r in rows if r.get("tool") == "Bash" and is_test_command(r.get("cmd")) and r.get("ok") is True]
            check("approve-blind", not ran,
                  "No passing test, gate or red/green run is recorded in this session. Approving means you saw it "
                  "work: check out the branch, run the suite (scripts/gate.py) and drive the changed path, then approve "
                  "with what you ran. If you can't run it, leave a comment instead of an approval.")
        posting = approving or any(t in ("--comment", "-c", "--request-changes", "-r") for t in rest)
        if posting:
            _no_second_comment(ref, repo, ev)

    if sub == "comment" and "--edit-last" not in rest and "--delete-last" not in rest:
        _no_second_comment(ref, repo, ev)


def _no_second_comment(ref: list[str], repo: list[str], ev: dict) -> None:
    key = (ref[0] if ref else "current-branch", repo[1] if repo else "")
    rows = load_trace(ev.get("session_id") or "")
    for r in rows:
        if r.get("tool") != "Bash" or r.get("ok") is False or not r.get("cmd"):
            continue
        for toks in segments(r["cmd"]):
            if len(toks) > 2 and toks[0] == "gh" and toks[1] == "pr" and toks[2] in ("comment", "review"):
                if toks[2] == "comment" and ("--edit-last" in toks or "--delete-last" in toks):
                    continue
                if toks[2] == "review" and not any(t in ("--approve", "-a", "--comment", "-c", "--request-changes", "-r") for t in toks):
                    continue
                pref, prepo = pr_target(toks[3:])
                if (pref[0] if pref else "current-branch", prepo[1] if prepo else "") == key:
                    check("comment-spam", True,
                          "This session already posted a review or comment on this PR. Reviews go out as ONE "
                          "consolidated comment per round: edit it with `gh pr comment <n> --edit-last --body-file <f>` "
                          "instead of adding another.")


def current_branch(cwd: str | None) -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5, cwd=cwd or None)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def guard_git(toks: list[str], cwd: str | None = None) -> None:
    # skip git's global options, including the ones that take a value (-C dir, -c k=v)
    i = 1
    while i < len(toks) and toks[i].startswith("-"):
        i += 2 if toks[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    if i >= len(toks):
        return
    sub = toks[i]
    rest = toks[i + 1:]
    for j in range(1, i):
        if toks[j] == "-C" and j + 1 < len(toks):
            cwd = os.path.join(cwd or os.getcwd(), toks[j + 1])
    if sub in ("commit", "push", "merge", "rebase"):
        check("no-verify", "--no-verify" in rest or (sub == "commit" and "-n" in rest),
              "--no-verify skips the repo's hooks (lint, tests, secret scan). Fix what the hook reports instead.")
    if sub != "push":
        return
    force = any(t in ("--force", "-f") or (t.startswith("-") and not t.startswith("--") and "f" in t[1:]) for t in rest)
    lease = any(t.startswith("--force-with-lease") or t.startswith("--force-if-includes") for t in rest)
    check("force-push", force and not lease,
          "Plain --force can overwrite a teammate's commits. Use --force-with-lease.")
    refs = [t for t in rest if not t.startswith("-")]
    targets = []
    for spec in refs[1:]:
        dst = spec.split(":", 1)[-1].lstrip("+")
        targets.append(dst.removeprefix("refs/heads/"))
    if not targets or targets == ["HEAD"]:
        targets = [current_branch(cwd)]
    hit = [t for t in targets if t in PROTECTED]
    check("protected-push", bool(hit),
          f"Pushing straight to {', '.join(hit)} skips review. Push a branch and open a PR.")


def _record_block(ev: dict, rule: str, command: str) -> None:
    """Blocked attempts belong in the audit trail too."""
    try:
        from _common import now_iso, redact, sessions_dir
        sid = ev.get("session_id")
        if sid:
            row = {"ts": now_iso(), "ev": "Blocked", "sid": sid, "tool": "Bash", "rule": rule, "cmd": redact(command), "ok": False}
            with (sessions_dir() / f"{sid}.jsonl").open("a") as fh:
                fh.write(json.dumps(row, separators=(",", ":")) + "\n")
    except Exception:
        pass


def main() -> int:
    ev = read_hook_input()
    apply_settings(config.for_session(ev))
    ti = ev.get("tool_input") or {}
    command = ti.get("command") if isinstance(ti, dict) else None
    if isinstance(command, list):  # some agents pass argv
        command = " ".join(command)
    if not isinstance(command, str):
        return 0
    if not command or "*" in OFF:
        return 0
    try:
        for toks in segments(command):
            if toks[0] == "gh" and len(toks) > 2 and toks[1] == "pr":
                guard_gh_pr(toks, ev)
            elif toks[0] == "gh" and len(toks) > 2 and toks[1] == "api":
                api = " ".join(toks[2:])
                check("merge-bypass", bool(re.search(r"pulls/\d+/merge\b", api)),
                      "Merging through `gh api` skips this guard's approval and check tests. Use `gh pr merge` instead.")
                check("self-approve", bool(re.search(r"pulls/\d+/reviews\b", api) and re.search(r"APPROVE\b", api)),
                      "Approving through `gh api` skips the self-approval and evidence checks. Use `gh pr review --approve`.")
            elif toks[0] == "git":
                guard_git(toks, ev.get("cwd"))
    except Block as b:
        print(f"tmn-fdekit guard [{b.rule}]: {b.msg}", file=sys.stderr)
        _record_block(ev, b.rule, command)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

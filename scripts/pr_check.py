#!/usr/bin/env python3
"""Deterministic PR hygiene. Every check is yes/no on the diff, so no model is needed.

    pr_check.py [--base origin/main] [--body pr.md | --pr 123] [--json]

Checks (FAIL blocks, WARN informs):
  size        changed lines / files (generated files and lockfiles excluded)
  commits     commits on the branch (one commit per PR when "one_commit" is set)
  tests       a test file changed, or the body has a "Why no tests:" line
  ticket      a ticket reference in the branch, commits or body
  secrets     credential-shaped strings in added lines
  paths       one person's machine paths (/Users/<name>/, C:\\Users\\...) in added lines
  env         env vars read by new code but missing from .env.example
  claims      the body says tests pass / adds security that no changed file shows

Limits and patterns come from .tmn-fdekit.json ("pr": {...}) when present:
  {"pr": {"warn_lines": 300, "max_lines": 500, "warn_files": 10, "max_files": 15,
          "one_commit": true, "ticket_re": "[A-Z][A-Z0-9]+-\\\\d+"}}
Add `pr-check:allow` on a line to vet a one-off exception; it shows in the report.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import SECRET_PATTERNS  # noqa: E402

DEFAULTS = {"warn_lines": 300, "max_lines": 500, "warn_files": 10, "max_files": 15, "one_commit": False,
            "ticket_re": r"\b[A-Z][A-Z0-9]{1,9}-\d+\b|(?:closes|fixes|resolves|refs)\s+#\d+|linear\.app/\S+/issue/|/browse/[A-Z]+-\d+"}
GENERATED = re.compile(r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock|Cargo\.lock|go\.sum|.*\.min\.(js|css)|.*\.snap|dist/|build/|vendor/)")
TEST_FILE = re.compile(r"(^|/)(tests?|__tests__|spec|e2e)/|(\.|_)(test|spec)\.[a-z]+$|(^|/)test_[^/]*\.py$|_test\.go$")
MACHINE = re.compile(r"/Users/(?!<|\$|\{|name\b|you\b|me\b|runner\b|Shared\b)[A-Za-z][\w.-]+/|/home/(?!<|\$|\{|runner\b|user\b|ubuntu\b|node\b)[a-z][\w.-]+/|C:\\\\?Users\\\\?")
SECRET = re.compile("|".join(f"(?:{p})" for p in SECRET_PATTERNS))
ENV_READ = re.compile(r"""os\.environ(?:\.get)?\(?\[?\s*['"]([A-Z][A-Z0-9_]+)['"]|os\.getenv\(\s*['"]([A-Z][A-Z0-9_]+)['"]|process\.env\.([A-Z][A-Z0-9_]+)|process\.env\[['"]([A-Z][A-Z0-9_]+)['"]\]|import\.meta\.env\.([A-Z][A-Z0-9_]+)|ENV\[['"]([A-Z][A-Z0-9_]+)['"]\]|os\.Getenv\("([A-Z][A-Z0-9_]+)"\)""")
ENV_IGNORE = {"PATH", "HOME", "USER", "PWD", "SHELL", "TERM", "CI", "NODE_ENV", "TZ", "LANG", "TMPDIR", "DEBUG", "PORT", "HOSTNAME"}


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def default_base() -> str:
    for ref in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", ref], capture_output=True).returncode == 0:
            return ref
    raise SystemExit("cannot find a base branch; pass --base")


def added_lines(base: str) -> dict[str, list[tuple[int, str]]]:
    diff = git("diff", "--unified=0", "--no-color", f"{base}...HEAD")
    out: dict[str, list[tuple[int, str]]] = {}
    cur, line_no = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else None
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)", line)
        if m:
            line_no = int(m.group(1))
            continue
        if cur and line.startswith("+") and not line.startswith("+++"):
            out.setdefault(cur, []).append((line_no, line[1:]))
            line_no += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--body", help="file with the PR description")
    ap.add_argument("--pr", help="read title+body from this PR with gh")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    root = Path(git("rev-parse", "--show-toplevel").strip())
    cfg = dict(DEFAULTS)
    cfg_file = root / ".tmn-fdekit.json"
    if cfg_file.exists():
        cfg.update((json.loads(cfg_file.read_text()).get("pr") or {}))
    base = a.base or default_base()

    body = ""
    if a.body:
        body = Path(a.body).read_text()
    elif a.pr:
        r = subprocess.run(["gh", "pr", "view", a.pr, "--json", "title,body"], capture_output=True, text=True)
        if r.returncode != 0:
            raise SystemExit(f"gh pr view failed: {r.stderr.strip()}")
        d = json.loads(r.stdout)
        body = f"{d.get('title', '')}\n{d.get('body', '')}"

    results: list[dict] = []

    def add(check: str, level: str, msg: str) -> None:
        results.append({"check": check, "level": level, "msg": msg})

    numstat = [l.split("\t") for l in git("diff", "--numstat", f"{base}...HEAD").splitlines() if l.strip()]
    counted = [(int(x) if x != "-" else 0, int(y) if y != "-" else 0, f) for x, y, f in numstat if not GENERATED.search(f)]
    lines = sum(x + y for x, y, _ in counted)
    files = [f for *_, f in counted]
    size_msg = f"{lines} lines in {len(files)} files (excluding generated/lockfiles)"
    if lines > cfg["max_lines"] or len(files) > cfg["max_files"]:
        add("size", "FAIL", f"{size_msg}; limit {cfg['max_lines']} lines / {cfg['max_files']} files. Ship the first working piece, then the next.")
    elif lines > cfg["warn_lines"] or len(files) > cfg["warn_files"]:
        add("size", "WARN", f"{size_msg}; target is under {cfg['warn_lines']} / {cfg['warn_files']}.")
    else:
        add("size", "ok", size_msg)

    commits = [c for c in git("log", "--format=%H%x09%s", f"{base}..HEAD").splitlines() if c]
    if cfg["one_commit"] and len(commits) != 1:
        add("commits", "FAIL", f"{len(commits)} commits; this repo wants one per PR. Squash: git reset --soft $(git merge-base {base} HEAD) && git commit")
    else:
        add("commits", "ok", f"{len(commits)} commit(s)")

    all_files = [f for *_, f in numstat]
    if any(TEST_FILE.search(f) for f in all_files):
        add("tests", "ok", "test files changed: " + ", ".join(f for f in all_files if TEST_FILE.search(f))[:200])
    elif re.search(r"(?im)^\W*why no tests\s*:", body):
        add("tests", "WARN", "no test changed; the body explains why")
    else:
        add("tests", "FAIL", "no test file changed and no 'Why no tests:' line. Add a test that fails without this change.")

    branch = git("rev-parse", "--abbrev-ref", "HEAD").strip()
    hay = "\n".join([branch, body, *(c.split("\t", 1)[-1] for c in commits)])
    tre = re.compile(cfg["ticket_re"], re.I)
    m = tre.search(hay)
    add("ticket", "ok" if m else "FAIL", f"ticket {m.group(0)}" if m else "no ticket reference in branch, commits or body (e.g. 'Closes ABC-123')")

    added = added_lines(base)
    env_example = ""
    for name in (".env.example", ".env.sample", ".env.template"):
        if (root / name).exists():
            env_example += (root / name).read_text(errors="ignore")
    secret_hits, path_hits, env_hits, allowed = [], [], set(), []
    for f, rows in added.items():
        if GENERATED.search(f):
            continue
        for n, text in rows:
            if "pr-check:allow" in text:
                allowed.append(f"{f}:{n}")
                continue
            if SECRET.search(text) and not re.search(r"(?i)example|placeholder|changeme|xxx|<[^>]+>|\$\{", text):
                secret_hits.append(f"{f}:{n}")
            if MACHINE.search(text):
                path_hits.append(f"{f}:{n}")
            for g in ENV_READ.finditer(text):
                var = next(x for x in g.groups() if x)
                if var not in ENV_IGNORE and not re.search(rf"(?m)^\s*(export\s+)?{var}\s*=", env_example):
                    env_hits.add(var)
    add("secrets", "FAIL" if secret_hits else "ok", ("credential-shaped strings at " + ", ".join(secret_hits[:8])) if secret_hits else "none in added lines")
    add("paths", "FAIL" if path_hits else "ok", ("personal machine paths at " + ", ".join(path_hits[:8]) + ". Resolve against a configurable base instead.") if path_hits else "none")
    if env_hits:
        add("env", "FAIL" if env_example else "WARN",
            f"new env vars not in .env.example: {', '.join(sorted(env_hits))}" + ("" if env_example else " (repo has no .env.example)"))
    else:
        add("env", "ok", "no undocumented env vars")
    if allowed:
        add("allowed", "WARN", "vetted exceptions (pr-check:allow): " + ", ".join(allowed[:8]))

    if body:
        if re.search(r"(?i)\b(tests? pass|all green|fully tested)\b", body) and not re.search(r"```|https?://\S+/actions/runs/|\d+ passed", body):
            add("claims", "WARN", "body says tests pass but shows no output or CI link. Paste the real result or the run URL.")
        for word, pat in (("RLS", r"(?i)row.level security|\bRLS\b|policy"), ("migration", r"(?i)migrat")):
            if re.search(rf"(?i)\b{word}\b", body) and not any(re.search(pat, f + "".join(t for _, t in added.get(f, []))) for f in files):
                add("claims", "WARN", f"body mentions {word} but no changed file shows it")

    worst = "FAIL" if any(r["level"] == "FAIL" for r in results) else "WARN" if any(r["level"] == "WARN" for r in results) else "ok"
    if a.json:
        print(json.dumps({"base": base, "result": worst, "checks": results}, indent=1))
    else:
        for r in results:
            print(f"{r['level']:4}  {r['check']:8} {r['msg']}")
        print(f"PR CHECK {'FAIL' if worst == 'FAIL' else 'PASS' + (' (with warnings)' if worst == 'WARN' else '')}  (base {base})")
    return 1 if worst == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())

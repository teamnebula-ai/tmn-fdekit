"""Shared helpers for tmn-fdekit scripts. Standard library only."""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

# Secrets we never write to a trace or print back. Patterns are deliberately broad;
# a false redaction costs nothing, a leaked key costs a rotation.
SECRET_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",                                   # AWS access key id
    r"gh[pousr]_[A-Za-z0-9]{30,}",                         # GitHub tokens
    r"github_pat_[A-Za-z0-9_]{40,}",
    r"xox[abprs]-[A-Za-z0-9-]{10,}",                       # Slack tokens
    r"sk-[A-Za-z0-9_-]{20,}",                              # OpenAI / Anthropic style keys
    r"sk-lf-[A-Za-z0-9-]{10,}|pk-lf-[A-Za-z0-9-]{10,}",    # Langfuse keys
    r"AIza[0-9A-Za-z_-]{35}",                              # Google API key
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*['\"]?[^\s'\"]{8,}",
    r"(?i:authorization:\s*(?:bearer|basic))\s+[A-Za-z0-9._~+/=-]{8,}",
]
_SECRET_RE = re.compile("|".join(f"(?:{p})" for p in SECRET_PATTERNS))

# Commands that count as "ran the tests / the gate" in a receipt.
TEST_CMD_RE = re.compile(
    r"(?:^|[\s;&|(])(?:"
    r"pytest|python3? -m pytest|tox|nox|"
    r"(?:npm|pnpm|yarn|bun)(?: run)? (?:test|check|ci)|npx (?:vitest|jest|playwright test)|vitest|jest|"
    r"go test|cargo test|cargo nextest|mvn (?:-\S+ )*(?:test|verify)|gradle(?:w)? (?:test|check)|"
    r"\./gradlew (?:test|check)|rspec|bundle exec rspec|mix test|dotnet test|phpunit|"
    r"make (?:\S+ )*(?:test|check|gate|ci)\b|just (?:test|check)|"
    r"\S*scripts/gate(?:\.py)?|\S*scripts/redgreen(?:\.sh)?"
    r")"
)

LINT_CMD_RE = re.compile(r"\b(?:ruff|eslint|biome|tsc|mypy|pyright|golangci-lint|clippy|shellcheck|stylelint|make (?:\S+ )*lint)\b")


def redact(text: str | None, limit: int = 400) -> str | None:
    if text is None:
        return None
    text = _SECRET_RE.sub("[REDACTED]", str(text))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def data_dir() -> Path:
    """Where traces, receipts and logs live. Never inside the repo being worked on."""
    base = os.environ.get("TMN_FDEKIT_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    path = Path(base) if base else Path.home() / ".tmn-fdekit"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sessions_dir() -> Path:
    d = data_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def read_hook_input() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def load_trace(session_id: str) -> list[dict]:
    path = sessions_dir() / f"{session_id}.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return rows


def latest_session_id(cwd: str | None = None) -> str | None:
    """Most recently active session. Several sessions can run at once, so prefer
    the newest one whose working directory is (inside) `cwd`."""
    sid = os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("TMN_FDEKIT_SESSION")
    if sid:
        return sid
    files = sorted(sessions_dir().glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    if cwd:
        here = os.path.realpath(cwd)
        for f in files[:50]:
            try:
                tail = f.read_bytes()[-4000:].decode(errors="ignore").splitlines()
                last = json.loads(tail[-1]) if tail else {}
            except (OSError, json.JSONDecodeError):
                continue
            there = os.path.realpath(last.get("cwd") or "")
            if there and (here == there or here.startswith(there + os.sep) or there.startswith(here + os.sep)):
                return f.stem
    return files[0].stem


EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def is_test_command(cmd: str | None) -> bool:
    return bool(cmd and TEST_CMD_RE.search(cmd))


def evidence_since_last_edit(rows: list[dict]) -> dict:
    """What a reviewer or the Stop hook needs to know: was anything run after the last edit?"""
    last_edit = -1
    for i, r in enumerate(rows):
        if r.get("tool") in EDIT_TOOLS and r.get("ok") is not False:
            last_edit = i
    tests = [r for r in rows[last_edit + 1 :] if r.get("tool") == "Bash" and is_test_command(r.get("cmd"))]
    return {
        "edited": last_edit >= 0,
        "tests_after_edit": len(tests),
        "tests_passed_after_edit": sum(1 for r in tests if r.get("ok") is True),
        "tests_failed_after_edit": sum(1 for r in tests if r.get("ok") is False),
    }


def segments(command: str) -> list[list[str]]:
    """Split a shell command line into simple commands and tokenise each."""
    parts = re.split(r"\s*(?:&&|\|\||;|\||\n)\s*", command)
    out = []
    for p in parts:
        p = p.strip().lstrip("(").rstrip(")")
        if not p:
            continue
        try:
            toks = shlex.split(p)
        except ValueError:
            toks = p.split()
        # drop leading VAR=value assignments and common wrappers
        while toks and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]) or toks[0] in ("env", "command", "time", "sudo")):
            toks = toks[1:]
        if toks:
            out.append(toks)
    return out

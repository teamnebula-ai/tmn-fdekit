#!/usr/bin/env python3
"""tmn-fdekit settings: one place for the limits, modes and team rules the skills and hooks follow.

    config.py show [--json]                 effective settings, and where each one came from
    config.py rules <skill>                 team rules that override that skill's defaults
    config.py set <key> <value> --scope user|repo     e.g. set pr.max_lines 1200 --scope repo
    config.py add-rule <skill|all> "<rule>" --scope user|repo
    config.py path [--scope user|repo]      where the file lives
    config.py validate                      exit 1 and say why if any file is wrong
    config.py snapshot                      SessionStart hook: freeze settings for this session

Layers, later wins: built-in defaults, the user file (~/.tmn-fdekit/config.json, or
$TMN_FDEKIT_CONFIG), the repo's .tmn-fdekit.json, then TMN_FDEKIT_* environment variables.
Team rules from the user and repo files add up rather than replace each other.

The guard and the comms lint read the snapshot taken when the session started, so a
change to these files applies from the next session. An agent can't loosen its own
guard halfway through a task by editing a file.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import read_hook_input, sessions_dir  # noqa: E402

# Size limits follow published review research: Google's guide calls ~100 lines reasonable and
# 1000 "usually too large"; the SmartBear/Cisco study saw defect detection drop past 200-400 lines.
DEFAULTS: dict = {
    "mode": "standard",
    "pr": {
        "warn_lines": 400, "max_lines": 1000, "warn_files": 25, "max_files": 50, "one_commit": False,
        "ticket_re": r"\b[A-Z][A-Z0-9]{1,9}-\d+\b|(?:closes|fixes|resolves|refs)\s+#\d+|linear\.app/\S+/issue/|/browse/[A-Z]+-\d+",
    },
    "guard": {"off": [], "protected": ["main", "master", "prod", "production", "release"], "allow_no_checks": False},
    "comms": {"mode": "block", "voice": None},
    "rules": {},
}
MODES = ("standard", "yolo")
COMMS_MODES = ("block", "warn", "off")
GUARD_RULES = ("merge-bypass", "merge-unready", "self-approve", "approve-blind", "approve-empty",
               "comment-spam", "force-push", "protected-push", "no-verify")
# Keys other scripts own (detect.py reads the repo's commands); accepted, not checked here.
PASSTHROUGH = {"lint", "types", "test", "build", "up", "down"}

ENV = {
    "TMN_FDEKIT_MODE": ("mode", lambda v: v.strip().lower()),
    "TMN_FDEKIT_GUARD_OFF": ("guard.off", lambda v: [x.strip() for x in v.split(",") if x.strip()]),
    "TMN_FDEKIT_PROTECTED": ("guard.protected", lambda v: v.split()),
    "TMN_FDEKIT_ALLOW_NO_CHECKS": ("guard.allow_no_checks", lambda v: v.strip() == "1"),
    "TMN_FDEKIT_COMMS": ("comms.mode", lambda v: v.strip().lower()),
    "TMN_FDEKIT_VOICE": ("comms.voice", lambda v: v.strip() or None),
}


class ConfigError(Exception):
    pass


def user_file() -> Path:
    return Path(os.environ.get("TMN_FDEKIT_CONFIG") or Path.home() / ".tmn-fdekit" / "config.json")


def repo_root(cwd: str | Path | None = None) -> Path:
    cwd = Path(cwd or os.getcwd())
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return cwd


def repo_file(cwd=None) -> Path:
    return repo_root(cwd) / ".tmn-fdekit.json"


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text() or "{}")
    except ValueError as e:
        raise ConfigError(f"{path} is not valid JSON ({e})")
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must hold a JSON object")
    validate(data, str(path))
    return data


def validate(data: dict, where: str) -> None:
    def bad(msg):
        raise ConfigError(f"{where}: {msg}")
    for key in data:
        if key not in DEFAULTS and key not in PASSTHROUGH:
            bad(f"unknown setting {key!r}")
    if "mode" in data and data["mode"] not in MODES:
        bad(f"mode {data['mode']!r} is not one of {', '.join(MODES)}")
    pr = data.get("pr", {})
    if not isinstance(pr, dict):
        bad("pr must be an object")
    for k, v in pr.items():
        if k not in DEFAULTS["pr"]:
            bad(f"unknown setting pr.{k}")
        if k in ("warn_lines", "max_lines", "warn_files", "max_files") and (not isinstance(v, int) or isinstance(v, bool) or v < 1):
            bad(f"pr.{k} must be a whole number above 0")
        if k == "one_commit" and not isinstance(v, bool):
            bad("pr.one_commit must be true or false")
    g = data.get("guard", {})
    if not isinstance(g, dict):
        bad("guard must be an object")
    for k in g:
        if k not in DEFAULTS["guard"]:
            bad(f"unknown setting guard.{k}")
    off = g.get("off", [])
    if not isinstance(off, list) or any(r not in (*GUARD_RULES, "all") for r in off):
        bad(f"guard.off takes rule names from: {', '.join(GUARD_RULES)}, or all")
    if "protected" in g and (not isinstance(g["protected"], list) or not all(isinstance(b, str) for b in g["protected"])):
        bad("guard.protected must be a list of branch names")
    c = data.get("comms", {})
    if not isinstance(c, dict):
        bad("comms must be an object")
    if "mode" in c and c["mode"] not in COMMS_MODES:
        bad(f"comms.mode must be one of {', '.join(COMMS_MODES)}")
    rules = data.get("rules", {})
    if not isinstance(rules, dict) or not all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in rules.values()):
        bad('rules must look like {"tmn-ship-pr": ["one rule", "another"], "all": ["..."]}')


def _merge(base: dict, layer: dict, source: str, sources: dict, prefix: str = "") -> None:
    for k, v in layer.items():
        path = f"{prefix}{k}"
        if k == "rules" and not prefix:
            for skill, items in v.items():
                base.setdefault("rules", {}).setdefault(skill, []).extend(items)
                sources[f"rules.{skill}"] = (sources.get(f"rules.{skill}", "") + " + " if f"rules.{skill}" in sources else "") + source
        elif isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v, source, sources, f"{path}.")
        else:
            base[k] = v
            sources[path] = source


def _leaves(d: dict, prefix: str = ""):
    for k, v in d.items():
        if isinstance(v, dict) and k != "rules":
            yield from _leaves(v, f"{prefix}{k}.")
        elif k != "rules":
            yield f"{prefix}{k}"


def load(cwd=None, env: dict | None = None) -> tuple[dict, dict]:
    """Effective settings and the source of each key. Raises ConfigError on any bad file or value."""
    env = os.environ if env is None else env
    cfg = copy.deepcopy(DEFAULTS)
    sources = {k: "default" for k in _leaves(cfg)}
    for path in (user_file(), repo_file(cwd)):
        _merge(cfg, _read(path), str(path), sources)
    for var, (key, parse) in ENV.items():
        if env.get(var, "").strip():
            node = cfg
            *parents, leaf = key.split(".")
            for p in parents:
                node = node[p]
            node[leaf] = parse(env[var])
            sources[key] = var
    validate({k: v for k, v in cfg.items()}, "settings")
    return cfg, sources


def snapshot_path(session_id: str) -> Path:
    return sessions_dir() / f"{session_id}.config.json"


def for_session(ev: dict) -> dict:
    """What the hooks use: this session's snapshot, else the live settings, else strict defaults."""
    sid = ev.get("session_id")
    if sid:
        p = snapshot_path(sid)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except ValueError:
                return copy.deepcopy(DEFAULTS)
    try:
        return load(ev.get("cwd"))[0]
    except ConfigError:
        return copy.deepcopy(DEFAULTS)


def rules_for(cfg: dict, skill: str) -> list[str]:
    r = cfg.get("rules", {})
    return [*r.get("all", []), *(r.get(skill, []) if skill != "all" else [])]


def _parse_value(raw: str):
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("rules"); s.add_argument("skill")
    s = sub.add_parser("set"); s.add_argument("key"); s.add_argument("value"); s.add_argument("--scope", choices=("user", "repo"), required=True)
    s = sub.add_parser("add-rule"); s.add_argument("skill"); s.add_argument("rule"); s.add_argument("--scope", choices=("user", "repo"), required=True)
    s = sub.add_parser("path"); s.add_argument("--scope", choices=("user", "repo"))
    sub.add_parser("validate")
    sub.add_parser("snapshot")
    a = ap.parse_args(argv)

    if a.cmd == "snapshot":
        ev = read_hook_input()
        sid = ev.get("session_id")
        try:
            cfg = load(ev.get("cwd"))[0]
            note = ""
        except ConfigError as e:
            cfg, note = copy.deepcopy(DEFAULTS), f"tmn-fdekit settings ignored for this session, strict defaults in use: {e}"
        if sid:
            _write(snapshot_path(sid), cfg)
        if note:
            print(note)        # SessionStart output reaches the session, so the person sees it too
        return 0

    try:
        if a.cmd == "path":
            scopes = [a.scope] if a.scope else ["user", "repo"]
            for sc in scopes:
                print(f"{sc}: {user_file() if sc == 'user' else repo_file()}")
            return 0
        if a.cmd in ("set", "add-rule"):
            path = user_file() if a.scope == "user" else repo_file()
            data = _read(path)
            if a.cmd == "set":
                node = data
                *parents, leaf = a.key.split(".")
                for p in parents:
                    node = node.setdefault(p, {})
                    if not isinstance(node, dict):
                        raise ConfigError(f"{a.key}: {p} is not an object")
                node[leaf] = _parse_value(a.value)
            else:
                data.setdefault("rules", {}).setdefault(a.skill, []).append(a.rule)
            validate(data, f"{a.key if a.cmd == 'set' else 'rules'}")
            merged = copy.deepcopy(DEFAULTS)
            _merge(merged, data, "new", {})
            pr = merged["pr"]
            if pr["warn_lines"] > pr["max_lines"] or pr["warn_files"] > pr["max_files"]:
                raise ConfigError("a pr.warn_* limit can't be above its pr.max_* limit")
            _write(path, data)
            print(f"wrote {path}. The guard and comms lint pick it up from the next session.")
            return 0
        cfg, sources = load()
        pr = cfg["pr"]
        if pr["warn_lines"] > pr["max_lines"] or pr["warn_files"] > pr["max_files"]:
            raise ConfigError("a pr.warn_* limit is above its pr.max_* limit")
        if a.cmd == "validate":
            print("settings OK")
        elif a.cmd == "rules":
            rules = rules_for(cfg, a.skill)
            print("\n".join(f"- {r}" for r in rules) if rules else f"No team rules for {a.skill}; the skill's defaults apply.")
        elif a.json:
            print(json.dumps({"config": cfg, "sources": sources}, indent=2))
        else:
            for key in sorted(sources):
                node = cfg
                for part in key.split("."):
                    node = node.get(part) if isinstance(node, dict) else None
                print(f"{key:24} {json.dumps(node):40} {sources[key]}")
    except ConfigError as e:
        print(f"config: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

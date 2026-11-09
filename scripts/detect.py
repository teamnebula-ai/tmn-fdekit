#!/usr/bin/env python3
"""Discover how to lint, type-check, test, build and run a repo. Never guess silently.

    detect.py [DIR]          # JSON: {"lint": "...", "types": "...", "test": "...", ...}

Order of authority (first hit per step wins):
  1. .tmn-fdekit.json in the repo  {"lint": "...", "test": "...", "up": "..."}
  2. .claude/project.json            keys lint/typecheck/test/build/run (if present)
  3. Makefile targets                lint, typecheck|types, test, build, up|dev|run
  4. package.json scripts            lint, typecheck|types|tsc, test, build, dev|start
  5. Python / Go / Rust conventions  ruff, mypy, pytest; go vet/test; cargo clippy/test
  6. docker compose file             "up" = docker compose up -d --wait

Each step reports where the command came from, so a reviewer can tell a repo's
own target from a fallback guess.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

STEPS = ("lint", "types", "test", "build", "up", "down")


def make_targets(root: Path) -> set[str]:
    mk = root / "Makefile"
    if not mk.exists():
        return set()
    return set(re.findall(r"^([A-Za-z0-9][\w.-]*)\s*:(?!=)", mk.read_text(errors="ignore"), re.M))


def pkg_manager(root: Path) -> str:
    for lock, pm in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun")):
        if (root / lock).exists():
            return pm
    return "npm"


def detect(root: Path) -> dict:
    found: dict[str, dict] = {}

    def put(step: str, cmd: str, source: str) -> None:
        if step not in found and cmd:
            found[step] = {"cmd": cmd, "source": source}

    cfg = root / ".tmn-fdekit.json"
    if cfg.exists():
        for k, v in json.loads(cfg.read_text()).items():
            if k in STEPS and isinstance(v, str):
                put(k, v, ".tmn-fdekit.json")

    pj = root / ".claude" / "project.json"
    if pj.exists():
        try:
            data = json.loads(pj.read_text())
            cmds = data.get("commands", data)
            for k, step in (("lint", "lint"), ("typecheck", "types"), ("test", "test"), ("build", "build"), ("run", "up")):
                if isinstance(cmds.get(k), str):
                    put(step, cmds[k], ".claude/project.json")
        except (json.JSONDecodeError, AttributeError):
            pass

    targets = make_targets(root)
    for step, names in (("lint", ["lint"]), ("types", ["typecheck", "types", "type-check"]), ("test", ["test", "tests", "check"]),
                        ("build", ["build"]), ("up", ["up", "dev", "run", "docker-up"]), ("down", ["down", "docker-down", "stop"])):
        for n in names:
            if n in targets:
                put(step, f"make {n}", "Makefile")
                break

    pkg = root / "package.json"
    if pkg.exists():
        scripts = (json.loads(pkg.read_text()).get("scripts") or {})
        pm = pkg_manager(root)
        run = f"{pm} run" if pm != "npm" else "npm run"
        for step, names in (("lint", ["lint"]), ("types", ["typecheck", "types", "tsc", "check-types"]), ("test", ["test"]),
                            ("build", ["build"]), ("up", ["dev", "start"])):
            for n in names:
                if n in scripts and "no test specified" not in scripts[n]:
                    put(step, f"{run} {n}" if n != "test" else f"{pm} test", "package.json")
                    break

    py = (root / "pyproject.toml").exists() or (root / "setup.py").exists() or (root / "requirements.txt").exists()
    if py:
        text = (root / "pyproject.toml").read_text(errors="ignore") if (root / "pyproject.toml").exists() else ""
        if "ruff" in text or shutil.which("ruff"):
            put("lint", "ruff check .", "python convention")
        if "mypy" in text:
            put("types", "mypy .", "python convention")
        elif "pyright" in text:
            put("types", "pyright", "python convention")
        if (root / "tests").exists() or "pytest" in text:
            put("test", "python3 -m pytest -q", "python convention")
    if (root / "go.mod").exists():
        put("lint", "go vet ./...", "go convention")
        put("test", "go test ./...", "go convention")
        put("build", "go build ./...", "go convention")
    if (root / "Cargo.toml").exists():
        put("lint", "cargo clippy --all-targets -- -D warnings", "rust convention")
        put("test", "cargo test", "rust convention")
        put("build", "cargo build", "rust convention")

    compose = next((root / n for n in ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml") if (root / n).exists()), None)
    if compose:
        put("up", f"docker compose -f {compose.name} up -d --build --wait", "compose file")
        put("down", f"docker compose -f {compose.name} down", "compose file")

    missing = [s for s in ("lint", "test") if s not in found]
    return {"root": str(root), "steps": found, "missing": missing}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(json.dumps(detect(root), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

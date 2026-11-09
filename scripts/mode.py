#!/usr/bin/env python3
"""Print the run mode the skills follow: standard or yolo.

    mode.py              # prints "standard" or "yolo"
    mode.py --explain    # also says where the setting came from

standard  stop at every checkpoint (push, PR, review, comment, message, merge,
          next skill in the chain) and wait for a yes.
yolo      take each checkpoint without stopping, report at the end. The hooks
          and hard lines are the same in both modes.

Order: TMN_FDEKIT_MODE, then "mode" in the repo's .tmn-fdekit.json, then
standard. An unknown value or a broken config exits 1, never a silent default.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

MODES = ("standard", "yolo")


def repo_root() -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


def resolve() -> tuple[str, str]:
    env = os.environ.get("TMN_FDEKIT_MODE", "").strip()
    if env:
        return env.lower(), "TMN_FDEKIT_MODE"
    cfg = repo_root() / ".tmn-fdekit.json"
    if cfg.exists():
        try:
            value = json.loads(cfg.read_text()).get("mode")
        except (ValueError, AttributeError) as e:
            raise SystemExit(f"mode: {cfg} is not a JSON object ({e})")
        if value:
            return str(value).strip().lower(), str(cfg)
    return "standard", "default"


def main(argv: list[str]) -> int:
    try:
        mode, source = resolve()
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    if mode not in MODES:
        print(f"mode: unknown mode {mode!r} from {source}; use one of {', '.join(MODES)}", file=sys.stderr)
        return 1
    print(f"{mode} (from {source})" if "--explain" in argv else mode)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Print the run mode the skills follow: standard or yolo.

    mode.py              # prints "standard" or "yolo"
    mode.py --explain    # also says where the setting came from

standard  stop at every checkpoint (push, PR, review, comment, message, merge,
          next skill in the chain) and wait for a yes.
yolo      take each checkpoint without stopping, report at the end. The hooks
          and hard lines are the same in both modes.

Order: TMN_FDEKIT_MODE, then "mode" in the repo's .tmn-fdekit.json, then the
user's ~/.tmn-fdekit/config.json, then standard (see config.py). An unknown
value or a broken file exits 1, never a silent default.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402


def main(argv: list[str]) -> int:
    try:
        cfg, sources = config.load()
    except config.ConfigError as e:
        print(f"mode: {e}", file=sys.stderr)
        return 1
    print(f"{cfg['mode']} (from {sources['mode']})" if "--explain" in argv else cfg["mode"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

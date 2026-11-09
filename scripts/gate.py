#!/usr/bin/env python3
"""Run the repo's own gate (lint → types → test → build) and print a short verdict.

    gate.py                     # all steps detect.py finds
    gate.py test                # one step
    gate.py lint test           # several, in the order given
    gate.py --list              # show what would run and where it came from

Full output of every step goes to a log file; the terminal (and so the agent's
context) gets one line per step plus the last lines of a failure. That is the
point: an agent that pipes a 4,000-line test log into its context pays for it
on every later turn.

Exit code: 0 only if every step that ran passed. A missing test step is a
failure, not a pass; say why there are no tests instead.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import data_dir  # noqa: E402
from detect import detect  # noqa: E402

ORDER = ("lint", "types", "test", "build")
TAIL = int(os.environ.get("TMN_FDEKIT_GATE_TAIL", "25"))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    root = Path.cwd()
    found = detect(root)
    steps = found["steps"]
    if "--list" in sys.argv:
        for s in ORDER + ("up", "down"):
            if s in steps:
                print(f"{s:6} {steps[s]['cmd']}   ({steps[s]['source']})")
        if found["missing"]:
            print(f"missing: {', '.join(found['missing'])}")
        return 0

    wanted = args or [s for s in ORDER if s in steps]
    logs = data_dir() / "logs" / root.name
    logs.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = []
    failed = False
    if "test" in (args or ORDER) and "test" not in steps:
        print("test   MISSING  no test command found (add one to .tmn-fdekit.json, a Makefile `test` target, or package.json)")
        failed = True
    for step in wanted:
        if step not in steps:
            if args:
                print(f"{step:6} MISSING  no command found for this step")
                failed = True
            continue
        cmd = steps[step]["cmd"]
        log = logs / f"{stamp}-{step}.log"
        t0 = time.time()
        with log.open("w") as fh:
            fh.write(f"$ {cmd}\n")
            fh.flush()
            proc = subprocess.run(cmd, shell=True, stdout=fh, stderr=subprocess.STDOUT, cwd=root)
        secs = time.time() - t0
        ok = proc.returncode == 0
        failed |= not ok
        results.append({"step": step, "cmd": cmd, "ok": ok, "exit": proc.returncode, "secs": round(secs, 1), "log": str(log)})
        print(f"{step:6} {'pass' if ok else 'FAIL'}  {secs:5.1f}s  `{cmd}`")
        if not ok:
            tail = log.read_text(errors="ignore").splitlines()[-TAIL:]
            print("       └ last lines:")
            for line in tail:
                print("         " + line[:200])
            print(f"       └ full log: {log}")
    (logs / f"{stamp}-gate.json").write_text(json.dumps(results, indent=1))
    print("GATE " + ("FAIL" if failed else "PASS"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

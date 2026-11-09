"""Shared fixtures: a fake `gh` on PATH, a temp data dir, and throwaway git repos."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

# Tests never read the developer's own settings: point the user config at a file that doesn't exist,
# and drop any session overrides from the shell that runs the suite.
os.environ["TMN_FDEKIT_CONFIG"] = str(Path(tempfile.gettempdir()) / "tmn-fdekit-tests-no-user-config.json")
for _k in ("TMN_FDEKIT_MODE", "TMN_FDEKIT_GUARD_OFF", "TMN_FDEKIT_PROTECTED", "TMN_FDEKIT_COMMS",
           "TMN_FDEKIT_ALLOW_NO_CHECKS", "TMN_FDEKIT_VOICE"):
    os.environ.pop(_k, None)


def sh(cwd, *cmd, check=True):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        sh(self.repo, "git", "config", "user.email", "t@example.com")
        sh(self.repo, "git", "config", "user.name", "t")
        sh(self.repo, "git", "config", "commit.gpgsign", "false")
        self.env = dict(os.environ, TMN_FDEKIT_DATA=str(Path(self.tmp.name) / "data"))

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-q", "-m", msg)

    def run_tool(self, name, *args):
        exe = [str(SCRIPTS / name)] if name.endswith(".sh") else [sys.executable, str(SCRIPTS / name)]
        return subprocess.run([*exe, *args], cwd=self.repo, capture_output=True, text=True, env=self.env, timeout=120)

    def python_project(self, buggy=True):
        self.write("calc.py", "def add(a, b):\n    return a - b\n" if buggy else "def add(a, b):\n    return a + b\n")
        self.write("Makefile", "test:\n\tpython3 -m unittest discover -s tests -q\nlint:\n\tpython3 -m py_compile calc.py\n")


class HookCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name) / "data"
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        self.sid = "sess-test-1"
        self.gh_state = {"author": "someone-else", "me": "reviewer", "decision": "APPROVED",
                         "checks": [{"name": "ci", "conclusion": "SUCCESS"}], "draft": False,
                         "reviews": [{"state": "APPROVED", "author": {"login": "teammate"}, "commit": {"oid": "head1"}}]}
        self.write_fake_gh()

    def tearDown(self):
        self.tmp.cleanup()

    def write_fake_gh(self):
        state = Path(self.tmp.name) / "gh_state.json"
        state.write_text(json.dumps(self.gh_state))
        gh = self.bin / "gh"
        gh.write_text(textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import json, sys
            s = json.load(open({str(state)!r}))
            a = sys.argv[1:]
            if a[:2] == ["api", "user"]:
                print(json.dumps({{"login": s["me"]}}))
            elif a[:2] == ["pr", "view"]:
                print(json.dumps({{"number": 7, "author": {{"login": s["author"]}}, "reviewDecision": s["decision"],
                                  "statusCheckRollup": s["checks"], "isDraft": s["draft"], "reviews": s["reviews"],
                                  "headRefOid": "head1", "commits": [{{"authors": [{{"login": a}} for a in s.get("pushers", [])]}}]}}))
            else:
                sys.exit(1)
            """))
        gh.chmod(0o755)

    def env(self, **extra):
        e = dict(os.environ)
        e.update({"TMN_FDEKIT_DATA": str(self.data), "PATH": f"{self.bin}:{e['PATH']}"})
        e.pop("TMN_FDEKIT_GUARD_OFF", None)
        e.pop("CLAUDE_SESSION_ID", None)
        e.update(extra)
        return e

    def run_script(self, name, payload, *args, **env):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *args], input=json.dumps(payload),
                              capture_output=True, text=True, env=self.env(**env), timeout=30)

    def trace(self, tool, ok=True, cmd=None, file=None):
        ev = "PostToolUse" if ok else "PostToolUseFailure"
        ti = {}
        if cmd:
            ti["command"] = cmd
        if file:
            ti["file_path"] = file
        r = self.run_script("trace.py", {"session_id": self.sid, "hook_event_name": ev, "tool_name": tool,
                                         "tool_input": ti, "cwd": self.tmp.name})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "", "trace must print nothing (zero tokens)")

    def guard(self, command, **env):
        return self.run_script("guard.py", {"session_id": self.sid, "tool_name": "Bash", "cwd": self.tmp.name,
                                            "tool_input": {"command": command}}, **env)

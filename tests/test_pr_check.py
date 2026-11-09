"""pr_check against throwaway repos."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ROOT, SCRIPTS, HookCase, RepoCase, sh  # noqa: E402,F401


class PrCheckTests(RepoCase):
    def setUp(self):
        super().setUp()
        self.write("README.md", "x\n")
        self.write(".env.example", "API_URL=\n")
        self.commit("base")
        sh(self.repo, "git", "checkout", "-q", "-b", "feat/ABC-12-thing")

    def checks(self, *args):
        r = self.run_tool("pr_check.py", "--base", "main", "--json", *args)
        return r.returncode, {c["check"]: c for c in json.loads(r.stdout)["checks"]}

    def test_clean_pr_passes(self):
        self.write("app.py", "import os\nURL = os.environ['API_URL']\n")
        self.write("tests/test_app.py", "def test_x():\n    assert True\n")
        self.commit("add app")
        code, c = self.checks()
        self.assertEqual(code, 0, c)
        self.assertEqual(c["ticket"]["level"], "ok")

    def test_secret_path_env_and_missing_tests_fail(self):
        self.write("app.py", "import os\nKEY = 'AKIA" + "ABCDEFGHIJKLMNOP'\nBASE = '/Users/alice/data/'\nX = os.getenv('NEW_SETTING')\n")
        self.commit("add app")
        code, c = self.checks()
        self.assertEqual(code, 1)
        for name in ("secrets", "paths", "env", "tests"):
            self.assertEqual(c[name]["level"], "FAIL", name)
        self.assertIn("NEW_SETTING", c["env"]["msg"])

    def test_placeholder_paths_are_fine(self):
        self.write("doc.md", "Clone to /Users/<name>/code or $HOME.\n")
        self.write("tests/t_test.py", "x=1\n")
        self.commit("docs")
        self.assertEqual(self.checks()[1]["paths"]["level"], "ok")

    def test_size_limit_and_one_commit(self):
        self.write(".tmn-fdekit.json", json.dumps({"pr": {"max_lines": 20, "one_commit": True}}))
        self.write("big.py", "x = 1\n" * 40)
        self.write("tests/test_big.py", "x=1\n")
        self.commit("one")
        self.write("more.py", "y = 2\n")
        self.commit("two")
        code, c = self.checks()
        self.assertEqual(c["size"]["level"], "FAIL")
        self.assertEqual(c["commits"]["level"], "FAIL")

    def test_no_ticket_fails_and_claims_warn(self):
        sh(self.repo, "git", "checkout", "-q", "-b", "misc")
        self.write("tests/test_a.py", "x=1\n")
        self.commit("stuff")
        body = Path(self.tmp.name) / "body.md"
        body.write_text("All tests pass. Adds RLS to the table.")
        code, c = self.checks("--body", str(body))
        self.assertEqual(c["ticket"]["level"], "FAIL")
        self.assertEqual(c["claims"]["level"], "WARN")


if __name__ == "__main__":
    unittest.main()

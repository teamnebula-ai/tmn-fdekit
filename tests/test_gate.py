"""detect, gate and redgreen against throwaway repos."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ROOT, SCRIPTS, HookCase, RepoCase, sh  # noqa: E402,F401


class DetectGateTests(RepoCase):
    def test_makefile_wins_and_sources_are_reported(self):
        self.python_project()
        self.write("package.json", json.dumps({"scripts": {"test": "jest", "lint": "eslint ."}}))
        out = json.loads(self.run_tool("detect.py").stdout)
        self.assertEqual(out["steps"]["test"], {"cmd": "make test", "source": "Makefile"})
        self.assertEqual(out["steps"]["lint"]["source"], "Makefile")

    def test_repo_config_overrides_everything(self):
        self.python_project()
        self.write(".tmn-fdekit.json", json.dumps({"test": "./run-tests"}))
        out = json.loads(self.run_tool("detect.py").stdout)
        self.assertEqual(out["steps"]["test"]["cmd"], "./run-tests")

    def test_gate_fails_short_and_points_at_log(self):
        self.python_project(buggy=True)
        self.write("tests/test_calc.py", "import unittest, calc\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(calc.add(2, 2), 4)\n")
        r = self.run_tool("gate.py")
        self.assertEqual(r.returncode, 1)
        self.assertIn("test   FAIL", r.stdout)
        self.assertIn("full log:", r.stdout)
        self.assertLess(len(r.stdout.splitlines()), 45, "gate output must stay short")
        self.assertIn("GATE FAIL", r.stdout)

    def test_gate_missing_tests_is_not_a_pass(self):
        self.write("Makefile", "lint:\n\ttrue\n")
        r = self.run_tool("gate.py")
        self.assertEqual(r.returncode, 1)
        self.assertIn("MISSING", r.stdout)


class RedGreenTests(RepoCase):
    def setUp(self):
        super().setUp()
        self.python_project(buggy=True)
        self.write("tests/__init__.py", "")
        self.commit("base")
        sh(self.repo, "git", "checkout", "-q", "-b", "fix")

    def test_red_then_green(self):
        self.python_project(buggy=False)
        self.write("tests/test_calc.py", "import unittest, calc\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(calc.add(2, 2), 4)\n")
        self.commit("fix add")
        r = self.run_tool("redgreen.sh", "main", "python3 -m unittest discover -s tests -q")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REDGREEN PASS", r.stdout)
        self.assertNotIn("NOTE", r.stdout)
        self.assertEqual(sh(self.repo, "git", "worktree", "list").stdout.count("\n"), 1, "worktree must be cleaned up")

    def test_red_from_missing_code_gets_a_note(self):
        self.write("calc.py", "def add(a, b):\n    return a - b\n\ndef mul(a, b):\n    return a * b\n")
        self.write("tests/test_mul.py", "import unittest\nfrom calc import mul\nclass T(unittest.TestCase):\n    def test_mul(self):\n        self.assertEqual(mul(2, 3), 6)\n")
        self.commit("add mul")
        r = self.run_tool("redgreen.sh", "main", "python3 -m unittest discover -s tests -q")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("NOTE   red only because the code under test is new", r.stdout)

    def test_stale_bytecode_is_ignored(self):
        self.python_project(buggy=False)
        self.write("tests/test_calc.py", "import unittest, calc\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(calc.add(2, 2), 4)\n")
        self.commit("fix add")
        sh(self.repo, "python3", "-m", "unittest", "discover", "-s", "tests", "-q")  # leaves __pycache__ behind
        self.assertTrue(list(self.repo.rglob("*.pyc")))
        r = self.run_tool("redgreen.sh", "main", "python3 -m unittest discover -s tests -q")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(".pyc", r.stdout)

    def test_test_that_passes_on_base_is_caught(self):
        self.write("tests/test_calc.py", "import unittest, calc\nclass T(unittest.TestCase):\n    def test_exists(self):\n        self.assertTrue(callable(calc.add))\n")
        self.commit("weak test")
        r = self.run_tool("redgreen.sh", "main", "python3 -m unittest discover -s tests -q")
        self.assertEqual(r.returncode, 1)
        self.assertIn("do not detect this change", r.stdout)

    def test_no_tests_changed(self):
        self.python_project(buggy=False)
        self.commit("fix without test")
        r = self.run_tool("redgreen.sh", "main", "true")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NO TESTS CHANGED", r.stdout)


if __name__ == "__main__":
    unittest.main()

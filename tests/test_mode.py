"""mode.py: standard (stop at checkpoints) or yolo (run the chain through)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SCRIPTS  # noqa: E402


def mode(cwd: Path, env_mode: str | None = None, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "TMN_FDEKIT_MODE"}
    if env_mode is not None:
        env["TMN_FDEKIT_MODE"] = env_mode
    return subprocess.run([sys.executable, str(SCRIPTS / "mode.py"), *args], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=30)


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.dir)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_is_standard(self):
        r = mode(self.dir)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "standard"))

    def test_repo_config_sets_yolo(self):
        (self.dir / ".tmn-fdekit.json").write_text(json.dumps({"mode": "yolo"}))
        sub = self.dir / "src"
        sub.mkdir()
        self.assertEqual(mode(sub).stdout.strip(), "yolo", "found from a subfolder via the repo root")

    def test_environment_wins_over_repo_config(self):
        (self.dir / ".tmn-fdekit.json").write_text(json.dumps({"mode": "yolo"}))
        self.assertEqual(mode(self.dir, "standard").stdout.strip(), "standard")
        self.assertEqual(mode(self.dir, "YOLO").stdout.strip(), "yolo", "case doesn't matter")

    def test_explain_names_the_source(self):
        r = mode(self.dir, "yolo", "--explain")
        self.assertIn("yolo", r.stdout)
        self.assertIn("TMN_FDEKIT_MODE", r.stdout)

    def test_unknown_mode_fails_loudly(self):
        r = mode(self.dir, "fast")
        self.assertEqual(r.returncode, 1)
        self.assertIn("fast", r.stderr)
        self.assertEqual(r.stdout, "")
        (self.dir / ".tmn-fdekit.json").write_text("{not json")
        self.assertEqual(mode(self.dir).returncode, 1, "a broken config is an error, not the default")


if __name__ == "__main__":
    unittest.main()

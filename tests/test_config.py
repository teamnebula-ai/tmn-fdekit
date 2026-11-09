"""config.py: layered settings (defaults < user < repo < environment), team rules, session snapshots."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import SCRIPTS, HookCase  # noqa: E402


class ConfigTests(HookCase):
    def setUp(self):
        super().setUp()
        self.work = Path(self.tmp.name)            # the cwd the hooks see; not a git repo, so it's the "repo" root
        self.user = self.work / "user-config.json"
        self.repo_cfg = self.work / ".tmn-fdekit.json"

    def cfg(self, *args, **env):
        return subprocess.run([sys.executable, str(SCRIPTS / "config.py"), *args], cwd=self.work,
                              capture_output=True, text=True, env=self.env(TMN_FDEKIT_CONFIG=str(self.user), **env),
                              timeout=30)

    def show(self, **env) -> dict:
        r = self.cfg("show", "--json", **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_defaults_follow_review_research(self):
        pr = self.show()["config"]["pr"]
        self.assertEqual((pr["warn_lines"], pr["max_lines"], pr["warn_files"], pr["max_files"]), (400, 1000, 25, 50))
        self.assertEqual(self.show()["config"]["mode"], "standard")

    def test_layers_user_then_repo_then_environment(self):
        self.user.write_text(json.dumps({"pr": {"max_lines": 1500, "warn_lines": 600}, "mode": "yolo"}))
        self.repo_cfg.write_text(json.dumps({"pr": {"max_lines": 800}}))
        out = self.show()
        self.assertEqual(out["config"]["pr"]["max_lines"], 800, "repo beats user")
        self.assertEqual(out["config"]["pr"]["warn_lines"], 600, "user beats default")
        self.assertEqual(Path(out["sources"]["pr.max_lines"]).resolve(), self.repo_cfg.resolve())
        self.assertEqual(Path(out["sources"]["pr.warn_lines"]).resolve(), self.user.resolve())
        self.assertEqual(out["sources"]["pr.max_files"], "default")
        env = self.show(TMN_FDEKIT_MODE="standard")
        self.assertEqual((env["config"]["mode"], env["sources"]["mode"]), ("standard", "TMN_FDEKIT_MODE"))

    def test_team_rules_from_both_files_apply_to_a_skill(self):
        self.user.write_text(json.dumps({"rules": {"all": ["Say 'shipped', not 'deployed'."]}}))
        self.repo_cfg.write_text(json.dumps({"rules": {"tmn-ship-pr": ["Squash-merge only."], "tmn-slack": ["x"]}}))
        r = self.cfg("rules", "tmn-ship-pr")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Say 'shipped'", r.stdout)
        self.assertIn("Squash-merge only.", r.stdout)
        self.assertNotIn("\nx", r.stdout)
        other = self.cfg("rules", "tmn-debug").stdout
        self.assertIn("Say 'shipped'", other, "rules under 'all' apply to every skill")
        self.assertNotIn("Squash", other)
        self.user.unlink()
        self.repo_cfg.unlink()
        self.assertIn("No team rules", self.cfg("rules", "tmn-debug").stdout)

    def test_set_writes_the_chosen_scope_and_rejects_bad_values(self):
        r = self.cfg("set", "pr.max_lines", "1200", "--scope", "user")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(self.user.read_text())["pr"]["max_lines"], 1200, "numbers stay numbers")
        self.assertEqual(self.cfg("add-rule", "tmn-slack", "Eight sentences is fine in #eng.", "--scope", "repo").returncode, 0)
        self.assertEqual(json.loads(self.repo_cfg.read_text())["rules"]["tmn-slack"], ["Eight sentences is fine in #eng."])
        before = self.user.read_text()
        for key, value in (("pr.warn_lines", "5000"), ("mode", "fast"), ("guard.off", '["no-such-rule"]'),
                           ("comms.mode", "loud"), ("pr.nope", "1")):
            bad = self.cfg("set", key, value, "--scope", "user")
            self.assertEqual(bad.returncode, 1, f"{key}={value} should be refused")
            self.assertTrue(bad.stderr.strip())
        self.assertEqual(self.user.read_text(), before, "a refused value writes nothing")

    def test_a_broken_file_fails_loudly(self):
        self.user.write_text("{nope")
        r = self.cfg("show")
        self.assertEqual(r.returncode, 1)
        self.assertIn(str(self.user), r.stderr)

    def snapshot(self):
        r = self.run_script("config.py", {"session_id": self.sid, "hook_event_name": "SessionStart", "cwd": str(self.work)},
                            "snapshot", TMN_FDEKIT_CONFIG=str(self.user))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "", "a good snapshot prints nothing")

    def guard(self, command, **env):
        return super().guard(command, TMN_FDEKIT_CONFIG=str(self.user), **env)

    def test_guard_reads_settings_from_the_session_snapshot(self):
        self.repo_cfg.write_text(json.dumps({"guard": {"protected": ["trunk"]}}))
        self.snapshot()
        self.assertEqual(self.guard("git push origin trunk").returncode, 2)
        self.assertEqual(self.guard("git push origin main").returncode, 0, "main isn't protected in this repo")

    def test_loosening_the_guard_mid_session_waits_for_the_next_session(self):
        self.snapshot()
        self.assertEqual(self.guard("gh pr merge 7 --admin").returncode, 2)
        self.repo_cfg.write_text(json.dumps({"guard": {"off": ["merge-bypass"]}}))
        r = self.guard("gh pr merge 7 --admin")
        self.assertEqual(r.returncode, 2, "an edit during the session must not waive the guard")
        self.snapshot()                                    # the next session starts
        self.assertEqual(self.guard("gh pr merge 7 --admin").returncode, 0)

    def test_comms_mode_comes_from_config(self):
        self.user.write_text(json.dumps({"comms": {"mode": "off"}}))
        self.snapshot()
        slop = "I hope this helps! Let's delve into this robust, seamless, game-changing solution. 🚀"
        r = self.run_script("comms.py", {"session_id": self.sid, "tool_name": "mcp__slack__send_message",
                                         "cwd": str(self.work), "tool_input": {"text": slop}}, TMN_FDEKIT_CONFIG=str(self.user))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_snapshot_reports_a_broken_config_into_the_session_and_keeps_defaults(self):
        self.repo_cfg.write_text(json.dumps({"guard": {"off": ["merge-bypas"]}}))
        r = self.run_script("config.py", {"session_id": self.sid, "cwd": str(self.work)}, "snapshot",
                            TMN_FDEKIT_CONFIG=str(self.user))
        self.assertEqual(r.returncode, 0)
        self.assertIn("merge-bypas", r.stdout, "the agent and the person see why the settings were ignored")
        self.assertEqual(self.guard("gh pr merge 7 --admin").returncode, 2, "strict defaults, not a silent waiver")


if __name__ == "__main__":
    unittest.main()

"""Trace writer, receipts and the claims Stop hook."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ROOT, SCRIPTS, HookCase, RepoCase, sh  # noqa: E402,F401


class TraceTests(HookCase):
    def test_redacts_secrets_and_writes_one_line(self):
        self.trace("Bash", cmd="curl -H 'Authorization: Bearer abcdefghijklmnop123' https://x && echo ghp_" + "a" * 36)
        rows = (self.data / "sessions" / f"{self.sid}.jsonl").read_text().splitlines()
        self.assertEqual(len(rows), 1)
        self.assertNotIn("abcdefghijklmnop123", rows[0])
        self.assertNotIn("ghp_aaaa", rows[0])
        self.assertIn("[REDACTED]", rows[0])

    def test_nonzero_exit_inside_post_tool_use_is_a_failure(self):
        self.run_script("trace.py", {"session_id": self.sid, "hook_event_name": "PostToolUse", "tool_name": "Bash",
                                     "tool_input": {"command": "pytest"}, "tool_response": {"exit_code": 1}})
        row = json.loads((self.data / "sessions" / f"{self.sid}.jsonl").read_text())
        self.assertIs(row["ok"], False)

    def test_garbage_input_never_breaks(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "trace.py")], input="not json", capture_output=True,
                           text=True, env=self.env())
        self.assertEqual((r.returncode, r.stdout), (0, ""))


class ClaimsTests(HookCase):
    def stop(self, msg, active=False):
        return self.run_script("claims.py", {"session_id": self.sid, "hook_event_name": "Stop",
                                             "last_assistant_message": msg, "stop_hook_active": active})

    def test_claim_without_test_run_blocks_stop(self):
        self.trace("Edit", file="app.py")
        r = self.stop("Fixed the bug. All tests pass.")
        self.assertEqual(r.returncode, 2)
        self.assertIn("after your last edit", r.stderr)

    def test_claim_with_test_after_edit_is_fine(self):
        self.trace("Edit", file="app.py")
        self.trace("Bash", cmd="npm test")
        self.assertEqual(self.stop("Fixed it; tests pass (41 passed).").returncode, 0)

    def test_edit_after_test_reopens_the_claim(self):
        self.trace("Bash", cmd="pytest")
        self.trace("Edit", file="app.py")
        self.assertEqual(self.stop("Done, the suite passes.").returncode, 2)

    def test_honest_negative_is_fine(self):
        self.trace("Edit", file="app.py")
        self.assertEqual(self.stop("Changed app.py. Tests not run yet, so I can't say the tests pass.").returncode, 0)

    def test_merged_claim_needs_merge(self):
        self.trace("Bash", cmd="git status")
        self.assertEqual(self.stop("PR #9 is merged.").returncode, 2)

    def test_second_stop_is_allowed(self):
        self.trace("Edit", file="app.py")
        self.assertEqual(self.stop("All tests pass.", active=True).returncode, 0)


class ReceiptTests(HookCase):
    def test_receipt_lists_tests_and_warns_on_stale_edit(self):
        self.trace("Bash", cmd="pytest -q")
        self.trace("Edit", file=f"{self.tmp.name}/app.py")
        r = subprocess.run([sys.executable, str(SCRIPTS / "receipt.py"), "--session", self.sid],
                           capture_output=True, text=True, env=self.env())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("`pytest -q` → pass", r.stdout)
        self.assertIn("edited after the last test run", r.stdout)

    def test_hook_mode_writes_files_silently(self):
        self.trace("Bash", cmd="go test ./...")
        r = self.run_script("receipt.py", {"session_id": self.sid, "hook_event_name": "Stop"}, "--hook")
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        self.assertTrue((self.data / "receipts" / f"{self.sid}.md").exists())


if __name__ == "__main__":
    unittest.main()

"""Tests for the slop linter and the comms hook."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from slop import lint, verdict  # noqa: E402


def rules(text, target="slack", voice=None):
    return {r for _, r, s, _ in lint(text, target, voice) if s != "weak"}


class SlopTests(unittest.TestCase):
    def test_clean_human_message_passes(self):
        msg = ("Fixed the login timeout, Jacob. Sessions now last eight hours instead of one. "
               "Nice find on the cookie expiry. Let me know if you hit any blockers.")
        self.assertTrue(verdict(lint(msg, "slack")), lint(msg, "slack"))

    def test_chatbot_and_staged_tells_fail(self):
        msg = "Great question! Here's the thing: it's not just a bug, but a design flaw. I hope this helps!"
        found = rules(msg)
        self.assertTrue({"chatbot-residue", "not-x-but-y"} <= found, found)
        self.assertFalse(verdict(lint(msg)))

    def test_plain_not_but_is_fine(self):
        self.assertNotIn("not-x-but-y", rules("It's not merged yet, but CI is green."))

    def test_lmk_only_allowed_as_the_closer(self):
        self.assertIn("chatbot-residue", rules("Let me know if this works. The deploy is done."))

    def test_code_and_quotes_are_ignored(self):
        msg = "Renamed the flag.\n\n```\n# delve into robust seamless tapestry\n```\n> I hope this helps\n"
        self.assertTrue(verdict(lint(msg, "pr")))

    def test_slack_specific_rules(self):
        self.assertIn("lone-greeting", rules("hey"))
        found = rules("Deployed 3f9c2ab1 and I ran the tests, exit code 0.")
        self.assertTrue({"ref-soup", "proof-of-work"} <= found, found)

    def test_em_dash_follows_voice(self):
        msg = "Merged the fix — the page loads again."
        self.assertIn("em-dash", rules(msg, "slack"))
        voice = "Shipped it — thanks. All good — ping me. Done — see the doc." * 3
        self.assertNotIn("em-dash", rules(msg, "slack", voice))

    def test_first_person_fault_only_in_published_text(self):
        self.assertIn("first-person-fault", rules("It's my fault, I missed the smoke gate.", "pr"))
        self.assertNotIn("first-person-fault", rules("It's my fault, I missed the smoke gate.", "chat"))

    def test_ai_vocab_density(self):
        self.assertIn("ai-vocab", rules("We delve into a robust, seamless rollout."))
        long = "The migration adds an index on user id. " * 20 + "It is robust."
        self.assertNotIn("ai-vocab", rules(long, "pr"))


class CommsHookTests(unittest.TestCase):
    def run_hook(self, payload, **env):
        e = dict(os.environ)
        e.pop("TMN_FDEKIT_COMMS", None)
        e.update(env)
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "comms.py")], input=json.dumps(payload),
                              capture_output=True, text=True, env=e)

    def test_blocks_sloppy_pr_comment(self):
        cmd = "gh pr comment 4 --body 'Great question! I hope this helps.'"
        r = self.run_hook({"tool_name": "Bash", "tool_input": {"command": cmd}})
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("chatbot-residue", r.stderr)

    def test_reads_body_file_and_commit_message(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "b.md").write_text("Let's dive in! This PR is a testament to our pivotal, robust work.")
            r = self.run_hook({"tool_name": "Bash", "cwd": d, "tool_input": {"command": "gh pr create -t x --body-file b.md"}})
            self.assertEqual(r.returncode, 2)
        r = self.run_hook({"tool_name": "Bash", "tool_input": {"command": "git commit -m 'fix: session cookie expires after 8h'"}})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_slack_mcp_send(self):
        p = {"tool_name": "mcp__slack__slack_send_message", "tool_input": {"channel_id": "C1", "text": "hey"}}
        self.assertEqual(self.run_hook(p).returncode, 2)
        self.assertEqual(self.run_hook(p, TMN_FDEKIT_COMMS="warn").returncode, 0)
        p["tool_input"]["text"] = "The booking page shows the right time zone again. Thanks for flagging it, Maya."
        self.assertEqual(self.run_hook(p).returncode, 0)

    def test_other_tools_ignored(self):
        self.assertEqual(self.run_hook({"tool_name": "Read", "tool_input": {"file_path": "x"}}).returncode, 0)


if __name__ == "__main__":
    unittest.main()

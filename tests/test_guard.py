"""The PreToolUse guard."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ROOT, SCRIPTS, HookCase, RepoCase, sh  # noqa: E402,F401


class GuardTests(HookCase):
    def assertBlocked(self, r, rule):
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(f"[{rule}]", r.stderr)

    def assertAllowed(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_admin_and_auto_merge_blocked(self):
        self.assertBlocked(self.guard("gh pr merge 7 --squash --admin"), "merge-bypass")
        self.assertBlocked(self.guard("cd x && gh pr merge --auto 7"), "merge-bypass")
        self.assertBlocked(self.guard("gh api -X PUT repos/o/r/pulls/7/merge"), "merge-bypass")

    def test_typed_prefix_cannot_waive_the_guard(self):
        self.assertBlocked(self.guard("TMN_FDEKIT_GUARD_OFF=all gh pr merge 7 --admin"), "merge-bypass")

    def test_environment_can_waive_a_rule(self):
        self.assertAllowed(self.guard("gh pr merge 7 --admin", TMN_FDEKIT_GUARD_OFF="merge-bypass"))

    def test_merge_needs_green_and_approval(self):
        self.assertAllowed(self.guard("gh pr merge 7 --squash"))
        self.gh_state["checks"] = [{"name": "ci", "conclusion": "SUCCESS"}, {"name": "scan", "state": "PENDING"}]
        self.write_fake_gh()
        r = self.guard("gh pr merge 7 --squash")
        self.assertBlocked(r, "merge-unready")
        self.assertIn("scan=PENDING", r.stderr)

    def test_merge_without_non_author_approval_blocked(self):
        self.gh_state.update(decision="", reviews=[{"state": "APPROVED", "author": {"login": "someone-else"}}])
        self.write_fake_gh()
        self.assertBlocked(self.guard("gh pr merge 7"), "merge-unready")
        self.gh_state["reviews"] = [{"state": "APPROVED", "author": {"login": "teammate"}}]
        self.write_fake_gh()
        self.assertAllowed(self.guard("gh pr merge 7"))

    def test_stale_approval_open_hold_and_pusher_approval_blocked(self):
        self.gh_state["reviews"] = [{"state": "APPROVED", "author": {"login": "teammate"}, "commit": {"oid": "old"}}]
        self.write_fake_gh()
        self.assertBlocked(self.guard("gh pr merge 7"), "merge-unready")
        self.gh_state["reviews"] = [{"state": "APPROVED", "author": {"login": "teammate"}, "commit": {"oid": "head1"}},
                                    {"state": "CHANGES_REQUESTED", "author": {"login": "lead"}}]
        self.write_fake_gh()
        self.assertIn("lead", self.guard("gh pr merge 7").stderr)
        self.gh_state.update(reviews=[{"state": "APPROVED", "author": {"login": "teammate"}, "commit": {"oid": "head1"}}],
                             pushers=["teammate"])
        self.write_fake_gh()
        self.assertBlocked(self.guard("gh pr merge 7"), "merge-unready")

    def test_merge_with_no_checks_blocked(self):
        self.gh_state["checks"] = []
        self.write_fake_gh()
        self.assertBlocked(self.guard("gh pr merge 7"), "merge-unready")
        self.assertAllowed(self.guard("gh pr merge 7", TMN_FDEKIT_ALLOW_NO_CHECKS="1"))

    def test_self_approval_blocked(self):
        self.trace("Bash", cmd="pytest -q")
        self.gh_state.update(author="reviewer")
        self.write_fake_gh()
        self.assertBlocked(self.guard("gh pr review 7 --approve -b ok"), "self-approve")

    def test_approve_requires_a_passing_test_in_session(self):
        self.assertBlocked(self.guard("gh pr review 7 --approve -b 'Looks right to me overall.'"), "approve-blind")
        self.trace("Bash", ok=False, cmd="pytest -q")
        self.assertBlocked(self.guard("gh pr review 7 --approve -b 'ran it, all fine here'"), "approve-blind")
        self.trace("Bash", cmd="python3 -m pytest -q")
        self.assertBlocked(self.guard("gh pr review 7 --approve -b 'LGTM'"), "approve-empty")
        Path(self.tmp.name, "review.md").write_text("Approve. Ran pytest: 41 passed; drove the endpoint.")
        self.assertAllowed(self.guard("gh pr review 7 --approve --body-file review.md"))
        self.assertAllowed(self.guard("gh pr review 7 --approve -b 'ran pytest: 41 passed'"))

    def test_second_comment_on_same_pr_blocked_but_edit_allowed(self):
        self.trace("Bash", cmd="gh pr comment 7 --body-file findings.md")
        self.assertBlocked(self.guard("gh pr comment 7 -b 'one more nit'"), "comment-spam")
        self.assertBlocked(self.guard("gh pr review 7 --comment -b 'also'"), "comment-spam")
        self.assertAllowed(self.guard("gh pr comment 7 --edit-last --body-file findings.md"))
        self.assertAllowed(self.guard("gh pr comment 8 --body-file other.md"))

    def test_force_push(self):
        self.assertBlocked(self.guard("git push --force origin feat"), "force-push")
        self.assertBlocked(self.guard("git push -fu origin feat"), "force-push")
        self.assertAllowed(self.guard("git push --force-with-lease origin feat"))

    def test_protected_push_variants(self):
        for cmd in ("git push origin main", "git -C repo push origin main", "git push origin dev:main",
                    "git push origin HEAD:refs/heads/main", "git push origin +master"):
            self.assertBlocked(self.guard(cmd), "protected-push")
        self.assertAllowed(self.guard("git push origin main-fix"))
        self.assertAllowed(self.guard("git push -u origin feat/x"))

    def test_no_verify(self):
        self.assertBlocked(self.guard("git commit --no-verify -m x"), "no-verify")
        self.assertBlocked(self.guard("git push --no-verify origin feat"), "no-verify")

    def test_other_agents_shell_tool_names_are_guarded(self):
        r = self.run_script("guard.py", {"session_id": self.sid, "tool_name": "shell", "cwd": self.tmp.name,
                                         "tool_input": {"command": ["git", "push", "--force", "origin", "x"]}})
        self.assertBlocked(r, "force-push")

    def test_harmless_commands_pass(self):
        for cmd in ("git status", "ls -la", "gh pr view 7", "gh pr list", "echo 'gh pr merge --admin'"):
            self.assertAllowed(self.guard(cmd))


class GuardReceiptTests(HookCase):
    def test_guard_blocks_show_in_receipt(self):
        self.guard("git push --force origin feat")
        r = subprocess.run([sys.executable, str(SCRIPTS / "receipt.py"), "--session", self.sid],
                           capture_output=True, text=True, env=self.env())
        self.assertIn("Blocked by the guard: force-push", r.stdout)


if __name__ == "__main__":
    unittest.main()

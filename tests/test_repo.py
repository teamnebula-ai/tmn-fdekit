"""Repo-level checks: skill metadata, references, size, and no leaked private data."""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir()) if (ROOT / "skills").exists() else []
AGENTS = sorted((ROOT / "agents").glob("*.md"))
SHIPPED = [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "tests" not in p.parts
           and p.suffix in {".md", ".py", ".sh", ".json", ".yml", ".yaml", ".mjs", ".html"}]

# Markers of private context that must never ship. The generic ones live here. Names that are
# themselves private (people, clients, machines) go one regex per line in .private-patterns, which
# git ignores, or in TMN_FDEKIT_PRIVATE (comma-separated), so this public file never contains them.
_LOCAL = ROOT / ".private-patterns"
PRIVATE = [r"CLAUDE\.local", r"/Users/(?!<|\$|\{|name\b|you\b|me\b|runner\b|Shared\b|alice\b)[A-Za-z][\w.-]+/"]
PRIVATE += [x.strip() for x in os.environ.get("TMN_FDEKIT_PRIVATE", "").split(",") if x.strip()]
if _LOCAL.exists():
    PRIVATE += [x.strip() for x in _LOCAL.read_text().splitlines() if x.strip() and not x.startswith("#")]


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


class RepoTests(unittest.TestCase):
    def test_skill_frontmatter_follows_agent_skills_spec(self):
        for d in SKILLS:
            fm = frontmatter(d / "SKILL.md")
            self.assertEqual(fm.get("name"), d.name, d)
            self.assertRegex(fm["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
            self.assertLessEqual(len(fm["name"]), 64)
            self.assertTrue(20 < len(fm.get("description", "")) <= 1024, d)
            self.assertLessEqual(set(fm) - {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}, set(),
                                 f"{d}: only Agent Skills standard fields, so the skill works outside Claude Code")

    def test_skill_bodies_stay_small(self):
        for d in SKILLS:
            self.assertLess(len((d / "SKILL.md").read_text().splitlines()), 500, d)

    def test_agents_have_name_and_description(self):
        for a in AGENTS:
            fm = frontmatter(a)
            self.assertEqual(fm.get("name"), a.stem)
            self.assertTrue(fm.get("description"))

    def test_referenced_scripts_and_files_exist(self):
        for p in [d / "SKILL.md" for d in SKILLS] + AGENTS + [h for h in [ROOT / "hooks" / "hooks.json"] if h.exists()]:
            text = p.read_text()
            for s in set(re.findall(r"scripts/([\w.-]+\.(?:py|sh))", text)):
                self.assertTrue((ROOT / "scripts" / s).exists(), f"{p} references missing scripts/{s}")
            for s in set(re.findall(r"templates/([\w./-]+\.(?:yml|yaml|json))", text)):
                self.assertTrue((ROOT / "templates" / s).exists(), f"{p} references missing templates/{s}")
            for s in set(re.findall(r"\]\((references/[\w.-]+)\)", text)):
                self.assertTrue((p.parent / s).exists(), f"{p} links missing {s}")
            for s in set(re.findall(r"`tmn-fdekit:([\w-]+)`", text)):
                self.assertTrue((ROOT / "agents" / f"{s}.md").exists(), f"{p} names missing agent {s}")

    def test_skills_named_in_staff_bar_exist(self):
        if not (ROOT / "skills" / "tmn-staff-bar").exists():
            self.skipTest("staff-bar not added yet")
        text = (ROOT / "skills" / "tmn-staff-bar" / "SKILL.md").read_text()
        tiers = text.split("## Skill tiers", 1)[1]
        for name in re.findall(r"`([a-z-]+)`", tiers):
            self.assertTrue((ROOT / "skills" / name).is_dir(), f"staff-bar lists missing skill {name}")

    def test_every_skill_follows_the_run_mode(self):
        bar = (ROOT / "skills" / "tmn-staff-bar" / "SKILL.md").read_text()
        self.assertIn("scripts/mode.py", bar)
        for p in sorted((ROOT / "skills").glob("tmn-*/SKILL.md")):
            if p.parent.name != "tmn-staff-bar":
                self.assertIn("run mode in `tmn-staff-bar`", p.read_text(), p.parent.name)

    def test_no_private_context_ships(self):
        hits = []
        for p in SHIPPED:
            text = p.read_text(errors="ignore")
            for pat in PRIVATE:
                for m in re.finditer(pat, text, re.I):
                    hits.append(f"{p.relative_to(ROOT)}:{text.count(chr(10), 0, m.start()) + 1} {m.group(0)}")
        self.assertEqual(hits, [])

    def test_skill_examples_pass_our_own_slop_lint(self):
        if not SKILLS:
            self.skipTest("no skills yet")
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from slop import lint
        for d in SKILLS:
            for quote in re.findall(r"^> (.+(?:\n> .+)*)", (d / "SKILL.md").read_text(), re.M):
                text = re.sub(r"^> ", "", quote, flags=re.M)
                strong = [f for f in lint(text, "slack") if f[2] == "strong"]
                self.assertEqual(strong, [], f"{d.name} example: {text[:60]}")


if __name__ == "__main__":
    unittest.main()

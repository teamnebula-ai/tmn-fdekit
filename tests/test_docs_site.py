"""docs_site.py: markdown folder -> one self-contained documentation page."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ROOT, SCRIPTS  # noqa: E402

EXAMPLE = ROOT / "skills" / "tmn-docs-site" / "assets" / "example"


def build(src: Path, out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "docs_site.py"), str(src), "-o", str(out), *extra],
                          capture_output=True, text=True, timeout=60)


class DocsSiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.out = self.dir / "site.html"

    def tearDown(self):
        self.tmp.cleanup()

    def built(self, *extra: str) -> str:
        r = build(EXAMPLE, self.out, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return self.out.read_text()

    def test_builds_every_page_with_nav_toc_and_breadcrumbs(self):
        html = self.built()
        self.assertIn("<title>Lark Docs</title>", html)
        for slug in ("index", "quickstart", "config", "changelog"):
            self.assertIn(f'data-slug="{slug}"', html)
        self.assertIn(">Get started<", html)
        self.assertIn(">Reference<", html)
        self.assertIn('id="quickstart--install"', html, "headings get page-scoped ids")
        self.assertIn('href="#quickstart--install"', html, "on-this-page link")
        self.assertIn('class="crumbs"', html)
        self.assertIn("Updated 2026-11-07", html)

    def test_markdown_features_render(self):
        html = self.built()
        self.assertIn('<table>', html)
        self.assertIn("<th>Command</th>", html)
        self.assertIn('class="callout callout-important"', html)
        self.assertIn('class="callout callout-tip"', html)
        self.assertIn('class="callout callout-warning"', html)
        self.assertIn('class="callout callout-quote"', html, "a plain quote becomes a grey box")
        self.assertIn('class="steps"', html)
        self.assertIn('class="cards"', html)
        self.assertIn('<code class="lang-bash">', html)
        self.assertRegex(html, r"<ul>\s*<li><code>interval</code>")
        self.assertIn("<ol>", html)
        self.assertIn("<strong>everything</strong>", html)
        self.assertIn('href="#config--sync"', html, "links to .md pages become in-page routes")

    def test_raw_html_in_markdown_is_escaped(self):
        html = self.built()
        self.assertNotIn('<script>alert("not html")</script>', html)
        self.assertIn("&lt;script&gt;", html)

    def test_page_is_self_contained_and_follows_the_artifact_contract(self):
        html = self.built()
        srcs = re.findall(r"<script[^>]*\bsrc=\"([^\"]+)\"", html)
        self.assertEqual(srcs, [], "no external scripts")
        for href in re.findall(r"<link[^>]*rel=\"stylesheet\"[^>]*href=\"([^\"]+)\"", html):
            self.assertTrue(href.startswith("https://fonts.googleapis.com/"), href)
        self.assertIn(':root:not([data-theme="light"])', html)
        self.assertIn(':root[data-theme="dark"]', html)
        self.assertIn('name="viewport"', html)
        self.assertLess(len(html.encode()), 16 * 1024 * 1024)

    def test_copy_for_llm_carries_the_page_markdown(self):
        html = self.built()
        m = re.search(r'<script type="application/json" id="docs-data">(.*?)</script>', html, re.S)
        self.assertIsNotNone(m)
        data = json.loads(m.group(1))
        self.assertIn("lark init ~/notes", data["markdown"]["quickstart"])
        self.assertTrue(any(e["slug"] == "config" and e["heading"] == "Sync" for e in data["search"]))

    def test_output_passes_the_ui_linter(self):
        self.built()
        r = subprocess.run([sys.executable, str(SCRIPTS / "ui_lint.py"), str(self.out)], capture_output=True, text=True)
        self.assertNotIn("ERROR", r.stdout, r.stdout)

    def test_styles(self):
        warm = self.built("--style", "warm")
        self.assertIn("Source+Serif", warm)
        dark = self.built("--style", "dark")
        self.assertIn('<html lang="en">', dark, "dark-first is CSS only, so a viewer's own theme choice still wins")
        self.assertIn(':root:not([data-theme="dark"])', dark)
        self.assertRegex(dark, r":root\{--bg:#0a0d0b")

    def test_routes_are_plain_hash_names(self):
        html = self.built()
        self.assertNotIn('href="#/', html, "artifact links keep only a plain #name")
        src = self.dir / "src"
        src.mkdir()
        (src / "settings.md").write_text("# Settings\n\ntext\n")
        (src / "index.md").write_text("# Home\n\nSee [settings](settings.md).\n")
        self.assertEqual(build(src, self.out).returncode, 0)
        self.assertIn('href="#page-settings"', self.out.read_text(), "names the host reserves get a prefix")

    def test_artifact_mode_leaves_the_skeleton_to_the_host(self):
        html = self.built("--artifact")
        self.assertTrue(html.startswith("<title>Lark Docs</title>"), html[:80])
        for tag in ("<!doctype", "<html", "<head>", "<body>", "</body>"):
            self.assertNotIn(tag, html)

    def test_nav_without_site_json_comes_from_frontmatter(self):
        src = self.dir / "src"
        shutil.copytree(EXAMPLE, src)
        (src / "site.json").unlink()
        (src / "config.md").write_text("---\ntitle: Config file\ngroup: Reference\n---\n\n## Sync\n\ntext\n")
        r = build(src, self.out, "--title", "Lark")
        self.assertEqual(r.returncode, 0, r.stderr)
        html = self.out.read_text()
        self.assertIn(">Reference<", html)
        self.assertIn("<title>Lark</title>", html)

    def test_a_nav_entry_without_a_page_fails_loudly(self):
        src = self.dir / "src"
        shutil.copytree(EXAMPLE, src)
        (src / "config.md").unlink()
        r = build(src, self.out)
        self.assertEqual(r.returncode, 1)
        self.assertIn("config", r.stderr)
        self.assertFalse(self.out.exists())

    def test_unsafe_link_schemes_are_dropped(self):
        src = self.dir / "src"
        src.mkdir()
        (src / "index.md").write_text("# Home\n\n[click](javascript:alert(1)) and [ok](https://example.com)\n")
        r = build(src, self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        html = re.sub(r'<script type="application/json".*?</script>', "", self.out.read_text(), flags=re.S)
        self.assertNotIn("javascript:", html)
        self.assertIn("<p>click and", html)
        self.assertIn('href="https://example.com"', html)


if __name__ == "__main__":
    unittest.main()

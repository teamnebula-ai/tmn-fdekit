#!/usr/bin/env python3
"""Build a documentation site as ONE self-contained HTML page.

    docs_site.py SRC_DIR -o site.html [--style clean|warm|dark] [--title T] [--accent #hex]

SRC_DIR holds markdown pages (one per file) and an optional site.json:

    {"title": "...", "tagline": "...", "style": "clean", "accent": "#0e7c66",
     "links": [{"label": "GitHub", "href": "https://..."}],
     "nav": [{"group": "Get started", "pages": ["index", "quickstart"]}]}

Without site.json the nav comes from each page's frontmatter (`group`, `order`).
The result has a sidebar, breadcrumbs, an "On this page" rail with scroll spy,
Cmd/Ctrl+K search, Copy for LLM, light and dark themes, and a phone layout.
No dependencies; nothing is fetched at build time. Syntax: skills/tmn-docs-site/references/syntax.md.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

STYLES = ("clean", "warm", "dark")
CALLOUTS = {"NOTE": "note", "TIP": "tip", "IMPORTANT": "important", "WARNING": "warning", "CAUTION": "warning"}
CALLOUT_LABEL = {"note": "Note", "tip": "Tip", "important": "Important", "warning": "Warning"}

# 24px stroke icons for cards. Simple geometric shapes, drawn for this file.
ICONS = {
    "book": "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z M4 19V5 M8 7h8 M8 11h6",
    "terminal": "M3 5h18v14H3z M7 9l3 3-3 3 M12 15h5",
    "rocket": "M9 15l-3-3c1.5-4.5 5-8 11-9 .5 0 1 .5 1 1-1 6-4.5 9.5-9 11z M6 12l-3 1 2-4h4 M12 18l-1 3 4-2v-4 M15 9.5a1 1 0 1 0 0-.01",
    "cube": "M12 2l9 5v10l-9 5-9-5V7z M3 7l9 5 9-5 M12 12v10",
    "shield": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z M9 12l2 2 4-4",
    "chart": "M4 20V10 M10 20V4 M16 20v-7 M3 20h18",
    "code": "M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16",
    "plug": "M9 3v5 M15 3v5 M6 8h12v3a6 6 0 0 1-12 0z M12 17v4",
    "pen": "M4 20l4-1 11-11-3-3L5 16z M14 6l3 3",
    "search": "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4",
    "layers": "M12 3l9 5-9 5-9-5z M3 13l9 5 9-5",
    "check": "M5 12l4 4 10-10",
}
ICON_CYCLE = ["rocket", "terminal", "layers", "cube", "book", "code", "chart", "plug"]


# ---------------------------------------------------------------- markdown

RESERVED = {"settings", "sidebar", "customize", "upgrade", "downloads"}


def route_id(name: str) -> str:
    """A page's route: a plain #name (letters, digits, single hyphens), the only hash an artifact link keeps."""
    r = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "page"
    return f"page-{r}" if r in RESERVED or r.startswith("comment-") else r


def slugify(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    return re.sub(r"[\s-]+", "-", s).strip("-") or "section"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("'\"")
    return meta, text[m.end():]


class Renderer:
    """A small, strict markdown subset. Every piece of text is escaped; raw HTML is shown as text."""

    def __init__(self, slug: str, pages: dict):
        self.slug = slug
        self.pages = pages  # slug -> meta, for links and card icons
        self.ids: dict[str, int] = {}
        self.toc: list[tuple[int, str, str]] = []
        self.headings: list[tuple[str, str, str]] = []  # (id, text, body text) for search

    # ---- inline
    def href(self, url: str) -> str | None:
        url = url.strip()
        if re.match(r"^(https?:|mailto:)", url, re.I):
            return url
        if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.I):
            return None  # javascript:, data: and friends
        if url.startswith("#"):
            return f"#{self.slug}--{slugify(url[1:])}" if url[1:] else f"#{self.slug}"
        path, _, frag = url.partition("#")
        target = route_id(re.sub(r"\.mdx?$", "", path.removeprefix("./")))
        if target in self.pages and (path.endswith((".md", ".mdx")) or "/" not in path):
            return f"#{target}" + (f"--{slugify(frag)}" if frag else "")
        return url

    def inline(self, text: str) -> str:
        parts = re.split(r"(`[^`]+`)", text)
        out = []
        for p in parts:
            if len(p) > 1 and p.startswith("`") and p.endswith("`"):
                out.append(f"<code>{html.escape(p[1:-1])}</code>")
                continue
            s = html.escape(p, quote=False)
            s = re.sub(r"!\[([^\]]*)\]\(((?:[^()\s]|\([^()\s]*\))+)\)", lambda m: self._img(m.group(1), m.group(2)), s)
            s = re.sub(r"\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)", lambda m: self._link(m.group(1), m.group(2)), s)
            s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
            s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
            out.append(s)
        return "".join(out)

    def _link(self, label: str, url: str) -> str:
        h = self.href(html.unescape(url))
        if h is None:
            return label
        ext = ' target="_blank" rel="noopener"' if h.startswith("http") else ""
        return f'<a href="{html.escape(h)}"{ext}>{label}</a>'

    def _img(self, alt: str, url: str) -> str:
        h = self.href(html.unescape(url))
        return f'<img src="{html.escape(h)}" alt="{alt}" loading="lazy">' if h else alt

    def heading_id(self, text: str) -> str:
        base = slugify(text)
        n = self.ids.get(base, 0)
        self.ids[base] = n + 1
        return base if n == 0 else f"{base}-{n}"

    # ---- blocks
    def render(self, md: str) -> str:
        return self.blocks(md.replace("\r\n", "\n").split("\n"))

    def blocks(self, lines: list[str]) -> str:
        out: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            s = line.strip()
            if not s:
                i += 1
                continue
            if s.startswith("```"):
                lang = s[3:].strip()
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith("```"):
                    j += 1
                code = html.escape("\n".join(lines[i + 1:j]))
                cls = f' class="lang-{html.escape(lang)}"' if lang else ""
                out.append(f'<div class="code"><button type="button" class="copy-code" aria-label="Copy code">Copy</button>'
                           f"<pre><code{cls}>{code}</code></pre></div>")
                i = j + 1
                continue
            m = re.match(r"^:::(\w+)\s*$", s)
            if m:
                j = i + 1
                depth = 0
                while j < len(lines):
                    t = lines[j].strip()
                    if t.startswith("```"):
                        depth ^= 1
                    elif t == ":::" and not depth:
                        break
                    j += 1
                out.append(self.directive(m.group(1), lines[i + 1:j]))
                i = j + 1
                continue
            m = re.match(r"^(#{1,4})\s+(.*)$", s)
            if m:
                level = max(2, len(m.group(1)))
                text = m.group(2).strip()
                hid = self.heading_id(text)
                if level <= 3:
                    self.toc.append((level, text, hid))
                self.headings.append((hid, text, ""))
                out.append(f'<h{level} id="{self.slug}--{hid}"><a class="anchor" href="#{self.slug}--{hid}" '
                           f'aria-label="Link to this section">#</a>{self.inline(text)}</h{level}>')
                i += 1
                continue
            if re.match(r"^(-{3,}|\*{3,})$", s):
                out.append("<hr>")
                i += 1
                continue
            if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
                j = i + 2
                while j < len(lines) and lines[j].strip().startswith("|"):
                    j += 1
                out.append(self.table(lines[i], lines[i + 2:j]))
                i = j
                continue
            if s.startswith(">"):
                j = i
                while j < len(lines) and lines[j].strip().startswith(">"):
                    j += 1
                out.append(self.quote([re.sub(r"^\s*> ?", "", ln) for ln in lines[i:j]]))
                i = j
                continue
            if re.match(r"^([-*]|\d+\.)\s+", s) and not line.startswith(" "):
                j, block = self.list_block(lines, i)
                out.append(block)
                i = j
                continue
            m = re.match(r"^!\[([^\]]*)\]\(([^)\s]+)\)$", s)
            if m:
                out.append(f'<figure>{self.inline(s)}<figcaption>{self.inline(m.group(1))}</figcaption></figure>' if m.group(1) else self.inline(s))
                i += 1
                continue
            j = i
            para = []
            while j < len(lines) and lines[j].strip() and not self.starts_block(lines[j], lines[j + 1] if j + 1 < len(lines) else ""):
                para.append(lines[j].strip())
                j += 1
            if not para:  # a line that looks like a block start but did not parse as one
                para, j = [s], i + 1
            text = " ".join(para)
            self._note_text(text)
            out.append(f"<p>{self.inline(text)}</p>")
            i = j
        return "\n".join(out)

    def _note_text(self, text: str) -> None:
        if self.headings:
            hid, h, body = self.headings[-1]
            self.headings[-1] = (hid, h, (body + " " + text)[:400])
        else:
            self.headings.append(("", "", text[:400]))

    @staticmethod
    def starts_block(line: str, nxt: str) -> bool:
        s = line.strip()
        return bool(re.match(r"^(```|:::|#{1,4}\s|>|\|)", s) or (re.match(r"^([-*]|\d+\.)\s+", s) and not line.startswith(" "))
                    or re.match(r"^(-{3,}|\*{3,})$", s))

    def table(self, head: str, rows: list[str]) -> str:
        def cells(r: str) -> list[str]:
            r = r.strip().strip("|")
            return [c.strip() for c in re.split(r"(?<!\\)\|", r)]
        th = "".join(f"<th>{self.inline(c)}</th>" for c in cells(head))
        body = "".join("<tr>" + "".join(f"<td>{self.inline(c)}</td>" for c in cells(r)) + "</tr>" for r in rows)
        return f'<div class="table"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'

    def quote(self, lines: list[str]) -> str:
        kind = "quote"
        m = re.match(r"^\[!(\w+)\]\s*(.*)$", lines[0].strip()) if lines else None
        if m and m.group(1).upper() in CALLOUTS:
            kind = CALLOUTS[m.group(1).upper()]
            lines = ([m.group(2)] if m.group(2) else []) + lines[1:]
        inner = self.blocks(lines)
        label = f'<p class="callout-label">{CALLOUT_LABEL[kind]}</p>' if kind in CALLOUT_LABEL else ""
        role = ' role="note"' if kind != "quote" else ""
        return f'<div class="callout callout-{kind}"{role}>{label}{inner}</div>'

    def list_block(self, lines: list[str], i: int) -> tuple[int, str]:
        ordered = bool(re.match(r"^\d+\.", lines[i].strip()))
        items: list[list[str]] = []
        j = i
        while j < len(lines):
            ln = lines[j]
            m = re.match(r"^([-*]|\d+\.)\s+(.*)$", ln)
            if m and not ln.startswith(" "):
                items.append([m.group(2)])
            elif ln.startswith("  ") and items and ln.strip():
                items[-1].append(ln[3:] if ordered and ln.startswith("   ") else ln[2:])
            elif not ln.strip() and j + 1 < len(lines) and lines[j + 1].startswith("  ") and items:
                items[-1].append("")
            else:
                break
            j += 1
        tag = "ol" if ordered else "ul"
        lis = []
        for it in items:
            first, rest = it[0], it[1:]
            nested = [r for r in rest if r.strip()]
            self._note_text(first)
            body = self.inline(first)
            if nested:
                body += self.blocks(rest)
            lis.append(f"<li>{body}</li>")
        return j, f"<{tag}>\n" + "\n".join(lis) + f"\n</{tag}>"

    def directive(self, name: str, lines: list[str]) -> str:
        if name == "cards":
            cards = []
            for n, ln in enumerate([ln for ln in lines if ln.strip()]):
                m = re.match(r"^\s*[-*]\s+\[([^\]]+)\]\(([^)\s]+)\)\s*(.*)$", ln)
                if not m:
                    continue
                title, url, desc = m.groups()
                h = self.href(url) or "#"
                target = h[1:].split("--")[0] if h.startswith("#") else ""
                icon = self.pages.get(target, {}).get("icon") or ICON_CYCLE[n % len(ICON_CYCLE)]
                path = ICONS.get(icon, ICONS["book"])
                cards.append(
                    f'<a class="card" href="{html.escape(h)}"><span class="card-art" aria-hidden="true">'
                    f'<svg viewBox="0 0 24 24" width="56" height="56"><path d="{path}"/></svg></span>'
                    f'<span class="card-title">{self.inline(title)}</span><span class="card-desc">{self.inline(desc)}</span></a>')
            return f'<div class="cards">{"".join(cards)}</div>'
        if name == "steps":
            chunks: list[list[str]] = []
            for ln in lines:
                if re.match(r"^###\s+", ln.strip()):
                    chunks.append([ln.strip()[4:].strip()])
                elif chunks:
                    chunks[-1].append(ln)
            steps = []
            for c in chunks:
                hid = self.heading_id(c[0])
                self.headings.append((hid, c[0], ""))
                steps.append(f'<li><h3 id="{self.slug}--{hid}">{self.inline(c[0])}</h3>{self.blocks(c[1:])}</li>')
            return f'<ol class="steps">{"".join(steps)}</ol>'
        return self.blocks(lines)


# ---------------------------------------------------------------- site

def load_site(src: Path, args) -> tuple[dict, list[dict]]:
    cfg = {}
    if (src / "site.json").exists():
        cfg = json.loads((src / "site.json").read_text())
    files = {route_id(p.stem): p for p in sorted(src.glob("*.md")) + sorted(src.glob("*.mdx"))}
    if not files:
        raise SystemExit(f"docs_site: no .md pages in {src}")
    metas = {}
    for slug, p in files.items():
        meta, body = parse_frontmatter(p.read_text())
        if "title" not in meta:
            m = re.search(r"^#\s+(.+)$", body, re.M)
            meta["title"] = m.group(1).strip() if m else slug.replace("-", " ").capitalize()
        metas[slug] = {**meta, "_body": body, "_raw": p.read_text()}
    if cfg.get("nav"):
        nav = [{**g, "pages": [route_id(x) for x in g.get("pages", [])]} for g in cfg["nav"]]
        missing = [s for g in nav for s in g.get("pages", []) if s not in metas]
        if missing:
            raise SystemExit(f"docs_site: nav lists pages with no file in {src}: {', '.join(missing)}")
    else:
        groups: dict[str, list[tuple[float, str]]] = {}
        for slug, meta in metas.items():
            g = meta.get("group") or ("Get started" if slug == "index" else "Docs")
            order = -1 if slug == "index" else float(meta.get("order", 100))
            groups.setdefault(g, []).append((order, slug))
        first = ["Get started"] if "Get started" in groups else []
        nav = [{"group": g, "pages": [s for _, s in sorted(groups[g])]} for g in first + sorted(k for k in groups if k not in first)]
    cfg["title"] = args.title or cfg.get("title") or "Documentation"
    cfg["style"] = args.style or cfg.get("style") or "clean"
    if cfg["style"] not in STYLES:
        raise SystemExit(f"docs_site: style must be one of {', '.join(STYLES)}")
    cfg["accent"] = args.accent or cfg.get("accent")
    if cfg["accent"] and not re.match(r"^#[0-9a-fA-F]{6}$", cfg["accent"]):
        raise SystemExit("docs_site: accent must be a #rrggbb colour")
    order = [s for g in nav for s in g["pages"]]
    pages = []
    for g in nav:
        for slug in g["pages"]:
            pages.append({"slug": slug, "group": g["group"], **metas[slug]})
    # Pages not in the nav still build, so links to them work; they are just not listed.
    for slug in metas:
        if slug not in order:
            pages.append({"slug": slug, "group": "", **metas[slug]})
    cfg["nav"] = nav
    return cfg, pages


def esc(s: str) -> str:
    return html.escape(str(s))


def build(src: Path, out: Path, args) -> int:
    cfg, pages = load_site(src, args)
    by_slug = {p["slug"]: p for p in pages}
    listed = [s for g in cfg["nav"] for s in g["pages"]]
    articles, tocs, search, markdown = [], [], [], {}
    for p in pages:
        r = Renderer(p["slug"], by_slug)
        # The page title is rendered once; drop a leading "# Title" so it is not repeated.
        body_md = re.sub(r"^\s*#\s+.+\n?", "", p["_body"], count=1)
        body = r.render(body_md)
        landing = p.get("layout") == "landing"
        crumbs = "" if landing else (
            f'<nav class="crumbs" aria-label="Breadcrumb"><a href="#{esc(listed[0])}">{esc(cfg["title"])}</a>'
            + (f'<span aria-hidden="true">›</span><span>{esc(p["group"])}</span>' if p["group"] else "")
            + f'<span aria-hidden="true">›</span><span aria-current="page">{esc(p["title"])}</span></nav>')
        meta_row = ""
        if not landing:
            upd = f'<span class="updated">Updated {esc(p["updated"])}</span>' if p.get("updated") else "<span></span>"
            meta_row = (f'<div class="meta">{upd}<button type="button" class="btn copy-llm" data-slug="{esc(p["slug"])}">'
                        f'<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="M8 8h12v12H8z M16 8V4H4v12h4"/></svg>'
                        f"Copy for LLM</button></div>")
        lede = p.get("description") or (cfg.get("tagline") if landing else "")
        desc = f'<p class="lede">{esc(lede)}</p>' if lede else ""
        nav_links = ""
        if p["slug"] in listed:
            k = listed.index(p["slug"])
            prev_ = by_slug[listed[k - 1]] if k > 0 else None
            next_ = by_slug[listed[k + 1]] if k + 1 < len(listed) else None
            nav_links = '<nav class="pager" aria-label="Previous and next">' + (
                f'<a class="prev" href="#{esc(prev_["slug"])}"><small>Previous</small>{esc(prev_["title"])}</a>' if prev_ else "<span></span>") + (
                f'<a class="next" href="#{esc(next_["slug"])}"><small>Next</small>{esc(next_["title"])}</a>' if next_ else "<span></span>") + "</nav>"
        head = (f'<header class="hero"><h1>{esc(p["title"])}</h1>{desc}</header>' if landing
                else f'{crumbs}<h1>{esc(p["title"])}</h1>{desc}{meta_row}<hr class="rule">')
        articles.append(f'<article class="page{" landing" if landing else ""}" data-slug="{esc(p["slug"])}" hidden>'
                        f'{head}<div class="prose">{body}</div>{nav_links}</article>')
        toc_items = "".join(f'<li class="l{lvl}"><a href="#{esc(p["slug"])}--{hid}" data-target="{esc(p["slug"])}--{hid}">{r.inline(t)}</a></li>'
                            for lvl, t, hid in r.toc)
        tocs.append(f'<template data-toc-for="{esc(p["slug"])}">{toc_items}</template>')
        markdown[p["slug"]] = f"# {p['title']}\n\n" + body_md.strip() + "\n"
        search.append({"slug": p["slug"], "title": p["title"], "group": p["group"], "heading": "", "id": "",
                       "text": (p.get("description") or "")[:200]})
        for hid, h, text in r.headings:
            search.append({"slug": p["slug"], "title": p["title"], "group": p["group"], "heading": h, "id": hid, "text": text[:200]})

    sidebar = []
    for g in cfg["nav"]:
        links = "".join(f'<li><a href="#{esc(s)}" data-nav="{esc(s)}">{esc(by_slug[s]["title"])}</a></li>' for s in g["pages"])
        sidebar.append(f'<details class="group" open><summary>{esc(g["group"])}</summary><ul>{links}</ul></details>')
    top_links = "".join(f'<a href="{esc(Renderer("", by_slug).href(link["href"]) or "#")}">{esc(link["label"])}</a>' for link in cfg.get("links", []))
    data = json.dumps({"markdown": markdown, "search": search, "home": listed[0], "title": cfg["title"]}, ensure_ascii=False)
    data = data.replace("</", "<\\/").replace("<!--", "<\\!--")

    page = TEMPLATE
    accent_css = ""
    if cfg["accent"]:
        accent_css = f':root{{--accent:{cfg["accent"]};--accent-ink:{cfg["accent"]}}}'
    for k, v in {
        "{{TITLE}}": esc(cfg["title"]),
        "{{FONTS}}": FONTS[cfg["style"]],
        "{{STYLE_CSS}}": STYLE_CSS[cfg["style"]] + accent_css,
        "{{SIDEBAR}}": "".join(sidebar),
        "{{TOP_LINKS}}": top_links,
        "{{ARTICLES}}": "\n".join(articles),
        "{{TOCS}}": "".join(tocs),
        "{{DATA}}": data,
        "{{HOME}}": esc(listed[0]),
    }.items():
        page = page.replace(k, v)
    if getattr(args, "artifact", False):
        # The artifact host wraps the page in its own doctype, head and body.
        page = re.sub(r"^<!doctype html>\n<html[^>]*>\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\"[^>]*>\n", "", page)
        page = page.replace("</head>\n<body>\n", "").replace("</body>\n</html>\n", "")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    size = len(page.encode())
    print(f"docs_site: {len(pages)} pages -> {out} ({size // 1024} KB, style {cfg['style']})")
    if size > 16 * 1024 * 1024:
        print("docs_site: over the 16 MB artifact limit; move images out or split the site", file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------- template

FONTS = {
    "clean": '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap">',
    "warm": '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600&family=Geist+Mono:wght@400;500&display=swap">',
    "dark": '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap">',
}

_LIGHT_NEUTRAL = "--bg:#ffffff;--surface:#f6f7f8;--surface-2:#eef0f2;--text:#16181b;--muted:#5d636b;--border:#e3e6ea;--accent:#0e7c66;--accent-ink:#0b6a57;--note-bg:#eef4fb;--note-bd:#cfe0f3;--tip-bg:#ecf7f1;--tip-bd:#c8e8d6;--imp-bg:#fbf4dc;--imp-bd:#efe0a8;--warn-bg:#fdf0ee;--warn-bd:#f3cfc8;--grid:rgba(14,124,102,.10);"
_DARK_NEUTRAL = "--bg:#0d0f11;--surface:#15181b;--surface-2:#1c2024;--text:#e7eaee;--muted:#9aa2ab;--border:#262b31;--accent:#3ccf9e;--accent-ink:#5fe0b4;--note-bg:#14202c;--note-bd:#22384d;--tip-bg:#122219;--tip-bd:#1f3d2c;--imp-bg:#262012;--imp-bd:#4a3d1c;--warn-bg:#2a1715;--warn-bd:#4d2723;--grid:rgba(60,207,158,.10);"
_LIGHT_WARM = "--bg:#faf9f5;--surface:#f2f0e9;--surface-2:#ebe8de;--text:#1f1e1d;--muted:#5e5d59;--border:#e3dfd3;--accent:#b4532f;--accent-ink:#9a4426;--note-bg:#f0efe9;--note-bd:#dedbd0;--tip-bg:#edf3ea;--tip-bd:#d3e2cc;--imp-bg:#faf2d6;--imp-bd:#eadfae;--warn-bg:#f9ebe6;--warn-bd:#ecd0c6;--grid:rgba(180,83,47,.09);"
_DARK_WARM = "--bg:#1d1c1a;--surface:#262522;--surface-2:#2e2c29;--text:#ecebe6;--muted:#a8a69f;--border:#383631;--accent:#e08a66;--accent-ink:#eba183;--note-bg:#2a2926;--note-bd:#3d3b36;--tip-bg:#202a1f;--tip-bd:#33452f;--imp-bg:#2d2715;--imp-bd:#4f4422;--warn-bg:#301e19;--warn-bd:#523128;--grid:rgba(224,138,102,.10);"
_LIGHT_MINT = _LIGHT_NEUTRAL.replace("--accent:#0e7c66;--accent-ink:#0b6a57", "--accent:#16a34a;--accent-ink:#15803d").replace("rgba(14,124,102,.10)", "rgba(22,163,74,.10)")
_DARK_MINT = "--bg:#0a0d0b;--surface:#101512;--surface-2:#151c18;--text:#e6ece8;--muted:#95a19a;--border:#1d2621;--accent:#4ade80;--accent-ink:#6ee79b;--note-bg:#111b17;--note-bd:#1f3129;--tip-bg:#0f1f15;--tip-bd:#1d3a27;--imp-bg:#221f10;--imp-bd:#453d1b;--warn-bg:#261413;--warn-bd:#482522;--grid:rgba(74,222,128,.09);"


def _theme(light: str, dark: str, extra: str, dark_first: bool = False) -> str:
    light, dark = light + "color-scheme:light;", dark + "color-scheme:dark;"
    if dark_first:  # the mirror image: dark on bare :root, light only when the viewer or system asks
        return (f":root{{{dark}{extra}}}"
                f'@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{{light}}}}}'
                f':root[data-theme="light"]{{{light}}}')
    return (f":root{{{light}{extra}}}"
            f'@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{{dark}}}}}'
            f':root[data-theme="dark"]{{{dark}}}')


_SANS = "--font:'Geist',ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif;--mono:'Geist Mono',ui-monospace,SFMono-Regular,Menlo,monospace;"
STYLE_CSS = {
    "clean": _theme(_LIGHT_NEUTRAL, _DARK_NEUTRAL, _SANS + "--head:var(--font);--head-weight:700;--head-track:-0.02em;"),
    "warm": _theme(_LIGHT_WARM, _DARK_WARM, _SANS.replace("'Geist'", "'Source Sans 3'") + "--head:'Source Serif 4',Georgia,serif;--head-weight:600;--head-track:-0.01em;"),
    "dark": _theme(_LIGHT_MINT, _DARK_MINT, _SANS + "--head:var(--font);--head-weight:600;--head-track:-0.02em;", dark_first=True),
}

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{{FONTS}}
<style>
{{STYLE_CSS}}
*{box-sizing:border-box}
html{scroll-padding-top:84px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 var(--font);-webkit-font-smoothing:antialiased}
a{color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.skip{position:absolute;left:-999px;top:8px;background:var(--surface);padding:8px 12px;border-radius:8px;z-index:60}
.skip:focus{left:16px}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:41;background:var(--bg)}
.top{position:sticky;top:env(safe-area-inset-top,0px);z-index:40;height:64px;display:flex;align-items:center;gap:20px;padding:0 24px;background:var(--bg);border-bottom:1px solid var(--border)}
.brand{font:var(--head-weight) 21px/1 var(--head);letter-spacing:var(--head-track);text-decoration:none;display:flex;align-items:center;gap:10px;white-space:nowrap}
.brand-mark{width:22px;height:22px;border-radius:6px;background:var(--accent);flex:none}
.top-links{display:flex;gap:22px;margin-left:auto;font-size:14.5px}
.top-links a{text-decoration:none;color:var(--muted)}
.top-links a:hover{color:var(--text)}
.search-btn{display:flex;align-items:center;gap:10px;min-width:220px;height:38px;padding:0 10px 0 12px;border:1px solid var(--border);border-radius:10px;background:var(--surface);color:var(--muted);font:inherit;font-size:14px;cursor:pointer}
.search-btn kbd{margin-left:auto;font:500 12px var(--mono);color:var(--muted)}
.icon-btn{width:38px;height:38px;display:grid;place-items:center;border:1px solid var(--border);border-radius:10px;background:transparent;color:var(--text);cursor:pointer}
.menu-btn{display:none}
svg{fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.shell{display:grid;grid-template-columns:280px minmax(0,1fr) 240px;max-width:1480px;margin:0 auto}
.side{position:sticky;top:calc(64px + env(safe-area-inset-top,0px));height:calc(100dvh - 64px - env(safe-area-inset-top,0px));overflow:auto;padding:24px 16px 48px 24px;border-right:1px solid var(--border)}
.group{margin-bottom:18px}
.group summary{list-style:none;cursor:pointer;font-weight:600;font-size:14px;padding:6px 8px;display:flex;justify-content:space-between;align-items:center;border-radius:8px}
.group summary::-webkit-details-marker{display:none}
.group summary::after{content:"";width:7px;height:7px;border-right:1.5px solid var(--muted);border-bottom:1.5px solid var(--muted);transform:rotate(45deg);margin-right:4px;transition:transform .15s}
.group:not([open]) summary::after{transform:rotate(-45deg)}
.group ul{list-style:none;margin:4px 0 0;padding:0 0 0 10px;border-left:1px solid var(--border);margin-left:8px}
.group a{display:block;padding:7px 10px;font-size:14.5px;line-height:1.4;color:var(--muted);text-decoration:none;border-radius:8px}
.group a:hover{color:var(--text);background:var(--surface)}
.group a[aria-current="page"]{color:var(--accent-ink);font-weight:600;background:var(--surface)}
main{min-width:0;padding:40px 56px 96px}
.page{max-width:780px;margin:0 auto}
.page.landing{max-width:960px}
.crumbs{display:flex;flex-wrap:wrap;gap:10px;font-size:14px;color:var(--muted);margin-bottom:16px}
.crumbs a{text-decoration:none}
.crumbs a:hover{color:var(--text)}
.crumbs [aria-current]{color:var(--text)}
h1,h2,h3,h4{font-family:var(--head);font-weight:var(--head-weight);letter-spacing:var(--head-track);line-height:1.2;scroll-margin-top:84px}
.page>h1{font-size:clamp(30px,4.2vw,42px);margin:0 0 10px}
.lede{font-size:18px;color:var(--muted);margin:0 0 18px}
.meta{display:flex;justify-content:space-between;align-items:center;gap:12px;color:var(--muted);font-size:14px;margin:14px 0 0}
.btn{display:inline-flex;align-items:center;gap:8px;height:36px;padding:0 14px;border:1px solid var(--border);border-radius:10px;background:var(--bg);color:var(--text);font:600 14px var(--font);cursor:pointer}
.btn:hover{background:var(--surface)}
.rule{border:0;border-top:1px solid var(--border);margin:28px 0 30px}
.prose h2{font-size:28px;margin:52px 0 14px}
.prose h3{font-size:20px;margin:34px 0 10px}
.prose h4{font-size:17px;margin:26px 0 8px}
.prose p,.prose ul,.prose ol{margin:0 0 16px}
.prose li{margin:6px 0}
.prose a{color:var(--accent-ink);text-underline-offset:3px}
.anchor{float:left;margin-left:-26px;width:22px;color:var(--muted);text-decoration:none;opacity:0;transition:opacity .15s}
h2:hover .anchor,h3:hover .anchor,.anchor:focus-visible{opacity:1}
code{font:500 .88em var(--mono);background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:.1em .38em}
.code{position:relative;margin:0 0 18px}
pre{margin:0;overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 18px;font-size:14px;line-height:1.6}
pre code{background:none;border:0;padding:0;font-size:inherit}
.copy-code{position:absolute;top:8px;right:8px;height:28px;padding:0 10px;font:500 12px var(--font);color:var(--muted);background:var(--bg);border:1px solid var(--border);border-radius:8px;cursor:pointer;opacity:0;transition:opacity .15s}
.code:hover .copy-code,.copy-code:focus-visible{opacity:1}
.table{overflow-x:auto;margin:0 0 20px;border:1px solid var(--border);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:15px}
th,td{text-align:left;padding:10px 14px;border-bottom:1px solid var(--border);vertical-align:top}
th{background:var(--surface);font-weight:600}
td code{white-space:nowrap}
th+th,td+td{border-left:1px solid var(--border)}
tbody tr:last-child td{border-bottom:0}
.callout{border:1px solid var(--border);background:var(--surface);border-radius:12px;padding:16px 20px;margin:0 0 20px}
.callout>:last-child{margin-bottom:0}
.callout-label{font-weight:700;margin:0 0 4px}
.callout-note{background:var(--note-bg);border-color:var(--note-bd)}
.callout-tip{background:var(--tip-bg);border-color:var(--tip-bd)}
.callout-important{background:var(--imp-bg);border-color:var(--imp-bd)}
.callout-warning{background:var(--warn-bg);border-color:var(--warn-bd)}
.steps{list-style:none;counter-reset:step;padding:0;margin:0 0 20px}
.steps>li{counter-increment:step;position:relative;padding:0 0 8px 46px;margin:0}
.steps>li::before{content:counter(step);position:absolute;left:0;top:0;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:var(--surface-2);border:1px solid var(--border);font:600 14px var(--font)}
.steps>li::after{content:"";position:absolute;left:15px;top:36px;bottom:4px;width:1px;background:var(--border)}
.steps>li:last-child::after{display:none}
.steps h3{margin:2px 0 10px;font-size:18px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:24px;margin:8px 0 24px}
.card,.prose a.card{display:flex;flex-direction:column;gap:4px;text-decoration:none;color:var(--text)}
.card-art{display:grid;place-items:center;aspect-ratio:16/9;margin-bottom:12px;border:1px solid var(--border);border-radius:16px;color:var(--accent);background-color:var(--surface);background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);background-size:28px 28px;transition:border-color .15s,transform .15s}
.card-art svg{stroke-width:1.1;width:88px;height:88px}
.card:hover .card-art{border-color:var(--accent);transform:translateY(-2px)}
.card-title{font-weight:600;font-size:17px}
.card-desc{color:var(--muted);font-size:15px}
.landing .hero{text-align:center;padding:40px 0 36px}
.landing .hero h1{font-size:clamp(34px,5vw,52px);margin:0 0 12px}
.landing .lede{max-width:600px;margin:0 auto}
figure{margin:0 0 20px}
figure img,.prose img{max-width:100%;border-radius:12px;border:1px solid var(--border)}
figcaption{font-size:14px;color:var(--muted);margin-top:8px}
.pager{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:56px}
.pager a{display:flex;flex-direction:column;gap:2px;padding:14px 16px;border:1px solid var(--border);border-radius:12px;text-decoration:none;font-weight:600}
.pager a:hover{border-color:var(--accent)}
.pager small{font-weight:400;color:var(--muted);font-size:13px}
.pager .next{text-align:right}
.toc{position:sticky;top:calc(64px + env(safe-area-inset-top,0px));height:calc(100dvh - 64px - env(safe-area-inset-top,0px));overflow:auto;padding:40px 20px 40px 8px;font-size:13.5px}
.toc h2{font:600 14px var(--font);margin:0 0 12px;letter-spacing:0}
.toc ul{list-style:none;margin:0;padding:0;border-left:1px solid var(--border)}
.toc a{display:block;padding:5px 12px;margin-left:-1px;border-left:2px solid transparent;color:var(--muted);text-decoration:none;line-height:1.4}
.toc .l3 a{padding-left:24px}
.toc a:hover{color:var(--text)}
.toc a.on{color:var(--text);border-left-color:var(--text)}
dialog{margin-top:12dvh;width:min(640px,calc(100vw - 32px));max-height:min(560px,80dvh);padding:0;border:1px solid var(--border);border-radius:16px;background:var(--bg);color:var(--text);box-shadow:0 24px 64px rgba(0,0,0,.28)}
dialog::backdrop{background:rgba(0,0,0,.4)}
.search-head{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--border)}
.search-head input{flex:1;border:0;background:transparent;color:var(--text);font:inherit;font-size:17px}
.search-head input:focus-visible{outline:2px solid transparent}
.search-head:focus-within{box-shadow:inset 0 -2px 0 var(--accent)}
.results{list-style:none;margin:0;padding:8px;overflow:auto;max-height:440px}
.results a{display:block;padding:10px 12px;border-radius:10px;text-decoration:none}
.results a[aria-selected="true"],.results a:hover{background:var(--surface)}
.results small{display:block;color:var(--muted);font-size:13px}
.results .empty{padding:18px 12px;color:var(--muted)}
.toast{position:fixed;bottom:24px;left:50%;transform:translate(-50%,20px);opacity:0;background:var(--text);color:var(--bg);padding:10px 16px;border-radius:10px;font-size:14px;transition:opacity .2s,transform .2s;pointer-events:none;z-index:70}
.toast.show{opacity:1;transform:translate(-50%,0)}
@media (max-width:1180px){.shell{grid-template-columns:260px minmax(0,1fr)}.toc{display:none}main{padding:36px 40px 80px}}
@media (max-width:860px){
  .shell{display:block}.menu-btn{display:grid}.top{padding:0 16px;gap:10px}.top-links{display:none}
  .search-btn{min-width:0;width:38px;padding:0;justify-content:center;margin-left:auto}.search-btn span,.search-btn kbd{display:none}
  .side{position:fixed;inset:calc(64px + env(safe-area-inset-top,0px)) 0 0 0;z-index:30;background:var(--bg);transform:translateX(-100%);transition:transform .2s;border-right:0;height:auto}
  .side.open{transform:none}
  main{padding:24px 16px 72px}.anchor{display:none}.pager{grid-template-columns:1fr}
  .meta{flex-wrap:wrap}
}
@media (prefers-reduced-motion:reduce){*{transition-duration:0s!important;scroll-behavior:auto!important}}
</style>
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="top">
  <button type="button" class="icon-btn menu-btn" aria-label="Menu" aria-expanded="false" aria-controls="side">
    <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M4 7h16 M4 12h16 M4 17h16"/></svg></button>
  <a class="brand" href="#{{HOME}}"><span class="brand-mark" aria-hidden="true"></span>{{TITLE}}</a>
  <nav class="top-links" aria-label="Site">{{TOP_LINKS}}</nav>
  <button type="button" class="search-btn" aria-label="Search the docs">
    <svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4"/></svg>
    <span>Search</span><kbd>⌘K</kbd></button>
  <button type="button" class="icon-btn theme-btn" aria-label="Switch light or dark theme">
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 3a9 9 0 1 0 9 9 7 7 0 0 1-9-9z"/></svg></button>
</header>
<div class="shell">
  <aside class="side" id="side" aria-label="Documentation"><nav>{{SIDEBAR}}</nav></aside>
  <main id="content" tabindex="-1">{{ARTICLES}}</main>
  <aside class="toc" aria-label="On this page"><h2>On this page</h2><ul id="toc"></ul></aside>
</div>
{{TOCS}}
<dialog id="search" aria-label="Search">
  <div class="search-head">
    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4"/></svg>
    <label for="q" class="skip">Search</label>
    <input id="q" type="search" autocomplete="off" spellcheck="false" placeholder="Search the docs" aria-controls="results">
  </div>
  <ul class="results" id="results" role="listbox"></ul>
</dialog>
<div class="toast" role="status" aria-live="polite"></div>
<script type="application/json" id="docs-data">{{DATA}}</script>
<script>
(() => {
  const D = JSON.parse(document.getElementById("docs-data").textContent);
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const pages = new Map($$("article.page").map(a => [a.dataset.slug, a]));
  const toc = $("#toc"), side = $("#side"), menu = $(".menu-btn");
  let spy;
  const toast = msg => { const t = $(".toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 1600); };

  function route() {
    const raw = decodeURIComponent(location.hash.slice(1));
    const slug = pages.has(raw) ? raw : raw.split("--")[0], anchor = raw !== slug ? raw.slice(slug.length + 2) : "";
    const page = pages.get(slug) || pages.get(D.home);
    const s = page.dataset.slug;
    pages.forEach(a => a.hidden = a !== page);
    $$("[data-nav]").forEach(a => a.dataset.nav === s ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
    const cur = $(`[data-nav="${CSS.escape(s)}"]`); if (cur) { cur.closest("details").open = true; }
    const h1 = $("h1", page); document.title = page.classList.contains("landing") ? D.title : `${h1.textContent} · ${D.title}`;
    const tpl = $(`template[data-toc-for="${CSS.escape(s)}"]`);
    toc.replaceChildren(tpl ? tpl.content.cloneNode(true) : "");
    toc.parentElement.style.visibility = toc.children.length ? "visible" : "hidden";
    side.classList.remove("open"); menu.setAttribute("aria-expanded", "false");
    watch(page);
    if (anchor) { const el = document.getElementById(`${s}--${anchor}`); if (el) { el.scrollIntoView(); return; } }
    window.scrollTo(0, 0);
  }

  function watch(page) {
    if (spy) spy.disconnect();
    const links = new Map($$("a[data-target]", toc).map(a => [a.dataset.target, a]));
    if (!links.size || !("IntersectionObserver" in window)) return;
    const seen = new Set();
    spy = new IntersectionObserver(es => {
      es.forEach(e => e.isIntersecting ? seen.add(e.target.id) : seen.delete(e.target.id));
      const first = $$("h2[id],h3[id]", page).find(h => seen.has(h.id));
      if (first) links.forEach((a, id) => a.classList.toggle("on", id === first.id));
    }, { rootMargin: "-72px 0px -65% 0px" });
    $$("h2[id],h3[id]", page).forEach(h => links.has(h.id) && spy.observe(h));
  }

  async function copy(text, msg) {
    try { await navigator.clipboard.writeText(text); toast(msg); }
    catch { const t = document.createElement("textarea"); t.value = text; document.body.append(t); t.select();
      try { document.execCommand("copy"); toast(msg); } catch { toast("Copy failed"); } t.remove(); }
  }
  document.addEventListener("click", e => {
    const b = e.target.closest(".copy-llm, .copy-code");
    if (!b) return;
    if (b.classList.contains("copy-llm")) copy(D.markdown[b.dataset.slug] || "", "Page copied as Markdown");
    else copy(b.parentElement.querySelector("code").textContent, "Code copied");
  });

  menu.addEventListener("click", () => { const o = side.classList.toggle("open"); menu.setAttribute("aria-expanded", String(o)); });

  const root = document.documentElement, KEY = "docs-theme:" + D.title;
  try { const t = localStorage.getItem(KEY); if (t) root.dataset.theme = t; } catch {}
  $(".theme-btn").addEventListener("click", () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem(KEY, root.dataset.theme); } catch {}
  });

  const dlg = $("#search"), q = $("#q"), list = $("#results");
  let hits = [], sel = 0;
  const openSearch = () => { if (dlg.open) return; dlg.showModal(); q.value = ""; render(); q.focus(); };
  $(".search-btn").addEventListener("click", openSearch);
  document.addEventListener("keydown", e => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); openSearch(); }
    else if (e.key === "/" && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); openSearch(); }
  });
  dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });
  function score(entry, terms) {
    const t = (entry.title + " " + entry.heading).toLowerCase(), b = entry.text.toLowerCase();
    let s = 0;
    for (const w of terms) { if (t.includes(w)) s += 3; else if (b.includes(w)) s += 1; else return 0; }
    return s + (entry.heading ? 0 : 1);
  }
  function render() {
    const terms = q.value.toLowerCase().split(/\s+/).filter(Boolean);
    hits = terms.length ? D.search.map(e => [score(e, terms), e]).filter(x => x[0]).sort((a, b) => b[0] - a[0]).slice(0, 12).map(x => x[1])
                        : D.search.filter(e => !e.heading).slice(0, 12);
    sel = 0;
    list.replaceChildren(...(hits.length ? hits.map((h, i) => {
      const li = document.createElement("li"), a = document.createElement("a"), sm = document.createElement("small");
      a.href = `#${h.slug}${h.id ? "--" + h.id : ""}`; a.setAttribute("role", "option"); a.setAttribute("aria-selected", String(i === 0));
      a.append(h.heading || h.title); sm.textContent = [h.group, h.heading ? h.title : ""].filter(Boolean).join(" › ") || h.text;
      a.append(sm); a.addEventListener("click", () => dlg.close()); li.append(a); return li;
    }) : [Object.assign(document.createElement("li"), { className: "empty", textContent: "No matches. Try fewer words." })]));
  }
  q.addEventListener("input", render);
  q.addEventListener("keydown", e => {
    const as = $$("a", list);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (!as.length) return;
      sel = (sel + (e.key === "ArrowDown" ? 1 : -1) + as.length) % as.length;
      as.forEach((a, i) => a.setAttribute("aria-selected", String(i === sel))); as[sel].scrollIntoView({ block: "nearest" }); }
    else if (e.key === "Enter" && as[sel]) { e.preventDefault(); location.hash = as[sel].getAttribute("href"); dlg.close(); }
  });

  window.addEventListener("hashchange", route);
  route();
})();
</script>
</body>
</html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build a one-file documentation site from a folder of markdown pages.")
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--style", choices=STYLES)
    ap.add_argument("--title")
    ap.add_argument("--accent")
    ap.add_argument("--artifact", action="store_true", help="emit the page body only, for an artifact host that adds its own skeleton")
    a = ap.parse_args(argv)
    if not a.src.is_dir():
        print(f"docs_site: {a.src} is not a folder", file=sys.stderr)
        return 1
    try:
        return build(a.src, a.out, a)
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    sys.exit(main())

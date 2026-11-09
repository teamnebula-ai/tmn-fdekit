#!/usr/bin/env python3
"""Static UI checks: accessibility footguns and the common AI design tells.

    ui_lint.py <file> [file ...]      # .html .css .scss .jsx .tsx .vue .svelte

ERROR = an accessibility or behaviour bug (exit 1).
WARN  = a design tell. Fine when the brief asks for it; otherwise reconsider.
Add `ui-lint:allow` on a line to vet a one-off exception.
This is a cheap first pass; it does not replace looking at the page in a
browser or running axe.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RULES = [
    ("ERROR", "outline-none", r"outline\s*:\s*(?:none|0)\b(?![^}]*focus-visible)", "focus outline removed; add a :focus-visible style"),
    ("ERROR", "no-zoom", r"user-scalable\s*=\s*no|maximum-scale\s*=\s*1(?:\.0)?\b", "blocks pinch zoom"),
    ("ERROR", "div-click", r"<(?:div|span)\b[^>]*\bonClick\s*=", "clickable div/span; use <button> or <a>"),
    ("ERROR", "img-alt", r"<img\b(?![^>]*\balt\s*=)[^>]*>", "image without alt text"),
    ("ERROR", "paste-block", r"onPaste\s*=\s*\{?[^}]*preventDefault", "blocks paste"),
    ("ERROR", "transition-all", r"transition(?:-property)?\s*:\s*all\b|\btransition-all\b", "animate transform/opacity only"),
    ("ERROR", "placeholder-label", r"<input\b(?![^>]*\baria-label)(?![^>]*\bid\s*=)[^>]*\bplaceholder\s*=", "input with a placeholder but no label or id"),
    ("WARN", "gradient-text", r"background-clip\s*:\s*text|\bbg-clip-text\b", "gradient text"),
    ("WARN", "ai-gradient", r"\bfrom-(?:purple|violet|indigo|fuchsia)-\d+|linear-gradient\([^)]*(?:#(?:8b5cf6|7c3aed|a855f7|6366f1)|purple|violet)", "purple/violet gradient"),
    ("WARN", "glass", r"\bbackdrop-blur(?:-\w+)?\b|backdrop-filter\s*:\s*blur", "blur as decoration"),
    ("WARN", "side-stripe", r"\bborder-[lr]-[4-8]\b|border-(?:left|right)\s*:\s*[3-9]px\s+solid", "thick one-side card border"),
    ("WARN", "z-index", r"\bz-\[\d{3,}\]|z-index\s*:\s*\d{4,}", "z-index outside a scale"),
    ("WARN", "h-screen", r"\bh-screen\b|height\s*:\s*100vh", "use min-h-[100dvh] / 100dvh"),
    ("WARN", "eyebrow", r"\buppercase\b[^\"'\n]*\btracking-(?:wide|wider|widest)\b|text-transform\s*:\s*uppercase[^}]*letter-spacing", "tracked all-caps eyebrow label"),
    ("WARN", "pulse", r"\banimate-pulse\b(?![^\n]*[Ss]keleton)", "pulsing element outside a skeleton"),
    ("WARN", "placeholder-data", r"\b(?:John|Jane) Doe\b|\bAcme\b|\blorem ipsum\b|99\.99%", "placeholder data"),
    ("WARN", "filler-copy", r">\s*(?:Welcome to|Unlock|Elevate|Supercharge|Seamless(?:ly)?|Powered by AI)\b", "filler marketing copy"),
    ("WARN", "emoji-icon", "[\U0001F300-\U0001FAFF☀-➿]", "emoji used as an icon or decoration"),
]
EXT = {".html", ".htm", ".css", ".scss", ".sass", ".less", ".jsx", ".tsx", ".js", ".ts", ".vue", ".svelte", ".astro"}


def lint_file(path: Path) -> list[tuple[str, str, int, str]]:
    out = []
    text = path.read_text(errors="ignore")
    lines = text.splitlines()
    for sev, rule, pat, msg in RULES:
        for m in re.finditer(pat, text, re.I if rule not in ("emoji-icon",) else 0):
            ln = text.count("\n", 0, m.start()) + 1
            if "ui-lint:allow" in (lines[ln - 1] if ln - 1 < len(lines) else ""):
                continue
            out.append((sev, rule, ln, msg))
    anim = re.search(r"@keyframes|animation\s*:|\banimate-\w+|transition\s*:", text)
    if anim and path.suffix in {".css", ".scss", ".html", ".vue", ".svelte"} and "prefers-reduced-motion" not in text:
        out.append(("WARN", "reduced-motion", text.count("\n", 0, anim.start()) + 1, "animation without a prefers-reduced-motion rule in this file"))
    return out


def main() -> int:
    files = [Path(f) for f in sys.argv[1:] if Path(f).suffix in EXT and Path(f).is_file()]
    if not files:
        print(__doc__.strip().splitlines()[2])
        return 0 if len(sys.argv) > 1 else 2
    errors = 0
    for f in files:
        for sev, rule, ln, msg in lint_file(f):
            errors += sev == "ERROR"
            print(f"{sev:5} {f}:{ln}  {rule}: {msg}")
    print(f"UI LINT {'FAIL' if errors else 'PASS'}  ({errors} errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

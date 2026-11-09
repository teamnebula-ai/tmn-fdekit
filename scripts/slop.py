#!/usr/bin/env python3
"""Lint human-facing text for AI slop before it is sent.

    slop.py [--target slack|pr|review|commit|ticket|doc] [--voice sample.txt] [FILE|-]

Prints `line rule [severity] match` per finding and a verdict. Exits 1 when
there is any STRONG finding (one sighting is enough to rewrite), or when
medium findings pile up past the density limit. Code blocks, inline code,
URLs and quoted lines are ignored, so quoting someone is never flagged.

A voice sample (the author's own hand-written messages) relaxes the dash and
emoji rules to the author's own habits. The script finds tells; whether a
sentence earns its place is still a judgement call for the writer.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

I = re.I | re.M
STRONG = [
    ("chatbot-residue", r"\b(?:i hope this helps|certainly!|of course!|great question|you'?re absolutely right|happy to help|would you like me to|is there anything else|feel free to reach out)\b"),
    ("knowledge-hedge", r"\b(?:as of my (?:last|latest) (?:update|knowledge)|based on (?:the )?available information|while (?:specific )?details are (?:limited|scarce))\b"),
    ("leaked-artifact", r"contentReference\[oaicite:\d+\]|oai_citation|utm_source=(?:chatgpt|openai|copilot|perplexity)"),
    ("not-x-but-y", r"\bnot (?:just|only|merely) [^.;\n]{1,60}?,? but (?:also )?\w|\b(?:it'?s|this is|that'?s) not [^.\n]{1,60}[.;,] (?:it'?s|this is)\b|\bisn'?t (?:about|just) [^.\n]{1,60}\. it'?s\b"),
    ("staged-opener", r"^\s*(?:here'?s (?:the thing|what you need|why this matters)|let'?s (?:dive|break (?:it|this) down|explore|unpack)|quick note|honestly\?|real talk|the truth is|without further ado|make no mistake)"),
    ("closer", r"^\s*(?:that'?s (?:the|what) [^.\n]{0,30}\.|let that sink in\.?|read that again\.?|full stop\.?)\s*$"),
    ("agent-signoff", r"^\s*(?:agent note|— ?claude\b|generated (?:by|with) (?:claude|ai|chatgpt))"),
    ("placeholder", r"\[(?:insert|your|name|date|link)[^\]]*\]|<TODO>|\blorem ipsum\b|\b(?:jane|john) doe\b"),
]
STRONG_PUBLISHED = [
    ("first-person-fault", r"\b(?:i|i'?ve|my) (?:missed|broke|forgot|messed up)\b|\bit'?s my fault\b|\bmy (?:mistake|bad)\b"),
]
MEDIUM = [
    ("ai-vocab", r"\b(?:delve|tapestry|testament|pivotal|intricate|meticulous(?:ly)?|vibrant|underscore[sd]?|showcas(?:e|es|ing)|fostering|garner|interplay|multifaceted|leverag(?:e|es|ing)|bolster(?:ed)?|seamless(?:ly)?|robust|elevate|unlock|empower|streamline|supercharge|game.?chang(?:er|ing)|cutting.edge|world.class|next.gen)\b"),
    ("inflation", r"\b(?:stands as a|serves as a|is a testament|plays? a (?:key|pivotal|crucial|vital) role|setting the stage|evolving landscape|the future looks bright)\b"),
    ("ing-rider", r", (?:highlighting|underscoring|emphasizing|ensuring|reflecting|symbolizing|fostering|showcasing|contributing to)\b"),
    ("jargon", r"\b(?:circle back|double down|lean into|deep dive|moving forward|on the same page|navigate (?:the )?(?:challenges?|complexit\w+))\b"),
    ("summary-transition", r"^\s*(?:in summary|in conclusion|overall,|to summari[sz]e|with (?:this|that) in place|now that we'?ve)"),
    ("hedge-stack", r"\b(?:could|might|may|potentially|possibly|arguably|perhaps)\b(?:\W+\w+){0,4}?\W+(?:could|might|may|potentially|possibly|arguably|perhaps)\b"),
    ("bold-label-list", r"(?:^\s*[-*] \*\*[^*\n]+:\*\*.*\n){3,}"),
]
WEAK = [
    ("filler", r"\b(?:just|really|very|simply|actually|basically|literally|genuinely|it'?s worth noting|at the end of the day|when it comes to|in today'?s)\b"),
]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F2FF]")
DASH = re.compile(r"—|–| -- ")
REF = re.compile(r"#\d+|\b[A-Z][A-Z0-9]+-\d+\b|\b[0-9a-f]{7,40}\b")
HASH = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")
PROOF = re.compile(r"\b(?:i (?:checked|ran|verified|confirmed|tested)|exit code \d|\d+/\d+ (?:tests|passed))\b", re.I)
PUBLISHED = {"pr", "review", "commit", "ticket", "doc", "slack"}


def clean(text: str) -> str:
    text = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "``", text)
    text = re.sub(r"https?://\S+", "URL", text)
    text = re.sub(r"^\s*>.*$", "", text, flags=re.M)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return text


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def lint(text: str, target: str = "slack", voice: str | None = None, leader_close: bool = True) -> list[tuple[int, str, str, str]]:
    raw = text
    text = clean(text)
    out: list[tuple[int, str, str, str]] = []

    def scan(rules, sev):
        for name, pat in rules:
            for m in re.finditer(pat, text, I):
                out.append((line_of(text, m.start()), name, sev, m.group(0).strip()[:60]))

    scan(STRONG, "strong")
    if target in PUBLISHED:
        scan(STRONG_PUBLISHED, "strong")
    scan(MEDIUM, "medium")
    scan(WEAK, "weak")

    # "let me know if ..." is chatbot residue, except once as the closing line of a human message
    lmk = list(re.finditer(r"\blet me know if\b", text, I))
    parts = [x for x in re.split(r"(?<=[.!?])\s+|\n{2,}|\n(?=\s*[-*\d])", text.strip()) if x.strip()]
    last_line = parts[-1] if parts else ""
    for m in lmk:
        if not (leader_close and len(lmk) == 1 and re.search(r"\blet me know if\b", last_line, re.I)):
            out.append((line_of(text, m.start()), "chatbot-residue", "strong", m.group(0)))

    words = max(1, len(re.findall(r"\w+", text)))
    vtext = voice or ""
    vwords = max(1, len(re.findall(r"\w+", vtext)))
    dashes = DASH.findall(text)
    if dashes:
        allowed = len(DASH.findall(vtext)) / vwords * words * 1.5 if voice else (0 if target in ("slack", "commit") else words / 150)
        if len(dashes) > allowed:
            out.append((0, "em-dash", "medium", f"{len(dashes)} dashes; use a period, comma or colon"))
    emojis = EMOJI.findall(text)
    if emojis and not (voice and EMOJI.search(vtext)):
        lead = [l for l in text.splitlines() if EMOJI.match(l.strip().lstrip("-*#> ").strip() or " ")]
        if lead or len(emojis) >= 3:
            out.append((0, "emoji", "medium", f"{len(emojis)} emoji used as decoration"))
    if re.search(r"→|⟶|➜", text):
        out.append((0, "arrows", "weak", "arrows in prose"))

    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if len(re.findall(r"\w+", s)) >= 3]
    lens = [len(re.findall(r"\w+", s)) for s in sentences]
    if lens and max(lens) > 35:
        out.append((0, "long-sentence", "weak", f"a sentence of {max(lens)} words; split it"))
    if target == "slack":
        if len(sentences) > 5:
            out.append((0, "too-long", "medium", f"{len(sentences)} sentences; Slack caps at 5, link a doc for more"))
        if HASH.search(text):
            out.append((0, "ref-soup", "medium", "commit hash in a Slack message"))
        if PROOF.search(raw):
            out.append((0, "proof-of-work", "medium", "narrates verification steps; state the result"))
        if re.fullmatch(r"\s*(?:hi|hey|hello)(?: \w+)?[!.]?\s*", text, re.I):
            out.append((1, "lone-greeting", "strong", "say the whole thing in one message"))
    if target == "commit":
        subject = raw.strip().splitlines()[0] if raw.strip() else ""
        if len(subject) > 72:
            out.append((1, "subject-length", "medium", f"subject is {len(subject)} chars (max 72)"))
    for s in sentences:
        if len(REF.findall(s)) >= 3:
            out.append((0, "ref-soup", "medium", "three or more ids/hashes in one sentence"))
            break
    filler = sum(1 for f in out if f[1] == "filler")
    if filler and filler * 100 / words < 3:
        out = [f for f in out if f[1] != "filler"]
    vocab = sum(1 for f in out if f[1] == "ai-vocab")
    if vocab and not (vocab * 200 / words >= 3 or (target == "slack" and words < 60)):
        out = [(l, r, "weak" if r == "ai-vocab" else s, m) for l, r, s, m in out]
    return sorted(out)


def verdict(findings) -> bool:
    strong = sum(1 for f in findings if f[2] == "strong")
    medium = sum(1 for f in findings if f[2] == "medium")
    return strong == 0 and medium < 3


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default="-")
    ap.add_argument("--target", default="slack", choices=["slack", "pr", "review", "commit", "ticket", "doc", "chat"])
    ap.add_argument("--voice", help="file of the author's own messages")
    a = ap.parse_args()
    text = sys.stdin.read() if a.file == "-" else Path(a.file).read_text()
    voice = Path(a.voice).read_text() if a.voice else None
    findings = lint(text, a.target, voice)
    for line, rule, sev, match in findings:
        print(f"{line or '-':>3}  {rule:18} [{sev}]  {match}")
    ok = verdict(findings)
    print("SLOP " + ("PASS" if ok else "FAIL") + f"  ({sum(f[2]=='strong' for f in findings)} strong, {sum(f[2]=='medium' for f in findings)} medium)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

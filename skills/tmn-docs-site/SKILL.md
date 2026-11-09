---
name: tmn-docs-site
description: (tmn) Build a docs site as one self-contained HTML page and publish it as an artifact or hand over the file - sidebar nav, breadcrumbs, "On this page", Cmd+K search, Copy for LLM, callouts, steps, card grids, light and dark, in clean, warm or dark styles. Use whenever someone asks for docs, a guide, a handbook, a runbook, API or CLI reference, onboarding notes, a knowledge base or help center, "make this look like Mintlify", "a docs site", or wants existing markdown turned into something people can browse and share.
---

# Docs site

A docs page earns trust when it looks like a real docs site and every word in
it is true. The builder handles the first part. Your job is the second part:
the content, the structure and the check.

> Checkpoints follow the run mode in `tmn-staff-bar`: standard stops and asks before each push, post, message or hand-off to the next skill; yolo runs through. The hard lines hold in both. Team rules from `config.py rules tmn-docs-site` override anything else in this skill.

The builder is `scripts/docs_site.py`. It takes a folder of markdown pages and
writes one HTML file with no outside dependencies except Google Fonts. Never
hand-write the HTML. If the layout is missing something, add it to the
builder with a test.

## 1. Read the real thing first

Docs describe something that exists. Before writing a page:

- Read the source: the code, the README, the CLI's `--help`, the config
  schema, the API routes.
- Run every command you will show, or copy it from a file that runs it in
  CI. A command in the docs that fails is worse than no docs at all.
- If something is unclear, ask, or leave a visible "To confirm:" note. Never
  invent a flag, a default, a limit or a price.

## 2. Plan the pages

Write the plan out before writing pages:

- **Who reads it and what they came to do.** One sentence each.
- **Groups, in reading order.** Usually *Get started* (overview, quickstart),
  *Guides* (one task per page), *Reference* (config, commands, API) and
  *Help* (troubleshooting, changelog). Skip any group with nothing in it.
- **One job per page.** Name pages by the task ("Rotate an API key"), not
  the feature ("Key management"). Four to twelve pages is the usual size.
  Thirty pages means you need two sites.
- **A landing page** (`index.md`, `layout: landing`) with a card per
  starting point. Three to six cards.

## 3. Write the pages

Make a working folder (the scratchpad, or `docs-site/` in the repo if the
docs belong there). Add one `.md` file per page and a `site.json`. The syntax
is in [references/syntax.md](references/syntax.md); read it before the first
page. In short:

```markdown
---
title: Quickstart
description: Install the CLI and sync your first folder.
icon: rocket
updated: 2026-11-07
---

## Install

:::steps
### Get the binary
...
:::

> [!IMPORTANT]
> One sentence on the thing that breaks people.
```

How each page reads:

- **The first paragraph says what the page gets the reader.** No history,
  no "In this guide we will".
- **Headings are tasks or questions,** in sentence case. Every `##` shows up
  in "On this page", so keep them short.
- **Show, then explain.** A command block or a table beats a paragraph.
  Use a table whenever you compare three or more things.
- **Callouts are rare.** At most two per page. Use `IMPORTANT` for "this
  breaks if you skip it" and `WARNING` for "this loses data". A grey `>`
  box is for plan and availability notes.
- **Set `updated`** only to the date you checked the content against the
  source.
- Follow the `tmn-write` skill for wording: plain words, short sentences, no
  filler.

## 4. Build

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/docs_site.py <folder> -o <name>.html --style clean
```

| Style | Looks like | Use for |
|---|---|---|
| `clean` (default) | white, neutral greys, teal accent | product and engineering docs |
| `warm` | off-white paper, serif headings | help centres, handbooks, policy |
| `dark` | near-black, green accent, grid card art | developer tools, CLIs, APIs |

`--accent '#hex'` sets a brand colour. A brand file or design system the
user gives you wins over all three styles. The builder exits 1, and writes
nothing, when the nav names a page that has no file. Fix the nav; don't
work around it.

## 5. Check it like a reader

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ui_lint.py <name>.html` must report 0 errors.
2. Open it in a browser and look at three things. First, the landing page and
   one long page at desktop width, in both themes. Second, the same pages at
   390 px wide with the menu open. Third, search for a word that's only in a
   body paragraph, and check that the result opens the right section.
3. Click every sidebar link and every card. Use "Copy for LLM" once and
   paste the result. It should be the page's markdown.

## 6. Publish

- **Claude Code or Claude.ai with artifacts:** build again with `--artifact`
  (the host adds its own page skeleton), then publish that file as an
  artifact. It's private until the owner shares it. To change it later,
  edit the markdown, rebuild to the same path, and republish to the same
  URL. Never edit the built HTML by hand.
- **Anywhere else:** hand over the HTML file. It works opened from disk,
  on any static host, or attached to a ticket.
- **Docs that belong in a repo:** commit the markdown folder, not the
  HTML, and add a `make docs` target that runs the builder.

Before you publish, check that no secrets, internal hostnames, customer
names or personal data are in the pages. The artifact is a copy someone can
forward.

## Done means

- Every page came from the real source, and every command shown was run.
- The UI lint reports 0 errors, and the page was checked at desktop and
  phone widths in both themes.
- The reader gets one link (or one file) and a sentence saying what's in it.

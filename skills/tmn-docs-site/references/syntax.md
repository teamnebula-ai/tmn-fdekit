# docs_site.py syntax

Read this before writing the first page. A worked example lives in
`assets/example/`. Build it with
`python3 scripts/docs_site.py skills/tmn-docs-site/assets/example -o lark.html`.

## Folder

```
my-docs/
├── site.json        # optional; without it the nav comes from frontmatter
├── index.md         # the home page; `layout: landing` gives the hero and cards
├── quickstart.md
└── config.md
```

The file name, without `.md`, is the page's slug and route (`#quickstart`; a section is `#quickstart--install`). Routes
are plain `#name` hashes because that's all an artifact link keeps.

## site.json

```json
{
  "title": "Lark Docs",
  "tagline": "One line under the title on the landing page.",
  "style": "clean",
  "accent": "#0e7c66",
  "links": [{ "label": "Changelog", "href": "changelog.md" }],
  "nav": [
    { "group": "Get started", "pages": ["index", "quickstart"] },
    { "group": "Reference", "pages": ["config", "changelog"] }
  ]
}
```

- `nav` sets the sidebar order and the previous and next links. Every slug in
  it must have a file, or the build fails.
- Pages left out of `nav` still build, so links to them work, but they
  aren't listed in the sidebar.
- `links` appear top right on desktop. A link to a page `.md` becomes an
  in-page route.
- `--title`, `--style` and `--accent` on the command line override the file.
- `--artifact` leaves out the doctype, head and body tags, for an artifact
  host that adds its own. Leave it off for a file people open directly.

## Frontmatter

| Field | Use |
|---|---|
| `title` | page title; falls back to the first `# Heading`, then the file name |
| `description` | the line under the title; also used by search |
| `updated` | shown as "Updated …"; only the date you last checked it against the source |
| `icon` | card art when another page links here from `:::cards`: `book`, `terminal`, `rocket`, `cube`, `shield`, `chart`, `code`, `plug`, `pen`, `search`, `layers`, `check` |
| `layout` | `landing` for a centred hero with no breadcrumbs or Copy for LLM |
| `group`, `order` | used only when there is no `site.json` |

## Markdown

| Write | Get |
|---|---|
| `## Heading`, `### Sub` | section with an anchor link, listed in "On this page" (h4 isn't listed) |
| `**bold**`, `*italic*`, `` `code` `` | inline styles |
| `[text](other.md#anchor)` | an in-page route to that page and section |
| `[text](https://…)` | an external link that opens in a new tab; `javascript:` and `data:` links are dropped |
| `![alt](url)` on its own line | an image with a caption from the alt text |
| ```` ```bash ```` | a code block with a Copy button |
| `\| a \| b \|` plus a `---` row | a bordered table that scrolls on phones |
| `- item`, `1. item`, two-space indent to nest | lists |
| `> text` | a grey box, for availability or plan notes |
| `> [!NOTE]` / `[!TIP]` / `[!IMPORTANT]` / `[!WARNING]` | a coloured callout with a label |
| `---` | a divider |

Raw HTML is shown as text, never run. That's deliberate: pages are often
built from text you didn't write.

## Blocks

Steps: each `###` inside the block is a numbered step.

```markdown
:::steps
### Install
```bash
brew install lark
```

### Connect
Run `lark init`.
:::
```

Cards: a grid of linked cards with grid-paper art. The icon comes from the
linked page's `icon` field.

```markdown
:::cards
- [Quickstart](quickstart.md) Install and sync in two minutes.
- [Config file](config.md) Every setting, with defaults.
:::
```

## What the page does on its own

- A sidebar with collapsible groups, the current page highlighted, and a
  drawer on phones.
- Breadcrumbs (site, group, page) and previous and next links.
- "On this page", which highlights the section you're reading.
- Cmd+K, Ctrl+K or `/` search over titles, headings and body text, with
  arrow keys and Enter.
- "Copy for LLM", which copies the page's markdown.
- A light and dark toggle, remembered per site, that follows the system
  until it's used.

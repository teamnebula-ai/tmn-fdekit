---
title: Quickstart
description: Install Lark and sync your first folder.
icon: rocket
updated: 2026-11-07
---

Lark keeps a folder of notes in sync with a git remote. You run one command,
and it commits and pushes every change.

> Lark needs `git` 2.40 or newer. Run `git --version` to check.

## Install

:::steps
### Get the binary
```bash
brew install lark
```

### Point it at a folder
```bash
lark init ~/notes --remote git@example.com:me/notes.git
```
:::

## Check that it works

| Command | What it shows |
|---|---|
| `lark status` | the last sync and anything waiting |
| `lark log` | the last 20 syncs |

> [!IMPORTANT]
> Lark pushes **everything** in the folder. Add a `.gitignore` before the first sync if some files must stay local.

Next, read the [config file](config.md#sync) reference.

<script>alert("not html")</script>

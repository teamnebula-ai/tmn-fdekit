---
title: Config file
description: Every setting in lark.toml.
icon: code
---

## Sync

- `interval`: seconds between syncs. Default `60`.
- `branch`: the branch to push. Default `main`.
  - Lark never force-pushes.

> [!TIP]
> Set `interval = 0` to sync only when you run `lark sync`.

## Remote

1. `remote`: the git URL.
2. `ssh_key`: optional path to a key.

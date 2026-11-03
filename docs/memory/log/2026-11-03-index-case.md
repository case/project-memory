---
title: Union rule names the index as spelled on disk
summary: bootstrap writes the merge=union rule with the index path's real case and checks it case-sensitively, so a Docs/ repo gets a rule that matches on Linux
created: 2026-11-03
author: Eric Case
tags: [log, decisions, bootstrap, git]
---

# 2026-11-03: Union rule names the index as spelled on disk

In a project that keeps its docs under `Docs/`, `--upgrade` wrote `docs/memory/memory-index.md merge=union`, which matches only where git ignores case. macOS sets `core.ignorecase=true`, so the check reported `union` there. On Linux and on GitHub the rule matched nothing.

## Decision

- `index_path()` walks `docs/memory/memory-index.md` one component at a time and takes the spelling from disk. An exact match wins, then an ASCII case-insensitive one. With no match it keeps the default.
- The rule uses that spelling, and `check-attr` runs with `core.ignorecase=false`. An existing rule that matches only case-insensitively then counts as absent, so the correct one is appended next to it.
- The comparison is ASCII-only. `str.casefold()` maps `ſ` to `s`, and git's ignorecase never does.

## Trade-offs accepted

- The stale lowercase line stays in `.gitattributes`. It is harmless, and deleting a user's line is not this script's job.
- A fresh bootstrap on Linux into a repo with `Docs/` still creates a separate `docs/`. Files are written before the rule, so the rule follows wherever they landed.

---
title: --upgrade flag for bootstrap.py
summary: Re-syncs the AGENTS.md marker block to the current template. Content outside the markers is preserved.
created: 2026-05-13
author: Eric Case
tags: [log, decisions, bootstrap, upgrade]
---

# 2026-05-13: --upgrade flag for bootstrap.py

Existing project-memory installations had no path to pick up rule changes (this session alone added several). `--upgrade` replaces the block between `<!-- project-memory:start -->` and `<!-- project-memory:end -->` with the current template's contents.

## What landed

- `init/bootstrap.py`: new `--upgrade` flag; positional `name`/`description` made optional under `--upgrade`; new `upgrade_agents_md` function; shared `extract_memory_block` helper used by both upgrade and merge paths.
- `tests/test_bootstrap.py`: 6 new tests covering replace-stale, no-op-when-current, preserve-outside-markers, abort-on-no, missing-AGENTS.md, missing-markers.
- `README.md`: new "Upgrading" section between "Bootstrap files" and "Frontmatter schema."

## Why

- Same script, new flag (not a separate `upgrade.py`): smaller surface area, shared helpers, one place to look.
- Diff at runtime carries the changelog. No version stamp, no `VERSIONS` dict — the diff IS the release notes.
- Block treated as system-owned (documented in README). Hand-edits inside are overwritten; users add custom rules outside the markers.

---
title: Plan files split into current/ and archive/
summary: Bootstrap creates docs/plans/current/ and docs/plans/archive/; finished plans move to archive so open work stays visible
created: 2026-08-23
author: Eric Case
tags: [log, decisions, conventions, bootstrap]
---

# 2026-08-23: Plan files split into current/ and archive/

Plan documents live under `docs/plans/`, split into `current/` and `archive/`. A plan starts in `current/` and moves to `archive/` when its work is done. Listing `current/` answers "what is still open" without opening a file.

## What landed

- `init/bootstrap.py` creates `docs/plans/current/` and `docs/plans/archive/`, each seeded with a `README.md` from its own template.
- `--upgrade` creates the same directories when missing, so already-bootstrapped repos pick up the layout.
- The `AGENTS.md` marker block gained a **Plans** rule telling agents where to write plans and to move them on completion.

## Decisions

- **A `README.md` in each directory, not `.gitkeep`.** Git cannot track an empty directory, so a placeholder is needed either way. A README also states the convention at the point of use.
- **Status by location, not by frontmatter.** A `status: done` field would need parsing to answer the same question; a directory listing does not.
- **`--upgrade` creates directories.** Its contract was "re-sync the `AGENTS.md` block." Shipping the rule without the directories would leave every existing repo half-migrated. Declining the diff still creates nothing.
- **Existing plans READMEs are skipped, not a fatal conflict.** Unlike `docs/memory/`, these files carry no user decisions, and `--upgrade` must be safe to re-run.

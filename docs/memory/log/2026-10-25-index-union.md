---
title: Memory index merges with git's union driver
summary: .gitattributes gives memory-index.md merge=union so concurrent log entries never conflict; bootstrap and --upgrade install it
created: 2026-10-25
author: Eric Case
tags: [log, decisions, conventions, bootstrap, git]
---

# 2026-10-25: Memory index merges with git's union driver

Every branch adds its log line at the top of `memory-index.md`, so any two branches that each add an entry conflict on rebase. `docs/memory/memory-index.md merge=union` tells git to keep lines from both sides instead ([gitattributes](https://git-scm.com/docs/gitattributes#_built_in_merge_drivers)).

## What landed

- This repo's `.gitattributes` carries the rule.
- `init/bootstrap.py` adds it to the target's `.gitattributes`, on bootstrap and `--upgrade`. It creates the file if missing and asks before appending to an existing one.
- Detection asks git (`check-attr`, global attributes ignored), so an existing rule is honoured and a conflicting one is reported, not overridden.

## Trade-offs accepted

- Two entries added at once may land in either order.
- The same existing line edited on both sides keeps both copies, with no conflict reported.
- jj ignores `.gitattributes` (jj#53). GitHub's web conflict check reportedly ignores it too (unverified), so a PR can show a conflict that a local rebase resolves.

## Rejected

- **Generating the index from each log's frontmatter.** Needs a generator, a lint check and a memory-system change.
- **Chronological (append at bottom) order.** Two appends at the same spot conflict the same way.
- **A custom merge driver.** Needs per-clone config and cannot be committed.

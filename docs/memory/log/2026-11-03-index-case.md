---
title: Bootstrap writes into the docs spelling already on disk
summary: every path bootstrap writes, and the merge=union rule, follows the directory spelling already on disk, checked case-sensitively and tested in a Linux container
created: 2026-11-03
author: Eric Case
tags: [log, decisions, bootstrap, git, testing]
---

# 2026-11-03: Bootstrap writes into the docs spelling already on disk

A project may keep its docs under `Docs/` rather than `docs/`. On a case-sensitive filesystem, a file written to `docs/plans/` lands in a second directory beside `Docs/`, and a `docs/memory/memory-index.md merge=union` rule matches nothing on Linux or GitHub. macOS sets `core.ignorecase=true` and aliases `docs` and `Docs`, so both problems stay hidden there.

Every path bootstrap writes, every link it generates, and the rule itself therefore follow the spelling already on disk.

## Decision

- `on_disk_path()` spells a relative path from the directory listings. A component matches exactly or ASCII case-insensitively. The spelling that reaches deepest into existing directories wins, then an exact match, then the first sorted name. Components below the deepest match keep the default spelling.
- `DocsLayout` resolves the index first, then every other path under the directories it chose, component by component. A project's files therefore never land in two differently spelled trees.
- Every write goes through the layout: memory files, the log entry, plans READMEs, and the rule. The fresh-bootstrap pre-flight checks the same paths, so an index under `Docs/` is refused on Linux too.
- Generated links come from the same layout. Templates take `${index_path}`, `${plans_current}`, `${log_name}` and their siblings from `DocsLayout.template_vars()`, and `--upgrade` renders them into the marker block. A repo whose block links to another spelling is offered the corrected block once.
- "Deepest" handles a tree already split into `Docs/memory/` and `docs/plans/`: the rule names the real index, and plans follow it to `Docs/plans/`.
- `check-attr` runs with `core.ignorecase=false`. An existing rule that matches only case-insensitively counts as absent, so the correct one is appended next to it.
- The comparison is ASCII-only. `str.casefold()` maps `ſ` to `s`, and git's ignorecase never does.
- On macOS, `bin/test` also runs `bin/test-linux`: the unit tests in a digest-pinned Alpine image with `git` and `python3`. The run first proves its temp dir is case-sensitive. Dependabot updates the image.

## Trade-offs accepted

- An existing lowercase rule that matches only case-insensitively stays in `.gitattributes`. It is harmless, and deleting a user's line is not this script's job.
- A tree that is already split keeps both directories. Merging or deleting a user's directory is not this script's job either.
- The line above the markers in an existing `AGENTS.md` keeps its lowercase links. It is user content, and only a fresh bootstrap writes it.
- dprint skips `init/templates/AGENTS.md`. Its markdown plugin (0.22.1) inserts a space into a code span after the third `${placeholder}`. pymarkdown still lints it.
- `bin/test` on macOS needs Docker. A missing `docker` fails the run rather than skipping it, so a Linux-only failure cannot pass locally.

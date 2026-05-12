---
title: Project hygiene scaffolding
summary: CI, git hooks, ruff config, Dependabot, and bootstrap hardening. Standard OSS hygiene baseline.
created: 2026-05-11
updated: 2026-05-11
author: Eric Case
tags: [log, project-hygiene, ci, tooling]
---

# 2026-05-11: Project hygiene scaffolding

Added the standard "safe to clone, safe to contribute to" baseline to this repo. Treated as one log entry because each piece is part of the same hygiene layer, not an independent decision.

## What landed

- **CI**: `.github/workflows/tests.yaml` runs `bin/test` on pull requests and pushes to `main`. Runner: `ubuntu-slim` (1 vCPU, Python 3.12.3 preinstalled), so no `setup-python` action is needed.
- **Git hooks**: `.githooks/pre-commit` runs `bin/lint`; `.githooks/pre-push` runs `bin/test`. Wired in `bin/setup` via `git config core.hooksPath .githooks` (per-clone opt-in).
- **Ruff config**: `pyproject.toml` pins `target-version = "py310"`, selects `E F I B UP SIM`, ignores `E501` (the formatter handles line length). No `[project]` table; nothing to build.
- **Dependabot**: `.github/dependabot.yml` checks `github-actions` weekly. No `pip` ecosystem entry; project is stdlib-only.
- **Bootstrap hardening**: `merge_agents_md` slices the memory section between `<!-- project-memory:start -->` and `<!-- project-memory:end -->` markers, and all file I/O in `init/bootstrap.py` is centralized through `read_text` / `write_text` helpers that pin `encoding="utf-8"`.

## Load-bearing decisions

- **In-repo `.githooks/` over a hook framework** (lefthook, pre-commit). The project's "stdlib-only Python, no install needed" framing extends to local tooling. A framework would add a dep just for two ten-line shell scripts. `core.hooksPath` is per-repo, opt-in, and discoverable from `bin/setup`. Trigger to revisit: cross-language hook fanout or staged-file filtering.
- **HTML markers plus heading detection in `merge_agents_md`** (rather than slicing from `## Project memory` to EOF). Markers survive future template growth: added sections won't leak into the appended slice. Heading-text detection catches hand-added sections so a re-run won't duplicate. Both layers are cheap, and either alone has a failure mode.

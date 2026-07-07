---
title: Markdown linting via PyMarkdown
summary: Adopted PyMarkdown. Config in pyproject.toml.
created: 2026-07-06
author: Eric Case
tags: [log, tooling, linting, markdown]
---

# 2026-07-06: Markdown linting via PyMarkdown

The memory-entry templates emitted markdown that failed a default markdownlint run, so every bootstrapped project started with lint errors. Fixed the templates at the source, then added Markdown linting to this repo's own toolchain.

## What landed

- **Template fixes**: added the missing blank lines (`MD022`/`MD032`) in `init/templates/memory-index.md` and `init/templates/bootstrap-log.md`. Purely structural; no wording changes.
- **Linter choice**: **PyMarkdown** (`pymarkdownlnt`, CLI `pymarkdown`). Pure Python, so it installs like `ruff`. Rule IDs match markdownlint's `MD###` scheme.
- **Config**: `[tool.pymarkdown]` in `pyproject.toml` (auto-discovered). Disables `MD013` (line-length), `MD025` (single-h1), `MD032` (blanks-around-lists), `MD040` (fenced-code-language), `MD041` (first-line-heading) - all style/schema choices this project doesn't want enforced.
- **Content fixes** (rules kept on, because each caught a real defect): `MD022` blank lines in `docs/memory/memory-index.md` and after the `<!-- project-memory:start -->` marker in `AGENTS.md` + its template; `MD049` `*is*`->`_is_` in `product.md`; `MD033` wrapped the `array<string>` type in backticks in `README.md`; `MD014` dropped the leading `$` command prompt in `README.md`.
- **`bin/lint`**: runs `pymarkdown --strict-config scan -r .` - prefers a global `pymarkdown` binary, falls back to `uvx --from pymarkdownlnt pymarkdown`. The `.githooks/pre-commit` hook already runs `bin/lint`, so markdown now lints per-commit.

## Decisions

- **Front-matter extension is mandatory**: `extensions.front-matter.enabled = true`. PyMarkdown leaves front-matter parsing off by default, which misreads `title:` + the closing `---` as a setext heading and floods `MD003`/`MD022` false positives (61 -> 2 once enabled). Do not remove this line.
- **Config is this-repo-only**: bootstrapped downstream projects are shipped no lint config. Their linter, their rules. Matches the repo's existing restraint (`bin/lint` was markdown-agnostic before this).

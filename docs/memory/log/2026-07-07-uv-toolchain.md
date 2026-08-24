---
title: Pinned dev toolchain via uv
summary: Linters pinned in pyproject.toml dependency-groups + uv.lock, run via uv, updated by Dependabot's uv ecosystem with a 14-day cooldown.
created: 2026-07-07
author: Eric Case
tags: [log, tooling, linting, uv, dependabot]
---

# 2026-07-07: Pinned dev toolchain via uv

Reversed the earlier "dev tools are environment-provided and unpinned" stance. The three linters are now version-pinned, reproducible, and kept current by Dependabot. Supersedes the runner setup described in [2026-07-06 markdown-lint](2026-07-06-markdown-lint.md) (PyMarkdown no longer runs via `uvx`) and the "no `[project]` table, tools installed via mise" notes in [2026-05-11 project-hygiene](2026-05-11-project-hygiene.md).

## What landed

- **Pinned dev tools**: `[dependency-groups]` in `pyproject.toml` pins `ruff==0.15.20`, `shellcheck-py==0.11.0.1`, `pymarkdownlnt==0.9.38`. `uv.lock` is committed; `.venv` is gitignored.
- **Non-package project**: a minimal `[project]` table (only `requires-python = ">=3.10"`) plus `[tool.uv]` with `package = false`. The table exists solely so uv locks for 3.10+, not to build or publish anything.
- **shellcheck via shellcheck-py**: shellcheck is a Haskell binary, not a Python package. The `shellcheck-py` wrapper bundles the official binary so it can sit in the same pinned group.
- **bin/lint runs through uv**: `uv run --locked` for ruff, shellcheck, and pymarkdown. `--locked` fails if `pyproject.toml` and `uv.lock` drift, instead of silently re-resolving.
- **bin/setup**: runs `uv sync --locked` to install the pinned tools, and warns if `uv` is missing.
- **Dependabot**: added a `uv` ecosystem entry; both `uv` and `github-actions` carry `cooldown` with `default-days: 14`.

## Decisions

- **uv over mise for these tools**: the tools are cross-language (Rust, Haskell, Python), so mise was the conceptually cleaner manager. But Dependabot has no `mise` ecosystem, and automated Dependabot-managed updates were the priority. Dependabot's `uv` ecosystem (GA March 2025) reads `pyproject.toml` and `uv.lock` natively. mise plus Renovate stays the alternative if we ever drop Dependabot.
- **Exact pins, not ranges**: versions are visible in `pyproject.toml`, and exact pins avoid the dependabot-core behavior where a range constraint updates only `uv.lock` and leaves the manifest stale.
- **uv is now required to lint**: the pre-commit hook runs `bin/lint`, which needs `uv`. A contributor without `uv` cannot lint. Accepted, since `uv` is already the repo's install path and `bin/setup` flags its absence.

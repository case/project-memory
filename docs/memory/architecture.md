---
title: Architecture
summary: Just a folder full of markdown files, with some frontmatter
created: 2026-05-11
author: Eric Case
tags: [architecture, stack, codebase, conventions]
---

# Architecture

The current implementation of project-memory. Replace any of this and the [product](product.md) is unaffected. The product is "above the user experience abstraction layer," and the architecture is "below the abstraction layer."

## Repo layout

```
/.githooks        # Ensures that linting and tests are run before commits are pushed
/.github          # Simple CI for tests and the actions/checkout dependency update

/bin              # Simple scripts for Linting, Setup, and running the tests
/docs             # This project is using its own memory system. MindBlown.gif
/init             # The bootstrap script and template files used when bootstrapping
/tests            # The tests

/AGENTS.md        # Agent instructions for how to use this system.
/CLAUDE.md        # Come on Anthropic, just adopt AGENTS.md
/LICENSE          # MIT license
/pyproject.toml   # For tooling config
```

## Stack

- Text files - The memory system is just `.md` markdown text files, UTF-8 encoded.
- Python stdlib - The bootstrap script is just basic Python, with no third-party dependencies.

## Vendor decisions

Not applicable.

## Conventions

Simple and min-viable, no outside deps aside from the lint tooling.

- Python 3.10+ floor (declared in `pyproject.toml` and verified in `bin/setup`)
- Ruff for lint/format with `target-version = "py310"`; rules: E, F, I, B, UP, SIM; E501 ignored (formatter handles it)
- Shellcheck for `bin/*` and `.githooks/*`
- Tests via `python3 -m unittest`
- Git hooks in `.githooks/` wired via `core.hooksPath`: `pre-commit` → `bin/lint`, `pre-push` → `bin/test`
- CI on the `ubuntu-slim` runner, Python 3 is preinstalled
- Dependabot on weekly cadence for GitHub Actions, just for `actions/checkout`

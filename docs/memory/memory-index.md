# project-memory memory

Project decisions, architecture, and conventions. Two core files plus a dated `log/` subdir.

Agents: consult before suggesting layout, naming, dependencies, vendors, or conventions. Verify against the codebase before relying on a specific path or name - memory can lag reality.

## Core

- [Product](product.md) - what project-memory is and why; implementation-independent
- [Architecture](architecture.md) - current implementation: stack, layout, conventions

## Log (newest first)

- [2026-08-24 Template links checked against bootstrapped output](log/2026-08-24-template-link-guard.md) - the monorepo rationale links to the public README anchor; a test walks every link in a bootstrapped project
- [2026-08-23 --upgrade refuses to delete custom marker-block sections](log/2026-08-23-marker-block-guard.md) - an upgrade aborts and names any heading inside the markers that the template lacks; `--force` overrides
- [2026-08-23 Plan files split into current/ and archive/](log/2026-08-23-plans-current-archive.md) - plans live in `docs/plans/current/` and move to `docs/plans/archive/` when done; bootstrap and `--upgrade` create both
- [2026-07-07 Pinned dev toolchain via uv](log/2026-07-07-uv-toolchain.md) - linters pinned in `pyproject.toml` + `uv.lock`, run via `uv`, Dependabot-managed with a 14-day cooldown
- [2026-07-06 Markdown linting via PyMarkdown](log/2026-07-06-markdown-lint.md) - pure-Python linter (no Node); config in `pyproject.toml`, front-matter extension required
- [2026-05-13 --upgrade flag for bootstrap.py](log/2026-05-13-upgrade-flag.md) - re-syncs the AGENTS.md marker block to the current template; content outside the markers is preserved
- [2026-05-13 Entries are concise](log/2026-05-13-concise-entries.md) - bigger than a commit message, smaller than a design doc
- [2026-05-13 Log slugs are 1-3 words](log/2026-05-13-slug-brevity.md) - filename slug after the date is a topic distillation; if it needs more than 3 words, split the entry
- [2026-05-13 Draft meta-entries inline before writing](log/2026-05-13-meta-entry-review.md) - changes to conventions/schema/naming require inline draft and approval before save
- [2026-05-12 Frontmatter `updated` field is now optional](log/2026-05-12-frontmatter-updated-optional.md) - omit on first creation; add only on first meaningful edit
- [2026-05-12 Monorepo support pattern documented](log/2026-05-12-monorepo-support.md) - per-subproject `docs/memory/` plus an optional root `docs/memory/` for cross-cutting concerns
- [2026-05-11 Project hygiene scaffolding](log/2026-05-11-project-hygiene.md) - CI, git hooks, ruff config, Dependabot, and bootstrap hardening
- [2026-05-11 Bootstrap memory system](log/2026-05-11-bootstrap.md) - initial setup of this memory system

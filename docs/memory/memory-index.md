# project-memory memory

Project decisions, architecture, and conventions. Two core files plus a dated `log/` subdir.

Agents: consult before suggesting layout, naming, dependencies, vendors, or conventions. Verify against the codebase before relying on a specific path or name - memory can lag reality.

## Core
- [Product](product.md) - what project-memory is and why; implementation-independent
- [Architecture](architecture.md) - current implementation: stack, layout, conventions

## Log (newest first)
- [2026-05-13 --upgrade flag for bootstrap.py](log/2026-05-13-upgrade-flag.md) - re-syncs the AGENTS.md marker block to the current template; content outside the markers is preserved
- [2026-05-13 Entries are concise](log/2026-05-13-concise-entries.md) - bigger than a commit message, smaller than a design doc
- [2026-05-13 Log slugs are 1-3 words](log/2026-05-13-slug-brevity.md) - filename slug after the date is a topic distillation; if it needs more than 3 words, split the entry
- [2026-05-13 Draft meta-entries inline before writing](log/2026-05-13-meta-entry-review.md) - changes to conventions/schema/naming require inline draft and approval before save
- [2026-05-12 Frontmatter `updated` field is now optional](log/2026-05-12-frontmatter-updated-optional.md) - omit on first creation; add only on first meaningful edit
- [2026-05-12 Monorepo support pattern documented](log/2026-05-12-monorepo-support.md) - per-subproject `docs/memory/` plus an optional root `docs/memory/` for cross-cutting concerns
- [2026-05-11 Project hygiene scaffolding](log/2026-05-11-project-hygiene.md) - CI, git hooks, ruff config, Dependabot, and bootstrap hardening
- [2026-05-11 Bootstrap memory system](log/2026-05-11-bootstrap.md) - initial setup of this memory system

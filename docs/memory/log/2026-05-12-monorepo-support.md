---
title: Monorepo support pattern documented
summary: Per-subproject `docs/memory/` plus an optional root `docs/memory/` for cross-cutting concerns. Root AGENTS.md routes agents to the relevant subproject memory.
created: 2026-05-12
author: Eric Case
tags: [log, decisions, monorepo, product, docs]
---

# 2026-05-12: Monorepo support pattern documented

Clarified that monorepos are in scope and described the recommended layout. Triggered by considering how this system applies to a personal homelab monorepo where each `infra/<thing>` is a distinct subproject. Documentation-only change; no code edits.

## What landed

- **`docs/memory/product.md`**: new "Monorepos" section. A monorepo is a code-and-config layout, not a different product. Each subproject gets its own `docs/memory/`; the repo root gets a small `docs/memory/` for genuinely cross-cutting concerns.
- **`README.md`**: short "Monorepos" subsection between "Why this shape?" and "Getting started", linking to `product.md#monorepos` as the canonical reference.
- **`AGENTS.md` and `init/templates/AGENTS.md`**: added a one-line "Monorepos" rule inside the `<!-- project-memory:start/end -->` markers, routing agents to subproject memory when working inside one.

## Load-bearing decisions

- **Per-subproject `docs/memory/` over a flat directory with frontmatter scoping**. Considered a `scope: <subdir>` frontmatter field on entries in a single shared memory directory. Rejected: that reinvents directory structure with metadata, forces an index-and-filter step on every read, and breaks the "memory lives next to the code" convention. Locality wins for the common case (one subproject at a time).
- **Generic wording in `product.md`, not concrete example trees**. First draft used `infra/signoz` / `infra/hostbox` from the originating homelab; rewrote to abstract "subproject" language because `product.md` is open-source-facing and shouldn't prescribe one user's layout as canonical.
- **Guidance inside the `project-memory:start/end` markers in `AGENTS.md`**. Inside the markers means the bootstrap script's merge logic carries the new line forward when users re-bootstrap into an existing `AGENTS.md`. Outside would be a one-time-only insertion.
- **Conditional phrasing ("if this repo contains subprojects with their own `docs/memory/`")**. Makes the monorepo line a no-op for single-project users without needing a separate gating header.

## Open gaps

- `init/bootstrap.py` has no monorepo affordance. Users re-run it manually from each subproject. A future `--subproject` flag (or auto-detection of an existing root-level `docs/memory/`) could close the gap.
- Users who bootstrapped before today won't auto-pick up the new monorepo line on re-run; the merge logic likely no-ops when the marker block already exists. A "refresh marker block" mode would help.

---
title: Frontmatter `updated` field is now optional
summary: On first creation, omit `updated`. Add it only on the first meaningful edit. Absent means same as `created`.
created: 2026-05-12
author: Eric Case
tags: [log, decisions, conventions, frontmatter, schema]
---

# 2026-05-12: Frontmatter `updated` field is now optional

Dropped the convention that every entry ships with `updated:` set equal to `created:` on day one. That value carried no information beyond duplicating `created`. The field is now opt-in, added only when an entry is actually edited after creation.

## What landed

- **`README.md` frontmatter schema table**: row for `updated` rewritten to mark it optional, with the explicit semantic "absent means same as `created`."
- **Templates** (`init/templates/product.md`, `architecture.md`, `bootstrap-log.md`): removed the `updated: ${today}` line. Fresh bootstraps no longer emit it.
- **Existing entries with `updated == created`** swept clean: `docs/memory/architecture.md`, both `2026-05-11-*.md` log entries, and today's `2026-05-12-monorepo-support.md`.
- **`docs/memory/product.md`** kept its `updated:` because the value genuinely differs from `created` (bumped today for the monorepo section). This is the new field's intended use.

## Load-bearing decisions

- **Optional, not removed**. The field still has a real job once an entry has been edited: it drives staleness review and signals that the body has changed since first publication. The only thing it didn't do well was carry that signal on day one.
- **"Absent means same as `created`" spelled out in the schema**. Keeps tooling simple: `entry.updated or entry.created` is the canonical staleness key. Avoids a separate "is it stale?" decision tree for entries missing the field.
- **Schema uniformity preserved at the spec level, not the file level**. The README's anti-pattern entry says "keep the schema uniform across all entries so future tooling can rely on it." Marking `updated` optional with a documented default means the *spec* is still uniform, even though individual files vary in whether the field is present.
- **Did not retroactively bump `updated` on the swept entries**. Removing a noise field is not a "meaningful edit" of the content. Treating it as one would defeat the purpose.

## Verified

- `tests/test_bootstrap.py` does not assert on `updated:` shape; the sweep does not require test changes.

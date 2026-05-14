---
title: Log slugs are 1-3 words
summary: The slug after the date should be 1-3 words. Forces topic distillation and keeps `log/` browse-able.
created: 2026-05-13
author: Eric Case
tags: [log, decisions, conventions, naming]
---

# 2026-05-13: Log slugs are 1-3 words

Constrained log filename slugs to 1-3 words after the date.

## What landed

- **`README.md` "Conventions for working with the system"**: new bullet **Log slugs stay short** (1-3 words). Matches the existing voice of the **Core files stay short** rule.
- **Today's other draft entry**: saved as `2026-05-13-meta-entry-review.md` rather than the original 5-word slug.
- **Older entries left alone**: existing slugs (`bootstrap`, `project-hygiene`, `monorepo-support`, `frontmatter-updated-optional`) are all within the 3-word limit. No retroactive renames.

## Load-bearing decisions

- **1-3 words, not a hard cap of 3**. Some topics distill to one word (`bootstrap`); others need two or three. A floor and a ceiling beats a fixed count.
- **Topic distillation, not a sentence**. If a slug needs a verb or a preposition, it's drifting toward a title. The H1 inside the file carries the full title; the slug is the index key.
- **No retroactive renames**. Existing slugs comply. Renaming would invalidate any reference in commit history and other docs without improving anything.

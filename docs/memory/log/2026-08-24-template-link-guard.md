---
title: Template links checked against bootstrapped output
summary: The AGENTS.md template's monorepo rationale now points at the public README anchor, and a test walks every generated markdown link so a dangling relative target or anchor fails the suite.
created: 2026-08-24
author: Eric Case
tags: [log, decisions, templates, testing, docs]
---

# 2026-08-24: Template links checked against bootstrapped output

A bootstrap run in another repo reported that the marker block linked to `docs/memory/product.md#monorepos`, an anchor that exists only here. `init/templates/product.md` has no "Monorepos" heading, so every bootstrapped project inherited a dangling anchor.

## What landed

- **`init/templates/AGENTS.md` and `AGENTS.md`**: the Monorepos rule now links to `https://github.com/case/project-memory#monorepos`. Both files change together so the marker blocks stay byte-identical and `--upgrade` still reports "already current".
- **`tests/test_bootstrap.py`**: new `TestGeneratedLinks` bootstraps a project and walks every markdown link in the output. Relative targets must exist; a `#fragment` must match a GitHub-style heading slug in the target file.

## Decisions

- **Absolute upstream URL over adding a Monorepos section to `init/templates/product.md`**. The rationale is about this memory system, not about the bootstrapped project's own product, and most projects are not monorepos. Seeding that section into every downstream product doc puts the wrong content at the wrong layer.
- **URL over dropping the link**. The rule reads fine without a pointer, but the rationale stays reachable from any repo this way, and a public README anchor does not depend on the reader having this checkout.
- **Test asserts against bootstrapped output, not against the template files**. Template paths are written relative to the generated tree, so they only resolve after substitution. The guard was confirmed by restoring the old link and watching the test fail.

## Open gaps

- The link walk only covers generated files. Links inside this repo's own docs are still unchecked; PyMarkdown does not verify cross-file anchors.

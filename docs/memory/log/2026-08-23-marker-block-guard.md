---
title: --upgrade refuses to delete custom sections in the marker block
summary: An upgrade aborts and names any section inside the project-memory markers that the template lacks; --force overrides
created: 2026-08-23
author: Eric Case
tags: [log, decisions, bootstrap, safety]
---

# 2026-08-23: --upgrade refuses to delete custom sections in the marker block

`--upgrade` replaces the whole `project-memory:start`/`end` block with the template's. If a project put its own section inside those markers, the upgrade proposed deleting it. The diff and the `[y/N]` prompt made that visible but easy to approve past.

## What landed

- `init/bootstrap.py` gained `block_sections()` and `custom_sections()`. Before diffing, `upgrade_agents_md()` collects section markers in the project's block that the template lacks, and exits non-zero naming them.
- `--force` skips the refusal. It does not skip the `[y/N]` prompt.

## Decisions

- **Compare section markers, not lines.** A line-level check would flag every reworded template rule, so any prose edit to the template would abort every upgrade everywhere. Markers identify whole sections a user added, which is what an upgrade actually destroys.
- **Markers are headings and bold rule labels.** Every rule in the block is a `**Label**:` lead-in and `## Project memory` is the only heading in it, so a user adding a rule in the style the block teaches writes bold, not a heading. Detecting headings alone missed the likelier shape. Only the label is compared, so reworded prose after it is still not a new section.
- **Refuse rather than warn.** The prompt already showed the deletion and was easy to approve past. An exit forces the user to move the section out first, which is the fix.
- **Renaming a template marker will refuse every downstream upgrade.** A renamed heading or bold label makes every bootstrapped repo's old marker look custom, and the refusal then tells users to move system-owned content outside the markers, which is the wrong action. Version or hash tracking of prior templates was rejected as too much machinery for a rare event. Rename a marker only with a deliberate migration note, or expect downstream users to need `--force`.
- **Known gap: content a user adds under an existing marker is still not detected.** Only new sections are. Widening the check means line-level comparison and the false-positive problem above.
- **Fenced code is skipped** so a `#` or bold line inside an example block is not read as a marker. Setext headings are not recognized.

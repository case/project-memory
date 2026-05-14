---
title: Draft meta-entries inline before writing
summary: Meta-entries (changes to memory conventions, schema, naming, structure) must be drafted in chat and approved before written to disk. Event entries unchanged.
created: 2026-05-13
author: Eric Case
tags: [log, decisions, conventions, workflow]
---

# 2026-05-13: Draft meta-entries inline before writing

Added a review gate for memory entries that change the memory system itself. Triggered by yesterday's `updated`-field cleanup: entries had already been written with the redundant field by the time the operator caught the issue. A pre-save draft would have surfaced it one turn earlier.

## What landed

- **`AGENTS.md` and `init/templates/AGENTS.md`**: added an exception clause to the "When a new decision is made" rule, inside the `project-memory:start/end` markers. Meta-entries (changes to conventions, schema, naming, structure) require drafting the body inline and waiting for explicit go-ahead. Event entries follow the existing post-write diff-surface flow.

## Load-bearing decisions

- **Single-rule-with-exception over two-separate-rules**. Keeps the AGENTS.md short and frames meta entries as a deviation from the default, which matches the actual frequency: most entries are event captures.
- **"Draft the body inline" rather than "draft a summary"**. The full content goes in chat, not a paraphrase. Reviewing a summary and approving the file is a different (and weaker) check than reviewing the actual text.
- **No symmetric review gate on event entries**. The lightweight post-write diff is sufficient for routine captures; a hard pre-save gate on every log entry would defeat the system's low-friction framing. The operator can still object after the fact.
- **Self-review by Claude not added**. Memory entries are short markdown with no logic to verify; the failure modes (wrong framing, premature memorialization) aren't caught well by self-review. The operator's eye is the real check.

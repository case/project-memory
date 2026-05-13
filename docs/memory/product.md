---
title: Product
summary: A lightweight, file-based memory system for small software projects.
created: 2026-05-11
updated: 2026-05-12
author: Eric Case
tags: [product, scope, goals]
---

# Product

A lightweight, file-based memory system for small software projects.

## Why this exists

I need a simple, min-viable solution for automatically logging and tracking per-repo "project memory" as my various dev projects evolve over time. There are numerous other projects in this space, but I'm a "learn by doing" type, so I figured why not try this out.

## Who it's for

This is for smaller-scale software projects that have semi-regular development and operations. Probably usable by a small team.

## What it's not

This is _not_ meant for large projects with ongoing, daily development work by a large team with lots of iteration.

## Monorepos

A monorepo is still in scope. It's a code and config layout, not a different product.

The pattern: each subproject gets its own `docs/memory/`. The repo root gets a small `docs/memory/` for genuinely cross-cutting concerns: shared conventions, decisions that apply to every subproject, how the pieces fit together.

The root `AGENTS.md` becomes a routing doc. It tells agents: when working in a given subproject, the authoritative memory is that subproject's `docs/memory/`. The root memory is for repo-wide decisions only.

This keeps the convention that memory lives next to the code it describes. The root memory exists because some decisions don't belong to any single subproject.

## Implementation independence

The product is durable across two kinds of change: **how it's built** (stack, codebase) and **where it runs** (hosting, infrastructure, operational setup). Either can change without altering what the product *is*. See [`architecture.md`](architecture.md) for the current implementation.

The product is "above the user experience abstraction layer," and the architecture is "below the abstraction layer."

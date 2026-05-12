---
title: Product
summary: ${desc}
created: ${today}
updated: ${today}
author: ${author}
tags: [product, scope, goals]
---

# Product

${desc}

## Why this exists

<The motivating thesis — the problem the project solves and why it's worth solving now.>

## Who it's for

<Audience, users, scope of usage.>

## What it's not

<Explicit out-of-scope markers — what the project is deliberately not.>

## Implementation independence

The product is durable across two kinds of change: **how it's built** (stack, codebase) and **where it runs** (hosting, infrastructure, operational setup). Either can change without altering what the product *is*. See [`architecture.md`](architecture.md) for the current implementation.

The product is "above the user experience abstraction layer," and the architecture is "below the abstraction layer."

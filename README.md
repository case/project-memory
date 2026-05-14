# project-memory

A lightweight, file-based memory system for small software projects. Just markdown files, a simple directory structure, and your existing source control. No third-party dependencies. Captures high-level project entities like the project's product description, the project's system architecture, and an index of all memory entries. A minimal frontmatter system in the memory files allows for extensibility and future iteration (e.g. db-based storage). This system is meant for smaller-scale projects.

## What you get

After bootstrapping, your project will have these additions:

```
/AGENTS.md                   # Vendor-neutral entrypoint for any agent; updated if it already exists
/CLAUDE.md                   # One-line `@AGENTS.md` import for Claude Code
/docs/
  memory/
    memory-index.md          # Table of contents
    product.md               # What and why, implementation-independent
    architecture.md          # Current implementation overview
    log/
      yyyy-mm-dd-<slug>.md   # Dated events / decisions / incidents / etc.
```

Core files (`product.md`, `architecture.md`) plus a dated `log/` subdir. Add more core files (e.g. `codebase.md`, `conventions.md`, etc.) only when an existing file exceeds ~50 lines, or starts evolving on a separate cadence.

## Why this shape?

**Two core files** - `product.md` is the durable layer (which survives a code rewrite or systems migration), and `architecture.md` is the current implementation (which a rewrite would replace). That durability split is the load-bearing distinction. Splitting further (`codebase.md`, `conventions.md`, etc.) is deferred until a file outgrows itself.

**`AGENTS.md` as canonical** - `AGENTS.md` is the [open standard](https://agents.md) read by almost all coding agents. Claude Code only reads `CLAUDE.md` natively, so a one-line `@AGENTS.md` import is the [Anthropic-recommended workaround](https://code.claude.com/docs/en/memory#agentsmd). This keeps the project portable across agents.

**`memory-index.md`** - An agent reads one cheap file to discover what's in memory, then fetches specific entries on demand. Without an index, agents either guess or blanket-load, both of which are expensive.

**Frontmatter is schema-like** - Every entry has the same fields. If memory ever migrates to a database (or a static-site search index, or anything queryable), the frontmatter fields become columns.

## Monorepos

A monorepo is in scope. Run the bootstrap inside each subproject so each has its own `docs/memory/`, and optionally once more at the repo root for cross-cutting concerns. The root `AGENTS.md` should route agents to the relevant subproject memory when working inside one. See [`product.md`](docs/memory/product.md#monorepos) for the rationale.

---

## Getting started

Three ways to bootstrap, pick whichever you prefer:

### Option A - Run the bootstrap script (recommended)

[`init/bootstrap.py`](init/bootstrap.py) and its [`init/templates/`](init/templates/) directory are everything you need. Python 3.10+, stdlib-only - no install, no `chmod`, no `$PATH` setup. Clone this repo, then run from anywhere:

```
$ python3 /path/to/project-memory/init/bootstrap.py --project /path/to/your/project "<project name>" "<project description>"
```

Or `cd` into your target project first and omit `--project` (defaults to the current directory):

```
cd /path/to/your/project
python3 /path/to/project-memory/init/bootstrap.py "<project name>" "<project description>"
```

The script safely renders the templates into the target project, with metadata populated (project name, dates, author from `git config user.name` in the target repo) and `<placeholder>` strings left for you to fill in. If `AGENTS.md` or `CLAUDE.md` already exist, it offers to merge in the memory rules. It will not overwrite anything under `docs/memory/`. Safe to re-run after partial setup.

After bootstrapping, fill in `<placeholder>` strings in `docs/memory/product.md` and `docs/memory/architecture.md`

### Option B - Create the six files manually

Open each file in [`init/templates/`](init/templates/) (see [Bootstrap files](#bootstrap-files) below for the mapping), copy their contents into the target project at the corresponding path, and substitute the `${var}` placeholders by hand. Useful if you want to understand what the script does, or if Python isn't handy.

### Option C - Hand it to an agent

Hand this repo to an LLM coding agent, with this prompt:

> Bootstrap this project's memory system. The script is at `<path/to/project-memory/init/bootstrap.py>` (run with `--project .` from the target repo). Project name: `<project-name>`. Description: `<project-description>`. After the script completes, fill in `<placeholder>` strings in `docs/memory/product.md` and `docs/memory/architecture.md` from the existing codebase (manifests, README, etc.); leave any you can't infer for me to complete.

A capable agent should handle this end-to-end, and usually populate `architecture.md` partially from existing manifests.

## Bootstrap files

The bootstrap script (Option A) renders these template files into the target project. To change what gets generated, edit the template source files directly - they're the single source of truth.

| Bootstrap target                            | Template source                                                      | Substitutions                       |
|---------------------------------------------|----------------------------------------------------------------------|-------------------------------------|
| `AGENTS.md`                                 | [`init/templates/AGENTS.md`](init/templates/AGENTS.md)               | `${name}`, `${desc}`                |
| `CLAUDE.md`                                 | [`init/templates/CLAUDE.md`](init/templates/CLAUDE.md)               | none                                |
| `docs/memory/memory-index.md`               | [`init/templates/memory-index.md`](init/templates/memory-index.md)   | `${name}`, `${today}`               |
| `docs/memory/product.md`                    | [`init/templates/product.md`](init/templates/product.md)             | `${desc}`, `${author}`, `${today}`  |
| `docs/memory/architecture.md`               | [`init/templates/architecture.md`](init/templates/architecture.md)   | `${name}`, `${author}`, `${today}`  |
| `docs/memory/log/<yyyy-mm-dd>-bootstrap.md` | [`init/templates/bootstrap-log.md`](init/templates/bootstrap-log.md) | `${author}`, `${today}`             |

The script substitutes `${var}` placeholders using Python's `string.Template`. Other placeholder syntax (e.g. `<...>` markers) is left as-is for the user to fill in after bootstrap.

If a template ever needs a literal `$`, escape it as `$$` (a `string.Template` requirement).

## Upgrading

To pick up changes to the memory rules in an already-bootstrapped project, re-run the same script with `--upgrade`:

```
python3 /path/to/project-memory/init/bootstrap.py --upgrade --project /path/to/your/project
```

The script locates the `<!-- project-memory:start -->` ... `<!-- project-memory:end -->` block in your `AGENTS.md`, diffs it against the current template, and prompts before replacing. Content outside the markers is preserved. If your block already matches, the script exits with "already current."

The block between the markers is system-owned. Don't hand-edit it; add custom rules outside the markers instead.

## Frontmatter schema

Every memory entry (core file or log file) starts with this frontmatter:

| Field    | Type           | Purpose                                                                       | Example                                                                            |
|----------|----------------|-------------------------------------------------------------------------------|------------------------------------------------------------------------------------|
| title    | string         | Human-readable name                                                           | `Adopted VictoriaMetrics for observability`                                        |
| summary  | string ≤120ch  | Index hook - what an agent reads to decide if the entry is relevant           | `VM stack (logs+metrics+traces) on <hosting service>; rejected <other stack> for lack of maturity` |
| created  | YYYY-MM-DD     | Immutable date of record                                                      | `2026-05-07`                                                                       |
| updated  | YYYY-MM-DD     | Optional. Add on the first meaningful edit; bump on subsequent edits. Absent means same as `created`. Drives staleness review | `2026-05-08`                                                                       |
| author   | string         | Originator. Immutable - credit, not ownership (git blame covers ongoing edits)| `<git user.name>`                                                                  |
| tags     | array<string>  | Freeform, kebab-case. For grep/filter                                         | `[log, decisions, observability]`                                                  |

Deliberately not included:
- `status` (active/superseded/etc.) - if it's in memory it's true; if not, delete it and git remembers
- `type` - filename pattern encodes core vs log (no date prefix vs `log/yyyy-mm-dd-*.md`)

## Conventions for working with the system

- **Core files stay short** (~50 lines) - Past that, split (e.g. `codebase.md`, `conventions.md`) and update `memory-index.md`.
- **Entries are concise** - Bigger than a commit message, smaller than a design doc. A handful of bullets, short rationales per decision. If a bullet needs a paragraph, the entry is probably bundling.
- **One event per log file** - Multiple events on the same day = multiple files (`2026-05-08-layout-flatten.md`, `2026-05-08-dep-bump.md`). Don't append a second event onto an existing log file - keeps retrieval precise and titles meaningful.
- **Log slugs stay short** (1-3 words) - The slug after the date is a topic distillation, not a sentence. If you need more, the entry is probably bundling decisions and should be split.
- **Log entries are append-only** - If superseded, write a *new* log entry that links back; don't rewrite history. This shows the evolution of the discussion and decision-making process.

## Anti-patterns

- **Long entries** (>~50 lines) - usually a sign two topics got merged; split them.
- **Silent rewrites of log files** - log entries are dated events; supersede with a new dated entry, don't edit the old one.
- **Adding fields to frontmatter for one entry** - keep the schema uniform across all entries so future tooling can rely on it.

## Prior art

This system is inspired by, but deviates from:

- **[Cline's Memory Bank](https://docs.cline.bot/features/memory-bank)** - established 6-file taxonomy in a `memory-bank/` directory, loaded via `.clinerules`. This system adopts the *pattern* (markdown files in a memory directory as the agent's persistent context), but uses two core files instead of six, adds an index file, adds a `log/` subdir for dated events, and adds frontmatter for queryability.
- **[AGENTS.md](https://agents.md)** - open standard for the agent-facing instruction file. Not yet natively read by Claude Code - see the Claude Code memory docs link below.
- **[Anthropic Claude Code memory docs](https://code.claude.com/docs/en/memory#agentsmd)** - documents the `@AGENTS.md` import workaround used in `CLAUDE.md` above. The native-AGENTS.md feature requests ([#6235](https://github.com/anthropics/claude-code/issues/6235), [#34235](https://github.com/anthropics/claude-code/issues/34235), [#31005](https://github.com/anthropics/claude-code/issues/31005)) remain open.

Also shaped by conversations with, and prior work by:

- [cbro](https://cbro.dev/)
- [est](https://emily.news/)
- [Chris Killpack](https://github.com/chriskillpack)
- [Frank Denis](https://00f.net/) and his [Swival](https://swival.dev/) project
- [Jordan Alperin](https://alpjor.com/)
- [Peter Teichman](https://teichman.org/)
- [Steve Klabnik](https://steveklabnik.com/)

## License

[MIT](LICENSE) © Eric Case

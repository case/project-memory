#!/usr/bin/env python3
"""Bootstrap the project memory system.

Reads ${var}-substituted markdown templates from the 'templates/' directory next
to this script (override with --templates-dir). Renders them into:

  - AGENTS.md and CLAUDE.md at the project root
  - memory-index.md, product.md, architecture.md, and a dated bootstrap log entry
    under docs/memory/
  - a README.md in docs/plans/current/ and docs/plans/archive/

If AGENTS.md or CLAUDE.md already exist, interactively offers to merge the memory
rules in (append a '## Project memory' section to AGENTS.md; prepend '@AGENTS.md'
to CLAUDE.md). Refuses to overwrite any files under docs/memory/. Safe to re-run
after partial setup.

Usage:
    python3 bootstrap.py "<Project name>" "<One-line description>"
    python3 bootstrap.py --project /path/to/repo "<Project>" "<Description>"
    python3 bootstrap.py --upgrade --project /path/to/repo
    python3 bootstrap.py --upgrade --force --project /path/to/repo

If --project is omitted, the current working directory is used. With --upgrade,
the AGENTS.md marker block is replaced with the current template's contents,
content outside the markers is preserved, and any missing docs/plans/
directories are created. An upgrade refuses to run when the marker block holds
sections the template does not have, since replacing it would delete them;
--force overrides that.
"""

import argparse
import datetime
import difflib
import os
import pathlib
import re
import string
import subprocess
import sys

START_MARKER = "<!-- project-memory:start -->"
END_MARKER = "<!-- project-memory:end -->"
PLANS_SUBDIRS = ("current", "archive")


def git_user_name(cwd: pathlib.Path) -> str:
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        return result.stdout.strip() or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def colorize_diff(diff: str) -> str:
    """Color a unified diff with ANSI codes when stdout is a TTY.

    Respects NO_COLOR (https://no-color.org/) and skips coloring when stdout
    is piped or redirected so codes don't leak into files.
    """
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return diff
    reset = "\033[0m"
    bold = "\033[1m"
    red = "\033[31m"
    green = "\033[32m"
    cyan = "\033[36m"
    out = []
    for line in diff.splitlines(keepends=True):
        eol = "\n" if line.endswith("\n") else ""
        body = line[: -len(eol)] if eol else line
        if body.startswith(("+++", "---")):
            out.append(f"{bold}{body}{reset}{eol}")
        elif body.startswith("+"):
            out.append(f"{green}{body}{reset}{eol}")
        elif body.startswith("-"):
            out.append(f"{red}{body}{reset}{eol}")
        elif body.startswith("@@"):
            out.append(f"{cyan}{body}{reset}{eol}")
        else:
            out.append(line)
    return "".join(out)


def confirm(prompt: str) -> bool:
    """Ask yes/no on stdin. Defaults to no, including in non-interactive contexts."""
    try:
        response = input(prompt).strip().lower()
    except EOFError:
        return False
    return response in ("y", "yes")


def read_text(path: pathlib.Path) -> str:
    """Read a file as UTF-8. Centralizes the encoding choice for portability."""
    return path.read_text(encoding="utf-8")


def write_text(path: pathlib.Path, content: str) -> None:
    """Write a file as UTF-8. Centralizes the encoding choice for portability."""
    path.write_text(content, encoding="utf-8")


def load_template(
    templates_dir: pathlib.Path, filename: str, **substitutions: str
) -> str:
    """Load a template file from templates_dir and apply ${var} substitutions."""
    path = templates_dir / filename
    if not path.is_file():
        sys.exit(f"missing template file: {path}")
    return string.Template(read_text(path)).substitute(**substitutions)


def blocking_non_directory(path: pathlib.Path) -> pathlib.Path | None:
    """The nearest existing ancestor of path that is not a directory, if any."""
    for candidate in (path, *path.parents):
        if candidate.is_symlink() or candidate.exists():
            return None if candidate.is_dir() else candidate
    return None


def ensure_directory(path: pathlib.Path) -> None:
    """Create a directory, exiting with a readable message if a file is in the way."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except (FileExistsError, NotADirectoryError):
        blocker = blocking_non_directory(path) or path
        sys.exit(
            f"cannot create directory {path}: {blocker} exists and is not a "
            f"directory. Move or remove it, then re-run."
        )


def write_file(path: pathlib.Path, content: str) -> None:
    if path.exists():
        sys.exit(f"refusing to overwrite existing file: {path}")
    ensure_directory(path.parent)
    write_text(path, content)
    print(f"wrote {path}")


def extract_memory_block(content: str, source_label: str) -> str:
    """Return the inclusive slice between START_MARKER and END_MARKER, or exit."""
    start = content.find(START_MARKER)
    end = content.find(END_MARKER)
    if start < 0 or end < 0 or end < start:
        sys.exit(f"{source_label} missing '{START_MARKER}' / '{END_MARKER}' markers")
    return content[start : end + len(END_MARKER)]


ATX_HEADING = re.compile(r"#{1,6}\s+\S")
RULE_LEAD_IN = re.compile(r"\*\*(.+?)\*\*")


def block_sections(block: str) -> list[str]:
    """Return the section markers in a marker block, ignoring fenced code.

    Markers are ATX headings and the bold label that opens each template rule.
    Only the label is returned for a lead-in, so reworded prose after it is not a
    new section. Setext headings are not recognized.
    """
    sections = []
    in_fence = False
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if ATX_HEADING.match(stripped):
            sections.append(stripped)
            continue
        lead_in = RULE_LEAD_IN.match(stripped)
        if lead_in:
            sections.append(f"**{lead_in.group(1)}**")
    return sections


def custom_sections(current_block: str, template_block: str) -> list[str]:
    """Section markers in the project's marker block that the template lacks.

    These are sections a user added inside the markers, which an upgrade would
    silently delete. Reworded template prose is not flagged, only new sections.
    """
    known = set(block_sections(template_block))
    found = []
    for section in block_sections(current_block):
        if section not in known and section not in found:
            found.append(section)
    return found


def merge_agents_md(path: pathlib.Path, full_content: str) -> None:
    """Create AGENTS.md, or offer to append memory section to an existing one.

    The memory section in the template is delimited by HTML-comment markers
    so future template growth (extra sections after it) won't leak into the
    appended slice. Detection of "already present" uses the heading text, so
    a hand-added section without markers is also recognized.
    """
    heading = "## Project memory"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, full_content)
        print(f"wrote {path}")
        return
    existing = read_text(path)
    if heading in existing:
        print(f"skipped {path} (memory section already present)")
        return
    if not confirm(f"{path} exists. Append '{heading}' section to the end? [y/N]: "):
        print(
            f"skipped {path} - add the memory section manually if you want agents to read these rules"
        )
        return
    memory_section = extract_memory_block(full_content, "AGENTS.md template")
    new = existing.rstrip() + "\n\n" + memory_section.strip() + "\n"
    write_text(path, new)
    print(f"appended memory section to {path}")


def upgrade_agents_md(
    project_root: pathlib.Path, templates_dir: pathlib.Path, force: bool = False
) -> bool:
    """Replace the marker block in project AGENTS.md with the template's contents.

    Exits non-zero if the block holds sections the template does not have, unless
    force is set. Returns True when the block is current afterwards, False when
    the user declined.
    """
    project_agents = project_root / "AGENTS.md"
    if not project_agents.is_file():
        sys.exit(
            f"AGENTS.md not found at {project_agents} - run bootstrap to create it first"
        )
    template_agents = templates_dir / "AGENTS.md"
    if not template_agents.is_file():
        sys.exit(f"template AGENTS.md not found: {template_agents}")

    existing = read_text(project_agents)
    template = read_text(template_agents)
    current_block = extract_memory_block(existing, str(project_agents))
    new_block = extract_memory_block(template, str(template_agents))

    if current_block == new_block:
        print(f"AGENTS.md is already current ({project_agents})")
        return True

    custom = custom_sections(current_block, new_block)
    if custom and not force:
        sections = "\n".join(f"  {section}" for section in custom)
        sys.exit(
            f"refusing to upgrade {project_agents}: the marker block holds "
            f"sections the template does not have, and replacing the block "
            f"would delete them:\n\n{sections}\n\n"
            f"Move them below '{END_MARKER}' - content outside the markers is "
            f"preserved - then re-run. Pass --force to replace the block anyway."
        )

    diff = "".join(
        difflib.unified_diff(
            current_block.splitlines(keepends=True),
            new_block.splitlines(keepends=True),
            fromfile="current",
            tofile="template",
        )
    )
    print(colorize_diff(diff), end="")
    if not confirm(f"\nReplace marker block in {project_agents}? [y/N]: "):
        print("aborted")
        return False
    write_text(project_agents, existing.replace(current_block, new_block, 1))
    print(f"updated {project_agents}")
    return True


def load_plans_readmes(templates_dir: pathlib.Path) -> dict[pathlib.Path, str]:
    """Render the docs/plans READMEs, keyed by path relative to the project root."""
    return {
        pathlib.Path("docs/plans") / subdir / "README.md": load_template(
            templates_dir, f"plans-{subdir}-readme.md"
        )
        for subdir in PLANS_SUBDIRS
    }


def write_plans_readmes(
    project_root: pathlib.Path, readmes: dict[pathlib.Path, str]
) -> None:
    """Write the docs/plans READMEs, creating parent directories as needed.

    Idempotent: an existing README is left untouched rather than treated as a
    conflict, so --upgrade can add the layout to an already-bootstrapped repo.
    """
    for relpath, content in readmes.items():
        target = project_root / relpath
        if target.is_file():
            print(f"skipped {target} (already exists)")
            continue
        if target.exists():
            sys.exit(f"not a regular file, refusing to continue: {target}")
        ensure_directory(target.parent)
        write_text(target, content)
        print(f"wrote {target}")


def merge_claude_md(path: pathlib.Path, full_content: str) -> None:
    """Create CLAUDE.md, or offer to prepend the import line to an existing one."""
    import_line = full_content.strip()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text(path, full_content)
        print(f"wrote {path}")
        return
    existing = read_text(path)
    if import_line in existing:
        print(f"skipped {path} ({import_line} already imported)")
        return
    if not confirm(f"{path} exists. Prepend '{import_line}' to the top? [y/N]: "):
        print(
            f"skipped {path} - add '{import_line}' manually so Claude Code reads memory rules"
        )
        return
    new = import_line + "\n\n" + existing
    write_text(path, new)
    print(f"prepended {import_line} to {path}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Bootstrap a project memory system.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "name", nargs="?", help="Project name (not required with --upgrade)"
    )
    ap.add_argument(
        "description",
        nargs="?",
        help="One-line project description (not required with --upgrade)",
    )
    ap.add_argument(
        "--project",
        default=".",
        help="Project root directory (default: current directory)",
    )
    ap.add_argument(
        "--author",
        default=None,
        help="Memory-entry author (default: git config user.name in the project, or 'unknown')",
    )
    ap.add_argument(
        "--templates-dir",
        default=None,
        help="Directory containing template .md files (default: templates/ next to this script)",
    )
    ap.add_argument(
        "--upgrade",
        action="store_true",
        help="Re-sync the AGENTS.md marker block to the current template and create any missing docs/plans directories",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="With --upgrade, replace the marker block even when it holds sections the template does not have",
    )
    args = ap.parse_args()

    if args.force and not args.upgrade:
        ap.error("--force is only valid with --upgrade")

    project_root = pathlib.Path(args.project).resolve()
    if not project_root.is_dir():
        sys.exit(f"project directory does not exist: {project_root}")

    templates_dir = (
        pathlib.Path(args.templates_dir).resolve()
        if args.templates_dir
        else pathlib.Path(__file__).resolve().parent / "templates"
    )
    if not templates_dir.is_dir():
        sys.exit(f"templates directory does not exist: {templates_dir}")

    if args.upgrade:
        plans_readmes = load_plans_readmes(templates_dir)
        if upgrade_agents_md(project_root, templates_dir, force=args.force):
            write_plans_readmes(project_root, plans_readmes)
        return

    if not args.name or not args.description:
        ap.error("name and description are required unless --upgrade is set")

    today = datetime.date.today().isoformat()
    author = args.author or git_user_name(project_root)

    # Render all templates.
    agents_md = load_template(
        templates_dir, "AGENTS.md", name=args.name, desc=args.description
    )
    claude_md = load_template(templates_dir, "CLAUDE.md")
    memory_index = load_template(
        templates_dir, "memory-index.md", name=args.name, today=today
    )
    product = load_template(
        templates_dir,
        "product.md",
        desc=args.description,
        author=author,
        today=today,
    )
    architecture = load_template(
        templates_dir,
        "architecture.md",
        name=args.name,
        author=author,
        today=today,
    )
    bootstrap_log = load_template(
        templates_dir, "bootstrap-log.md", author=author, today=today
    )
    plans_readmes = load_plans_readmes(templates_dir)

    memory_files = {
        pathlib.Path("docs/memory/memory-index.md"): memory_index,
        pathlib.Path("docs/memory/product.md"): product,
        pathlib.Path("docs/memory/architecture.md"): architecture,
        pathlib.Path(f"docs/memory/log/{today}-bootstrap.md"): bootstrap_log,
    }

    # Pre-flight: bail before any prompts if a memory file already exists.
    # Without this, the user could answer prompts and then we'd abort partway.
    for relpath in memory_files:
        target = project_root / relpath
        if target.exists():
            sys.exit(f"refusing to overwrite existing file: {target}")

    for relpath in (*memory_files, *plans_readmes):
        target = project_root / relpath
        blocker = blocking_non_directory(target.parent)
        if blocker is not None:
            sys.exit(
                f"cannot create directory {target.parent}: {blocker} exists and "
                f"is not a directory. Move or remove it, then re-run."
            )
        if target.exists() and not target.is_file():
            sys.exit(f"not a regular file, refusing to continue: {target}")

    # Root files: create new, or interactively offer to merge into existing.
    merge_agents_md(project_root / "AGENTS.md", agents_md)
    merge_claude_md(project_root / "CLAUDE.md", claude_md)

    # Memory files: write fresh (pre-flight guaranteed no conflicts).
    for relpath, content in memory_files.items():
        write_file(project_root / relpath, content)

    write_plans_readmes(project_root, plans_readmes)

    print()
    print(f"Done. Bootstrapped memory system in {project_root}")
    print("Next steps:")
    print(
        "  1. Fill in <placeholder> strings in docs/memory/product.md and docs/memory/architecture.md"
    )
    print("  2. Commit as a single commit (e.g. 'Bootstrap project memory system')")


if __name__ == "__main__":
    main()

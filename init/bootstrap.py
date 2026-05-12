#!/usr/bin/env python3
"""Bootstrap the project memory system.

Reads ${var}-substituted markdown templates from the 'templates/' directory next
to this script (override with --templates-dir). Renders them into:

  - AGENTS.md and CLAUDE.md at the project root
  - memory-index.md, product.md, architecture.md, and a dated bootstrap log entry
    under docs/memory/

If AGENTS.md or CLAUDE.md already exist, interactively offers to merge the memory
rules in (append a '## Project memory' section to AGENTS.md; prepend '@AGENTS.md'
to CLAUDE.md). Refuses to overwrite any files under docs/memory/. Safe to re-run
after partial setup.

Usage:
    python3 bootstrap.py "<Project name>" "<One-line description>"
    python3 bootstrap.py --project /path/to/repo "<Project>" "<Description>"

If --project is omitted, the current working directory is used.
"""

import argparse
import datetime
import pathlib
import string
import subprocess
import sys


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


def write_file(path: pathlib.Path, content: str) -> None:
    if path.exists():
        sys.exit(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text(path, content)
    print(f"wrote {path}")


def merge_agents_md(path: pathlib.Path, full_content: str) -> None:
    """Create AGENTS.md, or offer to append memory section to an existing one.

    The memory section in the template is delimited by HTML-comment markers
    so future template growth (extra sections after it) won't leak into the
    appended slice. Detection of "already present" uses the heading text, so
    a hand-added section without markers is also recognized.
    """
    heading = "## Project memory"
    start_marker = "<!-- project-memory:start -->"
    end_marker = "<!-- project-memory:end -->"
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
    start = full_content.find(start_marker)
    end = full_content.find(end_marker)
    if start < 0 or end < 0 or end < start:
        sys.exit(
            f"AGENTS.md template missing '{start_marker}' / '{end_marker}' markers - check templates/AGENTS.md"
        )
    memory_section = full_content[start : end + len(end_marker)]
    new = existing.rstrip() + "\n\n" + memory_section.strip() + "\n"
    write_text(path, new)
    print(f"appended memory section to {path}")


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
    ap.add_argument("name", help="Project name")
    ap.add_argument("description", help="One-line project description")
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
    args = ap.parse_args()

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

    # Root files: create new, or interactively offer to merge into existing.
    merge_agents_md(project_root / "AGENTS.md", agents_md)
    merge_claude_md(project_root / "CLAUDE.md", claude_md)

    # Memory files: write fresh (pre-flight guaranteed no conflicts).
    for relpath, content in memory_files.items():
        write_file(project_root / relpath, content)

    print()
    print(f"Done. Bootstrapped memory system in {project_root}")
    print("Next steps:")
    print(
        "  1. Fill in <placeholder> strings in docs/memory/product.md and docs/memory/architecture.md"
    )
    print("  2. Commit as a single commit (e.g. 'Bootstrap project memory system')")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Bootstrap the project memory system.

Reads ${var}-substituted markdown templates from the 'templates/' directory next
to this script (override with --templates-dir). Renders them into:

  - AGENTS.md and CLAUDE.md at the project root
  - memory-index.md, product.md, architecture.md, and a dated bootstrap log entry
    under docs/memory/
  - a README.md in docs/plans/current/ and docs/plans/archive/
  - a .gitattributes rule giving memory-index.md git's union merge driver

If AGENTS.md, CLAUDE.md or .gitattributes already exist, interactively offers to
merge in (append a '## Project memory' section to AGENTS.md; prepend '@AGENTS.md'
to CLAUDE.md; append the union rule to .gitattributes unless git already applies
a merge attribute to the index). Refuses to overwrite any files under
docs/memory/. Safe to re-run after partial setup.

Usage:
    python3 bootstrap.py "<Project name>" "<One-line description>"
    python3 bootstrap.py --project /path/to/repo "<Project>" "<Description>"
    python3 bootstrap.py --upgrade --project /path/to/repo
    python3 bootstrap.py --upgrade --force --project /path/to/repo

If --project is omitted, the current working directory is used. With --upgrade,
the AGENTS.md marker block is replaced with the current template's contents,
content outside the markers is preserved, and any missing docs/plans/
directories and the .gitattributes rule are added. An upgrade refuses to run
when the marker block holds sections the template does not have, since
replacing it would delete them; --force overrides that.
"""

import argparse
import dataclasses
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
INDEX_PATH = "docs/memory/memory-index.md"


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


def as_sentence(text: str) -> str:
    """Return text with a trailing period unless it already ends in terminal punctuation."""
    text = text.rstrip()
    return text if text.endswith((".", "!", "?")) else f"{text}."


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
    new_block = string.Template(
        extract_memory_block(template, str(template_agents))
    ).substitute(DocsLayout.on_disk(project_root).template_vars())

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


def load_plans_readmes(
    templates_dir: pathlib.Path, layout: "DocsLayout"
) -> dict[pathlib.Path, str]:
    """Render the plans READMEs, keyed by their layout path relative to the project root."""
    names = layout.template_vars()
    return {
        pathlib.Path(layout.current_readme): load_template(
            templates_dir, "plans-current-readme.md", **names
        ),
        pathlib.Path(layout.archive_readme): load_template(
            templates_dir, "plans-archive-readme.md", **names
        ),
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


def check_gitattributes(project_root: pathlib.Path) -> None:
    """Exit if .gitattributes is a symlink (dangling included) or not a regular file."""
    path = project_root / ".gitattributes"
    if path.is_symlink() or (path.exists() and not path.is_file()):
        sys.exit(f"not a regular file, refusing to continue: {path}")


def on_disk_path(project_root: pathlib.Path, relpath: str) -> str:
    """relpath spelled as the directories on disk spell it, since git on Linux matches case exactly.

    A component matches exactly or ASCII case-insensitively. The spelling that reaches deepest
    into existing directories wins, then an exact match, then the first sorted name.
    Components below the deepest match keep relpath's spelling.
    """
    return "/".join(_spell_below(project_root, relpath.split("/"))[1])


def _spell_below(directory: pathlib.Path, parts: list[str]) -> tuple[int, list[str]]:
    """(components matched, spelling) of parts under directory; -1 when it is not a directory."""
    if not parts:
        return 0, []
    try:
        names = os.listdir(directory)
    except OSError:
        return -1, parts
    head, rest = parts[0], parts[1:]
    candidates = [head] if head in names else []
    candidates += sorted(
        n for n in names if n != head and n.isascii() and n.lower() == head.lower()
    )
    best = (0, parts)
    for name in candidates:
        depth, tail = _spell_below(directory / name, rest)
        if depth + 1 > best[0]:
            best = (depth + 1, [name, *tail])
    return best


def _under(
    project_root: pathlib.Path, base: pathlib.PurePosixPath, name: str
) -> pathlib.PurePosixPath:
    return base / on_disk_path(project_root / base, name)


@dataclasses.dataclass(frozen=True)
class DocsLayout:
    """Where each generated file goes, relative to the project root and spelled as on disk.

    The index is resolved first. Every other path is resolved under the directories it chose,
    so the files of one project never land in two differently spelled trees.
    """

    index: pathlib.PurePosixPath
    product: pathlib.PurePosixPath
    architecture: pathlib.PurePosixPath
    log_dir: pathlib.PurePosixPath
    current_readme: pathlib.PurePosixPath
    archive_readme: pathlib.PurePosixPath

    @classmethod
    def on_disk(cls, project_root: pathlib.Path) -> "DocsLayout":
        index = pathlib.PurePosixPath(on_disk_path(project_root, INDEX_PATH))
        memory = index.parent
        plans = _under(project_root, memory.parent, "plans")
        current = _under(project_root, plans, "current")
        archive = _under(project_root, plans, "archive")
        return cls(
            index=index,
            product=_under(project_root, memory, "product.md"),
            architecture=_under(project_root, memory, "architecture.md"),
            log_dir=_under(project_root, memory, "log"),
            current_readme=_under(project_root, current, "README.md"),
            archive_readme=_under(project_root, archive, "README.md"),
        )

    @property
    def plans_current(self) -> pathlib.PurePosixPath:
        return self.current_readme.parent

    @property
    def plans_archive(self) -> pathlib.PurePosixPath:
        return self.archive_readme.parent

    def log_entry(
        self, project_root: pathlib.Path, filename: str
    ) -> pathlib.PurePosixPath:
        return _under(project_root, self.log_dir, filename)

    def template_vars(self) -> dict[str, str]:
        """The ${...} substitutions templates use to link to these paths."""
        return {
            "memory_dir": str(self.index.parent),
            "index_path": str(self.index),
            "product_path": str(self.product),
            "architecture_path": str(self.architecture),
            "log_name": self.log_dir.name,
            "plans_current": str(self.plans_current),
            "plans_archive": str(self.plans_archive),
            "current_name": self.plans_current.name,
            "archive_name": self.plans_archive.name,
        }


def union_rule(index: str) -> str:
    return f"{index} merge=union"


def index_merge_attribute(project_root: pathlib.Path, index: str) -> str | None:
    """The merge attribute git applies to the index, or None when git cannot say.

    Returns git's own value: 'unspecified', 'set', 'unset', or a driver name.
    Global attributes are excluded, since they do not travel with the repo.
    Matching is case-sensitive, as on Linux, so a rule that only matches on macOS does not count.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                f"core.attributesFile={os.devnull}",
                "-c",
                "core.ignorecase=false",
                "check-attr",
                "-z",
                "merge",
                "--",
                index,
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=project_root,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    # -z output is <path> NUL <attribute> NUL <value> NUL.
    fields = result.stdout.split("\0")
    return fields[2] if len(fields) >= 3 else None


def has_union_rule(content: bytes, rule: str) -> bool:
    """True if a line is exactly rule. Idempotence only; git decides precedence."""
    text = content.decode("utf-8", errors="surrogateescape")
    return any(line.split() == rule.split() for line in text.splitlines())


def merge_gitattributes(project_root: pathlib.Path, index: str) -> None:
    """Create .gitattributes with the union rule, or offer to append it to an existing one.

    Leaves the file alone when git already applies a merge attribute to the
    index, so an explicit choice in the repo is never overridden.
    """
    path = project_root / ".gitattributes"
    existing = path.read_bytes() if path.exists() else None
    rule = union_rule(index)
    current = index_merge_attribute(project_root, index)
    if current == "union":
        print(f"skipped {path} (union merge already applies to {index})")
        return
    if current not in (None, "unspecified"):
        print(
            f"skipped {path} - git already applies 'merge: {current}' to "
            f"{index}; change it to merge=union by hand if you want that"
        )
        return
    if existing is not None and has_union_rule(existing, rule):
        if current is None:
            print(f"skipped {path} ({rule} already present)")
        else:
            print(
                f"skipped {path} - {rule} is present but git reports "
                f"'merge: unspecified' for {index}, so another rule "
                f"overrides it; fix that rule by hand if you want union merges"
            )
        return
    if existing is None:
        with path.open("xb") as f:
            f.write(rule.encode("utf-8") + b"\n")
        print(f"wrote {path}")
        return
    if not confirm(f"{path} exists. Append '{rule}'? [y/N]: "):
        print(
            f"skipped {path} - add '{rule}' manually so concurrent log "
            f"entries do not conflict"
        )
        return
    eol = b"\r\n" if b"\r\n" in existing else b"\n"
    separator = eol if existing and not existing.endswith(b"\n") else b""
    with path.open("ab") as f:
        f.write(separator + rule.encode("utf-8") + eol)
    print(f"appended {rule} to {path}")


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
        help="Re-sync the AGENTS.md marker block to the current template, create any missing docs/plans directories, and add the .gitattributes rule",
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

    check_gitattributes(project_root)

    if args.upgrade:
        layout = DocsLayout.on_disk(project_root)
        plans_readmes = load_plans_readmes(templates_dir, layout)
        if upgrade_agents_md(project_root, templates_dir, force=args.force):
            write_plans_readmes(project_root, plans_readmes)
            merge_gitattributes(project_root, layout.index.as_posix())
        return

    if not args.name or not args.description:
        ap.error("name and description are required unless --upgrade is set")

    today = datetime.date.today().isoformat()
    layout = DocsLayout.on_disk(project_root)
    paths = layout.template_vars()
    author = args.author or git_user_name(project_root)

    # Render all templates.
    agents_md = load_template(
        templates_dir,
        "AGENTS.md",
        name=args.name,
        desc=args.description,
        desc_sentence=as_sentence(args.description),
        **paths,
    )
    claude_md = load_template(templates_dir, "CLAUDE.md")
    memory_index = load_template(
        templates_dir, "memory-index.md", name=args.name, today=today, **paths
    )
    product = load_template(
        templates_dir,
        "product.md",
        desc=args.description,
        desc_sentence=as_sentence(args.description),
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
        templates_dir, "bootstrap-log.md", author=author, today=today, **paths
    )
    plans_readmes = load_plans_readmes(templates_dir, layout)

    memory_files = {
        pathlib.Path(layout.index): memory_index,
        pathlib.Path(layout.product): product,
        pathlib.Path(layout.architecture): architecture,
        pathlib.Path(
            layout.log_entry(project_root, f"{today}-bootstrap.md")
        ): bootstrap_log,
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
    merge_gitattributes(project_root, layout.index.as_posix())

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

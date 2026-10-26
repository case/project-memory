"""Unit tests for init/bootstrap.py.

Run from the repo root:
    python3 -m unittest discover tests
"""

import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOTSTRAP_PY = REPO_ROOT / "init" / "bootstrap.py"
GIT_ENV: dict[str, str] = {}
_sandbox_home: tempfile.TemporaryDirectory | None = None


def setUpModule() -> None:
    """Run every git and bootstrap subprocess with no access to the developer's git config."""
    global _sandbox_home
    _sandbox_home = tempfile.TemporaryDirectory()
    home = _sandbox_home.name
    GIT_ENV.clear()
    GIT_ENV.update(
        {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "XDG_"))}
    )
    GIT_ENV.update(
        HOME=home,
        XDG_CONFIG_HOME=os.path.join(home, ".config"),
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="t",
        GIT_AUTHOR_EMAIL="t@example.com",
        GIT_COMMITTER_NAME="t",
        GIT_COMMITTER_EMAIL="t@example.com",
    )


def tearDownModule() -> None:
    if _sandbox_home is not None:
        _sandbox_home.cleanup()


def git(
    cwd: pathlib.Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess:
    """Run git in cwd under the sandboxed environment."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=check,
    )


def _load_bootstrap():
    """Import bootstrap.py by path so its pure functions can be tested directly."""
    spec = importlib.util.spec_from_file_location("bootstrap", BOOTSTRAP_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bootstrap = _load_bootstrap()
TEMPLATE_BLOCK = bootstrap.extract_memory_block(
    (REPO_ROOT / "init/templates/AGENTS.md").read_text(encoding="utf-8"),
    "template",
)


def block(body: str) -> str:
    """Wrap body in the marker pair, as extract_memory_block would return it."""
    return f"<!-- project-memory:start -->\n\n{body}\n\n<!-- project-memory:end -->"


def run_bootstrap(
    project_dir: pathlib.Path,
    *,
    name: str = "TestProj",
    desc: str = "Test description",
    author: str = "testuser",
    input_text: str = "",
    force: bool = False,
) -> subprocess.CompletedProcess:
    """Invoke bootstrap.py against project_dir as a subprocess."""
    cmd = [
        sys.executable,
        str(BOOTSTRAP_PY),
        name,
        desc,
        "--project",
        str(project_dir),
        "--author",
        author,
    ]
    if force:
        cmd.append("--force")
    return subprocess.run(
        cmd, input=input_text, capture_output=True, text=True, env=GIT_ENV
    )


def run_upgrade(
    project_dir: pathlib.Path,
    *,
    input_text: str = "",
    templates_dir: pathlib.Path | None = None,
    force: bool = False,
) -> subprocess.CompletedProcess:
    """Invoke bootstrap.py --upgrade against project_dir as a subprocess."""
    cmd = [
        sys.executable,
        str(BOOTSTRAP_PY),
        "--upgrade",
        "--project",
        str(project_dir),
    ]
    if force:
        cmd.append("--force")
    if templates_dir is not None:
        cmd.extend(["--templates-dir", str(templates_dir)])
    return subprocess.run(
        cmd, input=input_text, capture_output=True, text=True, env=GIT_ENV
    )


class TestFreshProject(unittest.TestCase):
    """Bootstrapping a clean target directory creates every generated file."""

    def test_creates_all_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            result = run_bootstrap(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((tmpdir / "AGENTS.md").is_file())
            self.assertTrue((tmpdir / "CLAUDE.md").is_file())
            self.assertTrue((tmpdir / "docs/memory/memory-index.md").is_file())
            self.assertTrue((tmpdir / "docs/memory/product.md").is_file())
            self.assertTrue((tmpdir / "docs/memory/architecture.md").is_file())
            log_files = list((tmpdir / "docs/memory/log").iterdir())
            self.assertEqual(len(log_files), 1)
            self.assertTrue(log_files[0].name.endswith("-bootstrap.md"))
            self.assertTrue((tmpdir / "docs/plans/current/README.md").is_file())
            self.assertTrue((tmpdir / "docs/plans/archive/README.md").is_file())
            self.assertEqual(
                (tmpdir / ".gitattributes").read_bytes(),
                b"docs/memory/memory-index.md merge=union\n",
            )


def stale_agents_md(extra: str = "") -> str:
    """A marker block whose contents differ from the current template."""
    return (
        "# MyProj\n\n"
        "<!-- project-memory:start -->\n"
        "## Project memory\n\nOLD\n"
        f"{extra}"
        "<!-- project-memory:end -->\n\n"
        "## Outside section\n\nSafe.\n"
    )


class TestBlockSections(unittest.TestCase):
    """Section detection decides what an upgrade may silently delete."""

    def test_template_rules_are_all_recognized(self):
        sections = bootstrap.block_sections(TEMPLATE_BLOCK)
        self.assertIn("## Project memory", sections)
        for label in ("**Before suggesting**", "**Plans**", "**Monorepos**"):
            self.assertIn(label, sections)

    def test_detects_a_rule_added_in_the_templates_own_bold_style(self):
        added = block("## Project memory\n\n**Formatting**: dprint owns markdown.")
        self.assertEqual(
            bootstrap.custom_sections(added, TEMPLATE_BLOCK), ["**Formatting**"]
        )

    def test_detects_an_added_heading(self):
        added = block("## Project memory\n\n## Formatting: dprint owns markdown")
        self.assertEqual(
            bootstrap.custom_sections(added, TEMPLATE_BLOCK),
            ["## Formatting: dprint owns markdown"],
        )

    def test_detects_headings_with_extra_space_or_a_tab(self):
        for spacer in ("  ", "\t"):
            added = block(f"## Project memory\n\n##{spacer}Custom Section")
            self.assertEqual(
                bootstrap.custom_sections(added, TEMPLATE_BLOCK),
                [f"##{spacer}Custom Section"],
            )

    def test_reworded_rule_prose_is_not_a_new_section(self):
        reworded = block("## Project memory\n\n**Plans**: entirely different wording.")
        self.assertEqual(bootstrap.custom_sections(reworded, TEMPLATE_BLOCK), [])

    def test_bold_inside_a_sentence_is_not_a_section(self):
        prose = block("## Project memory\n\nSome text with **bold** inside it.")
        self.assertEqual(bootstrap.custom_sections(prose, TEMPLATE_BLOCK), [])

    def test_fenced_example_markdown_is_ignored(self):
        fenced = block(
            "## Project memory\n\n```md\n## Fake Heading\n**Fake**: rule\n```"
        )
        self.assertEqual(bootstrap.custom_sections(fenced, TEMPLATE_BLOCK), [])

    def test_repeated_custom_section_is_reported_once(self):
        twice = block("## Custom\n\ntext\n\n## Custom\n\nmore")
        self.assertEqual(
            bootstrap.custom_sections(twice, TEMPLATE_BLOCK), ["## Custom"]
        )

    def test_an_unmodified_block_has_no_custom_sections(self):
        self.assertEqual(bootstrap.custom_sections(TEMPLATE_BLOCK, TEMPLATE_BLOCK), [])


class TestForceFlagScope(unittest.TestCase):
    """--force is meaningful only with --upgrade."""

    def test_rejected_without_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            result = run_bootstrap(tmpdir, force=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--force is only valid with --upgrade", result.stderr)

    def test_rejected_before_anything_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            run_bootstrap(tmpdir, force=True)
            self.assertFalse((tmpdir / "AGENTS.md").exists())
            self.assertFalse((tmpdir / "docs").exists())


class TestUpgradeCustomSectionGuard(unittest.TestCase):
    """--upgrade refuses to delete sections the template does not have."""

    CUSTOM = "\n## Formatting: dprint owns markdown\n\nHand-written rules.\n"

    def test_refuses_and_names_the_custom_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            original = stale_agents_md(self.CUSTOM)
            (tmpdir / "AGENTS.md").write_text(original, encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("## Formatting: dprint owns markdown", result.stderr)
            self.assertIn("--force", result.stderr)
            self.assertEqual(
                (tmpdir / "AGENTS.md").read_text(encoding="utf-8"), original
            )

    def test_refusal_creates_no_plans_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "AGENTS.md").write_text(
                stale_agents_md(self.CUSTOM), encoding="utf-8"
            )
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((tmpdir / "docs/plans").exists())

    def test_force_replaces_the_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "AGENTS.md").write_text(
                stale_agents_md(self.CUSTOM), encoding="utf-8"
            )
            result = run_upgrade(tmpdir, input_text="y\n", force=True)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = (tmpdir / "AGENTS.md").read_text(encoding="utf-8")
            self.assertNotIn("Hand-written rules.", content)
            self.assertIn("Project memory lives in", content)
            self.assertIn("## Outside section", content)

    def test_force_still_prompts_and_honors_decline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            original = stale_agents_md(self.CUSTOM)
            (tmpdir / "AGENTS.md").write_text(original, encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="n\n", force=True)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(
                (tmpdir / "AGENTS.md").read_text(encoding="utf-8"), original
            )

    def test_refuses_a_rule_added_in_the_templates_bold_style(self):
        """The block teaches **Bold**: rules, so that is the likely custom shape."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            custom = "\n**Formatting**: dprint owns markdown, JSON and TOML.\n"
            original = stale_agents_md(custom)
            (tmpdir / "AGENTS.md").write_text(original, encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("**Formatting**", result.stderr)
            self.assertEqual(
                (tmpdir / "AGENTS.md").read_text(encoding="utf-8"), original
            )

    def test_stale_block_without_extra_sections_still_upgrades(self):
        """Reworded template prose is not mistaken for user content."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "AGENTS.md").write_text(stale_agents_md(), encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn(
                "Project memory lives in",
                (tmpdir / "AGENTS.md").read_text(encoding="utf-8"),
            )

    def test_heading_inside_a_code_fence_is_not_a_custom_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            fenced = "\n```markdown\n## Not a real heading\n```\n"
            (tmpdir / "AGENTS.md").write_text(stale_agents_md(fenced), encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)


class TestPlansDirs(unittest.TestCase):
    """docs/plans/current/ and docs/plans/archive/ scaffolding."""

    def test_bootstrap_seeds_each_plans_readme_from_its_own_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            result = run_bootstrap(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            current = (tmpdir / "docs/plans/current/README.md").read_text(
                encoding="utf-8"
            )
            archive = (tmpdir / "docs/plans/archive/README.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("../archive/", current)
            self.assertIn("../current/", archive)
            self.assertNotEqual(current, archive)

    def test_bootstrap_leaves_existing_plans_readme_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            existing = "# My own plans notes\n"
            target = tmpdir / "docs/plans/current/README.md"
            target.parent.mkdir(parents=True)
            target.write_text(existing, encoding="utf-8")
            result = run_bootstrap(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(target.read_text(encoding="utf-8"), existing)
            self.assertIn("already exists", result.stdout)
            self.assertTrue((tmpdir / "docs/plans/archive/README.md").is_file())

    def test_upgrade_creates_missing_plans_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            stale = (
                "<!-- project-memory:start -->\n"
                "## Project memory\n\nOLD\n"
                "<!-- project-memory:end -->\n"
            )
            (tmpdir / "AGENTS.md").write_text(stale, encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((tmpdir / "docs/plans/current/README.md").is_file())
            self.assertTrue((tmpdir / "docs/plans/archive/README.md").is_file())

    def test_upgrade_creates_plans_dirs_when_agents_md_already_current(self):
        """The block being current still means the repo predates docs/plans/."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            bootstrap_result = run_bootstrap(tmpdir)
            self.assertEqual(
                bootstrap_result.returncode, 0, msg=bootstrap_result.stderr
            )
            for subdir in ("current", "archive"):
                (tmpdir / "docs/plans" / subdir / "README.md").unlink()
            result = run_upgrade(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("already current", result.stdout)
            self.assertTrue((tmpdir / "docs/plans/current/README.md").is_file())
            self.assertTrue((tmpdir / "docs/plans/archive/README.md").is_file())

    def test_upgrade_creates_nothing_when_user_declines(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            stale = (
                "<!-- project-memory:start -->\n"
                "## Project memory\n\nOLD\n"
                "<!-- project-memory:end -->\n"
            )
            (tmpdir / "AGENTS.md").write_text(stale, encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="n\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertFalse((tmpdir / "docs/plans").exists())

    def test_upgrade_errors_when_plans_template_missing(self):
        """A stale --templates-dir fails before AGENTS.md is touched."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            templates = tmpdir / "templates"
            templates.mkdir()
            real_templates = REPO_ROOT / "init" / "templates"
            (templates / "AGENTS.md").write_text(
                (real_templates / "AGENTS.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            project = tmpdir / "proj"
            project.mkdir()
            stale = (
                "<!-- project-memory:start -->\n"
                "## Project memory\n\nOLD\n"
                "<!-- project-memory:end -->\n"
            )
            (project / "AGENTS.md").write_text(stale, encoding="utf-8")
            result = run_upgrade(project, input_text="y\n", templates_dir=templates)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing template file", result.stderr)
            self.assertEqual((project / "AGENTS.md").read_text(encoding="utf-8"), stale)


class TestDirectoryCollisions(unittest.TestCase):
    """A file where a directory belongs produces a message, not a traceback."""

    def assert_clean_exit(self, result, blocker: pathlib.Path):
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("cannot create directory", result.stderr)
        self.assertIn(str(blocker), result.stderr)

    def assert_nothing_written(self, project_dir: pathlib.Path, blocker: pathlib.Path):
        """The pre-flight contract: bail before prompts, leaving no partial state.

        The blocker is the fixture's own file, so it is excluded from the check.
        """
        for generated in (
            ".gitattributes",
            "AGENTS.md",
            "CLAUDE.md",
            "docs/memory/memory-index.md",
            "docs/memory/product.md",
            "docs/memory/architecture.md",
            "docs/plans/current/README.md",
            "docs/plans/archive/README.md",
        ):
            target = project_dir / generated
            if target == blocker or blocker in target.parents:
                continue
            self.assertFalse(target.exists(), msg=generated)

    def test_names_the_plans_leaf_when_it_is_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            blocker = tmpdir / "docs/plans/current"
            blocker.parent.mkdir(parents=True)
            blocker.write_text("not a directory", encoding="utf-8")
            result = run_bootstrap(tmpdir)
            self.assert_clean_exit(result, blocker)
            self.assert_nothing_written(tmpdir, blocker)

    def test_names_the_blocking_ancestor_not_the_leaf(self):
        """docs/plans is the file; naming docs/plans/current would misdirect."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            blocker = tmpdir / "docs/plans"
            blocker.parent.mkdir(parents=True)
            blocker.write_text("not a directory", encoding="utf-8")
            result = run_bootstrap(tmpdir)
            self.assert_clean_exit(result, blocker)
            self.assert_nothing_written(tmpdir, blocker)

    def test_names_the_blocker_for_memory_files_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            blocker = tmpdir / "docs/memory"
            blocker.parent.mkdir(parents=True)
            blocker.write_text("not a directory", encoding="utf-8")
            result = run_bootstrap(tmpdir)
            self.assert_clean_exit(result, blocker)
            self.assert_nothing_written(tmpdir, blocker)

    def test_readme_path_that_is_a_directory_is_refused(self):
        """A directory named README.md must error, not read as 'already exists'."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            blocker = tmpdir / "docs/plans/current/README.md"
            blocker.mkdir(parents=True)
            result = run_bootstrap(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a regular file", result.stderr)
            self.assert_nothing_written(tmpdir, blocker)

    def test_recovers_after_the_blocker_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            blocker = tmpdir / "docs/plans"
            blocker.parent.mkdir(parents=True)
            blocker.write_text("not a directory", encoding="utf-8")
            self.assertNotEqual(run_bootstrap(tmpdir).returncode, 0)
            blocker.unlink()
            result = run_bootstrap(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((tmpdir / "docs/plans/current/README.md").is_file())
            self.assertTrue((tmpdir / "docs/memory/product.md").is_file())

    def test_upgrade_reports_the_blocker_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "AGENTS.md").write_text(stale_agents_md(), encoding="utf-8")
            blocker = tmpdir / "docs/plans/current"
            blocker.parent.mkdir(parents=True)
            blocker.write_text("not a directory", encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assert_clean_exit(result, blocker)


RULE = b"docs/memory/memory-index.md merge=union"


def bootstrapped_git_repo(tmpdir: pathlib.Path) -> pathlib.Path:
    """A git repo bootstrapped without .gitattributes, so each test sets its own."""
    git(tmpdir, "init", "-q", "-b", "main")
    result = run_bootstrap(tmpdir)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    (tmpdir / ".gitattributes").unlink()
    return tmpdir


class TestGitattributesRefusal(unittest.TestCase):
    """A .gitattributes that cannot be safely written stops the run before any change."""

    def make_blocker(self, tmpdir: pathlib.Path, label: str) -> None:
        target = tmpdir / ".gitattributes"
        if label == "directory":
            target.mkdir()
        else:
            dest = "elsewhere.txt" if label == "symlink" else "missing"
            target.symlink_to(tmpdir / dest)

    def test_bootstrap_refuses_before_writing(self):
        for label in ("directory", "symlink", "dangling symlink"):
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tmpdir = pathlib.Path(tmp)
                (tmpdir / "elsewhere.txt").write_text("outside\n", encoding="utf-8")
                self.make_blocker(tmpdir, label)
                result = run_bootstrap(tmpdir)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("not a regular file", result.stderr)
                self.assertFalse((tmpdir / "AGENTS.md").exists())
                self.assertFalse((tmpdir / "docs").exists())
                self.assertFalse((tmpdir / "missing").exists())
                self.assertEqual(
                    (tmpdir / "elsewhere.txt").read_text(encoding="utf-8"),
                    "outside\n",
                )

    def test_upgrade_refuses_before_touching_agents_md(self):
        for label in ("directory", "symlink", "dangling symlink"):
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                tmpdir = pathlib.Path(tmp)
                (tmpdir / "elsewhere.txt").write_text("outside\n", encoding="utf-8")
                original = stale_agents_md()
                (tmpdir / "AGENTS.md").write_text(original, encoding="utf-8")
                self.make_blocker(tmpdir, label)
                result = run_upgrade(tmpdir, input_text="y\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not a regular file", result.stderr)
                self.assertNotIn("Replace marker block", result.stdout)
                self.assertEqual(
                    (tmpdir / "AGENTS.md").read_text(encoding="utf-8"), original
                )
                self.assertFalse((tmpdir / "docs").exists())
                self.assertFalse((tmpdir / "missing").exists())


class TestGitattributesMerge(unittest.TestCase):
    """The union rule is added once, appended byte-safely, and never overrides a choice."""

    def run_with_existing(
        self, content: bytes, input_text: str, *, in_git: bool
    ) -> tuple[subprocess.CompletedProcess, bytes]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tmpdir = pathlib.Path(tmp.name)
        if in_git:
            git(tmpdir, "init", "-q", "-b", "main")
        (tmpdir / ".gitattributes").write_bytes(content)
        result = run_bootstrap(tmpdir, input_text=input_text)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return result, (tmpdir / ".gitattributes").read_bytes()

    def test_appends_when_confirmed(self):
        for in_git in (False, True):
            with self.subTest(in_git=in_git):
                existing = b"* text=auto eol=lf\n"
                result, after = self.run_with_existing(existing, "y\n", in_git=in_git)
                self.assertEqual(after, existing + RULE + b"\n")
                self.assertIn("appended", result.stdout)

    def test_leaves_file_alone_when_declined(self):
        existing = b"* text=auto eol=lf\n"
        result, after = self.run_with_existing(existing, "", in_git=True)
        self.assertEqual(after, existing)
        self.assertIn(
            "add 'docs/memory/memory-index.md merge=union' manually", result.stdout
        )

    def test_adds_a_newline_when_the_file_lacks_one(self):
        _, after = self.run_with_existing(b"*.png binary", "y\n", in_git=True)
        self.assertEqual(after, b"*.png binary\n" + RULE + b"\n")

    def test_empty_file_gets_no_leading_blank_line(self):
        _, after = self.run_with_existing(b"", "y\n", in_git=True)
        self.assertEqual(after, RULE + b"\n")

    def test_crlf_file_keeps_crlf_and_its_bytes(self):
        existing = b"# caf\xe9 latin-1 comment\r\n* text=auto\r\n"
        _, after = self.run_with_existing(existing, "y\n", in_git=True)
        self.assertEqual(after, existing + RULE + b"\r\n")

    def test_existing_rule_is_not_duplicated(self):
        for in_git in (False, True):
            with self.subTest(in_git=in_git):
                existing = b"*.md text\ndocs/memory/memory-index.md \t merge=union\n"
                result, after = self.run_with_existing(existing, "", in_git=in_git)
                self.assertEqual(after, existing)
                self.assertNotIn("Append", result.stdout)

    def test_equivalent_rule_found_by_git_is_not_duplicated(self):
        for existing in (
            b'"docs/memory/memory-index.md" merge=union\n',
            b"/docs/memory/memory-index.md text merge=union\n",
            b"docs/memory/*.md merge=union\n",
        ):
            with self.subTest(existing=existing):
                result, after = self.run_with_existing(existing, "", in_git=True)
                self.assertEqual(after, existing)
                self.assertIn("already applies", result.stdout)

    def test_rule_with_trailing_comment_is_invalid_so_a_valid_one_is_appended(self):
        """git rejects '#' as an attribute name, discarding the whole line."""
        existing = RULE + b" # keeps log entries from conflicting\n"
        _, after = self.run_with_existing(existing, "y\n", in_git=True)
        self.assertEqual(after, existing + RULE + b"\n")

    def test_conflicting_rule_is_reported_not_overridden(self):
        for existing, value in (
            (b"docs/memory/memory-index.md -merge\n", "unset"),
            (b'"docs/memory/memory-index.md" merge=custom\n', "custom"),
            (b"*.md binary\n", "unset"),
            (RULE + b"\ndocs/memory/memory-index.md -merge\n", "unset"),
        ):
            with self.subTest(existing=existing):
                result, after = self.run_with_existing(existing, "y\n", in_git=True)
                self.assertEqual(after, existing)
                self.assertIn(f"already applies 'merge: {value}'", result.stdout)
                self.assertNotIn("Append", result.stdout)

    def test_rule_reset_by_a_later_line_is_reported_not_called_present(self):
        existing = RULE + b"\ndocs/memory/memory-index.md !merge\n"
        result, after = self.run_with_existing(existing, "y\n", in_git=True)
        self.assertEqual(after, existing)
        self.assertIn("present but git reports 'merge: unspecified'", result.stdout)
        self.assertNotIn("already present", result.stdout)
        self.assertNotIn("Append", result.stdout)

    def test_nested_override_is_reported(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tmpdir = pathlib.Path(tmp.name)
        git(tmpdir, "init", "-q", "-b", "main")
        (tmpdir / "docs/memory").mkdir(parents=True)
        (tmpdir / "docs/memory/.gitattributes").write_bytes(b"memory-index.md -merge\n")
        result = run_bootstrap(tmpdir)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("already applies 'merge: unset'", result.stdout)
        self.assertFalse((tmpdir / ".gitattributes").exists())

    def test_global_attributes_do_not_count_as_installed(self):
        """A rule in the developer's global file does not travel with the repo."""
        global_attrs = pathlib.Path(GIT_ENV["XDG_CONFIG_HOME"]) / "git/attributes"
        global_attrs.parent.mkdir(parents=True, exist_ok=True)
        global_attrs.write_bytes(RULE + b"\n")
        self.addCleanup(global_attrs.unlink)
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            git(tmpdir, "init", "-q", "-b", "main")
            check = git(
                tmpdir, "check-attr", "merge", "--", "docs/memory/memory-index.md"
            )
            self.assertIn("merge: union", check.stdout, msg="sentinel not active")
            result = run_bootstrap(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual((tmpdir / ".gitattributes").read_bytes(), RULE + b"\n")

    def test_without_git_on_path_the_exact_line_check_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "bin").mkdir()
            (tmpdir / "proj").mkdir()
            existing = RULE + b"\n"
            (tmpdir / "proj/.gitattributes").write_bytes(existing)
            env = {**GIT_ENV, "PATH": str(tmpdir / "bin")}
            cmd = [sys.executable, str(BOOTSTRAP_PY), "P", "D", "--project"]
            cmd += [str(tmpdir / "proj"), "--author", "a"]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("already present", result.stdout)
            self.assertEqual((tmpdir / "proj/.gitattributes").read_bytes(), existing)

    def test_upgrade_adds_the_rule_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = bootstrapped_git_repo(pathlib.Path(tmp))
            (tmpdir / ".gitattributes").write_bytes(b"* text=auto\n")
            first = run_upgrade(tmpdir, input_text="y\n")
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            after_first = (tmpdir / ".gitattributes").read_bytes()
            self.assertEqual(after_first, b"* text=auto\n" + RULE + b"\n")
            second = run_upgrade(tmpdir)
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertEqual((tmpdir / ".gitattributes").read_bytes(), after_first)
            self.assertNotIn("Append", second.stdout)

    def test_upgrade_adds_nothing_when_user_declines(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "AGENTS.md").write_text(stale_agents_md(), encoding="utf-8")
            result = run_upgrade(tmpdir, input_text="n\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertFalse((tmpdir / ".gitattributes").exists())


class TestUnionMergeRebase(unittest.TestCase):
    """Two branches that each add a log line rebase cleanly only with the rule."""

    def rebase_two_entries(self, keep_rule: bool) -> tuple[int, str]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = pathlib.Path(tmp.name)
        git(repo, "init", "-q", "-b", "main")
        result = run_bootstrap(repo)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        if not keep_rule:
            (repo / ".gitattributes").unlink()
        expected = "union" if keep_rule else "unspecified"
        check = git(repo, "check-attr", "merge", "--", "docs/memory/memory-index.md")
        self.assertIn(f"merge: {expected}", check.stdout)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "base")
        index = repo / "docs/memory/memory-index.md"
        heading = "## Log (newest first)\n\n"
        self.assertIn(heading, index.read_text(encoding="utf-8"))

        def add_entry(branch: str, line: str) -> None:
            git(repo, "checkout", "-q", branch)
            text = index.read_text(encoding="utf-8")
            index.write_text(text.replace(heading, heading + line, 1), encoding="utf-8")
            git(repo, "commit", "-q", "-am", line)

        git(repo, "branch", "feature")
        add_entry("main", "- main entry\n")
        add_entry("feature", "- feature entry\n")
        rebase = git(repo, "rebase", "main", check=False)
        return rebase.returncode, index.read_text(encoding="utf-8")

    def test_rule_lets_both_entries_rebase_cleanly(self):
        returncode, text = self.rebase_two_entries(keep_rule=True)
        self.assertEqual(returncode, 0)
        self.assertIn("- main entry\n", text)
        self.assertIn("- feature entry\n", text)
        self.assertNotIn("<<<<<<<", text)

    def test_without_rule_the_same_rebase_conflicts(self):
        returncode, text = self.rebase_two_entries(keep_rule=False)
        self.assertNotEqual(returncode, 0)
        self.assertIn("<<<<<<<", text)


class TestMemoryFileProtection(unittest.TestCase):
    """Pre-existing files under docs/memory/ are never overwritten."""

    def test_exits_when_product_md_already_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "docs/memory").mkdir(parents=True)
            existing = "existing content - do not touch\n"
            (tmpdir / "docs/memory/product.md").write_text(existing)
            result = run_bootstrap(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite", result.stderr)
            self.assertEqual((tmpdir / "docs/memory/product.md").read_text(), existing)

    def test_preflight_runs_before_any_prompt(self):
        """If a memory file exists AND AGENTS.md exists, exit without prompting."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "AGENTS.md").write_text("# Existing\nNo memory section yet.\n")
            (tmpdir / "docs/memory").mkdir(parents=True)
            (tmpdir / "docs/memory/product.md").write_text("existing\n")
            result = run_bootstrap(tmpdir, input_text="")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite", result.stderr)
            # If pre-flight ran first, the AGENTS.md prompt was never printed
            self.assertNotIn("Append", result.stdout)
            # AGENTS.md must be untouched
            self.assertEqual(
                (tmpdir / "AGENTS.md").read_text(),
                "# Existing\nNo memory section yet.\n",
            )


class TestAgentsMdMerge(unittest.TestCase):
    """AGENTS.md merge behavior for pre-existing files."""

    def test_skips_silently_when_memory_section_already_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            existing = "# MyProj\n\n## Project memory\n\nfoo bar\n"
            (tmpdir / "AGENTS.md").write_text(existing)
            result = run_bootstrap(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("memory section already present", result.stdout)
            self.assertEqual((tmpdir / "AGENTS.md").read_text(), existing)

    def test_appends_memory_section_when_user_confirms(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            existing = "# MyProj\n\nSome existing content.\n"
            (tmpdir / "AGENTS.md").write_text(existing)
            result = run_bootstrap(tmpdir, input_text="y\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = (tmpdir / "AGENTS.md").read_text()
            self.assertIn("Some existing content.", content)
            self.assertIn("## Project memory", content)
            self.assertIn("appended memory section", result.stdout)

    def test_leaves_existing_alone_when_user_declines(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            existing = "# MyProj\n\nSome existing content.\n"
            (tmpdir / "AGENTS.md").write_text(existing)
            result = run_bootstrap(tmpdir, input_text="n\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual((tmpdir / "AGENTS.md").read_text(), existing)

    def test_only_marker_delimited_section_is_appended(self):
        """Content after the end marker in the template is not appended."""
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            templates = tmpdir / "templates"
            templates.mkdir()
            (templates / "AGENTS.md").write_text(
                "# ${name}\n\n${desc}\n\n"
                "<!-- project-memory:start -->\n"
                "## Project memory\n\nrules here\n"
                "<!-- project-memory:end -->\n\n"
                "## Style\n\nthis must NOT be appended\n",
                encoding="utf-8",
            )
            real_templates = REPO_ROOT / "init" / "templates"
            for name in (
                "CLAUDE.md",
                "memory-index.md",
                "product.md",
                "architecture.md",
                "bootstrap-log.md",
                "plans-current-readme.md",
                "plans-archive-readme.md",
            ):
                (templates / name).write_text(
                    (real_templates / name).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            project = tmpdir / "proj"
            project.mkdir()
            (project / "AGENTS.md").write_text(
                "# Existing\n\nstuff\n", encoding="utf-8"
            )
            cmd = [
                sys.executable,
                str(BOOTSTRAP_PY),
                "TestProj",
                "Test desc",
                "--project",
                str(project),
                "--author",
                "testuser",
                "--templates-dir",
                str(templates),
            ]
            result = subprocess.run(
                cmd, input="y\n", capture_output=True, text=True, env=GIT_ENV
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = (project / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("## Project memory", content)
            self.assertIn("rules here", content)
            self.assertIn("<!-- project-memory:start -->", content)
            self.assertIn("<!-- project-memory:end -->", content)
            self.assertNotIn("this must NOT be appended", content)
            self.assertNotIn("## Style", content)


class TestClaudeMdMerge(unittest.TestCase):
    """CLAUDE.md merge behavior for pre-existing files."""

    def test_skips_when_already_imports_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            existing = "@AGENTS.md\n\nMy custom notes.\n"
            (tmpdir / "CLAUDE.md").write_text(existing)
            result = run_bootstrap(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("already imported", result.stdout)
            self.assertEqual((tmpdir / "CLAUDE.md").read_text(), existing)

    def test_prepends_import_when_user_confirms(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            # Pre-create AGENTS.md with memory section so the AGENTS.md path doesn't prompt
            (tmpdir / "AGENTS.md").write_text("# X\n\n## Project memory\n\nrules\n")
            existing = "Custom Claude instructions.\n"
            (tmpdir / "CLAUDE.md").write_text(existing)
            result = run_bootstrap(tmpdir, input_text="y\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = (tmpdir / "CLAUDE.md").read_text()
            self.assertTrue(content.startswith("@AGENTS.md"))
            self.assertIn("Custom Claude instructions.", content)


class TestUpgrade(unittest.TestCase):
    """--upgrade replaces the marker block with the current template's contents."""

    def test_replaces_stale_block_with_template_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            stale = (
                "# MyProj\n\n"
                "Description.\n\n"
                "<!-- project-memory:start -->\n"
                "## Project memory\n\n"
                "OLD RULE TEXT THAT NO LONGER MATCHES THE TEMPLATE.\n"
                "<!-- project-memory:end -->\n\n"
                "## Custom user section\n\nUser stuff.\n"
            )
            (tmpdir / "AGENTS.md").write_text(stale)
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("OLD RULE TEXT", result.stdout)
            content = (tmpdir / "AGENTS.md").read_text()
            self.assertNotIn("OLD RULE TEXT", content)
            self.assertIn("Project memory lives in", content)
            self.assertIn("## Custom user section", content)
            self.assertIn("User stuff.", content)

    def test_no_op_when_already_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            bootstrap_result = run_bootstrap(tmpdir)
            self.assertEqual(
                bootstrap_result.returncode, 0, msg=bootstrap_result.stderr
            )
            before = (tmpdir / "AGENTS.md").read_text()
            result = run_upgrade(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("already current", result.stdout)
            self.assertEqual((tmpdir / "AGENTS.md").read_text(), before)

    def test_preserves_content_outside_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            existing = (
                "# Custom Header\n\n"
                "User preamble that must survive.\n\n"
                "<!-- project-memory:start -->\n"
                "## Project memory\n\nOLD CONTENT\n"
                "<!-- project-memory:end -->\n\n"
                "## Trailing user section\n\nMore user content.\n"
            )
            (tmpdir / "AGENTS.md").write_text(existing)
            result = run_upgrade(tmpdir, input_text="y\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = (tmpdir / "AGENTS.md").read_text()
            self.assertIn("# Custom Header", content)
            self.assertIn("User preamble that must survive.", content)
            self.assertIn("## Trailing user section", content)
            self.assertIn("More user content.", content)
            self.assertNotIn("OLD CONTENT", content)

    def test_aborts_when_user_declines(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            stale = (
                "<!-- project-memory:start -->\n"
                "## Project memory\n\nOLD\n"
                "<!-- project-memory:end -->\n"
            )
            (tmpdir / "AGENTS.md").write_text(stale)
            result = run_upgrade(tmpdir, input_text="n\n")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual((tmpdir / "AGENTS.md").read_text(), stale)

    def test_errors_when_agents_md_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            result = run_upgrade(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not found", result.stderr)

    def test_errors_when_markers_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            (tmpdir / "AGENTS.md").write_text("# Has no markers\n\nNothing here.\n")
            result = run_upgrade(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("markers", result.stderr)


MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*$", re.MULTILINE)


def heading_slugs(text: str) -> set[str]:
    """GitHub-style anchor slugs for every heading in a markdown document."""
    slugs = set()
    for heading in HEADING.findall(text):
        slug = re.sub(r"[^\w\- ]", "", heading.replace("`", "").lower())
        slugs.add(slug.strip().replace(" ", "-"))
    return slugs


class TestGeneratedLinks(unittest.TestCase):
    """Every relative link in a bootstrapped project resolves, anchors included."""

    def test_relative_links_and_anchors_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            result = run_bootstrap(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            checked = 0
            for md in sorted(tmpdir.rglob("*.md")):
                for target in MD_LINK.findall(md.read_text(encoding="utf-8")):
                    if "://" in target or target.startswith(("#", "mailto:")):
                        continue
                    rel, _, anchor = target.partition("#")
                    path = (md.parent / rel).resolve() if rel else md
                    where = f"{md.relative_to(tmpdir)} -> {target}"
                    self.assertTrue(path.exists(), msg=f"missing target: {where}")
                    if anchor:
                        self.assertIn(
                            anchor,
                            heading_slugs(path.read_text(encoding="utf-8")),
                            msg=f"anchor not found: {where}",
                        )
                    checked += 1
            self.assertGreater(checked, 0)


class TestDescriptionSentence(unittest.TestCase):
    """The description reads as a full sentence wherever prose follows or surrounds it."""

    def bootstrap(self, desc: str) -> pathlib.Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tmpdir = pathlib.Path(tmp.name)
        result = run_bootstrap(tmpdir, desc=desc)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        return tmpdir

    def test_agents_md_gets_a_period_before_the_see_sentence(self):
        tmpdir = self.bootstrap("A tool for things")
        agents = (tmpdir / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("A tool for things. See [", agents)

    def test_existing_terminal_punctuation_is_not_doubled(self):
        for desc in ("A tool for things.", "A tool for things!", "A tool?"):
            with self.subTest(desc=desc):
                agents = (self.bootstrap(desc) / "AGENTS.md").read_text(
                    encoding="utf-8"
                )
                self.assertIn(f"{desc} See [", agents)

    def test_product_body_is_a_sentence_but_summary_is_verbatim(self):
        tmpdir = self.bootstrap("A tool for things")
        product = (tmpdir / "docs/memory/product.md").read_text(encoding="utf-8")
        self.assertIn("summary: A tool for things\n", product)
        self.assertIn("\nA tool for things.\n", product)


class TestBootstrapLogWording(unittest.TestCase):
    def test_log_says_project_root_so_subprojects_read_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = pathlib.Path(tmp)
            self.assertEqual(run_bootstrap(tmpdir).returncode, 0)
            (log,) = (tmpdir / "docs/memory/log").iterdir()
            text = log.read_text(encoding="utf-8")
            self.assertIn("at the project root", text)
            self.assertNotIn("repo root", text)


if __name__ == "__main__":
    unittest.main()

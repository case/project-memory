"""Unit tests for init/bootstrap.py.

Run from the repo root:
    python3 -m unittest discover tests
"""

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOTSTRAP_PY = REPO_ROOT / "init" / "bootstrap.py"


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
    return subprocess.run(cmd, input=input_text, capture_output=True, text=True)


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
    return subprocess.run(cmd, input=input_text, capture_output=True, text=True)


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
            result = subprocess.run(cmd, input="y\n", capture_output=True, text=True)
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


if __name__ == "__main__":
    unittest.main()

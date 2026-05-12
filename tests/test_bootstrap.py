"""Unit tests for init/bootstrap.py.

Run from the repo root:
    python3 -m unittest discover tests
"""

import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BOOTSTRAP_PY = REPO_ROOT / "init" / "bootstrap.py"


def run_bootstrap(
    project_dir: pathlib.Path,
    *,
    name: str = "TestProj",
    desc: str = "Test description",
    author: str = "testuser",
    input_text: str = "",
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
    return subprocess.run(cmd, input=input_text, capture_output=True, text=True)


class TestFreshProject(unittest.TestCase):
    """Bootstrapping a clean target directory creates all six files."""

    def test_creates_all_six_files(self):
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


if __name__ == "__main__":
    unittest.main()

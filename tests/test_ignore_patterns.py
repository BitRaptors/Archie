"""Tests for IgnoreMatcher — .archieignore + .gitignore pattern matching."""
from __future__ import annotations

import json
import os
import sys

import pytest

from archie.standalone._common import IgnoreMatcher

# Allow importing scanner.py as a module (it uses `from _common import ...`)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "archie", "standalone"))


# ── Helpers ──────────────────────────────────────────────────────────────


def _write(path, content: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ── Tests ────────────────────────────────────────────────────────────────


class TestEmptyIgnoreFiles:
    """No ignore files present — nothing should be ignored."""

    def test_nothing_ignored(self, tmp_path):
        m = IgnoreMatcher(tmp_path)
        assert not m.is_ignored("foo.py")
        assert not m.is_ignored("src/bar.go")
        assert not m.should_skip_dir("vendor", "")
        assert not m.should_skip_file("main.go", "")


class TestArchieignoreDirectoryPatterns:
    """Directory patterns (trailing /) match at any depth."""

    def test_dir_pattern_matches_root(self, tmp_path):
        _write(tmp_path / ".archieignore", "vendor/\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir("vendor", "")

    def test_dir_pattern_matches_nested(self, tmp_path):
        _write(tmp_path / ".archieignore", "vendor/\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir("vendor", "pkg/third_party")

    def test_dir_pattern_does_not_match_file(self, tmp_path):
        _write(tmp_path / ".archieignore", "vendor/\n")
        m = IgnoreMatcher(tmp_path)
        assert not m.should_skip_file("vendor", "")

    def test_multiple_dir_patterns(self, tmp_path):
        _write(tmp_path / ".archieignore", ".devenv/\nnode_modules/\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir(".devenv", "")
        assert m.should_skip_dir("node_modules", "pkg/sub")
        assert not m.should_skip_dir("src", "")


class TestArchieignoreExtensionPatterns:
    """Glob extension patterns like *.ext."""

    def test_extension_match(self, tmp_path):
        _write(tmp_path / ".archieignore", "*.pyc\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_file("module.pyc", "")
        assert m.should_skip_file("module.pyc", "deep/nested")

    def test_extension_no_false_positive(self, tmp_path):
        _write(tmp_path / ".archieignore", "*.pyc\n")
        m = IgnoreMatcher(tmp_path)
        assert not m.should_skip_file("module.py", "")


class TestGitignoreFallback:
    """When no .archieignore exists, .gitignore is used."""

    def test_gitignore_only(self, tmp_path):
        _write(tmp_path / ".gitignore", "build/\n*.log\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir("build", "")
        assert m.should_skip_file("app.log", "src")
        assert not m.should_skip_file("app.py", "src")


class TestMergedPatterns:
    """Both .archieignore and .gitignore are merged (union)."""

    def test_union(self, tmp_path):
        _write(tmp_path / ".archieignore", "vendor/\n")
        _write(tmp_path / ".gitignore", "build/\n*.log\n")
        m = IgnoreMatcher(tmp_path)
        # From .archieignore
        assert m.should_skip_dir("vendor", "")
        # From .gitignore
        assert m.should_skip_dir("build", "")
        assert m.should_skip_file("debug.log", "")


class TestNegationPatterns:
    """Negation with ! un-ignores a previously ignored pattern."""

    def test_negation_unignores(self, tmp_path):
        _write(tmp_path / ".archieignore", "*.log\n!important.log\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_file("debug.log", "")
        assert not m.should_skip_file("important.log", "")

    def test_negation_order_matters(self, tmp_path):
        # Negation then re-ignore
        _write(tmp_path / ".archieignore", "*.log\n!important.log\nimportant.log\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_file("important.log", "")


class TestCommentsAndBlankLines:
    """Comments (#) and blank lines are ignored."""

    def test_comments_ignored(self, tmp_path):
        _write(tmp_path / ".archieignore", "# This is a comment\nvendor/\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir("vendor", "")
        assert not m.should_skip_dir("#", "")

    def test_blank_lines_ignored(self, tmp_path):
        _write(tmp_path / ".archieignore", "\n\nvendor/\n\n*.pyc\n\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir("vendor", "")
        assert m.should_skip_file("x.pyc", "")


class TestRootedPatterns:
    """Patterns with leading / only match at the project root."""

    def test_rooted_dir_matches_root_only(self, tmp_path):
        _write(tmp_path / ".archieignore", "/build/\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir("build", "")
        assert not m.should_skip_dir("build", "sub/dir")

    def test_rooted_file_matches_root_only(self, tmp_path):
        _write(tmp_path / ".archieignore", "/Makefile\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_file("Makefile", "")
        assert not m.should_skip_file("Makefile", "sub")

    def test_unrooted_matches_any_depth(self, tmp_path):
        _write(tmp_path / ".archieignore", "build/\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir("build", "")
        assert m.should_skip_dir("build", "sub/dir")


class TestNestedGitignore:
    """Nested .gitignore files are scoped to their directory."""

    def test_nested_gitignore_scoped(self, tmp_path):
        _write(tmp_path / ".gitignore", "*.log\n")
        sub = tmp_path / "pkg" / "sub"
        sub.mkdir(parents=True)
        _write(sub / ".gitignore", "generated/\n")
        m = IgnoreMatcher(tmp_path)
        # Root .gitignore applies everywhere
        assert m.should_skip_file("app.log", "")
        assert m.should_skip_file("app.log", "pkg/sub")
        # Nested .gitignore only applies under pkg/sub
        assert m.should_skip_dir("generated", "pkg/sub")
        assert m.should_skip_dir("generated", "pkg/sub/deep")
        assert not m.should_skip_dir("generated", "")
        assert not m.should_skip_dir("generated", "pkg")


class TestShouldSkipDirIntegration:
    """should_skip_dir works correctly for os.walk integration."""

    def test_basic_walk_filtering(self, tmp_path):
        _write(tmp_path / ".archieignore", "node_modules/\n.devenv/\n")
        # Create dirs
        (tmp_path / "src").mkdir()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "src" / "node_modules").mkdir()
        (tmp_path / ".devenv").mkdir()

        m = IgnoreMatcher(tmp_path)
        skipped = []
        for root, dirs, files in os.walk(tmp_path):
            rel = os.path.relpath(root, tmp_path)
            if rel == ".":
                rel = ""
            dirs[:] = [d for d in dirs if not m.should_skip_dir(d, rel)]
            for d in dirs:
                pass  # just walk

        # Verify the matcher would skip correctly
        assert m.should_skip_dir("node_modules", "")
        assert m.should_skip_dir("node_modules", "src")
        assert m.should_skip_dir(".devenv", "")
        assert not m.should_skip_dir("src", "")


class TestShouldSkipFileIntegration:
    """should_skip_file works correctly for os.walk integration."""

    def test_file_filtering(self, tmp_path):
        _write(tmp_path / ".archieignore", "*.pyc\n*.log\n")
        m = IgnoreMatcher(tmp_path)
        files = ["main.py", "main.pyc", "debug.log", "readme.md"]
        kept = [f for f in files if not m.should_skip_file(f, "")]
        assert kept == ["main.py", "readme.md"]


class TestIsIgnoredConvenience:
    """is_ignored(rel_path) works for both files and directories."""

    def test_file_path(self, tmp_path):
        _write(tmp_path / ".archieignore", "*.log\n")
        m = IgnoreMatcher(tmp_path)
        assert m.is_ignored("src/debug.log")
        assert not m.is_ignored("src/main.py")

    def test_dir_path(self, tmp_path):
        _write(tmp_path / ".archieignore", "vendor/\n")
        # Create the dir so is_ignored can detect it
        (tmp_path / "vendor").mkdir()
        m = IgnoreMatcher(tmp_path)
        assert m.is_ignored("vendor")

    def test_nested_path(self, tmp_path):
        _write(tmp_path / ".archieignore", "*.pyc\n")
        m = IgnoreMatcher(tmp_path)
        assert m.is_ignored("pkg/deep/module.pyc")
        assert not m.is_ignored("pkg/deep/module.py")


class TestWildcardPatterns:
    """Wildcard patterns like doc/*.txt or **/foo."""

    def test_star_in_path(self, tmp_path):
        _write(tmp_path / ".archieignore", "doc/*.txt\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_file("readme.txt", "doc")
        # Should not match in other dirs since pattern has a /
        assert not m.should_skip_file("readme.txt", "src")

    def test_double_star(self, tmp_path):
        _write(tmp_path / ".archieignore", "**/build/\n")
        m = IgnoreMatcher(tmp_path)
        assert m.should_skip_dir("build", "")
        assert m.should_skip_dir("build", "deep/nested")


# ── Scanner integration tests ────────────────────────────────────────────


class TestScannerIgnoreIntegration:
    """Verify that scanner.run_scan() respects .archieignore patterns."""

    def test_archieignore_excludes_dir_from_scan(self, tmp_path):
        """Directories listed in .archieignore should be absent from scan results."""
        from archie.standalone.scanner import run_scan

        # Create project structure
        _write(tmp_path / "src" / "main.py", "print('hello')\n")
        _write(tmp_path / "src" / "utils.py", "pass\n")
        _write(tmp_path / "generated" / "output.py", "# auto\n")
        _write(tmp_path / "generated" / "models.py", "# auto\n")
        _write(tmp_path / ".archieignore", "generated/\n")

        result = run_scan(str(tmp_path))
        paths = [f["path"] for f in result["file_tree"]]

        # src/ files should be present
        assert any("main.py" in p for p in paths)
        assert any("utils.py" in p for p in paths)
        # generated/ files should be excluded
        assert not any("generated" in p for p in paths)

    def test_archieignore_excludes_files_by_extension(self, tmp_path):
        """File glob patterns in .archieignore should exclude matching files."""
        from archie.standalone.scanner import run_scan

        _write(tmp_path / "app.py", "print('app')\n")
        _write(tmp_path / "debug.log", "some log\n")
        _write(tmp_path / "error.log", "some error\n")
        _write(tmp_path / ".archieignore", "*.log\n")

        result = run_scan(str(tmp_path))
        paths = [f["path"] for f in result["file_tree"]]

        assert "app.py" in paths
        assert "debug.log" not in paths
        assert "error.log" not in paths

    def test_archieignore_negation_keeps_file(self, tmp_path):
        """Negation patterns (!) should un-ignore specific files."""
        from archie.standalone.scanner import run_scan

        _write(tmp_path / "a.dat", "data\n")
        _write(tmp_path / "b.dat", "data\n")
        _write(tmp_path / "keep.dat", "important\n")
        _write(tmp_path / ".archieignore", "*.dat\n!keep.dat\n")

        result = run_scan(str(tmp_path))
        paths = [f["path"] for f in result["file_tree"]]

        assert "a.dat" not in paths
        assert "b.dat" not in paths
        assert "keep.dat" in paths

    def test_skip_dirs_still_works_without_archieignore(self, tmp_path):
        """SKIP_DIRS fallback should still prune node_modules etc."""
        from archie.standalone.scanner import run_scan

        _write(tmp_path / "index.js", "console.log()\n")
        _write(tmp_path / "node_modules" / "pkg" / "index.js", "module.exports={}\n")

        result = run_scan(str(tmp_path))
        paths = [f["path"] for f in result["file_tree"]]

        assert "index.js" in paths
        assert not any("node_modules" in p for p in paths)

    def test_gitignore_patterns_respected(self, tmp_path):
        """Patterns from .gitignore should also be respected by scanner."""
        from archie.standalone.scanner import run_scan

        _write(tmp_path / "app.py", "print('hi')\n")
        _write(tmp_path / "tmp_output" / "result.py", "# tmp\n")
        _write(tmp_path / ".gitignore", "tmp_output/\n")

        result = run_scan(str(tmp_path))
        paths = [f["path"] for f in result["file_tree"]]

        assert "app.py" in paths
        assert not any("tmp_output" in p for p in paths)

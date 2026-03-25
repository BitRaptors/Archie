"""Tests for LocalRepoHandler."""
import pytest
from pathlib import Path

from application.services.local_repo_handler import LocalRepoHandler


class TestBuildFileTree:
    """Tests for build_file_tree."""

    def test_basic_file_tree(self, tmp_path):
        """Builds tree from a simple directory structure."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("print('hello')")
        (tmp_path / "README.md").write_text("# Hello")

        handler = LocalRepoHandler(tmp_path)
        tree = handler.build_file_tree()

        paths = {f["path"] for f in tree}
        assert "src/main.py" in paths
        assert "README.md" in paths

    def test_ignores_node_modules(self, tmp_path):
        """Skips node_modules when provided in ignored_dirs."""
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("x")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.js").write_text("app")

        handler = LocalRepoHandler(tmp_path, ignored_dirs={"node_modules"})
        tree = handler.build_file_tree()

        paths = {f["path"] for f in tree}
        assert not any("node_modules" in p for p in paths)
        assert "src/app.js" in paths

    def test_skips_hidden_dirs(self, tmp_path):
        """Skips directories starting with dot."""
        (tmp_path / ".git" / "objects").mkdir(parents=True)
        (tmp_path / ".git" / "objects" / "x").write_text("x")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("code")

        handler = LocalRepoHandler(tmp_path)
        tree = handler.build_file_tree()

        paths = {f["path"] for f in tree}
        assert not any(".git" in p for p in paths)

    def test_custom_ignored_dirs(self, tmp_path):
        """Respects custom ignored directories."""
        (tmp_path / "vendor").mkdir()
        (tmp_path / "vendor" / "lib.py").write_text("x")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("code")

        handler = LocalRepoHandler(tmp_path, ignored_dirs={"vendor"})
        tree = handler.build_file_tree()

        paths = {f["path"] for f in tree}
        assert not any("vendor" in p for p in paths)
        assert "src/main.py" in paths

    def test_file_entry_format(self, tmp_path):
        """Each entry has name, path, type, size, extension."""
        (tmp_path / "app.py").write_text("hello")

        handler = LocalRepoHandler(tmp_path)
        tree = handler.build_file_tree()

        assert len(tree) >= 1
        entry = [e for e in tree if e["name"] == "app.py"][0]
        assert entry["type"] == "file"
        assert entry["extension"] == "py"
        assert entry["size"] == 5  # "hello" = 5 bytes
        assert entry["path"] == "app.py"

    def test_empty_directory(self, tmp_path):
        """Empty directory returns empty tree."""
        handler = LocalRepoHandler(tmp_path)
        tree = handler.build_file_tree()
        assert tree == []

    def test_nested_structure(self, tmp_path):
        """Handles nested directories correctly."""
        (tmp_path / "a" / "b" / "c").mkdir(parents=True)
        (tmp_path / "a" / "b" / "c" / "deep.txt").write_text("deep")

        handler = LocalRepoHandler(tmp_path)
        tree = handler.build_file_tree()

        paths = {f["path"] for f in tree}
        assert "a/b/c/deep.txt" in paths


class TestReadFile:
    """Tests for read_file."""

    def test_reads_existing_file(self, tmp_path):
        (tmp_path / "test.py").write_text("content here")
        handler = LocalRepoHandler(tmp_path)
        assert handler.read_file("test.py") == "content here"

    def test_returns_none_for_missing(self, tmp_path):
        handler = LocalRepoHandler(tmp_path)
        assert handler.read_file("nonexistent.py") is None

    def test_reads_nested_file(self, tmp_path):
        (tmp_path / "src" / "api").mkdir(parents=True)
        (tmp_path / "src" / "api" / "routes.py").write_text("routes")
        handler = LocalRepoHandler(tmp_path)
        assert handler.read_file("src/api/routes.py") == "routes"


class TestWriteFile:
    """Tests for write_file."""

    def test_writes_new_file(self, tmp_path):
        handler = LocalRepoHandler(tmp_path)
        handler.write_file("output.md", "# Output")
        assert (tmp_path / "output.md").read_text() == "# Output"

    def test_creates_parent_dirs(self, tmp_path):
        handler = LocalRepoHandler(tmp_path)
        handler.write_file("deep/nested/dir/file.md", "content")
        assert (tmp_path / "deep" / "nested" / "dir" / "file.md").read_text() == "content"

    def test_overwrites_existing(self, tmp_path):
        (tmp_path / "file.md").write_text("old")
        handler = LocalRepoHandler(tmp_path)
        handler.write_file("file.md", "new")
        assert (tmp_path / "file.md").read_text() == "new"


class TestWriteMergedMarkdown:
    """Tests for write_merged_markdown."""

    def test_new_file_gets_markers(self, tmp_path):
        handler = LocalRepoHandler(tmp_path)
        handler.write_merged_markdown("CLAUDE.md", "# Test", "my-repo")
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "<!-- gbr:start repo=my-repo -->" in content
        assert "<!-- gbr:end -->" in content
        assert "# Test" in content

    def test_merges_with_existing(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Existing Content\nKeep this.")
        handler = LocalRepoHandler(tmp_path)
        handler.write_merged_markdown("CLAUDE.md", "# Generated", "my-repo")
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "# Existing Content" in content
        assert "Keep this." in content
        assert "# Generated" in content
        assert "<!-- gbr:start repo=my-repo -->" in content

    def test_replaces_existing_markers(self, tmp_path):
        existing = "# Manual\n\n<!-- gbr:start repo=my-repo -->\nold stuff\n<!-- gbr:end -->\n\n# Footer"
        (tmp_path / "CLAUDE.md").write_text(existing)
        handler = LocalRepoHandler(tmp_path)
        handler.write_merged_markdown("CLAUDE.md", "# New Content", "my-repo")
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "old stuff" not in content
        assert "# New Content" in content
        assert "# Manual" in content
        assert "# Footer" in content

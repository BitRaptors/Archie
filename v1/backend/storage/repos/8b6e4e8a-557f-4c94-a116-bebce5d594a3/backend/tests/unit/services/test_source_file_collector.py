"""Tests for SourceFileCollector — copying full repo to persistent storage."""
import json
import os
import pytest
from pathlib import Path

from application.services.source_file_collector import SourceFileCollector


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_file(tmp_path: Path, rel_path: str, content: str = "hello world"):
    """Create a file in the temp directory."""
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    return full


# ── Tests ────────────────────────────────────────────────────────────────────


class TestCopyRepo:
    """Tests for copying the full repository tree."""

    def test_copies_all_files(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "src/main.py", "main")
        _write_file(repo, "src/utils.py", "utils")
        _write_file(repo, "README.md", "readme")

        collector = SourceFileCollector()
        manifest = collector.copy_repo(repo, dest)

        assert (dest / "src" / "main.py").read_text() == "main"
        assert (dest / "src" / "utils.py").read_text() == "utils"
        assert (dest / "README.md").read_text() == "readme"
        assert manifest["file_count"] == 3

    def test_skips_git_directory(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "src/main.py", "main")
        _write_file(repo, ".git/HEAD", "ref: refs/heads/main")
        _write_file(repo, ".git/objects/abc", "blob data")

        collector = SourceFileCollector()
        manifest = collector.copy_repo(repo, dest, ignored_dirs={".git"})

        assert (dest / "src" / "main.py").exists()
        assert not (dest / ".git").exists()
        assert "src/main.py" in manifest["files"]
        assert not any(".git" in f for f in manifest["files"])

    def test_skips_node_modules(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "index.js", "app")
        _write_file(repo, "node_modules/react/index.js", "react")

        collector = SourceFileCollector()
        manifest = collector.copy_repo(repo, dest, ignored_dirs={"node_modules"})

        assert (dest / "index.js").exists()
        assert not (dest / "node_modules").exists()

    def test_skips_pycache(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "app.py", "app")
        _write_file(repo, "__pycache__/app.cpython-313.pyc", "bytecode")

        collector = SourceFileCollector()
        collector.copy_repo(repo, dest, ignored_dirs={"__pycache__"})

        assert (dest / "app.py").exists()
        assert not (dest / "__pycache__").exists()

    def test_skips_venv(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "app.py", "app")
        _write_file(repo, ".venv/bin/python", "python")

        collector = SourceFileCollector()
        collector.copy_repo(repo, dest, ignored_dirs={".venv"})

        assert (dest / "app.py").exists()
        assert not (dest / ".venv").exists()

    def test_preserves_directory_structure(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "src/api/routes/users.py", "users")
        _write_file(repo, "src/domain/entities/user.py", "user entity")
        _write_file(repo, "tests/test_users.py", "test")

        collector = SourceFileCollector()
        collector.copy_repo(repo, dest)

        assert (dest / "src" / "api" / "routes" / "users.py").read_text() == "users"
        assert (dest / "src" / "domain" / "entities" / "user.py").read_text() == "user entity"
        assert (dest / "tests" / "test_users.py").read_text() == "test"

    def test_replaces_old_copy(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"

        # First copy
        _write_file(repo, "old_file.py", "old")
        collector = SourceFileCollector()
        collector.copy_repo(repo, dest)
        assert (dest / "old_file.py").exists()

        # Update repo and re-copy
        (repo / "old_file.py").unlink()
        _write_file(repo, "new_file.py", "new")
        collector.copy_repo(repo, dest)

        assert not (dest / "old_file.py").exists()
        assert (dest / "new_file.py").exists()


class TestManifest:
    """Tests for manifest generation."""

    def test_writes_manifest_json(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "src/main.py", "main content")
        _write_file(repo, "src/app.py", "app content")

        collector = SourceFileCollector()
        manifest = collector.copy_repo(repo, dest)

        # Manifest returned
        assert manifest["file_count"] == 2
        assert "src/main.py" in manifest["files"]
        assert "src/app.py" in manifest["files"]
        assert manifest["total_size"] > 0
        assert "collected_at" in manifest

        # Manifest written to disk
        manifest_on_disk = json.loads((dest / "manifest.json").read_text())
        assert manifest_on_disk["file_count"] == 2

    def test_manifest_file_sizes_are_accurate(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        content = "x" * 1000
        _write_file(repo, "big.py", content)

        collector = SourceFileCollector()
        manifest = collector.copy_repo(repo, dest)

        assert manifest["files"]["big.py"] == 1000

    def test_total_size_is_sum(self, tmp_path):
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "a.py", "aaa")  # 3 bytes
        _write_file(repo, "b.py", "bb")   # 2 bytes

        collector = SourceFileCollector()
        manifest = collector.copy_repo(repo, dest)

        assert manifest["total_size"] == 5


class TestUserConfiguredIgnoredDirs:
    """Tests that user-configured ignored_dirs from DB are used."""

    def test_uses_provided_ignored_dirs(self, tmp_path):
        """When ignored_dirs is passed, those dirs are skipped (not defaults)."""
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "app.py", "app")
        _write_file(repo, "custom_build/output.js", "output")
        _write_file(repo, "vendor/lib.rb", "lib")

        collector = SourceFileCollector()
        # User configured only "custom_build" and "vendor"
        collector.copy_repo(repo, dest, ignored_dirs={"custom_build", "vendor"})

        assert (dest / "app.py").exists()
        assert not (dest / "custom_build").exists()
        assert not (dest / "vendor").exists()

    def test_provided_dirs_override_defaults(self, tmp_path):
        """User-configured dirs replace defaults — dirs NOT in the set are kept."""
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "app.py", "app")
        # node_modules would normally be skipped by defaults
        _write_file(repo, "node_modules/react/index.js", "react")
        _write_file(repo, "my_cache/data.bin", "cache")

        collector = SourceFileCollector()
        # User configured only "my_cache" — node_modules is NOT in this set
        collector.copy_repo(repo, dest, ignored_dirs={"my_cache"})

        assert (dest / "app.py").exists()
        assert (dest / "node_modules" / "react" / "index.js").exists()  # kept!
        assert not (dest / "my_cache").exists()  # skipped

    def test_empty_ignored_dirs_copies_everything(self, tmp_path):
        """Empty set means nothing is skipped."""
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "app.py", "app")
        _write_file(repo, "node_modules/react/index.js", "react")
        _write_file(repo, ".git/HEAD", "ref")

        collector = SourceFileCollector()
        collector.copy_repo(repo, dest, ignored_dirs=set())

        assert (dest / "app.py").exists()
        assert (dest / "node_modules" / "react" / "index.js").exists()
        assert (dest / ".git" / "HEAD").exists()

    def test_skips_all_user_configured_dirs(self, tmp_path):
        """Simulate a realistic user configuration from DB."""
        repo = tmp_path / "repo"
        dest = tmp_path / "dest"
        _write_file(repo, "src/main.py", "main")
        _write_file(repo, "node_modules/pkg/index.js", "pkg")
        _write_file(repo, "__pycache__/main.cpython.pyc", "bytecode")
        _write_file(repo, ".git/HEAD", "ref")
        _write_file(repo, "coverage/lcov.info", "lcov")
        _write_file(repo, "target/debug/main", "binary")

        # Simulate what gets loaded from Supabase discovery_ignored_dirs table
        user_ignored = {"node_modules", "__pycache__", ".git", "coverage", "target"}

        collector = SourceFileCollector()
        collector.copy_repo(repo, dest, ignored_dirs=user_ignored)

        assert (dest / "src" / "main.py").exists()
        assert not (dest / "node_modules").exists()
        assert not (dest / "__pycache__").exists()
        assert not (dest / ".git").exists()
        assert not (dest / "coverage").exists()
        assert not (dest / "target").exists()

"""Tests for archie.engine.scanner."""
from __future__ import annotations

import os
import time

import pytest

from archie.engine.scanner import scan_directory


@pytest.fixture()
def tmp_repo(tmp_path):
    """Return a tmp_path pre-configured as a tiny repo root."""
    return tmp_path


def _touch(path, content: str = "", mtime: float | None = None):
    """Create a file (and parents) with optional content and mtime."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


# -------------------------------------------------------------------
# 1. Empty directory
# -------------------------------------------------------------------
def test_scan_empty_dir(tmp_repo):
    entries = scan_directory(tmp_repo)
    assert entries == []


# -------------------------------------------------------------------
# 2. Simple repo with 3 files in src/ + README
# -------------------------------------------------------------------
def test_scan_simple_repo(tmp_repo):
    _touch(tmp_repo / "README.md", "# Hello")
    _touch(tmp_repo / "src" / "main.py", "print('hi')")
    _touch(tmp_repo / "src" / "utils.py", "pass")
    _touch(tmp_repo / "src" / "config.yaml", "key: val")

    entries = scan_directory(tmp_repo)
    paths = [e.path for e in entries]

    assert len(entries) == 4
    assert "README.md" in paths
    assert os.path.join("src", "main.py") in paths
    assert os.path.join("src", "utils.py") in paths
    assert os.path.join("src", "config.yaml") in paths


# -------------------------------------------------------------------
# 3. Skips .git and node_modules
# -------------------------------------------------------------------
def test_scan_skips_git_and_node_modules(tmp_repo):
    _touch(tmp_repo / "app.js", "console.log()")
    _touch(tmp_repo / ".git" / "config", "bare = false")
    _touch(tmp_repo / "node_modules" / "pkg" / "index.js", "module.exports={}")

    entries = scan_directory(tmp_repo)
    paths = [e.path for e in entries]

    assert paths == ["app.js"]


# -------------------------------------------------------------------
# 4. Captures size and extension
# -------------------------------------------------------------------
def test_scan_captures_size_and_extension(tmp_repo):
    content = "hello world"
    _touch(tmp_repo / "data.json", content)

    entries = scan_directory(tmp_repo)
    assert len(entries) == 1

    entry = entries[0]
    assert entry.path == "data.json"
    assert entry.size == len(content)
    assert entry.extension == ".json"
    assert entry.last_modified > 0


# -------------------------------------------------------------------
# 5. Skips binary extensions
# -------------------------------------------------------------------
def test_scan_skips_binary_extensions(tmp_repo):
    _touch(tmp_repo / "logo.png", "\x89PNG")
    _touch(tmp_repo / "font.woff2", "woff2data")
    _touch(tmp_repo / "archive.zip", "PKdata")
    _touch(tmp_repo / "lib.so", "elfdata")
    _touch(tmp_repo / "yarn.lock", "lockdata")
    _touch(tmp_repo / "app.ts", "const x = 1;")

    entries = scan_directory(tmp_repo)
    paths = [e.path for e in entries]

    assert paths == ["app.ts"]

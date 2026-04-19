"""Tests for archie.engine.scanner."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from archie.engine.scanner import scan_directory
import archie.standalone.scanner as scanner


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


# -------------------------------------------------------------------
# 6. Swift function extraction
# -------------------------------------------------------------------
def test_extract_swift_functions_returns_public_top_level_and_extensions():
    """Swift fixture has 1 public top-level fn, 1 public extension method, 1 private fn."""
    fixture = Path(__file__).parent / "fixtures" / "sample_sources" / "swift" / "Extensions.swift"
    content = fixture.read_text()
    results = scanner._extract_swift_functions(content, "Extensions.swift")

    names = sorted(r["name"] for r in results)
    assert names == ["String.trimmed", "formatLocalizedDate"]

    # All returned entries are exported, language=swift, kind=function
    for r in results:
        assert r["exported"] is True
        assert r["language"] == "swift"
        assert r["kind"] == "function"
        assert r["file"] == "Extensions.swift"

    # Signature for the top-level fn is captured (no leading `public ` is fine; signature is the canonical `func ...` form trimmed)
    top = next(r for r in results if r["name"] == "formatLocalizedDate")
    assert "func formatLocalizedDate" in top["signature"]
    assert "Date" in top["signature"]


def test_extract_swift_functions_skips_private_and_internal():
    """Verify private/fileprivate/internal/no-modifier funcs are excluded."""
    import textwrap
    content = textwrap.dedent("""
        public func keepMe() -> Int { return 1 }
        private func skip1() {}
        fileprivate func skip2() {}
        internal func skip3() {}
        func skipDefault() {}
    """)
    results = scanner._extract_swift_functions(content, "Test.swift")
    names = [r["name"] for r in results]
    assert names == ["keepMe"]


# -------------------------------------------------------------------
# 7. TypeScript/JavaScript function extraction
# -------------------------------------------------------------------
def test_extract_typescript_functions_returns_exported_functions_and_arrows():
    """TS fixture has 1 export function, 1 export const arrow, 1 unexported function."""
    fixture = Path(__file__).parent / "fixtures" / "sample_sources" / "typescript" / "utils.ts"
    content = fixture.read_text()
    results = scanner._extract_typescript_functions(content, "utils.ts")

    names = sorted(r["name"] for r in results)
    assert names == ["deduplicate", "formatDate"]

    for r in results:
        assert r["exported"] is True
        assert r["language"] == "typescript"
        assert r["kind"] == "function"
        assert r["file"] == "utils.ts"

    # formatDate is the export function
    fmt = next(r for r in results if r["name"] == "formatDate")
    assert "export function formatDate" in fmt["signature"]
    assert "Date" in fmt["signature"]

    # deduplicate is the arrow const
    dedup = next(r for r in results if r["name"] == "deduplicate")
    assert "export const deduplicate" in dedup["signature"]


def test_extract_typescript_functions_skips_unexported():
    content = """
export function keepMe(x: number): number { return x; }
function skipMe(x: number): number { return x; }
const skipArrow = (x: number) => x;
export const _privateArrow = (x: number) => x;
"""
    results = scanner._extract_typescript_functions(content, "test.ts")
    names = [r["name"] for r in results]
    assert names == ["keepMe"]  # _privateArrow skipped due to leading underscore

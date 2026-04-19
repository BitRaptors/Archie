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


# -------------------------------------------------------------------
# 8. Python function extraction
# -------------------------------------------------------------------
def test_extract_python_functions_returns_module_level_only():
    """Python fixture has 1 module-level def, 1 _private def, 1 class method."""
    fixture = Path(__file__).parent / "fixtures" / "sample_sources" / "python" / "helpers.py"
    content = fixture.read_text()
    results = scanner._extract_python_functions(content, "helpers.py")

    names = sorted(r["name"] for r in results)
    assert names == ["format_time"]

    fmt = results[0]
    assert fmt["exported"] is True
    assert fmt["language"] == "python"
    assert fmt["kind"] == "function"
    assert fmt["file"] == "helpers.py"
    assert "def format_time" in fmt["signature"]
    assert "datetime" in fmt["signature"]


def test_extract_python_functions_skips_class_methods_and_underscores():
    content = '''
def public_one(x: int) -> int:
    return x

def _private_skip(x: int) -> int:
    return x

async def async_one(x: int) -> int:
    return x

class Foo:
    def method_skip(self, x: int) -> int:
        return x
'''
    results = scanner._extract_python_functions(content, "test.py")
    names = sorted(r["name"] for r in results)
    assert names == ["async_one", "public_one"]


# -------------------------------------------------------------------
# 9. extract_symbols integration — wiring + test-path filtering
# -------------------------------------------------------------------
def test_run_scan_emits_symbols_for_sample_sources(tmp_path):
    """Running the scanner on the sample_sources fixture emits symbols[] with
    entries from each supported language."""
    import shutil
    fixture_root = Path(__file__).parent / "fixtures" / "sample_sources"
    project = tmp_path / "project"
    shutil.copytree(fixture_root, project)

    scan = scanner.run_scan(str(project))
    assert "symbols" in scan

    by_lang = {}
    for s in scan["symbols"]:
        by_lang.setdefault(s["language"], []).append(s["name"])

    # Swift fixture contributes formatLocalizedDate + String.trimmed
    assert "formatLocalizedDate" in by_lang.get("swift", [])
    assert "String.trimmed" in by_lang.get("swift", [])

    # TS fixture contributes formatDate + deduplicate
    assert "formatDate" in by_lang.get("typescript", [])
    assert "deduplicate" in by_lang.get("typescript", [])

    # Python fixture contributes format_time
    assert "format_time" in by_lang.get("python", [])

    # Private/test entries excluded
    all_names = [s["name"] for s in scan["symbols"]]
    assert "_internalHelper" not in all_names
    assert "privateHelper" not in all_names
    assert "_private_helper" not in all_names


def test_extract_symbols_filters_test_paths(tmp_path):
    """Files whose path matches a test pattern are excluded."""
    files = [
        {"path": "src/utils.ts", "extension": ".ts", "size": 100},
        {"path": "src/__tests__/utils.test.ts", "extension": ".ts", "size": 100},
        {"path": "MyAppTests/SomeTest.swift", "extension": ".swift", "size": 100},
        {"path": "tests/test_helpers.py", "extension": ".py", "size": 100},
    ]
    # Create dummy files so the read succeeds
    for f in files:
        p = tmp_path / f["path"]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("export function noop() {}\n" if f["extension"].startswith(".t") else "def noop(): pass\n")

    symbols = scanner.extract_symbols(tmp_path, files)
    files_seen = {s["file"] for s in symbols}
    assert "src/utils.ts" in files_seen
    assert "src/__tests__/utils.test.ts" not in files_seen
    assert "MyAppTests/SomeTest.swift" not in files_seen
    assert "tests/test_helpers.py" not in files_seen

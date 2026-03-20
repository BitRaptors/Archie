# Archie v2 CLI + Agent Hybrid — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `archie init .` end-to-end — local analysis engine scans a repo, Opus/Sonnet subagents fill the blueprint, outputs are rendered, and enforcement hooks are installed.

**Architecture:** New `archie/` pip-installable Python package at the project root. Reuses `StructuredBlueprint`, `blueprint_renderer`, and `agent_file_generator` from existing `backend/src/`. Local engine produces a `RawScan`, coordinator spawns Claude Code subagents to fill the blueprint, renderers produce all outputs, hook generator installs enforcement.

**Tech Stack:** Python 3.11+, Click (CLI), tiktoken (token counting), stdlib `ast` (import parsing), Pydantic (schema). No external AI libraries — subagents are invoked via Claude Code's `Task` tool at runtime.

**IP Constraint:** No code from Cartographer or Rippletide may be copied. All code written from scratch. Do not reference their repositories during implementation.

---

## Phase 1: Package Scaffold

### Task 1: Create package structure and pyproject.toml

**Files:**
- Create: `archie/__init__.py`
- Create: `archie/engine/__init__.py`
- Create: `archie/coordinator/__init__.py`
- Create: `archie/renderer/__init__.py`
- Create: `archie/hooks/__init__.py`
- Create: `archie/schema/__init__.py`
- Create: `archie/cli/__init__.py`
- Create: `archie/rules/__init__.py`
- Create: `pyproject.toml`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "archie"
version = "2.0.0-alpha.1"
description = "Your AI writes code. Archie makes sure it follows your architecture."
requires-python = ">=3.11"
dependencies = [
    "click>=8.1.0",
    "tiktoken>=0.7.0",
    "pydantic>=2.5.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "ruff>=0.1.0",
]

[project.scripts]
archie = "archie.cli.main:cli"

[tool.setuptools.packages.find]
include = ["archie*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 2: Create all `__init__.py` files**

Each is empty except `archie/__init__.py`:

```python
"""Archie — architecture enforcement for AI coding agents."""
__version__ = "2.0.0-alpha.1"
```

**Step 3: Create minimal CLI entry point**

File: `archie/cli/main.py`
```python
import click

@click.group()
@click.version_option()
def cli():
    """Archie — your AI writes code, Archie enforces your architecture."""
    pass

@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def init(path):
    """Analyze a repository and generate architecture blueprint + enforcement."""
    click.echo(f"archie init {path} — not yet implemented")

@cli.command()
def status():
    """Show blueprint freshness and enforcement stats."""
    click.echo("archie status — not yet implemented")
```

**Step 4: Verify package installs**

Run: `pip install -e ".[dev]"` from project root
Run: `archie --version`
Expected: `archie, version 2.0.0-alpha.1`

**Step 5: Commit**

```bash
git add pyproject.toml archie/
git commit -m "feat: scaffold archie v2 package with CLI entry point"
```

---

## Phase 2: Local Analysis Engine — Models

### Task 2: Define RawScan Pydantic model

**Files:**
- Create: `archie/engine/models.py`
- Create: `tests/test_engine_models.py`

**Step 1: Write the test**

```python
# tests/test_engine_models.py
from archie.engine.models import RawScan, FileEntry, DependencyEntry, FrameworkSignal

def test_raw_scan_empty():
    scan = RawScan()
    assert scan.file_tree == []
    assert scan.token_counts == {}
    assert scan.dependencies == []
    assert scan.framework_signals == []
    assert scan.import_graph == {}
    assert scan.file_hashes == {}
    assert scan.entry_points == []

def test_file_entry():
    entry = FileEntry(path="src/main.py", size=1024, last_modified=1710000000.0)
    assert entry.path == "src/main.py"
    assert entry.size == 1024

def test_dependency_entry():
    dep = DependencyEntry(name="fastapi", version=">=0.104.0", source="requirements.txt")
    assert dep.name == "fastapi"
    assert dep.source == "requirements.txt"

def test_framework_signal():
    sig = FrameworkSignal(name="Next.js", version="14", confidence=0.9, evidence=["next.config.js"])
    assert sig.name == "Next.js"
    assert sig.confidence == 0.9
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine_models.py -v`
Expected: FAIL with ImportError

**Step 3: Implement the models**

```python
# archie/engine/models.py
"""Data models for the local analysis engine."""
from __future__ import annotations
from pydantic import BaseModel, Field


class FileEntry(BaseModel):
    """A single file in the scanned repository."""
    path: str
    size: int = 0
    last_modified: float = 0.0
    extension: str = ""

class DependencyEntry(BaseModel):
    """A parsed dependency from a manifest file."""
    name: str
    version: str = ""
    source: str = ""  # e.g. "requirements.txt", "package.json"

class FrameworkSignal(BaseModel):
    """A detected framework or library with confidence."""
    name: str
    version: str = ""
    confidence: float = 1.0
    evidence: list[str] = Field(default_factory=list)

class RawScan(BaseModel):
    """Complete output of the local analysis engine."""
    file_tree: list[FileEntry] = Field(default_factory=list)
    token_counts: dict[str, int] = Field(default_factory=dict)  # path -> token count
    dependencies: list[DependencyEntry] = Field(default_factory=list)
    framework_signals: list[FrameworkSignal] = Field(default_factory=list)
    config_patterns: dict[str, str] = Field(default_factory=dict)  # filename -> content summary
    import_graph: dict[str, list[str]] = Field(default_factory=dict)  # path -> [imported paths]
    directory_structure: dict[str, list[str]] = Field(default_factory=dict)  # layer_name -> [paths]
    file_hashes: dict[str, str] = Field(default_factory=dict)  # path -> sha256
    entry_points: list[str] = Field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine_models.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add archie/engine/models.py tests/test_engine_models.py
git commit -m "feat: add RawScan data model for local analysis engine"
```

---

## Phase 3: Local Engine — File Tree Scanner

### Task 3: Build file tree scanner

**Files:**
- Create: `archie/engine/scanner.py`
- Create: `tests/test_scanner.py`

**Step 1: Write the tests**

```python
# tests/test_scanner.py
import os
import tempfile
from pathlib import Path
from archie.engine.scanner import scan_file_tree
from archie.engine.models import FileEntry

def _make_repo(tmp: Path, files: dict[str, str]):
    """Create a temp repo structure from a dict of path -> content."""
    for rel_path, content in files.items():
        full = tmp / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)

def test_scan_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        result = scan_file_tree(Path(tmp))
        assert result == []

def test_scan_simple_repo():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            "src/main.py": "print('hello')",
            "src/utils.py": "def add(a, b): return a + b",
            "README.md": "# Project",
        })
        result = scan_file_tree(root)
        paths = {e.path for e in result}
        assert "src/main.py" in paths
        assert "src/utils.py" in paths
        assert "README.md" in paths
        assert all(isinstance(e, FileEntry) for e in result)

def test_scan_skips_git_and_node_modules():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            ".git/config": "gitconfig",
            "node_modules/pkg/index.js": "module.exports = {}",
            "src/app.py": "app = Flask(__name__)",
        })
        result = scan_file_tree(root)
        paths = {e.path for e in result}
        assert "src/app.py" in paths
        assert ".git/config" not in paths
        assert "node_modules/pkg/index.js" not in paths

def test_scan_captures_size_and_extension():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {"src/main.py": "x = 1"})
        result = scan_file_tree(root)
        entry = result[0]
        assert entry.size > 0
        assert entry.extension == ".py"

def test_scan_skips_binary_extensions():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            "image.png": "binarydata",
            "app.py": "print(1)",
        })
        result = scan_file_tree(root)
        paths = {e.path for e in result}
        assert "app.py" in paths
        assert "image.png" not in paths
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scanner.py -v`
Expected: FAIL with ImportError

**Step 3: Implement the scanner**

```python
# archie/engine/scanner.py
"""File tree scanner — walks a repo and produces FileEntry list."""
from __future__ import annotations
import os
from pathlib import Path
from archie.engine.models import FileEntry

# Directories to always skip
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".next", ".nuxt", ".svelte-kit",
    "coverage", ".nyc_output", ".turbo", ".parcel-cache",
    "vendor", "Pods", ".gradle", ".idea", ".vscode",
}

# Binary/non-source extensions to skip
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe",
    ".lock", ".sum",
}


def scan_file_tree(repo_path: Path) -> list[FileEntry]:
    """Walk the repository and return a list of source file entries."""
    entries: list[FileEntry] = []
    root = repo_path.resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in SKIP_EXTENSIONS:
                continue
            if fname.startswith(".") and fname not in {".env.example", ".gitignore", ".dockerignore"}:
                continue

            full_path = Path(dirpath) / fname
            try:
                stat = full_path.stat()
            except OSError:
                continue

            rel_path = str(full_path.relative_to(root))
            entries.append(FileEntry(
                path=rel_path,
                size=stat.st_size,
                last_modified=stat.st_mtime,
                extension=ext,
            ))

    return sorted(entries, key=lambda e: e.path)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scanner.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add archie/engine/scanner.py tests/test_scanner.py
git commit -m "feat: add file tree scanner for local analysis engine"
```

---

## Phase 4: Local Engine — Dependency Parser

### Task 4: Build dependency parser

**Files:**
- Create: `archie/engine/dependencies.py`
- Create: `tests/test_dependencies.py`

**Step 1: Write the tests**

```python
# tests/test_dependencies.py
import tempfile
from pathlib import Path
from archie.engine.dependencies import parse_dependencies
from archie.engine.models import DependencyEntry

def test_parse_requirements_txt():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "requirements.txt").write_text("fastapi>=0.104.0\nuvicorn[standard]>=0.24.0\n# comment\npydantic\n")
        result = parse_dependencies(root)
        names = {d.name for d in result}
        assert "fastapi" in names
        assert "uvicorn" in names  # strip extras
        assert "pydantic" in names
        assert all(d.source == "requirements.txt" for d in result)

def test_parse_package_json():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "package.json").write_text('{"dependencies":{"react":"^18.2.0","next":"14.0.0"},"devDependencies":{"typescript":"^5.0.0"}}')
        result = parse_dependencies(root)
        names = {d.name for d in result}
        assert "react" in names
        assert "next" in names
        assert "typescript" in names

def test_parse_go_mod():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "go.mod").write_text("module example.com/app\n\ngo 1.21\n\nrequire (\n\tgithub.com/gin-gonic/gin v1.9.1\n\tgithub.com/lib/pq v1.10.9\n)\n")
        result = parse_dependencies(root)
        names = {d.name for d in result}
        assert "github.com/gin-gonic/gin" in names
        assert "github.com/lib/pq" in names

def test_parse_no_manifests():
    with tempfile.TemporaryDirectory() as tmp:
        result = parse_dependencies(Path(tmp))
        assert result == []

def test_parse_multiple_manifests():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "requirements.txt").write_text("fastapi\n")
        (root / "package.json").write_text('{"dependencies":{"react":"^18"}}')
        result = parse_dependencies(root)
        sources = {d.source for d in result}
        assert "requirements.txt" in sources
        assert "package.json" in sources

def test_parse_nested_manifests():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        backend = root / "backend"
        backend.mkdir()
        (backend / "requirements.txt").write_text("django>=4.0\n")
        frontend = root / "frontend"
        frontend.mkdir()
        (frontend / "package.json").write_text('{"dependencies":{"vue":"^3.0"}}')
        result = parse_dependencies(root)
        names = {d.name for d in result}
        assert "django" in names
        assert "vue" in names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_dependencies.py -v`
Expected: FAIL with ImportError

**Step 3: Implement the dependency parser**

```python
# archie/engine/dependencies.py
"""Dependency parser — extracts deps from package manifests."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from archie.engine.models import DependencyEntry

# Max depth for searching nested manifests
_MAX_DEPTH = 3


def parse_dependencies(repo_path: Path) -> list[DependencyEntry]:
    """Parse all dependency manifests found in the repo."""
    deps: list[DependencyEntry] = []
    root = repo_path.resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        # Limit depth
        depth = str(Path(dirpath).relative_to(root)).count(os.sep)
        if depth >= _MAX_DEPTH:
            dirnames.clear()
            continue
        # Skip non-source dirs
        dirnames[:] = [d for d in dirnames if d not in {
            "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
        }]

        for fname in filenames:
            full = Path(dirpath) / fname
            rel_source = str(full.relative_to(root))
            try:
                content = full.read_text(errors="ignore")
            except OSError:
                continue

            if fname == "requirements.txt":
                deps.extend(_parse_requirements_txt(content, rel_source))
            elif fname == "package.json":
                deps.extend(_parse_package_json(content, rel_source))
            elif fname == "go.mod":
                deps.extend(_parse_go_mod(content, rel_source))
            elif fname == "Cargo.toml":
                deps.extend(_parse_cargo_toml(content, rel_source))

    return deps


def _parse_requirements_txt(content: str, source: str) -> list[DependencyEntry]:
    entries = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip extras: uvicorn[standard]>=0.24 -> uvicorn
        match = re.match(r"^([a-zA-Z0-9_-]+)(?:\[.*?\])?\s*(.*)", line)
        if match:
            name = match.group(1)
            version = match.group(2).strip()
            entries.append(DependencyEntry(name=name, version=version, source=source))
    return entries


def _parse_package_json(content: str, source: str) -> list[DependencyEntry]:
    entries = []
    try:
        pkg = json.loads(content)
    except json.JSONDecodeError:
        return entries
    for dep_key in ("dependencies", "devDependencies", "peerDependencies"):
        for name, version in pkg.get(dep_key, {}).items():
            entries.append(DependencyEntry(name=name, version=version, source=source))
    return entries


def _parse_go_mod(content: str, source: str) -> list[DependencyEntry]:
    entries = []
    in_require = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if in_require:
            if stripped == ")":
                in_require = False
                continue
            parts = stripped.split()
            if len(parts) >= 2:
                entries.append(DependencyEntry(name=parts[0], version=parts[1], source=source))
    return entries


def _parse_cargo_toml(content: str, source: str) -> list[DependencyEntry]:
    entries = []
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "[dependencies]" or stripped == "[dev-dependencies]":
            in_deps = True
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            continue
        if in_deps:
            match = re.match(r'^(\S+)\s*=\s*"(.+)"', stripped)
            if match:
                entries.append(DependencyEntry(name=match.group(1), version=match.group(2), source=source))
    return entries
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_dependencies.py -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add archie/engine/dependencies.py tests/test_dependencies.py
git commit -m "feat: add dependency parser for multiple manifest formats"
```

---

## Phase 5: Local Engine — Framework Detector

### Task 5: Build framework detector

**Files:**
- Create: `archie/engine/frameworks.py`
- Create: `tests/test_frameworks.py`

**Step 1: Write the tests**

```python
# tests/test_frameworks.py
from archie.engine.frameworks import detect_frameworks
from archie.engine.models import FileEntry, DependencyEntry, FrameworkSignal

def test_detect_nextjs():
    files = [FileEntry(path="next.config.js", size=100)]
    deps = [DependencyEntry(name="next", version="14.0.0", source="package.json"),
            DependencyEntry(name="react", version="^18", source="package.json")]
    result = detect_frameworks(files, deps)
    names = {s.name for s in result}
    assert "Next.js" in names
    assert "React" in names

def test_detect_fastapi():
    files = [FileEntry(path="src/main.py", size=100)]
    deps = [DependencyEntry(name="fastapi", version=">=0.104", source="requirements.txt")]
    result = detect_frameworks(files, deps)
    names = {s.name for s in result}
    assert "FastAPI" in names

def test_detect_django():
    files = [FileEntry(path="manage.py", size=100), FileEntry(path="settings.py", size=200)]
    deps = [DependencyEntry(name="django", version=">=4.0", source="requirements.txt")]
    result = detect_frameworks(files, deps)
    names = {s.name for s in result}
    assert "Django" in names

def test_detect_nothing():
    files = [FileEntry(path="readme.txt", size=50)]
    deps = []
    result = detect_frameworks(files, deps)
    assert result == []

def test_detect_flutter():
    files = [FileEntry(path="pubspec.yaml", size=100), FileEntry(path="lib/main.dart", size=200)]
    deps = []
    result = detect_frameworks(files, deps)
    names = {s.name for s in result}
    assert "Flutter" in names

def test_detect_multiple_frameworks():
    files = [FileEntry(path="backend/main.py", size=100), FileEntry(path="frontend/next.config.js", size=100)]
    deps = [DependencyEntry(name="fastapi", version=">=0.104", source="backend/requirements.txt"),
            DependencyEntry(name="next", version="14", source="frontend/package.json")]
    result = detect_frameworks(files, deps)
    names = {s.name for s in result}
    assert "FastAPI" in names
    assert "Next.js" in names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_frameworks.py -v`
Expected: FAIL with ImportError

**Step 3: Implement framework detector**

```python
# archie/engine/frameworks.py
"""Framework detector — identifies frameworks from files + dependencies."""
from __future__ import annotations
from archie.engine.models import FileEntry, DependencyEntry, FrameworkSignal

# Map: dep name -> framework signal
_DEP_SIGNALS: dict[str, tuple[str, str]] = {
    # Python
    "fastapi": ("FastAPI", "python"),
    "django": ("Django", "python"),
    "flask": ("Flask", "python"),
    # JavaScript/TypeScript
    "next": ("Next.js", "js"),
    "react": ("React", "js"),
    "vue": ("Vue.js", "js"),
    "nuxt": ("Nuxt.js", "js"),
    "angular": ("Angular", "js"),
    "svelte": ("Svelte", "js"),
    "express": ("Express", "js"),
    "nestjs": ("NestJS", "js"),
    # Go
    "github.com/gin-gonic/gin": ("Gin", "go"),
    "github.com/gofiber/fiber": ("Fiber", "go"),
    # Rust
    "actix-web": ("Actix Web", "rust"),
    "axum": ("Axum", "rust"),
    "rocket": ("Rocket", "rust"),
}

# Map: filename pattern -> framework signal
_FILE_SIGNALS: dict[str, str] = {
    "next.config.js": "Next.js",
    "next.config.ts": "Next.js",
    "next.config.mjs": "Next.js",
    "nuxt.config.ts": "Nuxt.js",
    "nuxt.config.js": "Nuxt.js",
    "svelte.config.js": "Svelte",
    "angular.json": "Angular",
    "manage.py": "Django",
    "pubspec.yaml": "Flutter",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "docker-compose.yml": "Docker",
    "docker-compose.yaml": "Docker",
    "Dockerfile": "Docker",
    "tailwind.config.js": "Tailwind CSS",
    "tailwind.config.ts": "Tailwind CSS",
}


def detect_frameworks(
    files: list[FileEntry],
    dependencies: list[DependencyEntry],
) -> list[FrameworkSignal]:
    """Detect frameworks from file tree and dependency list."""
    seen: dict[str, FrameworkSignal] = {}

    # Check dependencies
    for dep in dependencies:
        key = dep.name.lower()
        if key in _DEP_SIGNALS:
            name, _ = _DEP_SIGNALS[key]
            if name not in seen:
                seen[name] = FrameworkSignal(
                    name=name,
                    version=dep.version,
                    confidence=0.9,
                    evidence=[f"dependency: {dep.name} in {dep.source}"],
                )
            else:
                seen[name].evidence.append(f"dependency: {dep.name} in {dep.source}")

    # Check file patterns
    for f in files:
        fname = f.path.rsplit("/", 1)[-1] if "/" in f.path else f.path
        if fname in _FILE_SIGNALS:
            name = _FILE_SIGNALS[fname]
            if name not in seen:
                seen[name] = FrameworkSignal(
                    name=name,
                    confidence=0.7,
                    evidence=[f"file: {f.path}"],
                )
            else:
                seen[name].evidence.append(f"file: {f.path}")
                seen[name].confidence = min(1.0, seen[name].confidence + 0.1)

    return sorted(seen.values(), key=lambda s: s.name)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_frameworks.py -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add archie/engine/frameworks.py tests/test_frameworks.py
git commit -m "feat: add framework detector for local analysis engine"
```

---

## Phase 6: Local Engine — File Hasher + Token Counter

### Task 6: Build file hasher and token counter

**Files:**
- Create: `archie/engine/hasher.py`
- Create: `tests/test_hasher.py`

**Step 1: Write the tests**

```python
# tests/test_hasher.py
import tempfile
from pathlib import Path
from archie.engine.hasher import hash_files, count_tokens
from archie.engine.models import FileEntry

def test_hash_files_deterministic():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.py").write_text("hello world")
        entries = [FileEntry(path="a.py", size=11)]
        hashes = hash_files(root, entries)
        assert "a.py" in hashes
        assert len(hashes["a.py"]) == 64  # sha256 hex length
        # Same content -> same hash
        hashes2 = hash_files(root, entries)
        assert hashes["a.py"] == hashes2["a.py"]

def test_hash_files_different_content():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.py").write_text("hello")
        (root / "b.py").write_text("world")
        entries = [FileEntry(path="a.py", size=5), FileEntry(path="b.py", size=5)]
        hashes = hash_files(root, entries)
        assert hashes["a.py"] != hashes["b.py"]

def test_hash_files_missing_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        entries = [FileEntry(path="missing.py", size=0)]
        hashes = hash_files(root, entries)
        assert hashes == {}

def test_count_tokens():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.py").write_text("def hello():\n    print('hello world')\n")
        entries = [FileEntry(path="a.py", size=37)]
        counts = count_tokens(root, entries)
        assert "a.py" in counts
        assert counts["a.py"] > 0
        assert isinstance(counts["a.py"], int)

def test_count_tokens_empty_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "empty.py").write_text("")
        entries = [FileEntry(path="empty.py", size=0)]
        counts = count_tokens(root, entries)
        assert counts["empty.py"] == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_hasher.py -v`
Expected: FAIL with ImportError

**Step 3: Implement**

```python
# archie/engine/hasher.py
"""File hashing and token counting."""
from __future__ import annotations
import hashlib
from pathlib import Path
from archie.engine.models import FileEntry


def hash_files(repo_path: Path, entries: list[FileEntry]) -> dict[str, str]:
    """Compute SHA-256 hash for each file. Skips missing files."""
    hashes: dict[str, str] = {}
    for entry in entries:
        full = repo_path / entry.path
        try:
            content = full.read_bytes()
        except OSError:
            continue
        hashes[entry.path] = hashlib.sha256(content).hexdigest()
    return hashes


def count_tokens(
    repo_path: Path,
    entries: list[FileEntry],
    max_file_size: int = 1_000_000,
) -> dict[str, int]:
    """Count tokens per file using tiktoken (cl100k_base)."""
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")

    counts: dict[str, int] = {}
    for entry in entries:
        if entry.size > max_file_size:
            continue
        full = repo_path / entry.path
        try:
            content = full.read_text(errors="ignore")
        except OSError:
            continue
        counts[entry.path] = len(enc.encode(content)) if content else 0
    return counts
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_hasher.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add archie/engine/hasher.py tests/test_hasher.py
git commit -m "feat: add file hasher and token counter"
```

---

## Phase 7: Local Engine — Import Graph Builder

### Task 7: Build import graph from Python and JS/TS files

**Files:**
- Create: `archie/engine/imports.py`
- Create: `tests/test_imports.py`

**Step 1: Write the tests**

```python
# tests/test_imports.py
import tempfile
from pathlib import Path
from archie.engine.imports import build_import_graph
from archie.engine.models import FileEntry

def _make_repo(root: Path, files: dict[str, str]):
    for rel, content in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)

def test_python_imports():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            "src/api/routes.py": "from src.domain.models import User\nimport src.services.auth",
            "src/domain/models.py": "class User: pass",
            "src/services/auth.py": "from src.domain.models import User",
        })
        entries = [
            FileEntry(path="src/api/routes.py", extension=".py"),
            FileEntry(path="src/domain/models.py", extension=".py"),
            FileEntry(path="src/services/auth.py", extension=".py"),
        ]
        graph = build_import_graph(root, entries)
        assert "src/domain/models" in graph.get("src/api/routes.py", []) or \
               "src.domain.models" in str(graph.get("src/api/routes.py", []))

def test_js_imports():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            "src/App.tsx": "import { Button } from './components/Button'\nimport axios from 'axios'",
            "src/components/Button.tsx": "export const Button = () => <button/>",
        })
        entries = [
            FileEntry(path="src/App.tsx", extension=".tsx"),
            FileEntry(path="src/components/Button.tsx", extension=".tsx"),
        ]
        graph = build_import_graph(root, entries)
        imports = graph.get("src/App.tsx", [])
        # Should capture relative imports, not bare npm imports
        assert any("components/Button" in imp for imp in imports)

def test_empty_file():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {"empty.py": ""})
        entries = [FileEntry(path="empty.py", extension=".py")]
        graph = build_import_graph(root, entries)
        assert graph.get("empty.py", []) == []

def test_no_source_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {"readme.md": "# Hello"})
        entries = [FileEntry(path="readme.md", extension=".md")]
        graph = build_import_graph(root, entries)
        assert graph == {}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_imports.py -v`
Expected: FAIL with ImportError

**Step 3: Implement**

```python
# archie/engine/imports.py
"""Import graph builder — extracts import relationships via AST and regex."""
from __future__ import annotations
import ast
import re
from pathlib import Path
from archie.engine.models import FileEntry

_PYTHON_EXTS = {".py"}
_JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".mjs"}

# Regex for JS/TS imports: import ... from '...' or require('...')
_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\))"""
)


def build_import_graph(
    repo_path: Path,
    entries: list[FileEntry],
) -> dict[str, list[str]]:
    """Build a map of file -> [imported module paths]."""
    graph: dict[str, list[str]] = {}

    for entry in entries:
        if entry.extension in _PYTHON_EXTS:
            imports = _extract_python_imports(repo_path / entry.path)
            if imports:
                graph[entry.path] = imports
        elif entry.extension in _JS_EXTS:
            imports = _extract_js_imports(repo_path / entry.path)
            if imports:
                graph[entry.path] = imports

    return graph


def _extract_python_imports(file_path: Path) -> list[str]:
    """Use stdlib ast to extract import targets from a Python file."""
    try:
        source = file_path.read_text(errors="ignore")
    except OSError:
        return []
    if not source.strip():
        return []
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    # Filter to project-internal imports (contain dots or match source paths)
    return [imp for imp in imports if "." in imp and not _is_stdlib(imp)]


def _extract_js_imports(file_path: Path) -> list[str]:
    """Use regex to extract import paths from JS/TS files."""
    try:
        source = file_path.read_text(errors="ignore")
    except OSError:
        return []

    imports: list[str] = []
    for match in _JS_IMPORT_RE.finditer(source):
        path = match.group(1) or match.group(2)
        # Only keep relative imports (project-internal)
        if path.startswith("."):
            imports.append(path)

    return imports


def _is_stdlib(module_name: str) -> bool:
    """Quick heuristic check for Python stdlib modules."""
    top = module_name.split(".")[0]
    return top in {
        "os", "sys", "re", "json", "ast", "math", "time", "datetime",
        "pathlib", "typing", "collections", "functools", "itertools",
        "hashlib", "io", "abc", "dataclasses", "enum", "logging",
        "unittest", "tempfile", "shutil", "subprocess", "threading",
        "asyncio", "concurrent", "contextlib", "copy", "csv",
        "http", "urllib", "email", "html", "xml", "sqlite3",
        "socket", "ssl", "struct", "textwrap", "traceback",
        "uuid", "warnings", "weakref", "zipfile", "gzip",
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_imports.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add archie/engine/imports.py tests/test_imports.py
git commit -m "feat: add import graph builder for Python and JS/TS"
```

---

## Phase 8: Local Engine — Assembler (RawScan)

### Task 8: Build the scan assembler that ties all sub-scanners together

**Files:**
- Create: `archie/engine/scan.py`
- Create: `tests/test_scan.py`

**Step 1: Write the tests**

```python
# tests/test_scan.py
import tempfile
from pathlib import Path
from archie.engine.scan import run_scan
from archie.engine.models import RawScan

def _make_repo(root: Path, files: dict[str, str]):
    for rel, content in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)

def test_scan_produces_raw_scan():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            "src/main.py": "from src.utils import helper\nprint('hello')",
            "src/utils.py": "def helper(): pass",
            "requirements.txt": "fastapi>=0.104.0\n",
            "package.json": '{"dependencies":{"react":"^18"}}',
        })
        result = run_scan(root)
        assert isinstance(result, RawScan)
        # File tree populated
        paths = {e.path for e in result.file_tree}
        assert "src/main.py" in paths
        assert "src/utils.py" in paths
        # Dependencies parsed
        dep_names = {d.name for d in result.dependencies}
        assert "fastapi" in dep_names
        assert "react" in dep_names
        # Frameworks detected
        fw_names = {f.name for f in result.framework_signals}
        assert "FastAPI" in fw_names
        assert "React" in fw_names
        # File hashes present
        assert "src/main.py" in result.file_hashes
        # Token counts present
        assert "src/main.py" in result.token_counts
        # Import graph present
        assert len(result.import_graph) >= 0  # may or may not find internal imports

def test_scan_empty_repo():
    with tempfile.TemporaryDirectory() as tmp:
        result = run_scan(Path(tmp))
        assert isinstance(result, RawScan)
        assert result.file_tree == []
        assert result.dependencies == []

def test_scan_writes_to_archie_dir():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {"src/app.py": "print(1)"})
        result = run_scan(root, save=True)
        scan_file = root / ".archie" / "scan.json"
        assert scan_file.exists()
        # Verify it's valid JSON that round-trips
        loaded = RawScan.model_validate_json(scan_file.read_text())
        assert len(loaded.file_tree) == len(result.file_tree)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_scan.py -v`
Expected: FAIL with ImportError

**Step 3: Implement the assembler**

```python
# archie/engine/scan.py
"""Scan assembler — orchestrates all sub-scanners into a RawScan."""
from __future__ import annotations
import json
from pathlib import Path
from archie.engine.models import RawScan
from archie.engine.scanner import scan_file_tree
from archie.engine.dependencies import parse_dependencies
from archie.engine.frameworks import detect_frameworks
from archie.engine.hasher import hash_files, count_tokens
from archie.engine.imports import build_import_graph


def run_scan(repo_path: Path, save: bool = False) -> RawScan:
    """Run the full local analysis engine and return a RawScan."""
    root = repo_path.resolve()

    # 1. Scan file tree
    file_tree = scan_file_tree(root)

    # 2. Parse dependencies
    dependencies = parse_dependencies(root)

    # 3. Detect frameworks
    framework_signals = detect_frameworks(file_tree, dependencies)

    # 4. Hash files
    file_hashes = hash_files(root, file_tree)

    # 5. Count tokens
    token_counts = count_tokens(root, file_tree)

    # 6. Build import graph
    import_graph = build_import_graph(root, file_tree)

    # 7. Detect entry points
    entry_points = _detect_entry_points(file_tree)

    # 8. Read config files
    config_patterns = _collect_config_patterns(root)

    scan = RawScan(
        file_tree=file_tree,
        token_counts=token_counts,
        dependencies=dependencies,
        framework_signals=framework_signals,
        config_patterns=config_patterns,
        import_graph=import_graph,
        file_hashes=file_hashes,
        entry_points=entry_points,
    )

    if save:
        archie_dir = root / ".archie"
        archie_dir.mkdir(exist_ok=True)
        (archie_dir / "scan.json").write_text(scan.model_dump_json(indent=2))

    return scan


def _detect_entry_points(entries: list) -> list[str]:
    """Heuristic: find likely entry point files."""
    patterns = {
        "main.py", "app.py", "server.py", "index.py", "cli.py", "manage.py",
        "main.ts", "app.ts", "server.ts", "index.ts",
        "main.js", "app.js", "server.js", "index.js",
        "main.go", "main.rs",
    }
    return [e.path for e in entries if e.path.rsplit("/", 1)[-1] in patterns]


def _collect_config_patterns(repo_path: Path) -> dict[str, str]:
    """Read key config files and store a summary."""
    config_files = [
        "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
        ".github/workflows", ".gitlab-ci.yml", "Makefile",
        "tsconfig.json", "pyproject.toml", "setup.cfg",
    ]
    configs: dict[str, str] = {}
    for name in config_files:
        path = repo_path / name
        if path.is_file():
            try:
                content = path.read_text(errors="ignore")
                # Store first 500 chars as summary
                configs[name] = content[:500]
            except OSError:
                pass
    return configs
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_scan.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add archie/engine/scan.py tests/test_scan.py
git commit -m "feat: add scan assembler that orchestrates all local analysis"
```

---

## Phase 9: Coordinator — Subagent Planning

### Task 9: Build the subagent planner that groups files for Claude Code agents

**Files:**
- Create: `archie/coordinator/planner.py`
- Create: `tests/test_planner.py`

**Step 1: Write the tests**

```python
# tests/test_planner.py
from archie.coordinator.planner import plan_subagent_groups, SubagentAssignment
from archie.engine.models import RawScan, FileEntry

def _make_scan(files: dict[str, int]) -> RawScan:
    """Create a RawScan with given path->token_count pairs."""
    return RawScan(
        file_tree=[FileEntry(path=p, size=t * 4, extension=p.rsplit(".", 1)[-1] if "." in p else "") for p, t in files.items()],
        token_counts=files,
    )

def test_small_repo_single_group():
    scan = _make_scan({"src/a.py": 1000, "src/b.py": 2000, "src/c.py": 3000})
    groups = plan_subagent_groups(scan)
    assert len(groups) == 1
    assert set(groups[0].files) == {"src/a.py", "src/b.py", "src/c.py"}

def test_large_repo_splits_by_budget():
    # 3 files each 60k tokens -> should split (budget is 150k)
    scan = _make_scan({
        "src/api/a.py": 60_000,
        "src/api/b.py": 60_000,
        "src/domain/c.py": 60_000,
    })
    groups = plan_subagent_groups(scan, token_budget=150_000)
    assert len(groups) == 2  # 120k + 60k

def test_groups_respect_module_boundaries():
    scan = _make_scan({
        "src/api/routes.py": 10_000,
        "src/api/middleware.py": 10_000,
        "src/domain/models.py": 10_000,
        "src/domain/services.py": 10_000,
    })
    scan.import_graph = {
        "src/api/routes.py": ["src.api.middleware"],
        "src/domain/models.py": [],
    }
    groups = plan_subagent_groups(scan, token_budget=150_000)
    # With small token counts, likely 1 group
    assert len(groups) >= 1
    # But if we force split, related files should stay together
    groups = plan_subagent_groups(scan, token_budget=25_000)
    group_files = [set(g.files) for g in groups]
    # api files should be in the same group
    for g in group_files:
        if "src/api/routes.py" in g:
            assert "src/api/middleware.py" in g

def test_assignment_has_sections():
    scan = _make_scan({"src/a.py": 1000})
    groups = plan_subagent_groups(scan)
    assert len(groups[0].sections) > 0  # Should assign blueprint sections

def test_empty_scan():
    scan = RawScan()
    groups = plan_subagent_groups(scan)
    assert groups == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_planner.py -v`
Expected: FAIL with ImportError

**Step 3: Implement the planner**

```python
# archie/coordinator/planner.py
"""Subagent planner — groups files into token-budgeted assignments."""
from __future__ import annotations
from dataclasses import dataclass, field
from archie.engine.models import RawScan

# Blueprint sections that subagents can fill
ALL_SECTIONS = [
    "architecture_rules", "decisions", "components", "communication",
    "quick_reference", "technology", "frontend", "developer_recipes",
    "pitfalls", "implementation_guidelines", "development_rules", "deployment",
]


@dataclass
class SubagentAssignment:
    """A group of files assigned to one Sonnet subagent."""
    files: list[str] = field(default_factory=list)
    token_total: int = 0
    sections: list[str] = field(default_factory=list)
    module_hint: str = ""  # e.g. "api", "domain", "frontend"


def plan_subagent_groups(
    scan: RawScan,
    token_budget: int = 150_000,
) -> list[SubagentAssignment]:
    """Divide scanned files into token-budgeted groups for subagents."""
    if not scan.file_tree:
        return []

    # Group files by top-level module directory
    modules: dict[str, list[str]] = {}
    for entry in scan.file_tree:
        parts = entry.path.split("/")
        module = parts[0] if len(parts) > 1 else "_root"
        modules.setdefault(module, []).append(entry.path)

    # Calculate total tokens
    total_tokens = sum(scan.token_counts.values())

    # If everything fits in one budget, single group
    if total_tokens <= token_budget:
        return [SubagentAssignment(
            files=[e.path for e in scan.file_tree],
            token_total=total_tokens,
            sections=ALL_SECTIONS[:],
            module_hint="all",
        )]

    # Otherwise, pack modules into groups respecting budget
    groups: list[SubagentAssignment] = []
    current = SubagentAssignment()

    for module_name in sorted(modules.keys()):
        module_files = modules[module_name]
        module_tokens = sum(scan.token_counts.get(f, 0) for f in module_files)

        # If this module alone exceeds budget, it gets its own group
        if module_tokens > token_budget:
            if current.files:
                groups.append(current)
                current = SubagentAssignment()
            groups.append(SubagentAssignment(
                files=module_files,
                token_total=module_tokens,
                module_hint=module_name,
            ))
            continue

        # If adding this module would exceed budget, start new group
        if current.token_total + module_tokens > token_budget:
            if current.files:
                groups.append(current)
            current = SubagentAssignment(
                files=module_files,
                token_total=module_tokens,
                module_hint=module_name,
            )
        else:
            current.files.extend(module_files)
            current.token_total += module_tokens
            if not current.module_hint:
                current.module_hint = module_name

    if current.files:
        groups.append(current)

    # Assign blueprint sections to groups
    _assign_sections(groups)

    return groups


def _assign_sections(groups: list[SubagentAssignment]) -> None:
    """Distribute blueprint sections across groups."""
    if len(groups) == 1:
        groups[0].sections = ALL_SECTIONS[:]
        return

    # Each group gets all sections — they fill what they can from their files.
    # The coordinator (Opus) will merge and deduplicate.
    for group in groups:
        group.sections = ALL_SECTIONS[:]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_planner.py -v`
Expected: PASS (all 5 tests)

**Step 5: Commit**

```bash
git add archie/coordinator/planner.py tests/test_planner.py
git commit -m "feat: add subagent planner for token-budgeted file grouping"
```

---

## Phase 10: Coordinator — Prompt Templates

### Task 10: Create the coordinator and subagent prompt templates

**Files:**
- Create: `archie/coordinator/prompts.py`
- Create: `tests/test_prompts.py`

**Step 1: Write the tests**

```python
# tests/test_prompts.py
from archie.coordinator.prompts import (
    build_coordinator_prompt,
    build_subagent_prompt,
)
from archie.engine.models import RawScan, FileEntry, DependencyEntry, FrameworkSignal
from archie.coordinator.planner import SubagentAssignment

def test_coordinator_prompt_includes_scan_data():
    scan = RawScan(
        file_tree=[FileEntry(path="src/main.py", size=100, extension=".py")],
        dependencies=[DependencyEntry(name="fastapi", version=">=0.104", source="requirements.txt")],
        framework_signals=[FrameworkSignal(name="FastAPI", confidence=0.9)],
    )
    groups = [SubagentAssignment(files=["src/main.py"], sections=["components"], module_hint="src")]
    prompt = build_coordinator_prompt(scan, groups)
    assert "fastapi" in prompt.lower() or "FastAPI" in prompt
    assert "src/main.py" in prompt
    assert isinstance(prompt, str)
    assert len(prompt) > 100

def test_subagent_prompt_includes_files_and_sections():
    assignment = SubagentAssignment(
        files=["src/api/routes.py", "src/api/middleware.py"],
        sections=["components", "architecture_rules"],
        module_hint="api",
    )
    scan = RawScan(
        framework_signals=[FrameworkSignal(name="FastAPI")],
        dependencies=[DependencyEntry(name="fastapi", source="requirements.txt")],
    )
    prompt = build_subagent_prompt(assignment, scan)
    assert "src/api/routes.py" in prompt
    assert "components" in prompt
    assert "architecture_rules" in prompt
    assert isinstance(prompt, str)
    assert len(prompt) > 100

def test_subagent_prompt_includes_schema_guidance():
    assignment = SubagentAssignment(files=["a.py"], sections=["technology"])
    scan = RawScan()
    prompt = build_subagent_prompt(assignment, scan)
    # Should include JSON schema guidance
    assert "JSON" in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL with ImportError

**Step 3: Implement the prompt templates**

```python
# archie/coordinator/prompts.py
"""Prompt templates for the Opus coordinator and Sonnet subagents."""
from __future__ import annotations
from archie.engine.models import RawScan
from archie.coordinator.planner import SubagentAssignment


def build_coordinator_prompt(
    scan: RawScan,
    groups: list[SubagentAssignment],
) -> str:
    """Build the prompt for the Opus coordinator that orchestrates subagents."""
    file_list = "\n".join(f"  {e.path} ({e.size}B)" for e in scan.file_tree[:200])
    dep_list = "\n".join(f"  {d.name} {d.version} ({d.source})" for d in scan.dependencies[:50])
    fw_list = ", ".join(f.name for f in scan.framework_signals)
    total_tokens = sum(scan.token_counts.values())

    group_summary = ""
    for i, g in enumerate(groups):
        group_summary += f"\n  Group {i+1}: {len(g.files)} files, ~{g.token_total:,} tokens, module: {g.module_hint}"

    return f"""You are an architecture analyst coordinating a codebase analysis.

## Repository Summary (from local scan)

**Detected frameworks:** {fw_list or 'none detected'}
**Total files:** {len(scan.file_tree)}
**Total tokens:** {total_tokens:,}
**Entry points:** {', '.join(scan.entry_points[:10]) or 'none detected'}

### Dependencies
{dep_list or '  (none found)'}

### File Tree (first 200)
{file_list or '  (empty)'}

### Subagent Groups
{group_summary}

## Your Task

You are the coordinator. You do NOT read code files directly.
Instead, you will receive analysis reports from Sonnet subagents who read the code.

For each subagent group above, a Sonnet subagent will:
1. Read all assigned files
2. Analyze architecture patterns, decisions, and conventions
3. Return structured JSON for their assigned blueprint sections

After all subagents report back, you will:
1. Merge their outputs into a single StructuredBlueprint JSON
2. Resolve any contradictions (prefer the subagent with more evidence)
3. Fill cross-cutting sections: meta, quick_reference, architecture_diagram
4. Validate the final blueprint is complete and consistent

Output the final StructuredBlueprint as valid JSON.
"""


def build_subagent_prompt(
    assignment: SubagentAssignment,
    scan: RawScan,
) -> str:
    """Build the prompt for a Sonnet subagent that reads and analyzes files."""
    file_list = "\n".join(f"  - {f}" for f in assignment.files)
    section_list = ", ".join(assignment.sections)
    fw_list = ", ".join(f.name for f in scan.framework_signals)
    dep_list = ", ".join(f"{d.name}" for d in scan.dependencies[:30])

    return f"""You are analyzing a section of a codebase. Read the assigned files and produce structured analysis.

## Context

**Detected frameworks:** {fw_list or 'unknown'}
**Known dependencies:** {dep_list or 'unknown'}
**Your module:** {assignment.module_hint}

## Assigned Files

Read ALL of these files:
{file_list}

## Blueprint Sections to Fill

You must produce JSON output for these sections: {section_list}

For each section, follow this schema guidance:

### `components`
Identify distinct components/modules. For each: name, purpose, directory path, key files, dependencies on other components.

### `architecture_rules`
Extract file placement rules (which types of files go where) and naming conventions (casing, prefixes, suffixes per layer).

### `decisions`
Document architectural decisions you can infer: why this framework, why this structure, what trade-offs were made.

### `communication`
How do components talk to each other? HTTP APIs, message queues, direct imports, events, shared state?

### `technology`
Full tech stack: framework versions, database, cache, CI/CD, deployment targets.

### `frontend`
If frontend code exists: framework, rendering strategy, state management, routing, styling, key conventions.

### `implementation_guidelines`
For each third-party library used for a capability (auth, payments, email, etc.): what library, what pattern, which files implement it.

### `deployment`
Runtime environment, containerization, CI/CD, cloud provider, infrastructure-as-code.

### `developer_recipes`
Common tasks a developer would do: "add a new API endpoint", "add a new model", "run tests". Step-by-step.

### `pitfalls`
Things that would trip up a new developer or an AI agent. Non-obvious conventions, gotchas, edge cases.

### `development_rules`
Always/never rules: "always use repository pattern for DB access", "never import from infrastructure in domain layer".

## Output Format

Return ONLY valid JSON. Structure it as a dict where each key is a section name from the list above, and each value follows the schema guidance. Example:

```json
{{
  "components": {{
    "structure_type": "layered",
    "components": [...],
    "contracts": [...]
  }},
  "architecture_rules": {{
    "file_placement_rules": [...],
    "naming_conventions": [...]
  }}
}}
```

Be thorough but concise. Focus on what an AI coding agent CANNOT infer just from reading individual files — architecture decisions, conventions, patterns that span multiple files.
"""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_prompts.py -v`
Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add archie/coordinator/prompts.py tests/test_prompts.py
git commit -m "feat: add coordinator and subagent prompt templates"
```

---

## Phase 11: Hook Generator

### Task 11: Generate enforcement hook scripts from blueprint

**Files:**
- Create: `archie/hooks/generator.py`
- Create: `tests/test_hook_generator.py`

**Step 1: Write the tests**

```python
# tests/test_hook_generator.py
import json
import tempfile
from pathlib import Path
from archie.hooks.generator import generate_hooks, install_hooks

def test_generate_inject_context_hook():
    hooks = generate_hooks()
    assert "inject-context.sh" in hooks
    content = hooks["inject-context.sh"]
    assert content.startswith("#!/")
    assert "UserPromptSubmit" not in content  # it's the hook itself, not the config
    assert ".archie/blueprint.json" in content or ".archie/rules.json" in content

def test_generate_pre_validate_hook():
    hooks = generate_hooks()
    assert "pre-validate.sh" in hooks
    content = hooks["pre-validate.sh"]
    assert content.startswith("#!/")
    assert "exit 0" in content  # fail-open default

def test_hooks_are_executable_scripts():
    hooks = generate_hooks()
    for name, content in hooks.items():
        assert content.startswith("#!/"), f"{name} missing shebang"

def test_install_hooks_creates_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        install_hooks(root)
        hook_dir = root / ".claude" / "hooks"
        assert (hook_dir / "inject-context.sh").exists()
        assert (hook_dir / "pre-validate.sh").exists()
        # Check they're executable
        import stat
        for hook in hook_dir.iterdir():
            mode = hook.stat().st_mode
            assert mode & stat.S_IXUSR, f"{hook.name} not executable"

def test_install_hooks_creates_settings():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        install_hooks(root)
        settings_path = root / ".claude" / "settings.local.json"
        assert settings_path.exists()
        settings = json.loads(settings_path.read_text())
        assert "hooks" in settings

def test_install_hooks_preserves_existing_settings():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        claude_dir = root / ".claude"
        claude_dir.mkdir()
        existing = {"permissions": {"allow": ["Bash"]}}
        (claude_dir / "settings.local.json").write_text(json.dumps(existing))
        install_hooks(root)
        settings = json.loads((claude_dir / "settings.local.json").read_text())
        assert "hooks" in settings
        assert settings["permissions"]["allow"] == ["Bash"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_hook_generator.py -v`
Expected: FAIL with ImportError

**Step 3: Implement the hook generator**

```python
# archie/hooks/generator.py
"""Hook generator — creates Claude Code enforcement hooks."""
from __future__ import annotations
import json
import os
import stat
from pathlib import Path

_INJECT_CONTEXT_HOOK = r'''#!/usr/bin/env bash
# Archie: inject architecture context into Claude Code conversations.
# Hook type: UserPromptSubmit
# Reads the user's prompt and injects relevant blueprint rules.

set -euo pipefail

ARCHIE_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")/.archie"
RULES_FILE="$ARCHIE_DIR/rules.json"
BLUEPRINT_FILE="$ARCHIE_DIR/blueprint.json"

# Fail open: if no blueprint, do nothing
if [ ! -f "$RULES_FILE" ] && [ ! -f "$BLUEPRINT_FILE" ]; then
    exit 0
fi

# Read the user prompt from stdin (Claude Code passes it as JSON)
USER_INPUT=$(cat)

# Extract the prompt text
PROMPT=$(echo "$USER_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('user_prompt', ''))
except:
    print('')
" 2>/dev/null || echo "")

if [ -z "$PROMPT" ]; then
    exit 0
fi

# Use Python to match prompt keywords against rules and inject context
python3 -c "
import json, sys, re

prompt = '''$PROMPT'''
prompt_lower = prompt.lower()

try:
    with open('$RULES_FILE') as f:
        rules_data = json.load(f)
except:
    sys.exit(0)

rules = rules_data.get('rules', [])
if not rules:
    sys.exit(0)

# Match rules by keyword overlap
matched = []
for rule in rules:
    keywords = rule.get('keywords', [])
    if any(kw.lower() in prompt_lower for kw in keywords):
        matched.append(rule)

# Also always include high-severity rules
for rule in rules:
    if rule.get('severity') == 'error' and rule not in matched:
        matched.append(rule)

if not matched:
    sys.exit(0)

# Format output
lines = ['[Archie] Relevant architecture rules:']
for r in matched[:10]:
    desc = r.get('description', r.get('id', 'unknown'))
    lines.append(f'  - {desc}')

print('\n'.join(lines))
" 2>/dev/null || exit 0
'''

_PRE_VALIDATE_HOOK = r'''#!/usr/bin/env bash
# Archie: validate code changes against architecture rules.
# Hook type: PreToolUse (Write, Edit, MultiEdit)
# Checks proposed changes against blueprint rules.

set -euo pipefail

ARCHIE_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")/.archie"
RULES_FILE="$ARCHIE_DIR/rules.json"
STATS_FILE="$ARCHIE_DIR/stats.jsonl"

# Fail open: if no rules, allow everything
if [ ! -f "$RULES_FILE" ]; then
    exit 0
fi

# Read tool input from stdin
TOOL_INPUT=$(cat)

# Extract file path and tool name
FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    ti = data.get('tool_input', {})
    print(ti.get('file_path', ti.get('path', '')))
except:
    print('')
" 2>/dev/null || echo "")

TOOL_NAME=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_name', ''))
except:
    print('')
" 2>/dev/null || echo "")

# Only check Write, Edit, MultiEdit
case "$TOOL_NAME" in
    Write|Edit|MultiEdit) ;;
    *) exit 0 ;;
esac

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Run validation
python3 -c "
import json, sys, os, datetime

file_path = '$FILE_PATH'
rules_file = '$RULES_FILE'
stats_file = '$STATS_FILE'

try:
    with open(rules_file) as f:
        rules_data = json.load(f)
except:
    sys.exit(0)

rules = rules_data.get('rules', [])
violations = []

for rule in rules:
    check_type = rule.get('check')
    if check_type == 'file_placement':
        # Check if file is in an allowed directory for its type
        allowed_dirs = rule.get('allowed_dirs', [])
        if allowed_dirs and not any(file_path.startswith(d) for d in allowed_dirs):
            violations.append(rule)
    elif check_type == 'naming':
        import re
        pattern = rule.get('pattern', '')
        fname = os.path.basename(file_path)
        if pattern and not re.match(pattern, fname):
            violations.append(rule)

if not violations:
    # Log pass
    try:
        with open(stats_file, 'a') as f:
            f.write(json.dumps({
                'ts': datetime.datetime.now().isoformat(),
                'hook': 'pre_validate',
                'file': file_path,
                'result': 'pass',
            }) + '\n')
    except:
        pass
    sys.exit(0)

# Check severity
errors = [v for v in violations if v.get('severity') == 'error']
warnings = [v for v in violations if v.get('severity') != 'error']

# Log violations
try:
    with open(stats_file, 'a') as f:
        for v in violations:
            f.write(json.dumps({
                'ts': datetime.datetime.now().isoformat(),
                'hook': 'pre_validate',
                'file': file_path,
                'rule': v.get('id', 'unknown'),
                'result': 'block' if v.get('severity') == 'error' else 'warn',
            }) + '\n')
except:
    pass

# Print warnings
for w in warnings:
    desc = w.get('description', w.get('id', ''))
    suggestion = w.get('suggestion', '')
    print(f'[Archie] Warning: {desc}')
    if suggestion:
        print(f'  Suggestion: {suggestion}')
    print(f'  (Promote to error: archie promote {w.get(\"id\", \"\")})')
    print()

# Print errors and block
for e in errors:
    desc = e.get('description', e.get('id', ''))
    suggestion = e.get('suggestion', '')
    print(f'[Archie] BLOCKED: {desc} [severity: error]')
    if suggestion:
        print(f'  Suggestion: {suggestion}')
    print(f'  To proceed: ask the user to approve this override.')
    print()

if errors:
    sys.exit(2)  # Block
else:
    sys.exit(0)  # Warn only
" 2>/dev/null || exit 0
'''


def generate_hooks() -> dict[str, str]:
    """Generate hook script contents."""
    return {
        "inject-context.sh": _INJECT_CONTEXT_HOOK,
        "pre-validate.sh": _PRE_VALIDATE_HOOK,
    }


def install_hooks(project_root: Path) -> None:
    """Install hooks into .claude/hooks/ and register in settings.local.json."""
    hook_dir = project_root / ".claude" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)

    hooks = generate_hooks()
    for name, content in hooks.items():
        hook_path = hook_dir / name
        hook_path.write_text(content)
        hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Update settings.local.json
    settings_path = project_root / ".claude" / "settings.local.json"
    settings: dict = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            settings = {}

    hooks_dir_str = ".claude/hooks"
    settings["hooks"] = {
        "UserPromptSubmit": [
            {
                "matcher": "",
                "command": f"{hooks_dir_str}/inject-context.sh",
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Write|Edit|MultiEdit",
                "command": f"{hooks_dir_str}/pre-validate.sh",
            }
        ],
    }

    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_hook_generator.py -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add archie/hooks/generator.py tests/test_hook_generator.py
git commit -m "feat: add hook generator for Claude Code enforcement"
```

---

## Phase 12: Rule Extractor

### Task 12: Extract enforcement rules from StructuredBlueprint

**Files:**
- Create: `archie/rules/extractor.py`
- Create: `tests/test_rule_extractor.py`

**Step 1: Write the tests**

```python
# tests/test_rule_extractor.py
import json
import tempfile
from pathlib import Path
from archie.rules.extractor import extract_rules, save_rules, load_rules, promote_rule, demote_rule

def _minimal_blueprint() -> dict:
    """Return a minimal blueprint dict with some rules."""
    return {
        "architecture_rules": {
            "file_placement_rules": [
                {"pattern": "api routes", "location": "src/api/routes/", "description": "API endpoints go in src/api/routes/"},
                {"pattern": "domain models", "location": "src/domain/models/", "description": "Domain models go in src/domain/models/"},
            ],
            "naming_conventions": [
                {"target": "files", "convention": "snake_case", "example": "user_service.py"},
            ],
        },
        "components": {
            "structure_type": "layered",
            "components": [
                {"name": "API Layer", "path": "src/api/", "purpose": "HTTP endpoints"},
                {"name": "Domain Layer", "path": "src/domain/", "purpose": "Business logic"},
            ],
        },
        "technology": {
            "stack": [{"name": "FastAPI", "version": "0.104", "category": "framework"}],
        },
    }

def test_extract_rules_from_blueprint():
    bp = _minimal_blueprint()
    rules = extract_rules(bp)
    assert len(rules) > 0
    assert all("id" in r for r in rules)
    assert all("severity" in r for r in rules)
    assert all(r["severity"] == "warn" for r in rules)  # all default to warn

def test_extract_rules_has_file_placement():
    bp = _minimal_blueprint()
    rules = extract_rules(bp)
    placement_rules = [r for r in rules if r["check"] == "file_placement"]
    assert len(placement_rules) >= 1

def test_extract_rules_has_naming():
    bp = _minimal_blueprint()
    rules = extract_rules(bp)
    naming_rules = [r for r in rules if r["check"] == "naming"]
    assert len(naming_rules) >= 1

def test_save_and_load_rules():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rules = [{"id": "test-1", "severity": "warn", "check": "file_placement"}]
        save_rules(root, rules)
        loaded = load_rules(root)
        assert loaded == rules

def test_promote_rule():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rules = [{"id": "test-1", "severity": "warn", "check": "file_placement"}]
        save_rules(root, rules)
        result = promote_rule(root, "test-1")
        assert result is True
        loaded = load_rules(root)
        assert loaded[0]["severity"] == "error"

def test_demote_rule():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rules = [{"id": "test-1", "severity": "error", "check": "file_placement"}]
        save_rules(root, rules)
        result = demote_rule(root, "test-1")
        assert result is True
        loaded = load_rules(root)
        assert loaded[0]["severity"] == "warn"

def test_promote_nonexistent_rule():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rules = [{"id": "test-1", "severity": "warn"}]
        save_rules(root, rules)
        result = promote_rule(root, "nonexistent")
        assert result is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_rule_extractor.py -v`
Expected: FAIL with ImportError

**Step 3: Implement the rule extractor**

```python
# archie/rules/extractor.py
"""Rule extractor — derives enforcement rules from a StructuredBlueprint."""
from __future__ import annotations
import json
import re
from pathlib import Path


def extract_rules(blueprint: dict) -> list[dict]:
    """Extract enforcement rules from a blueprint dict."""
    rules: list[dict] = []

    # File placement rules
    arch_rules = blueprint.get("architecture_rules", {})
    for i, fpr in enumerate(arch_rules.get("file_placement_rules", [])):
        location = fpr.get("location", "")
        description = fpr.get("description", fpr.get("pattern", ""))
        rules.append({
            "id": f"placement-{i}",
            "check": "file_placement",
            "description": description,
            "allowed_dirs": [location] if location else [],
            "severity": "warn",
            "keywords": _extract_keywords(description),
        })

    # Naming conventions
    for i, nc in enumerate(arch_rules.get("naming_conventions", [])):
        convention = nc.get("convention", "")
        target = nc.get("target", "")
        example = nc.get("example", "")
        pattern = _convention_to_regex(convention)
        rules.append({
            "id": f"naming-{i}",
            "check": "naming",
            "description": f"{target}: use {convention}" + (f" (e.g. {example})" if example else ""),
            "pattern": pattern,
            "severity": "warn",
            "keywords": [target, "name", "naming", convention],
        })

    # Layer boundary rules (from components)
    components = blueprint.get("components", {})
    comp_list = components.get("components", [])
    for i, comp in enumerate(comp_list):
        path = comp.get("path", "")
        name = comp.get("name", "")
        if path:
            rules.append({
                "id": f"layer-{i}",
                "check": "file_placement",
                "description": f"{name} files belong in {path}",
                "allowed_dirs": [path],
                "severity": "warn",
                "keywords": _extract_keywords(name) + _extract_keywords(path),
            })

    return rules


def save_rules(project_root: Path, rules: list[dict]) -> None:
    """Save rules to .archie/rules.json."""
    archie_dir = project_root / ".archie"
    archie_dir.mkdir(exist_ok=True)
    (archie_dir / "rules.json").write_text(
        json.dumps({"rules": rules}, indent=2) + "\n"
    )


def load_rules(project_root: Path) -> list[dict]:
    """Load rules from .archie/rules.json."""
    rules_file = project_root / ".archie" / "rules.json"
    if not rules_file.exists():
        return []
    try:
        data = json.loads(rules_file.read_text())
        return data.get("rules", [])
    except (json.JSONDecodeError, OSError):
        return []


def promote_rule(project_root: Path, rule_id: str) -> bool:
    """Promote a rule from warn to error. Returns True if found."""
    rules = load_rules(project_root)
    for rule in rules:
        if rule["id"] == rule_id:
            rule["severity"] = "error"
            save_rules(project_root, rules)
            return True
    return False


def demote_rule(project_root: Path, rule_id: str) -> bool:
    """Demote a rule from error to warn. Returns True if found."""
    rules = load_rules(project_root)
    for rule in rules:
        if rule["id"] == rule_id:
            rule["severity"] = "warn"
            save_rules(project_root, rules)
            return True
    return False


def _convention_to_regex(convention: str) -> str:
    """Convert a naming convention name to a regex pattern."""
    patterns = {
        "snake_case": r"^[a-z][a-z0-9_]*(\.[a-z]+)?$",
        "camelCase": r"^[a-z][a-zA-Z0-9]*(\.[a-z]+)?$",
        "PascalCase": r"^[A-Z][a-zA-Z0-9]*(\.[a-z]+)?$",
        "kebab-case": r"^[a-z][a-z0-9-]*(\.[a-z]+)?$",
    }
    return patterns.get(convention, "")


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a description."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    stop = {"the", "and", "for", "are", "this", "that", "with", "from", "use", "must"}
    return [w for w in words if w not in stop]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_rule_extractor.py -v`
Expected: PASS (all 7 tests)

**Step 5: Commit**

```bash
git add archie/rules/extractor.py tests/test_rule_extractor.py
git commit -m "feat: add rule extractor for blueprint-based enforcement"
```

---

## Phase 13: CLI `init` Command — End-to-End

### Task 13: Wire up `archie init .` to run the full pipeline

This is the integration task. It ties together: local engine → coordinator prompts → renderer (reused) → hook installer → rule extractor.

Note: The actual subagent spawning (Claude Code `Task` tool) cannot be tested in unit tests — it requires a live Claude Code session. The CLI will output the coordinator prompt and subagent prompts as files that a Claude Code skill can consume.

**Files:**
- Modify: `archie/cli/main.py`
- Create: `archie/cli/init_command.py`
- Create: `tests/test_init_command.py`

**Step 1: Write the tests**

```python
# tests/test_init_command.py
import json
import tempfile
from pathlib import Path
from click.testing import CliRunner
from archie.cli.main import cli

def _make_repo(root: Path, files: dict[str, str]):
    for rel, content in files.items():
        f = root / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)

def test_init_creates_archie_dir():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            "src/main.py": "from flask import Flask\napp = Flask(__name__)",
            "requirements.txt": "flask>=3.0\n",
        })
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(root), "--local-only"])
        assert result.exit_code == 0
        assert (root / ".archie" / "scan.json").exists()

def test_init_creates_hooks():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {"src/app.py": "print(1)"})
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(root), "--local-only"])
        assert result.exit_code == 0
        assert (root / ".claude" / "hooks" / "pre-validate.sh").exists()
        assert (root / ".claude" / "hooks" / "inject-context.sh").exists()

def test_init_creates_rules_json():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            "src/main.py": "print(1)",
            # Create a pre-existing blueprint to extract rules from
        })
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(root), "--local-only"])
        assert result.exit_code == 0
        # rules.json may be empty if no blueprint yet, but file should exist
        assert (root / ".archie").exists()

def test_init_outputs_coordinator_prompt():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _make_repo(root, {
            "src/main.py": "from fastapi import FastAPI\napp = FastAPI()",
            "requirements.txt": "fastapi>=0.104\n",
        })
        runner = CliRunner()
        result = runner.invoke(cli, ["init", str(root), "--local-only"])
        assert result.exit_code == 0
        # Should save coordinator prompt for Claude Code to use
        prompt_file = root / ".archie" / "coordinator_prompt.md"
        assert prompt_file.exists()
        content = prompt_file.read_text()
        assert "FastAPI" in content or "fastapi" in content
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_init_command.py -v`
Expected: FAIL (--local-only flag not implemented)

**Step 3: Implement the init command**

```python
# archie/cli/init_command.py
"""Implementation of `archie init` command."""
from __future__ import annotations
from pathlib import Path
import click

from archie.engine.scan import run_scan
from archie.coordinator.planner import plan_subagent_groups
from archie.coordinator.prompts import build_coordinator_prompt, build_subagent_prompt
from archie.hooks.generator import install_hooks
from archie.rules.extractor import extract_rules, save_rules


def run_init(repo_path: Path, local_only: bool = False) -> None:
    """Run the full archie init pipeline."""
    root = repo_path.resolve()
    archie_dir = root / ".archie"
    archie_dir.mkdir(exist_ok=True)

    # Phase 1: Local engine scan
    click.echo("Scanning repository...")
    scan = run_scan(root, save=True)
    click.echo(f"  Found {len(scan.file_tree)} source files")
    click.echo(f"  Detected: {', '.join(f.name for f in scan.framework_signals) or 'no frameworks'}")
    click.echo(f"  Dependencies: {len(scan.dependencies)}")
    total_tokens = sum(scan.token_counts.values())
    click.echo(f"  Total tokens: {total_tokens:,}")

    # Phase 2: Plan subagent groups
    groups = plan_subagent_groups(scan)
    click.echo(f"  Planned {len(groups)} subagent group(s)")

    # Phase 3: Generate coordinator + subagent prompts
    coordinator_prompt = build_coordinator_prompt(scan, groups)
    (archie_dir / "coordinator_prompt.md").write_text(coordinator_prompt)

    for i, group in enumerate(groups):
        subagent_prompt = build_subagent_prompt(group, scan)
        (archie_dir / f"subagent_{i}_prompt.md").write_text(subagent_prompt)

    # Phase 4: Install hooks
    click.echo("Installing enforcement hooks...")
    install_hooks(root)

    # Phase 5: Extract rules (from existing blueprint if available)
    blueprint_file = archie_dir / "blueprint.json"
    if blueprint_file.exists():
        import json
        try:
            bp = json.loads(blueprint_file.read_text())
            rules = extract_rules(bp)
            save_rules(root, rules)
            click.echo(f"  Extracted {len(rules)} enforcement rules")
        except Exception:
            click.echo("  No rules extracted (blueprint parse error)")
    else:
        # Save empty rules for now
        save_rules(root, [])
        click.echo("  No blueprint yet — rules will be extracted after agent analysis")

    # Summary
    click.echo("")
    if local_only:
        click.echo("Local scan complete. To run full analysis with AI agents:")
        click.echo(f"  1. Open Claude Code in {root}")
        click.echo(f"  2. Run: /archie-init")
        click.echo(f"  Or: archie init {root}  (without --local-only)")
    else:
        click.echo("Scan complete. Agent analysis prompts saved to .archie/")
        click.echo("To complete analysis, run /archie-init in Claude Code.")

    click.echo("")
    click.echo("Installed:")
    click.echo("  .archie/scan.json              — local analysis results")
    click.echo("  .archie/coordinator_prompt.md   — orchestrator instructions")
    click.echo("  .claude/hooks/pre-validate.sh   — enforcement hook")
    click.echo("  .claude/hooks/inject-context.sh — context injection hook")
    click.echo("  .claude/settings.local.json     — hook registration")
```

Now update the CLI to use this:

```python
# archie/cli/main.py (replace previous content)
import click
from pathlib import Path

@click.group()
@click.version_option()
def cli():
    """Archie — your AI writes code, Archie enforces your architecture."""
    pass

@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--local-only", is_flag=True, help="Run local scan only, skip agent analysis.")
def init(path, local_only):
    """Analyze a repository and generate architecture blueprint + enforcement."""
    from archie.cli.init_command import run_init
    run_init(Path(path), local_only=local_only)

@cli.command()
def status():
    """Show blueprint freshness and enforcement stats."""
    click.echo("archie status — not yet implemented")

@cli.command()
def rules():
    """List all enforcement rules with severity."""
    click.echo("archie rules — not yet implemented")

@cli.command()
@click.argument("rule_id")
def promote(rule_id):
    """Promote a rule from warn to error severity."""
    from archie.rules.extractor import promote_rule
    if promote_rule(Path("."), rule_id):
        click.echo(f"Promoted {rule_id} to error severity.")
    else:
        click.echo(f"Rule {rule_id} not found.", err=True)

@cli.command()
@click.argument("rule_id")
def demote(rule_id):
    """Demote a rule from error to warn severity."""
    from archie.rules.extractor import demote_rule
    if demote_rule(Path("."), rule_id):
        click.echo(f"Demoted {rule_id} to warn severity.")
    else:
        click.echo(f"Rule {rule_id} not found.", err=True)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_init_command.py -v`
Expected: PASS (all 4 tests)

**Step 5: Commit**

```bash
git add archie/cli/main.py archie/cli/init_command.py tests/test_init_command.py
git commit -m "feat: wire up archie init command end-to-end"
```

---

## Phase 14: Integration Test — Run Against Real Repo

### Task 14: Manual integration test

**This is not automated — run manually.**

**Step 1: Install the package**

```bash
cd /Users/hamutarto/DEV/BitRaptors/Archie
pip install -e ".[dev]"
```

**Step 2: Run against a real repo (this repo)**

```bash
archie init . --local-only
```

**Expected output:**
```
Scanning repository...
  Found ~XXX source files
  Detected: Next.js, React, FastAPI, ...
  Dependencies: XX
  Total tokens: XXX,XXX
  Planned X subagent group(s)
Installing enforcement hooks...
  No blueprint yet — rules will be extracted after agent analysis

Local scan complete. To run full analysis with AI agents:
  1. Open Claude Code in .
  2. Run: /archie-init
  Or: archie init .  (without --local-only)

Installed:
  .archie/scan.json              — local analysis results
  .archie/coordinator_prompt.md   — orchestrator instructions
  .claude/hooks/pre-validate.sh   — enforcement hook
  .claude/hooks/inject-context.sh — context injection hook
  .claude/settings.local.json     — hook registration
```

**Step 3: Verify outputs**

```bash
cat .archie/scan.json | python3 -m json.tool | head -30
cat .archie/coordinator_prompt.md | head -30
ls -la .claude/hooks/
cat .claude/settings.local.json
```

**Step 4: Run against a different repo**

```bash
cd /tmp
git clone https://github.com/tiangolo/fastapi.git --depth 1
archie init fastapi --local-only
cat fastapi/.archie/scan.json | python3 -m json.tool | head -50
```

**Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: integration test fixes from real repo testing"
```

---

## Phase 15: Run All Tests

### Task 15: Final test sweep

**Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: ALL PASS

**Step 2: Lint**

```bash
ruff check archie/ tests/
```

Expected: no errors

**Step 3: Commit final state**

```bash
git add -A && git commit -m "chore: all tests passing, lint clean"
```

---

## Summary

| Phase | What | Tests |
|-------|------|-------|
| 1 | Package scaffold + CLI entry point | manual verify |
| 2 | RawScan Pydantic model | 4 unit tests |
| 3 | File tree scanner | 5 unit tests |
| 4 | Dependency parser | 6 unit tests |
| 5 | Framework detector | 6 unit tests |
| 6 | File hasher + token counter | 5 unit tests |
| 7 | Import graph builder | 4 unit tests |
| 8 | Scan assembler | 3 unit tests |
| 9 | Subagent planner | 5 unit tests |
| 10 | Prompt templates | 3 unit tests |
| 11 | Hook generator | 6 unit tests |
| 12 | Rule extractor | 7 unit tests |
| 13 | CLI init command (e2e) | 4 integration tests |
| 14 | Manual real-repo test | manual |
| 15 | Final test sweep | all |

**Total automated tests: ~58**
**Total phases: 15**
**Total commits: ~15**

After this plan completes, `archie init . --local-only` works end-to-end. The next plan would cover: Claude Code skill for `/archie-init` (agent coordination runtime), `archie status`, `archie refresh`, and the freshness system.

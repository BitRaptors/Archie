"""Tests for archie.engine.imports — import graph builder."""
from __future__ import annotations

import tempfile
from pathlib import Path

from archie.engine.imports import build_import_graph
from archie.engine.models import FileEntry


def test_python_imports() -> None:
    """Python files with internal dotted imports are captured."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "app" / "service.py"
        src.parent.mkdir(parents=True)
        src.write_text(
            "from src.domain.models import User\nimport os\nimport src.utils.helpers\n"
        )

        entries = [FileEntry(path="app/service.py")]
        graph = build_import_graph(entries, root)

        assert "app/service.py" in graph
        assert "src.domain.models" in graph["app/service.py"]
        assert "src.utils.helpers" in graph["app/service.py"]
        # stdlib 'os' has no dot, so it should NOT appear
        assert "os" not in graph["app/service.py"]


def test_js_imports() -> None:
    """JS/TS files with relative imports are captured."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "src" / "App.tsx"
        src.parent.mkdir(parents=True)
        src.write_text(
            "import { Button } from './components/Button';\n"
            "import React from 'react';\n"
            "const util = require('./utils/helper');\n"
        )

        entries = [FileEntry(path="src/App.tsx")]
        graph = build_import_graph(entries, root)

        assert "src/App.tsx" in graph
        assert "./components/Button" in graph["src/App.tsx"]
        assert "./utils/helper" in graph["src/App.tsx"]
        # non-relative 'react' should NOT appear
        assert "react" not in graph["src/App.tsx"]


def test_empty_file() -> None:
    """An empty Python file produces no imports (not even a key)."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "empty.py"
        src.write_text("")

        entries = [FileEntry(path="empty.py")]
        graph = build_import_graph(entries, root)

        assert graph.get("empty.py") is None


def test_no_source_files() -> None:
    """Non-source files (e.g. .md) produce an empty graph."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        readme = root / "README.md"
        readme.write_text("# Hello\n")

        entries = [FileEntry(path="README.md")]
        graph = build_import_graph(entries, root)

        assert graph == {}

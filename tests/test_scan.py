"""Tests for archie.engine.scan — the scan assembler."""
from __future__ import annotations

import json
from pathlib import Path

from archie.engine.models import RawScan
from archie.engine.scan import run_scan


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scan_produces_raw_scan(tmp_path: Path) -> None:
    """A repo with src/main.py, src/utils.py, requirements.txt, package.json
    yields populated file_tree, dependencies, frameworks, hashes, token_counts."""
    _write(tmp_path / "src" / "main.py", "print('hello')\n")
    _write(tmp_path / "src" / "utils.py", "x = 1\n")
    _write(
        tmp_path / "requirements.txt",
        "fastapi>=0.100\nuvicorn\n",
    )
    _write(
        tmp_path / "package.json",
        json.dumps({"dependencies": {"react": "^18.0.0"}}),
    )

    result = run_scan(tmp_path)

    assert isinstance(result, RawScan)

    # file_tree should contain all four files
    paths = {e.path for e in result.file_tree}
    assert "src/main.py" in paths
    assert "src/utils.py" in paths
    assert "requirements.txt" in paths
    assert "package.json" in paths

    # dependencies from both manifests
    dep_names = {d.name for d in result.dependencies}
    assert "fastapi" in dep_names
    assert "react" in dep_names

    # framework signals should pick up FastAPI and React
    fw_names = {f.name for f in result.framework_signals}
    assert "FastAPI" in fw_names
    assert "React" in fw_names

    # hashes and token_counts should have entries for scanned files
    assert len(result.file_hashes) > 0
    assert len(result.token_counts) > 0

    # entry points should detect src/main.py
    assert "src/main.py" in result.entry_points


def test_scan_empty_repo(tmp_path: Path) -> None:
    """An empty directory produces a valid but empty RawScan."""
    result = run_scan(tmp_path)

    assert isinstance(result, RawScan)
    assert result.file_tree == []
    assert result.dependencies == []
    assert result.framework_signals == []
    assert result.file_hashes == {}
    assert result.token_counts == {}
    assert result.import_graph == {}
    assert result.entry_points == []
    assert result.config_patterns == {}
    assert result.directory_structure == {}


def test_scan_writes_to_archie_dir(tmp_path: Path) -> None:
    """save=True writes .archie/scan.json that round-trips back to RawScan."""
    _write(tmp_path / "main.py", "print('hi')\n")

    original = run_scan(tmp_path, save=True)

    scan_file = tmp_path / ".archie" / "scan.json"
    assert scan_file.exists()

    loaded = RawScan.model_validate(json.loads(scan_file.read_text(encoding="utf-8")))
    assert loaded.file_tree == original.file_tree
    assert loaded.entry_points == original.entry_points
    assert loaded.file_hashes == original.file_hashes

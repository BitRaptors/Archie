"""Tests for the Archie Studio server (studio/server.py)."""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "studio"))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Project with .archie blueprint and a docs/prd folder."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "blueprint.json").write_text(json.dumps({
        "meta": {"scan_count": 1},
        "components": {"components": [{"name": "x", "location": "src/x"}]},
    }))
    prd = tmp_path / "docs" / "prd"
    prd.mkdir(parents=True)
    (prd / "overview.md").write_text("---\nstatus: draft\n---\n# Overview\nSee [[Login Flow]].")
    sub = prd / "features"
    sub.mkdir()
    (sub / "login-flow.md").write_text("# Login Flow")
    (sub / "notes.txt").write_text("not markdown")
    hidden = prd / ".obsidian"
    hidden.mkdir()
    (hidden / "workspace.md").write_text("obsidian internals")
    return tmp_path


# --- helpers ---------------------------------------------------------------

def test_resolve_prd_root_prefers_explicit_flag(project: Path):
    from server import resolve_prd_root
    explicit = project / "docs" / "prd" / "features"
    assert resolve_prd_root(project, "docs/prd/features") == explicit.resolve()


def test_resolve_prd_root_falls_back_to_docs_prd(project: Path):
    from server import resolve_prd_root
    assert resolve_prd_root(project, None) == (project / "docs" / "prd").resolve()


def test_resolve_prd_root_none_when_missing(tmp_path: Path):
    from server import resolve_prd_root
    assert resolve_prd_root(tmp_path, None) is None
    assert resolve_prd_root(tmp_path, "nope") is None


def test_build_prd_tree_lists_md_only_skips_hidden(project: Path):
    from server import build_prd_tree
    tree = build_prd_tree((project / "docs" / "prd").resolve())
    names = [n["name"] for n in tree]
    assert names == ["features", "overview.md"]  # dirs first, then files
    feature_files = [n["name"] for n in tree[0]["children"]]
    assert feature_files == ["login-flow.md"]  # .txt excluded
    assert tree[0]["children"][0]["path"] == "features/login-flow.md"


def test_read_prd_file_returns_content(project: Path):
    from server import read_prd_file
    content = read_prd_file((project / "docs" / "prd").resolve(), "overview.md")
    assert content is not None and "# Overview" in content


def test_read_prd_file_blocks_traversal(project: Path):
    from server import read_prd_file
    (project / "secret.md").write_text("secret")
    prd_root = (project / "docs" / "prd").resolve()
    assert read_prd_file(prd_root, "../../secret.md") is None
    assert read_prd_file(prd_root, "/etc/hosts") is None


def test_read_prd_file_rejects_non_markdown(project: Path):
    from server import read_prd_file
    prd_root = (project / "docs" / "prd").resolve()
    assert read_prd_file(prd_root, "features/notes.txt") is None

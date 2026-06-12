"""Tests for the Archie Studio server (studio/server.py)."""
from __future__ import annotations

import json
import os
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


def test_read_prd_file_handles_null_byte(project: Path):
    """Embedded null bytes make Path.resolve() raise ValueError; must 404, not crash."""
    from server import read_prd_file
    prd_root = (project / "docs" / "prd").resolve()
    assert read_prd_file(prd_root, "a\x00.md") is None


def _symlinks_supported(base: Path) -> bool:
    probe = base / "_symlink_probe"
    try:
        probe.symlink_to(base)
    except (OSError, NotImplementedError):
        return False
    probe.unlink()
    return True


def test_build_prd_tree_skips_symlinks(project: Path):
    from server import build_prd_tree
    if not _symlinks_supported(project):
        pytest.skip("symlinks not supported on this platform")
    prd_root = (project / "docs" / "prd").resolve()
    # Symlink cycle: dir symlink pointing back at the PRD root (would ELOOP).
    (prd_root / "loop").symlink_to(prd_root)
    # Symlinked .md: would list in the tree but 404 on fetch (resolves outside).
    outside = project / "outside.md"
    outside.write_text("# Outside")
    (prd_root / "linked.md").symlink_to(outside)
    tree = build_prd_tree(prd_root)
    assert [n["name"] for n in tree] == ["features", "overview.md"]


def test_read_prd_file_accepts_unresolved_prd_root(project: Path):
    """The containment guard must not fail when callers pass an unresolved
    path (e.g. through a symlink like /tmp on macOS)."""
    from server import read_prd_file
    if not _symlinks_supported(project):
        pytest.skip("symlinks not supported on this platform")
    link = project / "prdlink"
    link.symlink_to(project / "docs" / "prd")
    content = read_prd_file(link, "overview.md")
    assert content is not None and "# Overview" in content


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="permission checks unavailable or bypassed as root",
)
def test_read_prd_file_returns_none_on_unreadable(project: Path):
    from server import read_prd_file
    prd_root = (project / "docs" / "prd").resolve()
    locked = prd_root / "locked.md"
    locked.write_text("# Locked")
    os.chmod(locked, 0)
    try:
        assert read_prd_file(prd_root, "locked.md") is None
    finally:
        os.chmod(locked, 0o644)


# --- HTTP app ---------------------------------------------------------------

def _start(project: Path, prd_root, dist_dir=None):
    from server import build_studio_app
    port = _free_port()
    app = build_studio_app(project, prd_root, port=port, dist_dir=dist_dir)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    time.sleep(0.05)
    return app, port


def _get_json(port: int, path: str):
    resp = urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=2)
    return json.loads(resp.read())


def test_prd_tree_endpoint(project: Path):
    prd_root = (project / "docs" / "prd").resolve()
    app, port = _start(project, prd_root)
    try:
        body = _get_json(port, "/api/prd/tree")
        assert body["prd_root"] == str(prd_root)
        assert [n["name"] for n in body["tree"]] == ["features", "overview.md"]
    finally:
        app.shutdown()


def test_prd_tree_endpoint_no_prd_folder(project: Path):
    app, port = _start(project, None)
    try:
        body = _get_json(port, "/api/prd/tree")
        assert body == {"prd_root": None, "tree": []}
    finally:
        app.shutdown()


def test_prd_file_endpoint(project: Path):
    prd_root = (project / "docs" / "prd").resolve()
    app, port = _start(project, prd_root)
    try:
        body = _get_json(port, "/api/prd/file?path=features%2Flogin-flow.md")
        assert body["content"] == "# Login Flow"
    finally:
        app.shutdown()


def test_prd_file_endpoint_404s(project: Path):
    prd_root = (project / "docs" / "prd").resolve()
    (project / "secret.md").write_text("secret")
    app, port = _start(project, prd_root)
    try:
        for bad in ("/api/prd/file?path=missing.md",
                    "/api/prd/file?path=..%2F..%2Fsecret.md"):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(f"http://127.0.0.1:{port}{bad}", timeout=2)
            assert exc.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/prd/file", timeout=2)
        assert exc.value.code == 400
    finally:
        app.shutdown()


def test_inherited_viewer_endpoints_still_work(project: Path):
    """The studio handler must keep every viewer endpoint intact."""
    prd_root = (project / "docs" / "prd").resolve()
    app, port = _start(project, prd_root)
    try:
        bundle = _get_json(port, "/api/bundle")
        assert bundle["bundle"]["blueprint"]["components"]["components"][0]["name"] == "x"
        gen = _get_json(port, "/api/generated-files")
        assert isinstance(gen, dict)
    finally:
        app.shutdown()


def test_studio_serves_own_dist_with_spa_fallback(project: Path, tmp_path: Path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>studio</html>")
    app, port = _start(project, None, dist_dir=dist)
    try:
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/product", timeout=2)
        assert b"<html>studio</html>" in resp.read()
    finally:
        app.shutdown()

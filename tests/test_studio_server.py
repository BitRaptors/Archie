"""Tests for the Archie Studio server (studio/server.py)."""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
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


# --- PRD source detection ----------------------------------------------------

@pytest.fixture(autouse=True)
def _studio_config(tmp_path: Path, monkeypatch):
    """Isolate the central studio config (~/.archie/studio.json) per test."""
    monkeypatch.setenv("ARCHIE_STUDIO_CONFIG", str(tmp_path / "studio-config.json"))


@pytest.fixture
def kavosz_like(tmp_path: Path) -> Path:
    """Project whose PRDs live in @docs/*.prd.md instead of docs/prd/."""
    root = tmp_path / "kavosz"
    docs = root / "@docs"
    docs.mkdir(parents=True)
    (docs / "prd.md").write_text("# Main PRD")
    (docs / "plan-audit.prd.md").write_text("# Audit PRD")
    (docs / "architecture.md").write_text("# Not a PRD")
    (docs / "notes.txt").write_text("not markdown")
    nm = root / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "fake.prd.md").write_text("must be skipped")
    (root / ".archie").mkdir()
    (root / ".archie" / "blueprint.json").write_text("{}")
    return root


def test_is_prd_filename():
    from server import _is_prd_filename
    assert _is_prd_filename("prd.md")
    assert _is_prd_filename("PRD-login.md")
    assert _is_prd_filename("plan-audit.prd.md")
    assert not _is_prd_filename("comprd.md")  # 'prd' must be a token, not a substring
    assert not _is_prd_filename("prd.txt")
    assert not _is_prd_filename("architecture.md")


def test_detect_prd_dirs_finds_unconventional_folders(kavosz_like: Path):
    from server import detect_prd_dirs
    assert detect_prd_dirs(kavosz_like.resolve()) == [(kavosz_like / "@docs").resolve()]


def test_initial_prd_state_never_promotes_detected_sources(kavosz_like: Path):
    """Regression: main() once fed the first computed (detected) source back in
    as the explicit seed, promoting it to all-markdown mode."""
    from server import initial_prd_state
    prd_root, labels = initial_prd_state(kavosz_like.resolve(), None)
    assert prd_root is None  # detected @docs must NOT become the explicit seed
    assert labels == ["@docs"]
    prd_root, labels = initial_prd_state(kavosz_like.resolve(), "@docs")
    assert prd_root == (kavosz_like / "@docs").resolve()  # real flag: explicit


def test_compute_prd_sources_orders_and_dedupes(project: Path):
    from server import compute_prd_sources
    root = project.resolve()
    # docs/prd is both the explicit pick and the convention folder: one source
    sources = compute_prd_sources(root, [root / "docs" / "prd"])
    assert [s["kind"] for s in sources] == ["explicit"]
    assert sources[0]["label"] == "docs/prd"


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
        assert len(body["sources"]) == 1
        src = body["sources"][0]
        assert src["root"] == str(prd_root)
        assert src["label"] == "docs/prd"
        assert [n["name"] for n in src["tree"]] == ["features", "overview.md"]
    finally:
        app.shutdown()


def test_prd_tree_endpoint_no_prd_anywhere(tmp_path: Path):
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "README.md").write_text("# Readme")  # md, but not PRD-named
    app, port = _start(bare, None)
    try:
        body = _get_json(port, "/api/prd/tree")
        assert body == {"sources": []}
    finally:
        app.shutdown()


def test_prd_tree_detects_prd_named_files(kavosz_like: Path):
    app, port = _start(kavosz_like, None)
    try:
        body = _get_json(port, "/api/prd/tree")
        assert len(body["sources"]) == 2
        prd_src, docs_src = body["sources"]
        assert prd_src["kind"] == "detected"
        assert prd_src["label"] == "@docs"
        assert [n["name"] for n in prd_src["tree"]] == ["plan-audit.prd.md", "prd.md"]
        # companion section: the same folder's OTHER markdown, separated
        assert docs_src["kind"] == "docs"
        assert docs_src["label"] == "@docs"
        assert [n["name"] for n in docs_src["tree"]] == ["architecture.md"]
        # files from the companion section are fetchable too
        content = _get_json(
            port,
            "/api/prd/file?root=" + urllib.parse.quote(docs_src["root"])
            + "&path=architecture.md",
        )
        assert content["content"] == "# Not a PRD"
    finally:
        app.shutdown()


def test_prd_tree_combines_convention_and_detected(project: Path):
    extra = project / "@docs"
    extra.mkdir()
    (extra / "billing.prd.md").write_text("# Billing PRD")
    app, port = _start(project, None)
    try:
        body = _get_json(port, "/api/prd/tree")
        assert [(s["kind"], s["label"]) for s in body["sources"]] == [
            ("convention", "docs/prd"), ("detected", "@docs"), ("docs", "@docs"),
        ]
        assert body["sources"][2]["tree"] == []  # no other markdown in @docs here
    finally:
        app.shutdown()


def test_prd_file_endpoint(project: Path):
    prd_root = (project / "docs" / "prd").resolve()
    app, port = _start(project, prd_root)
    try:
        body = _get_json(
            port,
            "/api/prd/file?root=" + urllib.parse.quote(str(prd_root))
            + "&path=features%2Flogin-flow.md",
        )
        assert body["content"] == "# Login Flow"
    finally:
        app.shutdown()


def test_prd_file_endpoint_404s(project: Path):
    prd_root = (project / "docs" / "prd").resolve()
    (project / "secret.md").write_text("secret")
    app, port = _start(project, prd_root)
    root_q = urllib.parse.quote(str(prd_root))
    try:
        for bad, code in (
            (f"/api/prd/file?root={root_q}&path=missing.md", 404),
            (f"/api/prd/file?root={root_q}&path=..%2F..%2Fsecret.md", 404),
            # root must be one of the registered sources, not an arbitrary dir
            (f"/api/prd/file?root={urllib.parse.quote(str(project))}&path=secret.md", 404),
            (f"/api/prd/file?root={root_q}", 400),
            ("/api/prd/file?path=missing.md", 400),
        ):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(f"http://127.0.0.1:{port}{bad}", timeout=2)
            assert exc.value.code == code
    finally:
        app.shutdown()


def test_add_prd_source_and_persistence(project: Path, tmp_path: Path):
    # sibling of the project root, so it exercises the outside-root abs label
    vault = tmp_path.parent / f"{tmp_path.name}-vault"
    vault.mkdir()
    (vault / "roadmap.md").write_text("# Roadmap")  # explicit sources show ALL .md
    app, port = _start(project, None)
    try:
        body = _post_json(port, "/api/prd/source", {"path": str(vault)})
        kinds = [(s["kind"], s["label"]) for s in body["sources"]]
        assert kinds[0] == ("explicit", str(vault.resolve()))  # outside root: abs label
        assert ("convention", "docs/prd") in kinds
        assert [n["name"] for n in body["sources"][0]["tree"]] == ["roadmap.md"]
        # persisted centrally and reloaded by a fresh server
        config = json.loads(Path(os.environ["ARCHIE_STUDIO_CONFIG"]).read_text())
        assert str(vault.resolve()) in config["projects"][str(project.resolve())]["prd_sources"]
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post_json(port, "/api/prd/source", {"path": str(vault / "nope")})
        assert exc.value.code == 404
    finally:
        app.shutdown()
    app2, port2 = _start(project, None)
    try:
        body = _get_json(port2, "/api/prd/tree")
        assert [s["kind"] for s in body["sources"]][0] == "explicit"
    finally:
        app2.shutdown()


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


def _post_json(port: int, path: str, payload: dict):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=2)
    return json.loads(resp.read())


def test_picker_mode_reports_no_project(project: Path):
    app, port = _start(None, None)
    try:
        body = _get_json(port, "/api/project")
        assert body == {"root": None, "prd_root": None, "name": None}
        for blocked in ("/api/bundle", "/api/prd/tree"):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(f"http://127.0.0.1:{port}{blocked}", timeout=2)
            assert exc.value.code == 404
    finally:
        app.shutdown()


def test_select_project_at_runtime(project: Path):
    """POST /api/project switches the live handler to the chosen project."""
    app, port = _start(None, None)
    try:
        body = _post_json(port, "/api/project", {"path": str(project)})
        assert body["root"] == str(project.resolve())
        assert body["name"] == project.name
        assert body["prd_root"] == str((project / "docs" / "prd").resolve())
        tree = _get_json(port, "/api/prd/tree")
        assert [n["name"] for n in tree["sources"][0]["tree"]] == ["features", "overview.md"]
        bundle = _get_json(port, "/api/bundle")
        assert bundle["bundle"]["blueprint"]["meta"]["scan_count"] == 1
    finally:
        app.shutdown()


def test_select_project_rejects_bad_paths(project: Path):
    app, port = _start(None, None)
    try:
        for payload, code in (({}, 400), ({"path": ""}, 400),
                              ({"path": str(project / "nope")}, 404),
                              ({"path": str(project / "docs" / "prd" / "overview.md")}, 404)):
            with pytest.raises(urllib.error.HTTPError) as exc:
                _post_json(port, "/api/project", payload)
            assert exc.value.code == code
        # picker mode never delegates unknown POSTs to the rules endpoint
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post_json(port, "/api/rules", {"action": "adopt", "rule_id": "x"})
        assert exc.value.code == 404
    finally:
        app.shutdown()


def test_select_project_honors_cli_prd_flag(project: Path):
    from server import build_studio_app
    port = _free_port()
    app = build_studio_app(None, None, port=port, prd_arg="docs/prd/features")
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        body = _post_json(port, "/api/project", {"path": str(project)})
        assert body["prd_root"] == str((project / "docs" / "prd" / "features").resolve())
    finally:
        app.shutdown()


def test_fs_list_endpoint(project: Path):
    app, port = _start(None, None)
    try:
        body = _get_json(port, f"/api/fs/list?path={project}")
        assert body["path"] == str(project.resolve())
        assert body["parent"] == str(project.resolve().parent)
        names = {d["name"] for d in body["dirs"]}
        assert "docs" in names and ".archie" not in names  # hidden skipped
        listing = _get_json(port, f"/api/fs/list?path={project.parent}")
        me = next(d for d in listing["dirs"] if d["path"] == str(project.resolve()))
        assert me["has_archie"] is True and me["has_prd"] is True
    finally:
        app.shutdown()


def test_fs_list_rejects_bad_paths(project: Path):
    app, port = _start(None, None)
    try:
        for q, code in ((f"path={project}/nope", 404),
                        (f"path={project}/docs/prd/overview.md", 404),
                        ("path=a%00b", 400)):
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/fs/list?{q}", timeout=2)
            assert exc.value.code == code
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

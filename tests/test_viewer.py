"""Tests for the Archie local viewer sidecar."""
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture
def project_with_blueprint(tmp_path: Path) -> Path:
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "blueprint.json").write_text(json.dumps({
        "meta": {"scan_count": 1},
        "components": {"components": [{"name": "x", "location": "src/x"}]},
    }))
    return tmp_path


def test_bundle_endpoint_returns_blueprint(project_with_blueprint: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    server_thread = threading.Thread(target=app.serve_forever, daemon=True)
    server_thread.start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/bundle", timeout=2)
        body = json.loads(resp.read())
        assert "bundle" in body
        assert body["bundle"]["blueprint"]["components"]["components"][0]["name"] == "x"
    finally:
        app.shutdown()


def test_404_for_unknown_api_path(project_with_blueprint: Path, tmp_path: Path):
    # Create a fake dist/ so build_app accepts the project
    dist = project_with_blueprint / ".archie" / "viewer" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>local</html>")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/nonexistent", timeout=2)
        assert exc.value.code == 404
    finally:
        app.shutdown()


def test_spa_fallback_serves_index_html(project_with_blueprint: Path):
    dist = project_with_blueprint / ".archie" / "viewer" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>local</html>")
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/local", timeout=2)
        assert b"<html>local</html>" in resp.read()
    finally:
        app.shutdown()


def test_api_only_skips_static(project_with_blueprint: Path):
    from viewer import build_app
    port = _free_port()
    app = build_app(project_with_blueprint, port=port, api_only=True)
    threading.Thread(target=app.serve_forever, daemon=True).start()
    try:
        time.sleep(0.05)
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        assert exc.value.code == 404
        # Bundle endpoint still works
        resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/bundle", timeout=2)
        assert resp.status == 200
    finally:
        app.shutdown()

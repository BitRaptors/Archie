"""Tests for the Archie local viewer sidecar."""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
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

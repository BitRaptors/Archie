"""Tests for the lightweight viewer server endpoints."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from starlette.testclient import TestClient

# Minimal blueprint used by the server
_MINIMAL_BLUEPRINT: dict = {
    "meta": {
        "schema_version": "2.0.0",
        "repository": "test-repo",
        "repository_id": "test-repo-id",
        "analyzed_at": "2025-01-01T00:00:00Z",
    },
    "architecture_rules": {
        "file_placement_rules": [],
        "naming_conventions": [],
    },
    "decisions": {
        "architectural_style": {
            "title": "Architecture",
            "chosen": "monolith",
            "rationale": "Simple",
            "alternatives_rejected": [],
        },
        "key_decisions": [],
        "trade_offs": [],
        "out_of_scope": [],
    },
    "components": {"components": [], "contracts": []},
    "communication": {"patterns": [], "external_apis": []},
    "quick_reference": {"critical_paths": [], "gotchas": []},
    "technology": {"languages": ["python"], "frameworks": [], "infrastructure": []},
}


def _make_project(tmp: Path) -> None:
    """Create a minimal project with a blueprint."""
    archie_dir = tmp / ".archie"
    archie_dir.mkdir()
    (archie_dir / "blueprint.json").write_text(
        json.dumps(_MINIMAL_BLUEPRINT), encoding="utf-8"
    )


def _build_client(project_root: Path) -> TestClient:
    """Build a TestClient for the viewer app."""
    import sys

    backend_src = Path(__file__).resolve().parent.parent / "backend" / "src"
    if backend_src.exists() and str(backend_src) not in sys.path:
        sys.path.insert(0, str(backend_src))

    from archie.cli.serve_command import _build_app

    app = _build_app(project_root)
    return TestClient(app)


# ── Validate local ────────────────────────────────────────────────────────────


def test_validate_local_valid_path() -> None:
    """A real directory should be reported as valid."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_project(tmp_path)
        client = _build_client(tmp_path)

        resp = client.post(
            "/api/v1/repositories/local/validate",
            json={"path": str(tmp_path)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["name"] == tmp_path.name
        assert data["error"] is None


def test_validate_local_invalid_path() -> None:
    """A nonexistent directory should be reported as invalid."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_project(tmp_path)
        client = _build_client(tmp_path)

        resp = client.post(
            "/api/v1/repositories/local/validate",
            json={"path": "/nonexistent/path/does/not/exist"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert data["name"] is None
        assert data["error"] == "Directory not found"


def test_validate_local_git_repo() -> None:
    """A directory with .git should report is_git_repo=True."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_project(tmp_path)
        (tmp_path / ".git").mkdir()
        client = _build_client(tmp_path)

        resp = client.post(
            "/api/v1/repositories/local/validate",
            json={"path": str(tmp_path)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["is_git_repo"] is True


# ── Delivery apply ────────────────────────────────────────────────────────────


def test_delivery_apply() -> None:
    """Delivery should render outputs into the target directory."""
    with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as tgt_tmp:
        src_path = Path(src_tmp)
        tgt_path = Path(tgt_tmp) / "output"
        _make_project(src_path)
        client = _build_client(src_path)

        resp = client.post(
            "/api/v1/delivery/apply",
            json={"target_local_path": str(tgt_path)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "delivered"
        assert data["strategy"] == "local"
        assert isinstance(data["files_delivered"], list)
        assert len(data["files_delivered"]) > 0
        # At minimum CLAUDE.md should be generated
        assert any("CLAUDE.md" in f for f in data["files_delivered"])
        # Verify files exist on disk
        for rel_path in data["files_delivered"]:
            assert (tgt_path / rel_path).exists(), f"Expected {rel_path} on disk"


# ── Analysis stream ───────────────────────────────────────────────────────────


def test_analysis_stream() -> None:
    """SSE stream should return phase_complete and analysis_complete events."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_project(tmp_path)
        client = _build_client(tmp_path)

        resp = client.get("/api/v1/analyses/local-analysis/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "phase_complete" in body
        assert "analysis_complete" in body


# ── Settings stubs ────────────────────────────────────────────────────────────


def test_ignored_dirs_stub() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_project(tmp_path)
        client = _build_client(tmp_path)

        resp = client.get("/api/v1/settings/ignored-dirs")
        assert resp.status_code == 200
        assert resp.json() == []


def test_list_prompts_stub() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_project(tmp_path)
        client = _build_client(tmp_path)

        resp = client.get("/api/v1/prompts/")
        assert resp.status_code == 200
        assert resp.json() == []


def test_delete_repo_stub() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_project(tmp_path)
        client = _build_client(tmp_path)

        resp = client.delete("/api/v1/workspace/repositories/test-repo-id")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": True}

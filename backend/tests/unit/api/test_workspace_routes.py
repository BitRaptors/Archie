"""Tests for workspace API routes.

These use the FastAPI TestClient + dependency mocking
so we can test routes without a real DB or storage.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.workspace import router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_path):
    """Create a FastAPI app with the workspace router and mock container."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # Mock container
    mock_container = MagicMock()

    # Mock DB client (backend-agnostic)
    mock_db = MagicMock()
    mock_container.db = AsyncMock(return_value=mock_db)

    # Mock storage
    mock_storage = MagicMock()
    mock_storage._base_path = str(tmp_path)
    mock_container.storage.return_value = mock_storage

    app.container = mock_container

    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_profile_repo():
    repo = AsyncMock()
    repo.get_default = AsyncMock(return_value=None)
    repo.set_active_repo = AsyncMock()
    return repo


@pytest.fixture
def mock_repo_repo():
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_analysis_repo():
    repo = AsyncMock()
    repo.get_all = AsyncMock(return_value=[])
    return repo


# ---------------------------------------------------------------------------
# Repository listing
# ---------------------------------------------------------------------------


class TestListRepositories:

    def test_returns_empty_when_no_blueprints_dir(self, client, tmp_path):
        resp = client.get("/api/v1/workspace/repositories")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_repos_with_blueprint_json(self, client, tmp_path):
        bp_dir = tmp_path / "blueprints" / "repo-uuid-1"
        bp_dir.mkdir(parents=True)
        (bp_dir / "blueprint.json").write_text(json.dumps({
            "meta": {"repository": "acme/api"}
        }))

        with patch("api.routes.workspace._get_repos") as mock_repos, \
             patch("api.routes.workspace._get_analysis_repo") as mock_analysis:
            mock_repos.return_value = AsyncMock(get_by_id=AsyncMock(return_value=None))
            mock_analysis.return_value = AsyncMock(get_all=AsyncMock(return_value=[]))

            resp = client.get("/api/v1/workspace/repositories")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["repo_id"] == "repo-uuid-1"
            assert data[0]["has_structured"] is True
            assert data[0]["name"] == "acme/api"  # enriched from blueprint.json

    def test_ignores_dirs_without_blueprint_json(self, client, tmp_path):
        """Directories without blueprint.json should not appear."""
        bp_dir = tmp_path / "blueprints" / "repo-old"
        bp_dir.mkdir(parents=True)
        (bp_dir / "backend_blueprint.md").write_text("# Old format")

        with patch("api.routes.workspace._get_repos") as mock_repos, \
             patch("api.routes.workspace._get_analysis_repo") as mock_analysis:
            mock_repos.return_value = AsyncMock(get_by_id=AsyncMock(return_value=None))
            mock_analysis.return_value = AsyncMock(get_all=AsyncMock(return_value=[]))

            resp = client.get("/api/v1/workspace/repositories")
            assert resp.status_code == 200
            assert resp.json() == []


# ---------------------------------------------------------------------------
# Active repository
# ---------------------------------------------------------------------------


class TestGetActive:

    def test_returns_none_when_no_profile(self, client):
        with patch("api.routes.workspace._get_profile_repo") as mock_fn:
            mock_fn.return_value = AsyncMock(get_default=AsyncMock(return_value=None))
            resp = client.get("/api/v1/workspace/active")
            assert resp.status_code == 200
            data = resp.json()
            assert data["active_repo_id"] is None

    def test_returns_active_repo(self, client):
        from domain.entities.user_profile import UserProfile
        profile = UserProfile(id="p1", active_repo_id="repo-xyz")
        mock_repo = MagicMock()
        mock_repo.id = "repo-xyz"
        mock_repo.full_name = "acme/backend"
        mock_repo.owner = "acme"
        mock_repo.name = "backend"
        mock_repo.language = "Python"

        with patch("api.routes.workspace._get_profile_repo") as mock_pfn, \
             patch("api.routes.workspace._get_repos") as mock_rfn:
            mock_pfn.return_value = AsyncMock(get_default=AsyncMock(return_value=profile))
            mock_rfn.return_value = AsyncMock(get_by_id=AsyncMock(return_value=mock_repo))

            resp = client.get("/api/v1/workspace/active")
            assert resp.status_code == 200
            data = resp.json()
            assert data["active_repo_id"] == "repo-xyz"
            assert data["repository"]["name"] == "acme/backend"


class TestSetActive:

    def test_requires_repo_id(self, client):
        resp = client.put("/api/v1/workspace/active", json={})
        assert resp.status_code == 400

    def test_returns_404_if_no_blueprint(self, client, tmp_path):
        resp = client.put(
            "/api/v1/workspace/active",
            json={"repo_id": "non-existent"},
        )
        assert resp.status_code == 404

    def test_sets_active_repo(self, client, tmp_path):
        # Create blueprint dir
        bp_dir = tmp_path / "blueprints" / "repo-123"
        bp_dir.mkdir(parents=True)
        (bp_dir / "blueprint.json").write_text("{}")

        with patch("api.routes.workspace._get_profile_repo") as mock_fn:
            mock_fn.return_value = AsyncMock(set_active_repo=AsyncMock())
            resp = client.put(
                "/api/v1/workspace/active",
                json={"repo_id": "repo-123"},
            )
            assert resp.status_code == 200
            assert resp.json()["active_repo_id"] == "repo-123"


class TestClearActive:

    def test_clears_active(self, client):
        with patch("api.routes.workspace._get_profile_repo") as mock_fn:
            mock_fn.return_value = AsyncMock(set_active_repo=AsyncMock())
            resp = client.delete("/api/v1/workspace/active")
            assert resp.status_code == 200
            assert resp.json()["active_repo_id"] is None


# ---------------------------------------------------------------------------
# Agent files
# ---------------------------------------------------------------------------


class TestGetAgentFiles:

    def test_returns_404_if_no_blueprint(self, client, tmp_path):
        with patch("api.routes.workspace._load_structured_blueprint", return_value=None):
            resp = client.get("/api/v1/workspace/repositories/repo-1/agent-files")
            assert resp.status_code == 404

    def test_returns_agent_files(self, client, tmp_path):
        from domain.entities.blueprint import StructuredBlueprint, BlueprintMeta
        bp = StructuredBlueprint(meta=BlueprintMeta(repository="test/repo"))

        with patch("api.routes.workspace._load_structured_blueprint", return_value=bp):
            resp = client.get("/api/v1/workspace/repositories/repo-1/agent-files")
            assert resp.status_code == 200
            data = resp.json()
            assert "claude_md" in data
            assert "cursor_rules" in data
            assert "agents_md" in data
            assert "# CLAUDE.md" in data["claude_md"]
            assert "# AGENTS.md" in data["agents_md"]
            assert "globs:" in data["cursor_rules"]


# ---------------------------------------------------------------------------
# Delete repository
# ---------------------------------------------------------------------------


class TestDeleteRepository:

    def test_deletes_repository_storage(self, client, tmp_path):
        # Create blueprint dir
        bp_dir = tmp_path / "blueprints" / "repo-del"
        bp_dir.mkdir(parents=True)
        (bp_dir / "blueprint.json").write_text("{}")

        with patch("api.routes.workspace._get_profile_repo") as mock_fn:
            mock_fn.return_value = AsyncMock(
                get_default=AsyncMock(return_value=None),
                set_active_repo=AsyncMock(),
            )
            resp = client.delete("/api/v1/workspace/repositories/repo-del")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True
            # Directory should be gone
            assert not bp_dir.exists()

    def test_clears_active_if_was_active(self, client, tmp_path):
        from domain.entities.user_profile import UserProfile
        bp_dir = tmp_path / "blueprints" / "repo-del2"
        bp_dir.mkdir(parents=True)
        (bp_dir / "blueprint.json").write_text("{}")

        profile = UserProfile(id="p1", active_repo_id="repo-del2")
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_default = AsyncMock(return_value=profile)
        mock_profile_repo.set_active_repo = AsyncMock()

        with patch("api.routes.workspace._get_profile_repo", return_value=mock_profile_repo):
            resp = client.delete("/api/v1/workspace/repositories/repo-del2")
            assert resp.status_code == 200
            mock_profile_repo.set_active_repo.assert_called_once_with(None)

    def test_deletes_repository_from_database(self, client, tmp_path):
        """Verify the endpoint calls repo_repo.delete(repo_id)."""
        bp_dir = tmp_path / "blueprints" / "repo-db"
        bp_dir.mkdir(parents=True)
        (bp_dir / "blueprint.json").write_text("{}")

        mock_repo = AsyncMock()
        mock_repo.delete = AsyncMock(return_value=True)

        with patch("api.routes.workspace._get_repos", return_value=mock_repo), \
             patch("api.routes.workspace._get_profile_repo") as mock_pfn:
            mock_pfn.return_value = AsyncMock(
                get_default=AsyncMock(return_value=None),
                set_active_repo=AsyncMock(),
            )
            resp = client.delete("/api/v1/workspace/repositories/repo-db")
            assert resp.status_code == 200
            mock_repo.delete.assert_called_once_with("repo-db")

    def test_delete_continues_if_db_delete_fails(self, client, tmp_path):
        """Even if repo_repo.delete() raises, the endpoint returns 200."""
        bp_dir = tmp_path / "blueprints" / "repo-fail"
        bp_dir.mkdir(parents=True)
        (bp_dir / "blueprint.json").write_text("{}")

        mock_repo = AsyncMock()
        mock_repo.delete = AsyncMock(side_effect=Exception("DB gone"))

        with patch("api.routes.workspace._get_repos", return_value=mock_repo), \
             patch("api.routes.workspace._get_profile_repo") as mock_pfn:
            mock_pfn.return_value = AsyncMock(
                get_default=AsyncMock(return_value=None),
                set_active_repo=AsyncMock(),
            )
            resp = client.delete("/api/v1/workspace/repositories/repo-fail")
            assert resp.status_code == 200
            assert resp.json()["deleted"] is True

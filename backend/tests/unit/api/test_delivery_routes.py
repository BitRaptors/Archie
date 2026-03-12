"""Tests for delivery API routes."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.delivery import router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """Create a FastAPI app with the delivery router and mock container."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_container = MagicMock()

    # Mock delivery service
    mock_delivery = AsyncMock()
    mock_container.delivery_service.return_value = mock_delivery

    app.container = mock_container
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_delivery_service(app):
    return app.container.delivery_service.return_value


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

class TestDeliveryPreview:

    def test_preview_returns_outputs(self, client, mock_delivery_service):
        mock_delivery_service.preview = AsyncMock(return_value={
            "claude_md": "# CLAUDE.md content",
            "agents_md": "# AGENTS.md content",
        })

        resp = client.post("/api/v1/delivery/preview", json={
            "source_repo_id": "repo-123",
            "outputs": ["claude_md", "agents_md"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "claude_md" in data
        assert "agents_md" in data

    def test_preview_404_when_no_blueprint(self, client, mock_delivery_service):
        from domain.exceptions.domain_exceptions import ValidationError
        mock_delivery_service.preview = AsyncMock(
            side_effect=ValidationError("Blueprint not found for repository missing")
        )

        resp = client.post("/api/v1/delivery/preview", json={
            "source_repo_id": "missing",
            "outputs": ["claude_md"],
        })
        assert resp.status_code == 404

    def test_preview_validates_required_fields(self, client):
        resp = client.post("/api/v1/delivery/preview", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

class TestDeliveryApply:

    def test_apply_creates_pr(self, client, mock_delivery_service):
        from application.services.delivery_service import DeliveryResult
        mock_delivery_service.apply = AsyncMock(return_value=DeliveryResult(
            status="success",
            strategy="pr",
            branch="feature/archi/sync-architecture-outputs",
            pr_url="https://github.com/owner/repo/pull/42",
            files_delivered=["CLAUDE.md", "AGENTS.md"],
        ))

        with patch("api.routes.delivery.resolve_github_token", return_value="test-token"):
            resp = client.post("/api/v1/delivery/apply", json={
                "source_repo_id": "repo-123",
                "target_repo": "owner/repo",
                "strategy": "pr",
                "outputs": ["claude_md", "agents_md"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["strategy"] == "pr"
        assert data["pr_url"] == "https://github.com/owner/repo/pull/42"
        assert "CLAUDE.md" in data["files_delivered"]

    def test_apply_requires_github_token(self, client):
        with patch("api.routes.delivery.resolve_github_token", return_value=None):
            resp = client.post("/api/v1/delivery/apply", json={
                "source_repo_id": "repo-123",
                "target_repo": "owner/repo",
            })
        assert resp.status_code == 401

    def test_apply_validates_required_fields(self, client):
        resp = client.post("/api/v1/delivery/apply", json={})
        assert resp.status_code == 422

    def test_apply_commit_strategy(self, client, mock_delivery_service):
        from application.services.delivery_service import DeliveryResult
        mock_delivery_service.apply = AsyncMock(return_value=DeliveryResult(
            status="success",
            strategy="commit",
            branch="main",
            commit_sha="sha-abc123",
            files_delivered=["CLAUDE.md"],
        ))

        with patch("api.routes.delivery.resolve_github_token", return_value="test-token"):
            resp = client.post("/api/v1/delivery/apply", json={
                "source_repo_id": "repo-123",
                "target_repo": "owner/repo",
                "strategy": "commit",
                "outputs": ["claude_md"],
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["strategy"] == "commit"
        assert data["commit_sha"] == "sha-abc123"

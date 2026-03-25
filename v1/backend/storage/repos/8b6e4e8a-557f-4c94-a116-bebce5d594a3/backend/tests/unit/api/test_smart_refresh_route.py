"""Tests for smart-refresh API route."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.delivery import router
from application.services.smart_refresh_service import SmartRefreshResult, ArchitectureWarning


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_smart_refresh_service():
    return AsyncMock()


@pytest.fixture
def app(mock_smart_refresh_service):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_container = MagicMock()
    mock_container.smart_refresh_service.return_value = mock_smart_refresh_service
    # Also mock delivery_service so other routes don't break
    mock_container.delivery_service.return_value = AsyncMock()

    app.container = mock_container
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestSmartRefreshRoute:

    def test_returns_200_no_refresh(self, client, mock_smart_refresh_service):
        mock_smart_refresh_service.refresh = AsyncMock(
            return_value=SmartRefreshResult(status="no_refresh_needed")
        )

        resp = client.post("/api/v1/delivery/smart-refresh", json={
            "repo_id": "repo-123",
            "changed_files": ["src/api/routes.py"],
            "target_local_path": "/tmp/project",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "no_refresh_needed"
        assert data["warnings"] == []
        assert data["updated_files"] == []

    def test_returns_warnings(self, client, mock_smart_refresh_service):
        mock_smart_refresh_service.refresh = AsyncMock(
            return_value=SmartRefreshResult(
                status="warnings",
                warnings=[
                    ArchitectureWarning(
                        severity="warning",
                        folder="src/api",
                        message="File misplaced",
                        rule_violated="placement",
                        suggestion="Move file",
                    )
                ],
            )
        )

        resp = client.post("/api/v1/delivery/smart-refresh", json={
            "repo_id": "repo-123",
            "changed_files": ["src/api/bad_file.py"],
            "target_local_path": "/tmp/project",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "warnings"
        assert len(data["warnings"]) == 1
        assert data["warnings"][0]["severity"] == "warning"

    def test_returns_refreshed_with_updated_files(self, client, mock_smart_refresh_service):
        mock_smart_refresh_service.refresh = AsyncMock(
            return_value=SmartRefreshResult(
                status="refreshed",
                updated_files=["src/api/CLAUDE.md"],
            )
        )

        resp = client.post("/api/v1/delivery/smart-refresh", json={
            "repo_id": "repo-123",
            "changed_files": ["src/api/routes.py"],
            "target_local_path": "/tmp/project",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "refreshed"
        assert "src/api/CLAUDE.md" in data["updated_files"]

    def test_500_on_service_error(self, client, mock_smart_refresh_service):
        mock_smart_refresh_service.refresh = AsyncMock(
            side_effect=Exception("Internal error")
        )

        resp = client.post("/api/v1/delivery/smart-refresh", json={
            "repo_id": "repo-123",
            "changed_files": ["src/api/routes.py"],
            "target_local_path": "/tmp/project",
        })
        assert resp.status_code == 500

    def test_422_on_missing_required_fields(self, client):
        resp = client.post("/api/v1/delivery/smart-refresh", json={})
        assert resp.status_code == 422

    def test_422_on_missing_changed_files(self, client):
        resp = client.post("/api/v1/delivery/smart-refresh", json={
            "repo_id": "repo-123",
            "target_local_path": "/tmp/project",
        })
        assert resp.status_code == 422

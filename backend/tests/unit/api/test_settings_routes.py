"""Tests for settings API routes — ignored directories & library capabilities."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.settings import router
from domain.entities.analysis_settings import (
    CAPABILITY_OPTIONS,
    DEFAULT_IGNORED_DIRS,
    DEFAULT_LIBRARY_CAPABILITIES,
    ECOSYSTEM_OPTIONS,
    IgnoredDirectory,
    LibraryCapability,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _dir_entity(name: str) -> IgnoredDirectory:
    return IgnoredDirectory(id="uuid-1", directory_name=name, created_at=NOW)


def _lib_entity(name: str, eco: str, caps: list[str]) -> LibraryCapability:
    return LibraryCapability(
        id="uuid-1", library_name=name, ecosystem=eco,
        capabilities=caps, created_at=NOW, updated_at=NOW,
    )


@pytest.fixture
def mock_dirs_repo():
    repo = AsyncMock()
    repo.get_all = AsyncMock(return_value=[])
    repo.replace_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_libs_repo():
    repo = AsyncMock()
    repo.get_all = AsyncMock(return_value=[])
    repo.replace_all = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def app(mock_dirs_repo, mock_libs_repo):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    mock_db = AsyncMock()
    mock_container = MagicMock()
    mock_container.db = AsyncMock(return_value=mock_db)

    app.container = mock_container

    # Patch the repo factories to return our mocks
    import api.routes.settings as mod
    original_dirs = mod._get_ignored_dirs_repo
    original_libs = mod._get_lib_caps_repo

    async def _dirs_factory(request):
        return mock_dirs_repo

    async def _libs_factory(request):
        return mock_libs_repo

    mod._get_ignored_dirs_repo = _dirs_factory
    mod._get_lib_caps_repo = _libs_factory

    yield app

    # Restore originals
    mod._get_ignored_dirs_repo = original_dirs
    mod._get_lib_caps_repo = original_libs


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Enum / Options endpoints
# ---------------------------------------------------------------------------

class TestEcosystemOptions:

    def test_returns_sorted_list(self, client):
        resp = client.get("/api/v1/settings/ecosystem-options")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data == sorted(data)

    def test_contains_expected_values(self, client):
        resp = client.get("/api/v1/settings/ecosystem-options")
        data = resp.json()
        for eco in ["React", "iOS", "Android", "Python", "Flutter"]:
            assert eco in data

    def test_matches_constant(self, client):
        resp = client.get("/api/v1/settings/ecosystem-options")
        assert resp.json() == ECOSYSTEM_OPTIONS


class TestCapabilityOptions:

    def test_returns_sorted_list(self, client):
        resp = client.get("/api/v1/settings/capability-options")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data == sorted(data)

    def test_contains_expected_values(self, client):
        resp = client.get("/api/v1/settings/capability-options")
        data = resp.json()
        for cap in ["persistence", "networking", "authentication", "state_management"]:
            assert cap in data

    def test_matches_constant(self, client):
        resp = client.get("/api/v1/settings/capability-options")
        assert resp.json() == CAPABILITY_OPTIONS


# ---------------------------------------------------------------------------
# Ignored Directories
# ---------------------------------------------------------------------------

class TestListIgnoredDirs:

    def test_returns_empty_list(self, client, mock_dirs_repo):
        mock_dirs_repo.get_all = AsyncMock(return_value=[])
        resp = client.get("/api/v1/settings/ignored-dirs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_existing_dirs(self, client, mock_dirs_repo):
        mock_dirs_repo.get_all = AsyncMock(return_value=[
            _dir_entity("node_modules"),
            _dir_entity("Pods"),
        ])
        resp = client.get("/api/v1/settings/ignored-dirs")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["directory_name"] == "node_modules"
        assert data[1]["directory_name"] == "Pods"


class TestUpdateIgnoredDirs:

    def test_replaces_all_dirs(self, client, mock_dirs_repo):
        new_dirs = ["vendor", ".build", "dist"]
        mock_dirs_repo.replace_all = AsyncMock(return_value=[
            _dir_entity(d) for d in new_dirs
        ])
        resp = client.put("/api/v1/settings/ignored-dirs", json={"directories": new_dirs})
        assert resp.status_code == 200
        mock_dirs_repo.replace_all.assert_called_once_with(new_dirs)

    def test_accepts_empty_list(self, client, mock_dirs_repo):
        mock_dirs_repo.replace_all = AsyncMock(return_value=[])
        resp = client.put("/api/v1/settings/ignored-dirs", json={"directories": []})
        assert resp.status_code == 200
        mock_dirs_repo.replace_all.assert_called_once_with([])

    def test_rejects_missing_body(self, client):
        resp = client.put("/api/v1/settings/ignored-dirs", json={})
        assert resp.status_code == 422


class TestResetIgnoredDirs:

    def test_resets_to_defaults(self, client, mock_dirs_repo):
        expected = sorted(DEFAULT_IGNORED_DIRS)
        mock_dirs_repo.replace_all = AsyncMock(return_value=[
            _dir_entity(d) for d in expected
        ])
        resp = client.post("/api/v1/settings/ignored-dirs/reset")
        assert resp.status_code == 200
        mock_dirs_repo.replace_all.assert_called_once_with(expected)

    def test_returns_full_default_set(self, client, mock_dirs_repo):
        expected = sorted(DEFAULT_IGNORED_DIRS)
        mock_dirs_repo.replace_all = AsyncMock(return_value=[
            _dir_entity(d) for d in expected
        ])
        resp = client.post("/api/v1/settings/ignored-dirs/reset")
        data = resp.json()
        names = [d["directory_name"] for d in data]
        assert len(names) == len(DEFAULT_IGNORED_DIRS)


# ---------------------------------------------------------------------------
# Library Capabilities
# ---------------------------------------------------------------------------

class TestListLibraryCapabilities:

    def test_returns_empty_list(self, client, mock_libs_repo):
        mock_libs_repo.get_all = AsyncMock(return_value=[])
        resp = client.get("/api/v1/settings/library-capabilities")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_existing_libraries(self, client, mock_libs_repo):
        mock_libs_repo.get_all = AsyncMock(return_value=[
            _lib_entity("firebase", "Google Firebase", ["persistence", "authentication"]),
            _lib_entity("axios", "JavaScript", ["networking"]),
        ])
        resp = client.get("/api/v1/settings/library-capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["library_name"] == "firebase"
        assert data[0]["ecosystem"] == "Google Firebase"
        assert "persistence" in data[0]["capabilities"]
        assert data[1]["library_name"] == "axios"


class TestUpdateLibraryCapabilities:

    def test_replaces_all_libraries(self, client, mock_libs_repo):
        payload = {
            "libraries": [
                {"library_name": "prisma", "ecosystem": "Node.js", "capabilities": ["persistence", "orm"]},
                {"library_name": "sentry", "ecosystem": "Sentry", "capabilities": ["error_tracking"]},
            ]
        }
        mock_libs_repo.replace_all = AsyncMock(return_value=[
            _lib_entity("prisma", "Node.js", ["persistence", "orm"]),
            _lib_entity("sentry", "Sentry", ["error_tracking"]),
        ])
        resp = client.put("/api/v1/settings/library-capabilities", json=payload)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_accepts_empty_capabilities(self, client, mock_libs_repo):
        payload = {
            "libraries": [
                {"library_name": "newlib", "ecosystem": "React", "capabilities": []},
            ]
        }
        mock_libs_repo.replace_all = AsyncMock(return_value=[
            _lib_entity("newlib", "React", []),
        ])
        resp = client.put("/api/v1/settings/library-capabilities", json=payload)
        assert resp.status_code == 200

    def test_rejects_invalid_capabilities(self, client, mock_libs_repo):
        payload = {
            "libraries": [
                {"library_name": "bad", "ecosystem": "X", "capabilities": ["not_a_real_cap"]},
            ]
        }
        resp = client.put("/api/v1/settings/library-capabilities", json=payload)
        assert resp.status_code == 422
        assert "not_a_real_cap" in resp.json()["detail"]

    def test_rejects_mixed_valid_and_invalid(self, client, mock_libs_repo):
        payload = {
            "libraries": [
                {"library_name": "ok", "ecosystem": "React", "capabilities": ["persistence"]},
                {"library_name": "bad", "ecosystem": "X", "capabilities": ["persistence", "fake_cap"]},
            ]
        }
        resp = client.put("/api/v1/settings/library-capabilities", json=payload)
        assert resp.status_code == 422
        assert "fake_cap" in resp.json()["detail"]
        assert "bad" in resp.json()["detail"]

    def test_all_capability_options_accepted(self, client, mock_libs_repo):
        """Every value in CAPABILITY_OPTIONS should be accepted."""
        payload = {
            "libraries": [
                {"library_name": "all_caps", "ecosystem": "React", "capabilities": CAPABILITY_OPTIONS},
            ]
        }
        mock_libs_repo.replace_all = AsyncMock(return_value=[
            _lib_entity("all_caps", "React", CAPABILITY_OPTIONS),
        ])
        resp = client.put("/api/v1/settings/library-capabilities", json=payload)
        assert resp.status_code == 200

    def test_rejects_missing_body(self, client):
        resp = client.put("/api/v1/settings/library-capabilities", json={})
        assert resp.status_code == 422


class TestResetLibraryCapabilities:

    def test_resets_to_defaults(self, client, mock_libs_repo):
        expected_libs = [
            _lib_entity(name, info["ecosystem"], info["capabilities"])
            for name, info in sorted(DEFAULT_LIBRARY_CAPABILITIES.items())
        ]
        mock_libs_repo.replace_all = AsyncMock(return_value=expected_libs)
        resp = client.post("/api/v1/settings/library-capabilities/reset")
        assert resp.status_code == 200
        mock_libs_repo.replace_all.assert_called_once()
        call_args = mock_libs_repo.replace_all.call_args[0][0]
        lib_names = [r["library_name"] for r in call_args]
        assert lib_names == sorted(DEFAULT_LIBRARY_CAPABILITIES.keys())

    def test_reset_includes_all_default_libraries(self, client, mock_libs_repo):
        expected_libs = [
            _lib_entity(name, info["ecosystem"], info["capabilities"])
            for name, info in sorted(DEFAULT_LIBRARY_CAPABILITIES.items())
        ]
        mock_libs_repo.replace_all = AsyncMock(return_value=expected_libs)
        resp = client.post("/api/v1/settings/library-capabilities/reset")
        data = resp.json()
        assert len(data) == len(DEFAULT_LIBRARY_CAPABILITIES)

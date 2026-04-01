"""Tests for IgnoredDirsRepository and LibraryCapabilitiesRepository."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from infrastructure.persistence.analysis_settings_repository import (
    IgnoredDirsRepository,
    LibraryCapabilitiesRepository,
)
from domain.entities.analysis_settings import IgnoredDirectory, LibraryCapability


# ---------------------------------------------------------------------------
# Helpers — mock the Supabase fluent query builder
# ---------------------------------------------------------------------------

NOW_ISO = "2025-01-01T00:00:00+00:00"


def _make_mock_db(data: list[dict] | None = None):
    """Build a mock DB client that supports fluent chaining."""
    if data is None:
        data = []

    mock_db = MagicMock()
    chain = MagicMock()
    chain.select = MagicMock(return_value=chain)
    chain.order = MagicMock(return_value=chain)
    chain.insert = MagicMock(return_value=chain)
    chain.delete = MagicMock(return_value=chain)
    chain.neq = MagicMock(return_value=chain)
    chain.execute = AsyncMock(return_value=MagicMock(data=data))
    mock_db.table = MagicMock(return_value=chain)
    return mock_db, chain


# ---------------------------------------------------------------------------
# IgnoredDirsRepository
# ---------------------------------------------------------------------------

class TestIgnoredDirsRepository:

    @pytest.mark.asyncio
    async def test_get_all_returns_entities(self):
        rows = [
            {"id": "id-1", "directory_name": "node_modules", "created_at": NOW_ISO},
            {"id": "id-2", "directory_name": "Pods", "created_at": NOW_ISO},
        ]
        db, chain = _make_mock_db(rows)
        repo = IgnoredDirsRepository(db=db)

        result = await repo.get_all()

        assert len(result) == 2
        assert isinstance(result[0], IgnoredDirectory)
        assert result[0].directory_name == "node_modules"
        assert result[1].directory_name == "Pods"
        chain.select.assert_called_once_with("*")
        chain.order.assert_called_once_with("directory_name")

    @pytest.mark.asyncio
    async def test_get_all_empty(self):
        db, _ = _make_mock_db([])
        repo = IgnoredDirsRepository(db=db)

        result = await repo.get_all()
        assert result == []

    @pytest.mark.asyncio
    async def test_replace_all_deletes_and_inserts(self):
        db, chain = _make_mock_db([])
        repo = IgnoredDirsRepository(db=db)
        repo.get_all = AsyncMock(return_value=[
            IgnoredDirectory(id="id-1", directory_name="vendor"),
        ])

        result = await repo.replace_all(["vendor"])

        # Verify delete was called
        chain.delete.assert_called()
        chain.neq.assert_called_once_with("id", "00000000-0000-0000-0000-000000000000")
        # Verify insert was called with correct rows
        chain.insert.assert_called_once_with([{"directory_name": "vendor"}])
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_replace_all_empty_list_skips_insert(self):
        db, chain = _make_mock_db([])
        repo = IgnoredDirsRepository(db=db)
        repo.get_all = AsyncMock(return_value=[])

        await repo.replace_all([])

        chain.delete.assert_called()
        chain.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_to_entity_handles_missing_created_at(self):
        rows = [{"id": "id-1", "directory_name": "dist", "created_at": None}]
        db, _ = _make_mock_db(rows)
        repo = IgnoredDirsRepository(db=db)

        result = await repo.get_all()
        assert result[0].created_at is None


# ---------------------------------------------------------------------------
# LibraryCapabilitiesRepository
# ---------------------------------------------------------------------------

class TestLibraryCapabilitiesRepository:

    @pytest.mark.asyncio
    async def test_get_all_returns_entities(self):
        rows = [
            {
                "id": "id-1", "library_name": "firebase",
                "ecosystem": "Google Firebase",
                "capabilities": ["persistence", "authentication"],
                "created_at": NOW_ISO, "updated_at": NOW_ISO,
            },
        ]
        db, chain = _make_mock_db(rows)
        repo = LibraryCapabilitiesRepository(db=db)

        result = await repo.get_all()

        assert len(result) == 1
        assert isinstance(result[0], LibraryCapability)
        assert result[0].library_name == "firebase"
        assert result[0].ecosystem == "Google Firebase"
        assert result[0].capabilities == ["persistence", "authentication"]

    @pytest.mark.asyncio
    async def test_get_all_handles_postgres_text_array_string(self):
        """Postgres may return TEXT[] as a string like '{persistence,auth}'."""
        rows = [
            {
                "id": "id-1", "library_name": "redux",
                "ecosystem": "React",
                "capabilities": "{state_management}",
                "created_at": NOW_ISO, "updated_at": None,
            },
        ]
        db, _ = _make_mock_db(rows)
        repo = LibraryCapabilitiesRepository(db=db)

        result = await repo.get_all()
        assert result[0].capabilities == ["state_management"]

    @pytest.mark.asyncio
    async def test_get_all_handles_postgres_multi_value_string(self):
        """Postgres TEXT[] as '{a,b,c}'."""
        rows = [
            {
                "id": "id-1", "library_name": "firebase",
                "ecosystem": "Google Firebase",
                "capabilities": "{persistence,authentication,storage}",
                "created_at": NOW_ISO, "updated_at": NOW_ISO,
            },
        ]
        db, _ = _make_mock_db(rows)
        repo = LibraryCapabilitiesRepository(db=db)

        result = await repo.get_all()
        assert result[0].capabilities == ["persistence", "authentication", "storage"]

    @pytest.mark.asyncio
    async def test_get_all_handles_empty_capabilities(self):
        rows = [
            {
                "id": "id-1", "library_name": "newlib",
                "ecosystem": "React", "capabilities": [],
                "created_at": NOW_ISO, "updated_at": None,
            },
        ]
        db, _ = _make_mock_db(rows)
        repo = LibraryCapabilitiesRepository(db=db)

        result = await repo.get_all()
        assert result[0].capabilities == []

    @pytest.mark.asyncio
    async def test_get_all_handles_empty_string_capabilities(self):
        """Postgres empty TEXT[] might come as '{}'."""
        rows = [
            {
                "id": "id-1", "library_name": "newlib",
                "ecosystem": "React", "capabilities": "{}",
                "created_at": NOW_ISO, "updated_at": None,
            },
        ]
        db, _ = _make_mock_db(rows)
        repo = LibraryCapabilitiesRepository(db=db)

        result = await repo.get_all()
        assert result[0].capabilities == []

    @pytest.mark.asyncio
    async def test_replace_all_deletes_and_inserts(self):
        db, chain = _make_mock_db([])
        repo = LibraryCapabilitiesRepository(db=db)
        repo.get_all = AsyncMock(return_value=[
            LibraryCapability(
                id="id-1", library_name="axios",
                ecosystem="JavaScript", capabilities=["networking"],
            ),
        ])

        result = await repo.replace_all([
            {"library_name": "axios", "ecosystem": "JavaScript", "capabilities": ["networking"]},
        ])

        chain.delete.assert_called()
        chain.neq.assert_called_once_with("id", "00000000-0000-0000-0000-000000000000")
        chain.insert.assert_called_once_with([
            {"library_name": "axios", "ecosystem": "JavaScript", "capabilities": ["networking"]},
        ])
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_replace_all_empty_list_skips_insert(self):
        db, chain = _make_mock_db([])
        repo = LibraryCapabilitiesRepository(db=db)
        repo.get_all = AsyncMock(return_value=[])

        await repo.replace_all([])

        chain.delete.assert_called()
        chain.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_replace_all_defaults_missing_fields(self):
        db, chain = _make_mock_db([])
        repo = LibraryCapabilitiesRepository(db=db)
        repo.get_all = AsyncMock(return_value=[])

        await repo.replace_all([{"library_name": "minimal"}])

        chain.insert.assert_called_once_with([
            {"library_name": "minimal", "ecosystem": "", "capabilities": []},
        ])

    @pytest.mark.asyncio
    async def test_to_entity_handles_missing_timestamps(self):
        rows = [
            {
                "id": "id-1", "library_name": "lib",
                "ecosystem": "", "capabilities": [],
                "created_at": None, "updated_at": None,
            },
        ]
        db, _ = _make_mock_db(rows)
        repo = LibraryCapabilitiesRepository(db=db)

        result = await repo.get_all()
        assert result[0].created_at is None
        assert result[0].updated_at is None

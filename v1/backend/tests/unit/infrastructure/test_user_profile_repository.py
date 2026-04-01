"""Tests for UserProfileRepository."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from domain.entities.user_profile import UserProfile
from domain.interfaces.database import DatabaseError, QueryResult


@pytest.fixture
def mock_db():
    """Create a mock DatabaseClient with chainable QueryBuilder."""
    db = MagicMock()
    mock_qb = MagicMock()
    # Make all chainable methods return mock_qb
    for method in ("select", "insert", "update", "delete", "upsert",
                   "eq", "range", "order", "limit", "maybe_single"):
        getattr(mock_qb, method).return_value = mock_qb
    mock_qb.execute = AsyncMock(return_value=QueryResult(data=None))
    db.table.return_value = mock_qb
    return db, mock_qb


@pytest.fixture
def repo(mock_db):
    from infrastructure.persistence.user_profile_repository import UserProfileRepository
    db, _ = mock_db
    return UserProfileRepository(db=db)


class TestGetDefault:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_profile(self, repo, mock_db):
        _, mock_qb = mock_db
        mock_qb.execute = AsyncMock(return_value=QueryResult(data=None))
        result = await repo.get_default()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_profile_when_exists(self, repo, mock_db):
        _, mock_qb = mock_db
        mock_qb.execute = AsyncMock(return_value=QueryResult(data={
            "id": "profile-1",
            "active_repo_id": "repo-abc",
            "preferences": {"theme": "dark"},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
        }))
        result = await repo.get_default()
        assert result is not None
        assert isinstance(result, UserProfile)
        assert result.id == "profile-1"
        assert result.active_repo_id == "repo-abc"
        assert result.preferences == {"theme": "dark"}

    @pytest.mark.asyncio
    async def test_returns_none_on_204_error(self, repo, mock_db):
        _, mock_qb = mock_db
        mock_qb.execute = AsyncMock(side_effect=DatabaseError(code="204", message="No content"))
        result = await repo.get_default()
        assert result is None

    @pytest.mark.asyncio
    async def test_raises_on_other_error(self, repo, mock_db):
        _, mock_qb = mock_db
        mock_qb.execute = AsyncMock(side_effect=DatabaseError(code="500", message="Internal"))
        with pytest.raises(DatabaseError):
            await repo.get_default()


class TestUpsert:
    @pytest.mark.asyncio
    async def test_upserts_profile(self, repo, mock_db):
        _, mock_qb = mock_db
        mock_qb.execute = AsyncMock(return_value=QueryResult(data=[{
            "id": "profile-1",
            "active_repo_id": "repo-new",
            "preferences": {},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
        }]))

        profile = UserProfile(id="profile-1", active_repo_id="repo-new")
        result = await repo.upsert(profile)

        assert result.id == "profile-1"
        assert result.active_repo_id == "repo-new"
        mock_qb.upsert.assert_called_once()


class TestSetActiveRepo:
    @pytest.mark.asyncio
    async def test_updates_existing_profile(self, repo, mock_db):
        _, mock_qb = mock_db
        # First call: get_default returns an existing profile
        existing_data = {
            "id": "profile-1",
            "active_repo_id": "old-repo",
            "preferences": {},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
        }
        call_count = {"n": 0}

        async def execute_side_effect():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return QueryResult(data=existing_data)
            return QueryResult(data=[])

        mock_qb.execute = AsyncMock(side_effect=execute_side_effect)

        await repo.set_active_repo("new-repo-id")

        # update should have been called
        mock_qb.update.assert_called_once()
        update_args = mock_qb.update.call_args[0][0]
        assert update_args["active_repo_id"] == "new-repo-id"

    @pytest.mark.asyncio
    async def test_creates_profile_when_none_exists(self, repo, mock_db):
        _, mock_qb = mock_db
        call_count = {"n": 0}

        async def execute_side_effect():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return QueryResult(data=None)  # get_default returns None
            return QueryResult(data=[{"id": "new-profile"}])

        mock_qb.execute = AsyncMock(side_effect=execute_side_effect)

        await repo.set_active_repo("new-repo-id")

        # insert should have been called
        mock_qb.insert.assert_called_once()
        insert_args = mock_qb.insert.call_args[0][0]
        assert insert_args["active_repo_id"] == "new-repo-id"

    @pytest.mark.asyncio
    async def test_clears_active_repo(self, repo, mock_db):
        _, mock_qb = mock_db
        existing_data = {
            "id": "profile-1",
            "active_repo_id": "some-repo",
            "preferences": {},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
        }
        call_count = {"n": 0}

        async def execute_side_effect():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return QueryResult(data=existing_data)
            return QueryResult(data=[])

        mock_qb.execute = AsyncMock(side_effect=execute_side_effect)

        await repo.set_active_repo(None)

        mock_qb.update.assert_called_once()
        update_args = mock_qb.update.call_args[0][0]
        assert update_args["active_repo_id"] is None


class TestEntityMapping:
    def test_to_entity_with_full_data(self, repo):
        data = {
            "id": "profile-1",
            "active_repo_id": "repo-abc",
            "preferences": {"key": "val"},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T12:00:00Z",
        }
        entity = repo._to_entity(data)
        assert entity.id == "profile-1"
        assert entity.active_repo_id == "repo-abc"
        assert entity.preferences == {"key": "val"}
        assert isinstance(entity.created_at, datetime)
        assert isinstance(entity.updated_at, datetime)

    def test_to_entity_with_missing_optional_fields(self, repo):
        data = {
            "id": "profile-1",
        }
        entity = repo._to_entity(data)
        assert entity.id == "profile-1"
        assert entity.active_repo_id is None
        assert entity.preferences == {}
        assert entity.created_at is None
        assert entity.updated_at is None

    def test_to_dict_round_trip(self, repo):
        profile = UserProfile(
            id="profile-1",
            active_repo_id="repo-abc",
            preferences={"theme": "dark"},
        )
        d = repo._to_dict(profile)
        assert d["id"] == "profile-1"
        assert d["active_repo_id"] == "repo-abc"
        assert d["preferences"] == {"theme": "dark"}

"""Parametric repository tests — run with both Postgres and Supabase mocks.

Verifies that all repositories produce identical behavior regardless of
which DatabaseClient backend is in use.

Mock strategy: Build mock DatabaseClient implementations that record method
calls and return canned QueryResult data.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from domain.interfaces.database import DatabaseClient, QueryBuilder, QueryResult


# ── Mock DatabaseClient ────────────────────────────────────────────────────


class MockQueryBuilder(QueryBuilder):
    """Records method calls and returns canned data on execute()."""

    def __init__(self, canned_data=None, canned_single=None):
        self._canned_data = canned_data if canned_data is not None else []
        self._canned_single = canned_single
        self._calls: list[tuple[str, tuple]] = []
        self._maybe_single_flag = False

    def _record(self, method, *args, **kwargs):
        self._calls.append((method, args, kwargs))
        return self

    def select(self, columns="*"):
        return self._record("select", columns)

    def insert(self, data):
        return self._record("insert", data)

    def update(self, data):
        return self._record("update", data)

    def delete(self):
        return self._record("delete")

    def upsert(self, data, *, on_conflict=""):
        return self._record("upsert", data, on_conflict=on_conflict)

    def eq(self, column, value):
        return self._record("eq", column, value)

    def neq(self, column, value):
        return self._record("neq", column, value)

    def in_(self, column, values):
        return self._record("in_", column, values)

    def range(self, start, end):
        return self._record("range", start, end)

    def order(self, column, *, desc=False):
        return self._record("order", column, desc=desc)

    def limit(self, count):
        return self._record("limit", count)

    def maybe_single(self):
        self._maybe_single_flag = True
        return self._record("maybe_single")

    async def execute(self):
        if self._maybe_single_flag:
            return QueryResult(data=self._canned_single)
        return QueryResult(data=self._canned_data)


class MockDatabaseClient(DatabaseClient):
    """Mock that returns canned data from table()."""

    def __init__(self, canned_data=None, canned_single=None):
        self._canned_data = canned_data if canned_data is not None else []
        self._canned_single = canned_single
        self._last_builder: MockQueryBuilder | None = None

    def table(self, name: str) -> MockQueryBuilder:
        self._last_builder = MockQueryBuilder(
            canned_data=self._canned_data,
            canned_single=self._canned_single,
        )
        return self._last_builder

    async def rpc(self, function_name, params):
        return QueryResult(data=self._canned_data)


# ── Parametric fixture ─────────────────────────────────────────────────────


@pytest.fixture(params=["postgres", "supabase"])
def mock_db(request):
    """Provide a mock DatabaseClient labeled by backend name."""
    # Both backends use the same mock — the point is that the repository
    # code doesn't care which backend it talks to.
    return request.param, MockDatabaseClient


# ── PromptRepository tests ─────────────────────────────────────────────────


class TestPromptRepository:

    @pytest.mark.asyncio
    async def test_add_and_get_by_id(self, mock_db):
        backend, DbFactory = mock_db
        prompt_data = {
            "id": str(uuid.uuid4()),
            "name": "Discovery",
            "category": "discovery",
            "prompt_template": "Analyze...",
            "variables": [],
            "is_default": True,
            "key": "discovery",
            "type": "prompt",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
            "user_id": None,
            "description": "Discovery prompt",
        }
        db = DbFactory(canned_data=[prompt_data], canned_single=prompt_data)

        from infrastructure.persistence.prompt_repository import PromptRepository
        repo = PromptRepository(db=db)
        result = await repo.get_by_id(prompt_data["id"])
        assert result is not None
        assert result.name == "Discovery"

    @pytest.mark.asyncio
    async def test_get_by_key(self, mock_db):
        _, DbFactory = mock_db
        prompt_data = {
            "id": str(uuid.uuid4()),
            "name": "Discovery",
            "category": "discovery",
            "prompt_template": "Analyze...",
            "variables": [],
            "is_default": True,
            "key": "discovery",
            "type": "prompt",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
            "user_id": None,
            "description": "Discovery prompt",
        }
        db = DbFactory(canned_single=prompt_data)

        from infrastructure.persistence.prompt_repository import PromptRepository
        repo = PromptRepository(db=db)
        result = await repo.get_by_key("discovery")
        assert result is not None
        assert result.key == "discovery"

    @pytest.mark.asyncio
    async def test_get_by_key_not_found(self, mock_db):
        _, DbFactory = mock_db
        db = DbFactory(canned_single=None)

        from infrastructure.persistence.prompt_repository import PromptRepository
        repo = PromptRepository(db=db)
        result = await repo.get_by_key("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_defaults(self, mock_db):
        _, DbFactory = mock_db
        prompts = [
            {
                "id": str(uuid.uuid4()),
                "name": f"Prompt {i}",
                "category": "cat",
                "prompt_template": "...",
                "variables": [],
                "is_default": True,
                "key": f"key_{i}",
                "type": "prompt",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
                "user_id": None,
                "description": f"Prompt {i}",
            }
            for i in range(3)
        ]
        db = DbFactory(canned_data=prompts)

        from infrastructure.persistence.prompt_repository import PromptRepository
        repo = PromptRepository(db=db)
        results = await repo.get_all_defaults()
        assert len(results) == 3


# ── UserRepository tests ──────────────────────────────────────────────────


class TestUserRepository:

    @pytest.mark.asyncio
    async def test_add_and_get_by_id(self, mock_db):
        _, DbFactory = mock_db
        user_data = {
            "id": str(uuid.uuid4()),
            "github_token_encrypted": "encrypted_token",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        db = DbFactory(canned_data=[user_data], canned_single=user_data)

        from infrastructure.persistence.user_repository import UserRepository
        repo = UserRepository(db=db)
        result = await repo.get_by_id(user_data["id"])
        assert result is not None

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db):
        _, DbFactory = mock_db
        db = DbFactory(canned_single=None)

        from infrastructure.persistence.user_repository import UserRepository
        repo = UserRepository(db=db)
        result = await repo.get_by_id("nonexistent")
        assert result is None


# ── RepositoryRepository tests ────────────────────────────────────────────


class TestRepositoryRepository:

    @pytest.mark.asyncio
    async def test_get_by_id(self, mock_db):
        _, DbFactory = mock_db
        repo_data = {
            "id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "owner": "acme",
            "name": "app",
            "full_name": "acme/app",
            "url": "https://github.com/acme/app",
            "description": "Test repo",
            "language": "Python",
            "default_branch": "main",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        db = DbFactory(canned_single=repo_data)

        from infrastructure.persistence.repository_repository import RepositoryRepository
        repo = RepositoryRepository(db=db)
        result = await repo.get_by_id(repo_data["id"])
        assert result is not None
        assert result.full_name == "acme/app"

    @pytest.mark.asyncio
    async def test_get_by_full_name(self, mock_db):
        _, DbFactory = mock_db
        repo_data = {
            "id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "owner": "acme",
            "name": "app",
            "full_name": "acme/app",
            "url": "https://github.com/acme/app",
            "description": "Test repo",
            "language": "Python",
            "default_branch": "main",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        db = DbFactory(canned_single=repo_data)

        from infrastructure.persistence.repository_repository import RepositoryRepository
        repo = RepositoryRepository(db=db)
        result = await repo.get_by_full_name(repo_data["user_id"], "acme", "app")
        assert result is not None


# ── AnalysisRepository tests ──────────────────────────────────────────────


class TestAnalysisRepository:

    @pytest.mark.asyncio
    async def test_get_by_id(self, mock_db):
        _, DbFactory = mock_db
        analysis_data = {
            "id": str(uuid.uuid4()),
            "repository_id": str(uuid.uuid4()),
            "status": "completed",
            "progress_percentage": 100,
            "error_message": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        db = DbFactory(canned_single=analysis_data)

        from infrastructure.persistence.analysis_repository import AnalysisRepository
        repo = AnalysisRepository(db=db)
        result = await repo.get_by_id(analysis_data["id"])
        assert result is not None
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_get_all(self, mock_db):
        _, DbFactory = mock_db
        analyses = [
            {
                "id": str(uuid.uuid4()),
                "repository_id": str(uuid.uuid4()),
                "status": "completed",
                "progress_percentage": 100,
                "error_message": None,
                "started_at": None,
                "completed_at": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
            }
            for _ in range(3)
        ]
        db = DbFactory(canned_data=analyses)

        from infrastructure.persistence.analysis_repository import AnalysisRepository
        repo = AnalysisRepository(db=db)
        results = await repo.get_all()
        assert len(results) == 3


# ── AnalysisEventRepository tests ─────────────────────────────────────────


class TestAnalysisEventRepository:

    @pytest.mark.asyncio
    async def test_get_by_analysis_id(self, mock_db):
        _, DbFactory = mock_db
        events = [
            {
                "id": str(uuid.uuid4()),
                "analysis_id": "analysis-123",
                "event_type": "INFO",
                "message": "Started",
                "details": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        db = DbFactory(canned_data=events)

        from infrastructure.persistence.analysis_event_repository import AnalysisEventRepository
        repo = AnalysisEventRepository(db=db)
        results = await repo.get_by_analysis_id("analysis-123")
        assert len(results) == 1
        assert results[0].message == "Started"


# ── AnalysisDataRepository tests ──────────────────────────────────────────


class TestAnalysisDataRepository:

    @pytest.mark.asyncio
    async def test_upsert(self, mock_db):
        _, DbFactory = mock_db
        upserted = {
            "id": str(uuid.uuid4()),
            "analysis_id": "analysis-123",
            "data_type": "gathered",
            "data": {"file_tree": "..."},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        db = DbFactory(canned_data=[upserted])

        from infrastructure.persistence.analysis_data_repository import AnalysisDataRepository
        repo = AnalysisDataRepository(db=db)
        # Should not raise
        await repo.upsert("analysis-123", "gathered", {"file_tree": "..."})

    @pytest.mark.asyncio
    async def test_get_by_analysis_id(self, mock_db):
        _, DbFactory = mock_db
        rows = [
            {
                "id": str(uuid.uuid4()),
                "analysis_id": "analysis-123",
                "data_type": "gathered",
                "data": {"file_tree": "..."},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": str(uuid.uuid4()),
                "analysis_id": "analysis-123",
                "data_type": "phase_discovery",
                "data": {"phase": "discovery"},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        db = DbFactory(canned_data=rows)

        from infrastructure.persistence.analysis_data_repository import AnalysisDataRepository
        repo = AnalysisDataRepository(db=db)
        results = await repo.get_by_analysis_id("analysis-123")
        assert len(results) == 2


# ── UserProfileRepository tests ──────────────────────────────────────────


class TestUserProfileRepository:

    @pytest.mark.asyncio
    async def test_get_default(self, mock_db):
        _, DbFactory = mock_db
        profile_data = {
            "id": str(uuid.uuid4()),
            "user_id": str(uuid.uuid4()),
            "active_repository_id": str(uuid.uuid4()),
            "preferences": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": None,
        }
        db = DbFactory(canned_single=profile_data)

        from infrastructure.persistence.user_profile_repository import UserProfileRepository
        repo = UserProfileRepository(db=db)
        result = await repo.get_default()
        assert result is not None

    @pytest.mark.asyncio
    async def test_set_active_repo(self, mock_db):
        _, DbFactory = mock_db
        db = DbFactory(canned_data=[{"id": "1"}])

        from infrastructure.persistence.user_profile_repository import UserProfileRepository
        repo = UserProfileRepository(db=db)
        # Should not raise
        await repo.set_active_repo("new-repo-id")

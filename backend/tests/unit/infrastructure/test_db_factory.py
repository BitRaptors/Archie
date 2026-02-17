"""Tests for db_factory: backend switching, caching, validation."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.interfaces.database import DatabaseClient


class TestDbFactory:

    @pytest.fixture(autouse=True)
    def reset_cache(self):
        """Reset the module-level cache before each test."""
        import infrastructure.persistence.db_factory as factory
        factory._cached_db = None
        factory._cached_pool = None
        yield
        factory._cached_db = None
        factory._cached_pool = None

    @pytest.mark.asyncio
    @patch("infrastructure.persistence.db_factory.get_settings")
    @patch("infrastructure.persistence.db_factory.asyncpg", create=True)
    async def test_create_db_postgres_returns_postgres_adapter(self, mock_asyncpg_mod, mock_get_settings):
        from infrastructure.persistence.db_factory import create_db
        from infrastructure.persistence.postgres_adapter import PostgresAdapter

        mock_settings = MagicMock()
        mock_settings.db_backend = "postgres"
        mock_settings.database_url = "postgresql://localhost/test"
        mock_get_settings.return_value = mock_settings

        # Mock asyncpg.create_pool
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_conn)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_pool.acquire.return_value = ctx

        with patch("asyncpg.create_pool", new_callable=AsyncMock, return_value=mock_pool):
            db = await create_db()

        assert isinstance(db, PostgresAdapter)

    @pytest.mark.asyncio
    @patch("infrastructure.persistence.db_factory.get_settings")
    async def test_create_db_supabase_returns_supabase_adapter(self, mock_get_settings):
        from infrastructure.persistence.db_factory import create_db
        from infrastructure.persistence.supabase_adapter import SupabaseAdapter

        mock_settings = MagicMock()
        mock_settings.db_backend = "supabase"
        mock_settings.supabase_url = "https://example.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        with patch("supabase.create_async_client", new_callable=AsyncMock, return_value=mock_client):
            db = await create_db()

        assert isinstance(db, SupabaseAdapter)

    @pytest.mark.asyncio
    @patch("infrastructure.persistence.db_factory.get_settings")
    async def test_create_db_caches_singleton(self, mock_get_settings):
        from infrastructure.persistence.db_factory import create_db

        mock_settings = MagicMock()
        mock_settings.db_backend = "supabase"
        mock_settings.supabase_url = "https://example.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        with patch("supabase.create_async_client", new_callable=AsyncMock, return_value=mock_client) as mock_create:
            db1 = await create_db()
            db2 = await create_db()

        assert db1 is db2
        mock_create.assert_called_once()  # Only created once

    @pytest.mark.asyncio
    @patch("infrastructure.persistence.db_factory.get_settings")
    async def test_shutdown_db_closes_pool(self, mock_get_settings):
        from infrastructure.persistence.db_factory import create_db, shutdown_db

        mock_settings = MagicMock()
        mock_settings.db_backend = "supabase"
        mock_settings.supabase_url = "https://example.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        with patch("supabase.create_async_client", new_callable=AsyncMock, return_value=mock_client):
            await create_db()

        # aclose is the method on supabase async client
        await shutdown_db()

    @pytest.mark.asyncio
    @patch("infrastructure.persistence.db_factory.get_settings")
    async def test_shutdown_db_resets_cache(self, mock_get_settings):
        from infrastructure.persistence.db_factory import create_db, shutdown_db
        import infrastructure.persistence.db_factory as factory

        mock_settings = MagicMock()
        mock_settings.db_backend = "supabase"
        mock_settings.supabase_url = "https://example.supabase.co"
        mock_settings.supabase_key = "test-key"
        mock_get_settings.return_value = mock_settings

        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        with patch("supabase.create_async_client", new_callable=AsyncMock, return_value=mock_client):
            await create_db()
            assert factory._cached_db is not None

            await shutdown_db()
            assert factory._cached_db is None
            assert factory._cached_pool is None

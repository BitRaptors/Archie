"""Tests for the database abstraction layer and SupabaseAdapter.

Verifies:
  - QueryResult data model
  - DatabaseError carries code + message
  - SupabaseAdapter delegates to the underlying Supabase client
  - SupabaseQueryBuilder chains correctly
  - APIError -> DatabaseError translation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from domain.interfaces.database import DatabaseClient, DatabaseError, QueryBuilder, QueryResult


# ── QueryResult ──────────────────────────────────────────────────────────────


class TestQueryResult:
    def test_stores_data(self):
        qr = QueryResult(data=[{"id": 1}])
        assert qr.data == [{"id": 1}]

    def test_stores_none(self):
        qr = QueryResult(data=None)
        assert qr.data is None

    def test_stores_dict(self):
        qr = QueryResult(data={"key": "value"})
        assert qr.data["key"] == "value"


# ── DatabaseError ────────────────────────────────────────────────────────────


class TestDatabaseError:
    def test_basic(self):
        err = DatabaseError(code="42P01", message="table not found")
        assert err.code == "42P01"
        assert "table not found" in str(err)

    def test_is_exception(self):
        assert issubclass(DatabaseError, Exception)

    def test_empty_defaults(self):
        err = DatabaseError()
        assert err.code == ""
        assert str(err) == ""


# ── ABC sanity ───────────────────────────────────────────────────────────────


class TestAbstractInterfaces:
    """Verify we cannot instantiate the ABCs directly."""

    def test_cannot_instantiate_query_builder(self):
        with pytest.raises(TypeError):
            QueryBuilder()

    def test_cannot_instantiate_database_client(self):
        with pytest.raises(TypeError):
            DatabaseClient()


# ── SupabaseAdapter ──────────────────────────────────────────────────────────


class TestSupabaseAdapter:
    """Tests for SupabaseAdapter + SupabaseQueryBuilder."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Raw Supabase AsyncClient mock (before adapter wrapping)."""
        client = MagicMock()
        # .table() returns a PostgREST query builder mock
        mock_query = MagicMock()
        # Make chainable methods return mock_query itself
        for method in ("select", "insert", "update", "delete", "upsert",
                       "eq", "range", "order", "limit", "maybe_single"):
            getattr(mock_query, method).return_value = mock_query
        # execute returns an async result
        mock_query.execute = AsyncMock(return_value=MagicMock(data=[{"id": "abc"}]))
        client.table.return_value = mock_query
        return client, mock_query

    @pytest.fixture
    def adapter(self, mock_supabase_client):
        from infrastructure.persistence.supabase_adapter import SupabaseAdapter
        client, _ = mock_supabase_client
        return SupabaseAdapter(client)

    def test_table_returns_query_builder(self, adapter, mock_supabase_client):
        from infrastructure.persistence.supabase_adapter import SupabaseQueryBuilder
        qb = adapter.table("users")
        assert isinstance(qb, SupabaseQueryBuilder)

    def test_table_delegates_to_client(self, adapter, mock_supabase_client):
        client, _ = mock_supabase_client
        adapter.table("users")
        client.table.assert_called_once_with("users")

    @pytest.mark.asyncio
    async def test_select_eq_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        result = await adapter.table("users").select("*").eq("id", "abc").execute()
        assert isinstance(result, QueryResult)
        assert result.data == [{"id": "abc"}]
        mock_query.select.assert_called_once_with("*")
        mock_query.eq.assert_called_once_with("id", "abc")

    @pytest.mark.asyncio
    async def test_insert_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        result = await adapter.table("users").insert({"name": "Alice"}).execute()
        assert isinstance(result, QueryResult)
        mock_query.insert.assert_called_once_with({"name": "Alice"})

    @pytest.mark.asyncio
    async def test_update_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        result = await adapter.table("users").update({"name": "Bob"}).eq("id", "1").execute()
        assert isinstance(result, QueryResult)
        mock_query.update.assert_called_once_with({"name": "Bob"})

    @pytest.mark.asyncio
    async def test_delete_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        result = await adapter.table("users").delete().eq("id", "1").execute()
        assert isinstance(result, QueryResult)
        mock_query.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        await adapter.table("users").select("*").order("created_at", desc=True).execute()
        mock_query.order.assert_called_once_with("created_at", desc=True)

    @pytest.mark.asyncio
    async def test_limit_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        await adapter.table("users").select("*").limit(10).execute()
        mock_query.limit.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_maybe_single_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        await adapter.table("users").select("*").eq("id", "1").maybe_single().execute()
        mock_query.maybe_single.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        await adapter.table("users").upsert({"id": "1", "name": "Alice"}, on_conflict="id").execute()
        mock_query.upsert.assert_called_once_with({"id": "1", "name": "Alice"}, on_conflict="id")

    @pytest.mark.asyncio
    async def test_range_execute(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        await adapter.table("users").select("*").range(0, 9).execute()
        mock_query.range.assert_called_once_with(0, 9)

    @pytest.mark.asyncio
    async def test_execute_returns_none_data_when_result_is_none(self, adapter, mock_supabase_client):
        """When maybe_single() finds no rows, execute() returns None — adapter must handle it."""
        _, mock_query = mock_supabase_client
        mock_query.execute = AsyncMock(return_value=None)
        result = await adapter.table("users").select("*").maybe_single().execute()
        assert isinstance(result, QueryResult)
        assert result.data is None

    @pytest.mark.asyncio
    async def test_api_error_translated_to_database_error(self, adapter, mock_supabase_client):
        """Verify postgrest APIError is caught and re-raised as DatabaseError."""
        from postgrest.exceptions import APIError
        _, mock_query = mock_supabase_client
        mock_query.execute = AsyncMock(
            side_effect=APIError({"message": "not found", "code": "404", "details": "", "hint": ""})
        )
        with pytest.raises(DatabaseError) as exc_info:
            await adapter.table("users").select("*").execute()
        assert "not found" in str(exc_info.value)

    def test_is_database_client_instance(self, adapter):
        assert isinstance(adapter, DatabaseClient)

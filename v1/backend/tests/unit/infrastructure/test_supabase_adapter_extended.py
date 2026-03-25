"""Tests for new methods on SupabaseAdapter: in_() and rpc().

Verifies:
  - in_() filter delegates to PostgREST's in_()
  - in_() is chainable with eq()
  - rpc() calls supabase client.rpc()
  - rpc() wraps result in QueryResult
  - rpc() translates errors to DatabaseError
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from domain.interfaces.database import DatabaseError, QueryResult


class TestSupabaseInFilter:

    @pytest.fixture
    def mock_supabase_client(self):
        client = MagicMock()
        mock_query = MagicMock()
        for method in ("select", "insert", "update", "delete", "upsert",
                       "eq", "in_", "range", "order", "limit", "maybe_single"):
            getattr(mock_query, method).return_value = mock_query
        mock_query.execute = AsyncMock(return_value=MagicMock(data=[{"id": "1"}]))
        client.table.return_value = mock_query
        return client, mock_query

    @pytest.fixture
    def adapter(self, mock_supabase_client):
        from infrastructure.persistence.supabase_adapter import SupabaseAdapter
        client, _ = mock_supabase_client
        return SupabaseAdapter(client)

    @pytest.mark.asyncio
    async def test_in_filter_delegates_to_postgrest(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        await adapter.table("users").select().in_("status", ["active", "pending"]).execute()
        mock_query.in_.assert_called_once_with("status", ["active", "pending"])

    @pytest.mark.asyncio
    async def test_in_filter_chainable(self, adapter, mock_supabase_client):
        _, mock_query = mock_supabase_client
        result = await (
            adapter.table("users")
            .select()
            .eq("org", "acme")
            .in_("role", ["admin", "user"])
            .execute()
        )
        assert isinstance(result, QueryResult)
        mock_query.eq.assert_called_once_with("org", "acme")
        mock_query.in_.assert_called_once_with("role", ["admin", "user"])


class TestSupabaseRpc:

    @pytest.fixture
    def mock_supabase_client(self):
        client = MagicMock()
        rpc_chain = MagicMock()
        rpc_chain.execute = AsyncMock(return_value=MagicMock(data=[{"similarity": 0.9}]))
        client.rpc.return_value = rpc_chain
        return client

    @pytest.fixture
    def adapter(self, mock_supabase_client):
        from infrastructure.persistence.supabase_adapter import SupabaseAdapter
        return SupabaseAdapter(mock_supabase_client)

    @pytest.mark.asyncio
    async def test_rpc_calls_supabase_rpc(self, adapter, mock_supabase_client):
        await adapter.rpc("match_embeddings", {"query": [0.1], "count": 5})
        mock_supabase_client.rpc.assert_called_once_with(
            "match_embeddings", {"query": [0.1], "count": 5}
        )

    @pytest.mark.asyncio
    async def test_rpc_returns_query_result(self, adapter):
        result = await adapter.rpc("my_func", {"a": 1})
        assert isinstance(result, QueryResult)
        assert result.data == [{"similarity": 0.9}]

    @pytest.mark.asyncio
    async def test_rpc_error_raises_database_error(self, mock_supabase_client):
        from postgrest.exceptions import APIError
        from infrastructure.persistence.supabase_adapter import SupabaseAdapter

        rpc_chain = MagicMock()
        rpc_chain.execute = AsyncMock(
            side_effect=APIError({"message": "rpc failed", "code": "500", "details": "", "hint": ""})
        )
        mock_supabase_client.rpc.return_value = rpc_chain

        adapter = SupabaseAdapter(mock_supabase_client)
        with pytest.raises(DatabaseError) as exc_info:
            await adapter.rpc("bad_func", {})
        assert "rpc failed" in str(exc_info.value)

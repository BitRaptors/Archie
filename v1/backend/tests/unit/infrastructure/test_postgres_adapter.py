"""Tests for PostgresAdapter and PostgresQueryBuilder SQL generation.

Verifies:
  - Correct SQL generation for all QueryBuilder operations
  - Proper $1, $2, ... positional parameter handling
  - Type normalization (UUID → str, datetime → ISO string)
  - Error translation (asyncpg → DatabaseError)
  - maybe_single() behavior
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domain.interfaces.database import DatabaseClient, DatabaseError, QueryResult


# ── Helpers ─────────────────────────────────────────────────────────────────


class FakeRecord(dict):
    """Mimics asyncpg.Record (behaves like a dict)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def items(self):
        return super().items()


def _make_pool(rows=None, side_effect=None):
    """Build a mock asyncpg.Pool that returns *rows* from fetch()."""
    if rows is None:
        rows = []
    conn = AsyncMock()
    if side_effect:
        conn.fetch = AsyncMock(side_effect=side_effect)
    else:
        conn.fetch = AsyncMock(return_value=[FakeRecord(r) for r in rows])

    pool = MagicMock()
    # pool.acquire() returns an async context manager
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = ctx

    return pool, conn


# ── SQL generation tests ───────────────────────────────────────────────────


class TestPostgresQueryBuilderSQL:
    """Verify SQL strings produced by the query builder."""

    def _builder(self, pool=None, table="test_table"):
        from infrastructure.persistence.postgres_adapter import PostgresQueryBuilder

        return PostgresQueryBuilder(pool or MagicMock(), table)

    def test_select_star(self):
        qb = self._builder()
        qb.select()
        sql, params = qb._build_sql()
        assert sql == "SELECT * FROM test_table"
        assert params == []

    def test_select_columns(self):
        qb = self._builder()
        qb.select("id, name")
        sql, params = qb._build_sql()
        assert sql == "SELECT id, name FROM test_table"

    def test_select_with_eq(self):
        qb = self._builder()
        qb.select().eq("col", "val")
        sql, params = qb._build_sql()
        assert sql == "SELECT * FROM test_table WHERE col = $1"
        assert params == ["val"]

    def test_select_with_multiple_eq(self):
        qb = self._builder()
        qb.select().eq("col1", "a").eq("col2", "b")
        sql, params = qb._build_sql()
        assert "col1 = $1" in sql
        assert "col2 = $2" in sql
        assert "AND" in sql
        assert params == ["a", "b"]

    def test_select_with_in(self):
        qb = self._builder()
        qb.select().in_("col", [1, 2, 3])
        sql, params = qb._build_sql()
        assert "col = ANY($1)" in sql
        assert params == [[1, 2, 3]]

    def test_select_with_eq_and_in(self):
        qb = self._builder()
        qb.select().eq("a", 1).in_("b", [2, 3])
        sql, params = qb._build_sql()
        assert "a = $1" in sql
        assert "b = ANY($2)" in sql
        assert params == [1, [2, 3]]

    def test_select_with_order_asc(self):
        qb = self._builder()
        qb.select().order("col")
        sql, _ = qb._build_sql()
        assert "ORDER BY col ASC" in sql

    def test_select_with_order_desc(self):
        qb = self._builder()
        qb.select().order("col", desc=True)
        sql, _ = qb._build_sql()
        assert "ORDER BY col DESC" in sql

    def test_select_with_multiple_order(self):
        qb = self._builder()
        qb.select().order("col1").order("col2", desc=True)
        sql, _ = qb._build_sql()
        assert "ORDER BY col1 ASC, col2 DESC" in sql

    def test_select_with_limit(self):
        qb = self._builder()
        qb.select().limit(10)
        sql, _ = qb._build_sql()
        assert "LIMIT 10" in sql

    def test_select_with_range(self):
        qb = self._builder()
        qb.select().range(5, 14)
        sql, _ = qb._build_sql()
        assert "LIMIT 10 OFFSET 5" in sql

    def test_insert_single_row(self):
        qb = self._builder()
        qb.insert({"name": "Alice", "age": 30})
        sql, params = qb._build_sql()
        assert sql.startswith("INSERT INTO test_table")
        assert "RETURNING *" in sql
        assert "Alice" in params
        assert 30 in params

    def test_insert_multiple_rows(self):
        qb = self._builder()
        qb.insert([{"name": "Alice"}, {"name": "Bob"}])
        sql, params = qb._build_sql()
        assert sql.count("$") == 2  # $1 and $2
        assert params == ["Alice", "Bob"]

    def test_update_with_eq(self):
        qb = self._builder()
        qb.update({"name": "Bob"}).eq("id", "123")
        sql, params = qb._build_sql()
        assert "UPDATE test_table SET name = $1" in sql
        assert "WHERE id = $2" in sql
        assert "RETURNING *" in sql
        assert params == ["Bob", "123"]

    def test_delete_with_eq(self):
        qb = self._builder()
        qb.delete().eq("id", "123")
        sql, params = qb._build_sql()
        assert "DELETE FROM test_table" in sql
        assert "WHERE id = $1" in sql
        assert "RETURNING *" in sql
        assert params == ["123"]

    def test_delete_with_multiple_filters(self):
        qb = self._builder()
        qb.delete().eq("a", 1).in_("b", [2, 3])
        sql, params = qb._build_sql()
        assert "a = $1" in sql
        assert "b = ANY($2)" in sql
        assert params == [1, [2, 3]]

    def test_upsert_with_on_conflict(self):
        qb = self._builder()
        qb.upsert({"id": "1", "name": "Alice"}, on_conflict="id")
        sql, params = qb._build_sql()
        assert "INSERT INTO test_table" in sql
        assert "ON CONFLICT (id) DO UPDATE SET" in sql
        assert "name = EXCLUDED.name" in sql
        assert "RETURNING *" in sql

    def test_upsert_without_on_conflict(self):
        qb = self._builder()
        qb.upsert({"id": "1", "name": "Alice"})
        sql, _ = qb._build_sql()
        assert "ON CONFLICT DO NOTHING" in sql

    def test_no_operation_raises(self):
        qb = self._builder()
        with pytest.raises(DatabaseError):
            qb._build_sql()


# ── Execution tests ────────────────────────────────────────────────────────


class TestPostgresQueryBuilderExecution:

    @pytest.mark.asyncio
    async def test_select_maybe_single_returns_dict(self):
        from infrastructure.persistence.postgres_adapter import PostgresQueryBuilder

        pool, _ = _make_pool([{"id": "abc", "name": "Alice"}])
        qb = PostgresQueryBuilder(pool, "users")
        result = await qb.select().eq("id", "abc").maybe_single().execute()
        assert isinstance(result, QueryResult)
        assert result.data == {"id": "abc", "name": "Alice"}

    @pytest.mark.asyncio
    async def test_select_maybe_single_returns_none(self):
        from infrastructure.persistence.postgres_adapter import PostgresQueryBuilder

        pool, _ = _make_pool([])
        qb = PostgresQueryBuilder(pool, "users")
        result = await qb.select().eq("id", "missing").maybe_single().execute()
        assert result.data is None

    @pytest.mark.asyncio
    async def test_select_returns_list(self):
        from infrastructure.persistence.postgres_adapter import PostgresQueryBuilder

        pool, _ = _make_pool([{"id": "1"}, {"id": "2"}])
        qb = PostgresQueryBuilder(pool, "users")
        result = await qb.select().execute()
        assert isinstance(result.data, list)
        assert len(result.data) == 2

    @pytest.mark.asyncio
    async def test_uuid_returned_as_string(self):
        from infrastructure.persistence.postgres_adapter import PostgresQueryBuilder

        test_uuid = uuid.uuid4()
        pool, _ = _make_pool([{"id": test_uuid}])
        qb = PostgresQueryBuilder(pool, "users")
        result = await qb.select().execute()
        assert isinstance(result.data[0]["id"], str)
        assert result.data[0]["id"] == str(test_uuid)

    @pytest.mark.asyncio
    async def test_datetime_returned_as_iso_string(self):
        from infrastructure.persistence.postgres_adapter import PostgresQueryBuilder

        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        pool, _ = _make_pool([{"created_at": dt}])
        qb = PostgresQueryBuilder(pool, "users")
        result = await qb.select().execute()
        assert isinstance(result.data[0]["created_at"], str)
        assert "2024-01-01" in result.data[0]["created_at"]

    @pytest.mark.asyncio
    async def test_jsonb_returned_as_dict(self):
        from infrastructure.persistence.postgres_adapter import PostgresQueryBuilder

        pool, _ = _make_pool([{"data": {"key": "value"}}])
        qb = PostgresQueryBuilder(pool, "users")
        result = await qb.select().execute()
        assert isinstance(result.data[0]["data"], dict)
        assert result.data[0]["data"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_database_error_on_failure(self):
        import asyncpg
        from infrastructure.persistence.postgres_adapter import PostgresQueryBuilder

        pool, _ = _make_pool(side_effect=asyncpg.PostgresError("test error"))
        qb = PostgresQueryBuilder(pool, "users")
        with pytest.raises(DatabaseError):
            await qb.select().execute()


# ── PostgresAdapter tests ──────────────────────────────────────────────────


class TestPostgresAdapter:

    def test_is_database_client(self):
        from infrastructure.persistence.postgres_adapter import PostgresAdapter

        adapter = PostgresAdapter(MagicMock())
        assert isinstance(adapter, DatabaseClient)

    def test_table_returns_query_builder(self):
        from infrastructure.persistence.postgres_adapter import PostgresAdapter, PostgresQueryBuilder

        adapter = PostgresAdapter(MagicMock())
        qb = adapter.table("users")
        assert isinstance(qb, PostgresQueryBuilder)

    @pytest.mark.asyncio
    async def test_rpc_call(self):
        from infrastructure.persistence.postgres_adapter import PostgresAdapter

        pool, conn = _make_pool([{"id": "1", "similarity": 0.95}])
        adapter = PostgresAdapter(pool)
        result = await adapter.rpc("match_embeddings", {"param1": "val1", "param2": "val2"})
        assert isinstance(result, QueryResult)
        assert result.data == [{"id": "1", "similarity": 0.95}]
        # Verify the SQL contains named params
        call_sql = conn.fetch.call_args[0][0]
        assert "match_embeddings" in call_sql
        assert "param1 := $1" in call_sql
        assert "param2 := $2" in call_sql

    @pytest.mark.asyncio
    async def test_rpc_returns_query_result(self):
        from infrastructure.persistence.postgres_adapter import PostgresAdapter

        pool, _ = _make_pool([{"result": 42}])
        adapter = PostgresAdapter(pool)
        result = await adapter.rpc("my_func", {"x": 1})
        assert isinstance(result, QueryResult)
        assert result.data[0]["result"] == 42

    @pytest.mark.asyncio
    async def test_rpc_error_raises_database_error(self):
        import asyncpg
        from infrastructure.persistence.postgres_adapter import PostgresAdapter

        pool, _ = _make_pool(side_effect=asyncpg.PostgresError("rpc failed"))
        adapter = PostgresAdapter(pool)
        with pytest.raises(DatabaseError):
            await adapter.rpc("bad_func", {})

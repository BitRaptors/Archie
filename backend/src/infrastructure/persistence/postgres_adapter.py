"""asyncpg-based adapter for the DatabaseClient interface.

Drop-in alternative to SupabaseAdapter for local/self-hosted PostgreSQL.
Builds SQL dynamically from chained QueryBuilder calls and executes
via an asyncpg connection pool.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any

import asyncpg

from domain.interfaces.database import (
    DatabaseClient,
    DatabaseError,
    QueryBuilder,
    QueryResult,
)


def _normalise_row(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a plain dict with JSON-friendly types."""
    out: dict[str, Any] = {}
    for key, value in dict(row).items():
        if isinstance(value, _uuid.UUID):
            out[key] = str(value)
        elif isinstance(value, datetime):
            # Ensure timezone-aware datetimes are returned as ISO strings
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


class PostgresQueryBuilder(QueryBuilder):
    """Builds SQL from chained method calls and executes via asyncpg pool."""

    def __init__(self, pool: asyncpg.Pool, table_name: str) -> None:
        self._pool = pool
        self._table = table_name

        # Operation state
        self._operation: str | None = None  # select, insert, update, delete, upsert
        self._columns: str = "*"
        self._data: dict | list[dict] | None = None
        self._filters: list[tuple[str, str, Any]] = []  # (column, op, value)
        self._order_clauses: list[tuple[str, bool]] = []  # (column, desc)
        self._limit_val: int | None = None
        self._range_start: int | None = None
        self._range_end: int | None = None
        self._maybe_single_flag: bool = False
        self._on_conflict: str = ""

    # -- CRUD ------------------------------------------------------------------

    def select(self, columns: str = "*") -> PostgresQueryBuilder:
        self._operation = "select"
        self._columns = columns
        return self

    def insert(self, data: dict | list[dict]) -> PostgresQueryBuilder:
        self._operation = "insert"
        self._data = data
        return self

    def update(self, data: dict) -> PostgresQueryBuilder:
        self._operation = "update"
        self._data = data
        return self

    def delete(self) -> PostgresQueryBuilder:
        self._operation = "delete"
        return self

    def upsert(self, data: dict | list[dict], *, on_conflict: str = "") -> PostgresQueryBuilder:
        self._operation = "upsert"
        self._data = data
        self._on_conflict = on_conflict
        return self

    # -- Filtering / shaping ---------------------------------------------------

    def eq(self, column: str, value: Any) -> PostgresQueryBuilder:
        self._filters.append((column, "eq", value))
        return self

    def in_(self, column: str, values: list[Any]) -> PostgresQueryBuilder:
        self._filters.append((column, "in", values))
        return self

    def range(self, start: int, end: int) -> PostgresQueryBuilder:
        self._range_start = start
        self._range_end = end
        return self

    def order(self, column: str, *, desc: bool = False) -> PostgresQueryBuilder:
        self._order_clauses.append((column, desc))
        return self

    def limit(self, count: int) -> PostgresQueryBuilder:
        self._limit_val = count
        return self

    def maybe_single(self) -> PostgresQueryBuilder:
        self._maybe_single_flag = True
        return self

    # -- Execution -------------------------------------------------------------

    async def execute(self) -> QueryResult:
        try:
            sql, params = self._build_sql()
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
            data = [_normalise_row(r) for r in rows]

            if self._maybe_single_flag:
                return QueryResult(data=data[0] if data else None)
            return QueryResult(data=data)
        except asyncpg.PostgresError as e:
            raise DatabaseError(
                code=getattr(e, "sqlstate", "") or "",
                message=str(e),
            ) from e

    # -- SQL building ----------------------------------------------------------

    def _build_sql(self) -> tuple[str, list[Any]]:
        """Build a (sql, params) tuple with $1, $2, ... positional placeholders."""
        params: list[Any] = []
        idx = 1  # asyncpg uses $1-based indexing

        if self._operation == "select":
            sql = f"SELECT {self._columns} FROM {self._table}"
            sql, idx, params = self._append_where(sql, idx, params)
            sql = self._append_order(sql)
            sql = self._append_limit_offset(sql)
            return sql, params

        elif self._operation == "insert":
            return self._build_insert(params)

        elif self._operation == "update":
            return self._build_update(params)

        elif self._operation == "delete":
            sql = f"DELETE FROM {self._table}"
            sql, idx, params = self._append_where(sql, idx, params)
            sql += " RETURNING *"
            return sql, params

        elif self._operation == "upsert":
            return self._build_upsert(params)

        else:
            raise DatabaseError(message=f"No operation specified on query for table {self._table}")

    def _append_where(self, sql: str, idx: int, params: list[Any]) -> tuple[str, int, list[Any]]:
        if not self._filters:
            return sql, idx, params

        clauses: list[str] = []
        for column, op, value in self._filters:
            if op == "eq":
                clauses.append(f"{column} = ${idx}")
                params.append(value)
                idx += 1
            elif op == "in":
                clauses.append(f"{column} = ANY(${idx})")
                params.append(value)
                idx += 1
        sql += " WHERE " + " AND ".join(clauses)
        return sql, idx, params

    def _append_order(self, sql: str) -> str:
        if self._order_clauses:
            parts = [
                f"{col} {'DESC' if desc else 'ASC'}"
                for col, desc in self._order_clauses
            ]
            sql += " ORDER BY " + ", ".join(parts)
        return sql

    def _append_limit_offset(self, sql: str) -> str:
        if self._range_start is not None and self._range_end is not None:
            limit = self._range_end - self._range_start + 1
            sql += f" LIMIT {limit} OFFSET {self._range_start}"
        elif self._limit_val is not None:
            sql += f" LIMIT {self._limit_val}"
        return sql

    def _build_insert(self, params: list[Any]) -> tuple[str, list[Any]]:
        rows = self._data if isinstance(self._data, list) else [self._data]
        columns = list(rows[0].keys())
        col_str = ", ".join(columns)

        value_groups: list[str] = []
        idx = 1
        for row in rows:
            placeholders = []
            for col in columns:
                placeholders.append(f"${idx}")
                params.append(row[col])
                idx += 1
            value_groups.append(f"({', '.join(placeholders)})")

        sql = f"INSERT INTO {self._table} ({col_str}) VALUES {', '.join(value_groups)} RETURNING *"
        return sql, params

    def _build_update(self, params: list[Any]) -> tuple[str, list[Any]]:
        assert isinstance(self._data, dict)
        set_parts: list[str] = []
        idx = 1
        for col, val in self._data.items():
            set_parts.append(f"{col} = ${idx}")
            params.append(val)
            idx += 1

        sql = f"UPDATE {self._table} SET {', '.join(set_parts)}"
        sql, idx, params = self._append_where(sql, idx, params)
        sql += " RETURNING *"
        return sql, params

    def _build_upsert(self, params: list[Any]) -> tuple[str, list[Any]]:
        rows = self._data if isinstance(self._data, list) else [self._data]
        columns = list(rows[0].keys())
        col_str = ", ".join(columns)

        value_groups: list[str] = []
        idx = 1
        for row in rows:
            placeholders = []
            for col in columns:
                placeholders.append(f"${idx}")
                params.append(row[col])
                idx += 1
            value_groups.append(f"({', '.join(placeholders)})")

        sql = f"INSERT INTO {self._table} ({col_str}) VALUES {', '.join(value_groups)}"

        if self._on_conflict:
            update_cols = [c for c in columns if c != self._on_conflict]
            if update_cols:
                set_parts = [f"{c} = EXCLUDED.{c}" for c in update_cols]
                sql += f" ON CONFLICT ({self._on_conflict}) DO UPDATE SET {', '.join(set_parts)}"
            else:
                sql += f" ON CONFLICT ({self._on_conflict}) DO NOTHING"
        else:
            sql += " ON CONFLICT DO NOTHING"

        sql += " RETURNING *"
        return sql, params


class PostgresAdapter(DatabaseClient):
    """Adapts an ``asyncpg.Pool`` to our :class:`DatabaseClient` ABC."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def table(self, name: str) -> PostgresQueryBuilder:
        return PostgresQueryBuilder(self._pool, name)

    async def rpc(self, function_name: str, params: dict[str, Any]) -> QueryResult:
        """Call a stored PostgreSQL function using named parameters."""
        try:
            # Build: SELECT * FROM function_name(key1 := $1, key2 := $2, ...)
            keys = list(params.keys())
            placeholders = [f"{k} := ${i+1}" for i, k in enumerate(keys)]
            sql = f"SELECT * FROM {function_name}({', '.join(placeholders)})"
            values = [params[k] for k in keys]

            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *values)
            return QueryResult(data=[_normalise_row(r) for r in rows])
        except asyncpg.PostgresError as e:
            raise DatabaseError(
                code=getattr(e, "sqlstate", "") or "",
                message=str(e),
            ) from e

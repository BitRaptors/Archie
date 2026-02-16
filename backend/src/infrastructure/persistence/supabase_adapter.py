"""Supabase adapter for the DatabaseClient interface.

Wraps the Supabase PostgREST client so that repositories never import
anything from ``supabase`` or ``postgrest`` directly.
"""
from __future__ import annotations

from typing import Any

from postgrest.exceptions import APIError

from domain.interfaces.database import (
    DatabaseClient,
    DatabaseError,
    QueryBuilder,
    QueryResult,
)


class SupabaseQueryBuilder(QueryBuilder):
    """Thin wrapper around Supabase's PostgREST query builder."""

    def __init__(self, query: Any) -> None:
        self._query = query

    # -- CRUD ------------------------------------------------------------------

    def select(self, columns: str = "*") -> SupabaseQueryBuilder:
        self._query = self._query.select(columns)
        return self

    def insert(self, data: dict | list[dict]) -> SupabaseQueryBuilder:
        self._query = self._query.insert(data)
        return self

    def update(self, data: dict) -> SupabaseQueryBuilder:
        self._query = self._query.update(data)
        return self

    def delete(self) -> SupabaseQueryBuilder:
        self._query = self._query.delete()
        return self

    def upsert(self, data: dict | list[dict], *, on_conflict: str = "") -> SupabaseQueryBuilder:
        kwargs: dict[str, Any] = {}
        if on_conflict:
            kwargs["on_conflict"] = on_conflict
        self._query = self._query.upsert(data, **kwargs)
        return self

    # -- Filtering / shaping ---------------------------------------------------

    def eq(self, column: str, value: Any) -> SupabaseQueryBuilder:
        self._query = self._query.eq(column, value)
        return self

    def range(self, start: int, end: int) -> SupabaseQueryBuilder:
        self._query = self._query.range(start, end)
        return self

    def order(self, column: str, *, desc: bool = False) -> SupabaseQueryBuilder:
        self._query = self._query.order(column, desc=desc)
        return self

    def limit(self, count: int) -> SupabaseQueryBuilder:
        self._query = self._query.limit(count)
        return self

    def maybe_single(self) -> SupabaseQueryBuilder:
        self._query = self._query.maybe_single()
        return self

    # -- Execution -------------------------------------------------------------

    async def execute(self) -> QueryResult:
        try:
            result = await self._query.execute()
            # maybe_single() can make execute() return None when no rows match
            if result is None:
                return QueryResult(data=None)
            return QueryResult(data=result.data)
        except APIError as e:
            raise DatabaseError(
                code=getattr(e, "code", "") or "",
                message=str(e),
            ) from e


class SupabaseAdapter(DatabaseClient):
    """Adapts a ``supabase.AsyncClient`` to our :class:`DatabaseClient` ABC."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def table(self, name: str) -> SupabaseQueryBuilder:
        return SupabaseQueryBuilder(self._client.table(name))

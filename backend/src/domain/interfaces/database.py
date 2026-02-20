"""Database abstraction layer.

Defines the interfaces that repositories depend on. Concrete implementations
(Supabase, asyncpg, SQLAlchemy, etc.) live in infrastructure/persistence/.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class QueryResult:
    """DB-agnostic query result."""

    data: Any  # list[dict] | dict | None


class DatabaseError(Exception):
    """DB-agnostic database error.

    Mirrors the information available from PostgREST / Supabase errors
    so that repositories can handle errors without importing DB-specific
    exception classes.
    """

    def __init__(self, code: str = "", message: str = ""):
        self.code = code
        super().__init__(message)


class QueryBuilder(ABC):
    """Chainable query builder.

    Mirrors the subset of PostgREST operations actually used across
    all repositories.  Implementations wrap a concrete DB client.
    """

    @abstractmethod
    def select(self, columns: str = "*") -> QueryBuilder: ...

    @abstractmethod
    def insert(self, data: dict | list[dict]) -> QueryBuilder: ...

    @abstractmethod
    def update(self, data: dict) -> QueryBuilder: ...

    @abstractmethod
    def delete(self) -> QueryBuilder: ...

    @abstractmethod
    def upsert(self, data: dict | list[dict], *, on_conflict: str = "") -> QueryBuilder: ...

    @abstractmethod
    def eq(self, column: str, value: Any) -> QueryBuilder: ...

    @abstractmethod
    def neq(self, column: str, value: Any) -> QueryBuilder: ...

    @abstractmethod
    def in_(self, column: str, values: list[Any]) -> QueryBuilder: ...

    @abstractmethod
    def range(self, start: int, end: int) -> QueryBuilder: ...

    @abstractmethod
    def order(self, column: str, *, desc: bool = False) -> QueryBuilder: ...

    @abstractmethod
    def limit(self, count: int) -> QueryBuilder: ...

    @abstractmethod
    def maybe_single(self) -> QueryBuilder: ...

    @abstractmethod
    async def execute(self) -> QueryResult: ...


class DatabaseClient(ABC):
    """DB-agnostic client.

    Repositories depend on this interface, never on a concrete DB SDK.
    To add a new database backend, implement ``DatabaseClient`` and
    ``QueryBuilder`` for that SDK.
    """

    @abstractmethod
    def table(self, name: str) -> QueryBuilder: ...

    async def rpc(self, function_name: str, params: dict[str, Any]) -> QueryResult:
        """Call a stored database function. Override in adapters that support it."""
        raise NotImplementedError(f"rpc() not supported by this database backend")

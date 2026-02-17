"""Backend-agnostic database factory.

Creates a ``DatabaseClient`` (either ``PostgresAdapter`` or ``SupabaseAdapter``)
based on the ``DB_BACKEND`` setting.  The instance is cached as a singleton so
every caller shares the same underlying connection pool.
"""
from __future__ import annotations

from domain.interfaces.database import DatabaseClient
from config.settings import get_settings

_cached_db: DatabaseClient | None = None
_cached_pool = None  # asyncpg.Pool or Supabase AsyncClient


async def create_db() -> DatabaseClient:
    """Create a DatabaseClient based on settings. Cached as singleton."""
    global _cached_db, _cached_pool
    if _cached_db is not None:
        return _cached_db

    settings = get_settings()

    if settings.db_backend == "postgres":
        import asyncpg
        from infrastructure.persistence.postgres_adapter import PostgresAdapter

        pool = await asyncpg.create_pool(settings.database_url)
        # Register pgvector codec so vector columns come back as lists
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            # Register text codec for vector type so we don't need pgvector Python lib
            await conn.set_type_codec(
                "vector",
                encoder=lambda v: v,
                decoder=lambda v: [float(x) for x in v.strip("[]").split(",")],
                schema="public",
                format="text",
            )
        _cached_pool = pool
        _cached_db = PostgresAdapter(pool)
    else:
        from supabase import create_async_client
        from infrastructure.persistence.supabase_adapter import SupabaseAdapter

        client = await create_async_client(settings.supabase_url, settings.supabase_key)
        _cached_pool = client
        _cached_db = SupabaseAdapter(client)

    return _cached_db


async def shutdown_db() -> None:
    """Close the underlying connection pool."""
    global _cached_db, _cached_pool
    if _cached_pool is not None and hasattr(_cached_pool, "close"):
        await _cached_pool.close()
    _cached_db = None
    _cached_pool = None

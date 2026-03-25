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
        import json
        import asyncpg
        from infrastructure.persistence.postgres_adapter import PostgresAdapter

        async def _init_connection(conn: asyncpg.Connection) -> None:
            """Register custom type codecs on every new connection."""
            # JSONB/JSON → Python objects (asyncpg returns raw strings by default)
            await conn.set_type_codec(
                "jsonb",
                encoder=json.dumps,
                decoder=json.loads,
                schema="pg_catalog",
                format="text",
            )
            await conn.set_type_codec(
                "json",
                encoder=json.dumps,
                decoder=json.loads,
                schema="pg_catalog",
                format="text",
            )
            # pgvector → Python lists (avoids requiring the pgvector Python lib)
            await conn.set_type_codec(
                "vector",
                encoder=lambda v: v if isinstance(v, str) else "[" + ",".join(str(x) for x in v) + "]",
                decoder=lambda v: [float(x) for x in v.strip("[]").split(",")],
                schema="public",
                format="text",
            )

        pool = await asyncpg.create_pool(settings.database_url, init=_init_connection)
        # Ensure vector extension exists
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
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

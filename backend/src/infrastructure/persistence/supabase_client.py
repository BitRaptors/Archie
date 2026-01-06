"""Supabase client wrapper."""
from supabase import create_client, Client
from supabase.client import ClientOptions
from config.settings import get_settings


def get_supabase_client() -> Client:
    """Get Supabase client instance (Sync)."""
    settings = get_settings()
    return create_client(
        settings.supabase_url, 
        settings.supabase_key,
        options=ClientOptions(
            postgrest_client_timeout=10,
            storage_client_timeout=10,
        )
    )


async def get_supabase_client_async():
    """Get Supabase client instance (Async)."""
    from supabase import create_async_client
    settings = get_settings()
    return await create_async_client(
        settings.supabase_url, 
        settings.supabase_key,
        options=ClientOptions(
            postgrest_client_timeout=10,
            storage_client_timeout=10,
        )
    )

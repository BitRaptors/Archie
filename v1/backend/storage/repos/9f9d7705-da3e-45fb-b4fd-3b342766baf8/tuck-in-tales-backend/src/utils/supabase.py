from supabase import create_client, Client
from src.config import settings

# Ensure settings are loaded for the SERVICE KEY
if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
    raise ValueError("Supabase URL and Service Key must be set in environment variables or .env file")

# Initialize SYNC client using the SERVICE KEY
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

def get_supabase_client() -> Client:
    """Dependency injector for Supabase sync client."""
    return supabase 
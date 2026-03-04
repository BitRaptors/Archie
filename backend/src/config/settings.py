from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from functools import lru_cache
from dotenv import load_dotenv

# Load from .env.local
load_dotenv(".env.local")


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Application
    app_name: str = Field(default="Repository Analysis API")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Database backend: "supabase" or "postgres"
    db_backend: str = Field(default="supabase")
    database_url: str | None = Field(default=None)  # Required when db_backend=postgres

    # Supabase (only required when db_backend=supabase)
    supabase_url: str | None = Field(default=None)
    supabase_key: str | None = Field(default=None)
    supabase_jwt_secret: str | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_db_backend(self) -> "Settings":
        def _is_set(val: str | None) -> bool:
            return val is not None and val.strip() != ""

        if self.db_backend == "postgres":
            if not _is_set(self.database_url):
                raise ValueError("DATABASE_URL is required when DB_BACKEND=postgres")
        else:
            # supabase backend — only URL and key are needed to connect
            missing = []
            if not _is_set(self.supabase_url):
                missing.append("SUPABASE_URL")
            if not _is_set(self.supabase_key):
                missing.append("SUPABASE_KEY")
            if missing:
                raise ValueError(
                    f"When DB_BACKEND=supabase, these are required: {', '.join(missing)}"
                )
        return self

    # Redis (Sessions/Cache/Task Queue)
    redis_url: str = Field(default="redis://localhost:6379")

    # GitHub API
    github_token: str | None = Field(default=None)  # Optional, users provide their own

    # AI Providers
    anthropic_api_key: str = Field(...)  # Claude API
    default_ai_model: str = Field(default="claude-haiku-4-5-20251001")  # Fast model for intermediate phases
    synthesis_ai_model: str = Field(default="claude-haiku-4-5-20251001")  # Model for final synthesis (supports up to 64K output tokens)
    synthesis_max_tokens: int = Field(default=64000)  # Max output tokens — Haiku 4.5 & Sonnet 4.5 support 64K, Opus 4.6 supports 128K

    # Embedding Model
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")

    # Storage
    storage_path: str = Field(default="./storage")  # Local storage path
    temp_storage_path: str = Field(default="./temp")  # Temp storage path

    # Analysis
    analysis_timeout_seconds: int = Field(default=3600)  # 1 hour

    # File reading budget (0 = auto/dynamic based on repo size)
    file_reading_budget: int = Field(default=0)
    file_reading_per_file_max: int = Field(default=0)

    # Intent Layer
    intent_layer_max_depth: int = Field(default=99)
    intent_layer_min_files: int = Field(default=2)
    intent_layer_max_concurrent: int = Field(default=5)
    intent_layer_excluded_dirs: str = Field(default="")  # Comma-separated
    intent_layer_ai_model: str = Field(default="")       # Empty = use default_ai_model
    intent_layer_enable_ai_enrichment: bool = Field(default=True)
    intent_layer_enrichment_model: str = Field(default="")  # Empty = use default_ai_model
    intent_layer_generate_codebase_map: bool = Field(default=True)

    model_config = {
        "env_file": ".env.local",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


from pydantic_settings import BaseSettings
from pydantic import Field
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

    # Supabase (Database, Auth, Storage)
    supabase_url: str = Field(...)
    supabase_key: str = Field(...)
    supabase_jwt_secret: str = Field(...)  # For JWT validation

    # Redis (Sessions/Cache/Task Queue)
    redis_url: str = Field(default="redis://localhost:6379")

    # GitHub API
    github_token: str | None = Field(default=None)  # Optional, users provide their own

    # AI Providers
    anthropic_api_key: str = Field(...)  # Claude API
    default_ai_model: str = Field(default="claude-3-haiku-20240307")

    # Embedding Model
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")

    # Vector Database
    vector_db_type: str = Field(default="pgvector")  # "pgvector", "qdrant", "pinecone"
    qdrant_url: str | None = Field(default=None)
    qdrant_api_key: str | None = Field(default=None)
    pinecone_api_key: str | None = Field(default=None)
    pinecone_environment: str | None = Field(default=None)

    # Storage
    storage_type: str = Field(default="local")  # "local", "gcs", "s3"
    storage_path: str = Field(default="./storage")  # Local storage path
    temp_storage_path: str = Field(default="./temp")  # Temp storage path
    gcs_bucket_name: str | None = Field(default=None)
    s3_bucket_name: str | None = Field(default=None)
    aws_access_key_id: str | None = Field(default=None)
    aws_secret_access_key: str | None = Field(default=None)
    aws_region: str | None = Field(default=None)

    # Analysis
    max_analysis_workers: int = Field(default=4)
    analysis_timeout_seconds: int = Field(default=3600)  # 1 hour

    model_config = {
        "env_file": ".env.local",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


"""Tests for Settings validation: DB backend field requirements."""
import os
import pytest
from unittest.mock import patch
from pydantic import ValidationError

# Keys that load_dotenv may have injected into os.environ from .env.local.
# We remove them so each test fully controls its own values.
_KEYS_TO_CLEAR = [
    "DB_BACKEND", "DATABASE_URL",
    "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET",
    "ANTHROPIC_API_KEY",
]


class TestSettingsValidation:

    def _make_settings(self, **kwargs):
        """Construct Settings isolated from .env.local."""
        from config.settings import Settings

        defaults = {"anthropic_api_key": "test-key"}
        defaults.update(kwargs)

        # Build a clean environ snapshot with the interfering keys removed
        clean = {k: v for k, v in os.environ.items() if k not in _KEYS_TO_CLEAR}
        with patch.dict(os.environ, clean, clear=True):
            return Settings(_env_file=None, **defaults)

    def test_postgres_backend_requires_database_url(self):
        with pytest.raises((ValidationError, ValueError)):
            self._make_settings(db_backend="postgres")

    def test_postgres_backend_supabase_fields_optional(self):
        settings = self._make_settings(
            db_backend="postgres",
            database_url="postgresql://localhost/test",
        )
        assert settings.db_backend == "postgres"
        assert settings.database_url == "postgresql://localhost/test"

    def test_supabase_backend_requires_url_and_key(self):
        """SUPABASE_URL and SUPABASE_KEY are required; JWT_SECRET is optional."""
        with pytest.raises((ValidationError, ValueError)):
            self._make_settings(
                db_backend="supabase",
                supabase_url="https://example.supabase.co",
                # Missing SUPABASE_KEY
            )

    def test_supabase_backend_works_without_jwt_secret(self):
        """JWT secret is not used in code — should not be required."""
        settings = self._make_settings(
            db_backend="supabase",
            supabase_url="https://example.supabase.co",
            supabase_key="test-key",
            # No supabase_jwt_secret
        )
        assert settings.db_backend == "supabase"

    def test_supabase_backend_database_url_optional(self):
        settings = self._make_settings(
            db_backend="supabase",
            supabase_url="https://example.supabase.co",
            supabase_key="test-key",
        )
        assert settings.db_backend == "supabase"
        assert settings.database_url is None

    def test_default_backend_is_supabase(self):
        settings = self._make_settings(
            supabase_url="https://example.supabase.co",
            supabase_key="test-key",
        )
        assert settings.db_backend == "supabase"

"""Tests that validate the project setup and configuration are correct.

These tests ensure that a fresh clone + ./run will work
out of the box for new developers. They validate:
- Required files exist
- Docker compose config is correct
- Migration SQL creates all tables (prompts seeded separately via seed_prompts.py)
- Env examples contain all necessary keys
- prompts.json has version field and all required phases
"""
import json
import re
import stat
from pathlib import Path

import pytest

# Project root — two levels up from this test file
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = PROJECT_ROOT / "backend"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ===========================================================================
# 1. Required files exist
# ===========================================================================


class TestRequiredFilesExist:
    """All files needed for out-of-box setup must be present."""

    @pytest.mark.parametrize(
        "rel_path",
        [
            "run",
            "docker-compose.yml",
            "backend/.env.example",
            "frontend/.env.example",
            "backend/requirements.txt",
            "frontend/package.json",
            "backend/migrations/001_initial_setup.sql",
            "backend/prompts.json",
            "backend/scripts/seed_prompts.py",
            "README.md",
            "docs/ARCHITECTURE.md",
        ],
    )
    def test_file_exists(self, rel_path):
        path = PROJECT_ROOT / rel_path
        assert path.exists(), f"Required file missing: {rel_path}"

    def test_run_is_executable(self):
        run = PROJECT_ROOT / "run"
        assert run.exists()
        mode = run.stat().st_mode
        assert mode & stat.S_IXUSR, "run must be executable (chmod +x)"


# ===========================================================================
# 2. Docker Compose configuration
# ===========================================================================


class TestDockerCompose:
    """docker-compose.yml must define postgres (pgvector) + redis."""

    @pytest.fixture
    def compose_content(self):
        return _read(PROJECT_ROOT / "docker-compose.yml")

    def test_postgres_service_defined(self, compose_content):
        assert "postgres" in compose_content

    def test_uses_pgvector_image(self, compose_content):
        assert "pgvector" in compose_content, "Must use pgvector-enabled PostgreSQL image"

    def test_redis_service_defined(self, compose_content):
        assert "redis" in compose_content

    def test_postgres_port_exposed(self, compose_content):
        assert "5432" in compose_content

    def test_redis_port_exposed(self, compose_content):
        assert "6379" in compose_content

    def test_migration_mounted_as_init_script(self, compose_content):
        assert "docker-entrypoint-initdb.d" in compose_content, (
            "Migration SQL must be mounted into docker-entrypoint-initdb.d for auto-execution"
        )

    def test_migration_file_referenced(self, compose_content):
        assert "001_initial_setup.sql" in compose_content

    def test_persistent_volume_defined(self, compose_content):
        assert "pgdata" in compose_content, "PostgreSQL data should be persisted in a volume"


# ===========================================================================
# 3. Migration SQL completeness
# ===========================================================================


class TestMigrationSQL:
    """Migration must create all tables, extensions, and seed data."""

    @pytest.fixture
    def migration(self):
        return _read(BACKEND_DIR / "migrations" / "001_initial_setup.sql")

    # --- Extensions ---
    def test_enables_uuid_extension(self, migration):
        assert "uuid-ossp" in migration

    def test_enables_pgvector_extension(self, migration):
        assert "vector" in migration

    # --- Core tables ---
    @pytest.mark.parametrize(
        "table",
        [
            "users",
            "user_profiles",
            "repositories",
            "analyses",
            "analysis_prompts",
            "analysis_data",
            "analysis_events",
            "embeddings",
            "discovery_ignored_dirs",
            "library_capabilities",
        ],
    )
    def test_creates_table(self, migration, table):
        pattern = rf"CREATE\s+TABLE.*\b{table}\b"
        assert re.search(pattern, migration, re.IGNORECASE), f"Table '{table}' not created in migration"

    # --- No prompt seeding in migration (prompts.json is sole source) ---
    def test_no_prompt_seeding_in_migration(self, migration):
        # Migration should NOT contain INSERT INTO analysis_prompts with prompt data
        # (seed_prompts.py handles this now)
        assert "INSERT INTO analysis_prompts" not in migration, (
            "Prompt seeding was moved to seed_prompts.py — migration must not seed prompts"
        )

    # --- pgvector function ---
    def test_creates_match_embeddings_function(self, migration):
        assert "match_embeddings" in migration


# ===========================================================================
# 4. .env.example files
# ===========================================================================


class TestEnvExamples:
    """Env example files must contain all required keys."""

    @pytest.fixture
    def backend_env(self):
        return _read(BACKEND_DIR / ".env.example")

    @pytest.fixture
    def frontend_env(self):
        return _read(PROJECT_ROOT / "frontend" / ".env.example")

    # Backend required keys
    @pytest.mark.parametrize(
        "key",
        [
            "DB_BACKEND",
            "DATABASE_URL",
            "ANTHROPIC_API_KEY",
        ],
    )
    def test_backend_has_required_key(self, backend_env, key):
        assert key in backend_env, f"backend/.env.example must contain {key}"

    # Backend optional but important keys
    @pytest.mark.parametrize(
        "key",
        [
            "REDIS_URL",
            "DEFAULT_AI_MODEL",
        ],
    )
    def test_backend_has_optional_key(self, backend_env, key):
        assert key in backend_env, f"backend/.env.example should document {key}"

    def test_backend_has_supabase_keys_commented(self, backend_env):
        assert "SUPABASE_URL" in backend_env
        assert "SUPABASE_KEY" in backend_env

    def test_frontend_has_api_url(self, frontend_env):
        assert "NEXT_PUBLIC_API_URL" in frontend_env

    def test_frontend_api_url_points_to_8000(self, frontend_env):
        assert "localhost:8000" in frontend_env


# ===========================================================================
# 5. README references correct setup flow
# ===========================================================================


class TestReadmeAccuracy:
    """README must reference the correct setup flow."""

    @pytest.fixture
    def readme(self):
        return _read(PROJECT_ROOT / "README.md")

    def test_mentions_run_script(self, readme):
        assert "./run" in readme

    def test_mentions_docker(self, readme):
        assert "docker" in readme.lower()

    def test_mentions_anthropic_key_required(self, readme):
        assert "Anthropic" in readme or "ANTHROPIC_API_KEY" in readme

    def test_mentions_postgres_option(self, readme):
        assert "postgres" in readme.lower()

    def test_mentions_supabase_option(self, readme):
        assert "supabase" in readme.lower() or "Supabase" in readme

    def test_correct_backend_port(self, readme):
        assert "localhost:8000" in readme

    def test_correct_frontend_port(self, readme):
        assert "localhost:4000" in readme

    def test_how_to_implement_tool_listed(self, readme):
        assert "how_to_implement" in readme


# ===========================================================================
# 6. Frontend port consistency
# ===========================================================================


class TestPortConsistency:
    """Frontend port must be consistent across all config and docs."""

    def test_package_json_port(self):
        pkg = json.loads(_read(PROJECT_ROOT / "frontend" / "package.json"))
        dev_script = pkg.get("scripts", {}).get("dev", "")
        assert "4000" in dev_script, f"Frontend dev script should use port 4000, got: {dev_script}"

    def test_frontend_env_example_points_to_backend(self):
        env = _read(PROJECT_ROOT / "frontend" / ".env.example")
        assert "8000" in env

    def test_readme_mentions_frontend_4000(self):
        readme = _read(PROJECT_ROOT / "README.md")
        assert "4000" in readme


# ===========================================================================
# 7. prompts.json is valid JSON with all required phases
# ===========================================================================


class TestPromptsJson:
    """prompts.json must be valid and contain all analysis phases."""

    @pytest.fixture
    def prompts(self):
        return json.loads(_read(BACKEND_DIR / "prompts.json"))

    def test_valid_json(self):
        # If this fails, json.loads would throw
        json.loads(_read(BACKEND_DIR / "prompts.json"))

    def test_has_version_field(self, prompts):
        assert "version" in prompts, "prompts.json must have a 'version' field"
        assert isinstance(prompts["version"], int), "version must be an integer"
        assert prompts["version"] >= 1, "version must be >= 1"

    def test_has_prompts_key(self, prompts):
        assert "prompts" in prompts

    @pytest.mark.parametrize(
        "phase",
        [
            "observation",
            "discovery",
            "layers",
            "patterns",
            "communication",
            "technology",
            "frontend_analysis",
            "implementation_analysis",
            "blueprint_synthesis",
        ],
    )
    def test_has_phase(self, prompts, phase):
        assert phase in prompts["prompts"], f"prompts.json missing phase: {phase}"

    def test_each_prompt_has_template(self, prompts):
        for key, prompt in prompts["prompts"].items():
            assert "prompt_template" in prompt, f"Prompt '{key}' missing prompt_template"
            assert len(prompt["prompt_template"]) > 100, f"Prompt '{key}' template is suspiciously short"

    def test_each_prompt_has_variables(self, prompts):
        for key, prompt in prompts["prompts"].items():
            assert "variables" in prompt, f"Prompt '{key}' missing variables list"
            assert isinstance(prompt["variables"], list)

    def test_synthesis_references_implementation_analysis(self, prompts):
        synthesis = prompts["prompts"]["blueprint_synthesis"]
        assert "implementation_analysis" in synthesis.get("prompt_template", ""), (
            "Synthesis prompt must reference {implementation_analysis}"
        )
        assert "implementation_analysis" in synthesis.get("variables", []), (
            "Synthesis must list implementation_analysis in variables"
        )

    def test_synthesis_outputs_implementation_guidelines(self, prompts):
        synthesis = prompts["prompts"]["blueprint_synthesis"]
        template = synthesis.get("prompt_template", "")
        assert "implementation_guidelines" in template, (
            "Synthesis prompt must include implementation_guidelines in output structure"
        )

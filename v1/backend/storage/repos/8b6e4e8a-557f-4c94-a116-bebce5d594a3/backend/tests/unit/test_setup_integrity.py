"""Tests that validate the project setup scripts and configuration are correct.

These tests ensure that a fresh clone + ./setup.sh + ./start-dev.sh will work
out of the box for new developers. They validate:
- Required files exist
- Docker compose config is correct
- Migration SQL creates all tables (prompts seeded separately via seed_prompts.py)
- Env examples contain all necessary keys
- setup.sh and start-dev.sh are valid and complete
- prompts.json has version field and all required phases
- start-dev scripts warn when prompts version is stale
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
            "setup.sh",
            "start-dev.sh",
            "start-dev.py",
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

    def test_setup_sh_is_executable(self):
        setup = PROJECT_ROOT / "setup.sh"
        assert setup.exists()
        mode = setup.stat().st_mode
        assert mode & stat.S_IXUSR, "setup.sh must be executable (chmod +x)"

    def test_start_dev_sh_is_executable(self):
        start = PROJECT_ROOT / "start-dev.sh"
        assert start.exists()
        mode = start.stat().st_mode
        assert mode & stat.S_IXUSR, "start-dev.sh must be executable (chmod +x)"


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
            "STORAGE_TYPE",
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
# 5. setup.sh script validation
# ===========================================================================


class TestSetupScript:
    """setup.sh must handle both database backends and all prerequisites."""

    @pytest.fixture
    def setup_content(self):
        return _read(PROJECT_ROOT / "setup.sh")

    def test_has_shebang(self, setup_content):
        assert setup_content.startswith("#!/")

    def test_offers_postgres_option(self, setup_content):
        assert "postgres" in setup_content

    def test_offers_supabase_option(self, setup_content):
        assert "supabase" in setup_content

    def test_installs_python_if_missing(self, setup_content):
        assert "python" in setup_content.lower()

    def test_installs_node_if_missing(self, setup_content):
        assert "node" in setup_content.lower() or "nodejs" in setup_content.lower()

    def test_creates_venv(self, setup_content):
        assert "venv" in setup_content

    def test_installs_pip_requirements(self, setup_content):
        assert "requirements.txt" in setup_content

    def test_installs_npm_dependencies(self, setup_content):
        assert "npm install" in setup_content

    def test_creates_backend_env(self, setup_content):
        assert ".env.local" in setup_content

    def test_prompts_for_anthropic_key(self, setup_content):
        assert "ANTHROPIC_API_KEY" in setup_content

    def test_runs_docker_compose(self, setup_content):
        assert "docker" in setup_content.lower()
        assert "compose" in setup_content.lower() or "docker-compose" in setup_content.lower()

    def test_verifies_migration_ran(self, setup_content):
        # setup.sh checks if analysis_prompts table exists after Docker starts
        assert "analysis_prompts" in setup_content

    def test_runs_seed_prompts(self, setup_content):
        assert "seed_prompts" in setup_content, (
            "setup.sh must run seed_prompts.py to sync prompts to database"
        )

    def test_reapplies_migration(self, setup_content):
        assert "001_initial_setup.sql" in setup_content, (
            "setup.sh must re-apply the migration SQL (idempotent)"
        )

    def test_handles_macos(self, setup_content):
        assert "Darwin" in setup_content

    def test_handles_linux(self, setup_content):
        assert "Linux" in setup_content

    def test_rejects_git_bash(self, setup_content):
        assert "MINGW" in setup_content or "MSYS" in setup_content


# ===========================================================================
# 6. start-dev.sh script validation
# ===========================================================================


class TestStartDevScript:
    """start-dev.sh must check preconditions and start all services."""

    @pytest.fixture
    def start_content(self):
        return _read(PROJECT_ROOT / "start-dev.sh")

    def test_has_shebang(self, start_content):
        assert start_content.startswith("#!/")

    def test_checks_env_files_exist(self, start_content):
        assert ".env.local" in start_content

    def test_references_setup_sh_on_missing_env(self, start_content):
        assert "setup.sh" in start_content, (
            "start-dev.sh should tell users to run setup.sh if env files are missing"
        )

    def test_starts_docker_for_postgres(self, start_content):
        assert "compose" in start_content.lower() or "docker-compose" in start_content.lower()

    def test_starts_backend(self, start_content):
        assert "main.py" in start_content or "uvicorn" in start_content

    def test_starts_frontend(self, start_content):
        assert "npm run dev" in start_content

    def test_checks_redis_for_worker(self, start_content):
        assert "redis" in start_content.lower()

    def test_handles_ctrl_c_gracefully(self, start_content):
        assert "trap" in start_content or "SIGINT" in start_content

    def test_shows_urls_on_success(self, start_content):
        assert "BACKEND_PORT" in start_content, "Backend URL should use BACKEND_PORT variable"
        assert "FRONTEND_PORT" in start_content, "Frontend URL should use FRONTEND_PORT variable"

    def test_supports_both_db_backends(self, start_content):
        assert "DB_BACKEND" in start_content

    def test_checks_prompts_version(self, start_content):
        assert "prompts-version" in start_content, (
            "start-dev.sh must check .prompts-version to warn about stale setup"
        )


# ===========================================================================
# 7. start-dev.py cross-platform script
# ===========================================================================


class TestStartDevPy:
    """start-dev.py must mirror start-dev.sh functionality."""

    @pytest.fixture
    def start_py_content(self):
        return _read(PROJECT_ROOT / "start-dev.py")

    def test_checks_env_files(self, start_py_content):
        assert ".env.local" in start_py_content

    def test_starts_backend(self, start_py_content):
        assert "main.py" in start_py_content or "uvicorn" in start_py_content

    def test_starts_frontend(self, start_py_content):
        assert "npm" in start_py_content

    def test_creates_venv_if_missing(self, start_py_content):
        assert "venv" in start_py_content

    def test_checks_prompts_version(self, start_py_content):
        assert "prompts-version" in start_py_content or ".prompts-version" in start_py_content, (
            "start-dev.py must check .prompts-version to warn about stale setup"
        )


# ===========================================================================
# 8. README references correct scripts and flow
# ===========================================================================


class TestReadmeAccuracy:
    """README must reference the correct setup flow."""

    @pytest.fixture
    def readme(self):
        return _read(PROJECT_ROOT / "README.md")

    def test_mentions_setup_sh(self, readme):
        assert "setup.sh" in readme

    def test_mentions_start_dev_sh(self, readme):
        assert "start-dev.sh" in readme

    def test_mentions_docker_compose(self, readme):
        assert "docker compose" in readme.lower() or "docker-compose" in readme.lower()

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
# 9. Frontend port consistency
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
# 10. prompts.json is valid JSON with all required phases
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

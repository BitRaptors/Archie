"""Comprehensive tests for MCP tool implementations.

Tests the core tool logic in BlueprintTools: validate_import, where_to_put,
check_naming, get_repository_blueprint, list_repository_sections,
get_repository_section, and internal helpers (_glob_match, _slice_markdown).
"""
import json
import pytest
from pathlib import Path

from domain.entities.blueprint import (
    ArchitectureRules,
    BlueprintMeta,
    Components,
    Communication,
    DependencyConstraint,
    Decisions,
    FilePlacementRule,
    Frontend,
    NamingConvention,
    QuickReference,
    StructuredBlueprint,
    Technology,
)
from infrastructure.mcp.tools import BlueprintTools, _glob_match, _match_segments, _slice_markdown, _slugify


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_blueprint(**overrides) -> StructuredBlueprint:
    """Create a minimal StructuredBlueprint for testing."""
    defaults = dict(
        meta=BlueprintMeta(
            repository="acme/webapp",
            repository_id="test-repo-123",
            schema_version="2.0.0",
            architecture_style="Clean Architecture",
            platforms=["backend"],
        ),
        architecture_rules=ArchitectureRules(
            dependency_constraints=[
                DependencyConstraint(
                    source_pattern="src/domain/**",
                    source_description="Domain layer",
                    allowed_imports=["src/domain/**"],
                    forbidden_imports=[
                        "src/infrastructure/**",
                        "src/api/**",
                        "fastapi",
                        "sqlalchemy",
                    ],
                    severity="error",
                    rationale="Domain must remain pure with no external deps",
                ),
                DependencyConstraint(
                    source_pattern="src/api/**",
                    source_description="API/Presentation layer",
                    allowed_imports=[
                        "src/application/**",
                        "src/domain/**",
                        "fastapi",
                    ],
                    forbidden_imports=["src/infrastructure/**"],
                    severity="error",
                    rationale="API should not access infrastructure directly",
                ),
                DependencyConstraint(
                    source_pattern="src/application/**",
                    source_description="Application layer",
                    allowed_imports=[
                        "src/domain/**",
                        "src/application/**",
                    ],
                    forbidden_imports=["src/api/**", "fastapi"],
                    severity="error",
                    rationale="Application layer must not depend on HTTP",
                ),
            ],
            file_placement_rules=[
                FilePlacementRule(
                    component_type="service",
                    location="src/application/services",
                    naming_pattern="*_service.py",
                    example="user_service.py",
                    description="Business logic services",
                ),
                FilePlacementRule(
                    component_type="entity",
                    location="src/domain/entities",
                    naming_pattern="*.py",
                    example="user.py",
                    description="Domain entities",
                ),
                FilePlacementRule(
                    component_type="repository",
                    location="src/infrastructure/persistence",
                    naming_pattern="*_repository.py",
                    example="user_repository.py",
                    description="Data access repositories",
                ),
                FilePlacementRule(
                    component_type="controller",
                    location="src/api/routes",
                    naming_pattern="*.py",
                    example="users.py",
                    description="API route handlers",
                ),
            ],
            naming_conventions=[
                NamingConvention(
                    scope="classes",
                    pattern="^[A-Z][a-zA-Z0-9]*$",
                    examples=["UserService", "OrderRepository"],
                    description="PascalCase for classes",
                ),
                NamingConvention(
                    scope="functions",
                    pattern="^[a-z_][a-z0-9_]*$",
                    examples=["get_user", "create_order"],
                    description="snake_case for functions",
                ),
                NamingConvention(
                    scope="files",
                    pattern="^[a-z][a-z0-9_]*\\.py$",
                    examples=["user_service.py", "models.py"],
                    description="snake_case for Python files",
                ),
            ],
        ),
        quick_reference=QuickReference(
            where_to_put_code={
                "service": "src/application/services",
                "entity": "src/domain/entities",
                "repository": "src/infrastructure/persistence",
                "controller": "src/api/routes",
                "middleware": "src/api/middleware",
                "dto": "src/api/dtos",
            },
        ),
        decisions=Decisions(),
        components=Components(),
        communication=Communication(),
        technology=Technology(),
        frontend=Frontend(),
    )
    defaults.update(overrides)
    return StructuredBlueprint(**defaults)


@pytest.fixture
def sample_blueprint():
    return _make_blueprint()


@pytest.fixture
def tools(tmp_path):
    """BlueprintTools with a temp storage dir containing a test blueprint."""
    storage_dir = tmp_path / "storage"
    bp_dir = storage_dir / "blueprints" / "test-repo-123"
    bp_dir.mkdir(parents=True)

    bp = _make_blueprint()
    (bp_dir / "blueprint.json").write_text(
        bp.model_dump_json(indent=2), encoding="utf-8"
    )

    return BlueprintTools(storage_dir=storage_dir)


# ══════════════════════════════════════════════════════════════════════════════
# _glob_match
# ══════════════════════════════════════════════════════════════════════════════


class TestGlobMatch:
    """Test the custom glob matching used by validate_import."""

    def test_double_star_matches_multiple_segments(self):
        assert _glob_match("src/domain/entities/user.py", "src/domain/**") is True

    def test_double_star_matches_single_segment(self):
        assert _glob_match("src/domain/user.py", "src/domain/**") is True

    def test_double_star_matches_zero_segments(self):
        assert _glob_match("src/domain", "src/domain/**") is True

    def test_double_star_at_start(self):
        assert _glob_match("src/domain/entities/user.py", "**/*.py") is True

    def test_double_star_at_start_does_not_match_wrong_ext(self):
        assert _glob_match("src/domain/entities/user.ts", "**/*.py") is False

    def test_single_star_matches_one_segment(self):
        assert _glob_match("src/api/routes.py", "src/api/*.py") is True

    def test_single_star_does_not_cross_slash(self):
        assert _glob_match("src/api/routes/users.py", "src/api/*.py") is False

    def test_exact_match(self):
        assert _glob_match("src/main.py", "src/main.py") is True

    def test_exact_no_match(self):
        assert _glob_match("src/main.py", "src/other.py") is False

    def test_backslash_normalisation(self):
        assert _glob_match("src\\domain\\user.py", "src/domain/**") is True

    def test_double_star_middle(self):
        assert _glob_match("src/domain/entities/deep/user.py", "src/**/user.py") is True

    def test_double_star_middle_zero_segments(self):
        assert _glob_match("src/user.py", "src/**/user.py") is True

    def test_pattern_longer_than_path(self):
        assert _glob_match("src", "src/domain/**") is False

    def test_empty_pattern_empty_path(self):
        assert _glob_match("", "") is True

    def test_wildcard_import_pattern(self):
        assert _glob_match("retrofit2.Call", "retrofit2.*") is True

    def test_double_star_suffix(self):
        assert _glob_match("presentation/screens/Login.kt", "presentation/**") is True

    def test_no_match_different_prefix(self):
        assert _glob_match("data/repo/UserRepo.kt", "presentation/**") is False


# ══════════════════════════════════════════════════════════════════════════════
# _slice_markdown / _slugify
# ══════════════════════════════════════════════════════════════════════════════


class TestSliceMarkdown:
    """Test the markdown slicing used by section tools."""

    def test_basic_slicing(self):
        content = "# Title\n\nIntro text\n\n## First\n\nSection 1\n\n## Second\n\nSection 2"
        sections = _slice_markdown(content)
        assert "introduction" in sections
        assert "first" in sections
        assert "second" in sections

    def test_no_sections(self):
        content = "# Title\n\nJust a document with no ## headers."
        sections = _slice_markdown(content)
        assert "introduction" in sections
        assert len(sections) == 1

    def test_preserves_header(self):
        content = "## Architecture\n\nDetails here"
        sections = _slice_markdown(content)
        assert "## Architecture" in sections["architecture"]

    def test_slugify_basic(self):
        assert _slugify("Layer Architecture") == "layer-architecture"

    def test_slugify_numbered(self):
        assert _slugify("1. Layer Architecture") == "layer-architecture"

    def test_slugify_special(self):
        assert _slugify("Key Decisions & Trade-Offs") == "key-decisions-trade-offs"


# ══════════════════════════════════════════════════════════════════════════════
# validate_import
# ══════════════════════════════════════════════════════════════════════════════


class TestValidateImport:
    """Test the validate_import tool — the core guardrail."""

    def test_forbidden_import_detected(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "src/domain/entities/user.py",
            "src/infrastructure/db/connection.py",
        )
        assert "VIOLATION" in result
        assert "is NOT allowed" in result
        assert '"is_valid": false' in result

    def test_allowed_import_passes(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "src/domain/entities/user.py",
            "src/domain/value_objects/email.py",
        )
        assert "ALLOWED" in result
        assert '"is_valid": true' in result

    def test_api_cannot_import_infrastructure(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "src/api/routes/users.py",
            "src/infrastructure/persistence/user_repo.py",
        )
        assert "VIOLATION" in result

    def test_api_can_import_application(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "src/api/routes/users.py",
            "src/application/services/user_service.py",
        )
        assert "ALLOWED" in result

    def test_application_cannot_import_fastapi(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "src/application/services/user_service.py",
            "fastapi",
        )
        assert "VIOLATION" in result

    def test_no_matching_rule(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "scripts/deploy.py",
            "boto3",
        )
        assert "UNGUARDED" in result
        assert "verify manually" in result.lower()
        assert '"is_valid": true' in result

    def test_nonexistent_repo(self, tools):
        result = tools.validate_import(
            "nonexistent-repo-id",
            "src/domain/user.py",
            "fastapi",
        )
        assert "not found" in result.lower() or "Run analysis" in result

    def test_response_contains_json_block(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "src/domain/entities/user.py",
            "src/infrastructure/db.py",
        )
        assert "```json" in result
        json_start = result.index("```json") + 7
        json_end = result.index("```", json_start)
        parsed = json.loads(result[json_start:json_end])
        assert "is_valid" in parsed
        assert "violations" in parsed
        assert "source_file" in parsed
        assert "target_import" in parsed

    def test_violation_includes_severity_and_rationale(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "src/domain/entities/user.py",
            "sqlalchemy",
        )
        assert "severity" in result
        assert "error" in result.lower()
        assert "Reason:" in result or "rationale" in result.lower()

    def test_multiple_violations_all_reported(self, tools):
        result = tools.validate_import(
            "test-repo-123",
            "src/domain/entities/user.py",
            "src/api/routes/users.py",
        )
        assert "VIOLATION" in result


# ══════════════════════════════════════════════════════════════════════════════
# where_to_put
# ══════════════════════════════════════════════════════════════════════════════


class TestWhereToPut:
    """Test the where_to_put tool."""

    def test_finds_service_location(self, tools):
        result = tools.where_to_put("test-repo-123", "service")
        assert "src/application/services" in result
        assert "*_service.py" in result
        assert "user_service.py" in result

    def test_finds_entity_location(self, tools):
        result = tools.where_to_put("test-repo-123", "entity")
        assert "src/domain/entities" in result

    def test_finds_repository_location(self, tools):
        result = tools.where_to_put("test-repo-123", "repository")
        assert "src/infrastructure/persistence" in result

    def test_finds_controller_location(self, tools):
        result = tools.where_to_put("test-repo-123", "controller")
        assert "src/api/routes" in result

    def test_case_insensitive_search(self, tools):
        result = tools.where_to_put("test-repo-123", "Service")
        assert "src/application/services" in result

    def test_partial_match(self, tools):
        result = tools.where_to_put("test-repo-123", "repo")
        assert "src/infrastructure/persistence" in result

    def test_unknown_component_lists_available(self, tools):
        result = tools.where_to_put("test-repo-123", "blockchain_module")
        assert "No placement rule" in result
        assert "Available component types" in result

    def test_nonexistent_repo(self, tools):
        result = tools.where_to_put("nonexistent-repo-id", "service")
        assert "not found" in result.lower() or "Run analysis" in result

    def test_response_contains_json(self, tools):
        result = tools.where_to_put("test-repo-123", "service")
        assert "```json" in result
        json_start = result.index("```json") + 7
        json_end = result.index("```", json_start)
        parsed = json.loads(result[json_start:json_end])
        assert isinstance(parsed, list)
        assert len(parsed) > 0
        assert "location" in parsed[0]

    def test_matches_from_quick_reference(self, tools):
        result = tools.where_to_put("test-repo-123", "middleware")
        assert "src/api/middleware" in result

    def test_dto_from_quick_reference(self, tools):
        result = tools.where_to_put("test-repo-123", "dto")
        assert "src/api/dtos" in result


# ══════════════════════════════════════════════════════════════════════════════
# check_naming
# ══════════════════════════════════════════════════════════════════════════════


class TestCheckNaming:
    """Test the check_naming tool."""

    def test_valid_class_name(self, tools):
        result = tools.check_naming("test-repo-123", "classes", "UserService")
        assert "OK" in result
        assert '"is_valid": true' in result

    def test_invalid_class_name_snake_case(self, tools):
        result = tools.check_naming("test-repo-123", "classes", "user_service")
        assert "NAMING ISSUE" in result
        assert '"is_valid": false' in result

    def test_invalid_class_name_with_underscore(self, tools):
        result = tools.check_naming("test-repo-123", "classes", "User_Service")
        assert "NAMING ISSUE" in result

    def test_valid_function_name(self, tools):
        result = tools.check_naming("test-repo-123", "functions", "get_user_by_id")
        assert "OK" in result
        assert '"is_valid": true' in result

    def test_invalid_function_name_camelcase(self, tools):
        result = tools.check_naming("test-repo-123", "functions", "getUserById")
        assert "NAMING ISSUE" in result
        assert '"is_valid": false' in result

    def test_valid_file_name(self, tools):
        result = tools.check_naming("test-repo-123", "files", "user_service.py")
        assert "OK" in result

    def test_invalid_file_name_uppercase(self, tools):
        result = tools.check_naming("test-repo-123", "files", "UserService.py")
        assert "NAMING ISSUE" in result

    def test_unknown_scope(self, tools):
        result = tools.check_naming("test-repo-123", "constants", "MAX_RETRIES")
        assert "No naming convention" in result
        assert "Available scopes" in result

    def test_nonexistent_repo(self, tools):
        result = tools.check_naming("nonexistent-repo-id", "classes", "Foo")
        assert "not found" in result.lower() or "Run analysis" in result

    def test_response_includes_examples(self, tools):
        result = tools.check_naming("test-repo-123", "classes", "bad_name")
        assert "NAMING ISSUE" in result
        assert "UserService" in result or "OrderRepository" in result

    def test_response_contains_json_block(self, tools):
        result = tools.check_naming("test-repo-123", "classes", "UserService")
        assert "```json" in result
        json_start = result.index("```json") + 7
        json_end = result.index("```", json_start)
        parsed = json.loads(result[json_start:json_end])
        assert "is_valid" in parsed
        assert "name" in parsed
        assert "scope" in parsed

    def test_non_regex_pattern_reports_note(self, tmp_path):
        """Non-regex naming patterns should include a manual-verification note."""
        storage_dir = tmp_path / "storage"
        bp_dir = storage_dir / "blueprints" / "non-regex-repo"
        bp_dir.mkdir(parents=True)

        bp = _make_blueprint(
            architecture_rules=ArchitectureRules(
                naming_conventions=[
                    NamingConvention(
                        scope="classes",
                        pattern="PascalCase with no underscores",
                        examples=["UserService"],
                        description="Informal convention",
                    ),
                ],
            ),
        )
        (bp_dir / "blueprint.json").write_text(bp.model_dump_json(indent=2), encoding="utf-8")
        t = BlueprintTools(storage_dir=storage_dir)

        result = t.check_naming("non-regex-repo", "classes", "anything")
        assert "OK" in result  # passes because it can't validate
        json_start = result.index("```json") + 7
        json_end = result.index("```", json_start)
        parsed = json.loads(result[json_start:json_end])
        assert any("note" in m for m in parsed["matching_conventions"])


# ══════════════════════════════════════════════════════════════════════════════
# Blueprint loading and section tools
# ══════════════════════════════════════════════════════════════════════════════


class TestBlueprintLoading:
    """Test _load_structured_blueprint and section tools."""

    def test_loads_valid_blueprint(self, tools):
        bp = tools._load_structured_blueprint("test-repo-123")
        assert bp is not None
        assert bp.meta.repository == "acme/webapp"

    def test_returns_none_for_missing_repo(self, tools):
        bp = tools._load_structured_blueprint("nonexistent-repo-id")
        assert bp is None

    def test_returns_none_for_invalid_json(self, tools):
        bp_dir = tools.storage_dir / "blueprints" / "bad-json"
        bp_dir.mkdir(parents=True)
        (bp_dir / "blueprint.json").write_text("{invalid json", encoding="utf-8")
        bp = tools._load_structured_blueprint("bad-json")
        assert bp is None

    def test_resolve_repo_display_name(self, tools):
        name = tools._resolve_repo_display_name("test-repo-123")
        assert name == "acme/webapp"

    def test_resolve_display_name_falls_back_to_id(self, tools):
        name = tools._resolve_repo_display_name("nonexistent-repo-id")
        assert name == "nonexistent-repo-id"


class TestListRepositorySections:
    def test_lists_sections(self, tools):
        result = tools.list_repository_sections("test-repo-123")
        assert "Blueprint Sections" in result
        assert "acme/webapp" in result
        assert "`" in result

    def test_nonexistent_repo(self, tools):
        result = tools.list_repository_sections("nonexistent-repo-id")
        assert "not found" in result.lower()


class TestGetRepositorySection:
    def test_nonexistent_repo(self, tools):
        result = tools.get_repository_section("nonexistent-repo-id", "any-section")
        assert "not found" in result.lower()

    def test_nonexistent_section(self, tools):
        result = tools.get_repository_section("test-repo-123", "nonexistent-section-slug")
        assert "not found" in result.lower() or "Available sections" in result


class TestGetRepositoryBlueprint:
    def test_returns_markdown(self, tools):
        result = tools.get_repository_blueprint("test-repo-123")
        assert len(result) > 100
        assert "#" in result

    def test_nonexistent_repo(self, tools):
        result = tools.get_repository_blueprint("nonexistent-repo-id")
        assert "not found" in result.lower()


class TestListAnalyzedRepositories:
    def test_lists_repos(self, tools):
        result = tools.list_analyzed_repositories()
        assert "acme/webapp" in result
        assert "test-repo-123" in result

    def test_empty_storage(self, tmp_path):
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()
        t = BlueprintTools(storage_dir=storage_dir)
        result = t.list_analyzed_repositories()
        assert "No analyzed" in result

    def test_no_blueprints_dir(self, tmp_path):
        storage_dir = tmp_path / "storage"
        t = BlueprintTools(storage_dir=storage_dir)
        result = t.list_analyzed_repositories()
        assert "No analyzed" in result


# ══════════════════════════════════════════════════════════════════════════════
# Real-world blueprint scenarios
# ══════════════════════════════════════════════════════════════════════════════


class TestRealWorldScenarios:
    """Test with patterns mimicking real analyzed repos (Android, Python, etc.)."""

    @pytest.fixture
    def android_tools(self, tmp_path):
        storage_dir = tmp_path / "storage"
        bp_dir = storage_dir / "blueprints" / "android-app"
        bp_dir.mkdir(parents=True)

        bp = _make_blueprint(
            meta=BlueprintMeta(
                repository="acme/android-app",
                repository_id="android-app",
                platforms=["mobile-android"],
            ),
            architecture_rules=ArchitectureRules(
                dependency_constraints=[
                    DependencyConstraint(
                        source_pattern="presentation/**",
                        source_description="UI layer (Compose screens, ViewModels)",
                        allowed_imports=["domain/**", "androidx.compose.*"],
                        forbidden_imports=["data/**", "retrofit2.*"],
                        severity="error",
                        rationale="Presentation depends on Domain only",
                    ),
                    DependencyConstraint(
                        source_pattern="domain/**",
                        source_description="Business logic",
                        allowed_imports=["kotlin.*", "kotlinx.coroutines.*"],
                        forbidden_imports=["data/**", "presentation/**", "android.content.*"],
                        severity="error",
                        rationale="Domain is pure Kotlin, no Android deps",
                    ),
                    DependencyConstraint(
                        source_pattern="data/**",
                        source_description="Data layer",
                        allowed_imports=["domain/**", "retrofit2.*", "androidx.room.*"],
                        forbidden_imports=["presentation/**"],
                        severity="error",
                        rationale="Data implements domain interfaces",
                    ),
                ],
                file_placement_rules=[
                    FilePlacementRule(
                        component_type="ViewModel",
                        location="presentation/viewmodels",
                        naming_pattern="*ViewModel.kt",
                        example="LoginViewModel.kt",
                    ),
                    FilePlacementRule(
                        component_type="UseCase",
                        location="domain/usecases",
                        naming_pattern="*UseCase.kt",
                        example="GetUserUseCase.kt",
                    ),
                ],
                naming_conventions=[
                    NamingConvention(
                        scope="classes",
                        pattern="^[A-Z][a-zA-Z0-9]*$",
                        examples=["LoginViewModel", "UserRepository"],
                        description="PascalCase",
                    ),
                ],
            ),
            quick_reference=QuickReference(
                where_to_put_code={
                    "ViewModel": "presentation/viewmodels",
                    "UseCase": "domain/usecases",
                    "Repository": "data/repositories",
                    "Screen": "presentation/screens",
                },
            ),
        )
        (bp_dir / "blueprint.json").write_text(
            bp.model_dump_json(indent=2), encoding="utf-8"
        )
        return BlueprintTools(storage_dir=storage_dir)

    def test_android_presentation_cannot_import_data(self, android_tools):
        result = android_tools.validate_import(
            "android-app",
            "presentation/screens/LoginScreen.kt",
            "data/api/AuthApi.kt",
        )
        assert "VIOLATION" in result

    def test_android_presentation_can_import_domain(self, android_tools):
        result = android_tools.validate_import(
            "android-app",
            "presentation/viewmodels/LoginViewModel.kt",
            "domain/usecases/LoginUseCase.kt",
        )
        assert "ALLOWED" in result

    def test_android_domain_cannot_import_android(self, android_tools):
        result = android_tools.validate_import(
            "android-app",
            "domain/usecases/GetUserUseCase.kt",
            "android.content.Context",
        )
        assert "VIOLATION" in result

    def test_android_data_cannot_import_presentation(self, android_tools):
        result = android_tools.validate_import(
            "android-app",
            "data/repositories/UserRepositoryImpl.kt",
            "presentation/viewmodels/UserViewModel.kt",
        )
        assert "VIOLATION" in result

    def test_android_where_to_put_viewmodel(self, android_tools):
        result = android_tools.where_to_put("android-app", "ViewModel")
        assert "presentation/viewmodels" in result
        assert "*ViewModel.kt" in result

    def test_android_where_to_put_screen(self, android_tools):
        result = android_tools.where_to_put("android-app", "Screen")
        assert "presentation/screens" in result

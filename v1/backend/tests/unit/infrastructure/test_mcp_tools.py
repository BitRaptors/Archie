"""Comprehensive tests for MCP tool implementations.

Tests the core tool logic in BlueprintTools: where_to_put,
check_naming, get_repository_blueprint, list_repository_sections,
get_repository_section, and internal helpers (_glob_match, _slice_markdown).
"""
import json
import pytest

from domain.entities.blueprint import (
    ArchitectureRules,
    BlueprintMeta,
    Components,
    Communication,
    Decisions,
    FilePlacementRule,
    Frontend,
    ImplementationGuideline,
    NamingConvention,
    QuickReference,
    StructuredBlueprint,
    Technology,
)
from infrastructure.mcp.tools import BlueprintTools, _glob_match, _slice_markdown, _slugify


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


@pytest.fixture
def tools_with_guidelines(tmp_path):
    """BlueprintTools with a blueprint containing implementation guidelines."""
    storage_dir = tmp_path / "storage"
    bp_dir = storage_dir / "blueprints" / "test-repo-123"
    bp_dir.mkdir(parents=True)

    bp = _make_blueprint(
        implementation_guidelines=[
            ImplementationGuideline(
                capability="Push Notifications",
                category="notifications",
                libraries=["Firebase Cloud Messaging 10.x"],
                pattern_description="FCM topic-based subscriptions via NotificationService singleton.",
                key_files=["Services/NotificationService.swift", "AppDelegate.swift"],
                usage_example="NotificationService.shared.subscribe(topic: 'place_updates')",
                tips=["Request notification permissions before subscribing", "Handle token refresh via FIRMessaging delegate"],
            ),
            ImplementationGuideline(
                capability="Map Display",
                category="location",
                libraries=["Mapbox Maps SDK 10.x", "Core Location"],
                pattern_description="MGLMapView wrapped in custom MapView. Annotations from PlacesService.",
                key_files=["Controllers/MapViewController.swift", "Views/MapView.swift"],
                usage_example="mapView.addAnnotations(places.map { PlaceAnnotation($0) })",
                tips=["Limit annotations to ~100 per viewport", "Use clustering for large datasets"],
            ),
        ],
    )
    (bp_dir / "blueprint.json").write_text(
        bp.model_dump_json(indent=2), encoding="utf-8"
    )

    return BlueprintTools(storage_dir=storage_dir)


# ══════════════════════════════════════════════════════════════════════════════
# _glob_match
# ══════════════════════════════════════════════════════════════════════════════


class TestGlobMatch:
    """Test the custom glob matching used by tool implementations."""

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

    def test_android_where_to_put_viewmodel(self, android_tools):
        result = android_tools.where_to_put("android-app", "ViewModel")
        assert "presentation/viewmodels" in result
        assert "*ViewModel.kt" in result

    def test_android_where_to_put_screen(self, android_tools):
        result = android_tools.where_to_put("android-app", "Screen")
        assert "presentation/screens" in result


# ══════════════════════════════════════════════════════════════════════════════
# how_to_implement
# ══════════════════════════════════════════════════════════════════════════════


class TestHowToImplement:
    """Test the how_to_implement tool."""

    def test_finds_by_capability_name(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "push notifications")
        assert "Push Notifications" in result
        assert "Firebase Cloud Messaging" in result
        assert "Services/NotificationService.swift" in result

    def test_finds_by_category(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "location")
        assert "Map Display" in result
        assert "Mapbox" in result

    def test_finds_by_library_name(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "mapbox")
        assert "Map Display" in result

    def test_case_insensitive(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "PUSH NOTIFICATIONS")
        assert "Push Notifications" in result

    def test_returns_key_files(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "push notifications")
        assert "`Services/NotificationService.swift`" in result

    def test_returns_usage_example(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "push notifications")
        assert "subscribe(topic:" in result

    def test_returns_tips(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "push notifications")
        assert "Request notification permissions" in result

    def test_no_match_lists_available(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "blockchain")
        assert "No implementation guideline" in result
        assert "Push Notifications" in result
        assert "Map Display" in result

    def test_empty_guidelines_graceful(self, tools):
        result = tools.how_to_implement("test-repo-123", "push notifications")
        assert "No implementation guideline" in result or "not found" in result.lower()

    def test_nonexistent_repo(self, tools):
        result = tools.how_to_implement("nonexistent-repo-id", "push notifications")
        assert "No structured blueprint found" in result

    def test_no_cross_contamination(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement("test-repo-123", "notifications")
        assert "Push Notifications" in result
        assert "Map Display" not in result


# ══════════════════════════════════════════════════════════════════════════════
# list_implementations
# ══════════════════════════════════════════════════════════════════════════════


class TestListCapabilities:
    """Test the list_implementations tool."""

    def test_returns_both_capability_ids(self, tools_with_guidelines):
        result = tools_with_guidelines.list_implementations("test-repo-123")
        assert "push-notifications" in result
        assert "map-display" in result

    def test_returns_categories(self, tools_with_guidelines):
        result = tools_with_guidelines.list_implementations("test-repo-123")
        assert "notifications" in result
        assert "location" in result

    def test_returns_libraries_as_hints(self, tools_with_guidelines):
        result = tools_with_guidelines.list_implementations("test-repo-123")
        assert "Firebase Cloud Messaging" in result
        assert "Mapbox" in result

    def test_returns_descriptions(self, tools_with_guidelines):
        result = tools_with_guidelines.list_implementations("test-repo-123")
        assert "FCM topic-based" in result
        assert "MGLMapView" in result

    def test_mentions_how_to_implement_by_id(self, tools_with_guidelines):
        result = tools_with_guidelines.list_implementations("test-repo-123")
        assert "how_to_implement_by_id" in result

    def test_empty_guidelines_graceful(self, tools):
        result = tools.list_implementations("test-repo-123")
        assert "No implementation guideline" in result or "not found" in result.lower()

    def test_nonexistent_repo(self, tools):
        result = tools.list_implementations("nonexistent-repo-id")
        assert "No structured blueprint found" in result


# ══════════════════════════════════════════════════════════════════════════════
# how_to_implement_by_id
# ══════════════════════════════════════════════════════════════════════════════


class TestHowToImplementById:
    """Test the how_to_implement_by_id tool."""

    def test_exact_match_returns_full_details(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement_by_id("test-repo-123", "push-notifications")
        assert "Push Notifications" in result
        assert "Firebase Cloud Messaging" in result
        assert "Services/NotificationService.swift" in result
        assert "subscribe(topic:" in result
        assert "Request notification permissions" in result

    def test_map_display_by_id(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement_by_id("test-repo-123", "map-display")
        assert "Map Display" in result
        assert "Mapbox" in result
        assert "Controllers/MapViewController.swift" in result
        assert "Limit annotations" in result

    def test_not_found_lists_available_ids(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement_by_id("test-repo-123", "blockchain")
        assert "No implementation guideline found" in result
        assert "push-notifications" in result
        assert "map-display" in result

    def test_not_found_mentions_list_implementations(self, tools_with_guidelines):
        result = tools_with_guidelines.how_to_implement_by_id("test-repo-123", "nonexistent")
        assert "list_implementations" in result

    def test_empty_guidelines_graceful(self, tools):
        result = tools.how_to_implement_by_id("test-repo-123", "push-notifications")
        assert "No implementation guideline" in result or "not found" in result.lower()

    def test_nonexistent_repo(self, tools):
        result = tools.how_to_implement_by_id("nonexistent-repo-id", "push-notifications")
        assert "No structured blueprint found" in result


# ── Source file tools ────────────────────────────────────────────────────────


class TestListSourceFiles:
    """Tests for the list_source_files MCP tool."""

    def test_returns_file_list_from_manifest(self, tools, tmp_path):
        # Create a persisted repo copy with manifest
        repo_dir = tmp_path / "storage" / "repos" / "test-repo-123"
        (repo_dir / "src").mkdir(parents=True)
        (repo_dir / "src" / "main.py").write_text("main", encoding="utf-8")
        (repo_dir / "src" / "app.py").write_text("app", encoding="utf-8")

        manifest = {
            "collected_at": "2026-02-19T00:00:00Z",
            "file_count": 2,
            "files": {"src/main.py": 4, "src/app.py": 3},
            "total_size": 7,
        }
        (repo_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        result = tools.list_source_files("test-repo-123")
        assert "src/main.py" in result
        assert "src/app.py" in result

    def test_returns_file_list_without_manifest(self, tools, tmp_path):
        # Create a repo dir without manifest — fallback to walk
        repo_dir = tmp_path / "storage" / "repos" / "test-repo-123"
        (repo_dir / "src").mkdir(parents=True)
        (repo_dir / "src" / "main.py").write_text("main", encoding="utf-8")

        result = tools.list_source_files("test-repo-123")
        assert "src/main.py" in result

    def test_returns_empty_when_no_repo(self, tools):
        result = tools.list_source_files("test-repo-123")
        assert "No source files available" in result


class TestGetFileContent:
    """Tests for the get_file_content MCP tool."""

    def test_returns_file_content(self, tools, tmp_path):
        repo_dir = tmp_path / "storage" / "repos" / "test-repo-123"
        (repo_dir / "src").mkdir(parents=True)
        (repo_dir / "src" / "main.py").write_text("hello world", encoding="utf-8")

        result = tools.get_file_content("test-repo-123", "src/main.py")
        assert "hello world" in result
        assert "src/main.py" in result

    def test_returns_not_found_for_missing_file(self, tools, tmp_path):
        repo_dir = tmp_path / "storage" / "repos" / "test-repo-123"
        repo_dir.mkdir(parents=True)

        result = tools.get_file_content("test-repo-123", "src/secret.py")
        assert "not found" in result

    def test_rejects_path_traversal(self, tools, tmp_path):
        repo_dir = tmp_path / "storage" / "repos" / "test-repo-123"
        repo_dir.mkdir(parents=True)

        result = tools.get_file_content("test-repo-123", "../etc/passwd")
        assert "Invalid file path" in result

    def test_returns_error_when_no_repo(self, tools):
        result = tools.get_file_content("test-repo-123", "main.py")
        assert "No source files available" in result


# ══════════════════════════════════════════════════════════════════════════════
# Multi-tool workflow tests
# ══════════════════════════════════════════════════════════════════════════════


class TestMCPWorkflow:
    """Test multi-tool sequences that mirror real AI agent workflows.

    Validates the core loop: ask how_to_implement → get file paths →
    call get_file_content to read those files.
    """

    @pytest.fixture
    def workflow_tools(self, tmp_path):
        """BlueprintTools with guidelines AND source files on disk."""
        storage_dir = tmp_path / "storage"
        bp_dir = storage_dir / "blueprints" / "test-repo-123"
        bp_dir.mkdir(parents=True)

        bp = _make_blueprint(
            implementation_guidelines=[
                ImplementationGuideline(
                    capability="Push Notifications",
                    category="notifications",
                    libraries=["Firebase Cloud Messaging 10.x"],
                    pattern_description="FCM topic-based subscriptions via NotificationService singleton.",
                    key_files=["Services/NotificationService.swift", "AppDelegate.swift"],
                    usage_example="NotificationService.shared.subscribe(topic: 'place_updates')",
                    tips=["Request notification permissions before subscribing"],
                ),
                ImplementationGuideline(
                    capability="Map Display",
                    category="location",
                    libraries=["Mapbox Maps SDK 10.x", "Core Location"],
                    pattern_description="MGLMapView wrapped in custom MapView.",
                    key_files=["Controllers/MapViewController.swift", "Views/MapView.swift"],
                    usage_example="mapView.addAnnotations(places.map { PlaceAnnotation($0) })",
                    tips=["Limit annotations to ~100 per viewport"],
                ),
            ],
        )
        (bp_dir / "blueprint.json").write_text(
            bp.model_dump_json(indent=2), encoding="utf-8"
        )

        # Create source files that match the key_files in guidelines
        repo_dir = storage_dir / "repos" / "test-repo-123"
        (repo_dir / "Services").mkdir(parents=True)
        (repo_dir / "Controllers").mkdir(parents=True)
        (repo_dir / "Views").mkdir(parents=True)

        (repo_dir / "Services" / "NotificationService.swift").write_text(
            "class NotificationService {\n    static let shared = NotificationService()\n    func subscribe(topic: String) { }\n}",
            encoding="utf-8",
        )
        (repo_dir / "AppDelegate.swift").write_text(
            "class AppDelegate: UIResponder {\n    func application(_ app: UIApplication) { }\n}",
            encoding="utf-8",
        )
        (repo_dir / "Controllers" / "MapViewController.swift").write_text(
            "class MapViewController: UIViewController {\n    var mapView: MapView!\n}",
            encoding="utf-8",
        )
        (repo_dir / "Views" / "MapView.swift").write_text(
            "class MapView: UIView {\n    func addAnnotations(_ annotations: [Any]) { }\n}",
            encoding="utf-8",
        )

        # Also create files for where_to_put tests
        (repo_dir / "src" / "application" / "services").mkdir(parents=True)
        (repo_dir / "src" / "application" / "services" / "user_service.py").write_text(
            "class UserService:\n    pass",
            encoding="utf-8",
        )

        return BlueprintTools(storage_dir=storage_dir)

    def test_how_to_implement_then_get_file_content(self, workflow_tools):
        """Full round-trip: ask how_to_implement → read returned key files."""
        # Step 1: Ask how push notifications are implemented
        impl_result = workflow_tools.how_to_implement("test-repo-123", "push notifications")
        assert "Push Notifications" in impl_result
        assert "Services/NotificationService.swift" in impl_result

        # Step 2: Read each key file mentioned in the response
        content1 = workflow_tools.get_file_content(
            "test-repo-123", "Services/NotificationService.swift"
        )
        assert "class NotificationService" in content1
        assert "subscribe(topic:" in content1

        content2 = workflow_tools.get_file_content("test-repo-123", "AppDelegate.swift")
        assert "class AppDelegate" in content2

    def test_where_to_put_then_list_and_read_files(self, workflow_tools):
        """Workflow: where_to_put → list_source_files → get_file_content."""
        # Step 1: Ask where to put a service
        location_result = workflow_tools.where_to_put("test-repo-123", "service")
        assert "src/application/services" in location_result

        # Step 2: List available source files
        file_list = workflow_tools.list_source_files("test-repo-123")
        assert "src/application/services/user_service.py" in file_list

        # Step 3: Read a file from that directory
        content = workflow_tools.get_file_content(
            "test-repo-123", "src/application/services/user_service.py"
        )
        assert "class UserService" in content

    def test_how_to_implement_files_not_available(self, workflow_tools):
        """Graceful error when key files from how_to_implement don't exist on disk."""
        # Step 1: Get implementation details for map display
        impl_result = workflow_tools.how_to_implement("test-repo-123", "map display")
        assert "Map Display" in impl_result
        assert "Controllers/MapViewController.swift" in impl_result

        # Step 2: Try to read a file that does NOT exist
        error_result = workflow_tools.get_file_content(
            "test-repo-123", "NonExistent/FakeFile.swift"
        )
        assert "not found" in error_result.lower()

    def test_two_step_capability_lookup(self, workflow_tools):
        """Full two-step flow: list_implementations → how_to_implement_by_id → get_file_content."""
        # Step 1: List all capabilities
        caps = workflow_tools.list_implementations("test-repo-123")
        assert "push-notifications" in caps
        assert "map-display" in caps

        # Step 2: Get full details by exact ID
        details = workflow_tools.how_to_implement_by_id("test-repo-123", "push-notifications")
        assert "Push Notifications" in details
        assert "Services/NotificationService.swift" in details

        # Step 3: Read the key file
        content = workflow_tools.get_file_content(
            "test-repo-123", "Services/NotificationService.swift"
        )
        assert "class NotificationService" in content

    def test_two_step_flow_nonexistent_capability(self, workflow_tools):
        """Two-step flow with bad ID: graceful error with available IDs."""
        # Step 1: List capabilities
        caps = workflow_tools.list_implementations("test-repo-123")
        assert "push-notifications" in caps

        # Step 2: Try a bad ID
        result = workflow_tools.how_to_implement_by_id("test-repo-123", "nonexistent-feature")
        assert "No implementation guideline found" in result
        assert "push-notifications" in result
        assert "map-display" in result
        assert "list_implementations" in result


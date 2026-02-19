"""Tests for agent file generator functions.

The agent file generator now uses standalone functions that derive
CLAUDE.md, Cursor rules, and AGENTS.md from a StructuredBlueprint.
"""
import pytest

from domain.entities.blueprint import (
    ArchitecturalDecision,
    ArchitectureRules,
    ImplementationGuideline,
    BlueprintMeta,
    Communication,
    CommunicationPattern,
    Component,
    Components,
    Decisions,
    ErrorMapping,
    FilePlacementRule,
    NamingConvention,
    PatternGuideline,
    QuickReference,
    StructuredBlueprint,
    TechStackEntry,
    Technology,
)
from application.services.agent_file_generator import (
    generate_agents_md,
    generate_claude_md,
    generate_cursor_rules,
)


@pytest.fixture
def sample_blueprint() -> StructuredBlueprint:
    """Create a realistic StructuredBlueprint for testing."""
    return StructuredBlueprint(
        meta=BlueprintMeta(
            repository="acme/backend-api",
            repository_id="repo-uuid-123",
            architecture_style="Layered (Clean Architecture)",
        ),
        architecture_rules=ArchitectureRules(
            file_placement_rules=[
                FilePlacementRule(
                    component_type="Service",
                    naming_pattern="*_service.py",
                    location="src/application/services/",
                    example="user_service.py",
                ),
                FilePlacementRule(
                    component_type="Repository",
                    naming_pattern="*_repository.py",
                    location="src/infrastructure/persistence/",
                    example="user_repository.py",
                ),
            ],
            naming_conventions=[
                NamingConvention(
                    scope="classes",
                    pattern="PascalCase",
                    examples=["UserService", "AnalysisRepository"],
                ),
                NamingConvention(
                    scope="files",
                    pattern="snake_case",
                    examples=["user_service.py", "analysis_repo.py"],
                ),
            ],
        ),
        decisions=Decisions(
            architectural_style=ArchitecturalDecision(
                title="Architecture Style",
                chosen="Layered (Clean Architecture)",
                rationale="Separation of concerns with dependency inversion.",
            ),
            key_decisions=[
                ArchitecturalDecision(
                    title="Database Access",
                    chosen="Repository Pattern",
                    rationale="Decouple domain from infrastructure.",
                ),
            ],
        ),
        components=Components(
            structure_type="layered",
            components=[
                Component(
                    name="Presentation",
                    location="src/api/",
                    responsibility="HTTP request handling",
                    depends_on=["Application"],
                ),
                Component(
                    name="Application",
                    location="src/application/",
                    responsibility="Business logic orchestration",
                    depends_on=["Domain"],
                ),
                Component(
                    name="Domain",
                    location="src/domain/",
                    responsibility="Core business entities and interfaces",
                    depends_on=[],
                ),
            ],
        ),
        communication=Communication(
            patterns=[
                CommunicationPattern(
                    name="Sync HTTP",
                    when_to_use="Standard request/response",
                    how_it_works="FastAPI routes call services synchronously",
                ),
            ],
            pattern_selection_guide=[
                PatternGuideline(
                    scenario="CRUD operations",
                    pattern="Sync HTTP",
                    rationale="Simple and direct",
                ),
            ],
        ),
        quick_reference=QuickReference(
            where_to_put_code={
                "Service": "src/application/services/",
                "Route": "src/api/routes/",
                "Entity": "src/domain/entities/",
            },
            error_mapping=[
                ErrorMapping(error="NotFoundError", status_code=404),
                ErrorMapping(error="ValidationError", status_code=422),
            ],
        ),
        technology=Technology(
            stack=[
                TechStackEntry(category="runtime", name="Python", version="3.13", purpose="Runtime"),
                TechStackEntry(category="framework", name="FastAPI", version="0.104", purpose="Web framework"),
            ],
        ),
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


@pytest.fixture
def minimal_blueprint() -> StructuredBlueprint:
    """A minimal blueprint with almost no data to test edge cases."""
    return StructuredBlueprint(
        meta=BlueprintMeta(repository="minimal/repo"),
    )


# ── CLAUDE.md tests ──────────────────────────────────────────────────────────


class TestGenerateClaudeMd:
    """Tests for generate_claude_md()."""

    def test_contains_header(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "# CLAUDE.md" in content

    def test_contains_repo_name(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "acme/backend-api" in content

    def test_contains_architecture_style(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "Layered (Clean Architecture)" in content

    def test_contains_file_placement(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "## File Placement" in content
        assert "Service" in content
        assert "src/application/services/" in content

    def test_contains_where_to_put_code(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "## Where to Put Code" in content
        assert "Service" in content
        assert "Route" in content
        assert "Entity" in content

    def test_contains_naming_conventions(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "## Naming Conventions" in content
        assert "PascalCase" in content
        assert "snake_case" in content

    def test_contains_pattern_selection(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "## Pattern Selection" in content
        assert "CRUD operations" in content

    def test_contains_error_mapping(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "## Error Mapping" in content
        assert "NotFoundError" in content
        assert "404" in content

    def test_contains_mandatory_mcp_section(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "## Architecture MCP Server (MANDATORY)" in content
        assert "`architecture-blueprints`" in content
        assert "where_to_put" in content
        assert "check_naming" in content
        assert "get_repository_blueprint" in content
        assert "single source of truth" in content

    def test_contains_mcp_rejection_rule(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "do NOT proceed" in content

    def test_contains_how_to_implement_tool(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "how_to_implement" in content

    def test_contains_list_implementations_tool(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "list_implementations" in content

    def test_contains_how_to_implement_by_id_tool(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "how_to_implement_by_id" in content

    def test_contains_file_content_tools(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "get_file_content" in content
        assert "list_source_files" in content

    def test_contains_workflow_instructions(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "### Recommended Workflow" in content
        assert "Call `list_implementations`" in content
        assert "call `get_file_content`" in content

    def test_minimal_blueprint_still_generates(self, minimal_blueprint):
        content = generate_claude_md(minimal_blueprint)
        assert "# CLAUDE.md" in content
        assert "minimal/repo" in content
        # Should not crash on empty sections
        assert len(content) > 50


# ── Cursor Rules tests ───────────────────────────────────────────────────────


class TestGenerateCursorRules:
    """Tests for generate_cursor_rules()."""

    def test_contains_yaml_frontmatter(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        lines = content.split("\n")
        assert lines[0] == "---"
        # Find the closing ---
        closing = [i for i, line in enumerate(lines[1:], 1) if line == "---"]
        assert len(closing) >= 1, "Missing closing YAML frontmatter"

    def test_contains_description(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "description:" in content
        assert "acme/backend-api" in content

    def test_contains_globs(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "globs:" in content
        # Python detected from tech stack
        assert "**/*.py" in content

    def test_contains_components(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "## Components" in content
        assert "Presentation" in content
        assert "Application" in content
        assert "Domain" in content

    def test_contains_file_placement(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "## File Placement" in content
        assert "src/application/services/" in content

    def test_contains_naming_conventions(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "## Naming Conventions" in content

    def test_contains_communication_patterns(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "## Communication Patterns" in content
        assert "Sync HTTP" in content

    def test_contains_all_mcp_tools(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "where_to_put" in content
        assert "check_naming" in content
        assert "how_to_implement" in content
        assert "list_implementations" in content
        assert "how_to_implement_by_id" in content
        assert "get_file_content" in content
        assert "list_source_files" in content
        assert "get_repository_blueprint" in content

    def test_minimal_blueprint_still_generates(self, minimal_blueprint):
        content = generate_cursor_rules(minimal_blueprint)
        assert "---" in content
        assert "globs:" in content
        assert len(content) > 30


# ── AGENTS.md tests ──────────────────────────────────────────────────────────


class TestGenerateAgentsMd:
    """Tests for generate_agents_md()."""

    def test_contains_header(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "# AGENTS.md" in content

    def test_contains_repo_name(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "acme/backend-api" in content

    def test_contains_repository_id(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "repo-uuid-123" in content

    def test_contains_blueprint_summary(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Blueprint Summary" in content
        assert "Layered (Clean Architecture)" in content

    def test_contains_agent_roles(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Agent Roles" in content
        assert "Architecture Analysis Agent" in content
        assert "Code Generation Agent" in content
        assert "Validation Agent" in content

    def test_contains_mandatory_mcp_section(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Architecture MCP Server (MANDATORY)" in content
        assert "`architecture-blueprints`" in content
        assert "where_to_put" in content
        assert "check_naming" in content
        assert "do NOT proceed" in content

    def test_contains_file_placement_instructions(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "CLAUDE.md" in content
        assert "AGENTS.md" in content

    def test_minimal_blueprint_still_generates(self, minimal_blueprint):
        content = generate_agents_md(minimal_blueprint)
        assert "# AGENTS.md" in content
        assert "Agent Roles" in content
        assert len(content) > 100

    def test_contains_all_mcp_tools(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "where_to_put" in content
        assert "check_naming" in content
        assert "how_to_implement" in content
        assert "list_implementations" in content
        assert "how_to_implement_by_id" in content
        assert "get_file_content" in content
        assert "list_source_files" in content
        assert "get_repository_blueprint" in content

    def test_summary_includes_rule_counts(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        # Should mention count of components
        assert "Components: 3" in content


# ── Glob detection tests ─────────────────────────────────────────────────────


class TestGlobDetection:
    """Tests for glob pattern detection from technology stack."""

    def test_python_detected(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "**/*.py" in content

    def test_react_detected(self):
        bp = StructuredBlueprint(
            technology=Technology(
                stack=[TechStackEntry(category="framework", name="React", version="18", purpose="UI")],
            ),
        )
        content = generate_cursor_rules(bp)
        assert "**/*.tsx" in content or "**/*.jsx" in content

    def test_fallback_glob_when_no_tech(self):
        bp = StructuredBlueprint()
        content = generate_cursor_rules(bp)
        assert "**/*" in content

    def test_multiple_languages_detected(self):
        bp = StructuredBlueprint(
            technology=Technology(
                stack=[
                    TechStackEntry(category="runtime", name="Python", version="3.13", purpose="Runtime"),
                    TechStackEntry(category="runtime", name="TypeScript", version="5", purpose="Frontend"),
                ],
            ),
        )
        content = generate_cursor_rules(bp)
        assert "**/*.py" in content
        assert "**/*.ts" in content


# ── Implementation Guidelines tests ─────────────────────────────────────────


class TestImplementationGuidelinesInClaudeMd:
    """Tests for implementation guidelines in CLAUDE.md."""

    def test_contains_heading(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "## Implementation Guidelines" in content

    def test_contains_capabilities(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "Push Notifications" in content
        assert "Map Display" in content

    def test_contains_libraries(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "Firebase Cloud Messaging 10.x" in content
        assert "Mapbox Maps SDK 10.x" in content

    def test_contains_key_files(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "Services/NotificationService.swift" in content

    def test_contains_pattern(self, sample_blueprint):
        content = generate_claude_md(sample_blueprint)
        assert "FCM topic-based subscriptions" in content

    def test_omitted_when_empty(self, minimal_blueprint):
        content = generate_claude_md(minimal_blueprint)
        assert "Implementation Guidelines" not in content


class TestImplementationGuidelinesInCursorRules:
    """Tests for implementation guidelines in Cursor rules."""

    def test_contains_section_heading(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "## Implementation Guidelines" in content

    def test_contains_capabilities(self, sample_blueprint):
        content = generate_cursor_rules(sample_blueprint)
        assert "Push Notifications" in content
        assert "Map Display" in content

    def test_omitted_when_empty(self, minimal_blueprint):
        content = generate_cursor_rules(minimal_blueprint)
        assert "Implementation Guidelines" not in content


class TestImplementationGuidelinesInAgentsMd:
    """Tests for implementation guidelines in AGENTS.md."""

    def test_count_shows_in_summary(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "Implementation guidelines: 2" in content

    def test_no_count_when_empty(self, minimal_blueprint):
        content = generate_agents_md(minimal_blueprint)
        assert "Implementation guidelines:" not in content

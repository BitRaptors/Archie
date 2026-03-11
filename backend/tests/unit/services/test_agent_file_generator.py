"""Tests for agent file generator functions.

Covers the topic-split rule file model, individual topic builders,
the lean root CLAUDE.md, the generate_all() orchestrator, and
backward-compatible public API wrappers.
"""
import pytest

from domain.entities.blueprint import (
    ArchitecturalDecision,
    ArchitectureRules,
    BlueprintMeta,
    Communication,
    CommunicationPattern,
    Component,
    Components,
    DataFetchingPattern,
    Decisions,
    DeveloperRecipe,
    DevelopmentRule,
    ErrorMapping,
    FilePlacementRule,
    Frontend,
    ImplementationGuideline,
    NamingConvention,
    ArchitecturalPitfall,
    PatternGuideline,
    QuickReference,
    StateManagement,
    StructuredBlueprint,
    TechStackEntry,
    Technology,
    UIComponent,
)
from application.services.agent_file_generator import (
    RuleFile,
    GeneratedOutput,
    generate_all,
    generate_agents_md,
    generate_claude_md_lean,
    _build_architecture_rule,
    _build_patterns_rule,
    _build_frontend_rule,
    _build_mcp_tools_rule,
    _build_recipes_rule,
    _build_pitfalls_rule,
    _build_dev_rules_rule,
    _detect_frontend_globs,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_blueprint() -> StructuredBlueprint:
    """Create a realistic StructuredBlueprint for testing."""
    return StructuredBlueprint(
        meta=BlueprintMeta(
            repository="acme/backend-api",
            repository_id="repo-uuid-123",
            architecture_style="Layered (Clean Architecture)",
            executive_summary="A backend API built with Python FastAPI using Clean Architecture patterns.",
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
            run_commands={
                "dev": "uvicorn main:app --reload --port 8000",
                "test": "pytest tests/ -v",
            },
        ),
        developer_recipes=[
            DeveloperRecipe(
                task="Add a new API endpoint",
                files=["src/api/routes/new_route.py", "src/api/app.py"],
                steps=["Create route file", "Register in app.py", "Add tests"],
            ),
        ],
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
        pitfalls=[
            ArchitecturalPitfall(
                area="Dependency Injection",
                description="Don't instantiate services directly; use the container.",
                recommendation="Always inject via constructor.",
            ),
        ],
        development_rules=[
            DevelopmentRule(
                category="dependency_management",
                rule="Always use pip with requirements.txt for dependency management",
                source="requirements.txt",
            ),
            DevelopmentRule(
                category="testing",
                rule="Always run pytest with PYTHONPATH=src",
                source="pytest.ini",
            ),
            DevelopmentRule(
                category="code_style",
                rule="Always use ruff for linting",
                source="ruff.toml",
            ),
        ],
    )


@pytest.fixture
def minimal_blueprint() -> StructuredBlueprint:
    """A minimal blueprint with almost no data to test edge cases."""
    return StructuredBlueprint(
        meta=BlueprintMeta(repository="minimal/repo"),
    )


@pytest.fixture
def fullstack_blueprint() -> StructuredBlueprint:
    """A blueprint with frontend data for testing frontend rule generation."""
    return StructuredBlueprint(
        meta=BlueprintMeta(
            repository="acme/fullstack-app",
            repository_id="repo-uuid-456",
            architecture_style="Full-Stack (Next.js + FastAPI)",
        ),
        technology=Technology(
            stack=[
                TechStackEntry(category="framework", name="Next.js", version="14", purpose="Frontend framework"),
                TechStackEntry(category="framework", name="React", version="18", purpose="UI library"),
                TechStackEntry(category="runtime", name="Python", version="3.13", purpose="Backend runtime"),
            ],
        ),
        frontend=Frontend(
            framework="Next.js 14",
            rendering_strategy="SSR + SSG hybrid",
            styling="Tailwind CSS",
            state_management=StateManagement(
                approach="React Query + Context",
                server_state="TanStack Query",
                local_state="useState",
            ),
            key_conventions=[
                "Use Server Components by default",
                "Client Components only when needed for interactivity",
            ],
            ui_components=[
                UIComponent(name="Dashboard", location="app/dashboard/page.tsx", component_type="page"),
            ],
            data_fetching=[
                DataFetchingPattern(name="Server fetch", mechanism="RSC async fetch", when_to_use="Initial page load"),
            ],
        ),
        components=Components(
            structure_type="layered",
            components=[
                Component(name="Frontend", location="frontend/", responsibility="UI layer"),
                Component(name="Backend", location="backend/", responsibility="API layer"),
            ],
        ),
    )


# ---------------------------------------------------------------------------
# RuleFile tests
# ---------------------------------------------------------------------------

class TestRuleFile:
    """Tests for RuleFile rendering."""

    def test_claude_path(self):
        rf = RuleFile(topic="architecture", body="test")
        assert rf.claude_path == ".claude/rules/architecture.md"

    def test_cursor_path(self):
        rf = RuleFile(topic="patterns", body="test")
        assert rf.cursor_path == ".cursor/rules/patterns.md"

    def test_render_claude_no_globs(self):
        rf = RuleFile(topic="architecture", body="## Components\nSome content")
        rendered = rf.render_claude()
        # No frontmatter when no globs
        assert rendered == "## Components\nSome content"
        assert "---" not in rendered

    def test_render_claude_with_globs(self):
        rf = RuleFile(topic="frontend", body="## Frontend", globs=["**/*.tsx", "**/*.jsx"])
        rendered = rf.render_claude()
        assert rendered.startswith("---\npaths:")
        assert "**/*.tsx" in rendered
        assert "**/*.jsx" in rendered
        assert "## Frontend" in rendered

    def test_render_cursor_always_apply(self):
        rf = RuleFile(
            topic="architecture",
            body="## Content",
            description="Arch rules",
            always_apply=True,
        )
        rendered = rf.render_cursor()
        assert "---" in rendered
        assert "description: Arch rules" in rendered
        assert "alwaysApply: true" in rendered
        assert "## Content" in rendered

    def test_render_cursor_with_globs(self):
        rf = RuleFile(
            topic="frontend",
            body="## Frontend",
            description="Frontend rules",
            always_apply=False,
            globs=["**/*.tsx"],
        )
        rendered = rf.render_cursor()
        assert "globs:" in rendered
        assert '"**/*.tsx"' in rendered
        assert "alwaysApply: false" in rendered

    def test_render_cursor_no_globs_not_always(self):
        rf = RuleFile(
            topic="test",
            body="body",
            description="desc",
            always_apply=False,
        )
        rendered = rf.render_cursor()
        assert "alwaysApply: false" in rendered
        assert "globs:" not in rendered


# ---------------------------------------------------------------------------
# GeneratedOutput tests
# ---------------------------------------------------------------------------

class TestGeneratedOutput:
    """Tests for GeneratedOutput.to_file_map()."""

    def test_to_file_map_includes_all_files(self):
        rf1 = RuleFile(topic="architecture", body="arch content", description="Arch")
        rf2 = RuleFile(topic="patterns", body="patterns content", description="Pat")
        output = GeneratedOutput(
            claude_md="# CLAUDE.md",
            agents_md="# AGENTS.md",
            rule_files=[rf1, rf2],
        )
        file_map = output.to_file_map()
        assert "CLAUDE.md" in file_map
        assert "AGENTS.md" in file_map
        assert ".claude/rules/architecture.md" in file_map
        assert ".cursor/rules/architecture.md" in file_map
        assert ".claude/rules/patterns.md" in file_map
        assert ".cursor/rules/patterns.md" in file_map

    def test_to_file_map_empty_rules(self):
        output = GeneratedOutput(claude_md="md", agents_md="agents")
        file_map = output.to_file_map()
        assert len(file_map) == 2


# ---------------------------------------------------------------------------
# generate_all() tests
# ---------------------------------------------------------------------------

class TestGenerateAll:
    """Tests for the generate_all() orchestrator."""

    def test_produces_generated_output(self, sample_blueprint):
        output = generate_all(sample_blueprint)
        assert isinstance(output, GeneratedOutput)
        assert output.claude_md
        assert output.agents_md
        assert len(output.rule_files) > 0

    def test_expected_topics_present(self, sample_blueprint):
        output = generate_all(sample_blueprint)
        topics = {rf.topic for rf in output.rule_files}
        assert "architecture" in topics
        assert "patterns" in topics
        assert "mcp-tools" in topics
        assert "recipes" in topics
        assert "pitfalls" in topics
        assert "dev-rules" in topics

    def test_frontend_conditional_absent(self, sample_blueprint):
        output = generate_all(sample_blueprint)
        topics = {rf.topic for rf in output.rule_files}
        assert "frontend" not in topics

    def test_frontend_conditional_present(self, fullstack_blueprint):
        output = generate_all(fullstack_blueprint)
        topics = {rf.topic for rf in output.rule_files}
        assert "frontend" in topics

    def test_minimal_blueprint_produces_output(self, minimal_blueprint):
        output = generate_all(minimal_blueprint)
        assert output.claude_md
        assert output.agents_md
        # mcp-tools always present
        topics = {rf.topic for rf in output.rule_files}
        assert "mcp-tools" in topics

    def test_file_map_contains_claude_and_cursor_rules(self, sample_blueprint):
        output = generate_all(sample_blueprint)
        file_map = output.to_file_map()
        claude_rules = [p for p in file_map if p.startswith(".claude/rules/")]
        cursor_rules = [p for p in file_map if p.startswith(".cursor/rules/")]
        assert len(claude_rules) == len(cursor_rules)
        assert len(claude_rules) > 0


# ---------------------------------------------------------------------------
# Lean CLAUDE.md tests
# ---------------------------------------------------------------------------

class TestLeanClaudeMd:
    """Tests for generate_claude_md_lean()."""

    def test_under_120_lines(self, sample_blueprint):
        content = generate_claude_md_lean(sample_blueprint)
        line_count = len(content.split("\n"))
        assert line_count <= 120, f"Lean CLAUDE.md has {line_count} lines (max 120)"

    def test_contains_header(self, sample_blueprint):
        content = generate_claude_md_lean(sample_blueprint)
        assert "# CLAUDE.md" in content

    def test_contains_repo_name(self, sample_blueprint):
        content = generate_claude_md_lean(sample_blueprint)
        assert "acme/backend-api" in content

    def test_contains_architecture_style(self, sample_blueprint):
        content = generate_claude_md_lean(sample_blueprint)
        assert "Layered (Clean Architecture)" in content

    def test_contains_commands(self, sample_blueprint):
        content = generate_claude_md_lean(sample_blueprint)
        assert "## Commands" in content
        assert "uvicorn" in content
        assert "pytest" in content

    def test_references_rules_dir(self, sample_blueprint):
        content = generate_claude_md_lean(sample_blueprint)
        assert ".claude/rules/" in content
        assert "dev-rules.md" in content

    def test_contains_mcp_mandatory_note(self, sample_blueprint):
        content = generate_claude_md_lean(sample_blueprint)
        assert "MCP Server (MANDATORY)" in content
        assert "where_to_put" in content
        assert "check_naming" in content

    def test_no_commands_when_empty(self, minimal_blueprint):
        content = generate_claude_md_lean(minimal_blueprint)
        assert "## Commands" not in content

    def test_minimal_still_generates(self, minimal_blueprint):
        content = generate_claude_md_lean(minimal_blueprint)
        assert "# CLAUDE.md" in content
        assert "minimal/repo" in content
        assert len(content) > 50


# ---------------------------------------------------------------------------
# Architecture rule tests
# ---------------------------------------------------------------------------

class TestArchitectureRule:
    """Tests for _build_architecture_rule()."""

    def test_contains_components(self, sample_blueprint):
        rf = _build_architecture_rule(sample_blueprint)
        assert rf is not None
        assert "Presentation" in rf.body
        assert "Application" in rf.body
        assert "Domain" in rf.body

    def test_contains_file_placement(self, sample_blueprint):
        rf = _build_architecture_rule(sample_blueprint)
        assert "File Placement" in rf.body
        assert "src/application/services/" in rf.body

    def test_contains_naming(self, sample_blueprint):
        rf = _build_architecture_rule(sample_blueprint)
        assert "Naming Conventions" in rf.body
        assert "PascalCase" in rf.body
        assert "snake_case" in rf.body

    def test_contains_where_to_put(self, sample_blueprint):
        rf = _build_architecture_rule(sample_blueprint)
        assert "Where to Put Code" in rf.body

    def test_none_when_empty(self, minimal_blueprint):
        rf = _build_architecture_rule(minimal_blueprint)
        assert rf is None


# ---------------------------------------------------------------------------
# Patterns rule tests
# ---------------------------------------------------------------------------

class TestPatternsRule:
    """Tests for _build_patterns_rule()."""

    def test_contains_communication_patterns(self, sample_blueprint):
        rf = _build_patterns_rule(sample_blueprint)
        assert rf is not None
        assert "Sync HTTP" in rf.body

    def test_contains_pattern_selection(self, sample_blueprint):
        rf = _build_patterns_rule(sample_blueprint)
        assert "CRUD operations" in rf.body

    def test_contains_decisions(self, sample_blueprint):
        rf = _build_patterns_rule(sample_blueprint)
        assert "Database Access" in rf.body
        assert "Repository Pattern" in rf.body

    def test_none_when_empty(self, minimal_blueprint):
        rf = _build_patterns_rule(minimal_blueprint)
        assert rf is None


# ---------------------------------------------------------------------------
# Frontend rule tests
# ---------------------------------------------------------------------------

class TestFrontendRule:
    """Tests for _build_frontend_rule()."""

    def test_none_when_no_frontend(self, sample_blueprint):
        rf = _build_frontend_rule(sample_blueprint)
        assert rf is None

    def test_present_when_frontend(self, fullstack_blueprint):
        rf = _build_frontend_rule(fullstack_blueprint)
        assert rf is not None
        assert "Next.js 14" in rf.body
        assert "Tailwind CSS" in rf.body

    def test_has_globs(self, fullstack_blueprint):
        rf = _build_frontend_rule(fullstack_blueprint)
        assert rf.globs
        assert "**/*.tsx" in rf.globs or "**/*.jsx" in rf.globs

    def test_not_always_apply(self, fullstack_blueprint):
        rf = _build_frontend_rule(fullstack_blueprint)
        assert rf.always_apply is False

    def test_state_management(self, fullstack_blueprint):
        rf = _build_frontend_rule(fullstack_blueprint)
        assert "React Query + Context" in rf.body

    def test_conventions(self, fullstack_blueprint):
        rf = _build_frontend_rule(fullstack_blueprint)
        assert "Server Components" in rf.body


# ---------------------------------------------------------------------------
# MCP Tools rule tests
# ---------------------------------------------------------------------------

class TestMcpToolsRule:
    """Tests for _build_mcp_tools_rule()."""

    def test_all_tools_present(self, sample_blueprint):
        rf = _build_mcp_tools_rule(sample_blueprint)
        assert rf is not None
        assert "where_to_put" in rf.body
        assert "check_naming" in rf.body
        assert "list_implementations" in rf.body
        assert "how_to_implement_by_id" in rf.body
        assert "how_to_implement" in rf.body
        assert "get_file_content" in rf.body
        assert "list_source_files" in rf.body
        assert "get_repository_blueprint" in rf.body

    def test_always_generated(self, minimal_blueprint):
        rf = _build_mcp_tools_rule(minimal_blueprint)
        assert rf is not None

    def test_contains_rejection_rule(self, sample_blueprint):
        rf = _build_mcp_tools_rule(sample_blueprint)
        assert "do NOT proceed" in rf.body

    def test_compact_size(self, sample_blueprint):
        rf = _build_mcp_tools_rule(sample_blueprint)
        line_count = len(rf.body.split("\n"))
        assert line_count <= 30, f"MCP tools rule has {line_count} lines (should be compact)"


# ---------------------------------------------------------------------------
# Recipes rule tests
# ---------------------------------------------------------------------------

class TestRecipesRule:
    """Tests for _build_recipes_rule()."""

    def test_contains_implementation_guidelines(self, sample_blueprint):
        rf = _build_recipes_rule(sample_blueprint)
        assert rf is not None
        assert "Push Notifications" in rf.body
        assert "Map Display" in rf.body

    def test_contains_libraries(self, sample_blueprint):
        rf = _build_recipes_rule(sample_blueprint)
        assert "Firebase Cloud Messaging 10.x" in rf.body

    def test_contains_key_files(self, sample_blueprint):
        rf = _build_recipes_rule(sample_blueprint)
        assert "Services/NotificationService.swift" in rf.body

    def test_none_when_empty(self, minimal_blueprint):
        rf = _build_recipes_rule(minimal_blueprint)
        assert rf is None

    def test_contains_developer_recipes(self):
        bp = StructuredBlueprint(
            developer_recipes=[
                DeveloperRecipe(
                    task="Add a new API endpoint",
                    files=["src/api/routes/new_route.py"],
                    steps=["Create route file", "Register in app.py"],
                ),
            ],
        )
        rf = _build_recipes_rule(bp)
        assert rf is not None
        assert "Add a new API endpoint" in rf.body
        assert "Create route file" in rf.body


# ---------------------------------------------------------------------------
# Pitfalls rule tests
# ---------------------------------------------------------------------------

class TestPitfallsRule:
    """Tests for _build_pitfalls_rule()."""

    def test_contains_pitfalls(self, sample_blueprint):
        rf = _build_pitfalls_rule(sample_blueprint)
        assert rf is not None
        assert "Dependency Injection" in rf.body
        assert "Don't instantiate services directly" in rf.body

    def test_contains_error_mapping(self, sample_blueprint):
        rf = _build_pitfalls_rule(sample_blueprint)
        assert "NotFoundError" in rf.body
        assert "404" in rf.body

    def test_none_when_empty(self, minimal_blueprint):
        rf = _build_pitfalls_rule(minimal_blueprint)
        assert rf is None


# ---------------------------------------------------------------------------
# Dev rules rule tests
# ---------------------------------------------------------------------------

class TestDevRulesRule:
    """Tests for _build_dev_rules_rule()."""

    def test_contains_rules(self, sample_blueprint):
        rf = _build_dev_rules_rule(sample_blueprint)
        assert rf is not None
        assert rf.topic == "dev-rules"
        assert "Always use ruff for linting" in rf.body
        assert "Always run pytest with PYTHONPATH=src" in rf.body

    def test_groups_by_category(self, sample_blueprint):
        rf = _build_dev_rules_rule(sample_blueprint)
        assert "### Dependency Management" in rf.body
        assert "### Testing" in rf.body
        assert "### Code Style" in rf.body

    def test_includes_source_citations(self, sample_blueprint):
        rf = _build_dev_rules_rule(sample_blueprint)
        assert "ruff.toml" in rf.body
        assert "pytest.ini" in rf.body

    def test_none_when_empty(self, minimal_blueprint):
        rf = _build_dev_rules_rule(minimal_blueprint)
        assert rf is None


# ---------------------------------------------------------------------------
# Frontend glob detection tests
# ---------------------------------------------------------------------------

class TestFrontendGlobDetection:
    """Tests for _detect_frontend_globs()."""

    def test_nextjs_globs(self, fullstack_blueprint):
        globs = _detect_frontend_globs(fullstack_blueprint)
        assert "**/*.tsx" in globs or "**/*.jsx" in globs

    def test_vue_globs(self):
        bp = StructuredBlueprint(
            frontend=Frontend(framework="Vue 3"),
        )
        globs = _detect_frontend_globs(bp)
        assert "**/*.vue" in globs

    def test_flutter_globs(self):
        bp = StructuredBlueprint(
            frontend=Frontend(framework="Flutter"),
        )
        globs = _detect_frontend_globs(bp)
        assert "**/*.dart" in globs

    def test_fallback_when_unknown(self):
        bp = StructuredBlueprint(
            frontend=Frontend(framework="SomeUnknownFramework"),
        )
        globs = _detect_frontend_globs(bp)
        assert globs == ["**/*"]


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# AGENTS.md tests
# ---------------------------------------------------------------------------

class TestGenerateAgentsMd:
    """Tests for generate_agents_md()."""

    def test_contains_header(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "# AGENTS.md" in content

    def test_contains_repo_name(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "acme/backend-api" in content

    def test_contains_agent_guidance_subtitle(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "Agent guidance" in content

    def test_contains_overview(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "backend API" in content

    def test_contains_commands(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Commands" in content
        assert "uvicorn" in content

    def test_contains_development_rules(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Development Rules" in content
        assert "Always use ruff for linting" in content

    def test_contains_common_workflows(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Common Workflows" in content
        assert "Add a new API endpoint" in content

    def test_contains_pitfalls_and_gotchas(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Pitfalls & Gotchas" in content
        assert "Dependency Injection" in content

    def test_contains_mcp_section(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Archie MCP Server" in content
        assert "where_to_put" in content
        assert "check_naming" in content

    def test_contains_key_mcp_tools(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "where_to_put" in content
        assert "check_naming" in content
        assert "how_to_implement" in content
        assert "list_implementations" in content
        assert "how_to_implement_by_id" in content
        assert "get_file_content" in content

    def test_contains_boundaries(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Boundaries" in content
        assert "### Always" in content
        assert "### Ask First" in content
        assert "### Never" in content
        assert "Commit secrets" in content

    def test_contains_tech_stack(self, sample_blueprint):
        content = generate_agents_md(sample_blueprint)
        assert "## Tech Stack" in content

    def test_minimal_blueprint_still_generates(self, minimal_blueprint):
        content = generate_agents_md(minimal_blueprint)
        assert "# AGENTS.md" in content
        assert "Archie MCP Server" in content
        assert len(content) > 100

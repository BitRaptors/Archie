"""Tests for blueprint_renderer.py — new sections, skip-if-empty, formatting fixes."""
import pytest

from domain.entities.blueprint import (
    ArchitecturalDecision,
    ArchitecturalPitfall,
    ArchitectureRules,
    BlueprintMeta,
    CodeTemplate,
    Communication,
    CommunicationPattern,
    Component,
    Components,
    Contract,
    Decisions,
    DeveloperRecipe,
    ErrorMapping,
    FilePlacementRule,
    Frontend,
    ImplementationGuideline,
    NamingConvention,
    PatternGuideline,
    QuickReference,
    Route,
    StructuredBlueprint,
    TechStackEntry,
    Technology,
    TradeOff,
    UIComponent,
)
from application.services.blueprint_renderer import render_blueprint_markdown


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def rich_blueprint() -> StructuredBlueprint:
    """Blueprint with all new fields populated."""
    return StructuredBlueprint(
        meta=BlueprintMeta(
            repository="acme/rich-app",
            repository_id="repo-uuid-rich",
            architecture_style="Clean Architecture with DDD",
            platforms=["backend"],
            executive_summary="A Python FastAPI backend implementing Clean Architecture. Uses dependency injection via dependency-injector. Stores data in Supabase PostgreSQL with pgvector for embeddings.",
        ),
        architecture_rules=ArchitectureRules(
            file_placement_rules=[
                FilePlacementRule(
                    component_type="Service",
                    naming_pattern="*_service.py",
                    location="src/application/services/",
                    example="user_service.py",
                ),
            ],
            naming_conventions=[
                NamingConvention(
                    scope="classes",
                    pattern="PascalCase",
                    examples=["UserService", "AnalysisRepo"],
                ),
            ],
        ),
        decisions=Decisions(
            architectural_style=ArchitecturalDecision(
                title="Architecture Style",
                chosen="Clean Architecture",
                rationale="Separation of concerns with dependency inversion.",
                alternatives_rejected=["MVC", "Hexagonal"],
            ),
            key_decisions=[
                ArchitecturalDecision(
                    title="Database Access",
                    chosen="Repository Pattern",
                    rationale="Decouple domain from DB.",
                ),
            ],
            trade_offs=[
                TradeOff(accept="More boilerplate", benefit="Better testability"),
            ],
            out_of_scope=["Mobile app"],
        ),
        components=Components(
            structure_type="layered",
            components=[
                Component(
                    name="API Layer",
                    location="src/api/",
                    responsibility="HTTP request handling",
                    platform="backend",
                ),
            ],
            contracts=[
                Contract(
                    interface_name="RepositoryInterface",
                    description="Data access abstraction",
                    methods=["get", "save"],
                ),
                # Empty contract — should be skipped
                Contract(interface_name="", description=""),
            ],
        ),
        communication=Communication(
            patterns=[
                CommunicationPattern(
                    name="REST API",
                    when_to_use="Client-server",
                    how_it_works="HTTP JSON",
                    examples=["GET /users"],
                ),
            ],
            pattern_selection_guide=[
                PatternGuideline(
                    scenario="CRUD ops",
                    pattern="REST",
                    rationale="Simple",
                ),
            ],
        ),
        quick_reference=QuickReference(
            where_to_put_code={"Service": "src/application/services/"},
            pattern_selection={"Real-time updates": "WebSocket", "CRUD operations": "REST API"},
            error_mapping=[
                ErrorMapping(error="NotFoundError", status_code=404, description="Resource not found"),
            ],
        ),
        technology=Technology(
            stack=[
                TechStackEntry(category="runtime", name="Python", version="3.13", purpose="Runtime"),
            ],
            project_structure="src/\n  api/\n  application/\n  domain/\n  infrastructure/",
            run_commands={"dev": "uvicorn main:app --reload"},
        ),
        developer_recipes=[
            DeveloperRecipe(
                task="Add a new API endpoint",
                files=["src/api/routes/new_route.py", "src/application/services/new_service.py"],
                steps=["Create the route handler", "Create the service", "Register in app.py"],
            ),
        ],
        architecture_diagram="graph TD\n  API-->Service\n  Service-->Domain\n  Service-->Infra",
        pitfalls=[
            ArchitecturalPitfall(
                area="Database",
                description="pgvector requires the extension to be enabled before creating tables.",
                recommendation="Run CREATE EXTENSION vector; before migrations.",
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
    )


@pytest.fixture
def empty_blueprint() -> StructuredBlueprint:
    """Minimal blueprint with no optional data."""
    return StructuredBlueprint(
        meta=BlueprintMeta(repository="empty/repo"),
    )


# ── Section ordering ─────────────────────────────────────────────────────────


class TestSectionOrdering:
    """Tests that sections appear in the correct order."""

    def test_overview_is_section_1(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 1. Architecture Overview" in md

    def test_diagram_is_section_2(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 2. Architecture Diagram" in md

    def test_project_structure_is_section_3(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 3. Project Structure" in md

    def test_components_is_section_4(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 4. Components & Layers" in md

    def test_rules_is_section_5(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 5. Architecture Rules" in md

    def test_decisions_is_section_6(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 6. Key Decisions & Trade-offs" in md

    def test_communication_is_section_7(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 7. Communication Patterns" in md

    def test_implementation_guidelines_is_section_8(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 8. Implementation Guidelines" in md

    def test_recipes_is_section_9(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 9. Developer Recipes" in md

    def test_tech_stack_is_section_10(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 10. Technology Stack" in md

    def test_pitfalls_is_section_11(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 11. Pitfalls & Edge Cases" in md

    def test_quick_ref_is_section_12(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 12. Quick Reference" in md

    def test_section_order_correct(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        idx_overview = md.index("## 1. Architecture Overview")
        idx_diagram = md.index("## 2. Architecture Diagram")
        idx_structure = md.index("## 3. Project Structure")
        idx_components = md.index("## 4. Components & Layers")
        idx_rules = md.index("## 5. Architecture Rules")
        idx_decisions = md.index("## 6. Key Decisions")
        idx_comm = md.index("## 7. Communication")
        idx_impl = md.index("## 8. Implementation")
        idx_recipes = md.index("## 9. Developer Recipes")
        idx_tech = md.index("## 10. Technology Stack")
        idx_pitfalls = md.index("## 11. Pitfalls")
        idx_quick = md.index("## 12. Quick Reference")
        assert idx_overview < idx_diagram < idx_structure < idx_components < idx_rules
        assert idx_rules < idx_decisions < idx_comm < idx_impl < idx_recipes
        assert idx_recipes < idx_tech < idx_pitfalls < idx_quick


# ── Skip-if-empty ────────────────────────────────────────────────────────────


class TestSkipIfEmpty:
    """Tests that empty sections are not rendered."""

    def test_no_diagram_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Architecture Diagram" not in md

    def test_no_project_structure_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Project Structure" not in md

    def test_no_components_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Components & Layers" not in md

    def test_no_rules_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Architecture Rules" not in md

    def test_no_decisions_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Key Decisions" not in md

    def test_no_communication_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Communication Patterns" not in md

    def test_no_recipes_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Developer Recipes" not in md

    def test_no_tech_stack_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Technology Stack" not in md

    def test_no_pitfalls_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Pitfalls" not in md

    def test_no_quick_ref_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Quick Reference" not in md

    def test_no_frontend_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Frontend Architecture" not in md

    def test_no_implementation_guidelines_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Implementation Guidelines" not in md

    def test_overview_always_rendered(self, empty_blueprint):
        """Section 1 (Architecture Overview) is always rendered."""
        md = render_blueprint_markdown(empty_blueprint)
        assert "## 1. Architecture Overview" in md


# ── New field rendering ──────────────────────────────────────────────────────


class TestExecutiveSummary:
    """Tests for executive_summary rendering."""

    def test_renders_executive_summary(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "A Python FastAPI backend implementing Clean Architecture" in md

    def test_no_summary_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "A Python FastAPI" not in md


class TestArchitectureDiagram:
    """Tests for architecture_diagram rendering."""

    def test_renders_mermaid_block(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "```mermaid" in md
        assert "graph TD" in md
        assert "API-->Service" in md

    def test_renders_mermaid_live_link(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "mermaid.live/edit#pako:" in md
        assert "[Open diagram in browser]" in md

    def test_mermaid_live_link_is_decodable(self, rich_blueprint):
        """The pako-encoded URL should decode back to valid JSON containing the chart."""
        import base64
        import zlib

        md = render_blueprint_markdown(rich_blueprint)
        # Extract the URL
        for line in md.splitlines():
            if "mermaid.live/edit#pako:" in line:
                encoded = line.split("pako:")[1].rstrip(")")
                break
        else:
            pytest.fail("mermaid.live link not found")

        decoded = zlib.decompress(base64.urlsafe_b64decode(encoded)).decode("utf-8")
        assert "graph TD" in decoded
        assert "API-->Service" in decoded


class TestDeveloperRecipes:
    """Tests for developer_recipes rendering."""

    def test_renders_recipe_task(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "### Add a new API endpoint" in md

    def test_renders_recipe_files(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "`src/api/routes/new_route.py`" in md

    def test_renders_recipe_steps(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "1. Create the route handler" in md
        assert "2. Create the service" in md
        assert "3. Register in app.py" in md


class TestPitfalls:
    """Tests for pitfalls rendering."""

    def test_renders_pitfall_area(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "**Database:**" in md

    def test_renders_pitfall_description(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "pgvector requires the extension" in md

    def test_renders_pitfall_recommendation(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "CREATE EXTENSION vector" in md


class TestImplementationGuidelines:
    """Tests for implementation_guidelines rendering."""

    def test_section_heading_is_number_8(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "## 8. Implementation Guidelines" in md

    def test_section_between_communication_and_recipes(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        idx_comm = md.index("## 7. Communication")
        idx_impl = md.index("## 8. Implementation Guidelines")
        idx_recipes = md.index("## 9. Developer Recipes")
        assert idx_comm < idx_impl < idx_recipes

    def test_renders_capability_names(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "Push Notifications" in md
        assert "Map Display" in md

    def test_renders_category_grouping(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "### Notifications" in md
        assert "### Location" in md

    def test_renders_libraries(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "`Firebase Cloud Messaging 10.x`" in md
        assert "`Mapbox Maps SDK 10.x`" in md

    def test_renders_pattern_description(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "FCM topic-based subscriptions" in md

    def test_renders_key_files(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "`Services/NotificationService.swift`" in md

    def test_renders_usage_example_in_code_block(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "NotificationService.shared.subscribe" in md

    def test_renders_tips(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "Request notification permissions" in md
        assert "Limit annotations" in md

    def test_no_section_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Implementation Guidelines" not in md


# ── "Why X?" heading fix ─────────────────────────────────────────────────────


class TestDecisionsFormatting:
    """Tests that decisions use proper headings (no 'Why X?')."""

    def test_no_why_heading(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "Why Clean Architecture?" not in md
        assert "Why " not in md.split("## 6.")[1].split("## 7.")[0] if "## 7." in md else True

    def test_uses_title_heading(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        # Should use the title as heading, with Chosen below
        assert "### Architecture Style" in md
        assert "**Chosen:** Clean Architecture" in md


# ── Empty contracts skipped ──────────────────────────────────────────────────


class TestContractFiltering:
    """Tests that contracts with empty interface_name AND description are skipped."""

    def test_skips_empty_contract(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        # The non-empty contract should render
        assert "RepositoryInterface" in md

    def test_does_not_render_empty_contract_heading(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        # The "Unnamed Contract" placeholder should not appear since empty contracts are skipped
        assert "Unnamed Contract" not in md
        # Only the RepositoryInterface contract heading should be rendered
        assert md.count("#### RepositoryInterface") == 1


# ── Pattern selection rendering ──────────────────────────────────────────────


class TestPatternSelection:
    """Tests that quick_reference.pattern_selection is rendered."""

    def test_renders_pattern_selection_table(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "### Pattern Selection" in md
        assert "| Scenario | Recommended Pattern |" in md

    def test_renders_pattern_entries(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "Real-time updates" in md
        assert "WebSocket" in md
        assert "CRUD operations" in md
        assert "REST API" in md

    def test_no_pattern_selection_when_empty(self, empty_blueprint):
        md = render_blueprint_markdown(empty_blueprint)
        assert "Pattern Selection" not in md


# ── Backward compatibility ───────────────────────────────────────────────────


class TestBackwardCompatibility:
    """Tests that old blueprints (without new fields) still work."""

    def test_old_blueprint_without_new_fields(self):
        """Deserialize a blueprint dict missing new fields — should work with defaults."""
        old_data = {
            "meta": {
                "repository": "old/repo",
                "schema_version": "2.0.0",
                "architecture_style": "Layered",
            },
            "architecture_rules": {},
            "decisions": {},
            "components": {},
            "communication": {},
            "quick_reference": {},
            "technology": {},
            "frontend": {},
        }
        bp = StructuredBlueprint.model_validate(old_data)
        assert bp.meta.executive_summary == ""
        assert bp.developer_recipes == []
        assert bp.architecture_diagram == ""
        assert bp.pitfalls == []

    def test_old_blueprint_renders_without_error(self):
        old_data = {
            "meta": {"repository": "old/repo"},
        }
        bp = StructuredBlueprint.model_validate(old_data)
        md = render_blueprint_markdown(bp)
        assert "old/repo" in md
        assert "Architecture Overview" in md

    def test_old_blueprint_without_implementation_guidelines(self):
        """Old blueprint JSON without implementation_guidelines field."""
        old_data = {
            "meta": {"repository": "old/repo"},
        }
        bp = StructuredBlueprint.model_validate(old_data)
        assert bp.implementation_guidelines == []
        md = render_blueprint_markdown(bp)
        assert "Implementation Guidelines" not in md


# ── Project structure moved from technology ──────────────────────────────────


class TestProjectStructureMoved:
    """Tests that project_structure renders as section 3 not inside Technology."""

    def test_project_structure_before_components(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        idx_struct = md.index("## 3. Project Structure")
        idx_comp = md.index("## 4. Components")
        assert idx_struct < idx_comp

    def test_project_structure_not_in_technology(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        # Project structure should NOT appear under Technology section
        tech_section = md.split("## 10. Technology Stack")[1].split("## 11.")[0] if "## 10." in md else ""
        assert "Project Structure" not in tech_section


# ── Clickable file paths ─────────────────────────────────────────────────────


class TestClickableFilePaths:
    """Tests that file paths render as source:// links."""

    def test_component_key_files_are_links(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        # The rich_blueprint doesn't have key_files on components, make one
        bp = StructuredBlueprint(
            components=Components(
                components=[
                    Component(
                        name="API",
                        location="src/api/",
                        responsibility="HTTP handling",
                        key_files=[
                            {"file": "src/api/routes.py", "description": "Route definitions"},
                        ],
                    ),
                ],
            ),
        )
        md = render_blueprint_markdown(bp)
        assert "[`src/api/routes.py`](source://src/api/routes.py)" in md

    def test_component_location_is_link(self):
        bp = StructuredBlueprint(
            components=Components(
                components=[
                    Component(
                        name="API",
                        location="src/api/",
                        responsibility="HTTP handling",
                    ),
                ],
            ),
        )
        md = render_blueprint_markdown(bp)
        assert "[`src/api/`](source://src/api/)" in md

    def test_implementation_guideline_files_are_links(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        # rich_blueprint has implementation_guidelines with key_files
        assert "[`Services/NotificationService.swift`](source://Services/NotificationService.swift)" in md

    def test_developer_recipe_files_are_links(self, rich_blueprint):
        md = render_blueprint_markdown(rich_blueprint)
        assert "[`src/api/routes/new_route.py`](source://src/api/routes/new_route.py)" in md

    def test_contract_implementing_files_are_links(self):
        bp = StructuredBlueprint(
            components=Components(
                contracts=[
                    Contract(
                        interface_name="IRepo",
                        description="Data access",
                        implementing_files=["src/infra/repo.py"],
                    ),
                ],
            ),
        )
        md = render_blueprint_markdown(bp)
        assert "[`src/infra/repo.py`](source://src/infra/repo.py)" in md

    def test_link_preserves_backtick_formatting(self):
        """Links should have backtick-wrapped path text inside."""
        bp = StructuredBlueprint(
            components=Components(
                components=[
                    Component(
                        name="API",
                        location="src/api/",
                        responsibility="HTTP handling",
                        key_files=[
                            {"file": "src/main.py", "description": "Entry point"},
                        ],
                    ),
                ],
            ),
        )
        md = render_blueprint_markdown(bp)
        # The link text should be backtick-wrapped: [`path`](source://path)
        assert "[`src/main.py`](source://src/main.py)" in md

    def test_template_file_path_is_link(self):
        from domain.entities.blueprint import CodeTemplate
        bp = StructuredBlueprint(
            technology=Technology(
                templates=[
                    CodeTemplate(
                        component_type="Service",
                        description="Service boilerplate",
                        file_path_template="src/services/{name}_service.py",
                        code="class Service: pass",
                    ),
                ],
            ),
        )
        md = render_blueprint_markdown(bp)
        assert "[`src/services/{name}_service.py`](source://src/services/{name}_service.py)" in md

    def test_frontend_ui_component_location_is_link(self):
        bp = StructuredBlueprint(
            frontend=Frontend(
                framework="React",
                ui_components=[
                    UIComponent(
                        name="Dashboard",
                        location="src/pages/Dashboard.tsx",
                        component_type="page",
                        description="Main dashboard",
                    ),
                ],
            ),
        )
        md = render_blueprint_markdown(bp)
        assert "[`src/pages/Dashboard.tsx`](source://src/pages/Dashboard.tsx)" in md

    def test_frontend_routing_component_is_link_via_ui_component(self):
        """Route component is linked when a matching UI component provides its location."""
        bp = StructuredBlueprint(
            frontend=Frontend(
                framework="React",
                ui_components=[
                    UIComponent(
                        name="DashboardPage",
                        component_type="page",
                        location="src/pages/DashboardPage.tsx",
                        description="Dashboard",
                    ),
                ],
                routing=[
                    Route(
                        path="/dashboard",
                        component="DashboardPage",
                        description="Main view",
                    ),
                ],
            ),
        )
        md = render_blueprint_markdown(bp)
        assert "[`src/pages/DashboardPage.tsx`](source://src/pages/DashboardPage.tsx)" in md

    def test_frontend_routing_component_plain_when_no_ui_match(self):
        """Route component renders as plain text when no UI component provides a location."""
        bp = StructuredBlueprint(
            frontend=Frontend(
                framework="React",
                routing=[
                    Route(
                        path="/dashboard",
                        component="DashboardPage",
                        description="Main view",
                    ),
                ],
            ),
        )
        md = render_blueprint_markdown(bp)
        assert "`DashboardPage`" in md
        assert "source://DashboardPage" not in md

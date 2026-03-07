"""Tests for CodebaseMapRenderer."""
import pytest

from domain.entities.blueprint import (
    StructuredBlueprint,
    BlueprintMeta,
    Components,
    Component,
    Technology,
    TechStackEntry,
    DeveloperRecipe,
    ArchitecturalPitfall,
    KeyInterface,
)
from application.services.codebase_map_renderer import CodebaseMapRenderer


@pytest.fixture
def renderer():
    return CodebaseMapRenderer()


@pytest.fixture
def rich_blueprint():
    return StructuredBlueprint(
        meta=BlueprintMeta(
            repository="acme/backend-api",
            architecture_style="Clean Architecture",
            executive_summary="A backend API using Clean Architecture with FastAPI.",
            platforms=["backend"],
        ),
        architecture_diagram="graph TD\n  A[API] --> B[Domain]",
        components=Components(
            components=[
                Component(
                    name="API Layer",
                    location="src/api",
                    responsibility="HTTP endpoints and routing",
                    depends_on=["Domain"],
                    key_files=[{"file": "routes.py", "description": "Route definitions"}],
                    key_interfaces=[KeyInterface(name="Router", description="HTTP router")],
                ),
                Component(
                    name="Domain Layer",
                    location="src/domain",
                    responsibility="Business logic and entities",
                ),
            ]
        ),
        developer_recipes=[
            DeveloperRecipe(task="Add endpoint", files=["src/api/routes.py"], steps=["Define route", "Add handler"]),
        ],
        pitfalls=[
            ArchitecturalPitfall(area="API", description="Don't put business logic in routes", recommendation="Use services"),
        ],
        technology=Technology(
            stack=[
                TechStackEntry(category="framework", name="FastAPI", version="0.100", purpose="Web framework"),
            ],
            project_structure="src/\n  api/\n  domain/",
            run_commands={"dev": "uvicorn main:app --reload"},
        ),
    )


class TestRenderHeader:

    def test_renders_repo_name(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "acme/backend-api" in result

    def test_renders_executive_summary(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "backend API using Clean Architecture" in result

    def test_renders_architecture_style(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "Clean Architecture" in result


class TestRenderSections:

    def test_renders_architecture_diagram(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "```mermaid" in result
        assert "graph TD" in result

    def test_renders_module_guide(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "## Module Guide" in result
        assert "API Layer" in result
        assert "Domain Layer" in result

    def test_renders_common_tasks(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "## Common Tasks" in result
        assert "Add endpoint" in result

    def test_renders_gotchas(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "## Gotchas" in result
        assert "Don't put business logic" in result

    def test_renders_tech_stack(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "## Technology Stack" in result
        assert "FastAPI" in result

    def test_renders_run_commands(self, renderer, rich_blueprint):
        result = renderer.render(rich_blueprint)
        assert "## Run Commands" in result
        assert "uvicorn" in result


class TestMinimalBlueprint:

    def test_empty_blueprint_produces_valid_output(self, renderer):
        bp = StructuredBlueprint()
        result = renderer.render(bp)
        assert "# Codebase — Architecture Map" in result
        assert result.endswith("\n")

    def test_no_empty_sections(self, renderer):
        bp = StructuredBlueprint()
        result = renderer.render(bp)
        # Should not have empty section headers with no content
        assert "## Module Guide" not in result
        assert "## Common Tasks" not in result
        assert "## Gotchas" not in result

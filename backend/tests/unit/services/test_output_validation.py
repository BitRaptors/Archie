"""Output validation tests — verify generated outputs are clean.

These tests assert rendered content from the blueprint does not reference
removed features (dependency constraints, technology guidelines, validate_import,
what_to_use) and that remaining tools are present.
"""
import json
import pytest

from domain.entities.blueprint import (
    ArchitecturalDecision,
    ArchitectureRules,
    BlueprintMeta,
    Communication,
    CommunicationPattern,
    Component,
    Components,
    Decisions,
    FilePlacementRule,
    NamingConvention,
    QuickReference,
    StructuredBlueprint,
    TechStackEntry,
    Technology,
)
from application.services.blueprint_renderer import render_blueprint_markdown
from application.services.agent_file_generator import (
    generate_agents_md,
    generate_claude_md,
    generate_cursor_rules,
)
from infrastructure.mcp.tools import BlueprintTools


# ── Shared fixture ────────────────────────────────────────────────────────────


@pytest.fixture
def blueprint() -> StructuredBlueprint:
    """Blueprint with file_placement, naming — NO dependency_constraints or technology_guidelines."""
    return StructuredBlueprint(
        meta=BlueprintMeta(
            repository="acme/test-app",
            repository_id="test-repo-001",
            architecture_style="Clean Architecture",
            platforms=["backend"],
        ),
        architecture_rules=ArchitectureRules(
            file_placement_rules=[
                FilePlacementRule(
                    component_type="service",
                    location="src/application/services/",
                    naming_pattern="*_service.py",
                    example="user_service.py",
                    description="Business logic services",
                ),
            ],
            naming_conventions=[
                NamingConvention(
                    scope="classes",
                    pattern="^[A-Z][a-zA-Z0-9]*$",
                    examples=["UserService", "OrderRepository"],
                    description="PascalCase for classes",
                ),
            ],
        ),
        decisions=Decisions(
            architectural_style=ArchitecturalDecision(
                title="Architecture",
                chosen="Clean Architecture",
                rationale="Separation of concerns.",
            ),
        ),
        components=Components(
            structure_type="layered",
            components=[
                Component(
                    name="API",
                    location="src/api/",
                    responsibility="HTTP handling",
                    platform="backend",
                ),
            ],
        ),
        communication=Communication(
            patterns=[
                CommunicationPattern(
                    name="REST",
                    when_to_use="Standard requests",
                    how_it_works="HTTP JSON",
                ),
            ],
        ),
        quick_reference=QuickReference(
            where_to_put_code={"service": "src/application/services/"},
        ),
        technology=Technology(
            stack=[
                TechStackEntry(category="runtime", name="Python", version="3.13", purpose="Runtime"),
            ],
        ),
    )


@pytest.fixture
def tools_with_blueprint(tmp_path, blueprint):
    """BlueprintTools instance with the test blueprint stored."""
    storage = tmp_path / "storage"
    bp_dir = storage / "blueprints" / "test-repo-001"
    bp_dir.mkdir(parents=True)
    (bp_dir / "blueprint.json").write_text(
        blueprint.model_dump_json(indent=2), encoding="utf-8"
    )
    return BlueprintTools(storage_dir=storage)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Markdown renderer output
# ══════════════════════════════════════════════════════════════════════════════


class TestMarkdownNoRemovedFeatures:

    def test_no_dependency_constraints_in_markdown(self, blueprint):
        md = render_blueprint_markdown(blueprint)
        assert "Dependency Constraints" not in md
        assert "Forbidden imports" not in md
        assert "Allowed imports" not in md

    def test_no_technology_guidelines_in_markdown(self, blueprint):
        md = render_blueprint_markdown(blueprint)
        assert "Technology Guidelines" not in md

    def test_architecture_rules_section_renders(self, blueprint):
        md = render_blueprint_markdown(blueprint)
        assert "## 5. Architecture Rules" in md
        assert "### File Placement Rules" in md
        assert "### Naming Conventions" in md


# ══════════════════════════════════════════════════════════════════════════════
# 2. CLAUDE.md output
# ══════════════════════════════════════════════════════════════════════════════


class TestClaudeMdNoRemovedFeatures:

    def test_no_dependency_rules_in_claude_md(self, blueprint):
        content = generate_claude_md(blueprint)
        assert "## Dependency Rules" not in content

    def test_no_validate_import_in_claude_md(self, blueprint):
        content = generate_claude_md(blueprint)
        assert "validate_import" not in content

    def test_no_technology_guidelines_in_claude_md(self, blueprint):
        content = generate_claude_md(blueprint)
        assert "## Technology Guidelines" not in content

    def test_no_what_to_use_in_claude_md(self, blueprint):
        content = generate_claude_md(blueprint)
        assert "what_to_use" not in content

    def test_mcp_workflow_no_removed_tools(self, blueprint):
        from application.services.agent_file_generator import generate_all
        output = generate_all(blueprint)
        mcp_rule = next((rf for rf in output.rule_files if rf.topic == "mcp-tools"), None)
        assert mcp_rule is not None
        assert "validate_import" not in mcp_rule.body
        assert "what_to_use" not in mcp_rule.body


# ══════════════════════════════════════════════════════════════════════════════
# 3. Cursor rules output
# ══════════════════════════════════════════════════════════════════════════════


class TestCursorRulesNoRemovedFeatures:

    def test_no_dependency_rules_in_cursor(self, blueprint):
        content = generate_cursor_rules(blueprint)
        assert "## Dependency Rules" not in content

    def test_no_anti_patterns_section(self, blueprint):
        content = generate_cursor_rules(blueprint)
        assert "## Anti-Patterns" not in content

    def test_no_validate_import_in_cursor(self, blueprint):
        content = generate_cursor_rules(blueprint)
        assert "validate_import" not in content

    def test_no_technology_guidelines_in_cursor(self, blueprint):
        content = generate_cursor_rules(blueprint)
        assert "## Technology Guidelines" not in content

    def test_no_what_to_use_in_cursor(self, blueprint):
        content = generate_cursor_rules(blueprint)
        assert "what_to_use" not in content


# ══════════════════════════════════════════════════════════════════════════════
# 4. AGENTS.md output
# ══════════════════════════════════════════════════════════════════════════════


class TestAgentsMdNoRemovedFeatures:

    def test_no_dependency_rules_count_in_agents(self, blueprint):
        content = generate_agents_md(blueprint)
        assert "Dependency rules" not in content

    def test_no_technology_guidelines_count_in_agents(self, blueprint):
        content = generate_agents_md(blueprint)
        assert "Technology guidelines" not in content

    def test_no_validate_import_in_agents(self, blueprint):
        content = generate_agents_md(blueprint)
        assert "validate_import" not in content

    def test_no_what_to_use_in_agents(self, blueprint):
        content = generate_agents_md(blueprint)
        assert "what_to_use" not in content


# ══════════════════════════════════════════════════════════════════════════════
# 5. MCP tools output
# ══════════════════════════════════════════════════════════════════════════════


class TestMcpToolsOutput:

    def test_where_to_put_still_works(self, tools_with_blueprint):
        result = tools_with_blueprint.where_to_put("test-repo-001", "service")
        assert "src/application/services/" in result

    def test_check_naming_still_works(self, tools_with_blueprint):
        result = tools_with_blueprint.check_naming("test-repo-001", "classes", "UserService")
        assert "OK" in result

    def test_no_what_to_use_method(self, tools_with_blueprint):
        assert not hasattr(tools_with_blueprint, "what_to_use")


# ══════════════════════════════════════════════════════════════════════════════
# 6. Blueprint model
# ══════════════════════════════════════════════════════════════════════════════


class TestBlueprintModel:

    def test_architecture_rules_no_dependency_constraints(self):
        rules = ArchitectureRules()
        assert not hasattr(rules, "dependency_constraints")

    def test_architecture_rules_no_technology_guidelines(self):
        rules = ArchitectureRules()
        assert not hasattr(rules, "technology_guidelines")

    def test_blueprint_roundtrip_clean(self, blueprint):
        data = json.loads(blueprint.model_dump_json())
        assert "dependency_constraints" not in data.get("architecture_rules", {})
        assert "technology_guidelines" not in data.get("architecture_rules", {})
        # Roundtrip
        restored = StructuredBlueprint.model_validate(data)
        assert not hasattr(restored.architecture_rules, "dependency_constraints")
        assert not hasattr(restored.architecture_rules, "technology_guidelines")

"""Tests for IntentLayerRenderer."""
import pytest

from domain.entities.intent_layer import (
    FolderNode,
    FolderContext,
    FolderBlueprint,
    FolderEnrichment,
    KeyFileGuide,
    CommonTask,
)
from application.services.intent_layer_renderer import IntentLayerRenderer, MAX_LINES


@pytest.fixture
def renderer():
    return IntentLayerRenderer()


@pytest.fixture
def sample_folder():
    return FolderNode(
        path="src/api",
        name="api",
        depth=2,
        parent_path="src",
        files=["routes.py", "middleware.py"],
        file_count=2,
    )


@pytest.fixture
def sample_context():
    return FolderContext(
        path="src/api",
        purpose="HTTP API layer handling REST endpoints",
        scope="All REST endpoints and middleware",
        key_files=[
            {"file": "routes.py", "description": "Route definitions"},
            {"file": "middleware.py", "description": "Auth middleware"},
        ],
        patterns=["Use dependency injection", "Return Pydantic models"],
        anti_patterns=["Don't put business logic in routes"],
        cross_references=[{"path": "../services/", "relationship": "Calls service layer"}],
        downlinks=[{"path": "handlers/", "summary": "Request handlers"}],
    )


@pytest.fixture
def sample_folder_blueprint():
    return FolderBlueprint(
        path="src/api",
        component_name="API Layer",
        component_responsibility="HTTP API layer handling REST endpoints",
        depends_on=["Domain", "Infrastructure"],
        exposes_to=["Frontend"],
        key_files=[
            {"file": "routes.py", "description": "Route definitions"},
            {"file": "middleware.py", "description": "Auth middleware"},
        ],
        file_placement_rules=[
            {"component_type": "route", "naming_pattern": "*_routes.py", "example": "user_routes.py", "description": "API route files"}
        ],
        where_to_put={"routes": "src/api/routes"},
        recipes=[
            {"task": "Add endpoint", "files": ["src/api/routes.py"], "steps": ["Define route", "Add handler"]}
        ],
        pitfalls=[
            {"area": "API", "description": "Don't put logic in routes", "recommendation": "Use services"}
        ],
        children_summaries=[
            {"path": "src/api/routes", "component_name": "Routes", "responsibility": "Route definitions"},
        ],
        peer_paths=["src/domain", "src/infrastructure"],
        parent_path="src",
        parent_component="Backend",
        has_blueprint_coverage=True,
    )


# ── Legacy AI-based rendering ──

class TestRenderFolderClaudeMd:

    def test_basic_structure(self, renderer, sample_folder, sample_context):
        result = renderer.render_folder_claude_md(sample_folder, sample_context, "my-repo")

        assert "# api/" in result
        assert "> HTTP API layer handling REST endpoints" in result
        assert "## Scope" in result
        assert "## Key Files" in result
        assert "## Patterns" in result
        assert "## Anti-Patterns" in result

    def test_key_files_table(self, renderer, sample_folder, sample_context):
        result = renderer.render_folder_claude_md(sample_folder, sample_context, "my-repo")

        assert "| `routes.py` | Route definitions |" in result
        assert "| `middleware.py` | Auth middleware |" in result

    def test_cross_references(self, renderer, sample_folder, sample_context):
        result = renderer.render_folder_claude_md(sample_folder, sample_context, "my-repo")

        assert "## Related" in result
        assert "`../services/`" in result

    def test_downlinks(self, renderer, sample_folder, sample_context):
        result = renderer.render_folder_claude_md(sample_folder, sample_context, "my-repo")

        assert "## Subfolders" in result
        assert "`handlers/`" in result

    def test_root_folder_uses_repo_name(self, renderer):
        root = FolderNode(path="", name="root", depth=0)
        ctx = FolderContext(path="", purpose="Project root")
        result = renderer.render_folder_claude_md(root, ctx, "my-app")

        assert "# my-app" in result

    def test_empty_context_minimal(self, renderer, sample_folder):
        ctx = FolderContext(path="src/api")
        result = renderer.render_folder_claude_md(sample_folder, ctx, "repo")

        assert "# api/" in result
        assert "## Key Files" not in result
        assert "## Patterns" not in result

    def test_ends_with_newline(self, renderer, sample_folder, sample_context):
        result = renderer.render_folder_claude_md(sample_folder, sample_context, "repo")
        assert result.endswith("\n")


class TestRenderClaudeRule:

    def test_frontmatter(self, renderer, sample_folder, sample_context):
        result = renderer.render_claude_rule(sample_folder, sample_context, "repo")

        assert result.startswith("---\n")
        assert 'description: "src/api conventions"' in result
        assert '- "src/api/**"' in result
        assert "---" in result

    def test_has_sections(self, renderer, sample_folder, sample_context):
        result = renderer.render_claude_rule(sample_folder, sample_context, "repo")

        assert "# api Rules" in result
        assert "## Purpose" in result
        assert "## Conventions" in result
        assert "## Anti-Patterns" in result

    def test_root_conventions(self, renderer):
        root = FolderNode(path="", name="root", depth=0)
        ctx = FolderContext(path="", purpose="Project root", patterns=["Follow PEP 8"])
        result = renderer.render_claude_rule(root, ctx, "repo")

        assert '"root conventions"' in result  # description uses "root" for empty path
        assert '"**"' in result  # glob matches everything

    def test_ends_with_newline(self, renderer, sample_folder, sample_context):
        result = renderer.render_claude_rule(sample_folder, sample_context, "repo")
        assert result.endswith("\n")


class TestRenderRuleFilename:

    def test_basic_path(self):
        assert IntentLayerRenderer.render_rule_filename("src/api/routes") == "src-api-routes.md"

    def test_root(self):
        assert IntentLayerRenderer.render_rule_filename("") == "root.md"

    def test_single_level(self):
        assert IntentLayerRenderer.render_rule_filename("src") == "src.md"

    def test_deep_path(self):
        assert IntentLayerRenderer.render_rule_filename("a/b/c/d") == "a-b-c-d.md"


# ── Blueprint-driven rendering ──

class TestRenderFromBlueprint:

    def test_basic_rendering(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "# api/" in result
        assert "> HTTP API layer handling REST endpoints" in result
        assert result.endswith("\n")

    def test_navigation_section_present(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "## Navigation" in result

    def test_parent_deep_link(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "../CLAUDE.md" in result

    def test_peer_deep_links(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "domain" in result
        assert "infrastructure" in result

    def test_children_deep_links(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "routes/CLAUDE.md" in result

    def test_relative_paths(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        # All links should be relative
        assert "../CLAUDE.md" in result  # Parent
        assert "../domain/CLAUDE.md" in result  # Peer
        assert "routes/CLAUDE.md" in result  # Child

    def test_key_files_table(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "## Key Files" in result
        assert "| `routes.py` |" in result

    def test_common_tasks(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "## Common Tasks" in result
        assert "Add endpoint" in result

    def test_gotchas(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "## Gotchas" in result
        assert "Don't put logic in routes" in result

    def test_dependencies(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "## Dependencies" in result
        assert "`Domain`" in result
        assert "`Frontend`" in result

    def test_what_goes_here(self, renderer, sample_folder, sample_folder_blueprint):
        result = renderer.render_from_blueprint(sample_folder, sample_folder_blueprint, "my-repo")

        assert "## What Goes Here" in result


class TestLineHardCap:

    def test_200_line_cap(self, renderer, sample_folder):
        """Generate a FolderBlueprint with large data in every field, assert line_count <= 200."""
        fb = FolderBlueprint(
            path="src/api",
            component_name="API",
            component_responsibility="Very long responsibility " * 5,
            depends_on=[f"dep_{i}" for i in range(20)],
            exposes_to=[f"exp_{i}" for i in range(20)],
            key_files=[{"file": f"file_{i}.py", "description": f"Description for file {i} " * 3} for i in range(30)],
            file_placement_rules=[{"component_type": f"type_{i}", "naming_pattern": f"*_{i}.py", "example": f"ex_{i}.py", "description": f"Rule {i} " * 3} for i in range(20)],
            naming_conventions=[{"scope": f"scope_{i}", "pattern": f"pattern_{i}", "examples": f"ex_{i}"} for i in range(10)],
            where_to_put={f"code_{i}": f"location_{i}" for i in range(10)},
            recipes=[{"task": f"Task {i}", "files": [f"file_{i}.py"], "steps": [f"Step {j}" for j in range(5)]} for i in range(10)],
            pitfalls=[{"area": f"Area {i}", "description": f"Pitfall {i} " * 5, "recommendation": f"Fix {i}"} for i in range(10)],
            implementation_guidelines=[{"capability": f"Cap {i}", "libraries": [f"lib_{i}"], "pattern_description": f"Pattern {i} " * 5, "key_files": [f"file_{i}.py"]} for i in range(10)],
            contracts=[{"interface_name": f"Interface_{i}", "description": f"Contract {i}", "methods": [f"method_{j}" for j in range(5)]} for i in range(5)],
            communication_patterns=[{"name": f"Pattern_{i}", "when_to_use": f"When {i}", "how_it_works": f"How {i}"} for i in range(5)],
            templates=[{"component_type": f"Template_{i}", "file_path_template": f"src/api/{i}.py", "code": f"# template {i}\nclass T{i}: pass"} for i in range(5)],
            children_summaries=[{"path": f"src/api/child_{i}", "component_name": f"Child_{i}", "responsibility": f"Resp {i}"} for i in range(10)],
            peer_paths=[f"src/peer_{i}" for i in range(5)],
            parent_path="src",
            has_blueprint_coverage=True,
        )

        result = renderer.render_from_blueprint(sample_folder, fb, "my-repo")
        line_count = len(result.split("\n"))
        assert line_count <= MAX_LINES, f"Output has {line_count} lines, exceeds {MAX_LINES} cap"

    def test_truncation_notice(self, renderer, sample_folder):
        """When capped, output should end with CODEBASE_MAP.md link."""
        fb = FolderBlueprint(
            path="src/api",
            component_name="API",
            component_responsibility="HTTP layer",
            key_files=[{"file": f"file_{i}.py", "description": f"Description {i} " * 5} for i in range(50)],
            recipes=[{"task": f"Task {i}", "files": [f"f_{i}.py"], "steps": [f"Step {j}" for j in range(10)]} for i in range(20)],
            pitfalls=[{"area": f"Area {i}", "description": f"Pitfall " * 10, "recommendation": f"Fix {i}"} for i in range(20)],
            children_summaries=[{"path": f"src/api/child_{i}", "component_name": f"Child_{i}", "responsibility": f"R"} for i in range(5)],
            peer_paths=["src/domain"],
            parent_path="src",
            has_blueprint_coverage=True,
        )

        result = renderer.render_from_blueprint(sample_folder, fb, "my-repo")
        line_count = len(result.split("\n"))

        if line_count >= MAX_LINES - 10:
            # If we're close to the cap, the truncation notice should be present
            assert "CODEBASE_MAP.md" in result


# ── Minimal rendering ──

class TestRenderMinimal:

    def test_basic_minimal(self, renderer, sample_folder):
        fb = FolderBlueprint(path="src/api", parent_path="src")
        result = renderer.render_minimal(sample_folder, fb, "my-repo")

        assert "# api/" in result
        assert result.endswith("\n")

    def test_navigation_present(self, renderer, sample_folder):
        fb = FolderBlueprint(
            path="src/api",
            parent_path="src",
            peer_paths=["src/domain"],
        )
        result = renderer.render_minimal(sample_folder, fb, "my-repo")

        assert "## Navigation" in result

    def test_file_listing(self, renderer, sample_folder):
        fb = FolderBlueprint(path="src/api", parent_path="src")
        result = renderer.render_minimal(sample_folder, fb, "my-repo")

        assert "`routes.py`" in result
        assert "`middleware.py`" in result

    def test_under_200_lines(self, renderer):
        folder = FolderNode(
            path="src/api",
            name="api",
            depth=2,
            parent_path="src",
            files=[f"file_{i}.py" for i in range(25)],
            file_count=25,
        )
        fb = FolderBlueprint(path="src/api", parent_path="src", peer_paths=["src/domain"])
        result = renderer.render_minimal(folder, fb, "my-repo")

        line_count = len(result.split("\n"))
        assert line_count <= MAX_LINES

    def test_root_uses_repo_name(self, renderer):
        root = FolderNode(path="", name="root", depth=0, files=["README.md"])
        fb = FolderBlueprint(path="")
        result = renderer.render_minimal(root, fb, "my-app")

        assert "# my-app" in result


# ── FolderEnrichment model tests ──

class TestFolderEnrichmentModel:

    def test_defaults(self):
        e = FolderEnrichment(path="src/api")
        assert e.purpose == ""
        assert e.patterns == []
        assert e.key_file_guides == []
        assert e.anti_patterns == []
        assert e.common_task is None
        assert e.testing == []
        assert e.debugging == []
        assert e.decisions == []
        assert e.has_ai_content is False

    def test_full_enrichment(self):
        e = FolderEnrichment(
            path="src/api",
            purpose="HTTP routing layer: thin handlers only",
            patterns=["Use @router decorators", "Validate with Pydantic"],
            key_file_guides=[
                KeyFileGuide(file="routes.py", purpose="Route defs", modification_guide="Add via @router.get"),
            ],
            anti_patterns=["Don't put logic here -- use services instead"],
            common_task=CommonTask(task="Add endpoint", steps=["Create route", "Add handler"]),
            testing=["pytest with AsyncClient"],
            debugging=["Check DI container"],
            decisions=["Thin by design for clean architecture"],
            has_ai_content=True,
        )
        assert e.has_ai_content is True
        assert len(e.key_file_guides) == 1
        assert e.common_task.task == "Add endpoint"


# ── Hybrid rendering ──

class TestRenderHybrid:

    @pytest.fixture
    def sample_enrichment(self):
        return FolderEnrichment(
            path="src/api",
            purpose="Thin HTTP handlers: validate input, call service, return DTO",
            patterns=[
                "Every route uses @router.get/post() with explicit response_model",
                "Auth: current_user = Depends(get_current_user) on protected endpoints",
            ],
            key_file_guides=[
                KeyFileGuide(
                    file="routes.py",
                    purpose="Route definitions",
                    modification_guide="Follow pattern: auth -> validate -> service -> response",
                ),
            ],
            anti_patterns=[
                "Don't put business logic in routes -- delegate to services",
                "Don't return raw dicts -- always use Pydantic response models",
            ],
            common_task=CommonTask(
                task="Add a new endpoint",
                steps=["Create route function", "Define response DTO", "Register router"],
            ),
            testing=["Route tests mock the DI container", "Use AsyncMock for async services"],
            debugging=["Check request.app.container if DI fails"],
            decisions=["Routes are thin by design -- clean architecture boundary"],
            has_ai_content=True,
        )

    def test_ai_purpose_over_blueprint(self, renderer, sample_folder, sample_folder_blueprint, sample_enrichment):
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, sample_enrichment, "my-repo")

        assert "Thin HTTP handlers" in result

    def test_patterns_section_present(self, renderer, sample_folder, sample_folder_blueprint, sample_enrichment):
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, sample_enrichment, "my-repo")

        assert "## Patterns" in result
        assert "response_model" in result

    def test_navigation_deterministic(self, renderer, sample_folder, sample_folder_blueprint, sample_enrichment):
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, sample_enrichment, "my-repo")

        assert "## Navigation" in result
        assert "../CLAUDE.md" in result

    def test_key_files_with_modification_guide(self, renderer, sample_folder, sample_folder_blueprint, sample_enrichment):
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, sample_enrichment, "my-repo")

        assert "## Key Files" in result
        assert "How to Modify" in result
        assert "routes.py" in result

    def test_anti_patterns_as_dont(self, renderer, sample_folder, sample_folder_blueprint, sample_enrichment):
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, sample_enrichment, "my-repo")

        assert "## Don't" in result
        assert "business logic" in result

    def test_testing_section(self, renderer, sample_folder, sample_folder_blueprint, sample_enrichment):
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, sample_enrichment, "my-repo")

        assert "## Testing" in result
        assert "DI container" in result

    def test_debugging_section(self, renderer, sample_folder, sample_folder_blueprint, sample_enrichment):
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, sample_enrichment, "my-repo")

        assert "## Debugging" in result

    def test_decisions_section(self, renderer, sample_folder, sample_folder_blueprint, sample_enrichment):
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, sample_enrichment, "my-repo")

        assert "## Why It's Built This Way" in result
        assert "clean architecture" in result

    def test_fallback_when_no_ai_content(self, renderer, sample_folder, sample_folder_blueprint):
        empty_enrichment = FolderEnrichment(path="src/api", has_ai_content=False)
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, empty_enrichment, "my-repo")

        # Should fall back to blueprint data
        assert "# api/" in result
        assert "> HTTP API layer handling REST endpoints" in result
        # Blueprint key files (2-column, no modification guide column)
        assert "## Key Files" in result
        assert "## Patterns" not in result  # No AI patterns

    def test_200_line_cap(self, renderer, sample_folder):
        """Oversized enrichment data should be capped at 200 lines."""
        enrichment = FolderEnrichment(
            path="src/api",
            purpose="Purpose",
            patterns=[f"Pattern {i} " * 10 for i in range(30)],
            key_file_guides=[
                KeyFileGuide(file=f"file_{i}.py", purpose=f"Purpose {i} " * 5, modification_guide=f"Guide {i} " * 5)
                for i in range(20)
            ],
            anti_patterns=[f"Don't do {i} " * 10 for i in range(20)],
            common_task=CommonTask(task="Big task", steps=[f"Step {i} " * 5 for i in range(20)]),
            testing=[f"Test {i} " * 10 for i in range(20)],
            debugging=[f"Debug {i} " * 10 for i in range(20)],
            decisions=[f"Decision {i} " * 10 for i in range(20)],
            has_ai_content=True,
        )
        fb = FolderBlueprint(
            path="src/api",
            component_responsibility="HTTP layer",
            children_summaries=[{"path": f"src/api/child_{i}", "component_name": f"C{i}", "responsibility": f"R{i}"} for i in range(20)],
            peer_paths=["src/domain"],
            parent_path="src",
            has_blueprint_coverage=True,
        )

        result = renderer.render_hybrid(sample_folder, fb, enrichment, "my-repo")
        line_count = len(result.split("\n"))
        assert line_count <= MAX_LINES, f"Output has {line_count} lines, exceeds {MAX_LINES} cap"

"""Tests for IntentLayerRenderer."""
import pytest

from domain.entities.intent_layer import (
    FolderNode,
    FolderBlueprint,
    FolderEnrichment,
    KeyFileGuide,
    CommonTask,
    CodeExample,
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
            code_examples=[
                CodeExample(
                    label="Create a new route",
                    code="@router.get('/items')\nasync def list_items(service: ItemService = Depends()):\n    return await service.list_all()",
                    language="python",
                ),
            ],
            key_imports=[
                "from api.routes import router",
                "from api.middleware import auth_middleware",
            ],
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


# ── Code Examples & Key Imports rendering ──

class TestRenderCodeExamples:

    def test_render_code_examples(self, renderer, sample_folder, sample_folder_blueprint):
        enrichment = FolderEnrichment(
            path="src/api",
            code_examples=[
                CodeExample(label="Create a service", code="class MyService:\n    pass", language="python"),
            ],
            has_ai_content=True,
        )
        result = renderer._render_code_examples(enrichment)
        assert result is not None
        assert "## Usage Examples" in result
        assert "### Create a service" in result
        assert "```python" in result
        assert "class MyService:" in result

    def test_render_code_examples_empty(self, renderer):
        enrichment = FolderEnrichment(path="src/api")
        result = renderer._render_code_examples(enrichment)
        assert result is None

    def test_render_key_imports(self, renderer):
        enrichment = FolderEnrichment(
            path="src/api",
            key_imports=["from api.routes import router", "from api.auth import get_user"],
            has_ai_content=True,
        )
        result = renderer._render_key_imports(enrichment)
        assert result is not None
        assert "## Key Imports" in result
        assert "`from api.routes import router`" in result

    def test_render_key_imports_empty(self, renderer):
        enrichment = FolderEnrichment(path="src/api")
        result = renderer._render_key_imports(enrichment)
        assert result is None

    def test_code_examples_in_hybrid(self, renderer, sample_folder, sample_folder_blueprint):
        enrichment = FolderEnrichment(
            path="src/api",
            purpose="API layer",
            code_examples=[
                CodeExample(label="Add route", code="@router.get('/x')\ndef handler(): ...", language="python"),
            ],
            key_imports=["from api import router"],
            has_ai_content=True,
        )
        result = renderer.render_hybrid(sample_folder, sample_folder_blueprint, enrichment, "my-repo")
        assert "## Usage Examples" in result
        assert "## Key Imports" in result


# ── Pass-through rendering ──

class TestRenderPassthrough:

    def test_passthrough_one_liner(self, renderer):
        folder = FolderNode(
            path="com/bitraptors", name="bitraptors", depth=2,
            parent_path="com", children=["com/bitraptors/app"],
            is_passthrough=True,
        )
        fb = FolderBlueprint(path="com/bitraptors")
        result = renderer.render_passthrough(folder, fb, "my-repo")
        lines = [l for l in result.strip().split("\n") if l]
        assert len(lines) == 2  # heading + blockquote

    def test_passthrough_links_to_child(self, renderer):
        folder = FolderNode(
            path="com/bitraptors", name="bitraptors", depth=2,
            parent_path="com", children=["com/bitraptors/app"],
            is_passthrough=True,
        )
        fb = FolderBlueprint(path="com/bitraptors")
        result = renderer.render_passthrough(folder, fb, "my-repo")
        assert "app/CLAUDE.md" in result

    def test_passthrough_says_namespace(self, renderer):
        folder = FolderNode(
            path="com", name="com", depth=1,
            parent_path="", children=["com/bitraptors"],
            is_passthrough=True,
        )
        fb = FolderBlueprint(path="com")
        result = renderer.render_passthrough(folder, fb, "my-repo")
        assert "Namespace folder" in result


# ── is_passthrough computation ──

class TestIsPassthrough:

    def _build(self, file_tree):
        from application.services.intent_layer_service import FolderHierarchyBuilder
        builder = FolderHierarchyBuilder()
        return builder.build_from_file_tree(file_tree)

    def test_single_child_no_files_is_passthrough(self):
        tree = [
            {"name": "App.java", "path": "com/bitraptors/app/App.java", "type": "file", "size": 100, "extension": "java"},
        ]
        nodes = self._build(tree)
        assert nodes["com"].is_passthrough is True
        assert nodes["com/bitraptors"].is_passthrough is True

    def test_single_child_with_init_only_is_passthrough(self):
        tree = [
            {"name": "__init__.py", "path": "com/__init__.py", "type": "file", "size": 0, "extension": "py"},
            {"name": "App.py", "path": "com/bitraptors/app/App.py", "type": "file", "size": 100, "extension": "py"},
        ]
        nodes = self._build(tree)
        assert nodes["com"].is_passthrough is True

    def test_multi_child_not_passthrough(self):
        tree = [
            {"name": "a.py", "path": "src/api/a.py", "type": "file", "size": 10, "extension": "py"},
            {"name": "b.py", "path": "src/domain/b.py", "type": "file", "size": 10, "extension": "py"},
            {"name": "c.py", "path": "src/infra/c.py", "type": "file", "size": 10, "extension": "py"},
        ]
        nodes = self._build(tree)
        assert nodes["src"].is_passthrough is False

    def test_single_child_with_code_not_passthrough(self):
        tree = [
            {"name": "routes.py", "path": "src/routes.py", "type": "file", "size": 100, "extension": "py"},
            {"name": "a.py", "path": "src/api/a.py", "type": "file", "size": 10, "extension": "py"},
        ]
        nodes = self._build(tree)
        assert nodes["src"].is_passthrough is False

    def test_root_never_passthrough(self):
        tree = [
            {"name": "a.py", "path": "src/a.py", "type": "file", "size": 10, "extension": "py"},
        ]
        nodes = self._build(tree)
        assert nodes[""].is_passthrough is False

    def test_passthrough_chain(self):
        """com/ -> bitraptors/ -> app/ — both com/ and bitraptors/ are passthrough."""
        tree = [
            {"name": "App.java", "path": "com/bitraptors/app/App.java", "type": "file", "size": 100, "extension": "java"},
            {"name": "Util.java", "path": "com/bitraptors/app/Util.java", "type": "file", "size": 100, "extension": "java"},
        ]
        nodes = self._build(tree)
        assert nodes["com"].is_passthrough is True
        assert nodes["com/bitraptors"].is_passthrough is True
        assert nodes["com/bitraptors/app"].is_passthrough is False


# ── Resource folder filtering ──

class TestResourceFolderFiltering:
    """Leaf folders with no source code files are excluded from significant folders."""

    def _build_and_filter(self, file_tree):
        from application.services.intent_layer_service import FolderHierarchyBuilder
        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_file_tree(file_tree)
        return builder.filter_significant(nodes)

    def test_drawable_folder_excluded(self):
        """Android res/drawable with only PNGs should be excluded."""
        tree = [
            {"name": "MainActivity.java", "path": "src/main/java/MainActivity.java", "type": "file", "size": 100, "extension": "java"},
            {"name": "icon.png", "path": "src/main/res/drawable/icon.png", "type": "file", "size": 500, "extension": "png"},
            {"name": "logo.png", "path": "src/main/res/drawable/logo.png", "type": "file", "size": 500, "extension": "png"},
        ]
        significant = self._build_and_filter(tree)
        assert "src/main/res/drawable" not in significant

    def test_assets_images_excluded(self):
        """Folder with only image files should be excluded."""
        tree = [
            {"name": "app.ts", "path": "src/app.ts", "type": "file", "size": 100, "extension": "ts"},
            {"name": "hero.jpg", "path": "src/assets/images/hero.jpg", "type": "file", "size": 1000, "extension": "jpg"},
            {"name": "bg.svg", "path": "src/assets/images/bg.svg", "type": "file", "size": 200, "extension": "svg"},
        ]
        significant = self._build_and_filter(tree)
        assert "src/assets/images" not in significant

    def test_code_folder_kept(self):
        """Folder with source code files should be kept."""
        tree = [
            {"name": "main.py", "path": "src/main.py", "type": "file", "size": 100, "extension": "py"},
            {"name": "utils.py", "path": "src/utils.py", "type": "file", "size": 100, "extension": "py"},
        ]
        significant = self._build_and_filter(tree)
        assert "src" in significant

    def test_mixed_folder_kept(self):
        """Folder with both code and resource files should be kept."""
        tree = [
            {"name": "styles.css", "path": "src/styles.css", "type": "file", "size": 100, "extension": "css"},
            {"name": "app.tsx", "path": "src/app.tsx", "type": "file", "size": 100, "extension": "tsx"},
        ]
        significant = self._build_and_filter(tree)
        assert "src" in significant

    def test_android_layout_xml_kept(self):
        """Android layout XML is a source code extension — folder should be kept."""
        tree = [
            {"name": "activity_main.xml", "path": "res/layout/activity_main.xml", "type": "file", "size": 100, "extension": "xml"},
            {"name": "fragment_home.xml", "path": "res/layout/fragment_home.xml", "type": "file", "size": 100, "extension": "xml"},
        ]
        significant = self._build_and_filter(tree)
        assert "res/layout" in significant

    def test_parent_kept_when_subtree_has_code(self):
        """Non-leaf folder is kept when a descendant has source code."""
        tree = [
            {"name": "icon.png", "path": "res/drawable/icon.png", "type": "file", "size": 500, "extension": "png"},
            {"name": "main.xml", "path": "res/layout/main.xml", "type": "file", "size": 100, "extension": "xml"},
        ]
        significant = self._build_and_filter(tree)
        # res/ kept because res/layout/ has .xml (source code extension)
        assert "res" in significant
        # drawable/ excluded — only PNGs
        assert "res/drawable" not in significant

    def test_xcassets_excluded(self):
        """Xcode asset catalog tree has no source code — entire subtree excluded."""
        tree = [
            {"name": "AppDelegate.swift", "path": "App/AppDelegate.swift", "type": "file", "size": 100, "extension": "swift"},
            {"name": "ViewController.swift", "path": "App/ViewController.swift", "type": "file", "size": 100, "extension": "swift"},
            {"name": "Contents.json", "path": "App/Assets.xcassets/Contents.json", "type": "file", "size": 50, "extension": "json"},
            {"name": "Contents.json", "path": "App/Assets.xcassets/AppIcon.appiconset/Contents.json", "type": "file", "size": 50, "extension": "json"},
            {"name": "icon.png", "path": "App/Assets.xcassets/AppIcon.appiconset/icon.png", "type": "file", "size": 1000, "extension": "png"},
            {"name": "Contents.json", "path": "App/Assets.xcassets/AccentColor.colorset/Contents.json", "type": "file", "size": 50, "extension": "json"},
        ]
        significant = self._build_and_filter(tree)
        assert "App" in significant  # Has .swift files
        assert "App/Assets.xcassets" not in significant
        assert "App/Assets.xcassets/AppIcon.appiconset" not in significant
        assert "App/Assets.xcassets/AccentColor.colorset" not in significant

    def test_resource_only_parent_excluded(self):
        """Parent folder excluded when entire subtree is resource-only."""
        tree = [
            {"name": "app.js", "path": "src/app.js", "type": "file", "size": 100, "extension": "js"},
            {"name": "hero.jpg", "path": "src/assets/images/hero.jpg", "type": "file", "size": 1000, "extension": "jpg"},
            {"name": "Roboto.ttf", "path": "src/assets/fonts/Roboto.ttf", "type": "file", "size": 5000, "extension": "ttf"},
        ]
        significant = self._build_and_filter(tree)
        assert "src" in significant
        assert "src/assets" not in significant  # No code in entire subtree
        assert "src/assets/images" not in significant
        assert "src/assets/fonts" not in significant

    def test_dart_files_kept(self):
        """Flutter .dart files are source code."""
        tree = [
            {"name": "main.dart", "path": "lib/main.dart", "type": "file", "size": 100, "extension": "dart"},
            {"name": "app.dart", "path": "lib/app.dart", "type": "file", "size": 100, "extension": "dart"},
        ]
        significant = self._build_and_filter(tree)
        assert "lib" in significant

    def test_swift_files_kept(self):
        """iOS .swift files are source code."""
        tree = [
            {"name": "AppDelegate.swift", "path": "App/AppDelegate.swift", "type": "file", "size": 100, "extension": "swift"},
            {"name": "ViewController.swift", "path": "App/ViewController.swift", "type": "file", "size": 100, "extension": "swift"},
        ]
        significant = self._build_and_filter(tree)
        assert "App" in significant

    def test_kotlin_files_kept(self):
        """Android .kt files are source code."""
        tree = [
            {"name": "MainActivity.kt", "path": "app/src/main/kotlin/MainActivity.kt", "type": "file", "size": 100, "extension": "kt"},
            {"name": "App.kt", "path": "app/src/main/kotlin/App.kt", "type": "file", "size": 100, "extension": "kt"},
        ]
        significant = self._build_and_filter(tree)
        assert "app/src/main/kotlin" in significant

    def test_fonts_folder_excluded(self):
        """Folder with only font files should be excluded."""
        tree = [
            {"name": "app.js", "path": "src/app.js", "type": "file", "size": 100, "extension": "js"},
            {"name": "Roboto.ttf", "path": "src/assets/fonts/Roboto.ttf", "type": "file", "size": 5000, "extension": "ttf"},
            {"name": "OpenSans.woff2", "path": "src/assets/fonts/OpenSans.woff2", "type": "file", "size": 3000, "extension": "woff2"},
        ]
        significant = self._build_and_filter(tree)
        assert "src/assets/fonts" not in significant

    def test_root_always_kept(self):
        """Root is always kept even if it has no source code files."""
        tree = [
            {"name": "README.md", "path": "README.md", "type": "file", "size": 100, "extension": "md"},
            {"name": "main.py", "path": "src/main.py", "type": "file", "size": 100, "extension": "py"},
        ]
        significant = self._build_and_filter(tree)
        assert "" in significant

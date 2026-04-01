"""Tests for BlueprintFolderMapper."""
import pytest

from domain.entities.blueprint import (
    StructuredBlueprint,
    BlueprintMeta,
    ArchitectureRules,
    Components,
    Component,
    Contract,
    FilePlacementRule,
    NamingConvention,
    QuickReference,
    Communication,
    CommunicationPattern,
    Technology,
    CodeTemplate,
    DeveloperRecipe,
    ArchitecturalPitfall,
    ImplementationGuideline,
)
from application.services.blueprint_folder_mapper import (
    BlueprintFolderMapper,
    _normalize_path,
    compute_blueprint_hash,
)


@pytest.fixture
def mapper():
    return BlueprintFolderMapper()


# ── Path normalization ──

class TestPathNormalization:

    def test_trailing_slash(self):
        assert _normalize_path("src/api/") == "src/api"

    def test_leading_dot_slash(self):
        assert _normalize_path("./src/api") == "src/api"

    def test_backslash(self):
        assert _normalize_path("src\\api\\routes") == "src/api/routes"

    def test_combined(self):
        assert _normalize_path("./src\\api/") == "src/api"

    def test_empty(self):
        assert _normalize_path("") == ""


# ── Path matching ──

class TestPathMatching:

    def test_exact_match(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                components=[Component(name="API", location="src/api", responsibility="HTTP endpoints")]
            )
        )
        result = mapper.map_all(bp, ["src/api"])
        assert result["src/api"].component_name == "API"
        assert result["src/api"].component_responsibility == "HTTP endpoints"

    def test_child_match(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                components=[Component(name="API", location="src/api", responsibility="HTTP layer")]
            )
        )
        result = mapper.map_all(bp, ["src/api/routes"])
        assert result["src/api/routes"].component_name == "API"

    def test_parent_match(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                components=[Component(name="Routes", location="src/api/routes", responsibility="Route defs")]
            )
        )
        result = mapper.map_all(bp, ["src/api"])
        assert result["src/api"].component_name == "Routes"

    def test_no_match(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                components=[Component(name="API", location="src/api", responsibility="HTTP")]
            )
        )
        result = mapper.map_all(bp, ["tests"])
        assert result["tests"].component_name == ""


# ── Component matching ──

class TestComponentMatching:

    def test_most_specific_wins(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                components=[
                    Component(name="Backend", location="src", responsibility="All backend"),
                    Component(name="API", location="src/api", responsibility="HTTP layer"),
                ]
            )
        )
        result = mapper.map_all(bp, ["src/api"])
        assert result["src/api"].component_name == "API"

    def test_depends_on_populated(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                components=[Component(
                    name="API", location="src/api",
                    depends_on=["Domain", "Infrastructure"],
                    exposes_to=["Frontend"],
                )]
            )
        )
        result = mapper.map_all(bp, ["src/api"])
        assert result["src/api"].depends_on == ["Domain", "Infrastructure"]
        assert result["src/api"].exposes_to == ["Frontend"]

    def test_key_interfaces_populated(self, mapper):
        from domain.entities.blueprint import KeyInterface
        bp = StructuredBlueprint(
            components=Components(
                components=[Component(
                    name="API", location="src/api",
                    key_interfaces=[KeyInterface(name="Router", methods=["get", "post"], description="HTTP methods")],
                )]
            )
        )
        result = mapper.map_all(bp, ["src/api"])
        assert len(result["src/api"].key_interfaces) == 1
        assert result["src/api"].key_interfaces[0]["name"] == "Router"


# ── Recipe matching ──

class TestRecipeMatching:

    def test_matches_by_file(self, mapper):
        bp = StructuredBlueprint(
            developer_recipes=[
                DeveloperRecipe(task="Add endpoint", files=["src/api/routes.py", "src/api/schemas.py"], steps=["Define route"])
            ]
        )
        result = mapper.map_all(bp, ["src/api"])
        assert len(result["src/api"].recipes) == 1
        assert result["src/api"].recipes[0]["task"] == "Add endpoint"

    def test_no_match(self, mapper):
        bp = StructuredBlueprint(
            developer_recipes=[
                DeveloperRecipe(task="Add endpoint", files=["src/api/routes.py"], steps=["Define route"])
            ]
        )
        result = mapper.map_all(bp, ["tests"])
        assert len(result["tests"].recipes) == 0

    def test_multiple_recipes(self, mapper):
        bp = StructuredBlueprint(
            developer_recipes=[
                DeveloperRecipe(task="Add endpoint", files=["src/api/routes.py"], steps=["Step 1"]),
                DeveloperRecipe(task="Add middleware", files=["src/api/middleware.py"], steps=["Step A"]),
            ]
        )
        result = mapper.map_all(bp, ["src/api"])
        assert len(result["src/api"].recipes) == 2


# ── Pitfall matching ──

class TestPitfallMatching:

    def test_keyword_match(self, mapper):
        bp = StructuredBlueprint(
            pitfalls=[
                ArchitecturalPitfall(area="API routes", description="Don't put logic in routes", recommendation="Use services")
            ]
        )
        result = mapper.map_all(bp, ["src/api/routes"])
        assert len(result["src/api/routes"].pitfalls) == 1

    def test_no_false_positive(self, mapper):
        bp = StructuredBlueprint(
            pitfalls=[
                ArchitecturalPitfall(area="Database migrations", description="Check schema", recommendation="Test first")
            ]
        )
        result = mapper.map_all(bp, ["src/api"])
        assert len(result["src/api"].pitfalls) == 0


# ── Full mapping ──

class TestFullMapping:

    def test_coverage_flag_set(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                components=[Component(name="API", location="src/api", responsibility="HTTP")]
            )
        )
        result = mapper.map_all(bp, ["src/api", "tests"])
        assert result["src/api"].has_blueprint_coverage is True
        assert result["tests"].has_blueprint_coverage is False

    def test_children_summaries_populated(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                components=[
                    Component(name="API", location="src/api", responsibility="HTTP layer"),
                    Component(name="Routes", location="src/api/routes", responsibility="Route defs"),
                ]
            )
        )
        result = mapper.map_all(bp, ["src/api", "src/api/routes"])
        assert len(result["src/api"].children_summaries) == 1
        assert result["src/api"].children_summaries[0]["path"] == "src/api/routes"

    def test_file_placement_rules(self, mapper):
        bp = StructuredBlueprint(
            architecture_rules=ArchitectureRules(
                file_placement_rules=[
                    FilePlacementRule(
                        component_type="route", naming_pattern="*_routes.py",
                        location="src/api", description="API route files"
                    )
                ]
            )
        )
        result = mapper.map_all(bp, ["src/api", "src/api/routes"])
        assert len(result["src/api"].file_placement_rules) == 1
        assert len(result["src/api/routes"].file_placement_rules) == 1

    def test_naming_conventions_global(self, mapper):
        bp = StructuredBlueprint(
            architecture_rules=ArchitectureRules(
                naming_conventions=[
                    NamingConvention(scope="classes", pattern="PascalCase", examples=["UserService"])
                ]
            )
        )
        result = mapper.map_all(bp, ["src", "tests"])
        assert len(result["src"].naming_conventions) == 1
        assert len(result["tests"].naming_conventions) == 1

    def test_where_to_put(self, mapper):
        bp = StructuredBlueprint(
            quick_reference=QuickReference(where_to_put_code={"routes": "src/api/routes"})
        )
        result = mapper.map_all(bp, ["src/api/routes"])
        assert "routes" in result["src/api/routes"].where_to_put

    def test_contracts_matching(self, mapper):
        bp = StructuredBlueprint(
            components=Components(
                contracts=[
                    Contract(
                        interface_name="RepositoryInterface",
                        description="Data access",
                        methods=["find", "save"],
                        implementing_files=["src/infrastructure/repo.py"],
                    )
                ]
            )
        )
        result = mapper.map_all(bp, ["src/infrastructure"])
        assert len(result["src/infrastructure"].contracts) == 1

    def test_templates_matching(self, mapper):
        bp = StructuredBlueprint(
            technology=Technology(
                templates=[
                    CodeTemplate(
                        component_type="route",
                        file_path_template="src/api/routes/{name}_routes.py",
                        code="# route template",
                    )
                ]
            )
        )
        result = mapper.map_all(bp, ["src/api/routes"])
        assert len(result["src/api/routes"].templates) == 1


# ── Navigation fields ──

class TestNavigationFields:

    def test_peer_paths_populated(self, mapper):
        bp = StructuredBlueprint()
        result = mapper.map_all(bp, ["src/api", "src/domain", "src/infra"])
        peers = result["src/api"].peer_paths
        assert "src/domain" in peers
        assert "src/infra" in peers

    def test_parent_path_set(self, mapper):
        bp = StructuredBlueprint()
        result = mapper.map_all(bp, ["src", "src/api"])
        assert result["src/api"].parent_path == "src"
        assert result["src"].parent_path == ""

    def test_children_have_correct_peers(self, mapper):
        bp = StructuredBlueprint()
        result = mapper.map_all(bp, ["src", "src/api", "src/domain"])
        # api and domain should be peers
        assert "src/domain" in result["src/api"].peer_paths
        assert "src/api" in result["src/domain"].peer_paths


# ── Blueprint hash ──

class TestBlueprintHash:

    def test_same_blueprint_same_hash(self):
        ts = "2024-01-01T00:00:00+00:00"
        bp1 = StructuredBlueprint(meta=BlueprintMeta(repository="test", analyzed_at=ts))
        bp2 = StructuredBlueprint(meta=BlueprintMeta(repository="test", analyzed_at=ts))
        assert compute_blueprint_hash(bp1) == compute_blueprint_hash(bp2)

    def test_different_blueprint_different_hash(self):
        bp1 = StructuredBlueprint(meta=BlueprintMeta(repository="test1"))
        bp2 = StructuredBlueprint(meta=BlueprintMeta(repository="test2"))
        assert compute_blueprint_hash(bp1) != compute_blueprint_hash(bp2)

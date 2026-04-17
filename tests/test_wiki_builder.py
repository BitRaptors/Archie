"""Tests for wiki_builder.py — deterministic blueprint → markdown generator."""

import sys
from pathlib import Path

# Make archie/standalone importable — mirrors how consumer projects use .archie/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

import json

import wiki_builder  # noqa: E402


def test_slugify_basic():
    assert wiki_builder.slugify("User Service") == "user-service"
    assert wiki_builder.slugify("PostgreSQL as primary store") == "postgresql-as-primary-store"
    assert wiki_builder.slugify("JWT over sessions") == "jwt-over-sessions"


def test_slugify_collision_suffix():
    seen: set[str] = set()
    a = wiki_builder.slugify_unique("User", seen)
    b = wiki_builder.slugify_unique("User", seen)
    c = wiki_builder.slugify_unique("User", seen)
    assert a == "user"
    assert b == "user-2"
    assert c == "user-3"


def test_slugify_strips_non_alnum():
    assert wiki_builder.slugify("Auth/Flow: v2!") == "auth-flow-v2"
    assert wiki_builder.slugify("   spaced   out   ") == "spaced-out"


def test_render_decision_page_basic():
    decision = {
        "title": "PostgreSQL as primary store",
        "chosen": "PostgreSQL 15",
        "rationale": "ACID guarantees for user data",
        "forced_by": "Compliance requirements",
        "enables": "Point-in-time recovery",
        "alternatives_rejected": ["MongoDB (no ACID)"],
    }
    md = wiki_builder.render_decision(decision, slug="postgresql-as-primary-store")
    assert md.startswith("---\n")
    assert "type: decision" in md
    assert "slug: postgresql-as-primary-store" in md
    assert "# PostgreSQL as primary store" in md
    assert "**Chosen:** PostgreSQL 15" in md
    assert "Compliance requirements" in md
    assert "MongoDB (no ACID)" in md


def test_render_decision_page_missing_optional_fields():
    decision = {
        "title": "Minimal decision",
        "chosen": "Option A",
    }
    md = wiki_builder.render_decision(decision, slug="minimal-decision")
    # Missing fields render as "N/A" or are omitted, but rendering must not crash
    assert "# Minimal decision" in md
    assert "**Chosen:** Option A" in md


def test_render_component_page_links_depends_on():
    component = {
        "name": "UserService",
        "purpose": "User auth and lifecycle",
        "depends_on": ["UserRepository"],
        "exposes_to": ["AuthController"],
    }
    component_slugs = {"UserService": "user-service", "UserRepository": "user-repository", "AuthController": "auth-controller"}
    md = wiki_builder.render_component(component, slug="user-service", component_slugs=component_slugs)
    assert "# UserService" in md
    assert "[UserRepository](../components/user-repository.md)" in md
    assert "[AuthController](../components/auth-controller.md)" in md
    assert "User auth and lifecycle" in md


def test_render_component_page_handles_unknown_reference():
    component = {
        "name": "OrphanService",
        "purpose": "Depends on something not in the blueprint",
        "depends_on": ["ExternalThing"],
    }
    component_slugs = {"OrphanService": "orphan-service"}
    md = wiki_builder.render_component(component, slug="orphan-service", component_slugs=component_slugs)
    # Unknown references render as plain text, not broken links
    assert "ExternalThing" in md
    assert "[ExternalThing]" not in md


def test_render_pattern_page():
    pattern = {
        "name": "Repository",
        "when_to_use": "When abstracting data access",
        "when_not_to_use": "For trivial CRUD",
    }
    md = wiki_builder.render_pattern(pattern, slug="repository")
    assert "# Repository" in md
    assert "type: pattern" in md
    assert "When abstracting data access" in md
    assert "For trivial CRUD" in md


def test_render_pitfall_page_with_stems_from_link():
    pitfall = {
        "area": "Password storage",
        "description": "Plain text passwords",
        "stems_from": "PostgreSQL as primary store",
        "recommendation": "Hash with bcrypt",
    }
    decision_slugs = {"PostgreSQL as primary store": "postgresql-as-primary-store"}
    md = wiki_builder.render_pitfall(
        pitfall, slug="password-storage", decision_slugs=decision_slugs
    )
    assert "# Password storage" in md
    assert "Plain text passwords" in md
    assert "[PostgreSQL as primary store](../decisions/postgresql-as-primary-store.md)" in md
    assert "Hash with bcrypt" in md


def test_render_pitfall_page_with_unknown_stems_from():
    pitfall = {"area": "Foo", "description": "Bar", "stems_from": "UnknownDecision", "recommendation": "Fix"}
    md = wiki_builder.render_pitfall(pitfall, slug="foo", decision_slugs={})
    # Unknown stems_from still renders the prose
    assert "UnknownDecision" in md
    assert "[UnknownDecision]" not in md


def test_render_index():
    fixture = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"
    blueprint = json.loads(fixture.read_text())
    slug_map = {
        "decisions": {
            "PostgreSQL as primary store": "postgresql-as-primary-store",
            "JWT over sessions": "jwt-over-sessions",
        },
        "components": {
            "UserService": "user-service",
            "UserRepository": "user-repository",
            "AuthController": "auth-controller",
        },
        "patterns": {"Repository": "repository"},
        "pitfalls": {"Password storage": "password-storage"},
    }
    md = wiki_builder.render_index(blueprint, slug_map)
    assert "# TestProject Wiki" in md
    assert "## Browse by type" in md
    assert "Decisions (2)" in md
    assert "Components (3)" in md
    assert "Patterns (1)" in md
    assert "Pitfalls (1)" in md
    # At least one link into a sub-page
    assert "[PostgreSQL as primary store](./decisions/postgresql-as-primary-store.md)" in md


def test_render_capability_page_links_all_relations():
    capability = {
        "name": "User Authentication",
        "purpose": "Users sign up, log in, and receive a JWT.",
        "entry_points": [
            "POST /api/auth/login -> AuthController.login",
            "screens/LoginScreen.tsx",
        ],
        "uses_components": ["UserService", "AuthController"],
        "constrained_by_decisions": ["JWT over sessions"],
        "related_pitfalls": ["Password storage"],
        "key_files": ["features/auth/**"],
        "evidence": ["features/auth/**"],
        "provenance": "INFERRED",
    }
    slugs = {
        "components": {"UserService": "user-service", "AuthController": "auth-controller"},
        "decisions": {"JWT over sessions": "jwt-over-sessions"},
        "pitfalls": {"Password storage": "password-storage"},
    }
    md = wiki_builder.render_capability(capability, slug="user-authentication", slugs=slugs)
    assert "type: capability" in md
    assert "provenance: INFERRED" in md
    assert "# User Authentication" in md
    assert "POST /api/auth/login -> AuthController.login" in md
    assert "[UserService](../components/user-service.md)" in md
    assert "[AuthController](../components/auth-controller.md)" in md
    assert "[JWT over sessions](../decisions/jwt-over-sessions.md)" in md
    assert "[Password storage](../pitfalls/password-storage.md)" in md
    assert "features/auth/**" in md


def test_render_capability_tolerates_missing_fields():
    capability = {"name": "Minimal cap", "purpose": "Just a name"}
    md = wiki_builder.render_capability(
        capability, slug="minimal-cap", slugs={"components": {}, "decisions": {}, "pitfalls": {}}
    )
    assert "# Minimal cap" in md
    assert "type: capability" in md


def test_render_index_promotes_capabilities_at_top():
    fixture = Path(__file__).parent / "fixtures" / "wiki_fixture_blueprint.json"
    blueprint = json.loads(fixture.read_text())
    slug_map = {
        "decisions": {"PostgreSQL as primary store": "postgresql-as-primary-store"},
        "components": {"UserService": "user-service"},
        "patterns": {"Repository": "repository"},
        "pitfalls": {"Password storage": "password-storage"},
        "capabilities": {"User Authentication": "user-authentication"},
    }
    md = wiki_builder.render_index(blueprint, slug_map)
    assert "## Before you implement anything" in md
    # The capabilities section comes before the "Browse by type" section.
    before_idx = md.index("## Before you implement anything")
    browse_idx = md.index("## Browse by type")
    assert before_idx < browse_idx
    assert "[User Authentication](./capabilities/user-authentication.md)" in md
    assert "Capabilities (1)" in md


def test_as_text_handles_list():
    assert wiki_builder._as_text([]) == ""
    assert wiki_builder._as_text(["a", "b"]) == "a\nb"
    assert wiki_builder._as_text(["  spaced  ", "", "x"]) == "spaced\nx"


def test_as_text_handles_none_and_str():
    assert wiki_builder._as_text(None) == ""
    assert wiki_builder._as_text("  hello  ") == "hello"


def test_render_pitfall_handles_list_stems_from():
    pitfall = {
        "area": "Multi-upstream",
        "description": "Linked to 2 decisions",
        "stems_from": ["Decision A", "Decision B"],
        "recommendation": "Review",
    }
    decision_slugs = {"Decision A": "decision-a", "Decision B": "decision-b"}
    md = wiki_builder.render_pitfall(pitfall, slug="multi", decision_slugs=decision_slugs)
    assert "[Decision A](../decisions/decision-a.md)" in md
    assert "[Decision B](../decisions/decision-b.md)" in md


def test_render_pitfall_handles_empty_list_stems_from():
    pitfall = {
        "area": "No upstream",
        "description": "Standalone",
        "stems_from": [],
        "recommendation": "Fix",
    }
    md = wiki_builder.render_pitfall(pitfall, slug="no-up", decision_slugs={})
    assert "# No upstream" in md
    assert "Stems from" not in md  # Empty list produces no section
    assert "Fix" in md


def test_render_decision_handles_list_fields():
    """Wave 2 may emit forced_by/enables as list in some blueprints."""
    decision = {
        "title": "Decision with list fields",
        "chosen": "X",
        "forced_by": ["reason 1", "reason 2"],
        "enables": ["outcome 1"],
    }
    md = wiki_builder.render_decision(decision, slug="test")
    assert "reason 1" in md
    assert "reason 2" in md
    assert "outcome 1" in md


def test_extract_components_from_list():
    bp = {"components": [{"name": "A"}, {"name": "B"}]}
    assert wiki_builder._extract_components(bp) == [{"name": "A"}, {"name": "B"}]


def test_extract_components_from_nested_dict():
    """Real Archie output sometimes wraps components in a dict."""
    bp = {"components": {"structure_type": "layered", "components": [{"name": "X"}]}}
    assert wiki_builder._extract_components(bp) == [{"name": "X"}]


def test_extract_components_empty_or_missing():
    assert wiki_builder._extract_components({}) == []
    assert wiki_builder._extract_components({"components": None}) == []
    assert wiki_builder._extract_components({"components": "weird"}) == []


def test_render_index_uses_project_root_fallback_for_name(tmp_path):
    blueprint = {"decisions": {}, "components": [], "pitfalls": [], "capabilities": []}
    slug_map = {"decisions": {}, "components": {}, "patterns": {}, "pitfalls": {}, "capabilities": {}}
    md = wiki_builder.render_index(blueprint, slug_map, project_root=tmp_path)
    assert f"# {tmp_path.name} Wiki" in md


def test_render_index_meta_project_name_takes_precedence(tmp_path):
    blueprint = {"meta": {"project_name": "ExplicitName"}}
    slug_map = {"decisions": {}, "components": {}, "patterns": {}, "pitfalls": {}, "capabilities": {}}
    md = wiki_builder.render_index(blueprint, slug_map, project_root=tmp_path)
    assert "# ExplicitName Wiki" in md
    assert f"# {tmp_path.name}" not in md

"""Tests for wiki_builder.py — deterministic blueprint → markdown generator."""

import sys
from pathlib import Path

# Make archie/standalone importable — mirrors how consumer projects use .archie/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))

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

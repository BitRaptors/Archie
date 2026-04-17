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

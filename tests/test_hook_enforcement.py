"""Tests for archie.hooks.enforcement — extracted hook validation logic."""

from __future__ import annotations

from archie.hooks.enforcement import check_pre_validate, match_context_rules


# ---------------------------------------------------------------------------
# Pre-validate: file placement
# ---------------------------------------------------------------------------


def test_file_placement_pass():
    """File inside an allowed directory passes."""
    rules = [
        {
            "id": "placement-1",
            "check": "file_placement",
            "severity": "warn",
            "allowed_dirs": ["src/services/", "src/utils/"],
            "description": "Service files go in src/services",
        }
    ]
    result = check_pre_validate("src/services/auth.py", rules)
    assert result["pass"] is True
    assert result["warnings"] == []
    assert result["errors"] == []


def test_file_placement_warn():
    """File NOT in allowed dir with severity=warn produces a warning."""
    rules = [
        {
            "id": "placement-1",
            "check": "file_placement",
            "severity": "warn",
            "allowed_dirs": ["src/services/"],
            "description": "Service files go in src/services",
        }
    ]
    result = check_pre_validate("lib/helpers/auth.py", rules)
    assert result["pass"] is True  # warnings don't block
    assert len(result["warnings"]) == 1
    assert "placement-1" in result["warnings"][0]
    assert result["errors"] == []


def test_file_placement_block():
    """File NOT in allowed dir with severity=error produces an error and blocks."""
    rules = [
        {
            "id": "placement-1",
            "check": "file_placement",
            "severity": "error",
            "allowed_dirs": ["src/services/"],
            "description": "Service files must be in src/services",
        }
    ]
    result = check_pre_validate("lib/helpers/auth.py", rules)
    assert result["pass"] is False
    assert len(result["errors"]) == 1
    assert "placement-1" in result["errors"][0]


# ---------------------------------------------------------------------------
# Pre-validate: naming
# ---------------------------------------------------------------------------


def test_naming_pass():
    """Filename matching the pattern passes."""
    rules = [
        {
            "id": "naming-1",
            "check": "naming",
            "severity": "warn",
            "pattern": r"^[a-z][a-z0-9_]*\.py$",
            "description": "Python files use snake_case",
        }
    ]
    result = check_pre_validate("src/my_module.py", rules)
    assert result["pass"] is True
    assert result["warnings"] == []


def test_naming_warn():
    """Filename NOT matching the pattern produces a warning."""
    rules = [
        {
            "id": "naming-1",
            "check": "naming",
            "severity": "warn",
            "pattern": r"^[a-z][a-z0-9_]*\.py$",
            "description": "Python files use snake_case",
        }
    ]
    result = check_pre_validate("src/MyModule.py", rules)
    assert result["pass"] is True
    assert len(result["warnings"]) == 1
    assert "naming-1" in result["warnings"][0]


# ---------------------------------------------------------------------------
# Pre-validate: edge cases
# ---------------------------------------------------------------------------


def test_no_rules():
    """Empty rules list always passes."""
    result = check_pre_validate("anything/goes/here.py", [])
    assert result["pass"] is True
    assert result["warnings"] == []
    assert result["errors"] == []


def test_check_returns_structured_result():
    """Result dict always has pass, warnings, errors keys."""
    result = check_pre_validate("foo.py", [])
    assert "pass" in result
    assert "warnings" in result
    assert "errors" in result
    assert isinstance(result["pass"], bool)
    assert isinstance(result["warnings"], list)
    assert isinstance(result["errors"], list)


# ---------------------------------------------------------------------------
# Context matching
# ---------------------------------------------------------------------------


def test_context_matching():
    """Prompt containing a keyword matches the rule."""
    rules = [
        {
            "id": "placement-1",
            "check": "file_placement",
            "severity": "warn",
            "keywords": ["service", "api"],
            "description": "Services go in src/services",
        }
    ]
    matched = match_context_rules("create a new service for auth", rules)
    assert len(matched) == 1
    assert matched[0]["id"] == "placement-1"


def test_context_always_includes_errors():
    """Error-severity rules are always included regardless of keywords."""
    rules = [
        {
            "id": "critical-1",
            "check": "file_placement",
            "severity": "error",
            "keywords": ["database"],
            "description": "Never put DB logic in controllers",
        },
        {
            "id": "soft-1",
            "check": "naming",
            "severity": "warn",
            "keywords": ["naming"],
            "description": "Use snake_case",
        },
    ]
    # Prompt has nothing to do with either rule's keywords.
    matched = match_context_rules("refactor the logging system", rules)
    # Error rule must be included, warn rule must not.
    assert any(r["id"] == "critical-1" for r in matched)
    assert not any(r["id"] == "soft-1" for r in matched)


def test_context_no_match_returns_empty():
    """Prompt with no keyword overlap returns no matches (excluding error rules)."""
    rules = [
        {
            "id": "placement-1",
            "check": "file_placement",
            "severity": "warn",
            "keywords": ["database"],
            "description": "DB files go in src/db",
        }
    ]
    matched = match_context_rules("fix the CSS styling", rules)
    assert matched == []


def test_context_token_fallback_match():
    """When no explicit keyword matches, token-from-description fallback works."""
    rules = [
        {
            "id": "layer-1",
            "check": "file_placement",
            "severity": "warn",
            "keywords": [],
            "description": "Repository implementations go in infrastructure",
        }
    ]
    # "infrastructure" (len > 3) appears in both description and prompt.
    matched = match_context_rules("add a new infrastructure adapter", rules)
    assert len(matched) == 1
    assert matched[0]["id"] == "layer-1"


def test_pre_validate_accepts_type_field():
    """Rules using legacy 'type' field (instead of 'check') still work."""
    rules = [
        {
            "id": "placement-1",
            "type": "file_placement",
            "severity": "warn",
            "allowed_dirs": ["src/"],
            "description": "All source in src/",
        }
    ]
    result = check_pre_validate("lib/foo.py", rules)
    assert len(result["warnings"]) == 1


# ---------------------------------------------------------------------------
# forbidden_content
# ---------------------------------------------------------------------------


def test_forbidden_content_blocks_on_match():
    rules = [
        {
            "id": "no-naive-dt",
            "check": "forbidden_content",
            "severity": "error",
            "forbidden_patterns": [r"datetime\.(utcnow|now)\s*\(\s*\)"],
            "description": "Use tz-aware datetime",
        }
    ]
    result = check_pre_validate(
        "src/foo.py", rules, content="t = datetime.utcnow()"
    )
    assert result["pass"] is False
    assert len(result["errors"]) == 1
    assert "no-naive-dt" in result["errors"][0]


def test_forbidden_content_passes_when_content_clean():
    rules = [
        {
            "id": "no-naive-dt",
            "check": "forbidden_content",
            "severity": "error",
            "forbidden_patterns": [r"datetime\.(utcnow|now)\s*\(\s*\)"],
            "description": "Use tz-aware datetime",
        }
    ]
    result = check_pre_validate(
        "src/foo.py", rules, content="t = datetime.now(tz=UTC)"
    )
    assert result["pass"] is True
    assert result["errors"] == []


def test_forbidden_content_scoped_by_applies_to():
    """applies_to prefix scopes the check to matching paths only."""
    rules = [
        {
            "id": "backend-only",
            "check": "forbidden_content",
            "severity": "warn",
            "applies_to": "backend/",
            "forbidden_patterns": [r"console\.log"],
            "description": "No console.log in backend",
        }
    ]
    # Outside scope — should NOT match.
    out = check_pre_validate(
        "frontend/app.ts", rules, content="console.log('hi')"
    )
    assert out["warnings"] == []
    # Inside scope — should match.
    inside = check_pre_validate(
        "backend/handler.ts", rules, content="console.log('hi')"
    )
    assert len(inside["warnings"]) == 1


def test_forbidden_content_skipped_when_no_content():
    """Content-based checks fail open when content is empty."""
    rules = [
        {
            "id": "no-naive-dt",
            "check": "forbidden_content",
            "severity": "error",
            "forbidden_patterns": [r"datetime\.utcnow"],
            "description": "x",
        }
    ]
    result = check_pre_validate("src/foo.py", rules, content="")
    assert result["pass"] is True


def test_forbidden_content_invalid_regex_does_not_crash():
    """A broken regex in one rule must not sink the whole hook."""
    rules = [
        {
            "id": "broken",
            "check": "forbidden_content",
            "severity": "error",
            "forbidden_patterns": ["[unclosed"],
            "description": "x",
        },
        {
            "id": "working",
            "check": "forbidden_content",
            "severity": "error",
            "forbidden_patterns": [r"BAD"],
            "description": "y",
        },
    ]
    result = check_pre_validate(
        "src/foo.py", rules, content="this is BAD code"
    )
    assert result["pass"] is False
    assert any("working" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# forbidden_import
# ---------------------------------------------------------------------------


def test_forbidden_import_blocks_on_match():
    rules = [
        {
            "id": "no-star-import",
            "check": "forbidden_import",
            "severity": "error",
            "applies_to": "src/",
            "forbidden_patterns": [r"from\s+\w+\s+import\s+\*"],
            "description": "No star imports",
        }
    ]
    result = check_pre_validate(
        "src/mod.py", rules, content="from os import *"
    )
    assert result["pass"] is False


def test_forbidden_import_requires_applies_to_match():
    rules = [
        {
            "id": "no-star-import",
            "check": "forbidden_import",
            "severity": "error",
            "applies_to": "src/",
            "forbidden_patterns": [r"from\s+\w+\s+import\s+\*"],
            "description": "No star imports",
        }
    ]
    # Path outside applies_to prefix.
    result = check_pre_validate(
        "tests/t.py", rules, content="from os import *"
    )
    assert result["pass"] is True
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# required_pattern
# ---------------------------------------------------------------------------


def test_required_pattern_warns_when_missing():
    rules = [
        {
            "id": "migrations-need-down",
            "check": "required_pattern",
            "severity": "warn",
            "file_pattern": "*_migration.py",
            "required_in_content": ["def downgrade("],
            "description": "Migrations need a downgrade()",
        }
    ]
    result = check_pre_validate(
        "db/001_migration.py",
        rules,
        content="def upgrade(): pass",
    )
    assert len(result["warnings"]) == 1


def test_required_pattern_passes_when_present():
    rules = [
        {
            "id": "migrations-need-down",
            "check": "required_pattern",
            "severity": "warn",
            "file_pattern": "*_migration.py",
            "required_in_content": ["def downgrade("],
            "description": "Migrations need a downgrade()",
        }
    ]
    result = check_pre_validate(
        "db/001_migration.py",
        rules,
        content="def upgrade(): pass\ndef downgrade(): pass",
    )
    assert result["pass"] is True
    assert result["warnings"] == []


def test_required_pattern_file_pattern_must_match():
    rules = [
        {
            "id": "migrations-need-down",
            "check": "required_pattern",
            "severity": "warn",
            "file_pattern": "*_migration.py",
            "required_in_content": ["def downgrade("],
            "description": "x",
        }
    ]
    # Filename doesn't match pattern — rule doesn't fire.
    result = check_pre_validate(
        "src/foo.py", rules, content="def upgrade(): pass"
    )
    assert result["warnings"] == []


# ---------------------------------------------------------------------------
# architectural_constraint
# ---------------------------------------------------------------------------


def test_architectural_constraint_blocks_cross_layer_import():
    rules = [
        {
            "id": "no-db-in-handlers",
            "check": "architectural_constraint",
            "severity": "error",
            "file_pattern": "*_handler.py",
            "forbidden_patterns": [r"from\s+\w+\.db\s+import"],
            "description": "Handlers must not import DB",
        }
    ]
    result = check_pre_validate(
        "api/user_handler.py",
        rules,
        content="from app.db import session",
    )
    assert result["pass"] is False
    assert any("no-db-in-handlers" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# file_naming
# ---------------------------------------------------------------------------


def test_file_naming_enforces_pattern_in_scope():
    rules = [
        {
            "id": "services-snake",
            "check": "file_naming",
            "severity": "warn",
            "applies_to": "src/services/*",
            "file_pattern": r"^[a-z][a-z0-9_]*\.py$",
            "description": "Services use snake_case",
        }
    ]
    # In scope, bad name.
    bad = check_pre_validate(
        "src/services/AuthService.py",
        rules,
        project_root="",
    )
    assert len(bad["warnings"]) == 1
    # In scope, good name.
    good = check_pre_validate(
        "src/services/auth_service.py",
        rules,
        project_root="",
    )
    assert good["warnings"] == []
    # Out of scope — rule doesn't fire even with bad name.
    out = check_pre_validate(
        "lib/Foo.py",
        rules,
        project_root="",
    )
    assert out["warnings"] == []


# ---------------------------------------------------------------------------
# project_root rewriting
# ---------------------------------------------------------------------------


def test_project_root_strips_prefix_for_applies_to():
    """Absolute path gets stripped to a rel path for applies_to matching."""
    rules = [
        {
            "id": "backend-only",
            "check": "forbidden_content",
            "severity": "error",
            "applies_to": "backend/",
            "forbidden_patterns": [r"console\.log"],
            "description": "x",
        }
    ]
    result = check_pre_validate(
        "/home/user/proj/backend/api.ts",
        rules,
        content="console.log('x')",
        project_root="/home/user/proj",
    )
    assert result["pass"] is False

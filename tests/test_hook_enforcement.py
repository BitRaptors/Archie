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

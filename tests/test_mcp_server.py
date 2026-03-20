"""Tests for the standalone MCP server tool logic."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from archie.mcp.server import (
    where_to_put,
    check_naming,
    get_architecture_rules,
    get_component_info,
    list_components,
    _load_blueprint,
)


def _sample_blueprint() -> dict:
    """Return a minimal blueprint dict for testing."""
    return {
        "architecture_rules": {
            "file_placement_rules": [
                {
                    "component_type": "service",
                    "location": "src/services/",
                    "naming_pattern": "*_service.py",
                    "example": "src/services/user_service.py",
                    "description": "Business logic services",
                },
                {
                    "component_type": "controller",
                    "location": "src/controllers/",
                    "naming_pattern": "*_controller.py",
                    "example": "src/controllers/user_controller.py",
                    "description": "HTTP request handlers",
                },
            ],
            "naming_conventions": [
                {
                    "scope": "classes",
                    "pattern": "^[A-Z][a-zA-Z0-9]+$",
                    "description": "PascalCase for class names",
                    "examples": ["UserService", "OrderController"],
                },
                {
                    "scope": "functions",
                    "pattern": "^[a-z_][a-z0-9_]*$",
                    "description": "snake_case for function names",
                    "examples": ["get_user", "create_order"],
                },
            ],
        },
        "components": {
            "structure_type": "layered",
            "components": [
                {
                    "name": "API Layer",
                    "location": "src/api/",
                    "responsibility": "Handle HTTP requests and routing",
                    "platform": "backend",
                    "depends_on": ["Service Layer"],
                    "exposes_to": [],
                    "key_files": [
                        {"path": "src/api/routes.py", "purpose": "Route definitions"},
                    ],
                    "key_interfaces": [
                        {"name": "Router", "description": "FastAPI router", "methods": ["get", "post"]},
                    ],
                },
                {
                    "name": "Service Layer",
                    "location": "src/services/",
                    "responsibility": "Business logic orchestration",
                    "platform": "backend",
                    "depends_on": ["Data Layer"],
                    "exposes_to": ["API Layer"],
                    "key_files": [
                        {"path": "src/services/user_service.py", "purpose": "User operations"},
                    ],
                    "key_interfaces": [],
                },
            ],
        },
        "quick_reference": {
            "where_to_put_code": {
                "models": "src/models/",
                "tests": "tests/",
            },
        },
    }


# ── Test: where_to_put ───────────────────────────────────────────────────

def test_where_to_put_finds_match():
    """Loading a blueprint with file_placement_rules returns correct directory."""
    bp = _sample_blueprint()
    result = where_to_put(bp, "service")
    assert "src/services/" in result
    assert "*_service.py" in result
    assert "Where to put: service" in result


def test_where_to_put_no_match():
    """Unmatched component type lists available types."""
    bp = _sample_blueprint()
    result = where_to_put(bp, "middleware")
    assert "No placement rule found" in result
    assert "service" in result


def test_where_to_put_quick_reference():
    """Matches from quick_reference.where_to_put_code are included."""
    bp = _sample_blueprint()
    result = where_to_put(bp, "models")
    assert "src/models/" in result


# ── Test: check_naming ───────────────────────────────────────────────────

def test_check_naming_valid():
    """A valid PascalCase class name passes validation."""
    bp = _sample_blueprint()
    result = check_naming(bp, "classes", "UserService")
    assert "**OK**" in result
    assert "is_valid" in result
    assert '"is_valid": true' in result


def test_check_naming_invalid():
    """An invalid class name is flagged with a suggestion."""
    bp = _sample_blueprint()
    result = check_naming(bp, "classes", "user_service")
    assert "**NAMING ISSUE**" in result
    assert "user_service" in result
    assert '"is_valid": false' in result


def test_check_naming_unknown_scope():
    """An unknown scope returns available scopes."""
    bp = _sample_blueprint()
    result = check_naming(bp, "variables", "foo")
    assert "No naming convention found" in result
    assert "Available scopes" in result


# ── Test: get_architecture_rules ─────────────────────────────────────────

def test_get_architecture_rules():
    """Returns formatted architecture rules."""
    bp = _sample_blueprint()
    result = get_architecture_rules(bp)
    assert "# Architecture Rules" in result
    assert "File Placement Rules" in result
    assert "Naming Conventions" in result
    assert "service" in result.lower()
    assert "PascalCase" in result


def test_get_architecture_rules_empty():
    """Empty rules returns appropriate message."""
    result = get_architecture_rules({"architecture_rules": {}})
    assert "No architecture rules found" in result


# ── Test: list_components ────────────────────────────────────────────────

def test_list_components():
    """Lists all component names with locations."""
    bp = _sample_blueprint()
    result = list_components(bp)
    assert "API Layer" in result
    assert "Service Layer" in result
    assert "src/api/" in result
    assert "src/services/" in result


def test_list_components_empty():
    """Empty components returns appropriate message."""
    result = list_components({"components": {"components": []}})
    assert "No components found" in result


# ── Test: get_component_info ─────────────────────────────────────────────

def test_get_component_info():
    """Returns details for a known component."""
    bp = _sample_blueprint()
    result = get_component_info(bp, "API Layer")
    assert "API Layer" in result
    assert "src/api/" in result
    assert "HTTP requests" in result
    assert "routes.py" in result


def test_get_component_info_not_found():
    """Unknown component lists available ones."""
    bp = _sample_blueprint()
    result = get_component_info(bp, "Nonexistent")
    assert "not found" in result
    assert "API Layer" in result


# ── Test: no blueprint ───────────────────────────────────────────────────

def test_no_blueprint():
    """Graceful handling when no blueprint exists on disk."""
    with tempfile.TemporaryDirectory() as tmp:
        result = _load_blueprint(Path(tmp))
        assert result is None


def test_no_blueprint_with_archie_dir():
    """Graceful handling when .archie/ exists but no blueprint.json."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / ".archie").mkdir()
        result = _load_blueprint(Path(tmp))
        assert result is None


def test_load_blueprint_valid():
    """Successfully loads a valid blueprint.json."""
    with tempfile.TemporaryDirectory() as tmp:
        archie_dir = Path(tmp) / ".archie"
        archie_dir.mkdir()
        bp = _sample_blueprint()
        (archie_dir / "blueprint.json").write_text(json.dumps(bp))
        result = _load_blueprint(Path(tmp))
        assert result is not None
        assert "architecture_rules" in result

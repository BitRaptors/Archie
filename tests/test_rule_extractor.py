"""Tests for archie.rules.extractor."""

from __future__ import annotations

import pytest
from pathlib import Path

from archie.rules.extractor import (
    extract_rules,
    save_rules,
    load_rules,
    promote_rule,
    demote_rule,
)


@pytest.fixture()
def _minimal_blueprint() -> dict:
    return {
        "architecture_rules": {
            "file_placement_rules": [
                {
                    "description": "API routes live in the routes directory",
                    "allowed_dirs": ["src/api/routes"],
                },
                {
                    "description": "Domain entities belong in domain layer",
                    "allowed_dirs": ["src/domain/entities"],
                },
            ],
            "naming_conventions": [
                {
                    "description": "Python modules use snake case naming",
                    "convention": "snake_case",
                },
            ],
        },
        "components": {
            "components": [
                {
                    "name": "AuthService",
                    "path": "src/services/auth",
                    "description": "Handles authentication and authorization",
                },
                {
                    "name": "UserRepository",
                    "path": "src/repositories/user",
                    "description": "Persists user data to the database",
                },
            ],
        },
    }


def test_extract_rules_from_blueprint(_minimal_blueprint: dict) -> None:
    rules = extract_rules(_minimal_blueprint)
    assert len(rules) > 0
    for rule in rules:
        assert "id" in rule
        assert rule["severity"] == "warn"
        assert rule["source"] == "blueprint"
        assert "confidence" in rule
        assert 0.0 <= rule["confidence"] <= 1.0


def test_extract_rules_uses_blueprint_confidence(_minimal_blueprint: dict) -> None:
    """Confidence should come from blueprint meta, not be hardcoded."""
    bp = dict(_minimal_blueprint)
    bp["meta"] = {"confidence": {"architecture_rules": 0.85, "components": 0.7}}
    rules = extract_rules(bp)
    placement_rules = [r for r in rules if r["id"].startswith("placement-")]
    naming_rules = [r for r in rules if r["id"].startswith("naming-")]
    layer_rules = [r for r in rules if r["id"].startswith("layer-")]
    for r in placement_rules:
        assert r["confidence"] == 0.85
    for r in naming_rules:
        assert r["confidence"] == 0.85
    for r in layer_rules:
        assert r["confidence"] == 0.7


def test_extract_rules_has_file_placement(_minimal_blueprint: dict) -> None:
    rules = extract_rules(_minimal_blueprint)
    placement_rules = [r for r in rules if r["check"] == "file_placement"]
    assert len(placement_rules) >= 1


def test_extract_rules_has_naming(_minimal_blueprint: dict) -> None:
    rules = extract_rules(_minimal_blueprint)
    naming_rules = [r for r in rules if r["check"] == "naming"]
    assert len(naming_rules) >= 1


def test_save_and_load_rules(tmp_path: Path) -> None:
    rules = [
        {"id": "placement-1", "check": "file_placement", "severity": "warn", "allowed_dirs": ["src/api"]},
        {"id": "naming-1", "check": "naming", "severity": "warn", "pattern": "^[a-z][a-z0-9_]*$"},
    ]
    save_rules(tmp_path, rules)
    loaded = load_rules(tmp_path)
    assert loaded == rules


def test_promote_rule(tmp_path: Path) -> None:
    rules = [
        {"id": "placement-1", "check": "file_placement", "severity": "warn"},
    ]
    save_rules(tmp_path, rules)
    result = promote_rule(tmp_path, "placement-1")
    assert result is True
    loaded = load_rules(tmp_path)
    assert loaded[0]["severity"] == "error"


def test_demote_rule(tmp_path: Path) -> None:
    rules = [
        {"id": "placement-1", "check": "file_placement", "severity": "error"},
    ]
    save_rules(tmp_path, rules)
    result = demote_rule(tmp_path, "placement-1")
    assert result is True
    loaded = load_rules(tmp_path)
    assert loaded[0]["severity"] == "warn"


def test_promote_nonexistent_rule(tmp_path: Path) -> None:
    rules = [
        {"id": "placement-1", "check": "file_placement", "severity": "warn"},
    ]
    save_rules(tmp_path, rules)
    result = promote_rule(tmp_path, "nonexistent-99")
    assert result is False

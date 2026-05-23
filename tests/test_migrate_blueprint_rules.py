"""Tests for the legacy-blueprint → proposed-rules migration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.fixture
def project_with_legacy_blueprint(tmp_path: Path) -> Path:
    """Blueprint with all four legacy rule sections + empty rules.json
    + empty proposed_rules.json. The shape mimics what a pre-3.0 deep
    scan would have produced."""
    archie = tmp_path / ".archie"
    blueprint = {
        "meta": {"scan_count": 1},
        "components": {"components": [{"name": "x"}]},
        "architecture_rules": {
            "file_placement_rules": [
                {
                    "pattern": "*ViewModel.kt",
                    "kind": "ViewModel",
                    "location": "app/src/main/java/.../page_*/",
                    "scope": "all features",
                    "rationale": "ViewModels live with their pages",
                },
                {
                    "pattern": "*Repository.kt",
                    "kind": "Repository",
                    "location": "app/src/main/java/.../domain/repository/",
                    "rationale": "Repositories live in the domain layer",
                },
            ],
            "naming_conventions": [
                {
                    "pattern": "*ViewModel.kt",
                    "scope": "feature ViewModels",
                    "applies_to": "page_*",
                    "examples": ["LoginViewModel.kt", "DashboardViewModel.kt"],
                    "rationale": "Distinguishes view models from regular Kotlin classes",
                },
            ],
        },
        "development_rules": [
            "Always validate input at the boundary",
            {
                "rule": "Prefer composition over inheritance",
                "severity_class": "pattern_divergence",
                "rationale": "Inheritance creates rigid couplings",
            },
        ],
        "infrastructure_rules": [
            "Keep all secrets out of source control",
            {"rule": "Use environment-specific build variants for API URLs"},
        ],
    }
    _write_json(archie / "blueprint.json", blueprint)
    _write_json(archie / "rules.json", {"rules": []})
    _write_json(archie / "proposed_rules.json", {"rules": []})
    return tmp_path


@pytest.fixture
def project_with_no_legacy(tmp_path: Path) -> Path:
    """Clean modern blueprint — migrate() should be a no-op."""
    archie = tmp_path / ".archie"
    _write_json(archie / "blueprint.json", {
        "meta": {"scan_count": 1},
        "components": {"components": []},
    })
    _write_json(archie / "rules.json", {"rules": []})
    _write_json(archie / "proposed_rules.json", {"rules": []})
    return tmp_path


def test_migrate_converts_all_four_sections(project_with_legacy_blueprint: Path):
    from migrate_blueprint_rules import migrate

    summary = migrate(project_with_legacy_blueprint)

    # Expect: 2 file_placement + 1 naming_convention + 2 dev practices + 2 infra practices = 7
    assert summary["added"] == 7
    assert summary["skipped"] == 0
    assert set(summary["sections_stripped"]) == {
        "architecture_rules.file_placement_rules",
        "architecture_rules.naming_conventions",
        "development_rules",
        "infrastructure_rules",
    }


def test_migrate_writes_proposed_with_kind_and_stable_id(project_with_legacy_blueprint: Path):
    from migrate_blueprint_rules import migrate

    migrate(project_with_legacy_blueprint)
    proposed = _read_json(project_with_legacy_blueprint / ".archie" / "proposed_rules.json")
    rules = proposed["rules"]

    kinds = [r["kind"] for r in rules]
    assert kinds.count("file_placement") == 2
    assert kinds.count("naming_convention") == 1
    assert kinds.count("coding_practice") == 2  # development_rules only
    assert kinds.count("infrastructure") == 2   # infrastructure_rules

    # Every rule has an id with the bp-<prefix>- shape, severity class, and
    # source stamped as blueprint_migrated.
    for r in rules:
        assert r["id"].startswith("bp-")
        assert r["severity_class"] == "pattern_divergence"
        assert r["source"] == "blueprint_migrated"
        assert isinstance(r["description"], str) and r["description"]

    # The naming_convention rule should carry the existing check field that
    # the pre-validate hook can consume directly.
    nc = next(r for r in rules if r["kind"] == "naming_convention")
    assert nc["check"] == "file_naming"
    assert nc["file_pattern"] == "*ViewModel.kt"


def test_migrate_strips_legacy_sections_from_blueprint(project_with_legacy_blueprint: Path):
    from migrate_blueprint_rules import migrate

    migrate(project_with_legacy_blueprint)
    bp = _read_json(project_with_legacy_blueprint / ".archie" / "blueprint.json")

    # All four legacy paths must be gone
    assert "development_rules" not in bp
    assert "infrastructure_rules" not in bp
    # architecture_rules itself is dropped because it became empty after the
    # two nested keys were removed
    assert "architecture_rules" not in bp
    # Untouched fields stay
    assert bp["meta"]["scan_count"] == 1
    assert bp["components"]["components"] == [{"name": "x"}]


def test_migrate_is_idempotent(project_with_legacy_blueprint: Path):
    from migrate_blueprint_rules import migrate

    first = migrate(project_with_legacy_blueprint)
    second = migrate(project_with_legacy_blueprint)

    # The second pass has nothing to do — legacy sections are gone
    assert first["added"] == 7
    assert second["added"] == 0
    assert second["sections_stripped"] == []


def test_migrate_skips_already_adopted_rules(tmp_path: Path):
    """If a rule with the same hash-derived id is already in rules.json,
    don't re-propose it."""
    from migrate_blueprint_rules import migrate, _stable_id

    archie = tmp_path / ".archie"

    # Compute the id the migration WILL generate for the file_placement entry
    fp_entry = {"pattern": "*Repo.kt", "location": "domain/", "kind": "Repository"}
    expected_id = _stable_id("fp", fp_entry)

    _write_json(archie / "blueprint.json", {
        "architecture_rules": {
            "file_placement_rules": [
                {
                    "pattern": "*Repo.kt",
                    "kind": "Repository",
                    "location": "domain/",
                    "rationale": "Repositories live in domain",
                }
            ]
        }
    })
    _write_json(archie / "rules.json", {"rules": [{"id": expected_id, "description": "already adopted"}]})
    _write_json(archie / "proposed_rules.json", {"rules": []})

    summary = migrate(tmp_path)

    assert summary["added"] == 0
    assert summary["skipped"] == 1
    proposed = _read_json(archie / "proposed_rules.json")
    assert proposed["rules"] == []


def test_migrate_skips_already_ignored_rules(tmp_path: Path):
    """If the user rejected this rule before, don't re-propose it."""
    from migrate_blueprint_rules import migrate, _stable_id

    archie = tmp_path / ".archie"

    fp_entry = {"pattern": "*Repo.kt", "location": "domain/", "kind": "Repository"}
    expected_id = _stable_id("fp", fp_entry)

    _write_json(archie / "blueprint.json", {
        "architecture_rules": {
            "file_placement_rules": [
                {"pattern": "*Repo.kt", "kind": "Repository", "location": "domain/"}
            ]
        }
    })
    _write_json(archie / "rules.json", {"rules": []})
    _write_json(archie / "proposed_rules.json", {"rules": []})
    _write_json(archie / "ignored_rules.json", {"rules": [{"id": expected_id}]})

    summary = migrate(tmp_path)
    assert summary["added"] == 0
    assert summary["skipped"] == 1


def test_migrate_skips_already_proposed_rules(tmp_path: Path):
    """If a previous partial migration already proposed this, don't duplicate."""
    from migrate_blueprint_rules import migrate, _stable_id

    archie = tmp_path / ".archie"

    fp_entry = {"pattern": "*Repo.kt", "location": "domain/", "kind": "Repository"}
    expected_id = _stable_id("fp", fp_entry)

    _write_json(archie / "blueprint.json", {
        "architecture_rules": {
            "file_placement_rules": [
                {"pattern": "*Repo.kt", "kind": "Repository", "location": "domain/"}
            ]
        }
    })
    _write_json(archie / "rules.json", {"rules": []})
    _write_json(archie / "proposed_rules.json", {"rules": [{"id": expected_id}]})

    summary = migrate(tmp_path)
    assert summary["added"] == 0
    assert summary["skipped"] == 1
    proposed = _read_json(archie / "proposed_rules.json")
    assert len(proposed["rules"]) == 1  # the existing one, not doubled


def test_migrate_handles_no_legacy_sections(project_with_no_legacy: Path):
    from migrate_blueprint_rules import migrate

    summary = migrate(project_with_no_legacy)
    assert summary["added"] == 0
    assert summary["sections_stripped"] == []


def test_migrate_handles_malformed_section_entries(tmp_path: Path):
    """Garbage entries (string where a dict was expected, missing fields)
    get silently skipped rather than crashing the migration."""
    from migrate_blueprint_rules import migrate

    archie = tmp_path / ".archie"
    _write_json(archie / "blueprint.json", {
        "architecture_rules": {
            "file_placement_rules": [
                "this is not a dict",            # skipped — wrong type
                {},                              # skipped — no useful fields
                {"pattern": "*X.kt", "location": "src/"},  # good
            ],
            "naming_conventions": [
                {"no_pattern_field": True},      # skipped — missing pattern
                {"pattern": "*Y.kt"},            # good
            ],
        },
        "development_rules": [
            "",                                  # skipped — empty string
            "Real practice",                     # good
            {"no_rule_field": True},             # skipped — no rule/description
        ],
    })
    _write_json(archie / "rules.json", {"rules": []})
    _write_json(archie / "proposed_rules.json", {"rules": []})

    summary = migrate(tmp_path)
    # 1 fp + 1 nc + 1 dev = 3
    assert summary["added"] == 3
    proposed = _read_json(archie / "proposed_rules.json")
    assert len(proposed["rules"]) == 3


def test_infrastructure_rules_get_infrastructure_kind(tmp_path: Path):
    """infrastructure_rules entries must migrate to kind='infrastructure', not 'coding_practice'."""
    from migrate_blueprint_rules import migrate

    archie = tmp_path / ".archie"
    _write_json(archie / "blueprint.json", {
        "infrastructure_rules": [
            "Keep all secrets out of source control",
        ],
    })
    _write_json(archie / "rules.json", {"rules": []})
    _write_json(archie / "proposed_rules.json", {"rules": []})

    migrate(tmp_path)
    proposed = _read_json(archie / "proposed_rules.json")
    rules = proposed["rules"]

    assert len(rules) == 1
    assert rules[0]["kind"] == "infrastructure"


def test_migrate_handles_missing_blueprint(tmp_path: Path):
    from migrate_blueprint_rules import migrate

    summary = migrate(tmp_path)
    assert summary["added"] == 0
    assert summary["sections_stripped"] == []


def test_migrate_dry_run_does_not_write(project_with_legacy_blueprint: Path):
    from migrate_blueprint_rules import migrate

    bp_before = (project_with_legacy_blueprint / ".archie" / "blueprint.json").read_text()
    pr_before = (project_with_legacy_blueprint / ".archie" / "proposed_rules.json").read_text()

    summary = migrate(project_with_legacy_blueprint, dry_run=True)
    assert summary["added"] == 7

    # Files unchanged
    assert (project_with_legacy_blueprint / ".archie" / "blueprint.json").read_text() == bp_before
    assert (project_with_legacy_blueprint / ".archie" / "proposed_rules.json").read_text() == pr_before

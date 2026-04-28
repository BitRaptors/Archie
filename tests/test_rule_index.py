"""Tests for archie/standalone/rule_index.py — the Phase 2 lookup table."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "_archie_rule_index",
    REPO_ROOT / "archie" / "standalone" / "rule_index.py",
)
assert _SPEC and _SPEC.loader
_ri = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_ri)


def test_build_index_buckets_by_path_glob_and_code_shape(tmp_path):
    rules = [
        {
            "id": "tx-001",
            "severity_class": "decision_violation",
            "description": "Wrap in entutils.Tx",
            "triggers": {
                "path_glob": ["openmeter/billing/**/adapter/**"],
                "code_shape": [
                    {
                        "kind": "regex_in_content",
                        "must_match": [r"\*entdb\.Client"],
                        "must_not_match": [r"entutils\.Tx\("],
                    }
                ],
            },
        },
        {
            "id": "ctx-001",
            "severity_class": "pitfall_triggered",
            "triggers": {
                "code_shape": [
                    {"kind": "regex_in_content", "must_match": [r"context\.TODO\("]}
                ],
            },
        },
    ]
    index = _ri.build_index(rules)

    # Path-glob bucket — only tx-001 has a path_glob
    assert "openmeter/billing/**/adapter/**" in index["by_path_glob"]
    assert index["by_path_glob"]["openmeter/billing/**/adapter/**"] == ["tx-001"]

    # Code-shape bucket — both rules contribute
    code_shape_ids = {entry["rule_id"] for entry in index["by_code_shape"]}
    assert code_shape_ids == {"tx-001", "ctx-001"}

    # Classifier bucket — both rules are architectural (severity_class != mechanical)
    assert set(index["for_classifier"]) == {"tx-001", "ctx-001"}


def test_for_classifier_excludes_mechanical(tmp_path):
    rules = [
        {"id": "arch-1", "severity_class": "decision_violation"},
        {"id": "mech-1", "severity_class": "mechanical_violation"},
    ]
    index = _ri.build_index(rules)
    assert index["for_classifier"] == ["arch-1"]


def test_legacy_rule_with_rationale_lands_in_classifier(tmp_path):
    """Old-shape rules without severity_class but with rationale go into
    the classifier even if they also have a `check` field — the rationale
    text is architectural reasoning the classifier should weigh."""
    rules = [
        {"id": "legacy-arch", "description": "...", "rationale": "Some why text"},
        {"id": "legacy-mech-with-rationale", "description": "...",
         "rationale": "intent text", "check": "forbidden_content"},
        {"id": "legacy-bare", "description": "...", "check": "naming"},  # no rationale
    ]
    index = _ri.build_index(rules)
    assert set(index["for_classifier"]) == {"legacy-arch", "legacy-mech-with-rationale"}


def test_legacy_applies_to_back_compat_indexed(tmp_path):
    """Old-shape rules with `applies_to` but no `triggers` block still get
    O(1) narrowing — derive a path_glob from applies_to."""
    rules = [
        {
            "id": "legacy-1",
            "description": "...",
            "check": "forbidden_content",
            "applies_to": "openmeter/ent/db/",
            "forbidden_patterns": ["^(?!// Code generated)"],
        }
    ]
    index = _ri.build_index(rules)
    assert "openmeter/ent/db/" in index["by_path_glob"]
    assert index["by_path_glob"]["openmeter/ent/db/"] == ["legacy-1"]


def test_cmd_build_writes_index_file(tmp_path):
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    (archie_dir / "rules.json").write_text(json.dumps({
        "rules": [
            {"id": "r1", "severity_class": "decision_violation",
             "triggers": {"path_glob": ["src/**"]}},
        ]
    }))
    rc = _ri.cmd_build(str(tmp_path))
    assert rc == 0
    out = json.loads((archie_dir / "rule_index.json").read_text())
    assert "src/**" in out["by_path_glob"]
    assert out["for_classifier"] == ["r1"]


def test_cmd_build_handles_missing_rules_file(tmp_path):
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    rc = _ri.cmd_build(str(tmp_path))
    assert rc == 0
    out = json.loads((archie_dir / "rule_index.json").read_text())
    # Empty buckets — nothing to index
    assert out["by_path_glob"] == {}
    assert out["by_code_shape"] == []
    assert out["for_classifier"] == []

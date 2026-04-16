"""Tests for archie.standalone.aggregate_findings.

Red-phase TDD: the module does not exist yet. These tests establish the
contract for finding_signature, compute_lifecycle, apply_quality_gate, and
merge_sources. Task 3 implements the module; these tests pin down its shape.
"""
from __future__ import annotations

import json

from archie.standalone.aggregate_findings import (
    _adapt_mechanical,
    _load,
    apply_quality_gate,
    compute_lifecycle,
    finding_signature,
    merge_sources,
)


# ---------------------------------------------------------------------------
# finding_signature — type + sorted(components_affected)
# ---------------------------------------------------------------------------


def test_finding_signature_orders_components():
    f = {"type": "fragmentation", "scope": {"components_affected": ["b", "a"]}}
    assert finding_signature(f) == "fragmentation|a|b"


def test_finding_signature_handles_missing_components():
    f = {"type": "cycle", "scope": {}}
    assert finding_signature(f) == "cycle|"


def test_finding_signature_ignores_evidence_locations():
    f1 = {
        "type": "god_component",
        "scope": {"components_affected": ["shared"], "locations": ["a.ts:1"]},
    }
    f2 = {
        "type": "god_component",
        "scope": {"components_affected": ["shared"], "locations": ["b.ts:2"]},
    }
    assert finding_signature(f1) == finding_signature(f2)


# ---------------------------------------------------------------------------
# compute_lifecycle — new / recurring / resolved / worsening
# ---------------------------------------------------------------------------


def test_lifecycle_new_when_no_prior():
    current = [
        {"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}
    ]
    result = compute_lifecycle(current, prior=[])
    assert result[0]["lifecycle_status"] == "new"
    assert result[0]["blast_radius_delta"] == 0


def test_lifecycle_recurring_when_in_prior():
    prior = [
        {"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}
    ]
    current = [
        {"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}
    ]
    result = compute_lifecycle(current, prior=prior)
    assert result[0]["lifecycle_status"] == "recurring"
    assert result[0]["blast_radius_delta"] == 0


def test_lifecycle_worsening_when_blast_grew():
    prior = [
        {"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}
    ]
    current = [
        {"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 8}
    ]
    result = compute_lifecycle(current, prior=prior)
    assert result[0]["lifecycle_status"] == "worsening"
    assert result[0]["blast_radius_delta"] == 5


def test_lifecycle_resolved_findings_emitted_separately():
    prior = [
        {"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}
    ]
    current = []
    result = compute_lifecycle(current, prior=prior)
    resolved = [f for f in result if f["lifecycle_status"] == "resolved"]
    assert len(resolved) == 1
    assert resolved[0]["type"] == "cycle"


# ---------------------------------------------------------------------------
# apply_quality_gate — drop findings missing required fields
# ---------------------------------------------------------------------------


def test_quality_gate_drops_systemic_missing_pattern_description():
    findings = [
        {
            "category": "systemic",
            "type": "fragmentation",
            "scope": {
                "components_affected": ["a", "b", "c"],
                "locations": ["x", "y", "z"],
            },
            # pattern_description missing
            "root_cause": "...",
            "fix_direction": "...",
            "blast_radius": 3,
        }
    ]
    kept = apply_quality_gate(findings)
    assert len(kept) == 0


def test_quality_gate_drops_systemic_with_fewer_than_3_evidence():
    findings = [
        {
            "category": "systemic",
            "type": "fragmentation",
            "pattern_description": "x",
            "scope": {"components_affected": ["a"], "locations": ["x"]},
            "root_cause": "...",
            "fix_direction": "...",
            "blast_radius": 1,
        }
    ]
    kept = apply_quality_gate(findings)
    assert len(kept) == 0


def test_quality_gate_keeps_localized_with_single_location():
    findings = [
        {
            "category": "localized",
            "type": "dependency_violation",
            "scope": {"components_affected": ["a"], "locations": ["x:1"]},
            "root_cause": "...",
            "fix_direction": "...",
        }
    ]
    kept = apply_quality_gate(findings)
    assert len(kept) == 1


def test_quality_gate_normalizes_category_case():
    """Agent output sometimes emits SYSTEMIC or Systemic — must normalize."""
    findings = [{
        "category": "SYSTEMIC",
        "type": "fragmentation",
        "pattern_description": "auth enforcement scattered",
        "scope": {"components_affected": ["handlers"], "locations": ["a", "b", "c"]},
        "root_cause": "no shared middleware",
        "fix_direction": "extract authGuard",
        "blast_radius": 3,
    }]
    kept = apply_quality_gate(findings)
    assert len(kept) == 1
    assert kept[0]["category"] == "systemic"


def test_quality_gate_normalizes_mixed_case_category():
    findings = [{
        "category": "Systemic",
        "type": "fragmentation",
        "pattern_description": "x",
        "scope": {"components_affected": ["a"], "locations": ["a", "b", "c"]},
        "root_cause": "...",
        "fix_direction": "...",
        "blast_radius": 2,
    }]
    kept = apply_quality_gate(findings)
    assert len(kept) == 1
    assert kept[0]["category"] == "systemic"


def test_quality_gate_unknown_category_defaults_to_localized():
    """Garbage category value degrades to localized — not dropped on that alone."""
    findings = [{
        "category": "wat",
        "type": "dependency_violation",
        "scope": {"components_affected": ["a"], "locations": ["x:1"]},
        "root_cause": "...",
        "fix_direction": "...",
    }]
    kept = apply_quality_gate(findings)
    assert len(kept) == 1
    assert kept[0]["category"] == "localized"


def test_quality_gate_keeps_systemic_with_all_required_fields():
    # All systemic requirements met: pattern_description, exactly-3 locations (boundary),
    # root_cause, fix_direction, blast_radius populated.
    findings = [{
        "category": "systemic",
        "type": "fragmentation",
        "pattern_description": "auth enforcement scattered across handlers",
        "scope": {"components_affected": ["handlers"], "locations": ["h1.ts:3", "h2.ts:5", "h3.ts:7"]},
        "root_cause": "no shared auth middleware; each handler reimplements validate()",
        "fix_direction": "extract authGuard middleware; migrate handlers h1 → h2 → h3",
        "blast_radius": 3
    }]
    kept = apply_quality_gate(findings)
    assert len(kept) == 1
    assert kept[0]["type"] == "fragmentation"


# ---------------------------------------------------------------------------
# merge_sources — dedupe by signature, prefer canonical, never downgrade
# ---------------------------------------------------------------------------


def test_merge_dedupes_by_signature_keeps_canonical():
    wave2 = [
        {
            "type": "cycle",
            "scope": {"components_affected": ["a"]},
            "synthesis_depth": "canonical",
            "source": "wave2",
        }
    ]
    mech = [
        {
            "type": "cycle",
            "scope": {"components_affected": ["a"]},
            "synthesis_depth": "draft",
            "source": "mechanical",
        }
    ]
    merged = merge_sources(wave1=[], wave2=wave2, phase2=[], mechanical=mech)
    sigs = [f["source"] for f in merged]
    assert sigs.count("mechanical") == 0
    assert sigs.count("wave2") == 1


def test_merge_never_downgrades_severity():
    # Winner (wave2, canonical) has LOWER severity than loser (mechanical, draft).
    # Aggregator must promote the merged entry to the loser's higher severity.
    wave2 = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "severity": "warn", "source": "wave2"}]
    mech = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "severity": "error", "source": "mechanical"}]
    merged = merge_sources(wave1=[], wave2=wave2, phase2=[], mechanical=mech)
    assert len(merged) == 1
    assert merged[0]["severity"] == "error"
    # The winning source is still wave2 — only severity is promoted, not ownership.
    assert merged[0]["source"] == "wave2"


def test_merge_preserves_unknown_severity_against_known_loser():
    """Winner carries an off-spec 'critical' label. Loser has known 'info' (rank 1).

    The previous implementation compared unknown→rank 0 vs info→rank 1 and
    concluded the loser was "higher", silently demoting the winner to 'info'.
    The fix must treat unknown severities as opaque and preserve them.
    """
    wave2 = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "severity": "critical", "source": "wave2"}]
    mech = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "severity": "info", "source": "mechanical"}]
    merged = merge_sources(wave1=[], wave2=wave2, phase2=[], mechanical=mech)
    assert len(merged) == 1
    assert merged[0]["severity"] == "critical"


def test_merge_preserves_empty_severity_against_known_loser():
    """Winner has no severity field. Loser has 'info'. Must NOT fabricate 'info'
    on the winner — the field stays absent, since only an upgrade between
    known ranks is allowed."""
    wave2 = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "source": "wave2"}]
    mech = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "severity": "info", "source": "mechanical"}]
    merged = merge_sources(wave1=[], wave2=wave2, phase2=[], mechanical=mech)
    assert len(merged) == 1
    # Winner had no severity; promotion requires a known winner rank, so field stays unset.
    assert "severity" not in merged[0] or merged[0].get("severity") in ("", None)


# ---------------------------------------------------------------------------
# _load robustness — malformed JSON + non-list findings
# ---------------------------------------------------------------------------


def test_load_returns_empty_for_missing_file(tmp_path):
    assert _load(tmp_path / "nonexistent.json") == []


def test_load_returns_empty_for_malformed_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert _load(p) == []


def test_load_returns_empty_for_non_list_findings(tmp_path):
    for bad in ['{"findings": null}', '{"findings": {"k": "v"}}', '{"findings": "oops"}']:
        p = tmp_path / "in.json"
        p.write_text(bad, encoding="utf-8")
        assert _load(p) == []


# ---------------------------------------------------------------------------
# _adapt_mechanical — flatten drift.py's categorized-arrays shape
# ---------------------------------------------------------------------------


def test_adapt_mechanical_missing_file_returns_empty(tmp_path):
    assert _adapt_mechanical(tmp_path / "nope.json") == []


def test_adapt_mechanical_malformed_returns_empty(tmp_path):
    p = tmp_path / "drift_report.json"
    p.write_text("{not valid json", encoding="utf-8")
    assert _adapt_mechanical(p) == []


def test_adapt_mechanical_flattens_drift_categorized_arrays(tmp_path):
    """drift.py writes a categorized-arrays dict; aggregator must flatten it.

    Each entry becomes a Semantic Finding tagged source=mechanical,
    synthesis_depth=draft, category=localized.
    """
    drift_shape = {
        "pattern_divergences": [
            {
                "type": "pattern_divergence",
                "folder": "services/auth",
                "message": "Siblings mostly use repository pattern but this folder does not",
                "severity": "warn",
            }
        ],
        "naming_violations": [
            {
                "type": "naming_violation",
                "convention": "snake_case",
                "scope": "utils",
                "violating_files": ["utils/BadName.py", "utils/AnotherBad.py"],
                "count": 2,
                "severity": "info",
            }
        ],
        "dependency_violations": [
            {
                "type": "dependency_violation",
                "from_component": "api",
                "to_component": "db",
                "file": "api/handlers/user.py",
                "import": "db.models",
                "message": "api imports from db but does not declare it as a dependency",
                "severity": "warn",
            }
        ],
        "structural_outliers": [
            {
                "type": "structural_outlier",
                "folder": "modules/legacy",
                "message": "Has 200 files — significantly more than sibling average",
                "severity": "info",
            }
        ],
        "antipattern_clusters": [
            {
                "type": "antipattern_cluster",
                "folder": "services/god",
                "count": 8,
                "anti_patterns": ["god_object", "copy_paste"],
                "message": "Has 8 anti-patterns — high-risk area",
                "severity": "warn",
            }
        ],
        "summary": {"total_findings": 5},
    }
    path = tmp_path / "drift_report.json"
    path.write_text(json.dumps(drift_shape))

    findings = _adapt_mechanical(path)
    assert len(findings) == 5
    assert all(f["source"] == "mechanical" for f in findings)
    assert all(f["synthesis_depth"] == "draft" for f in findings)
    assert all(f["category"] == "localized" for f in findings)
    # Each severity must land in the known enum.
    for f in findings:
        assert f["severity"] in ("error", "warn", "info")
        assert "scope" in f and "locations" in f["scope"]
        assert f.get("root_cause")
        assert f.get("fix_direction")


def test_adapt_mechanical_naming_violation_uses_violating_files_as_locations(tmp_path):
    """naming_violation entries carry a list of files under violating_files,
    not a single `file`. Adapter must surface them in scope.locations."""
    drift_shape = {
        "pattern_divergences": [],
        "naming_violations": [{
            "type": "naming_violation",
            "convention": "camelCase",
            "scope": "components",
            "violating_files": ["components/bad_name.ts", "components/another_bad.ts"],
            "count": 2,
            "severity": "info",
        }],
        "dependency_violations": [],
        "structural_outliers": [],
        "antipattern_clusters": [],
    }
    path = tmp_path / "drift_report.json"
    path.write_text(json.dumps(drift_shape))

    findings = _adapt_mechanical(path)
    assert len(findings) == 1
    locs = findings[0]["scope"]["locations"]
    assert "components/bad_name.ts" in locs
    assert "components/another_bad.ts" in locs


def test_adapt_mechanical_tolerates_malformed_entries(tmp_path):
    """Non-dict entries inside category arrays must be skipped, not crash."""
    drift_shape = {
        "pattern_divergences": [None, "oops", {"folder": "ok", "message": "real finding", "severity": "warn"}],
        "naming_violations": "not a list",
        "dependency_violations": [],
        "structural_outliers": [],
        "antipattern_clusters": [],
    }
    path = tmp_path / "drift_report.json"
    path.write_text(json.dumps(drift_shape))

    findings = _adapt_mechanical(path)
    # Only the valid dict entry survives.
    assert len(findings) == 1
    assert findings[0]["source"] == "mechanical"

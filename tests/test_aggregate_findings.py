"""Tests for archie.standalone.aggregate_findings.

Red-phase TDD: the module does not exist yet. These tests establish the
contract for finding_signature, compute_lifecycle, apply_quality_gate, and
merge_sources. Task 3 implements the module; these tests pin down its shape.
"""
from __future__ import annotations

from archie.standalone.aggregate_findings import (
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

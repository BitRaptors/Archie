#!/usr/bin/env python3
"""Archie findings aggregator — merge, gate, and lifecycle-tag semantic findings.

Consumes the per-wave/phase outputs of a scan (wave1, wave2, phase2, mechanical
drift) and produces the single canonical `.archie/semantic_findings.json`:

  1. merge_sources — dedupe by (type + sorted components_affected) signature,
     preferring canonical over draft, deeper synthesis over shallower, and
     never downgrading severity when picking a winner.
  2. apply_quality_gate — drop systemic findings missing pattern_description,
     root_cause, fix_direction, blast_radius, or with <3 evidence locations;
     drop localized findings missing root_cause, fix_direction, or locations.
  3. compute_lifecycle — compare against the prior semantic_findings.json and
     tag each finding as new / recurring / worsening, emit resolved entries
     for signatures that disappeared, and attach blast_radius_delta.

Run:
  python3 aggregate_findings.py /path/to/repo

Reads (from `<repo>/.archie/`):
  - semantic_findings_wave1.json       (deep-scan)
  - semantic_findings_wave2.json       (deep-scan)
  - semantic_findings_phase2.json      (deep-scan)
  - semantic_findings_fast_a.json      (fast-scan Agent A)
  - semantic_findings_fast_b.json      (fast-scan Agent B)
  - semantic_findings_fast_c.json      (fast-scan Agent C)
  - drift_report.json                  (mechanical findings)
  - semantic_findings.json             (prior run, for lifecycle)

Writes:
  - semantic_findings.json     ({"findings": [...], "schema_version": 1})

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


# ── Source + severity ranking ────────────────────────────────────────────

SOURCE_RANK = {
    "wave2": 4,
    "phase2": 3,
    "wave1_structure": 2,
    "wave1_patterns": 2,
    "fast_agent_a": 2,
    "fast_agent_b": 2,
    "fast_agent_c": 2,
    "mechanical": 1,
}

SEVERITY_RANK = {"error": 3, "warn": 2, "info": 1}


# ── Signature ────────────────────────────────────────────────────────────

def finding_signature(finding: dict) -> str:
    """Return a dedupe key: type + sorted components_affected.

    Evidence locations are intentionally ignored so the same systemic issue
    surfaces as one entry even when agents cite different example files.
    """
    ftype = finding.get("type", "")
    components = sorted(finding.get("scope", {}).get("components_affected", []) or [])
    return f"{ftype}|{'|'.join(components)}"


# ── Quality gate ─────────────────────────────────────────────────────────

def apply_quality_gate(findings: list) -> list:
    """Drop findings that lack the minimum fields for actionable reporting.

    Systemic findings must have pattern_description, root_cause, fix_direction,
    a numeric blast_radius, and at least 3 evidence locations. Localized
    findings must have root_cause, fix_direction, and at least 1 location.
    """
    kept = []
    for f in findings:
        # Agents sometimes emit SYSTEMIC or Systemic. Normalize to lowercase
        # so the category check (and every downstream consumer, including the
        # viewer) sees a stable value. Unknown categories degrade to localized
        # rather than being dropped — the per-category gate below decides fate.
        raw_cat = f.get("category", "")
        category = raw_cat.lower() if isinstance(raw_cat, str) else "localized"
        if category not in ("systemic", "localized"):
            category = "localized"
        f = {**f, "category": category}

        if category == "systemic":
            if not f.get("pattern_description"):
                continue
            locations = f.get("scope", {}).get("locations", []) or []
            if len(locations) < 3:
                continue
            if not f.get("root_cause") or not f.get("fix_direction"):
                continue
            if f.get("blast_radius") is None:
                continue
        else:  # localized
            locations = f.get("scope", {}).get("locations", []) or []
            if len(locations) < 1:
                continue
            if not f.get("root_cause") or not f.get("fix_direction"):
                continue
        kept.append(f)
    return kept


# ── Lifecycle ────────────────────────────────────────────────────────────

def compute_lifecycle(current: list, prior: list) -> list:
    """Tag each current finding with lifecycle_status + blast_radius_delta.

    Findings present in prior but missing from current are emitted with
    lifecycle_status="resolved". A current finding with a larger blast_radius
    than its prior counterpart is "worsening"; same/smaller is "recurring";
    absent from prior is "new".
    """
    prior_by_sig = {finding_signature(f): f for f in prior}
    current_sigs = set()
    result = []
    for f in current:
        sig = finding_signature(f)
        current_sigs.add(sig)
        prev = prior_by_sig.get(sig)
        current_br = f.get("blast_radius") or 0
        prior_br = (prev.get("blast_radius") if prev else 0) or 0
        # New findings have no prior to diff against — delta is only meaningful
        # across runs, so zero it out when the finding is brand new.
        delta = 0 if prev is None else current_br - prior_br
        f = {**f, "blast_radius_delta": delta}
        if prev is None:
            f["lifecycle_status"] = "new"
        elif delta > 0:
            f["lifecycle_status"] = "worsening"
        else:
            f["lifecycle_status"] = "recurring"
        result.append(f)
    for sig, prev in prior_by_sig.items():
        if sig not in current_sigs:
            resolved = {**prev, "lifecycle_status": "resolved", "blast_radius_delta": 0}
            result.append(resolved)
    return result


# ── Merge ────────────────────────────────────────────────────────────────

def _pick(a: dict, b: dict) -> dict:
    """Choose the winning finding between two duplicates, promoting severity.

    Priority order: canonical synthesis_depth > draft; within the same depth,
    higher SOURCE_RANK wins (wave2 > phase2 > wave1 > mechanical). The loser
    never contributes ownership, but its severity wins if it's higher — we
    must not silently downgrade an "error" to a "warn".
    """
    a_depth = 1 if a.get("synthesis_depth") == "canonical" else 0
    b_depth = 1 if b.get("synthesis_depth") == "canonical" else 0
    if a_depth != b_depth:
        winner = a if a_depth > b_depth else b
    else:
        a_rank = SOURCE_RANK.get(a.get("source", ""), 0)
        b_rank = SOURCE_RANK.get(b.get("source", ""), 0)
        winner = a if a_rank >= b_rank else b
    loser = b if winner is a else a
    if SEVERITY_RANK.get(loser.get("severity", ""), 0) > SEVERITY_RANK.get(winner.get("severity", ""), 0):
        winner = {**winner, "severity": loser["severity"]}
    return winner


def merge_sources(wave1, wave2, phase2, mechanical) -> list:
    """Dedupe the four finding streams by signature, keeping the best entry."""
    all_findings = list(wave1) + list(wave2) + list(phase2) + list(mechanical)
    by_sig: dict = {}
    for f in all_findings:
        sig = finding_signature(f)
        if sig in by_sig:
            by_sig[sig] = _pick(by_sig[sig], f)
        else:
            by_sig[sig] = f
    return list(by_sig.values())


# ── CLI ──────────────────────────────────────────────────────────────────

def _load(path: Path) -> list:
    """Load a findings list from disk, tolerating absent files and dict wrappers.

    Agent-written JSON is occasionally malformed, and the `findings` key is
    occasionally non-list (null, dict, string). Both must not crash the whole
    aggregation — degrade to an empty list so other sources can still merge.
    """
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"warning: could not read {path.name}: {e}", file=sys.stderr)
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        findings = data.get("findings", [])
        return findings if isinstance(findings, list) else []
    return []


# ── Drift-report adapter ─────────────────────────────────────────────────

# Each drift.py category maps to a Semantic Findings `type`. Drift entries are
# always localized (single-folder or single-file scope) and mechanically
# generated, so `category`/`source`/`synthesis_depth` are fixed at the call
# site — only the type varies per category.
_DRIFT_TYPE_MAP = {
    "pattern_divergences": "pattern_divergence",
    "naming_violations": "pattern_divergence",
    "dependency_violations": "dependency_violation",
    "structural_outliers": "pattern_divergence",
    "antipattern_clusters": "pattern_divergence",
}


def _drift_entry_locations(entry: dict) -> list:
    """Pull location hints off a drift entry into a flat list.

    drift.py is not uniform: dependency_violations carry `file`, pattern/
    structural findings carry `folder`, naming_violations carry a
    `violating_files` array. Adapter flattens all of those so the downstream
    Semantic Findings consumer sees one shape.
    """
    locs: list = []
    viol = entry.get("violating_files")
    if isinstance(viol, list):
        locs.extend([v for v in viol if isinstance(v, str) and v])
    for key in ("file", "folder", "path"):
        val = entry.get(key)
        if isinstance(val, str) and val and val not in locs:
            locs.append(val)
    return locs


def _adapt_mechanical(path: Path) -> list:
    """Adapt drift.py's categorized-arrays shape into Semantic Findings.

    drift.py writes `{pattern_divergences: [...], naming_violations: [...], ...}`
    rather than the canonical `{findings: [...]}` envelope. This adapter
    flattens those category arrays into a list of findings tagged
    source=mechanical, synthesis_depth=draft, category=localized — the shape
    the merge/gate/lifecycle pipeline expects.
    """
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"warning: could not read {path.name}: {e}", file=sys.stderr)
        return []
    if not isinstance(data, dict):
        return []

    findings = []
    for drift_key, type_name in _DRIFT_TYPE_MAP.items():
        entries = data.get(drift_key, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            severity = entry.get("severity", "info")
            if severity not in ("error", "warn", "info"):
                severity = "info"
            locations = _drift_entry_locations(entry)
            # drift.py uses `message` for human-readable text; fall back to
            # `description` if a future producer writes that key instead.
            description = (
                entry.get("message")
                or entry.get("description")
                or f"{drift_key.replace('_', ' ')} detected"
            )
            fix_direction = (
                entry.get("recommendation")
                or entry.get("fix")
                or f"Review and address: {description}"
            )
            findings.append({
                "category": "localized",
                "type": type_name,
                "severity": severity,
                "scope": {
                    "kind": "single_file" if len(locations) <= 1 else "multi_file",
                    "components_affected": [],
                    "locations": locations,
                },
                "evidence": description,
                "root_cause": description,
                "fix_direction": fix_direction,
                "synthesis_depth": "draft",
                "source": "mechanical",
            })
    return findings


def main():
    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    archie_dir = project_root / ".archie"
    wave1 = _load(archie_dir / "semantic_findings_wave1.json")
    wave2 = _load(archie_dir / "semantic_findings_wave2.json")
    phase2 = _load(archie_dir / "semantic_findings_phase2.json")
    # Fast-scan per-agent outputs. Deep-scan never writes these; fast-scan
    # never writes the wave/phase files — either branch degrades to [] via
    # _load. Merging them through the same pipeline keeps one code path.
    fast_a = _load(archie_dir / "semantic_findings_fast_a.json")
    fast_b = _load(archie_dir / "semantic_findings_fast_b.json")
    fast_c = _load(archie_dir / "semantic_findings_fast_c.json")
    # drift_report.json uses a categorized-arrays shape (pattern_divergences,
    # naming_violations, dependency_violations, ...) rather than the canonical
    # `{findings: [...]}` envelope. _adapt_mechanical flattens it; _load would
    # silently return [] and we'd lose every mechanical finding.
    mechanical = _adapt_mechanical(archie_dir / "drift_report.json")
    prior = _load(archie_dir / "semantic_findings.json")

    # fast_agent_* share SOURCE_RANK 2 with wave1_*, so threading them through
    # the wave1 bucket keeps _pick's ranking correct. wave2/phase2 outrank them
    # (deep-scan wins when both exist); mechanical is lower (draft-only bucket).
    merged = merge_sources(
        list(wave1) + list(fast_a) + list(fast_b) + list(fast_c),
        wave2,
        phase2,
        mechanical,
    )
    gated = apply_quality_gate(merged)
    with_lifecycle = compute_lifecycle(gated, prior)

    out = {"findings": with_lifecycle, "schema_version": 1}
    (archie_dir / "semantic_findings.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(with_lifecycle)} findings to semantic_findings.json", file=sys.stderr)


if __name__ == "__main__":
    main()

"""Evidence schema: the single finding shape every producer emits.

Additive over the legacy finding dict — legacy fields (problem_statement,
triggering_call_site, ...) are preserved; these fields are added alongside.
Zero dependencies beyond the Python 3.9+ stdlib.
"""
from __future__ import annotations

EVIDENCE_FIELDS = ("kind", "edge", "anchor", "assumptions", "falsification", "confidence")

def make_finding(*, id, kind, edge, problem_statement, anchor, assumptions,
                 evidence, falsification, confidence, source, severity_class) -> dict:
    return {
        "id": id,
        "kind": kind,
        "edge": edge,
        "problem_statement": problem_statement,
        # keep the legacy anchor mirror so verify_findings can still read a call site
        "triggering_call_site": f'{anchor.get("file","")}:{anchor.get("line","")}',
        "anchor": dict(anchor),
        "assumptions": list(assumptions),
        "evidence": list(evidence),
        "falsification": falsification,
        "confidence": float(confidence),
        "source": source,
        "severity_class": severity_class,
        "applies_to": [anchor.get("file", "")],
    }

def has_evidence_fields(finding: dict) -> bool:
    if not all(k in finding for k in EVIDENCE_FIELDS):
        return False
    return bool(finding.get("falsification")) and bool(finding.get("anchor"))

def clamp_confidence(finding: dict, ceiling: float) -> dict:
    out = dict(finding)
    out["confidence"] = min(float(finding.get("confidence", 0.0)), float(ceiling))
    return out

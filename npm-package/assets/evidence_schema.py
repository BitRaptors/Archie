"""Evidence schema: the single finding shape every producer emits.

Additive over the legacy finding dict — legacy fields (problem_statement,
triggering_call_site, ...) are preserved; these fields are added alongside.
Zero dependencies beyond the Python 3.9+ stdlib.
"""
from __future__ import annotations

EVIDENCE_FIELDS = ("kind", "edge", "anchor", "assumptions", "falsification", "confidence")


def extract_json_obj(raw: str) -> dict:
    """Return the first top-level JSON object parsed from raw model text, or {} on failure.

    Brace-depth scan from the first '{' so trailing/leading prose (incl. stray braces)
    is ignored. When a depth-0 close is reached but the slice is not valid JSON (e.g.
    a stray balanced-brace pair in prose), scanning resumes from the next '{' so a later
    valid object is still found.
    """
    import json as _json
    if not raw:
        return {}
    pos = 0
    while True:
        start = raw.find("{", pos)
        if start < 0:
            return {}
        depth, in_str, esc = 0, False, False
        found_end = -1
        for i in range(start, len(raw)):
            c = raw[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        found_end = i
                        break
        if found_end < 0:
            return {}
        try:
            return _json.loads(raw[start:found_end + 1])
        except Exception:
            # Not valid JSON — skip past this closing brace and try again
            pos = found_end + 1


def coerce_confidence(value, default: float = 0.0) -> float:
    """Coerce LLM-emitted confidence to float; return default on null/string/missing."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def make_finding(*, id, kind, edge, problem_statement, anchor, assumptions,
                 evidence, falsification, confidence, source, severity_class,
                 severity="medium") -> dict:
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
        "confidence": coerce_confidence(confidence),
        "source": source,
        "severity_class": severity_class,
        "severity": severity,
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

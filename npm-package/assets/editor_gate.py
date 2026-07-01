"""Editor gate: the single reliability pass every surface routes through.
Validates, floor-gates, anchor-checks, and dedups. It NEVER invents a finding
absent from its input — every confirmed item is an input item, unchanged in id.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from evidence_schema import has_evidence_fields  # noqa: E402


def _dupe_key(f: dict):
    return ((f.get("anchor") or {}).get("file", ""), f.get("kind", ""))


def gate(raw_findings, store, *, changed_lines, floors) -> dict:
    """Validate and gate findings through reliability filters.

    Args:
        raw_findings: List of candidate findings to validate
        store: List of existing findings (used for dedup)
        changed_lines: Optional dict mapping file paths to sets of changed line numbers
        floors: Dict mapping kind -> minimum confidence threshold

    Returns:
        Dict with "confirmed" (passed) and "suppressed" (failed) finding lists.
        Each suppressed entry has "id" and "reason" keys.
    """
    confirmed, suppressed = [], []
    seen = {_dupe_key(s) for s in store}
    for f in raw_findings:
        if not has_evidence_fields(f):
            suppressed.append({"id": f.get("id"), "reason": "schema"}); continue
        floor = floors.get(f.get("kind", ""), 0.5)
        if float(f.get("confidence", 0.0)) < floor:
            suppressed.append({"id": f.get("id"), "reason": "below_floor"}); continue
        anchor = f.get("anchor") or {}
        if changed_lines is not None:
            lines = changed_lines.get(anchor.get("file", ""), set())
            if anchor.get("line") not in lines:
                suppressed.append({"id": f.get("id"), "reason": "anchor_unchanged"}); continue
        key = _dupe_key(f)
        if key in seen:
            suppressed.append({"id": f.get("id"), "reason": "duplicate"}); continue
        seen.add(key)
        confirmed.append(f)
    return {"confirmed": confirmed, "suppressed": suppressed}

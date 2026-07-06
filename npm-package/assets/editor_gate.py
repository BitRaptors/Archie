"""Editor gate: the single reliability pass every surface routes through.
Validates, floor-gates, anchor-checks, and dedups. It NEVER invents a finding
absent from its input — every confirmed item is an input item, unchanged in id.
"""
from __future__ import annotations
import sys
from pathlib import Path
_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from evidence_schema import has_evidence_fields, coerce_confidence  # noqa: E402


def _dupe_key(f: dict):
    anchor = f.get("anchor") or {}
    raw_line = anchor.get("line")
    line = int(raw_line) if isinstance(raw_line, str) and raw_line.isdigit() else raw_line
    return (anchor.get("file", ""), line, f.get("kind", ""))


def gate(raw_findings, store, *, changed_lines, floors, file_level_kinds=frozenset()) -> dict:
    """Validate and gate findings through reliability filters.

    Args:
        raw_findings: List of candidate findings to validate
        store: List of existing findings (used for dedup)
        changed_lines: Optional dict mapping file paths to sets of changed line numbers
        floors: Dict mapping kind -> minimum confidence threshold
        file_level_kinds: Kinds for which a change ANYWHERE in the anchored file is
            enough — the exact-line check is skipped. LLM code reviewers cite
            imprecise line numbers, so requiring an exact added-line match silently
            drops real findings on changed files; these kinds anchor file-level.

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
        if coerce_confidence(f.get("confidence")) < floor:
            suppressed.append({"id": f.get("id"), "reason": "below_floor"}); continue
        anchor = f.get("anchor") or {}
        if changed_lines is not None:
            file_lines = changed_lines.get(anchor.get("file", ""))
            if file_lines is None:
                # file not in the changed set at all -> genuinely unchanged
                suppressed.append({"id": f.get("id"), "reason": "anchor_unchanged"}); continue
            if f.get("kind", "") not in file_level_kinds:
                raw_line = anchor.get("line")
                line = int(raw_line) if isinstance(raw_line, str) and raw_line.isdigit() else raw_line
                if line is not None and line not in file_lines:
                    suppressed.append({"id": f.get("id"), "reason": "anchor_unchanged"}); continue
                # line is None but file changed -> keep (file-level finding)
        key = _dupe_key(f)
        if key in seen:
            suppressed.append({"id": f.get("id"), "reason": "duplicate"}); continue
        seen.add(key)
        confirmed.append(f)
    return {"confirmed": confirmed, "suppressed": suppressed}

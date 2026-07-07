"""Deterministic evidence pack: source excerpts + blueprint slice for the
reviewers, so the CI LLM path (which has no tools) still reviews code in context.
Pure aside from reading files under root. No LLM."""
from __future__ import annotations
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from reachability import consumers  # noqa: E402

_PER_FILE = 8000


def _read(root, rel, cap=_PER_FILE):
    try:
        text = (Path(root) / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(text) > cap:
        return text[:cap] + f"\n[truncated {len(text) - cap} chars]\n"
    return text


def _blueprint_slice(blueprint, changed_files):
    comps = ((blueprint or {}).get("components") or {}).get("components") or []
    out = []
    changed = set(changed_files)
    for c in comps:
        loc = str(c.get("location", ""))
        if loc and any(cf == loc or cf.startswith(loc.rstrip("/") + "/") for cf in changed):
            ki = ", ".join(c.get("key_interfaces", []) or [])
            out.append(f"- {c.get('name')}: {c.get('responsibility','')} [interfaces: {ki}]")
    return "\n".join(out)


def build_pack(root, changed_files, import_graph, blueprint, budget_chars=40000) -> str:
    parts = ["CONTEXT (read-only source excerpts + architecture slice):"]
    used = len(parts[0])
    omitted = 0
    seen_consumers = set()
    for rel in changed_files:
        body = _read(root, rel)
        if body is None:
            continue
        block = f"\n--- {rel} ---\n{body}"
        if used + len(block) > budget_chars:
            omitted += 1
            continue
        parts.append(block); used += len(block)
        for cons in (consumers(import_graph, rel) or [])[:3]:
            if cons in seen_consumers or cons in changed_files:
                continue
            seen_consumers.add(cons)
            cbody = _read(root, cons, cap=1600)
            if cbody is None:
                continue
            cblock = f"\n--- consumer: {cons} ---\n{cbody}"
            if used + len(cblock) > budget_chars:
                omitted += 1; continue
            parts.append(cblock); used += len(cblock)
    bslice = _blueprint_slice(blueprint, changed_files)
    if bslice and used + len(bslice) + 40 <= budget_chars:
        parts.append("\nARCHITECTURE (touched components):\n" + bslice)
    if omitted:
        parts.append(f"\n[[evidence truncated: {omitted} file(s) omitted for budget]]")
    return "\n".join(parts)

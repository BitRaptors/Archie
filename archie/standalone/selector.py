"""Non-reviewing router: intersect changed files with blueprint anchors to
pick Lane-2 specialists. Decides WHO runs; never reviews.
"""
from __future__ import annotations

def _anchor_files(anchors) -> list[str]:
    out = []
    for a in anchors or []:
        s = str(a).split(":", 1)[0]
        if s:
            out.append(s)
    return out

def _related_roots(a: str, b: str) -> bool:
    """True when two top-level dir names look like the same tree duplicated or
    renamed (worker <-> new_worker, api <-> api_v2): the shorter is a prefix or
    suffix of the longer. Keeps unrelated roots (billing vs other) from matching."""
    a, b = a.lower(), b.lower()
    lo, hi = sorted((a, b), key=len)
    return bool(lo) and (hi.startswith(lo) or hi.endswith(lo))


def _hit(changed: list[str], targets: list[str]) -> bool:
    for c in changed:
        for t in targets:
            if not t:
                continue
            seg = t.rstrip("/")
            if c == seg or c.startswith(seg + "/"):
                return True
            # Duplicated/parallel-tree tolerance: an invariant anchored in one copy of
            # duplicated code (worker/X) still applies to the sibling copy (new_worker/X).
            # Match file anchors that share the same path tail under a RELATED top-level
            # dir. Loose by design — the contract->tracer->challenger loop filters false
            # routes, so recall matters more than precision at the routing stage.
            if not seg.endswith("/") and "/" in seg and "/" in c:
                c_root, c_tail = c.split("/", 1)
                s_root, s_tail = seg.split("/", 1)
                if c_tail and c_tail == s_tail and c_root != s_root and _related_roots(c_root, s_root):
                    return True
    return False

def select_specialists(blueprint: dict, changed_files: list[str]) -> dict:
    specialists, reason = [], {}
    for inv in blueprint.get("domain_invariants", []) or []:
        if _hit(changed_files, _anchor_files(inv.get("enforced_at"))):
            if "invariant-integrity" not in specialists:
                specialists.append("invariant-integrity")
            reason.setdefault("invariant-integrity", []).append(inv.get("id", "?"))
    decisions = (blueprint.get("decisions") or {}).get("key_decisions", []) or []
    forced = [str(d.get("forced_by", "")) for d in decisions if d.get("forced_by")]
    if _hit(changed_files, forced):
        specialists.append("decision-integrity")
        reason["decision-integrity"] = "changed a decision's forced_by file"
    store_files = [str(s.get("location", "")) for s in blueprint.get("persistence_stores", []) or []]
    store_files += [str(m.get("location", "")) for m in blueprint.get("data_models", []) or []]
    if _hit(changed_files, store_files):
        specialists.append("data-lifecycle")
        reason["data-lifecycle"] = "changed a persistence/data-model file"
    if "invariant-integrity" in reason:
        reason["invariant-integrity"] = "cites domain_invariant " + ",".join(reason["invariant-integrity"])
    return {"specialists": specialists, "reason": reason}


def touched_context(blueprint, changed_files):
    """Return {'invariants': [...], 'decisions': [...]} whose anchors intersect changed_files."""
    invs = [i for i in (blueprint.get("domain_invariants") or [])
            if _hit(changed_files, _anchor_files(i.get("enforced_at")))]
    decs = [d for d in ((blueprint.get("decisions") or {}).get("key_decisions") or [])
            if d.get("forced_by") and _hit(changed_files, [str(d.get("forced_by"))])]
    return {"invariants": invs, "decisions": decs}

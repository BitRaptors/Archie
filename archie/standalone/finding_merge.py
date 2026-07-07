"""Union + dedup + agreement-weighted confidence for review findings. Two passes
that surface the same finding boost its confidence; a lone hunch stays advisory.
Pure. Reuses the token overlap idea from story_synthesize."""
from __future__ import annotations
import re
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from evidence_schema import coerce_confidence  # noqa: E402

_BREAK_KINDS = ("behavioral_break", "conformance_break")


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 3}


def _same(a, b):
    if (a["anchor"].get("file"), a.get("kind")) != (b["anchor"].get("file"), b.get("kind")):
        return False
    ta, tb = _tokens(a.get("problem_statement")), _tokens(b.get("problem_statement"))
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.6


def merge(findings, passes=1) -> list:
    groups = []  # each: {"rep": finding, "count": int, "maxconf": float}
    for f in findings or []:
        placed = False
        for g in groups:
            if _same(g["rep"], f):
                g["count"] += 1
                g["maxconf"] = max(g["maxconf"], coerce_confidence(f.get("confidence")))
                placed = True
                break
        if not placed:
            groups.append({"rep": f, "count": 1,
                           "maxconf": coerce_confidence(f.get("confidence"))})
    out = []
    for g in groups:
        rep = dict(g["rep"])
        conf = g["maxconf"]
        if rep.get("kind") in _BREAK_KINDS:
            conf = max(conf, min(1.0, g["count"] / max(1, passes)))
        rep["confidence"] = conf
        out.append(rep)
    return out

"""Reconciliation reviewer — edges A (intent vs diff) and C (intent vs blueprint).
Prompt-builders and parsers are pure; the LLM seam is run_verifier.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_cli import run_verifier            # noqa: E402
from evidence_schema import make_finding, clamp_confidence   # noqa: E402
from intent import ceiling_for                # noqa: E402

_VERDICT_KIND = {"unmet": "intent_unmet", "partial": "intent_partial", "drift": "intent_drift"}


def build_edge_a_prompt(intent_spec: dict, diff_text: str) -> str:
    crit = "\n".join(
        f'- {c.get("id")}: {c.get("text")}'
        for c in intent_spec.get("acceptance_criteria", [])
    )
    return (
        "Decide, per acceptance criterion, whether the DIFF implements it and the code is "
        "reachable. Verdict met|partial|unmet, plus drift for unrequested behavior. Give a "
        "falsification for each. Return JSON {\"findings\":[{criterion_id,verdict,file,line,"
        f"evidence[],falsification,confidence}}]}}\n\nCRITERIA:\n{crit}\n\nDIFF:\n{diff_text}"
    )


def parse_edge_a(raw: str, intent_spec: dict) -> list[dict]:
    ceiling = ceiling_for(intent_spec)
    try:
        s, e = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[s:e + 1]) if s >= 0 else {}
    except Exception:
        return []
    out = []
    for i, f in enumerate(data.get("findings", [])):
        verdict = f.get("verdict")
        if verdict == "met" or not f.get("falsification"):
            continue
        finding = make_finding(
            id=f.get("id") or f"f_a_{i}",
            kind=_VERDICT_KIND.get(verdict, "intent_partial"),
            edge="A",
            problem_statement=f"{f.get('criterion_id', '?')}: {verdict}",
            anchor={"file": f.get("file", ""), "line": f.get("line"), "changed": True},
            assumptions=[f"criterion {f.get('criterion_id')}"],
            evidence=f.get("evidence", []),
            falsification=f["falsification"],
            confidence=float(f.get("confidence", 0.0)),
            source="reconcile:edgeA",
            severity_class="pattern_divergence",
        )
        out.append(clamp_confidence(finding, ceiling))
    return out


def review_edge_a(root, intent_spec: dict, diff_text: str, run=None) -> list[dict]:
    if run is None:
        run = run_verifier   # call-time lookup → monkeypatch works
    raw = run(build_edge_a_prompt(intent_spec, diff_text), Path(root), "claude")
    return parse_edge_a(raw or "", intent_spec)

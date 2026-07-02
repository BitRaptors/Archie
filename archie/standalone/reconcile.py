"""Reconciliation reviewer — edges A (intent vs diff) and C (intent vs blueprint).
Prompt-builders and parsers are pure; the LLM seam is run_verifier.
"""
from __future__ import annotations

import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from agent_cli import run_verifier            # noqa: E402
from evidence_schema import make_finding, clamp_confidence, extract_json_obj, coerce_confidence   # noqa: E402
from intent import ceiling_for                # noqa: E402

_VERDICT_KIND = {"unmet": "intent_unmet", "partial": "intent_partial", "drift": "intent_drift"}
_KIND_SEVERITY = {"intent_unmet": "high", "intent_partial": "medium", "intent_drift": "low"}


def build_edge_a_prompt(intent_spec: dict, diff_text: str) -> str:
    crit = "\n".join(
        f'- {c.get("id")}: {c.get("text")}'
        for c in (intent_spec.get("acceptance_criteria") or [])
    )
    ng = "\n".join(f"- {g}" for g in (intent_spec.get("non_goals") or []))
    ng_block = f"\n\nNON-GOALS (flag any diff behavior that violates these):\n{ng}" if ng else ""
    return (
        "Decide, per acceptance criterion, whether the DIFF implements it and the code is "
        "reachable. Verdict met|partial|unmet, plus drift for unrequested behavior. Give a "
        "falsification for each. Return JSON {\"findings\":[{criterion_id,verdict,file,line,"
        f"evidence[],falsification,confidence}}]}}\n\nCRITERIA:\n{crit}{ng_block}\n\nDIFF:\n{diff_text}"
    )


def parse_edge_a(raw: str, intent_spec: dict) -> list[dict]:
    ceiling = ceiling_for(intent_spec)
    data = extract_json_obj(raw)
    out = []
    for i, f in enumerate(data.get("findings", [])):
        verdict = f.get("verdict")
        if verdict == "met" or not f.get("falsification"):
            continue
        kind = _VERDICT_KIND.get(verdict, "intent_partial")
        # delivery findings are advisory — never a blocking severity_class.
        finding = make_finding(
            id=f.get("id") or f"f_a_{i}",
            kind=kind,
            edge="A",
            problem_statement=f"{f.get('criterion_id', '?')}: {verdict}",
            anchor={"file": f.get("file", ""), "line": f.get("line"), "changed": True},
            assumptions=[f"criterion {f.get('criterion_id')}"],
            evidence=f.get("evidence", []),
            falsification=f["falsification"],
            confidence=coerce_confidence(f.get("confidence")),
            source="reconcile:edgeA",
            severity_class="tradeoff_undermined",
            severity=_KIND_SEVERITY.get(kind, "medium"),
        )
        finding["criterion_id"] = f.get("criterion_id")
        out.append(clamp_confidence(finding, ceiling))
    return out


def review_edge_a(root, intent_spec: dict, diff_text: str, run=None) -> list[dict]:
    if run is None:
        run = run_verifier   # call-time lookup → monkeypatch works
    raw = run(build_edge_a_prompt(intent_spec, diff_text), Path(root), "claude")
    return parse_edge_a(raw or "", intent_spec)


def build_edge_c_prompt(intent_spec, blueprint_slice):
    crit = "\n".join(f'- {c.get("id")}: {c.get("text")}' for c in (intent_spec.get("acceptance_criteria") or []))
    goals = "\n".join(f"- {g}" for g in (intent_spec.get("goals") or []))
    invs = "\n".join(f'- {i.get("id")}: {i.get("invariant","")}' for i in (blueprint_slice or []))
    return ("Decide whether the REQUIREMENT itself (its goals/criteria) would VIOLATE any standing "
            "architectural invariant if implemented as asked. Only report a conflict with clear evidence. "
            "Return JSON {\"findings\":[{\"invariant_id\":\"...\",\"file\":\"...\",\"line\":0,"
            "\"evidence\":[\"...\"],\"falsification\":\"...\",\"confidence\":0.0}]}.\n\n"
            f"GOALS:\n{goals}\n\nCRITERIA:\n{crit}\n\nTOUCHED INVARIANTS:\n{invs}")


def parse_edge_c(raw, intent_spec):
    data = extract_json_obj(raw or "")
    out = []
    ceiling = ceiling_for(intent_spec)
    for i, f in enumerate(data.get("findings", [])):
        if not f.get("falsification"):
            continue
        finding = make_finding(
            id=f.get("id") or f"f_c_{i}", kind="intent_conflict", edge="C",
            problem_statement=f"requirement conflicts with {f.get('invariant_id','?')}",
            anchor={"file": f.get("file", ""), "line": f.get("line"), "changed": False},
            assumptions=[f"invariant {f.get('invariant_id')}"], evidence=f.get("evidence", []),
            falsification=f["falsification"], confidence=coerce_confidence(f.get("confidence", 0.0)),
            source="reconcile:edgeC", severity_class="tradeoff_undermined", severity="high")
        out.append(clamp_confidence(finding, ceiling))
    return out


def review_edge_c(root, intent_spec, blueprint_slice, run=None):
    if run is None:
        run = run_verifier
    raw = run(build_edge_c_prompt(intent_spec, blueprint_slice), Path(root), "claude")
    return parse_edge_c(raw or "", intent_spec)


def build_conformance_prompt(diff_text, invariants, decisions, intent=None):
    prefix = ""
    if intent:
        _pp = str(Path(__file__).parent)
        if _pp not in sys.path:
            sys.path.insert(0, _pp)
        from intent import intent_brief  # noqa: E402
        brief = intent_brief(intent)
        if brief:
            prefix = ("INTENDED CHANGE (review whether the diff correctly and safely achieves this, "
                      "and flag where it does not):\n" + brief + "\n\n")
    inv = "\n".join(f'- {i.get("id")}: {i.get("invariant","")}' for i in (invariants or []))
    dec = "\n".join(f'- {d.get("title","")}: {d.get("rationale") or d.get("forced_by","")}'
                    for d in (decisions or []))
    ng = "\n".join(f"- {g}" for g in (intent.get("non_goals") or [] if intent else []))
    ng_block = f"\n\nNON-GOALS (flag any diff behavior that violates these):\n{ng}" if ng else ""
    return (prefix
            + "Decide whether this DIFF VIOLATES any of these standing architectural invariants or "
            "decisions. Report only clear violations INTRODUCED or worsened by the change, each with a "
            "falsification (how you'd prove it does NOT violate). Anchor to a changed line. Return JSON "
            "{\"findings\":[{\"invariant_id\":\"...\",\"file\":\"...\",\"line\":0,\"evidence\":[\"...\"],"
            "\"falsification\":\"...\",\"confidence\":0.0}]}.\n\n"
            f"INVARIANTS:\n{inv}\n\nDECISIONS:\n{dec}{ng_block}\n\nDIFF:\n{diff_text}")


def parse_conformance(raw):
    data = extract_json_obj(raw or "")
    out = []
    for i, f in enumerate(data.get("findings", [])):
        if not f.get("falsification"):
            continue
        out.append(make_finding(
            id=f.get("id") or f"f_cf_{i}", kind="conformance_break", edge="B",
            problem_statement=f"violates {f.get('invariant_id','?')}",
            anchor={"file": f.get("file",""), "line": f.get("line"), "changed": True},
            assumptions=[f"invariant {f.get('invariant_id')}"], evidence=f.get("evidence", []),
            falsification=f["falsification"], confidence=coerce_confidence(f.get("confidence", 0.0)),
            source="reconcile:conformance", severity_class="tradeoff_undermined", severity="high"))
    return out


def review_conformance(root, diff_text, invariants, decisions, run=None, intent=None):
    """Single-pass conformance reviewer: did the DIFF break a standing invariant/decision?

    NOTE: the full contract -> tracer -> challenger 3-role loop is a future enhancement;
    this is the single-pass form that produces `conformance_break` findings.
    """
    if run is None:
        run = run_verifier
    if not (invariants or decisions):
        return []
    raw = run(build_conformance_prompt(diff_text, invariants, decisions, intent=intent), Path(root), "claude")
    return parse_conformance(raw or "")


def aggregate_verdict(intent_spec: dict, confirmed: list[dict]) -> dict:
    """Aggregate confirmed findings into a delivery verdict.

    Computes intent completeness (met/total acceptance criteria), counts breaks
    and conflicts, and computes a gate signal for PR gating.

    Args:
        intent_spec: dict with "acceptance_criteria" key (list of dicts with "id")
        confirmed: list of confirmed finding dicts with "kind" key

    Returns:
        dict with keys:
        - intent_completeness: "m/n" string (met / total criteria)
        - breaks: count of conformance_break + behavioral_break
        - conflicts: count of intent_conflict
        - gate_signal: float in [0.0, 1.0] (1.0 = pass, 0.0 = fail)
    """
    total = len(intent_spec.get("acceptance_criteria") or [])
    unmet_criteria = set()
    extra_unmet = 0
    for f in confirmed:
        if f.get("kind") in ("intent_unmet", "intent_partial"):
            cid = f.get("criterion_id")
            if cid:
                unmet_criteria.add(cid)
            else:
                extra_unmet += 1
    unmet = len(unmet_criteria) + extra_unmet
    met = max(0, total - unmet)
    breaks = sum(1 for f in confirmed if f.get("kind") in ("conformance_break", "behavioral_break"))
    conflicts = sum(1 for f in confirmed if f.get("kind") == "intent_conflict")
    drift = sum(1 for f in confirmed if f.get("kind") == "intent_drift")
    gate_signal = round(1.0 - min(1.0, 0.25 * breaks + 0.5 * conflicts + 0.1 * drift), 3)
    return {
        "intent_completeness": f"{met}/{total}",
        "breaks": breaks,
        "conflicts": conflicts,
        "drift": drift,
        "gate_signal": gate_signal,
    }

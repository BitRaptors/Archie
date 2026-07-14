"""Invariant specialist: contract -> tracer -> challenger (design §6.6a).

The Lane-2 sophisticated reviewer for domain invariants. Unlike the single-pass
conformance check, it runs a three-role loop per touched invariant:

  contract   — the stored domain_invariant (guarantee + anchors). Data, not an agent.
  tracer     — (Sonnet) traces the change write -> intermediate state -> consumer-
               visible behavior; one verdict per contract; marks under-proven rather
               than assuming safe.
  challenger — (Opus) agrees / challenges / rebuts the tracer; rejects verdicts that
               stop at intermediate state, are unreachable, contradicted, or unrelated
               to the change.

Only invariants the challenger CONFIRMS violated become findings. Prompt-builders and
parsers are pure + unit-tested; the LLM is called through run_verifier.

Import convention: bare-name imports via sys.path so this works on Python 3.9
(archie/__init__.py uses tomllib which is 3.11+).
"""
from __future__ import annotations

import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from agent_cli import run_verifier  # noqa: E402
from evidence_schema import make_finding, extract_json_obj, coerce_confidence  # noqa: E402

# Design §6.6a: the tracer is a Sonnet role, the challenger an Opus role. Threaded
# to run_verifier as model aliases (claude --model / API model map).
TRACER_MODEL = "sonnet"
CHALLENGER_MODEL = "opus"


def contract_of(invariant: dict) -> dict:
    """The contract role: read the stored guarantee + cited anchors off the
    invariant. Pure data extraction — no agent, no planning per change."""
    return {
        "id": invariant.get("id", "?"),
        "guarantee": invariant.get("invariant", ""),
        "entity": invariant.get("entity", ""),
        "category": invariant.get("category", ""),
        "anchors": invariant.get("enforced_at") or [],
    }


def build_tracer_prompt(contract: dict, diff_text: str) -> str:
    anchors = "\n".join(f"  - {a}" for a in contract["anchors"]) or "  (none recorded)"
    return (
        "You are the TRACER in an invariant-integrity review. A CONTRACT is a product "
        "invariant that must always hold. Trace THIS DIFF from the write it makes, through "
        "intermediate state, to the consumer-visible behavior, and decide whether the "
        "contract still holds AFTER the change.\n\n"
        "Rules:\n"
        "- Judge only consumer-visible behavior. A change that alters intermediate state "
        "but not what any consumer observes does NOT violate the contract.\n"
        "- If you cannot trace the change through to a consumer, return verdict "
        "'under_proven' — never assume safe.\n"
        "- Read the cited anchor files to ground your trace.\n\n"
        f"CONTRACT {contract['id']} ({contract['category']} / {contract['entity']}):\n"
        f"  {contract['guarantee']}\n"
        f"ANCHORS (cited enforcement sites — read these to trace):\n{anchors}\n\n"
        f"DIFF:\n{diff_text}\n\n"
        'Return JSON {"invariant_id":"...","verdict":"upheld|violated|under_proven",'
        '"trace":"write -> intermediate -> consumer","file":"<changed file>","line":0,'
        '"evidence":["..."],"confidence":0.0}.'
    )


def parse_tracer(raw: str) -> dict:
    d = extract_json_obj(raw or "")
    if not d.get("invariant_id"):
        return {}
    return {
        "invariant_id": d.get("invariant_id"),
        "verdict": (d.get("verdict") or "under_proven").lower(),
        "trace": d.get("trace", ""),
        "file": d.get("file", ""),
        "line": d.get("line"),
        "evidence": d.get("evidence", []),
        "confidence": coerce_confidence(d.get("confidence", 0.0)),
    }


def build_challenger_prompt(contract: dict, tracer: dict, diff_text: str) -> str:
    return (
        "You are the CHALLENGER in an invariant-integrity review. The TRACER produced a "
        "verdict on whether this diff violates a contract. Your job is to REBUT it. Reject "
        "the tracer's verdict if it: stops at intermediate state (no consumer-visible "
        "impact), cites unreachable code, is contradicted by the diff, or is unrelated to "
        "the change. Only CONFIRM a violation you can defend.\n\n"
        f"CONTRACT {contract['id']}:\n  {contract['guarantee']}\n\n"
        f"TRACER VERDICT: {tracer.get('verdict')}\n"
        f"TRACER TRACE: {tracer.get('trace')}\n"
        f"TRACER EVIDENCE: {tracer.get('evidence')}\n\n"
        f"DIFF:\n{diff_text}\n\n"
        'Return JSON {"invariant_id":"...","decision":"confirm_violation|reject",'
        '"final_verdict":"violated|upheld|under_proven","reason":"...",'
        '"falsification":"how to prove this is NOT a violation","file":"...","line":0,'
        '"confidence":0.0}.'
    )


def parse_challenger(raw: str) -> dict:
    d = extract_json_obj(raw or "")
    if not d.get("invariant_id"):
        return {}
    return {
        "invariant_id": d.get("invariant_id"),
        "decision": (d.get("decision") or "reject").lower(),
        "final_verdict": (d.get("final_verdict") or "upheld").lower(),
        "reason": d.get("reason", ""),
        "falsification": d.get("falsification", ""),
        "file": d.get("file", ""),
        "line": d.get("line"),
        "confidence": coerce_confidence(d.get("confidence", 0.0)),
    }


def review_invariants(root, diff_text, invariants, run=None, skip_ids=frozenset()) -> list[dict]:
    """Run contract -> tracer -> challenger for each touched invariant. Emits a
    conformance_break finding only where the challenger CONFIRMS a violation.

    Short-circuits: a tracer 'upheld' verdict needs no challenge (no finding); a
    challenger 'reject' drops the finding — that veto is the whole point of the loop.

    skip_ids — invariant ids the user already acknowledged breaking
    (contract_delta.acked_rule_ids). Skipped entirely: no tracer, no challenger.
    Paying Opus to rediscover a law the user retired at the confirm prompt produces
    a finding that tells them nothing.
    """
    if run is None:
        run = run_verifier   # call-time global lookup → monkeypatch works
    out = []
    for inv in invariants or []:
        if inv.get("id") in skip_ids:
            continue   # the user acknowledged this law — do not pay Opus to rediscover it
        contract = contract_of(inv)
        traw = run(build_tracer_prompt(contract, diff_text), Path(root), "claude", model=TRACER_MODEL, tools=True)
        tracer = parse_tracer(traw or "")
        if not tracer or tracer["verdict"] == "upheld":
            continue
        craw = run(build_challenger_prompt(contract, tracer, diff_text), Path(root), "claude", model=CHALLENGER_MODEL, tools=True)
        ch = parse_challenger(craw or "")
        if not ch or ch["decision"] != "confirm_violation" or ch["final_verdict"] != "violated":
            continue
        if not ch.get("falsification"):
            continue
        file = ch.get("file") or tracer.get("file") or ""
        line = ch.get("line") if ch.get("line") is not None else tracer.get("line")
        out.append(make_finding(
            id=f"f_inv_{contract['id']}", kind="conformance_break", edge="B",
            problem_statement=f"violates {contract['id']}: {contract['guarantee'][:80]}",
            anchor={"file": file, "line": line, "changed": True},
            assumptions=[f"invariant {contract['id']}", f"trace: {tracer.get('trace','')[:120]}"],
            evidence=[e for e in (tracer.get("evidence") or []) if e] + [ch.get("reason", "")],
            falsification=ch["falsification"],
            # A challenger-confirmed violation is at least moderately confident; floor
            # it so a model that omits the number can't be silently gated below_floor.
            confidence=max(ch["confidence"], 0.6),
            source="invariant_specialist:ctc",
            severity_class="tradeoff_undermined", severity="high"))
    return out

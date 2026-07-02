"""Isolated intent transform: reads ONLY the intent-event log and regenerates
.archie/intent.json acceptance criteria. BLIND to the implementation by contract —
it never opens the diff, code, or the coding conversation. Regeneration (not union)
lets a re-plan RETIRE criteria, killing the scope-ratchet.
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from intent_capture import load_events            # noqa: E402
from evidence_schema import extract_json_obj       # noqa: E402

_SYSTEM = (
    "You author acceptance criteria for a change from its REQUIREMENT ONLY. "
    "You are NOT shown the implementation, diff, or code — do not assume how it was built. "
    "From the requirement/planning turns below, write the goals, concrete checkable "
    "acceptance_criteria, and any non_goals (things explicitly out of scope). "
    "Return JSON {\"goals\":[...],\"acceptance_criteria\":[{\"id\":\"ac1\",\"text\":\"...\"}],\"non_goals\":[...]}."
)


def build_synthesis_prompt(events) -> str:
    turns = "\n".join(f"- {e.get('text','')}" for e in (events or []) if e.get("kind") == "user_turn" and e.get("text"))
    return f"{_SYSTEM}\n\nREQUIREMENT / PLANNING TURNS:\n{turns}"


def parse_synthesis(raw) -> dict:
    data = extract_json_obj(raw or "")
    crit = []
    for i, c in enumerate(data.get("acceptance_criteria") or []):
        text = (c.get("text") if isinstance(c, dict) else str(c)) or ""
        if text.strip():
            crit.append({"id": f"ac{i + 1}", "text": text})
    goals = [str(g) for g in (data.get("goals") or []) if str(g).strip()]
    non_goals = [str(g) for g in (data.get("non_goals") or []) if str(g).strip()]
    return {"goals": goals, "acceptance_criteria": crit, "non_goals": non_goals}


def synthesize(root, run=None):
    """Regenerate .archie/intent.json from the event log (authoritative). Returns
    the spec, or None if there are no events. Blind to the implementation."""
    if run is None:
        from agent_cli import run_verifier
        run = run_verifier
    events = load_events(root)
    if not any(e.get("kind") == "user_turn" for e in events):
        return None
    raw = run(build_synthesis_prompt(events), Path(root), "claude")
    parsed = parse_synthesis(raw or "")
    caps = sorted({e["ts"] for e in events if e.get("kind") == "user_turn" and e.get("ts")})
    spec = {
        "source": "sync",
        "confidence": "medium",
        "goals": parsed["goals"],
        "acceptance_criteria": parsed["acceptance_criteria"],
        "non_goals": parsed["non_goals"],
        "ticket_ids": [],
        "raw": "",
        "confirmed": False,
        "capture_points": len(caps),
        "captured_at": caps,
        "synthesized_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M"),
    }
    p = Path(root) / ".archie" / "intent.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(spec, indent=2))
    os.replace(tmp, p)
    return spec

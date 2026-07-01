"""Tests for reconcile.py edge A (intent vs diff) reviewer."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "archie" / "standalone"))
import reconcile as rc  # noqa: E402
import intent as it  # noqa: E402


def test_edge_a_prompt_lists_criteria():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1", "text": "scope by tenant"}]
    p = rc.build_edge_a_prompt(spec, "diff")
    assert "ac1" in p and "scope by tenant" in p


def test_edge_a_clamps_to_intent_ceiling():
    spec = it.normalize("", source="inferred", ticket_ids=[])  # ceiling 0.5
    raw = json.dumps({"findings": [{"criterion_id": "ac1", "verdict": "unmet",
        "file": "x.py", "line": 1, "evidence": ["missing"], "falsification": "wired elsewhere",
        "confidence": 0.9}]})
    out = rc.parse_edge_a(raw, spec)
    assert out[0]["kind"] == "intent_unmet" and out[0]["confidence"] == 0.5

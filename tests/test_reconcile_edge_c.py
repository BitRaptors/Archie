"""Tests for reconcile.py edge C (requirement vs standing invariants) reviewer."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "archie" / "standalone"))
import reconcile as rc  # noqa: E402
import intent as it  # noqa: E402


def test_edge_c_prompt_lists_invariants():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1", "text": "let anyone read all tenants"}]
    p = rc.build_edge_c_prompt(spec, [{"id": "inv-tenant", "invariant": "tenant isolation"}])
    assert "inv-tenant" in p and "tenant isolation" in p


def test_parse_edge_c_produces_intent_conflict():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])  # ceiling 1.0
    raw = json.dumps({"findings": [{"invariant_id": "inv-tenant", "file": "x.py",
        "line": 3, "evidence": ["criterion asks cross-tenant read"],
        "falsification": "the criterion could be met per-tenant", "confidence": 0.9}]})
    out = rc.parse_edge_c(raw, spec)
    assert len(out) == 1
    f = out[0]
    assert f["kind"] == "intent_conflict"
    assert f["edge"] == "C"
    assert f["severity"] == "high"
    assert f["confidence"] == 0.9


def test_parse_edge_c_drops_no_falsification():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    raw = json.dumps({"findings": [{"invariant_id": "inv-x", "file": "x.py", "line": 1,
        "evidence": ["e"], "confidence": 0.9}]})  # no falsification
    out = rc.parse_edge_c(raw, spec)
    assert out == []

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
    # delivery findings are advisory: non-blocking severity_class + per-kind severity
    assert out[0]["severity"] == "high"
    assert out[0]["severity_class"] in {"tradeoff_undermined", "pattern_divergence"}


def test_edge_a_per_kind_severity():
    """parse_edge_a assigns per-kind severity: unmet=high, partial=medium, drift=low."""
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    def make_raw(verdict):
        return json.dumps({"findings": [{"criterion_id": "ac1", "verdict": verdict,
            "file": "x.py", "line": 1, "evidence": ["e"], "falsification": "fx",
            "confidence": 0.8}]})

    out_unmet = rc.parse_edge_a(make_raw("unmet"), spec)
    out_partial = rc.parse_edge_a(make_raw("partial"), spec)
    out_drift = rc.parse_edge_a(make_raw("drift"), spec)

    assert out_unmet[0]["severity"] == "high"
    assert out_partial[0]["severity"] == "medium"
    assert out_drift[0]["severity"] == "low"


def test_parse_edge_a_null_confidence():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])  # ceiling 1.0
    raw = json.dumps({"findings": [{"criterion_id": "ac1", "verdict": "unmet",
        "file": "x.py", "line": 1, "evidence": ["missing"], "falsification": "tested elsewhere",
        "confidence": None}]})
    out = rc.parse_edge_a(raw, spec)
    assert len(out) == 1
    assert out[0]["confidence"] == 0.0


def test_edge_a_prompt_none_criteria_no_crash():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = None
    p = rc.build_edge_a_prompt(spec, "diff")
    assert "DIFF" in p  # just verify it doesn't crash


def test_edge_a_prompt_includes_non_goals():
    spec = it.normalize("", source="sync", ticket_ids=[])
    spec["acceptance_criteria"] = [{"id": "ac1", "text": "scope it"}]
    spec["non_goals"] = ["do not touch the import path"]
    p = rc.build_edge_a_prompt(spec, "diff")
    assert "import path" in p

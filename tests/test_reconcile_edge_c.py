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


# --- conformance reviewer (edge B) ---

def test_build_conformance_prompt_lists_invariants():
    p = rc.build_conformance_prompt(
        "diff --git a/billing/usage.py",
        [{"id": "inv-tenant", "invariant": "tenant isolation"}],
        [{"title": "single-writer", "rationale": "avoid races"}],
    )
    assert "inv-tenant" in p and "tenant isolation" in p
    assert "single-writer" in p and "avoid races" in p
    assert "DIFF:" in p


def test_parse_conformance_produces_conformance_break():
    raw = json.dumps({"findings": [{"invariant_id": "inv-tenant", "file": "billing/usage.py",
        "line": 44, "evidence": ["export skips tenant filter"],
        "falsification": "show a tenant guard on the export path", "confidence": 0.85}]})
    out = rc.parse_conformance(raw)
    assert len(out) == 1
    f = out[0]
    assert f["kind"] == "conformance_break"
    assert f["edge"] == "B"
    assert f["severity"] == "high"
    assert f["confidence"] == 0.85


def test_parse_conformance_drops_no_falsification():
    raw = json.dumps({"findings": [{"invariant_id": "inv-x", "file": "x.py", "line": 1,
        "evidence": ["e"], "confidence": 0.9}]})  # no falsification
    out = rc.parse_conformance(raw)
    assert out == []


def test_review_conformance_empty_when_no_context():
    called = {"n": 0}
    def fake_run(*a, **k):
        called["n"] += 1
        return "{}"
    out = rc.review_conformance("/x", "diff", [], [], run=fake_run)
    assert out == []
    assert called["n"] == 0


def test_conformance_prompt_includes_intent():
    p = rc.build_conformance_prompt("diff", [{"id": "inv1", "invariant": "tenant iso"}], [],
                                    intent={"goals": ["Add export"], "acceptance_criteria": []})
    assert "Add export" in p
    assert "INTENDED CHANGE" not in rc.build_conformance_prompt("diff", [], [])   # backward compat

"""Tests for behavioral_review.py — prompt builder, parser, and review orchestrator.

The LLM seam (run_verifier) is mocked via monkeypatch so no real CLI is invoked.
Pattern mirrors test_verify_findings.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import behavioral_review as br  # noqa: E402


def test_build_prompt_lists_consumers():
    p = br.build_prompt("diff --git a/x.py", {"x.py": ["y.py", "z.py"]})
    assert "x.py" in p and "y.py" in p and "falsification" in p


def test_parse_findings_maps_to_evidence_schema():
    raw = json.dumps({"findings": [{
        "problem_statement": "N+1 in loop", "file": "x.py", "line": 5,
        "assumptions": ["called per row"], "evidence": ["x.py:5 queries in loop"],
        "falsification": "query is batched upstream", "confidence": 0.8,
        "kind": "behavioral_break"}]})
    out = br.parse_findings(raw)
    assert out[0]["kind"] == "behavioral_break" and out[0]["anchor"]["line"] == 5
    assert out[0]["falsification"]
    # delivery findings are advisory: non-blocking severity_class and severity field
    assert out[0]["severity"] == "high"
    assert out[0]["severity_class"] in {"tradeoff_undermined", "pattern_divergence"}


def test_review_mocked(monkeypatch):
    payload = json.dumps({"findings": [{
        "problem_statement": "mock bug", "file": "x.py", "line": 2,
        "assumptions": [], "evidence": ["e"], "falsification": "guarded upstream",
        "confidence": 0.9, "kind": "behavioral_break"}]})
    monkeypatch.setattr(br, "run_verifier", lambda *a, **k: payload)
    out = br.review("/x", "diff", {}, ["x.py"])
    assert len(out) == 1 and out[0]["problem_statement"] == "mock bug"


def test_parse_findings_drops_missing_falsification():
    assert br.parse_findings('{"findings":[{"problem_statement":"x","file":"a.py","line":1}]}') == []


def test_parse_findings_null_confidence():
    raw = json.dumps({"findings": [{
        "problem_statement": "crash", "file": "x.py", "line": 3,
        "assumptions": [], "evidence": ["x.py:3"],
        "falsification": "handled above", "confidence": None,
        "kind": "behavioral_break"}]})
    out = br.parse_findings(raw)
    assert len(out) == 1
    assert out[0]["confidence"] == 0.0


def test_parse_findings_string_confidence():
    raw = json.dumps({"findings": [{
        "problem_statement": "race", "file": "y.py", "line": 7,
        "assumptions": [], "evidence": ["y.py:7"],
        "falsification": "mutex applied", "confidence": "high",
        "kind": "behavioral_break"}]})
    out = br.parse_findings(raw)
    assert len(out) == 1
    assert out[0]["confidence"] == 0.0

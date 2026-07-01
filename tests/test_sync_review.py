"""Tests for sync_review.py — light delivery review with skip-gate.

The LLM seam (run_verifier / review_edge_a / behavioral_review_run) is
injected so no real CLI is invoked.
"""
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync_review as sr  # noqa: E402

BP = {"domain_invariants": [], "decisions": {"key_decisions": []},
      "persistence_stores": [], "data_models": []}


def test_skip_gate_no_llm_when_nothing_touched():
    called = {"n": 0}
    def fake_run(*a, **k): called["n"] += 1; return "{}"
    out = sr.run_sync_review("/x", "b", BP, {}, "diff", ["README.md"], {}, {}, run=fake_run)
    assert out["skipped"] is True and called["n"] == 0


def test_runs_when_source_touched(monkeypatch):
    monkeypatch.setattr(sr, "review_edge_a", lambda *a, **k: [])
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])
    out = sr.run_sync_review("/x", "b", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {})
    assert out["skipped"] is False and "verdict" in out

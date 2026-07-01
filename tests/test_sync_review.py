"""Tests for sync_review.py — light delivery review with skip-gate.

The LLM seam (run_verifier / review_edge_a / behavioral_review_run) is
injected so no real CLI is invoked.
"""
import json
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync_review as sr  # noqa: E402
import intent as it  # noqa: E402

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


def test_edge_c_skipped_without_criteria(monkeypatch):
    """With no acceptance_criteria and no goals, review_edge_c is never called."""
    monkeypatch.setattr(sr, "review_edge_a", lambda *a, **k: [])
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])
    calls = {"n": 0}
    def counting_edge_c(*a, **k):
        calls["n"] += 1
        return []
    monkeypatch.setattr(sr, "review_edge_c", counting_edge_c)
    # inferred spec (no branch record) has empty criteria + goals
    out = sr.run_sync_review("/x", "b", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {})
    assert out["skipped"] is False
    assert calls["n"] == 0


def test_edge_c_runs_with_criteria(tmp_path, monkeypatch):
    """When the spec has acceptance_criteria, review_edge_c is invoked once."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    spec = it.normalize("Add export", source="prompt", ticket_ids=[])
    spec["acceptance_criteria"] = [{"id": "ac1", "text": "export scoped by tenant"}]
    it.save_branch_record(archie_dir, "b", spec)

    monkeypatch.setattr(sr, "review_edge_a", lambda *a, **k: [])
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])
    calls = {"n": 0}
    def counting_edge_c(*a, **k):
        calls["n"] += 1
        return []
    monkeypatch.setattr(sr, "review_edge_c", counting_edge_c)
    sr.run_sync_review(str(tmp_path), "b", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {},
                       run=lambda *a, **k: "{}")
    assert calls["n"] == 1


def test_sync_review_resolves_before_edge_a(tmp_path, monkeypatch):
    """Branch record with raw text but empty acceptance_criteria: resolve() is called
    before edge-A so edge-A sees populated criteria."""
    # Set up a branch intent record with raw text and no acceptance_criteria
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    spec = it.normalize("Add rate limiting", source="prompt", ticket_ids=[])
    it.save_branch_record(archie_dir, "feature/rate-limit", spec)

    # resolve() LLM response
    resolve_payload = json.dumps({
        "goals": ["rate limit the API"],
        "acceptance_criteria": [{"id": "ac1", "text": "returns 429 after limit"}],
    })

    # edge-A response (empty findings)
    edge_a_payload = json.dumps({"findings": []})

    call_log = []
    def fake_run(prompt, path, model):
        call_log.append(prompt[:60])
        # First call is resolve, second is edge-A
        if "Extract the concrete" in prompt:
            return resolve_payload
        return edge_a_payload

    # Capture the intent_spec passed to review_edge_a
    captured = {}
    original_edge_a = sr.review_edge_a
    def capturing_edge_a(root, intent_spec, diff_text, run=None):
        captured["spec"] = intent_spec
        return []
    monkeypatch.setattr(sr, "review_edge_a", capturing_edge_a)
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])

    sr.run_sync_review(
        str(tmp_path), "feature/rate-limit", BP, {},
        "diff text", ["a.py"], {"a.py": {1}}, {},
        run=fake_run,
    )

    # edge-A must have seen non-empty acceptance_criteria
    assert captured.get("spec") is not None
    assert len(captured["spec"].get("acceptance_criteria", [])) > 0, (
        f"edge-A spec had no criteria: {captured['spec']}"
    )

def test_conformance_runs_when_specialist_routed(tmp_path, monkeypatch):
    """A blueprint invariant on the changed file routes the selector to a Lane-2
    specialist, so review_conformance runs and its conformance_break reaches confirmed."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()

    bp = {
        "domain_invariants": [
            {"id": "inv-tenant", "invariant": "tenant scope", "enforced_at": ["a.py"]}
        ],
        "decisions": {"key_decisions": []},
        "persistence_stores": [],
        "data_models": [],
    }

    monkeypatch.setattr(sr, "review_edge_a", lambda *a, **k: [])
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])
    monkeypatch.setattr(sr, "review_edge_c", lambda *a, **k: [])

    conf_finding = {
        "id": "f_cf_0", "kind": "conformance_break", "edge": "B",
        "problem_statement": "violates inv-tenant",
        "anchor": {"file": "a.py", "line": 1, "changed": True},
        "assumptions": ["invariant inv-tenant"], "evidence": ["no tenant filter"],
        "falsification": "show a tenant guard", "confidence": 0.9,
        "source": "reconcile:conformance", "severity_class": "tradeoff_undermined",
        "severity": "high",
    }
    called = {"n": 0}
    def fake_conformance(root, diff_text, invariants, decisions, run=None):
        called["n"] += 1
        # the routed invariant must have been passed through touched_context
        assert any(i.get("id") == "inv-tenant" for i in invariants)
        return [conf_finding]
    monkeypatch.setattr(sr, "review_conformance", fake_conformance)

    out = sr.run_sync_review(
        str(tmp_path), "b", bp, {}, "diff", ["a.py"], {"a.py": {1}},
        floors={"conformance_break": 0.5},
        run=lambda *a, **k: "{}",
    )
    assert out["skipped"] is False
    assert called["n"] == 1
    confirmed_kinds = {f["kind"] for f in out["confirmed"]}
    assert "conformance_break" in confirmed_kinds
    assert out["verdict"]["breaks"] >= 1


def test_resolved_spec_persisted(tmp_path, monkeypatch):
    """After a run where resolve() populates acceptance_criteria, the resolved
    spec is persisted so load_branch_record returns criteria (no repeat LLM)."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    spec = it.normalize("Add rate limiting", source="prompt", ticket_ids=[])
    it.save_branch_record(archie_dir, "feature/rate-limit", spec)

    resolve_payload = json.dumps({
        "goals": ["rate limit the API"],
        "acceptance_criteria": [{"id": "ac1", "text": "returns 429 after limit"}],
    })

    def fake_run(prompt, path, model):
        if "Extract the concrete" in prompt:
            return resolve_payload
        return json.dumps({"findings": []})

    monkeypatch.setattr(sr, "review_edge_a", lambda *a, **k: [])
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])
    monkeypatch.setattr(sr, "review_edge_c", lambda *a, **k: [])

    out = sr.run_sync_review(
        str(tmp_path), "feature/rate-limit", BP, {},
        "diff text", ["a.py"], {"a.py": {1}}, {},
        run=fake_run,
    )
    assert out["skipped"] is False

    # The persisted record now carries the resolved criteria.
    persisted = it.load_branch_record(archie_dir, "feature/rate-limit")
    assert persisted is not None
    assert len(persisted.get("acceptance_criteria", [])) > 0

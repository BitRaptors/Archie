"""Tests for sync_review.py — light delivery review with skip-gate.

sync_review now delegates its reviewer fan-out to review_core.run_review (F3:
one reviewer brain shared with the CI delivery review). Individual reviewers
(review_edge_a, review_edge_c, review_conformance, review_invariants,
behavioral_review_run) are bound into review_core's OWN module namespace at
review_core's import time, so tests that want to intercept them must patch
review_core's attributes (rc.review_edge_a, etc.) — patching sync_review's
(sr.review_edge_a) no longer has any effect on the actual call, since
sync_review only calls review_core.run_review now.

The LLM seam (run_verifier / review_core.run_review) is injected so no real
CLI is invoked.
"""
import json
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync_review as sr  # noqa: E402
import intent as it  # noqa: E402
import review_core as rc  # noqa: E402

BP = {"domain_invariants": [], "decisions": {"key_decisions": []},
      "persistence_stores": [], "data_models": []}


def test_skip_gate_no_llm_when_nothing_touched():
    called = {"n": 0}
    def fake_run(*a, **k): called["n"] += 1; return "{}"
    out = sr.run_sync_review("/x", "b", BP, {}, "diff", ["README.md"], {}, {}, run=fake_run)
    assert out["skipped"] is True and called["n"] == 0


def test_runs_when_source_touched():
    out = sr.run_sync_review("/x", "b", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {},
                             run=lambda *a, **k: "{}")
    assert out["skipped"] is False and "verdict" in out


def test_edge_c_skipped_without_criteria(monkeypatch):
    """With no acceptance_criteria and no goals, review_edge_c is never called.
    (Gating now lives inside review_core.run_review's has_intent check.)"""
    calls = {"n": 0}
    def counting_edge_c(*a, **k):
        calls["n"] += 1
        return []
    monkeypatch.setattr(rc, "review_edge_c", counting_edge_c)
    # inferred spec (no branch record) has empty criteria + goals
    out = sr.run_sync_review("/x", "b", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {},
                             run=lambda *a, **k: "{}")
    assert out["skipped"] is False
    assert calls["n"] == 0


def test_edge_c_runs_with_criteria(tmp_path, monkeypatch):
    """When the spec has acceptance_criteria, review_edge_c is invoked once
    (via review_core's has_intent gate)."""
    archie_dir = tmp_path / ".archie"
    archie_dir.mkdir()
    spec = it.normalize("Add export", source="prompt", ticket_ids=[])
    spec["acceptance_criteria"] = [{"id": "ac1", "text": "export scoped by tenant"}]
    it.save_branch_record(archie_dir, "b", spec)

    calls = {"n": 0}
    def counting_edge_c(*a, **k):
        calls["n"] += 1
        return []
    monkeypatch.setattr(rc, "review_edge_c", counting_edge_c)
    sr.run_sync_review(str(tmp_path), "b", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {},
                       run=lambda *a, **k: "{}")
    assert calls["n"] == 1


def test_sync_review_resolves_before_edge_a(tmp_path, monkeypatch):
    """Branch record with raw text but empty acceptance_criteria: resolve() is called
    (in sync_review, before the core fan-out) so edge-A — now invoked inside
    review_core.run_review — sees populated criteria."""
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
        # First call is resolve, second is edge-A (called inside review_core)
        if "Extract the concrete" in prompt:
            return resolve_payload
        return edge_a_payload

    # Capture the intent_spec passed to review_edge_a. review_core imports
    # review_edge_a into its OWN module namespace, so the reviewer to patch is
    # review_core's, not sync_review's (sync_review no longer calls it directly).
    captured = {}
    def capturing_edge_a(root, intent_spec, diff_text, run=None):
        captured["spec"] = intent_spec
        return []
    monkeypatch.setattr(rc, "review_edge_a", capturing_edge_a)

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
    """A blueprint invariant on the changed file makes touched_context() return a
    non-empty invariants list, so review_core routes to the invariant-specialist
    (review_invariants) and its conformance_break reaches confirmed.

    Accepted behavior change (F3): the OLD sync-only code gated this on
    sel["specialists"] and called review_conformance for invariants+decisions
    together. The shared core instead gates invariant-specialist on
    touched_context()["invariants"] and review_conformance separately on
    touched_context()["decisions"] — the two surfaces now gate identically."""
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

    conf_finding = {
        "id": "f_cf_0", "kind": "conformance_break", "edge": "B",
        "problem_statement": "violates inv-tenant",
        "anchor": {"file": "a.py", "line": 1, "changed": True},
        "assumptions": ["invariant inv-tenant"], "evidence": ["no tenant filter"],
        "falsification": "show a tenant guard", "confidence": 0.9,
        "source": "invariant_specialist", "severity_class": "tradeoff_undermined",
        "severity": "high",
    }
    called = {"n": 0}
    def fake_review_invariants(root, diff_text, invariants, run=None):
        called["n"] += 1
        # the routed invariant must have been passed through touched_context
        assert any(i.get("id") == "inv-tenant" for i in invariants)
        return [conf_finding]
    monkeypatch.setattr(rc, "review_invariants", fake_review_invariants)
    # decisions is empty for this bp, so review_conformance would not be routed to
    # anyway; patch it out defensively so a future bp change doesn't hit the real thing.
    monkeypatch.setattr(rc, "review_conformance", lambda *a, **k: [])

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


def test_sync_review_uses_committed_intent(tmp_path, monkeypatch):
    """sync_review prefers committed .archie/intent.json over branch record. The
    spec is now consumed inside review_core.run_review, so capture it by patching
    review_core's review_edge_a (bound into review_core's own namespace)."""
    it.write_committed_intent(tmp_path, {"source": "sync", "goals": [],
        "acceptance_criteria": [{"id": "a", "text": "Scoped"}], "ticket_ids": [], "raw": "plan"})
    seen = {}
    monkeypatch.setattr(rc, "review_edge_a",
                        lambda root, spec, diff, run=None: seen.setdefault("crit", spec.get("acceptance_criteria")) or [])
    sr.run_sync_review(str(tmp_path), "feature/x", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {},
                       run=lambda *a, **k: "{}")
    assert seen.get("crit") and seen["crit"][0]["text"] == "Scoped"   # committed criteria reached edge-A


def test_sync_review_uses_core(tmp_path, monkeypatch):
    (tmp_path / ".archie").mkdir()
    (tmp_path / "a.py").write_text("def f():\n    return None.x\n")
    called = {"core": False}
    import review_core
    real = review_core.run_review

    def spy(*a, **k):
        called["core"] = True
        return real(*a, **k)
    monkeypatch.setattr(review_core, "run_review", spy)

    def fake_run(prompt, root, verifier, **kw):
        return '{"findings":[{"problem_statement":"null deref","file":"a.py","line":2,'\
               '"falsification":"p","confidence":0.8}]}'

    # REAL signature: root, branch, blueprint, import_graph, diff_text,
    #                 changed_files, changed_lines, floors, *, run
    out = sr.run_sync_review(tmp_path, "main", {"domain_invariants": []}, {},
                             "diff --git a/a.py b/a.py", ["a.py"], {}, {},
                             run=fake_run)
    assert called["core"] is True
    assert out.get("skipped") is not True   # a.py is source → skip-gate must not fire


def test_sync_review_excludes_acked_findings_from_verdict(tmp_path, monkeypatch):
    (tmp_path / ".archie").mkdir()
    (tmp_path / "a.py").write_text("x = 1\n")
    import overrides as ov
    entry = {"rule_id": "inv-003", "reason": "r", "authorized_by": "G",
             "branch": "b", "created_at": "t", "status": "acked"}
    monkeypatch.setattr(ov, "active", lambda root: {"inv-003": entry})

    import review_core

    def fake_core(*a, **k):
        return [{"kind": "conformance_break", "id": "f_inv_inv-003", "edge": "B",
                 "problem_statement": "violates inv-003: cost stored",
                 "anchor": {"file": "a.py", "line": 1, "changed": True},
                 "assumptions": [], "evidence": ["e"], "falsification": "f",
                 "confidence": 0.9, "source": "invariant_specialist:ctc"}]
    monkeypatch.setattr(review_core, "run_review", fake_core)

    out = sr.run_sync_review(str(tmp_path), "main", {"domain_invariants": []}, {},
                             "diff --git a/a.py b/a.py", ["a.py"], {"a.py": {1}}, {},
                             run=lambda *a, **k: "{}")
    assert out["skipped"] is False
    assert out["verdict"]["breaks"] == 0            # acked → not a break
    assert out["acked"][0][0]["rule_id"] == "inv-003"

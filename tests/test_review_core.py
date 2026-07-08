import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import review_core as rc  # noqa: E402


def test_run_review_fans_out_and_merges(tmp_path):
    (tmp_path / "a.py").write_text("def f():\n    return None.x\n")
    spec = {"acceptance_criteria": [{"id": "ac1", "text": "do the thing"}], "non_goals": []}
    bp = {"domain_invariants": []}

    def fake_run(prompt, root, verifier, **kw):
        # behavioral + universals emit one finding each; edge-A silent
        if "focused ONLY on" in prompt or "behavioral code reviewer" in prompt:
            return '{"findings":[{"problem_statement":"null deref","file":"a.py","line":2,'\
                   '"falsification":"prove","confidence":0.8}]}'
        return "{}"

    out = rc.run_review(tmp_path, "diff --git a/a.py b/a.py", ["a.py"], bp, {}, spec,
                        run=fake_run, passes=2, workers=2)
    # 2 behavioral passes + 4 universal lenses all found "null deref on a.py" → merged to 1
    files = {f["anchor"]["file"] for f in out}
    assert "a.py" in files
    nulls = [f for f in out if "null deref" in f.get("problem_statement", "")]
    assert len(nulls) == 1                     # union+dedup collapsed them
    assert nulls[0]["confidence"] >= 0.9       # high agreement


def test_run_review_serial_when_workers_env_1(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_REVIEW_WORKERS", "1")
    (tmp_path / "a.py").write_text("x=1\n")
    out = rc.run_review(tmp_path, "diff", ["a.py"], {"domain_invariants": []}, {},
                        {"acceptance_criteria": []}, run=lambda *a, **k: "{}", passes=1)
    assert isinstance(out, list)


def test_run_review_serial_degrades_on_raising_reviewer(tmp_path, monkeypatch):
    # A reviewer that raises must not crash the whole fan-out, even in the
    # serial (ARCHIE_REVIEW_WORKERS=1) path — same degrade-to-[] contract as
    # the threaded path.
    monkeypatch.setenv("ARCHIE_REVIEW_WORKERS", "1")
    (tmp_path / "a.py").write_text("x=1\n")

    def boom(*a, **k):
        raise ValueError("kaboom")

    out = rc.run_review(tmp_path, "diff", ["a.py"], {"domain_invariants": []}, {},
                        {"acceptance_criteria": []}, run=boom, passes=1)
    assert out == []


def test_context_prep_crash_degrades_but_reviewers_still_run(tmp_path, monkeypatch):
    # Regression (PR #17): a TypeError in build_pack ran UNGUARDED before the
    # fan-out and killed every reviewer. Now it degrades to empty evidence and
    # the reviewers still produce findings.
    import review_core as rcmod
    monkeypatch.setattr(rcmod, "build_pack",
                        lambda *a, **k: (_ for _ in ()).throw(TypeError("legacy shape")))
    (tmp_path / "a.py").write_text("def f():\n    return None.x\n")

    def fake_run(prompt, root, verifier, **kw):
        if "focused ONLY on" in prompt or "behavioral code reviewer" in prompt:
            return '{"findings":[{"problem_statement":"null deref","file":"a.py","line":2,'\
                   '"falsification":"prove","confidence":0.8}]}'
        return "{}"

    out = rc.run_review(tmp_path, "diff --git a/a.py b/a.py", ["a.py"],
                        {"domain_invariants": []}, {}, {"acceptance_criteria": []},
                        run=fake_run, passes=1, workers=1)
    assert any("null deref" in f.get("problem_statement", "") for f in out)


def test_run_review_drops_intent_graders(tmp_path, monkeypatch):
    import review_core as rcmod
    called = []
    monkeypatch.setattr(rcmod, "review_edge_a",
                        lambda *a, **k: called.append("edge_a") or [], raising=False)
    monkeypatch.setattr(rcmod, "review_edge_c",
                        lambda *a, **k: called.append("edge_c") or [], raising=False)
    (tmp_path / "a.py").write_text("x = 1\n")
    rc.run_review(tmp_path, "diff --git a/a.py b/a.py", ["a.py"],
                  {"domain_invariants": []}, {},
                  {"acceptance_criteria": [{"id": "ac1", "text": "t"}]},
                  run=lambda *a, **k: "{}", workers=1)
    assert called == []


def test_run_review_defaults_to_one_pass():
    import inspect
    assert inspect.signature(rc.run_review).parameters["passes"].default == 1


def test_failed_reviewers_are_counted_not_silently_swallowed(tmp_path):
    """A lens that times out must not vanish. _safe swallowed every exception with
    no log and no count, so a thin review looked identical to a clean one."""
    (tmp_path / "a.py").write_text("x = 1\n")
    stats = {}

    def boom(prompt, root, verifier, **kw):
        if "focused ONLY on" in prompt:      # every universal lens explodes
            raise RuntimeError("timeout")
        return "{}"

    rc.run_review(tmp_path, "diff --git a/a.py b/a.py", ["a.py"],
                  {"domain_invariants": []}, {}, {"acceptance_criteria": []},
                  run=boom, workers=1, stats=stats)
    assert stats["failed"] == 4          # the four lenses
    assert stats["total"] >= 5


def test_stats_is_optional_and_zero_on_success(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    stats = {}
    rc.run_review(tmp_path, "diff", ["a.py"], {"domain_invariants": []}, {},
                  {"acceptance_criteria": []}, run=lambda *a, **k: "{}",
                  workers=1, stats=stats)
    assert stats["failed"] == 0
    rc.run_review(tmp_path, "diff", ["a.py"], {"domain_invariants": []}, {},
                  {"acceptance_criteria": []}, run=lambda *a, **k: "{}", workers=1)

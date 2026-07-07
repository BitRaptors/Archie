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

import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import universal_specialists as us  # noqa: E402


def test_four_lenses_defined():
    keys = [k for k, _ in us.LENSES]
    assert keys == ["null-safety", "security", "resource-perf", "concurrency"]


def test_review_one_tags_source_and_focus():
    lens = us.LENSES[1]  # security
    seen = {}

    def fake_run(prompt, root, verifier, **kw):
        seen["prompt"] = prompt
        return '{"findings":[{"problem_statement":"sql injection","file":"a.py",'\
               '"line":2,"falsification":"prove","confidence":0.8}]}'

    out = us.review_one(".", "diff", "CTX", None, lens, run=fake_run)
    assert "security" in seen["prompt"].lower()
    assert out[0]["source"] == "universal:security"


def test_review_universal_runs_all_four():
    calls = {"n": 0}

    def fake_run(prompt, root, verifier, **kw):
        calls["n"] += 1
        return "{}"

    us.review_universal(".", "diff", "CTX", None, run=fake_run)
    assert calls["n"] == 4

import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import finding_merge as fm  # noqa: E402


def _f(file, stmt, conf, kind="behavioral_break"):
    return {"kind": kind, "confidence": conf, "problem_statement": stmt,
            "anchor": {"file": file, "line": 1}}


def test_two_agreeing_passes_boost_confidence():
    a = _f("a.py", "null deref on billable_steps", 0.4)
    b = _f("a.py", "null deref when billable_steps is missing", 0.4)  # paraphrase
    out = fm.merge([a, b], passes=2)
    assert len(out) == 1
    assert out[0]["confidence"] >= 0.9   # 2/2 agreement → ~1.0


def test_single_pass_finding_kept_distinct():
    a = _f("a.py", "unbounded loop over rows", 0.8)
    b = _f("b.py", "missing index on user_id", 0.8)
    out = fm.merge([a, b], passes=2)
    assert len(out) == 2


def test_low_agreement_stays_low_confidence():
    a = _f("a.py", "maybe a race in the cache write", 0.3)
    out = fm.merge([a], passes=2)   # 1/2 agreement
    assert out[0]["confidence"] < 0.6   # renders as a "possible issue"


def test_empty():
    assert fm.merge([], passes=2) == []

import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import delivery_review as dr  # noqa: E402


def test_intake_skips_bot_and_large():
    ok, why = dr.should_review({"author": "dependabot[bot]", "changed_files": 3, "labels": []}, 75)
    assert ok is False and "bot" in why
    ok, why = dr.should_review({"author": "human", "changed_files": 200, "labels": []}, 75)
    assert ok is False and "too many files" in why


def test_intake_override_label_forces_run():
    ok, _ = dr.should_review({"author": "dependabot[bot]", "changed_files": 3,
                              "labels": ["archie-review"]}, 75)
    assert ok is True


def test_render_verdict_shows_completeness_and_breaks():
    md = dr.render_verdict({"intent_completeness": "3/4", "breaks": 1, "conflicts": 0},
                           [{"kind": "intent_unmet", "problem_statement": "ac2", "anchor": {"file": "x.py", "line": 4}}])
    assert "3/4" in md and "1" in md and "x.py:4" in md

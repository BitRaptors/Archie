import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import evidence_schema as es  # noqa: E402

def test_make_finding_carries_all_fields():
    f = es.make_finding(
        id="f_1", kind="behavioral_break", edge="B",
        problem_statement="null deref on export path",
        anchor={"file": "export.py", "line": 44, "changed": True},
        assumptions=["field may be None"], evidence=["export.py:44 dereferences x"],
        falsification="a guard exists upstream of export.py:44",
        confidence=0.7, source="behavioral", severity_class="pitfall_triggered",
    )
    assert es.has_evidence_fields(f)
    assert f["falsification"] and f["anchor"]["changed"] is True

def test_clamp_confidence_caps_but_never_raises():
    f = es.make_finding(id="f_2", kind="intent_unmet", edge="A",
        problem_statement="p", anchor={"file": "a.py", "line": 1, "changed": True},
        assumptions=[], evidence=["e"], falsification="fx",
        confidence=0.9, source="reconcile:edgeA", severity_class="pattern_divergence")
    assert es.clamp_confidence(f, 0.5)["confidence"] == 0.5
    assert es.clamp_confidence(f, 0.99)["confidence"] == 0.9

def test_has_evidence_fields_false_when_missing_falsification():
    assert es.has_evidence_fields({"id": "x", "anchor": {}, "evidence": []}) is False

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


def test_extract_json_obj_ignores_surrounding_prose():
    # Stray balanced-brace pair in prose ("{ x }") is invalid JSON — scanning
    # continues and finds the next valid object.
    raw = 'note { x } then {"findings":[]} end'
    assert es.extract_json_obj(raw) == {"findings": []}
    assert es.extract_json_obj('no json here') == {}
    assert es.extract_json_obj('{"findings":[]} end') == {"findings": []}
    assert es.extract_json_obj('preamble {"findings":[]}') == {"findings": []}


def test_extract_json_obj_valid_payload():
    import json
    payload = {"findings": [{"id": "f1", "confidence": 0.9}]}
    assert es.extract_json_obj(json.dumps(payload)) == payload


def test_coerce_confidence_float():
    assert es.coerce_confidence(0.8) == 0.8


def test_coerce_confidence_null():
    assert es.coerce_confidence(None) == 0.0


def test_coerce_confidence_string():
    assert es.coerce_confidence("high") == 0.0


def test_coerce_confidence_string_numeric():
    assert es.coerce_confidence("0.7") == 0.7


def test_make_finding_has_severity():
    """make_finding includes severity field; default is 'medium'; explicit value passes through."""
    f_default = es.make_finding(
        id="f_sev", kind="behavioral_break", edge="B",
        problem_statement="test", anchor={"file": "a.py", "line": 1, "changed": True},
        assumptions=[], evidence=["e"], falsification="fx",
        confidence=0.5, source="behavioral", severity_class="tradeoff_undermined",
    )
    assert f_default["severity"] == "medium"

    f_explicit = es.make_finding(
        id="f_sev2", kind="intent_unmet", edge="A",
        problem_statement="test2", anchor={"file": "b.py", "line": 2, "changed": True},
        assumptions=[], evidence=["e2"], falsification="fx2",
        confidence=0.8, source="reconcile:edgeA", severity_class="tradeoff_undermined",
        severity="high",
    )
    assert f_explicit["severity"] == "high"

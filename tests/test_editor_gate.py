import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import editor_gate as eg  # noqa: E402
from evidence_schema import make_finding  # noqa: E402


def _f(fid, file, line, conf, kind="behavioral_break"):
    return make_finding(id=fid, kind=kind, edge="B", problem_statement="p",
        anchor={"file": file, "line": line, "changed": True}, assumptions=[],
        evidence=["e"], falsification="fx", confidence=conf,
        source="behavioral", severity_class="pitfall_triggered")

FLOORS = {"behavioral_break": 0.5, "intent_unmet": 0.4}

def test_drops_below_floor():
    out = eg.gate([_f("f1", "a.py", 3, 0.2)], [], changed_lines=None, floors=FLOORS)
    assert out["confirmed"] == [] and out["suppressed"][0]["reason"] == "below_floor"

def test_drops_when_anchor_not_on_changed_line():
    out = eg.gate([_f("f1", "a.py", 99, 0.9)], [], changed_lines={"a.py": {1, 2}}, floors=FLOORS)
    assert out["confirmed"] == [] and out["suppressed"][0]["reason"] == "anchor_unchanged"

def test_dedups_against_store():
    store = [{"anchor": {"file": "a.py"}, "kind": "behavioral_break", "id": "old"}]
    out = eg.gate([_f("f1", "a.py", 1, 0.9)], store, changed_lines={"a.py": {1}}, floors=FLOORS)
    assert out["confirmed"] == [] and out["suppressed"][0]["reason"] == "duplicate"

def test_keeps_valid_new_finding():
    out = eg.gate([_f("f1", "a.py", 1, 0.9)], [], changed_lines={"a.py": {1}}, floors=FLOORS)
    assert len(out["confirmed"]) == 1 and out["confirmed"][0]["id"] == "f1"

def test_cannot_invent_only_passes_through_inputs():
    out = eg.gate([], [], changed_lines=None, floors=FLOORS)
    assert out["confirmed"] == []

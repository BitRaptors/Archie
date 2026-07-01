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
    # Store entry with same (file, line, kind) as the incoming finding
    store = [{"anchor": {"file": "a.py", "line": 1}, "kind": "behavioral_break", "id": "old"}]
    out = eg.gate([_f("f1", "a.py", 1, 0.9)], store, changed_lines={"a.py": {1}}, floors=FLOORS)
    assert out["confirmed"] == [] and out["suppressed"][0]["reason"] == "duplicate"

def test_keeps_valid_new_finding():
    out = eg.gate([_f("f1", "a.py", 1, 0.9)], [], changed_lines={"a.py": {1}}, floors=FLOORS)
    assert len(out["confirmed"]) == 1 and out["confirmed"][0]["id"] == "f1"

def test_cannot_invent_only_passes_through_inputs():
    out = eg.gate([], [], changed_lines=None, floors=FLOORS)
    assert out["confirmed"] == []


def test_dedup_keeps_distinct_lines_same_file_kind():
    """Two findings with same file+kind but different lines should BOTH be confirmed."""
    f1 = _f("f1", "a.py", 10, 0.9)
    f2 = _f("f2", "a.py", 99, 0.9)
    out = eg.gate([f1, f2], [], changed_lines={"a.py": {10, 99}}, floors=FLOORS)
    ids = {x["id"] for x in out["confirmed"]}
    assert ids == {"f1", "f2"}, f"Expected both confirmed, got confirmed={ids}, suppressed={out['suppressed']}"


def test_anchor_string_line_matches_int_changed_line():
    """Anchor line as string '88' should match int 88 in changed_lines."""
    f = _f("f1", "x.py", "88", 0.9)
    out = eg.gate([f], [], changed_lines={"x.py": {88}}, floors=FLOORS)
    assert len(out["confirmed"]) == 1, f"Expected confirmed, got suppressed={out['suppressed']}"


def test_anchor_none_line_file_changed_keeps():
    """When anchor line is None but the file is in changed_lines, keep the finding."""
    f = _f("f1", "y.py", None, 0.9)
    out = eg.gate([f], [], changed_lines={"y.py": {1, 2, 3}}, floors=FLOORS)
    assert len(out["confirmed"]) == 1, f"Expected confirmed, got suppressed={out['suppressed']}"


def test_gate_coerces_nonnumeric_confidence():
    """A raw finding with non-numeric confidence ("high" or None) must not crash
    the gate — it is coerced to 0.0 and dropped below floor, never raised."""
    high = _f("f1", "a.py", 1, 0.9); high["confidence"] = "high"
    nul = _f("f2", "a.py", 1, 0.9); nul["confidence"] = None
    out = eg.gate([high, nul], [], changed_lines=None, floors=FLOORS)
    assert out["confirmed"] == []
    reasons = {s["reason"] for s in out["suppressed"]}
    assert reasons == {"below_floor"}

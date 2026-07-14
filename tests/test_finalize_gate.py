"""Test gate_and_merge in finalize.py — cold-read editor gate pass."""
import json
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))

import finalize as fz  # noqa: E402
from evidence_schema import make_finding  # noqa: E402


def _f(fid, conf):
    return make_finding(id=fid, kind="behavioral_break", edge="B", problem_statement="p",
        anchor={"file": "a.py", "line": 3, "changed": False}, assumptions=[], evidence=["e"],
        falsification="fx", confidence=conf, source="deep_scan", severity_class="pitfall_triggered")


def test_cold_read_strict_floor(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    out = fz.gate_and_merge(ad, [_f("f1", 0.55), _f("f2", 0.9)], floors={"behavioral_break": 0.7})
    store = json.loads((ad / "findings.json").read_text())["findings"]
    ids = {f["id"] for f in store}
    assert "f2" in ids and "f1" not in ids and out["suppressed"] == 1


def test_finalize_routes_risk_through_gate(tmp_path):
    """A Risk finding WITH evidence fields at confidence 0.7 survives the gate at
    DEFAULT_COLD_FLOORS (behavioral_break floor 0.6) and lands in the store; a
    finding lacking `falsification` (no evidence schema) is dropped."""
    ad = tmp_path / ".archie"; ad.mkdir()
    good = _f("risk_good", 0.7)                      # full evidence fields, conf 0.7 >= 0.6
    bad = dict(_f("risk_bad", 0.9)); bad.pop("falsification")  # no evidence schema -> dropped
    out = fz.gate_and_merge(ad, [good, bad], floors=fz.DEFAULT_COLD_FLOORS)
    store = json.loads((ad / "findings.json").read_text())["findings"]
    ids = {f["id"] for f in store}
    assert "risk_good" in ids
    assert "risk_bad" not in ids
    assert out["merged"] == 1 and out["suppressed"] == 1


def test_finalize_gate_survives_bad_confidence(tmp_path):
    """A raw finding carrying a non-numeric confidence ("high") must not raise
    through gate_and_merge — it is coerced (dropped below floor), returns a dict."""
    ad = tmp_path / ".archie"; ad.mkdir()
    bad = _f("risk_str", 0.9); bad["confidence"] = "high"
    out = fz.gate_and_merge(ad, [bad], floors=fz.DEFAULT_COLD_FLOORS)
    assert isinstance(out, dict)
    assert "merged" in out and "suppressed" in out

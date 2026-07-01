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

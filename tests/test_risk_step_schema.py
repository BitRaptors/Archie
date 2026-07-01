import json
import pathlib
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
from evidence_schema import has_evidence_fields  # noqa: E402


def test_risk_fixture_satisfies_evidence_schema():
    fx = pathlib.Path("tests/fixtures/risk_finding_sample.json")
    finding = json.loads(fx.read_text())
    assert has_evidence_fields(finding)
    assert finding["edge"] == "B"

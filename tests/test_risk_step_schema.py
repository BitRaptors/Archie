import json
import pathlib
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
from evidence_schema import has_evidence_fields  # noqa: E402

_RISK_MD = Path(__file__).resolve().parent.parent / "archie" / "assets" / "workflow" / "deep-scan" / "steps" / "step-5b-risk.md"


def test_risk_fixture_satisfies_evidence_schema():
    fx = pathlib.Path("tests/fixtures/risk_finding_sample.json")
    finding = json.loads(fx.read_text())
    assert has_evidence_fields(finding)
    assert finding["edge"] == "B"


def test_risk_kinds_only_delivery_taxonomy():
    """Canonical risk step must NOT list schema_drift or mechanical_violation as emitted kinds."""
    text = _RISK_MD.read_text()
    # The allowed-kind line must only contain the delivery taxonomy
    assert "schema_drift" not in text or "behavioral_break|schema_drift" not in text, (
        "schema_drift still appears as an emitted kind in step-5b-risk.md"
    )
    assert "mechanical_violation" not in text or "behavioral_break|mechanical_violation" not in text, (
        "mechanical_violation still appears as an emitted kind in step-5b-risk.md"
    )
    # The delivery taxonomy kinds must be present
    assert "behavioral_break" in text
    assert "conformance_break" in text

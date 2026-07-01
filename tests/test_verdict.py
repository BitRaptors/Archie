"""Test aggregate_verdict function from reconcile."""
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import reconcile as rc  # noqa: E402
import intent as it     # noqa: E402


def test_aggregate_counts_completeness_and_breaks():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}, {"id": "ac3"}]
    confirmed = [
        {"kind": "intent_unmet", "assumptions": ["criterion ac2"]},
        {"kind": "conformance_break"},
        {"kind": "behavioral_break"},
    ]
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["intent_completeness"] == "2/3" and v["breaks"] == 2 and v["conflicts"] == 0


def test_aggregate_dedups_unmet_by_criterion():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}, {"id": "ac3"}]
    confirmed = [
        {"kind": "intent_unmet", "criterion_id": "ac2"},
        {"kind": "intent_partial", "criterion_id": "ac2"},  # same criterion, must not double-count
    ]
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["intent_completeness"] == "2/3"

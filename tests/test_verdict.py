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
    # 2 breaks, 0 conflicts, 0 drift → gate_signal = 1.0 - min(1.0, 0.5) = 0.5
    assert v["gate_signal"] == 0.5


def test_aggregate_dedups_unmet_by_criterion():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}, {"id": "ac3"}]
    confirmed = [
        {"kind": "intent_unmet", "criterion_id": "ac2"},
        {"kind": "intent_partial", "criterion_id": "ac2"},  # same criterion, must not double-count
    ]
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["intent_completeness"] == "2/3"


def test_aggregate_counts_drift():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}, {"id": "ac3"}]
    confirmed = [
        {"kind": "intent_drift"},
        {"kind": "intent_drift"},
        {"kind": "intent_drift"},
    ]
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["drift"] == 3
    assert v["gate_signal"] < 1.0
    # 0 breaks, 0 conflicts, 3 drift → gate_signal = 1.0 - min(1.0, 0.3) = 0.7
    assert v["gate_signal"] == 0.7


def test_aggregate_counts_intent_conflict():
    """A confirmed intent_conflict (produced by edge-C) is counted and lowers the gate signal."""
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}]
    confirmed = [{"kind": "intent_conflict", "problem_statement": "conflicts with tenant isolation"}]
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["conflicts"] >= 1
    # 0 breaks, 1 conflict, 0 drift → gate_signal = 1.0 - min(1.0, 0.5) = 0.5
    assert v["gate_signal"] < 1.0
    assert v["gate_signal"] == 0.5


def test_aggregate_counts_conformance_break():
    """A confirmed conformance_break (now produced by review_conformance) is counted
    in the breaks total — proving the counter finally has a producer path."""
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}]
    confirmed = [{"kind": "conformance_break", "problem_statement": "violates inv-tenant"}]
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["breaks"] >= 1
    assert v["gate_signal"] < 1.0


def test_aggregate_none_criteria_no_crash():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = None
    v = rc.aggregate_verdict(spec, [])
    assert v["intent_completeness"] == "0/0"
    assert v["breaks"] == 0

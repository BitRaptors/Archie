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
    # 1 extra_unmet (no criterion_id) → unmet=1, met=3-1=2, unknown=0 (silence=met)
    assert v["breaks"] == 2 and v["conflicts"] == 0
    # 2 breaks, 0 conflicts, 0 drift → gate_signal = 1.0 - min(1.0, 0.5) = 0.5
    assert v["gate_signal"] == 0.5
    assert "unknown" in v
    assert v["unknown"] == 0
    assert v["intent_completeness"] == "2/3"


def test_aggregate_dedups_unmet_by_criterion():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}, {"id": "ac3"}]
    confirmed = [
        {"kind": "intent_unmet", "criterion_id": "ac2"},
        {"kind": "intent_partial", "criterion_id": "ac2"},  # same criterion, must not double-count
    ]
    v = rc.aggregate_verdict(spec, confirmed)
    # ac2 is unmet (deduped to 1); ac1+ac3 are silent → met (silence=met) → met=2, unknown=0
    assert v["intent_completeness"] == "2/3"
    assert v["unknown"] == 0


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


def test_aggregate_reports_unknown_criteria():
    spec = it.normalize("", source="sync", ticket_ids=[])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}, {"id": "ac3"}]
    confirmed = [{"kind": "intent_unmet", "criterion_id": "ac1"}]   # only 1 of 3 flagged unmet
    v = rc.aggregate_verdict(spec, confirmed)
    # silence=met: ac2+ac3 not flagged → counted met; ac1 unmet → met=2, unknown=0
    assert v["unknown"] == 0 and v["intent_completeness"] == "2/3"


def test_low_confidence_break_is_a_possible_issue_not_a_break():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}]
    confirmed = [
        {"kind": "behavioral_break", "problem_statement": "null-safety", "confidence": 0.4},
        {"kind": "behavioral_break", "problem_statement": "real bug", "confidence": 0.9},
        {"kind": "conformance_break", "problem_statement": "no-conf → stays a break"},  # no confidence
    ]
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["breaks"] == 2            # the 0.9 one + the no-confidence one
    assert v["possible_issues"] == 1   # the 0.4 one


def test_advisory_predicate():
    assert rc.is_advisory_finding({"confidence": 0.3}) is True
    assert rc.is_advisory_finding({"confidence": 0.9}) is False
    assert rc.is_advisory_finding({}) is False           # missing conf is NOT a downgrade

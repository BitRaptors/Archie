import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent as it  # noqa: E402


def test_merge_specs_unions_criteria_and_dedups():
    a = {"source": "sync", "confidence": "high", "goals": ["G1"],
         "acceptance_criteria": [{"id": "x", "text": "Tenant scoped"}], "ticket_ids": ["ARCH-1"], "raw": "plan"}
    b = {"source": "pr_body", "confidence": "medium", "goals": ["G1", "G2"],
         "acceptance_criteria": [{"id": "y", "text": "tenant scoped"}, {"id": "z", "text": "Rate limited"}],
         "ticket_ids": [], "raw": "body"}
    m = it.merge_specs(a, b)
    texts = [c["text"] for c in m["acceptance_criteria"]]
    assert texts == ["Tenant scoped", "Rate limited"]          # dedup by normalized text, order preserved
    assert m["acceptance_criteria"][0]["id"] == "ac1"          # ids reindexed
    assert m["goals"] == ["G1", "G2"] and m["ticket_ids"] == ["ARCH-1"]
    assert m["source"] == "sync"                               # highest _RANK wins (sync outranks pr_body)
    assert "plan" in m["raw"] and "body" in m["raw"]


def test_merge_specs_no_clobber_populated_by_empty():
    populated = {"source": "sync", "acceptance_criteria": [{"id": "a", "text": "Keep me"}], "goals": [], "raw": ""}
    empty = {"source": "pr_body", "acceptance_criteria": [], "goals": [], "raw": ""}
    m = it.merge_specs(populated, empty)
    assert [c["text"] for c in m["acceptance_criteria"]] == ["Keep me"]


def test_merge_specs_all_empty_returns_inferred():
    m = it.merge_specs(None, None)
    assert m["source"] == "inferred" and m["acceptance_criteria"] == []


def test_load_committed_intent_missing_and_malformed(tmp_path):
    assert it.load_committed_intent(tmp_path) is None          # no file
    ad = tmp_path / ".archie"; ad.mkdir()
    (ad / "intent.json").write_text("{ not json")
    assert it.load_committed_intent(tmp_path) is None          # malformed -> None
    (ad / "intent.json").write_text('["a","b"]')
    assert it.load_committed_intent(tmp_path) is None          # non-dict -> None


def test_write_committed_intent_merges_and_roundtrips(tmp_path):
    it.write_committed_intent(tmp_path, {"source": "sync", "acceptance_criteria": [{"id": "a", "text": "First"}],
                                         "goals": [], "ticket_ids": [], "raw": "one"})
    it.write_committed_intent(tmp_path, {"source": "sync", "acceptance_criteria": [{"id": "b", "text": "Second"}],
                                         "goals": [], "ticket_ids": [], "raw": "two"})
    got = it.load_committed_intent(tmp_path)
    assert [c["text"] for c in got["acceptance_criteria"]] == ["First", "Second"]   # merged across writes


def test_merge_specs_bridges_singular_ticket_id():
    a = {"source": "sync", "acceptance_criteria": [], "goals": [], "ticket_id": "ARCH-9", "raw": ""}
    b = {"source": "pr_body", "acceptance_criteria": [], "goals": [], "ticket_ids": ["ARCH-10"], "raw": ""}
    m = it.merge_specs(a, b)
    assert "ARCH-9" in m["ticket_ids"] and "ARCH-10" in m["ticket_ids"]


def test_merge_specs_carries_non_goals():
    a = {"source": "sync", "acceptance_criteria": [], "goals": [], "non_goals": ["no schema change"], "raw": ""}
    b = {"source": "pr_body", "acceptance_criteria": [], "goals": [], "non_goals": [], "raw": ""}
    assert it.merge_specs(a, b).get("non_goals") == ["no schema change"]

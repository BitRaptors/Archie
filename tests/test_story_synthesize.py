import json
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import story_synthesize as ssyn  # noqa: E402


def test_gather_sources_from_events_and_ticket(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    (ad / "intent-events.jsonl").write_text(
        json.dumps({"kind": "user_turn", "text": "add a cost preview"}) + "\n"
        + json.dumps({"kind": "transition"}) + "\n"
        + json.dumps({"kind": "user_turn", "text": "total = steps × price"}) + "\n")
    (ad / "ticket.md").write_text("ARCH-1: cost preview endpoint")
    srcs = ssyn.gather_sources(tmp_path)
    kinds = [(s["src"], s["text"]) for s in srcs]
    assert ("plan", "add a cost preview") in kinds
    assert ("plan", "total = steps × price") in kinds
    assert ("ticket", "ARCH-1: cost preview endpoint") in kinds


def test_story_prompt_is_faithful_and_blind():
    p = ssyn.build_story_prompt([{"src": "plan", "text": "add a cost preview"}])
    assert "summar" in p.lower() and "supported by a source" in p.lower()
    assert "add a cost preview" in p
    # blindness: no diff/code words leaked in
    assert "diff --git" not in p


def test_parse_story_extracts_prose():
    assert ssyn.parse_story(json.dumps({"story": "We add a cost preview."})) == "We add a cost preview."
    assert ssyn.parse_story("garbage") == ""


def test_facts_prompt_demands_provenance():
    p = ssyn.build_facts_prompt("We add a cost preview.", [{"src": "plan", "text": "cost preview"}])
    assert "cite" in p.lower() and "from" in p.lower()
    assert "We add a cost preview." in p


def test_parse_facts():
    raw = json.dumps({"facts": [{"id": "f1", "text": "t", "from": {"src": "plan", "quote": "q"}}],
                      "non_goals": ["ng"]})
    got = ssyn.parse_facts(raw)
    assert got["facts"][0]["text"] == "t" and got["non_goals"] == ["ng"]
    assert ssyn.parse_facts("junk") == {"facts": [], "non_goals": []}


def test_validate_provenance_drops_invented_facts():
    sources = [{"src": "plan", "text": "the total must be the number of billable steps times the price"}]
    facts = [
        {"text": "total is number of billable steps times price",
         "from": {"src": "plan", "quote": "the total must be the number of billable steps times the price"}},
        {"text": "response includes a billable_step_count field",   # invented — no source
         "from": {"src": "plan", "quote": "billable_step_count field must be present"}},
    ]
    kept = ssyn.validate_provenance(facts, sources)
    assert len(kept) == 1
    assert kept[0]["id"] == "f1"
    assert "total" in kept[0]["text"]

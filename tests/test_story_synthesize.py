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

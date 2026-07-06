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


def test_validate_provenance_does_not_mutate_inputs():
    sources = [{"src": "plan", "text": "total is billable steps times price"}]
    original = {"text": "total billable steps price",
                "from": {"src": "plan", "quote": "total is billable steps times price"}}
    facts = [original]
    kept = ssyn.validate_provenance(facts, sources)
    assert kept[0]["id"] == "f1"          # survivor is re-id'd
    assert "id" not in original           # the caller's dict is untouched


import story_store as ss  # noqa: E402


def test_imprint_writes_versioned_story(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    (ad / "intent-events.jsonl").write_text(
        json.dumps({"kind": "user_turn", "text": "total is billable steps times price"}) + "\n")

    def fake_run(prompt, root, verifier, **kw):
        if "TASK STORY:" in prompt:   # facts pass (has "TASK STORY:" heading)
            return json.dumps({"facts": [{"text": "total = billable steps × price",
                "from": {"src": "plan", "quote": "total is billable steps times price"}}],
                "non_goals": []})
        return json.dumps({"story": "We add a cost preview."})   # story pass

    p = ssyn.imprint(tmp_path, "feature/x", "sess-1", "2026-07-06T091200", run=fake_run)
    assert p is not None and p.exists()
    got = ss.parse_story_file(p)
    assert got["story"] == "We add a cost preview."
    assert got["facts"][0]["id"] == "f1"
    assert got["meta"]["version"] == 1 and got["meta"]["session_id"] == "sess-1"


def test_imprint_returns_none_without_sources(tmp_path):
    (tmp_path / ".archie").mkdir()
    assert ssyn.imprint(tmp_path, "feature/x", "s", "2026-07-06T091200", run=lambda *a, **k: "") is None

import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import story_store as ss           # noqa: E402
import delivery_review as dr       # noqa: E402


def test_assemble_pr_intent_uses_story_facts(tmp_path, monkeypatch):
    ss.write_story(tmp_path, "feature/x", "s1", "2026-07-06T090000",
                   story="We add a cost preview.",
                   facts=[{"id": "f1", "text": "total from live steps",
                           "from": {"src": "plan", "quote": "live steps"}}],
                   non_goals=["apply cap"], version=1)
    monkeypatch.setenv("ARCHIE_BRANCH", "feature/x")
    spec = dr.assemble_pr_intent(tmp_path, {"title": "Cost preview", "body": ""}, {})
    texts = [c["text"] for c in spec["acceptance_criteria"]]
    assert "total from live steps" in texts
    assert spec["non_goals"] == ["apply cap"]
    assert spec["story"].startswith("We add a cost preview.")


def test_assemble_pr_intent_no_story_falls_back_to_pr_body(tmp_path):
    """When there is no story, PR title/body are resolved as before."""
    payload = '{"acceptance_criteria":[{"id":"t","text":"From body"}]}'
    spec = dr.assemble_pr_intent(tmp_path, {"head_ref": "b", "title": "Add export", "body": "tenant scoped"}, {},
                                 run=lambda *a, **k: payload)
    assert [c["text"] for c in spec["acceptance_criteria"]] == ["From body"]


def test_assemble_pr_intent_story_non_goals_preserved(tmp_path, monkeypatch):
    """non_goals from the story appear in the assembled spec."""
    ss.write_story(tmp_path, "main", "s2", "2026-07-06T100000",
                   story="Auth overhaul.",
                   facts=[{"id": "g1", "text": "tokens rotated", "from": None}],
                   non_goals=["no DB migration", "no UI changes"], version=1)
    monkeypatch.setenv("ARCHIE_BRANCH", "main")
    spec = dr.assemble_pr_intent(tmp_path, {"title": "Auth", "body": ""}, {})
    assert "no DB migration" in spec["non_goals"]
    assert "no UI changes" in spec["non_goals"]


def test_assemble_pr_intent_story_fields_in_spec(tmp_path, monkeypatch):
    """story string is present in the assembled spec."""
    ss.write_story(tmp_path, "feat/y", "s3", "2026-07-06T110000",
                   story="Cost guardrails for live steps.",
                   facts=[{"id": "h1", "text": "budget enforced", "from": None}],
                   non_goals=[], version=1)
    monkeypatch.setenv("ARCHIE_BRANCH", "feat/y")
    spec = dr.assemble_pr_intent(tmp_path, {"title": "Guardrails", "body": ""}, {})
    assert spec.get("story", "").startswith("Cost guardrails")

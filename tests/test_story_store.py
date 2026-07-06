import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import story_store as ss  # noqa: E402


def test_branch_slug_flattens_slashes_and_specials():
    assert ss.branch_slug("feature/run-cost-preview") == "feature-run-cost-preview"
    assert ss.branch_slug("bugfix/AB-12_x") == "bugfix-AB-12_x"
    assert ss.branch_slug("") == "detached"


def test_story_dir_is_under_archie_stories(tmp_path):
    d = ss.story_dir(tmp_path, "feature/x")
    assert d == tmp_path / ".archie" / "stories" / "feature-x"


def test_write_then_parse_round_trip(tmp_path):
    facts = [{"id": "f1", "text": "total = steps × price",
              "from": {"src": "plan", "quote": "the total must be steps × price"}, "kind": "constraint"}]
    p = ss.write_story(tmp_path, "feature/x", session_id="sess-1",
                       timestamp="2026-07-06T091200", story="We add a cost preview.\n\nIt is fresh.",
                       facts=facts, non_goals=["applying the cap"], supersedes=None, version=1)
    assert p.exists() and p.name == "2026-07-06T091200.md"
    got = ss.parse_story_file(p)
    assert got["story"].startswith("We add a cost preview.")
    assert got["facts"] == facts
    assert got["non_goals"] == ["applying the cap"]
    assert got["meta"]["branch"] == "feature/x" and got["meta"]["session_id"] == "sess-1"
    assert got["meta"]["version"] == 1


def test_parse_bad_file_returns_empty(tmp_path):
    bad = tmp_path / "x.md"
    bad.write_text("no fenced json here")
    assert ss.parse_story_file(bad) == {}

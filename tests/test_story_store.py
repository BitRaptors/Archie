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


def _w(tmp, ts, sess, ver, sup=None):
    return ss.write_story(tmp, "feature/x", session_id=sess, timestamp=ts,
                          story=f"story {ts}", facts=[], non_goals=[], supersedes=sup, version=ver)


def test_list_versions_sorted_oldest_first(tmp_path):
    _w(tmp_path, "2026-07-06T090000", "s1", 1)
    _w(tmp_path, "2026-07-06T100000", "s2", 2)
    names = [p.name for p in ss.list_versions(tmp_path, "feature/x")]
    assert names == ["2026-07-06T090000.md", "2026-07-06T100000.md"]


def test_current_story_session_scoped(tmp_path):
    _w(tmp_path, "2026-07-06T090000", "old-session", 1)
    _w(tmp_path, "2026-07-06T100000", "this-session", 2)
    # newest overall
    assert ss.current_story(tmp_path, "feature/x")["meta"]["imprinted_at"] == "2026-07-06T100000"
    # scoped to a session returns that session's newest, not a newer other-session one
    _w(tmp_path, "2026-07-06T110000", "other-session", 3)
    got = ss.current_story(tmp_path, "feature/x", session_id="this-session")
    assert got["meta"]["imprinted_at"] == "2026-07-06T100000"


def test_current_story_none_when_absent(tmp_path):
    assert ss.current_story(tmp_path, "feature/none") is None


def test_next_version_increments_and_supersedes(tmp_path):
    assert ss.next_version(tmp_path, "feature/x") == (1, None)
    _w(tmp_path, "2026-07-06T090000", "s1", 1)
    assert ss.next_version(tmp_path, "feature/x") == (2, "2026-07-06T090000")

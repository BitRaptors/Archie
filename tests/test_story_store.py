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

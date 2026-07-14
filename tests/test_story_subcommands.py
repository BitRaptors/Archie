import json
import subprocess
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import story_store as ss  # noqa: E402


def _run(root, *args):
    return subprocess.run([sys.executable, str(_STANDALONE / "sync.py"), *args, str(root)],
                          capture_output=True, text=True)


def test_story_command_prints_current(tmp_path):
    ss.write_story(tmp_path, "feature/x", "s1", "2026-07-06T090000",
                   story="We add a cost preview.", facts=[{"id": "f1", "text": "fresh compute",
                   "from": {"src": "plan", "quote": "fresh"}}], non_goals=[], version=1)
    # story reads the *current branch*; force it via env the command honors
    r = subprocess.run([sys.executable, str(_STANDALONE / "sync.py"), "story", str(tmp_path)],
                       capture_output=True, text=True, env={"ARCHIE_BRANCH": "feature/x", "PATH": ""})
    assert r.returncode == 0
    assert "We add a cost preview." in r.stdout and "f1" in r.stdout

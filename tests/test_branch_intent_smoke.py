import sys, json, subprocess
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent as it  # noqa: E402


def test_write_intent_cli_roundtrip(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"source": "sync", "goals": ["G"],
        "acceptance_criteria": [{"id": "a", "text": "Scoped"}], "ticket_ids": ["ARCH-9"], "raw": "plan"}))
    rc = subprocess.run(["python3", str(_STANDALONE / "sync.py"), "write-intent", str(tmp_path), str(spec)],
                        capture_output=True, text=True)
    assert rc.returncode == 0
    got = it.load_committed_intent(tmp_path)
    assert got["acceptance_criteria"][0]["text"] == "Scoped"


def test_sync_skill_has_intent_capture_step():
    skill = (Path(__file__).resolve().parent.parent / "archie" / "assets" / "workflow"
             / "sync" / "SKILL.md").read_text()
    assert "write-intent" in skill and ".archie/intent.json" in skill

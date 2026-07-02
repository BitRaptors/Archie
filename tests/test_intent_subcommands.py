import sys, json
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync  # noqa: E402


def _write_intent(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir(parents=True, exist_ok=True)
    (ad / "intent.json").write_text(json.dumps({"source": "sync", "confidence": "medium",
        "goals": ["G"], "acceptance_criteria": [{"id": "ac1", "text": "Scoped"}],
        "non_goals": [], "confirmed": False, "capture_points": 2}))


def test_show_intent_renders_criteria_and_provenance(tmp_path, capsys):
    _write_intent(tmp_path)
    assert sync.cmd_show_intent(tmp_path) == 0
    out = capsys.readouterr().out
    assert "Scoped" in out and "ac1" in out and "confirmed" in out.lower()


def test_confirm_intent_sets_flag(tmp_path):
    _write_intent(tmp_path)
    assert sync.cmd_confirm_intent(tmp_path) == 0
    assert json.loads((tmp_path / ".archie" / "intent.json").read_text())["confirmed"] is True


def test_capture_intent_appends_event(tmp_path):
    assert sync.cmd_capture_intent(tmp_path, "add rate limiting") == 0
    import intent_capture as ic
    assert any("rate limiting" in e.get("text", "") for e in ic.load_events(tmp_path))

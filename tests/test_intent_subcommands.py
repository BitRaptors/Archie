import sys, json
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync  # noqa: E402


def test_capture_intent_appends_event(tmp_path):
    assert sync.cmd_capture_intent(tmp_path, "add rate limiting") == 0
    import intent_capture as ic
    assert any("rate limiting" in e.get("text", "") for e in ic.load_events(tmp_path))

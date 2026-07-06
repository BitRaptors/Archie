from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "archie" / "assets" / "hook_scripts" / "stop.sh"


def test_stop_hook_launches_imprint_in_background_nonblocking():
    text = SCRIPT.read_text()
    assert "sync.py" in text and "imprint" in text
    # must be backgrounded so it never blocks the turn
    line = next(l for l in text.splitlines() if "imprint" in l and "sync.py" in l)
    assert line.rstrip().endswith("&"), f"imprint call must be backgrounded: {line!r}"
    # uses PROJECT_ROOT, not cwd
    assert "$PROJECT_ROOT/.archie/sync.py" in text

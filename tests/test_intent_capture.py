import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent_capture as ic  # noqa: E402


def test_record_user_turn_appends_verbatim(tmp_path):
    ic.record_user_turn(tmp_path, "Add tenant-scoped export")
    events = ic.load_events(tmp_path)
    assert len(events) == 1 and events[0]["kind"] == "user_turn"
    assert events[0]["text"] == "Add tenant-scoped export"


def test_note_edit_fires_transition_only_after_a_planning_turn(tmp_path):
    # edit with no prior user turn -> no transition
    assert ic.note_edit(tmp_path) is False
    ic.record_user_turn(tmp_path, "plan: add rate limiting")
    # first edit after the turn -> transition
    assert ic.note_edit(tmp_path) is True
    # a second edit with no new turn -> no transition (already implementing)
    assert ic.note_edit(tmp_path) is False
    # new planning turn, then edit -> transition again (multi-point)
    ic.record_user_turn(tmp_path, "re-plan: also audit-log")
    assert ic.note_edit(tmp_path) is True
    transitions = [e for e in ic.load_events(tmp_path) if e["kind"] == "transition"]
    assert len(transitions) == 2


def test_malformed_line_is_skipped(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    (ad / "intent-events.jsonl").write_text('{"kind":"user_turn","text":"ok"}\nnot json\n')
    assert [e["text"] for e in ic.load_events(tmp_path)] == ["ok"]


def test_slash_commands_are_not_captured(tmp_path):
    # slash-commands are tool invocations, not stated intent -> skipped
    ic.record_user_turn(tmp_path, "/archie-deep-scan")
    ic.record_user_turn(tmp_path, "/archie-sync")
    ic.record_user_turn(tmp_path, "   ")  # empty/whitespace also skipped
    ic.record_user_turn(tmp_path, "Add tenant-scoped export")
    texts = [e["text"] for e in ic.load_events(tmp_path)]
    assert texts == ["Add tenant-scoped export"]


def test_internal_spawn_marker_skips_capture(tmp_path, monkeypatch):
    # When ARCHIE_INTERNAL is set, the CLI entrypoint must record nothing —
    # those turns are Archie's own `claude -p` prompts firing the same hook.
    import subprocess
    monkeypatch.setenv("ARCHIE_INTERNAL", "1")
    subprocess.run(
        [sys.executable, str(_STANDALONE / "intent_capture.py"), "user-turn", str(tmp_path)],
        input="You are verifying a candidate architectural finding",
        text=True, check=True,
    )
    assert ic.load_events(tmp_path) == []

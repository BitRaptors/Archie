from pathlib import Path


def _hook(name):
    return (Path(__file__).resolve().parent.parent / "archie" / "assets" / "hook_scripts" / name).read_text()


def test_pre_turn_captures_user_intent():
    s = _hook("pre-turn.sh")
    assert "intent_capture.py" in s and "user-turn" in s


def test_pre_validate_marks_edit_transition():
    s = _hook("pre-validate.sh")
    assert "intent_capture.py" in s and "edit" in s


def test_sync_skill_no_longer_authors_criteria():
    skill = (Path(__file__).resolve().parent.parent / "archie" / "assets" / "workflow"
             / "sync" / "SKILL.md").read_text()
    # the old silent-authoring step is gone; replaced by synthesize/show
    assert "synthesize-intent" in skill and "show-intent" in skill
    assert "author `goals` and concrete" not in skill  # the old silent-author instruction removed

"""Regression tests for the hook-registration repair (SubscriberAgent incident).

Old installs wrote RELATIVE hook commands (`.claude/hooks/x.sh`), which break
with exit 127 the moment the session shell cd's out of the repo root — and
Claude Code treats that as non-blocking, so enforcement silently vanishes.
Matcher orders also changed across versions ('Edit|Write|MultiEdit' vs
'Write|Edit|MultiEdit'), and the old matcher-keyed dedup appended duplicates
instead of repairing. The upsert must dedup by SCRIPT NAME and rewrite the
command to the $CLAUDE_PROJECT_DIR-anchored form.
"""
import json
import sys
from pathlib import Path

_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import install_hooks as ih  # noqa: E402


def _poisoned_bucket():
    # Verbatim shape observed in SubscriberAgent's settings.local.json.
    return [
        {"matcher": "Edit|Write|MultiEdit",
         "hooks": [{"type": "command", "command": ".claude/hooks/pre-validate.sh"}]},
        {"matcher": "Bash",
         "hooks": [{"type": "command", "command": ".claude/hooks/pre-commit-review.sh"}]},
        {"matcher": "Write|Edit|MultiEdit",
         "hooks": [{"type": "command", "command": ".claude/hooks/pre-validate.sh"}]},
    ]


def test_upsert_repairs_stale_relative_and_duplicates():
    bucket = _poisoned_bucket()
    ih._add_hook(bucket, "Write|Edit|MultiEdit", "pre-validate.sh")
    cmds = [h["command"] for e in bucket for h in e["hooks"]]
    # exactly ONE pre-validate registration, absolute-anchored
    pv = [c for c in cmds if c.endswith("pre-validate.sh")]
    assert pv == ["$CLAUDE_PROJECT_DIR/.claude/hooks/pre-validate.sh"]
    # the unrelated Bash hook is untouched
    assert ".claude/hooks/pre-commit-review.sh" in cmds


def test_upsert_is_idempotent():
    bucket = []
    ih._add_hook(bucket, "Bash", "pre-commit-review.sh")
    ih._add_hook(bucket, "Bash", "pre-commit-review.sh")
    cmds = [h["command"] for e in bucket for h in e["hooks"]]
    assert cmds == ["$CLAUDE_PROJECT_DIR/.claude/hooks/pre-commit-review.sh"]


def test_upsert_does_not_match_lookalike_scripts():
    bucket = [{"matcher": "Bash",
               "hooks": [{"type": "command",
                          "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/my-pre-validate.sh"}]}]
    ih._add_hook(bucket, "Write|Edit|MultiEdit", "pre-validate.sh")
    cmds = [h["command"] for e in bucket for h in e["hooks"]]
    # the user's own similarly-named hook survives
    assert "$CLAUDE_PROJECT_DIR/.claude/hooks/my-pre-validate.sh" in cmds
    assert "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-validate.sh" in cmds


def test_install_repairs_poisoned_settings_end_to_end(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.local.json").write_text(json.dumps({
        "hooks": {"PreToolUse": _poisoned_bucket()},
        "permissions": {"allow": ["Bash(ls *)"]},
    }))
    ih.install(tmp_path)
    settings = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
    pre = settings["hooks"]["PreToolUse"]
    pv_cmds = [h["command"] for e in pre for h in e["hooks"]
               if h["command"].endswith("pre-validate.sh")]
    assert pv_cmds == ["$CLAUDE_PROJECT_DIR/.claude/hooks/pre-validate.sh"]
    pcr_cmds = [h["command"] for e in pre for h in e["hooks"]
                if h["command"].endswith("pre-commit-review.sh")]
    assert pcr_cmds == ["$CLAUDE_PROJECT_DIR/.claude/hooks/pre-commit-review.sh"]
    # no relative commands left anywhere in the bucket
    assert all(not h["command"].startswith(".claude/")
               for e in pre for h in e["hooks"])

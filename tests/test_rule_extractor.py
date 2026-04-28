"""Tests for archie.rules.extractor — save/load/promote/demote.

Note: `extract_rules()` was retired in v2.5.0 (Phase 1 of the richer-rules
plan). The deep-scan slash command pipeline never called it, and Step 6's
AI-synthesized rules cover placement+naming with full semantic content.
The remaining functions (save/load/promote/demote) are still used by the
`archie rules promote/demote` CLI commands.
"""

from __future__ import annotations

from pathlib import Path

from archie.rules.extractor import (
    save_rules,
    load_rules,
    promote_rule,
    demote_rule,
)


def test_save_and_load_rules(tmp_path: Path) -> None:
    rules = [
        {"id": "placement-1", "check": "file_placement", "severity": "warn", "allowed_dirs": ["src/api"]},
        {"id": "naming-1", "check": "naming", "severity": "warn", "pattern": "^[a-z][a-z0-9_]*$"},
    ]
    save_rules(tmp_path, rules)
    loaded = load_rules(tmp_path)
    assert loaded == rules


def test_promote_rule(tmp_path: Path) -> None:
    rules = [
        {"id": "placement-1", "check": "file_placement", "severity": "warn"},
    ]
    save_rules(tmp_path, rules)
    result = promote_rule(tmp_path, "placement-1")
    assert result is True
    loaded = load_rules(tmp_path)
    assert loaded[0]["severity"] == "error"


def test_demote_rule(tmp_path: Path) -> None:
    rules = [
        {"id": "placement-1", "check": "file_placement", "severity": "error"},
    ]
    save_rules(tmp_path, rules)
    result = demote_rule(tmp_path, "placement-1")
    assert result is True
    loaded = load_rules(tmp_path)
    assert loaded[0]["severity"] == "warn"


def test_promote_nonexistent_rule(tmp_path: Path) -> None:
    rules = [
        {"id": "placement-1", "check": "file_placement", "severity": "warn"},
    ]
    save_rules(tmp_path, rules)
    result = promote_rule(tmp_path, "nonexistent-99")
    assert result is False

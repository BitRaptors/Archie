"""Tests for the connector-driven install loop."""
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from archie.install import install  # noqa: E402


def test_claude_install_preserves_main_assets(tmp_path: Path) -> None:
    install(tmp_path, ["claude"])

    assert (tmp_path / ".claude" / "commands" / "archie-scan.md").exists()
    assert (tmp_path / ".claude" / "skills" / "archie-deep-scan" / "SKILL.md").exists()
    assert (tmp_path / ".claude" / "hooks" / "pre-validate.sh").exists()
    assert (tmp_path / ".archie" / "platform_rules.json").exists()
    assert (tmp_path / ".archie" / "viewer" / "package.json").exists()
    assert (tmp_path / ".archieignore").exists()
    assert (tmp_path / ".archiebulk").exists()


def test_claude_install_writes_settings_local_json(tmp_path: Path) -> None:
    install(tmp_path, ["claude"])

    settings_path = tmp_path / ".claude" / "settings.local.json"
    assert settings_path.exists()

    settings = json.loads(settings_path.read_text())
    assert "hooks" in settings
    assert "PreToolUse" in settings["hooks"]
    assert any(
        entry.get("matcher") == "Edit|Write|MultiEdit"
        for entry in settings["hooks"]["PreToolUse"]
    )

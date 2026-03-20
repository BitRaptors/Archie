"""Tests for archie.hooks.generator."""
from __future__ import annotations

import json
import stat


from archie.hooks.generator import generate_hooks, install_hooks


# -------------------------------------------------------------------
# 1. inject-context hook content
# -------------------------------------------------------------------
def test_generate_inject_context_hook():
    hooks = generate_hooks()
    script = hooks["inject-context.sh"]
    assert script.startswith("#!/")
    assert "rules.json" in script


# -------------------------------------------------------------------
# 2. pre-validate hook content
# -------------------------------------------------------------------
def test_generate_pre_validate_hook():
    hooks = generate_hooks()
    script = hooks["pre-validate.sh"]
    assert script.startswith("#!/")
    assert "exit 0" in script


# -------------------------------------------------------------------
# 3. All hooks are executable scripts (shebang)
# -------------------------------------------------------------------
def test_hooks_are_executable_scripts():
    hooks = generate_hooks()
    for name, content in hooks.items():
        assert content.startswith("#!/"), f"{name} missing shebang"


# -------------------------------------------------------------------
# 4. install_hooks creates files that are executable
# -------------------------------------------------------------------
def test_install_hooks_creates_files(tmp_path):
    install_hooks(tmp_path)

    inject = tmp_path / ".claude" / "hooks" / "inject-context.sh"
    validate = tmp_path / ".claude" / "hooks" / "pre-validate.sh"

    assert inject.exists()
    assert validate.exists()

    # Check executable bit
    assert inject.stat().st_mode & stat.S_IXUSR
    assert validate.stat().st_mode & stat.S_IXUSR


# -------------------------------------------------------------------
# 5. install_hooks creates settings.local.json with hooks key
# -------------------------------------------------------------------
def test_install_hooks_creates_settings(tmp_path):
    install_hooks(tmp_path)

    settings_path = tmp_path / ".claude" / "settings.local.json"
    assert settings_path.exists()

    settings = json.loads(settings_path.read_text())
    assert "hooks" in settings
    assert "UserPromptSubmit" in settings["hooks"]
    assert "PreToolUse" in settings["hooks"]


# -------------------------------------------------------------------
# 6. install_hooks preserves existing settings
# -------------------------------------------------------------------
def test_install_hooks_preserves_existing_settings(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    settings_path = claude_dir / "settings.local.json"
    settings_path.write_text(json.dumps({"permissions": {"allow": ["Read"]}}))

    install_hooks(tmp_path)

    settings = json.loads(settings_path.read_text())
    assert "permissions" in settings, "Existing 'permissions' key was lost"
    assert settings["permissions"] == {"allow": ["Read"]}
    assert "hooks" in settings

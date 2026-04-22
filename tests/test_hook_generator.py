"""Tests for archie.hooks.generator."""
from __future__ import annotations

import json
import stat


from archie.hooks.generator import generate_hooks, install_git_hook, install_hooks
from archie.standalone.install_hooks import install as standalone_install


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


# -------------------------------------------------------------------
# 7. install_git_hook creates post-commit
# -------------------------------------------------------------------
def test_install_git_hook_creates_post_commit(tmp_path):
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    result = install_git_hook(tmp_path)

    assert result is True
    post_commit = tmp_path / ".git" / "hooks" / "post-commit"
    assert post_commit.exists()
    assert post_commit.stat().st_mode & stat.S_IXUSR
    content = post_commit.read_text()
    assert "archie refresh" in content
    assert content.startswith("#!/bin/sh\n")


# -------------------------------------------------------------------
# 8. install_git_hook is idempotent
# -------------------------------------------------------------------
def test_install_git_hook_idempotent(tmp_path):
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    install_git_hook(tmp_path)
    install_git_hook(tmp_path)

    content = (tmp_path / ".git" / "hooks" / "post-commit").read_text()
    assert content.count("archie refresh") == 1


# -------------------------------------------------------------------
# 9. install_git_hook preserves existing post-commit content
# -------------------------------------------------------------------
def test_install_git_hook_preserves_existing(tmp_path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True)
    existing = "#!/bin/sh\necho 'hello from existing hook'\n"
    (hooks_dir / "post-commit").write_text(existing)

    result = install_git_hook(tmp_path)

    assert result is True
    content = (hooks_dir / "post-commit").read_text()
    assert "echo 'hello from existing hook'" in content
    assert "archie refresh" in content


# -------------------------------------------------------------------
# 10. install_git_hook returns False when no .git dir
# -------------------------------------------------------------------
def test_install_git_hook_no_git_dir(tmp_path):
    result = install_git_hook(tmp_path)
    assert result is False


# -------------------------------------------------------------------
# 11. standalone install creates blueprint-nudge.sh
# -------------------------------------------------------------------
def test_standalone_install_creates_blueprint_nudge(tmp_path):
    standalone_install(tmp_path)

    nudge = tmp_path / ".claude" / "hooks" / "blueprint-nudge.sh"
    assert nudge.exists()
    assert nudge.stat().st_mode & stat.S_IXUSR
    content = nudge.read_text()
    assert "blueprint.json" in content
    assert "[Archie]" in content


# -------------------------------------------------------------------
# 12. standalone install registers blueprint-nudge on PreToolUse Glob|Grep
# -------------------------------------------------------------------
def test_standalone_install_registers_blueprint_nudge(tmp_path):
    standalone_install(tmp_path)

    settings_path = tmp_path / ".claude" / "settings.local.json"
    settings = json.loads(settings_path.read_text())

    pre_tool = settings["hooks"]["PreToolUse"]
    assert any(
        entry.get("matcher") == "Glob|Grep"
        and any(h.get("command") == ".claude/hooks/blueprint-nudge.sh" for h in entry.get("hooks", []))
        for entry in pre_tool
    )


# -------------------------------------------------------------------
# 13. standalone install creates post-lint.sh
# -------------------------------------------------------------------
def test_standalone_install_creates_post_lint_hook(tmp_path):
    standalone_install(tmp_path)

    post_lint = tmp_path / ".claude" / "hooks" / "post-lint.sh"
    assert post_lint.exists()
    assert post_lint.stat().st_mode & stat.S_IXUSR
    content = post_lint.read_text()
    assert "enforcement.json" in content
    assert "lint_gate.py" in content


# -------------------------------------------------------------------
# 14. standalone install registers post-lint on PostToolUse Write|Edit|MultiEdit
# -------------------------------------------------------------------
def test_standalone_install_registers_post_lint(tmp_path):
    standalone_install(tmp_path)

    settings = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
    post_tool = settings["hooks"].get("PostToolUse", [])
    assert any(
        entry.get("matcher") == "Write|Edit|MultiEdit"
        and any(h.get("command") == ".claude/hooks/post-lint.sh" for h in entry.get("hooks", []))
        for entry in post_tool
    ), "post-lint.sh not registered under PostToolUse Write|Edit|MultiEdit"


# -------------------------------------------------------------------
# 15. standalone install creates pre-turn.sh (Tier 4)
# -------------------------------------------------------------------
def test_standalone_install_creates_pre_turn_hook(tmp_path):
    standalone_install(tmp_path)

    pre_turn = tmp_path / ".claude" / "hooks" / "pre-turn.sh"
    assert pre_turn.exists()
    assert pre_turn.stat().st_mode & stat.S_IXUSR
    content = pre_turn.read_text()
    assert "archie_turn" in content
    assert "rm -f" in content


# -------------------------------------------------------------------
# 16. standalone install registers pre-turn on UserPromptSubmit
# -------------------------------------------------------------------
def test_standalone_install_registers_pre_turn(tmp_path):
    standalone_install(tmp_path)

    settings = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
    ups = settings["hooks"].get("UserPromptSubmit", [])
    assert any(
        any(h.get("command") == ".claude/hooks/pre-turn.sh" for h in entry.get("hooks", []))
        for entry in ups
    ), "pre-turn.sh not registered under UserPromptSubmit"

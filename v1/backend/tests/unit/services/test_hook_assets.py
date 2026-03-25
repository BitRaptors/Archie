"""Tests for hook_assets module — pure data tests against static content."""
import json

from application.services.hook_assets import (
    HOOK_SCRIPTS,
    HOOKS_SETTINGS,
    SKILL_FILES,
    get_archie_files,
    get_hook_files,
)


# ── HOOK_SCRIPTS ──────────────────────────────────────────────────────────────


class TestHookScripts:

    def test_has_two_entries(self):
        assert len(HOOK_SCRIPTS) == 2

    def test_paths_under_claude_hooks(self):
        for path in HOOK_SCRIPTS:
            assert path.startswith(".claude/hooks/"), f"{path} not under .claude/hooks/"

    def test_scripts_start_with_shebang(self):
        for path, content in HOOK_SCRIPTS.items():
            assert content.startswith("#!/bin/bash"), f"{path} missing shebang"

    def test_stop_script_calls_smart_refresh(self):
        stop_script = HOOK_SCRIPTS[".claude/hooks/stop-review-and-refresh.sh"]
        assert "smart-refresh" in stop_script

    def test_staleness_check_references_archie(self):
        staleness = HOOK_SCRIPTS[".claude/hooks/check-architecture-staleness.sh"]
        assert ".archie" in staleness


# ── HOOKS_SETTINGS ────────────────────────────────────────────────────────────


class TestHooksSettings:

    def test_has_two_hook_types(self):
        hooks = HOOKS_SETTINGS["hooks"]
        assert "Stop" in hooks
        assert "SessionStart" in hooks
        assert len(hooks) == 2

    def test_stop_hook_timeout_30s(self):
        stop_hooks = HOOKS_SETTINGS["hooks"]["Stop"]
        timeout = stop_hooks[0]["hooks"][0]["timeout"]
        assert timeout == 30

    def test_session_start_timeout_10s(self):
        session_hooks = HOOKS_SETTINGS["hooks"]["SessionStart"]
        timeout = session_hooks[0]["hooks"][0]["timeout"]
        assert timeout == 10

    def test_all_hooks_are_command_type(self):
        for hook_type, entries in HOOKS_SETTINGS["hooks"].items():
            for entry in entries:
                for hook in entry["hooks"]:
                    assert hook["type"] == "command", f"{hook_type} hook is not command type"


# ── get_hook_files ────────────────────────────────────────────────────────────


class TestGetHookFiles:

    def test_returns_dict(self):
        result = get_hook_files()
        assert isinstance(result, dict)

    def test_includes_all_hook_scripts(self):
        result = get_hook_files()
        for path in HOOK_SCRIPTS:
            assert path in result

    def test_includes_settings_json(self):
        result = get_hook_files()
        assert ".claude/settings.json" in result

    def test_settings_json_is_valid_json(self):
        result = get_hook_files()
        parsed = json.loads(result[".claude/settings.json"])
        assert "hooks" in parsed

    def test_includes_skill_files(self):
        result = get_hook_files()
        # Skill files should be included if any exist
        for path in SKILL_FILES:
            assert path in result

    def test_total_file_count_at_least_3(self):
        """2 hook scripts + settings.json (no archie files without params)."""
        result = get_hook_files()
        assert len(result) >= 3

    def test_includes_archie_files_when_params_provided(self):
        result = get_hook_files(
            repo_id="test-repo",
            backend_url="http://localhost:8000",
            storage_path="/tmp/storage",
        )
        assert ".archie/config.json" in result
        assert ".archie/repo_id" in result

    def test_excludes_archie_files_without_params(self):
        result = get_hook_files()
        assert ".archie/config.json" not in result
        assert ".archie/repo_id" not in result


# ── get_archie_files ──────────────────────────────────────────────────────────


class TestGetArchieFiles:

    def test_returns_config_and_repo_id(self):
        result = get_archie_files("my-repo", "http://localhost:8000", "/tmp/storage")
        assert ".archie/config.json" in result
        assert ".archie/repo_id" in result

    def test_config_json_is_valid(self):
        result = get_archie_files("my-repo", "http://localhost:8000", "/tmp/storage")
        parsed = json.loads(result[".archie/config.json"])
        assert parsed["storage_path"] == "/tmp/storage"
        assert parsed["backend_url"] == "http://localhost:8000"

    def test_repo_id_contains_id(self):
        result = get_archie_files("my-repo", "http://localhost:8000", "/tmp/storage")
        assert result[".archie/repo_id"].strip() == "my-repo"

    def test_custom_backend_url(self):
        result = get_archie_files("r", "https://api.example.com", "/data")
        parsed = json.loads(result[".archie/config.json"])
        assert parsed["backend_url"] == "https://api.example.com"


# ── SKILL_FILES ───────────────────────────────────────────────────────────────


class TestSkillLoading:

    def test_skill_files_is_dict(self):
        assert isinstance(SKILL_FILES, dict)

    def test_skill_files_have_expected_keys(self):
        for key in SKILL_FILES:
            assert key.startswith(".claude/skills/")
            assert key.endswith(".md")

    def test_skill_content_nonempty(self):
        for path, content in SKILL_FILES.items():
            assert len(content) > 0, f"{path} has empty content"

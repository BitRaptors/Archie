"""ClaudeConnector — installs Archie for Claude Code.

Writes:
  .claude/commands/archie-*.md        — slash command shims
  .claude/hooks/*.sh                  — hook scripts (copies from archie/assets/hook_scripts/)
  .claude/settings.local.json         — hook bindings + permissions

See docs/plans/2026-05-18-multi-agent-connector-architecture.md §9.1.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

from ..manifest import AgentDef, CommandDef, ConfigPatch, HookDef
from .base import Connector


ASSETS_ROOT = Path(os.environ.get("ARCHIE_ASSETS_ROOT") or (Path(__file__).resolve().parent.parent / "assets"))
HOOK_SCRIPTS_DIR = ASSETS_ROOT / "hook_scripts"


_EVENT_NAME_CLAUDE = {
    "pre-tool-use": "PreToolUse",
    "post-tool-use": "PostToolUse",
    "user-prompt-submit": "UserPromptSubmit",
    "stop": "Stop",
}


class ClaudeConnector(Connector):
    name = "claude"
    capabilities = frozenset({
        "commands",
        "hooks:pre-tool-use",
        "hooks:post-tool-use",
        "hooks:user-prompt-submit",
        "hooks:stop",
        "hooks:pre-commit",
        "parallel-agents",
    })

    def home_dir(self) -> Path:
        return Path.home() / ".claude"

    def install_command(self, project_root: Path, cmd: CommandDef) -> None:
        # Claude's slash commands at .claude/commands/<name>.md are thin shims
        # pointing at the canonical body (.archie/prompts/skill_archie_<name>.md
        # copied by the install loop). Same shape as Codex's SKILL.md, modulo
        # Claude's frontmatter conventions.
        dest = project_root / ".claude" / "commands" / f"{cmd.name}.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            f"---\ndescription: {cmd.description}\n---\n\n"
            f"Read `{cmd.body_path}` in full and execute the instructions as written. "
            f"The canonical body lives there so Claude Code, Codex, and Pi sessions all "
            f"follow the same workflow.\n"
        )

    def install_hook(self, project_root: Path, hook: HookDef) -> None:
        script_name = Path(hook.script_path).name
        src = HOOK_SCRIPTS_DIR / script_name
        if not src.exists():
            raise FileNotFoundError(
                f"Canonical hook script missing: {src}. "
                f"Stage 1 should have extracted it from install_hooks.py."
            )
        # Copy script to .claude/hooks/ (Claude's expected location).
        hook_dir = project_root / ".claude" / "hooks"
        hook_dir.mkdir(parents=True, exist_ok=True)
        dest = hook_dir / script_name
        shutil.copyfile(src, dest)
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Register in .claude/settings.local.json
        event_key = _EVENT_NAME_CLAUDE.get(hook.event)
        if event_key is None:
            return  # pre-commit handled separately by the install loop

        settings_path = project_root / ".claude" / "settings.local.json"
        settings: dict = {}
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text())
            except (json.JSONDecodeError, OSError):
                settings = {}

        hooks_root = settings.setdefault("hooks", {})
        bucket = hooks_root.setdefault(event_key, [])

        relative_cmd = f".claude/hooks/{script_name}"
        if not _hook_entry_present(bucket, hook.tool_match, relative_cmd):
            bucket.append({
                "matcher": hook.tool_match or "*",
                "hooks": [{"type": "command", "command": relative_cmd}],
            })

        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")


def _hook_entry_present(bucket: list, matcher: str | None, command: str) -> bool:
    needle = matcher or "*"
    for entry in bucket:
        if entry.get("matcher") != needle:
            continue
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                return True
    return False

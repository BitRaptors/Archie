"""CodexConnector — installs Archie for OpenAI Codex CLI.

Writes:
  .agents/skills/archie-*/SKILL.md  — slash-command shims (parent-walk discovered)
  .codex/hooks.json                  — hook registrations referencing .archie/hooks/*.sh
  .codex/agents/archie-*.toml        — named sub-agents for deep-scan fan-out
  ~/.codex/config.toml               — idempotent merge: project_doc_max_bytes + fallback_filenames

See docs/plans/2026-05-18-multi-agent-connector-architecture.md §9.2 and
docs/plans/HANDOFF_CODEX.md for the full implementation contract. Codex
hooks schema documented at https://developers.openai.com/codex/hooks.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from ..manifest import AgentDef, CommandDef, ConfigPatch, HookDef
from .base import Connector
from .claude import ASSETS_ROOT, HOOK_SCRIPTS_DIR


_EVENT_NAME_CODEX = {
    "pre-tool-use": "PreToolUse",
    "post-tool-use": "PostToolUse",
    "user-prompt-submit": "UserPromptSubmit",
    "stop": "Stop",
}


class CodexConnector(Connector):
    name = "codex"
    capabilities = frozenset({
        "commands",
        "hooks:pre-tool-use",
        "hooks:post-tool-use",
        "hooks:user-prompt-submit",
        "hooks:stop",
        "hooks:pre-commit",
        "agents",
        "parallel-agents",
        "config-patch",
    })

    def home_dir(self) -> Path:
        return Path.home() / ".codex"

    def install_command(self, project_root: Path, cmd: CommandDef) -> None:
        # Codex (and Pi via inheritance) parent-walk .agents/skills/<name>/SKILL.md
        # — verified by Q1 probe 2026-05-15. SKILL.md is a thin shim that points
        # at the canonical body installed at .archie/prompts/<name>.md.
        dest = project_root / ".agents" / "skills" / cmd.name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            f"---\nname: {cmd.name}\ndescription: {cmd.description}\n---\n\n"
            f"Read `{cmd.body_path}` in full and execute the instructions as written. "
            f"The canonical body lives there so Claude Code, Codex, and Pi sessions all "
            f"follow the same workflow.\n"
        )

    def install_hook(self, project_root: Path, hook: HookDef) -> None:
        script_name = Path(hook.script_path).name
        src = HOOK_SCRIPTS_DIR / script_name
        if not src.exists():
            raise FileNotFoundError(f"Canonical hook script missing: {src}")

        event_key = _EVENT_NAME_CODEX.get(hook.event)
        if event_key is None:
            return  # pre-commit handled by the universal git hook in install.py

        hooks_path = project_root / ".codex" / "hooks.json"
        config: dict = {"hooks": {}}
        if hooks_path.exists():
            try:
                config = json.loads(hooks_path.read_text())
                config.setdefault("hooks", {})
            except (json.JSONDecodeError, OSError):
                config = {"hooks": {}}

        # Use an absolute command path so the hook fires regardless of whether
        # the user started Codex from a subdirectory of the project.
        command_path = str((project_root / hook.script_path).resolve())
        bucket = config["hooks"].setdefault(event_key, [])
        if not _codex_entry_present(bucket, hook.tool_match, command_path):
            bucket.append({
                "matcher": hook.tool_match or "*",
                "hooks": [{"type": "command", "command": command_path, "timeout": 30}],
            })

        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        hooks_path.write_text(json.dumps(config, indent=2) + "\n")

    def install_agent(self, project_root: Path, agent: AgentDef) -> None:
        dest = project_root / ".codex" / "agents" / f"{agent.name}.toml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f'name = "{_toml_string(agent.name)}"',
            f'description = "{_toml_string(agent.description)}"',
            (
                'developer_instructions = """'
                f'Read and follow {agent.prompt_path} in full. '
                f'You are the {agent.name} sub-agent for Archie deep-scan."""'
            ),
            f'sandbox_mode = "{_toml_string(agent.sandbox_mode)}"',
        ]
        if agent.model:
            lines.append(f'model = "{_toml_string(agent.model)}"')
        dest.write_text("\n".join(lines) + "\n")

    def patch_config(self, patches: list[ConfigPatch]) -> None:
        cfg_path = self.home_dir() / "config.toml"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        existing = cfg_path.read_text() if cfg_path.exists() else ""
        updated = existing
        for patch in patches:
            updated = _toml_set_top_level(updated, patch.key, patch.value)
        if updated != existing:
            cfg_path.write_text(updated)


# ---------- helpers ----------


def _codex_entry_present(bucket: list, matcher: str | None, command: str) -> bool:
    needle = matcher or "*"
    for entry in bucket:
        if entry.get("matcher") != needle:
            continue
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                return True
    return False


def _toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _toml_serialize_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return f'"{_toml_string(value)}"'
    if isinstance(value, list):
        parts = [_toml_serialize_value(v) for v in value]
        return "[" + ", ".join(parts) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")


_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_\-]+)\s*=\s*(.*)$", re.MULTILINE)


def _toml_set_top_level(content: str, key: str, value: object) -> str:
    """Set a top-level TOML key in `content`, preserving any preceding table
    sections. For list-of-string values, union with existing entries if present.

    Constraints:
    - Only operates on top-level (pre-first-table) keys. If the key lives under
      a [section], this won't find it.
    - Does NOT handle inline-table value types or multi-line arrays.
    These are the keys Archie patches (project_doc_max_bytes, project_doc_fallback_filenames);
    both are top-level scalars/arrays per Codex docs.
    """
    # Compute the "header region" — everything before the first [section] line.
    header_end = len(content)
    for m in re.finditer(r"^\[", content, flags=re.MULTILINE):
        header_end = m.start()
        break
    header = content[:header_end]
    tail = content[header_end:]

    # Look for an existing assignment to `key` in the header.
    existing_match = None
    for m in _TOP_LEVEL_KEY_RE.finditer(header):
        if m.group(1) == key:
            existing_match = m
            break

    if existing_match is None:
        # Append a new line at end of header
        prefix = header
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        new_line = f"{key} = {_toml_serialize_value(value)}\n"
        return prefix + new_line + tail

    # Existing line: union arrays of strings; otherwise replace verbatim.
    raw_value = existing_match.group(2).strip()
    if isinstance(value, list) and raw_value.startswith("["):
        existing_items = _parse_inline_str_array(raw_value)
        merged = list(existing_items)
        for v in value:
            if isinstance(v, str) and v not in merged:
                merged.append(v)
        new_assignment = f"{key} = {_toml_serialize_value(merged)}"
    else:
        new_assignment = f"{key} = {_toml_serialize_value(value)}"

    start, end = existing_match.span()
    return content[:start] + new_assignment + content[end:]


_STR_ITEM_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _parse_inline_str_array(raw: str) -> list[str]:
    if not raw.startswith("[") or "]" not in raw:
        return []
    inner = raw[1: raw.rindex("]")]
    return [m.group(1).replace('\\"', '"').replace("\\\\", "\\") for m in _STR_ITEM_RE.finditer(inner)]

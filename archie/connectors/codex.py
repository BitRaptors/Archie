"""CodexConnector — installs Archie for OpenAI Codex CLI.

Writes:
  .agents/skills/archie-*/SKILL.md  — slash-command shims (parent-walk discovered)
  .codex/hooks.json                  — hook registrations referencing .archie/hooks/*.sh
  ~/.codex/config.toml               — idempotent merge: project_doc_max_bytes + fallback_filenames

See docs/plans/2026-05-18-multi-agent-connector-architecture.md §9.2 and
docs/plans/HANDOFF_CODEX.md for the full implementation contract. Codex
hooks schema documented at https://developers.openai.com/codex/hooks.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..manifest import CommandDef, ConfigPatch, HookDef
from .base import Connector
from .claude import HOOK_SCRIPTS_DIR


_EVENT_NAME_CODEX = {
    "pre-tool-use": "PreToolUse",
    "post-tool-use": "PostToolUse",
    "user-prompt-submit": "UserPromptSubmit",
    "stop": "Stop",
}

_MATCHER_NAME_CODEX = {
    "Edit|Write|MultiEdit": "^apply_patch$",
    "Bash": "^Bash$",
    "Glob|Grep": "^(Glob|Grep)$",
    "ExitPlanMode": "^ExitPlanMode$",
}


# Where the rendered workflow tree lands for Codex. Matches {{WORKFLOW_ROOT}}.
CODEX_WORKFLOW_ROOT = ".archie/workflow/codex"


# Render map for the templated canonical workflow. Codex token values + native
# block partials. See HANDOFF_codex_command_parity.md §4 for the locked slot
# set. Codex's strongest reasoning model is gpt-5; the analysis/verify tiers
# also run gpt-5 (Codex exposes a single frontier model).
_CODEX_RENDER_TOKENS = {
    "ANALYSIS_MODEL": "gpt-5",
    "REASONING_MODEL": "gpt-5",
    "VERIFY_MODEL": "gpt-5",
    "WORKFLOW_ROOT": CODEX_WORKFLOW_ROOT,
}

# Block partials carry only the CLI-specific *mechanism*. The worker model and
# the task/question text stay inline in the canonical workflow so the same
# partial is reusable at every dispatch site.
_CODEX_RENDER_PARTIALS = {
    # How to spawn N parallel analysis workers.
    "dispatch_parallel": (
        "Dispatch the whole wave as ONE batch with Codex's "
        "`spawn_agents_on_csv`. It is a blocking call: Codex spawns one "
        "worker per CSV row, runs them with bounded concurrency it manages "
        "itself, waits for EVERY worker to finish, then returns. Do NOT "
        "spawn workers individually and do NOT hand-roll your own chunking "
        "— a single `spawn_agents_on_csv` call processes every row no "
        "matter how many there are, and that blocking behavior is what "
        "keeps the wave loop self-driving in one run. Write a CSV at "
        "`/tmp/archie_dispatch_$PROJECT_NAME.csv` with one row per "
        "sub-agent — columns `agent` (a stable id) and `prompt` (that "
        "sub-agent's full prompt text). Call `spawn_agents_on_csv` with "
        "`id_column: agent`, `max_concurrency: 6`, and an `instruction` "
        "telling each worker: `Project root: $PWD. Read $PWD/AGENTS.md "
        "first if it exists, then carry out the task in the {prompt} "
        "column in full.` Each worker writes its own output file per the "
        "output contract below and calls `report_agent_job_result` exactly "
        "once. When `spawn_agents_on_csv` returns, the batch is complete "
        "— verify every output file exists; if any row errored, stop and "
        "report which one."
    ),
    # How to spawn one worker.
    "dispatch_single": (
        "Ask Codex to spawn one subagent for this task and wait for it to "
        "finish before continuing. Give it the project root, the exact prompt "
        "text or prompt-file path named in this workflow, and the one output "
        "file path it owns. After it finishes, verify the expected output file "
        "exists before continuing."
    ),
    # How a spawned worker must write its output file.
    "output_contract": (
        "1. Prefer `apply_patch` when writing the file path named above. If "
        "the target is an intermediate `/tmp/archie_*` artifact and your "
        "Codex build cannot create that path with `apply_patch`, use a direct "
        "shell file write only for that temp artifact.\n"
        "2. Write the raw output only — no markdown fences, no prose, unless "
        "the target format explicitly expects them.\n"
        "3. If you were launched through `spawn_agents_on_csv`, call "
        "`report_agent_job_result` exactly once after writing the file. "
        "Otherwise reply with exactly: \"Wrote <that file path>\".\n"
        "4. Do NOT paste the full output into the conversation."
    ),
    # How to ask the user an interactive question. The question text, header,
    # and options stay inline in the canonical workflow — only the asking
    # mechanism is slotted.
    "ask_user": (
        "Ask the user directly in the Codex conversation. Present the question "
        "text, then a numbered list of the options, explicitly say when "
        "multiple selections are allowed, accept comma-separated numbers or "
        "`all` when the workflow allows it, and wait for the user's reply "
        "before continuing"
    ),
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
        "parallel-agents",
        "config-patch",
    })

    render_tokens = _CODEX_RENDER_TOKENS
    render_partials = _CODEX_RENDER_PARTIALS

    def home_dir(self) -> Path:
        return Path.home() / ".codex"

    def install_command(self, project_root: Path, cmd: CommandDef) -> None:
        # Codex parent-walks .agents/skills/<name>/SKILL.md
        # — verified by Q1 probe 2026-05-15. SKILL.md is a thin shim that points
        # at the rendered canonical body under
        # .archie/workflow/codex/<command>/SKILL.md.
        dest = project_root / ".agents" / "skills" / cmd.name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        body_path = f"{CODEX_WORKFLOW_ROOT}/{cmd.body_path}"
        dest.write_text(
            f"---\nname: {cmd.name}\ndescription: {cmd.description}\n---\n\n"
            f"Read `{body_path}` in full and execute the instructions as written.\n"
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
        matcher = _codex_matcher(hook.tool_match)
        if not _codex_entry_present(bucket, matcher, command_path):
            entry = {
                "hooks": [{"type": "command", "command": command_path, "timeout": 30}],
            }
            if matcher is not None:
                entry["matcher"] = matcher
            bucket.append(entry)

        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        hooks_path.write_text(json.dumps(config, indent=2) + "\n")

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
    for entry in bucket:
        if entry.get("matcher") != matcher:
            continue
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                return True
    return False


def _codex_matcher(tool_match: str | None) -> str | None:
    if tool_match is None:
        return None
    return _MATCHER_NAME_CODEX.get(tool_match, tool_match)


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


_TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_\-]+)\s*=\s*(.*)$")


def _toml_set_top_level(content: str, key: str, value: object) -> str:
    """Set a top-level TOML key in `content`.

    The Codex installer only patches two top-level keys, but users may already
    have the same key nested in another section or formatted as a multi-line
    array. This setter keeps the file idempotent by:
    - updating an existing top-level assignment when present
    - moving a misplaced section-level assignment to the top level
    - unioning string-array values without duplicating entries
    """
    entries = _find_toml_assignments(content, key)
    top_level = next((e for e in entries if e["scope"] == "top"), None)
    section_level = next((e for e in entries if e["scope"] == "section"), None)
    existing = top_level or section_level

    new_value = value
    if existing and isinstance(value, list):
        existing_items = _parse_inline_str_array(existing["raw_value"].strip())
        merged = list(existing_items)
        for item in value:
            if item not in merged:
                merged.append(item)
        new_value = merged

    new_assignment = f"{key} = {_toml_serialize_value(new_value)}"
    if not existing:
        return _insert_top_level_assignment(content, new_assignment)

    replacement = new_assignment
    if existing["end"] > existing["start"] and content[existing["end"] - 1: existing["end"]] == "\n":
        replacement += "\n"
    updated = content[: existing["start"]] + replacement + content[existing["end"] :]
    if existing["scope"] == "top":
        return updated

    without_section_assignment = content[: existing["start"]] + content[existing["end"] :]
    return _insert_top_level_assignment(without_section_assignment, new_assignment)


_STR_ITEM_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _parse_inline_str_array(raw: str) -> list[str]:
    normalized = raw.strip()
    if not normalized.startswith("[") or "]" not in normalized:
        return []
    inner = normalized[1: normalized.rindex("]")]
    return [m.group(1).replace('\\"', '"').replace("\\\\", "\\") for m in _STR_ITEM_RE.finditer(inner)]


def _insert_top_level_assignment(content: str, assignment: str) -> str:
    section_match = re.search(r"^\[", content, flags=re.MULTILINE)
    insert_at = section_match.start() if section_match else len(content)
    head = content[:insert_at]
    tail = content[insert_at:]
    if head and not head.endswith("\n"):
        head += "\n"
    if head and not head.endswith("\n\n") and tail:
        head += "\n"
    return head + assignment + "\n" + tail


def _find_toml_assignments(content: str, key: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    pos = 0
    scope = "top"
    lines = content.splitlines(keepends=True)
    while pos < len(content) and lines:
        line = lines.pop(0)
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            scope = "section"
            pos += len(line)
            continue

        match = _TOP_LEVEL_KEY_RE.match(line)
        if not match or match.group(1) != key:
            pos += len(line)
            continue

        start = pos
        raw_value = match.group(2)
        end = pos + len(line)
        if raw_value.lstrip().startswith("[") and "]" not in raw_value:
            while lines:
                next_line = lines.pop(0)
                raw_value += next_line
                end += len(next_line)
                if "]" in next_line:
                    break
        entries.append({
            "scope": scope,
            "start": start,
            "end": end,
            "raw_value": raw_value,
        })
        pos = end
    return entries

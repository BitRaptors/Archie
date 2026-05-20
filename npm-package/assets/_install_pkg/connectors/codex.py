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
from pathlib import Path

from ..manifest import AgentDef, CommandDef, ConfigPatch, HookDef
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
        "Dispatch the sub-agents in parallel with `spawn_agents_on_csv`. Write "
        "a CSV at `/tmp/archie_dispatch_$PROJECT_NAME.csv` with one row per "
        "sub-agent — columns `agent` (a stable id) and `prompt` (that "
        "sub-agent's full prompt text). Call `spawn_agents_on_csv` with "
        "`id_column: agent`, `max_concurrency` equal to the number of rows, "
        "and an `instruction` that tells each worker: `Project root: $PWD. "
        "Read $PWD/AGENTS.md first if it exists, then carry out the task in "
        "the {prompt} column in full.` Each worker writes its own output file "
        "per the output contract below. After the batch completes, verify "
        "every worker's output file exists before continuing; if any worker "
        "failed, stop and report which one."
    ),
    # How to spawn one worker.
    "dispatch_single": (
        "Dispatch the sub-agent as a single Codex agent run. Use the matching "
        "named agent under `.codex/agents/` when one exists for this task; "
        "otherwise spawn one agent with `spawn_agents_on_csv` over a "
        "single-row CSV. Pass the full prompt text to the worker and seed "
        "`Project root: $PWD` plus `Read $PWD/AGENTS.md first if it exists.` "
        "The worker writes its output file per the output contract below."
    ),
    # How a spawned worker must write its output file.
    "output_contract": (
        "1. Write your COMPLETE output to the file path named above using a "
        "shell heredoc or the apply_patch tool.\n"
        "2. Write the raw output verbatim — the merge/finalize step handles JSON envelopes.\n"
        "3. After writing, report exactly: \"Wrote <that file path>\" via "
        "`report_agent_job_result` (or your final message when not in a batch).\n"
        "4. Do NOT print the output in your response body."
    ),
    # How to ask the user an interactive question.
    "ask_user": (
        "present the question text followed by a numbered list of the options "
        "above, then wait for the user to reply with their choice before "
        "continuing"
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
        "agents",
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

    def install_agent(self, project_root: Path, agent: AgentDef) -> None:
        dest = project_root / ".codex" / "agents" / f"{agent.name}.toml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        prompt_path = (project_root / _codex_agent_prompt_path(agent)).resolve()
        project_root_abs = project_root.resolve()
        lines = [
            f'name = "{_toml_string(agent.name)}"',
            f'description = "{_toml_string(agent.description)}"',
            (
                'developer_instructions = """'
                f'Project root: {project_root_abs}. '
                f'Read {project_root_abs / "AGENTS.md"} first if it exists, then read and follow {prompt_path} in full. '
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


def _codex_agent_prompt_path(agent: AgentDef) -> str:
    # Wave-1 / Wave-2 sub-agent prompts are rendered from the canonical
    # workflow templates into .archie/workflow/codex/_shared/. agent.prompt_path
    # is the sub-path relative to the per-CLI workflow root.
    return f"{CODEX_WORKFLOW_ROOT}/{agent.prompt_path}"


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

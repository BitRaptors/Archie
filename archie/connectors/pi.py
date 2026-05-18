"""PiConnector — installs Archie for Earendil Pi (pi.dev).

Writes:
  .agents/skills/archie-*/SKILL.md       — inherited from CodexConnector (same path/format)
  .pi/extensions/archie-hooks.ts          — TS extension wrapping canonical .archie/hooks/*.sh
  .pi/extensions/package.json             — extension manifest (open question — see HANDOFF_PI.md)

Pi capabilities are intentionally narrower than Claude/Codex:
  - No post-tool-use, user-prompt-submit, or stop events (Pi extension API ceiling)
  - No parallel sub-agents (Pi explicitly has none — README states "No sub-agents")
  - No config-patch (no required Pi config patches)

See docs/plans/2026-05-18-multi-agent-connector-architecture.md §9.3, §10
and docs/plans/HANDOFF_PI.md for the full contract.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from ..manifest import HookDef
from .codex import CodexConnector
from .claude import ASSETS_ROOT, HOOK_SCRIPTS_DIR

PI_EXTENSION_DIR = ASSETS_ROOT / "pi_extension"


class PiConnector(CodexConnector):
    name = "pi"
    capabilities = frozenset({
        "commands",
        "hooks:pre-tool-use",
        "hooks:pre-commit",
    })

    def __init__(self) -> None:
        self._pending_hooks: list[HookDef] = []

    def home_dir(self) -> Path:
        return Path.home() / ".pi" / "agent"

    def install_hook(self, project_root: Path, hook: HookDef) -> None:
        if not self.supports_event(hook.event):
            return
        self._pending_hooks.append(hook)

    def install_agent(self, project_root, agent) -> None:
        return  # Pi has no sub-agents

    def patch_config(self, patches) -> None:
        return  # Pi has no required config patches

    def finalize(self, project_root: Path) -> None:
        if not self._pending_hooks:
            return
        template_path = PI_EXTENSION_DIR / "archie-hooks.ts.template"
        if not template_path.exists():
            raise FileNotFoundError(
                f"Pi TS extension template missing: {template_path}"
            )
        hooks_json = json.dumps(
            [asdict(h) for h in self._pending_hooks],
            indent=2,
        )
        rendered = template_path.read_text().replace("{{HOOKS_JSON}}", hooks_json)
        dest = project_root / ".pi" / "extensions" / "archie-hooks.ts"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered)
        # Ship a minimal package.json alongside. Pi may resolve
        # @earendil-works/pi-coding-agent from its global install, in which case
        # this is informational; if it requires a local node_modules, the user
        # runs `npm install` inside .pi/extensions/.
        pkg_src = PI_EXTENSION_DIR / "package.json"
        if pkg_src.exists():
            shutil.copy(pkg_src, dest.parent / "package.json")

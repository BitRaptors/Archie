"""PiConnector — installs Archie commands and pre-tool hooks for Pi."""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from ..manifest import HookDef
from .codex import CodexConnector
from .claude import ASSETS_ROOT

PI_EXTENSION_DIR = ASSETS_ROOT / "pi_extension"


class PiConnector(CodexConnector):
    name = "pi"
    capabilities = frozenset({
        "commands",
        "hooks:pre-tool-use",
        "hooks:post-tool-use",
        "hooks:user-prompt-submit",
        "hooks:pre-commit",
    })

    def __init__(self) -> None:
        self._pending_hooks: list[HookDef] = []

    def home_dir(self) -> Path:
        return Path.home() / ".pi" / "agent"

    def install_command(self, project_root: Path, cmd) -> None:
        dest = project_root / ".agents" / "skills" / cmd.name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        body_path = _pi_command_body_path(cmd)
        dest.write_text(
            f"---\nname: {cmd.name}\ndescription: {cmd.description}\n---\n\n"
            f"Read `{body_path}` in full and execute the instructions as written. "
            f"The canonical body lives there so Claude Code, Codex, and Pi sessions all "
            f"follow the same workflow.\n"
        )

    def install_hook(self, project_root: Path, hook: HookDef) -> None:
        if self.supports_event(hook.event):
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
            raise FileNotFoundError(f"Pi TS extension template missing: {template_path}")
        hook_defs = []
        for hook in self._pending_hooks:
            item = asdict(hook)
            item["script_path"] = str((project_root / hook.script_path).resolve())
            hook_defs.append(item)
        rendered = template_path.read_text().replace("{{HOOKS_JSON}}", json.dumps(hook_defs, indent=2))
        dest = project_root / ".pi" / "extensions" / "archie-hooks.ts"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered)
        pkg_src = PI_EXTENSION_DIR / "package.json"
        if pkg_src.exists():
            shutil.copy(pkg_src, dest.parent / "package.json")


def _pi_command_body_path(cmd) -> str:
    pi_body = ASSETS_ROOT / "prompts" / "pi" / f"skill_{cmd.name.replace('-', '_')}.md"
    return f".archie/prompts/pi/{pi_body.name}" if pi_body.exists() else cmd.body_path

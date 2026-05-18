# Multi-Agent Connector Architecture — Implementation Spec

**Date:** 2026-05-18
**Branch:** `feature/agent_connectors` (cut from `main`; archived predecessor at tag `archive/feature-codex-support-2026-05-15`)
**Status:** **Approved — this document is the spec.** Anything implementation-related not covered here is open for the implementing agent to decide. Anything covered here is a settled decision unless explicitly marked "open".
**Authors:** Gabor (founder) + Claude (Anthropic). Probes run against Codex CLI 0.130.0 and Pi 0.74.0.

---

## 1. Context

Archie ships as a Claude Code-only tool today. Slash commands live in `.claude/commands/`, hooks live in `.claude/settings.json` referencing scripts in `.claude/hooks/`, and the install flow assumes Claude. We're adding first-class support for OpenAI Codex CLI and Earendil Pi as **peers** to Claude, not replacements.

The constraint is hard and load-bearing: **minimize CLI-specific code; share everything possible; ship feature parity where each CLI's surface allows.**

## 2. Goals & non-goals

**Goals**
- Three CLIs (Claude Code, Codex, Pi) all read identical Archie outputs.
- Connector code is bounded: each CLI has exactly one file under `archie/connectors/<name>.py`.
- The shared layer (`archie/assets/`, `archie/standalone/*.py`, manifest, prompts, hook scripts) doesn't grow when we add a CLI.
- Adding a 4th CLI = one new file under `archie/connectors/` + (optionally) one new template under `archie/assets/`.
- Pi gets full feature parity to the extent its extension API allows. Where Pi's API has hard ceilings, those drops are explicit and documented.

**Non-goals**
- Refactoring analysis logic (`archie/standalone/scanner.py`, `renderer.py`, `validate.py`, `intent_layer.py`).
- Building a runtime abstraction layer over the three CLIs. We just emit files; CLIs run themselves.
- Forward-compat scaffolding for hypothetical 4th-5th CLIs. The interface naturally extends; no need to over-design.
- Per-CLI duplicated SKILL bodies, hook scripts, or prompts.

## 3. Design principles (load-bearing)

1. **Strict separation via the `Connector` interface.** All CLI-specific code lives in one file per CLI under `archie/connectors/`. Nothing else in the codebase imports `pi` or `codex` names.
2. **No code or prompt duplication.** Each prompt, hook script, agent definition, and extension template lives once in `archie/assets/`. Connectors emit thin **shims** that reference them via path at runtime.
3. **Capabilities are explicit and per-event.** Connectors declare `capabilities: frozenset[str]` listing exactly what they support (`hooks:pre-tool-use`, `agents`, `config-patch`, etc.). The install loop respects this declaration. Drops are visible, not hidden.
4. **Feature parity where the CLI's surface allows; graceful degradation otherwise.** No CLI's API ceiling dictates the architecture; each one gets as close to Claude's behavior as its API permits, and explicit `capabilities` makes the ceiling visible.

## 4. Runtime model — install-time vs runtime

This is the most-asked clarification. Both phases are independent.

**Install time (Python install loop, runs once when user does `npx @bitraptors/archie .`):**
- Auto-detects `~/.claude/`, `~/.codex/`, `~/.pi/agent/`.
- For each detected CLI, calls its connector's `install_command`, `install_hook`, `install_agent`, `patch_config`, `finalize` as appropriate.
- Writes files under `.archie/`, `.claude/`, `.agents/skills/`, `.codex/`, `.pi/extensions/`.
- After install completes, Python connectors are **dormant**. They never run again until the next install/update.

**Runtime (each CLI runs independently, ignoring the others):**
- Claude reads `.claude/commands/archie-*.md` (5-line pointer) → follows the pointed-to body in `.archie/prompts/`. Claude's hooks (`.claude/settings.json`) reference `.archie/hooks/*.sh`.
- Codex parent-walks `.agents/skills/` → finds `archie-*/SKILL.md` (5-line pointer) → same body file. Codex hooks (`.codex/hooks.json`) reference the same `.archie/hooks/*.sh`. Codex agents (`.codex/agents/*.toml`) reference Wave-1/Wave-2 prompts.
- Pi parent-walks `.agents/skills/` → finds the same SKILL.md → same body file. Pi loads `.pi/extensions/archie-hooks.ts`, which shells out to the same `.archie/hooks/*.sh`.

Three CLIs, one shared body. Each CLI reads only its native idiom. No CLI knows the others exist.

## 5. Directory layout

```
archie/                                  ← Python package, canonical source of truth
  manifest.py                            ← CommandDef, HookDef, ConfigPatch, AgentDef dataclasses
  manifest_data.py                       ← Single source: all commands, hooks, patches, agents

  assets/                                ← Canonical bodies that get copied / referenced verbatim
    prompts/                             ← SKILL bodies + sub-agent prompts
      skill_archie_scan.md
      skill_archie_deep_scan.md
      skill_archie_intent_layer.md
      skill_archie_viewer.md
      skill_archie_share.md
      wave1_structure.md
      wave1_patterns.md
      wave1_technology.md
      wave1_ui.md
      wave2_reasoning.md
    hook_scripts/                        ← Canonical shell scripts (one per hook event)
      pre-validate.sh
      pre-turn.sh
      pre-commit-review.sh
      blueprint-nudge.sh
      post-plan-review.sh
      post-lint.sh
    pi_extension/                        ← Pi TS extension source
      archie-hooks.ts.template
      package.json                       ← if Pi expects extension manifest
    codex_agents/                        ← Codex named agent TOML templates
      archie-wave1-structure.toml.template
      archie-wave1-patterns.toml.template
      archie-wave1-technology.toml.template
      archie-wave1-ui.toml.template
      archie-wave2-reasoning.toml.template

  connectors/
    __init__.py                          ← ALL_CONNECTORS registry
    base.py                              ← Connector ABC + capability vocabulary
    claude.py                            ← ClaudeConnector
    codex.py                             ← CodexConnector
    pi.py                                ← PiConnector (inherits from CodexConnector)

  install.py                             ← Install loop entry point

  standalone/                            ← UNCHANGED: existing analysis scripts
    scanner.py, renderer.py, validate.py, intent_layer.py, install_hooks.py
    align_check.py, arch_review.py, ...

  hooks/                                 ← UNCHANGED: existing Python module for hook enforcement logic
    enforcement.py, generator.py        (this is logic, distinct from the shell scripts in assets/hook_scripts/)

  cli/, coordinator/, engine/,           ← UNCHANGED
  renderer/, rules/, schema/

docs/plans/
  2026-05-18-multi-agent-connector-architecture.md    ← THIS DOCUMENT

npm-package/
  bin/archie.mjs                         ← Node entry, spawns `python3 -m archie.install`
  assets/                                ← Verbatim copy of archie/assets/* (verified by scripts/verify_sync.py)

scripts/
  verify_sync.py                         ← Sync checks (extended to cover the new layout)
```

**Naming note:** the directory is `archie/assets/hook_scripts/` (not `archie/assets/hooks/`) because `archie/hooks/` is an existing Python module with enforcement logic. The `hook_scripts/` name keeps the canonical shell scripts distinct from the Python module.

## 6. Data model

```python
# archie/manifest.py
from dataclasses import dataclass
from typing import Literal, Optional

HookEvent = Literal[
    "pre-tool-use",          # before a tool fires (Claude PreToolUse / Codex PreToolUse / Pi tool_call)
    "post-tool-use",         # after a tool completes (Claude / Codex; Pi does not expose)
    "user-prompt-submit",    # before user prompt sent to model (Claude / Codex; Pi does not expose)
    "stop",                  # turn ends (Codex; Claude has its own variant; Pi does not expose)
    "pre-commit",            # git pre-commit (universal, runs outside any CLI)
]

@dataclass(frozen=True)
class CommandDef:
    name: str                # "archie-scan"
    description: str         # one-liner shown in slash menu / skill list
    body_path: str           # ".archie/prompts/skill_archie_scan.md"

@dataclass(frozen=True)
class HookDef:
    event: HookEvent
    tool_match: Optional[str]  # regex like "Edit|Write|MultiEdit"; None means "any tool"
    script_path: str           # ".archie/hooks/pre-validate.sh"
    blocking: bool

@dataclass(frozen=True)
class ConfigPatch:
    cli: str                 # "codex"
    key: str                 # "project_doc_max_bytes"
    value: object            # 131072

@dataclass(frozen=True)
class AgentDef:
    """Named sub-agent for deep-scan fan-out. Codex consumes these as TOMLs.
    Claude uses ad-hoc Agent tool (no materialization). Pi can't fan out at all."""
    name: str
    description: str
    prompt_path: str
    model: Optional[str] = None
    sandbox_mode: str = "read-only"
```

## 7. The Connector interface

```python
# archie/connectors/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from ..manifest import CommandDef, HookDef, ConfigPatch, AgentDef

class Connector(ABC):
    name: str
    capabilities: frozenset[str]   # see §8 for vocabulary

    @abstractmethod
    def home_dir(self) -> Path: ...

    @abstractmethod
    def install_command(self, project_root: Path, cmd: CommandDef) -> None: ...

    def install_hook(self, project_root: Path, hook: HookDef) -> None:
        raise NotImplementedError(f"{self.name} does not support hooks")

    def install_agent(self, project_root: Path, agent: AgentDef) -> None:
        return  # default no-op (Claude / Pi)

    def patch_config(self, patches: list[ConfigPatch]) -> None:
        return  # default no-op

    def finalize(self, project_root: Path) -> None:
        return  # default no-op (Pi overrides to emit the consolidated TS extension)

    def detect(self) -> bool:
        return self.home_dir().exists()

    def supports_event(self, event: str) -> bool:
        return f"hooks:{event}" in self.capabilities
```

## 8. Capability vocabulary

Strings used in each connector's `capabilities` set:

| Capability | Meaning |
|---|---|
| `commands` | Can install slash commands / skills (via `install_command`) |
| `hooks:pre-tool-use` | Can wire a `pre-tool-use` HookDef |
| `hooks:post-tool-use` | Can wire a `post-tool-use` HookDef |
| `hooks:user-prompt-submit` | Can wire a `user-prompt-submit` HookDef |
| `hooks:stop` | Can wire a `stop` HookDef |
| `hooks:pre-commit` | Can install git `pre-commit` hook (universal — every connector declares this) |
| `agents` | Can materialize `AgentDef` into a CLI-native artifact (Codex only) |
| `parallel-agents` | Runtime fan-out: the CLI's prompt can spawn parallel sub-agents at runtime (Claude via Agent tool; Codex via `spawn_agents_on_csv`; Pi: no) |
| `config-patch` | Can write to the user's CLI config file (Codex only) |

The install loop reads `capabilities` to decide whether to call each method. Capability claims must be honored — if a connector declares `hooks:stop`, its `install_hook` for that event must work.

## 9. Per-connector implementations

### 9.1 ClaudeConnector (file: `archie/connectors/claude.py`)

```python
capabilities = frozenset({
    "commands",
    "hooks:pre-tool-use", "hooks:post-tool-use", "hooks:user-prompt-submit",
    "hooks:pre-commit",
    "parallel-agents",
})
home_dir = Path.home() / ".claude"
```

**Responsibilities**
- `install_command`: writes `.claude/commands/<cmd.name>.md` as a 5-line shim:
  ```
  ---
  description: {cmd.description}
  ---

  Read and follow `{cmd.body_path}` exactly as written.
  ```
- `install_hook`: merges into `.claude/settings.json` `hooks.<EventName>` array. Event name mapping: `pre-tool-use` → `PreToolUse`, `post-tool-use` → `PostToolUse`, `user-prompt-submit` → `UserPromptSubmit`. `pre-commit` is handled by the universal git hook installer, not by ClaudeConnector.
- `install_agent`: not called (no `"agents"` capability) — Claude uses the Agent tool inline at runtime, via instructions in the deep-scan SKILL body.
- `patch_config`: not called (no `"config-patch"` capability).

**Owner:** Claude (i.e., the Anthropic agent / human implementing the foundation). Migrates existing behavior from `archie/standalone/install_hooks.py`'s Claude branch.

### 9.2 CodexConnector (file: `archie/connectors/codex.py`)

```python
capabilities = frozenset({
    "commands",
    "hooks:pre-tool-use", "hooks:post-tool-use", "hooks:user-prompt-submit", "hooks:stop",
    "hooks:pre-commit",
    "agents", "parallel-agents",
    "config-patch",
})
home_dir = Path.home() / ".codex"
```

**Responsibilities**
- `install_command`: writes `.agents/skills/<cmd.name>/SKILL.md` with YAML frontmatter (`name`, `description`) + 1-line body pointer. **Path note:** `.agents/skills/` is parent-walked from cwd by both Codex AND Pi — same file serves both CLIs. PiConnector's `install_command` is idempotent here.
- `install_hook`: merges into `.codex/hooks.json` `hooks.<EventName>` array. Event name mapping: same as Claude plus `stop` → `Stop`. Hook payload schema is similar to Claude but the deny output uses `hookSpecificOutput.permissionDecision = "deny"` (vs Claude's `decision: "block"`). See Codex hooks doc at https://developers.openai.com/codex/hooks.
- `install_agent`: writes `.codex/agents/<agent.name>.toml` with TOML body:
  ```
  name = "{agent.name}"
  description = "{agent.description}"
  developer_instructions = """Read and follow {agent.prompt_path} in full."""
  sandbox_mode = "{agent.sandbox_mode}"
  model = "{agent.model}"        # only if set
  ```
- `patch_config`: idempotent TOML merge into `~/.codex/config.toml`. Patches are listed in `manifest_data.CONFIG_PATCHES`. Notable patches:
  - `project_doc_max_bytes = 131072` — raises the 32 KiB cap; needed because real Archie output already breaches 32 KiB on 6-deep folder paths.
  - `project_doc_fallback_filenames = ["CLAUDE.md"]` — adds `CLAUDE.md` to Codex's walk list so per-folder intent-layer files (which keep their existing `CLAUDE.md` filename) are read by Codex.

**Owner:** Codex agent (i.e., implementing engineer using Codex). Open questions for this agent are in §17.

### 9.3 PiConnector (file: `archie/connectors/pi.py`)

```python
class PiConnector(CodexConnector):
    capabilities = frozenset({
        "commands",
        "hooks:pre-tool-use",     # implemented via TS extension that wraps shell scripts
        "hooks:pre-commit",
        # NOT supported (Pi extension API ceiling):
        # - hooks:post-tool-use, hooks:user-prompt-submit, hooks:stop
        # - parallel-agents
        # - agents (no named sub-agent system in Pi)
        # - config-patch (no required Pi config patches)
    })
home_dir = Path.home() / ".pi" / "agent"
```

**Responsibilities**
- `install_command`: **inherited from CodexConnector** verbatim. Both CLIs read `.agents/skills/*/SKILL.md`. Writes are idempotent — whichever connector runs first wins; the second call writes the same content.
- `install_hook`: accumulates `HookDef`s into `self._pending_hooks` (does not write files yet). Only accepts events declared in `capabilities`; silently skips others (the install loop already filters via `supports_event`, so this is defense in depth).
- `finalize`: emits **one** consolidated `.pi/extensions/archie-hooks.ts` containing all pending hooks. The TS extension is a thin glue layer that shells out to `.archie/hooks/*.sh`. See §10 for the full TS template.
- `install_agent`: not called.
- `patch_config`: not called.

**Owner:** Pi agent (i.e., implementing engineer using Pi). Open questions for this agent are in §17.

## 10. The Pi TS extension (canonical, shared across all Pi installs)

**Template file:** `archie/assets/pi_extension/archie-hooks.ts.template`

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawnSync } from "node:child_process";

const HOOKS: Array<{
  event: string;
  tool_match: string | null;
  script_path: string;
  blocking: boolean;
}> = {{HOOKS_JSON}};

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    for (const h of HOOKS) {
      if (h.event !== "pre-tool-use") continue;
      if (h.tool_match && !new RegExp(h.tool_match).test(event.tool_name)) continue;

      const res = spawnSync("bash", [h.script_path], {
        input: JSON.stringify({
          tool_name: event.tool_name,
          tool_input: event.tool_input,
          cwd: ctx.cwd,
          session_id: ctx.session_id,
          hook_event_name: "PreToolUse",
        }),
        encoding: "utf8",
        cwd: ctx.cwd,
        timeout: 30_000,
      });

      if (h.blocking && (res.status === 2 || res.status === 1)) {
        return {
          decision: "deny",
          reason: res.stderr?.trim() || "Archie hook blocked this action.",
        };
      }
    }
  });
}
```

**Design notes**
- The extension's only logic is event routing. The actual validation lives in `.archie/hooks/*.sh` (which is shared with Claude and Codex).
- `{{HOOKS_JSON}}` is replaced at install time by `PiConnector.finalize` with the JSON-serialized list of accumulated HookDefs.
- The shell script reads the same JSON shape Claude/Codex hooks emit, so the script is dialect-agnostic.
- Exit code 2 → blocking deny (matches Claude/Codex behavior).
- If Pi's extension API later exposes more events (`post-tool-use`, `prompt-submit`, etc.), the template adds a handler; `PiConnector.capabilities` adds the event; nothing else changes.

## 11. Install loop

```python
# archie/install.py
from pathlib import Path
from .connectors import ALL_CONNECTORS
from .manifest_data import COMMANDS, HOOKS, CONFIG_PATCHES, AGENTS

def install(project_root: Path, requested: list[str] | None = None) -> None:
    selected = _resolve_targets(requested, ALL_CONNECTORS)
    if not selected:
        die("No supported CLI detected. Install one of: Claude Code, Codex, Pi.")

    _copy_canonical_assets(project_root)            # populates .archie/{prompts,hooks,scanner.py,...}
    _install_git_pre_commit(project_root)           # universal (all CLIs benefit)

    for conn in selected:
        for cmd in COMMANDS:
            conn.install_command(project_root, cmd)
        for hook in HOOKS:
            if conn.supports_event(hook.event):
                conn.install_hook(project_root, hook)
        if "agents" in conn.capabilities:
            for agent in AGENTS:
                conn.install_agent(project_root, agent)
        if "config-patch" in conn.capabilities:
            conn.patch_config([p for p in CONFIG_PATCHES if p.cli == conn.name])
        conn.finalize(project_root)
        print(f"installed for {conn.name}")
```

`_resolve_targets`, `_copy_canonical_assets`, `_install_git_pre_commit` are utility helpers in the same file. Target resolution: `auto` = detected CLIs; explicit list = use as-is; `all` = every registered connector regardless of detection.

## 12. Canonical assets — what to populate during Stage 1

Each file below has a Stage-1 task. Sources for the body content are listed.

### 12.1 Prompts (`archie/assets/prompts/`)

| File | Source | Notes |
|---|---|---|
| `skill_archie_scan.md` | extract body from current `.claude/commands/archie-scan.md` | Strip the Claude frontmatter; the body becomes shared. The frontmatter gets re-applied by the connector at install time. |
| `skill_archie_deep_scan.md` | extract from `.claude/commands/archie-deep-scan.md` | Body should be CLI-agnostic. Reference Wave-1/Wave-2 prompts via path. |
| `skill_archie_intent_layer.md` | extract from `.claude/commands/archie-intent-layer.md` | |
| `skill_archie_viewer.md` | extract from `.claude/commands/archie-viewer.md` | |
| `skill_archie_share.md` | extract from `.claude/commands/archie-share.md` | |
| `wave1_structure.md` | extract from inline deep-scan command (currently embedded) | Standalone prompt body. |
| `wave1_patterns.md` | same | |
| `wave1_technology.md` | same | |
| `wave1_ui.md` | same | |
| `wave2_reasoning.md` | same | |

**Cross-CLI body considerations:**
- The body should NOT reference Claude-specific concepts like "use the Agent tool" by name. Instead say "if parallel sub-agent fan-out is available in your environment, use it; otherwise run sequentially." Each CLI's runtime then picks the right primitive.
- The body should NOT reference `AskUserQuestion` (Claude-only). Replace with natural-language "ask the user X and wait for their answer."
- The body MAY reference `.archie/` paths — they're guaranteed to exist in any installed project.

### 12.2 Hook scripts (`archie/assets/hook_scripts/`)

| File | Source | Notes |
|---|---|---|
| `pre-validate.sh` | move from `.claude/hooks/pre-validate.sh` | Keep stdin JSON contract — already CLI-agnostic. |
| `pre-turn.sh` | move from `.claude/hooks/pre-turn.sh` | |
| `pre-commit-review.sh` | move from `.claude/hooks/pre-commit-review.sh` | |
| `blueprint-nudge.sh` | move from `.claude/hooks/blueprint-nudge.sh` | |
| `post-plan-review.sh` | move from `.claude/hooks/post-plan-review.sh` | |
| `post-lint.sh` | move from `.claude/hooks/post-lint.sh` | |

The scripts should accept stdin JSON with `tool_name`, `tool_input`, `cwd`, `session_id`, `hook_event_name` fields. They emit either nothing (allow) or exit code 2 + stderr message (block). This is the Claude contract today and Codex matches it. Pi's TS extension produces the same JSON shape when shelling out.

### 12.3 Pi TS extension (`archie/assets/pi_extension/`)

| File | Source | Notes |
|---|---|---|
| `archie-hooks.ts.template` | new (template provided in §10) | Verbatim from §10. `{{HOOKS_JSON}}` placeholder. |
| `package.json` | new (if Pi expects one) | **Open question** — see §17. May not be needed if Pi auto-resolves `@earendil-works/pi-coding-agent` from its global install. |

### 12.4 Codex agent TOMLs (`archie/assets/codex_agents/`)

| File | Source | Notes |
|---|---|---|
| `archie-wave1-structure.toml.template` | new | `developer_instructions` reads from `.archie/prompts/wave1_structure.md`. |
| `archie-wave1-patterns.toml.template` | new | |
| `archie-wave1-technology.toml.template` | new | |
| `archie-wave1-ui.toml.template` | new | |
| `archie-wave2-reasoning.toml.template` | new | `model = "opus"` (or whatever Opus-equivalent Codex exposes). |

`CodexConnector.install_agent` either reads these `.toml.template` files and substitutes `{{prompt_path}}` etc., or constructs the TOML inline from `AgentDef` fields. Either approach is acceptable; templates are cleaner if any TOML keys need to vary.

## 13. Feature parity matrix

| Capability | Claude | Codex | Pi |
|---|---|---|---|
| All 5 commands (scan, deep-scan, intent-layer, viewer, share) | ✅ | ✅ | ✅ |
| In-session pre-edit enforcement | ✅ PreToolUse Edit/Write | ✅ PreToolUse apply_patch | ✅ TS ext on tool_call |
| In-session pre-bash enforcement | ✅ | ✅ | ✅ TS ext |
| Blueprint nudge on Glob/Grep | ✅ | ✅ | ✅ TS ext |
| Post-plan-review (after ExitPlanMode) | ✅ | ✅ | ⚠️ no Pi equivalent (Pi has no plan mode) |
| Post-lint on Edit/Write | ✅ | ✅ | ⚠️ Pi extension API has no documented post-tool event |
| Pre-turn (UserPromptSubmit) | ✅ | ✅ | ⚠️ Pi extension API has no documented prompt-submit event |
| Git pre-commit gate | ✅ | ✅ | ✅ universal |
| Deep-scan parallel fan-out | ✅ Agent tool | ✅ spawn_agents_on_csv + named agent TOMLs | ❌ sequential (Pi has no sub-agents) |
| Per-folder context (intent layer) | ✅ | ✅ (config-patched) | ✅ |
| Root context file | CLAUDE.md (pointer) + AGENTS.md | AGENTS.md | AGENTS.md / CLAUDE.md |

⚠️ marks Pi-API hard ceilings. If Pi later exposes more events, `PiConnector.capabilities` adds them; no other code changes.

## 14. Migration roadmap (stages with E2E gates)

All stages happen on `feature/agent_connectors`. No stage is "shipped" until its gate passes.

### Stage 1 — Extract canonical assets (refactor only, no behavior change)
- Move `.claude/commands/archie-*.md` bodies → `archie/assets/prompts/skill_archie_*.md` (strip Claude frontmatter from each).
- Rewrite `.claude/commands/archie-*.md` as 5-line shims pointing at the prompts.
- Extract Wave-1/Wave-2 inline content from deep-scan → `archie/assets/prompts/wave1_*.md`, `wave2_reasoning.md`.
- Move `.claude/hooks/*.sh` → `archie/assets/hook_scripts/*.sh`; update `.claude/settings.json` paths.
- Extend `scripts/verify_sync.py` to verify all `body_path`/`script_path`/`prompt_path` references resolve.

**Gate 1:** `/archie-scan` + `/archie-deep-scan` from Claude on Archie repo produce byte-identical AGENTS.md + blueprint.json vs main.

**Owner:** Claude agent (foundation work).

### Stage 2 — Build the connector framework
- Write `archie/manifest.py`, `archie/manifest_data.py` (scaffolded in this commit).
- Write `archie/connectors/base.py` with `Connector` ABC + capability model (scaffolded in this commit).
- Write `archie/connectors/claude.py` — re-implements current Claude behavior via the interface. Migrates from `archie/standalone/install_hooks.py`'s Claude branch.
- Write `archie/install.py` (the loop).
- Modify `npm-package/bin/archie.mjs`: replace Claude-specific install with `python3 -m archie.install --target=auto`.

**Gate 2:** Fresh project. `npx @bitraptors/archie .` produces the same `.claude/commands/*.md` + `.claude/settings.json` content as Stage 1. Diff = zero. Existing Claude users see no behavior change on upgrade.

**Owner:** Claude agent (foundation work).

### Stage 3 — Codex connector (commands + hooks + agents + config patch)
- Write `archie/connectors/codex.py`.
- Write `archie/assets/codex_agents/*.toml.template` (5 named agents for Wave-1/Wave-2).
- Update `archie/assets/prompts/skill_archie_deep_scan.md` so the body adapts to the CLI: "if `spawn_agents_on_csv` is available, fan out via named agents; else run Wave-1 sequentially".
- Codex config patcher (idempotent TOML merge): see `manifest_data.CONFIG_PATCHES`.

**Gate 3:**
- Fresh project with both Claude + Codex installed. Installer writes both targets' shims.
- From Codex: `$archie-scan` runs end-to-end, produces same AGENTS.md as Claude.
- From Codex: `$archie-deep-scan` fans out 4 Wave-1 agents in parallel via `spawn_agents_on_csv`. Blueprint matches Claude's structurally.
- Codex `~/.codex/config.toml` shows the merged patch entries.
- A rule violation in Codex (e.g., editing a forbidden file) is blocked by the PreToolUse hook. **Validate in both `codex exec` mode AND interactive mode** — the earlier probe was inconclusive in exec mode and we want to know whether interactive-mode behavior differs.

**Owner:** Codex agent.

### Stage 4 — Pi connector v1 (commands only, no TS extension yet)
- Write `archie/connectors/pi.py` (inherits from CodexConnector for `install_command`).
- `capabilities = frozenset({"commands", "hooks:pre-commit"})` — git pre-commit only.
- Verify Pi discovers `.agents/skills/*/SKILL.md` end-to-end.

**Gate 4:**
- Fresh project with all 3 CLIs. Installer detects Pi, writes `.agents/skills/`, skips `.codex/hooks.json`, skips Pi extension.
- From Pi: `/skill:archie-scan` runs end-to-end. Same AGENTS.md output as Claude/Codex.
- From Pi: deep-scan runs Wave-1 sequentially. Document wall-clock vs Codex parallel. If sequential ≤ 3× slower, accept. If > 5×, escalate to Stage 5b (RPC parallel adapter spike).

**Owner:** Pi agent.

### Stage 5 — Pi connector v2 (TS extension for in-session enforcement)
- Write `archie/assets/pi_extension/archie-hooks.ts.template` (full template in §10).
- Write `archie/assets/pi_extension/package.json` if needed (open question — Pi agent confirms).
- Extend `PiConnector` with `install_hook` (accumulator) + `finalize` (emit consolidated TS).
- Expand `PiConnector.capabilities` to include `hooks:pre-tool-use`.
- Verify the TS extension loads in Pi sessions; may require `pi install` step (open question — Pi agent confirms).

**Gate 5:**
- In Pi, attempt an edit that violates a rule. The TS extension intercepts, runs `.archie/hooks/pre-validate.sh`, denies.
- Run `pi list` in a project with the extension installed; archie-hooks appears.
- Run an allowed edit; the extension allows it without significant latency (>50 ms overhead is a red flag).

**Owner:** Pi agent.

### Stage 6 — Telemetry consent (cross-agent)
- Rewrite `_shared/telemetry-consent.md` fragment as a model-driven natural-language prompt (no `AskUserQuestion`).
- Inject into all 5 SKILL bodies (or as a shared fragment they all reference).
- Verify consent flow in each CLI.

**Gate 6:** All 3 CLIs prompt for consent on first run. Consent persists in `~/.archie/telemetry-consent`. Subsequent runs skip the prompt.

**Owner:** Claude agent.

### Stage 7 — Installer hardening + auto-detect
- `archie.mjs --target=auto|claude|codex|pi|all`. Cherry-pick the `--target` flag scaffold from archived branch (`archive/feature-codex-support-2026-05-15`) as a starting point, refactor to delegate to Python install loop.
- Auto-detect inspects `~/.claude/`, `~/.codex/`, `~/.pi/agent/`.
- Test matrix: every subset of {Claude, Codex, Pi}.

**Gate 7:** Test matrix passes.

**Owner:** Claude agent.

### Stage 8 — Verify sync + tests
- Extend `scripts/verify_sync.py`:
  - Every `body_path`/`script_path`/`prompt_path` in `manifest_data` resolves.
  - `archie/assets/*` ↔ `npm-package/assets/*` in sync.
- Tests:
  - `tests/test_connector_contract.py` — each Connector's claimed capabilities work end-to-end against a tmpdir project.
  - `tests/test_install_matrix.py` — every target combination produces the right file set.
  - `tests/test_capability_coverage.py` — assert that every `HookDef` is honored by at least one connector.

**Gate 8:** CI green.

**Owner:** Claude agent.

### Stage 9 — Release
- README rewrite covering install/usage for all three CLIs.
- CHANGELOG entry.
- Version bump (3.0.0 — major because of internal refactor; existing Claude users see no behavior change).
- Migration note.

**Gate 9:** Tag, publish npm, smoke test from a clean machine for each CLI.

**Owner:** Claude agent + Gabor (final merge).

## 15. Asset migration map (current → new locations)

| Current path | New path | Stage |
|---|---|---|
| `.claude/commands/archie-scan.md` (body) | `archie/assets/prompts/skill_archie_scan.md` | 1 |
| `.claude/commands/archie-deep-scan.md` (body) | `archie/assets/prompts/skill_archie_deep_scan.md` + 5 Wave-1/2 prompt files | 1 |
| `.claude/commands/archie-intent-layer.md` (body) | `archie/assets/prompts/skill_archie_intent_layer.md` | 1 |
| `.claude/commands/archie-viewer.md` (body) | `archie/assets/prompts/skill_archie_viewer.md` | 1 |
| `.claude/commands/archie-share.md` (body) | `archie/assets/prompts/skill_archie_share.md` | 1 |
| `.claude/hooks/*.sh` | `archie/assets/hook_scripts/*.sh` | 1 |
| `archie/standalone/install_hooks.py` (Claude branch) | folded into `archie/connectors/claude.py` | 2 |
| `npm-package/assets/.claude/commands/*` | regenerated from `archie/assets/prompts/` at install time | 2 |
| `npm-package/assets/.claude/hooks/*` | mirrored from `archie/assets/hook_scripts/` (verify_sync.py enforces) | 1 |

## 16. Test plan

**Unit (per connector)**
- `test_claude_connector.py`: install_command/hook against a tmpdir → assert files exist with expected content.
- `test_codex_connector.py`: same + verify TOML config patch is idempotent (run twice, file unchanged).
- `test_pi_connector.py`: same + verify `finalize` emits the TS extension with the right `HOOKS_JSON`.

**Contract (capability claims hold)**
- For each connector, iterate declared capabilities; assert the corresponding install method runs without error against a tmpdir.
- Catches "I claimed `hooks:stop` but my install_hook errors on it."

**E2E (each Gate)**
- Stages 3/4/5 require real CLI invocations against a fixture project. BabyWeather.Android is the standard fixture for deep-scan E2E (per Gabor's memory).

## 17. Open questions (organized by owning agent)

Anything below is unresolved and requires the named agent's local knowledge.

### For the Codex agent

**Q-C1: Does `PreToolUse` fire on `apply_patch` in `codex exec` mode?**
The probe with a project-level `.codex/hooks.json` did not fire the hook in exec mode (likely an interactive-only trust gate, but not confirmed). Resolution: validate in Stage 3 in both interactive and exec sessions. If exec-mode bypasses hooks, document the limitation and accept it — interactive sessions are the primary use case.

**Q-C2: Does `spawn_agents_on_csv` inherit AGENTS.md and the parent's CWD?**
Codex docs are silent. Resolution: test in Stage 3. If sub-agents need explicit context bootstrapping, the deep-scan SKILL body needs to seed it (e.g., explicitly pass the project root in each CSV row).

**Q-C3: TOML config-patch idempotency.**
`~/.codex/config.toml` is user-owned. Our merge must (a) preserve all existing user keys, (b) not duplicate our keys on second run, (c) handle the case where `project_doc_fallback_filenames` already exists with user-set values (union, not replace). Resolution: implement and test in Stage 3.

**Q-C4: What's the right approval/sandbox config?**
Default Codex sandbox is `read-only` for `codex exec`. Our scan scripts need to write `.archie/scan.json` etc. Resolution: the Codex SKILL body should instruct the user to enable workspace-write OR the installer should set a project trust level. Decide in Stage 3.

### For the Pi agent

**Q-P1: Does Pi auto-discover `.pi/extensions/*.ts` or does the user need to run `pi install /path/to/extension`?**
The Pi README mentions extensions in `.pi/extensions/` but the install/load semantics aren't crystal clear from the docs. Resolution: test in Stage 5. If `pi install` is required, the installer prints the one-line instruction.

**Q-P2: Does Pi expose lifecycle events beyond `tool_call`?**
The docs example only shows `pi.on("tool_call", ...)`. If Pi also exposes `post-tool`, `prompt-submit`, `stop`, etc., we add them to `PiConnector.capabilities` and the TS template grows handlers. Resolution: read Pi's `ExtensionAPI` type definition (or the source at https://github.com/earendil-works/pi/tree/main/packages/coding-agent) and confirm.

**Q-P3: Does Pi resolve `@earendil-works/pi-coding-agent` from the global install or does the project need a local `node_modules`?**
Affects whether `archie/assets/pi_extension/package.json` is needed in the installed project. Resolution: test in Stage 5.

**Q-P4: Does `pi.on("tool_call", ...)` support async denials that the extension can return?**
Affects whether shell-out is synchronous (current template) or async. The template uses `spawnSync` for simplicity; if async is supported and reduces latency, switch. Resolution: test in Stage 5.

**Q-P5: Pi's sequential deep-scan acceptability.**
Measure Wave-1 sequential time on a real fixture (BabyWeather.Android). If acceptably slow (≤ 3× Codex parallel), ship. If too slow, spike on `pi --mode rpc` to spawn parallel Pi processes from a wrapper, as a v2 add. Resolution: time in Stage 4 before deciding.

### For Claude (foundation work)

**Q-A1: Does Claude Code natively discover `.agents/skills/`?**
If yes, ClaudeConnector could potentially write to the same path as Codex/Pi and skip `.claude/commands/` altogether — collapsing the connector even further. Resolution: probe in Stage 2.

**Q-A2: Should the universal `git/hooks/pre-commit` go into `.git/hooks/` or a `.archie/git_hooks/` location plus install instructions?**
Direct write to `.git/hooks/pre-commit` clobbers existing user hooks. Resolution: write to `.git/hooks/pre-commit.archie` and print an integration line ("add `.git/hooks/pre-commit.archie` to your `pre-commit` chain"). Same approach the archived branch's PR3 design used.

## 18. Handoff matrix

| Stage | Owner | Notes |
|---|---|---|
| 1. Extract canonical assets | Claude agent | Behavior-preserving refactor. |
| 2. Connector framework | Claude agent | Implements interface + ClaudeConnector. |
| 3. Codex connector | **Codex agent** | Resolves Q-C1..Q-C4 in the process. |
| 4. Pi connector v1 | **Pi agent** | Resolves Q-P5 in the process. |
| 5. Pi connector v2 (TS) | **Pi agent** | Resolves Q-P1..Q-P4 in the process. |
| 6. Telemetry consent | Claude agent | |
| 7. Installer auto-detect | Claude agent | Cherry-pick `--target` flag from archived branch. |
| 8. Verify sync + tests | Claude agent | |
| 9. Release | Claude agent + Gabor | Gabor merges. |

Stage ordering: 1 → 2 sequential. 3, 4 can run in parallel after 2. 5 after 4. 6, 7, 8 after 3+5. 9 last.

## 19. What we explicitly DON'T build

- Per-CLI duplicated SKILL bodies, hook scripts, or prompts.
- A runtime abstraction layer over CLIs.
- A YAML/JSON-to-code generator (manifest is plain Python dataclasses).
- Forward-compat scaffolding for hypothetical 4th-5th CLIs (the interface extends naturally).
- Pi-specific validation logic. Pi's TS extension is glue; rules live in Python (one source).

## 20. References

- Archived predecessor branch (cherry-pickable salvage): tag `archive/feature-codex-support-2026-05-15`
  - `archie/standalone/renderer.py` `--target` flag (useful for Stage 1)
  - `npm-package/bin/archie.mjs` `--target` flag + auto-detect (useful for Stage 7)
  - `scripts/verify_sync.py` extensions for prompt-reference resolution (useful for Stage 1)
  - Closed PR #37 (for historical context)
- Codex docs: https://developers.openai.com/codex/cli, https://developers.openai.com/codex/hooks, https://developers.openai.com/codex/skills, https://developers.openai.com/codex/subagents, https://developers.openai.com/codex/guides/agents-md
- Pi repo: https://github.com/earendil-works/pi/tree/main/packages/coding-agent
- Pi-as-SDK reference for runtime semantics: `~/DEV/gbr/craft-agents-oss/packages/pi-agent-server/`
- Probes run on this session: confirmed `.agents/skills/<name>/SKILL.md` is discovered by both Codex 0.130.0 and Pi 0.74.0 from the same path (Q1 ✅). Codex 32 KiB cap measured at 34,024 bytes on a real 6-deep Archie output (Q5 ⚠️ — config patch resolves it). Codex `PreToolUse` exec-mode firing inconclusive (Q-C1, escalated to Stage 3).

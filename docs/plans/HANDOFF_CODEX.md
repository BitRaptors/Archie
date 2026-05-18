# Handoff to the Codex agent — Archie CodexConnector

**Target branch:** `feature/agent_connectors`
**Your tasks:** Stage 3 (#14) in TaskList — `CodexConnector` (commands + hooks + agents + config patch).
**Design spec:** `docs/plans/2026-05-18-multi-agent-connector-architecture.md` — this is the contract. Read §9.2 (CodexConnector responsibilities), §17 (Q-C1..Q-C4 open questions), §14 Stage 3 (acceptance gate).

## What is already done

- Connector framework: `archie/connectors/base.py` (the ABC you implement), `archie/manifest.py`, `archie/manifest_data.py`.
- Install loop: `archie/install.py` — iterates `ALL_CONNECTORS`, calls each connector's methods. Just register yourself in `archie/connectors/__init__.py::ALL_CONNECTORS`.
- Canonical hook scripts (used by all 3 CLIs): `archie/assets/hook_scripts/*.sh`. Your `install_hook` must wire `.codex/hooks.json` entries that reference these scripts at their installed location (`<project>/.archie/hooks/<name>.sh`).
- ClaudeConnector reference implementation at `archie/connectors/claude.py` — same shape you're building.

## Your deliverables

### 1. `archie/connectors/codex.py`

Implement `CodexConnector(Connector)` with capabilities:

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

Methods:

- **`install_command(project_root, cmd)`** — write `.agents/skills/<cmd.name>/SKILL.md` with YAML frontmatter (`name`, `description`) and a one-line body that says "Read and follow `<cmd.body_path>` exactly as written."
- **`install_hook(project_root, hook)`** — idempotent merge into `<project>/.codex/hooks.json`. Event name map: `pre-tool-use` → `PreToolUse`, `post-tool-use` → `PostToolUse`, `user-prompt-submit` → `UserPromptSubmit`, `stop` → `Stop`. Each hook entry's `command` field points at `.archie/hooks/<basename>.sh` (the canonical script we already extracted). JSON shape per https://developers.openai.com/codex/hooks.
- **`install_agent(project_root, agent)`** — write `.codex/agents/<agent.name>.toml`. Template content:
  ```toml
  name = "<agent.name>"
  description = "<agent.description>"
  developer_instructions = """Read and follow <agent.prompt_path> in full."""
  sandbox_mode = "<agent.sandbox_mode>"
  model = "<agent.model>"   # only when set
  ```
  These 5 named agents are consumed at runtime by Codex's `spawn_agents_on_csv` for parallel Wave-1/Wave-2 fan-out in deep-scan.
- **`patch_config(patches)`** — idempotent TOML merge into `~/.codex/config.toml`. Patches come from `manifest_data.CONFIG_PATCHES`. Critical patches:
  - `project_doc_max_bytes = 131072` (default 32 KiB is too small — measured 34 KiB on real Archie output on a 6-deep path)
  - `project_doc_fallback_filenames = ["CLAUDE.md"]` (union with any existing user list — do NOT replace)

### 2. Register in `archie/connectors/__init__.py`

Uncomment the `CodexConnector()` line in `ALL_CONNECTORS` after importing it.

### 3. Verification (Q-C1..Q-C4 from the spec)

These are the unknowns probes couldn't resolve in `codex exec` mode. You can answer them in an interactive Codex session:

- **Q-C1**: Does `PreToolUse` actually fire on `apply_patch` when the hook is in `.codex/hooks.json` and the project trust is granted (via `/hooks` interactive command)? Test by creating a deny hook on a sentinel filename and confirming Codex refuses to edit it. **Do this BOTH in interactive `codex` AND `codex exec` modes.** The probe last time showed exec-mode might silently skip project hooks — document what you find.
- **Q-C2**: When `spawn_agents_on_csv` spawns one of your `.codex/agents/archie-wave1-*.toml` agents, does the sub-agent see the parent's AGENTS.md? Test by spawning a wave1 agent that should reference architecture context — if it can't find AGENTS.md, your SKILL body for deep-scan needs to seed context explicitly in the CSV instruction column.
- **Q-C3**: Your TOML merge must be idempotent. Run install twice; second run should produce zero diff in `~/.codex/config.toml`. Also: if the user already has `project_doc_fallback_filenames = ["TEAM_GUIDE.md"]`, your merge must produce `["TEAM_GUIDE.md", "CLAUDE.md"]`, not `["CLAUDE.md"]`.
- **Q-C4**: Default `codex exec --sandbox=read-only` blocks the scan scripts from writing to `.archie/`. Options: (a) the SKILL body instructs the user to use `--sandbox=workspace-write` for scan, or (b) the installer sets a project-level write permission. Pick one; document in the SKILL body.

### 4. Codex agent TOML templates (deferred work — your call)

`archie/assets/codex_agents/` is currently empty. Either:
- (a) Write 5 `.toml.template` files (`archie-wave1-structure.toml.template`, etc.) and have `install_agent` substitute placeholders from the `AgentDef` fields.
- (b) Construct the TOML inline from `AgentDef` fields in `install_agent` — no template files needed.

Recommendation: (b) if the TOML keys are stable; (a) if any agent's TOML needs unusual keys not in `AgentDef`.

### 5. Deep-scan SKILL body adaptation (deferred)

The current `.claude/commands/archie-deep-scan.md` is Claude-specific (uses Claude's Skill tool indirectly). For Codex deep-scan, you need a body that instructs the model to:
1. Run `.archie/scanner.py` data gathering.
2. Use `spawn_agents_on_csv` with the 4 Wave-1 agent TOMLs in parallel.
3. Use `wait` semantics to gather their outputs.
4. Spawn Wave-2 reasoning agent with all Wave-1 outputs as input.
5. Run `.archie/renderer.py` and `.archie/validate.py`.

**Open design call:** Should this body live at (a) `archie/assets/prompts/codex/skill_archie_deep_scan.md` (Codex-specific) or (b) `archie/assets/prompts/skill_archie_deep_scan.md` shared with the model branching based on CLI? Your decision — recommend (a) for now; consolidation is a future Claude session.

## Acceptance gate (Stage 3 in the spec)

- Fresh project. `npx @bitraptors/archie .` installs both Claude + Codex shims.
- `$archie-scan` from Codex produces same AGENTS.md as `/archie-scan` from Claude (modulo timestamps).
- `$archie-deep-scan` from Codex fans out 4 Wave-1 agents in parallel via `spawn_agents_on_csv`; blueprint matches Claude structurally.
- `~/.codex/config.toml` shows merged patch entries (idempotent on second install).
- Edit a forbidden file in Codex → blocked by PreToolUse hook. Validate in BOTH interactive and exec modes.

## Workflow

1. `git checkout feature/agent_connectors && git pull`
2. Implement `archie/connectors/codex.py`. ClaudeConnector is your reference shape.
3. Register in `archie/connectors/__init__.py`.
4. Test against a tmpdir + your own home directory.
5. Validate Q-C1..Q-C4 in an interactive Codex session. Document findings in your commit messages.
6. Push commits to `feature/agent_connectors`. Do not merge to `main`.

## Hard constraints

- No edits outside `archie/connectors/codex.py`, `archie/assets/codex_agents/`, `archie/connectors/__init__.py`, and (optionally) `archie/assets/prompts/codex/`. Do not touch ClaudeConnector or the install loop unless coordinating with the Claude session.
- No prompt or hook script duplication. Bodies you write live ONCE under `archie/assets/`.
- Honor the `Connector` ABC contract: capabilities you declare must work.

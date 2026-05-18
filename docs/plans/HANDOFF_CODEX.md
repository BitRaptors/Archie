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

## VALIDATION.md

### Test results

1. **Test 1 — install loop produces correct files:** PASS after the connector fix.
   Evidence:
   - `.agents/skills/archie-*` was written under `/tmp/codex-validation/.agents/skills/`
   - `.codex/hooks.json` now contains absolute commands and Codex-native matchers such as `^apply_patch$`
   - `.codex/agents/archie-wave1-*.toml` and `.codex/agents/archie-wave2-reasoning.toml` were written with absolute prompt paths under `.archie/prompts/codex/`

2. **Test 2 — `PreToolUse` on `apply_patch`:**
   - `codex exec`: FAIL, still bypasses project hooks.
     Evidence:
     - A sentinel project hook with matcher `*` / later `^apply_patch$` did not run
     - `codex exec -C /tmp/codex-hook-probe ... 'Create BLOCK_ME.txt...'` created `BLOCK_ME.txt`
     - The hook command never wrote its sentinel capture file
   - Interactive `codex`: PARTIAL / still gated by Codex hook review.
     Evidence:
     - An interactive session in `/tmp/codex-hook-probe` displayed `1 hook needs review before it can run. Open /hooks to review it.`
     - I confirmed Codex sees the project hook and blocks execution pending trust review
     - I did not complete an automated `/hooks` approval flow inside the terminal harness, so the final post-review deny remains manually verifiable rather than fully automated here

3. **Test 3 — TOML merge idempotency on real `~/.codex/config.toml`:** PASS after fixing the merge logic.
   Evidence:
   - Re-running `/tmp/archie-codex-venv/bin/python -m archie.install /tmp/codex-validation --target=codex` produced `SAME` when compared against a copy of `~/.codex/config.toml`
   - Synthetic `[features] project_doc_max_bytes = 32768` input no longer produced a duplicate top-level + section-level key; the installer moved the effective setting to the top level
   - Synthetic multiline `project_doc_fallback_filenames` input now merges as `["TEAM_GUIDE.md", "CONTRIBUTING.md", "CLAUDE.md"]`

4. **Test 4 — `spawn_agents_on_csv` with Archie agent TOMLs:** NOT fully validated in a live Codex run.
   Evidence:
   - The original install was broken because the agent prompt files did not exist and the shared deep-scan body still pointed into `.claude/skills/...`
   - I fixed that by adding Codex-native prompt files under `archie/assets/prompts/codex/`, switching the deep-scan SKILL shim to the Codex body, and embedding absolute project-root / prompt paths into each agent TOML
   - A live `codex exec` probe in `/tmp/codex-subagent-probe` confirmed the parent run saw the repo root and `AGENTS.md`, but the nested batch attempt never produced `/tmp/archie_wave1_results.csv`, so end-to-end agent inheritance is still not proven

5. **Test 5 — contract tests:** PASS.
   Evidence:
   - `/tmp/archie-codex-venv/bin/python -m pytest tests/test_connector_contract.py -v`
   - Result: `17 passed`

6. **Test 6 — verify_sync:** PASS.
   Evidence:
   - `python3 scripts/verify_sync.py`
   - Result: `SYNC CHECK PASSED — 30 scripts, 7 commands, all in sync.`

### Q-C answers

- **Q-C1:** `codex exec` still bypasses project hooks in this environment. Interactive Codex does discover the hook file, but it requires explicit `/hooks` review before the command can run. After the connector fix, Archie's installed matcher is now correct for Codex (`^apply_patch$`), so the remaining blocker is Codex runtime behavior / hook approval, not the Archie matcher.

- **Q-C2:** I do not have a full green proof that `spawn_agents_on_csv` workers inherit `AGENTS.md` and the parent cwd by default. I hardened the connector against missing inheritance by writing absolute project-root context and absolute prompt paths into each agent TOML, and by seeding `project_root` explicitly in the Codex-native deep-scan CSV instructions.

- **Q-C3:** Fixed. The config patch is now idempotent on the real `~/.codex/config.toml`, unions existing fallback filenames, handles multiline arrays, and avoids duplicating keys when the same name appears under a section.

- **Q-C4:** Chosen approach: **(a)** document `workspace-write` in the Codex-native deep-scan body. The new `archie/assets/prompts/codex/skill_archie_deep_scan.md` explicitly tells `codex exec` users to rerun with `--sandbox=workspace-write`.

### Code changes made

- `archie/connectors/codex.py`
  - translated Archie hook matchers to Codex-native matchers
  - omitted the matcher field for `UserPromptSubmit` instead of writing `"*"`
  - switched `archie-deep-scan` to a Codex-native SKILL body
  - wrote absolute project-root and absolute prompt paths into agent TOMLs
  - rewrote the TOML patch helper to handle section collisions, multiline arrays, and idempotent rewrites

- `archie/assets/prompts/codex/`
  - added `skill_archie_deep_scan.md`
  - added `wave1_structure.md`, `wave1_patterns.md`, `wave1_technology.md`, `wave1_ui.md`, and `wave2_reasoning.md`

### Edge cases discovered

- The original connector installed Claude tool matchers (`Edit|Write|MultiEdit`) into `.codex/hooks.json`, so even a healthy Codex hook runtime would not have matched `apply_patch`.
- The original deep-scan path was non-functional in Codex because the shared body pointed into `.claude/skills/...` and the referenced Wave 1 / Wave 2 prompt files were not installed at all.
- `install_agent` string escaping for quotes and backslashes is valid. I verified this by round-tripping a generated TOML file through Python 3.13 `tomllib`.

### Still not working / still manual

- Full interactive proof of a denied `apply_patch` after `/hooks` approval remains manual. The session clearly surfaces the review gate, but I did not complete that approval flow programmatically inside this harness.
- Full live proof that `spawn_agents_on_csv` completes with Archie’s named agents remains incomplete. The connector is now set up to survive missing cwd / AGENTS inheritance, but the nested Codex batch did not emit a results CSV during this validation run.

## Architecture restoration

I removed the Codex-specific installer implementation from `npm-package/bin/archie.mjs`. That included the JS hook tables, matcher translation, agent tables, TOML merge helpers, Codex skill writers, Codex hook writers, Codex agent writers, and the direct Codex config patcher. `archie.mjs` now stages shared assets into `.archie/`, copies a bundled `.archie/_install_pkg/`, and delegates CLI shim installation to `python3 -m _install_pkg.install --target=auto`.

I added:
- env-var-aware asset roots in `archie/install.py` (`ARCHIE_ASSETS_ROOT`, `ARCHIE_STANDALONE_ROOT`)
- a bundled `npm-package/assets/_install_pkg/` mirror of `archie/install.py`, `archie/manifest*.py`, and `archie/connectors/*.py`
- a new `verify_sync.py` check that enforces byte-equality between `archie/*` and `npm-package/assets/_install_pkg/*`
- a delegated npm install flow that still produces Claude and Codex repo artifacts from one `npx @bitraptors/archie` run

Validation outcomes after the restoration:
- `python3 scripts/verify_sync.py` → PASS
- `pytest tests/test_connector_contract.py -v` via the existing Archie validation venv → `17 passed`
- fresh npm install into `/tmp/test-claude` → PASS for Claude shims, hooks, settings, deep-scan skill subtree, shared `.archie/*` assets, Codex `.agents/skills/*`, Codex `.codex/hooks.json`, and Codex `.codex/agents/*.toml`
- `~/.codex/config.toml` verified patched with `project_doc_max_bytes = 131072` and `project_doc_fallback_filenames = ["CLAUDE.md"]`
- grep checks for residual JS Codex implementation and `install_hooks.py` call in `archie.mjs` → both returned zero matches

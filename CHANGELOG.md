# Changelog

## 3.0.0 — 2026-05-18

### Multi-agent connector architecture

Archie now targets three coding-agent CLIs as peers:

- **Claude Code** (existing — behavior preserved for Claude users)
- **OpenAI Codex CLI** (new) — discovers `.agents/skills/<name>/SKILL.md` via parent-walk; hooks wire through `.codex/hooks.json`; named sub-agents at `.codex/agents/*.toml` drive `spawn_agents_on_csv` parallel fan-out for deep-scan
- **Earendil Pi** (new) — discovers `.agents/skills/` (same path as Codex); a TS extension at `.pi/extensions/archie-hooks.ts` shells out to the same canonical hook scripts

One install, one source of truth. All three CLIs read identical Archie outputs.

### What's new

- **`Connector` interface** at `archie/connectors/base.py` — each CLI's integration lives in one file (`claude.py`, `codex.py`, `pi.py`) under `archie/connectors/`. Per-event capability flags (`hooks:pre-tool-use`, `agents`, `config-patch`) make feature drops explicit rather than hidden.
- **Single source of truth** for everything Archie ships: `archie/manifest_data.py` (commands, hooks, config patches, agent defs), `archie/assets/prompts/` (canonical bodies), `archie/assets/hook_scripts/` (canonical shell scripts shared across all CLIs), `archie/assets/pi_extension/` (Pi's TS hook bridge).
- **`python3 -m archie.install <project> [--target=auto|claude|codex|pi|all]`** — connector-based install loop. Auto-detect inspects `~/.claude/`, `~/.codex/`, `~/.pi/agent/`.
- **Telemetry consent rewritten as a model-driven prompt** — the shared fragment now asks via natural language so the same consent flow works in Claude, Codex, and Pi (the previous `AskUserQuestion` dependency was Claude-only).
- **Codex config patches**: the installer raises `project_doc_max_bytes` to 131072 (default 32 KiB was already breached on real Archie output at 6-deep folder paths) and adds `CLAUDE.md` to Codex's `project_doc_fallback_filenames` so per-folder context files are discovered.
- **Pi TS extension** for in-session enforcement — wraps Pi's `tool_call` event around the canonical `.archie/hooks/*.sh` scripts. Validation logic stays in Python (single source); the TS file is glue.
- **Contract tests** at `tests/test_connector_contract.py` — every connector's capability claims must work end-to-end against a tmpdir.

### Breaking changes

- The 5 slash-command bodies have moved from `.claude/commands/archie-*.md` (full bodies, hundreds of lines each) to `.archie/prompts/skill_archie_*.md` (canonical) plus thin 5-line shims at `.claude/commands/`. Existing Claude users see no behavior change — the shim references the canonical body, which the install loop copies into `.archie/prompts/`.
- Hook script content moved from inline heredocs in `archie/standalone/install_hooks.py` to canonical files at `archie/assets/hook_scripts/*.sh`. The installer reads from the canonical location (and ClaudeConnector copies the same files for Claude installs). Edits to validation logic in the `.sh` files now propagate to all three CLIs.

### Deferred / known limitations

- The npm-package installer (`npx @bitraptors/archie`) ships with the existing Claude-only flow. Codex+Pi support requires the additional `python3 -m archie.install` step described in the README. Full unification of the install entry points is a v3.1 follow-up.
- `.claude/skills/archie-deep-scan/` substeps remain Claude-specific (substep router files like `step-3-wave1/orchestration.md`). Codex and Pi execute the inlined SKILL body without the substep router — the analysis pipeline produces equivalent outputs but the in-session UX is slightly different.
- Codex `PreToolUse` hook firing in `codex exec` non-interactive mode was inconclusive in 2026-05-15 probes. Interactive Codex sessions are the primary supported surface.
- Pi cannot fan out sub-agents (its README states "No sub-agents"). Deep-scan on Pi runs Wave-1 sequentially — slower than Claude/Codex but functional. An RPC-mode parallel adapter is on the roadmap.

### Migration

Existing Claude users: run `npx @bitraptors/archie .` to upgrade in-place. The installer wipes old `.claude/commands/archie-*.md` (which had full bodies) and writes the new shims plus canonical bodies under `.archie/prompts/`. Settings and hook bindings merge non-destructively.

Codex / Pi users: after `npx @bitraptors/archie .` (or `pip install archie-cli`), run `python3 -m archie.install . --target=auto` to install shims for any detected CLI.

## 2.6.0 — earlier

See git history.

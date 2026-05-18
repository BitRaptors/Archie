# archie/assets/

Canonical bodies that get copied verbatim (or referenced by path) into installed projects. **Single source of truth** for every file Archie ships across all CLIs.

## Layout

- `prompts/` — SKILL bodies and sub-agent prompts. Read by all 3 CLIs at runtime via thin shims emitted by connectors.
- `hook_scripts/` — Shell scripts for in-session enforcement. Same scripts power Claude, Codex, and Pi (Pi shells out via its TS extension).
- `pi_extension/` — TypeScript source for Pi's hook bridge.
- `codex_agents/` — TOML templates for Codex named sub-agents (deep-scan Wave-1 / Wave-2 fan-out).

## How files here get into installed projects

The install loop (`archie/install.py`) copies asset files into `<project>/.archie/...` at install time. Connectors then emit thin shims (under `.claude/`, `.agents/skills/`, `.codex/`, `.pi/`) that reference these canonical paths.

## Status

Empty as of 2026-05-18 (scaffold commit). Stage 1 of the migration roadmap populates each subdirectory. See `docs/plans/2026-05-18-multi-agent-connector-architecture.md` §12 and §15 for the exact source → destination mapping.

# Design — OpenAI Codex CLI support for Archie

**Date:** 2026-04-09
**Status:** Approved (brainstorm), pending implementation
**Branch:** `feature/codex_support`
**Author:** Gabor + Claude (brainstorming session)

## Problem

Archie ships today as a Claude Code–only tool. The slash commands (`/archie-scan`, `/archie-deep-scan`, `/archie-viewer`), the hooks installer, and the rendered context files (`CLAUDE.md`) all assume Claude Code is the host CLI. We want OpenAI's Codex CLI users to get the same first-class experience without forking the project or duplicating analysis logic.

## Goal

Ship parity ASAP. Codex users get scan, deep-scan, viewer, hooks, and per-folder context files — the same surface Claude Code users have today. One npm package, one repo, one source of truth for analysis logic.

## Non-goals

- Replacing Claude Code support. Codex is an additional target, not a replacement.
- Building a runtime abstraction layer over both CLIs. Each CLI has its own connector with its own native idioms; the connectors are the abstraction.
- Supporting CLIs beyond Claude Code and Codex. The architecture leaves room but the brief is two targets.
- Refactoring the existing Claude Code commands. They keep working as-is.

## Mental model — the four boxes

```
┌─────────────────┐  ┌─────────────────┐
│ CONNECTOR       │  │ CONNECTOR       │
│ Claude Code     │  │ Codex CLI       │
│ .claude/        │  │ .agents/skills/ │
│   commands/     │  │   archie-*/     │
│   archie-*.md   │  │   SKILL.md      │
└────────┬────────┘  └────────┬────────┘
         │                    │
         └──────────┬─────────┘
                    ▼
         ┌──────────────────────┐
         │ SHARED LOGIC         │
         │ .archie/scanner.py   │
         │ .archie/renderer.py  │
         │ .archie/validator.py │
         │ .archie/prompts/*.md │
         └──────────┬───────────┘
                    │
         ┌──────────▼───────────┐
         │ INSTALLER            │
         │ archie.mjs           │
         │   --target=auto|     │
         │            claude|   │
         │            codex|    │
         │            both      │
         └──────────────────────┘
```

Four boxes. Anything not in one of these four boxes is over-engineering and must justify itself explicitly.

**Invariants:**
1. Sub-agent prompts live in exactly one place: `archie/prompts/`. Both connectors read them via their host CLI's native file-read mechanism.
2. The Python analysis layer (~8k LOC) never learns Codex exists, except for the renderer's `--target` flag which switches the output filename between `CLAUDE.md` and `AGENTS.md`.
3. Connectors are small (~30–50 lines each) and hand-written. Each contains the platform-specific orchestration in its host CLI's native idiom.
4. The installer is the only Node code that's target-aware. Everything Python is target-agnostic.

## Architecture decisions and rejected alternatives

| Decision | Rejected alternatives | Why |
|---|---|---|
| **Hand-written connectors per target.** Each is small, references shared prompts. | A YAML workflow definition + generator that emits both connectors. | The duplication is small (~50 lines × 2). A generator adds ~300–500 LOC of tooling, a new dev dep, schema lock-in, and an opaque "generated artifact" review experience. Not worth it for the volume of workflows we expect to add. |
| **Shared sub-agent prompts in `archie/prompts/`.** Both connectors read the same files at runtime. | Embed prompt text inline in each connector (duplicated). | The bulky content (prompt text, ~50% of file size) is identical across targets. Extracting it eliminates the duplication risk that motivated the simplification conversation. |
| **Sequential Wave 1 on Codex in PR 1; parallel `spawn_agent` fan-out in PR 2.** | Always parallel from day one (TOMLs everywhere). Always sequential (slower forever). | PR 1 needs zero TOMLs for the single-agent scan command. Adding parallelism in PR 2 is purely additive — the connector grows from "do these N things" to "spawn_agent for these N things, wait, then continue". |
| **Auto-detect default for `--target`.** Inspects `~/.claude/` and `~/.codex/`. | Always-both default. Claude-only default. Interactive prompt. | Most users have exactly one CLI installed. Auto-detect picks the right one without requiring users to learn a flag. Falls back to `both` if both are present, errors with install URLs if neither is. |
| **Stop hook + pre-commit hook for Codex enforcement.** | In-session blocking PreToolUse on Write/Edit (not possible — Codex's PreToolUse only fires on Bash today). | OpenAI hasn't extended PreToolUse beyond Bash. Stop hook gives in-session feedback (validator runs after each turn, results injected next turn). Pre-commit gives a hard gate before code leaves the dev's machine. Belt and suspenders. |
| **`AGENTS.md` as Codex's primary context file.** | Use `CLAUDE.md` for both. Use a third name like `ARCHIE.md`. | Codex natively reads `AGENTS.md` with nested per-folder discovery. Claude Code also reads `AGENTS.md` as a fallback. This is the most native fit for Codex with zero loss for Claude users. |
| **All multi-PR work on `feature/codex_support` branch; never auto-merge to main.** | Direct-to-main PRs. Auto-merge the integration PR. | Main must stay shippable for existing Claude users at all times. Gabor reserves the final integration merge for himself. |

## Sequencing — five PRs on `feature/codex_support`

All PRs target `feature/codex_support`. Only PR 5 has `main` as its base, and PR 5 is *prepared* (commits, push, `gh pr create`) but not auto-merged — Gabor handles the merge.

### PR 1 — Vertical slice (scan only)

The smallest possible thing that proves the four-box architecture end-to-end on Codex.

**New files:**
- `archie/prompts/scan_analyzer.md` — system prompt for the scan analysis agent.
- `npm-package/assets/prompts/scan_analyzer.md` — verbatim copy.
- `npm-package/assets/codex/skills/archie-scan/SKILL.md` — Codex connector (~30 lines).

**Modified files:**
- `npm-package/bin/archie.mjs` — add `--target=auto|claude|codex|both` flag, auto-detection logic, per-target install dispatch, shared `.archie/` install path.
- `archie/standalone/renderer.py` — add `--target` flag controlling root context filename (`CLAUDE.md` vs `AGENTS.md`).
- `scripts/verify_sync.py` — extend to verify `archie/prompts/` ↔ `npm-package/assets/prompts/` sync and to verify every prompt reference in connector files resolves to a real file.

**Out of scope for PR 1:** deep-scan, parallel subagents, TOMLs, hooks, intent layer, `.codex/config.toml` editing.

**Acceptance:** Fresh clone of a Codex user's project. Run `npx @bitraptors/archie /path/to/project --target=codex`. In Codex, `$archie-scan` runs end-to-end and produces `AGENTS.md` + rule files matching what Claude users get from `/archie-scan`.

### PR 2 — Deep-scan + Codex parallelism

**New files:**
- `archie/prompts/wave1_structure.md`, `wave1_patterns.md`, `wave1_technology.md`, `wave1_ui.md`, `wave2_reasoning.md` — five prompts.
- `npm-package/assets/codex/skills/archie-deep-scan/SKILL.md` — Codex deep-scan connector.
- `npm-package/assets/codex/agents/archie-wave1-{structure,patterns,technology,ui}.toml` and `archie-wave2-reasoning.toml` — five agent TOMLs for Codex's `spawn_agent` fan-out. Each TOML contains a thin `developer_instructions` shim that says "read your full prompt from `.archie/prompts/<file>.md` and follow it."

**Modified files:**
- `archie/standalone/renderer.py` — extend to render the full deep-scan blueprint output paths under both targets.
- `scripts/verify_sync.py` — add cross-target agent parity check (every agent referenced in a Claude command file must have a corresponding TOML referenced in the matching Codex SKILL.md).
- Codex feature flag enablement — `features.multi_agent = true` must be set in the user's `.codex/config.toml`. **Mechanism deferred to PR 2 implementation:** sidecar file + print instructions vs. in-place merge. Decided when actually building.

**E2E benchmark:** Run deep-scan against BabyWeather.Android with both CLIs. Compare wall-clock and output quality. Document.

### PR 3 — Enforcement hooks

**Modified files:**
- `archie/standalone/install_hooks.py` — add `--target=codex` branch.

**New files:**
- `npm-package/assets/codex/hooks.json` — Codex hook wiring. Three hooks:
  - `Stop` → `python3 .archie/validator.py all $PWD --post-turn` (validator runs after every Codex turn, violations injected into next prompt).
  - `UserPromptSubmit` → blueprint context nudge (lightweight, mirrors today's `blueprint-nudge.sh`).
  - `PreToolUse` matcher on `Bash` for `git commit` interception → `python3 .archie/validator.py all $PWD --pre-commit`.
- `npm-package/assets/git-hooks/pre-commit` — git pre-commit shell wrapper that calls `python3 .archie/validator.py all . --pre-commit`. Installer writes this to `.git/hooks/pre-commit`, with conflict handling: if a pre-commit hook already exists, write to `.git/hooks/pre-commit.archie` and print integration instructions instead of overwriting.

**Honest gap (documented in the SKILL.md and README):** Codex's `PreToolUse` does not fire on Write/Edit/MultiEdit today. Claude Code blocks file writes that violate rules; Codex catches them via the Stop hook (after the fact) and the pre-commit hook (before commit). When OpenAI extends `PreToolUse` to file edits, this gap closes automatically with no Archie code change.

### PR 4 — Per-folder context

**Modified files:**
- `archie/standalone/intent_layer.py` — `--target=codex` emits per-folder `AGENTS.md` instead of `CLAUDE.md`.
- `archie/standalone/renderer.py` — per-folder rendering follows the same target switch.

**Per-folder filename collision handling:** deferred to PR 4 implementation. If a folder already has both `CLAUDE.md` and `AGENTS.md`, decide whether to merge, prefer one, or skip with a warning.

### PR 5 — Integration to main

**Prepared, not merged.** This PR is created by automation (commits, push, `gh pr create`) but Gabor clicks the merge button.

**Contents:**
- Final rebase of `feature/codex_support` onto `main`.
- README updates documenting Codex support, install command, `$archie-scan` invocation, and the known PreToolUse gap.
- CHANGELOG entry.
- Landing page updates (if applicable to the npm release).
- Version bump.
- The PR description summarizes all 4 prior PRs as a single coherent change.

## Data flow

| Command | Flow |
|---|---|
| **Scan** (PR 1) | `$archie-scan` → Codex reads `SKILL.md` → runs `.archie/scanner.py` → reads `.archie/prompts/scan_analyzer.md` → analyzes in-session → runs `.archie/renderer.py --target=codex` and `.archie/validate.py` → writes `AGENTS.md` + rules. |
| **Deep-scan** (PR 2) | `$archie-deep-scan` → Codex reads `SKILL.md` → runs `.archie/scanner.py` → `spawn_agent` × 4 (Wave 1, parallel) → `wait_agent --all` → `spawn_agent` (Wave 2 reasoning, reads all four Wave 1 outputs) → render + validate → writes `AGENTS.md`, blueprint, rules. |
| **Enforcement** (PR 3) | After every Codex turn → `Stop` hook fires → `validator.py --post-turn` runs → violations injected as a system message into the next prompt → model self-corrects. Belt: `git commit` triggers `PreToolUse` Bash matcher → `validator.py --pre-commit` blocks if violations. Suspenders: `.git/hooks/pre-commit` blocks if user bypasses Codex entirely. |
| **Per-folder context** (PR 4) | At deep-scan time, `intent_layer.py --target=codex` walks the folder DAG bottom-up and emits `AGENTS.md` in each qualifying directory. Codex's nested AGENTS.md discovery picks them up automatically. |

## Error handling

Only the cases that actually need handling — no defensive fluff.

| Case | Behavior |
|---|---|
| Neither `~/.claude` nor `~/.codex` detected during install | Print both install URLs, exit non-zero. Never install into the wrong place. |
| Existing `AGENTS.md` in user project | Don't overwrite. Print "AGENTS.md already exists; skipping. Re-run with `--force` to replace." |
| Existing `.git/hooks/pre-commit` in user project | Write to `.git/hooks/pre-commit.archie`, print integration instructions, never silently clobber. |
| `features.multi_agent` not enabled in PR 2+ | Codex SKILL.md preflight check detects this and prints "Add `features.multi_agent = true` to ~/.codex/config.toml or run `archie enable-codex-features`." Fails gracefully before `spawn_agent` errors. |
| `verify_sync.py` finds drift | CI fails the PR with a specific error message: "Prompt file X referenced by Claude command but not Codex SKILL.md", or "Agent TOML Y has no matching SKILL.md reference". |

## Testing

Three layers, no fancier.

- **Static / sync:** `scripts/verify_sync.py` runs in CI on every PR. Checks prompt sync, prompt reference resolution, and (PR 2+) cross-target agent parity.
- **Smoke:** new `tests/test_install.py` runs `archie.mjs --target=codex|claude|both` against a tmpdir, asserts the expected files land in the expected locations.
- **E2E:** PR 2 introduces a benchmark — run deep-scan against BabyWeather.Android (the standard fixture) with both CLIs, diff the resulting `AGENTS.md`/`CLAUDE.md` against checked-in golden output. Same fixture extended in PR 3 for hook validation.

## Deferred decisions

Decided in the PR that needs them, not now.

| Decision | Decided in | Why deferred |
|---|---|---|
| `.codex/config.toml` enablement: sidecar file + print instructions vs. in-place merge | PR 2 | Doesn't change the four-box architecture. Easier to evaluate when implementing the actual installer logic with Codex's TOML format in front of us. |
| Exact set of Codex hook events to wire (and exact validator integration shape) | PR 3 | Same reason. The Stop hook is locked in; the rest depends on what works in practice. |
| Per-folder filename collision handling (folder has both `CLAUDE.md` and `AGENTS.md`) | PR 4 | Won't matter until the intent layer runs against a project that's used both Archie-Claude and Archie-Codex previously. Edge case. |

## Memory + workflow notes

- All implementation work happens on `feature/codex_support`. Direct-to-main is forbidden until PR 5.
- PR 5 is prepared but not auto-merged. Gabor merges manually.
- Existing memories that apply: `feedback_iterative_over_batch.md` (no batch one-shot), `feedback_simplicity_first.md` (default to smallest viable design), `feedback_feature_branches.md` (multi-PR initiatives use feature branches; never auto-merge to main).

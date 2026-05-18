# Handoff to the reviewer agent — multi-agent connector architecture

**Branch:** `feature/agent_connectors`
**Spec:** `docs/plans/2026-05-18-multi-agent-connector-architecture.md` (the contract).
**Tasks:** #12-20 in TaskList (9 stages).
**Status when handed to you:** Stages 1-5 implemented end-to-end on best-effort basis from public docs + probes. None of it has been validated against live Codex/Pi CLIs. That's your first job.

## The shape

```
archie/
  manifest.py                    — CommandDef, HookDef, ConfigPatch, AgentDef
  manifest_data.py               — single source of truth: 5 commands, 6 hooks, 2 config patches, 5 sub-agents
  connectors/
    base.py                      — Connector ABC + capability vocabulary
    claude.py                    — ClaudeConnector (full)
    codex.py                     — CodexConnector (full — needs CLI validation)
    pi.py                        — PiConnector (full — needs CLI validation)
    __init__.py                  — ALL_CONNECTORS registry (all 3 registered)
  install.py                     — install loop, target resolution, asset copy, git pre-commit
  assets/
    hook_scripts/*.sh            — 6 canonical shell scripts (extracted from install_hooks.py)
    pi_extension/                — TS template + package.json for Pi's hook bridge
    prompts/                     — empty (Stage 1 follow-up: body extraction)
    codex_agents/                — empty (CodexConnector constructs TOMLs inline; templates only if keys diverge)

tests/
  test_connector_contract.py     — capability claims must work; registry must be non-empty; every HookDef must have a backer

docs/plans/
  2026-05-18-multi-agent-connector-architecture.md   — SPEC (the contract)
  HANDOFF_CODEX.md, HANDOFF_PI.md                    — per-agent original work briefs
  HANDOFF_REVIEWER.md                                 — THIS DOC
```

## Where to start the review

**1. Read the spec first** — `docs/plans/2026-05-18-multi-agent-connector-architecture.md`. Section §4 (runtime model), §6 (data model), §7 (interface), §8 (capability vocabulary), §13 (parity matrix) are load-bearing. Everything else implements these.

**2. Run the contract tests:**
```bash
cd /Users/hamutarto/DEV/BitRaptors/Archie
python -m pytest tests/test_connector_contract.py -v
```
If anything fails, that's where to start. The tests assert the interface contract — capability claims must be honored.

**3. Diff against main:**
```bash
git log --oneline main..feature/agent_connectors
```
Two commits: `c3508abad` (scaffold), `013735332` (Stage 1+2 partials + handoff docs). Additional commits land the connector implementations.

## What's been validated vs what hasn't

### Validated by probes (Claude session, 2026-05-15)
- ✅ One `.agents/skills/<name>/SKILL.md` is discovered identically by Codex 0.130.0 and Pi 0.74.0 from the same path. Both invoked the test SKILL and printed the marker token.
- ✅ Codex's default `project_doc_max_bytes = 32 KiB` is already breached by real Archie output (measured 34,024 bytes on a 6-deep folder path). The `CodexConnector.patch_config` raises it to 131,072.
- ⚠️ Codex `PreToolUse` hook firing on `apply_patch`: inconclusive in `codex exec` mode. Project-trust was set in `~/.codex/config.toml` but the hook did not fire. Likely interactive-only trust gate OR exec-mode bypass. **Must validate in interactive Codex during review.**

### NOT validated (your job during review)
- **Codex hook deny semantics.** Write a test hook that denies edits to a sentinel filename, install via Archie, try to edit the sentinel in an interactive Codex session. Confirm the file is NOT created and the deny reason appears in Codex's output. Probe attempt failed in exec mode — interactive mode may differ.
- **Codex `spawn_agents_on_csv` agent inheritance.** When Codex spawns one of the `.codex/agents/archie-wave1-*.toml` agents we install, does the sub-agent inherit `AGENTS.md`, parent CWD, parent's permission state? Codex docs are silent. Test by deep-scanning a real fixture (BabyWeather.Android per Gabor's memory) and seeing whether sub-agents have architecture context.
- **Pi TS extension loading.** Does `.pi/extensions/archie-hooks.ts` auto-load on Pi session start, or does the user need to run `pi install /path/to/extension`? The `PiConnector.finalize` writes the file but never invokes a Pi CLI command. Test in real Pi session.
- **Pi extension module resolution.** Does Pi resolve `@earendil-works/pi-coding-agent` from its global install (ideal — our `package.json` is informational), or does our extension need `npm install` in `.pi/extensions/` first?
- **Pi async-vs-sync extension returns.** Template uses `spawnSync`. If Pi's `pi.on("tool_call", async (event, ctx) => ...)` requires async returns for denials, swap to `spawn` with an async wrapper.
- **Pi sequential deep-scan wall-clock.** Measure against BabyWeather.Android vs Codex parallel via `spawn_agents_on_csv`. If sequential is > 5× slower, design needs a Stage 5b RPC parallel adapter.

## Implementation choices that need a second opinion

These are decisions I made under uncertainty — please flag if any seem wrong:

1. **TOML config merge** (`archie/connectors/codex.py::_toml_set_top_level`). I rolled a regex-based top-level TOML key setter because Archie targets Python 3.9+ and `tomllib` only landed in 3.11. The merge handles top-level scalars and inline string arrays — the two key shapes Archie patches. It does NOT handle inline tables, multi-line arrays, or keys inside `[section]` blocks. Risks: a user's `~/.codex/config.toml` with unusual structure (commented blocks, nested tables with our key name) could behave unexpectedly. Reviewer call: is the constraint acceptable, or should we add a `tomli` dep?

2. **CodexConnector.install_command body fallback.** When `archie/assets/prompts/codex/<name>.md` doesn't exist (current state — body extraction deferred), we emit a SKILL with a one-line pointer to `.archie/prompts/<name>.md`. But `.archie/prompts/` is also empty until Stage 1 follow-up extracts bodies. This means a fresh install produces SKILL.md files that reference non-existent body files. **Reviewer decision:** ship the broken pointer for now (Stage 1 follow-up fixes it), OR have install fail loudly when body source is missing, OR copy the existing `.claude/commands/archie-*.md` bodies as Codex bodies (cross-pollution, but works).

3. **PiConnector inheritance from CodexConnector.** Pi inherits `install_command` because both walk `.agents/skills/` with the same SKILL.md format. This is pragmatic but couples Pi to Codex's shape. If Codex later changes its frontmatter requirements (e.g., adds required fields), Pi breaks. Reviewer call: keep inheritance and accept the coupling, or extract a `SkillBasedConnector` mixin?

4. **Pi `package.json` shipped under `.pi/extensions/`.** We don't know if Pi expects this manifest. Shipping it doesn't hurt (Pi ignores irrelevant files); not shipping it might mean the extension can't resolve imports. The peerDependencies declaration is a hint but doesn't actually install anything. Reviewer call: leave as-is, or strip it and let Q-P3 decide?

5. **Hook scripts at canonical `.archie/hooks/` vs per-CLI `.claude/hooks/`.** ClaudeConnector currently copies the script to `.claude/hooks/<name>.sh` AND the install loop copies the canonical script to `.archie/hooks/<name>.sh`. The Codex/Pi connectors reference `.archie/hooks/<name>.sh`. So we have BOTH paths in installed projects. That's redundant. Either: (a) Claude also references `.archie/hooks/` (settings.json paths change), or (b) Codex/Pi reference `.claude/hooks/` (creates cross-CLI directory dependency). Reviewer call: (a) is cleaner long-term but breaks current Claude installs. (b) keeps current Claude path but couples Codex/Pi to a Claude directory.

## What was deliberately left for later

- **Body extraction** (Stage 1 follow-up): `.claude/commands/archie-*.md` bodies still live there, not in `archie/assets/prompts/`. The bodies reference `AskUserQuestion`, the `Agent` tool, `.claude/skills/` — Claude-specific. A CLI-agnostic rewrite is best done with concrete Codex+Pi bodies in hand for comparison.
- **`archie.mjs` rewire** (Stage 2 follow-up): the Node installer still runs the legacy Claude-only install path. Adding `python3 -m archie.install --target=auto` as the new entry needs careful migration — defer until you've validated the Python install loop end-to-end.
- **Telemetry consent rewrite** (Stage 6): the current `_shared/telemetry-consent.md` uses `AskUserQuestion`. Rewriting as a model-driven prompt is a content rewrite that benefits from concrete Codex+Pi acceptance tests.
- **Verify-sync extensions** (Stage 8): `scripts/verify_sync.py` should check that every `body_path`/`script_path`/`prompt_path` in manifest_data resolves to a real file under `archie/assets/`. Add it.
- **README + CHANGELOG** (Stage 9 partial): no version bump yet. The reviewer / Gabor coordinates release timing.

## Recommended review order

1. Run `python -m pytest tests/test_connector_contract.py -v`. Fix any failures first.
2. Read the spec (§4, §6, §7, §8, §13 are load-bearing).
3. Read `archie/connectors/claude.py` (the reference implementation that's known to work — it migrates existing logic).
4. Read `archie/connectors/codex.py` — focus on the TOML merge (`_toml_set_top_level`) and the hooks.json schema.
5. Read `archie/connectors/pi.py` and `archie/assets/pi_extension/archie-hooks.ts.template` — focus on whether the spawnSync glue is correct.
6. Run an actual install on a tmpdir, inspect the output:
   ```bash
   mkdir /tmp/archie-test && cd /tmp/archie-test && git init
   python3 -m archie.install $PWD --target=all
   find . -type f
   ```
7. Validate Codex hook firing in an interactive Codex session (Q-C1 from the spec).
8. Validate Pi TS extension loading in a real Pi session (Q-P1).
9. Flag anything that looks off — Gabor reviews your findings before merge.

## Reviewer's red-flag checklist

- [ ] Any connector method that crashes on a valid manifest entry → broken capability claim, fix the connector.
- [ ] `python3 -m archie.install /tmp/foo --target=all` writes files for ALL 3 CLIs (even if their home dirs don't exist locally).
- [ ] `~/.codex/config.toml` patch is idempotent — second install produces zero diff.
- [ ] Test `--target=auto` on a system with only Claude installed → only Claude shims written.
- [ ] Pi TS extension loads without errors in `pi --print "hello"` (sanity check).
- [ ] No prompt body, hook script, or extension code is duplicated anywhere.
- [ ] No new Python deps. Stays stdlib-only per Archie's zero-dep promise.

## After your review

Gabor takes over for:
- Body extraction (Stage 1 follow-up)
- `archie.mjs` rewire (Stage 2 follow-up)
- Telemetry rewrite (Stage 6)
- Installer auto-detect polish (Stage 7) — `--target=auto` is implemented; Gabor decides on UX of "X CLI not detected, install?" messaging
- README, CHANGELOG, version bump to 3.0.0 (Stage 9)
- Final merge to `main`

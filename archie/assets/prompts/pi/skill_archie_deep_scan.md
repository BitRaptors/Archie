---
name: archie-deep-scan
description: Pi-native sequential deep scan for Archie. Runs scanner, four Wave-1 passes locally in sequence, then synthesizes and renders the blueprint.
---

# Archie Deep Scan For Pi

Run Archie’s deep scan end to end from Pi. Pi has no sub-agents, so do **not** use `spawn_agents_on_csv` or any parallel-agent primitive. Execute the four Wave-1 perspectives yourself, sequentially, using the same scanner / renderer / validator pipeline and the Wave prompts installed under `.archie/prompts/codex/`.

## Preconditions

- If `.archie/scanner.py`, `.archie/renderer.py`, or `.archie/validate.py` is missing, stop and tell the user to run `npx @bitraptors/archie "$PWD"` first.
- Use the repository root as the working directory for every shell command.
- Read `AGENTS.md` first if it exists. Treat it as required architectural context.

## Step 1: Run the deterministic scanner

Run:

```bash
python3 .archie/scanner.py "$PWD" >/tmp/archie_deep_scan_stdout.json
```

This must leave `.archie/scan.json` and `.archie/skeletons.json` in place.

## Step 2: Load shared inputs

Read:

- `AGENTS.md` if it exists
- `.archie/scan.json`
- `.archie/skeletons.json`
- `.archie/prompts/codex/wave1_structure.md`
- `.archie/prompts/codex/wave1_patterns.md`
- `.archie/prompts/codex/wave1_technology.md`
- `.archie/prompts/codex/wave1_ui.md`
- `.archie/prompts/codex/wave2_reasoning.md`

The Wave prompt files are content-agnostic; they are reused by Pi even though they live in the `codex/` prompt subtree.

## Step 3: Run Wave 1 sequentially

Perform exactly four local analysis passes, in this order:

1. `archie-wave1-structure` — components, layers, file placement. Follow `.archie/prompts/codex/wave1_structure.md`.
2. `archie-wave1-patterns` — communication, design patterns, integrations. Follow `.archie/prompts/codex/wave1_patterns.md`.
3. `archie-wave1-technology` — stack, deployment, development rules. Follow `.archie/prompts/codex/wave1_technology.md`.
4. `archie-wave1-ui` — UI components, state, routing, only if the scanner indicates a meaningful frontend/UI surface; otherwise record a skipped UI pass with the reason. Follow `.archie/prompts/codex/wave1_ui.md` when applicable.

For each pass, write a JSON object with keys:

- `agent`
- `focus`
- `cwd`
- `saw_agents_md`
- `summary`
- `findings`

Set `cwd` to the project root. Set `saw_agents_md` to true only if you actually read `AGENTS.md`.

Save the four objects as a JSON array to `/tmp/archie_wave1_results.json`. Also write `/tmp/archie_wave1_results.csv` with equivalent columns for compatibility with the Codex workflow notes.

## Step 4: Wave 2 synthesis

Read `/tmp/archie_wave1_results.json`, scanner outputs, `AGENTS.md` if present, and `.archie/prompts/codex/wave2_reasoning.md`. Perform the reasoning pass locally and produce a structurally complete Archie blueprint JSON containing:

- `meta`
- `architecture_rules`
- `decisions`
- `components`
- `communication`
- `quick_reference`
- `technology`
- `deployment`
- `frontend`
- `pitfalls`
- `implementation_guidelines`
- `development_rules`
- `architecture_diagram`

Save the returned JSON to `.archie/blueprint.json`. The result should be structurally equivalent to Claude/Codex deep-scan output; only wall-clock time should differ.

## Step 5: Render and validate

Run:

```bash
python3 .archie/renderer.py "$PWD"
python3 .archie/validate.py all "$PWD"
```

If validation fails, report the failing validator and the error output.

## Completion

Your final response must include:

- that Wave 1 ran sequentially in Pi
- whether each pass reported `saw_agents_md = true`
- whether the pass `cwd` values matched the project root
- whether render and validation completed successfully

---
name: archie-deep-scan
description: Codex-native deep scan for Archie. Runs the scanner, fans Wave 1 out through named Codex subagents, then synthesizes Wave 2 output and renders the project docs.
---

# Archie Deep Scan For Codex

Run Archie’s deep scan end to end from Codex. This workflow is Codex-specific because it relies on named subagents under `.codex/agents/` and `spawn_agents_on_csv`.

## Preconditions

- If `.archie/scanner.py`, `.archie/renderer.py`, or `.archie/validate.py` is missing, stop and tell the user to run `npx @bitraptors/archie "$PWD"` first.
- If you are in `codex exec` and the sandbox is read-only, stop immediately and tell the user to rerun with `--sandbox=workspace-write`. Archie writes scan artifacts into `.archie/`, so read-only mode is not sufficient.
- Use the repository root as the working directory for every shell command.

## Shared context

Before spawning subagents, read these files if they exist:

- `AGENTS.md`
- `.archie/scan.json`
- `.archie/skeletons.json`

Treat `AGENTS.md` as required context for every architectural judgment. The subagents may or may not inherit it automatically, so you must seed the project root explicitly in the CSV job instructions.

## Step 1: Run the deterministic scanner

Run:

```bash
python3 .archie/scanner.py "$PWD" >/tmp/archie_deep_scan_stdout.json
```

This must leave `.archie/scan.json` and `.archie/skeletons.json` in place.

## Step 2: Create the Wave 1 batch

Write `/tmp/archie_wave1.csv` with columns:

- `agent`
- `focus`
- `project_root`

Create exactly these rows:

- `archie-wave1-structure,components layers and file placement,$PWD`
- `archie-wave1-patterns,communication design patterns and integrations,$PWD`
- `archie-wave1-technology,stack deployment and development rules,$PWD`
- `archie-wave1-ui,ui components state routing and frontend-specific structure,$PWD`

## Step 3: Spawn Wave 1 subagents in parallel

Call `spawn_agents_on_csv` with:

- `csv_path`: `/tmp/archie_wave1.csv`
- `id_column`: `agent`
- `max_concurrency`: `4`
- `output_csv_path`: `/tmp/archie_wave1_results.csv`
- `instruction`:

```text
Project root: {project_root}
You are the {agent} worker.
Start by reading {project_root}/AGENTS.md if it exists.
Then read .archie/scan.json and .archie/skeletons.json from that project root.
Focus only on {focus}.
Return your result via report_agent_job_result as JSON with keys:
agent, focus, cwd, saw_agents_md, summary, findings.
Set saw_agents_md to true only if you actually read AGENTS.md.
Set cwd to your observed working directory.
```

- `output_schema`: an object with required fields `agent`, `focus`, `cwd`, `saw_agents_md`, `summary`, and `findings`

After the batch completes, inspect `/tmp/archie_wave1_results.csv`. If any row failed, stop and report which worker failed.

## Step 4: Wave 2 synthesis

Read:

- `/tmp/archie_wave1_results.csv`
- `AGENTS.md`
- `.archie/scan.json`
- `.archie/skeletons.json`

Then use the named agent `archie-wave2-reasoning` for the synthesis pass. Give it the scanner outputs plus the full Wave 1 CSV results and ask it to return structured JSON containing:

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

Save the returned JSON to `.archie/blueprint.json`.

## Step 5: Render and validate

Run:

```bash
python3 .archie/renderer.py "$PWD"
python3 .archie/validate.py all "$PWD"
```

If validation fails, report the failing validator and the error output.

## Completion

Your final response must include:

- whether Wave 1 fan-out succeeded
- whether each worker reported `saw_agents_md = true`
- whether the worker `cwd` values matched the project root
- whether render and validation completed successfully

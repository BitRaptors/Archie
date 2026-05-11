# Archie Deep Scan — Comprehensive Architecture Baseline

Run a comprehensive architecture analysis. Produces full blueprint, per-folder CLAUDE.md, rules, and health metrics.

**Modes:**
- `/archie-deep-scan` — full baseline from step 1 (default, proven workflow)
- `/archie-deep-scan --incremental` — only process files changed since last deep scan (fast, 3-6 min)
- `/archie-deep-scan --from N` — resume from step N (runs N through 9)
- `/archie-deep-scan --continue` — resume from where the last run stopped

**Prerequisites:** Run `npx @bitraptors/archie` first to install the scripts. If `.archie/scanner.py` doesn't exist, tell the user to run `npx @bitraptors/archie` and try again.

**CRITICAL CONSTRAINT: Never write inline Python.**
Do NOT use `python3 -c "..."` or any ad-hoc scripting to inspect, parse, or transform JSON. Every operation has a dedicated command:
- Normalize blueprint: `python3 .archie/finalize.py "$PROJECT_ROOT" --normalize-only`
- Append health history: `python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history --scan-type deep`
- Inspect any JSON file: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" <filename>`
- Query a specific field: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" scan.json --query .frontend_ratio`

If you need data not covered by these commands, proceed without it or ask the user. NEVER improvise Python.

## Preamble: Determine starting step

Check the user's message (ARGUMENTS) for flags:

**If `--from N` is present** (e.g., `/archie-deep-scan --from 5`):
1. Set `START_STEP = N` (the number after --from) and `RESUME_ACTION=resume` (so the Resume Prelude rehydrates shell variables from `deep_scan_state.run_context`).
2. Validate prerequisites exist:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" check-prereqs N
```
3. If check fails, tell the user which files are missing and which earlier step to run.
4. If check passes, proceed. Do NOT call `deep-scan-state init` — it would wipe the state the Resume Prelude needs to read.

**If `--continue` is present:**
1. Read state (no prompt — `--continue` is an explicit opt-in):
```bash
LAST=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .last_completed 2>/dev/null)
STATUS=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .status 2>/dev/null)
[ -z "$LAST" ] || [ "$LAST" = "null" ] && LAST=0
```
2. If `LAST == 0` or `STATUS == "completed"`: print "No interrupted run found. Starting fresh from step 1." Set `START_STEP=1`, `RESUME_ACTION=fresh`, and run `deep-scan-state init` below.
3. Otherwise: Set `START_STEP = LAST + 1`, `RESUME_ACTION=resume`. Print `"Resuming deep scan from step {START_STEP}."`. Skip the init call.

**If `--incremental` is present:**
1. Check if `.archie/blueprint.json` exists. If not: print "No existing blueprint — running full baseline instead." Set SCAN_MODE = "full", START_STEP = 1, and proceed as default.
2. If blueprint exists, detect changes:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" detect-changes
```
3. Read the JSON output:
   - If `mode` is "full" (threshold exceeded or no previous scan): print the `reason` and say "Running full baseline." Set SCAN_MODE = "full", START_STEP = 1.
   - If `mode` is "incremental" and `changed_count` is 0: print "No files changed since last deep scan. Nothing to do." Exit.
   - If `mode` is "incremental": Set SCAN_MODE = "incremental". Save `changed_files` and `affected_folders` from the output. Print "Incremental deep scan: N files changed. Analyzing changes only." Set START_STEP = 1.
4. Initialize state:
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
```

**If no flags (default — detect interrupted run, otherwise full baseline):**

Before assuming a fresh run, check whether a previous deep-scan was left unfinished. If so, offer the user a choice instead of silently wiping their work.

1. Read state:
```bash
LAST=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .last_completed 2>/dev/null)
STATUS=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" deep_scan_state.json --query .status 2>/dev/null)
[ -z "$LAST" ] || [ "$LAST" = "null" ] && LAST=0
```

2. **If `LAST == 0` or `STATUS == "completed"`** → no interrupted run. Proceed as fresh:
   - Set `SCAN_MODE=full`, `START_STEP=1`, `RESUME_ACTION=fresh`.
   - Initialize state: `python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init`.

3. **Otherwise** (`LAST > 0` and `STATUS == "in_progress"`) → an interrupted run exists. Figure out which step stopped it and where enrichment state stands:
   ```bash
   ENRICH_DONE=$(python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" enrich_state.json --query '.done|length' 2>/dev/null)
   [ -z "$ENRICH_DONE" ] || [ "$ENRICH_DONE" = "null" ] && ENRICH_DONE=0
   ```
   Build a human-readable label for the last completed step:
   | LAST | step_name |
   |---|---|
   | 1 | scanner |
   | 2 | read accumulated knowledge |
   | 3 | Wave 1 analytical agents |
   | 4 | Wave 1 merge |
   | 5 | Wave 2 reasoning agent |
   | 6 | AI rule synthesis |
   | 7 | Intent Layer |
   | 8 | Cleanup |
   | 9 | Drift detection |

   Call `AskUserQuestion`:
   - **question:** (build dynamically) `"A previous deep-scan stopped after Step {LAST} ({step_name})."` — and if `ENRICH_DONE > 0`, append `" The Intent Layer got {ENRICH_DONE} folders in before stopping."` — then `"What do you want to do?"`
   - **header:** "Resume"
   - **multiSelect:** false
   - **options** (exactly these two labels):
     1. label `Resume` — description `Continue from Step {LAST+1}. Preserves all completed work, including any partial Intent Layer batches. Recommended.`
     2. label `Fresh start` — description `Discard all progress and restart from Step 1. Erases the interrupted blueprint, Wave 1 outputs, and the partial Intent Layer state. Use only if the codebase changed significantly.`

   Map the answer:
   - `Resume` → Set `START_STEP = LAST + 1`, `RESUME_ACTION=resume`. Skip `init`. Print `"Resuming from Step {START_STEP}."`.
   - `Fresh start` → Reset everything and start over:
     ```bash
     python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" init
     python3 .archie/intent_layer.py reset-state "$PROJECT_ROOT"
     rm -f /tmp/archie_enrichment_*.json
     ```
     `reset-state` wipes both `.archie/enrich_state.json` and the `.archie/enrichments/` directory — no `rm -rf` needed in the slash-command layer (keeps the command inside the default Bash permission allowlist so this runs prompt-free).
     Set `SCAN_MODE=full`, `START_STEP=1`, `RESUME_ACTION=fresh`. Print `"Starting fresh. Previous progress discarded."`.

4. Regardless of branch above, `RESUME_ACTION` is now set. It gates the Resume Prelude (below) and the Step 7 delta (passes `RESUME_INTENT` to the Intent Layer).

**For every step below:**
- If the step number < START_STEP, skip it entirely.
- If SCAN_MODE is not set, it defaults to "full" (all existing behavior unchanged).
- **Do NOT ask the user any questions during execution. Do NOT offer to skip, reduce scope, or present alternatives for any step. Execute every step fully as documented.**

## Phase 0: Resolve scope

Every run needs to know whether to scan the root, a specific workspace, or a set of workspaces. The choice is persisted in `.archie/archie_config.json` so we ask at most once per project.

### Step A: Read existing config

```bash
python3 .archie/intent_layer.py scan-config "$PWD" read
```

- **Exit 0** → config exists. Parse `scope`, `workspaces`, `monorepo_type` from the JSON. Skip to Step D.
- **Exit 1** → config missing. Go to Step B.

If the user invoked the command with `--reconfigure`, skip Step A entirely and go to Step B.

### Step B: Detect monorepo type + subprojects

```bash
python3 .archie/scanner.py "$PWD" --detect-subprojects
```

Parse `monorepo_type` and count subprojects where `is_root_wrapper` is false.

- **0 or 1 non-wrapper subprojects** → Not a monorepo. Write config as `single`:

  ```bash
  echo '{"scope":"single","monorepo_type":"<detected-type>","workspaces":[]}' \
    | python3 .archie/intent_layer.py scan-config "$PWD" write
  ```

  Skip to Step D.

- **2+ non-wrapper subprojects** → Go to Step C.

### Step C: Interactive scope prompt

First, print the workspace list so the user sees what's available:

> Found **N workspaces** in this **{monorepo_type}** monorepo:
> 1. {name} ({type}) — {path}
> 2. {name} ({type}) — {path}
> ...

Then call `AskUserQuestion` with the scope choice:

- **question:** "How do you want to analyze this monorepo?"
- **header:** "Scope"
- **multiSelect:** false
- **options** (exactly these four labels and descriptions):
  1. label `Whole` — description `One unified blueprint treating the monorepo as one product. Workspaces become components; cross-workspace imports become the primary architecture view. Fastest.`
  2. label `Per-package` — description `One blueprint per workspace you pick. Deep detail per package, no product-level view.`
  3. label `Hybrid` — description `Whole blueprint at root + per-workspace blueprints for specific workspaces. Most comprehensive, slowest.`
  4. label `Single` — description `Ignore the workspaces and scan the whole tree as if it were one project. Only for small monorepos.`

Map the answer: Whole → `whole`, Per-package → `per-package`, Hybrid → `hybrid`, Single → `single`.

- If `whole` or `single` → `WORKSPACES=[]`
- If `per-package` or `hybrid` → ask which workspaces to include.
  - **N ≤ 4 workspaces:** use `AskUserQuestion` with `multiSelect: true`. One option per workspace, label `{name} ({type})`, description `Path: {path}`. Map the user's checkbox picks back to paths.
  - **N ≥ 5 workspaces:** `AskUserQuestion` caps options at 4 — fall back to a free-form follow-up: *"Which workspaces? Type comma-separated numbers (e.g., `1,3,5`) or `all`."* Resolve to paths relative to `$PWD`.
  - Either way, honor `all` as a shortcut for every workspace.

If `per-package` or `hybrid`, also call `AskUserQuestion` for run mode:

- **question:** "How should the selected workspaces run?"
- **header:** "Run mode"
- **multiSelect:** false
- **options:**
  1. label `Parallel` — description `Spawn one agent per workspace at the same time. Faster, more concurrent model usage.`
  2. label `Sequential` — description `Run workspaces one after another. Slower but easier to follow the output.`

Map: Parallel → `parallel`, Sequential → `sequential`.

Persist the chosen config (parallel/sequential lives only in the run itself, not in the config file):

```bash
echo '{"scope":"<chosen>","monorepo_type":"<detected-type>","workspaces":[<array>]}' \
  | python3 .archie/intent_layer.py scan-config "$PWD" write
```

### Step D: Validate

```bash
python3 .archie/intent_layer.py scan-config "$PWD" validate
```

- **Exit 0** → proceed.
- **Exit 1** → workspace drift. Instruct the user to re-run with `--reconfigure`. Stop.

Expose `SCOPE`, `WORKSPACES`, `MONOREPO_TYPE`.

### Step E: Intent Layer choice

Call `AskUserQuestion` to decide whether to run the per-folder enrichment pass (Step 7):

- **question:** "Generate per-folder CLAUDE.md files (Intent Layer)?"
- **header:** "Intent Layer"
- **multiSelect:** false
- **options:**
  1. label `Yes — enrich every folder (Recommended)` — description `Adds a short, folder-specific CLAUDE.md to every directory in your project — role, expected patterns, anti-patterns. AI coding agents then get pinpoint local context wherever they edit instead of re-deriving it from the root CLAUDE.md each time. Adds a few minutes of Sonnet time (scales with folder count).`
  2. label `No — skip Intent Layer` — description `Faster deep-scan. Only the root CLAUDE.md + rule files are written. AI agents editing files in deep folders won't have folder-local architectural guidance.`

Map the answer: Yes → `INTENT_LAYER=yes`, No → `INTENT_LAYER=no`. Expose `INTENT_LAYER` for the rest of the run. Step 7 honors this flag.

### Step F: Persist run context

Write every shell variable that Steps 1–10 depend on into `.archie/deep_scan_state.json` so `/compact` + `--continue` can rehydrate them from disk without relying on orchestrator memory:

```bash
echo "$WORKSPACES" | python3 .archie/intent_layer.py deep-scan-state "$PWD" save-run-context \
    --scope "$SCOPE" \
    --intent-layer "$INTENT_LAYER" \
    --scan-mode "$SCAN_MODE" \
    --monorepo-type "$MONOREPO_TYPE" \
    --start-step "$START_STEP" \
    --workspaces-from-stdin
```

Note: `PROJECT_ROOT` is not persisted — `$PWD` at resume time is the authoritative value (slash commands are always invoked from the repo root, and the state file itself lives under `<root>/.archie/`). Persisting the absolute path would leak machine-specific info (e.g. `/Users/foo/...`) into a state file users may commit. The `save-run-context` subcommand silently accepts `--project-root` for backward compat with older installs but discards the value.

This is a no-op on `--continue` runs because the Resume Prelude already rehydrated these variables. Safe to call every time.

### Execution plan based on SCOPE

- **SCOPE=single** — Set `PROJECT_ROOT="$PWD"` and run Steps 1-9 once. No monorepo awareness.
- **SCOPE=whole** — Set `PROJECT_ROOT="$PWD"` and run Steps 1-9 once, applying the workspace-aware addendum in the Structure agent (Step 3) so each workspace is a top-level component, and the Wave 2 reasoning agent populates `blueprint.workspace_topology`.
- **SCOPE=per-package** — For each path in `WORKSPACES`, set `PROJECT_ROOT="$PWD/<path>"` and run Steps 1-9. Parallel mode spawns one background Agent per workspace (temp files namespaced as `/tmp/archie_sub1_<name>.json`). Sequential mode runs them one after another. After all finish, go to Step 8 / 9 each within its own `PROJECT_ROOT`.
- **SCOPE=hybrid** — Pass 1: run Steps 1-9 at `PROJECT_ROOT="$PWD"` with whole-mode semantics. Pass 2: iterate `WORKSPACES` per-package. Each pass writes its own blueprint under `PROJECT_ROOT/.archie/`.

**IMPORTANT:** The `.archie/*.py` scripts are installed at the REPO ROOT. Always reference them as `.archie/scanner.py` etc. from the repo root. Pass `PROJECT_ROOT` as the first argument when it is not `$PWD`.

---

Run the following steps once per project. In single-project mode, `PROJECT_ROOT` is the repo root. In monorepo mode, `PROJECT_ROOT` is the sub-project directory.

Use `PROJECT_NAME` as the basename of `PROJECT_ROOT` for namespacing temp files (e.g., "gasztroterkepek-android").

## Telemetry conventions

<!-- archie:extracted -> archie-deep-scan/fragments/telemetry-conventions.md -->

## Compact-and-resume contract

<!-- archie:extracted -> archie-deep-scan/fragments/compact-resume-contract.md -->

## Resume Prelude (runs whenever `RESUME_ACTION=resume`)

<!-- archie:extracted -> archie-deep-scan/fragments/resume-prelude.md -->

## Step 1: Run the scanner

<!-- archie:extracted -> archie-deep-scan/steps/step-1-scanner.md -->

## Step 2: Read scan results

<!-- archie:extracted -> archie-deep-scan/steps/step-2-read-scan.md -->

## Step 3: Spawn analytical agents

<!-- archie:extracted -> archie-deep-scan/steps/step-3-wave1/orchestration.md -->

## Step 4: Save Wave 1 output and merge

<!-- archie:extracted -> archie-deep-scan/steps/step-4-merge.md -->

## Step 5: Wave 2 — Reasoning agent

<!-- archie:extracted -> archie-deep-scan/steps/step-5-wave2-reasoning.md -->
## Step 6: AI Rule Synthesis

<!-- archie:extracted -> archie-deep-scan/steps/step-6-rule-synthesis.md -->

## Step 7: Intent Layer — per-folder CLAUDE.md

<!-- archie:extracted -> archie-deep-scan/steps/step-7-intent-layer.md -->

## Step 8: Clean up

<!-- archie:extracted -> archie-deep-scan/steps/step-8-cleanup.md -->

## Step 9: Drift Detection & Architectural Assessment

<!-- archie:extracted -> archie-deep-scan/steps/step-9-drift.md -->

## Step 10: Write telemetry

<!-- archie:extracted -> archie-deep-scan/steps/step-10-telemetry.md -->

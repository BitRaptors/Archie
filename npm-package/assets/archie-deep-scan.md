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
    --project-root "$PWD" \
    --monorepo-type "$MONOREPO_TYPE" \
    --start-step "$START_STEP" \
    --workspaces-from-stdin
```

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

Every Step 1–9 records its start timestamp to disk via `telemetry.py mark` as its first action. The mark auto-closes the previous step's `completed_at`, mirroring the "next step's start = prior step's end" convention. Step 9 finishes its own completion with `telemetry.py finish`. After Step 10, `telemetry.py write` consumes the persisted `.archie/telemetry/_current_run.json` and emits the final `deep-scan_<timestamp>.json`.

Shell-variable fallback: the existing `TELEMETRY_STEPN_START` shell variables are still set for readability, but they are **not load-bearing** — the disk file is the source of truth. This makes the pipeline safe to `/compact` mid-run without losing timing data.

## Compact-and-resume contract

At every "✓ Step N complete" boundary, all state needed to resume lives on disk:

- `.archie/deep_scan_state.json` — last completed step + `run_context` (scope, intent_layer, scan_mode, workspaces, monorepo_type, project_root, start_step)
- `.archie/telemetry/_current_run.json` — every step's start/completed timestamp + extras
- `.archie/archie_config.json` — persisted scope picker answer (whole/per-package/hybrid/single)
- `.archie/blueprint_raw.json`, `.archie/blueprint.json`, `.archie/findings.json` — pipeline output as it accumulates
- `.archie/enrich_state.json`, `.archie/enrich_batches.json` — Intent Layer DAG scheduler state (survives mid-Step-7 compaction)

After a `/compact`, running `/archie-deep-scan --continue` re-enters via the **Resume Prelude** below, which rehydrates every shell variable from disk before jumping to the next step. No conversation memory required.

## Resume Prelude (runs whenever `RESUME_ACTION=resume`)

Execute this block **before any other step** when resuming. It rehydrates every shell variable the pipeline depends on from disk, so the orchestrator does NOT need to have carried them forward in its conversation context.

`RESUME_ACTION=resume` is set by the Preamble in any of these cases:
- `--continue` flag was passed (explicit opt-in)
- `--from N` flag was passed (explicit opt-in; also sets `START_STEP=N`)
- **No flag was passed, partial state was detected, and the user chose "Resume"** at the interactive prompt (the bare-invocation path added in v2.4)

In all three cases, the variables `SCOPE`, `INTENT_LAYER`, `SCAN_MODE`, `MONOREPO_TYPE`, `WORKSPACES`, `PROJECT_ROOT`, `PROJECT_NAME` need to be rehydrated from `deep_scan_state.run_context` — they were set during the original run and persisted to disk. Without this block, the resumed run has no idea what scope was chosen, whether Intent Layer was opt-in, etc.

Safe to run on a fresh invocation too — the `LAST=0` branch short-circuits back to normal Phase 0 flow.

```bash
# 1. Read last_completed via dedicated CLI. A fresh run returns "null" → normalise to 0.
LAST=$(python3 .archie/intent_layer.py inspect "$PWD" deep_scan_state.json --query .last_completed 2>/dev/null)
[ -z "$LAST" ] || [ "$LAST" = "null" ] && LAST=0

# 2. If we have real state, rehydrate every shell variable from run_context.
if [ "$LAST" -gt 0 ]; then
    PROJECT_ROOT=$(python3 .archie/intent_layer.py inspect "$PWD" deep_scan_state.json --query .run_context.project_root 2>/dev/null)
    [ "$PROJECT_ROOT" = "null" ] && PROJECT_ROOT=""
    SCOPE=$(python3 .archie/intent_layer.py inspect "$PWD" deep_scan_state.json --query .run_context.scope 2>/dev/null)
    [ "$SCOPE" = "null" ] && SCOPE=""
    INTENT_LAYER=$(python3 .archie/intent_layer.py inspect "$PWD" deep_scan_state.json --query .run_context.intent_layer 2>/dev/null)
    [ "$INTENT_LAYER" = "null" ] || [ -z "$INTENT_LAYER" ] && INTENT_LAYER=yes
    SCAN_MODE=$(python3 .archie/intent_layer.py inspect "$PWD" deep_scan_state.json --query .run_context.scan_mode 2>/dev/null)
    [ "$SCAN_MODE" = "null" ] || [ -z "$SCAN_MODE" ] && SCAN_MODE=full
    MONOREPO_TYPE=$(python3 .archie/intent_layer.py inspect "$PWD" deep_scan_state.json --query .run_context.monorepo_type 2>/dev/null)
    [ "$MONOREPO_TYPE" = "null" ] || [ -z "$MONOREPO_TYPE" ] && MONOREPO_TYPE=none
    # WORKSPACES as newline-separated (matches the scope picker's original shape).
    WORKSPACES=$(python3 .archie/intent_layer.py inspect "$PWD" deep_scan_state.json --query .run_context.workspaces --list 2>/dev/null)
    PROJECT_NAME="${PROJECT_ROOT##*/}"

    # 3. Compute START_STEP. --from N overrides; otherwise resume at LAST+1.
    if [ -n "$FROM_STEP" ]; then
        START_STEP=$FROM_STEP
    else
        START_STEP=$((LAST + 1))
    fi

    # 4. Consistency check: telemetry _current_run.json should contain at least
    # one step entry per completed step. Warn loudly if the two states diverge
    # — that signals either corruption or manual intervention. Do not abort;
    # telemetry is informational, the scan itself is still resumable from
    # blueprint/findings on disk.
    TELEMETRY_STEPS=$(python3 .archie/telemetry.py steps-count "$PWD" 2>/dev/null)
    [ -z "$TELEMETRY_STEPS" ] && TELEMETRY_STEPS=0
    if [ "$TELEMETRY_STEPS" -lt "$LAST" ]; then
        echo "WARNING: deep_scan_state says last_completed=$LAST but telemetry has only $TELEMETRY_STEPS step marks. Final per-step timing may be incomplete. Scan output itself is not affected." >&2
    fi

    echo "Resuming from persisted state: SCOPE=$SCOPE SCAN_MODE=$SCAN_MODE INTENT_LAYER=$INTENT_LAYER last_completed=$LAST start_step=$START_STEP" >&2

    # 5. Skip Phase 0 (scope resolution) — we already have the answers on disk.
    # Jump directly to Step $START_STEP in the main pipeline below.
else
    # Fresh run: LAST=0 or no run_context. Fall through to Phase 0 normally.
    : # no-op; flow continues with scope resolution below.
fi
```

**Notes on accuracy:**

- Rehydrating from disk is lossless by construction — `save-context` wrote exactly these fields, and `save-context` runs both in Step F (fresh runs) and is safe to call again if anything changes mid-run.
- The consistency check is defensive. Under normal compact-and-resume flow, telemetry step count ≥ last_completed always holds because each step marks its start *before* calling `complete-step N`. A warning here signals something outside the happy path (manual state edit, aborted step, corrupted file).
- `WORKSPACES` is rehydrated as a newline-separated string, matching what Step C's scope picker originally produced. Downstream iteration patterns (`while IFS= read`; `printf '%s\n' "$WORKSPACES" | ...`) work identically.
- If `--from N` is supplied, the orchestrator sets `FROM_STEP=N` before this block runs.

## Step 1: Run the scanner

**Telemetry:** persist the step start to disk (compaction-safe), then keep the shell var for readability:
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan scan
TELEMETRY_STEP1_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 1, skip this step.**

```bash
python3 .archie/scanner.py "$PROJECT_ROOT"
python3 .archie/detect_cycles.py "$PROJECT_ROOT" --full 2>/dev/null
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 1
```

## Step 2: Read scan results

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan read
TELEMETRY_STEP2_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 2, skip this step.**

Read `$PROJECT_ROOT/.archie/scan.json`. Note total files, detected frameworks, top-level directories, and `frontend_ratio`.

Also read `$PROJECT_ROOT/.archie/dependency_graph.json` if it exists — it provides the resolved directory-level dependency graph with node metrics (in-degree, out-degree, file count) and cycle data. Wave 1 agents can reference this for quantitative dependency analysis.

**UI layer detection:** Only spawn the dedicated UI Layer agent if `frontend_ratio` >= 0.20 (20%+ of source files are UI/frontend). A small SwiftUI menubar or a minor React admin panel in an otherwise backend/CLI/library project does NOT warrant a dedicated UI agent — the Structure agent will cover it.

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 2
```

## Step 3: Spawn analytical agents

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan wave1
python3 .archie/telemetry.py extra "$PROJECT_ROOT" wave1 model=sonnet
TELEMETRY_STEP3_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 3, skip this step.**

### If SCAN_MODE = "incremental":

Spawn a **single Sonnet subagent** (`model: "sonnet"`) with:
- The `changed_files` list (from detect-changes output in preamble)
- The existing `.archie/blueprint_raw.json`
- Skeletons for changed files only (read `.archie/skeletons.json`, filter to only keys matching changed file paths)
- The scan.json import graph

Agent prompt:
> You have the existing architectural blueprint and a list of files that changed since the last analysis. Read the changed files and their context. Report what changed architecturally:
> - New or modified components (name, location, responsibility, depends_on)
> - Changed communication patterns or integrations
> - New technology or dependencies
> - Modified file placement patterns
>
> Return the same JSON structure as the full analysis but ONLY for sections affected by the changes. Omit unchanged sections — they'll be preserved from the existing blueprint.
>
> GROUNDING RULES apply (see below).

Save the agent's complete output to `/tmp/archie_incremental_$PROJECT_NAME.json`.

Then skip to Step 4.

### If SCAN_MODE = "full" (default):

Spawn 3–4 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`), each focused on a different analytical concern. ALL agents read ALL source files under `$PROJECT_ROOT` — they are not split by directory. Each agent gets: the scan.json file_tree, dependencies, config files, and the GROUNDING RULES at the end of this step.

**If `frontend_ratio` >= 0.20, spawn all 4 agents. Otherwise spawn only the first 3 (skip UI Layer).**

**Bulk content — off-limits for reading.** `scan.json.bulk_content_manifest` lists files classified by `.archiebulk` as "visible inventory, not contents": categories like `ui_resource` (Android `res/`, iOS storyboards), `generated`, `localization`, `migration`, `fixture`, `asset`, `lockfile`, `dependency`, `data`. Every agent below inherits this rule: **you may reference these paths by name and inventory counts, but you MUST NOT call Read on them.** The scanner has already summarized their shape. If a specific file is genuinely required to resolve a finding, read it surgically and note why — it is an exception, not the default.

---

### Structure agent

> **CRITICAL INSTRUCTIONS:**
> You are analyzing a codebase to understand its architecture. Your goal is to OBSERVE and DESCRIBE what exists, NOT to categorize it into known patterns.
>
> **Workspace-aware addendum (only when `SCOPE === "whole"`):**
> This is a workspace monorepo (`MONOREPO_TYPE={type}`, N workspaces under paths `<workspaces>`). Treat each workspace member as a top-level component in `components.components`:
> - `name` = workspace `name` from its `package.json` (or equivalent for Cargo/Gradle)
> - `location` = workspace directory path relative to `$PROJECT_ROOT`
> - `platform` = inferred from workspace contents (frontend/backend/shared/etc.)
> - `responsibility` = inferred from package `description` + entry points
> - `depends_on` = other workspace members it imports (read its `package.json` dependencies, filter to workspace names)
>
> Additionally produce a top-level `workspace_topology` field:
> ```json
> "workspace_topology": {
>   "type": "{MONOREPO_TYPE}",
>   "members": [{"name": "...", "path": "...", "role": "app|lib|tool"}],
>   "edges": [{"from": "name-a", "to": "name-b", "count": 3}],
>   "cycles": [["a", "b", "a"]],
>   "dependency_magnets": [{"name": "shared", "in_degree": 8}]
> }
> ```
>
> Record `dependency_magnets` (workspaces in the top quartile of in_degree) inside `workspace_topology` as shown — it's a structural inventory field, not a finding.
>
> **DO NOT write directly to `blueprint.pitfalls`.** Pitfalls are emitted only by Wave 2 Opus synthesis in the canonical 4-field shape. Instead, capture cross-workspace import cycles and other workspace-level problems as **draft findings** for Wave 2 to upgrade. Append each to the `findings` array you return alongside your structure output, using this shape:
>
> ```json
> {
>   "problem_statement": "Cross-workspace import cycle: <name-a> → <name-b> → <name-a>",
>   "evidence": ["<name-a>/path/to/file.ts imports <name-b>/…", "<name-b>/path/to/file.ts imports <name-a>/…"],
>   "root_cause": "",
>   "fix_direction": "",
>   "severity": "error",
>   "confidence": 0.9,
>   "applies_to": ["<name-a>", "<name-b>"],
>   "source": "scan:structure",
>   "depth": "draft"
> }
> ```
>
> Leave `root_cause` and `fix_direction` empty strings — Wave 2 will fill them with architectural grounding when it upgrades the draft to canonical. Reference workspace members by **name** (not path) in all cross-references.

>
> **DO NOT:**
> - Assume this is a "layered architecture", "MVC", "Clean Architecture", or any specific pattern
> - Look for patterns that match your training data
> - Force observations into predefined categories
>
> **DO:**
> - Describe the ACTUAL file organization you see
> - Identify how files relate to each other based on naming and imports
> - Note any conventions unique to this codebase
>
> Read all source files. Analyze the actual structure of this codebase:
>
> ### 1. Project Type & Platforms
> - Identify if this is a monorepo, single app, microservice, serverless, full-stack, library, etc.
> - List ALL platforms found: backend, web-frontend, mobile-ios, mobile-android, desktop, CLI, shared/common
> - List main entry point files for EACH platform (main.py, index.ts, App.tsx, AppDelegate.swift, MainActivity.kt, main.dart, etc.)
> - Document module/package organization approach
>
> ### 2. Components
> Identify main components from actual code — class names, imports, file organization. For each component:
> - **name**: Component name
> - **location**: Directory path (MUST exist in file_tree)
> - **platform**: backend | frontend | shared | ios | android
> - **responsibility**: Describe what the code DOES, not what names suggest. BAD: "Handles business logic". GOOD: "Orchestrates weather data fetching via WeatherProvider, manages profile state, coordinates push notification scheduling". Reference actual class names and services.
> - **depends_on**: From actual import statements
> - **exposes_to**: What other components consume from it
> - **key_interfaces**: Actual method/function names with brief description. For API routes, list ONLY methods actually implemented — do NOT assume CRUD.
> - **key_files**: With descriptions of what each file does (paths MUST exist in file_tree)
>
> ### 3. Layers
> Analyze ALL platforms (backend AND frontend). Only document layers you can clearly identify from:
> 1. Import patterns between directories
> 2. Directory structure and naming
> 3. Actual code organization
>
> **If no clear layers exist**, set structure_type to flat, modular, or feature-based and document the actual structure.
>
> For each layer found, document: name, platform (backend|frontend|shared), location, responsibility (SPECIFIC — reference actual classes), contains (component types), depends_on (from imports), exposes_to, key_files.
>
> Common backend patterns (only if they ACTUALLY exist): Presentation/API (routes, controllers, DTOs), Application/Service (orchestration, use cases), Domain (entities, interfaces), Infrastructure (database, external APIs, caching).
> Common frontend patterns (only if they ACTUALLY exist): Pages/Views, Features/Containers, Components/UI, Hooks/Services, State/Store.
>
> ### 4. Architecture Style
> Describe in plain language. Examples: "Actor-based with message passing", "Event-sourced with CQRS separation", "Feature-sliced with co-located concerns", "Traditional layered with services and repositories", "Functional core with imperative shell" — or describe something completely unique.
>
> ### 5. File Placement & Naming
> - Where do tests, configs, components, services actually live? With naming patterns observed.
> - Search the file_tree for where test files, config files, build output, and generated code actually live. Do NOT assume conventional locations.
> - Document actual naming conventions: PascalCase components, snake_case utils, kebab-case files, etc. With 2-4 examples each.
>
> ### 6. Framework Usage
> Catalog external frameworks/libraries from import statements. For each, note the framework name and usage scope.
>
> Return JSON:
> ```json
> {
>   "meta": {
>     "architecture_style": "plain language description",
>     "platforms": ["backend", "web-frontend"],
>     "executive_summary": "3-5 factual sentences: what this does, primary tech, architecture style. No filler."
>   },
>   "components": {
>     "structure_type": "layered | flat | modular | feature-based",
>     "components": [
>       {"name": "", "location": "", "platform": "", "responsibility": "", "depends_on": [], "exposes_to": [], "key_interfaces": [{"name": "", "methods": [], "description": ""}], "key_files": [{"file": "", "description": ""}]}
>     ]
>   },
>   "architecture_rules": {
>     "file_placement_rules": [
>       {"component_type": "", "naming_pattern": "", "location": "", "example": "", "description": ""}
>     ],
>     "naming_conventions": [
>       {"scope": "", "pattern": "", "examples": [], "description": ""}
>     ]
>   }
> }
> ```

### Patterns agent

> Read all source files. Analyze design patterns and communication across ALL platforms (backend AND frontend).
>
> ### 1. Structural Patterns (identify with concrete examples)
> **Backend:**
> - **Dependency Injection**: How are dependencies wired? Container? Manual? Framework? (@inject, providers, etc.)
> - **Repository**: How is data access abstracted? Interface + implementation? Active Record?
> - **Factory**: How are complex objects created?
> - **Registry/Plugin**: How are multiple implementations managed?
>
> **Frontend:**
> - **Component Composition**: How are UI components composed? HOC? Render props? Hooks? Slots?
> - **Data Fetching**: How is server state managed? React Query? SWR? Apollo? Combine? Coroutines?
> - **State Management**: Global state approach? Context? Redux? Zustand? @Observable? ViewModel+StateFlow? Bloc?
> - **Routing**: File-based? Config-based? NavigationStack? NavGraph?
>
> For each pattern found: pattern name, platform (backend|frontend|shared), implementation description, example file paths.
>
> ### 2. Behavioral Patterns
> - **Service Orchestration**: How are multi-step workflows coordinated?
> - **Streaming**: How are long-running responses handled? SSE? WebSockets? gRPC streams?
> - **Event-Driven**: Are there publish/subscribe patterns? Event buses?
> - **Optimistic Updates**: How are UI updates handled before server confirmation?
> - **State Machines**: Any explicit state machine patterns?
>
> ### 3. Cross-Cutting Patterns
> - **Error Handling**: Custom exceptions? Error boundaries? Global handler? Error mapping? What errors map to what status codes?
> - **Validation**: Where? How? What library? Client-side vs server-side?
> - **Authentication**: JWT? Session? OAuth? Where validated? How propagated to frontend?
> - **Logging**: Structured? What logger? What's logged?
> - **Caching**: What's cached? TTL strategy? Browser cache? Server cache?
>
> For each: concern, approach, location (actual file paths).
>
> ### 4. Internal Communication
> - **Backend**: Direct method calls between layers, in-process events, message buses
> - **Frontend**: Props, Context, event emitters, pub/sub, state management stores
> - **Cross-Platform**: API calls from frontend to backend, shared types/contracts
> - **Runtime boundaries** (flag whenever present): separate processes/workers/threads/iframes/subprocesses, their lifecycle (who spawns, how they die), and the protocol crossing each boundary (IPC channel names, stdio framing like NDJSON/length-prefix, RPC shape). Record the exact files where each side is implemented.
> - **Seams and invariants** (flag whenever present): abstract interfaces/classes/traits with multiple concrete implementations (note what varies vs. what's stable); any wrapper/middleware/interceptor/guard that conditionally allows, denies, transforms, or sequences other operations based on state. Wave 2 will upgrade these into key decisions — just surface the raw signal here.
>
> ### 5. External Communication
> - **HTTP/REST**: External API calls (both backend-to-external and frontend-to-backend)
> - **Message Queue**: Async job processing (Redis, RabbitMQ, etc.)
> - **Streaming**: SSE, WebSockets, gRPC streams
> - **Database**: Query patterns, transactions, ORM usage
> - **Real-time**: Push notifications, live updates
>
> ### 6. Third-Party Integrations
> List ALL external services with: service name, purpose, integration point (file path).
> Categories: AI/LLM providers, payment processors, auth providers, storage services, analytics/monitoring, CDN/asset hosting.
> Also call out any **extension protocols** — mechanisms by which third-party or user-supplied capabilities can be plugged in at runtime (plugin systems, protocol-based tool/resource loading, hook/callback registries, config-driven dispatch). For each: the protocol, the registration point, and how contributed capabilities stitch into the core's catalog.
>
> ### 7. Frontend-Backend Contract
> - How do frontend and backend communicate? (REST, GraphQL, tRPC, WebSocket, etc.)
> - Are types shared between frontend and backend?
> - How are API errors propagated to the UI?
>
> ### 8. Pattern Selection Guide
> For common scenarios in this codebase, which pattern should be used and why?
>
> Return JSON:
> ```json
> {
>   "communication": {
>     "patterns": [
>       {"name": "", "when_to_use": "", "how_it_works": "", "examples": []}
>     ],
>     "integrations": [
>       {"service": "", "purpose": "", "integration_point": ""}
>     ],
>     "pattern_selection_guide": [
>       {"scenario": "", "pattern": "", "rationale": ""}
>     ]
>   },
>   "quick_reference": {
>     "pattern_selection": {"scenario": "pattern"},
>     "error_mapping": [{"error": "", "status_code": 0, "description": ""}]
>   }
> }
> ```

### Technology agent

> Read config files, package.json/requirements.txt/Gemfile/build.gradle/pubspec.yaml/Package.swift, CI/CD configs, Dockerfiles, cloud platform files. Create a complete technology inventory.
>
> ### 1. Full Stack Inventory (by category)
> For each technology include: category, name, version, purpose, platform (backend|frontend|shared).
>
> Categories to check:
> 1. **Runtime**: Language, version, runtime environment (for each platform)
> 2. **Backend Framework**: Web framework, version, key features used
> 3. **Frontend Framework**: UI framework/library, version, rendering strategy
> 4. **Database**: Type, ORM/query builder, version
> 5. **Cache**: Redis, Memcached, in-memory, browser cache, etc.
> 6. **Queue**: Celery, RabbitMQ, ARQ, Redis Queue, etc.
> 7. **AI/ML**: Providers (OpenAI, Anthropic, etc.), SDKs, models
> 8. **Auth**: Library, provider, JWT/session handling
> 9. **State Management**: Frontend state (Redux, Zustand, React Query, etc.)
> 10. **Styling**: CSS framework, component library
> 11. **Validation**: Library, approach
> 12. **Testing**: Framework, tools, coverage approach (for each platform)
> 13. **Linting/Formatting**: Tools, configuration
> 14. **Monitoring**: Logging, metrics, error tracking
>
> ### 2. Run Commands
> From package.json scripts, Makefile, Rakefile, etc. Map command name to command string.
>
> ### 3. Project Structure
> ASCII directory tree from scan.json showing top-level organization.
>
> ### 4. Templates
> Common file patterns — how to create a new component/route/service/test in this codebase. Include file_path_template, component_type, description, and a brief code skeleton (max 3 lines).
>
> ### 5. Deployment Detection (CRITICAL — check for ALL of these)
> - **Cloud provider**: GCP (app.yaml, cloudbuild.yaml, google-cloud-* deps, firebase.json), AWS (boto3, aws-cdk, serverless.yml, buildspec.yml, template.yaml), Azure (azure-* SDKs, azure-pipelines.yml, host.json), Vercel (vercel.json), Netlify (netlify.toml), Fly.io (fly.toml), Railway (railway.json), Render (render.yaml)
> - **Compute**: Cloud Run, App Engine, Lambda, EC2, Fargate, Azure Functions, Vercel Edge, Heroku dynos
> - **Container**: Docker (Dockerfile, .dockerignore), Podman; orchestration (Kubernetes, Docker Compose, ECS, Helm, skaffold)
> - **Serverless**: Cloud Functions, Lambda, Edge Functions, Vercel Serverless
> - **CI/CD**: GitHub Actions (.github/workflows/), Cloud Build (cloudbuild.yaml), GitLab CI (.gitlab-ci.yml), CircleCI, Jenkins, Fastlane (Fastfile), Bitrise
> - **Distribution**: App Store, Google Play, npm registry, PyPI, Docker Hub, Maven Central, CocoaPods, pub.dev, Homebrew, APK sideload
> - **IaC**: Terraform (*.tf), CloudFormation/SAM (template.yaml), Pulumi, Helm charts
> - **Supporting services**: Firebase, Supabase, Redis Cloud, managed databases, CDNs, object storage (GCS, S3)
> - **Environment config**: .env files, Secret Manager, SSM Parameter Store, Vault, config maps
> - **Mobile-specific**: Backend services (BaaS), push notification providers, analytics, OTA updates, app signing
> - **Library-specific**: Package registry, build/publish pipeline, versioning strategy
> - List all deployment-related KEY FILES found in the repository
>
> ### 6. Development Rules
> Imperative rules inferred from tooling config. Each MUST cite a source file.
>
> Sources to check:
> - Package manager lockfiles (poetry.lock, yarn.lock, pnpm-lock.yaml)
> - Pre-commit/quality checks (.pre-commit-config.yaml, husky, lint-staged)
> - CI enforcement (.github/workflows/, Makefile, tox.ini)
> - Linting/formatting mandates (ruff.toml, .eslintrc, prettier, editorconfig)
> - Environment setup (setup.sh, Makefile, docker-compose.yml, .env.example)
> - Testing requirements (CI configs, pytest.ini, jest.config)
> - Git conventions (.gitignore, commit hooks, branch protection)
>
> State each as: "Always X" or "Never Y", cite the source file.
>
> **CRITICAL**: Every rule MUST be specific to THIS project. Generic rules are WORTHLESS.
> GOOD: "Always register new routes in api/app.py — uses explicit include_router()" (source: api/app.py)
> GOOD: "Never import from infrastructure/ in domain/ — dependency rule enforced by layer structure" (source: directory layout)
> BAD: "Use descriptive variable names", "Follow SOLID principles", "Write unit tests"
>
> Return JSON:
> ```json
> {
>   "technology": {
>     "stack": [{"category": "", "name": "", "version": "", "purpose": ""}],
>     "run_commands": {"command_name": "command_string"},
>     "project_structure": "ASCII tree",
>     "templates": [{"component_type": "", "description": "", "file_path_template": "", "code": ""}]
>   },
>   "deployment": {
>     "runtime_environment": "GCP|AWS|Azure|Vercel|on-device|browser|self-hosted",
>     "compute_services": [],
>     "container_runtime": "Docker|Podman|none",
>     "orchestration": "Kubernetes|Docker Compose|ECS|none",
>     "serverless_functions": "Cloud Functions|Lambda|Edge Functions|none",
>     "ci_cd": [],
>     "distribution": [],
>     "infrastructure_as_code": "Terraform|CloudFormation|Pulumi|none",
>     "supporting_services": [],
>     "environment_config": "",
>     "key_files": []
>   },
>   "development_rules": [
>     {"category": "dependency_management|testing|code_style|ci_cd|environment|git", "rule": "Always/Never ...", "source": "file_that_proves_it"}
>   ]
> }
> ```

### UI Layer agent (only if `frontend_ratio` >= 0.20)

> Read all UI/frontend source files. This codebase contains a significant UI layer. Analyze it as ONE ASPECT of the project — do NOT label the entire project as a "frontend app" or "iOS app" if the UI is only part of a larger system. Adapt each section to the platform detected.
>
> ### 1. Framework & Rendering
> - **Web**: What UI framework? (React, Vue, Angular, Svelte, etc.) Rendering strategy? (SSR, SSG, CSR, ISR, hybrid) Meta-framework? (Next.js, Nuxt, Remix, etc.)
> - **iOS**: Declarative (SwiftUI) vs imperative (UIKit)? App architecture? (MVVM, VIPER, Clean Swift, etc.)
> - **Android**: Jetpack Compose vs XML layouts? Architecture? (MVVM, MVI, Clean Architecture?)
> - **Cross-platform**: Framework? (Flutter, React Native, KMP, etc.) Platform-specific bridging?
>
> ### 2. UI Components
> For each major component/screen/view:
> - **name** and **location** (must exist in file_tree)
> - **component_type**: screen | page | layout | feature | shared | primitive | widget
> - **description**: What it renders and its purpose
> - **props**/inputs/parameters
> - **children**: Child components it renders or embeds
>
> ### 3. State Management
> - **Web**: Global state (Context, Redux, Zustand, Recoil), server state (React Query, SWR, Apollo), local state, form state
> - **iOS**: @State, @Observable, @EnvironmentObject, Combine, MVVM with ObservableObject, @Published
> - **Android**: ViewModel + StateFlow/LiveData, Compose state (remember/mutableStateOf), MVI pattern, SavedStateHandle
> - **Cross-platform**: Platform-specific (Bloc, Riverpod, Provider for Flutter; Redux/MobX for RN)
>
> Document: approach, global_state stores with purposes, server_state mechanism, local_state approach, and rationale for the choices.
>
> ### 4. Routing / Navigation
> - **Web**: File-based or config-based? List routes with paths, components, descriptions, auth requirements, dynamic segments.
> - **iOS**: NavigationStack, UINavigationController, Coordinator pattern, TabBar, deep links
> - **Android**: Navigation Component (NavHost/NavGraph), bottom navigation, deep links, Intent-based
> - **Cross-platform**: Navigator/Router, tab/stack/drawer navigation
>
> ### 5. Data Fetching / Networking
> - **Web**: Data fetching hooks/patterns, loading/error states, caching strategy
> - **iOS**: URLSession, Alamofire, Moya; Combine/async-await patterns; offline support
> - **Android**: Retrofit, Ktor, OkHttp; Coroutine/Flow patterns; offline support (Room + network)
> - **Cross-platform**: Dio/http for Flutter; fetch/axios for RN; Ktor for KMP
>
> ### 6. Styling / Theming
> - **Web**: Tailwind, CSS Modules, Styled Components, component library, design tokens
> - **iOS**: SwiftUI modifiers, UIKit programmatic styling, Interface Builder, custom themes
> - **Android**: Compose theming/Material3, XML themes, Material Components, custom design system
> - **Cross-platform**: Flutter ThemeData, RN StyleSheet, shared design tokens
>
> ### 7. Key Conventions
> - File naming conventions for components/screens/views
> - Component organization (co-located, feature-based, atomic, module-based)
> - Custom hooks/extensions/utilities naming and organization
> - Test file placement
>
> Return JSON:
> ```json
> {
>   "frontend": {
>     "framework": "",
>     "rendering_strategy": "SSR | SSG | CSR | ISR | hybrid | declarative | imperative",
>     "ui_components": [
>       {"name": "", "location": "", "component_type": "", "description": "", "props": [], "children": []}
>     ],
>     "state_management": {
>       "approach": "",
>       "global_state": [{"store": "", "purpose": ""}],
>       "server_state": "",
>       "local_state": "",
>       "rationale": ""
>     },
>     "routing": [
>       {"path": "", "component": "", "description": "", "auth_required": false}
>     ],
>     "data_fetching": [
>       {"name": "", "mechanism": "", "when_to_use": "", "examples": []}
>     ],
>     "styling": "",
>     "key_conventions": []
>   }
> }
> ```

---

**Every agent also gets these GROUNDING RULES:**

> **GROUNDING RULES — every claim must come from code you READ, never from names or conventions.**
> This applies to ANY codebase — web, mobile, desktop, backend, CLI, library, any language.
>
> 1. **Paths**: Only reference file/directory paths that appear in scan.json file_tree. Do NOT infer conventional paths — every framework has different conventions (Rails uses `spec/`, Go uses `_test.go` files, Swift uses `Tests/`, etc.). Find the ACTUAL paths by reading the code.
> 2. **Component responsibility**: Read the actual source file. Describe what the code DOES, not what the filename or class name suggests. A file named `Publisher.swift` might only subscribe to events. A class named `UserManager` might only read, never write. Only the code tells you which.
> 3. **API/route/endpoint methods**: Read the actual handler code. List ONLY the methods/verbs/actions that are actually implemented. Do NOT assume CRUD from the resource name — a "presets" endpoint might support GET+PUT but not POST. This applies to HTTP routes, gRPC services, GraphQL resolvers, CLI commands, or any interface.
> 4. **File placement rules**: Search the file_tree for where test files, config files, build output, and generated code actually live. Do NOT assume conventional locations — the project might put tests alongside source, in a top-level `test/` dir, or anywhere else.
> 5. **Pitfalls**: Only describe problems grounded in actual code patterns you observed. Describe what the code DOES and the risks of THAT pattern. Do NOT recommend alternatives the code doesn't use as if it does.
> 6. **Build/output paths**: Read the build config, generation logic, or Makefile to find where output is actually written. Do NOT assume any framework's default output directory.
>
> **The rule is simple: if you didn't read it in a file, don't claim it.** Focus on cross-file relationships, architecture decisions, conventions, and integration patterns. Return ONLY valid JSON.

**Spawn ALL agents in parallel.**

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 3
```

## Step 4: Save Wave 1 output and merge

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan merge
TELEMETRY_STEP4_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 4, skip this step.**

### If SCAN_MODE = "incremental":

The single incremental agent's output was saved to `/tmp/archie_incremental_$PROJECT_NAME.json` in Step 3. Patch the existing blueprint:

```bash
python3 .archie/merge.py "$PROJECT_ROOT" --patch /tmp/archie_incremental_$PROJECT_NAME.json
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 3
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 4
```

### If SCAN_MODE = "full" (default):

**If resuming via --from or --continue:** Step 4 depends on Wave 1 agent outputs in /tmp/. These may not survive a system reboot. If merge fails with missing files, re-run from step 3: `/archie-deep-scan --from 3`

**Subagent output contract (mandatory — append to each agent's prompt before spawning):**

Each Wave 1 subagent must write its own output directly to a pre-specified path. The orchestrator must NEVER copy or Write the transcript itself — attempting to access `.claude/projects/.../subagents/*.jsonl` triggers a sensitive-file permission prompt on every call.

Append this block to each Wave 1 agent's prompt, substituting `<OUTPUT_PATH>` with the path below:

```
---
OUTPUT CONTRACT (mandatory):
1. Use the Write tool to save your COMPLETE output to <OUTPUT_PATH>.
2. Write the raw output verbatim — the merge script handles JSON envelopes, code fences, and multi-block text.
3. After Writing, reply with exactly: "Wrote <OUTPUT_PATH>"
4. Do NOT print the output in your response body. /tmp/archie_* is already permissioned via Write(//tmp/archie_*).
```

Output paths per agent:
- Structure agent → `/tmp/archie_sub1_$PROJECT_NAME.json`
- Patterns agent → `/tmp/archie_sub2_$PROJECT_NAME.json`
- Technology agent → `/tmp/archie_sub3_$PROJECT_NAME.json`
- UI Layer agent (if spawned) → `/tmp/archie_sub4_$PROJECT_NAME.json`

When each subagent's confirmation reply returns, its file is already on disk — proceed directly to the merge step below. Do NOT attempt to re-extract output from the subagent's conversation — if the confirmation is missing or file absent, skip that agent's contribution and report the failure.

Then merge:

```bash
python3 .archie/merge.py "$PROJECT_ROOT" /tmp/archie_sub1_$PROJECT_NAME.json /tmp/archie_sub2_$PROJECT_NAME.json /tmp/archie_sub3_$PROJECT_NAME.json /tmp/archie_sub4_$PROJECT_NAME.json
```

This saves `$PROJECT_ROOT/.archie/blueprint_raw.json` (raw merged data). Verify the output shows non-zero component/section counts. If it says "0 sections, 0 components", the merge failed — check the agent output files.

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 4
```

## Step 5: Wave 2 — Reasoning agent

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan wave2_synthesis
python3 .archie/telemetry.py extra "$PROJECT_ROOT" wave2_synthesis model=opus
TELEMETRY_STEP5_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 5, skip this step.**

### Findings store (accumulates across all runs)

`.archie/findings.json` is a shared, compounding store — both `/archie-scan` and `/archie-deep-scan` read from it and write back to it. Each run adds new findings, upgrades existing ones (with matching `id`), confirms recurrence, or marks resolution. Scan and deep-scan are independent — neither requires the other; you can run either command any number of times in any order.

Before Wave 2:

- If `$PROJECT_ROOT/.archie/findings.json` exists, load the `findings` array and pass it to the Reasoning agent. It will upgrade the draft entries and emit additional findings it discovers.
- If the file is absent (first-ever run, or brand-new project), the Reasoning agent produces findings from scratch and Wave 2 writes the file as part of its output.

Either way, after Wave 2 the store reflects accumulated knowledge across every prior scan and deep-scan run.

### If SCAN_MODE = "incremental":

Spawn an **Opus subagent** (`model: "opus"`) with scoped context:
- The existing `$PROJECT_ROOT/.archie/blueprint.json` (full current architecture)
- The patched `$PROJECT_ROOT/.archie/blueprint_raw.json` (with incremental changes from Step 4)
- The current `$PROJECT_ROOT/.archie/findings.json` if it exists (the accumulated findings store)
- The changed file contents (from `changed_files` list)

Tell the scoped Reasoning agent:

> The architecture was previously analyzed (blueprint.json attached). The blueprint_raw.json was updated with incremental structural changes. If findings.json is present, it carries the accumulated findings from prior scan and deep-scan runs. These specific files changed: [list changed_files]. Review the changes and update ONLY the affected sections:
> - If changes affect a key decision, update it
> - If changes introduce a new trade-off or invalidate one, update trade_offs
> - If changes trigger, resolve, or modify findings/pitfalls in the changed areas, update them
> - Update the decision_chain only for affected branches
> Return ONLY the sections that need updating — unchanged sections will be preserved. Use the 4-field contract (`problem_statement`, `evidence`, `root_cause`, `fix_direction`) when writing finding or pitfall entries.

Instruct the Reasoning agent to write its own output (append to its prompt):

```
---
OUTPUT CONTRACT (mandatory):
1. Use the Write tool to save your COMPLETE output to /tmp/archie_sub_x_$PROJECT_NAME.json
2. Write the raw output verbatim — merge handles JSON envelopes.
3. After Writing, reply with exactly: "Wrote /tmp/archie_sub_x_$PROJECT_NAME.json"
4. Do NOT print the output in your response body.
```

The file will be on disk when the agent's confirmation returns. Then finalize with patch mode:
```bash
python3 .archie/finalize.py "$PROJECT_ROOT" --patch /tmp/archie_sub_x_$PROJECT_NAME.json
```
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 5
```

Then skip to Step 6.

### If SCAN_MODE = "full" (default):

Wave 1 gathered facts: components, patterns, technology, deployment, UI layer. Now spawn a single Opus subagent (`model: "opus"`) that reads ALL Wave 1 output and produces deep architectural reasoning.

Tell the Reasoning agent:

> Read `$PROJECT_ROOT/.archie/blueprint_raw.json` — it contains the full analysis from Wave 1 agents: components, communication patterns, technology stack, deployment, frontend. It may also carry a top-level `findings` array holding **draft findings from Wave 1 agents** (for example, the Structure agent's workspace-level observations — cross-workspace cycles, monorepo constraint violations). Pick those drafts up and include them in your own findings output, upgrading them to canonical (fill `root_cause` and `fix_direction`, keep their `problem_statement`/`evidence`/`applies_to`, set `depth: "canonical"`, `source: "deep:synthesis"`). Also read `$PROJECT_ROOT/.archie/findings.json` **if it exists** — it is the accumulated findings store across every prior scan and deep-scan run, each entry shaped as `{id, problem_statement, evidence, root_cause, fix_direction, depth, source, ...}`. If the file is absent, proceed without it and produce findings from scratch. Also read key source files: entry points, main configs, core abstractions.
>
> With the COMPLETE picture of what was built and how, produce deep architectural reasoning. You will upgrade any draft findings in the accumulated store, emit new findings you discover, AND emit pitfalls (classes of problem rooted in architectural decisions). Both findings and pitfalls share the same 4-field core (`problem_statement`, `evidence`, `root_cause`, `fix_direction`); pitfalls differ in altitude (class-of-problem, not instance) and ownership (blueprint-durable, not per-run).
>
> ### 1. Decision Chain
> Trace the root constraint(s) that shaped this architecture. Build a dependency tree:
> - What is the ROOT constraint? (e.g., "local-first tool requiring filesystem access")
> - What does it FORCE? (each forced decision)
> - What does EACH forced decision FORCE in turn?
> - Continue until you reach leaf decisions
> - For EACH node, include `violation_keywords`: specific code patterns or package names that would violate this decision (e.g., for "SQLite only" → `["pg", "mongoose", "prisma", "typeorm", "postgres"]`)
>
> Every decision in the chain must be grounded in code you can see in the blueprint or source files. Do NOT invent theoretical constraints.
>
> ### 2. Architectural Style Decision
> THE top-level architecture choice. You can see the full component list, pattern list, and tech stack — explain WHY this architecture, not just WHAT. Reference specific components and patterns from the blueprint.
> - **title**: e.g., "Full-stack monolith with subprocess orchestration"
> - **chosen**: What was chosen and how it manifests
> - **rationale**: WHY — reference specific components, patterns, and tech stack items from the blueprint
> - **alternatives_rejected**: What alternatives were NOT chosen and WHY they were ruled out by the constraints
>
> ### 3. Key Decisions (3-7)
>
> Before writing key decisions, run these three probes across the codebase. They surface load-bearing decisions that are often invisible to pure structural analysis (components, layers, tech stack). Each probe is **shape-based and framework-neutral** — it asks about *how* the code commits, not about any specific pattern. A probe can produce 0-N decisions; only emit what is actually present. Name each commitment in the **codebase's own vocabulary** (exact class/module/file names), not generic restatements.
>
> **Probe A — Complexity-budget:** identify every place where this codebase spends meaningful complexity on something a naive implementation of the same product wouldn't need. For each:
> - Name the commitment (in the codebase's own terms).
> - Sketch the naive alternative in one sentence.
> - What does this choice **enable** (capability unlocked)?
> - What does it **foreclose** (path closed off)?
> - Point at the specific files/modules where the commitment is implemented. If you can't, drop it.
>
> **Probe B — Invariants & gates:** locate every rule the codebase enforces on itself — anything that constrains, sequences, authorizes, versions, rate-limits, or otherwise gates other operations. For each: state the invariant in plain language, identify whether it is enforced at a single seam or scattered, and name what violates it (or where violation would slip through).
>
> **Probe C — Seams:** locate every place designed for substitution or extension — abstract interfaces with multiple concrete implementations, registry- or config-driven dispatch, protocol boundaries, plugin surfaces, hook/callback systems. For each: what **varies** across the seam, what is held **stable**, and what is the **mechanism** for adding a new implementation.
>
> **Working from Wave 1 output.** Wave 1 has already read the codebase (skeletons and, where needed, source). Run each probe primarily against `blueprint_raw.json` — specifically the `communication`, `components`, and `technology` sections, plus any raw agent output captured there. The probes are synthesis questions over Wave 1's data, not a fresh read pass.
>
> Only read source directly when Wave 1's output is genuinely insufficient to answer a probe (e.g., Wave 1 named a seam but didn't record what varies across it, or flagged a gate without naming the invariant). Judge file-by-file — no blanket re-read. If a signal clearly exists in the codebase but Wave 1's data is thin, prefer to record that as a gap in `pitfalls` (so the next scan catches more) over re-doing Wave 1's job here.
>
> **Emitting decisions.** Consolidate what the probes surface into `key_decisions` (target 3-7). Each with: title, chosen, rationale, alternatives_rejected.
> - **rationale** must reference specific components, patterns, or tech from the blueprint AND cite the concrete file/module that implements the commitment.
> - **forced_by**: what constraint or other decision made this one necessary
> - **enables**: what this decision makes possible downstream
>
> A codebase with few commitments (template apps, naive CRUD) may genuinely have only 2-3 meaningful decisions — do not invent filler. A codebase heavy in protocols, gates, and seams will have more than 7 candidates; in that case keep the most load-bearing and note the rest in `trade_offs` or `pitfalls` as appropriate.
>
> ### 4. Trade-offs (3-5)
> Each with: accept, benefit, caused_by (which decision created this trade-off), violation_signals (code patterns that would indicate someone is undoing this trade-off, e.g., removing Puppeteer → `["uninstall puppeteer", "remove puppeteer", "playwright"]`)
>
> ### 5. Out-of-Scope
> What this codebase does NOT do. For each item, optionally note which decision makes it out of scope.
>
> ### 6. Findings (primary: new; secondary: upgrade existing)
> Findings describe **instances**: concrete problems observed in specific files.
>
> **Primary goal — emit NEW findings.** You have the overall picture (all Wave 1 output plus source files). Your highest-leverage work is surfacing problems that are NOT already in findings.json — things only visible from the whole-system view: cross-component coupling, pattern breakdowns that individual agents miss, constraint violations implied by the decision chain, gaps between what the blueprint claims and what the code does. Spend the bulk of your cognitive budget here. For each new finding: next-free `f_NNNN` id, `first_seen` = today, `confirmed_in_scan` = 1, `depth: "canonical"`, `source: "deep:synthesis"`.
>
> **Novelty check before emitting.** Before you add a "new" finding, verify it is genuinely new: scan the existing store for any entry with overlapping `problem_statement` meaning OR overlapping `applies_to` files. If the same problem is already tracked under a different wording, DO NOT mint a new id — instead upgrade the existing entry (see below). A new finding must describe something the store doesn't already cover.
>
> **Secondary goal — upgrade existing drafts.** If findings.json has entries (especially `depth: "draft"` from scan:triage), upgrade them: preserve `id`, `first_seen`, `applies_to`, `evidence` (you may append new evidence). Rewrite `root_cause` with architectural grounding (name the decision, pattern, or constraint — not generic explanation) and rewrite `fix_direction` as an **ordered list of sequenced steps** referencing specific components and file paths. Set `depth: "canonical"`, `source: "deep:synthesis"`, increment `confirmed_in_scan` by 1. Upgrading is housekeeping — quick, targeted; don't re-derive evidence from scratch.
>
> Quality bar (both new and upgraded): `problem_statement` specific, `evidence` with concrete references, `root_cause` architecturally grounded, `fix_direction` sequenced and actionable. Soft floor of 3 total findings in the updated store; if fewer meet the bar, say so explicitly in your output. If the store is already comprehensive and you cannot find anything new, say "no new findings emerged from the overall-picture pass" in your output rather than restating existing ones under different ids.
>
> ### 7. Pitfalls
> Pitfalls describe **classes** of problem — architectural traps rooted in decisions or patterns, covering both current manifestations and latent risks. They are durable blueprint entries, not per-run observations. Each pitfall uses the same 4-field core as findings:
> - `id` (`pf_NNNN`, stable across runs — reuse existing ids when upgrading)
> - `problem_statement` — one sentence describing the class of problem
> - `evidence` — list of observations (cite architectural decisions, pattern recurrences across multiple findings, component absences)
> - `root_cause` — the decision/pattern/constraint making this class of problem likely
> - `fix_direction` — **ordered list** of strategic steps (migration order, seam to introduce, rule to establish)
> - `applies_to` — component/folder paths (broader than finding-level file paths)
> - `severity`, `confidence`, `source: "deep:synthesis"`, `depth: "canonical"`, `first_seen`, `confirmed_in_scan`
>
> Where a finding's `root_cause` is structural/recurring, also emit a corresponding pitfall and set the finding's `pitfall_id` to it. A single pitfall may have multiple confirming findings.
>
> **Novelty check for pitfalls.** If the blueprint already contains pitfalls, reuse their `id`s when you upgrade them (preserve `first_seen`, bump `confirmed_in_scan`). Before minting a new `pf_NNNN`, verify no existing pitfall covers the same class of problem — the store is durable across runs, and a pitfall that re-emerges under a new id loses its history. Spend your cognitive budget surfacing NEW classes of problem (architectural traps visible only from the whole-system view) rather than restating existing ones.
>
> Quality bar: only emit pitfalls whose `root_cause` traces to something visible in the blueprint (decision, pattern, component absence). Soft floor of 3; if fewer meet the bar, say so. If no new pitfalls emerged, say so explicitly rather than duplicating existing ones under new wording.
>
> Only describe problems grounded in actual code and observed decisions. Do NOT recommend alternatives the code doesn't use.
>
> ### 8. Architecture Diagram
> Mermaid `graph TD` with 8-12 nodes. You have the full component list and communication patterns from the blueprint — use actual component names and real data flows.
>
> ### 9. Implementation Guidelines (5-8)
> Capabilities using third-party libraries. Cross-reference the tech stack and pattern list from the blueprint. For each:
> - **capability**: Human-readable name
> - **category**: auth | notifications | media | storage | networking | analytics | persistence | ui | payments | location | state_management | navigation | testing
> - **libraries**: Libraries used with versions (from tech stack)
> - **pattern_description**: Architecture pattern, main service/class, data flow
> - **key_files**: Actual file paths (MUST exist in file_tree)
> - **usage_example**: Realistic code snippet. A single line is fine when the pattern genuinely is one-line (`logger.track(Event.X)`). Multi-line (typically 3-10 lines) when clarity demands it — use real newlines, not `;` chains. Show the full pattern a developer would actually write.
> - **tips**: Gotchas specific to this implementation
>
> Return JSON:
> ```json
> {
>   "decisions": {
>     "architectural_style": {"title": "", "chosen": "", "rationale": "", "alternatives_rejected": []},
>     "key_decisions": [{"title": "", "chosen": "", "rationale": "", "alternatives_rejected": [], "forced_by": "", "enables": ""}],
>     "trade_offs": [{"accept": "", "benefit": "", "caused_by": "", "violation_signals": []}],
>     "out_of_scope": [],
>     "decision_chain": {"root": "", "forces": [{"decision": "", "rationale": "", "violation_keywords": [], "forces": []}]}
>   },
>   "findings": [
>     {
>       "id": "f_NNNN",
>       "problem_statement": "",
>       "evidence": [],
>       "root_cause": "",
>       "fix_direction": ["step 1", "step 2", "step 3"],
>       "severity": "error|warn|info",
>       "confidence": 0.9,
>       "applies_to": [],
>       "source": "deep:synthesis",
>       "depth": "canonical",
>       "pitfall_id": "pf_NNNN (optional)",
>       "first_seen": "YYYY-MM-DDTHHMM",
>       "confirmed_in_scan": 1,
>       "status": "active"
>     }
>   ],
>   "pitfalls": [
>     {
>       "id": "pf_NNNN",
>       "problem_statement": "",
>       "evidence": [],
>       "root_cause": "",
>       "fix_direction": ["step 1", "step 2", "step 3"],
>       "severity": "error|warn",
>       "confidence": 0.9,
>       "applies_to": [],
>       "source": "deep:synthesis",
>       "depth": "canonical",
>       "first_seen": "YYYY-MM-DD",
>       "confirmed_in_scan": 1
>     }
>   ],
>   "architecture_diagram": "graph TD\n  A[...] --> B[...]",
>   "implementation_guidelines": [
>     {"capability": "", "category": "", "libraries": [], "pattern_description": "", "key_files": [], "usage_example": "", "tips": []}
>   ]
> }
> ```

The Reasoning agent also gets the GROUNDING RULES from Step 3.

Instruct the Reasoning agent to write its own output (append to its prompt):

```
---
OUTPUT CONTRACT (mandatory):
1. Use the Write tool to save your COMPLETE output to /tmp/archie_sub_x_$PROJECT_NAME.json
2. Write the raw output verbatim — finalize handles JSON envelopes.
3. After Writing, reply with exactly: "Wrote /tmp/archie_sub_x_$PROJECT_NAME.json"
4. Do NOT print the output in your response body.
```

After the agent's confirmation returns, finalize:

```bash
python3 .archie/finalize.py "$PROJECT_ROOT" /tmp/archie_sub_x_$PROJECT_NAME.json
```

This single command: merges the Reasoning agent's output into the blueprint, normalizes the schema, renders CLAUDE.md + AGENTS.md + rule files, installs hooks, and validates. Review the validation output — warnings are informational, not blocking.

After finalize completes, regenerate the dependency graph (the blueprint now has component definitions, which enables cross-component edge detection):

```bash
python3 .archie/detect_cycles.py "$PROJECT_ROOT" --full 2>/dev/null
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 5
```

## Step 6: AI Rule Synthesis

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan rule_synthesis
python3 .archie/telemetry.py extra "$PROJECT_ROOT" rule_synthesis model=sonnet
TELEMETRY_STEP6_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 6, skip this step.**

### If SCAN_MODE = "incremental":

The blueprint was patched in Step 5. Spawn a **Sonnet subagent** (`model: "sonnet"`) with this additional instruction prepended to the standard prompt below:

> The existing rules are in `.archie/rules.json`. Only propose rules for patterns discovered in the changed files. Do not regenerate existing rules. If a change invalidates an existing rule, flag it with `"status": "invalidated"` in the output.

### All modes (full and incremental):

The blueprint contains architectural facts. This step synthesizes them into **architectural rules** — insights that the AI reviewer uses to evaluate plans and code changes.

Spawn a **Sonnet subagent** (`model: "sonnet"`) with this prompt:

> Read `$PROJECT_ROOT/.archie/blueprint.json` ONCE (do not re-read it). It contains the full architecture: components, decisions (with decision chains and violation keywords), patterns, trade-offs (with violation signals), pitfalls (with causal chains), technology stack, and development rules.
>
> Produce 20-40 architectural rules. Each rule captures an architectural insight that a coding agent must respect when planning or making changes.
>
> **Primary enforcement is AI-powered:** the AI reviewer reads each rule's `rationale` on every plan approval and pre-commit, and evaluates whether changes violate the rule's *intent*.
>
> **Secondary enforcement is mechanical (optional):** if a rule can also be expressed as a regex, add `check` + `forbidden_patterns`/`required_in_content` fields so the pre-edit hook catches obvious violations instantly. Most rules won't have this — that's fine. Don't force regex where it doesn't fit.
>
> Return ONLY valid JSON: `{"rules": [...]}`.
>
> ## Rule schema
>
> **Required fields** (every rule):
> ```json
> {"id": "dep-001", "description": "What is forbidden/required", "rationale": "Why — the architectural reasoning chain", "severity": "error|warn"}
> ```
>
> **Prompt-time matching** (RECOMMENDED for every rule):
> - `"keywords"`: 2-5 terms an AI would use when describing a task this rule governs (e.g. `["datetime", "timestamp"]`, `["migration"]`, `["handler", "endpoint"]`). The `UserPromptSubmit` hook matches these against the user's prompt and surfaces the rule BEFORE the agent writes code. Without keywords the hook falls back to noisy description-token extraction — always emit keywords.
>
> **Optional mechanical fields** (add ONLY when a meaningful regex exists):
> - `"check"`: one of `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`, `file_naming`
> - `"applies_to"`: directory prefix (string-prefix match, NOT a glob) — e.g. `"backend/"`
> - `"file_pattern"`: glob on basename for `required_pattern` / `architectural_constraint`, OR regex on basename for `file_naming`
> - `"forbidden_patterns"`: array of regexes; rule fires if any matches the content
> - `"required_in_content"`: array of literal strings; rule fires if NONE appears in the content
>
> When `check` is present:
> - `forbidden_import`: requires `applies_to` + `forbidden_patterns`
> - `required_pattern`: requires `file_pattern` (glob) + `required_in_content`
> - `forbidden_content`: requires `forbidden_patterns`, optional `applies_to`
> - `architectural_constraint`: requires `file_pattern` (glob) + `forbidden_patterns`
> - `file_naming`: requires `applies_to` (path glob) + `file_pattern` (regex on basename)
>
> ## The `rationale` field (REQUIRED — this is the most important field)
>
> This tells the AI reviewer WHY this rule exists — the architectural reasoning chain. Write 1-3 sentences tracing the constraint back to a root decision, trade-off, or pitfall from the blueprint. Examples:
> - "We chose SQLite for the local-first constraint. Introducing any ORM or remote database would undermine the zero-config deployment model and force connection management the architecture doesn't support."
> - "ViewModels must stay framework-agnostic because the decision chain roots in testability — if a ViewModel references Android Context, it can't be unit-tested without instrumentation, which breaks the fast-feedback development loop."
> - "Feature modules are isolated to enable independent deployment. Cross-feature imports create hidden coupling that prevents releasing features independently."
>
> ## Examples
>
> Rationale-only rule with prompt-time keywords (most rules will look like this):
> ```json
> {"id": "arch-001", "description": "Business logic must not depend on UI framework classes", "rationale": "The decision chain roots in testability. Business logic that references framework classes can't be unit-tested without instrumentation, which breaks the fast-feedback loop and makes refactoring risky.", "severity": "error", "keywords": ["viewmodel", "domain", "business logic", "context"]}
> ```
>
> Rule with full mechanical enforcement AND prompt-time keywords:
> ```json
> {"id": "dep-001", "description": "Domain layer must not import from presentation layer", "rationale": "The domain is the stable core. UI depends on domain, never the reverse. Inverting this makes every UI refactor a domain change.", "severity": "error", "keywords": ["domain", "presentation", "import"], "check": "forbidden_import", "applies_to": "domain/", "forbidden_patterns": ["from presentation", "import.*\\.ui\\."]}
> ```
>
> ## What to produce:
>
> **Deep architectural rules** — invariants an AI coding agent might accidentally violate. These are the most valuable. Derive them from decision chains, trade-offs, pitfalls, and pattern descriptions. Examples: "ViewModel must never reference View/Context", "Repository must use IO dispatcher", "Fragments must use DI delegation not direct construction".
>
> **Structural rules** — dependency direction between layers/components, forbidden technologies (from decisions/trade-offs).
>
> ## Critical:
> - Every rule must be specific to THIS project — never generic programming advice
> - Focus on what an AI coding agent would get wrong without knowing this codebase
> - If you include `forbidden_patterns`, every entry must be a valid regex
> - Include an `"id"` field for each rule (e.g., "dep-001", "arch-001", "ban-001")
> - The `description` must explain WHAT is forbidden in one sentence
> - The `rationale` must explain WHY — trace it back to a decision, trade-off, or pitfall from the blueprint
> - Do NOT force mechanical fields — if the insight is "don't put orchestration logic in repositories", that's a rationale-only rule

**IMPORTANT: If `.archie/rules.json` already exists (from previous scans), read it first. The new rules must be MERGED with existing rules — do not overwrite user-adopted rules.**

Instruct the agent to write its own output (append to its prompt):

```
---
OUTPUT CONTRACT (mandatory):
1. Use the Write tool to save your COMPLETE output to /tmp/archie_rules_$PROJECT_NAME.json
2. Write the raw output verbatim — extract_output.py handles JSON envelopes.
3. After Writing, reply with exactly: "Wrote /tmp/archie_rules_$PROJECT_NAME.json"
4. Do NOT print the output in your response body.
```

After the agent's confirmation returns, extract:

```bash
python3 .archie/extract_output.py rules /tmp/archie_rules_$PROJECT_NAME.json "$PROJECT_ROOT/.archie/rules.json"
```

**IMPORTANT: Do NOT try to extract or parse JSON yourself. Do NOT copy the agent's transcript. Always use the pre-installed scripts on the file the agent already wrote.**

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 6
```

---

### ✓ Compact Checkpoint A — before Intent Layer

**This is the highest-leverage compaction point in the whole pipeline.** Steps 1–6 are fully persisted (blueprint, findings, pitfalls, rules, proposed_rules, telemetry marks). Wave 1 subagent transcripts, Wave 2 Opus synthesis, and Rule Synthesis are redundant with the disk state — holding them in conversation context is pure waste for the massive Intent Layer pass that follows (which spawns one Sonnet subagent per folder batch).

If the orchestrator's context is over ~70%, pause here, run `/compact`, and resume with `/archie-deep-scan --continue`. The Resume Prelude reads `deep_scan_state.json` (last_completed=6) and jumps straight to Step 7 after rehydrating shell vars from the persisted run_context.

Skipping this checkpoint is safe — auto-compact will fire if needed — but compacting here is strictly cheaper and cleaner.

---

## Step 7: Intent Layer — per-folder CLAUDE.md

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan intent_layer
python3 .archie/telemetry.py extra "$PROJECT_ROOT" intent_layer model=sonnet skipped=false
TELEMETRY_STEP7_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 7, skip this step.**

**If `INTENT_LAYER=no` (user opted out in Step E), skip this entire step.** Print a one-line note to the user: *"Intent Layer skipped (no per-folder CLAUDE.md generated). Root CLAUDE.md + rule files still written. You can run `/archie-intent-layer` later if you change your mind."* Then proceed to Step 8. The `intent_layer` telemetry step will record zero elapsed time (its `started_at == completed_at`) and carry `"skipped": true` (see Step 10).

**If `INTENT_LAYER=yes`, execute this step fully. Do NOT ask the user whether to run, skip, or reduce scope. Do NOT offer alternatives. Run all batches as instructed below.**

### Shared pipeline

**This step runs the exact same pipeline as the standalone `/archie-intent-layer` command.** The canonical description lives there (Phases 1–4): prepare the DAG → loop `next-ready` / `suggest-batches` / Sonnet subagent per batch / `save-enrichment` → `merge` enrichments into per-folder CLAUDE.md files.

**Load the canonical prose into context before starting** — slash-command bodies are not cross-loaded automatically, so you must Read the file yourself:

```
Read .claude/commands/archie-intent-layer.md
```

Then execute Phases 1–4 from that file, using `PROJECT_ROOT` in place of `$PWD`, with the deep-scan-specific deltas below layered on top. Do NOT reinterpret or re-derive the pipeline logic — follow what the file says.

### Deep-scan-specific deltas

1. **Skip the precondition check (Phase 0).** The blueprint was just produced in Steps 5–6, so the hard-requirement check in `/archie-intent-layer` Phase 0 is a no-op in this context. Do not re-run it.

2. **Auto-resume when this deep-scan itself is resuming.** If the Preamble set `RESUME_ACTION=resume` (from `--continue`, `--from N`, or the user picking "Resume" at the bare-invocation prompt), pass `RESUME_INTENT=continue` to the Intent Layer. Phase 0.25 in the intent-layer skips its own reconciliation prompt and auto-resumes from the on-disk done list.

   For fresh deep-scan runs (`RESUME_ACTION=fresh`), pass `RESUME_INTENT=ask`. Phase 0.25 will either see no partial state (the Preamble's Fresh-start path already reset it) or — in the rare case where enrichments survived the reset — ask the user. The Fresh-start path in the Preamble explicitly resets enrich_state + enrichments/, so this should be a no-op in practice.

3. **Skip the mode selector (Phase 0.5).** The deep-scan already decided `SCAN_MODE` in its own preamble — don't ask the user again. In Phase 1 of `/archie-intent-layer`, treat `MODE=incremental` as equivalent to `SCAN_MODE=incremental`, and `MODE=full` as `SCAN_MODE=full`.

3. **SCAN_MODE = "incremental" → pass `--only-folders`.** When the preamble set `SCAN_MODE=incremental`, the Phase 1 `prepare` call becomes:

   ```bash
   python3 .archie/intent_layer.py prepare "$PROJECT_ROOT" --only-folders AFFECTED_FOLDER1,AFFECTED_FOLDER2,...
   ```

   Use the comma-separated `affected_folders` list from the detect-changes output you captured earlier in the deep-scan run. `next-ready` will then only return dirty folders and their ancestors — waves will be much smaller than a full scan.

3. **Batch-processing compact checkpoint.**

   **✓ Compact Checkpoint B** — between Intent Layer waves. After every wave's `save-enrichment` commands have all returned (so no subagent is in flight and all completed folders are persisted in `enrich_state.json`), this is a safe compaction boundary. Suggested frequency: every 3 waves when the project has >20 folders. On small projects (<20 folders) ignore this checkpoint. Procedure: `/compact` → `/archie-deep-scan --continue` → Resume Prelude sees `last_completed=6` and re-enters Step 7, which calls `next-ready` and resumes from the next wave using disk state alone.

4. **Mark step complete at the end.** After Phase 3 (`merge`) and Phase 4 (cleanup) of the standalone command, record completion:

   ```bash
   python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 7
   ```

---

### ✓ Compact Checkpoint C — after Intent Layer

Only meaningful when `INTENT_LAYER=yes`. Step 7 has just pushed dozens-to-hundreds of Sonnet subagent transcripts into conversation context; those are now fully persisted to `.archie/enrichments/*.json` and merged into per-folder `CLAUDE.md` files. Compacting here gives Step 9 (Drift Assessment) a fresh context, which matters because drift assessment reads blueprint + drift_report + CLAUDE.md files and benefits from focused attention.

If `INTENT_LAYER=no` (opted out in Step E), skip this checkpoint — Checkpoint A already covered it.

Procedure when firing: `/compact` → `/archie-deep-scan --continue` → Resume Prelude sees `last_completed=7` and jumps to Step 8 (Cleanup is cheap, so continuing through 8→9 in a fresh context costs nothing).

---

## Step 8: Clean up

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan cleanup
TELEMETRY_STEP8_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 8, skip this step.**

```bash
rm -f /tmp/archie_sub*_$PROJECT_NAME.json /tmp/archie_rules_$PROJECT_NAME.json /tmp/archie_intent_prompt_$PROJECT_NAME.txt /tmp/archie_enrichment_*.json
```

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 8
```

## Step 9: Drift Detection & Architectural Assessment

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan drift
TELEMETRY_STEP9_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 9, skip this step.**

### Phase 0: Health measurement

```bash
python3 .archie/measure_health.py "$PROJECT_ROOT" > "$PROJECT_ROOT/.archie/health.json" 2>/dev/null
```

Save health scores to history for trending:

```bash
python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history --scan-type deep
```

### Phase 1: Mechanical drift scan

```bash
python3 .archie/drift.py "$PROJECT_ROOT"
```

### Phase 2: Deep architectural drift (AI)

Identify files to analyze:
```bash
git -C "$PROJECT_ROOT" log --name-only --pretty=format: --since="30 days ago" -- '*.kt' '*.java' '*.swift' '*.ts' '*.tsx' '*.py' '*.go' '*.rs' | sort -u | head -100
```
If that returns nothing (new repo or no recent changes), use all source files from the scan:
```bash
python3 .archie/extract_output.py recent-files "$PROJECT_ROOT/.archie/scan.json"
```

For each file (batch into groups of ~15), collect:
- The file's content
- Its folder's CLAUDE.md **if it exists** (per-folder patterns, anti-patterns — these were generated in Step 7, but may be missing if Step 7 was skipped or partially completed)
- Its parent folder's CLAUDE.md **if it exists**

Read `$PROJECT_ROOT/.archie/blueprint.json` — specifically `decisions.key_decisions`, `decisions.decision_chain`, `decisions.trade_offs` (with `violation_signals`), `pitfalls` (with `stems_from`), `communication.patterns`, `development_rules`.

Read `$PROJECT_ROOT/.archie/drift_report.json` (mechanical findings from Phase 1).

Spawn a **Sonnet subagent** (`model: "sonnet"`) with the file contents, their folder CLAUDE.md files, and the blueprint context. Tell it:

> You are an architecture reviewer. You have the project's architectural blueprint (decisions, trade-offs, pitfalls, patterns), per-folder CLAUDE.md files describing expected patterns, mechanical drift findings (already detected), and source files to review.
>
> Find **deep architectural violations** — problems that pattern matching cannot catch. For each finding, return:
> - `folder`: the folder path
> - `file`: the specific file
> - `type`: one of `decision_violation`, `pattern_erosion`, `trade_off_undermined`, `pitfall_triggered`, `responsibility_leak`, `abstraction_bypass`, `semantic_duplication`
> - `severity`: `error` or `warn`
> - `decision_or_pattern`: which architectural decision, pattern, or pitfall this violates (reference by name from the blueprint)
> - `evidence`: the specific code (function name, class, line pattern) that demonstrates the violation
> - `message`: one sentence explaining what's wrong and why it matters
>
> Focus on:
> 1. **Decision violations** — code that contradicts a key architectural decision
> 2. **Pattern erosion** — code that doesn't follow the patterns described in its folder's CLAUDE.md
> 3. **Trade-off undermining** — code that works against an accepted trade-off (check `violation_signals`)
> 4. **Pitfall triggers** — code that falls into a documented pitfall (check `stems_from` chains)
> 5. **Responsibility leaks** — a component doing work that belongs to another component
> 6. **Abstraction bypass** — code reaching through a layer instead of using the intended interface
> 7. **Semantic duplication** — functions/methods with different signatures but essentially the same logic. AI agents frequently copy-paste a function, tweak the name/parameters, and leave the body identical or near-identical. Look for: functions with similar names (e.g., `getText`/`getTexts`, `loadUser`/`fetchUser`), functions in different files that do the same thing with slightly different types, helper functions reimplemented instead of shared. For each, use type `semantic_duplication` and explain what's duplicated and which function should be the canonical one.
>
> Do NOT report: style/formatting/naming (the script handles those), generic best-practice violations not grounded in THIS project's blueprint, or issues already in the mechanical drift report.
>
> Return JSON: `{"deep_findings": [...]}`

Instruct the reviewer subagent to write its own output (append to its prompt):

```
---
OUTPUT CONTRACT (mandatory):
1. Use the Write tool to save your COMPLETE output to /tmp/archie_deep_drift.json
2. Write the raw output verbatim — extract_output.py handles JSON envelopes.
3. After Writing, reply with exactly: "Wrote /tmp/archie_deep_drift.json"
4. Do NOT print the output in your response body.
```

After the agent's confirmation returns, extract and clean up:

```bash
python3 .archie/extract_output.py deep-drift /tmp/archie_deep_drift.json "$PROJECT_ROOT/.archie/drift_report.json"
rm -f /tmp/archie_deep_drift.json
```

### Phase 3: Present the combined assessment

Read `$PROJECT_ROOT/.archie/blueprint.json` and `$PROJECT_ROOT/.archie/drift_report.json` (now contains both mechanical and deep findings). This is the final output — make it valuable.

#### Part 1: What was generated

List the generated artefacts with counts:
- Blueprint sections populated (out of total)
- Components discovered
- Enforcement rules generated
- Per-folder CLAUDE.md files created
- Rule files in `.claude/rules/`

#### Part 2: Architecture Summary

From the blueprint, summarize in 5-10 lines:
- **Architecture style** (from `meta.architecture_style`)
- **Key components** (top 5-7 from `components.components` — name + one-line responsibility)
- **Technology stack highlights** (from `technology.stack` — framework, language, key libs)
- **Key decisions** (from `decisions.key_decisions` — the 2-3 most impactful, one line each)

#### Part 3: Architecture Health Assessment

Rate and explain each dimension (use these exact labels: Strong / Adequate / Weak / Not assessed):

1. **Separation of concerns** — Are layers/modules clearly bounded? Do components have single responsibilities? Any god classes or circular dependencies?
2. **Dependency direction** — Do dependencies flow in one direction? Are domain/core layers independent of infrastructure? Any inverted or tangled dependencies?
3. **Pattern consistency** — Is the same pattern used consistently across similar components? Are there one-off deviations that break the uniformity?
4. **Testability** — Is the architecture conducive to testing? Can components be tested in isolation? Are external dependencies injectable?
5. **Change impact radius** — When a component changes, how many others are affected? Are changes localised or do they ripple?

Base every rating on actual evidence from the blueprint and drift findings — reference specific components, patterns, or findings. If the blueprint lacks data for a dimension, say "Not assessed" rather than guessing.

#### Part 4: Architectural Drift

Present ALL findings — mechanical and deep together, organized by severity (errors first).

**Deep architectural findings** (from AI analysis):
- For each: the file, which decision/pattern it violates, the evidence, and why it matters
- Group related findings (e.g., multiple files violating the same decision)

**Mechanical findings** (from script):
- Pattern divergences, dependency violations, naming violations, structural outliers, anti-pattern clusters
- For each: what diverged, why it matters, suggested action

If 0 findings, say so — that's a positive signal.

#### Part 5: Top Risks & Recommendations

Synthesize from pitfalls, trade-offs, drift findings (both mechanical and deep), and your observations. List the **3-5 most important architectural risks**, ordered by impact:
- What the risk is (one sentence)
- Where it manifests (specific components/files/drift findings)
- What to watch for going forward

#### Part 6: Semantic Duplication

**This is a critical section.** The mechanical verbosity score (0-1) only catches exact line-for-line clones. AI agents frequently create near-identical functions with slightly different names, signatures, or types — the verbosity metric completely misses these.

Present the `semantic_duplication` findings from the deep drift analysis. If the drift agent found none, **do your own quick check now**: scan the skeletons for functions with similar names (e.g., `getText`/`getTexts`, `loadUser`/`fetchUser`, `formatDate` in multiple files, `handleError` reimplemented per-module). Read suspicious pairs and confirm whether the logic is duplicated.

For each confirmed duplicate group:
- The canonical function (the one that should be the shared version)
- The duplicates: which files, what differs (just the signature? types? minor logic?)
- Whether they could be consolidated

Present in the health table as:
```
| Semantic duplication | N groups found | See Part 6 for details |
```

If genuinely none found after checking, say "No semantic duplication detected after AI analysis."

**Health scores** from Phase 0 have been saved to `.archie/health_history.json` for trending. Note: the verbosity metric is mechanical (exact line clones only) — the semantic duplication analysis in Part 6 above is the AI-powered complement. Run `/archie-scan` regularly to track how these metrics change over time.

### Phase 4: Persist findings to `.archie/scan_report.md`

The Phase 3 synthesis above is valuable but ephemeral — it only exists in the chat output. `/archie-share` (and future trending runs of `/archie-scan`) need the findings on disk. Write the same content to `.archie/scan_report.md` in the format `/archie-scan` produces.

Check whether a prior scan report exists (for resolved/new/recurring classification):
```bash
test -f "$PROJECT_ROOT/.archie/scan_report.md" && echo "PRIOR_REPORT_EXISTS" || echo "FIRST_BASELINE"
```

If `FIRST_BASELINE` (no prior scan_report.md): all findings are tagged **NEW (baseline)**. If `PRIOR_REPORT_EXISTS`: compare against the prior file's Findings section and classify each as **NEW**, **RECURRING**, or **RESOLVED**.

Read `$PROJECT_ROOT/.archie/health.json` for precise numeric values and `$PROJECT_ROOT/.archie/health_history.json` to compute trends (previous run values vs. current).

Write `$PROJECT_ROOT/.archie/scan_report.md` with this exact structure (use the Write tool, do NOT shell-heredoc):

```markdown
# Archie Scan Report
> Deep scan baseline | <today's date in YYYY-MM-DD HH:MM UTC> | <total_functions> functions / <total_loc> LOC analyzed | baseline run

## Architecture Overview

<2-3 paragraphs from Part 2: architecture style, key components, most important decisions. Prose, not bullets.>

## Health Scores

| Metric | Current | Previous | Trend | What it means |
|--------|--------:|---------:|------:|---------------|
| Erosion    | <erosion>    | <prev or "—"> | <up/down/flat> | <one-liner interpretation> |
| Gini       | <gini>       | <prev or "—"> | <trend> | <one-liner> |
| Top-20%    | <top20>      | <prev or "—"> | <trend> | <one-liner> |
| Verbosity  | <verbosity>  | <prev or "—"> | <trend> | <one-liner> |
| LOC        | <total_loc>  | <prev or "—"> | <trend> | <one-liner> |

<one paragraph summarizing what the numbers say together>

### Complexity Trajectory
<short list of the top 5-8 high-CC functions from health.json with file:line and CC values, and what they suggest about risk concentration>

## Findings

Ranked by severity, grouped by novelty.

### NEW (first observed this scan)
<numbered list of findings — each: **[severity] Title.** Description. Confidence N.>

### RECURRING (previously documented, still present)
<only if prior report exists; otherwise omit this subsection>

### RESOLVED
<only if prior report exists; otherwise omit. "None" if nothing resolved.>

## Proposed Rules

<Any new rules proposed by Step 6 synthesis that are not yet in rules.json. Reference proposed_rules.json.>
```

Sources for Findings:
- `drift_report.json` — mechanical and deep drift findings from Phase 1 and 2
- `blueprint.json` — `pitfalls` (each causal chain becomes a finding), `decisions.trade_offs` with violated `violation_signals` (if any appear in drift_report)
- Top complexity offenders from `health.json` (only if CC ≥ 15 or a cluster — don't list every high-CC function as a finding)

Severity mapping:
- `error` — decision violations, inverted dependencies, cycles across architectural boundaries
- `warn` — pattern erosion, god-objects, pitfalls currently manifesting, trade-offs actively undermined
- `info` — structural observations (dependency magnets, high fan-in nodes) that aren't currently broken

Confidence: carry forward from drift findings when available; otherwise use 0.8-0.95 for findings grounded in direct code reading, lower for inferred ones.

Verify the write:
```bash
test -s "$PROJECT_ROOT/.archie/scan_report.md" && wc -l "$PROJECT_ROOT/.archie/scan_report.md"
```

Expected: non-empty file with at least 30 lines.

```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" complete-step 9
```

Save baseline marker for future incremental runs (use "full" or "incremental" based on SCAN_MODE):
```bash
python3 .archie/intent_layer.py deep-scan-state "$PROJECT_ROOT" save-baseline SCAN_MODE
```
(Replace SCAN_MODE with the actual mode — "full" or "incremental")

End with: **"Archie is now active. Architecture rules will be enforced on every code change. Run `/archie-scan` for fast health checks. Run `/archie-deep-scan --incremental` after code changes to update the architecture analysis."**

## Step 10: Write telemetry

Each prior step persisted its start timestamp to `.archie/telemetry/_current_run.json` via `telemetry.py mark` — so the final writer reads entirely from disk (no shell variables required, no /tmp timing file to assemble). This is what makes mid-run `/compact` safe: even if the orchestrator's conversation was compacted, every step's timing is on disk.

If the Intent Layer was skipped (INTENT_LAYER=no), mark it so explicitly:

```bash
if [ "$INTENT_LAYER" = "no" ]; then
  python3 .archie/telemetry.py extra "$PROJECT_ROOT" intent_layer skipped=true
fi
```

Then flush the in-flight file into the final `.archie/telemetry/deep-scan_<timestamp>.json`:

```bash
python3 .archie/telemetry.py finish "$PROJECT_ROOT"
python3 .archie/telemetry.py write  "$PROJECT_ROOT"
```

`write` auto-closes any still-open step with `now`, emits the final timestamped JSON, then deletes `_current_run.json` so the next deep-scan starts fresh. If telemetry fails for any reason, do not abort — telemetry is informational only.

**Legacy fallback:** the old `/tmp/archie_timing.json` + `telemetry.py <root> --command … --timing-file …` invocation still works for any downstream tool that expects it, but the disk-persisted flow above is the compaction-safe canonical path.

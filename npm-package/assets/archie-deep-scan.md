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
> ### 9. Pattern preconditions (REQUIRED — do not skip)
>
> A pattern that "looks right" in one part of a codebase may silently break in another part that has the same call shape but a different invariant (e.g. an advisory lock keyed on `(namespace, X)` where the schema's index on `(namespace, X)` is unique in one entity but non-unique in another — the same call serializes unrelated rows in the second case). The defense is to make the precondition explicit and code-grounded.
>
> For each pattern that depends on a structural invariant (schema constraint, type-system guarantee, lifecycle state, ownership rule, concurrency primitive, structural contract), populate:
>
> - `applicable_when`: the **verifiable invariant** that makes this pattern correct in THIS codebase. MUST cite a concrete code artifact at `<file>:<line>` — pick whichever invariant shape fits the language and paradigm. Common shapes:
>   - **Schema annotation:** a unique/foreign-key/NOT-NULL/index constraint that the pattern relies on
>   - **Type signature:** a function returning Result/Option/Either; an exhaustive enum or sealed type; a generic bound that constrains callers
>   - **Lifecycle / framework state:** a hook called under a required Provider; a handler registered before bus start; a composable inside a known scope
>   - **Ownership / concurrency:** borrow scope, lock-held interval, transaction-active context
>   - **Structural:** single registration point + iterating consumer; sealed hierarchy + exhaustive match; conventional placement enforced by build/lint config
>   The requirement is that the citation is **falsifiable against the corpus**, not the invariant *shape*. Do NOT use prose like "per-customer", "per-user", "in the auth flow" — those pattern-match across contexts where the invariant doesn't hold.
>
>   **Empty by default — fill ONLY when misapplying the pattern in a context where the cited invariant does NOT hold would produce silently incorrect code.** That's the openmeter lockr test: cited `(namespace, customerID)` UNIQUE index ⇒ applying to a non-unique key silently serializes unrelated rows. The failure mode is articulable in one sentence and verifiable by reading the cited file:line.
>
>   **REQUIRED SHAPE — category-then-evidence, never raw description.** The predicate must name the **class of callers, components, or situations** the invariant guards or excludes — a categorical noun phrase a future agent can pattern-match against an unfamiliar component. The citation grounds the category by showing where the invariant is declared (or where it would be violated for `do_not_apply_when`); the citation does NOT replace the category. Read every entry as: `<categorical predicate> — <file:line>: <evidence that the predicate holds / fails here>`. If you can substitute any other component name into the predicate and the sentence still parses meaningfully, the shape is right; if it only makes sense about ONE specific file, you wrote trivia, not a rule.
>
>   **Reject these as `applicable_when` (leave empty instead) — they read as fuzzy circular text:**
>     - **Pattern-name restatements**: e.g. *"A class needs to receive a dependency without constructing it directly"* (= "use DI when you want DI"); *"A feature is locked behind the 'pro' entitlement and you need to render the gated UI"* (= "use Pro gating when you want to gate by Pro"); *"Any user-facing string"* (= "use the i18n system for all strings"). Restating `when_to_use` adds nothing.
>     - **Use-case lists masquerading as preconditions**: e.g. *"A service must react to whole-app foreground/background — GPS start/stop, analytics events, RevenueCat refresh"* — that's enumerating consumers, not stating an invariant.
>     - **"Any X" universals**: e.g. *"Any ViewModel that participates in Loading/Success state"* — if the answer to "when does this apply?" is "everywhere this kind of thing exists," it's not a precondition.
>     - **Recipe pointers**: e.g. *"The destination Fragment is registered in navigation_main.xml"* (without that, the recipe doesn't even compile — it's not a precondition, it's a step). Citing a registration site is OK ONLY if there's a real misapplication failure mode tied to that site.
>     - **Per-instance trivia masquerading as a category** (the most common failure mode — read this carefully): a description of what ONE specific file does, with a citation tacked on. The citation is concrete, but the predicate names a single entity instead of a class of cases, so a reader looking at any other file cannot decide whether the rule applies.
>       *BAD:* *"BabyWeatherAnalyticsManager uses an internal AtomicBoolean singleton and its own initialize() — exposed through analyticsModule but not constructed via Koin injection."* — true, falsifiable, useless. It's a fact about one file, not a category. A new component reading this can't ask "do I match?" because the predicate is the entity itself.
>       *GOOD (same content, categorical shape):* *"Component manages its own initialization lifecycle (manual `initialize()` outside DI; Koin only exposes the already-built instance) — `BabyWeatherAnalyticsManager` (analyticsModule) and `LocalisationHelper` (`DomainModules.kt:18-21`) both follow this shape."* The predicate is now a class of cases ("manages its own init lifecycle"); the citations are evidence the class is real in the corpus. Any future component asking "is my init lifecycle DI-managed?" can answer.
>
>   **Fill applicable_when when there's a real boundary** — patterns where one type of consumer must use this and another type must NOT. Citing `APIService.kt:13 declares @Header("Authorization")` works because anonymous endpoints (which lack that header) MUST NOT route through `tokenCheck` — applying it would block public calls behind auth. That's the openmeter shape.
>
> - `do_not_apply_when`: array of concrete anti-indicators. Each entry follows the same **category-then-evidence** shape as `applicable_when`: lead with a categorical noun phrase describing the kind of caller/context where the pattern misapplies, then back it with a citation. Each MUST be falsifiable against schema/code. Include any places in the corpus where the same shape is used WITHOUT the invariant holding — those are the real-world `do_not_apply_when` anchors. Reject the same per-instance trivia shape: *"`FooManager` does X in `Foo.kt:42`"* without a class of cases is a fact, not a rule.
>
> - `scope`: array of component names from `components.components[].name` where this pattern is **relevant when editing** — including producers, consumers, and boundary participants, NOT just where the source file lives. Example: a registry pattern defined in component `core` but consumed by `feature-A` and `feature-B` has scope `["core", "feature-A", "feature-B"]`. Empty array means "applies repo-wide". **Conservative default:** if uncertain, leave `[]` — the rule loads everywhere (no regression vs. today). Only narrow scope when there is verifiable evidence the pattern is component-bound.
>
> For **generic** patterns (REST, WebSocket, Event Bus, generic logging) where no codebase-specific invariant applies, leave `applicable_when` as `""`, `do_not_apply_when` as `[]`, `scope` as `[]`. Do NOT invent preconditions.
>
> **Two illustrative examples** — each grounds `applicable_when` in a different invariant shape, to show the field is paradigm-agnostic. Pick whichever shape fits the codebase you are analyzing; do not force a schema annotation if there is no schema. Placeholder paths (`<schema>/<entity>.<ext>`, `<domain-A>`) are shown to keep these examples language-neutral — substitute concrete files and components for the actual codebase.
>
> *Example 1 (lifecycle / framework state — typical for UI codebases):*
> ```json
> {
>   "name": "Context-backed session hook",
>   "when_to_use": "Read the current user inside any component below the root provider",
>   "how_it_works": "useSession() reads from a context populated by SessionProvider; provider hydrates from cookie on mount",
>   "examples": ["src/auth/use-session.<ext>", "src/auth/provider.<ext>"],
>   "applicable_when": "src/app/layout.<ext>:14 wraps the entire tree in <SessionProvider> — the hook is therefore safe to call from any descendant client component",
>   "do_not_apply_when": ["Caller is a server component or middleware — context is unavailable; the server-side equivalent (e.g. getServerSession) is the correct API", "Test renders the component in isolation without SessionProvider — context is null and the hook throws"],
>   "scope": []
> }
> ```
>
> *Example 2 (schema-bound — typical for DB-backed services):*
> ```json
> {
>   "name": "Per-key advisory lock",
>   "when_to_use": "Serialize concurrent mutations of the same logical entity",
>   "how_it_works": "Acquire a database advisory lock keyed on (namespace, entityID) inside a transaction; lock auto-releases on commit/rollback",
>   "examples": ["<lib>/lock.<ext>", "<domain>/service/write.<ext>"],
>   "applicable_when": "<schema>/<entity>.<ext>:<line> declares a UNIQUE index on the lock-key columns — the (namespace, entityID) tuple maps to at most one row in the locked entity's table",
>   "do_not_apply_when": ["Schema index for the proposed key is NOT unique — multiple rows can legitimately share the key, so a single advisory lock would serialize unrelated rows", "Operation mutates one row only — built-in row-level locking (e.g. SELECT FOR UPDATE) suffices, no cross-row invariant to protect"],
>   "scope": ["<domain-A>", "<domain-B>"]
> }
> ```
>
> Both shapes are valid. The requirement isn't a specific invariant *type* — it's that the citation lets a reader verify the precondition by looking at the cited code.
>
> Return JSON:
> ```json
> {
>   "communication": {
>     "patterns": [
>       {"name": "", "when_to_use": "", "how_it_works": "", "examples": [], "applicable_when": "", "do_not_apply_when": [], "scope": []}
>     ],
>     "integrations": [
>       {"service": "", "purpose": "", "integration_point": ""}
>     ],
>     "pattern_selection_guide": [
>       {"scenario": "", "pattern": "", "rationale": ""}
>     ]
>   },
>   "quick_reference": {
>     "pattern_selection": [
>       {"scenario": "", "pattern": "", "scope": []}
>     ],
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
> ### 6. Development Rules + Infrastructure Rules
>
> Two SEPARATE output buckets. Each rule belongs in exactly one. The split is load-bearing — `development_rules` is what a coding agent reads at edit-time; `infrastructure_rules` is onboarding/ops info that the same agent never consults when writing code. Mixing them buries the coding rules in noise.
>
> #### `development_rules` — coding-time rules
>
> Rules a coding agent must follow when **writing, editing, or refactoring** code in this project. Each must answer at least one of:
> - "When I add a new <thing> (screen, repository, route, module), what must I do?"
> - "When I touch <area>, what must I avoid?"
> - "What boundary must I respect when changing <component>?"
>
> **Inclusion test:** would a coding agent change the file it's editing because of this rule? If no, it does NOT belong here — push it to `infrastructure_rules`.
>
> **Source priority:** actual code files first (real `.kt`, `.swift`, `.py`, `.ts` etc., the patterns visible there). Config files only when they map directly to a coding-time decision (e.g. a Gradle plugin that requires registering Fragments in NavGraph IS a coding rule; a CI YAML telling you which gradle tasks to run is NOT).
>
> Categories:
> - `pattern_to_follow` — a positive convention visible in existing code
> - `anti_pattern` — a thing the codebase carefully AVOIDS
> - `boundary` — a layer/module separation that must hold
> - `wiring` — what to register/connect when adding a feature (DI, navigation, routing, plugins)
> - `data_flow` — how data moves and where to plug in
>
> GOOD examples:
> - "Always extend TraceViewModel<T> for screen ViewModels — gives Firebase Performance traces per loading cycle" (source: util/perf/TraceViewModel.kt; usage: DashboardViewModel, SettingsViewModel)
> - "Always register new Fragments in res/navigation/navigation_main.xml and use Safe Args (navArgs() delegates) for type-safe nav arguments" (source: app/build.gradle.kts safeArgsPlugin + DashboardFragmentArgs)
> - "Never import from infrastructure/ in domain/ — dependency rule enforced by layer structure" (source: directory layout, no existing violations)
>
> BAD examples (push to infrastructure_rules instead):
> - "Always run `assemble{BuildType} cleanTestDebugUnitTest` in CI" — CI orchestration
> - "Always store keystores as Azure DevOps secure files named …" — signing infra
> - "Never commit local.properties" — onboarding gotcha, not coding rule
>
> #### `infrastructure_rules` — ops / build / onboarding
>
> Rules and gotchas about CI, distribution, signing, secrets, env setup, branch protection, dependency-registry auth — the kind of thing a developer needs to know once during onboarding or when touching pipelines / build configs, but not when writing a feature.
>
> Categories:
> - `ci_cd` — CI orchestration, pipeline triggers, mandatory tasks
> - `distribution` — App Store, Play Store, AppCenter, npm publish, etc.
> - `signing` — keystores, certificates, code-signing identities
> - `secrets` — env vars, secret-file conventions, `.gitignore` of sensitive paths
> - `env_setup` — `.env` files, local-only files, dev-machine prereqs
> - `dependency_registry` — auth to private registries (e.g. GitHub Packages, internal Artifactory), JitPack/private Maven repos
> - `git` — branch protection, PR-trigger conventions, commit hooks
>
> Every rule MUST cite its source file. State each as "Always X" or "Never Y".
>
> **CRITICAL**: Both buckets must be specific to THIS project. Generic rules are WORTHLESS in either bucket.
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
>     {"category": "pattern_to_follow|anti_pattern|boundary|wiring|data_flow", "rule": "Always/Never ...", "source": "file_that_proves_it"}
>   ],
>   "infrastructure_rules": [
>     {"category": "ci_cd|distribution|signing|secrets|env_setup|dependency_registry|git", "rule": "Always/Never ...", "source": "file_that_proves_it"}
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

## Step 3: Spawn analytical agents

**Telemetry:**
```bash
python3 .archie/telemetry.py mark "$PROJECT_ROOT" deep-scan wave1
python3 .archie/telemetry.py extra "$PROJECT_ROOT" wave1 model={{ANALYSIS_MODEL}}
TELEMETRY_STEP3_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

**If START_STEP > 3, skip this step.**

### If SCAN_MODE = "incremental":

Spawn a **single {{ANALYSIS_MODEL}} subagent** with:
- The `changed_files` list (from detect-changes output in preamble)
- The existing `.archie/blueprint_raw.json`
- Skeletons for changed files only (read `.archie/skeletons.json`, filter to only keys matching changed file paths)
- The scan.json import graph

**Before dispatch — assign the subagent's output path and append the output
contract to its prompt.** The "file path named above" in the contract is
`.archie/tmp/archie_incremental_$PROJECT_NAME.json`.

The subagent's prompt is the agent body below, followed by a blank line,
followed by:

```
---
OUTPUT CONTRACT (mandatory):
{{>output_contract}}
```

Agent prompt:
> You have the existing architectural blueprint and a list of files that changed since the last analysis. Read the changed files and their context. Report what changed architecturally:
> - New or modified components (name, location, responsibility, depends_on)
> - Changed communication patterns or integrations
> - New technology or dependencies
> - Modified file placement patterns
> - New or changed product invariants (`domain_invariants[*]`) — behavioral laws the changed files add, alter, or remove (balance bounds, lifecycle immutability, idempotency, tenant scoping). Cite `enforced_at` for each, same cite-or-omit discipline as the full Domain agent. Omit when no changed file touches an enforced law.
>
> Return the same JSON structure as the full analysis but ONLY for sections affected by the changes. Omit unchanged sections — they'll be preserved from the existing blueprint.
>
> GROUNDING RULES apply (see below).

{{>dispatch_single}}

Then skip to Step 4.

### If SCAN_MODE = "full" (default):

Spawn 3–6 {{ANALYSIS_MODEL}} subagents in parallel, each focused on a different analytical concern. ALL agents read ALL source files under `$PROJECT_ROOT` — they are not split by directory. Each agent gets: the scan.json file_tree, dependencies, config files, and the GROUNDING RULES at the end of this step.

**The five core agents — Structure, Patterns, Technology, Data, Domain — ALWAYS spawn.** They are NOT gated on any heuristic. Data inventories the data layer; Domain extracts the product's behavioral invariants; both feed the later steps (merge → blueprint → rules) on every run. A repo with no data surface simply yields an empty `data_models` / `domain_invariants` array — a valid result, never a reason to skip the agent. (`has_persistence_signal` is no longer a spawn gate; it survives only as an informational hint inside the Data/Domain prompts.)

**Conditional agents:**
- **UI Layer** — the ONLY optional Wave 1 agent. Spawn when `frontend_ratio >= 0.20`; otherwise skip.

A backend service gets the five core agents; a full-stack app gets all six.

**When `DEPTH=comprehensive`, also spawn the UI Layer agent regardless of `frontend_ratio` — the five core agents already always run.**

**Bulk content — off-limits for reading.** `scan.json.bulk_content_manifest` lists files classified by `.archiebulk` as "visible inventory, not contents": categories like `ui_resource` (Android `res/`, iOS storyboards), `generated`, `localization`, `migration`, `fixture`, `asset`, `lockfile`, `dependency`, `data`. Every agent below inherits this rule: **you may reference these paths by name and inventory counts, but you MUST NOT call Read on them.** The scanner has already summarized their shape. If a specific file is genuinely required to resolve a finding, read it surgically and note why — it is an exception, not the default.

**Data agent exception (stated, not implicit):** the Data agent MAY surgically Read 1-2 recent migration files per persistence store to extract the observed `how_to_add` / `how_to_modify` procedure. This is the only blanket exception to the bulk-content rule and is bounded — enumeration of every migration in `migration` category is still forbidden.

**Domain agent exception (stated, not implicit):** the Domain agent MAY surgically Read **test files** to harvest invariant assertions (the highest-signal source of product laws), bounded to the few most relevant test files per core entity in default depth. Enumeration of every test in the `fixture` category is still forbidden.

**When `DEPTH=comprehensive`, the bulk-content read ban is lifted: agents MAY Read any path that is not excluded by `.gitignore`/`.archieignore` (the ignore system remains the boundary). The 1-2-migration-files limit does not apply in comprehensive depth.**

**Dispatching the sub-agents:**

For each sub-agent below, Read the corresponding prompt file, then ALSO Read `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/grounding-rules.md`, and use the concatenated text (agent body + blank line + grounding rules body) as that sub-agent's prompt.

All paths are relative to the project root (your cwd).

| Sub-agent | Prompt file | Output path | Spawn when |
|---|---|---|---|
| Structure | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/structure-agent.md` | `.archie/tmp/archie_sub1_$PROJECT_NAME.json` | Always |
| Patterns | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/patterns-agent.md` | `.archie/tmp/archie_sub2_$PROJECT_NAME.json` | Always |
| Technology | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/technology-agent.md` | `.archie/tmp/archie_sub3_$PROJECT_NAME.json` | Always |
| UI Layer | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/ui-layer-agent.md` | `.archie/tmp/archie_sub4_$PROJECT_NAME.json` | Only when `frontend_ratio >= 0.20` |
| Data | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/data-agent.md` | `.archie/tmp/archie_sub5_$PROJECT_NAME.json` | Always |
| Domain | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/domain-agent.md` | `.archie/tmp/archie_sub6_$PROJECT_NAME.json` | Always |

**Before dispatch — append the output contract to each sub-agent's prompt,
substituting its output path from the table above as the "file path named
above".** Each prompt is the agent body + blank line + grounding rules body
+ blank line + the contract block:

```
---
OUTPUT CONTRACT (mandatory):
{{>output_contract}}
```

**Also prepend the depth contract to each sub-agent's prompt** so the comprehensive
behavior in the agent bodies (bulk-content reads, the Data agent's migration cap,
the Structure agent's naming-examples cap) is actionable. When `DEPTH=comprehensive`,
prepend this line verbatim:
> *COMPREHENSIVE MODE — be exhaustive. Every item-count in these instructions ("N-M", "up to N", "soft floor of N", "top N", "the most important") is a FLOOR, not a ceiling: emit every item that meets the quality bar, with no upper bound and no padding.*

When `DEPTH=default`, prepend nothing.

**Also prepend a timing instruction to each sub-agent's prompt** so each fact
agent self-times its run (same mechanism as Wave 2 — gives per-agent durations,
not just the aggregate wave1 step). The sub-agent's FIRST action is
`python3 .archie/telemetry.py agent-start wave1 <key>` and its LAST action
(after writing its output file) is `python3 .archie/telemetry.py agent-finish wave1 <key>`,
where `<key>` is: Structure → `structure`, Patterns → `patterns`,
Technology → `technology`, UI Layer → `ui`, Data → `data`, Domain → `domain`.

The merge step (Step 4) reads each agent's output file directly — do NOT
copy or transcribe a subagent's output yourself.

All spawned sub-agents (3 always + UI Layer and/or Data and/or Domain as applicable) run at the {{ANALYSIS_MODEL}} model. {{>dispatch_parallel}}

After the parallel dispatch returns, fold the per-agent timings into the `wave1` step so it reports each fact agent's duration (Structure / Patterns / Technology / UI Layer / Data) the same way `wave2_synthesis` does, instead of one aggregate number:

```bash
python3 .archie/telemetry.py collect-agents "$PROJECT_ROOT" wave1
```

Then record per-agent counts for trend tracking. Each call no-ops gracefully when its source file is missing (skipped agent — sub5 absent when `has_persistence_signal == false`). Uses the standard `python3 -c …` form that both Claude and Codex auto-approve via the installer's command catalogue — no new permission rules needed:

```bash
DATA_COUNT=$(python3 -c "import json,os,sys; p=sys.argv[1]; print(len((json.load(open(p)).get('data_models') or [])) if os.path.exists(p) else 0)" .archie/tmp/archie_sub5_$PROJECT_NAME.json)
python3 .archie/telemetry.py extra "$PROJECT_ROOT" wave1 data_models_count=$DATA_COUNT

STORE_COUNT=$(python3 -c "import json,os,sys; p=sys.argv[1]; print(len((json.load(open(p)).get('persistence_stores') or [])) if os.path.exists(p) else 0)" .archie/tmp/archie_sub5_$PROJECT_NAME.json)
python3 .archie/telemetry.py extra "$PROJECT_ROOT" wave1 persistence_stores_count=$STORE_COUNT
```


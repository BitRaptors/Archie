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
>
> Return the same JSON structure as the full analysis but ONLY for sections affected by the changes. Omit unchanged sections — they'll be preserved from the existing blueprint.
>
> GROUNDING RULES apply (see below).

{{>dispatch_single}}

Then skip to Step 4.

### If SCAN_MODE = "full" (default):

Spawn 3–4 {{ANALYSIS_MODEL}} subagents in parallel, each focused on a different analytical concern. ALL agents read ALL source files under `$PROJECT_ROOT` — they are not split by directory. Each agent gets: the scan.json file_tree, dependencies, config files, and the GROUNDING RULES at the end of this step.

**If `frontend_ratio` >= 0.20, spawn all 4 agents. Otherwise spawn only the first 3 (skip UI Layer).**

**Bulk content — off-limits for reading.** `scan.json.bulk_content_manifest` lists files classified by `.archiebulk` as "visible inventory, not contents": categories like `ui_resource` (Android `res/`, iOS storyboards), `generated`, `localization`, `migration`, `fixture`, `asset`, `lockfile`, `dependency`, `data`. Every agent below inherits this rule: **you may reference these paths by name and inventory counts, but you MUST NOT call Read on them.** The scanner has already summarized their shape. If a specific file is genuinely required to resolve a finding, read it surgically and note why — it is an exception, not the default.

**Dispatching the sub-agents:**

For each sub-agent below, Read the corresponding prompt file, then ALSO Read `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/grounding-rules.md`, and use the concatenated text (agent body + blank line + grounding rules body) as that sub-agent's prompt.

All paths are relative to the project root (your cwd).

| Sub-agent | Prompt file | Output path | Spawn when |
|---|---|---|---|
| Structure | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/structure-agent.md` | `.archie/tmp/archie_sub1_$PROJECT_NAME.json` | Always |
| Patterns | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/patterns-agent.md` | `.archie/tmp/archie_sub2_$PROJECT_NAME.json` | Always |
| Technology | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/technology-agent.md` | `.archie/tmp/archie_sub3_$PROJECT_NAME.json` | Always |
| UI Layer | `{{WORKFLOW_ROOT}}/deep-scan/steps/step-3-wave1/ui-layer-agent.md` | `.archie/tmp/archie_sub4_$PROJECT_NAME.json` | Only when `frontend_ratio >= 0.20` |

**Before dispatch — append the output contract to each sub-agent's prompt,
substituting its output path from the table above as the "file path named
above".** Each prompt is the agent body + blank line + grounding rules body
+ blank line + the contract block:

```
---
OUTPUT CONTRACT (mandatory):
{{>output_contract}}
```

The merge step (Step 4) reads each agent's output file directly — do NOT
copy or transcribe a subagent's output yourself.

All four sub-agents run at the {{ANALYSIS_MODEL}} model. {{>dispatch_parallel}}


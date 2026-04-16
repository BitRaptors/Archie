# Archie Scan — Architecture Health Check with Compound Learning

Analyze this project's architectural health using parallel agents. Each scan evolves the blueprint — knowledge compounds over time.

**Prerequisites:** If `.archie/scanner.py` doesn't exist, tell the user to run `npx @bitraptors/archie` first.

**CRITICAL CONSTRAINT: Never write inline Python.**
Do NOT use `python3 -c "..."` or any ad-hoc scripting to inspect, parse, or transform JSON. Every operation has a dedicated command:
- Normalize blueprint: `python3 .archie/finalize.py "$PWD" --normalize-only`
- Append health history: `python3 .archie/measure_health.py "$PWD" --append-history --scan-type fast`
- Inspect any JSON file: `python3 .archie/intent_layer.py inspect "$PWD" <filename>`
- Query a specific field: `python3 .archie/intent_layer.py inspect "$PWD" scan.json --query .frontend_ratio`

If you need data not covered by these commands, proceed without it or ask the user. NEVER improvise Python.

---

## Phase 0: Resolve scope

Every run needs to know whether to scan the root, a specific workspace, or a set of workspaces. The choice is persisted in `.archie/archie_config.json` so we ask at most once per project.

### Step A: Read existing config

```bash
python3 .archie/intent_layer.py scan-config "$PWD" read
```

- **Exit 0** → config exists. Parse `scope`, `workspaces`, `monorepo_type` from the JSON. Skip to Step D.
- **Exit 1** → config missing. Go to Step B.

If the user invoked the command with `--reconfigure`, skip Step A entirely and go to Step B (forcing a fresh prompt).

### Step B: Detect monorepo type + subprojects

```bash
python3 .archie/scanner.py "$PWD" --detect-subprojects
```

Parse `monorepo_type` and count subprojects where `is_root_wrapper` is false.

- **0 or 1 non-wrapper subprojects** → Not a monorepo (or a monorepo with only one real package). Write config as `single`:

  ```bash
  echo '{"scope":"single","monorepo_type":"<detected-type>","workspaces":[]}' \
    | python3 .archie/intent_layer.py scan-config "$PWD" write
  ```

  Skip to Step D.

- **2+ non-wrapper subprojects** → Go to Step C.

### Step C: Interactive scope prompt

Present the user with:

> Found **N workspaces** in this **{monorepo_type}** monorepo:
> 1. {name} ({type}) — {path}
> 2. {name} ({type}) — {path}
> ...
>
> **How do you want to analyze it?**
>
> - **whole** — One unified blueprint treating the monorepo as one product. Workspaces become components; cross-workspace imports become the primary architecture view. Fastest.
> - **per-package** — One blueprint per workspace you pick. Deep detail per package, no product-level view.
> - **hybrid** — Whole blueprint at root + per-workspace blueprints for specific workspaces. Most comprehensive, slowest.
> - **single** — Ignore the workspaces and scan the whole tree as if it were one project. Only use this for small monorepos.

Wait for the user's answer.

- If `whole` or `single` → `WORKSPACES=[]`
- If `per-package` or `hybrid` → ask which workspaces to include. Accept comma-separated numbers (`1,3,5`) or `all`. Resolve to paths relative to `$PWD`.

Persist the choice:

```bash
echo '{"scope":"<chosen>","monorepo_type":"<detected-type>","workspaces":[<array>]}' \
  | python3 .archie/intent_layer.py scan-config "$PWD" write
```

### Step D: Validate

```bash
python3 .archie/intent_layer.py scan-config "$PWD" validate
```

- **Exit 0** → proceed with the rest of the pipeline.
- **Exit 1** → a workspace was removed/renamed. Print the drift message and instruct the user to re-run with `--reconfigure`. Stop execution.

Expose `SCOPE`, `WORKSPACES`, and `MONOREPO_TYPE` for the rest of the run.

### Execution plan based on SCOPE

- **SCOPE=single or whole** — Run Phases 1-6 once with `PROJECT_ROOT="$PWD"`. For `whole`, apply the workspace-aware addendum in Phase 3 so components represent workspaces.
- **SCOPE=per-package** — For each path in `WORKSPACES`, set `PROJECT_ROOT="$PWD/<path>"` and run Phases 1-6. Produce one scan_report per workspace.
- **SCOPE=hybrid** — Pass 1 with `PROJECT_ROOT="$PWD"` (whole semantics); Pass 2 iterates `WORKSPACES`. Each pass writes its own blueprint, health, and scan_report in its `PROJECT_ROOT/.archie/`.

After all passes finish, print a summary if >1 blueprint was touched: "Updated N blueprints. Errors: X total. See <paths>."

---

## Phase 1: Data Gathering (parallel scripts, seconds)

Run all three scripts simultaneously:

```bash
python3 .archie/scanner.py "$PWD"
```
```bash
python3 .archie/measure_health.py "$PWD" > .archie/health.json 2>/dev/null
```
```bash
python3 .archie/detect_cycles.py "$PWD" --full 2>/dev/null
```
```bash
git log --oneline --since="7 days ago" --name-only 2>/dev/null | sort -u | head -50
```

---

## Phase 2: Read All Existing Knowledge

Read the fresh scan data:
- `.archie/skeletons.json` — every file's header, function/class signatures, line counts
- `.archie/scan.json` — file tree, import graph, detected frameworks
- `.archie/health.json` — erosion, gini, verbosity, complexity per function
- `.archie/dependency_graph.json` — resolved directory-level dependency graph

Read accumulated knowledge (skip any that don't exist — that's normal for early scans):
- `.archie/blueprint.json` — the evolving architectural knowledge base
- `.archie/scan_report.md` — previous scan's report (for trending and resolved/new findings)
- `.archie/health_history.json` — historical health scores
- `.archie/rules.json` — adopted enforcement rules
- `.archie/proposed_rules.json` — rules discovered but not yet adopted

**This is the compound learning input.** The agents below receive everything Archie has ever learned about this codebase.

---

## Phase 3: Parallel Analysis (3 agents)

Spawn 3 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`). Each agent receives all the data from Phase 2 and can read source files when needed.

**EFFICIENCY RULE:** Agents read skeletons.json which contains every file's path, class/function signatures, imports, and first lines. This is sufficient for pattern detection, outlier finding, and most analysis. Agents should ONLY use the Read tool on source files when the skeleton genuinely lacks the information needed to make a judgment.

**IMPORTANT:** Write each agent's output to a temp file so Phase 4 can read them all.

### Agent A: Architecture & Dependencies

```
Prompt for Agent A:
```

You are analyzing the ARCHITECTURE and DEPENDENCIES of a codebase. You have access to all scan data and the existing blueprint (if any).

**Your inputs:**
- `.archie/dependency_graph.json` — resolved directory-level graph. Node schema: `{id, label, component, inDegree, outDegree, inCycle, fileCount}` — use `id` for directory path, NOT `path`. Edge schema: `{source, target, weight, crossComponent}`. Do NOT write ad-hoc Python to analyze this data — use it directly in your analysis.
- `.archie/skeletons.json` — every file's structure
- `.archie/blueprint.json` — existing architectural knowledge (if any)
- `.archie/scan.json` — import graph, frameworks

**Your job:**
1. **Component analysis:** Identify all logical components. If a blueprint exists, compare — are there new components? Removed ones? Changed responsibilities? If no blueprint, infer components from directory structure and import patterns.

2. **Dependency direction:** Using the dependency graph, trace the dependency flow. Are there layers? Do dependencies flow in one direction? Flag cross-component edges as potential violations. Use the dependency graph and skeletons to judge violations. Only Read a source file if the skeleton doesn't show enough context to judge whether the import is a real violation or an acceptable exception (e.g., type-only import, test helper).

3. **Dependency magnets:** Which directories have highest in-degree? These are stability bottlenecks. The dependency graph shows what they provide — only read if the role is ambiguous from the skeleton.

4. **Tight coupling:** Edges with high weight (many imports). The import graph and skeletons show why coupling exists — only read if intent is unclear from the skeleton.

5. **Circular dependencies:** For each cycle in the graph, explain what coupling it creates and why it matters. Read a cycle participant only if the skeleton doesn't explain the coupling.

6. **Architecture style:** Based on the dependency flow, component structure, and patterns you observe, what is the architecture style? How confident are you? If the blueprint already states one, do you agree based on current evidence?

**Output:** Write a structured JSON report to `/tmp/archie_agent_a_arch.json`:
```json
{
  "components": [{"name": "...", "path": "...", "role": "...", "confidence": 0.9}],
  "architecture_style": {"style": "...", "confidence": 0.85, "evidence": "..."},
  "dependency_violations": [{"from": "...", "to": "...", "severity": "error|warn", "description": "...", "verified_in_file": "...", "confidence": 0.9}],
  "dependency_magnets": [{"directory": "...", "in_degree": N, "risk": "..."}],
  "cycles": [{"directories": [...], "impact": "...", "evidence_files": [...]}],
  "tight_coupling": [{"from": "...", "to": "...", "weight": N, "reason": "..."}]
}
```

```
Save output: /tmp/archie_agent_a_arch.json
```

### Agent B: Health & Complexity

```
Prompt for Agent B:
```

You are analyzing the HEALTH and COMPLEXITY of a codebase. You have access to health metrics, complexity data, and historical trends.

**Your inputs:**
- `.archie/health.json` — current erosion, gini, verbosity, waste, function-level complexity
- `.archie/health_history.json` — historical health scores (for trend analysis)
- `.archie/skeletons.json` — file structure
- `.archie/blueprint.json` — existing architectural knowledge (if any)

**Your job:**
1. **Health assessment:** Report each metric with plain-language explanation. Thresholds:
   - Erosion: <0.3 good, 0.3-0.5 moderate, >0.5 high
   - Gini: <0.4 good, 0.4-0.6 moderate, >0.6 high
   - Top-20% share: <0.5 good, 0.5-0.7 moderate, >0.7 high
   - Verbosity: <0.05 good, 0.05-0.15 moderate, >0.15 high

2. **Trend analysis:** Compare against health_history.json. Are things improving or degrading? Which metrics moved most? Is LOC growth justified?

3. **Complexity hotspots:** Identify functions with CC > 10. Assess from skeletons first — the function signature and surrounding context usually explain the complexity. Only Read a function's source if you can't determine from the skeleton whether the complexity is justified.

4. **Abstraction waste:** Single-method classes, tiny functions (<=2 lines). Flag from skeletons. Only read if the skeleton is ambiguous about whether a single-method class is a legitimate abstraction.

**Output:** Write to `/tmp/archie_agent_b_health.json`:
```json
{
  "health_scores": {"erosion": 0.31, "gini": 0.58, "top20_share": 0.72, "verbosity": 0.003, "total_loc": 9400},
  "trend": {"direction": "improving|degrading|stable", "details": "..."},
  "complexity_hotspots": [{"function": "...", "file": "...", "cc": N, "assessment": "...", "recommendation": "..."}],
  "complexity_trajectory": [{"function": "...", "file": "...", "previous_cc": N, "current_cc": N}],
  "abstraction_waste": {"single_method_classes": N, "tiny_functions": N, "notable": ["..."]}
}
```

```
Save output: /tmp/archie_agent_b_health.json
```

### Agent C: Rules & Patterns

```
Prompt for Agent C:
```

You are analyzing PATTERNS and discovering RULES in a codebase. You look for architectural invariants — things that should always be true.

**Your inputs:**
- `.archie/skeletons.json` — every file's structure
- `.archie/rules.json` — currently adopted rules
- `.archie/proposed_rules.json` — previously proposed rules (adopted or pending)
- `.archie/blueprint.json` — existing architectural knowledge (if any)
- `.archie/scan.json` — file tree, imports, frameworks

**Your job:**
1. **Pattern consistency:** Identify patterns and outliers from skeletons alone — the class hierarchy, function names, file organization, and import patterns are all visible in skeletons. Only Read an outlier source file if you cannot determine from the skeleton whether it's intentional (e.g., a comment, a different base class for a reason).

2. **Duplication / reimplementation:** Detect duplicate/similar function names from skeletons. AI agents do this constantly — they reimplement helpers instead of importing shared code. Only Read source files if the function signatures differ and you need to confirm whether they're true duplicates or just same-named but different.

3. **Propose new rules:** Based on patterns found, propose architectural rules. No file reads needed — patterns come from skeletons. Do NOT re-propose rules already in rules.json or proposed_rules.json. Look for DEEPER rules — subtler invariants, behavioral constraints, scoped rules for specific components.

4. **Validate existing rules:** Check from skeletons and scan data. Only Read a source file if you need to confirm a rule violation that isn't obvious from the skeleton. Check if any proposed rules have become more or less valid since they were proposed (adjust confidence).

**Rule schema:**
Required: `{"id": "scan-NNN", "description": "...", "rationale": "...", "severity": "error|warn", "confidence": 0.85}`

Confidence calibration:
- 0.9-1.0: Verified invariant — N files follow pattern with 0-1 exceptions, you read the files.
- 0.7-0.9: Strong pattern with some exceptions, clear architectural intent.
- 0.5-0.7: Inferred from structure, not verified in every case.
- 0.3-0.5: Speculative, based on best practices not specific evidence.

Be honest. A wrong rule with high confidence is worse than a right rule with low confidence.

Optional mechanical fields (add ONLY when a meaningful regex exists):
- `"check"`: `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`
- `"applies_to"`, `"file_pattern"`, `"forbidden_patterns"`, `"required_in_content"`

**Output:** Write to `/tmp/archie_agent_c_rules.json`:
```json
{
  "pattern_findings": [{"pattern": "...", "followers": N, "outliers": ["..."], "severity": "warn|error", "confidence": 0.85}],
  "duplications": [{"function": "...", "locations": ["..."], "recommendation": "..."}],
  "proposed_rules": [{"id": "scan-NNN", "description": "...", "rationale": "...", "severity": "...", "confidence": 0.85}],
  "existing_rule_violations": [{"rule_id": "...", "violated_by": "...", "details": "..."}],
  "rule_confidence_updates": [{"rule_id": "...", "old_confidence": 0.7, "new_confidence": 0.85, "reason": "..."}]
}
```

#### Workspace-aware addendum (only when `SCOPE === "whole"`)

If the current scope is `whole`, `PROJECT_ROOT` is a workspace monorepo (`MONOREPO_TYPE={type}`). The blueprint's `components` section treats each workspace as a top-level component, and `blueprint.workspace_topology` (if present) captures the inter-workspace dependency graph. When analyzing drift and findings, pay special attention to:

- Cross-workspace imports that create cycles in the workspace dependency graph → always severity `error`
- Shared/library packages (e.g., `packages/*`) that import from application packages (e.g., `apps/*`) → inverted dependency flow, severity `error`
- Workspaces with very high fan-in (top 20% of `in_degree`) that keep growing — flag as "dependency magnet at risk"
- Reference components by **workspace name** (from `package.json`), not by path, in findings

```
Save output: /tmp/archie_agent_c_rules.json
```

**Wait for all 3 agents to complete before proceeding to Phase 4.**

---

## Phase 4: Synthesis + Blueprint Evolution

Read the outputs from all three agents:
- `/tmp/archie_agent_a_arch.json`
- `/tmp/archie_agent_b_health.json`
- `/tmp/archie_agent_c_rules.json`

Also re-read `.archie/blueprint.json` (the current state of accumulated knowledge).

Now you are the **synthesis agent**. Your job is to merge the three agents' findings with the existing blueprint to produce an evolved blueprint. This is where compound learning happens.

### 4a: Evolve the Blueprint

Read the existing blueprint (or start with `{}` if none exists). Apply these evolution rules:

**IMPORTANT: The blueprint must always use the canonical schema below. The viewer depends on these exact field names. Do NOT invent alternative field names.**

**Components** (`blueprint.components`):
Structure: `{"components": [{"name": "", "location": "", "responsibility": "", "depends_on": [], "confidence": 0.9}]}`
- Map Agent A's output: `path` → `location`, `role` → `responsibility`
- If Agent A found new components not in blueprint → add them
- If Agent A found components that match existing ones → keep existing data, update confidence if Agent A's is higher
- If a component in the blueprint no longer appears in Agent A's analysis → keep it but add `"status": "not_found_in_latest_scan"` (don't delete — it might be in an unscanned area)

**Architecture style** (`blueprint.decisions.architectural_style`):
Structure: `{"title": "Architectural Style", "chosen": "", "rationale": "", "confidence": 0.9, "alternatives_rejected": []}`
- Map Agent A's output: `style` → `chosen`, `details`/`evidence` → `rationale`
- If no blueprint → use Agent A's assessment
- If blueprint exists and Agent A agrees → increase confidence (min of 1.0)
- If blueprint exists and Agent A disagrees → keep blueprint's but add Agent A's assessment as `"alternative_assessment"` with reasoning. Don't overwrite the deep scan's analysis with a scan's inference.

**Health** (`blueprint.meta.health`):
- Always update with Agent B's latest scores
- Add `"trend"` from Agent B's trend analysis
- Add `"last_health_scan"` timestamp

**Pitfalls** (`blueprint.pitfalls`):
Structure: `[{"area": "", "description": "", "recommendation": "", "severity": "error|warn", "confidence": 0.9, "source": "scan-observed", "stems_from": [], "applies_to": [], "first_seen": "", "confirmed_in_scan": N}]`
- Agent A's dependency violations → add as pitfalls. Map `title` → `area`.
- Agent B's complexity hotspots → add as pitfalls
- Agent C's pattern violations → add as pitfalls
- Existing pitfalls from blueprint → keep. If a scan-observed pitfall matches an existing one, increase its confidence.
- If a previously scan-observed pitfall is no longer found → mark `"status": "resolved"` with timestamp. Don't delete — the resolution is valuable knowledge.

**Architecture rules** (`blueprint.architecture_rules`):
- Agent C's proposed rules that have confidence >= 0.8 → add to `architecture_rules` with `"source": "scan-inferred"`
- Existing rules from deep scan → keep as-is (higher authority)
- Agent C's rule confidence updates → apply to matching rules

**Development rules** (`blueprint.development_rules`):
Structure: `[{"rule": "", "severity": "warn|error", "confidence": 0.9, "source": "scan-inferred"}]`
- Map Agent C's output: `description` → `rule`
- Agent C's pattern findings with confidence >= 0.7 → add as development rules

**Meta** (`blueprint.meta`):
- Update `"last_scan"` timestamp
- Update `"scan_count"` (increment)
- Update `"confidence"` per section — each scan that confirms a section's data increases its confidence slightly (up to 1.0)
- Set `"schema_version": "2.0.0"`

**CRITICAL EVOLUTION RULES:**
- **Never decrease confidence** on data that came from a deep scan unless you have strong contrary evidence from reading source files.
- **Never delete** sections or entries that came from a deep scan. Mark them as stale if needed, but don't delete.
- **Always add** new findings. Accumulate, don't replace.
- **Resolved findings stay** in the blueprint with `"status": "resolved"` — they're part of the project's architectural history.

Write the evolved blueprint to `.archie/blueprint.json`.

Then normalize it to ensure canonical schema:
```bash
python3 .archie/finalize.py "$PWD" --normalize-only
```

### 4b: Write Scan Report

Get the current date/time and scan number from the blueprint (`meta.scan_count`):
```bash
date -u +"%Y-%m-%dT%H%M"
```

Create the scan history directory if it doesn't exist:
```bash
mkdir -p .archie/scan_history
```

Write to `.archie/scan_history/scan_NNN_YYYY-MM-DDTHHMM.md` (where NNN is the zero-padded scan number, e.g., `scan_003_2026-04-08T1423.md`) and copy to `.archie/scan_report.md` (latest pointer).

The report should include:
```markdown
# Archie Scan Report
> Scan #N | YYYY-MM-DD HH:MM UTC | X files analyzed | Y changed in last 7 days

## Architecture Overview
[5-10 lines from Agent A's analysis]

## Health Scores
| Metric | Current | Previous | Trend | What it means |
|--------|---------|----------|-------|---------------|
| Erosion | | | | Files breaking expected structure (naming, docs, tests). <0.3 good, >0.5 high |
| Gini | | | | Code distribution inequality. High = a few god-files hold most code. <0.4 good, >0.6 high |
| Top-20% | | | | Share of code in the largest 20% of files. <0.5 good, >0.7 high |
| Verbosity | | | | Comment-to-code ratio. High = over-documented or commented-out code. <0.05 good, >0.15 high |
| LOC | | | | Total lines of code. Tracks growth over time |
[Fill in Current, Previous, Trend from Agent B]

### Complexity Trajectory
[functions that got more complex since last scan]

## Findings
[ALL findings from agents A, B, C — ranked by severity then confidence]
[Each finding: what's wrong, which file, evidence from the code, why it matters]
[Mark which findings are NEW vs. RECURRING vs. RESOLVED since last scan]

## Blueprint Evolution
[What changed in the blueprint this scan — new components, updated confidence, resolved pitfalls, new rules added]

## Proposed Rules
[from Agent C — numbered checklist with rationale and confidence]

## Next Task
**What:** [highest-impact action from across all three agents]
**Where:** [exact file paths]
**Why:** [what improves]
**How:** [2-3 sentence approach]

## Recommendations
[Re-baseline with /archie-deep-scan if: no deep scan ever, erosion increased >0.10, major structural changes]
```

### 4c: Update Satellite Files

Append health scores to history:
```bash
python3 .archie/measure_health.py "$PWD" --append-history --scan-type fast
```

Save ALL proposed rules (from Agent C) to `.archie/proposed_rules.json`:
```
1. Read existing proposed_rules.json (create as {"rules": []} if missing)
2. Append new proposed rules with "source": "scan-proposed" (keep AI-assigned confidence)
3. Skip if a rule with the same id already exists
4. Update confidence on existing proposed rules if Agent C recommended changes
5. Write back
```

Save Agent C's semantic duplications to `.archie/semantic_duplications.json`:
```
1. Read /tmp/archie_agent_c_rules.json and extract the `duplications` array (each entry: {function, locations[], recommendation})
2. Write to .archie/semantic_duplications.json as {"duplications": [...], "scanned_at": "<ISO UTC>"}
3. Overwrite on every scan — this is a snapshot of the current state, not append-only
```

This is what `/archie-share` surfaces as "N semantic reimplementations" alongside the textual verbosity metric.

### 4d: Clean up temp files

```bash
rm -f /tmp/archie_agent_a_arch.json /tmp/archie_agent_b_health.json /tmp/archie_agent_c_rules.json
```

Note: keep `.archie/health.json` — `/archie-share` needs it to populate the Metrics panel in the viewer. It is regenerated on every scan, so stale data is not a concern.

---

## Phase 5: Present Results and Process Adoptions

Print the summary to the user. Include:
1. **Health scores** table (all metrics with trend) and a **metric legend** explaining each one:
   - **Erosion** — How many files break expected structure (naming, docs, tests). <0.3 good, 0.3–0.5 moderate, >0.5 high
   - **Gini** — Code distribution inequality. High = a few god-files hold most code. <0.4 good, 0.4–0.6 moderate, >0.6 high
   - **Top-20%** — Share of code in the largest 20% of files. <0.5 good, 0.5–0.7 moderate, >0.7 high
   - **Verbosity** — Comment-to-code ratio. High = over-documented or commented-out code. <0.05 good, 0.05–0.15 moderate, >0.15 high
   - **LOC** — Total lines of code. Tracks growth over time
2. **Blueprint evolution** — what changed in the blueprint this scan (new components, updated confidence, resolved pitfalls, new rules inferred)
3. **All findings** from all agents — ranked by severity. Group as NEW / RECURRING / RESOLVED. This is the most valuable part — don't skip or summarize as counts.
4. **Proposed rules** with numbered checklist from Agent C
5. **Next task**
6. Path to full report

The rule adoption prompt:
> **Reply with the numbers to adopt** (e.g., `1, 3` or `all` or `none`).
> Adopted rules take effect immediately. Skipped rules remain in `/archie-viewer` → Rules tab.

**Wait for the user's response.** Then process:

- Numbers → adopt those rules into `.archie/rules.json` with `"source": "scan-adopted"` (keep AI confidence)
- `all` → adopt every proposed rule
- `none` → skip (rules stay in proposed_rules.json)

Print confirmation: `Adopted N rules, skipped M (available in /archie-viewer → Rules tab). Scan #N complete — blueprint evolved.`

---

## Buddy

After presenting scan results, show the Archie buddy in compact mode:

```bash
python3 .archie/buddy.py "$PROJECT_ROOT" --compact
```

Include its output at the end of the scan results.

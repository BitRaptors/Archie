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
- If `per-package` or `hybrid` → ask which workspaces to include as a free-form follow-up: *"Which workspaces? Type comma-separated numbers (e.g., `1,3,5`) or `all`."* Resolve to paths relative to `$PWD`.

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

Before running the scanner, snapshot the previous scan so the wiki incremental builder can diff against it:

```bash
cp "$PROJECT_ROOT/.archie/scan.json" /tmp/archie_prev_scan.json 2>/dev/null || echo '{}' > /tmp/archie_prev_scan.json
```

**Telemetry:** record `TELEMETRY_DATA_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")` before launching the scripts below.

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

**Telemetry:** record `TELEMETRY_DATA_END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")` and `TELEMETRY_AGENTS_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")` before spawning agents.

Spawn 3 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`). Each agent receives all the data from Phase 2 and can read source files when needed.

**EFFICIENCY RULE:** Agents read skeletons.json which contains every file's path, class/function signatures, imports, and first lines. This is sufficient for pattern detection, outlier finding, and most analysis. Agents should ONLY use the Read tool on source files when the skeleton genuinely lacks the information needed to make a judgment.

**Bulk content — off-limits for reading.** `scan.json.bulk_content_manifest` classifies files that the scanner saw but intentionally did not skeleton-parse: `ui_resource` (Android `res/`, iOS storyboards), `generated` (codegen output, bundled/minified JS, `*.d.ts`, `*.pb.go`, `*.g.dart`), `localization`, `migration`, `fixture`, `asset`, `lockfile`, `dependency`, `data`. Every agent below inherits this rule: **reference these paths by name and inventory counts, but do NOT call Read on them** — the scanner already summarized their shape. Surgical Read is allowed only when resolving a specific finding requires the content; note the reason.

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
- `.archie/findings.json` — accumulated findings from prior runs (if present). Entries with `source: "scan:structure"` are yours to steward.

**Novelty priority.** If findings.json exists, open it first and skim the entries in your slice (`source: "scan:structure"`, `status: "active"`). Those problems are already known — **your job is not to rediscover them**. Spend your analysis budget on problems that are NOT in the store: new components, newly-introduced violations, previously-missed gaps, anything emerging from recent changes to the dependency graph or skeletons. Reconfirming known items is bookkeeping, not analysis — emit them with the same `problem_statement` wording as the store (so 4b can id-match them) but do NOT re-derive evidence from scratch. If you genuinely find nothing new, say so in your output rather than padding.

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
- `.archie/findings.json` — accumulated findings from prior runs (if present). Entries with `source: "scan:health"` are yours to steward.

**Novelty priority.** If findings.json exists, open it first and skim the entries in your slice (`source: "scan:health"`, `status: "active"`). Those hotspots are already known — **your job is not to rediscover them**. Point your analysis at what has MOVED: functions whose CC climbed since last run, newly-introduced complexity, LOC growth that wasn't there before, hotspots that cooled off (mark candidates for resolution). Reconfirming known hotspots is bookkeeping — emit them with the same `problem_statement` wording (so 4b can id-match) without re-deriving evidence. If trends are flat and nothing new emerged, say so explicitly rather than padding.

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
- `.archie/findings.json` — accumulated findings from prior runs (if present). Entries with `source: "scan:patterns"` are yours to steward.

**Novelty priority.** If findings.json exists, open it first and skim the entries in your slice (`source: "scan:patterns"`, `status: "active"`). Those pattern issues are already known — **your job is not to rediscover them**. Aim your analysis at pattern drift that is NEW since the last run: freshly-introduced outliers, newly-emergent duplications, new rule violations in recently-touched files, categories of pattern you haven't flagged before. Reconfirming known pattern issues is bookkeeping — emit them with the same `problem_statement` wording (so 4b can id-match) without re-deriving evidence. Similarly for proposed_rules.json: do not re-propose rules that already exist there — look deeper. If nothing new has drifted, say so explicitly rather than padding.

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

**Telemetry:** record `TELEMETRY_AGENTS_END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")` and `TELEMETRY_SYNTHESIS_START=$(date -u +"%Y-%m-%dT%H:%M:%SZ")` before starting synthesis.

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
- **DO NOT write, edit, or delete entries in `blueprint.pitfalls` during scan.** Pitfalls are class-of-problem, blueprint-durable entries owned exclusively by `/archie-deep-scan` Wave 2, which emits them in the canonical 4-field shape (`problem_statement`, `evidence`, `root_cause`, `fix_direction`).
- Concrete problems surfaced by Agents A/B/C become **findings** in `.archie/findings.json` via step 4b — not pitfalls. Their schema is the same 4-field core; `source` is `scan:structure | scan:health | scan:patterns`; `depth` is `draft`.
- If a scan-observed finding recurs across runs its `confirmed_in_scan` counter increments (id-stable match in 4b). If a deep-scan has already linked it to a parent pitfall (`pitfall_id` set), the link is preserved.
- Existing `blueprint.pitfalls` entries pass through untouched.

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

### 4b: Write structured findings

Collect every concrete problem the three agents surfaced (Agent A: architecture/structure, Agent B: health/complexity, Agent C: patterns/rules) and emit them as structured JSON to `.archie/findings.json`. This is the machine-readable companion to the prose scan report in 4c, and it is the seam that `/archie-deep-scan` consumes to produce canonical findings and pitfalls.

**Dedup is the default, novelty is the goal.** The agents were told to prioritize NEW problems and to reuse the existing `problem_statement` wording when they reconfirm known ones — so ID-matching should be cheap here. The store compounds across runs; your job in 4b is to make sure:

- Already-known findings get reused (same `id`, `confirmed_in_scan += 1`), not duplicated.
- Genuinely new findings get a fresh `f_NNNN` id.
- Known findings the agents couldn't confirm any more get `status: "resolved"` (plus `resolved_at`).

A run whose output is dominated by reconfirmations is a valid result only when the codebase is stable. If the agents reported novelty but 4b flattened it into reconfirmations, you did it wrong — preserve the new findings they flagged.

**Quality bar — quality-gated, not quantity-gated.** A finding is valid only if:

- `problem_statement` is specific. "Code is complex" is not a finding; "3 route handlers exceed 500 SLOC with cyclomatic complexity > 20" is.
- `evidence` is non-empty and concrete: file paths with line numbers, counts, pattern observations. No `evidence` → drop the finding.
- `root_cause` names the architectural decision, pattern choice, or constraint driving the problem. "Needs refactoring" is not a root cause.
- `fix_direction` is actionable and tactical (single sentence).

**Soft floor of 3.** If you would emit fewer than 3 findings total across all three agents, explicitly state why in the scan report's Findings section (e.g., "no material issues — codebase is clean in areas X, Y, Z; only one finding met the quality bar"). Never invent filler findings to hit a number.

No upper cap on `findings.json` — rank-clip happens only at render time in `scan_report.md` (4c).

**Finding schema:**

```json
{
  "id": "f_NNNN",
  "problem_statement": "One sentence, specific.",
  "evidence": ["src/file.py:42", "pattern observed in 7 modules", "..."],
  "root_cause": "Names a decision/pattern/constraint, specific to this codebase.",
  "fix_direction": "Single tactical sentence.",
  "severity": "error | warn | info",
  "confidence": 0.85,
  "applies_to": ["src/auth/", "src/routes/profile.py"],
  "source": "scan:structure | scan:health | scan:patterns",
  "depth": "draft",
  "first_seen": "YYYY-MM-DDTHHMM",
  "confirmed_in_scan": 1,
  "status": "active"
}
```

`source` maps to the agent: Agent A → `scan:structure`, Agent B → `scan:health`, Agent C → `scan:patterns`.

**ID stability across scans.** Read the previous `.archie/findings.json` if present. For each new finding:

- Try to match an existing finding by (similar `problem_statement`) ∧ (overlapping `applies_to`). On match: reuse the existing `id`, increment `confirmed_in_scan`, keep `first_seen`.
- Unmatched new findings → assign the next-free `f_NNNN` id, set `first_seen` = current scan timestamp, `confirmed_in_scan` = 1.
- Previous findings that no longer apply → set `status: "resolved"` and add `resolved_at: <current timestamp>`. Keep them in the file (the resolution is valuable signal for `/archie-deep-scan` and trend analysis).

**Output file shape:**

```json
{
  "scanned_at": "YYYY-MM-DDTHHMM",
  "scan_count": N,
  "findings": [ ... ]
}
```

Write to `.archie/findings.json`. `scanned_at` must match the date/time you compute in 4c. `scan_count` matches `blueprint.meta.scan_count` after 4a evolved it.

### 4c: Write Scan Report

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

## Wiki health
[Read /tmp/archie_wiki_lint.json. If the array is empty, write: "Wiki lint: clean."
Otherwise group findings by `kind` and emit:]

**Orphans ({N}):**
- `<page>`

**Broken links ({N}):**
- `<page>` → `<target>`

**Stale evidence ({N}):**
- `<page>` (globs: `<evidence>`)

**Dangling backlinks ({N}):**
- `<page>` (missing source: `<missing_source>`)

**Contradictions ({N}):**
- `<page>` → `<target>`: `<message>`

[Omit any kind that has 0 findings.]

## Recommendations
[Re-baseline with /archie-deep-scan if: no deep scan ever, erosion increased >0.10, major structural changes]
```

### 4d: Update Satellite Files

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

Save Agent C's semantic duplications to `.archie/semantic_duplications.json` — run this unconditionally (it writes an empty list when Agent C found none, so the file always reflects the latest AI verdict):

```bash
python3 .archie/extract_output.py save-duplications /tmp/archie_agent_c_rules.json "$PWD"
```

This is what `/archie-share` surfaces as "N semantic reimplementations" alongside the textual verbosity metric. Keeping the write deterministic means every fresh bundle carries a structured `semantic_duplications` field — the share viewer never has to fall back to regex-parsing the scan report.

### 4e: Wiki — conditional capabilities refresh

This step only applies when a prior wiki exists (`.archie/wiki/_meta/provenance.json` is present). Skip entirely if that file does not exist.

Read `/tmp/archie_prev_scan.json` (the pre-run snapshot) and `$PROJECT_ROOT/.archie/scan.json` (the fresh scan). Compute which file paths changed (added, modified, or deleted) by comparing the `files[].hash` values between the two scans.

Read `.archie/wiki/_meta/provenance.json`. For each page whose key starts with `capabilities/`, check whether any entry in its `evidence` array glob-matches one of the changed file paths. Collect the unique directory prefixes (the part before the first `*`) of the matching globs into a set called `cap_evidence_dirs`.

If `cap_evidence_dirs` is non-empty, dispatch a Sonnet subagent with this prompt:

> Read `$PROJECT_ROOT/.archie/blueprint.json`. Focus only on capability entries whose evidence directories overlap with: {cap_evidence_dirs}.
> For each matching capability, decide whether its `summary`, `evidence`, or `linked_decisions` fields need updating based on the changed files.
> Return a JSON array of capability objects (same schema as `blueprint.capabilities[]`) containing ONLY the capabilities that actually changed. Return `[]` if nothing changed materially. Do NOT introduce capabilities from outside the scoped directories.

Save the subagent output to `/tmp/archie_agent_capabilities_scoped.json`.

Then merge the returned capabilities into `.archie/blueprint.json`: for each returned capability, find the existing entry with matching `name` and replace it in-place; leave all other capabilities untouched. Write the updated blueprint back and re-run normalize:

```bash
python3 .archie/finalize.py "$PROJECT_ROOT" --normalize-only
```

If `cap_evidence_dirs` is empty, skip the subagent dispatch and merge entirely.

### 4f: Wiki — incremental build

Run the incremental wiki builder. It rewrites only pages whose evidence files changed; it is a no-op when no prior wiki exists or when no files changed:

```bash
python3 .archie/wiki_builder.py "$PROJECT_ROOT" --incremental \
  --previous-scan /tmp/archie_prev_scan.json
```

Expected output (one of):
- `Wiki incremental: N pages rewritten.`
- `Wiki incremental: no changed files, nothing to do.`
- `Wiki incremental: no affected pages.`
- `Wiki generation disabled (ARCHIE_WIKI_ENABLED=false). Skipped.`

If `wiki_builder.py` exits with a non-zero status because the blueprint structure changed (RuntimeError), surface the following line in the scan report and continue — do not abort the scan:

> Wiki: blueprint structure changed — run /archie-deep-scan to rebuild wiki.

### 4g: Wiki lint

Run the wiki linter and capture findings as JSON:

```bash
python3 .archie/wiki_index.py --wiki "$PROJECT_ROOT/.archie/wiki" --fs-root "$PROJECT_ROOT" --lint --json > /tmp/archie_wiki_lint.json 2>/dev/null || echo '[]' > /tmp/archie_wiki_lint.json
```

(The fallback `echo '[]'` ensures a missing or empty wiki does not break the scan.)

### 4h: Clean up temp files

```bash
rm -f /tmp/archie_agent_a_arch.json /tmp/archie_agent_b_health.json /tmp/archie_agent_c_rules.json /tmp/archie_wiki_lint.json /tmp/archie_prev_scan.json /tmp/archie_agent_capabilities_scoped.json
```

Note: keep `.archie/health.json` — `/archie-share` needs it to populate the Metrics panel in the viewer. It is regenerated on every scan, so stale data is not a concern.

### 4i: Write telemetry

Record the synthesis end timestamp and write the per-run telemetry file. This captures step-level wall-clock for measuring the impact of prompt/code changes; output lives in `.archie/telemetry/`.

```bash
TELEMETRY_SYNTHESIS_END=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
```

Write `/tmp/archie_timing.json` with the timestamps you recorded at each phase boundary above:

```json
[
  {"name": "data", "started_at": "<TELEMETRY_DATA_START>", "completed_at": "<TELEMETRY_DATA_END>"},
  {"name": "agents", "started_at": "<TELEMETRY_AGENTS_START>", "completed_at": "<TELEMETRY_AGENTS_END>", "model": "sonnet"},
  {"name": "synthesis", "started_at": "<TELEMETRY_SYNTHESIS_START>", "completed_at": "<TELEMETRY_SYNTHESIS_END>"}
]
```

Then invoke the writer:

```bash
python3 .archie/telemetry.py "$PWD" --command scan --timing-file /tmp/archie_timing.json
```

If telemetry fails for any reason (missing timestamp, file write error), do not abort the scan — telemetry is informational only.

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

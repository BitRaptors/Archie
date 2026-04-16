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

Emit findings per `.claude/commands/_shared/semantic_findings_spec.md` — follow the schema, severity rubric, and quality gate exactly. Your domain is **architecture and dependencies**.

Before emitting any findings, Read the spec file and follow §1 (schema), §2 (quality gate), §3 (severity rubric), §4 (taxonomy).

Produce two kinds of output:

1. **pattern_observations** (for Wave 2 or fast-scan synthesis to consume): raw cross-file anomalies in your domain — dep-graph magnets, cycles crossing layers, inverted dependencies, workspace-boundary violations. These are NOT finished findings; they're signals. Each observation: `{type, evidence_locations, note}`.

2. **findings** in your domain:
   - **Systemic** (category: systemic): `god_component`, `boundary_violation`. Each with ≥3 evidence locations, pattern_description, root_cause, fix_direction, blast_radius.
   - **Localized** (category: localized): `dependency_violation`, `cycle`, `pattern_divergence` (where the pattern is dependency-shaped). Each with a single location, root_cause, fix_direction.

All findings MUST carry `synthesis_depth: "draft"` and `source: "fast_agent_a"`.

Do NOT emit count caps. Emit every finding you can substantiate with concrete evidence.

**Efficiency rule:** read skeletons.json + dep_graph.json first. Only Read source files when the skeleton is genuinely insufficient to judge.

Before emitting, verify each finding against the quality gate in §2 of the spec — dropped candidates are better than padded ones.

**Output:** Write to `/tmp/archie_agent_a.json`:

```json
{
  "pattern_observations": [
    {"type": "dep_magnet", "evidence_locations": ["packages/shared"], "note": "fan-in 22 across unrelated domains"}
  ],
  "findings": [
    {
      "category": "systemic",
      "type": "god_component",
      "severity": "error",
      "scope": {"kind": "system_wide", "components_affected": ["packages/shared"], "locations": ["apps/webui/src/auth.ts:14", "apps/electron/src/storage.ts:3", "apps/webui/src/ui/Button.tsx:1"]},
      "pattern_description": "shared/ accumulates responsibilities from 7 unrelated domains",
      "evidence": "22 consumers import from packages/shared across auth, storage, UI, logging",
      "root_cause": "every cross-cutting util was added to shared without domain boundary; decision D.3 treated shared as primitives but actual usage crosses domains",
      "fix_direction": "split into packages/{auth, storage, ui-primitives, logging}; migrate per-domain starting with auth",
      "blueprint_anchor": "decision:D.3",
      "blast_radius": 22,
      "synthesis_depth": "draft",
      "source": "fast_agent_a"
    },
    {
      "category": "localized",
      "type": "dependency_violation",
      "severity": "error",
      "scope": {"kind": "single_file", "components_affected": ["apps/webui"], "locations": ["apps/webui/src/app.ts:42"]},
      "evidence": "apps/webui imports from apps/electron/src/shared (inverted)",
      "root_cause": "shared helper never extracted to packages/; apps reach sideways instead",
      "fix_direction": "extract to packages/shared-ui or duplicate the helper in webui",
      "blueprint_anchor": null,
      "synthesis_depth": "draft",
      "source": "fast_agent_a"
    }
  ]
}
```

```
Save output: /tmp/archie_agent_a.json
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

Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **health and complexity**.

Before emitting any findings, Read the spec file and follow §1 (schema), §2 (quality gate), §3 (severity rubric), §4 (taxonomy).

Produce:

1. **health_scores** (existing — preserve): a summary of erosion, gini, top20_share, verbosity, total_loc for the viewer's Health tab.

2. **trend**: direction + details, comparing against health_history.json. Unchanged shape.

3. **findings** in your domain:
   - **Localized**: `complexity_hotspot` for functions with CC ≥ 10 (severity per the spec's CC rubric: ≥50 error, 25-49 warn, 10-24 info), `abstraction_bypass` where a single-method class or tiny function obscures structure.
   - **Systemic** (only when substantiated): `trajectory_degradation` when ≥3 hotspots are all worsening over history. If you spot copy-paste or a repeated helper shape, leave it for Agent C's `missing_abstraction`/`fragmentation` — do not emit here.

All findings MUST carry `synthesis_depth: "draft"` and `source: "fast_agent_b"`.

For each complexity_hotspot, `root_cause` must be mechanistic — NOT "high CC" but "conflates auth validation with request parsing". Use skeletons first; Read the source only when CC signature is insufficient.

Before emitting, verify each finding against the quality gate in §2 of the spec — dropped candidates are better than padded ones.

**Output:** Write to `/tmp/archie_agent_b.json`:

```json
{
  "health_scores": {"erosion": 0.31, "gini": 0.58, "top20_share": 0.72, "verbosity": 0.003, "total_loc": 9400},
  "trend": {"direction": "degrading", "details": "top-20 share grew 0.64 → 0.72 over 3 scans"},
  "findings": [
    {
      "category": "localized",
      "type": "complexity_hotspot",
      "severity": "error",
      "scope": {"kind": "single_file", "components_affected": ["apps/electron"], "locations": ["apps/electron/src/AppShell.tsx:45:render"]},
      "evidence": "AppShell.render has CC=669; combines layout + routing + state wiring + providers",
      "root_cause": "organic accretion: render grew to serve as god-function for startup; no extraction ever happened",
      "fix_direction": "split into AppLayout + AppRouter + AppProviders (three components, each <CC 50)",
      "synthesis_depth": "draft",
      "source": "fast_agent_b"
    }
  ]
}
```

```
Save output: /tmp/archie_agent_b.json
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

Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **rules, patterns, and duplication**.

Before emitting any findings, Read the spec file and follow §1 (schema), §2 (quality gate), §3 (severity rubric), §4 (taxonomy).

Produce:

1. **findings**:
   - **Systemic**: `fragmentation` (same job done N different ways — e.g., 5 handlers each implement auth differently), `missing_abstraction` (copy-paste without helper), `inconsistency` (feature built one way in component X and another way in component Y). Each with ≥3 evidence locations.
   - **Localized**: `pattern_divergence` (outlier that breaks a pattern 0.7+ confident), `semantic_duplication` (near-twin functions), `rule_violation` (code breaking an adopted rule from `.archie/rules.json`).

2. **proposed_rules** (existing — preserve): new rules discovered in this scan, per the existing rule schema with `{id, description, rationale, severity, confidence}`.

3. **rule_confidence_updates** (existing — preserve): adjustments to previously-proposed rule confidence.

All findings MUST carry `synthesis_depth: "draft"` and `source: "fast_agent_c"`.

Be honest about systemic vs localized: if ≥3 locations exhibit the same problem, it's systemic; a single outlier is localized.

Before emitting, verify each finding against the quality gate in §2 of the spec — dropped candidates are better than padded ones.

**Output:** Write to `/tmp/archie_agent_c.json`:

```json
{
  "findings": [
    {
      "category": "systemic",
      "type": "fragmentation",
      "severity": "error",
      "scope": {"kind": "cross_component", "components_affected": ["handlers"], "locations": ["handlers/orders.ts:23", "handlers/users.ts:15", "handlers/reports.ts:41", "handlers/admin.ts:12"]},
      "pattern_description": "auth enforcement is done inline in each handler with divergent policies",
      "evidence": "4 handlers each validate session differently; no shared middleware",
      "root_cause": "first handler copy-pasted as pattern; subsequent handlers added domain checks inline rather than extending a shared guard",
      "fix_direction": "extract authGuard({scope?, role?, allowServiceToken?}) middleware; migrate admin → reports → users → orders",
      "blast_radius": 4,
      "synthesis_depth": "draft",
      "source": "fast_agent_c"
    },
    {
      "category": "localized",
      "type": "rule_violation",
      "severity": "warn",
      "scope": {"kind": "single_file", "components_affected": ["apps/api"], "locations": ["apps/api/src/handlers/orders.ts:12"]},
      "evidence": "handler imports from internal/ — breaks rule scan-042 (handlers must not depend on internal/)",
      "root_cause": "quick import while adding order history; missed during review",
      "fix_direction": "route through the orders service layer or widen the rule",
      "synthesis_depth": "draft",
      "source": "fast_agent_c"
    }
  ],
  "proposed_rules": [{"id": "scan-NNN", "description": "...", "rationale": "...", "severity": "error|warn", "confidence": 0.85}],
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
Save output: /tmp/archie_agent_c.json
```

**Wait for all 3 agents to complete before proceeding to Phase 4.**

---

## Phase 4: Synthesis + Blueprint Evolution

### 4a: Aggregate findings → semantic_findings.json

Before synthesizing the blueprint, extract the findings from each agent's output into per-source files in `.archie/`, then invoke the aggregator. This produces the unified `semantic_findings.json` consumed by the viewer and the next scan (dedupe by signature, quality gate, lifecycle diff against the prior run).

```bash
python3 .archie/extract_output.py findings /tmp/archie_agent_a.json "$PROJECT_ROOT/.archie/semantic_findings_fast_a.json"
python3 .archie/extract_output.py findings /tmp/archie_agent_b.json "$PROJECT_ROOT/.archie/semantic_findings_fast_b.json"
python3 .archie/extract_output.py findings /tmp/archie_agent_c.json "$PROJECT_ROOT/.archie/semantic_findings_fast_c.json"
python3 .archie/aggregate_findings.py "$PROJECT_ROOT"
```

The aggregator reads every `semantic_findings_*.json` source it knows about in `.archie/`, merges by signature, applies the quality gate, computes `lifecycle_status` against the prior `semantic_findings.json`, and writes the canonical result back to `.archie/semantic_findings.json`.

### 4b: Evolve the Blueprint

Read the inputs to synthesis:
- `.archie/semantic_findings.json` — the aggregated, gated, lifecycle-tagged canonical findings from 4a (primary input for findings + rules reasoning)
- `/tmp/archie_agent_a.json`, `/tmp/archie_agent_b.json`, `/tmp/archie_agent_c.json` — raw per-agent output (use for `pattern_observations`, `health_scores`, `trend`, `proposed_rules`, `rule_confidence_updates` — fields the aggregator does NOT carry)
- `.archie/blueprint.json` — current state of accumulated knowledge

Now you are the **synthesis agent**. Your job is to merge the aggregated findings + the per-agent auxiliary fields with the existing blueprint to produce an evolved blueprint. This is where compound learning happens.

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

### 4c: Write Scan Report

Get the current date/time and scan number from the blueprint (`meta.scan_count`):
```bash
date -u +"%Y-%m-%dT%H%M"
```

Create the scan history directory if it doesn't exist:
```bash
mkdir -p .archie/scan_history
```

Read `$PROJECT_ROOT/.archie/semantic_findings.json` (from 4a), `$PROJECT_ROOT/.archie/blueprint.json`, `$PROJECT_ROOT/.archie/health.json`, and `$PROJECT_ROOT/.archie/health_history.json` for health trend.

Write the report to `.archie/scan_history/scan_NNN_YYYY-MM-DDTHHMM.md` (where NNN is the zero-padded scan number, e.g., `scan_003_2026-04-08T1423.md`) and copy to `.archie/scan_report.md` (latest pointer).

Use this **exact** structure — this layout is shared with `/archie-deep-scan`; deep-scan and fast-scan produce structurally identical reports. The data provenance differs (fast-scan has no Wave 2 canonical findings — all entries will be `synthesis_depth: draft`) but the rendering is the same.

```markdown
# Scan Report — <repo name>

## Executive Summary
- Health score: X.XX (trend: ↑ / ↓ / → vs previous scan from `health_history.json`)
- Systemic findings: N total (new: X, recurring: Y, worsening: Z, resolved: W)
- Top 3 systemic findings by severity × blast_radius:
  1. [severity] type — component name (blast: N)
  2. [severity] type — component name (blast: N)
  3. [severity] type — component name (blast: N)

## Systemic Findings (N)

<For each finding where `category == "systemic"` AND `lifecycle_status != "resolved"`, render with the full expanded treatment below. Order by severity (error > warn > info) then `blast_radius` descending.>

### [severity · lifecycle] type — component name
**Pattern:** <pattern_description — one sentence>
**Evidence:**
- location1 — short why
- location2 — short why
- (more...)
**Root cause:** <root_cause>
**Fix direction:** <fix_direction>
**Severity:** <severity> — blast_radius: N (delta: +K / -K / 0)
**Blueprint anchor:** <blueprint_anchor if present, else omit line>

## Localized Findings (M)

<Compact tables grouped by `type`. Only emit a subsection if at least one finding of that type exists. Use these exact table schemas.>

### Dependency violations (k)
| Sev | Location | Evidence | Fix |
|---|---|---|---|
| error | path/file:line | short detail | short fix |

### Cycles (k)
| Sev | Modules | Evidence | Fix |
|---|---|---|---|

### Complexity hotspots (k)
| Sev | Function | CC | Location | Why | Fix |
|---|---|---:|---|---|---|

### Pattern divergences (k)
| Sev | Location | Evidence | Fix |
|---|---|---|---|

### Rule violations (k)
| Sev | Rule | Location | Evidence | Fix |
|---|---|---|---|---|

### Semantic duplications (k)
| Sev | Canonical | Duplicates | Fix |
|---|---|---|---|

### Pattern erosion (k)
| Sev | File | Violated pattern | Fix |
|---|---|---|---|

### Decision violations (k)
| Sev | Decision | Location | Evidence | Fix |
|---|---|---|---|---|

### Trade-offs undermined (k)
| Sev | Trade-off | Location | Evidence | Fix |
|---|---|---|---|---|

### Pitfalls triggered (k)
| Sev | Pitfall | Location | Evidence | Fix |
|---|---|---|---|---|

### Responsibility leaks (k)
| Sev | Location | Evidence | Fix |
|---|---|---|---|

### Abstraction bypasses (k)
| Sev | Location | Evidence | Fix |
|---|---|---|---|

## Resolved Findings (W)

<Compressed list of findings where `lifecycle_status == "resolved"`. Group by `type`. Omit the section entirely if W == 0.>

## Mechanical Findings (p)

<Findings where `source == "mechanical"` — output of `drift.py` that AI analysis didn't subsume. Keep compact (1 line per item: severity, type, location, one-line detail). Omit the section if p == 0.>
```

**Rendering rules:**

- Order within Systemic Findings: severity (error > warn > info), then `blast_radius` descending.
- Within each Localized table, order by severity then by location string for stable diffs.
- "component name" in the Top-3 summary and Systemic headings comes from `scope.components_affected[0]` if present, else derived from the first location.
- `blast_radius_delta` renders as `+K` (worsening), `-K` (improving), or `0` (unchanged). Omit parentheses if the finding is new and delta is 0.
- When the aggregator produces zero findings in a section, include the heading only if the section has a count in parentheses (so `## Systemic Findings (0)` stays; empty Localized subsections are omitted).
- `blueprint_anchor` lines: include only when the field is non-null.

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

Derive the legacy `.archie/semantic_duplications.json` snapshot from the aggregated findings (for `/archie-share` + old-viewer backward compat):
```
1. Read .archie/semantic_findings.json (the aggregator's canonical output from 4a)
2. Filter `findings` where `type == "semantic_duplication"` — this replaces the previous "read Agent C's duplications array" flow; duplications now live inside the findings stream tagged with that type
3. For each matching finding, map to the legacy entry shape: {function, locations, recommendation}
   - function: derive from the finding's first location (e.g. "path/to/file.ts::symbol") or from `pattern_description` — whichever reads cleanest
   - locations: `scope.locations` (list of "file:line" strings)
   - recommendation: `fix_direction`
4. Write to .archie/semantic_duplications.json as {"duplications": [...], "scanned_at": "<ISO UTC>"}
5. Overwrite on every scan — this is a snapshot of the current state, not append-only
```

This is what `/archie-share` surfaces as "N semantic reimplementations" alongside the textual verbosity metric. The canonical source of truth is now `semantic_findings.json`; this legacy file exists only so the current `/archie-share` upload path and the current viewer keep working during the transition.

### 4e: Clean up temp files

```bash
rm -f /tmp/archie_agent_a.json /tmp/archie_agent_b.json /tmp/archie_agent_c.json
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

# Shared fragment — Agent: Health (complexity, erosion, trends)

> **This is the source of truth for the Health agent prompt used by both `/archie-scan` and `/archie-deep-scan`.**
> Slash commands can't include other files, so the block below is physically inlined into both.
> When updating this fragment, update BOTH archie-scan.md AND archie-deep-scan.md, then re-sync to npm-package/assets/.

---

You are analyzing the HEALTH and COMPLEXITY of a codebase. You have access to health metrics, complexity data, and historical trends.

**Your inputs:**
- `.archie/health.json` — current erosion, gini, verbosity, waste, function-level complexity (cyclomatic complexity per function)
- `.archie/health_history.json` — historical health scores (for trend analysis across scans)
- `.archie/skeletons.json` — every file's header, class/function signatures, imports, line counts
- `.archie/blueprint.json` — existing architectural knowledge (if any)

**Your job:**

### 1. Health Scores
Compute a summary of the current health state from `health.json`: erosion, gini, top20_share, verbosity, total_loc. These populate the viewer's Health tab and feed into the scan report.

### 2. Trend Analysis
Compare current health scores against `health_history.json` (if it exists) to determine the trajectory:
- **direction**: `improving`, `stable`, or `degrading`
- **details**: Describe what changed and by how much (e.g., "top-20 share grew 0.64 -> 0.72 over 3 scans", "erosion stable at 0.28 for 5 scans")

If no history exists, set direction to `stable` and note "first scan — no trend data".

### 3. Complexity Hotspots
Identify functions with cyclomatic complexity (CC) >= 10 from `health.json`. Severity per the spec's CC rubric:
- CC >= 50: `error`
- CC 25-49: `warn`
- CC 10-24: `info`

For each hotspot, the `root_cause` must be **mechanistic** — NOT "high CC" but a specific explanation of why the function is complex. Examples:
- "conflates auth validation with request parsing and response formatting in a single method"
- "switch statement handles 14 message types with inline processing for each"
- "nested conditionals for 6 platform variants with platform-specific retry logic interleaved"

Use skeletons first to understand the function's signature and context. Read the actual source file only when the skeleton is genuinely insufficient to determine why the function is complex.

### 4. Trajectory Degradation
Only when substantiated by history: if >=3 complexity hotspots are ALL worsening over `health_history.json` entries, emit a systemic `trajectory_degradation` finding.

### 5. Abstraction Bypass
Identify cases where a single-method class, tiny wrapper function, or trivial indirection layer exists that obscures rather than clarifies the underlying structure. These are localized findings.

**Important boundary:** If you spot copy-paste or a repeated helper shape, leave it for the Patterns agent's `missing_abstraction` / `fragmentation` findings — do not emit those here.

**Efficiency rule:** Read skeletons.json + health.json first. Only use the Read tool on source files when the CC signature in the skeleton is genuinely insufficient to determine the mechanistic root cause.

**Findings:**
Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **health and complexity**.
Before emitting, Read the spec file and follow S1 (schema), S2 (quality gate), S3 (severity rubric), S4 (taxonomy).

Produce:
- **Localized**: `complexity_hotspot` (functions with CC >= 10, severity per CC rubric above), `abstraction_bypass` (trivial indirection obscuring structure). Each with a single location, root_cause, fix_direction.
- **Systemic** (only when substantiated): `trajectory_degradation` (>=3 hotspots all worsening over history). With >=3 evidence locations, pattern_description, root_cause, fix_direction, blast_radius.

All findings MUST carry `synthesis_depth: "draft"` and `source: "agent_health"`.

Do NOT emit count caps. Emit every finding you can substantiate with concrete evidence. Before emitting, verify each finding against the quality gate in S2 of the spec — dropped candidates are better than padded ones.

**Output:** Write to `/tmp/archie_agent_health.json`:
```json
{
  "health_scores": {
    "erosion": 0.31,
    "gini": 0.58,
    "top20_share": 0.72,
    "verbosity": 0.003,
    "total_loc": 9400
  },
  "trend": {
    "direction": "degrading",
    "details": "top-20 share grew 0.64 -> 0.72 over 3 scans"
  },
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
      "source": "agent_health"
    },
    {
      "category": "systemic",
      "type": "trajectory_degradation",
      "severity": "warn",
      "scope": {"kind": "cross_component", "components_affected": ["apps/electron", "apps/webui"], "locations": ["apps/electron/src/AppShell.tsx:45", "apps/webui/src/Dashboard.tsx:12", "apps/webui/src/Settings.tsx:88"]},
      "pattern_description": "3 hotspots all grew CC by >20% over last 4 scans",
      "evidence": "AppShell.render CC 520->669, Dashboard.main CC 35->48, Settings.handleSave CC 18->29",
      "root_cause": "feature additions land in existing god-functions rather than extracting new components; no complexity budget enforced",
      "fix_direction": "establish CC ceiling (50) in CI; refactor the 3 hotspots in priority order",
      "blast_radius": 3,
      "synthesis_depth": "draft",
      "source": "agent_health"
    }
  ]
}
```

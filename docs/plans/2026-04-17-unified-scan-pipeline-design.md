# Unified Scan Pipeline — Design

**Status:** Design, pending approval.

**Audience:** Archie maintainers evolving `/archie-scan` and `/archie-deep-scan`.

**Supersedes:** `docs/plans/2026-04-16-semantic-findings-design.md` (pipeline architecture only — the Semantic Findings schema, aggregator, upload v2, and viewer panel from that design are retained).

---

## TL;DR

Both scan commands share ONE agent roster (Structure, Patterns, Health, Technology), ONE findings spec, and ONE blueprint lifecycle. The only fork is the synthesis step: Sonnet (scan) vs Opus (deep-scan). Scan produces an architectural overview + draft findings. Deep-scan deepens the blueprint with decisions, pitfalls, trade-offs, canonical findings, and per-folder CLAUDE.md via the Intent Layer. Both commands emit timing telemetry so we can measure actual performance instead of guessing.

Both commands populate the blueprint from run 1. Blueprint reflects current reality — sections are rewritten when code changes, not preserved as historical artifacts.

---

## Core values driving this design

1. **Blueprint as guardrails** — AI agents follow CLAUDE.md, per-folder CLAUDE.md, rules. The blueprint must be populated (even if thin) for this to work.
2. **Problem surfacing** — Semantic Findings surface errors, drift, architectural violations so humans can act.
3. **User trust** — user inspects the blueprint in the viewer, sees it's accurate, trusts the product.

Both commands must serve all three values. Scan-only users must never see an empty viewer or thin CLAUDE.md.

---

## Two commands, well-defined scopes

### `/archie-scan` — findings + rules + architectural overview

Run after every material change. Primary value is problem surfacing.

- **Findings:** Semantic Findings (draft depth) — systemic + localized with root_cause, fix_direction, blast_radius, lifecycle tracking
- **Rules:** proposed rules discovered by the Patterns agent
- **Architectural overview:** components, layers, architecture style, file placement, naming conventions, communication patterns, integrations, tech stack, health metrics
- **Blueprint:** thin on first run, evolves each subsequent run. Does NOT produce decisions, pitfalls, trade-offs, architecture diagram, or implementation guidelines — those are deep-scan territory.

### `/archie-deep-scan` — deep reasoning layer

Run on first install, after major refactors, or when Opus-depth reasoning is wanted.

- **Everything scan produces** — same agents, same facts, same findings
- **Plus Opus synthesis:** decisions (with decision_chain, forced_by/enables, violation_keywords), trade-offs (with violation_signals), pitfalls (with stems_from causal chains), architecture diagram (Mermaid), implementation guidelines
- **Plus "what's unusual":** 4-8 distinctive architectural decisions that deviate from standard patterns — the choices a new team member would be surprised by or that someone evaluating the codebase would find most interesting. Not just generic "uses MVVM" observations, but the domain-specific, unusual decisions that make this codebase unique.
- **Canonical findings:** Opus upgrades draft findings to canonical depth (richer root_cause, sequenced fix_direction)
- **Intent Layer:** per-folder CLAUDE.md generation (default — part of the deep-scan pipeline)

---

## Unified agent roster

4 parallel Sonnet agents, shared by both commands. Each produces blueprint facts AND semantic findings in its domain. Agents read skeletons first, selectively read actual source files when needed.

### Agent 1: Structure

**Reads:** `skeletons.json`, `dependency_graph.json`, `scan.json`, `blueprint.json` (if exists). Selective source reads when skeletons are insufficient.

**Blueprint facts:**

```json
{
  "meta": {
    "architecture_style": "plain language description",
    "platforms": ["backend", "android"],
    "executive_summary": "3-5 factual sentences"
  },
  "components": [{
    "name": "", "location": "", "platform": "",
    "responsibility": "", "depends_on": [], "exposes_to": [],
    "key_interfaces": [{"name": "", "methods": [], "description": ""}],
    "key_files": [{"file": "", "description": ""}]
  }],
  "layers": [{
    "name": "", "platform": "", "location": "",
    "responsibility": "", "contains": [], "depends_on": [], "exposes_to": []
  }],
  "architecture_rules": {
    "file_placement_rules": [{"component_type": "", "naming_pattern": "", "location": "", "example": ""}],
    "naming_conventions": [{"scope": "", "pattern": "", "examples": []}]
  },
  "workspace_topology": { /* monorepo only */ }
}
```

**Findings:** `dependency_violation`, `cycle`, `god_component`, `boundary_violation`

**Pattern observations:** `dep_magnet`, `layer_cycle`, `inverted_dependency`, `workspace_boundary_crossed`, `high_fan_in_rising`

### Agent 2: Patterns

**Reads:** `skeletons.json`, `scan.json`, `rules.json`, `proposed_rules.json`, `blueprint.json` (if exists). Selective source reads for pattern confirmation.

**Blueprint facts:**

```json
{
  "communication": {
    "patterns": [{"name": "", "when_to_use": "", "how_it_works": "", "examples": []}],
    "integrations": [{"service": "", "purpose": "", "integration_point": ""}],
    "pattern_selection_guide": [{"scenario": "", "pattern": "", "rationale": ""}]
  }
}
```

**Findings:** `fragmentation`, `missing_abstraction`, `inconsistency`, `pattern_divergence`, `semantic_duplication`, `rule_violation`

**Also produces:** `proposed_rules`, `rule_confidence_updates`

### Agent 3: Health

**Reads:** `health.json`, `health_history.json`, `skeletons.json`, `blueprint.json` (if exists). Selective source reads for CC interpretation.

**Blueprint facts:**

```json
{
  "health_scores": {"erosion": 0.0, "gini": 0.0, "top20_share": 0.0, "verbosity": 0.0, "total_loc": 0},
  "trend": {"direction": "stable", "details": ""}
}
```

**Findings:** `complexity_hotspot`, `trajectory_degradation`, `abstraction_bypass`

### Agent 4: Technology

**Reads:** config files only — `package.json`, `build.gradle`, `Dockerfile`, CI/CD configs, `.env.example`, `Makefile`. No source code reads.

**Blueprint facts:**

```json
{
  "technology": {
    "stack": [{"category": "", "name": "", "version": "", "purpose": ""}],
    "run_commands": {},
    "project_structure": "",
    "templates": {}
  },
  "deployment": {
    "runtime_environment": "",
    "compute_services": [],
    "ci_cd": [],
    "container": {},
    "distribution": {}
  },
  "development_rules": [{"rule": "", "source": ""}]
}
```

**Findings:** none — config-only domain.

---

## Pipeline: `/archie-scan`

| Step | What | How |
|---|---|---|
| 1 | Scan | `scanner.py` + `measure_health.py` + `detect_cycles.py` (deterministic) |
| 2 | Gather | 4 parallel Sonnet agents → blueprint facts + draft findings + pattern observations |
| 3 | Aggregate | `aggregate_findings.py` (deterministic) — merge, quality gate, lifecycle |
| 4 | Light synthesis | **Sonnet** — reads 4 agent outputs + existing blueprint → produces executive summary + architecture style characterization. Small prompt, small output. |
| 5 | Merge + Render | Deterministic — assemble agent facts + synthesis into `blueprint.json` → `renderer.py` → CLAUDE.md, AGENTS.md, rules, `scan_report.md` |

**AI calls: 5** (4 agents + 1 light synthesis)

---

## Pipeline: `/archie-deep-scan`

| Step | What | How |
|---|---|---|
| 1 | Scan | Same deterministic scripts |
| 2 | Gather | Same 4 parallel Sonnet agents, same prompts |
| 3 | Aggregate | Same `aggregate_findings.py` |
| 4 | Deep synthesis | **Opus** — reads 4 agent outputs + existing blueprint → produces: |
| | | - Decisions: key_decisions with forced_by/enables, decision_chain with violation_keywords |
| | | - 4-8 distinctive architectural decisions ("surface what's unusual, not just what's obvious" — choices that deviate from standard patterns, custom protocols, unusual process architectures, non-standard state lifecycles) |
| | | - Trade-offs with violation_signals |
| | | - Pitfalls with stems_from causal chains |
| | | - Architecture diagram (Mermaid) |
| | | - Implementation guidelines (capability, libraries, pattern, key_files, usage_example, tips) |
| | | - Upgrade pass: re-processes draft findings → canonical depth (richer root_cause, sequenced fix_direction) |
| 5 | Merge + Render | Same deterministic pipeline |
| 6 | Intent Layer | Per-folder CLAUDE.md via DAG scheduling (default, not opt-in) |

**AI calls: 5 + N** (4 agents + 1 Opus synthesis + N Intent Layer calls for folders with source files).

---

## Blueprint lifecycle

The blueprint is a living document. Either command can create or evolve it.

```
Run 1 (/archie-scan):      blueprint created — thin (architectural overview, no decisions/pitfalls)
Run 2 (/archie-scan):      blueprint evolved — findings compound, components refined
Run 3 (/archie-deep-scan): blueprint evolved — Opus deepens with decisions, pitfalls, trade-offs, diagram
Run 4 (/archie-scan):      blueprint evolved — now with richer context from deep-scan
```

Or:

```
Run 1 (/archie-deep-scan): blueprint created at Opus depth
Run 2 (/archie-scan):      blueprint evolved incrementally
```

Either order works. **Blueprint reflects current reality.** If code changed, blueprint changes. Sections are rewritten when they no longer match the code — accuracy beats preservation.

---

## Semantic Findings (retained from prior design)

The Semantic Findings schema, aggregator, quality gate, and lifecycle tracking from the `2026-04-16-semantic-findings-design.md` are retained unchanged:

- **Schema:** category (systemic/localized), type (21 types), severity, scope, pattern_description, evidence, root_cause, fix_direction, blueprint_anchor, blast_radius, blast_radius_delta, lifecycle_status, synthesis_depth (draft/canonical), source
- **Quality gate:** systemic requires pattern_description + ≥3 evidence + root_cause + fix_direction + blast_radius; localized requires 1 evidence + root_cause + fix_direction
- **Severity rubric:** from `_shared/semantic_findings_spec.md`
- **Lifecycle:** new / recurring / resolved / worsening with blast_radius_delta
- **Aggregator:** `aggregate_findings.py` with `_adapt_mechanical` for drift.py output, case normalization, severity promotion guard
- **synthesis_depth:** draft (from scan agents) / canonical (from deep-scan Opus synthesis + upgrade pass)
- **No count caps** — quality gate is the only filter

---

## `scan_report.md` layout (retained)

Both commands produce the same report format:

```
# Scan Report — <repo>

## Executive Summary
Health score, trend, systemic finding count + top 3

## Systemic Findings (N)
Full treatment per finding — pattern, evidence, root_cause, fix_direction, blast_radius

## Localized Findings (M)
Compact tables grouped by type

## Resolved Findings (W)
Compressed list

## Mechanical Findings (p)
From drift.py
```

---

## `/archie-share` (retained + adapted)

`upload.py` bundles:
- `blueprint.json` (always — may be thin from scan or deep from deep-scan)
- `semantic_findings` (structured JSON — from `semantic_findings.json`)
- `scan_report` (markdown string)
- `health` (health scores with fallback to history)
- `scan_meta`, `rules_adopted`, `rules_proposed` (existing)
- `semantic_duplications` (legacy key for old-viewer compat — derived from semantic_findings)
- `bundle_version: "v2"` when semantic_findings present

Wave/phase intermediate files (`semantic_findings_wave1.json`, etc.) are NOT bundled.

**Change from prior design:** Since both commands now use the same agent roster, there's no "wave1/wave2/phase2" intermediate distinction for scan. Scan's agents write directly to per-agent temp files; aggregator merges them. Deep-scan's Opus synthesis writes to a synthesis output file; aggregator merges that too.

---

## `/archie-viewer` (retained + adapted)

### Local viewer (`viewer.py`)

- `/api/semantic-findings` endpoint serves `semantic_findings.json`
- Semantic Findings panel: systemic cards + localized tables + resolved + mechanical
- Legacy Drift Findings panel as fallback when `semantic_findings.json` absent
- `synthesis_depth: "draft"` shows "provisional" badge; canonical is default render

### Share viewer (React, `share/viewer/`)

- `Bundle` interface includes `semantic_findings` and `bundle_version`
- Prefers structured `semantic_findings` over markdown-parsed `scan_report` for the "Architectural Problems" section
- Falls back to markdown parsing for v1 bundles (no `semantic_findings`)
- Systemic findings: full card treatment with pattern, evidence, root_cause, fix_direction, blast_radius
- Localized findings: compact rendering with fix_direction
- Lifecycle badges: NEW (teal), RECURRING (neutral), WORSENING (red), RESOLVED (gray)
- "provisional" badge for draft synthesis_depth

---

## What changes vs current main

| Area | Main (current) | Proposed |
|---|---|---|
| Agent roster | 3 scan agents (A, B, C) + 4 deep-scan Wave 1 (Structure, Patterns, Technology, UI) = **7 prompts** | 4 unified agents (Structure, Patterns, Health, Technology) = **4 prompts** |
| Deep-scan pipeline | 9 steps, ~70 AI calls (Wave 1 + Wave 2 + normalize + rule synthesis + deep-drift + Intent Layer) | 5-6 steps, 5 AI calls + opt-in Intent Layer |
| Scan blueprint | Thin — components + style only; decisions/pitfalls/trade-offs empty without deep-scan | Thin but populated — architectural overview (components, layers, style, file placement, communication, tech stack). Decisions/pitfalls still require deep-scan. |
| Scan CLAUDE.md | Minimal without deep-scan | Architectural overview narrative from run 1 |
| Findings | Two different pipelines, different severities for same issues | One pipeline, one spec, one schema, calibration-consistent |
| Deep-scan AI calls | ~70 (Wave 1 + Wave 2 + normalize + rule synthesis + deep-drift + Intent Layer) | 5 + N Intent Layer (need to measure via telemetry) |
| Scan AI calls | 4 (3 agents + synthesis) | 5 (4 agents + light synthesis) (need to measure via telemetry) |
| Timing data | None — all estimates were guesses | Per-step telemetry: `.archie/telemetry/{command}_{timestamp}.json` |
| Findings schema | Flat bespoke JSON per agent | Unified Semantic Findings: root_cause, fix_direction, blast_radius, lifecycle |
| Deep-scan distinctive decisions | Generic observations ("uses MVVM") | 4-8 distinctive decisions — unusual patterns, custom protocols, non-standard architectures |

---

## What survives from PR #44 (docs/scan-consolidation branch)

| Artifact | Status |
|---|---|
| `aggregate_findings.py` + 26 tests | **Survives** |
| `_shared/semantic_findings_spec.md` | **Survives** |
| `extract_output.py` findings + concat-findings | **Survives** |
| `upload.py` v2 bundle + tests | **Survives** |
| `viewer.py` Semantic Findings panel | **Survives** |
| Share viewer (React) update | **Survives** |
| npm installer `_shared/` support | **Survives** |
| `verify_sync.py` `_shared/` coverage | **Survives** |
| `archie-scan.md` prompts | **Rewrite** — 4 unified agents replacing current 3 |
| `archie-deep-scan.md` prompts | **Rewrite** — collapse 9 steps to 6, drop Wave 1/Wave 2 distinction |

~60% of PR #44 carries forward. The slash command prompts are the main rewrite.

---

## Risks

1. **Scan gets slower** — adding Technology agent + richer output + synthesis + render step vs current 1-3 min. Telemetry will reveal actual impact. Acceptable if under 8 min; concerning if over 10.
2. **Component detail thinner in deep-scan** — agents read skeletons, not full source. `key_interfaces`, `exposes_to`, detailed `responsibility` descriptions may be less rich than current full-source-reading Wave 1. Mitigated by agents' selective source reads when skeletons are insufficient.
3. **Intent Layer runtime on deep-scan** — still the dominant cost for large projects with many directories. Must be optimized (filter resource dirs, batch, parallelize) but that's a separate initiative.
4. **Timing is unmeasured** — telemetry system (below) will provide real data. No runtime claims until measured.
5. **Rewrite scope** — both slash commands need significant rewrite. Agent prompts, synthesis prompts, pipeline wiring.

---

## Timing telemetry

Both commands emit per-step timing to `.archie/scan_telemetry.json` so we can measure actual performance instead of guessing. Written by the slash command prompt instructing the model to record timestamps at each step boundary.

### Schema

```json
{
  "command": "archie-scan | archie-deep-scan",
  "started_at": "ISO UTC",
  "completed_at": "ISO UTC",
  "total_seconds": 0,
  "project": {
    "source_files": 0,
    "total_loc": 0,
    "directories": 0
  },
  "steps": [
    {
      "name": "scan",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0
    },
    {
      "name": "gather:structure",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0
    },
    {
      "name": "gather:patterns",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0
    },
    {
      "name": "gather:health",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0
    },
    {
      "name": "gather:technology",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0
    },
    {
      "name": "aggregate",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0
    },
    {
      "name": "synthesis",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0,
      "model": "sonnet | opus"
    },
    {
      "name": "render",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0
    },
    {
      "name": "intent_layer",
      "started_at": "ISO UTC",
      "completed_at": "ISO UTC",
      "seconds": 0,
      "folders_processed": 0
    }
  ]
}
```

### File naming — one file per run per type

Each run produces its own telemetry file:

```
.archie/telemetry/scan_2026-04-17T14-30-22Z.json
.archie/telemetry/scan_2026-04-17T16-45-10Z.json
.archie/telemetry/deep-scan_2026-04-17T18-00-05Z.json
```

Pattern: `.archie/telemetry/{command}_{ISO-timestamp}.json`

Separate files per run per type (scan vs deep-scan) so you can:
- Compare scan runs over time (is it getting faster/slower?)
- Compare scan vs deep-scan on the same project (what's the Opus delta?)
- Diff two runs side by side
- Track regression if a prompt change slows an agent

No overwriting, no appending to a single file. Each run is its own record.

### How it's produced

The slash command prompt instructs the model to:
1. Before each step: record `started_at` by running `python3 -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat())"`
2. After each step: record `completed_at` the same way
3. After completion: `mkdir -p .archie/telemetry/` and write the telemetry JSON to `.archie/telemetry/{command}_{timestamp}.json`

Since the 4 gather agents run in parallel, their individual times overlap. The `gather:*` entries capture per-agent wall-clock; the total step 2 time is `max(gather:*)`.

### What we measure

From telemetry data:
- **Total wall-clock** per command per project size
- **Per-step breakdown** — which step dominates (gather? synthesis? intent layer?)
- **Agent parallelism efficiency** — are agents roughly equal, or is one much slower?
- **Synthesis model cost** — Sonnet vs Opus actual time difference
- **Intent Layer cost** — folders processed × time, to identify optimization targets
- **Trend over runs** — does compound learning make subsequent scans faster or slower?

This replaces all the made-up estimates in prior documents with real data.

---

## Out of scope (follow-up)

- Project-configurable severity thresholds
- Intent Layer performance optimization (filtering resource dirs, batching, parallelism)
- Change-targeted scan mode (only analyze changed files via git diff)
- Programmatic prompt-drift detector (`verify_shared_prompts.py`)
- Viewer blast-radius visualization
- Auto-rule proposal from systemic findings

---

## Success criteria

1. Running `/archie-scan` on a project with no prior blueprint produces a populated viewer (components, layers, style, communication, tech stack, health, findings) — no empty sections in the architectural overview.
2. Running `/archie-deep-scan` on the same project deepens the blueprint with decisions, pitfalls, trade-offs, diagram, and 4-8 distinctive architectural decisions.
3. Both commands produce Semantic Findings with the same schema, same calibration, consistent severities.
4. Telemetry files produced for every run — per-step timing, project size, model used.
5. First measurement run on BabyWeather.Android establishes the real baseline for both commands.
6. A single prompt change (e.g., CC threshold) applies to both commands via `semantic_findings_spec.md`.
7. `/archie-share` produces a v2 bundle that the share viewer renders with the Semantic Findings panel populated.

# Unified Scan Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite both `/archie-scan` and `/archie-deep-scan` to share ONE agent roster (Structure, Patterns, Health, Technology), one findings spec, and one blueprint lifecycle. The only fork is the synthesis step: Sonnet (scan) vs Opus (deep-scan). Both produce timing telemetry.

**Architecture:** 4 shared agent prompts live in `.claude/commands/_shared/`. Both slash commands inline these prompts and diverge only at the synthesis step. Scan's synthesis is a light Sonnet call (executive summary + architecture style). Deep-scan's synthesis is an Opus call (decisions, pitfalls, trade-offs, distinctive decisions, diagram, guidelines, canonical findings upgrade) followed by the Intent Layer.

**Tech Stack:** Markdown slash commands (Claude Code), Python 3.9+ scripts (stdlib only), JSON data files. Existing infrastructure from PR #44 (aggregator, spec, upload, viewer) is retained.

**Design reference:** `docs/plans/2026-04-17-unified-scan-pipeline-design.md` (committed `c22f1ca`).

---

## What survives from PR #44 (no changes needed)

These files are already correct and tested:
- `archie/standalone/aggregate_findings.py` (26 tests)
- `.claude/commands/_shared/semantic_findings_spec.md`
- `archie/standalone/extract_output.py` (7 tests)
- `archie/standalone/upload.py` (12 tests)
- `archie/standalone/viewer.py` (Semantic Findings panel)
- `share/viewer/src/` (React share viewer update)
- `npm-package/bin/archie.mjs` (`_shared/` installer support)
- `scripts/verify_sync.py` (`_shared/` coverage)

---

## Phase A: Shared agent prompts (4 fragments)

Write the 4 agent prompts as `_shared/` fragments. These are the canonical source of truth — both commands inline the same text.

### Task 1: Write `_shared/agent_structure.md`

**Files:**
- Create: `.claude/commands/_shared/agent_structure.md`

**Content specification:**

The Structure agent covers architecture and dependencies. Its prompt must include these sections:

**Header:**
```markdown
# Shared fragment — Agent: Structure (architecture & dependencies)

> **This is the source of truth for the Structure agent prompt used by both `/archie-scan` and `/archie-deep-scan`.**
> Slash commands can't include other files, so the block below is physically inlined into both.
> When updating this fragment, update BOTH archie-scan.md AND archie-deep-scan.md, then re-sync to npm-package/assets/.
```

**Inputs section:**
- `.archie/skeletons.json` — every file's path, class/function signatures, imports, first lines
- `.archie/dependency_graph.json` — resolved directory-level graph with node/edge metrics
- `.archie/scan.json` — import graph, frameworks, file tree
- `.archie/blueprint.json` — existing architectural knowledge (if any)

**Analysis sections (what the agent does):**

1. **Project Type & Platforms** — monorepo/single-app/microservice, all platforms found, entry points
2. **Components** — from actual code: name, location, platform, responsibility (specific — reference actual classes), depends_on, exposes_to, key_interfaces, key_files
3. **Layers** — only if clearly identifiable from imports + directory structure. Structure type (layered/flat/modular/feature-based). Each layer: name, platform, location, responsibility, contains, depends_on, exposes_to
4. **Architecture Style** — plain language, evidence-based
5. **File Placement & Naming** — where tests/configs/components actually live, naming conventions with examples
6. **Framework Usage** — catalog from import statements

**New sections (from unified design):**

7. **Pattern observations** — raw anomalies for synthesis: `{type, evidence_locations, note}`. Types: `dep_magnet`, `layer_cycle`, `inverted_dependency`, `workspace_boundary_crossed`, `high_fan_in_rising`.
8. **Findings** — per `.claude/commands/_shared/semantic_findings_spec.md`. Only `dependency_violation` and `cycle` types (localized). `synthesis_depth: "draft"`, `source: "agent_structure"`.

**Efficiency rule:** Read skeletons + dep_graph first. Only Read source files when skeletons are genuinely insufficient.

**Quality gate reminder:** Before emitting, Read the spec file and verify each finding against §2.

**Output schema:**
```json
{
  "meta": {"architecture_style": "", "platforms": [], "executive_summary": ""},
  "components": {"structure_type": "", "components": [...]},
  "layers": [...],
  "architecture_rules": {"file_placement_rules": [...], "naming_conventions": [...]},
  "workspace_topology": {},
  "pattern_observations": [{"type": "", "evidence_locations": [], "note": ""}],
  "findings": [...]
}
```

**Workspace-aware addendum** (only when `SCOPE === "whole"`): Same workspace topology instructions as current Structure agent (lines 233-252 of current deep-scan). Treat each workspace member as a top-level component.

**What to reference while writing:** Read the current Structure agent prompt in `archie-deep-scan.md` (lines 228-331) AND the current Agent A prompt in `archie-scan.md` (lines 147-224). Merge the best of both. The Structure agent from deep-scan has richer component analysis; Agent A from scan has the findings + pattern_observations sections we added in PR #44.

**Commit:**
```bash
git add .claude/commands/_shared/agent_structure.md
git commit -m "docs(agents): shared Structure agent fragment"
```

---

### Task 2: Write `_shared/agent_patterns.md`

**Files:**
- Create: `.claude/commands/_shared/agent_patterns.md`

**Content specification:**

The Patterns agent covers communication patterns, integrations, and rule/pattern analysis.

**Inputs:**
- `.archie/skeletons.json`
- `.archie/scan.json`
- `.archie/rules.json` — currently adopted rules
- `.archie/proposed_rules.json` — previously proposed rules
- `.archie/blueprint.json` — existing knowledge (if any)

**Analysis sections (merged from Patterns agent + Agent C):**

1. **Structural Patterns** — DI, repository, factory, registry (backend); component composition, data fetching, state management, routing (frontend)
2. **Behavioral Patterns** — service orchestration, streaming, event-driven, optimistic updates, state machines
3. **Cross-Cutting Patterns** — error handling, validation, auth, logging, caching
4. **Internal Communication** — backend (method calls, events, buses), frontend (props, context, stores), cross-platform (API calls, shared types)
5. **External Communication** — HTTP/REST, message queues, streaming, database, real-time
6. **Third-Party Integrations** — ALL external services with purpose and integration point
7. **Frontend-Backend Contract** — how they communicate, shared types, error propagation
8. **Pattern Selection Guide** — for common scenarios, which pattern to use and why

**New sections:**

9. **Pattern observations** — raw anomalies for synthesis: `{type, evidence_locations, note}`. Types: `fragmentation_signal`, `missing_abstraction_signal`, `pattern_outlier`, `inconsistency_signal`.
10. **Findings** — per spec. Systemic: `fragmentation`, `missing_abstraction`, `inconsistency`. Localized: `pattern_divergence`, `semantic_duplication`, `rule_violation`. `synthesis_depth: "draft"`, `source: "agent_patterns"`.
11. **Proposed rules** — new rules discovered, with confidence calibration (0.3-1.0)
12. **Rule confidence updates** — adjustments to previously-proposed rules

**Output schema:**
```json
{
  "communication": {"patterns": [...], "integrations": [...], "pattern_selection_guide": [...]},
  "quick_reference": {"pattern_selection": {}, "error_mapping": {}},
  "pattern_observations": [...],
  "findings": [...],
  "proposed_rules": [...],
  "rule_confidence_updates": [...]
}
```

**What to reference:** Current Patterns agent in deep-scan (lines 352-439) AND current Agent C in scan (lines 287-375). Merge both.

**Commit:**
```bash
git add .claude/commands/_shared/agent_patterns.md
git commit -m "docs(agents): shared Patterns agent fragment"
```

---

### Task 3: Write `_shared/agent_health.md`

**Files:**
- Create: `.claude/commands/_shared/agent_health.md`

**Content specification:**

The Health agent covers complexity metrics, trend analysis, and health findings. Largely unchanged from current Agent B.

**Inputs:**
- `.archie/health.json` — current erosion, gini, verbosity, waste, function-level complexity
- `.archie/health_history.json` — historical health scores
- `.archie/skeletons.json`
- `.archie/blueprint.json` (if any)

**Analysis sections:**
1. **Health assessment** — each metric with thresholds (erosion, gini, top20_share, verbosity)
2. **Trend analysis** — compare against history, direction, which metrics moved
3. **Complexity hotspots** — functions with CC > 10, assessed from skeletons first
4. **Abstraction waste** — single-method classes, tiny functions

**Findings:** `complexity_hotspot`, `trajectory_degradation`, `abstraction_bypass`. `synthesis_depth: "draft"`, `source: "agent_health"`.

**Output schema:**
```json
{
  "health_scores": {"erosion": 0, "gini": 0, "top20_share": 0, "verbosity": 0, "total_loc": 0},
  "trend": {"direction": "", "details": ""},
  "findings": [...]
}
```

**What to reference:** Current Agent B in scan (lines 225-286). Largely copy with minor schema alignment.

**Commit:**
```bash
git add .claude/commands/_shared/agent_health.md
git commit -m "docs(agents): shared Health agent fragment"
```

---

### Task 4: Write `_shared/agent_technology.md`

**Files:**
- Create: `.claude/commands/_shared/agent_technology.md`

**Content specification:**

The Technology agent reads config files only (no source code) and produces the tech stack + deployment + dev rules sections.

**Inputs:** Config files and manifests only:
- `package.json` / `requirements.txt` / `build.gradle` / `Podfile` / `pubspec.yaml` / `Package.swift`
- CI/CD configs (GitHub Actions, Cloud Build, etc.)
- `Dockerfile`, Kubernetes configs, IaC files
- `Makefile`, build configs, `.env.example`
- NOT source files — this agent never reads `.ts`, `.py`, `.kt`, etc.

**Analysis sections:**
1. **Technology Stack** (14 categories): runtime, framework, database, cache, queue, AI/ML, auth, state management, styling, validation, testing, linting, monitoring, other
2. **Run Commands** — npm scripts, Makefile targets, etc.
3. **Project Structure** — ASCII tree of key directories
4. **Templates** — how to create new components/routes/services
5. **Deployment** — runtime environment, compute, container, orchestration, CI/CD, distribution, IaC, environment config
6. **Development Rules** — Always/Never rules derived from tooling and config (e.g., "Always register routes in api/app.py")

**Findings:** none — config-only domain, no architectural violations to detect.

**Output schema:**
```json
{
  "technology": {"stack": [...], "run_commands": {}, "project_structure": "", "templates": {}},
  "deployment": {"runtime_environment": "", "compute_services": [], "ci_cd": [], "container": {}, "distribution": {}},
  "development_rules": [{"rule": "", "source": ""}]
}
```

**What to reference:** Current Technology agent in deep-scan (lines 440-532). Largely copy.

**Commit:**
```bash
git add .claude/commands/_shared/agent_technology.md
git commit -m "docs(agents): shared Technology agent fragment"
```

---

### Task 5: Sync new fragments to npm-package + verify

**Files:**
- Copy: `.claude/commands/_shared/agent_*.md` → `npm-package/assets/_shared/`

```bash
cp .claude/commands/_shared/agent_structure.md npm-package/assets/_shared/
cp .claude/commands/_shared/agent_patterns.md npm-package/assets/_shared/
cp .claude/commands/_shared/agent_health.md npm-package/assets/_shared/
cp .claude/commands/_shared/agent_technology.md npm-package/assets/_shared/
python3 scripts/verify_sync.py
```

Expected: exit 0.

**Commit:**
```bash
git add npm-package/assets/_shared/
git commit -m "chore(npm): sync agent fragments to npm-package/assets/_shared"
```

---

## Phase B: Rewrite `/archie-scan`

### Task 6: Write new `archie-scan.md`

**Files:**
- Rewrite: `.claude/commands/archie-scan.md`

This is a FULL REWRITE. Read the current file first to understand what exists, then write the new version from scratch following the design.

**Structure of the new archie-scan.md:**

```markdown
# Archie Scan — Architecture Health Check with Compound Learning

[Usage line: just `/archie-scan`, plus `--reconfigure` flag]

## Phase 0: Resolve scope

[INLINE the full content from `.claude/commands/_shared/scope_resolution.md` — same as today, unchanged]

## Step 1: Scan (deterministic)

Run scanner + health measurement + cycle detection:
```bash
python3 .archie/scanner.py "$PROJECT_ROOT"
python3 .archie/measure_health.py "$PROJECT_ROOT" --append-history
python3 .archie/detect_cycles.py "$PROJECT_ROOT"
python3 -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat())" > /tmp/archie_step1_time.txt
```

Record telemetry start.

## Step 2: Gather (4 parallel agents)

[IMPORTANT: Record timestamp before spawning agents]

Spawn 4 Sonnet subagents in parallel (Agent tool, `model: "sonnet"`). Each agent receives the data from Step 1 and can read source files when needed.

**EFFICIENCY RULE:** Agents read skeletons.json which contains every file's path, class/function signatures, imports, and first lines. This is sufficient for pattern detection, outlier finding, and most analysis. Agents should ONLY use the Read tool on source files when the skeleton genuinely lacks the information needed to make a judgment.

**Write each agent's output to a temp file so Step 3 can aggregate them:**
- Structure → `/tmp/archie_agent_structure.json`
- Patterns → `/tmp/archie_agent_patterns.json`
- Health → `/tmp/archie_agent_health.json`
- Technology → `/tmp/archie_agent_technology.json`

### Agent: Structure

[INLINE the full content from `.claude/commands/_shared/agent_structure.md`]

Save output: /tmp/archie_agent_structure.json

### Agent: Patterns

[INLINE from `_shared/agent_patterns.md`]

Save output: /tmp/archie_agent_patterns.json

### Agent: Health

[INLINE from `_shared/agent_health.md`]

Save output: /tmp/archie_agent_health.json

### Agent: Technology

[INLINE from `_shared/agent_technology.md`]

Save output: /tmp/archie_agent_technology.json

**Wait for all 4 agents to complete before proceeding.**

[Record timestamp after agents complete]

## Step 3: Aggregate (deterministic)

Extract findings from each agent's output and invoke the aggregator:

```bash
python3 .archie/extract_output.py findings /tmp/archie_agent_structure.json "$PROJECT_ROOT/.archie/sf_structure.json"
python3 .archie/extract_output.py findings /tmp/archie_agent_patterns.json "$PROJECT_ROOT/.archie/sf_patterns.json"
python3 .archie/extract_output.py findings /tmp/archie_agent_health.json "$PROJECT_ROOT/.archie/sf_health.json"
python3 .archie/aggregate_findings.py "$PROJECT_ROOT"
```

[Record timestamp]

## Step 4: Light synthesis (Sonnet)

Spawn a single Sonnet subagent. It reads ALL 4 agent outputs + the existing blueprint (if any) and produces the narrative glue that ties the architectural overview together.

Tell the synthesis agent:

> Read these files:
> - /tmp/archie_agent_structure.json — components, layers, architecture style
> - /tmp/archie_agent_patterns.json — communication patterns, integrations
> - /tmp/archie_agent_health.json — health scores, trends
> - /tmp/archie_agent_technology.json — tech stack, deployment, dev rules
> - $PROJECT_ROOT/.archie/blueprint.json — existing blueprint (if any; skip if missing)
>
> Produce:
> 1. **Executive summary** (3-5 sentences): what this codebase does, primary tech, architecture style, current health state. Reference specific components and patterns — no generic filler.
> 2. **Architecture style characterization** (1 paragraph): what pattern, how it manifests across the codebase, what holds it together. If the existing blueprint has a style, evolve it — don't restart from scratch.
>
> Do NOT produce decisions, pitfalls, trade-offs, architecture diagram, or implementation guidelines — those are deep-scan territory.
>
> Return JSON:
> ```json
> {
>   "meta": {
>     "executive_summary": "...",
>     "architecture_style": "..."
>   }
> }
> ```

Save output: /tmp/archie_synthesis.json

[Record timestamp]

## Step 5: Merge + Render (deterministic)

Merge all agent outputs + synthesis into the blueprint, then render:

```bash
python3 .archie/merge.py "$PROJECT_ROOT" /tmp/archie_agent_structure.json /tmp/archie_agent_patterns.json /tmp/archie_agent_health.json /tmp/archie_agent_technology.json /tmp/archie_synthesis.json
python3 .archie/renderer.py "$PROJECT_ROOT"
```

The merge step:
1. Reads existing `blueprint.json` (or starts from `{}`)
2. Deep-merges each agent's output into the appropriate blueprint sections
3. Writes updated `blueprint.json`

The renderer produces: `CLAUDE.md`, `AGENTS.md`, rule files from `rules.json`

Write `scan_report.md` deterministically from `.archie/semantic_findings.json`:

[INLINE the scan_report.md template — same as current, with Executive Summary → Systemic → Localized → Resolved → Mechanical sections]

Derive legacy `semantic_duplications.json` from semantic_findings (for `/archie-share` backward compat).

Clean up temp files:
```bash
rm -f /tmp/archie_agent_structure.json /tmp/archie_agent_patterns.json /tmp/archie_agent_health.json /tmp/archie_agent_technology.json /tmp/archie_synthesis.json
```

[Record final timestamp]

## Step 6: Telemetry

Write timing telemetry:
```bash
python3 -c "
import json, os
from datetime import datetime, timezone
from pathlib import Path
# ... assemble telemetry JSON from recorded timestamps ...
# Write to .archie/telemetry/scan_{timestamp}.json
"
```

[Actually — this should NOT be inline Python. Create a small `write_telemetry.py` script or add a subcommand to an existing script. See Task 9.]

## Present Results

Show the user:
- Scan report highlights (top 3 systemic findings, health score + trend)
- New/worsening findings count
- Rules proposed count
- Blueprint evolution summary (what sections changed)
```

**Key decisions for the implementer:**
- Phase 0 (scope resolution): INLINE from `_shared/scope_resolution.md` exactly as current — no changes
- Agent prompts: INLINE from the `_shared/agent_*.md` fragments — with a maintainer comment at the top of Step 2 noting the shared fragments
- Temp file naming: `/tmp/archie_agent_{structure,patterns,health,technology}.json` (new names, replacing old `archie_agent_{a,b,c}.json`)
- Aggregator source files: `sf_structure.json`, `sf_patterns.json`, `sf_health.json` in `.archie/` (not `/tmp/`)
- `merge.py` may need updates — see Task 8

**What to reference while writing:**
- Current `archie-scan.md` (for Phase 0, Phase 1 scripts, Phase 4 synthesis style)
- `docs/plans/2026-04-17-unified-scan-pipeline-design.md` (for the pipeline spec)
- `_shared/agent_*.md` fragments (just written in Tasks 1-4)

**Commit:**
```bash
git add -f .claude/commands/archie-scan.md
git commit -m "feat(archie-scan): unified pipeline — 4 shared agents + light Sonnet synthesis + telemetry"
```

---

### Task 7: Rewrite `archie-deep-scan.md`

**Files:**
- Rewrite: `.claude/commands/archie-deep-scan.md`

FULL REWRITE. Same 4 agents as scan, but with Opus synthesis and Intent Layer.

**Structure of the new archie-deep-scan.md:**

```markdown
# Archie Deep Scan — Comprehensive Architecture Baseline

[Usage: `/archie-deep-scan`, plus `--from N`, `--continue`, `--incremental`, `--reconfigure`, `--with-intent-layer` is now unnecessary since Intent Layer is default]

[Preamble: determine starting step — same --from/--continue/--incremental logic as current]

## Phase 0: Resolve scope

[INLINE from _shared/scope_resolution.md — same as scan]

## Step 1: Scan (deterministic)

[Same as scan — scanner.py + measure_health.py + detect_cycles.py]
[Record telemetry]

## Step 2: Gather (4 parallel agents)

[IDENTICAL to scan Step 2 — same 4 agents, same prompts, same temp files]
[Record telemetry per agent]

## Step 3: Aggregate (deterministic)

[IDENTICAL to scan Step 3]
[Record telemetry]

## Step 4: Deep synthesis (Opus)

Spawn a single Opus subagent (`model: "opus"`). It reads ALL 4 agent outputs + existing blueprint and produces the full reasoning layer.

Tell the synthesis agent:

> Read these files:
> - /tmp/archie_agent_structure.json — components, layers, architecture style, pattern_observations
> - /tmp/archie_agent_patterns.json — communication, integrations, pattern_observations
> - /tmp/archie_agent_health.json — health scores, trends
> - /tmp/archie_agent_technology.json — tech stack, deployment, dev rules
> - $PROJECT_ROOT/.archie/blueprint.json — existing blueprint (evolve, don't restart)
> - $PROJECT_ROOT/.archie/skeletons.json — for cross-file pattern spotting
> - $PROJECT_ROOT/.archie/semantic_findings.json — prior findings for upgrade pass (skip if missing)
> - Key source files: entry points, main configs, core abstractions (targeted reads)
>
> With the COMPLETE picture of what was built and how, produce deep architectural reasoning:
>
> ### 1. Decision Chain
> [Same as current Wave 2: root constraint → forced decisions → violation_keywords]
>
> ### 2. Architectural Style Decision
> [Same as current Wave 2: title, chosen, rationale, alternatives_rejected]
>
> ### 3. Key Decisions (3-7)
> [Same: forced_by, enables]
>
> ### 4. Distinctive Decisions (4-8)
> Surface what's unusual, not just what's obvious. Identify 4-8 architectural decisions that are DISTINCTIVE to this codebase — choices a new team member would be surprised by or that deviate from the standard approach for this tech stack. Generic patterns (uses MVC, has a service layer) are NOT interesting. Examples of what IS interesting:
> - A custom protocol or communication mechanism (JSONL stdio, custom IPC)
> - An unusual process architecture (dual backends, in-process vs out-of-process split)
> - A permission/capability system that gates behavior
> - A non-standard state lifecycle or session model
> - Integration with an uncommon protocol or standard
>
> For each: explain WHAT it is, WHY it was chosen over the obvious alternative, and WHERE it manifests in the code.
>
> ### 5. Trade-offs (3-5)
> [Same: accept, benefit, caused_by, violation_signals]
>
> ### 6. Pitfalls (3-5+)
> [Same: area, description, recommendation, stems_from causal chain, applies_to]
>
> ### 7. Architecture Diagram
> [Same: Mermaid graph TD, 8-12 nodes]
>
> ### 8. Implementation Guidelines (5-8)
> [Same: capability, category, libraries, pattern_description, key_files, usage_example, tips]
>
> ### 9. Executive Summary
> 3-5 sentences tying everything together. What this codebase does, primary tech, architecture style, current state.
>
> ### 10. Findings (canonical)
> Produce canonical-tier Semantic Findings per `.claude/commands/_shared/semantic_findings_spec.md`.
> [Same canonical finding types and upgrade pass as current Wave 2 sections 9-10]
>
> Return JSON:
> [Full schema with decisions, pitfalls, architecture_diagram, implementation_guidelines, meta, findings]

Save output: /tmp/archie_deep_synthesis.json

[Record telemetry]

## Step 5: Merge + Render (deterministic)

[Same as scan Step 5, but merges deep synthesis output instead of light synthesis]

```bash
python3 .archie/merge.py "$PROJECT_ROOT" /tmp/archie_agent_structure.json /tmp/archie_agent_patterns.json /tmp/archie_agent_health.json /tmp/archie_agent_technology.json /tmp/archie_deep_synthesis.json
python3 .archie/renderer.py "$PROJECT_ROOT"
```

Also extract canonical findings from synthesis output:
```bash
python3 .archie/extract_output.py findings /tmp/archie_deep_synthesis.json "$PROJECT_ROOT/.archie/sf_synthesis.json"
python3 .archie/aggregate_findings.py "$PROJECT_ROOT"
```

Write scan_report.md, clean up temp files.
[Record telemetry]

## Step 6: Intent Layer

Per-folder CLAUDE.md via DAG scheduling. Uses `intent_layer.py`.

[INLINE the existing Intent Layer logic from current deep-scan Step 7]
[Record telemetry — folders_processed count]

## Telemetry

[Same as scan but includes synthesis model="opus" and intent_layer step]

## Present Results

[Same structure as scan but also highlight: key decisions found, distinctive decisions, pitfall count, intent layer folders processed]
```

**Flags to preserve:**
- `--from N` — resume from step N. Steps are now 1-6, not 1-9.
- `--continue` — resume from last completed step (from `deep_scan_state.json`)
- `--incremental` — process only changed files (existing logic)
- `--reconfigure` — re-run scope resolution

**What to reference:**
- Current `archie-deep-scan.md` (for scope resolution, scanner, incremental mode, intent layer, --from/--continue logic)
- Scan's new `archie-scan.md` (for Steps 1-3 which are identical)
- `_shared/agent_*.md` fragments
- `docs/plans/2026-04-17-unified-scan-pipeline-design.md`

**Commit:**
```bash
git add -f .claude/commands/archie-deep-scan.md
git commit -m "feat(archie-deep-scan): unified pipeline — 4 shared agents + Opus synthesis + Intent Layer + telemetry"
```

---

## Phase C: Merge script update + telemetry script

### Task 8: Update `merge.py` to accept the new agent output structure

**Files:**
- Modify: `archie/standalone/merge.py`

**Check first:** Read `merge.py` to understand how it currently merges Wave 1 outputs into the blueprint. It likely expects the Wave 1 output format (separate keys per agent). The new format has 4 agent outputs + 1 synthesis output.

The merge script needs to:
1. Accept N input JSON files (from argv or a known pattern)
2. For each input, extract the JSON (handling prose-wrapped output via `extract_json_from_text`)
3. Deep-merge each into the existing `blueprint.json` — agent facts go to their respective sections, synthesis goes to `decisions`/`pitfalls`/`meta`/etc.

**Mapping:**
- Structure output → `blueprint.meta`, `blueprint.components`, `blueprint.architecture_rules`, `blueprint.workspace_topology`
- Patterns output → `blueprint.communication`, `blueprint.quick_reference`
- Health output → (health.json is separate, not in blueprint — check if this is right)
- Technology output → `blueprint.technology`, `blueprint.deployment`, `blueprint.development_rules`
- Light synthesis (scan) → `blueprint.meta.executive_summary`, `blueprint.meta.architecture_style`
- Deep synthesis (deep-scan) → `blueprint.decisions`, `blueprint.pitfalls`, `blueprint.architecture_diagram`, `blueprint.implementation_guidelines`, `blueprint.meta`

**If merge.py already handles this mapping:** minimal changes. If it expects a different structure: refactor the merge logic.

**Test:** Run existing tests to ensure no regression. Add a test if merge.py behavior changes.

**Sync + commit:**
```bash
cp archie/standalone/merge.py npm-package/assets/merge.py
python3 scripts/verify_sync.py
git add archie/standalone/merge.py npm-package/assets/merge.py
git commit -m "feat(merge): accept unified agent output structure"
```

---

### Task 9: Add telemetry writing capability

**Files:**
- Modify: `archie/standalone/extract_output.py` — add `write-telemetry` subcommand (avoids inline Python in slash commands)

**Or create:** `archie/standalone/telemetry.py` — a small standalone script

**The script must:**
1. Accept: command name (`scan` | `deep-scan`), project root, and a JSON string (or file path) with step timings
2. Create `.archie/telemetry/` if it doesn't exist
3. Write `.archie/telemetry/{command}_{ISO-timestamp}.json` with the schema from the design doc
4. Read project metadata from `.archie/scan.json` (source_files, total_loc) to populate the `project` field

**TDD:**
```python
def test_telemetry_writes_file(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "scan.json").write_text('{"statistics": {"source_files": 100, "total_loc": 5000}}')
    # invoke telemetry script
    # verify .archie/telemetry/scan_*.json exists with correct schema
```

**Commit:**
```bash
git add archie/standalone/telemetry.py tests/test_telemetry.py npm-package/assets/telemetry.py
git commit -m "feat(telemetry): per-run timing output to .archie/telemetry/"
```

---

### Task 10: Update aggregator source file pattern

**Files:**
- Modify: `archie/standalone/aggregate_findings.py`

The aggregator's `main()` currently reads hardcoded filenames (`semantic_findings_wave1.json`, `semantic_findings_wave2.json`, etc.). The new pipeline writes findings to `sf_structure.json`, `sf_patterns.json`, `sf_health.json` (from agents) + optionally `sf_synthesis.json` (from deep-scan Opus).

**Update `main()`** to read the new file pattern:
```python
# Agent findings (both commands)
structure = _load(archie_dir / "sf_structure.json")
patterns = _load(archie_dir / "sf_patterns.json")
health = _load(archie_dir / "sf_health.json")
# Synthesis findings (deep-scan only — may not exist)
synthesis = _load(archie_dir / "sf_synthesis.json")
# Mechanical
mechanical = _adapt_mechanical(archie_dir / "drift_report.json")
# Prior
prior = _load(archie_dir / "semantic_findings.json")
```

Also keep backward compat: still load `semantic_findings_wave1.json` etc. if they exist (for `--from` resume).

**Update tests:** Adjust any test that hardcodes the old filenames.

**Sync + commit:**
```bash
cp archie/standalone/aggregate_findings.py npm-package/assets/aggregate_findings.py
python3 scripts/verify_sync.py
git add archie/standalone/aggregate_findings.py npm-package/assets/aggregate_findings.py tests/test_aggregate_findings.py
git commit -m "feat(aggregator): read new agent output filenames (sf_structure, sf_patterns, sf_health, sf_synthesis)"
```

---

## Phase D: Sync + validate

### Task 11: Sync both commands to npm-package

```bash
cp .claude/commands/archie-scan.md npm-package/assets/archie-scan.md
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
python3 scripts/verify_sync.py
```

**Commit:**
```bash
git add -f npm-package/assets/archie-scan.md npm-package/assets/archie-deep-scan.md
git commit -m "chore(npm): sync rewritten scan commands to npm-package"
```

---

### Task 12: Install on BabyWeather.Android + run /archie-scan

**No code changes — validation only.**

1. Re-install Archie on BabyWeather.Android (same manual process as before — copy files, don't modify .gitignore)
2. Run `/archie-scan` in Claude Code on BabyWeather.Android
3. Check outputs:
   - `.archie/blueprint.json` — has components, layers, architecture_style, communication, tech_stack, health
   - `.archie/semantic_findings.json` — has findings with new source strings (`agent_structure`, `agent_patterns`, `agent_health`)
   - `.archie/scan_report.md` — new layout
   - `.archie/telemetry/scan_*.json` — exists with per-step timing
   - `CLAUDE.md` — has architectural overview narrative
4. Open viewer — Semantic Findings panel populated, architectural overview visible
5. Run `/archie-share` — upload succeeds, share viewer renders findings

---

### Task 13: Run `/archie-deep-scan` on BabyWeather.Android

1. Run `/archie-deep-scan` in Claude Code
2. Check outputs:
   - `blueprint.json` — now has decisions, pitfalls, trade-offs, diagram, implementation guidelines, distinctive decisions
   - `semantic_findings.json` — has canonical findings (synthesis_depth: "canonical")
   - `scan_report.md` — updated
   - `.archie/telemetry/deep-scan_*.json` — exists with per-step timing including intent_layer
3. Compare telemetry: scan vs deep-scan timing side by side
4. Open viewer — all blueprint sections populated, findings panel rich
5. Run `/archie-share` — upload succeeds

---

### Task 14: Final sync verify + PR update

```bash
python3 scripts/verify_sync.py
python3 -m pytest tests/ -v
```

Update PR #44 body to reflect the unified pipeline changes, or create a new PR if the branch is too diverged.

**Commit:**
```bash
git add docs/plans/2026-04-17-unified-scan-pipeline.md
git commit -m "docs(plan): unified scan pipeline implementation plan"
```

---

## Verification checklist

- [ ] 4 shared agent fragments in `.claude/commands/_shared/agent_{structure,patterns,health,technology}.md`
- [ ] `archie-scan.md` has 5-step pipeline (scan → gather → aggregate → light synthesis → merge+render) + telemetry
- [ ] `archie-deep-scan.md` has 6-step pipeline (same + Opus synthesis replacing light + Intent Layer) + telemetry
- [ ] Both commands INLINE the same 4 agent prompts from `_shared/` fragments
- [ ] Both commands produce `semantic_findings.json` via `aggregate_findings.py`
- [ ] Both commands write telemetry to `.archie/telemetry/{command}_{timestamp}.json`
- [ ] Deep-scan's Opus synthesis includes "4-8 distinctive decisions" directive
- [ ] Deep-scan's Opus synthesis includes upgrade pass (draft → canonical)
- [ ] Deep-scan includes Intent Layer as default (not opt-in)
- [ ] `--from N`, `--continue`, `--incremental`, `--reconfigure` flags preserved on deep-scan
- [ ] `merge.py` accepts the new 4-agent + synthesis output structure
- [ ] Aggregator reads new filenames (`sf_structure.json`, etc.)
- [ ] Telemetry script exists and writes per-run files
- [ ] `verify_sync.py` passes — all scripts, commands, fragments in sync
- [ ] All existing tests still pass
- [ ] `/archie-scan` on BabyWeather.Android produces populated blueprint + findings + telemetry
- [ ] `/archie-deep-scan` on BabyWeather.Android produces deep blueprint + canonical findings + telemetry

## Files summary

| Status | File | Purpose |
|---|---|---|
| New | `.claude/commands/_shared/agent_structure.md` | Shared Structure agent prompt |
| New | `.claude/commands/_shared/agent_patterns.md` | Shared Patterns agent prompt |
| New | `.claude/commands/_shared/agent_health.md` | Shared Health agent prompt |
| New | `.claude/commands/_shared/agent_technology.md` | Shared Technology agent prompt |
| New | `archie/standalone/telemetry.py` | Per-run timing telemetry writer |
| New | `tests/test_telemetry.py` | Telemetry writer tests |
| Rewrite | `.claude/commands/archie-scan.md` | 5-step unified pipeline |
| Rewrite | `.claude/commands/archie-deep-scan.md` | 6-step unified pipeline |
| Modify | `archie/standalone/merge.py` | Accept new agent output structure |
| Modify | `archie/standalone/aggregate_findings.py` | Read new filenames |
| Synced | `npm-package/assets/*` | Mirror all changes |

# Archie v2 — Technical Architecture

Comprehensive technical documentation covering system architecture, analysis pipeline, data models, enforcement hooks, sharing ecosystem, and development.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Layered Architecture](#layered-architecture)
5. [Engine — Local Analysis](#engine--local-analysis)
6. [Ignore System — Three Tiers](#ignore-system--three-tiers)
7. [Bulk-Content Classifier](#bulk-content-classifier)
8. [Coordinator — AI Pipeline](#coordinator--ai-pipeline)
9. [Fast Scan (`/archie-scan`)](#fast-scan-archie-scan)
10. [Deep Scan (`/archie-deep-scan`)](#deep-scan-archie-deep-scan)
11. [Findings Store](#findings-store)
12. [Pitfalls](#pitfalls)
13. [Hooks — Real-Time Enforcement](#hooks--real-time-enforcement)
14. [Rules — Synthesis and Delivery](#rules--synthesis-and-delivery)
15. [Renderer — Output Generation](#renderer--output-generation)
16. [Standalone Scripts](#standalone-scripts)
17. [NPM Package — Distribution](#npm-package--distribution)
18. [Claude Code Integration](#claude-code-integration)
19. [Share Pipeline (`/archie-share`)](#share-pipeline-archie-share)
20. [StructuredBlueprint Data Model](#structuredblueprint-data-model)
21. [Data Flow](#data-flow)
22. [Compound Learning](#compound-learning)
23. [Drift Detection](#drift-detection)
24. [Cycle Detection](#cycle-detection)
25. [Telemetry](#telemetry)
26. [No Inline Python Constraint](#no-inline-python-constraint)
27. [Error Handling and Resilience](#error-handling-and-resilience)
28. [Testing](#testing)
29. [File Sync Protocol](#file-sync-protocol)

---

## System Overview

Archie is a CLI tool + NPM package that bolts onto any codebase to give AI coding agents durable architectural context. No backend server and no database are required for local operation; a lightweight Supabase-backed share ecosystem exists for handing blueprints to teammates via a URL.

The core workflow:

1. **Scan** — deterministic local analysis of the repository (file tree, imports, frameworks, hashing, token counting, skeleton extraction, bulk-content classification). Pure Python, no AI.
2. **Analyze** — Claude Code subagents (Sonnet) gather architectural facts in parallel; a single Opus subagent produces deep reasoning.
3. **Store** — architectural synthesis lands in `blueprint.json`; concrete problems land in the shared, compounding `findings.json` store (4-field shape with id-stable upsert).
4. **Render** — deterministic JSON-to-Markdown generation of CLAUDE.md, AGENTS.md, optional per-folder context, and rule files.
5. **Enforce** — Claude Code hooks validate every file write against extracted rules.
6. **Share** (optional) — `/archie-share` has three modes. **Default** uploads a bundle to BitRaptors' Supabase edge function and renders via the hosted React viewer at `archie-viewer.vercel.app`. **Enterprise (stored credentials)** uploads directly to the customer's own S3 bucket via pure-stdlib sigv4 signing — BitRaptors is never in the data path; the GET URL rides in the share URL's fragment (never transmitted to any server); the viewer fetches client-side from the customer bucket. **Enterprise (paste URL)** is the same flow but with a per-share presigned PUT URL minted by the customer's InfoSec, so no credentials ever live on the dev's laptop.

Archie has four user-facing slash commands (+ one local inspector):

- **`/archie-scan`** — architecture health check (1–3 min). Runs deterministic scanner for data gathering, then AI acts as a senior architect: analyzes dependencies, finds pattern drift, identifies complexity hotspots, proposes enforceable rules. Writes concrete findings to the shared `.archie/findings.json` store with id-stable upsert. Single AI synthesis, 3 parallel Sonnet agents below it.
- **`/archie-deep-scan`** — comprehensive baseline (15–20 min). Full 2-wave multi-agent analysis (3–4 parallel Sonnet fact-gatherers + one Opus reasoner). Produces complete blueprint and all outputs. Supports `--incremental` (changed files only, 3–6 min), `--continue` (resume interrupted run), `--from N` (resume from step N), `--reconfigure` (re-prompt monorepo scope). Auto-detects monorepos and offers parallel sub-project analysis. Intent Layer (per-folder CLAUDE.md) is **opt-in** via an interactive prompt at Step E. Implemented as a **modular Claude Code skill** — `.claude/skills/archie-deep-scan/` holds a `SKILL.md` router plus self-contained per-step files, fragments, and templates, so the long pipeline survives `/compact` and resumes mid-run.
- **`/archie-intent-layer`** — standalone per-folder CLAUDE.md regeneration. Phase 0.5 asks Full/Incremental/Auto upfront (Auto uses `detect-changes` against the `last_deep_scan.json` baseline). Hard-requires `blueprint.json` — otherwise tells the user to run `/archie-deep-scan` first, no degraded path. **Shares its Phases 1–4 pipeline with `/archie-deep-scan` Step 7** (single source of truth); deep-scan Reads this file and layers its own deltas (telemetry, SCAN_MODE mapping, Compact Checkpoint B).
- **`/archie-share`** — uploads blueprint + findings + scan report and returns a URL. Dual-mode at share time: default (BitRaptors Supabase, unchanged) or enterprise (BYO customer S3 bucket, zero BitRaptors storage). Enterprise mode supports either stored credentials (one-time `share_setup.py`) or per-share presigned PUT URL paste. See [Share Pipeline](#share-pipeline-archie-share) for the full architecture.
- **`/archie-viewer`** — local inspector that runs the **same React UI as the hosted share viewer**. `viewer.py` serves the prebuilt React `dist/` plus a localhost JSON API (`/api/bundle`, `/api/generated-files`, `/api/folder-claude-mds`, `/api/intent-layer-status`, `/api/ignored-rules`, `POST /api/rules`) at `localhost:5847/local`. Two tabs: **Blueprint** (the full report — health, diagram, decisions, findings, pitfalls, plus inline rule adopt/reject/edit) and **Files** (per-folder CLAUDE.md browser + click-to-view generated-files tree). The bundle is rebuilt from `.archie/` on every request; the rule actions write back to `.archie/`.

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Standalone scripts | Python 3.9+ (stdlib only) | Type hints, dataclasses, pathlib, http.server |
| Python package (CLI) | Python 3.9+, Pydantic, Click | Model validation, command dispatch |
| AI agents | Claude Code CLI (`claude -p`) + Anthropic Sonnet + Opus | Subagent execution via subprocess |
| NPM installer | Node.js 18+ | `npx @bitraptors/archie` distribution |
| Viewer (shared) | React 18 + Vite + TypeScript + Tailwind v3 + React Router | One React codebase serves both the hosted share viewer (`archie-viewer.vercel.app`) and the local `/archie-viewer` sidecar |
| Share backend | Supabase Edge Functions (Deno) + Postgres | Upload + blueprint fetch by token + anonymous telemetry ingest |
| Testing | pytest | 50 test files |
| Linting | Ruff | Python linting and formatting |

### Dependency philosophy

Standalone scripts (copied to target projects via `npx @bitraptors/archie`) have **zero pip dependencies** — Python 3.9+ stdlib only, including `viewer.py`'s HTTP server. The viewer's React/TypeScript stack is a separate concern: its source ships inside the npm package and the installer builds it once into a static `dist/` (cached by version); target projects never install or run React at scan time.

---

## Project Structure

```
archie/
  __init__.py
  cli/                          # Click CLI commands (used by the Python-package path)
    main.py                     # CLI group
    init_command.py             # Full pipeline orchestration
    refresh_command.py          # Rescan + change detection
    status_command.py           # Blueprint freshness, rule stats, health metrics
    serve_command.py            # FastAPI viewer server (legacy)
    check_command.py            # CI validation: check files against rules
  engine/                       # Local codebase analysis (no AI)
    models.py                   # Pydantic: FileEntry, DependencyEntry, FrameworkSignal, RawScan
    scan.py                     # Orchestrator: runs all analysis steps -> RawScan
    scanner.py                  # Walk directory tree, apply ignore + bulk layering
    dependencies.py             # Parse requirements.txt, package.json, go.mod, Cargo.toml, pyproject.toml
    frameworks.py               # Detect React, FastAPI, Django, etc. with confidence scores
    hasher.py                   # SHA256 file hashes + token counting
    imports.py                  # Build import graph from source code
  coordinator/                  # AI pipeline (Python-package path)
    planner.py                  # Group files into token-budgeted SubagentAssignments
    prompts.py                  # Build markdown prompts for subagents and coordinator
    runner.py                   # Spawn `claude -p` subprocesses, parse JSON responses
    merger.py                   # Deep merge partial blueprints into single StructuredBlueprint
  hooks/
    generator.py                # Generate .claude/hooks/*.sh, register in settings.local.json
    enforcement.py              # Validate files against rules (Python API)
  renderer/
    render.py                   # Adapter: calls standalone renderer + intent layer
    intent_layer.py             # Generate per-folder CLAUDE.md with local patterns
  rules/
    extractor.py                # Legacy blueprint rule extractor — RETIRED in v2.5.0, no longer on the pipeline (kept for tests)
  standalone/                   # Zero-dependency scripts (30 files, exported to target projects)
    _common.py                  # IgnoreMatcher, BulkMatcher, DECISION_RE, normalize_blueprint
    scanner.py                  # File tree, import graph, framework detection, skeleton extraction, bulk manifest
    renderer.py                 # Generate AGENTS.md (canonical) + CLAUDE.md pointer + .claude/rules/ topic files
    intent_layer.py             # Per-folder CLAUDE.md via DAG scheduling + AI enrichment + inspect/scan-config/deep-scan-state/save-run-context
    viewer.py                   # Local viewer — serves the React dist/ + /api/* JSON endpoints (stdlib http.server)
    drift.py                    # Mechanical drift detection
    validate.py                 # Cross-reference blueprint against actual codebase
    check_rules.py              # Check files against rules (CI path)
    measure_health.py           # Erosion, gini, verbosity, top-20%, waste scores + history append + --compare-history
    code_shape.py               # Code-shape matching primitives consumed by the pre-validate hook + rule index
    detect_cycles.py            # Tarjan's SCC on the import graph
    install_hooks.py            # Install 6 hooks + 29 permissions in settings.local.json
    merge.py                    # Merge blueprint sections from multiple sources
    finalize.py                 # Deep merge + findings upsert into store + pitfalls into blueprint
    verify_findings.py          # Parallel Haiku verifier — checks each finding's triggering_call_site against real code
    apply_verdicts.py           # Apply verifier verdicts to findings.json with cross-run hysteresis
    rule_index.py               # Pre-compute .archie/rule_index.json (keyword / path / always-inject buckets) for hot-path enforcement
    align_check.py              # Phase 3 semantic alignment classifier — plan/diff intent vs rule description+why+example
    migrate_blueprint_rules.py  # Migrate legacy blueprint rule sections into proposed_rules.json
    arch_review.py              # Architectural review checklist for plans and diffs
    refresh.py                  # File change detection (hash comparison)
    extract_output.py           # rules / deep-drift / recent-files / save-duplications subcommands
    telemetry.py                # Per-run step-level wall-clock timing + steps-count action
    telemetry_sync.py           # Anonymous opt-in telemetry — record events, push to Supabase
    update_check.py             # Anonymous opt-in npm-registry update check + snooze ladder
    config.py                   # Machine-level config at ~/.archie/config.json (telemetry consent, update prefs, install id)
    analytics.py                # Local analytics dashboard over ~/.archie/analytics/runs.jsonl
    upload.py                   # Build share bundle; default mode POSTs to Supabase, enterprise modes do sigv4-PUT or presigned-PUT to customer bucket + build fragment-embedded viewer URL
    share_setup.py              # Enterprise share setup wizard: writes ~/.archie/share-profile.json (chmod 600) from flags
    lint_gate.py                # Opt-in external linter gate (ruff / eslint / golangci-lint / semgrep) behind .archie/enforcement.json

npm-package/
  bin/archie.mjs                # npx @bitraptors/archie installer entry point
  assets/                       # Canonical copies of everything the installer ships
    *.py                        # Mirror of every standalone script (30)
    archie-*.md                 # Mirror of the 5 slash commands
    _shared/scope_resolution.md # Mirror of the shared Phase 0 fragment
    skills/archie-deep-scan/    # Mirror of the deep-scan skill subtree (SKILL.md, steps/, fragments/, templates/)
    viewer/                     # Mirror of share/viewer/ source — built into dist/ at install time
    archieignore.default        # Default `.archieignore` template
    archiebulk.default          # Default `.archiebulk` template (three tier, path-based)
    platform_rules.json         # 30 predefined architectural checks
  package.json

share/
  viewer/                       # React/Vite app — powers archie-viewer.vercel.app AND the local /archie-viewer sidecar
    src/pages/                  # HomePage, LocalPage (/local), CoverPage (/r/:token), ReportPage (/r/:token/details)
    src/components/             # ReportSections, FixThisButton, MermaidDiagram + local/ (TreeNav, browsers, RuleControls, RuleEditModal)
    src/lib/                    # api.ts (Bundle/ReportResponse types), findings.ts, fixPrompt.ts, autocode.ts
  supabase/
    migrations/                 # reports table + telemetry_events table (RLS-restricted)
    functions/upload/           # POST a bundle, get a token
    functions/blueprint/        # GET bundle by token
    functions/telemetry-ingest/ # Anonymous telemetry ingest (anon key + insert-only RLS)

tests/                          # 50 test files

docs/
  ARCHITECTURE.md               # This file
  enterprise-share-setup.md     # Customer-side bucket setup walkthrough (CORS + IAM templates)

landing/                        # Landing page
v1/                             # Archived V1 web app + landing (FastAPI + Next.js, obsolete)

.claude/
  commands/
    archie-scan.md              # Architecture health check (1–3 min)
    archie-deep-scan.md         # Thin router — invokes the archie-deep-scan skill
    archie-intent-layer.md      # Standalone per-folder CLAUDE.md regen (shared pipeline w/ deep-scan Step 7)
    archie-share.md             # Upload bundle to shared viewer
    archie-viewer.md            # Local viewer launcher
    _shared/scope_resolution.md # Phase 0 scope-resolution fragment, loaded by deep-scan (and inlined by scan)
  skills/
    archie-deep-scan/           # The deep-scan pipeline as a skill: SKILL.md router + steps/ + fragments/ + templates/

scripts/
  verify_sync.py                # Pre-commit: verify canonical ↔ asset sync

pyproject.toml                  # Package metadata
CLAUDE.md                       # AI agent instructions for this repository
README.md                       # User-facing documentation
```

---

## Layered Architecture

```
User
  |
  v
Claude Code slash commands (archie-scan, archie-deep-scan, archie-share, archie-viewer)
  |
  v  (orchestration is markdown-in-a-slash-command, not Python — the slash command
  |   spawns subagents and calls the standalone scripts via Bash)
  |
  v
Standalone scripts (archie/standalone/*.py)            <-- primary runtime path
  |   scanner, measure_health, detect_cycles,
  |   finalize, merge, intent_layer, drift,
  |   extract_output, telemetry, upload, ...
  v
File system + Claude Code subagent spawning (Agent tool) + Anthropic API
```

A parallel Python-package path exists (`archie/cli/ + engine/ + coordinator/`) for non-Claude-Code execution — but the shipped user experience runs through the slash commands orchestrating the standalone scripts. The standalone scripts are the canonical implementation; the Python package modules are older scaffolding, kept for CI / tests but not on the primary runtime path.

**Separation of concerns:**

- **Engine / standalone scanner** — stateless local analysis. No AI, no blueprint writing. Input: repo path. Output: `scan.json` with file tree, imports, frameworks, hashes, skeletons, `bulk_content_manifest`, `frontend_ratio`.
- **Coordinator / slash-command orchestration** — spawns subagents, builds prompts, merges outputs. Input: `scan.json`. Output: `blueprint.json` + `findings.json` updates.
- **Hooks** — real-time Claude Code integration. Registered in `.claude/settings.local.json` at install time.
- **Renderer** — deterministic file generation. Input: `blueprint.json`. Output: CLAUDE.md, AGENTS.md, per-folder context, rule files.
- **Rules** — extraction and severity management. Input: blueprint + AI proposals + platform rules. Output: `rules.json`.
- **Share** — `upload.py` builds a bundle (blueprint + findings + scan_report + health + rules) and POSTs it to the Supabase edge function; the React viewer renders it from a token URL.

---

## Engine — Local Analysis

The engine runs analysis steps in sequence and produces a `RawScan` (defined in `archie/engine/models.py`). The standalone scanner produces the same shape as JSON at `.archie/scan.json`:

```python
class FileEntry(BaseModel):
    path: str
    size: int = 0
    extension: str = ""
    bulk: dict | None = None           # Present if matched by .archiebulk

class RawScan(BaseModel):
    file_tree: list[FileEntry]
    token_counts: dict[str, int]
    tokens_by_directory: dict[str, int]
    dependencies: list[DependencyEntry]
    framework_signals: list[FrameworkSignal]
    config_patterns: dict[str, str]
    import_graph: dict[str, list[str]]
    file_hashes: dict[str, str]
    entry_points: list[str]
    frontend_ratio: float
    bulk_content_manifest: dict[str, dict]   # category -> {count, frameworks, files}
```

### Analysis steps (`archie/standalone/scanner.py::run_scan`)

| # | What it does |
|---|--------------|
| 1 | Build `IgnoreMatcher` (`.gitignore` + `.archieignore` + `SKIP_DIRS` fallback) |
| 2 | Build `BulkMatcher` from `.archiebulk` |
| 3 | Walk directory tree — pruning ignored dirs, emitting `FileEntry` per surviving file |
| 4 | Classify each file against `BulkMatcher` — bulk matches get `{category, framework}` tag; downstream steps skip reading their contents |
| 5 | Parse manifests (`requirements.txt`, `package.json`, `go.mod`, `Cargo.toml`, `pyproject.toml`, etc.) |
| 6 | Detect frameworks with confidence scores + evidence |
| 7 | SHA256 hash + token count every non-bulk file |
| 8 | Parse import statements to build directed import graph (Python, JS/TS, Go, Rust, Kotlin, Swift) |
| 9 | Detect entry points by filename pattern |
| 10 | Read first 500 chars of config files |
| 11 | Extract skeletons (class/function signatures + imports + first lines) for every non-bulk source file |
| 12 | Compute `frontend_ratio` — counts extension-tagged UI source (tsx/jsx/vue/swift/xib/storyboard/dart/xaml) **plus** bulk files tagged `ui_resource` against a denominator of readable source + source-shape bulk categories |
| 13 | Assemble `scan.json` and `skeletons.json`; return |

---

## Ignore System — Three Tiers

Most-restrictive wins. A path matched by a higher tier is not re-considered by a lower tier.

| Tier | File | Semantics |
|---|---|---|
| 1 | `.gitignore` (root + nested) | Fully skipped — the scanner never sees the path |
| 2 | `.archieignore` | Fully skipped — Archie-specific exclusions on top of `.gitignore` |
| 3 | `.archiebulk` | **Visible inventory, opaque contents** — recorded in `scan.json.file_tree` with a `bulk: {category, framework}` tag and aggregated in `bulk_content_manifest`, but never skeleton-parsed, hashed, token-counted, or import-parsed |

All three files use gitignore-style globs. `.archiebulk` patterns carry two whitespace-separated metadata columns (`category`, optional `framework`):

```
# <glob>                   <category>        <framework>
**/res/layout/**            ui_resource       android
**/res/drawable*/**         ui_resource       android
**/*.storyboard             ui_resource       ios
**/*.g.dart                 generated         flutter
**/*.pb.go                  generated         protobuf
**/migrations/**/*.sql      migration         sql
package-lock.json           lockfile          node
```

`IgnoreMatcher` and `BulkMatcher` both live in `archie/standalone/_common.py`. `BulkMatcher` implements proper `**` semantics via `_glob_to_regex` (translating gitignore-style globs into regex so `**/res/layout/**` matches at any depth).

---

## Bulk-Content Classifier

### Purpose

Some files are *structurally verbose but architecturally inert* — Android `res/layout/*.xml`, iOS `.storyboard`, generated protobuf Go stubs, minified JS, TypeScript `.d.ts`, SQL migrations. Their **existence and count** carry signal (this is an Android project with 248 layouts → `frontend_ratio` flips to 0.5 → UI Layer agent spawns), but reading their contents burns context for no analytical gain.

### Categories (shipped defaults)

| Category | Examples | Counted as source shape? |
|---|---|---|
| `ui_resource` | Android `res/layout/`, `drawable/`, `values/`; iOS storyboards/xibs | yes → boosts `frontend_ratio` |
| `generated` | `.g.dart`, `.freezed.dart`, `.pb.go`, `.min.js`, `.d.ts`, `dist/`, `.next/`, `.nuxt/`, `.svelte-kit/` | yes |
| `localization` | `locales/`, `i18n/`, `.arb`, `.po`, `.strings` | yes |
| `migration` | `db/migrate/`, `migrations/**/*.sql`, `prisma/migrations/` | yes |
| `fixture` | `fixtures/`, `seeds/`, `testdata/`, `__snapshots__/` | yes |
| `asset` | fonts, mipmaps, `Assets.xcassets/`, `res/raw/` | no (not source shape) |
| `lockfile` | `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `go.sum` | no |
| `dependency` | `vendor/` (Go) | no |
| `data` | large CSV/JSON catalogs | no |

### How agents see it

Every scan / deep-scan agent prompt injects a no-read rule:

> `scan.json.bulk_content_manifest` lists files classified by `.archiebulk` as "visible inventory, not contents". You may reference these paths by name and inventory counts, but you MUST NOT call Read on them. The scanner has already summarised their shape.

Agents can still Read bulk paths in rare surgical cases (resolving a specific finding) — the prompt allows it as an explicit exception.

### Extensibility

Project-specific bulks (e.g. a 20k-key product catalog, a giant CLDR dump) are added in one line to `.archiebulk`. New frameworks require only new rows in the default template — no scanner code changes.

---

## Coordinator — AI Pipeline

### Slash-command orchestration (primary path)

`/archie-scan` is a single markdown template in `.claude/commands/`. `/archie-deep-scan` is a thin router in `.claude/commands/` that invokes the **`archie-deep-scan` skill** — a `SKILL.md` orchestrator plus self-contained per-step files under `.claude/skills/archie-deep-scan/` (`steps/`, `fragments/`, `templates/`). The skill split keeps each step independently readable and lets the pipeline survive `/compact` and resume via `--continue` / `--from N`. Both orchestrate the pipeline by:

1. Calling standalone Python scripts for deterministic steps (`scanner.py`, `measure_health.py`, `detect_cycles.py`, `finalize.py`, `extract_output.py`, `drift.py`, `intent_layer.py`, `telemetry.py`).
2. Spawning subagents via the Agent tool for AI steps (3–4 parallel Sonnets in Wave 1, one Opus in Wave 2, one Sonnet for rule synthesis, N Sonnets for Intent Layer if opted in).
3. Using `AskUserQuestion` for all single-choice prompts (scope picker, parallel/sequential, Intent Layer opt-in) — no free-text answers to parse.

### Python-package path (planner/runner/merger, `archie/coordinator/`)

Kept for CI/tests and standalone Python usage. Groups files into token-budgeted `SubagentAssignment`s (150k tokens per group, bin-packed by top-level directory), builds prompts, spawns `claude -p` subprocesses, parses JSON responses with three-strategy fallback, merges partial blueprints. Not exercised by the default slash-command flow.

---

## Fast Scan (`/archie-scan`)

1–3 minutes. Designed for frequent runs.

```
Phase 1  Data Gathering (deterministic, seconds)
  scanner.py, measure_health.py, detect_cycles.py, git log
Phase 2  Read accumulated knowledge
  skeletons.json, scan.json, health.json, blueprint.json (if exists),
  findings.json, rules.json, proposed_rules.json
Phase 3  Parallel analysis — 3 Sonnet agents
  Agent A (architecture + dependencies)
  Agent B (health + complexity)
  Agent C (patterns + rules)
  Each agent gets its slice of findings.json and is told to prioritise NEW problems.
Phase 4  Synthesis (single AI pass, Sonnet)
  4a Evolve blueprint (does NOT touch blueprint.pitfalls — deep-scan-Opus-only)
  4b Write structured findings to .archie/findings.json (id-stable upsert)
  4c Write prose scan report to .archie/scan_history/ + .archie/scan_report.md
  4d Save semantic duplications to .archie/semantic_duplications.json
      (deterministic via `extract_output.py save-duplications`)
Phase 5  Proposed rules to .archie/proposed_rules.json
Phase 6  Telemetry write
```

---

## Deep Scan (`/archie-deep-scan`)

15–20 minutes on first run; `--incremental` mode handles later runs in 3–6 min.

**Skill structure.** `/archie-deep-scan` is a Claude Code skill, not a monolithic command file. `.claude/commands/archie-deep-scan.md` is a thin router; the real pipeline lives in `.claude/skills/archie-deep-scan/`:

- `SKILL.md` — the orchestrator: flag parsing (`--incremental` / `--continue` / `--from N` / `--reconfigure`), the resume preamble, and a step-routing table.
- `steps/step-1-scanner.md` … `step-10-telemetry.md` — one self-contained file per step (Step 3 expands into `step-3-wave1/` with one prompt file per Wave 1 agent + shared grounding rules).
- `fragments/` — cross-step contracts: `telemetry-conventions.md`, `compact-resume-contract.md`, `resume-prelude.md`.
- `templates/scan-report.md` — the scan-report template Step 9 fills in.
- Phase 0 scope resolution is loaded from the shared `.claude/commands/_shared/scope_resolution.md` fragment.

The router Reads only the files for the steps it actually runs, so a `--from 7` resume never loads Steps 1–6, and `.archie/deep_scan_state.json` rehydrates shell variables after a `/compact`.

```
Phase 0       Scope resolution (interactive, AskUserQuestion)
              - monorepo detection -> whole/per-package/hybrid/single picker
              - if multi-workspace: AskUserQuestion for parallel/sequential
              - AskUserQuestion for Intent Layer opt-in (Step E)
Step 1        Scanner (same as fast scan)
Step 2        Read accumulated knowledge
Step 3  Wave 1 (parallel) — 3–4 Sonnet agents
              Structure, Patterns, Technology [+ UI Layer if frontend_ratio >= 0.20]
              Writes /tmp/archie_agent_*.json
Step 4        Merge Wave 1 outputs into blueprint_raw.json via merge.py
Step 5  Wave 2 (single Opus) — synthesis
              Reads blueprint_raw.json + findings.json
              Runs three probes: A complexity-budget, B invariants & gates, C seams
              Emits decision chain, architectural style, key decisions,
                   trade-offs, out-of-scope, findings (upgrade + new),
                   pitfalls, architecture diagram, implementation guidelines
              Writes /tmp/archie_sub_x_*.json
              finalize.py deep-merges into blueprint.json and upserts findings into the store
Step 6  Rule synthesis (single Sonnet) — proposes architecturally-grounded rules
Step 7  Intent Layer (opt-in) — per-folder CLAUDE.md via DAG scheduling
              If INTENT_LAYER=no from Step E, this step is skipped and
              telemetry records "skipped": true
Step 8        Cleanup
Step 9        Drift Detection & Architectural Assessment
              Mechanical drift (drift.py) + Deep AI drift (single Sonnet)
              Writes scan_report.md to scan_history/
Step 10       Telemetry write
```

### Incremental mode (`--incremental`)

Skips Wave 1 entirely. One scoped Reasoning agent receives `blueprint.json` + `blueprint_raw.json` + changed-files list + `findings.json`, returns only the sections that need updating, and `finalize.py --patch` deep-merges the diff.

### Resume modes

- `--continue` resumes from the last completed step (tracked in `.archie/deep_scan_state.json`).
- `--from N` resumes from a specific step.

---

## Findings Store

`.archie/findings.json` is a **shared, compounding store** — both `/archie-scan` and `/archie-deep-scan` read from it and write back to it. Neither requires the other to have run first.

### Schema

```json
{
  "scanned_at": "YYYY-MM-DDTHHMM",
  "scan_count": N,
  "findings": [
    {
      "id": "f_NNNN",
      "problem_statement": "One sentence, specific.",
      "evidence": ["src/file.py:42", "pattern observed in 7 modules", "..."],
      "root_cause": "Names a decision/pattern/constraint, specific to this codebase.",
      "fix_direction": "Single tactical sentence." | ["step 1", "step 2", "step 3"],
      "severity": "error | warn | info",
      "confidence": 0.85,
      "applies_to": ["src/auth/", "src/routes/profile.py"],
      "source": "scan:structure | scan:health | scan:patterns | deep:synthesis",
      "depth": "draft | canonical",
      "pitfall_id": "pf_NNNN (optional, when root_cause is structural)",
      "first_seen": "YYYY-MM-DDTHHMM",
      "confirmed_in_scan": 1,
      "status": "active | resolved"
    }
  ]
}
```

### Lifecycle

| Event | Action |
|---|---|
| Scan agent surfaces a problem matching an existing finding (similar `problem_statement` ∧ overlapping `applies_to`) | Reuse `id`, keep `first_seen`, increment `confirmed_in_scan`, keep evidence |
| Scan agent surfaces a novel problem | Assign next-free `f_NNNN`, set `first_seen = today`, `confirmed_in_scan = 1`, `depth: "draft"` |
| Previous finding no longer appears | Flip `status: "resolved"`, add `resolved_at`. Preserved as history, not deleted |
| Deep-scan Wave 2 Opus upgrades a draft | Preserve `id`, `first_seen`, `applies_to`, `evidence`; rewrite `root_cause` with architectural grounding; rewrite `fix_direction` as an ordered list of sequenced steps; flip `depth: "canonical"`, `source: "deep:synthesis"`; link to parent pitfall via `pitfall_id` if structural |
| Deep-scan Wave 2 Opus discovers a NEW problem | Mint a new `f_NNNN` after running a novelty check against the existing store |

### Id-stable merge (`finalize.py::_merge_findings_into_store`)

Deterministic Python code enforces id-stable upsert: entries whose `id` matches an existing one are replaced in place (with preserved `first_seen` and bumped `confirmed_in_scan`), unmatched entries in the new set get minted, and existing entries not referenced by the current run are left untouched (scan is responsible for marking resolution).

### Novelty priority in agent prompts

Every scan agent (A / B / C) receives the findings store scoped to its `source` slice and is explicitly told:

> Those problems are already known — your job is not to rediscover them. Emit them with the same `problem_statement` wording (so 4b can id-match them) without re-deriving evidence. Spend your cognitive budget on problems NOT in the store.

Same rule for Wave 2 Opus: the primary goal is **NEW findings visible only from the overall-picture pass**; upgrading drafts is secondary housekeeping.

---

## Pitfalls

Pitfalls are **classes of problem** — architectural traps rooted in decisions or patterns. They share the same 4-field core as findings but live in `blueprint.pitfalls` (blueprint-durable, not per-run).

| Aspect | Finding | Pitfall |
|---|---|---|
| Altitude | Instance (specific files) | Class-of-problem |
| `applies_to` | File-level | Component/folder-level |
| `source` | `scan:{structure,health,patterns}` or `deep:synthesis` | `deep:synthesis` only |
| `depth` | `draft` or `canonical` | `canonical` only |
| Owner | Both commands write to findings.json | Only deep-scan Wave 2 Opus writes to blueprint.pitfalls |
| Persistence | Compounding store, status flips on resolve | Durable blueprint entries |
| ID | `f_NNNN` | `pf_NNNN` |

A single pitfall may have multiple confirming findings via `pitfall_id`.

---

## Hooks — Real-Time Enforcement

The installer (`npx @bitraptors/archie`) generates six hooks and registers them in `.claude/settings.local.json`:

**`pre-validate.sh`** (PreToolUse, matcher: `Write|Edit|MultiEdit`)
- **Rule injection (Tier 4)** — before the violation check, prints every rule that applies to the file's path (rules with `applies_to` prefix-matching `rel_path`) plus every rule tagged `always_inject: true` (critical globals). Each rule carries inline semantic content the agent reads at edit time — `description`, the `WHY:` block, and an `EXAMPLE:` block — so no blueprint read is needed. Deduped per-turn via `/tmp/.archie_turn_<cksum-of-project-root>` marker so the same rule doesn't re-surface on every Edit within a turn.
- **Violation check** — runs the mechanical `check` rules (`forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`, `file_naming`).
- **`severity_class` gating** — the hook gates its response on the rule's `severity_class`: `decision_violation` / `pitfall_triggered` / `mechanical_violation` block (exit 2), `tradeoff_undermined` warns (exit 0, prominent), `pattern_divergence` informs (exit 0, quiet). Old-shape rules without `severity_class` fall back to `severity` + `rationale`.
- Reads the content being written for deeper validation (not just file path); uses `printf %s` + tempfile + JSON parse to pass tool input to Python without shell-escaping bugs.
- Loads `rules.json` + `platform_rules.json`; consults the pre-computed `.archie/rule_index.json` (keyword / path / always-inject buckets, rebuilt by `rule_index.py`) for hot-path lookup.

**`pre-turn.sh`** (UserPromptSubmit)
- Clears the per-turn rule-injection marker at the start of each new user turn so applicable rules re-surface on the first Write/Edit of that turn.

**`pre-commit-review.sh`** (PreToolUse, matcher: `Bash`)
- Filters to fire only on `git commit` commands
- Triggers an architectural review of the staged diff via `arch_review.py`

**`post-plan-review.sh`** (PostToolUse, matcher: `ExitPlanMode`)
- Triggers an architectural review of the plan via `arch_review.py`

**`blueprint-nudge.sh`** (PreToolUse, matcher: `Glob|Grep`)
- Always-on architectural reminder — fires before code exploration to remind the agent about project architecture

**`post-lint.sh`** (PostToolUse, matcher: `Write|Edit|MultiEdit`)
- **Opt-in external linter gate** — reads `.archie/enforcement.json`; no-op unless `{"enabled": true}`
- Auto-detects the right linter per file extension + project config: Python (`.py` + `pyproject.toml [tool.ruff]` → `ruff check --quiet`), JS/TS (`.js/.ts/...` + `.eslintrc` + eslint on PATH → `eslint --quiet`), Go (`.go` + `.golangci.yaml` → `golangci-lint run --fast` on the parent dir since golangci-lint is package-aware), Semgrep (any file type + `.semgrep.yml` → `semgrep --error --quiet`)
- Config overrides let users pin custom commands per kind
- `severity: error` → exit 2 blocks; `severity: warn` → exit 0 with message

### Permissions

The installer writes a 29-entry `allow` list into `.claude/settings.local.json` so the workflow runs without interactive prompts:

- `Bash(python3 .archie/*.py *)`, `Bash(python3 -c *)`
- `Bash(git *)`, `Bash(sort *)`, `Bash(head *)`, `Bash(test *)`, `Bash(cp *)`, `Bash(ls *)`, `Bash(wc *)`, `Bash(cat *)`, `Bash(echo *)`, `Bash(for *)`, `Bash(mkdir *)`, `Bash(date *)`
- `Bash(rm -f /tmp/archie_*)`, `Bash(rm -f .archie/health.json)`
- `Write(//tmp/archie_*)`, `Read(//tmp/archie_*)`
- `Read(.archie/*)`, `Read(.archie/**)`, `Write(.archie/*)`, `Write(.archie/**)`, `Edit(.archie/*)`, `Edit(.archie/**)`
- `Read(**)`
- `Write(**/CLAUDE.md)`, `Edit(**/CLAUDE.md)`
- `Agent(*)` for subagent spawning

All hooks fail open: missing rules/config/marker files → hooks exit 0 silently.

### Subagent output contract

Every Sonnet/Opus subagent spawned during a scan receives a mandatory instruction to Write its own output directly to `/tmp/archie_*.json` using the Write tool (permissioned via `Write(//tmp/archie_*)`). The orchestrator never copies subagent transcripts. This avoids Claude Code's sensitive-file guardrail on `~/.claude/projects/.../subagents/*.jsonl` (which used to fire a permission prompt on every batch), keeps subagent output out of the orchestrator's context (less compaction pressure), and isolates failures (missing confirmation line or missing file → clear signal, no silent fallback to transcript scraping).

The contract is enforced in 6 spawn sites across the slash commands: Wave 1 structural agents (3–4 Sonnets), Wave 2 reasoning agent (full + incremental paths), rule-proposer agent, deep-drift reviewer, and Intent Layer enrichment subagents.

---

## Rules — Synthesis and Delivery

Rules come from two AI-synthesized sources plus a universal platform set. They all share one **inline rich rule shape** — each rule carries the semantic content the agent needs at edit time, so the pre-edit hook never has to read the blueprint or follow a pointer.

> **Retired:** the deterministic blueprint extractor (`archie/rules/extractor.py::extract_rules`) was removed from the pipeline in v2.5.0. Its `allowed_dirs` lookup went stale and AI rule synthesis (source 1 below) covers placement + naming with full semantic content the extractor couldn't express. The file still exists for test coverage but nothing calls it. A fresh `archie init` writes an empty `rules.json`; the user populates it by running `/archie-deep-scan` or `/archie-scan`.

### 1. `/archie-deep-scan` Step 6 — Sonnet rule synthesis (the baseline)

The Step 6 agent reads the synthesized blueprint and proposes the architectural rule baseline. Each rule carries inline semantic content:

- `severity_class` — one of `decision_violation` / `pitfall_triggered` / `tradeoff_undermined` / `pattern_divergence` / `mechanical_violation` (drives how the pre-edit hook responds)
- `description` — what the rule enforces
- `why` — the reasoning, copy-pasted from the motivating blueprint section
- `example` — canonical code shape, from `implementation_guidelines.usage_example` when present
- `forced_by` / `enables` / `alternative` — links back to the motivating decision
- `source: "deep_scan"`

Mechanical rules (regex-checkable housekeeping) additionally carry `check` + `forbidden_patterns` / `required_in_content` fields, and may emit a `code_shape` entry consumed by `code_shape.py` + the rule index.

### 2. `/archie-scan` — senior-architect pass

`/archie-scan` proposes new rules in the same inline shape (`source: "scan"`), or amends existing ones (`source: "scan-amended"`), by spotting drift in recently-changed files. Severity is **inferred from the blueprint anchor, never invented** — and scan never promotes a rule to blocking on its own; that happens at the next deep-scan with full Wave 2 reasoning. The mechanical `check` types remain: `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`, `file_naming`.

Old-shape rules (no `severity_class` / `why` / `example`) still work — the hook and renderer fall back to `severity` + `rationale`.

### 3. Platform rules (`platform_rules.json`, 30 rules)

Installed with every project. Categories:

| Category | Count | Examples |
|---|---|---|
| `architecture` | 12 | Android ViewModel/Context separation, Fragment/network, Swift view-layer networking, React components fetching data, TypeScript `any`, array index keys |
| `safety` | 6 | Swift force unwraps / force try, Python `TYPE_CHECKING` guards, React DOM manipulation |
| `erosion` | 5 | God-functions, growing complexity, monster files |
| `decay` | 4 | Empty catches, disabled tests, TODO/HACK markers, debug breakpoints |
| `security` | 3 | Hardcoded secrets, eval/exec, plaintext API keys in logs |

Severity can be changed from `/archie-viewer` or by Claude Code during scans. Rules are stored in `.archie/rules.json` as `{"rules": [...]}`.

### Rule delivery — the four-tier enforcement ladder

Rules don't do anything unless the agent sees them at the right moment. Archie uses a layered delivery model:

| Tier | Mechanism | What it covers | Effect |
|---|---|---|---|
| **Session start** | `CLAUDE.md`, `AGENTS.md`, `.claude/rules/*.md` auto-loaded by Claude Code | All rules (prose + mechanical) | Agent-aware |
| **Prompt time** | `UserPromptSubmit` hook keyword-matches `rules.json` entries against the user's prompt | Rules with `keywords` array OR `severity: error` (always-inject) | Surfaces relevant rules before the agent starts writing |
| **Edit time — injection (Tier 4)** | `PreToolUse` `pre-validate.sh` prints matching rules — `description` + `WHY:` + `EXAMPLE:` — before any violation check | Rules with `applies_to` prefix-matching the file path, and rules with `always_inject: true` | Re-surfaces rule + reasoning + example at the point of edit, deduped per-turn |
| **Edit time — mechanical block (Tier 1)** | `PreToolUse` `pre-validate.sh` runs regex / glob checks, then gates the response on `severity_class` | Rules with a `check` field (`forbidden_content`, `forbidden_import`, `required_pattern`, `architectural_constraint`, `file_naming`) | `decision_violation` / `pitfall_triggered` / `mechanical_violation` → exit 2 (blocked); `tradeoff_undermined` → warn; `pattern_divergence` → quiet inform |
| **Post-edit — external linter (Tier 3, opt-in)** | `PostToolUse` `post-lint.sh` runs project's native linter on changed file | Standard language-level issues (ruff / eslint / golangci-lint / semgrep) | Blocks if `severity: error`, warns otherwise |

Plan-time and commit-time, `align_check.py` adds a **semantic** layer: it compares the agent's intent (ExitPlanMode plan text or staged diff) against each rule's `description` + `why` + `example` via a single Claude CLI call, catching divergence the regex `check` rules can't express.

**Rule schema fields** that drive this ladder:

- `severity_class` — `decision_violation` / `pitfall_triggered` / `tradeoff_undermined` / `pattern_divergence` / `mechanical_violation`; gates the Tier 1 hook response (old-shape rules fall back to `severity`)
- `description` / `why` / `example` — inline semantic content surfaced at edit time (Tier 4), no blueprint read needed
- `forced_by` / `enables` / `alternative` — links back to the motivating architectural decision (rendered in rule cards + topic files)
- `keywords: [...]` — 2–5 terms for prompt-time matching (Tier 2)
- `applies_to: "path/prefix"` — scopes the rule to edits under that path (Tier 4 injection + content-check scoping)
- `always_inject: true` — critical globals that should re-surface at every first-edit-of-turn regardless of path (Tier 4)
- `check: "..."` + `forbidden_patterns` / `required_in_content` / `file_pattern` (+ optional `code_shape`) — mechanical enforcement (Tier 1)
- `source` — provenance: `deep_scan` (baseline), `scan` / `scan-amended` (senior-architect pass), `scan-adopted` (curated in), `platform`

The AI rule synthesizer in `/archie-deep-scan` Step 6 and the `/archie-scan` proposer emit `keywords` for every rule and pick the narrowest meaningful `applies_to` scope, promoting broad-but-critical globals to `always_inject` rather than leaving them scopeless. `rule_index.py` pre-computes `.archie/rule_index.json` from `rules.json` + `platform_rules.json` so the hot-path hook does bucket lookups instead of scanning every rule.

### Per-turn rule-injection dedup

Tier 4 injection uses `/tmp/.archie_turn_<cksum-of-project-root>` as a marker file: `pre-validate.sh` appends each injected rule id after printing it; `pre-turn.sh` (UserPromptSubmit) clears the file at the start of each user turn. Within a single turn, editing N files doesn't re-inject the same rule N times — the agent sees it once, keeps it in context, and moves on.

---

## Renderer — Output Generation

### Standalone renderer (`archie/standalone/renderer.py`)

Deterministic JSON-to-Markdown, runs independently with just a `blueprint.json`:

```bash
python3 .archie/renderer.py /path/to/project
```

Produces:
- `AGENTS.md` — the **canonical agent context**: architecture summary, decision chains, and deep-links into the topic rule files
- `CLAUDE.md` — a thin **pointer** to `AGENTS.md`, so Claude Code and agent-agnostic tools load the same context (the renderer can still preserve hand-authored content in either file via bracketed markers)
- `.claude/rules/*.md` — topic-split rule files: `architecture`, `patterns`, `frontend`, `guidelines`, `pitfalls`, `dev-rules`, `infrastructure`, `technology` (the lean Commands catalog moved here), plus a browsable `enforcement/` directory (`index.md` + per-topic + `universal.md`) indexing every rule the pre-edit hook and the plan/commit classifier consult, grouped by severity and path glob

Pitfalls and findings use a shared `_render_pitfall_lines` helper that handles the 4-field shape (`problem_statement` / `evidence` / `root_cause` / `fix_direction` as list or string) and falls back to the legacy `{area, description, recommendation}` shape for blueprints written before 2.3.0.

### Intent Layer (`archie/standalone/intent_layer.py`)

Per-folder CLAUDE.md generation via bottom-up DAG scheduling:

- Leaf folders processed first, parents inherit child summaries
- Incremental re-generation: only folders containing changed files + their parent chain
- State tracked automatically in `.archie/enrich_state.json`
- Batches of folders processed in parallel waves (spawned Sonnet subagents)

Intent Layer is **opt-in** at deep-scan Step E. When skipped, a one-line note is printed and telemetry records `"skipped": true`.

---

## Standalone Scripts

30 zero-dependency Python scripts in `archie/standalone/`. These are exported to target projects via `npx @bitraptors/archie`.

| Script | Purpose |
|--------|---------|
| `_common.py` | `IgnoreMatcher`, `BulkMatcher`, `_glob_to_regex`, `DECISION_RE`, `normalize_blueprint()`, JSON helpers |
| `scanner.py` | File tree, import graph, framework detection, skeleton extraction, bulk classification, `frontend_ratio` |
| `renderer.py` | Blueprint JSON → AGENTS.md (canonical) + CLAUDE.md pointer + `.claude/rules/` topic files + `enforcement/` directory |
| `intent_layer.py` | Per-folder CLAUDE.md via DAG scheduling + AI enrichment. Subcommands: `prepare`, `next-ready`, `suggest-batches`, `prompt`, `save-enrichment`, `merge`, `inspect [--query] [--list]`, `scan-config`, `deep-scan-state` (incl. `save-run-context` for shell-friendly run-context writes) |
| `viewer.py` | Local viewer — stdlib `http.server` serving the React `dist/` + `/api/bundle` (reuses `upload.py::build_bundle`), `/api/generated-files`, `/api/folder-claude-mds`, `/api/intent-layer-status`, `/api/ignored-rules`, `POST /api/rules` (5 atomic rule actions); auto-reloads when its own source changes |
| `drift.py` | Mechanical drift detection |
| `validate.py` | Cross-reference blueprint against actual codebase |
| `check_rules.py` | Check files against rules (CI path) |
| `measure_health.py` | Erosion, gini, verbosity, top-20%, waste scores + `--append-history` + `--compare-history` (trend deltas) |
| `code_shape.py` | Code-shape matching primitives — a `code_shape` entry on a rule, consumed by `pre-validate.sh` + `rule_index.py` |
| `detect_cycles.py` | Tarjan's SCC on the import graph |
| `install_hooks.py` | 6 hooks + 29 permissions in `.claude/settings.local.json` |
| `merge.py` | Merge blueprint sections; `extract_json_from_text` handles conversation envelopes / code fences |
| `finalize.py` | Normalise blueprint + deep-merge Opus output + id-stable findings upsert + pitfalls into blueprint |
| `verify_findings.py` | Parallel Haiku verifier — per finding, reads the cited `triggering_call_site` + surrounding files and returns `keep` / `demote` / `drop` |
| `apply_verdicts.py` | Applies the verifier's verdicts to `findings.json` with cross-run hysteresis (single-scan flips don't propagate; a git-diff anchor lets real transitions land immediately) |
| `rule_index.py` | Builds `.archie/rule_index.json` (keyword / path / always-inject buckets) from `rules.json` + `platform_rules.json` for hot-path edit-time enforcement |
| `align_check.py` | Phase 3 semantic alignment classifier — compares plan text / staged diff against each rule's `description` + `why` + `example` via one Claude CLI call |
| `migrate_blueprint_rules.py` | Migrates legacy blueprint-derived rule sections (pre-3.0) into `proposed_rules.json` |
| `arch_review.py` | Architectural review checklist for plans and diffs |
| `refresh.py` | File change detection (hash comparison) |
| `extract_output.py` | Subcommands: `rules`, `deep-drift`, `recent-files`, `save-duplications` |
| `telemetry.py` | Per-run step-level wall-clock timing → `.archie/telemetry/<command>_<ts>.json`. Subcommands: `mark`, `finish`, `extra`, `read`, `write`, `clear`, `steps-count` |
| `telemetry_sync.py` | Anonymous opt-in usage telemetry — records events to `~/.archie/analytics/runs.jsonl` and pushes to the Supabase `telemetry-ingest` function. Subcommands incl. `record-event`, `record-install`, `post-run`, `status`, `purge` |
| `update_check.py` | Anonymous opt-in npm-registry update check (cached, snooze ladder 24h→48h→7d). Prints `UPGRADE_AVAILABLE` / `JUST_UPGRADED` markers for slash-command preambles |
| `config.py` | Machine-level config at `~/.archie/config.json` — telemetry consent tier, update-check prefs, stable random install id |
| `analytics.py` | Local analytics dashboard over `~/.archie/analytics/runs.jsonl` (`7d` / `30d` / `all` windows) |
| `upload.py` | Build share bundle (`build_bundle` — also reused by `viewer.py`). Default mode POSTs raw bundle to Supabase edge function. Enterprise modes wrap bundle in `{bundle, created_at}` envelope and either (a) sigv4-PUT directly to customer S3 bucket + generate presigned GET URL (`--mode enterprise-creds`), or (b) do plain HTTP PUT to a customer-provided presigned URL (`--mode enterprise-paste --put-url ... --get-url ...`). All modes produce a URL; enterprise modes encode the GET URL in the viewer URL's fragment. |
| `share_setup.py` | One-time setup wizard for enterprise share Mode 2A. Accepts `--bucket --region --access-key-id --secret-access-key [--key-prefix] [--presign-expires-seconds]` and writes `~/.archie/share-profile.json` with `chmod 600`. Per-user (not per-project). |
| `lint_gate.py` | Opt-in external linter gate (Tier 3). Invoked by `post-lint.sh`; reads `.archie/enforcement.json`; auto-detects ruff / eslint / golangci-lint / semgrep based on project config files + binary on PATH; per-kind config overrides; `target: "parent"` dispatch for package-aware linters (golangci-lint) |

---

## NPM Package — Distribution

### Installer (`npm-package/bin/archie.mjs`)

`npx @bitraptors/archie /path/to/project [--commands-dir dir]` performs:

1. **Preflight** — require Node 18+; reject unknown flags and print `--help` (a past source of bogus installs was silently-swallowed typos)
2. **Clean install** — removes old `.py` scripts from `.archie/`, old `archie-*.md` commands, the legacy `archie-deep-scan/` command subtree, `_shared/scope_resolution.md`, the `.claude/skills/archie-deep-scan/` subtree, `.claude/hooks/`, the hook section of `.claude/settings.local.json`, and the old `platform_rules.json` — so re-installs are clean and upgrades are safe in-place. User data (`blueprint.json`, `findings.json`, `rules.json`, …) is preserved.
3. Create `.claude/commands/`, `.claude/skills/`, and `.archie/` in the target project
4. Copy the 5 slash commands + `_shared/scope_resolution.md`
5. Copy the `archie-deep-scan` skill subtree to `.claude/skills/archie-deep-scan/` (`SKILL.md`, `steps/`, `fragments/`, `templates/`)
6. Copy 30 standalone Python scripts to `.archie/`
7. Copy `platform_rules.json`
8. Copy the React viewer source into `.archie/viewer/` and build it once (`npm ci` + `vite build`, then drop `node_modules`) — cached by a `.archie-version` marker so unchanged versions skip the ~45s build
9. Copy `.archieignore` + `.archiebulk` defaults (only if not already present — preserves user customisations)
10. Append `.gitignore` entries for installed tooling (idempotent, handles upgrade from older versions)
11. Run `python3 install_hooks.py` to set up 6 hooks + 29 permissions in `.claude/settings.local.json`
12. Write the machine-level version marker (`~/.archie/version`); on a version change, mark `JUST_UPGRADED` so the next slash command can acknowledge it
13. Print installation summary + next steps

The installer does **not** prompt for telemetry consent — an `npx` install can be non-interactive (CI, pipe, agent shell), so a prompt there is unreliable. Consent is asked in-session by the first slash command instead (see [Telemetry](#telemetry)).

If the viewer build fails (no internet, old Node), the installer keeps going — scripts and hooks still install; only `/archie-viewer` is affected until the user re-runs.

### Assets (`npm-package/assets/`)

Exact copies of every canonical file the installer ships — the 30 scripts, the 5 commands, `_shared/`, the `skills/archie-deep-scan/` subtree, the `viewer/` source, and the `.archieignore` / `.archiebulk` / `platform_rules.json` defaults. See [File Sync Protocol](#file-sync-protocol).

---

## Claude Code Integration

### Slash commands (`.claude/commands/`)

| Command | File | Purpose |
|---------|------|---------|
| `/archie-scan` | `archie-scan.md` | Architecture health check: 3 parallel Sonnets + single AI synthesis. Writes to `findings.json` and `semantic_duplications.json` |
| `/archie-deep-scan` | `archie-deep-scan.md` (router) → `skills/archie-deep-scan/` | Full 2-wave analysis. The command file is a thin router; the pipeline is the **`archie-deep-scan` skill**. Supports `--incremental`, `--continue`, `--from N`, `--reconfigure`. Intent Layer is opt-in via Step E. Step 7 delegates to `/archie-intent-layer` Phases 1–4 as a single source of truth |
| `/archie-intent-layer` | `archie-intent-layer.md` | Standalone per-folder CLAUDE.md regen. Phase 0.5 asks Full/Incremental/Auto; Auto uses `deep-scan-state detect-changes` against `last_deep_scan.json`. Hard-requires `blueprint.json`. Same Sonnet subagent DAG used by deep-scan Step 7 |
| `/archie-share` | `archie-share.md` | Upload bundle to hosted viewer via `upload.py` + return URL |
| `/archie-viewer` | `archie-viewer.md` | Launches `viewer.py` — the local React sidecar at `localhost:5847/local` (Blueprint + Files tabs) |

All choice prompts in scan/deep-scan use `AskUserQuestion` (monorepo scope picker, parallel/sequential, Intent Layer opt-in) — no free-text answers to parse. The scope (Step C) and Intent Layer (Step E) prompts are **mandatory decision gates**: the skill instructs the agent to ask them even under a "no clarifying questions" harness mode, since they change which trees get scanned and what files get written.

### Skills (`.claude/skills/`)

`archie-deep-scan/` — the deep-scan pipeline itself, packaged as a skill. `SKILL.md` is the orchestrator/router; `steps/` holds one file per pipeline step (Step 3 fans out into `step-3-wave1/` with a prompt file per Wave 1 agent); `fragments/` holds the cross-step telemetry and `/compact`-resume contracts; `templates/` holds the scan-report template. Moving the substeps under `skills/` instead of `commands/` keeps Claude Code from listing every substep file as its own slash command.

---

## Share Pipeline (`/archie-share`)

Upload a blueprint + findings + scan report to a hosted React viewer. Three modes — picked interactively at share time.

### Mode overview

| Mode | Where blueprint lives | Credentials on dev disk | URL shape | BitRaptors stores |
|---|---|---|---|---|
| **Default** | BitRaptors Supabase | none | `archie-viewer.vercel.app/r/{token}` | Full bundle JSON |
| **Enterprise — stored credentials** (Mode 2A) | Customer's S3 bucket | AWS access key/secret in `~/.archie/share-profile.json` (`chmod 600`) | `archie-viewer.vercel.app/r/ext#{base64url(presigned-GET)}` | **Nothing** |
| **Enterprise — paste URL** (Mode 2B) | Customer's bucket (any S3-compatible / Azure / GCS) | None — InfoSec mints presigned PUT per share | `archie-viewer.vercel.app/r/ext#{base64url(GET)}` | **Nothing** |

Default is the out-of-the-box behavior. Enterprise modes are for teams whose InfoSec blocks uploading architecture data to third-party infrastructure.

### Key architectural property — URL fragment carries the GET URL

The URL fragment (`#...`) is a browser-only construct — never transmitted to any server in HTTP requests. In enterprise modes:

1. Archie uploads the bundle directly to the customer's bucket.
2. Archie base64url-encodes the GET URL (presigned in Mode 2A, customer-supplied in Mode 2B) into the share URL's fragment.
3. When a teammate opens the URL, their browser loads the static viewer JS from Vercel but the fragment never goes over the network.
4. The viewer reads `window.location.hash` client-side, decodes the GET URL, and `fetch()`s the blueprint directly from the customer bucket.

Net effect: **BitRaptors' only role in enterprise mode is serving static JS from Vercel**. No data at rest, no pointer storage, no metadata captured.

### Default flow (unchanged)

```
Local project                    Supabase (upload function)              Supabase DB
  |                                        |                                   |
  archie-share                             |                                   |
  |                                        |                                   |
  python3 .archie/upload.py -----> POST /functions/v1/upload --> insert report
  |     build_bundle()                     |                         token, bundle
  |     - blueprint.json                   |                                   |
  |     - findings.json (if exists)        |                                   |
  |     - health.json (stripped)           |                                   |
  |     - scan_meta, rules_adopted         |                                   |
  |     - rules_proposed                   |                                   |
  |     - scan_report.md                   |                                   |
  |     - semantic_duplications            |                                   |
  |                                        v                                   |
  |<---------------------------- {"token": "…"}                                |
  |                                                                            |
  Print:  archie-viewer.vercel.app/r/{token}                                   |
                                                                               |
User shares URL  -->  React viewer  -->  GET /functions/v1/blueprint?token=… -|
                        (CoverPage preview + ReportPage details)
```

### Enterprise Mode 2A — stored credentials

Setup (one-time):

```bash
python3 .archie/share_setup.py \
  --bucket acme-archie-shares \
  --region us-east-1 \
  --access-key-id AKIA… \
  --secret-access-key … \
  [--key-prefix archie-shares/] \
  [--presign-expires-seconds 604800]
```

`share_setup.py` writes `~/.archie/share-profile.json` with `chmod 600` (owner read/write only). The file never lives in the project directory — it's per-user, not per-project.

Flow:

```
Local project                        Customer S3 bucket
  |                                           |
  archie-share (mode=enterprise-creds)        |
  |                                           |
  python3 .archie/upload.py --mode=...        |
  |     _read_share_profile()                 |
  |     _build_enterprise_bundle()            |
  |     _sigv4_sign_put() --------> PUT /archie-shares/<uuid>.json
  |                                           |
  |     _sigv4_presign_get()   <-- returns presigned GET URL (7-day expiry)
  |                                           |
  |     _build_enterprise_share_url()         |
  Print:  archie-viewer.vercel.app/r/ext#<base64url(get_url)>

Teammate opens URL:
  Browser --> Vercel (static JS only) --> fetches blueprint directly
                                          from customer bucket via fragment-decoded URL
```

SigV4 signing is pure stdlib (`hashlib`, `hmac`, `urllib.parse`, `datetime`) — no boto3. Implementation validated against AWS's canonical presigned-GET test vector (signature `aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404`).

Scope: AWS virtual-hosted-style (`{bucket}.s3.{region}.amazonaws.com`). S3-compatible services (R2, B2, Minio, Wasabi) use different DNS shapes and need a future `endpoint_url` profile override. Non-AWS users should use Mode 2B.

### Enterprise Mode 2B — per-share presigned PUT URL

No setup, no credentials persisted. Per-share workflow:

```
Dev:                                 InfoSec:
  /archie-share                       acme-archie-url-mint (Lambda/script/ticket)
      picks enterprise-paste               generates presigned PUT + GET pair
      prompts for URLs                     — URLs expire (typically 1h)
  pastes URLs     <------------------- hands over
  |
  python3 .archie/upload.py \
    --mode=enterprise-paste \
    --put-url "<PRESIGNED_PUT>" \
    --get-url "<PRESIGNED_GET>"
  |
  HTTP PUT --------> customer bucket (via presigned PUT URL)
  |
  _build_enterprise_share_url(GET)
  Print:  archie-viewer.vercel.app/r/ext#<base64url(get_url)>
```

Cloud-agnostic by design — Mode 2B is the recommended path for Azure Blob, GCS, Artifactory, or any HTTP-PUT-accepting endpoint. InfoSec keeps full control over URL lifetime and audit trail via their own minter.

### Upload bundle (`upload.py::build_bundle`)

Shared across all three modes:

```python
{
  "blueprint": {...},                    # required
  "health": {...},                       # stripped (top-20 high-CC functions, top-10 duplicates)
  "scan_meta": {...},                    # frameworks, subproject count, frontend_ratio
  "rules_adopted": {...},
  "rules_proposed": {...},
  "scan_report": "...",
  "semantic_duplications": [...],        # structured, from semantic_duplications.json
  "findings": [...]                      # from findings.json (shared store)
}
```

In enterprise modes, the bundle is wrapped in an envelope `{bundle, created_at}` before upload so the viewer's `ReportResponse` shape matches both flows. `created_at` is the scan timestamp (`blueprint.meta.scanned_at` / `last_scan`), not the upload time, so re-shares show a stable date.

### Supabase edge functions (`share/supabase/functions/`)

Used only in default share mode — not touched by enterprise modes.

- **`upload/index.ts`** — accepts JSON up to 5 MB, validates `blueprint` field, generates 24-char token, inserts `{token, bundle, size_bytes}` into the `reports` table.
- **`blueprint/index.ts`** — fetches bundle by token, returns `{bundle, created_at}`.
- **`telemetry-ingest/index.ts`** — receives anonymous opt-in usage events (see [Telemetry](#telemetry)). Uses the Supabase anon key plus an RLS-restricted **insert-only** policy on `telemetry_events` (never the service role); RLS is hardened to block direct PostgREST bypass.

### React viewer (`share/viewer/`) — one codebase, local + cloud

The **same React/Vite app** powers both the hosted share viewer (`archie-viewer.vercel.app`) and the local `/archie-viewer` sidecar. It does not assemble the bundle itself — `upload.py::build_bundle` is the single bundle assembler, and `viewer.py` imports it directly, so local and cloud render byte-identical data. The unifying contract is the `ReportResponse` envelope `{ bundle, created_at }` (`src/lib/api.ts`).

Routes (`src/main.tsx`):

- **`/local`** — `LocalPage.tsx`: fetches `/api/bundle` from `viewer.py` and hands the bundle to `ReportPage`. Adds a **Files** tab (per-folder CLAUDE.md browser + generated-files tree) and inline rule actions that `POST /api/rules`.
- **`/r/{token}`** — `CoverPage.tsx`: executive summary, top findings, headline metrics, hero CTA.
- **`/r/{token}/details`** — `ReportPage.tsx`: the full report with sidebar navigation. Sections: Executive Summary, System Health, Architecture Diagram, Workspace Topology, Architecture Rules, Development Rules, Key Decisions, Trade-offs, Implementation Guidelines, Communications, Components, **Integrations**, Technology Stack, Deployment, Architectural Problems, Pitfalls. A **"Fix this"** button on each finding/pitfall generates an agent-agnostic fix prompt (`src/lib/fixPrompt.ts`).

`fetchReport(token)` in `src/lib/api.ts` routes on the token value:

- Any token OTHER than the sentinel `ext` → GET `${SUPABASE}/blueprint?token=X` (default flow, unchanged)
- Token `ext` → read `window.location.hash`, base64url-decode to the GET URL, fetch directly from customer bucket with CORS + 403-expired error messaging

Local mode bypasses `fetchReport` entirely — it talks to `viewer.py`'s localhost API. The sentinel routing means **zero behavioral change for existing share URLs** — anything without the `ext` token falls through to the legacy Supabase path.

### Customer bucket setup (enterprise)

The customer's bucket needs CORS allowing `https://archie-viewer.vercel.app` (so the browser can `fetch()` cross-origin) plus an IAM user with narrow `s3:PutObject` + `s3:GetObject` scoped to the prefix. See [`docs/enterprise-share-setup.md`](enterprise-share-setup.md) for the CORS policy template, IAM policy template, and step-by-step walkthrough for an InfoSec team.

The `/archie-share` slash command also offers a **"Help me ask InfoSec for a bucket"** option — the agent asks three context questions (company name, preferred bucket name, cloud provider) and composes a ready-to-paste request with the CORS + IAM JSON inlined, adapted to AWS / Azure / GCS.

### Backward compatibility

Old bundles on Supabase (uploaded before the 4-field schema migration) are rendered correctly:

- `normalizePitfall` bridges the legacy `{area, description, recommendation, stems_from}` shape into the current `{problem_statement, evidence, root_cause, fix_direction}` shape.
- `RichFindingBody` renders `description` as a lead paragraph so legacy prose bodies are never dropped.
- `scanReportAssertsZeroSemanticDup()` detects explicit "no semantic duplication detected" verdicts in the scan report prose and treats them as a structured 0, so older bundles that never wrote `semantic_duplications.json` still render a trustworthy count.
- Decision precedence in the viewer: structured `bundle.findings` → scan report zero detector → heuristic markdown parse → unknown.

---

## StructuredBlueprint Data Model

The blueprint is the single source of truth for synthesised architecture. All rendered outputs derive from it. Concrete findings live in the separate `findings.json` shared store.

```
blueprint.json
  meta                          # Executive summary, platforms, schema version, scan_count, confidence
  architecture_rules
    file_placement_rules[]      # Where each file type belongs
    naming_conventions[]        # How files and classes should be named
  decisions
    architectural_style         # Title, chosen, rationale, alternatives_rejected
    decision_chain              # Rooted constraint tree with violation_keywords per node
    key_decisions[]             # Each with forced_by / enables / alternatives_rejected
    trade_offs[]                # Accept, benefit, caused_by, violation_signals
    out_of_scope[]              # Explicit boundary markers with linking decisions
  components
    structure_type              # layered, modular, monolith, feature-based, flat, etc.
    components[]                # Name, location, responsibility, depends_on, confidence
  communication
    patterns[]                  # Design and communication patterns (name, when_to_use, how_it_works,
                                #   + preconditions: applicable_when / do_not_apply_when / scope)
    integrations[]              # service, purpose, integration_point (file path)
    pattern_selection_guide[]
  quick_reference
    where_to_put_code           # File type -> directory mapping
    pattern_selection           # Scenario -> pattern mapping
    error_mapping[]
  technology
    stack[]                     # category, name, version, purpose
    project_structure
    run_commands                # build, test, lint, serve, etc.
  frontend                      # Only if frontend_ratio >= 0.20
    framework, rendering_strategy, styling, state_management
    ui_components[]
  workspace_topology            # Only in monorepo `whole` scope
    type, members[], edges[], cycles[], dependency_magnets[]
  pitfalls[]                    # 4-field shape + id + source + depth + confirmed_in_scan
  implementation_guidelines[]
  development_rules[]
  deployment
  architecture_diagram          # Mermaid graph TD, 8-12 nodes
```

Schema version: `2.0.0`

---

## Data Flow

### Hook Execution (during editing)

```
Claude calls Write/Edit/MultiEdit
    |
    v
PreToolUse hook fires
    |
    v
pre-validate.sh
    |-- Read tool call from stdin (tool_name, file_path, content)
    |-- Load rules.json + platform_rules.json
    |-- Check forbidden_import, required_pattern, forbidden_content,
    |   architectural_constraint, file_naming rules
    |-- severity=error -> exit 2 (BLOCKED)
    |-- severity=warn  -> print warning, exit 0
    v
Edit proceeds (or is blocked)
```

### Fast Scan (`/archie-scan`)

```
Phase 1  Parallel data gathering (scripts, seconds)
  scanner.py, measure_health.py, detect_cycles.py, git log
Phase 2  Read accumulated knowledge
  skeletons, scan, health, blueprint, findings, rules, proposed_rules
Phase 3  3 Sonnet agents in parallel (Architecture, Health, Patterns)
  Each receives findings.json scoped to its source slice.
  Novelty priority: focus on problems NOT in store.
Phase 4  Synthesis
  4a Evolve blueprint (components, decisions, health, architecture_rules, development_rules, meta)
     DO NOT write blueprint.pitfalls (deep-scan-Opus-only).
  4b Write findings.json
     - ID-stable match against existing entries (reused id + confirmed_in_scan += 1)
     - Unmatched -> next-free f_NNNN + first_seen = today + depth: draft
     - Gone -> status: resolved + resolved_at
  4c Write scan_history/scan_NNN_*.md and scan_report.md
  4d python3 .archie/extract_output.py save-duplications \
       /tmp/archie_agent_c_rules.json "$PWD"
Phase 5  Proposed rules -> .archie/proposed_rules.json
Phase 6  Telemetry write
```

### Deep Scan (`/archie-deep-scan`, full mode)

```
Step 0  Scope resolution (AskUserQuestion)
Step 1  Scanner -> scan.json (with bulk_content_manifest, frontend_ratio)
Step 2  Read accumulated knowledge
Step 3  Wave 1 — 3-4 parallel Sonnets
        Structure: components, layers, workspace_topology (if whole-mode),
                   cross-workspace cycles as DRAFT findings (not pitfalls)
        Patterns:  communication patterns, design patterns, integrations
        Tech:      stack, deployment, dev_rules
        [UI Layer: if frontend_ratio >= 0.20]
Step 4  Merge Wave 1 outputs via merge.py
        -> blueprint_raw.json
Step 5  Wave 2 — single Opus
        Reads blueprint_raw.json + findings.json
        Three probes: A complexity-budget, B invariants & gates, C seams
        Emits: decision_chain, architectural_style, key_decisions,
               trade_offs, out_of_scope, findings (upgrade drafts + new),
               pitfalls, architecture_diagram, implementation_guidelines
        finalize.py:
          - deep-merge blueprint sections
          - pop findings, id-stable upsert into findings.json
          - merge pitfalls into blueprint.pitfalls
Step 6  Rule synthesis — single Sonnet
        Reads evolved blueprint, proposes architecturally-grounded rules
Step 7  Intent Layer — per-folder CLAUDE.md (OPT-IN, Step E decides)
        If INTENT_LAYER=no: skip, telemetry records "skipped": true
Step 8  Cleanup /tmp/archie_*
Step 9  Drift Detection & Architectural Assessment
        drift.py (mechanical) + single Sonnet (deep AI drift)
        Writes final scan_report.md + scan_history/scan_NNN_*.md
Step 10 Telemetry write to .archie/telemetry/deep-scan_<ts>.json
```

### Incremental deep scan (`--incremental`)

```
Step 1  Scanner (same)
Step 2  Read accumulated knowledge + detect changed files
Step 3' One scoped Reasoning agent (Sonnet)
        Input: blueprint, blueprint_raw, findings, changed files
        Output: ONLY the sections that need updating
Step 4  finalize.py --patch /tmp/archie_sub_x_*.json
        Deep-merges the partial output into existing blueprint + findings store
(skip to Step 6)
```

---

## Compound Learning

Every run feeds the next. Both commands read and write the same `findings.json` shared store:

- **Id-stable upsert.** Recurring findings reuse `id` and bump `confirmed_in_scan`; new ones get a fresh id + `first_seen`; gone ones flip `status: "resolved"` (preserved as history).
- **Novelty priority.** Agents are told to spend cognitive budget on NEW problems, not rediscover known ones under different wording.
- **Depth escalation.** Scan emits `depth: "draft"` quickly (single-line `fix_direction`). Deep-scan Wave 2 upgrades the same id to `depth: "canonical"` with sequenced `fix_direction` and architectural `root_cause`.
- **Blueprint confidence** also grows per-section with repeated confirmation across scans.
- **Health scores** appended to `health_history.json` for trend detection.
- **Source provenance** is tracked on every rule and finding: `deep-baseline`, `scan-observed`, `scan-adopted`, `scan-inferred`, `scan-proposed`, `deep:synthesis`, `scan:{structure,health,patterns}`.

---

## Drift Detection

Deep scans include two-phase drift detection:

### Phase 1: Mechanical drift (`drift.py`)

Deterministic analysis:
- Pattern outliers (files that don't match established patterns)
- File size and complexity violations
- Dependency-direction breaches
- Structural anomalies

### Phase 2: Deep AI drift

An agent reads blueprint + drift report + CLAUDE.md files + `findings.json` to identify drift categories:

| Category | What it detects |
|----------|----------------|
| `decision_violation` | Code that contradicts a recorded architectural decision |
| `pattern_erosion` | Gradual drift away from established patterns |
| `trade_off_undermined` | Changes that undermine accepted trade-offs |
| `pitfall_triggered` | Known pitfalls that have materialised in code |
| `responsibility_leak` | Logic placed in the wrong component/layer |
| `abstraction_bypass` | Direct access that skips established abstractions |
| `semantic_duplication` | Reimplementation of existing functionality |

Violations are grounded with `violation_signals` from the blueprint's trade-off and decision chain data.

---

## Cycle Detection

Every scan runs Tarjan's strongly connected components algorithm (`detect_cycles.py`) on the import graph. Output includes each cycle with the participating directories, file-level evidence showing which imports create the cycle, and dependency magnets (high-in-degree nodes). Results stored in `.archie/dependency_graph.json`.

---

## Telemetry

There are two distinct telemetry surfaces. **Per-run step timing** is always-on and stays local. **Anonymous usage telemetry** is opt-in and, when enabled, uploads a minimal payload to BitRaptors' Supabase.

### Per-run step timing (always-on, local)

Every run writes a per-step wall-clock timing file:

- `.archie/telemetry/scan_<timestamp>.json` — for `/archie-scan`
- `.archie/telemetry/deep-scan_<timestamp>.json` — for `/archie-deep-scan`

```json
{
  "command": "deep-scan",
  "started_at": "YYYY-MM-DDTHHMMSSZ",
  "completed_at": "YYYY-MM-DDTHHMMSSZ",
  "total_seconds": 22147,
  "steps": [
    {"name": "scan",            "seconds": 52, "started_at": "...", "completed_at": "..."},
    {"name": "read",            "seconds": 34},
    {"name": "wave1",           "seconds": 830,   "model": "sonnet"},
    {"name": "merge",           "seconds": 14},
    {"name": "wave2_synthesis", "seconds": 863,   "model": "opus"},
    {"name": "rule_synthesis",  "seconds": 316,   "model": "sonnet"},
    {"name": "intent_layer",    "seconds": 19676, "model": "sonnet", "skipped": false},
    {"name": "cleanup",         "seconds": 22},
    {"name": "drift",           "seconds": 340}
  ]
}
```

Used to measure the wall-clock impact of prompt/code changes over time. Individual steps can set `skipped: true` (e.g. Intent Layer when opted out, or earlier steps skipped via `--from N`) with both timestamps identical. This file never leaves the project.

### Anonymous usage telemetry + update checks (opt-in)

Consent is asked **once per machine**, in-session, by the first Archie slash command the user runs — not by the `npx` installer. Every entry point (`/archie-scan`, `/archie-deep-scan`, `/archie-viewer`, `/archie-share`, `/archie-intent-layer`) loads the shared `_shared/telemetry-consent.md` fragment in its preamble; the fragment runs `config.py should-prompt` and, if this machine hasn't answered, presents an `AskUserQuestion` opt-in. This deliberately lives in the slash commands — which always run inside Claude Code, where a picker is available — instead of the `npx` install, which can be non-interactive (CI, pipe, agent shell). Consent, update-check preferences, and a stable random installation id live in machine-level `~/.archie/config.json` (managed by `config.py`) — not per-project. Three tiers:

| Tier | Payload | Installation id |
|---|---|---|
| `community` *(recommended)* | usage event | included (stable random id) |
| `anonymous` | usage event | stripped before upload — each event unlinkable |
| `off` | nothing leaves the machine | — |

**What an event contains:** command name (`scan` / `deep-scan` / `viewer` / `share` / `intent-layer` / `install`), Archie version, OS/arch, per-step durations, outcome, detected stack categories (e.g. `kotlin` / `gradle` / `android`). **Never collected:** source code, file paths, repo names, blueprint contents, errors from the user's code. Local-only fields (e.g. `_project_basename`) are stripped before upload.

Flow: every scan/share/viewer command ends by calling `telemetry_sync.py record-event` (silent no-op when opted out). Events are appended to `~/.archie/analytics/runs.jsonl` (the local source of truth, readable via `analytics.py 7d|30d|all`) and pushed to the Supabase `telemetry-ingest` edge function — anon key + insert-only RLS, never the service role.

**Update checks** are a separate opt-in (default on). Each slash command preamble runs `update_check.py check` — a cached hit against the public npm registry (`registry.npmjs.org`, no Archie infrastructure) that prints an `UPGRADE_AVAILABLE` / `JUST_UPGRADED` marker. The command surfaces a one-line hint and continues; the user can snooze (24h → 48h → 7d ladder) or disable entirely.

---

## No Inline Python Constraint

Scan templates include a "CRITICAL CONSTRAINT: Never write inline Python" block that forbids `python3 -c "..."` during scans. Every operation has a dedicated CLI command:

| Command | Replaces |
|---------|----------|
| `measure_health.py --append-history --scan-type fast\|deep` | Inline health history append |
| `finalize.py --normalize-only` | Inline blueprint normalisation |
| `finalize.py --patch <file>` | Incremental deep-scan merge |
| `intent_layer.py inspect <file> [--query .key] [--list]` | Ad-hoc JSON inspection; `--list` prints array elements one per line (replaces inline python for array→newline conversion) |
| `intent_layer.py scan-config <dir> read\|write\|validate` | Monorepo scope config management |
| `intent_layer.py deep-scan-state <dir> init\|read\|complete-step N\|detect-changes\|save-baseline\|save-context\|save-run-context` | Deep-scan resume state; `save-run-context` takes flags + newline-separated workspaces via stdin (replaces heredoc-JSON-with-inline-python that used to round-trip workspaces through `python3 -c`) |
| `extract_output.py rules <in> <out>` | Parse rule synthesis output |
| `extract_output.py deep-drift <in> <out>` | Merge drift findings into report |
| `extract_output.py recent-files <scan.json>` | Print source file paths |
| `extract_output.py save-duplications <agent_c_file> <project_root>` | Deterministic semantic_duplications.json writer |
| `telemetry.py <project_root> --command <name> --timing-file <file>` | Write per-run telemetry |
| `telemetry.py steps-count <project_root>` | Count completed step marks (replaces inline python `len(json.load(...).get('steps'))` in deep-scan Resume Prelude) |
| `upload.py <project_root>` | Build + POST share bundle |

This prevents crashes from Claude guessing wrong field names (e.g. `batch_id` vs `id`, `path` vs `id`) and keeps the pipeline deterministic where it matters. The constraint is enforced in the scan templates themselves; Claude Code is told "CRITICAL CONSTRAINT: Never write inline Python" at the top of each scan command, and every data operation has a dedicated subcommand. Even the deep-scan Resume Prelude — which used to contain 8 inline `python3 -c` blocks — now reads every field via dedicated CLIs.

---

## Error Handling and Resilience

| Scenario | Behaviour |
|----------|----------|
| `.archie/rules.json` missing | Hooks exit 0 silently (fail open) |
| Blueprint missing | Scan proceeds without prior knowledge — starts fresh |
| `.archiebulk` missing | `BulkMatcher.classify()` returns None; no bulk tagging; frontend_ratio falls back to extension counts only |
| `findings.json` missing | Agents produce fresh entries; first scan builds the store from scratch |
| File I/O errors during scan | Individual files skipped with try/except; scan continues |
| Deep-scan subagent fails | Skipped; remaining agents continue. `merge.extract_json_from_text` tries three strategies: direct parse, code-block extraction, brace-matching |
| Deep-scan interrupted | `.archie/deep_scan_state.json` tracks completed steps; `--continue` resumes |
| Telemetry write fails | Non-fatal; the scan already completed |
| `/archie-share` upload fails | Blueprint remains local at `.archie/blueprint.json`; exit 1 with stderr explanation |

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific module tests
python -m pytest tests/test_scanner.py -v
python -m pytest tests/test_planner.py -v
python -m pytest tests/test_telemetry.py -v

# Run with coverage
python -m pytest --cov=archie tests/
```

### Test organisation

50 test files. Tests mirror the package structure:

- **Engine** — scanner (+ monorepo variant), dependencies, frameworks, hasher, imports, scan (+ scan_config), engine_models
- **Coordinator** — planner, runner, merger, prompts
- **Hooks** — hook_generator, hook_enforcement
- **Rules** — rule_extractor (legacy), rule_shape, rule_index, code_shape, align_check, migrate_blueprint_rules
- **Renderer** — renderer (+ field_coverage, merge), intent_layer (+ bulk_filter, inject_scoped, resume, run_context, suggest_batches), normalize, inspect
- **Findings / scan pipeline** — finalize_findings_merge, verify_findings, apply_verdicts
- **Deep-scan skill** — deep_scan_state_shell_api
- **CLI** — init, refresh, status, serve, check
- **E2E** — refresh_e2e
- **Standalone helpers** — ignore_patterns, health_append, telemetry, upload, share_setup, lint_gate, viewer

Tests use fixtures (temp directories with known file structures), subprocess mocking for runner/agent tests, and Pydantic model validation for schema compliance.

---

## File Sync Protocol

Standalone scripts, slash commands, the deep-scan skill subtree, the shared scope fragment, and the viewer source all exist in two places (canonical → copy):

```
archie/standalone/*.py                 ->  npm-package/assets/*.py
archie/standalone/platform_rules.json  ->  npm-package/assets/platform_rules.json
.claude/commands/archie-*.md           ->  npm-package/assets/archie-*.md
.claude/commands/_shared/*.md          ->  npm-package/assets/_shared/*.md
.claude/skills/archie-deep-scan/**     ->  npm-package/assets/skills/archie-deep-scan/**
share/viewer/  (source, minus build)   ->  npm-package/assets/viewer/
```

`archiebulk.default` and `archieignore.default` live only in `npm-package/assets/` (installer-only resources).

**Workflow:**

1. Always edit the canonical file first (`archie/standalone/`, `.claude/commands/`, `.claude/skills/`, or `share/viewer/`)
2. Copy to `npm-package/assets/`
3. Before committing, run the sync checker:

```bash
python3 scripts/verify_sync.py
```

This verifies all canonical files, asset copies, and `archie.mjs` references are consistent. It catches missing copies, orphan assets, and dead installer references, then reports:

```
SYNC CHECK PASSED — 30 scripts, 6 commands, all in sync.
```

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
9. [Deep Scan (`/archie-deep-scan`)](#deep-scan-archie-deep-scan)
10. [Findings Store](#findings-store)
11. [Pitfalls](#pitfalls)
12. [Hooks — Real-Time Enforcement](#hooks--real-time-enforcement)
13. [Rules — Synthesis and Delivery](#rules--synthesis-and-delivery)
14. [Renderer — Output Generation](#renderer--output-generation)
15. [Standalone Scripts](#standalone-scripts)
16. [NPM Package — Distribution](#npm-package--distribution)
18. [Multi-Agent Connector Architecture](#multi-agent-connector-architecture)
19. [Coding Agent Integration (Claude / Codex)](#coding-agent-integration-claude--codex)
20. [Share Pipeline (`/archie-share`)](#share-pipeline-archie-share)
20. [StructuredBlueprint Data Model](#structuredblueprint-data-model)
21. [Data Flow](#data-flow)
22. [Compound Learning](#compound-learning)
23. [Drift Coverage](#drift-coverage-no-dedicated-drift-step)
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

Archie has three user-facing slash commands (+ one local inspector):

- **`/archie-deep-scan`** — comprehensive baseline (15–20 min). Full 2-wave multi-agent analysis (3–4 parallel Sonnet fact-gatherers + one Opus reasoner). Produces complete blueprint and all outputs. Supports `--incremental` (changed files only, 3–6 min), `--continue` (resume interrupted run), `--from N` (resume from step N), `--reconfigure` (re-prompt monorepo scope). Auto-detects monorepos and offers parallel sub-project analysis. Intent Layer (per-folder CLAUDE.md) is **opt-in** via an interactive prompt at Step E. Implemented as a **modular workflow** — the rendered `deep-scan/` tree holds a `SKILL.md` router plus self-contained per-step files, fragments, and templates, so the long pipeline survives `/compact` and resumes mid-run.
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
| Testing | pytest | 54 test files |
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
  manifest.py                   # CLI-agnostic install dataclasses: CommandDef, HookDef, ConfigPatch
  manifest_data.py              # The manifest: 5 COMMANDS, 7 HOOKS, 2 CONFIG_PATCHES
  install.py                    # Connector-driven install loop + workflow template renderer
  connectors/                   # Install-time per-CLI adapters
    base.py                     # Connector ABC + render-map fields
    claude.py                   # ClaudeConnector — Claude Code install + render map
    codex.py                    # CodexConnector — Codex CLI install + render map
  standalone/                   # Zero-dependency scripts (exported to target projects)
    _common.py                  # IgnoreMatcher, BulkMatcher, DECISION_RE, normalize_blueprint
    agent_cli.py                # Runtime per-CLI adapter — headless Claude/Codex invocation (detect_verifier/run_verifier)
    scanner.py                  # File tree, import graph, framework detection, skeleton extraction, bulk manifest
    renderer.py                 # Generate AGENTS.md (canonical) + CLAUDE.md pointer + .claude/rules/ topic files
    intent_layer.py             # Per-folder CLAUDE.md via DAG scheduling + AI enrichment + inspect/scan-config/deep-scan-state/save-run-context
    viewer.py                   # Local viewer — serves the React dist/ + /api/* JSON endpoints (stdlib http.server)
    validate.py                 # Cross-reference blueprint against actual codebase
    check_rules.py              # Check files against rules (CI path)
    measure_health.py           # Erosion, gini, verbosity, top-20%, waste scores + history append + --compare-history
    code_shape.py               # Code-shape matching primitives consumed by the pre-validate hook + rule index
    detect_cycles.py            # Tarjan's SCC on the import graph
    install_hooks.py            # Legacy Claude-only hook installer (backwards compat; modern installs route through the connector loop)
    merge.py                    # Merge blueprint sections from multiple sources
    finalize.py                 # Deep merge + findings upsert into store + pitfalls into blueprint
    verify_findings.py          # Finding verifier — checks each finding's triggering_call_site against real code (calls agent_cli)
    apply_verdicts.py           # Apply verifier verdicts to findings.json with cross-run hysteresis
    rule_index.py               # Pre-compute .archie/rule_index.json (keyword / path / always-inject buckets) for hot-path enforcement
    align_check.py              # Phase 3 semantic alignment classifier — plan/diff intent vs rule description+why+example
    migrate_blueprint_rules.py  # Migrate legacy blueprint rule sections into proposed_rules.json
    arch_review.py              # Architectural review checklist for plans and diffs
    refresh.py                  # File change detection (hash comparison)
    extract_output.py           # rules / save-duplications subcommands
    telemetry.py                # Per-run step-level wall-clock timing + steps-count action
    telemetry_sync.py           # Anonymous opt-in telemetry — record events, push to Supabase
    update_check.py             # Anonymous opt-in npm-registry update check + snooze ladder
    config.py                   # Machine-level config at ~/.archie/config.json (telemetry consent, update prefs, install id)
    analytics.py                # Local analytics dashboard over ~/.archie/analytics/runs.jsonl
    upload.py                   # Build share bundle; default mode POSTs to Supabase, enterprise modes do sigv4-PUT or presigned-PUT to customer bucket + build fragment-embedded viewer URL
    share_setup.py              # Enterprise share setup wizard: writes ~/.archie/share-profile.json (chmod 600) from flags
    lint_gate.py                # Opt-in external linter gate (ruff / eslint / golangci-lint / semgrep) behind .archie/enforcement.json
  assets/                       # Canonical install assets (rendered/copied into target projects)
    workflow/                   # Templated canonical workflow — authored once, rendered per-CLI
      _shared/                  # Cross-command fragments (scope_resolution, telemetry-consent)
      scan/SKILL.md             # Fast-scan workflow
      deep-scan/                # SKILL.md router + steps/ + fragments/ + templates/
      intent-layer/SKILL.md     # Per-folder CLAUDE.md workflow
      share/SKILL.md            # Share workflow
      viewer/SKILL.md           # Local viewer launcher workflow
    hook_scripts/               # Canonical hook .sh scripts (copied to .archie/hooks/)
    viewer/                     # React viewer source — built into dist/ at install time
    archieignore.default        # Default `.archieignore` template
    archiebulk.default          # Default `.archiebulk` template (three tier, path-based)
    platform_rules.json         # 30 predefined architectural checks

npm-package/
  bin/archie.mjs                # npx @bitraptors/archie installer entry point
  assets/                       # Verbatim mirror of canonical Archie install assets
    *.py                        # Mirror of every standalone script
    workflow/                   # Mirror of archie/assets/workflow/ (templated, unrendered)
    hook_scripts/               # Mirror of canonical hook scripts
    _install_pkg/               # Byte-identical copy of archie/ install loop + connectors + manifest
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

tests/                          # 54 test files

docs/
  ARCHITECTURE.md               # This file
  enterprise-share-setup.md     # Customer-side bucket setup walkthrough (CORS + IAM templates)

landing/                        # Landing page
v1/                             # Archived V1 web app + landing (FastAPI + Next.js, obsolete)

.archie/                        # Installed into target projects (shown here for orientation)
  workflow/claude/              # Canonical workflow rendered through the Claude render map
  workflow/codex/               # Canonical workflow rendered through the Codex render map
  *.py                          # The standalone pipeline scripts
  hooks/*.sh                    # The canonical hook scripts

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
Claude Code slash commands (archie-deep-scan, archie-share, archie-viewer)
  |
  v  (orchestration is markdown-in-a-slash-command, not Python — the slash command
  |   spawns subagents and calls the standalone scripts via Bash)
  |
  v
Standalone scripts (archie/standalone/*.py)            <-- primary runtime path
  |   scanner, measure_health, detect_cycles,
  |   finalize, merge, intent_layer,
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
- **Share** — `upload.py` builds a bundle (blueprint + findings + health + rules) and POSTs it to the Supabase edge function; the React viewer renders it from a token URL.

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

Each command is a thin shim (`.claude/commands/archie-*.md` for Claude, `.agents/skills/archie-*/SKILL.md` for Codex) that points at the command's rendered workflow under `.archie/workflow/<cli>/<command>/SKILL.md`. `/archie-deep-scan`'s `SKILL.md` is an orchestrator/router with self-contained per-step files (`steps/`, `fragments/`, `templates/`); the other commands have a single `SKILL.md`. The step split keeps each step independently readable and lets the pipeline survive `/compact` and resume via `--continue` / `--from N`. The orchestrator pattern:

1. Calling standalone Python scripts for deterministic steps (`scanner.py`, `measure_health.py`, `detect_cycles.py`, `finalize.py`, `extract_output.py`, `drift.py`, `intent_layer.py`, `telemetry.py`).
2. Spawning subagents via the Agent tool for AI steps (3–4 parallel Sonnets in Wave 1, one Opus in Wave 2, one Sonnet for rule synthesis, N Sonnets for Intent Layer if opted in).
3. Using `AskUserQuestion` for all single-choice prompts (scope picker, parallel/sequential, Intent Layer opt-in) — no free-text answers to parse.

### Python-package path (planner/runner/merger, `archie/coordinator/`)

Kept for CI/tests and standalone Python usage. Groups files into token-budgeted `SubagentAssignment`s (150k tokens per group, bin-packed by top-level directory), builds prompts, spawns `claude -p` subprocesses, parses JSON responses with three-strategy fallback, merges partial blueprints. Not exercised by the default slash-command flow.

---

## Deep Scan (`/archie-deep-scan`)

15–20 minutes on first run; `--incremental` mode handles later runs in 3–6 min.

**Workflow structure.** `/archie-deep-scan` is a modular workflow tree, not a monolithic command file. The command shim is a thin router; the real pipeline is the rendered `deep-scan/` tree under `.archie/workflow/<cli>/` — authored once as a template under `archie/assets/workflow/deep-scan/`:

- `SKILL.md` — the orchestrator: flag parsing (`--incremental` / `--continue` / `--from N` / `--reconfigure`), the resume preamble, and a step-routing table.
- `steps/step-1-scanner.md` … `step-9-finalize.md` — one self-contained file per step (Step 3 expands into `step-3-wave1/` with one prompt file per Wave 1 agent + shared grounding rules).
- `fragments/` — cross-step contracts: `telemetry-conventions.md`, `compact-resume-contract.md`, `resume-prelude.md`.
- Phase 0 scope resolution is loaded from the shared `_shared/scope_resolution.md` fragment.

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
              Writes .archie/tmp/archie_agent_*.json
Step 4        Merge Wave 1 outputs into blueprint_raw.json via merge.py
Step 5  Wave 2 (single Opus) — synthesis
              Reads blueprint_raw.json + findings.json
              Runs three probes: A complexity-budget, B invariants & gates, C seams
              Emits decision chain, architectural style, key decisions,
                   trade-offs, out-of-scope, findings (upgrade + new),
                   pitfalls, architecture diagram, implementation guidelines
              Writes .archie/tmp/archie_sub_x_*.json
              finalize.py deep-merges into blueprint.json and upserts findings into the store
Step 6  Rule synthesis (single Sonnet) — proposes architecturally-grounded rules
Step 7  Intent Layer (opt-in) — per-folder CLAUDE.md via DAG scheduling
              If INTENT_LAYER=no from Step E, this step is skipped and
              telemetry records "skipped": true
Step 8        Cleanup
Step 9        Finalize — health metrics (measure_health.py + history),
              incremental baseline marker, telemetry write, closing summary
```

### Incremental mode (`--incremental`)

Skips Wave 1 entirely. One scoped Reasoning agent receives `blueprint.json` + `blueprint_raw.json` + changed-files list + `findings.json`, returns only the sections that need updating, and `finalize.py --patch` deep-merges the diff.

### Resume modes

- `--continue` resumes from the last completed step (tracked in `.archie/deep_scan_state.json`).
- `--from N` resumes from a specific step.

---

## Findings Store

`.archie/findings.json` is a **compounding store** — `/archie-deep-scan` reads from it and writes back to it on every run.

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

Both connectors pre-approve the deep-scan command surface at install time so the workflow runs without interactive prompts on either CLI. The two mechanisms are different — Claude's `permissions.allow` (shell-glob semantics) versus Codex's execpolicy Rules (argv-prefix semantics) — but they're seeded from a shared catalogue in `archie/manifest_data.py::COMMAND_RULES` so adding a new utility or Archie script extends both with one entry.

**Claude side — `.claude/settings.local.json` `permissions.allow`:**

- `Bash(python3 .archie/*.py *)`, `Bash(python3 -c *)`
- `Bash(git *)`, `Bash(sort *)`, `Bash(head *)`, `Bash(test *)`, `Bash(cp *)`, `Bash(ls *)`, `Bash(wc *)`, `Bash(cat *)`, `Bash(echo *)`, `Bash(for *)`, `Bash(mkdir *)`, `Bash(date *)`
- `Bash(rm -f .archie/tmp/archie_*)`, `Bash(rm -f .archie/health.json)`
- `Read(.archie/*)`, `Read(.archie/**)`, `Write(.archie/*)`, `Write(.archie/**)`, `Edit(.archie/*)`, `Edit(.archie/**)` — the broad `.archie/**` Read/Write rules cover the `.archie/tmp/` artifact directory natively; no separate `/tmp/` permissions needed since Wave 1 / Intent Layer / rule outputs all land workspace-relative
- `Read(**)`
- `Write(**/CLAUDE.md)`, `Edit(**/CLAUDE.md)`
- `Agent(*)` for subagent spawning

**Codex side — three coordinated writes** in `CodexConnector.finalize()`:

1. `<project>/.codex/rules/archie.rules` — a Starlark file with one `prefix_rule(decision="allow", …)` per Archie Python script and per shell-utility shape from the catalogue. Format documented at developers.openai.com/codex/rules. Codex's argv-prefix matcher pre-approves these commands without asking the user.
2. `<project>/.codex/agents/archie-analysis.toml` — the project-scoped custom subagent definition (`name = "archie_analysis"` + `sandbox_mode = "workspace-write"`) that the parallel-dispatch partials ask Codex to spawn.
3. `~/.codex/config.toml` patches:
   - top-level `project_doc_max_bytes` + `project_doc_fallback_filenames` (overwrite — Archie requirement for CLAUDE.md fallback to fit)
   - `[agents] max_threads = 6, max_depth = 2` (set-if-absent — depth 2 supports root → workspace worker → Wave-1 worker on monorepo deep-scans)
   - `[projects."<abs-path>"] trust_level = "trusted"` (set-if-absent — gates whether the project-scoped `.codex/` layer above loads at all; per Codex docs: "Untrusted projects skip project-scoped `.codex/` layers, including project-local config, hooks, and rules")

Installing Archie is itself the trust act. All three `[…] section` writes use set-if-absent semantics so a user who manually customised `max_threads`, raised `max_depth`, or explicitly marked the project `"untrusted"` is respected.

**Intentionally NOT auto-approved** on either CLI: mutating git (`commit`, `push`, `reset`, `rebase`, `checkout`), network egress (the share upload triggers Codex's one-time workspace-write network-access prompt — documented in `share/SKILL.md`), and anything outside the catalogue's command list.

All hooks fail open: missing rules/config/marker files → hooks exit 0 silently.

### Subagent output contract

Every analysis subagent spawned during a scan receives a mandatory instruction (the connector-rendered `{{>output_contract}}` partial) to write its complete output directly to `.archie/tmp/archie_*.json` — Claude renders this as a `Write` tool call, Codex renders it as `apply_patch` against the workspace path. Both land covered by `Write(.archie/**)` (Claude's permission allowlist) and Codex's default `workspace-write` sandbox. The orchestrator never copies subagent transcripts. This avoids Claude Code's sensitive-file guardrail on `~/.claude/projects/.../subagents/*.jsonl` (which used to fire a permission prompt on every batch), keeps subagent output out of the orchestrator's context (less compaction pressure), and isolates failures (missing confirmation line or missing file → clear signal, no silent fallback to transcript scraping). Artifacts are workspace-relative under `.archie/tmp/`, gitignored at install time via a self-ignoring `.archie/tmp/.gitignore` so they never get committed.

The contract is enforced in 5 spawn sites across the slash commands: Wave 1 structural agents (3–4 Sonnets), Wave 2 reasoning agents (full + incremental paths), rule-proposer agent, and Intent Layer enrichment subagents.

---

## Rules — Synthesis and Delivery

Rules come from two AI-synthesized sources plus a universal platform set. They all share one **inline rich rule shape** — each rule carries the semantic content the agent needs at edit time, so the pre-edit hook never has to read the blueprint or follow a pointer.

> **Retired:** the deterministic blueprint extractor (`archie/rules/extractor.py::extract_rules`) was removed from the pipeline in v2.5.0. Its `allowed_dirs` lookup went stale and AI rule synthesis (source 1 below) covers placement + naming with full semantic content the extractor couldn't express. The file still exists for test coverage but nothing calls it. A fresh `archie init` writes an empty `rules.json`; the user populates it by running `/archie-deep-scan`.

### 1. `/archie-deep-scan` Step 6 — Sonnet rule synthesis (the baseline)

The Step 6 agent reads the synthesized blueprint and proposes the architectural rule baseline. Each rule carries inline semantic content:

- `severity_class` — one of `decision_violation` / `pitfall_triggered` / `tradeoff_undermined` / `pattern_divergence` / `mechanical_violation` (drives how the pre-edit hook responds)
- `description` — what the rule enforces
- `why` — the reasoning, copy-pasted from the motivating blueprint section
- `example` — canonical code shape, from `implementation_guidelines.usage_example` when present
- `forced_by` / `enables` / `alternative` — links back to the motivating decision
- `source: "deep_scan"`

Mechanical rules (regex-checkable housekeeping) additionally carry `check` + `forbidden_patterns` / `required_in_content` fields, and may emit a `code_shape` entry consumed by `code_shape.py` + the rule index.

Old-shape rules (no `severity_class` / `why` / `example`) still work — the hook and renderer fall back to `severity` + `rationale`. Historical rules carrying `source: "scan"` or `source: "scan-amended"` (from the retired `/archie-scan` command) are still respected at edit time but no longer produced — the deep-scan synthesizer is now the only generator of new rules.

### 2. Platform rules (`platform_rules.json`, 30 rules)

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

The AI rule synthesizer in `/archie-deep-scan` Step 6 emits `keywords` for every rule and picks the narrowest meaningful `applies_to` scope, promoting broad-but-critical globals to `always_inject` rather than leaving them scopeless. `rule_index.py` pre-computes `.archie/rule_index.json` from `rules.json` + `platform_rules.json` so the hot-path hook does bucket lookups instead of scanning every rule.

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

**Topic-file chunking.** A topic file whose rendered body exceeds 8 KB is split per H2 section (falling back to H3 categories when the body has a single H2 wrapper, e.g. `dev-rules`): the sections move to `.claude/rules/<topic>/<section-slug>.md` and the topic file itself — at the same path AGENTS.md already links to — becomes a routing index: a table of section · file · ~token estimate · contents summary (H3 entry names or rule counts). An agent reads the ~1 KB index and loads only the 2–6 KB section it needs. Small topics stay single-file. `cleanup_stale_rule_files()` runs after every render and removes the retired pre-2.5 `enforcement.md` monolith, orphaned chunks after section renames, and the chunk directory when a topic shrinks back to a single file.

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

Zero-dependency Python scripts in `archie/standalone/`. These are exported to target projects via `npx @bitraptors/archie` (and `pip install archie-cli` + `python3 -m archie.install`); the install loop's `_STANDALONE_SCRIPTS` list is the canonical roster.

| Script | Purpose |
|--------|---------|
| `_common.py` | `IgnoreMatcher`, `BulkMatcher`, `_glob_to_regex`, `DECISION_RE`, `normalize_blueprint()`, JSON helpers |
| `agent_cli.py` | Runtime per-CLI adapter — `detect_verifier()` reads `CLAUDECODE` to pick the harness, `run_verifier()` shells out to `claude -p` / `codex exec` for mid-pipeline model calls |
| `scanner.py` | File tree, import graph, framework detection, skeleton extraction, bulk classification, `frontend_ratio` |
| `renderer.py` | Blueprint JSON → AGENTS.md (canonical) + CLAUDE.md pointer + `.claude/rules/` topic files + `enforcement/` directory |
| `intent_layer.py` | Per-folder CLAUDE.md via DAG scheduling + AI enrichment. Subcommands: `prepare`, `next-ready`, `suggest-batches`, `prompt`, `save-enrichment`, `merge`, `inspect [--query] [--list]`, `scan-config`, `deep-scan-state` (incl. `save-run-context` for shell-friendly run-context writes) |
| `viewer.py` | Local viewer — stdlib `http.server` serving the React `dist/` + `/api/bundle` (reuses `upload.py::build_bundle`), `/api/generated-files`, `/api/folder-claude-mds`, `/api/intent-layer-status`, `/api/ignored-rules`, `POST /api/rules` (5 atomic rule actions); auto-reloads when its own source changes |
| `validate.py` | Cross-reference blueprint against actual codebase |
| `check_rules.py` | Check files against rules (CI path) |
| `measure_health.py` | Erosion, gini, verbosity, top-20%, waste scores + `--append-history` + `--compare-history` (trend deltas) |
| `code_shape.py` | Code-shape matching primitives — a `code_shape` entry on a rule, consumed by `pre-validate.sh` + `rule_index.py` |
| `detect_cycles.py` | Tarjan's SCC on the import graph |
| `install_hooks.py` | Legacy Claude-only hook installer (kept for backwards compat; modern installs route through `ClaudeConnector.install_hook` via the connector loop). Writes hooks + permissions in `.claude/settings.local.json` |
| `merge.py` | Merge blueprint sections; `extract_json_from_text` handles conversation envelopes / code fences |
| `finalize.py` | Normalise blueprint + deep-merge Opus output + id-stable findings upsert + pitfalls into blueprint |
| `verify_findings.py` | Parallel finding verifier — per finding, reads the cited `triggering_call_site` + surrounding files and returns `keep` / `demote` / `drop`. Routes the model call through `agent_cli` (Claude Haiku or Codex, auto-detected) |
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

`npx @bitraptors/archie /path/to/project` performs:

1. **Preflight** — require Node 18+; reject unknown flags and print `--help` (a past source of bogus installs was silently-swallowed typos). `--commands-dir` is accepted for legacy compatibility but ignored under multi-CLI installs.
2. **Clean install** — removes old `.py` scripts from `.archie/`, old `archie-*.md` commands, the stale `.archie/workflow/` tree, the superseded `.claude/skills/archie-deep-scan/` and `.archie/prompts/` layouts, `.claude/hooks/`, the hook section of `.claude/settings.local.json`, the old `platform_rules.json`, and a stale `.archie/_install_pkg/` if present — so re-installs are clean and upgrades are safe in-place. User data (`blueprint.json`, `findings.json`, `rules.json`, …) is preserved.
3. Create `.claude/commands/` and `.archie/` in the target project
4. Copy the standalone Python scripts to `.archie/`
5. Copy `platform_rules.json`
6. Copy the canonical hook scripts into `.archie/hooks/`
7. Copy the bundled `_install_pkg/` Python package into `.archie/_install_pkg/` (the connector-driven install loop, byte-identical to `archie/`)
8. Note: the canonical workflow templates (`assets/workflow/`) are **not** copied raw — the Python install loop renders them per-CLI into `.archie/workflow/<cli>/` (step 13)
9. Copy `.archieignore` + `.archiebulk` defaults (only if not already present — preserves user customisations)
10. Copy the React viewer source into `.archie/viewer/` and build it once (`npm ci` + `vite build`, then drop `node_modules`) — cached by a `.archie-version` marker so unchanged versions skip the ~45s build
11. Append `.gitignore` entries for installed tooling — `.archie/workflow/`, `.claude/commands/archie-*.md`, `.claude/hooks/`, `.claude/settings.local.json`, `.agents/skills/archie-*/`, `.codex/hooks.json`; idempotent across upgrades
12. **Interactive picker** (TTY only) — show a raw-mode multi-select prompt with both CLIs pre-selected. User navigates with arrow keys, toggles with space, confirms with Enter (or hits Ctrl-C to cancel cleanly). Non-TTY stdin (CI, pipe) skips the prompt and uses the same default as Enter: `all`. The `--target=<spec>` CLI flag bypasses the prompt with an explicit value (`auto` / `all` / `claude` / `claude,codex` / etc.).
13. **Delegate to the Python connector loop:** spawn `python3 -m _install_pkg.install $PROJECT_ROOT --target=<chosen>` with `ARCHIE_ASSETS_ROOT` and `ARCHIE_STANDALONE_ROOT` env vars pointing at the npm bundle. The Python loop resolves the target spec (auto = detect each CLI's home dir; all = every supported CLI; explicit = use the list), renders the canonical workflow into `.archie/workflow/<cli>/` per selected CLI, and writes per-CLI shims, hooks, and (for Codex) the `~/.codex/config.toml` patch. See [Multi-Agent Connector Architecture](#multi-agent-connector-architecture).
14. Write the machine-level version marker (`~/.archie/version`); on a version change, mark `JUST_UPGRADED` so the next slash command can acknowledge it
15. Print installation summary + next steps

The installer does **not** prompt for telemetry consent — an `npx` install can be non-interactive (CI, pipe, agent shell), so a prompt there is unreliable. Consent is asked in-session by the first slash command instead (see [Telemetry](#telemetry)).

If Python is missing, archie.mjs prints `⚠ python3 not found — Claude/Codex shims not written` and continues without writing per-CLI shims. Asset files still land in `.archie/`. Install Python 3.9+ and re-run to complete.

If the viewer build fails (no internet, old Node), the installer keeps going — scripts and assets still install; only `/archie-viewer` is affected until the user re-runs.

### Assets (`npm-package/assets/`)

Verbatim mirror of canonical Archie assets — the standalone scripts, the `workflow/` tree (the unrendered canonical workflow templates), the `viewer/` source, the `hook_scripts/`, the `.archieignore` / `.archiebulk` / `platform_rules.json` defaults, and **`_install_pkg/`** — a byte-identical copy of `archie/install.py`, `archie/manifest.py`, `archie/manifest_data.py`, and `archie/connectors/*.py` so the npm installer can spawn the connector loop without requiring `pip install archie-cli`. The templates ship unrendered; the connector loop renders them per-CLI at install time. `scripts/verify_sync.py` enforces byte-equality across all mirrors. See [File Sync Protocol](#file-sync-protocol).

---

## Multi-Agent Connector Architecture

> **🚧 Status: Codex CLI is BETA and may contain errors.** Claude Code is the stable, primary target — install + run-time both validated end-to-end. The Codex connector ships every static artifact the runtime needs (rendered workflow tree, `.codex/hooks.json`, project-scoped `archie_analysis` custom agent, `.codex/rules/archie.rules` execpolicy auto-approvals, `~/.codex/config.toml` `[agents]` + project trust marker), and the contract test suite gates static capability claims. **What is not yet exhaustively validated**: the runtime behavior of Codex's native subagent dispatch under our prompt wording (natural-language-driven, since the docs don't formalize a "spawn-by-name" tool call), `PreToolUse` hooks in `codex exec` non-interactive mode (observed not firing in Codex 0.130.0 despite project trust), and the interaction surface between sandbox modes / approval policies / hook trust gates across Codex versions. **Pin Claude Code for production scans. Treat Codex as evaluation.**

Archie ships a connector-based install loop that targets two coding-agent CLIs as peers:

- **Claude Code** (Anthropic) — original target, fully validated, detected via `~/.claude/`
- **OpenAI Codex CLI** — 🚧 BETA, may contain errors, detected via `~/.codex/`

Both run the *identical* workflow — same phases, same steps, same Python pipeline (`scanner.py`, `renderer.py`, `validate.py`, etc.) — and invoke the same canonical hook scripts under `.archie/hooks/`. The only differences are the agent-spawn mechanism and the worker model. This is achieved with a **templated canonical workflow** rendered per-CLI at install time (see [Templated workflow + install-time render](#templated-workflow--install-time-render) below).

### Two per-CLI adapters, one per lifecycle

CLI-specific knowledge is concentrated in exactly two places, split by *when* it runs:

- **Connector** (`archie/connectors/`) — the **install-time** adapter. Translates the CLI-agnostic manifest (commands, hooks, config patches) into native install artifacts, and renders the canonical workflow into the CLI's native idiom. Connectors are gone by the time a scan runs.
- **`agent_cli`** (`archie/standalone/agent_cli.py`) — the **runtime** adapter. Turns "run this prompt through the user's coding agent" into the right headless CLI call. The few pipeline scripts that need a mid-pipeline model call import from here; they cannot reach the connector layer because connectors no longer exist at scan time. See [Runtime per-CLI adapter](#runtime-per-cli-adapter-agent_clipy).

### Design principles

1. **Single source of truth** — every workflow body and hook script lives once under `archie/assets/`. Each command's workflow is authored exactly once, as a template. Connectors emit thin shims that point at the rendered workflow; updates to step logic touch zero CLI-specific files.
2. **Strict separation** — all install-time CLI-specific code lives in one file per CLI under `archie/connectors/`; all runtime CLI-specific code lives in `archie/standalone/agent_cli.py`. `archie.mjs` is target-agnostic; it copies the bundled `_install_pkg/` and spawns it.
3. **Explicit capabilities** — each connector declares its supported event surface via a `capabilities: frozenset[str]` set. Missing capabilities are honest API ceilings, not hidden gaps. The contract test suite asserts every declared capability is honored end-to-end against a tmpdir.
4. **Byte-equal mirroring** — the Python install package is bundled into `npm-package/assets/_install_pkg/` for the npm distribution. `scripts/verify_sync.py` enforces byte-equality across all connector / install / manifest files.

### Templated workflow + install-time render

There is **one canonical workflow per command**, authored once under `archie/assets/workflow/<command>/`. The template is harness-neutral — every CLI-specific word is a *slot*. The installer **renders** the template through the active connector's render map, writing fully native output into `<project>/.archie/workflow/<cli>/`. There is no runtime indirection: the running agent never sees a placeholder or a "look up the right phrasing" instruction — Claude's rendered copy literally says `Opus` / `Agent tool` / `AskUserQuestion`, Codex's literally says `gpt-5` / native Codex subagents / direct conversation prompts. The step logic is identical; only the slotted words differ.

**Why render at install time, not resolve at runtime:** a workflow that says "spawn an Opus subagent with the Agent tool" performs better than one that says "dispatch a reasoning-tier worker, see profile." Baking native vocabulary in keeps the running agent on rails.

Two kinds of slot:

- **Inline tokens** `{{ANALYSIS_MODEL}}` / `{{REASONING_MODEL}}` / `{{VERIFY_MODEL}}` / `{{WORKFLOW_ROOT}}` — single-word substitutions that drop into prose. Claude → `Sonnet` / `Opus` / `Haiku` / `.archie/workflow/claude`; Codex → `gpt-5` / `gpt-5` / `gpt-5` / `.archie/workflow/codex`.
- **Block partials** `{{>dispatch_parallel}}` / `{{>dispatch_single}}` / `{{>output_contract}}` / `{{>ask_user}}` — multi-line native paragraphs. Each partial carries only the CLI-specific *mechanism* (how to spawn N parallel workers, how a worker writes its output file, how to ask the user a question). The worker model and the task/question text stay inline in the canonical template so a partial is reusable at every dispatch site regardless of tier.

The renderer (`render_template` in `archie/install.py`) is plain string substitution — no new dependencies. It substitutes `{{>partial}}` first (partials may themselves contain `{{TOKEN}}`s, which are then resolved), then inline `{{TOKEN}}`s. **Any unresolved `{{ }}` after rendering raises `ValueError`** — a missing slot is a hard install error, never silently shipped.

### Connector interface (`archie/connectors/base.py`)

```python
class Connector(ABC):
    name: str
    capabilities: frozenset[str]   # see "Capabilities vocabulary" below
    render_tokens: dict[str, str]    # inline {{TOKEN}} values
    render_partials: dict[str, str]  # multi-line {{>partial}} bodies

    def detect(self) -> bool: ...                                   # ~/.<cli>/ exists?
    def install_command(self, project_root, cmd: CommandDef): ...   # write SKILL/shim files
    def install_hook(self, project_root, hook: HookDef): ...        # register native hook
    def patch_config(self, patches: list[ConfigPatch]): ...         # global CLI config (Codex only)
    def finalize(self, project_root): ...                           # cross-method finalization
    def supports_event(self, event) -> bool: ...                    # capability check
```

`render_tokens` and `render_partials` together form the connector's **render map** — consumed by the install loop's `_render_workflow_tree` step. A connector touches these only on a CLI API change.

Capabilities vocabulary:

| Capability string | Meaning |
|---|---|
| `commands` | Connector implements `install_command` (every connector declares this) |
| `hooks:pre-tool-use`, `hooks:post-tool-use`, `hooks:user-prompt-submit`, `hooks:stop` | Per-event hook support; the install loop calls `install_hook` only for events the connector claims |
| `hooks:pre-commit` | Git pre-commit gate — universal across all connectors |
| `parallel-agents` | CLI runtime supports parallel sub-agent fan-out (Claude via Agent tool; Codex via native subagents) |
| `config-patch` | Connector patches a global CLI config file (Codex's `~/.codex/config.toml`); Claude needs none |

### Manifest (`archie/manifest_data.py`)

Single source of truth for what Archie installs across all CLIs. Three lists, three CLI-agnostic dataclasses (`CommandDef`, `HookDef`, `ConfigPatch` — defined in `archie/manifest.py`):

| Manifest | Count | Contents |
|---|---|---|
| `COMMANDS` | 4 | archie-deep-scan, archie-intent-layer, archie-viewer, archie-share |
| `HOOKS` | 7 | pre-validate (Edit/Write), pre-commit-review (Bash), blueprint-nudge (Glob/Grep), post-plan-review (ExitPlanMode), post-lint (Edit/Write), pre-turn (UserPromptSubmit), stop (turn end) |
| `CONFIG_PATCHES` | 2 | Codex `project_doc_max_bytes = 131072`, `project_doc_fallback_filenames = ["CLAUDE.md"]` |

Each `CommandDef` carries a `body_path` — the command's `SKILL.md` *inside the rendered workflow tree*, relative to that tree's per-CLI root (e.g. `scan/SKILL.md`). Connectors prepend their own `{{WORKFLOW_ROOT}}` when writing the shim. Adding a new command or hook is one entry here plus one workflow template (or hook script) under `archie/assets/`. No connector code changes; the install loop iterates the manifest and dispatches per capability.

### Per-connector implementations

| Connector | File | Capabilities | CLI native artifacts |
|---|---|---|---|
| `ClaudeConnector` | `archie/connectors/claude.py` | commands, hooks (all 4 events), pre-commit, parallel-agents | `.claude/commands/archie-*.md` (5 shims), `.claude/hooks/*.sh` scripts, `.claude/settings.local.json` (hooks merge + `permissions.allow`) |
| `CodexConnector` | `archie/connectors/codex.py` | commands, hooks (all 4 events), pre-commit, parallel-agents, config-patch | `.agents/skills/archie-*/SKILL.md` (5 shims, parent-walked by Codex), `.codex/hooks.json` with absolute hook paths and Codex-native matchers (`^apply_patch$`, `^Bash$`, `^(Glob\|Grep)$`, `^ExitPlanMode$`), `.codex/config.toml` `[agents]` limits, `.codex/agents/archie-analysis.toml`, idempotent regex-based merge into `~/.codex/config.toml` |

Codex uses a project-scoped custom agent definition for Archie analysis workers. Claude fans out via inline Agent tool calls; Codex fans out through the native Codex subagent workflow, where the orchestrator reads full sub-agent prompts straight from the rendered workflow and asks Codex to spawn one subagent per prompt. The analytical prompts remain ordinary workflow files, not connector-emitted prompt artifacts.

### Shims and the rendered workflow

Both connectors emit a thin shim per command; the shim points at that command's rendered `SKILL.md` and says "Read this file in full and execute it":

- **Claude** — `.claude/commands/archie-<cmd>.md` → `.archie/workflow/claude/<cmd>/SKILL.md`
- **Codex** — `.agents/skills/archie-<cmd>/SKILL.md` → `.archie/workflow/codex/<cmd>/SKILL.md` (parent-walk discovered by Codex)

The two `.archie/workflow/claude/` and `.archie/workflow/codex/` trees are produced by rendering the same `archie/assets/workflow/` source through each connector's render map. They differ *only* in the slotted lines (model names, dispatch blocks, the `{{WORKFLOW_ROOT}}` prefix) — and contain no `{{ }}` and no foreign-CLI paths. They install side by side; a project may have both.

### Install loop (`archie/install.py`)

```python
def install(project_root, requested):
    selected = resolve_targets(requested)        # auto-detect / explicit list / "all"
    _clean_legacy_layout(project_root)           # drop superseded install artifacts (see below)
    _copy_canonical_assets(project_root)         # .archie/hooks/, standalone scripts, viewer, ignore defaults
    _install_git_pre_commit(project_root)        # .git/hooks/pre-commit.archie — universal

    for conn in selected:
        _render_workflow_tree(conn, project_root)  # render workflow/ -> .archie/workflow/<cli>/
        for cmd in COMMANDS:
            conn.install_command(project_root, cmd)
        for hook in HOOKS:
            if conn.supports_event(hook.event):
                conn.install_hook(project_root, hook)
        if "config-patch" in conn.capabilities:
            conn.patch_config([p for p in CONFIG_PATCHES if p.cli == conn.name])
        conn.finalize(project_root)
```

Step by step:

- **`_clean_legacy_layout`** — on upgrade from an older Archie, removes superseded install artifacts so a returning user is not left with a dead skill registration or a stale, duplicated workflow body: the `.claude/skills/archie-deep-scan/` skill tree, the `.claude/commands/archie-deep-scan/` subtree, the old `.archie/prompts/` workflow bodies, and a stale `.claude/commands/_shared/scope_resolution.md`.
- **`_copy_canonical_assets`** — copies the canonical hook scripts into `.archie/hooks/`, the standalone Python pipeline scripts into `.archie/`, the viewer source, `platform_rules.json`, and the `.archieignore` / `.archiebulk` defaults (only if not already present).
- **`_render_workflow_tree`** — runs *once per selected connector*. Walks `archie/assets/workflow/`, renders every `.md` file through the connector's render map (non-Markdown files are copied verbatim), and writes the result into `<project>/.archie/workflow/<cli>/`, preserving the source tree shape.
- Then, per connector: `install_command` writes the shims, `install_hook` registers each supported hook event, `patch_config` (Codex only) merges into `~/.codex/config.toml`, and `finalize` does cross-method work (Claude merges the `permissions.allow` array into `.claude/settings.local.json`).

Asset locations are parameterized via `ARCHIE_ASSETS_ROOT` and `ARCHIE_STANDALONE_ROOT` env vars so the same code runs from the source repo, a pip-installed wheel, or the npm-bundled `_install_pkg/`. `archie.mjs` sets both env vars before spawning `python3 -m _install_pkg.install`. From a pip install, both default to `Path(__file__).resolve().parent / "assets"` (resp. `.../standalone`).

### Runtime per-CLI adapter (`agent_cli.py`)

`archie/standalone/agent_cli.py` is the runtime counterpart of the connector. Most pipeline scripts are CLI-agnostic, but a few must spawn an AI model mid-pipeline — currently only `verify_findings.py` (the finding backward-check). Those scripts import `detect_verifier` / `run_verifier` from `agent_cli` and stay CLI-agnostic themselves; all headless-CLI invocation knowledge lives in this one module.

`detect_verifier()` decides which harness is driving the run with **no flag and no config**: a pipeline script only ever runs from inside a harness-driven scan, so the orchestrating harness *is* the signal. Claude Code exports `CLAUDECODE=1` to every process it spawns — present means the Claude verifier (`claude -p --model haiku`), absent means the Codex verifier (`codex exec --sandbox read-only`). `run_verifier()` then shells out to the chosen CLI. Like the rest of `archie/standalone/`, this shells out rather than importing a vendor SDK — preserving the zero-dependency invariant and inheriting the user's existing auth.

### Contract tests (`tests/test_connector_contract.py`, `tests/test_install_loop.py`)

The contract suite gates the framework:

- Every connector has `name`, `capabilities`, and the required ABC methods
- `install_command` produces a file artifact for every command for every connector
- `install_hook` honors each connector's declared `capabilities` (no `NotImplementedError` for claimed events)
- Every connector declares all required render tokens and partials; `{{WORKFLOW_ROOT}}` resolves to its own `.archie/workflow/<cli>` namespace
- Codex's render partials reference only runtime tools Codex actually supports
- `patch_config` is idempotent on real files (writes twice, second pass produces zero diff)
- Every `HookDef` event has at least one backing connector
- The `ALL_CONNECTORS` registry contains exactly `{claude, codex}`

Run via `python -m pytest tests/test_connector_contract.py -v` (requires `pydantic` in the test venv because `archie/__init__.py` eagerly imports the engine).

---

## Coding Agent Integration (Claude / Codex)

---

### Claude Code (stable, primary)

Slash commands at `.claude/commands/` — 4 shim files written by `ClaudeConnector.install_command`. Each shim is one line: "Read `.archie/workflow/claude/<cmd>/SKILL.md` in full and execute it."

| Command | Shim → rendered body | Purpose |
|---------|----------------------|---------|
| `/archie-deep-scan` | `archie-deep-scan.md` → `workflow/claude/deep-scan/SKILL.md` | Full 2-wave analysis. `SKILL.md` is a router into the per-step tree. Supports `--incremental`, `--continue`, `--from N`, `--reconfigure`. Intent Layer is opt-in via Step E. Step 7 delegates to `/archie-intent-layer` Phases 1–4 as a single source of truth |
| `/archie-intent-layer` | `archie-intent-layer.md` → `workflow/claude/intent-layer/SKILL.md` | Standalone per-folder CLAUDE.md regen. Phase 0.5 asks Full/Incremental/Auto; Auto uses `deep-scan-state detect-changes` against `last_deep_scan.json`. Hard-requires `blueprint.json` |
| `/archie-share` | `archie-share.md` → `workflow/claude/share/SKILL.md` | Upload bundle to hosted viewer via `upload.py` + return URL |
| `/archie-viewer` | `archie-viewer.md` → `workflow/claude/viewer/SKILL.md` | Launches `viewer.py` — the local React sidecar at `localhost:5847/local` |

All choice prompts in scan/deep-scan use the `{{>ask_user}}` partial, which renders to `AskUserQuestion` for Claude (monorepo scope picker, parallel/sequential, Intent Layer opt-in) — no free-text answers to parse. The scope (Step C) and Intent Layer (Step E) prompts are **mandatory decision gates**: the workflow instructs the agent to ask them even under a "no clarifying questions" harness mode, since they change which trees get scanned and what files get written.

The rendered deep-scan tree (`.archie/workflow/claude/deep-scan/`) is the pipeline itself: `SKILL.md` is the orchestrator/router; `steps/` holds one file per pipeline step (Step 3 fans out into `step-3-wave1/` with a prompt file per Wave 1 agent); `fragments/` holds the cross-step telemetry and `/compact`-resume contracts; `templates/` holds the scan-report template. The dispatch partials render to Agent tool calls — Wave-1 fans out by emitting all Agent tool calls in a single message.

`ClaudeConnector.finalize` writes hook event registrations + the `permissions.allow` array into `.claude/settings.local.json` so `python3 .archie/*.py`, `Agent(*)`, `Read(.archie/**)`, `Write(**/CLAUDE.md)` and the rest of the workflow runs prompt-free.

### Codex CLI (🚧 BETA — may contain errors)

Skills at `.agents/skills/archie-*/SKILL.md` — 5 shims written by `CodexConnector.install_command`. Codex discovers them via parent-walk from cwd. Each shim points at the rendered Codex body at `.archie/workflow/codex/<cmd>/SKILL.md` — produced by rendering the same canonical templates through the Codex render map, so it is byte-for-byte the same step logic as the Claude tree, differing only in the slotted lines.

`.codex/hooks.json` is generated by `CodexConnector.install_hook` with absolute paths to `.archie/hooks/*.sh` and Codex-native matchers (`^apply_patch$`, `^Bash$`, `^(Glob|Grep)$`, `^ExitPlanMode$`). Codex's `PreToolUse` hook fires on `apply_patch` (its native tool name for file edits) — equivalent to Claude's `Write|Edit|MultiEdit` matcher.

Codex's deep-scan Wave-1 parallel fan-out renders the `{{>dispatch_parallel}}` partial: the workflow asks Codex (in natural-language prose, since the docs don't formalize a "spawn-by-name" tool call) to spawn one native subagent per Wave-1 task using the project-scoped `archie_analysis` custom agent (or built-in `worker` as fallback). Same shape for `{{>dispatch_workspace_parallel}}` (monorepo per-package / hybrid). Codex waits for all subagents and returns a consolidated response per its documented model.

`CodexConnector.finalize` writes 4 coordinated artifacts:
1. `<project>/.codex/agents/archie-analysis.toml` — project-scoped custom subagent (`name = "archie_analysis"`, `sandbox_mode = "workspace-write"`, plus `developer_instructions` keeping the worker focused on its assigned task and writing to its declared output path).
2. `<project>/.codex/rules/archie.rules` — Starlark execpolicy file with **53 `prefix_rule(decision="allow", …)`** entries (31 per `_STANDALONE_SCRIPTS` script + 22 catalogue entries from `manifest_data.py::COMMAND_RULES` covering shell utilities, read-only git, `python3 -c`, and `codex exec` for the Step-9 verifier subprocess). Validated locally with `codex execpolicy check`.
3. `~/.codex/config.toml [agents] max_threads = 6, max_depth = 2` (set-if-absent via `CodexConnector.patch_config` + the section-aware `_toml_set_section_key`). Depth 2 supports the root → workspace worker → Wave-1 worker call chain on monorepo deep-scans.
4. `~/.codex/config.toml [projects."<abs-path>"] trust_level = "trusted"` (set-if-absent). **This is the gate that lets the project-scoped `.codex/` layer load at all** — per Codex docs: "Untrusted projects skip project-scoped `.codex/` layers, including project-local config, hooks, and rules." Installing Archie *is* the trust act; a manual `"untrusted"` choice is respected.

`CodexConnector.patch_config` also writes the top-level `project_doc_max_bytes = 131072` (raising the 32 KiB default that real Archie output already exceeded) and unions `project_doc_fallback_filenames` with `["CLAUDE.md"]` so per-folder context files are picked up. Non-destructive — preserves all existing keys and sections.

The Step-9 finding backward-check (`verify_findings.py`) runs under Codex with no extra wiring: `agent_cli.detect_verifier()` sees that `CLAUDECODE` is unset and routes to `codex exec` automatically (see [Runtime per-CLI adapter](#runtime-per-cli-adapter-agent_clipy)). The catalogue's `codex-exec` rule pre-approves the `codex exec ...` subprocess so Step 9 runs prompt-free.

All disk artifacts (`.archie/tmp/archie_*.json`) are workspace-relative so the default `workspace-write` sandbox covers writes natively — no `[sandbox_workspace_write] writable_roots` widening needed.

**Known BETA caveats and unvalidated edges:**
- **Natural-language subagent invocation** — the Codex docs ([developers.openai.com/codex/subagents](https://developers.openai.com/codex/subagents)) show example prompts like "Spawn one agent per point" but do not formally specify a tool-call shape for "spawn the `archie_analysis` custom agent for each task." Our rendered prose follows the documented natural-language style; runtime behavior under different Codex versions has only been validated for representative test cases.
- **`PreToolUse` hooks in `codex exec` non-interactive mode** (validated against Codex 0.130.0) were observed not firing on `.codex/hooks.json` despite the project being trusted. Interactive mode displays "1 hook needs review before it can run" — the hook is discovered but gated by Codex's own `/hooks` review flow. Interactive sessions with hook approval work end-to-end; `codex exec` headless invocations remain an open item.
- **`max_depth = 2`** is set unconditionally at install (set-if-absent — respects user customisation). Most users will be single-project (depth 1 suffices for Wave 1 fan-out); monorepo users need depth 2. We pay the speculative cost for all users because install-time can't predict scope.
- **Recursive subagent nesting limits and approval-policy / sandbox-mode / trust-marker interactions** across Codex versions have not been exhaustively mapped — the runtime test is the validator.

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
  |     - semantic_duplications (legacy)   |                                   |
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
  "semantic_duplications": [...],        # legacy, from semantic_duplications.json when present
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
Step 8  Cleanup .archie/tmp/archie_*
Step 9  Finalize
        measure_health.py -> health.json + health_history.json
        complete-step + save-baseline (incremental change detection)
        Telemetry write to .archie/telemetry/deep-scan_<ts>.json
```

### Incremental deep scan (`--incremental`)

```
Step 1  Scanner (same)
Step 2  Read accumulated knowledge + detect changed files
Step 3' One scoped Reasoning agent (Sonnet)
        Input: blueprint, blueprint_raw, findings, changed files
        Output: ONLY the sections that need updating
Step 4  finalize.py --patch .archie/tmp/archie_sub_x_*.json
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

## Drift Coverage (no dedicated drift step)

The standalone drift step was retired: its findings duplicated the Wave 2 Risk pipeline without the verifier/hysteresis guarantees, and its run time scaled with recent churn. The problem classes it covered now live in verified channels:

| Class | Where it's caught now |
|----------|----------------|
| `decision_violation` | Risk agent's invariant walk (Step 5b) + `pre-validate.sh` blocks at edit time |
| `pattern_erosion` | Incremental recency sweep (Risk agent reads changed files against per-folder CLAUDE.md) |
| `trade_off_undermined` | Risk agent reads `trade_offs.violation_signals`; hooks warn via `tradeoff_undermined` |
| `pitfall_triggered` | Risk agent pitfall pass + hooks block via `pitfall_triggered` |
| `responsibility_leak` / `abstraction_bypass` | Risk agent's whole-system pass (cross-component coupling, decision-chain constraints) |
| schema drift | Risk agent's data-shaped pitfall classes (`data_models` + `persistence_stores`) |

Everything user-facing flows through `findings.json` — `triggering_call_site` required, backward-verified, hysteresis-stabilised.

---

## Cycle Detection

Every scan runs Tarjan's strongly connected components algorithm (`detect_cycles.py`) on the import graph. Output includes each cycle with the participating directories, file-level evidence showing which imports create the cycle, and dependency magnets (high-in-degree nodes). Results stored in `.archie/dependency_graph.json`.

---

## Telemetry

There are two distinct telemetry surfaces. **Per-run step timing** is always-on and stays local. **Anonymous usage telemetry** is opt-in and, when enabled, uploads a minimal payload to BitRaptors' Supabase.

### Per-run step timing (always-on, local)

Every `/archie-deep-scan` run writes a per-step wall-clock timing file:

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
    {"name": "finalize",        "seconds": 18}
  ]
}
```

Used to measure the wall-clock impact of prompt/code changes over time. Individual steps can set `skipped: true` (e.g. Intent Layer when opted out, or earlier steps skipped via `--from N`) with both timestamps identical. This file never leaves the project.

### Anonymous usage telemetry + update checks (opt-in)

Consent is asked **once per machine**, in-session, by the first Archie slash command the user runs — not by the `npx` installer. Every entry point (`/archie-deep-scan`, `/archie-viewer`, `/archie-share`, `/archie-intent-layer`) loads the shared `_shared/telemetry-consent.md` fragment in its preamble; the fragment runs `config.py should-prompt` and, if this machine hasn't answered, presents an `AskUserQuestion` opt-in. This deliberately lives in the slash commands — which always run inside Claude Code, where a picker is available — instead of the `npx` install, which can be non-interactive (CI, pipe, agent shell). Consent, update-check preferences, and a stable random installation id live in machine-level `~/.archie/config.json` (managed by `config.py`) — not per-project. Three tiers:

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

54 test files. Tests mirror the package structure:

- **Engine** — scanner (+ monorepo variant), dependencies, frameworks, hasher, imports, scan (+ scan_config), engine_models
- **Coordinator** — planner, runner, merger, prompts
- **Hooks** — hook_generator, hook_enforcement
- **Rules** — rule_extractor (legacy), rule_shape, rule_index, code_shape, align_check, migrate_blueprint_rules
- **Renderer** — renderer (+ field_coverage, merge), intent_layer (+ bulk_filter, inject_scoped, resume, run_context, suggest_batches), normalize, inspect
- **Findings / scan pipeline** — finalize_findings_merge, verify_findings, apply_verdicts
- **Deep-scan workflow** — deep_scan_state_shell_api
- **CLI** — init, refresh, status, serve, check
- **E2E** — refresh_e2e
- **Standalone helpers** — ignore_patterns, health_append, telemetry, upload, share_setup, lint_gate, viewer
- **Multi-agent connector framework** — `test_connector_contract.py` asserts every connector's declared capabilities work end-to-end against a tmpdir (install_command produces a file, install_hook honors per-event claims, every connector declares all required render tokens and partials, `{{WORKFLOW_ROOT}}` is namespaced to the connector, Codex partials reference only supported runtime tools, patch_config is idempotent on a real `~/.codex/config.toml`, every `HookDef` event has at least one backing connector, the `ALL_CONNECTORS` registry is exactly `{claude, codex}`). `test_install_loop.py` asserts `install(tmp_path, ["claude"])` produces a `.claude/settings.local.json` whose Edit/Write matcher is present and whose `permissions.allow` is populated — the **regression gate for "Claude on the feature branch behaves identically to Claude on `main`."**

Tests use fixtures (temp directories with known file structures), subprocess mocking for runner/agent tests, and Pydantic model validation for schema compliance.

---

## File Sync Protocol

Standalone scripts, the canonical workflow tree, the install package, and the viewer source all exist in two places (canonical → copy):

```
archie/standalone/*.py                 ->  npm-package/assets/*.py
archie/standalone/platform_rules.json  ->  npm-package/assets/platform_rules.json
archie/assets/workflow/**              ->  npm-package/assets/workflow/**
archie/assets/hook_scripts/**          ->  npm-package/assets/hook_scripts/**
archie/install.py, manifest*.py,       ->  npm-package/assets/_install_pkg/**
  connectors/*.py
share/viewer/  (source, minus build)   ->  npm-package/assets/viewer/
```

`archiebulk.default` and `archieignore.default` live only in `npm-package/assets/` (installer-only resources).

**Workflow:**

1. Always edit the canonical file first (`archie/standalone/`, `archie/assets/workflow/`, `archie/connectors/`, or `share/viewer/`)
2. Copy to `npm-package/assets/`
3. Before committing, run the sync checker:

```bash
python3 scripts/verify_sync.py
```

This verifies all canonical files, asset copies, and `archie.mjs` references are consistent. It catches missing copies, orphan assets, and dead installer references, then reports:

```
SYNC CHECK PASSED — 31 scripts, workflow + assets all in sync.
```

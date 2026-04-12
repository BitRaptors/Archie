# Archie v2 — Technical Architecture

Comprehensive technical documentation covering system architecture, analysis pipeline, data models, enforcement hooks, and development.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Layered Architecture](#layered-architecture)
5. [Engine — Local Analysis](#engine--local-analysis)
6. [Coordinator — AI Pipeline](#coordinator--ai-pipeline)
7. [Hooks — Real-Time Enforcement](#hooks--real-time-enforcement)
8. [Rules — Extraction and Management](#rules--extraction-and-management)
9. [Renderer — Output Generation](#renderer--output-generation)
10. [Standalone Scripts](#standalone-scripts)
11. [NPM Package — Distribution](#npm-package--distribution)
12. [Claude Code Integration](#claude-code-integration)
13. [StructuredBlueprint Data Model](#structuredblueprint-data-model)
14. [Data Flow](#data-flow)
15. [Compound Learning](#compound-learning)
16. [Drift Detection](#drift-detection)
17. [Cycle Detection](#cycle-detection)
18. [Error Handling and Resilience](#error-handling-and-resilience)
19. [Testing](#testing)
20. [File Sync Protocol](#file-sync-protocol)

---

## System Overview

Archie v2 is a standalone CLI tool and NPM package. No backend server, no database, no web UI required for core operation.

The core workflow:

1. **Scan** — Deterministic local analysis of the repository (file tree, imports, frameworks, hashing, token counting). Pure Python, no AI.
2. **Plan** — Group scanned files into token-budgeted subagent assignments using bin-packing.
3. **Analyze** — Spawn Claude Code subagents (Sonnet) to gather architectural facts.
4. **Reason** — A reasoning agent (Opus) reads all fact-gathering output and produces deep architectural analysis: decision chains, trade-offs, pitfalls.
5. **Merge** — Combine partial blueprints from all subagents into a single `StructuredBlueprint`.
6. **Render** — Deterministic JSON-to-Markdown generation of CLAUDE.md, AGENTS.md, per-folder context, rule files.
7. **Enforce** — Install Claude Code hooks that validate every file write against extracted rules.

Archie has two user-facing modes:

- **`/archie-scan`** — Architecture health check (1-3 min). Runs deterministic scanner for data gathering, then AI acts as a senior architect: analyzes dependencies, finds pattern drift, identifies complexity hotspots, proposes enforceable rules. Each scan builds on prior knowledge — blueprint confidence grows with repeated confirmation. Single AI session, no subagent spawning.
- **`/archie-deep-scan`** — Comprehensive baseline (15-20 min). Full 2-wave multi-agent analysis (3-4 Sonnet agents + Opus reasoning). Produces complete blueprint and all outputs. Supports `--incremental` (changed files only, 3-6 min), `--continue` (resume interrupted run), and `--from N` (resume from step N). Auto-detects monorepos and offers parallel sub-project analysis.

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.9+ (standalone scripts) | Type hints, dataclasses, pathlib |
| AI agents | Claude Code CLI (`claude -p`) | Subagent execution via subprocess |
| NPM installer | Node.js 18+ | `npx @bitraptors/archie` distribution |
| Testing | pytest | 22 test files, 2700+ LOC |
| Linting | Ruff | Python linting and formatting |

### Dependency philosophy

Standalone scripts (copied to target projects via `npx @bitraptors/archie`) have **zero pip dependencies** — Python 3.9+ stdlib only.

---

## Project Structure

```
archie/
  __init__.py
  cli/                          # Click CLI commands
    main.py                     # CLI group: init, refresh, status, rules, promote, demote, serve, check
    init_command.py             # Full pipeline: scan -> plan -> prompts -> hooks -> run -> merge -> render -> rules
    refresh_command.py          # Rescan and detect changes since last blueprint
    status_command.py           # Blueprint freshness, rule stats, health metrics
    serve_command.py            # FastAPI viewer server
    check_command.py            # CI validation: check files against rules
  engine/                       # Local codebase analysis (no AI)
    models.py                   # Pydantic: FileEntry, DependencyEntry, FrameworkSignal, RawScan
    scan.py                     # Orchestrator: runs all analysis steps -> RawScan
    scanner.py                  # Walk directory tree, skip ignored dirs/files
    dependencies.py             # Parse requirements.txt, package.json, go.mod, Cargo.toml, pyproject.toml
    frameworks.py               # Detect React, FastAPI, Django, etc. with confidence scores
    hasher.py                   # SHA256 file hashes + tiktoken token counting
    imports.py                  # Build import graph from source code
  coordinator/                  # AI pipeline
    planner.py                  # Group files into token-budgeted SubagentAssignments
    prompts.py                  # Build markdown prompts for subagents and coordinator
    runner.py                   # Spawn `claude -p` subprocesses, parse JSON responses
    merger.py                   # Deep merge partial blueprints into single StructuredBlueprint
  hooks/                        # Claude Code hook generation
    generator.py                # Generate inject-context.sh and pre-validate.sh; install hooks + git hook
    enforcement.py              # Validate files against rules (Python API: check_pre_validate)
  rules/                        # Rule extraction and management
    extractor.py                # Extract file_placement + naming rules from blueprint -> rules.json
  renderer/                     # Output generation
    render.py                   # Adapter: calls standalone renderer + intent layer
    intent_layer.py             # Generate per-folder CLAUDE.md with local patterns
  schema/                       # Schema definitions (placeholder)
  standalone/                   # Zero-dependency scripts (exported to target projects)
    scanner.py                  # File tree, import graph, framework detection, skeleton extraction
    renderer.py                 # Generate CLAUDE.md, AGENTS.md, rule files from blueprint
    intent_layer.py             # Per-folder CLAUDE.md via DAG scheduling + AI enrichment
    viewer.py                   # Interactive CLI blueprint inspector
    drift.py                    # Detect architectural drift since last scan
    validate.py                 # Cross-reference blueprint against actual codebase
    check_rules.py              # Check files against rules (for CI pipelines)
    measure_health.py           # Calculate erosion, gini, verbosity, top-20%, waste scores
    detect_cycles.py            # Find cycles in the import graph
    install_hooks.py            # Install Claude Code hooks + permissions + register in settings.local.json
    merge.py                    # Merge blueprint sections from multiple sources
    arch_review.py              # Architectural review checklist for plans and diffs
    refresh.py                  # File change detection (hash comparison)
    extract_output.py           # Extract specific sections from blueprint
    finalize.py                 # Post-processing (clean up, normalize)
    _common.py                  # Shared utilities (JSON loading, error handling)

npm-package/
  bin/archie.mjs                # npx @bitraptors/archie entry point
  assets/                       # Copies of standalone scripts + slash commands + platform_rules.json
  package.json

tests/                          # 22 test files, 2740 LOC
  test_scanner.py               # Engine: file tree scanning
  test_dependencies.py          # Engine: manifest parsing
  test_frameworks.py            # Engine: framework detection
  test_hasher.py                # Engine: hashing and token counting
  test_imports.py               # Engine: import graph
  test_scan.py                  # Engine: full scan orchestration
  test_engine_models.py         # Engine: Pydantic model validation
  test_planner.py               # Coordinator: token budget grouping
  test_runner.py                # Coordinator: subprocess management
  test_merger.py                # Coordinator: blueprint merging
  test_prompts.py               # Coordinator: prompt generation
  test_hook_generator.py        # Hooks: script generation
  test_hook_enforcement.py      # Hooks: rule validation
  test_rule_extractor.py        # Rules: extraction from blueprint
  test_renderer.py              # Renderer: output generation
  test_intent_layer.py          # Renderer: per-folder context
  test_init_command.py          # CLI: init pipeline
  test_refresh_command.py       # CLI: refresh
  test_status_command.py        # CLI: status
  test_serve_command.py         # CLI: serve
  test_check_command.py         # CLI: check
  test_refresh_e2e.py           # E2E: full refresh workflow
  test_ignore_patterns.py       # IgnoreMatcher: .archieignore + .gitignore merge
  test_health_append.py         # measure_health.py --append-history
  test_normalize.py             # finalize.py --normalize-only
  test_inspect.py               # intent_layer.py inspect subcommand

.claude/
  commands/                     # Slash commands for Claude Code
    archie-scan.md              # Architecture health check (1-3 min)
    archie-deep-scan.md         # Full 2-wave analysis (15-20 min)
    archie-viewer.md            # Blueprint inspector
  skills/                       # Developer assistance skills
    check-architecture.md       # Validate changes against architecture
    check-naming.md             # Verify naming conventions
    how-to-implement.md         # Feature implementation guide
    where-to-put.md             # File placement assistant
    sync-architecture.md        # Update architecture after changes

.github/
  workflows/
    archie-check.yml            # CI workflow for architecture validation

scripts/
  verify_sync.py                # Pre-commit: verify canonical -> copy file sync

pyproject.toml                  # Package metadata, dependencies, entry points
CLAUDE.md                       # AI agent instructions for this repository
README.md                       # User-facing documentation
```

---

## Layered Architecture

```
User
  |
  v
CLI Commands (init, refresh, status, check, serve, rules, promote, demote)
  |
  v
Coordinator (planner, runner, merger, prompts)    <-- only used by init/deep-scan
  |
  v
Engine (scanner, dependencies, frameworks, hasher, imports)
  |
  v
File System + Claude Code CLI (subprocess)
```

Dependencies point downward. The engine knows nothing about the coordinator. The coordinator knows nothing about the CLI. The hooks and renderer are siblings that consume the engine's output.

**Separation of concerns:**

- **Engine** — Stateless local analysis. No AI, no file writing. Input: repo path. Output: `RawScan`.
- **Coordinator** — AI orchestration. Spawns subagent processes, builds prompts, merges outputs. Input: `RawScan`. Output: `StructuredBlueprint` dict.
- **Hooks** — Real-time Claude Code integration. Generates shell scripts, registers in settings.local.json. Input: `rules.json`. Output: shell scripts + settings.
- **Renderer** — Deterministic file generation. Input: `StructuredBlueprint`. Output: CLAUDE.md, AGENTS.md, per-folder context, rule files.
- **Rules** — Extraction and severity management. Input: `StructuredBlueprint`. Output: `rules.json`.
- **Standalone** — Self-contained copies of the above for export to target projects. Zero dependencies.

---

## Engine — Local Analysis

The engine runs analysis steps in sequence and produces a `RawScan` (defined in `archie/engine/models.py`):

```python
class FileEntry(BaseModel):
    path: str
    size: int = 0
    last_modified: float = 0.0
    extension: str = ""

class DependencyEntry(BaseModel):
    name: str
    version: str = ""
    source: str = ""

class FrameworkSignal(BaseModel):
    name: str
    version: str = ""
    confidence: float = 1.0
    evidence: list[str] = Field(default_factory=list)

class RawScan(BaseModel):
    file_tree: list[FileEntry]               # All source files
    token_counts: dict[str, int]             # tiktoken cl100k_base count per file
    dependencies: list[DependencyEntry]      # Parsed from manifests
    framework_signals: list[FrameworkSignal]  # Detected frameworks with confidence + evidence
    config_patterns: dict[str, str]          # First 500 chars of config files
    import_graph: dict[str, list[str]]       # Source file -> imported modules
    directory_structure: dict[str, list[str]] # Directory -> filenames
    file_hashes: dict[str, str]              # SHA256 per file (for change detection)
    entry_points: list[str]                  # Files named main.py, app.py, index.ts, etc.
```

### Analysis steps (`engine/scan.py`)

| Step | Module | What it does |
|------|--------|-------------|
| 1 | `scanner.py` | Walk directory tree using `IgnoreMatcher` (`.archieignore` + `.gitignore` patterns, with `SKIP_DIRS` fallback). Skips vendored, cache, build, and binary files |
| 2 | `dependencies.py` | Parse `requirements.txt`, `package.json`, `go.mod`, `Cargo.toml`, `pyproject.toml` |
| 3 | `frameworks.py` | Match dependencies against known frameworks (React, FastAPI, Django, Express, etc.) with confidence scores and evidence |
| 4 | `hasher.py` | SHA256 hash of every source file |
| 5 | `hasher.py` | Token count (tiktoken cl100k_base) of every source file |
| 6 | `imports.py` | Parse import statements (Python, JS/TS, Go, Rust) to build a directed import graph |
| 7 | `scan.py` | Detect entry points by filename pattern (main.py, app.ts, server.js, etc.) |
| 8 | `scan.py` | Read first 500 chars of config files (Dockerfile, docker-compose, CI configs, pyproject.toml) |
| 9 | `scan.py` | Build directory-to-filenames mapping |
| 10 | `scan.py` | Assemble all into `RawScan` |
| 11 | `scan.py` | Optionally persist to `.archie/scan.json` (when `save=True`) |

---

## Coordinator — AI Pipeline

### Planner (`coordinator/planner.py`)

Groups files into token-budgeted subagent assignments:

- **Token budget:** 150,000 tokens per group (configurable)
- **Grouping strategy:** Files grouped by top-level directory, bin-packed largest-first
- **Section assignment:** Every group receives all 12 blueprint sections (merger combines later)

```python
@dataclass
class SubagentAssignment:
    files: list[str]          # File paths for this subagent
    token_total: int          # Total tokens in group
    sections: list[str]       # All 12 sections (architecture_rules, decisions, components, ...)
    module_hint: str          # Top-level dirs (for logging)
```

The 12 sections each subagent analyzes: `architecture_rules`, `decisions`, `components`, `communication`, `quick_reference`, `technology`, `frontend`, `developer_recipes`, `pitfalls`, `implementation_guidelines`, `development_rules`, `deployment`.

If the entire repo fits within the token budget, a single subagent handles everything. Otherwise, modules are bin-packed into groups.

### Prompts (`coordinator/prompts.py`)

Builds structured markdown prompts:

- **Subagent prompt** (`build_subagent_prompt`) — Includes RawScan context (file tree, imports, frameworks, entry points, config patterns) and the JSON schema for `StructuredBlueprint`. Instructs the agent to read source files and fill each section.
- **Coordinator prompt** (`build_coordinator_prompt`) — Takes all subagent blueprints as input. Instructs Opus to synthesize, resolve conflicts, and produce the final merged blueprint.

### Runner (`coordinator/runner.py`)

Spawns Claude Code CLI subprocesses:

```bash
claude -p --model sonnet --output-format json --permission-mode bypassPermissions \
    --allowedTools Read,Grep,Glob,WebSearch,WebFetch
```

- Prompt sent via stdin
- Timeout: 600 seconds per subagent
- Response: JSON envelope with `result` field containing the blueprint
- JSON extraction: tries direct parse, then ```json code block extraction, then brace-matching fallback
- Failed subagents are skipped gracefully; remaining agents continue

### Merger (`coordinator/merger.py`)

Combines N partial blueprints into one:

| Field type | Strategy |
|-----------|----------|
| Dicts (`meta`, `architecture_rules`, `decisions`, `components`, `communication`, `quick_reference`, `technology`, `frontend`, `deployment`) | Deep merge: nested dicts merged recursively |
| Lists (`developer_recipes`, `pitfalls`, `implementation_guidelines`, `development_rules`) | Concatenate and deduplicate by key field (`task`, `area`, `capability`, `rule`) |
| Strings (`architecture_diagram`) | Prefer non-empty |

Post-merge enrichment fills `meta.platforms` from framework signals, generates `quick_reference.where_to_put_code` from file placement rules, and timestamps with `analyzed_at`.

---

## Hooks — Real-Time Enforcement

### Hooks (`standalone/install_hooks.py`)

The installer (`npx @bitraptors/archie`) generates four hooks:

**`pre-validate.sh`** (PreToolUse, matcher: `Write|Edit|MultiEdit`)
- Checks `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`, and `file_naming` rules
- Reads the content being written for deeper validation (not just file path)
- Loads both `rules.json` and `platform_rules.json`

**`pre-commit-review.sh`** (PreToolUse, matcher: `Bash`)
- Internally filters to only fire on `git commit` commands
- Triggers an architectural review of the staged diff via `arch_review.py`

**`post-plan-review.sh`** (PostToolUse, matcher: `ExitPlanMode`)
- Triggers an architectural review of the plan via `arch_review.py`

**`blueprint-nudge.sh`** (PreToolUse, matcher: `Glob|Grep`)
- Always-on architectural reminder (inspired by Graphify's pattern)
- Fires before code exploration to remind the agent about project architecture
- Prints architecture style, component names, and suggests reading the blueprint

Hooks are registered in `.claude/settings.local.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [{"type": "command", "command": ".claude/hooks/pre-validate.sh"}]
      },
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": ".claude/hooks/pre-commit-review.sh"}]
      },
      {
        "matcher": "Glob|Grep",
        "hooks": [{"type": "command", "command": ".claude/hooks/blueprint-nudge.sh"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "ExitPlanMode",
        "hooks": [{"type": "command", "command": ".claude/hooks/post-plan-review.sh"}]
      }
    ]
  }
}
```

The standalone installer also sets up **permissions** in `settings.local.json` — an `allow` list covering archie script execution, git commands, temp files, reading/writing `.archie/` data, per-folder CLAUDE.md, and subagent spawning.

---

## Rules — Extraction and Management

### Blueprint rule extraction (`rules/extractor.py`)

Deterministically extracts rules from the StructuredBlueprint. Three sources:

1. `architecture_rules.file_placement_rules` -> `check=file_placement` (id: `placement-N`)
2. `architecture_rules.naming_conventions` -> `check=naming` (id: `naming-N`)
3. `components.components` -> `check=file_placement` for layer boundaries (id: `layer-N`)

Each extracted rule has:

```python
{
    "id": "placement-1",        # Unique identifier
    "check": "file_placement",  # Rule type
    "severity": "warn",         # "warn" (advisory) or "error" (blocking)
    "description": "...",       # Human-readable description
    "keywords": ["api", "route"],  # Extracted from description (3+ chars, no stopwords)
    "allowed_dirs": ["src/api/"],   # Type-specific fields
}
```

### AI-proposed rules (`/archie-scan`)

The scan AI proposes architectural rules with rationale, using additional check types:

| Check type | What it validates |
|-----------|------------------|
| `forbidden_import` | Blocks specific import patterns in specific directories |
| `required_pattern` | Requires certain content in files matching a glob |
| `forbidden_content` | Blocks specific content patterns in files |
| `architectural_constraint` | Blocks content patterns in files matching a glob |
| `file_naming` | Enforces filename patterns in specific directories |

AI-proposed rules include a `rationale` field explaining the architectural reasoning. Rules can be adopted, skipped, or managed from `/archie-viewer` (Rules tab) or interactively by Claude Code during scans.

### Platform rules (`platform_rules.json`)

Pre-built architectural checks (40+ rules) installed with every project via `npx @bitraptors/archie`. Coverage includes:
- **Universal** — God-functions, growing complexity, monster files, empty catches, disabled tests, TODO/HACK markers, hardcoded secrets, debug breakpoints
- **Android** — Layer violations (ViewModel/Context, Fragment/network), lifecycle (GlobalScope.launch), DI anti-patterns (service locator)
- **Swift** — Force unwraps, force try, view-layer network access
- **TypeScript** — Components fetching data, `any` type, React DOM manipulation, array index keys
- **Python** — Bare except, eval/exec, mutable defaults, star imports, TYPE_CHECKING guards

### Severity management

Rule severity can be changed from `/archie-viewer` (Rules tab) or by Claude Code during scans. Rules are stored in `.archie/rules.json` as `{"rules": [...]}`.

---

## Renderer — Output Generation

### Main renderer (`renderer/render.py`)

Adapter that calls the standalone renderer and intent layer:

1. `standalone/renderer.py` — Deterministic JSON-to-Markdown for root files:
   - `CLAUDE.md` — Root architecture context
   - `AGENTS.md` — Multi-agent guidance with decision chains
   - `.claude/rules/*.md` — Topic-split rule files (architecture, patterns, guidelines, pitfalls, dev-rules)

2. `renderer/intent_layer.py` — Per-folder CLAUDE.md generation:
   - Bottom-up DAG scheduling (leaf folders first, then parents)
   - Each folder gets context about its role, patterns, anti-patterns, key files
   - AI-enriched with code examples and common tasks

### Standalone renderer (`standalone/renderer.py`)

The standalone version (953 LOC) handles the full rendering pipeline and can run independently with just a `blueprint.json` file:

```bash
python3 archie/standalone/renderer.py /path/to/project
```

---

## Standalone Scripts

The `archie/standalone/` directory contains self-contained Python scripts (8500+ LOC total) that run without importing from the main archie package. These are exported to target projects via `npx @bitraptors/archie`.

| Script | LOC | Purpose |
|--------|-----|---------|
| `scanner.py` | 851 | File tree, import graph, framework detection, skeleton extraction |
| `renderer.py` | 953 | Blueprint JSON to CLAUDE.md, AGENTS.md, rule files |
| `intent_layer.py` | 1310 | Per-folder CLAUDE.md via DAG scheduling + AI enrichment. `inspect` subcommand for JSON file inspection |
| `viewer.py` | 1470 | Interactive CLI blueprint inspector |
| `drift.py` | 708 | Detect architectural drift since last scan |
| `validate.py` | 524 | Cross-reference blueprint against actual codebase |
| `check_rules.py` | 509 | Check files against rules (for CI pipelines) |
| `measure_health.py` | 480 | Calculate erosion, gini, verbosity, top-20%, waste scores. `--append-history` flag for health history management |
| `detect_cycles.py` | 383 | Find cycles in the import graph |
| `merge.py` | 301 | Merge blueprint sections from multiple sources |
| `install_hooks.py` | 283 | Install Claude Code hooks + permissions + register in settings.local.json |
| `arch_review.py` | 263 | Architectural review checklist for plans and diffs |
| `refresh.py` | 196 | File change detection (hash comparison) |
| `extract_output.py` | 164 | Extract specific sections from blueprint |
| `finalize.py` | 160 | Post-processing (clean up, `--normalize-only` for canonical schema enforcement) |
| `_common.py` | 320 | Shared utilities (JSON loading, error handling, `IgnoreMatcher` for `.archieignore`+`.gitignore`, `normalize_blueprint()`) |

---

## NPM Package — Distribution

### Installer (`npm-package/bin/archie.mjs`)

`npx @bitraptors/archie /path/to/project [--commands-dir dir]` performs:

1. Clean previous install — removes old `.py` scripts from `.archie/`, old slash commands from commands dir, old hooks from `.claude/hooks/`, and hook config from `.claude/settings.local.json`
2. Create commands directory (default `.claude/commands/`) and `.archie/` directories in the target project
3. Copy 3 slash commands (archie-scan.md, archie-deep-scan.md, archie-viewer.md) to commands dir
4. Copy 16 standalone Python scripts to `.archie/`
5. Copy `platform_rules.json` (predefined architectural checks)
6. Deliver `.archieignore` with default ignore patterns (only if not already present — preserves user customizations)
7. Append `.gitignore` entries for installed tooling (scripts, commands, hooks, platform_rules, settings — idempotent, handles upgrade from older versions)
8. Run `python3 install_hooks.py` to set up 4 hooks + 27 permissions in `.claude/settings.local.json`
9. Print installation summary

### Assets (`npm-package/assets/`)

Exact copies of canonical files. See [File Sync Protocol](#file-sync-protocol) for the sync workflow.

---

## Claude Code Integration

### Slash commands (`.claude/commands/`)

| Command | File | Purpose |
|---------|------|---------|
| `/archie-scan` | `archie-scan.md` | Architecture health check: deterministic data gathering (scanner, health metrics), then AI analyzes architecture like a senior architect — finds dependency violations, pattern drift, complexity hotspots, proposes rules with rationale. Single AI session, no subagent spawning. |
| `/archie-deep-scan` | `archie-deep-scan.md` | Comprehensive baseline: full 2-wave multi-agent analysis. Wave 1: 3-4 parallel Sonnet agents gather facts. Wave 2: Opus reasoning produces decision chains, trade-offs, pitfalls. Supports `--incremental` and `--from N` for resume. |
| `/archie-viewer` | `archie-viewer.md` | Interactive blueprint inspection via `viewer.py`. Six tabs: Dashboard (health scores), Scan Reports (history), Blueprint (architecture data), Rules (adopted + proposed), Files (per-file analysis), Dependencies (graph visualization). |

### Skills (`.claude/skills/`)

| Skill | Purpose |
|-------|---------|
| `check-architecture.md` | Validate proposed changes against architecture rules |
| `check-naming.md` | Verify file and class naming conventions |
| `how-to-implement.md` | Get guidance on implementing a feature within the architecture |
| `where-to-put.md` | Find the right location for new files |
| `sync-architecture.md` | Update architecture context after code changes |

---

## StructuredBlueprint Data Model

The blueprint is the single source of truth. All rendered outputs derive from it.

```
blueprint.json
  meta                          # Executive summary, platforms, schema version, confidence scores
  architecture_rules
    file_placement_rules[]      # Where each file type belongs
    naming_conventions[]        # How files and classes should be named
  decisions
    architectural_style         # e.g. layered, hexagonal, microservices
    key_decisions[]             # Each with forced_by / enables links
    trade_offs[]                # Accepted trade-offs
    out_of_scope[]              # Explicit boundary markers
  components
    structure_type              # layered, modular, monolith, etc.
    components[]                # Name, path, responsibility, dependencies
    contracts[]                 # Interface contracts between components
  communication
    patterns[]                  # Design and communication patterns in use
    integrations[]              # External service integrations
    pattern_selection_guide[]   # When to use which pattern
  quick_reference
    where_to_put_code           # File type -> directory mapping
    pattern_selection           # Scenario -> pattern mapping
    error_mapping[]             # Common errors and their fixes
  technology
    stack[]                     # Language, framework, version
    templates[]                 # Code templates and snippets
    project_structure           # High-level directory purpose
    run_commands                # Build, test, lint, serve commands
  frontend                      # Only if frontend detected
    framework                   # React, Vue, Svelte, etc.
    rendering_strategy          # SSR, SSG, SPA, hybrid
    ui_components[]             # Component inventory
    state_management[]          # State patterns in use
    routing                     # Routing strategy
  developer_recipes[]           # Step-by-step task guides
  pitfalls[]                    # Common mistakes with causal chains
  implementation_guidelines[]   # Capability-specific implementation guides
  development_rules[]           # Always/never imperatives
  deployment                    # CI/CD, hosting, environment config
  architecture_diagram          # Mermaid or PlantUML diagram
```

Schema version: `2.0.0`

Note: The `/archie-deep-scan` Wave 2 (Opus reasoning) may add additional fields to the blueprint such as `decision_chain` (root constraint tree), violation keywords per decision node, and violation signals per trade-off. These are produced by the AI reasoning step and consumed by the renderer for deeper context generation.

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

### Health Check (`/archie-scan`)

```
/archie-scan
    |
    v
Step 1: Deterministic data gathering (scripts, seconds)
    |-- scanner.py: file tree, imports, frameworks, skeletons
    |-- measure_health.py: erosion, gini, verbosity, top-20%, waste
    |-- git log: recent changes
    |-- Read: skeletons.json, scan.json, health.json
    |-- Read (if exist): blueprint.json, scan_report.md, health_history.json,
    |                     rules.json, ignored_rules.json
    v
Step 2: AI architectural analysis (senior architect role)
    |-- Analyze dependency direction from import graph
    |-- Assess component responsibilities from skeletons
    |-- Find pattern inconsistencies across files
    |-- Detect duplication / reimplementation
    |-- Read suspicious source files to verify findings
    |-- Check blueprint violations (if deep scan exists)
    |-- Propose new architectural rules with rationale
    v
Step 3: Write outputs
    |-- .archie/scan_report_YYYY-MM-DD.md (dated report)
    |-- .archie/scan_report.md (latest pointer, copy)
    |-- .archie/health_history.json (append health scores)
    |-- .archie/function_complexity.json (complexity snapshot)
    v
Step 4: Present findings, save proposed rules
    |-- Show health scores table
    |-- List all findings with evidence
    |-- Save proposed rules to .archie/proposed_rules.json
    |-- Rules can be adopted from /archie-viewer (Rules tab) or by Claude Code
```

---

## Compound Learning

Each `/archie-scan` reads all accumulated knowledge before analyzing:

- `.archie/blueprint.json` — Evolving architectural knowledge base
- `.archie/health_history.json` — Timestamped health snapshots for trend detection
- `.archie/rules.json` — Previously adopted rules (scan won't override deep-baseline rules)
- `.archie/proposed_rules.json` — Pending rules with AI confidence scores (0-1)
- `.archie/function_complexity.json` — Previous complexity snapshot for comparison

After analysis, findings are merged back:
- Blueprint confidence increases with repeated confirmation across scans
- Resolved pitfalls are marked with timestamps but preserved as architectural history
- Health scores are appended to history for trend analysis (improving/degrading/stable)
- All data items track provenance: `deep-baseline`, `scan-observed`, `scan-adopted`, `scan-inferred`

The blueprint evolves incrementally rather than being rebuilt from scratch.

---

## Drift Detection

Deep scans include two-phase drift detection:

### Phase 1: Mechanical drift (`standalone/drift.py`)

Deterministic analysis that detects:
- Pattern outliers (files that don't match established patterns)
- File size and complexity violations
- Dependency direction breaches
- Structural anomalies

### Phase 2: Deep AI drift

An agent reads the blueprint, mechanical drift report, and generated CLAUDE.md files to identify architectural drift categories:

| Category | What it detects |
|----------|----------------|
| `decision_violation` | Code that contradicts a recorded architectural decision |
| `pattern_erosion` | Gradual drift away from established patterns |
| `trade_off_undermined` | Changes that undermine accepted trade-offs |
| `pitfall_triggered` | Known pitfalls that have materialized in code |
| `responsibility_leak` | Logic placed in the wrong component/layer |
| `abstraction_bypass` | Direct access that skips established abstractions |
| `semantic_duplication` | Reimplementation of existing functionality |

Violations are grounded with specific `violation_signals` from the blueprint's trade-off and decision chain data.

---

## Cycle Detection

Every scan runs Tarjan's strongly connected components algorithm (`standalone/detect_cycles.py`) on the import graph. Output includes:
- Each cycle with the participating files
- File-level evidence showing which import creates each cycle
- Results stored in `.archie/dependency_graph.json`

Both `/archie-scan` and `/archie-deep-scan` run cycle detection.

---

## Ignore System

The scanner uses `IgnoreMatcher` (in `_common.py`) to determine which files and directories to skip:

1. **`.archieignore`** — Gitignore-format patterns delivered by the installer. Covers dependencies (`node_modules/`, `vendor/`, `.devenv/`), build outputs, IDE files, caches, and binary formats. Patterns without leading `/` match at any depth.
2. **`.gitignore`** — Merged with `.archieignore` (union). Nested `.gitignore` files are scoped to their directory.
3. **`SKIP_DIRS`** — Hardcoded fallback safety net in `_common.py` (30+ directories including `.devenv`, `.swiftpm`, `.pub-cache`, `.dart_tool`, `.ccache`).

All three layers are combined during `os.walk()` — ignored directories are pruned in-place so their entire subtrees are never visited.

## Blueprint Normalization

`normalize_blueprint()` in `_common.py` enforces the canonical schema:
- Dict sections (`meta`, `components`, `decisions`, etc.) are ensured to be dicts
- `components` arriving as a plain list is wrapped into `{"components": [...]}`
- List sections (`pitfalls`, `development_rules`, etc.) are ensured to be lists

Both pipelines use it: deep-scan via `finalize.py`, fast scan via `finalize.py --normalize-only`.

## No Inline Python Constraint

Scan templates include a "CRITICAL CONSTRAINT: Never write inline Python" block that forbids `python3 -c "..."` during scans. Every operation has a dedicated CLI command:

| Command | Replaces |
|---------|----------|
| `measure_health.py --append-history --scan-type fast\|deep` | Inline Python health history append |
| `finalize.py --normalize-only` | Inline Python blueprint normalization |
| `intent_layer.py inspect <file> [--query .key]` | Ad-hoc JSON inspection |

This prevents crashes from Claude guessing wrong field names (e.g., `batch_id` vs `id`, `path` vs `id`).

---

## Error Handling and Resilience

| Scenario | Behavior |
|----------|----------|
| Rules file missing | Hooks exit 0 silently (fail open). |
| Blueprint file missing | Scan proceeds without prior knowledge — starts fresh. |
| File I/O errors during scan | Individual files skipped with try/except. Scan continues. |
| Deep scan agent fails | Skipped. Remaining agents continue. Three JSON extraction strategies tried: direct parse, code block extraction, brace matching. |
| Deep scan interrupted | Use `--continue` to resume from where it stopped. |

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific module tests
python -m pytest tests/test_scanner.py -v
python -m pytest tests/test_planner.py -v

# Run with coverage
python -m pytest --cov=archie tests/
```

### Test organization

Tests mirror the package structure. Each module has a corresponding `test_*.py` file. 26 test files, 3400+ LOC total. Tests use:

- **Fixtures** — Common test repos (temp directories with known file structures)
- **Mocking** — Subprocess calls mocked for runner tests, file system mocked where needed
- **Pydantic validation** — Model tests verify schema compliance
- **E2E** — `test_refresh_e2e.py` tests full scan-change-rescan workflow

---

## File Sync Protocol

Standalone scripts and slash commands exist in two places (canonical -> copy):

```
archie/standalone/*.py     ->  npm-package/assets/*.py
.claude/commands/*.md      ->  npm-package/assets/*.md
```

**Workflow:**
1. Always edit the canonical file first (`archie/standalone/` or `.claude/commands/`)
2. Copy to `npm-package/assets/`
3. Before committing, run the sync checker:

```bash
python3 scripts/verify_sync.py
```

This verifies all canonical files, asset copies, and `archie.mjs` references are consistent. It catches missing copies, orphan assets, and dead installer references.

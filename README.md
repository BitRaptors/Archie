# Archie — AI Governance for Coding Agents

[![npm version](https://img.shields.io/npm/v/@bitraptors/archie)](https://www.npmjs.com/package/@bitraptors/archie)
[![GitHub release](https://img.shields.io/github/v/release/BitRaptors/Archie)](https://github.com/BitRaptors/Archie/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Your AI writes code. Archie makes sure it follows your architecture.

Archie scans your codebase, builds a structured architecture blueprint, and enforces it in real-time through Claude Code hooks. When your AI agent tries to put a file in the wrong place, break a naming convention, or violate an architectural constraint, Archie catches it before the code is written.

Works with any language. Zero runtime dependencies for standalone scripts.

## Install

```bash
npx @bitraptors/archie /path/to/your/project
```

This copies Archie's standalone scripts and Claude Code commands into your project, installs enforcement hooks, configures permissions, and sets up `.gitignore` entries. Then open your project in Claude Code.

The installer performs a clean install — it removes old scripts, hooks, and commands before installing fresh versions, so upgrades are safe to run in-place.

## Two Commands

| Command | What it does | Time |
|---------|-------------|------|
| `/archie-scan` | Architecture health check. Runs deterministic scanner for data, then AI analyzes the architecture like a senior architect: finds dependency violations, pattern drift, complexity hotspots, proposes enforceable rules. Each scan builds on prior knowledge — confidence grows with repeated confirmation. | 1-3 min |
| `/archie-deep-scan` | Comprehensive architecture baseline. Full 2-wave multi-agent analysis (3-4 Sonnet agents + Opus reasoning) producing blueprint, per-folder CLAUDE.md, rules, and health metrics. | 15-20 min |

Run `/archie-deep-scan` once to establish a baseline. Then use `/archie-scan` for ongoing checks — each scan compounds on previous knowledge.

There is also `/archie-viewer` for interactive blueprint inspection (6 tabs: Dashboard, Scan Reports, Blueprint, Rules, Files, Dependencies).

### `/archie-scan` in action

![archie-scan demo](docs/assets/archie-scan-demo.gif)

<details>
<summary>Example scan output (this is the actual agent summary — the underlying blueprint is much richer)</summary>

```
Archie Scan #2 Complete

Health Scores

┌───────────┬─────────┬──────────┬────────┬──────────┐
│  Metric   │ Current │ Previous │ Trend  │  Status  │
├───────────┼─────────┼──────────┼────────┼──────────┤
│ Erosion   │ 0.87    │ 0.87     │ Stable │ CRITICAL │
├───────────┼─────────┼──────────┼────────┼──────────┤
│ Gini      │ 0.8852  │ 0.8852   │ Stable │ HIGH     │
├───────────┼─────────┼──────────┼────────┼──────────┤
│ Top-20%   │ 0.9216  │ 0.9216   │ Stable │ HIGH     │
├───────────┼─────────┼──────────┼────────┼──────────┤
│ Verbosity │ 0.0103  │ 0.0103   │ Stable │ GOOD     │
├───────────┼─────────┼──────────┼────────┼──────────┤
│ LOC       │ 122,290 │ 122,290  │ Stable │ -        │
└───────────┴─────────┴──────────┴────────┴──────────┘

Blueprint Evolution

- Components: 25 -> 27 (+Context Types, +Debug Component)
- Pitfalls: 12 -> 18 (6 new from deeper analysis)
- Architecture rules: 0 -> 2 (async tools, ApiClient singleton)
- Development rules: 8 -> 14 (6 new pattern-based rules)
- 8 rule confidences updated based on verified evidence

All Findings (20 total)

RECURRING - Error (8):
1. Renderer Mega-Cycle — 11-dir cycle, entire renderer layer entangled (0.92)
2. API/Models Circular Dependency — models import ApiClient (0.95)
3. ProjectScreen God Component — CC=365, 1420 SLOC (0.95)
4. Compatibility Hooks Debt — ~2000 SLOC, 8 dirs depend on it (0.92)
5. Bare except: Clauses — 15 instances in 8 files (0.99)
6. Inline Pydantic Models — 27 in projects_router, 8 duplicates (0.95)
7. Hardcoded Supabase Credentials — JWT in AuthContext.tsx (0.99)
8. Electron Process Boundary — main imports renderer context (0.85)

NEW - Error (1):
9. ApiClient Singleton Violation — new ApiClient() in EnvironmentMcpTab.tsx (0.93)

RECURRING - Warning (5):
10. Backend Utils-Tools coupling (weight=24) (0.80)
11. Inconsistent imports — 40 absolute from src. across 14 files (0.97)
12. Duplicated JSON/HTML extraction (0.85)
13. Repeated step_logger guards (0.88)
14. Tool naming — TOOL_ID only in 10/22 files (0.85)

NEW - Warning (5):
15. Memory Services — 8 identical methods in 2 services, no base class (0.95)
16. Duplicated utilities — 7 functions duplicated across files (0.90)
17. settings_loader.py — 7+ high-CC functions, 2000+ lines (0.90)
18. graph.py — 8 high-CC LangGraph step functions (0.87)
19. Test stubs — 4 tests with no assertions (0.88)

Proposed Rules

┌─────┬───────────────────────────────────────────────────────────────┬──────────┬────────────┐
│  #  │                             Rule                              │ Severity │ Confidence │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 1   │ scan-013: Tool entry functions must be async                  │ error    │ 0.99       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 2   │ scan-014: Tool files must init logger                         │ warn     │ 0.97       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 3   │ scan-015: Feature components use PascalCase                   │ warn     │ 0.82       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 4   │ scan-016: ApiClient accessed only via getInstance()           │ error    │ 0.93       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 5   │ scan-017: LangGraph steps named <verb>_<noun>_step            │ warn     │ 0.87       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 6   │ scan-018: FastAPI dependency factories follow get_<service>() │ warn     │ 0.90       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 7   │ scan-019: Memory services must share a base class             │ warn     │ 0.95       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 8   │ scan-020: Date utilities centralized in dateUtils.ts only     │ warn     │ 0.90       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 9   │ scan-021: TOOL_ID constant must be named exactly TOOL_ID      │ warn     │ 0.83       │
├─────┼───────────────────────────────────────────────────────────────┼──────────┼────────────┤
│ 10  │ scan-022: No inline Pydantic models in routers                │ error    │ 0.91       │
└─────┴───────────────────────────────────────────────────────────────┴──────────┴────────────┘

Next Task

What: Refactor ProjectScreen god component (CC=365, 1420 SLOC)
Where: frontend/src/renderer/screens/project.tsx
Why: Highest complexity in the codebase, disproportionate impact on all red metrics

Full report: .archie/scan_report_2026-04-08.md
```

</details>

### `/archie-deep-scan` in action

![archie-deep-scan demo](docs/assets/archie-deep-scan-demo.gif)

<details>
<summary>Example deep scan output (this is the actual agent summary — the underlying blueprint is much richer)</summary>

```
Archie Deep Scan — Complete Assessment

Part 1: What Was Generated

┌──────────────────────────────┬──────────┬─────────┐
│           Artefact           │ Frontend │ Backend │
├──────────────────────────────┼──────────┼─────────┤
│ Blueprint sections           │ 13       │ 13      │
├──────────────────────────────┼──────────┼─────────┤
│ Components discovered        │ 11       │ 9       │
├──────────────────────────────┼──────────┼─────────┤
│ Enforcement rules            │ 32       │ 31      │
├──────────────────────────────┼──────────┼─────────┤
│ Per-folder CLAUDE.md files   │ 54       │ 442     │
├──────────────────────────────┼──────────┼─────────┤
│ Rule files in .claude/rules/ │ 6        │ 6       │
├──────────────────────────────┼──────────┼─────────┤
│ Total source files scanned   │ 228      │ 972     │
├──────────────────────────────┼──────────┼─────────┤
│ Dependencies mapped          │ 118      │ 358     │
└──────────────────────────────┴──────────┴─────────┘

Part 2: Architecture Summary

Architecture style: Electron desktop application (frontend) + Python FastAPI
backend with LangGraph-based multi-agent AI orchestration.

Key components:
- Electron Main Process — Window lifecycle, backend spawning, IPC, auto-updates
- React Renderer — SPA with 7 nested Context providers, Shadcn UI, Tailwind CSS
- API Layer — FastAPI routers for REST + WebSocket real-time communication
- Agent System — Planner/Executor/Validator/Corrector pipeline via LangGraph
- Tool Registry — 20+ pluggable async tools (browser, LLM, file I/O, MCP)
- Persistence — Local filesystem with UUID-based project directories
- WebSocket Service — Unified singleton connection with ~60fps message batching

Part 3: Architecture Health Assessment

┌─────────────────┬──────────────────────────────────────────┬──────────────────────────────────────────┐
│    Dimension    │                 Frontend                  │                 Backend                  │
├─────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────┤
│ Separation of   │ Weak — Layout does data fetching,        │ Adequate — Clear module boundaries but   │
│ concerns        │ compat hooks own CRUD operations         │ graph nodes reach into persistence       │
├─────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────┤
│ Dependency      │ Weak — Preload exposes raw ipcRenderer,  │ Weak — Utils imports from DI layer,      │
│ direction       │ components bypass ApiClient singleton    │ tools import DI factories directly       │
├─────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────┤
│ Pattern         │ Adequate — Most contexts follow          │ Adequate — Tool pattern consistent but   │
│ consistency     │ useReducer, AuthContext uses useState    │ DI bypass in 3 tools                    │
├─────────────────┼──────────────────────────────────────────┼──────────────────────────────────────────┤
│ Testability     │ Adequate — Singleton provides seams but  │ Weak — Tools directly call DI factories │
│                 │ raw IPC creates hard-to-mock paths       │ making them untestable in isolation      │
└─────────────────┴──────────────────────────────────────────┴──────────────────────────────────────────┘

Health metrics:

┌────────────────────────────┬──────────────┬─────────────────┐
│           Metric           │   Frontend   │     Backend     │
├────────────────────────────┼──────────────┼─────────────────┤
│ Erosion (complexity)       │ 0.95 (high)  │ 0.69 (moderate) │
├────────────────────────────┼──────────────┼─────────────────┤
│ Gini (code concentration)  │ 0.92         │ 0.76            │
├────────────────────────────┼──────────────┼─────────────────┤
│ Top 20% file share         │ 96.9%        │ 81.5%           │
├────────────────────────────┼──────────────┼─────────────────┤
│ Verbosity (exact clones)   │ 1.0%         │ 1.1%            │
├────────────────────────────┼──────────────┼─────────────────┤
│ Total LoC                  │ 76,903       │ 45,261          │
├────────────────────────────┼──────────────┼─────────────────┤
│ High cyclomatic complexity │ 74 functions │ 124 functions   │
└────────────────────────────┴──────────────┴─────────────────┘

Part 4: Architectural Drift

Errors (must fix):
- Raw ipcRenderer exposed in preload — bypasses security model
- WebSocket stale closure — handlers read initial empty state forever
- Duplicate startup_event handlers — session cleanup silently dropped
- API key logged in plaintext on every startup
- Circular import: settings_loader ↔ dependencies.py
- Validator hardcodes LLM creation instead of injection

Part 5: Top Risks & Recommendations

1. IPC Security Hole — Raw ipcRenderer passthrough makes preload bridge meaningless
2. API Key Exposure — Full OpenAI key logged to file on every cold start
3. Stale WebSocket State — All real-time mapping uses stale data
4. Circular Dependencies — Fragile dependency web across layers
5. Duplicate Startup Handler — Session cleanup never runs

Part 6: Semantic Duplication

3 groups found: placeholder resolver duplicated in executor.py,
dual WebSocketMappingService instances, sidebar state in two contexts.
```

</details>

### Deep Scan Advanced Modes

| Flag | What it does |
|------|-------------|
| `--incremental` | Only process files changed since last deep scan (3-6 min vs 15-20 min) |
| `--continue` | Resume from where the last run stopped (handles interruptions) |
| `--from N` | Resume from a specific step N (steps 1-9) |

### Monorepo Support

Deep scan auto-detects sub-projects (via Gradle, package.json, pyproject.toml, etc.) and offers parallel or sequential analysis. Each sub-project gets its own blueprint.

## What It Generates

| Output | Purpose |
|--------|---------|
| `.archie/blueprint.json` | Structured architecture data (single source of truth) |
| `.archie/rules.json` | Adopted enforcement rules (from blueprint extraction + AI-proposed scan rules) |
| `.archie/proposed_rules.json` | AI-proposed rules pending adoption, with confidence scores |
| `.archie/health.json` | Current architecture health scores |
| `.archie/health_history.json` | Timestamped health snapshots for trend analysis |
| `.archie/dependency_graph.json` | Resolved dependency graph with cycle detection |
| `.archie/function_complexity.json` | Per-function cyclomatic complexity snapshot |
| `.archie/scan_report.md` | Latest scan report (all reports preserved in `.archie/scan_history/`) |
| `CLAUDE.md` | Root architecture context for Claude Code |
| `AGENTS.md` | Multi-agent guidance with decision chains |
| Per-folder `CLAUDE.md` | Directory-level context with patterns, anti-patterns, code examples |
| `.claude/hooks/` | Real-time enforcement hooks |
| `.claude/rules/*.md` | Topic-split rule files (architecture, patterns, guidelines, pitfalls) |

## How It Works

### Deep Scan Pipeline (2-Wave)

1. **Scanner** — Deterministic local analysis: file tree, import graph, framework detection, token counting, file hashing, skeleton extraction (class/function signatures for efficient AI context). Pure Python, no AI.

2. **Wave 1** (parallel) — 3-4 Sonnet agents gather facts simultaneously:
   - **Structure agent** — Components, layers, file placement rules
   - **Patterns agent** — Communication patterns, design patterns, integrations
   - **Technology agent** — Stack inventory, deployment config, dev rules
   - **UI agent** — UI components, state management, routing (only if frontend detected)

3. **Wave 2** — Opus reasoning agent reads all Wave 1 output and produces deep architectural reasoning:
   - Decision chain (root constraint tree with forced_by/enables links)
   - Key decisions with violation keywords
   - Trade-offs with violation signals (patterns that would indicate the trade-off is being undermined)
   - Pitfalls traced to specific architectural choices (causal chains)
   - Architecture diagram

4. **Normalize** — AI reshapes raw output to canonical schema
5. **Render** — Deterministic JSON-to-Markdown (CLAUDE.md, AGENTS.md, per-folder context)
6. **Validate** — Cross-reference output against actual codebase (paths, methods, pitfalls)
7. **Intent Layer** — AI-generated per-folder CLAUDE.md via bottom-up DAG scheduling (leaf folders first, parents inherit child summaries, incremental re-generation for changed folders only)

### Compound Learning

Each `/archie-scan` reads the existing blueprint, health history, and prior rules before analyzing. Findings are merged back — confidence scores increase with repeated confirmation, resolved pitfalls are marked but preserved as history. The blueprint evolves incrementally rather than being rebuilt from scratch.

### Drift Detection

Deep scans include two-phase drift detection:

1. **Mechanical drift** (`drift.py`) — Detects pattern outliers, file size/complexity violations, dependency direction breaches, structural anomalies
2. **Deep AI drift** — Agent reads blueprint + drift report + CLAUDE.md files to identify: decision violations, pattern erosion, trade-off undermining, pitfall triggers, responsibility leaks, abstraction bypasses, semantic duplication

### Cycle Detection

Every scan runs Tarjan's algorithm on the import graph to find strongly connected components. Cycles are reported with file-level evidence showing which imports create each cycle.

### Real-Time Enforcement

Once installed via `npx @bitraptors/archie`, four hooks are registered:

- **PreToolUse (Write|Edit|MultiEdit)** — Before every file write, checks against `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`, and `file_naming` rules. Violations are blocked (error) or warned (warn).
- **PreToolUse (Bash)** — Before git commits, triggers an architectural review of the diff via `arch_review.py`.
- **PostToolUse (ExitPlanMode)** — After plan approval, triggers an architectural review of the plan.
- **PreToolUse (Glob|Grep)** — Blueprint nudge: reminds the agent about project architecture before code exploration.

All hooks fail open: if `.archie/rules.json` doesn't exist, they exit silently. Permissions are auto-configured in `.claude/settings.local.json` to prevent workflow interruptions.

## Rules

Rules come from three sources:

1. **Blueprint extraction** (`rules/extractor.py`) — Deterministically extracts `file_placement` and `naming` rules from the blueprint's `architecture_rules` and `components` sections.

2. **AI-proposed rules** (`/archie-scan`) — The scan AI proposes architectural rules with deep rationale tracing back to decision chains and trade-offs. Each rule includes a confidence score (0-1). Rules can be adopted, skipped, or managed from `/archie-viewer` (Rules tab) or interactively by Claude Code during scans. Source tracking distinguishes `deep-baseline`, `scan-adopted`, and `scan-inferred` rules.

3. **Platform rules** (`platform_rules.json`) — 40+ predefined architectural checks installed with every project, covering:
   - **Universal** — God-functions, growing complexity, empty catches, disabled tests, hardcoded secrets
   - **Android** — Layer violations (ViewModel/Context, Fragment/network), lifecycle (GlobalScope), DI anti-patterns
   - **Swift** — Force unwraps, force try, view-layer network access
   - **TypeScript** — Components fetching data, `any` type, React DOM manipulation, array index keys
   - **Python** — Bare except, eval/exec, mutable defaults, star imports

Each rule has a severity (`warn` for advisory, `error` for blocking). Severity can be changed from `/archie-viewer` or by Claude Code during scans.

## Health Metrics

`/archie-scan` calculates architecture health scores and tracks them over time in `.archie/health_history.json`:

| Metric | What it measures |
|--------|-----------------|
| **Erosion** (0-1) | Fraction of complexity mass concentrated in high-branching-complexity functions (>10 CC). 0 = evenly distributed, 1 = all in a few god-functions. |
| **Gini** (0-1) | Inequality of complexity distribution across all functions, like wealth inequality for code. 0 = every function equally complex. |
| **Top-20% share** (0.2-1) | Fraction of total complexity held by the top 20% of functions. |
| **Verbosity** (0-1) | Duplicate-line ratio across source files. Measures exact line-for-line duplication. |
| **Abstraction waste** | Count of single-method classes and tiny functions (likely trivial wrappers). |
| **LOC** | Total lines of code. Monotonic growth without feature growth signals degradation. |

Each scan compares current scores against history to detect trends (improving, degrading, or stable).

## Requirements

- **Python 3.9+** for standalone scripts (installed via `npx @bitraptors/archie`, stdlib only)
- **Node.js 18+** for `npx @bitraptors/archie` installer
- **Claude Code** for `/archie-scan` and `/archie-deep-scan`

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full technical documentation.

## Repository Layout

```
archie/              Python package (CLI, engine, coordinator, hooks, renderer)
  cli/               Click CLI commands
  engine/            Local codebase analysis (scanner, imports, frameworks)
  coordinator/       2-wave AI pipeline (planner, runner, merger, prompts)
  hooks/             Claude Code hook generation and enforcement
  renderer/          Output generation (CLAUDE.md, per-folder context)
  rules/             Rule extraction and management
  standalone/        Zero-dependency scripts (copied to target projects via npm)
npm-package/         NPM distribution (npx @bitraptors/archie)
tests/               Pytest suite (22 files, 2700+ LOC)
docs/                Architecture documentation
.claude/commands/    Slash commands (archie-scan, archie-deep-scan, archie-viewer)
.claude/skills/      Developer assistance skills
```

## Kudos for Inspiration

- **[Cartographer](https://github.com/kingbootoshi/cartographer)** by [@kingbootoshi](https://github.com/kingbootoshi)
- **[Graphify](https://github.com/safishamsi/graphify)** by [@safishamsi](https://github.com/safishamsi)
- **[SlopCodeBench](https://arxiv.org/abs/2603.24755)**

## License

MIT

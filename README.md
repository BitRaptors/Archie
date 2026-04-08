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
| `.archie/scan_report.md` | Latest scan report (also dated copies in `scan_history/`) |
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

2. **AI-proposed rules** (`/archie-scan`) — The scan AI proposes architectural rules with deep rationale tracing back to decision chains and trade-offs. Each rule includes a confidence score (0-1). Users adopt them interactively during the scan. Source tracking distinguishes `deep-baseline`, `scan-adopted`, and `scan-inferred` rules.

3. **Platform rules** (`platform_rules.json`) — 40+ predefined architectural checks installed with every project, covering:
   - **Universal** — God-functions, growing complexity, empty catches, disabled tests, hardcoded secrets
   - **Android** — Layer violations (ViewModel/Context, Fragment/network), lifecycle (GlobalScope), DI anti-patterns
   - **Swift** — Force unwraps, force try, view-layer network access
   - **TypeScript** — Components fetching data, `any` type, React DOM manipulation, array index keys
   - **Python** — Bare except, eval/exec, mutable defaults, star imports

Each rule has a severity (`warn` for advisory, `error` for blocking) that you can change:
```bash
archie promote <rule-id>   # warn -> error
archie demote <rule-id>    # error -> warn
```

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
- **Python 3.11+** for the `archie-cli` pip package
- **Node.js 18+** for `npx @bitraptors/archie` installer
- **Claude Code** for `/archie-scan` and `/archie-deep-scan`

## CLI (pip install)

```bash
pip install archie-cli
```

| Command | What it does |
|---------|-------------|
| `archie init [PATH]` | Full pipeline: scan, plan, prompts, hooks, run subagents, merge, render, extract rules |
| `archie refresh [PATH]` | Rescan and report changes since last scan (`--deep` for targeted refresh prompt) |
| `archie status [--path PATH]` | Blueprint freshness, rule counts, health scores |
| `archie rules [PATH]` | List all architecture rules with severity |
| `archie check [--files ...]` | Check files against rules (exit 0 = pass, 1 = violations; default: git diff) |
| `archie promote <rule-id>` | Promote rule from warn to error (blocks code changes) |
| `archie demote <rule-id>` | Demote rule from error to warn (advisory only) |
| `archie serve [--port PORT]` | Start blueprint viewer server (requires `archie-cli[serve]`) |

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

## License

MIT

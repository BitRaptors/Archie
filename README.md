# Archie — AI Governance for Coding Agents

Your AI writes code. Archie makes sure it follows your architecture.

Archie scans your codebase, builds a structured architecture blueprint, and enforces it in real-time through Claude Code hooks. When your AI agent tries to put a file in the wrong place, break a naming convention, or violate an architectural constraint, Archie catches it before the code is written.

Works with any language. Zero runtime dependencies for standalone scripts.

## Install

```bash
npx archie /path/to/your/project
```

This copies Archie's standalone scripts and Claude Code commands into your project, installs enforcement hooks, and sets up permissions. Then open your project in Claude Code.

## Two Commands

| Command | What it does | Time |
|---------|-------------|------|
| `/archie-scan` | Architecture health check. Runs deterministic scanner for data, then AI analyzes the architecture like a senior architect: finds dependency violations, pattern drift, complexity hotspots, proposes enforceable rules. | 1-3 min |
| `/archie-deep-scan` | Comprehensive architecture baseline. Full 2-wave multi-agent analysis (3-4 Sonnet agents + Opus reasoning) producing blueprint, per-folder CLAUDE.md, rules, and health metrics. | 15-20 min |

Run `/archie-deep-scan` once to establish a baseline. Then use `/archie-scan` for ongoing checks.

There is also `/archie-viewer` for interactive blueprint inspection.

## What It Generates

| Output | Purpose |
|--------|---------|
| `.archie/blueprint.json` | Structured architecture data (single source of truth) |
| `.archie/rules.json` | Enforcement rules (from blueprint extraction + AI-proposed scan rules) |
| `.archie/health.json` | Architecture health scores |
| `CLAUDE.md` | Root architecture context for Claude Code |
| `AGENTS.md` | Multi-agent guidance with decision chains |
| Per-folder `CLAUDE.md` | Directory-level context with patterns, anti-patterns, code examples |
| `.claude/hooks/` | Real-time enforcement hooks |

## How It Works

### Deep Scan Pipeline (2-Wave)

1. **Scanner** — Deterministic local analysis: file tree, import graph, framework detection, token counting, file hashing. Pure Python, no AI.

2. **Wave 1** (parallel) — 3-4 Sonnet agents gather facts simultaneously:
   - **Structure agent** — Components, layers, file placement rules
   - **Patterns agent** — Communication patterns, design patterns, integrations
   - **Technology agent** — Stack inventory, deployment config, dev rules
   - **UI agent** — UI components, state management, routing (only if frontend detected)

3. **Wave 2** — Opus reasoning agent reads all Wave 1 output and produces deep architectural reasoning:
   - Decision chain (root constraint tree)
   - Key decisions with forced_by/enables links
   - Trade-offs with violation signals
   - Pitfalls traced to specific architectural choices
   - Architecture diagram

4. **Normalize** — AI reshapes raw output to canonical schema
5. **Render** — Deterministic JSON-to-Markdown (CLAUDE.md, AGENTS.md, per-folder context)
6. **Validate** — Cross-reference output against actual codebase
7. **Intent Layer** — AI-generated per-folder CLAUDE.md via bottom-up DAG

### Real-Time Enforcement

Once installed via `npx archie`, three hooks are registered:

- **PreToolUse (Write|Edit|MultiEdit)** — Before every file write, checks against `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`, and `file_naming` rules. Violations are blocked (error) or warned (warn).
- **PreToolUse (Bash)** — Before git commits, triggers an architectural review of the diff.
- **PostToolUse (ExitPlanMode)** — After plan approval, triggers an architectural review of the plan.

All hooks fail open: if `.archie/rules.json` doesn't exist, they exit silently.

## Rules

Rules come from two sources:

1. **Blueprint extraction** (`rules/extractor.py`) — Deterministically extracts `file_placement` and `naming` rules from the blueprint's `architecture_rules` and `components` sections.

2. **AI-proposed rules** (`/archie-scan`) — The scan AI proposes architectural rules with rationale, which you adopt interactively. These use check types: `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`, `file_naming`.

Additionally, `platform_rules.json` provides predefined architectural checks that are installed with the project.

Each rule has a severity (`warn` for advisory, `error` for blocking) that you can change:
```bash
archie promote <rule-id>   # warn -> error
archie demote <rule-id>    # error -> warn
```

## Health Metrics

`/archie-scan` calculates architecture health scores:

| Metric | What it measures |
|--------|-----------------|
| **Erosion** (0-1) | Fraction of complexity mass concentrated in high-branching-complexity functions (>10 CC). 0 = evenly distributed, 1 = all in a few god-functions. |
| **Gini** (0-1) | Inequality of complexity distribution across all functions, like wealth inequality for code. 0 = every function equally complex. |
| **Top-20% share** (0.2-1) | Fraction of total complexity held by the top 20% of functions. |
| **Verbosity** (0-1) | Duplicate-line ratio across source files. Measures exact line-for-line duplication. |
| **Abstraction waste** | Count of single-method classes and tiny functions (likely trivial wrappers). |
| **LOC** | Total lines of code. Monotonic growth without feature growth signals degradation. |

## Requirements

- **Python 3.9+** for standalone scripts (installed via `npx archie`, stdlib only)
- **Python 3.11+** for the `archie-cli` pip package
- **Node.js 18+** for `npx archie` installer
- **Claude Code** for `/archie-scan` and `/archie-deep-scan`

## CLI (pip install)

```bash
pip install archie-cli
```

Commands: `archie init`, `archie refresh`, `archie status`, `archie check`, `archie serve`, `archie rules`, `archie promote`, `archie demote`.

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
npm-package/         NPM distribution (npx archie)
tests/               Pytest suite (22 files, 2700+ LOC)
docs/                Architecture documentation
.claude/commands/    Slash commands (archie-scan, archie-deep-scan, archie-viewer)
.claude/skills/      Developer assistance skills
```

## License

MIT

# Archie — Architecture Enforcement for AI Coding Agents

Archie analyzes your codebase, builds a structured architecture blueprint, and enforces it through Claude Code rules, hooks, and per-folder context. Works with any language. Zero dependencies.

## Install

```bash
npx archie /path/to/your/project
```

This copies Archie's scripts and Claude Code commands into your project.

## Use

Open your project in Claude Code, then:

```
/archie-init       # Full architecture analysis (5 parallel agents + reasoning)
/archie-refresh    # Update after code changes
/archie-enrich     # AI-enrich per-folder CLAUDE.md
/archie-viewer     # Inspect the blueprint
```

## What It Generates

| Output | Purpose |
|--------|---------|
| `.archie/blueprint.json` | Structured architecture data (single source of truth) |
| `CLAUDE.md` | Root architecture context for Claude Code |
| `AGENTS.md` | Multi-agent guidance with decision chains |
| `.claude/rules/*.md` | Topic-split rule files (architecture, patterns, guidelines, pitfalls, dev-rules) |
| `.cursor/rules/*.md` | Cursor rule files (mirrored) |
| Per-folder `CLAUDE.md` | Directory-level context with patterns, anti-patterns, code examples |
| `.claude/hooks/` | Real-time enforcement hooks |
| `.archie/rules.json` | 84+ enforcement rules extracted from blueprint |

## How It Works

**2-Wave Analysis:**

1. **Wave 1** (parallel) — 4 AI agents gather facts simultaneously:
   - Structure & Components — file organization, layers, interfaces
   - Patterns & Communication — design patterns, integrations, data flow
   - Technology & Deployment — stack inventory, deployment, dev rules
   - Frontend Architecture — UI components, state, routing (if detected)

2. **Wave 2** — Agent X reads all Wave 1 output and produces deep architectural reasoning:
   - Decision chain (root constraint → forced decisions → cascading consequences)
   - Trade-offs with violation signals
   - Pitfalls traced to specific architectural choices
   - Architecture diagram

## Rule Types

Archie extracts 12 types of rules from the blueprint:

- **file_placement** / **naming** — where files go, how they're named
- **dependency_direction** — prevents reverse imports between components
- **chain_violation** — protects the decision chain (with per-node violation keywords)
- **tradeoff_violation** — warns when undoing accepted trade-offs
- **pitfall_trace** — links pitfalls to their causal decision chain
- **impact_radius** — blast radius warnings for high-dependency components
- **dev_rule** — always/never imperatives from codebase signals
- **pattern_required** / **pattern_extension** — established patterns and extension points
- **out_of_scope** — boundary warnings

## Requirements

- Python 3.11+ (stdlib only, zero pip dependencies)
- Node.js 18+ (for `npx archie` installer)
- Claude Code (for `/archie-init` analysis)

## V1

The original Archie web application (FastAPI + Next.js) is archived in `v1/`. It's obsolete — the current standalone version produces better results.

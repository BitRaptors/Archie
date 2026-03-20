# Archie v2: CLI + Agent Hybrid — Design Document

> Approved 2026-03-19. Continues from `docs/BRAINSTORM.md`.

---

## Problem Statement

Archie's analysis is valuable but inert. After running a full analysis, the developer gets static output (CLAUDE.md, Cursor rules, AGENTS.md, MCP tools) that:

- **Goes stale silently** — code changes daily, the blueprint doesn't update, and nobody knows it's outdated
- **Has no enforcement** — violations go unnoticed until they're in production; the blueprint is a suggestion, not a contract
- **Is expensive and slow** — 7-9 Claude API calls per analysis, $1-10 per run, 2-5 minutes
- **Requires heavy infrastructure** — Docker, PostgreSQL, Redis, API keys, 15-30 min setup

The trust problem and the enforcement problem are deeply coupled: you can't enforce stale rules (harmful), and without enforcement, even a fresh blueprint is ignored.

---

## Design Principles

1. **Zero Claude API calls.** All LLM work happens through Claude Code subagents (developer's existing subscription).
2. **Zero infrastructure.** No Docker, no database, no Redis, no server for core functionality.
3. **Warn by default, block optionally.** Trust the developer. Earn strictness.
4. **Transparent in both directions.** Invisible when working (auto-integrates into workflow). Visible when inspecting (full observability).
5. **Local analysis is the moat.** 70% of the blueprint data is extracted for free in seconds. LLM handles the remaining 30% that requires judgment.
6. **Solo developer first, teams second.** The solo experience must work completely before team features layer on.

---

## Constraints and Non-Negotiables

### Intellectual Property

- **No code from Cartographer (kingbootoshi/cartographer) or Rippletide (rippletideco/rippletide) may be copied, adapted, or derived.** Not a single line.
- What informed this design are publicly observable architectural patterns: orchestrator/subagent coordination, Claude Code hooks for enforcement, conversational overrides. These are concepts, not implementations.
- All code must be written from scratch. During implementation, do not reference their source code.

### Technical

- Zero Claude API calls — subagents only (developer's Claude Code session)
- Zero infrastructure — no Docker, no database, no Redis, no server
- Zero API keys — developer needs Claude Code installed, nothing else
- Local engine must be pure Python with minimal dependencies (stdlib `ast`, regex heuristics)
- `StructuredBlueprint` v2.0.0 stays backward-compatible — new fields are additive
- All enforcement runs locally — no network calls in hooks
- Stats file is append-only JSONL, `.gitignore`d by default

### UX

- `archie init .` must produce usable output even if subagent analysis is shallow — the local engine alone generates a valid (if incomplete) blueprint
- Hooks must fail open — missing or corrupt `blueprint.json` means hooks do nothing, never block
- No telemetry, no analytics, no phone-home — fully offline except for subagent sessions
- Override is always available — no rule can permanently block without user escape

---

## Section 1: Core Model

Archie becomes a "local analysis engine + agent coordinator" — not an API client.

```
┌──────────────────────────────────────────────────────────────┐
│  archie init .                                               │
│                                                              │
│  ┌─────────────────┐                                         │
│  │ Local Engine     │  1. Scan file tree, parse deps,        │
│  │ (free, instant)  │     detect frameworks, count tokens,   │
│  │                  │     hash signatures, build component   │
│  │                  │     map, extract config patterns       │
│  └────────┬────────┘                                         │
│           │ raw scan + token-budgeted file groups             │
│           ▼                                                  │
│  ┌─────────────────┐     ┌────────────────────────────────┐  │
│  │ Opus Coordinator │────►│ Sonnet Subagents (parallel)    │  │
│  │ (orchestrates,   │     │                                │  │
│  │  never reads     │◄────│ • read assigned files          │  │
│  │  code directly)  │     │ • search web for unknown libs  │  │
│  │                  │     │ • fill blueprint sections       │  │
│  └────────┬────────┘     └────────────────────────────────┘  │
│           │ validated StructuredBlueprint JSON                │
│           ▼                                                  │
│  ┌─────────────────┐                                         │
│  │ Renderer +       │  CLAUDE.md, AGENTS.md, Cursor rules,   │
│  │ Hook Generator   │  MCP config, .claude/hooks/*,          │
│  │ (deterministic)  │  .archie/blueprint.json                │
│  └─────────────────┘                                         │
└──────────────────────────────────────────────────────────────┘
```

**Three layers:**

1. **Local Engine (free, instant)** — File tree scanning, AST parsing, dependency detection, framework identification, file hashing, import graph, pattern matching. Deterministic, zero-cost, runs in milliseconds. Produces a "raw scan" that's ~60-70% of the blueprint data.

2. **Agent Coordinator** — Takes the raw scan and asks a Claude Code Opus coordinator to plan subagent assignments. Sonnet subagents read files and fill in sections requiring judgment: architecture decisions, layer boundaries, communication patterns, implementation guidelines. 1-3 agent interactions instead of 7-9 API calls.

3. **Renderer + Hook Generator** — Deterministic. Takes the validated blueprint JSON and produces all output formats plus enforcement hooks. No AI needed.

---

## Section 2: Local Analysis Engine

The moat. Produces a raw scan for free in seconds.

**Output structure:**

```
RawScan:
  file_tree:           # every source file path, size, last modified
  token_counts:        # per-file token count (tiktoken)
  dependencies:        # parsed from package.json, requirements.txt, go.mod, etc.
  framework_signals:   # detected: "Next.js 14", "FastAPI", "React 18", etc.
  config_patterns:     # docker-compose.yml, CI configs, env files, cloud configs
  import_graph:        # who imports whom (AST-based, not LLM)
  directory_structure:  # heuristic layer detection (src/api/, src/domain/, etc.)
  file_hashes:         # SHA256 per file — for freshness diffing
  entry_points:        # detected main files, route definitions, CLI entry points
```

**What this gives the Opus coordinator:**
- Already knows the stack, dependencies, file structure, and rough layering before any LLM call
- Can plan subagent assignments by module/layer, not just by token count
- Subagents focus on *why* and *how* (decisions, conventions, patterns) — the *what* is already known

**What this gives enforcement:**
- File hashes enable instant "what changed since last analysis"
- Import graph enables "this file violates layer boundaries" detection — no LLM needed
- Framework signals enable rule templates per framework

---

## Section 3: Agent Coordination

Opus orchestrates, Sonnet reads. Inspired by the orchestrator/subagent pattern but implemented from scratch.

**The flow:**

1. Local engine runs (2-5 seconds), produces raw scan
2. Opus coordinator receives raw scan, plans subagent assignments based on:
   - Module boundaries (from import graph)
   - Token budgets (~150k per subagent)
   - Blueprint sections that need filling
3. Sonnet subagents spawned in parallel via Claude Code's `Task` tool:
   - Each gets a file group + relevant raw scan data + blueprint section schema
   - Each returns structured JSON matching blueprint schema sections
   - Can use all Claude Code tools: file reading, grep, web search for unknown libraries
4. Opus receives subagent reports:
   - Merges into single StructuredBlueprint JSON
   - Validates against Pydantic schema
   - Resolves contradictions between subagents
   - Fills cross-cutting sections (quick_reference, meta)
5. Returns validated blueprint to Archie CLI

**Scaling:** Small repos (< 100 files): 1 subagent. Medium repos (100-500 files): 2-3 subagents. Large repos (500+): 3-5 subagents. Always guided by module boundaries + token budget.

---

## Section 4: Enforcement Layer

Blueprint-backed enforcement via Claude Code hooks. No LLM calls — all checks run locally against structured JSON.

### Hook 1: `inject-context.sh` (UserPromptSubmit)

Fires before every user prompt. Matches keywords from the prompt against blueprint sections, injects relevant rules into context.

Example: User types "Add a new payment endpoint" → hook injects API layer rules + payment component conventions. Claude self-corrects before writing code.

No LLM call. Pure keyword matching + JSON lookup. Instant, free.

### Hook 2: `pre-validate.sh` (PreToolUse)

Fires before Write, Edit, or MultiEdit. Checks the proposed change against blueprint rules.

Example: Claude about to write a file with a direct SQL import in the API layer → hook detects forbidden cross-layer import → returns warning or block depending on severity.

### Check Catalog

**Tier 1: Free, instant, no LLM — runs on every Write/Edit**

| Check | Source | How |
|---|---|---|
| File placement | `blueprint.components` | Path pattern matching |
| Naming conventions | `blueprint.architecture_rules.naming` | Regex |
| Cross-layer imports | `blueprint.architecture_rules.layer_boundaries` | Import parsing |
| File name matches responsibility | `blueprint.components` | Path + name pattern |
| Technology stack violations | `blueprint.technology` | Dependency check |
| Function length | AST analysis | Line count per function |
| Unused imports / dead code | AST + import graph | Static analysis |
| Contradictory patterns | `blueprint.decisions` | Pattern matching |

**Tier 2: Injected context, no extra LLM call — runs via UserPromptSubmit**

| Injection | Source | When |
|---|---|---|
| Relevant architecture rules | `blueprint.architecture_rules` | Always — keyword matched |
| Component placement guidance | `blueprint.components` | Creating/adding something new |
| Existing implementation patterns | `blueprint.implementation_guidelines` | Capability that already exists |
| Planning constraints | `blueprint.decisions` + `architecture_rules` | Planning prompts |
| Convention reminders | `blueprint.quick_reference` | Always |

**Tier 3: Blueprint-unique checks (local, no LLM)**

| Check | Source | How |
|---|---|---|
| API contract consistency | `blueprint.communication` | Route pattern matching |
| Deployment pattern violations | `blueprint.deployment` | Config analysis |
| Frontend/backend boundary | `blueprint.frontend` + `blueprint.components` | Import check |
| Duplicate responsibility | `blueprint.components` | Similarity check |

### Severity Model

```json
{
  "info":  "Injected as context. No action required.",
  "warn":  "Hook allows (exit 0) but prints warning. Claude can self-correct.",
  "error": "Hook blocks (exit 2). Claude must fix or ask user to override."
}
```

- All rules default to `warn`
- Developer promotes rules: `archie promote <rule-id>` → flips to `error`
- Developer demotes rules: `archie demote <rule-id>` → flips back to `warn`
- Override is always conversational — hook tells Claude to ask user, no magic comments in code

---

## Section 5: Freshness System

Three levels, cost-proportional.

### Level 1: Passive detection (free, automatic)

Every time the PreToolUse hook fires, it also checks freshness by comparing file hashes and checking for unknown files. If stale, injects an informational note. No enforcement degradation — uses best available data.

### Level 2: Local refresh (free, seconds)

```bash
archie refresh    # or triggered by git hook on commit
```

Re-runs the local engine only. Updates file tree, token counts, dependencies, import graph, file hashes. Adds placeholder blueprint entries for new files/modules with `"confidence": "local-only"`. Removes entries for deleted files.

**Can run on every commit via git hook. Cost: zero. Speed: 2-5 seconds.**

### Level 3: Agent refresh (uses Claude Code, targeted)

```bash
archie refresh --deep     # CLI
/archie-refresh           # Claude Code skill
```

Only runs when Level 2 detects changes needing judgment. Spawns a single Sonnet subagent scoped to changed files/sections. Updates affected blueprint sections. Re-renders affected outputs.

**Cost: minimal — one targeted subagent reading 3-5 files.**

### Freshness Lifecycle

```
Day 1:  archie init .              → full analysis (2-4 subagents)
Day 2:  git commit                 → Level 2 auto-refresh (local, free)
Day 3:  git commit                 → Level 2 (local, free)
Day 5:  git commit adds new module → Level 2 detects, flags "stale"
Day 5:  archie refresh --deep      → Level 3 (1 subagent, targeted)
Day 8:  git commit                 → Level 2 (local, free)
Day 14: major refactor             → archie init . --refresh (full re-analysis)
```

---

## Section 6: Observability

### CLI dashboard

```bash
archie status
```

Shows: blueprint freshness per section (% of files matching), enforcement stats (checks run, warnings, blocks, self-corrections), rule summary (total, warn count, error count), recommendation for next action.

**Cost: zero. Reads from `.archie/blueprint.json` + `.archie/stats.jsonl`.**

### Inline hook feedback

- **Everything fine:** silence. No output, no friction.
- **Warning:** printed in conversation with rule ID, explanation, suggestion. Claude sees it, self-corrects.
- **Block:** printed with rule ID, explanation, instruction for Claude to ask user for override.
- **Stale:** informational note that a file isn't in the blueprint, suggest `archie refresh --deep`.

### Stats file

`.archie/stats.jsonl` — append-only, one line per hook execution. Records: timestamp, hook type, file, rule, result (pass/warn/block/stale), action taken. Powers `archie status`. `.gitignore`d by default.

---

## Section 7: Two Entry Points

### CLI: `archie`

```bash
pip install archie
archie init .             # full analysis
archie refresh            # local-only refresh (free, instant)
archie refresh --deep     # targeted agent refresh
archie status             # dashboard
archie rules              # list rules with severity
archie promote <rule-id>  # warn → error
archie demote <rule-id>   # error → warn
```

`archie init .` does everything: local engine → subagent analysis → render outputs → install hooks → print status. After init, hooks handle enforcement automatically.

### Claude Code skills

```
/archie-init              # same as archie init . but interactive
/archie-refresh           # targeted refresh, developer can guide
/archie-status            # inline status
/archie-rules             # list and manage rules
```

Skill advantage: developer can watch, intervene, guide. CLI advantage: headless, scriptable, CI-compatible.

### Installed file structure

```
project/
├── .archie/
│   ├── blueprint.json          # structured blueprint (source of truth)
│   ├── rules.json              # extracted enforcement rules
│   ├── stats.jsonl             # hook execution log
│   └── scan.json               # latest local engine output
├── .claude/
│   ├── hooks/
│   │   ├── pre-validate.sh     # PreToolUse enforcement
│   │   └── inject-context.sh   # UserPromptSubmit context injection
│   ├── settings.local.json     # hook registration
│   └── rules/                  # Claude Code rule files
├── .cursor/
│   └── rules/                  # Cursor rule files
├── CLAUDE.md                   # root architecture context
├── AGENTS.md                   # multi-agent guidance
└── .mcp.json                   # MCP server config (optional)
```

---

## Section 8: Migration From Current Archie

### Stays unchanged

- `StructuredBlueprint` Pydantic model (schema v2.0.0)
- `blueprint_renderer.py` (deterministic JSON→Markdown)
- `agent_file_generator.py` (generates CLAUDE.md, Cursor rules, AGENTS.md)
- MCP tools (optional, reads from `.archie/blueprint.json`)
- Delivery pipeline (for team use — push to GitHub repos)

### Removed

- Direct Claude API calls (`phased_blueprint_generator.py`)
- Docker + PostgreSQL + Redis requirement
- Supabase/pgvector for embeddings
- Web UI as entry point (becomes optional `archie dashboard`)
- `ANTHROPIC_API_KEY` as a requirement
- Background workers (ARQ, orchestrator, analysis_worker)
- FastAPI server for core analysis

### Transformed

- 7-9 phase API pipeline → local engine (70%) + 2-4 Sonnet subagents (30%)
- `analysis_service.py` → Opus coordinator prompt + local engine
- RAG retrieval → subagents read files directly, guided by import graph
- `smart_refresh_service.py` → three-level freshness system
- `intent_layer_service.py` → subagent task for per-directory context
- MCP server as primary enforcement → hooks as primary, MCP optional

### New

- Local analysis engine (AST, import graph, dependency detection, file hashing)
- `.claude/hooks/` (enforcement + context injection)
- `.archie/rules.json` (extracted rules with severity)
- `.archie/stats.jsonl` (observability log)
- `archie` CLI commands (init, refresh, status, rules, promote, demote)
- `/archie-*` Claude Code skills
- Git hook integration for auto local refresh

### New repo structure

```
archie/                    # pip-installable Python package
├── cli/                   # CLI commands
├── engine/                # local analysis engine
├── coordinator/           # Opus prompt templates + subagent instructions
├── renderer/              # from current blueprint_renderer + agent_file_generator
├── hooks/                 # hook script templates
├── schema/                # StructuredBlueprint Pydantic model
├── skills/                # Claude Code skill definitions
└── mcp/                   # optional MCP server
```

Current `backend/` + `frontend/` becomes optional `archie dashboard` for teams.

---

## Section 9: Testing Strategy

Principle: **if it can't be tested without an LLM, it's designed wrong.**

### Local Engine — Unit Tests (100% coverage target)

Pure Python, deterministic. Standard pytest.

- File tree scanner — temp directory fixtures, assert structure detection
- Dependency parser — feed package files, assert parsed output
- Import graph builder — feed source files with imports, assert graph edges
- Framework detector — feed file tree + deps, assert signals
- Token counter — deterministic with tiktoken
- File hasher — SHA256, deterministic
- Raw scan assembler — integration of all sub-components

### Enforcement Hooks — Unit Tests (100% coverage target)

Read JSON, make local decisions. Fully testable.

- File placement check — file path + blueprint → pass/warn/error
- Naming convention check — name + rules → result
- Cross-layer import check — imports + layer boundaries → result
- Technology stack check — new import + technology section → result
- Context injection matching — user prompt + blueprint → injected sections
- Severity resolution — rule id + rules.json → warn/error
- Override handling — blocked → user approves → pass on retry
- Stale detection — file hashes vs blueprint → stale file list
- Fail-open behavior — missing/corrupt blueprint → no block (exit 0)

### Rule Extraction — Unit Tests

- Blueprint → rules.json extraction
- Rule promotion/demotion
- Rule catalog completeness (all checkable patterns produce rules)

### Agent Coordination — Integration Tests (mocked subagents)

Test orchestration without LLM calls. Subagent responses are JSON fixtures.

- Subagent planning — raw scan → file group assignments
- Token budget enforcement — no group exceeds limit
- Module-aware grouping — related files stay together
- Blueprint merge — multiple partial blueprints → one valid whole
- Schema validation — malformed output → rejection + retry
- Small repo handling — few files → single subagent

### CLI Commands — Integration Tests

- `archie init .` against test repo → all files created
- `archie refresh` after modification → blueprint updated
- `archie status` against known state → correct output
- `archie rules` against known rules.json → correct listing
- `archie promote` → rules.json updated

### End-to-End Tests (gated, manual, pre-release only)

Real Claude Code subagents, real repos. Expensive — run before releases only.

- Full `archie init` on test repo
- Hook enforcement on real edits
- Freshness cycle (init → modify → refresh → deep refresh)
- Skill invocation in real Claude Code session

### Testing Pyramid

```
        ╱╲
       ╱  ╲       E2E: real repos, real subagents (4%)
      ╱    ╲      manual, pre-release
     ╱──────╲
    ╱        ╲     Integration: CLI, coordination (12%)
   ╱          ╲    mocked subagents, CI on every PR
  ╱────────────╲
 ╱              ╲   Unit: engine, hooks, rules, renderer (84%)
╱────────────────╲  CI on every commit
```

---

## Research References

This design was informed by publicly observable patterns from:

- **Cartographer** (kingbootoshi/cartographer) — orchestrator/subagent coordination concept, parallel spawning, token budgeting. No code was or will be copied.
- **Rippletide** (rippletideco/rippletide) — Claude Code hook enforcement concept, UserPromptSubmit/PreToolUse pattern, conversational overrides. No code was or will be copied.
- **ETH Zurich study (Feb 2026)** — LLM-generated context files reduce success by 3%; non-inferable details (decisions, conventions) are valuable.
- **Architect MCP** — 80% pattern compliance with runtime tools vs 30-40% with docs alone.
- **MCP ecosystem data** — 97M+ monthly SDK downloads, 6,400+ servers.

See `docs/BRAINSTORM.md` for full market data and competitive analysis.

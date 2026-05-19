# Archie — AI Governance for Coding Agents

[![npm version](https://img.shields.io/npm/v/@bitraptors/archie)](https://www.npmjs.com/package/@bitraptors/archie)
[![GitHub release](https://img.shields.io/github/v/release/BitRaptors/Archie)](https://github.com/BitRaptors/Archie/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Your AI agent is fast on day 1. By week 3, it's putting files in the wrong layer, re-implementing helpers that already exist, and quietly drifting from the architecture you carefully explained at the start. The codebase erodes; the speed advantage fades.

Archie scans your repo, builds a structured blueprint of decisions and pitfalls, and installs coding-agent hooks that block edits violating it. CLAUDE.md and AGENTS.md (root plus per-folder) load the architecture passively at session start; pre-tool-use hooks are the active gate at edit time — when the agent tries to write a file that violates a decision, the hook exits with the rule plus the architectural reason, and the agent retries.

Works with any language. Zero runtime dependencies for standalone scripts.

**Coding-agent harness support:** Archie targets three CLIs through a single connector framework:

| Harness | Status | How it integrates |
|---|---|---|
| **Claude Code** (Anthropic) | **stable** — primary target | `.claude/commands/*.md` shims, `.claude/settings.local.json` hooks, modular skill subtree |
| [**OpenAI Codex CLI**](https://developers.openai.com/codex/cli) | **beta** | `.agents/skills/*/SKILL.md` shims, `.codex/hooks.json` with absolute paths, `.codex/agents/*.toml` named sub-agents, idempotent `~/.codex/config.toml` patch |
| [**Pi**](https://pi.dev) | **beta** | `.pi/skills/*/SKILL.md` shims, `.pi/extensions/archie-hooks.ts` (TS extension wrapping the canonical shell scripts), RPC parallel adapter with sequential fallback |

All three CLIs read identical Archie outputs (blueprint, rules, per-folder context) and run the same Python analysis pipeline. The same canonical hook scripts at `.archie/hooks/` power in-session enforcement in every CLI — one source of truth. See "Multi-CLI install" below.

## Install

```bash
npx @bitraptors/archie /path/to/your/project
```

![archie-scan demo](docs/assets/archie-scan-demo.gif)

The installer pops up an interactive multi-select picker showing which coding-agent CLIs were detected on your machine — Claude Code, OpenAI Codex CLI, Pi — with all three pre-selected. Hit `enter` to install for all of them (recommended), or `space` to deselect anything you don't want. The installer then copies Archie's standalone scripts, the canonical SKILL bodies / hook scripts, and the `/archie-deep-scan` Claude-modular skill subtree into your project; writes per-CLI shims for each picked target (slash commands for Claude, SKILL.md files for Codex/Pi, hook bindings, named sub-agent TOMLs for Codex, TS extension for Pi); patches Codex's `~/.codex/config.toml` (raises the per-folder context byte cap + adds `CLAUDE.md` to its fallback list — non-destructive merge); builds the local viewer bundle (one-time, ~45s — cached by version); delivers `.archieignore` + `.archiebulk` (pattern files for scanning); and sets up `.gitignore` entries (installed tooling is gitignored, outputs are not). Open your project in any of the picked CLIs — the first Archie command you run asks once whether to share anonymous usage telemetry (opt-in).

The installer performs a clean install — it removes old scripts, hooks, and commands before installing fresh versions, so upgrades are safe to run in-place.

**Options:**
```bash
npx @bitraptors/archie /path/to/project --target=all       # skip the picker, force all 3 CLIs
npx @bitraptors/archie /path/to/project --target=auto      # only the CLIs detected on this machine
npx @bitraptors/archie /path/to/project --target=claude    # only Claude (or codex / pi / claude,codex etc.)
```
The picker is shown only in a real terminal. Non-TTY stdin (CI, scripts) skips the prompt and defaults to `--target=all` for consistency with the interactive default. Pass `--target=…` to override.

## Multi-CLI install (Claude + Codex + Pi)

> **Status:** Claude Code is the stable, primary supported harness. **Codex CLI and Pi are in BETA** — the connector architecture is in place and end-to-end installs work, but some edge cases (Codex's interactive hook-trust gate, Pi RPC parallel deep-scan wall-clock against real provider quota) have not been validated against every provider/session configuration. Production use on Claude Code is recommended; treat Codex and Pi as preview.

Archie ships a connector-based install loop that targets all three CLIs from one command. Each CLI gets shims in its native idiom — Claude reads `.claude/commands/*.md`, Codex parent-walks `.agents/skills/*/SKILL.md`, Pi reads `.pi/skills/*/SKILL.md` and loads a TS extension at `.pi/extensions/archie-hooks.ts` — but they all reference the same canonical bodies at `.archie/prompts/` and invoke the same canonical hook scripts at `.archie/hooks/`. One install, one source of truth.

```bash
# npx — recommended. Bundles .archie/ scripts + viewer AND auto-detects every
# installed CLI under ~/.claude, ~/.codex, ~/.pi/agent and writes shims for each.
npx @bitraptors/archie /path/to/project

# pip alternative — installs the archie-cli Python package, then runs the
# connector-based install loop directly.
pip install archie-cli
python3 -m archie.install /path/to/project [--target=auto|claude|codex|pi|all]
```

Both paths run the **same Python connector loop** under the hood — `npx` invokes it (via `python3 -m _install_pkg.install`) after copying the bundled scripts; `python3 -m archie.install` runs it from the pip-installed package. The connector code (`archie/connectors/*.py`) is the single source of truth. The `--target` flag accepts `auto` (detects each CLI's home directory), `all` (force every supported CLI), or a comma-separated subset.

**Interactive multi-select.** When `npx @bitraptors/archie` runs in a terminal, it shows a checkbox picker with each CLI pre-selected. Default is **all three** — use `↑/↓` to navigate, `space` to toggle, `a` to toggle all, `enter` to confirm, `ctrl-c` to cancel:

```
  Pick coding-agent CLIs to install Archie for:
  ↑/↓ navigate · space toggles · a toggles all · enter confirms · ctrl-c cancels

    ❯ [✓] Claude Code      detected      stable
      [✓] Codex CLI         detected      beta
      [✓] Pi       not detected  beta
```

Press `enter` immediately to install for all 3. Or `space` to deselect anything you don't want. Pipe a non-TTY stdin (CI, scripts) and the prompt is skipped — the default is **all 3** in both interactive and non-TTY modes (consistent behavior). Pass `--target=…` to override with a specific value (`auto` for detected-only, `claude,codex` for a subset, etc.).

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) → "Multi-Agent Connector Architecture" for the internal design.

## Commands

| Command | What it does | Time |
|---------|-------------|------|
| `/archie-scan` | Architecture health check. Runs deterministic scanner for data, then AI analyzes the architecture like a senior architect: finds dependency violations, pattern drift, complexity hotspots, proposes enforceable rules. Writes concrete problems to `.archie/findings.json` (a shared 4-field store). Each scan builds on prior knowledge — recurring findings bump a `confirmed_in_scan` counter, resolved ones flip `status`, new ones get fresh ids. | 1-3 min |
| `/archie-deep-scan` | Comprehensive architecture baseline. Full 2-wave multi-agent analysis (3-4 Sonnet agents + Opus reasoning) producing blueprint, optional per-folder CLAUDE.md, rules, findings, pitfalls, and health metrics. Wave 2 upgrades scan-triage drafts to canonical and emits class-of-problem pitfalls. Intent Layer (per-folder enrichment) is opt-in via an interactive prompt. Supports `--incremental`, `--continue`, and `--from N`. | 15-20 min |
| `/archie-intent-layer` | Standalone per-folder CLAUDE.md regeneration. Use when you skipped Intent Layer during deep-scan or need to refresh after structural changes. Asks Full / Incremental / Auto upfront and shares its pipeline with deep-scan's Step 7 (single source of truth). Hard-requires `blueprint.json` — tells you to run `/archie-deep-scan` first if missing. | 3-15 min |
| `/archie-share` | Upload a blueprint + findings + scan report to a hosted viewer for teammates to review. Returns a shareable URL. Three modes: **default** (BitRaptors Supabase, one-click), **enterprise — stored credentials** (BYO S3 bucket, set up once), **enterprise — paste URL** (per-share presigned PUT URL, zero credentials on disk). In enterprise modes, BitRaptors stores nothing — blueprints land directly in your bucket and the viewer fetches from there via a URL fragment. | seconds |

Run `/archie-deep-scan` once to establish a baseline. Then use `/archie-scan` for ongoing checks — each scan compounds on previous knowledge. Use `/archie-share` to hand a snapshot to anyone with a browser.

`/archie-deep-scan` is implemented as a modular Claude Code skill (`.claude/skills/archie-deep-scan/`) — a thin router plus self-contained per-step files — so the long pipeline survives `/compact` and can resume mid-run via `--continue` / `--from N`.

There is also `/archie-viewer` for interactive local blueprint inspection. It runs the **same React UI as the hosted share viewer**, served locally from `viewer.py` at `localhost:5847/local` — no upload, all data stays on your machine. Two tabs: **Blueprint** (the full report — health scores, architecture diagram, decisions, findings, pitfalls, plus inline rule adopt/reject/edit) and **Files** (per-folder CLAUDE.md browser + a click-to-view tree of every generated file). It renders whatever's in `.archie/`, so it works right after `/archie-scan`; deep-scan-only sections just render sparse.

### `/archie-scan` in action

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

  Metric Legend:
  - Erosion — Files breaking expected structure. <0.3 good, 0.3-0.5 moderate, >0.5 high
  - Gini — Code distribution inequality. High = a few god-files hold most code. <0.4 good, 0.4-0.6 moderate, >0.6 high
  - Top-20% — Share of code in the largest 20% of files. <0.5 good, 0.5-0.7 moderate, >0.7 high
  - Verbosity — Comment-to-code ratio. <0.05 good, 0.05-0.15 moderate, >0.15 high
  - LOC — Total lines of code

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

  ┌─────┬───────────────────────────────────────────────────────────────────────┬──────────┬────────────┐
  │  #  │                                 Rule                                  │ Severity │ Confidence │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 1   │ scan-013: Tool entry functions must be async                          │ error    │ 0.99       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 2   │ scan-014: Tool files must init logger = logging.getLogger(__name__)   │ warn     │ 0.97       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 3   │ scan-015: Feature components use PascalCase; only ui/ uses kebab-case │ warn     │ 0.82       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 4   │ scan-016: ApiClient accessed only via getInstance()                   │ error    │ 0.93       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 5   │ scan-017: LangGraph steps named <verb>_<noun>_step                    │ warn     │ 0.87       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 6   │ scan-018: FastAPI dependency factories follow get_<service>()         │ warn     │ 0.90       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 7   │ scan-019: Memory services must share a base class                     │ warn     │ 0.95       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 8   │ scan-020: Date utilities centralized in dateUtils.ts only             │ warn     │ 0.90       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 9   │ scan-021: TOOL_ID constant must be named exactly TOOL_ID              │ warn     │ 0.83       │
  ├─────┼───────────────────────────────────────────────────────────────────────┼──────────┼────────────┤
  │ 10  │ scan-022: No inline Pydantic models in routers                        │ error    │ 0.91       │
  └─────┴───────────────────────────────────────────────────────────────────────┴──────────┴────────────┘

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

  ---
  Part 2: Architecture Summary

  Architecture style: Electron desktop application (frontend) + Python FastAPI backend with LangGraph-based multi-agent AI orchestration.

  Key components:
  - Electron Main Process — Window lifecycle, backend spawning, IPC, deep links, auto-updates
  - React Renderer — SPA with 7 nested Context providers, Shadcn UI, Tailwind CSS
  - API Layer — FastAPI routers for REST + WebSocket real-time communication
  - Agent System — Planner/Executor/Validator/Corrector pipeline via LangGraph state machine
  - Tool Registry — 20+ pluggable async tools (browser automation, LLM, file I/O, MCP)
  - Persistence — Local filesystem with UUID-based project directories, abstract interface
  - WebSocket Service — Unified singleton connection with ~60fps message batching

  Tech highlights: React 19, TypeScript, Tailwind v4, Electron, Python 3.12, FastAPI, LangGraph, Playwright/browser-use, multi-LLM (OpenAI, Anthropic, Google, Groq, Ollama), Supabase auth, FAISS
  vector memory.

  Key decisions:
  1. Embedded Python backend — spawned as child process by Electron for zero-config desktop deployment
  2. LangGraph for agent orchestration — plan-execute-validate-correct loop maps naturally to state machine nodes
  3. React Context + useReducer over external state libraries — seven domain-specific providers, no Redux/Zustand

  ---
  Part 3: Architecture Health Assessment

  ┌─────────────────┬───────────────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────────────────────────────────────────────┐
  │    Dimension    │                                     Frontend                                      │                                         Backend                                         │
  ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
  │ Separation of   │ Weak — Layout does data fetching, AppContext handles tool updates, compat hooks   │ Adequate — Clear module boundaries (agents/tools/services/utils) but graph nodes reach  │
  │ concerns        │ own CRUD operations, sidebar state duplicated across contexts                     │ into persistence internals for logging, and API layer imports tool-level globals        │
  ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
  │ Dependency      │ Weak — Preload exposes raw ipcRenderer allowing arbitrary channel access from     │ Weak — Utils imports from DI layer (settings_loader→dependencies.py circular import),   │
  │ direction       │ renderer; multiple components bypass ApiClient singleton with raw fetch()         │ tools import DI factories directly, API imports concrete persistence class              │
  ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
  │ Pattern         │ Adequate — Most contexts follow useReducer+typed-actions, but AuthContext uses    │ Adequate — Tool pattern is consistent across 20+ tools, but DI bypass (3 tools import   │
  │ consistency     │ plain useState; WebSocket singleton duplicated in ProjectContext                  │ from dependencies.py) and inconsistent LLM injection (validator vs corrector)           │
  ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
  │ Testability     │ Adequate — Singleton ApiClient and compatibility hooks provide test seams, but    │ Weak — Tools directly call DI factories making them untestable in isolation; validator  │
  │                 │ raw IPC access and direct fetch calls create hard-to-mock paths                   │ hardcodes LLM creation; graph nodes reach into persistence internals                    │
  ├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────┤
  │ Change impact   │ Adequate — Context providers isolate state domains; but ProjectContext is a       │ Adequate — LangGraph isolates agent concerns; but projects_router.py is monolithic, and │
  │ radius          │ monolith touching WebSocket, state mapping, artifacts, sidebar state, and project │  the persistence→logging side-channel means swapping persistence breaks logging         │
  │                 │  CRUD                                                                             │                                                                                         │
  └─────────────────┴───────────────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────┘

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

  ---
  Part 4: Architectural Drift

  Errors (must fix)

  Frontend (6 errors):
  1. Raw ipcRenderer exposed in preload — src/preload/index.ts exposes window.electron.ipcRenderer passthrough, completely bypassing the named-operations security model
  2. useAppUpdater bypasses preload bridge — Uses raw ipcRenderer.on('update-checking') instead of dedicated named methods
  3. main.tsx bypasses preload bridge — Uses raw ipcRenderer.send('read-file-request') instead of window.electron.readFile
  4. AuthContext uses useState — Only context provider not following useReducer+typed-actions pattern
  5. WebSocket stale closure — ProjectContext WebSocket useEffect has [] deps, all handlers read initial empty state forever
  6. Raw fetch() in loadArtifacts — ProjectContext constructs manual fetch() bypassing ApiClient singleton

  Backend (8 errors):
  1. Duplicate startup_event handlers — Two @app.on_event('startup') with same name; session cleanup silently dropped
  2. tool_browser_use.py imports from DI — Directly calls get_browser_session_manager() instead of receiving via kwargs
  3. tool_start_login_session.py imports from DI — Same bypass, two DI factories called directly
  4. settings_loader imports from dependencies — Creates circular import by importing upward from utils→DI layer
  5. Duplicate placeholder resolver — executor.py contains full copy of _resolve_placeholders_recursive() alongside canonical version
  6. API key logged in plaintext — dependencies.py:174 logs raw API key on every startup
  7. LoggingService accessed via side-channel — All graph nodes do getattr(persistence_manager, 'logging_service', None) instead of proper AgentState field
  8. Validator hardcodes LLM creation — _validate_with_llm() calls get_llm_client_for_tool() directly, unlike corrector which correctly accepts BaseChatModel

  Warnings (should fix)

  Frontend (8 warnings): Dual WebSocketMappingService instances, duplicated sidebar state, AppContext tool-update leak, compat hook CRUD responsibility leak, useBackendHealth raw fetch, Layout data
  orchestration, main process monolith (260-line reveal-in-finder), startup cache-clear dependency.

  Backend (6 warnings): Sync file I/O in async graph nodes, tool_llm direct WebSocket access, aioconsole stdin in server process, corrector force-completes failed tasks at 0.85 confidence,
  projects_router imports from tool layer, executions_router imports concrete persistence class.

  ---
  Part 5: Top Risks & Recommendations

  1. IPC Security Hole (Frontend) — The raw ipcRenderer passthrough in src/preload/index.ts makes the named-operations preload bridge meaningless. Any renderer code can invoke arbitrary IPC
  channels. Action: Remove the ipcRenderer passthrough and add dedicated named methods for each IPC operation.
  2. API Key Exposure (Backend) — src/dependencies.py:174 logs the full OpenAI API key to the log file on every cold start. This is a security vulnerability actively being triggered. Action: Remove
  or mask the log line immediately.
  3. Stale WebSocket State (Frontend) — ProjectContext's WebSocket handlers close over initial empty state, meaning all real-time mapping computations use stale data. This is a correctness bug
  affecting every WebSocket message for the lifetime of the app. Action: Use refs or functional dispatch to avoid stale closures.
  4. Circular Dependencies & Layer Violations (Backend) — settings_loader.py ↔ dependencies.py circular import, tools importing from DI layer, graph nodes reaching into persistence internals. These
  create a fragile dependency web that will break if any layer is swapped. Action: Inject LoggingService via AgentState, pass dependencies to tools via kwargs.
  5. Duplicate Startup Handler (Backend) — Two startup_event functions with the same name means session cleanup never runs. Action: Rename the second handler to startup_mcp_event or merge into a
  single handler.

  ---
  Part 6: Semantic Duplication

  ┌─────┬──────────────────────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────┬──────────────────────────────────────────────┐
  │  #  │                                Canonical                                 │                          Duplicate                           │                  Difference                  │
  ├─────┼──────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ 1   │ src/utils/placeholder_resolver.py:resolve_placeholders_recursive()       │ src/agents/executor.py:_resolve_placeholders_recursive()     │ Full logic duplicate with private prefix;    │
  │     │                                                                          │                                                              │ same signature and recursive structure       │
  ├─────┼──────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │     │ Module-level webSocketMappingService singleton (imported from            │ useMemo(() => new WebSocketMappingService(), []) in          │ Two independent instances of the same        │
  │ 2   │ LogMappingService)                                                       │ ProjectContext                                               │ service class, one shadows the other's       │
  │     │                                                                          │                                                              │ import                                       │
  ├─────┼──────────────────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ 3   │ AppContext.ui.isLeftSidebarOpen/isRightSidebarOpen                       │ ProjectContext.ui.isLeftSidebarOpen/isRightSidebarOpen       │ Same state tracked in two contexts with      │
  │     │                                                                          │                                                              │ separate action dispatchers, no sync         │
  └─────┴──────────────────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────┴──────────────────────────────────────────────┘

  Recommendation: Consolidate placeholder resolver to single canonical version. Use the module-level WebSocketMappingService singleton consistently. Move sidebar state to a single context owner.

  ┌──────────────────────┬────────────────────────────┐
  │        Metric        │           Value            │
  ├──────────────────────┼────────────────────────────┤
  │ Semantic duplication │ 3 groups found (see above) │
  └──────────────────────┴────────────────────────────┘

  ---
  Archie is now active. Architecture rules will be enforced on every code change. Run /archie-scan for fast health checks. Run /archie-deep-scan --incremental after code changes to update the
  architecture analysis.
```

</details>

### Deep Scan Advanced Modes

| Flag | What it does |
|------|-------------|
| `--incremental` | Only process files changed since last deep scan (3-6 min vs 15-20 min) |
| `--continue` | Resume from where the last run stopped (handles interruptions) |
| `--from N` | Resume from a specific step N (steps 1-9) |
| `--reconfigure` | Re-prompt for monorepo scope config (whole/per-package/hybrid/single) |

### Monorepo Support

Both scan commands auto-detect sub-projects (via Gradle, package.json, Cargo.toml, pyproject.toml, etc.). On the first run for a monorepo they present an interactive single-choice picker:

- **Whole** — one unified blueprint treating the monorepo as one product
- **Per-package** — one blueprint per workspace you pick
- **Hybrid** — whole blueprint at root + per-workspace blueprints for specific workspaces
- **Single** — ignore the workspaces and scan as one tree (small monorepos only)

The choice is persisted in `.archie/archie_config.json` so it's only asked once per project. In `whole` mode, Archie additionally produces a `workspace_topology` field with inter-workspace edges, cycles, and dependency magnets.

### Ignore Patterns

Archie uses three layered pattern files to decide what the scanner sees and what agents read. Most-restrictive wins:

| File | Semantics |
|---|---|
| `.gitignore` | Not scanned at all (standard git rules, nested files supported) |
| `.archieignore` | Not scanned at all — Archie-specific exclusions on top of `.gitignore` (default covers deps, caches, build outputs, IDE files, binaries) |
| `.archiebulk` | **Scanned but opaque** — the scanner records path + `{category, framework}` metadata but never reads the contents. Default covers Android `res/`, iOS storyboards/asset catalogs, Flutter/Dart codegen, minified JS, TypeScript `.d.ts`, Go protobuf/vendor, Python protobuf/migrations, SQL migrations, lockfiles, OpenAPI codegen, and more. |

The `.archiebulk` tier gives AI agents structural inventory (e.g. "this project has 248 Android layouts across 24 screens") without burning analytical budget on reading boilerplate contents. All patterns use gitignore syntax — `**/res/layout/**` matches at any depth. Any coding agent (Claude / Codex / Pi) can edit the three files on demand.

### Enterprise Share Modes

For teams whose InfoSec policy doesn't allow uploading architecture data to third-party infrastructure, `/archie-share` supports two enterprise modes alongside the default:

- **Default** — upload to the BitRaptors Supabase share service. Existing behavior, unchanged.
- **Enterprise (stored credentials)** — `python3 .archie/share_setup.py --bucket <name> --region <r> --access-key-id AKIA… --secret-access-key …` writes `~/.archie/share-profile.json` with `chmod 600`. From then on `/archie-share` uploads directly to your S3 bucket via sigv4-signed PUT (pure Python stdlib, no boto3). Returns a viewer URL like `https://archie-viewer.vercel.app/r/ext#<base64url-encoded-presigned-GET-URL>`. **BitRaptors stores nothing** — the GET URL lives entirely in the URL fragment (which browsers never transmit to any server), and the viewer fetches the blueprint directly from your bucket client-side.
- **Enterprise (paste URL)** — no credentials stored. InfoSec mints a presigned PUT URL on demand (Lambda, script, or ticket-driven) and the dev pastes it into `/archie-share`. Archie does a plain HTTP PUT and wraps the matching GET URL into the share URL fragment. Strongest audit story at the cost of one extra step per share.

Customer-side setup walkthrough (CORS policy template, IAM policy template, step-by-step) is in [`docs/enterprise-share-setup.md`](docs/enterprise-share-setup.md) — hand it to your InfoSec team and Archie guides you through the request composition if you pick the "Help me ask InfoSec for a bucket" option during `/archie-share`.

Scope: Mode 2A (stored credentials) targets AWS S3 virtual-hosted-style URLs. S3-compatible services (R2, B2, Minio, Wasabi), Azure Blob, and GCS should use Mode 2B (paste URL) since they need different DNS shapes or signing schemes.

## What It Generates

| Output | Purpose |
|--------|---------|
| `.archie/blueprint.json` | Structured architecture data (single source of truth). Decisions, components, trade-offs, communication patterns, pitfalls (4-field shape), implementation guidelines, architecture diagram. |
| `.archie/findings.json` | Shared, compounding findings store. Each entry is `{id, problem_statement, evidence, root_cause, fix_direction, severity, confidence, applies_to, source, depth, first_seen, confirmed_in_scan, status, pitfall_id?}`. Read and written by both `/archie-scan` and `/archie-deep-scan`. |
| `.archie/rules.json` | Adopted enforcement rules (from blueprint extraction + AI-proposed scan rules + platform rules) |
| `.archie/proposed_rules.json` | AI-proposed rules pending adoption, with confidence scores |
| `.archie/health.json` | Current architecture health scores + per-function complexity snapshot |
| `.archie/health_history.json` | Timestamped health snapshots for trend analysis |
| `.archie/dependency_graph.json` | Resolved dependency graph with cycle detection |
| `.archie/semantic_duplications.json` | Near-twin / reimplementation groups found by AI analysis (deterministic writer) |
| `.archie/scan.json` | Raw scan data: file tree, import graph, framework signals, `bulk_content_manifest`, `frontend_ratio`, token counts |
| `.archie/skeletons.json` | Per-file class/function signatures + imports + first lines (efficient AI context) |
| `.archie/drift_report.json` | Mechanical drift findings (pattern outliers, dependency-direction breaches, structural anomalies) |
| `.archie/scan_report.md` | Latest prose report; every run is archived in `.archie/scan_history/scan_NNN_*.md` |
| `.archie/telemetry/*.json` | Per-run step-level wall-clock timing (for measuring changes to the pipeline) |
| `.archie/archie_config.json` | Persisted monorepo scope config (whole/per-package/hybrid/single) |
| `.archieignore` / `.archiebulk` | Scanning pattern files (merged with `.gitignore`) |
| `AGENTS.md` | Canonical agent context — architecture, decision chains, deep-links to the topic rule files |
| `CLAUDE.md` | Thin pointer to `AGENTS.md` (so Claude Code and agent-agnostic tools load the same context) |
| Per-folder `CLAUDE.md` | Directory-level context with patterns, anti-patterns, code examples (only if Intent Layer opt-in) |
| `.claude/hooks/*.sh` | Claude-deployed copies of the canonical hook scripts |
| `.claude/settings.local.json` | Claude hook bindings + 29-entry permissions allow list |
| `.claude/skills/archie-deep-scan/` | Claude-modular deep-scan skill router (Claude-specific bonus) |
| `.claude/rules/*.md` | Topic-split rule files (architecture, patterns, guidelines, pitfalls, dev-rules) + browsable `enforcement/` directory |
| `.archie/hooks/*.sh` | Canonical hook scripts (`pre-validate.sh`, `pre-commit-review.sh`, `blueprint-nudge.sh`, `post-plan-review.sh`, `post-lint.sh`, `pre-turn.sh`, `stop.sh`) — invoked by all 3 CLIs |
| `.archie/prompts/` | Canonical SKILL bodies + `_shared/` cross-CLI fragments + `codex/` and `pi/` per-CLI overrides |
| `.archie/_install_pkg/` | Bundled Python install loop (manifest, connectors, install.py) — re-run for upgrades or to install additional CLIs |
| `.agents/skills/archie-*/SKILL.md` | Codex slash-command shims (parent-walked by Codex) |
| `.codex/hooks.json` | Codex hook bindings with absolute paths and Codex-native matchers (`^apply_patch$`, etc.) |
| `.codex/agents/archie-*.toml` | Codex named sub-agents for `spawn_agents_on_csv` parallel Wave-1 fan-out |
| `.pi/skills/archie-*/SKILL.md` | Pi slash-command shims (Pi's own discovery path, isolated from Codex's) |
| `.pi/extensions/archie-hooks.ts` | Pi TS extension routing lifecycle events to canonical `.archie/hooks/*.sh` |
| `.pi/extensions/package.json` | Pi extension manifest |
| `.git/hooks/pre-commit.archie` | Universal git pre-commit gate (works regardless of which CLI is active) |
| `~/.codex/config.toml` *(patched)* | Idempotent merge: `project_doc_max_bytes = 131072` + `CLAUDE.md` in `project_doc_fallback_filenames` |

## CLI Compatibility

| Capability | Claude (stable) | Codex (beta) | Pi (beta) |
|---|---|---|---|
| 5 slash commands / skills (scan, deep-scan, intent-layer, viewer, share) | ✅ | ✅ | ✅ |
| In-session pre-edit enforcement | ✅ PreToolUse | ✅ PreToolUse `apply_patch` | ✅ TS extension on `tool_call` |
| Pre-commit-review (Bash matcher) | ✅ | ✅ | ✅ via TS extension |
| Blueprint-nudge on Glob/Grep | ✅ | ✅ | ✅ via TS extension |
| Post-tool-use, user-prompt-submit, stop hooks | ✅ | ✅ | ✅ via Pi `tool_result` / `input` / `agent_end` events |
| Parallel sub-agent fan-out (deep-scan Wave 1) | ✅ Agent tool | ✅ `spawn_agents_on_csv` | ✅ RPC parallel adapter with **automatic sequential fallback** |
| Git pre-commit gate | ✅ | ✅ | ✅ |
| Per-folder context (CLAUDE.md / AGENTS.md) | ✅ | ✅ (installer auto-patches Codex's fallback list) | ✅ |

Implementation details differ per CLI but every CLI reaches the same user-facing outcome through the same shared `.archie/` pipeline. Codex auto-patches `~/.codex/config.toml` (`project_doc_max_bytes`, `project_doc_fallback_filenames`) so per-folder context reads correctly — non-destructive merge, preserves your existing keys. Pi's TS extension is glue: it routes Pi's lifecycle events to the same `.archie/hooks/*.sh` scripts that Claude and Codex invoke directly.

## How It Works

### Deep Scan Pipeline (2-Wave)

1. **Scanner** — Deterministic local analysis: file tree, import graph, framework detection, token counting, file hashing, skeleton extraction (class/function signatures for efficient AI context), and **bulk-content classification** (files matching `.archiebulk` get tagged by category/framework and skipped from skeleton/hash/import reads). Respects `.archieignore` + `.gitignore` + `.archiebulk` layering. Pure Python, no AI. Writes `.archie/scan.json` with `bulk_content_manifest` and `frontend_ratio`.

2. **Wave 1** (parallel) — 3-4 Sonnet agents gather facts simultaneously:
   - **Structure agent** — Components, layers, file placement rules, workspace topology in monorepos
   - **Patterns agent** — Communication patterns, design patterns, integrations
   - **Technology agent** — Stack inventory, deployment config, dev rules
   - **UI Layer agent** — UI components, state management, routing (only if `frontend_ratio ≥ 0.20`)

   Each agent receives `.archie/findings.json` scoped to its `source` slice and is told to prioritise NEW problems over re-deriving known ones. Draft findings flow into the shared store as `depth: "draft"`; structural workspace observations (cross-workspace cycles, magnets) flow in as draft findings rather than free-form pitfalls.

3. **Wave 2 — Opus reasoning** — One Opus subagent reads all Wave 1 output plus the accumulated findings store, and produces the architectural synthesis:
   - **Three codebase probes** before emitting key decisions: (A) complexity-budget — where the codebase spends complexity a naive implementation wouldn't, (B) invariants & gates — self-enforced rules, (C) seams — substitution/extension points
   - **Decision chain** — rooted constraint tree with `violation_keywords` per node
   - **Key decisions** (3-7) with `forced_by` / `enables` links and alternatives_rejected
   - **Trade-offs** (3-5) with `violation_signals` (code patterns that would undo the trade-off)
   - **Findings** — upgrades scan-triage drafts in place (fills `root_cause` with architectural grounding, rewrites `fix_direction` as an ordered sequence of steps, flips `depth: "canonical"`) and emits NEW findings visible only from the whole-system view
   - **Pitfalls** — class-of-problem entries (same 4-field shape) durable across runs, linked from confirming findings via `pitfall_id`
   - **Architecture diagram** and **implementation guidelines**

4. **Finalize** — Deterministic id-stable merge of Opus output: findings into the shared store (`confirmed_in_scan += 1` on id match, new ids minted for novel entries), pitfalls into the blueprint.
5. **Rule Synthesis** (Sonnet) — Proposes new architecturally-grounded rules from the synthesised blueprint.
6. **Intent Layer** (opt-in) — Step E asks whether to generate per-folder CLAUDE.md via bottom-up DAG scheduling (leaves first, parents inherit child summaries, incremental re-generation for changed folders only). Skipping saves the bulk of the wall-clock on large projects.
7. **Drift Detection & Architectural Assessment** — Mechanical drift (pattern outliers, file-size/complexity violations, dependency-direction breaches) + deep AI drift (decision violations, pattern erosion, trade-off undermining, pitfall triggers, responsibility leaks, abstraction bypasses, semantic duplication). Writes the final scan report.
8. **Telemetry** — Every step records wall-clock; `.archie/telemetry/deep-scan_<ts>.json` captures per-step seconds + whether Intent Layer was skipped.

### Compound Learning

Every run feeds the next. Both `/archie-scan` and `/archie-deep-scan` read and write the same `findings.json` shared store:

- **Id-stable upsert.** Recurring findings reuse their existing `f_NNNN` id and bump `confirmed_in_scan`; brand-new ones get a fresh id and `first_seen` stamp; findings that no longer apply flip `status: "resolved"` (preserved as history, not deleted).
- **Novelty priority.** Agents are explicitly told to spend their cognitive budget on NEW problems, not re-describe known ones under different wording.
- **Depth escalation.** Scan emits `depth: "draft"` entries quickly (`source: scan:structure|health|patterns`, single-line `fix_direction`). Deep-scan Wave 2 upgrades the same id to `depth: "canonical"` (`source: deep:synthesis`, ordered-list `fix_direction` with architectural root_cause) and links to a parent pitfall if the problem is structural.
- **Blueprint confidence** also grows per-section with repeated confirmation across scans.
- **Health scores** appended to `health_history.json` for trend detection (improving / degrading / stable).

### Drift Detection

Deep scans include two-phase drift detection:

1. **Mechanical drift** (`drift.py`) — Detects pattern outliers, file size/complexity violations, dependency direction breaches, structural anomalies
2. **Deep AI drift** — Agent reads blueprint + drift report + CLAUDE.md files to identify: decision violations, pattern erosion, trade-off undermining, pitfall triggers, responsibility leaks, abstraction bypasses, semantic duplication

### Cycle Detection

Every scan runs Tarjan's algorithm on the import graph to find strongly connected components. Cycles are reported with file-level evidence showing which imports create each cycle.

### Real-Time Enforcement

Once installed via `npx @bitraptors/archie`, seven hooks are wired up per detected CLI (Claude uses `.claude/settings.local.json`, Codex uses `.codex/hooks.json`, Pi uses `.pi/extensions/archie-hooks.ts` — all three invoke the same canonical scripts under `.archie/hooks/`):

- **PreToolUse (Write|Edit|MultiEdit)** — `pre-validate.sh`. Two behaviors: (1) **rule injection** — prints every rule that applies to the file being edited (rules with `applies_to` prefix-matching the path, plus `always_inject: true` critical globals) with rationale, deduped per-turn; (2) **violation check** — blocks `forbidden_import`, `required_pattern`, `forbidden_content`, `architectural_constraint`, and `file_naming` violations.
- **UserPromptSubmit** — `pre-turn.sh`. Clears the per-turn rule-injection marker so applicable rules re-surface on the first write of each new user turn.
- **PreToolUse (Bash)** — `pre-commit-review.sh`. Before git commits, triggers an architectural review of the diff via `arch_review.py`.
- **PostToolUse (ExitPlanMode)** — `post-plan-review.sh`. After plan approval, triggers an architectural review of the plan.
- **PreToolUse (Glob|Grep)** — `blueprint-nudge.sh`. Reminds the agent about project architecture before code exploration.
- **PostToolUse (Write|Edit|MultiEdit)** — `post-lint.sh`. **Opt-in external linter gate**: when `.archie/enforcement.json` has `{"enabled": true}`, runs the project's native linter (ruff / eslint / golangci-lint / semgrep) on the changed file and blocks on failure. Auto-detects based on config files (`pyproject.toml [tool.ruff]`, `.eslintrc`, `.golangci.yaml`, `.semgrep.yml`) + binary on PATH. Silent no-op when config is missing.
- **Stop** — `stop.sh`. Defensive cleanup at turn end: removes the per-turn rule-injection marker (`/tmp/.archie_turn_$HASH`) so any next session starts fresh. Harmless if the marker has already been cleared by `pre-turn.sh`.

All hooks fail open: missing rules/config/marker files → hooks exit 0 silently. The Claude installer also writes a comprehensive `allow` list (29 entries) into `.claude/settings.local.json` — covering Python script execution, git / sort / head / test / wc, temp files under `/tmp/archie_*`, reads/writes under `.archie/**`, per-folder CLAUDE.md, and `Agent(*)` for subagent spawning — so the scan workflow runs without permission prompts. Codex uses its own approval modes (`workspace-write` is recommended for the scan scripts to write to `.archie/`); Pi uses its `--tools` allowlist or extension-level gates (Archie's TS extension is non-blocking on tool calls outside the rule set).

**Subagent output contract** — varies per CLI but produces the same merged outputs:
- **Claude** — every Sonnet/Opus subagent spawned via the Agent tool gets a mandatory instruction to Write its output directly to `/tmp/archie_*.json` (permissioned via `Write(//tmp/archie_*)`). The orchestrator never copies subagent transcripts, which avoids Claude Code's sensitive-file guardrail on `.claude/projects/.../subagents/*.jsonl`. Zero permission prompts during any scan.
- **Codex** — `spawn_agents_on_csv` reads `.codex/agents/archie-wave1-*.toml` (5 named sub-agents written by `CodexConnector.install_agent`) and dispatches them in parallel; workers write back via the CSV results contract the SKILL body reads.
- **Pi** — the RPC parallel deep-scan adapter (`.archie/pi_parallel_deep_scan.py`) spawns `pi --mode rpc --no-session` workers per the declarative job graph at `.archie/prompts/pi/deep_scan_jobs.json`; each worker emits JSON the adapter aggregates into the standard `.archie/blueprint.json`. Auto-falls back to running Wave-1 sequentially in the host session if any RPC worker fails.

## Rules

Rules come from two AI-synthesized sources plus a universal platform set.

1. **`/archie-deep-scan` Step 6** (Sonnet rule synthesis) — The architectural baseline. Each rule carries inline semantic content the agent reads at edit time: `severity_class` (decision_violation / pitfall_triggered / tradeoff_undermined / pattern_divergence / mechanical_violation), `description`, `why` (reasoning copy-pasted from the motivating blueprint section), `example` (canonical code shape), and `forced_by` / `enables` / `alternative` links back to the motivating decision, `source: "deep_scan"`. Mechanical rules also carry regex `check` fields. Tagged with `keywords` for prompt-time matching and `applies_to`/`always_inject` for path-scoped surfacing.

2. **`/archie-scan`** (Sonnet senior-architect pass) — Proposes new rules in the same shape (`source: "scan"`) by spotting drift in recently-changed files, or amends existing ones (`source: "scan-amended"`). Severity is inferred from the blueprint anchor; scan never promotes a rule to blocking on its own — that happens at the next deep-scan with full Wave-2 reasoning.

3. **Platform rules** (`platform_rules.json`) — 30 predefined universal checks installed with every project, categorized by concern:
   - **Erosion** — God-functions, growing complexity, monster files
   - **Decay** — Empty catches, disabled tests, TODO/HACK markers, debug breakpoints
   - **Security** — Hardcoded secrets, eval/exec, plaintext API keys in logs
   - **Architecture** — Layer violations (Android ViewModel/Context, Fragment/network, Swift view-layer networking, React components fetching data), DI anti-patterns, TypeScript `any`, React DOM manipulation, array index keys, Python mutable defaults, star imports, bare except
   - **Safety** — Python `TYPE_CHECKING` guards, Swift force unwraps / force try

The pre-edit hook (`pre-validate.sh`) reads `severity_class` to gate the response: blocking severities (`decision_violation`, `pitfall_triggered`, `mechanical_violation`) exit 2 with the agent-facing message, `tradeoff_undermined` warns (exit 0 prominent), `pattern_divergence` informs (exit 0 quiet). Old-shape rules without `severity_class`/`why`/`example` still work via `severity` + `rationale` fallbacks for backward compat. Rules can be adopted, skipped, or managed from `/archie-viewer` (Rules tab) or interactively by the coding agent during scans (works in Claude, Codex, and Pi).

The deterministic blueprint extractor was retired in v2.5.0 — Step 6's AI synthesis covers placement+naming with semantic content the extractor couldn't express. Fresh `archie init` writes an empty `rules.json`; the user runs `/archie-deep-scan` or `/archie-scan` to populate it.

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

- **Python 3.9+** for standalone scripts (installed via `npx @bitraptors/archie`, stdlib only, zero pip dependencies)
- **Node.js 18+** for `npx @bitraptors/archie` installer
- A supported coding-agent harness:
  - **Claude Code** — stable, primary target
  - **OpenAI Codex CLI** — beta
  - **Pi** — beta

  The same `archie-scan` / `archie-deep-scan` / `archie-intent-layer` / `archie-share` / `archie-viewer` commands run in all three harnesses with feature parity (subject to each harness's API ceiling — see the Multi-CLI install table above).

The scan templates use only pre-installed CLI commands — no inline Python is written during scans. Every data operation has a dedicated subcommand: `measure_health.py --append-history`, `finalize.py --normalize-only`, `intent_layer.py inspect`, `extract_output.py save-duplications`, `extract_output.py recent-files`, and so on. Agents are explicitly forbidden from `python3 -c` one-liners.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full technical documentation.

## Telemetry & update checks (anonymous, opt-in)

The first time you run an Archie command (`/archie-scan`, `/archie-deep-scan`, etc.) in any supported harness (Claude Code, Codex, or Pi), it asks once whether you'd like to share usage telemetry — a model-driven prompt in the shared `.archie/prompts/_shared/telemetry-consent.md` fragment, asked in-session rather than during `npx` install (which can run non-interactively). The consent flow works identically across all three CLIs. There are three tiers:

- **community** *(recommended)* — events include a stable random installation ID written once to `~/.archie/config.json`. Lets us see which features get used together.
- **anonymous** — same payload but the installation ID is stripped before upload. Each event is unlinkable.
- **off** — nothing leaves your machine.

**What's collected** (when telemetry is on): command name (`scan` / `deep-scan` / `viewer` / `share` / `intent-layer` / `install`), Archie version, OS / arch (`darwin` / `arm64`, etc.), per-step durations, outcome, and detected stack categories (e.g. `kotlin` / `gradle` / `android`).

**What is never collected**: source code, file paths, repo names, blueprint contents, error messages from your code. Local-only fields (e.g. `_project_basename`) are stripped before upload — they appear only in the local dashboard.

**Local data**: every event is appended to `~/.archie/analytics/runs.jsonl`. You own it, you can read it.

```bash
# See your local activity (7d / 30d / all)
python3 .archie/analytics.py 7d

# Inspect / change consent at any time
python3 .archie/config.py list
python3 .archie/config.py set telemetry off       # opt out
python3 .archie/config.py set telemetry anonymous # downgrade
python3 .archie/telemetry_sync.py status          # see pending uploads
python3 .archie/telemetry_sync.py purge           # delete local jsonl
```

**Update checks** are also opt-in via `~/.archie/config.json` (default on). Each slash command runs a fast cached check against the public npm registry — never your code. If a new version is out, the slash command surfaces a one-line hint suggesting `npx @bitraptors/archie@latest`. Snooze with `python3 .archie/update_check.py snooze` (24h → 48h → 7d ladder), or disable entirely with `python3 .archie/update_check.py disable`. The check itself uses `registry.npmjs.org` — no Archie infrastructure is involved.

The ingest endpoint is a Supabase edge function that uses an anon key + RLS-restricted insert-only policy (never the service role). Source: `share/supabase/functions/telemetry-ingest/`.

## Repository Layout

```
archie/              Python package (CLI + engine + coordinator + standalone)
  cli/               Click CLI commands (init, refresh, status, check, serve)
  engine/            Local codebase analysis (scanner, imports, frameworks)
  coordinator/       2-wave AI pipeline (planner, runner, merger, prompts)
  connectors/        Multi-agent harness adapters (base.py, claude.py, codex.py, pi.py) — one file per CLI
  hooks/             Hook generation and enforcement logic
  renderer/          Output generation (CLAUDE.md, per-folder context)
  rules/             Legacy blueprint rule extractor (retired in v2.5.0; kept for tests)
  standalone/        Zero-dependency scripts (31 files, copied to target projects) — canonical runtime path
  assets/            Canonical assets shipped to installed projects: prompts/, hook_scripts/, pi_extension/
    prompts/         5 SKILL bodies + _shared/ fragments (incl. Wave-1/2 sub-agent prompts) + codex/ + pi/ per-CLI overrides
    hook_scripts/    7 canonical .sh hooks, invoked identically by all three CLIs
    pi_extension/    TS extension template that wraps the canonical hook scripts for Pi
  manifest.py        CommandDef / HookDef / ConfigPatch / AgentDef dataclasses
  manifest_data.py   Single source of truth: 5 commands, 7 hooks, 2 config patches, 5 sub-agents
  install.py         The connector-driven install loop entry point
npm-package/         NPM distribution (npx @bitraptors/archie)
  bin/archie.mjs     Installer entry point — copies assets and delegates to the Python install loop
  assets/            Verbatim copies of canonical assets + a bundled _install_pkg/ (the Python install loop in a self-contained package the npm installer runs)
    _install_pkg/    Bundled Python install loop (byte-identical to archie/ — manifest, connectors, install.py)
share/               Blueprint sharing ecosystem
  viewer/            React/Vite app — powers both the hosted viewer (archie-viewer.vercel.app) and the local /archie-viewer sidecar
  supabase/          Edge functions (upload, blueprint, telemetry-ingest) + migrations
landing/             Landing page
tests/               Pytest suite (50 files)
docs/                Architecture documentation
scripts/             verify_sync.py — pre-commit canonical ↔ asset sync checker
.claude/commands/    Slash commands (archie-scan, archie-deep-scan, archie-intent-layer, archie-share, archie-viewer) + _shared/scope_resolution.md
.claude/skills/      archie-deep-scan/ — the deep-scan skill (SKILL.md router + per-step files + fragments + templates)
v1/                  Archived V1 web app (FastAPI + Next.js, obsolete)
```

## Kudos for Inspiration

- **[Cartographer](https://github.com/kingbootoshi/cartographer)** by [@kingbootoshi](https://github.com/kingbootoshi)
- **[Graphify](https://github.com/safishamsi/graphify)** by [@safishamsi](https://github.com/safishamsi)
- **[SlopCodeBench](https://arxiv.org/abs/2603.24755)**

## License

MIT

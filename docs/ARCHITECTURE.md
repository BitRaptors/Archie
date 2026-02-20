# Architecture Blueprints — Developer Documentation

Comprehensive technical documentation covering system architecture, analysis pipeline internals, API reference, database schema, MCP server, delivery pipeline, and contribution guidelines.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Backend Architecture](#backend-architecture)
5. [Analysis Pipeline](#analysis-pipeline)
6. [Web vs Mobile Platform Handling](#web-vs-mobile-platform-handling)
7. [StructuredBlueprint Data Model](#structuredblueprint-data-model)
8. [MCP Server](#mcp-server)
9. [Delivery Pipeline](#delivery-pipeline)
10. [API Reference](#api-reference)
11. [Database Schema](#database-schema)
12. [Frontend (Web UI)](#frontend-web-ui)
13. [Configuration](#configuration)
14. [Testing](#testing)
15. [Extending the System](#extending-the-system)

---

## System Overview

Architecture Blueprints is a monorepo with two services:

- **Backend** — Python FastAPI application following Clean Architecture (DDD layers). Handles repository analysis, blueprint generation, MCP server, and delivery.
- **Frontend** — Next.js 14 application for managing analyses, viewing blueprints, and triggering delivery.

The core workflow:

1. User submits a GitHub repository URL
2. Backend clones the repo, extracts structural data, and runs a multi-phase AI analysis using Claude
3. Analysis produces a `StructuredBlueprint` — a Pydantic model that is the single source of truth
4. All outputs (CLAUDE.md, Cursor rules, AGENTS.md, MCP tool responses) derive deterministically from this blueprint
5. The delivery pipeline pushes these outputs to the target repository via GitHub API

---

## Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web framework | FastAPI + Uvicorn | Async HTTP server with OpenAPI docs |
| Language | Python 3.11+ | Type hints, async/await |
| Data models | Pydantic v2 | Schema validation, serialization |
| Dependency injection | dependency-injector | Constructor injection via declarative container |
| Database | Supabase (PostgreSQL) | Persistence for repos, analyses, blueprints, rules |
| Vector search | pgvector | Semantic similarity search on code embeddings |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | 384-dimensional code chunk embeddings |
| AI | Anthropic Claude API | Multi-phase architecture analysis |
| Code parsing | tree-sitter (Python, JS, TS grammars) | AST-based code chunking |
| GitHub API | PyGithub | Repository cloning, file reads, branch/PR creation |
| Task queue | ARQ (Redis-backed, optional) | Background analysis jobs (falls back to in-process without Redis) |
| MCP | mcp SDK + sse-starlette | Model Context Protocol server over SSE |
| Storage | Local filesystem (default), GCS, S3 | Blueprint and temp file storage |
| Linting | Ruff | Fast Python linter and formatter |
| Testing | pytest + pytest-asyncio | Unit and integration tests |

### Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Next.js 14 (Pages Router) | SSR/SSG React framework |
| Language | TypeScript | Type safety |
| Styling | Tailwind CSS | Utility-first CSS |
| State | React Query (@tanstack/react-query) | Server state management |
| HTTP | Axios | API client |
| Markdown | react-markdown + remark-gfm | Blueprint rendering |

### Infrastructure

| Component | Technology |
|-----------|-----------|
| Database hosting | Supabase (managed PostgreSQL) |
| Cache/Queue | Redis (optional) |
| Hosting | Any platform supporting Python + Node.js |

---

## Project Structure

```
architecture-blueprints/
├── backend/
│   ├── src/
│   │   ├── api/                          # HTTP layer
│   │   │   ├── app.py                    # FastAPI app factory, route registration
│   │   │   ├── middleware/               # Auth, CORS, error handling
│   │   │   ├── routes/                   # Route modules (9 registered + 1 unused)
│   │   │   │   ├── analyses.py           # Analysis CRUD + streaming
│   │   │   │   ├── repositories.py       # Repository management + analyze trigger
│   │   │   │   ├── delivery.py           # Preview + apply delivery
│   │   │   │   ├── architecture.py       # Architecture rules + validation (not registered)
│   │   │   │   ├── auth.py               # GitHub token auth
│   │   │   │   ├── workspace.py          # Workspace management
│   │   │   │   ├── prompts.py            # Prompt CRUD + revision history
│   │   │   │   ├── settings.py           # Analysis settings (ignored dirs, library capabilities)
│   │   │   │   ├── health.py             # Health check
│   │   │   │   └── mcp.py               # MCP SSE endpoint mount
│   │   │   └── dto/                      # Request/response schemas
│   │   ├── application/                  # Business logic layer
│   │   │   ├── services/                 # Service classes
│   │   │   │   ├── analysis_service.py           # Main orchestrator
│   │   │   │   ├── phased_blueprint_generator.py # Multi-phase AI pipeline
│   │   │   │   ├── blueprint_renderer.py         # JSON → Markdown renderer
│   │   │   │   ├── agent_file_generator.py       # CLAUDE.md, Cursor rules, AGENTS.md
│   │   │   │   ├── delivery_service.py           # GitHub delivery + merge logic
│   │   │   │   ├── analysis_data_collector.py    # Phase data persistence
│   │   │   │   └── ...
│   │   │   └── agents/                   # Background workers
│   │   │       ├── orchestrator.py       # Coordinates workers
│   │   │       ├── analysis_worker.py    # Runs analysis pipeline
│   │   │       ├── sync_worker.py        # Blueprint sync
│   │   │       └── validation_worker.py  # Code validation
│   │   ├── workers/                      # ARQ task queue (Redis-backed)
│   │   │   ├── worker.py                # Entry point (Python 3.14+ compatible)
│   │   │   └── tasks.py                 # Task definitions, WorkerSettings, startup/shutdown
│   │   ├── domain/                       # Domain layer
│   │   │   ├── entities/                 # Pydantic models
│   │   │   │   ├── blueprint.py          # StructuredBlueprint (central model)
│   │   │   │   └── ...
│   │   │   ├── interfaces/              # Repository interfaces (ports)
│   │   │   └── exceptions/              # Domain exceptions
│   │   ├── infrastructure/              # Infrastructure layer
│   │   │   ├── persistence/             # Supabase repository implementations
│   │   │   ├── analysis/                # RAG retriever, AST parser, embeddings
│   │   │   ├── mcp/                     # MCP server, tools, resources
│   │   │   ├── external/               # GitHub push client
│   │   │   ├── prompts/                # Prompt loader
│   │   │   └── storage/                # Local/GCS/S3 adapters
│   │   ├── config/
│   │   │   ├── settings.py             # Pydantic settings from .env.local
│   │   │   └── container.py            # DI container
│   │   └── main.py                     # Entry point
│   ├── migrations/                     # Database migrations (single initial setup)
│   ├── prompts.json                    # All AI prompts (~38KB)
│   ├── requirements.txt
│   └── tests/
│       └── unit/
│           ├── services/               # Service tests (165+)
│           └── infrastructure/         # Infrastructure tests (200+)
├── frontend/
│   ├── pages/                          # Next.js pages
│   │   ├── index.tsx                   # Dashboard
│   │   ├── auth.tsx                    # Authentication
│   │   ├── workspace.tsx               # Workspace management
│   │   ├── analysis/[id].tsx           # Analysis progress (SSE streaming)
│   │   └── blueprint/[id].tsx          # Blueprint viewer (tabbed)
│   ├── components/
│   │   ├── DeliveryPanel.tsx           # Delivery UI
│   │   └── DebugView.tsx               # Debug info
│   ├── context/                        # React context providers
│   ├── hooks/                          # Custom hooks
│   └── package.json
├── docs/
│   └── ARCHITECTURE.md                 # This file
├── docker-compose.yml                  # PostgreSQL (pgvector) + Redis containers
├── README.md                           # Project overview
├── setup.sh                            # One-time setup: prerequisites, Docker, env files, dependencies
├── start-dev.sh                        # Linux/Mac startup script
├── start-dev.py                        # Cross-platform startup script
└── start-dev.bat                       # Windows startup script
```

---

## Backend Architecture

The backend follows **Clean Architecture** with four layers. Dependencies point inward: infrastructure → application → domain.

```
┌──────────────────────────────────────────────────────────┐
│                        API Layer                          │
│  FastAPI routes, DTOs, middleware                         │
│  Depends on: Application                                 │
├──────────────────────────────────────────────────────────┤
│                    Application Layer                      │
│  Services (business logic), Agents (workers)             │
│  Depends on: Domain                                      │
├──────────────────────────────────────────────────────────┤
│                      Domain Layer                         │
│  Entities (Pydantic models), Interfaces, Exceptions      │
│  Depends on: nothing                                     │
├──────────────────────────────────────────────────────────┤
│                  Infrastructure Layer                     │
│  Supabase repos, RAG, MCP server, GitHub client,         │
│  storage adapters, prompt loader                         │
│  Implements: Domain interfaces                           │
└──────────────────────────────────────────────────────────┘
```

### Dependency Injection

All wiring happens in `config/container.py` using the `dependency-injector` library:

```python
class Container(DeclarativeContainer):
    settings = Singleton(get_settings)
    storage = Singleton(LocalStorage, base_path=settings.storage_path)
    supabase_client = Resource(_create_supabase_client, ...)
    analysis_service = Singleton(AnalysisService, storage=storage, ...)
    delivery_service = Singleton(DeliveryService, storage=storage)
```

Services receive all dependencies through constructor injection. No service instantiates its own dependencies.

### Key Patterns

- **Repository pattern** — Domain interfaces in `domain/interfaces/`, Supabase implementations in `infrastructure/persistence/`
- **RAG fallback** — If RAG indexing fails or Supabase is unavailable, analysis falls back to static code samples
- **Analysis data collector** — Shared singleton that persists per-phase analysis data to Supabase, initialized on app startup
- **Frontend auto-detection** — `_detect_frontend()` checks 31 indicators covering web frameworks (React, Vue, Angular, Svelte, etc.), iOS (SwiftUI, UIKit, .storyboard, .xcodeproj, Podfile, viewcontroller), Android (Jetpack Compose, build.gradle, AndroidManifest), cross-platform (Flutter, React Native, Expo), and file patterns (.tsx, .jsx, .swift, .kt). Branches to unified synthesis when found

### Background Task Execution (ARQ vs In-Process)

Analysis runs as a background task. The system supports two execution modes, selected automatically at runtime:

```
┌─────────────────────────────────────────────────────────────────┐
│                   POST /{owner}/{repo}/analyze                   │
│                   (api/routes/repositories.py)                   │
├─────────────────────────────────────────────────────────────────┤
│  1. Create Analysis entity (status: pending → in_progress)       │
│  2. Resolve arq_pool from container                             │
├──────────────────────┬──────────────────────────────────────────┤
│  arq_pool != None    │  arq_pool == None                        │
│  (Redis available)   │  (no Redis)                              │
├──────────────────────┼──────────────────────────────────────────┤
│  arq_pool.enqueue_   │  asyncio.create_task(                    │
│  job("analyze_       │    _run_in_process()                     │
│  repository", ...)   │  )                                       │
├──────────────────────┼──────────────────────────────────────────┤
│  ARQ Worker picks    │  Runs directly in the                    │
│  up job from Redis   │  FastAPI event loop                      │
├──────────────────────┴──────────────────────────────────────────┤
│            Both paths call analysis_service.run_analysis()       │
└─────────────────────────────────────────────────────────────────┘
```

#### Mode 1: ARQ Worker (with Redis)

When Redis is available, analysis runs in a separate ARQ worker process:

- **Entry point:** `workers/worker.py` → calls `arq.run_worker(WorkerSettings)`
- **Task definitions:** `workers/tasks.py` defines `WorkerSettings`, `startup()`, `shutdown()`, and `analyze_repository()` task
- **Startup:** `start-dev.sh` checks Redis availability and launches the worker via `python -m workers.worker`
- **Lifecycle:** Worker `startup()` initializes a full DI container, resolves Supabase client, creates all services, and stores them in the ARQ context dict. `shutdown()` cleans up container resources.
- **Python 3.14+ compatibility:** `worker.py` ensures an event loop exists before calling `run_worker()`, because Python 3.14 removed automatic event loop creation in `asyncio.get_event_loop()`

#### Mode 2: In-Process (without Redis)

When Redis is unavailable, analysis runs directly in the FastAPI process:

- **Fallback detection:** `Container._create_arq_pool()` attempts to connect to Redis with a 2-second timeout and 1 retry. If it fails, it returns `None` and prints a warning.
- **Execution:** The route handler creates an `asyncio.create_task()` that clones the repo and calls `analysis_service.run_analysis()` directly
- **Error handling:** Both paths wrap the analysis in try/except and mark the `Analysis` entity as failed if an error occurs

#### Key Files

| File | Role |
|------|------|
| `config/container.py` | `_create_arq_pool()` — connects to Redis or returns `None` |
| `api/routes/repositories.py` | `start_analysis()` — dispatches to ARQ or in-process based on `arq_pool` |
| `workers/worker.py` | ARQ worker entry point with Python 3.14 event loop fix |
| `workers/tasks.py` | `WorkerSettings`, `startup()`, `shutdown()`, `analyze_repository()` task |
| `start-dev.sh` | Checks Redis, starts worker only if available |

#### Tests

Both workflows are tested in `tests/unit/workers/test_analysis_workflows.py`:

- Worker entry point event loop compatibility (Python 3.14 simulation)
- Container ARQ pool graceful fallback (timeout, connection refused → `None`)
- Route dispatch to ARQ when pool available
- In-process fallback when pool is `None`
- Worker startup/shutdown lifecycle
- Task execution, clone failure handling, missing services detection

---

## Analysis Pipeline

The analysis pipeline is the core of the system. It turns a raw GitHub repository into a `StructuredBlueprint`.

### Pipeline Stages

#### Stage 1: Data Extraction (`analysis_service.py`)

Clones the repository and extracts:

| Data | Source | Size |
|------|--------|------|
| File tree | `structure_analyzer.py` scans all files | Compressed to ~3000 chars |
| Dependencies | `requirements.txt`, `package.json`, `pyproject.toml`, `Gemfile`, `Cargo.toml`, `go.mod`, `Podfile`, `Package.swift`, `Cartfile`, `build.gradle`, `build.gradle.kts`, `settings.gradle*` | ~1500 chars |
| Config files | `tsconfig.json`, `docker-compose.yml`, `.env.example`, etc. | ~4000 chars |
| Code samples | 10 representative files chosen by heuristics | ~5000 chars |

All gathered data is persisted to Supabase via `analysis_data_collector` with `data_type: "gathered"`.

#### Stage 2: RAG Indexing (`rag_retriever.py`) — Optional

When Supabase is available, RAG indexing enables phase-specific code retrieval:

1. **Chunking** — Each code file is split by function/class boundaries using tree-sitter AST parsing
2. **Embedding** — Each chunk is embedded using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
3. **Storage** — Vectors are stored in Supabase's pgvector extension
4. **File-level retrieval** — `retrieve_files_for_phase()` uses chunk-level search to identify relevant files, then deduplicates at the file level and returns **full file contents** (up to 3KB per file) instead of isolated fragments. This provides complete import context, class relationships, and method signatures.
5. **Phase-specific chunk type preferences** — Each phase has preferred chunk types (e.g., `layers` prefers `class` + `module`, `patterns` prefers `class` + `function`). Results matching preferred types are promoted to the top of the result set. Defined in `PHASE_CHUNK_PREFERENCES` in `rag_retriever.py`.
6. **File registry** — `get_file_registry()` returns all unique file paths indexed for a repository via `SELECT DISTINCT` on the embeddings table — no vector search needed. Used as a grounding constraint.

```sql
-- pgvector similarity search (used internally)
SELECT file_path, metadata,
       1 - (embedding <=> query_embedding) as similarity
FROM embeddings
WHERE repository_id = $1
ORDER BY embedding <=> query_embedding
LIMIT 15;
```

Without RAG, each phase relies on priority files (from the observation phase's smart file reading) or falls back to the same 10 static code samples. With RAG, each phase gets different, semantically relevant code from across the entire codebase, combined with priority files for the best context quality.

#### Stage 3: Phased AI Analysis (`phased_blueprint_generator.py`)

Eight to nine sequential Claude API calls, each building on the outputs of previous phases:

| Phase | Input | Output | Purpose |
|-------|-------|--------|---------|
| **0. Observation** | File signatures from up to 300 files (~200 tokens each: path + imports + class/function names) | Architecture style, detected components, priority files per phase, custom RAG search terms | Architecture-agnostic detection. Generates custom queries and identifies key files for each downstream phase |
| **0.5 Smart File Reading** | `priority_files_by_phase` from observation | Per-phase file content cache (150KB budget) | Reads full content of AI-selected architecturally significant files |
| **1. Discovery** | File tree + dependencies + config files + observation results + priority files | Project type, entry points, module organization, config approach | Understand what the project is |
| **2. Layers** | Discovery output + file tree + priority files (or RAG) | Layer definitions, dependency rules, structure type | Identify architectural boundaries |
| **3. Patterns** | Discovery + layers + priority files (or RAG) | Structural patterns, behavioral patterns, cross-cutting concerns | Extract design patterns |
| **4. Communication** | All previous + priority files (or RAG) | Internal/external communication, integrations, pattern selection guide | Map how components communicate |
| **5. Technology** | All previous + dependencies + priority files (or RAG) | Complete tech stack inventory | Document all technologies |
| **6. Frontend** (conditional) | Discovery results checked for frontend indicators + priority files | Frontend framework, rendering, state management, styling, conventions | Only runs if frontend code detected |
| **7. Implementation Analysis** | Technology + communication + patterns + layers + code samples | Implementation guidelines for existing capabilities | Document how features were built (libraries, patterns, key files) |
| **8. Synthesis** | All phase outputs combined | `StructuredBlueprint` JSON | Produce the final structured model |

Each phase's prompt is loaded from `prompts.json` via `PromptLoader` and rendered with template variables.

**Observation-first approach:** Traditional analysis assumes patterns like "service layer" or "repository pattern." The observation phase scans all file signatures first and detects the actual architecture style — whether that's actor-based, event-sourced, CQRS, feature-sliced, or something custom. It then generates targeted RAG queries for that specific architecture.

#### Smart File Reading (Phase 0.5)

After the observation phase completes, the pipeline reads the full content of architecturally significant files identified by the AI. This bridges the gap between observation (which scans signatures of all files) and downstream phases (which need actual code to analyze).

**How it works:**

1. The observation phase outputs `priority_files_by_phase` — a mapping of phase names to file paths the AI considers most important for that phase
2. `_calculate_file_budget()` determines the reading budget dynamically based on actual source code size (see Dynamic File Reading Budget below)
3. The pipeline reads each unique file once into a shared cache
4. For small repos where the budget allows, `_supplement_with_remaining_files()` reads ALL remaining source files not yet in the cache
5. Each downstream phase receives its targeted files via `_build_phase_context()`

**Dynamic file reading budget:**

Instead of a fixed 150KB budget, the pipeline now calculates the budget dynamically from the raw `structure_data` (file tree with exact sizes per file):

| Repo Size (source code) | Total Budget | Per-File Max | Behavior |
|--------------------------|-------------|-------------|----------|
| Small (<300KB) | All source + 50KB headroom | 35KB | Reads every source file — near-complete coverage |
| Medium (300KB–1MB) | 400KB | 15KB | Priority files + expanded budget |
| Large (>1MB) | 250KB | 10KB | Priority files only, strict budget |

Budget overrides can be set via environment variables `FILE_READING_BUDGET` and `FILE_READING_PER_FILE_MAX` (0 = auto).

**Priority file selection by phase:**

| Phase | What the AI selects |
|-------|-------------------|
| Discovery | Entry points, app factories, main config, top-level orchestration |
| Layers | DI containers, module registries, route registrations, service/repository interfaces |
| Patterns | Files showing design patterns (factories, decorators, middleware, state machines) |
| Communication | HTTP clients/servers, event handlers, message queues, WebSocket handlers |
| Technology | Build configs, CI/CD, Dockerfiles, deployment scripts |
| Frontend | UI entry points, root layout, route config, state store, data fetching hooks |

**Code context priority cascade** (`_get_phase_code()`):

Each analysis phase resolves its code context using this priority:

1. **RAG + targeted files** — Semantic retrieval combined with priority files (best quality)
2. **Targeted files only** — Priority files without RAG (when RAG unavailable)
3. **RAG only** — Semantic retrieval without priority files (when observation parsing fails)
4. **Fallback** — Generic code samples (final fallback)

**Key methods in `phased_blueprint_generator.py`:**

| Method | Purpose |
|--------|---------|
| `_parse_priority_files()` | Extracts `priority_files_by_phase` from observation JSON output |
| `_read_priority_files()` | Reads file content into a per-phase cache with budget protection |
| `_calculate_file_budget()` | Determines dynamic budget based on actual source code size |
| `_supplement_with_remaining_files()` | For small repos, reads all remaining source files into the cache |
| `_build_file_registry()` | Builds a compact list of all source file paths for grounding |
| `_build_phase_context()` | Formats cached files as code blocks for prompt inclusion |
| `_get_phase_code()` | Resolves the best available code context using the priority cascade |

#### File Path Grounding System

The AI analysis pipeline can hallucinate file paths — referencing files that don't exist or inventing directory structures. The grounding system eliminates this by injecting a **file registry** as a constraint into every analysis phase.

**How it works:**

1. `_build_file_registry()` extracts all source file paths from the raw `structure_data` (the file tree with exact paths)
2. The registry is a compact newline-separated list (~3KB for 65 files) injected into every phase prompt as a `{file_registry}` template variable
3. Every phase prompt in `prompts.json` includes a grounding instruction:

```
### File Registry (GROUNDING CONSTRAINT)
The following file paths exist in this repository. You MUST ONLY reference
file paths from this list. Do NOT invent, infer, or restructure file paths.

{file_registry}
```

4. The synthesis prompt additionally enforces: *"Every file path in the output MUST appear in the File Registry."*

**Result:** On tested repositories, file path grounding accuracy improved from ~70% to 92%+ combined accuracy (files + directories), with the original hallucination patterns (invented subdirectory structures) eliminated entirely.

#### Stage 4: Blueprint Storage

The synthesis phase produces a `StructuredBlueprint` Pydantic model. This is serialized to JSON and stored at `storage/blueprints/{repository_id}/blueprint.json`. Individual phase outputs are also saved alongside:

```
blueprints/{repository_id}/
├── blueprint.json               (main output — single source of truth)
├── observation.json             (phase 0 output)
├── discovery.json               (phase 1 output)
├── layers.json                  (phase 2 output)
├── patterns.json                (phase 3 output)
├── communication.json           (phase 4 output)
├── technology.json              (phase 5 output)
├── frontend_analysis.json       (phase 6 output, if applicable)
└── implementation_analysis.json (phase 7 output)
```

#### Stage 5: Output Generation

All outputs are deterministic transformations of the blueprint JSON:

| Output | Generator | Description |
|--------|-----------|-------------|
| Markdown blueprint | `blueprint_renderer.py` | Human-readable architecture document |
| CLAUDE.md | `agent_file_generator.py:generate_claude_md()` | AI assistant instructions with mandatory MCP enforcement |
| Cursor rules | `agent_file_generator.py:generate_cursor_rules()` | `.cursor/rules/architecture.md` with YAML frontmatter and globs |
| AGENTS.md | `agent_file_generator.py:generate_agents_md()` | Multi-agent system guidance with MCP workflow |
| MCP tool responses | `infrastructure/mcp/tools.py` | Real-time queries against the blueprint |

### Context Window Management

AI models have limited context windows. The pipeline handles large codebases (100K+ files) through:

1. **Compressed structure** — Full file tree compressed to ~3000 chars showing directory shape
2. **File-level RAG** — Full file contents (up to 3KB each, 5 files per phase) selected by semantic search with phase-specific chunk type preferences
3. **Dynamic file budget** — Small repos get all files read; large repos use priority-based selection with tiered budgets (see Smart File Reading above)
4. **File registry grounding** — Compact list of all source file paths (~3KB) injected into every phase prompt to prevent hallucinated file references
5. **Progressive context** — Each phase outputs a compact JSON summary (~500-2500 chars) that feeds into the next
6. **Smart truncation** — Data is truncated with tracked limits; both gathered and sent sizes are stored for transparency

Per-phase context budget (character truncation limits from source code):

| Phase | File Tree | Dependencies | Code/Config | Previous Context | Total |
|-------|-----------|-------------|-------------|------------------|-------|
| Discovery | 3,000 | 1,500 | 12,000 | 2,000 (observation) | ~18,500 |
| Layers | 2,500 | — | 15,000 | 1,500 (discovery) | ~19,000 |
| Patterns | — | — | 15,000 | 1,000 + 1,500 (discovery + layers) | ~17,500 |
| Communication | — | — | 12,000 | 3,000 (all previous) | ~15,000 |
| Technology | — | 2,000 | 10,000 | 3,500 (all previous) | ~15,500 |
| Frontend | — | — | 15,000 | 3,000 (all previous) | ~18,000 |
| Implementation | — | — | 10,000 | 5,000 + 3,000 + 3,000 + 3,000 | ~24,000 |
| Synthesis | 10,000 | — | 10,000 | 10,000 × 7 phases | ~90,000 |

Note: Synthesis truncates each phase output independently to 10,000 characters, resulting in significantly more context than earlier phases.

---

## Web vs Mobile Platform Handling

The pipeline provides first-class support for **web**, **Android**, and **iOS** projects. All platform-specific logic is additive — each platform's handling extends the shared pipeline without affecting the others.

### Platform Detection

The system detects the project's platform through multiple signals:

| Signal | Web | Android | iOS | Cross-Platform |
|--------|-----|---------|-----|----------------|
| **Framework keywords** | react, vue, angular, svelte, nuxt, remix, gatsby | jetpack compose | swiftui, uikit | flutter, react-native, expo |
| **File extensions** | .tsx, .jsx, .vue, .svelte | .kt, .java | .swift, .m, .mm | .dart |
| **Build/config files** | package.json | build.gradle, AndroidManifest.xml | .xcodeproj, .storyboard, Podfile | pubspec.yaml |
| **Directory patterns** | pages/, components/, src/app/ | app/src/main | — | — |

Detection happens in `_detect_frontend()` (`phased_blueprint_generator.py`) which checks 31 indicators against the combined discovery results, file tree, and dependency text. If any indicator matches, the frontend analysis phase runs.

### Dependency Parsing

Each platform has its own dependency files, all parsed via the same `rglob` pattern in `analysis_service.py`:

| Platform | Dependency Files | Format |
|----------|-----------------|--------|
| **Web (Node.js)** | `package.json` | JSON — extracts `dependencies` + `devDependencies` |
| **Web (Python)** | `requirements.txt`, `pyproject.toml` | Plain text / TOML |
| **Web (Ruby)** | `Gemfile` | Ruby DSL |
| **Web (Go)** | `go.mod` | Go module format |
| **Web (Rust)** | `Cargo.toml` | TOML |
| **iOS (CocoaPods)** | `Podfile` | Ruby DSL — pod names, versions, targets |
| **iOS (SPM)** | `Package.swift` | Swift — package dependencies |
| **iOS (Carthage)** | `Cartfile` | Plain text — GitHub refs |
| **Android (Gradle)** | `build.gradle`, `build.gradle.kts` | Groovy / Kotlin DSL — dependencies block |
| **Android (Settings)** | `settings.gradle*` | Groovy / Kotlin — module declarations |

All dependency files are truncated to ~1000 characters each and tagged with language hints for the AI.

### Config File Detection

Mobile-specific config files are detected alongside web configs:

| Platform | Config Files |
|----------|-------------|
| **Android** | `AndroidManifest.xml`, `proguard-rules.pro`, `gradle.properties`, `build.gradle`, `settings.gradle` |
| **iOS** | `Info.plist`, `Podfile.lock` |
| **Web** | `tsconfig.json`, `docker-compose.yml`, `.env.example`, `webpack.config.*`, `vite.config.*`, etc. |

### Source Code Extensions

A shared `SOURCE_CODE_EXTENSIONS` constant (`domain/entities/analysis_settings.py`) defines all recognized source file extensions:

```
.py .js .ts .tsx .jsx .java .go .rs .swift .kt .rb .php
.cs .cpp .c .h .hpp .m .mm .scala .xml
```

Key mobile additions: `.xml` (Android layouts, navigation graphs, resources), `.kt` (Kotlin), `.swift`, `.m`/`.mm` (Objective-C). This constant is used by the phased generator (file signature extraction, file reading), RAG retriever (code file filtering), and embedding generator.

### Code Sample Selection

When extracting representative code samples, the pipeline filters for these extensions:

```
.py .ts .tsx .js .jsx .kt .java .swift .xml
```

This ensures mobile source files are included in the static code samples available to all analysis phases.

### Frontend Analysis Prompt

The `frontend_analysis` prompt in `prompts.json` is platform-aware. Each of its 7 analysis sections includes platform-specific guidance:

| Section | Web | iOS | Android |
|---------|-----|-----|---------|
| **Framework & Rendering** | SPA vs SSR vs SSG, React/Vue/Angular | SwiftUI (declarative) vs UIKit (imperative) vs hybrid | Jetpack Compose (declarative) vs XML layouts (imperative) vs hybrid |
| **Component Architecture** | Component hierarchy, HOCs, render props | View hierarchy, ViewControllers, SwiftUI view composition | Activities, Fragments, Composable functions, ViewModels |
| **State Management** | Redux, Zustand, MobX, Context API | @State, @Observable, Combine, MVVM | ViewModel + StateFlow/LiveData, Compose state, MVI |
| **Routing / Navigation** | React Router, Next.js file routing, hash routing | NavigationStack, Coordinator pattern, deep links | Navigation Component, NavHost, deep links, Intents |
| **Data Fetching / Networking** | fetch, Axios, React Query, SWR, GraphQL | URLSession, Alamofire, Moya, async/await | Retrofit, Ktor, OkHttp, Coroutine/Flow |
| **Styling / Theming** | CSS Modules, Tailwind, styled-components | SwiftUI modifiers, Interface Builder, programmatic UIKit | Compose Material3 theming, XML themes/styles |
| **Conventions** | File naming, folder structure, import patterns | Xcode project organization, target structure | Module structure, package conventions, resource organization |

The AI selects the relevant platform branch based on what it detects in the codebase.

### Directory Summarization

The directory summarizer (`infrastructure/analysis/directory_summarizer.py`) recognizes mobile-specific directory patterns:

| Pattern | Platform | Classified As |
|---------|----------|--------------|
| `viewmodels`, `viewmodel`, `vm` | Android/iOS | MVVM view models |
| `composables`, `compose` | Android | Jetpack Compose UI |
| `fragments`, `activities` | Android | Android UI components |
| `adapters` | Android | RecyclerView/list adapters |
| `res`, `layout`, `drawable`, `values`, `mipmap`, `navigation` | Android | Android resources |
| `coordinators` | iOS | Navigation coordinator pattern |
| `screens`, `features` | iOS/Android | Screen/feature modules |
| `extensions`, `protocols` | iOS | Swift extensions/protocols |
| `di`, `injection` | Android/iOS | Dependency injection modules |
| `network`, `remote`, `datasource` | Any | Network/API layer |

File name analysis also recognizes mobile patterns: files containing `ViewModel`, `Composable`, `Fragment`, `Activity`, `ViewController`, `Coordinator`, or `DAO` in their names get appropriate descriptions.

### Library Capabilities

The `library_capabilities` table (seeded by `001_initial_setup.sql`) maps library names to capabilities and ecosystems. This enables the implementation analysis phase to detect what existing capabilities a project has.

| Category | Example Libraries | Capabilities |
|----------|------------------|-------------|
| **Android UI** | compose, navigation-compose | `ui_framework`, `navigation` |
| **Android Infra** | hilt/dagger, room, coroutines, timber | `dependency_injection`, `persistence`, `concurrency`, `logging` |
| **Android Media** | glide, coil | `image_loading` |
| **iOS UI** | swiftui, uikit, snapkit | `ui_framework` |
| **iOS Media** | kingfisher, sdwebimage | `image_loading` |
| **iOS Networking** | alamofire, moya | `networking` |
| **Cross-Platform** | lottie, ktor, okhttp, moshi | `ui_framework`, `networking`, `serialization` |
| **Web State** | redux, zustand, mobx, riverpod, bloc | `state_management` |
| **Web/Backend** | prisma, sequelize, sqlalchemy, mongoose | `persistence`, `orm`/`odm` |
| **Auth** | firebase, supabase, auth0, clerk | `authentication` |
| **Payments** | stripe | `payments` |

Library matching is substring-based — a single entry like `lottie` matches `lottie-ios`, `lottie-android`, and `lottie-react-native`.

### Web Compatibility

All mobile additions are strictly additive. Web projects are unaffected because:

- Mobile file extensions (`.swift`, `.kt`) and build files (`build.gradle`, `Podfile`) don't exist in web repos
- `.xml` in source extensions: web projects rarely have XML; any that do (e.g., `pom.xml`) are small and harmless
- The frontend analysis prompt uses conditional sections — the AI picks the relevant platform branch
- Mobile library names (hilt, compose, alamofire) don't appear in `package.json` or `requirements.txt`
- Mobile directory patterns (`viewmodels`, `composables`) don't match standard web directories

---

## StructuredBlueprint Data Model

Defined in `domain/entities/blueprint.py`. This is the single source of truth — every output derives from it.

### Top-Level Structure

```python
class StructuredBlueprint(BaseModel):
    meta: BlueprintMeta               # Repository info, architecture style, platforms
    architecture_rules: ArchitectureRules  # Dependency constraints, file placement, naming
    decisions: ArchitectureDecisions   # Style choice, rationale, trade-offs
    components: ComponentMap           # Named components with locations and responsibilities
    communication: CommunicationMap    # Patterns, selection guide
    quick_reference: QuickReference    # Where-to-put-code map, error mapping
    technology: TechnologyStack        # Categorized tech stack inventory
    frontend: FrontendArchitecture     # Framework, rendering, state, styling (optional)
    implementation_guidelines: list[ImplementationGuideline]  # How existing capabilities were built
```

### Key Sections

**`architecture_rules`** — What the MCP tools enforce:
- `file_placement_rules[]` — Component type, location, naming pattern, example
- `naming_conventions[]` — Scope (classes, files, etc.), pattern, examples

**`components`** — Discovered architectural components:
- Name, location, responsibility, dependencies, public interface

**`communication`** — How components interact:
- Patterns (name, when to use, how it works)
- Pattern selection guide (scenario → recommended pattern → rationale)

**`frontend`** (populated only when frontend code is detected):
- Framework, rendering strategy, styling, state management, routing, data fetching, key conventions

**`implementation_guidelines`** — How existing capabilities were built:
- Capability name, category, libraries used, pattern description, key files, usage example, tips
- Documents what ALREADY EXISTS (e.g., push notifications via FCM, maps via Mapbox) — not future tasks

### Source File Retention

After analysis, the cloned repository is deleted from the temp directory. To allow AI agents and developers to view source files after the fact, the `SourceFileCollector` (`application/services/source_file_collector.py`) copies the entire repository to persistent storage during analysis:

1. Uses `shutil.copytree` to copy the full repo tree to `storage/repos/{repo_id}/`
2. Skips non-source directories (`.git`, `node_modules`, `__pycache__`, `.venv`, `build`, `dist`, etc.)
3. Writes a `manifest.json` listing all files with sizes

This means **every source file** is available after analysis — not just files referenced in the blueprint.

**Clickable file paths:** The blueprint renderer outputs file paths as `[`path`](source://path)` markdown links. The frontend intercepts `source://` links (via ReactMarkdown `urlTransform` + custom `a` component) and opens a modal with the file content fetched from `GET /api/v1/workspace/repositories/{id}/source-files/{path}`. MCP tools `list_source_files` and `get_file_content` provide the same access for AI agents.

---

## MCP Server

The MCP server runs as part of the FastAPI backend via SSE transport at `/mcp/sse`.

### Architecture

```
FastAPI app
  └── /mcp/sse (Starlette mount, raw ASGI)
        └── SseServerTransport
              └── MCP Server (mcp SDK)
                    ├── Tools (10)
                    └── Resources (dynamic)
```

Defined in `infrastructure/mcp/`. The server is mounted as a raw ASGI app in `api/app.py` via Starlette to avoid FastAPI middleware interference with the SSE stream.

### Tools

| Tool | Parameters | Returns | Description |
|------|-----------|---------|-------------|
| `get_repository_blueprint` | — | Full blueprint JSON | Returns the complete `StructuredBlueprint` |
| `list_repository_sections` | — | Section IDs and names | Lists addressable blueprint sections |
| `get_repository_section` | `section_id` | Section content | Token-efficient alternative to full blueprint |
| `where_to_put` | `component_type` | Directory, naming pattern, example | Returns correct file location for a component type |
| `check_naming` | `scope`, `name` | Pass/fail with convention details | Validates name against naming conventions |
| `how_to_implement` | `feature` | Libraries, patterns, key files, example | Look up how a capability is already implemented (fuzzy search) |
| `list_implementations` | — | All implementation guidelines | Lists all documented existing capabilities |
| `how_to_implement_by_id` | `implementation_id` | Specific implementation guideline | Look up a specific implementation by index |
| `list_source_files` | — | File list with sizes | List all source files collected during analysis |
| `get_file_content` | `file_path` | File content | Read a source file collected during analysis |

All MCP tools use an implicit active repository context (from the user's profile) — no `repo_id` parameter is exposed in the MCP protocol. The underlying `BlueprintTools` class methods accept `repo_id` explicitly for internal use.

### Resources

Dynamic resources based on analyzed repositories:

- `blueprint://analyzed` — List all analyzed repositories
- `blueprint://analyzed/{repo_id}` — Full rendered markdown blueprint
- `blueprint://analyzed/{repo_id}/{section_id}` — Specific section

### Connecting from an IDE

Add to `.mcp.json` (Claude Code) or `.cursor/mcp.json` (Cursor):

```json
{
  "mcpServers": {
    "architecture-blueprints": {
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

The generated CLAUDE.md, Cursor rules, and AGENTS.md all enforce that the AI agent must call these tools before every architecture decision (file creation, import, naming).

---

## Delivery Pipeline

Pushes generated outputs to a target GitHub repository via the GitHub API.

### Components

- `delivery_service.py` — Orchestration and merge logic
- `github_push_client.py` — PyGithub wrapper for branches, commits, PRs, file reads
- `api/routes/delivery.py` — HTTP endpoints

### Output File Mapping

| Output Key | Target Path | Merge Strategy |
|-----------|-------------|----------------|
| `claude_md` | `CLAUDE.md` | Markdown (fenced section) |
| `agents_md` | `AGENTS.md` | Markdown (fenced section) |
| `cursor_rules` | `.cursor/rules/architecture.md` | Markdown (fenced section) |
| `mcp_claude` | `.mcp.json` | JSON (key-level merge) |
| `mcp_cursor` | `.cursor/mcp.json` | JSON (key-level merge) |

### Merge Strategies

**Markdown merge** — Uses HTML comment markers to fence the generated section:

```markdown
<!-- gbr:start repo=my-repo -->
(generated content here)
<!-- gbr:end -->
```

- If the file doesn't exist: creates it wrapped in markers
- If markers exist: replaces content between them, preserves everything outside
- If no markers found: appends fenced block at the end, preserving existing content

**JSON merge** — Only upserts the `mcpServers.architecture-blueprints` key:

```json
{
  "mcpServers": {
    "existing-server": { "...": "preserved" },
    "architecture-blueprints": { "url": "http://localhost:8000/mcp/sse" }
  }
}
```

Other keys in the JSON file are never touched.

### Delivery Strategies

| Strategy | Behavior |
|----------|----------|
| `pr` | Creates a new branch (`gbr/sync-architecture-outputs`), commits merged files, opens a pull request |
| `commit` | Commits merged files directly to the default branch |

Both strategies use the PyGithub Git Trees API for atomic multi-file commits.

### Flow

```
1. Load blueprint from storage
2. Generate outputs (CLAUDE.md, Cursor rules, etc.)
3. Read existing files from target repo (get_file_content)
4. Apply merge strategy per file type
5. Commit merged content atomically
6. (If PR strategy) Create pull request
```

---

## API Reference

All routes are prefixed with `/api/v1` and registered in `api/app.py`.

### Authentication (`/api/v1/auth`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/config` | Get auth configuration |
| `POST` | `/github` | Validate a GitHub token |
| `GET` | `/status` | Check current auth status |
| `DELETE` | `/` | Logout |

### Repositories (`/api/v1/repositories`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List repositories |
| `POST` | `/` | Create/register a repository |
| `GET` | `/{repo_id}` | Get repository details |
| `POST` | `/{owner}/{repo}/analyze` | Start analysis (enqueues background task) |
| `GET` | `/{repo_id}/status` | Get analysis status |
| `GET` | `/{repo_id}/blueprint` | Get latest blueprint |

### Analyses (`/api/v1/analyses`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List analyses |
| `GET` | `/{id}` | Get analysis details |
| `GET` | `/{id}/events` | Stream analysis events (SSE) |
| `GET` | `/{id}/stream` | Stream analysis progress (SSE) |
| `GET` | `/{id}/analysis-data` | Get all phase data (gathered, prompts, outputs) |
| `GET` | `/{id}/agent-files` | Get generated CLAUDE.md, Cursor rules, AGENTS.md |
| `GET` | `/{id}/blueprint` | Get blueprint (query `?type=backend` or `?format=json`) |

### Delivery (`/api/v1/delivery`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/preview` | Preview outputs without pushing |
| `POST` | `/apply` | Push outputs to target GitHub repo |

**Preview request:**
```json
{
  "source_repo_id": "uuid",
  "outputs": ["claude_md", "agents_md", "cursor_rules", "mcp_claude", "mcp_cursor"]
}
```

**Apply request:**
```json
{
  "source_repo_id": "uuid",
  "target_repo": "owner/repo",
  "token": "ghp_...",
  "outputs": ["claude_md", "mcp_claude"],
  "strategy": "pr"
}
```

### Architecture (`/api/v1/architecture`) — NOT REGISTERED

> **Note:** `architecture.py` exists on disk but is not included in `app.py` route registration. These endpoints are currently inaccessible.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repositories/{id}` | Get resolved architecture rules |
| `PUT` | `/repositories/{id}/config` | Configure architecture sources and merge strategy |
| `POST` | `/repositories/{id}/validate` | Validate code against architecture rules |
| `POST` | `/repositories/{id}/check-location` | Check if a file is in the correct location |
| `GET` | `/repositories/{id}/guide/{type}` | Get implementation guide for a feature type |
| `GET` | `/repositories/{id}/agent-files` | Get agent files |
| `GET` | `/reference-blueprints` | List available reference architectures |

### Workspace (`/api/v1/workspace`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repositories` | List analyzed repositories in workspace |
| `GET` | `/active` | Get currently active repository |
| `PUT` | `/active` | Set active repository |
| `DELETE` | `/active` | Clear active repository |
| `GET` | `/repositories/{id}/agent-files` | Get agent files for repo |
| `GET` | `/repositories/{id}/blueprint` | Get blueprint for repo |
| `GET` | `/repositories/{id}/source-files/{path}` | Get collected source file content |
| `DELETE` | `/repositories/{id}` | Delete repository analysis |

### Settings (`/api/v1/settings`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/ignored-dirs` | List all discovery ignored directories |
| `PUT` | `/ignored-dirs` | Replace all ignored directories |
| `POST` | `/ignored-dirs/reset` | Reset ignored directories to seed defaults |
| `GET` | `/ecosystem-options` | List valid ecosystem values |
| `GET` | `/capability-options` | List valid capability values |
| `GET` | `/library-capabilities` | List all library capability mappings |
| `PUT` | `/library-capabilities` | Replace all library capabilities |
| `POST` | `/library-capabilities/reset` | Reset library capabilities to seed defaults |

### Prompts (`/api/v1/prompts`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List all default prompts |
| `GET` | `/{prompt_id}` | Get a single prompt by ID |
| `PUT` | `/{prompt_id}` | Update a prompt (creates a revision) |
| `GET` | `/{prompt_id}/revisions` | List revision history |
| `POST` | `/{prompt_id}/revert/{revision_id}` | Revert a prompt to a previous revision |

### Health (`/`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/system/path` | Get project root path |

### MCP (`/mcp`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/mcp/sse` | MCP SSE stream (connect from IDE) |
| `POST` | `/mcp/messages` | MCP message endpoint |

---

## Database Schema

PostgreSQL hosted on Supabase with pgvector extension. A single initial migration in `backend/migrations/001_initial_setup.sql` creates all tables, indexes, and functions (idempotent — safe to re-run). Prompt data is seeded separately by `backend/scripts/seed_prompts.py` (not in the migration).

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | User accounts | `id`, `github_token_encrypted`, `created_at`, `updated_at` |
| `user_profiles` | User preferences | `id`, `user_id`, `active_repository_id`, `preferences` |
| `repositories` | Tracked repositories | `id`, `user_id`, `owner`, `name`, `full_name`, `language`, `default_branch` |
| `analyses` | Analysis runs | `id`, `repository_id`, `status`, `progress_percentage`, `error_message`, `started_at`, `completed_at` |
| `analysis_prompts` | Prompt definitions | `id`, `user_id`, `name`, `category`, `prompt_template`, `variables`, `is_default`, `key`, `type` |
| `prompt_revisions` | Prompt revision history | `id`, `prompt_id`, `revision_number`, `prompt_template`, `variables`, `change_summary`, `created_by` |
| `analysis_data` | Phase inputs/outputs | `id`, `analysis_id`, `data_type`, `data` (JSONB) |
| `analysis_events` | SSE event log | `id`, `analysis_id`, `event_type`, `message`, `details` |
| `embeddings` | Code chunk vectors | `id`, `repository_id`, `file_path`, `chunk_type`, `embedding` (vector(384)), `metadata` |
| `discovery_ignored_dirs` | Directories to skip during file scanning | `id`, `directory_name` (unique) |
| `library_capabilities` | Library-to-capability mappings | `id`, `library_name` (unique), `ecosystem`, `capabilities` (text[]) |

### Key `data_type` Values in `analysis_data`

| Value | Content |
|-------|---------|
| `gathered` | Raw extracted data (file tree, dependencies, configs, code samples) |
| `phase_observation` | Observation phase input/output |
| `phase_discovery` | Discovery phase input/output |
| `phase_layers` | Layers phase input/output |
| `phase_patterns` | Patterns phase input/output |
| `phase_communication` | Communication phase input/output |
| `phase_technology` | Technology phase input/output |
| `phase_frontend` | Frontend phase input/output (conditional) |
| `phase_implementation_analysis` | Implementation analysis phase input/output |
| `phase_backend_synthesis` | Synthesis phase input/output |
| `summary` | Overall metrics (chars sent, phase count, timestamps) |

### pgvector

The `embeddings` table uses a `vector(384)` column for storing sentence-transformer embeddings. The `match_embeddings` SQL function performs cosine similarity search:

```sql
CREATE FUNCTION match_embeddings(
    query_embedding vector(384),
    match_count int DEFAULT 10,
    filter_repository_id uuid DEFAULT NULL
) RETURNS TABLE(...)
```

---

## Frontend (Web UI)

### Pages

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Repository list, start new analysis |
| Auth | `/auth` | GitHub token authentication |
| Workspace | `/workspace` | Manage analyzed repos, set active repo |
| Analysis | `/analysis/[id]` | Real-time analysis progress via SSE |
| Blueprint | `/blueprint/[id]` | Tabbed view of all outputs |

### Blueprint View Tabs

| Tab | Content |
|-----|---------|
| Backend Architecture | Rendered markdown blueprint |
| Frontend Architecture | Frontend-specific blueprint (when applicable) |
| CLAUDE.md | Generated AI assistant instructions |
| Cursor Rules | Generated Cursor IDE rules |
| MCP Server Setup | Connection instructions |
| Analysis Data & Prompts | Full transparency into gathered data, truncation, prompts |

### State Management

- **Server state** — React Query handles all API calls with caching and invalidation
- **Auth state** — React Context (`context/auth.tsx`) stores GitHub token
- **No client-side global store** — All state is server-derived

---

## Configuration

### Setup Scripts

| Script | Purpose | When to use |
|--------|---------|-------------|
| `setup.sh` | Environment setup | First time and after `git pull`. Installs prerequisites (Docker, Python, Node), starts database, re-applies migration (idempotent), seeds prompts, creates env files, installs dependencies. |
| `start-dev.sh` | Start all services | Every time you want to run the app. Starts Docker containers (if postgres), backend, frontend, and ARQ worker (if Redis available). |
| `start-dev.py` | Cross-platform startup | Same as `start-dev.sh` but works on Windows/macOS/Linux without bash. |

### Database Backends

The system supports two database backends, selected via `DB_BACKEND` in `backend/.env.local`:

| Backend | `DB_BACKEND` | Setup | Migration |
|---------|-------------|-------|-----------|
| **Local PostgreSQL** (recommended) | `postgres` | `docker compose up -d` starts PostgreSQL (with pgvector) + Redis | Automatic — `setup.sh` re-applies `001_initial_setup.sql` (idempotent) and runs `seed_prompts.py` |
| **Supabase** (cloud) | `supabase` | Create project at supabase.com | Manual — paste `001_initial_setup.sql` then `migrations/seed_prompts.sql` into Supabase SQL editor |

`setup.sh` handles both paths interactively.

### Backend Environment Variables

Generated by `setup.sh` at `backend/.env.local`, or copy from `backend/.env.example`:

```bash
# ── Database Backend (choose one) ─────────────────────────────
DB_BACKEND=postgres                # "postgres" (local Docker) or "supabase" (cloud)

# For postgres:
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/architecture_mcp

# For supabase:
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-supabase-anon-key

# ── AI (REQUIRED) ────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...

# ── Redis (optional — without it, analysis runs in-process) ──
REDIS_URL=redis://localhost:6379

# ── Optional ─────────────────────────────────────────────────
GITHUB_TOKEN=ghp_...               # Server-side GitHub token (users can also provide their own)
DEFAULT_AI_MODEL=claude-haiku-4-5-20251001
SYNTHESIS_AI_MODEL=claude-haiku-4-5-20251001
SYNTHESIS_MAX_TOKENS=64000
STORAGE_TYPE=local                 # local, gcs, or s3
STORAGE_PATH=./storage

# ── File Reading Budget (optional — 0 = auto/dynamic) ────
FILE_READING_BUDGET=0              # Total chars budget (0 = dynamic based on repo size)
FILE_READING_PER_FILE_MAX=0        # Per-file max chars (0 = dynamic)
```

### Frontend Environment Variables

Generated by `setup.sh` at `frontend/.env.local`, or copy from `frontend/.env.example`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Prompt Customization

`backend/prompts.json` is the **only** source of truth for prompt content (the migration SQL does NOT seed prompts). The file has a `"version"` field that must be bumped for any change requiring `./setup.sh` re-run (prompt content or schema changes).

```json
{
  "version": 3,
  "prompts": {
    "observation": {
      "name": "Architecture Observation",
      "category": "observation",
      "prompt_template": "You are analyzing a codebase...\n{file_signatures}...",
      "variables": ["repository_name", "file_signatures"]
    }
  }
}
```

After editing prompts, bump `"version"` and run `./setup.sh` (which calls `seed_prompts.py` to upsert into the database). The script also saves `backend/migrations/seed_prompts.sql` for Supabase users to paste into the SQL editor.

`start-dev.sh` and `start-dev.py` compare `prompts.json` version against `backend/.prompts-version` (written by `seed_prompts.py`) and warn if stale.

The `PromptLoader` (`infrastructure/prompts/prompt_loader.py`) renders templates with variable substitution.

---

## Testing

### Running Tests

```bash
cd backend

# All unit tests
PYTHONPATH=src python -m pytest tests/unit/ -v

# Service tests only
PYTHONPATH=src python -m pytest tests/unit/services/ -v

# Single test file
PYTHONPATH=src python -m pytest tests/unit/services/test_delivery_service.py -v

# Single test by name
PYTHONPATH=src python -m pytest tests/unit/services/ -k "test_merge_existing_with_markers"

# With coverage
PYTHONPATH=src python -m pytest tests/unit/ --cov=src --cov-report=html
```

### Test Structure

```
tests/unit/
├── services/
│   ├── test_agent_file_generator.py    # CLAUDE.md, Cursor rules, AGENTS.md generation
│   ├── test_delivery_service.py        # Delivery + merge logic
│   ├── test_unified_features.py        # Frontend detection, unified pipeline
│   ├── test_mobile_support.py          # Android/iOS mobile platform support (24 tests)
│   └── ...
├── workers/
│   └── test_analysis_workflows.py      # ARQ + in-process workflow tests (23 tests)
└── infrastructure/
    ├── test_github_push_client.py      # GitHub API operations
    ├── test_mcp_utils.py               # MCP tools and resources
    └── ...
```

Current test count: **838 unit tests**.

### Test Conventions

- Tests use `pytest` with `pytest-asyncio` for async tests
- Mocking via `unittest.mock` (`MagicMock`, `AsyncMock`, `patch`)
- Fixtures provide sample blueprints, mock storage, mock push clients
- Pure function tests (merge logic, generators) don't need async
- Integration tests mock external services (Supabase, GitHub API)

---

## Extending the System

### Adding a New MCP Tool

1. Define the tool function in `infrastructure/mcp/tools.py`
2. Register it with the MCP server in `infrastructure/mcp/server.py`
3. The tool should read from `StructuredBlueprint` — never write to it
4. Add tests in `tests/unit/infrastructure/test_mcp_utils.py`

### Adding a New Analysis Phase

1. Add the prompt to `prompts.json` with a unique key
2. Add the phase call in `phased_blueprint_generator.py` (after the appropriate preceding phase)
3. Store results via `analysis_data_collector` with a new `data_type`
4. If the phase produces new data for the blueprint, extend the `StructuredBlueprint` model in `domain/entities/blueprint.py`
5. Add tests in `tests/unit/services/`

### Adding a New Output Format

1. Add a generator function in `agent_file_generator.py` (or a new file for complex formats)
2. Add the output key to `OUTPUT_FILE_MAP` and `MERGE_STRATEGY` in `delivery_service.py`
3. Wire it into `_generate_outputs()` in `delivery_service.py`
4. Add tests for the generator and the delivery merge behavior

### Adding a New Delivery Target

The delivery pipeline currently supports GitHub. To add another target (GitLab, Bitbucket, etc.):

1. Create a new push client in `infrastructure/external/` implementing the same interface as `GitHubPushClient` (get_file_content, commit_files, create_branch, create_pull_request)
2. Update `delivery_service.py:apply()` to select the client based on target type
3. Add tests for the new client

### Changing AI Models

Update `DEFAULT_AI_MODEL` and `SYNTHESIS_AI_MODEL` in your `.env.local`. The system uses the Anthropic SDK and supports any Claude model. The synthesis phase can use a more capable model than the earlier phases if needed.

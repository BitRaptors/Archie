# Architecture Blueprints — Developer Documentation

Comprehensive technical documentation covering system architecture, analysis pipeline internals, intent layer generation, API reference, database schema, MCP server, delivery pipeline, and contribution guidelines.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Backend Architecture](#backend-architecture)
5. [Analysis Pipeline](#analysis-pipeline)
6. [Intent Layer Pipeline](#intent-layer-pipeline)
7. [Incremental Re-Analysis](#incremental-re-analysis)
8. [Web vs Mobile Platform Handling](#web-vs-mobile-platform-handling)
9. [StructuredBlueprint Data Model](#structuredblueprint-data-model)
10. [MCP Server](#mcp-server)
11. [Delivery Pipeline](#delivery-pipeline)
12. [API Reference](#api-reference)
13. [Database Schema](#database-schema)
14. [Frontend (Web UI)](#frontend-web-ui)
15. [Configuration](#configuration)
16. [Testing](#testing)
17. [Extending the System](#extending-the-system)

---

## System Overview

Architecture Blueprints is a monorepo with two services:

- **Backend** — Python FastAPI application following Clean Architecture (DDD layers). Handles repository analysis, blueprint generation, intent layer (per-folder CLAUDE.md), MCP server, and delivery.
- **Frontend** — Next.js 14 application for managing analyses, viewing blueprints, browsing per-folder context, and triggering delivery.

The core workflow:

1. User submits a GitHub repository URL
2. Backend clones the repo, extracts structural data, and runs a multi-phase AI analysis using Claude
3. Analysis produces a `StructuredBlueprint` — a Pydantic model that is the single source of truth
4. The **intent layer** maps the blueprint onto every significant folder, optionally enriching each with AI-generated patterns, key file guides, and common tasks
5. All outputs (root CLAUDE.md, per-folder CLAUDE.md, Cursor rules, AGENTS.md, CODEBASE_MAP.md, MCP tool responses) derive from this blueprint
6. The delivery pipeline pushes these outputs to the target repository via GitHub API
7. **Incremental re-analysis** skips AI enrichment for unchanged folders on subsequent runs

---

## Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web framework | FastAPI + Uvicorn | Async HTTP server with OpenAPI docs |
| Language | Python 3.11+ | Type hints, async/await |
| Data models | Pydantic v2 | Schema validation, serialization |
| Dependency injection | dependency-injector | Constructor injection via declarative container |
| Database | PostgreSQL (local Docker recommended) or Supabase | Persistence for repos, analyses, blueprints, rules |
| Vector search | pgvector | Semantic similarity search on code embeddings |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | 384-dimensional code chunk embeddings |
| Token counting | tiktoken (cl100k_base) | Budget management for AI enrichment |
| AI | Anthropic Claude API | Multi-phase architecture analysis + per-folder enrichment |
| Code parsing | tree-sitter (Python, JS, TS grammars) | AST-based code chunking |
| GitHub API | PyGithub | Repository cloning, file reads, branch/PR creation |
| Task queue | ARQ (Redis-backed, optional) | Background analysis jobs (falls back to in-process without Redis) |
| MCP | mcp SDK + sse-starlette | Model Context Protocol server over SSE |
| Storage | Local filesystem | Blueprint, intent layer, and temp file storage |
| Event bus | In-memory asyncio queues | Real-time SSE delivery of analysis progress |
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
| Database | Docker PostgreSQL with pgvector (recommended) or Supabase (cloud) |
| Cache/Queue | Redis (optional — analysis runs in-process without it) |
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
│   │   │   ├── routes/                   # Route modules
│   │   │   │   ├── analyses.py           # Analysis CRUD + streaming
│   │   │   │   ├── repositories.py       # Repository management + analyze trigger
│   │   │   │   ├── delivery.py           # Preview + apply delivery
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
│   │   │   │   ├── intent_layer_service.py       # Per-folder CLAUDE.md orchestrator
│   │   │   │   ├── hybrid_enrichment_engine.py   # AI enrichment for folders
│   │   │   │   ├── blueprint_folder_mapper.py    # Maps blueprint onto folder paths
│   │   │   │   ├── intent_layer_renderer.py      # Deterministic markdown rendering
│   │   │   │   ├── intent_layer_manifest.py      # Incremental update tracking
│   │   │   │   ├── codebase_map_renderer.py      # CODEBASE_MAP.md generator
│   │   │   │   ├── local_repo_handler.py         # Local filesystem I/O for repos
│   │   │   │   ├── blueprint_renderer.py         # JSON → Markdown renderer
│   │   │   │   ├── agent_file_generator.py       # Root CLAUDE.md, Cursor rules, AGENTS.md
│   │   │   │   ├── delivery_service.py           # GitHub delivery + merge logic
│   │   │   │   ├── source_file_collector.py      # Copies repo to persistent storage
│   │   │   │   ├── analysis_data_collector.py    # Phase data persistence
│   │   │   │   └── ...
│   │   │   └── agents/                   # Background workers
│   │   ├── workers/                      # ARQ task queue (Redis-backed)
│   │   │   ├── worker.py                # Entry point (Python 3.14+ compatible)
│   │   │   └── tasks.py                 # Task definitions, WorkerSettings, startup/shutdown
│   │   ├── domain/                       # Domain layer
│   │   │   ├── entities/                 # Pydantic models
│   │   │   │   ├── blueprint.py          # StructuredBlueprint (central model)
│   │   │   │   ├── intent_layer.py       # FolderNode, FolderBlueprint, FolderEnrichment, etc.
│   │   │   │   └── ...
│   │   │   ├── interfaces/              # Repository interfaces (ports)
│   │   │   └── exceptions/              # Domain exceptions
│   │   ├── infrastructure/              # Infrastructure layer
│   │   │   ├── persistence/             # Database repository implementations
│   │   │   ├── analysis/                # RAG retriever, AST parser, shared embedder
│   │   │   ├── mcp/                     # MCP server, tools, resources
│   │   │   ├── events/                  # In-memory event bus for SSE
│   │   │   ├── external/               # GitHub push client
│   │   │   ├── prompts/                # Prompt loader
│   │   │   └── storage/                # Local storage adapter
│   │   ├── config/
│   │   │   ├── settings.py             # Pydantic settings from .env.local
│   │   │   └── container.py            # DI container
│   │   └── main.py                     # Entry point
│   ├── migrations/
│   │   ├── 001_initial_setup.sql       # Tables, indexes, seed data
│   │   └── 002_add_commit_sha.sql      # Commit SHA tracking for analyses
│   ├── prompts.json                    # All AI prompts
│   ├── requirements.txt
│   └── tests/
│       └── unit/
│           ├── services/               # Service tests
│           └── infrastructure/         # Infrastructure tests
├── frontend/
│   ├── pages/                          # Next.js pages (SPA — only 2 routes)
│   │   ├── index.tsx                   # Dashboard (SPA shell, manages all views via state)
│   │   └── auth.tsx                    # GitHub token authentication
│   ├── components/
│   │   ├── views/                      # View components (rendered by index.tsx)
│   │   │   ├── RepositoryView.tsx      # Repository list + public repo URL analysis
│   │   │   ├── AnalysisView.tsx        # Real-time analysis progress (SSE)
│   │   │   ├── BlueprintView.tsx       # Blueprint viewer (tabbed) with file tree browser
│   │   │   └── SettingsView.tsx        # Ignored dirs, library capabilities
│   │   ├── layout/                     # Layout components
│   │   │   ├── Shell.tsx               # App shell (sidebar + content)
│   │   │   ├── Sidebar.tsx             # Navigation + workspace history
│   │   │   └── PageHeader.tsx          # Reusable page header
│   │   ├── DeliveryPanel.tsx           # Delivery UI (sync with agent)
│   │   ├── SourceFileModal.tsx         # Source file viewer modal
│   │   └── DebugView.tsx               # Analysis data debug view
│   ├── hooks/                          # Custom hooks (useAuth, useWorkspace, etc.)
│   ├── services/                       # API client services
│   └── package.json
├── docs/
│   └── ARCHITECTURE.md                 # This file
├── docker-compose.yml                  # PostgreSQL (pgvector) + Redis containers
├── README.md                           # Project overview
├── run                                 # Single entry point: setup + start (installs prereqs, Docker, deps, seeds DB, starts services)
├── setup.sh                            # Legacy wrapper (redirects to ./run)
└── start-dev.sh                        # Legacy wrapper (redirects to ./run)
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
│  DB repos, RAG, MCP server, GitHub client,               │
│  storage adapters, prompt loader, event bus              │
│  Implements: Domain interfaces                           │
└──────────────────────────────────────────────────────────┘
```

### Dependency Injection

All wiring happens in `config/container.py` using the `dependency-injector` library:

```python
class Container(DeclarativeContainer):
    settings = Singleton(get_settings)
    storage = Singleton(LocalStorage, base_path=settings.storage_path)
    intent_layer_service = Singleton(IntentLayerService, storage=storage, settings=settings)
    analysis_service = Singleton(AnalysisService, storage=storage, intent_layer_service=intent_layer_service, ...)
    delivery_service = Singleton(DeliveryService, storage=storage)
```

Services receive all dependencies through constructor injection. No service instantiates its own dependencies.

### Key Patterns

- **Repository pattern** — Domain interfaces in `domain/interfaces/`, implementations in `infrastructure/persistence/`
- **RAG fallback** — If RAG indexing fails or the database is unavailable, analysis falls back to static code samples
- **Event bus** — In-memory asyncio queue system (`infrastructure/events/event_bus.py`) for real-time SSE delivery of analysis progress
- **Shared embedder** — Singleton for the SentenceTransformer model (`infrastructure/analysis/shared_embedder.py`); lazy-loaded, released after each analysis to free ~400 MB
- **Frontend auto-detection** — `_detect_frontend()` checks 31 indicators covering web, iOS, Android, and cross-platform; branches to unified synthesis when found
- **Settings resilience** — `extra = "ignore"` in Pydantic settings so stale env vars from old `.env.local` files don't crash startup

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
│     Both paths: capture HEAD commit SHA, pass mode (full/incr)   │
│            Both paths call analysis_service.run_analysis()       │
└─────────────────────────────────────────────────────────────────┘
```

Both execution paths capture the repository's HEAD commit SHA via `git rev-parse HEAD` after cloning, and accept a `mode` parameter (`"full"` or `"incremental"`) from the API request.

---

## Analysis Pipeline

The analysis pipeline turns a raw GitHub repository into a `StructuredBlueprint` and then generates the full intent layer.

### Pipeline Stages

#### Stage 1: Data Extraction (`analysis_service.py`)

Clones the repository and extracts:

| Data | Source | Size |
|------|--------|------|
| File tree | `structure_analyzer.py` scans all files | Compressed to ~3000 chars |
| Dependencies | `requirements.txt`, `package.json`, `pyproject.toml`, `Gemfile`, `Cargo.toml`, `go.mod`, `Podfile`, `Package.swift`, `Cartfile`, `build.gradle`, `build.gradle.kts`, `settings.gradle*` | ~1500 chars |
| Config files | `tsconfig.json`, `docker-compose.yml`, `.env.example`, etc. | ~4000 chars |
| Code samples | 10 representative files chosen by heuristics | ~5000 chars |

All I/O operations are wrapped in `asyncio.to_thread()` to avoid blocking the event loop. Gathered data is persisted to the database via `analysis_data_collector`.

#### Stage 2: RAG Indexing (`rag_retriever.py`) — Optional

When the database is available, RAG indexing enables phase-specific code retrieval:

1. **Chunking** — Each code file is split by function/class boundaries using tree-sitter AST parsing
2. **Embedding** — Each chunk is embedded using the shared embedder singleton (sentence-transformers, 384 dimensions)
3. **Storage** — Vectors are stored in pgvector
4. **File-level retrieval** — `retrieve_files_for_phase()` uses chunk-level search to identify relevant files, then deduplicates at the file level and returns **full file contents** (up to 3KB per file)
5. **Phase-specific chunk type preferences** — Each phase has preferred chunk types (e.g., `layers` prefers `class` + `module`)
6. **File registry** — `get_file_registry()` returns all unique file paths indexed for a repository via `SELECT DISTINCT`

#### Stage 3: Phased AI Analysis (`phased_blueprint_generator.py`)

Eight to nine sequential Claude API calls, each building on previous outputs:

| Phase | Input | Output | Purpose |
|-------|-------|--------|---------|
| **0. Observation** | File signatures from up to 300 files | Architecture style, detected components, priority files per phase | Architecture-agnostic detection |
| **0.5 Smart File Reading** | `priority_files_by_phase` from observation | Per-phase file content cache | Reads full content of AI-selected files |
| **1. Discovery** | File tree + dependencies + config files + observation results | Project type, entry points, module organization | Understand what the project is |
| **2. Layers** | Discovery output + file tree + priority files (or RAG) | Layer definitions, dependency rules | Identify architectural boundaries |
| **3. Patterns** | Discovery + layers + priority files (or RAG) | Structural/behavioral patterns, cross-cutting concerns | Extract design patterns |
| **4. Communication** | All previous + priority files (or RAG) | Internal/external communication, pattern selection guide | Map how components communicate |
| **5. Technology** | All previous + dependencies + infrastructure files | Complete tech stack inventory + deployment environment | Document all technologies; scans infra files (`INFRASTRUCTURE_FILE_NAMES`) for deployment detection |
| **6. Frontend** (conditional) | Discovery results checked for frontend indicators | Frontend framework, rendering, state management, styling | Only runs if frontend code detected |
| **7. Implementation Analysis** | Technology + communication + patterns + code samples | Implementation guidelines for existing capabilities | Document how features were built |
| **8. Synthesis** | All phase outputs combined | `StructuredBlueprint` JSON | Produce the final structured model |

#### Stage 4: Blueprint Storage

The synthesis phase produces a `StructuredBlueprint`. This is serialized to JSON and stored at `storage/blueprints/{repository_id}/blueprint.json`. Individual phase outputs are also saved alongside.

#### Stage 5: Source File Retention

The `SourceFileCollector` copies the entire repository to `storage/repos/{repo_id}/` (skipping `.git`, `node_modules`, etc.) before the temp directory is cleaned up. This enables file viewing after analysis and provides the file tree for intent layer generation.

#### Stage 6: Intent Layer Generation (Phase 7)

See [Intent Layer Pipeline](#intent-layer-pipeline) below.

#### Stage 7: Completion

The analysis entity is marked as completed, the commit SHA is persisted, and the shared embedder model is released to free ~400 MB of memory.

### Smart File Reading (Phase 0.5)

Dynamic reading budget based on actual source code size:

| Repo Size (source code) | Total Budget | Per-File Max | Behavior |
|--------------------------|-------------|-------------|----------|
| Small (<300KB) | All source + 50KB headroom | 35KB | Reads every source file |
| Medium (300KB–1MB) | 400KB | 15KB | Priority files + expanded budget |
| Large (>1MB) | 250KB | 10KB | Priority files only, strict budget |

### File Path Grounding

Every phase prompt includes a **file registry** — a compact list of all source file paths injected as a grounding constraint. This eliminates hallucinated file paths in the AI output (accuracy improved from ~70% to 92%+).

---

## Intent Layer Pipeline

The intent layer is the system that generates per-folder `CLAUDE.md` files across an entire repository. It runs as Phase 7 of the analysis pipeline.

### Architecture

```
StructuredBlueprint + Folder Hierarchy
          │
          ▼
  BlueprintFolderMapper         ── maps blueprint sections onto folder paths
          │
          ├── deterministic ──▶ IntentLayerRenderer
          │                        render_from_blueprint() / render_minimal() / render_passthrough()
          │
          └── AI enrichment ──▶ HybridEnrichmentEngine
                                   bottom-up processing (deepest folders first)
                                   per-folder: read priority files → call Claude → FolderEnrichment
                                   │
                                   ▼
                                IntentLayerRenderer.render_hybrid()
                                   AI content + blueprint data → CLAUDE.md
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `IntentLayerService` | `intent_layer_service.py` | Orchestrator — loads blueprint, builds hierarchy, runs enrichment, saves manifest |
| `FolderHierarchyBuilder` | `intent_layer_service.py` | Builds `FolderNode` tree from file tree or local path |
| `BlueprintFolderMapper` | `blueprint_folder_mapper.py` | Maps 10 blueprint sections onto folder paths (components, rules, recipes, pitfalls, etc.) |
| `IntentLayerRenderer` | `intent_layer_renderer.py` | Deterministic markdown rendering with 200-line hard cap |
| `HybridEnrichmentEngine` | `hybrid_enrichment_engine.py` | Per-folder AI enrichment with bottom-up child propagation |
| `CodebaseMapRenderer` | `codebase_map_renderer.py` | Generates flat `CODEBASE_MAP.md` from blueprint |
| `ManifestManager` | `intent_layer_manifest.py` | Tracks content hashes for incremental updates |
| `LocalRepoHandler` | `local_repo_handler.py` | File I/O for local repositories |

### End-to-End Flow

```
IntentLayerService.preview(source_repo_id, incremental=False)
    │
    1. Load ignored dirs from DB
    2. Load StructuredBlueprint from blueprints/{repo_id}/blueprint.json
    3. Load file tree from storage/repos/{repo_id}/
    4. FolderHierarchyBuilder.build_from_file_tree()
         → dict[path, FolderNode] with recursive file counts, extensions, children
    5. filter_significant() — removes shallow dirs, resource-only trees, marks passthroughs
    6. BlueprintFolderMapper.map_all(blueprint, folder_paths)
         → dict[path, FolderBlueprint] with has_blueprint_coverage flag
    │
    ├── enable_ai_enrichment=False (deterministic only)
    │     For each folder:
    │       is_passthrough? → render_passthrough()
    │       has_blueprint_coverage? → render_from_blueprint()
    │       else → render_minimal()
    │
    └── enable_ai_enrichment=True (hybrid)
          HybridEnrichmentEngine.enrich_all()
            → Process by depth (deepest first), parallel within depth (max_concurrent=5)
            → Per folder: read top 5 priority files (tiktoken-budgeted)
            → Call Claude with intent_layer_enrichment prompt
            → Returns dict[path, FolderEnrichment]
          For each folder:
            is_passthrough? → render_passthrough()
            else → render_hybrid(node, folder_blueprint, enrichment)
    │
    7. CodebaseMapRenderer.render(blueprint) → CODEBASE_MAP.md
    8. agent_file_generator.generate_all(blueprint) → root CLAUDE.md, AGENTS.md, rules
    9. Save manifest for incremental tracking
    10. Return IntentLayerOutput with all files
```

### Rendering Modes

| Mode | When used | Content |
|------|-----------|---------|
| `render_passthrough` | Namespace-only folders (0 source files, 1 child) | One-line pointer to child |
| `render_minimal` | No blueprint coverage, no AI | Header, navigation, file list, extensions |
| `render_from_blueprint` | Blueprint coverage, no AI | 13 sections: navigation, what-goes-here, key files, tasks, pitfalls, dependencies, naming, contracts, etc. |
| `render_hybrid` | AI enrichment enabled | AI content (purpose, patterns, key file guides, anti-patterns, code examples) + blueprint data (placement rules, templates, subfolders). Hard 200-line cap. |

### AI Enrichment Details

The `HybridEnrichmentEngine` processes folders bottom-up:

1. **Priority files** — Top 5 files per folder, ranked by tier (app/index/main files first), max 1,500 tokens each, max 5,000 tokens total per folder
2. **Child propagation** — Child purpose and top patterns bubble up to parent prompts
3. **Previous content** — Existing CLAUDE.md content fed into the AI prompt for refinement
4. **Output** — `FolderEnrichment` with: purpose, patterns, key file guides (file + purpose + modification guide), common task (task + steps), anti-patterns, testing/debugging insights, decisions, code examples, key imports

### Generated Outputs

```
blueprints/{repo_id}/intent_layer/
├── CLAUDE.md                          # Root — from agent_file_generator
├── AGENTS.md                          # Multi-agent guidance
├── CODEBASE_MAP.md                    # Flat architecture overview
├── .claude/rules/*.md                 # Claude Code rule files
├── .cursor/rules/*.md                 # Cursor IDE rule files
├── src/CLAUDE.md                      # Per-folder context
├── src/api/CLAUDE.md
├── src/api/routes/CLAUDE.md
├── src/application/services/CLAUDE.md
└── ... (one per significant folder)
```

---

## Incremental Re-Analysis

When re-analyzing a repository, the system supports two modes:

### Full Mode (`mode=full`)

Re-runs the entire pipeline from scratch: clone, scan, 7-9 AI calls for blueprint, copy repo, then N AI calls for per-folder enrichment.

### Incremental Mode (`mode=incremental`)

Reuses cached AI enrichment for folders whose deterministic content hasn't changed:

1. **Commit SHA tracking** — Each analysis stores the HEAD commit SHA (`analyses.commit_sha` column, migration `002_add_commit_sha.sql`)
2. **Manifest diffing** — The `ManifestManager` stores content hashes of deterministic renders (not AI-enriched content) in `intent_layer_manifest.json`
3. **On re-analysis:**
   - Build deterministic content for all folders (no AI, cheap)
   - Compare content hashes against the stored manifest
   - If blueprint hash changed → everything is new (full re-enrichment)
   - For unchanged folders → load cached final output from `blueprints/{repo_id}/intent_layer/`
   - For changed folders → re-run AI enrichment
4. **Fallback** — If cached file reads fail, folders fall back to re-enrichment

### UI Flow

When clicking re-analyze on a repo with an existing blueprint, a dialog offers:
- **Incremental** (faster) — Skips unchanged folders
- **Full** — Re-runs everything from scratch

First-time analysis always runs in full mode.

### API

The `POST /{owner}/{repo}/analyze` endpoint accepts a `mode` field in the request body:

```json
{
  "mode": "incremental",
  "prompt_config": {}
}
```

---

## Web vs Mobile Platform Handling

The pipeline provides first-class support for **web**, **Android**, and **iOS** projects. All platform-specific logic is additive.

### Platform Detection

| Signal | Web | Android | iOS | Cross-Platform |
|--------|-----|---------|-----|----------------|
| **Framework keywords** | react, vue, angular, svelte | jetpack compose | swiftui, uikit | flutter, react-native |
| **File extensions** | .tsx, .jsx, .vue, .svelte | .kt, .java | .swift, .m, .mm | .dart |
| **Build/config files** | package.json | build.gradle, AndroidManifest.xml | .xcodeproj, Podfile | pubspec.yaml |

Detection happens in `_detect_frontend()` which checks 31 indicators. If any match, the frontend analysis phase runs.

### Source Code Extensions

```
.py .js .ts .tsx .jsx .java .go .rs .swift .kt .rb .php
.cs .cpp .c .h .hpp .m .mm .scala .xml
```

The intent layer's `filter_significant()` uses these extensions to determine which folders contain actual source code. Android resource directories (`drawable`, `values`, `mipmap`, etc.) have `.xml` excluded from the source code check since those are data files, not code.

---

## StructuredBlueprint Data Model

Defined in `domain/entities/blueprint.py`. This is the single source of truth — every output derives from it.

### Top-Level Structure

```python
class StructuredBlueprint(BaseModel):
    meta: BlueprintMeta               # Repository info, architecture style, platforms
    architecture_rules: ArchitectureRules  # File placement, naming conventions
    decisions: ArchitectureDecisions   # Style choice, rationale, trade-offs
    components: ComponentMap           # Named components with locations and responsibilities
    communication: CommunicationMap    # Patterns, selection guide
    quick_reference: QuickReference    # Where-to-put-code map, error mapping
    technology: TechnologyStack        # Categorized tech stack inventory
    deployment: DeploymentEnvironment  # Runtime, compute, CI/CD, distribution (auto-detected)
    frontend: FrontendArchitecture     # Framework, rendering, state, styling (optional)
    implementation_guidelines: list[ImplementationGuideline]  # How existing capabilities were built
```

### Key Sections

**`architecture_rules`** — What the MCP tools enforce:
- `file_placement_rules[]` — Component type, location, naming pattern, example
- `naming_conventions[]` — Scope (classes, files, etc.), pattern, examples

**`components`** — Discovered architectural components with location, responsibility, dependencies, public interface.

**`communication`** — Patterns (name, when to use, how it works) and pattern selection guide.

**`deployment`** — Auto-detected deployment/distribution environment. Fields: `runtime_environment`, `compute_services[]`, `container_runtime`, `orchestration`, `serverless_functions`, `ci_cd[]`, `distribution[]`, `infrastructure_as_code`, `supporting_services[]`, `environment_config`, `key_files[]`. Detection covers cloud providers (GCP, AWS, Azure), PaaS (Vercel, Netlify, Fly.io), mobile distribution (App Store, Play Store), package registries (npm, PyPI), and desktop distribution. Infrastructure files are scanned via `INFRASTRUCTURE_FILE_NAMES` in `analysis_settings.py` and injected into the technology analysis phase.

**`frontend`** (populated only when frontend code is detected) — Framework, rendering strategy, styling, state management, routing, data fetching, key conventions.

**`implementation_guidelines`** — How existing capabilities were built (libraries, patterns, key files, usage examples).

### Intent Layer Data Model (`domain/entities/intent_layer.py`)

| Model | Purpose |
|-------|---------|
| `FolderNode` | Folder in hierarchy: path, files, depth, children, extensions, is_passthrough |
| `FolderBlueprint` | Blueprint data projected onto a folder (deterministic) |
| `FolderEnrichment` | AI-produced content: purpose, patterns, key file guides, common task, anti-patterns, code examples |
| `IntentLayerConfig` | Configuration: max_depth, min_files, max_concurrent, excluded_dirs, AI model settings |
| `IntentLayerOutput` | Pipeline output: claude_md_files dict, folder_count, skipped_folder_count, total_ai_calls |
| `GenerationManifest` | Incremental tracking: blueprint_hash + content hashes |
| `FolderManifestEntry` | Single file hash entry |

### Source File Retention

After analysis, the `SourceFileCollector` copies the entire repo to `storage/repos/{repo_id}/`. The intent layer reads files from this storage for AI enrichment context. The frontend can view files via `GET /api/v1/workspace/repositories/{id}/source-files/{path}`. MCP tools `list_source_files` and `get_file_content` provide the same access.

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

### Tools

| Tool | Parameters | Returns | Description |
|------|-----------|---------|-------------|
| `get_repository_blueprint` | — | Full blueprint JSON | Returns the complete `StructuredBlueprint` |
| `list_repository_sections` | — | Section IDs and names | Lists addressable blueprint sections |
| `get_repository_section` | `section_id` | Section content | Token-efficient alternative to full blueprint |
| `where_to_put` | `component_type` | Directory, naming pattern, example | Returns correct file location |
| `check_naming` | `scope`, `name` | Pass/fail with convention details | Validates name against conventions |
| `how_to_implement` | `feature` | Libraries, patterns, key files, example | Look up existing implementation (fuzzy search) |
| `list_implementations` | — | All implementation guidelines | Lists all documented capabilities |
| `how_to_implement_by_id` | `implementation_id` | Specific guideline | Look up by index |
| `list_source_files` | — | File list with sizes | List all collected source files |
| `get_file_content` | `file_path` | File content | Read a collected source file |

### Connecting from an IDE

```json
{
  "mcpServers": {
    "architecture-blueprints": {
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

---

## Delivery Pipeline

Pushes generated outputs to a target GitHub repository via the GitHub API.

### Architecture

Outputs are **pre-generated** during analysis (stored at `blueprints/{repo_id}/intent_layer/`). At delivery time, files are loaded from storage — not regenerated.

### Output Categories

| Output Key | Target Paths | Merge Strategy |
|-----------|-------------|----------------|
| `claude_md` | `CLAUDE.md` (root only) | Markdown (gbr fenced section) |
| `agents_md` | `AGENTS.md` | Markdown (gbr fenced section) |
| `intent_layer` | `**/CLAUDE.md` (per-folder) | Direct write (fully generated) |
| `codebase_map` | `CODEBASE_MAP.md` | Direct write |
| `claude_rules` | `.claude/rules/*.md` | Direct write |
| `cursor_rules` | `.cursor/rules/*.md` | Direct write |
| `mcp_claude` | `.mcp.json` | JSON (key-level merge) |
| `mcp_cursor` | `.cursor/mcp.json` | JSON (key-level merge) |

### Merge Strategies

**Markdown merge** — Uses HTML comment markers for root-level files only:
```markdown
<!-- gbr:start repo=my-repo -->
(generated content here)
<!-- gbr:end -->
```

**JSON merge** — Only upserts the `mcpServers.architecture-blueprints` key; other keys are preserved.

**Direct write** — Per-folder CLAUDE.md files and rule files are fully generated and pushed as-is.

### Delivery Strategies

| Strategy | Behavior |
|----------|----------|
| `pr` | Creates a new branch, commits files, opens a pull request |
| `commit` | Commits files directly to the default branch |

Both strategies use the PyGithub Git Trees API for atomic multi-file commits.

---

## API Reference

All routes are prefixed with `/api/v1` and registered in `api/app.py`.

### Repositories (`/api/v1/repositories`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List repositories |
| `POST` | `/{owner}/{repo}/analyze` | Start analysis (accepts `mode: "full" \| "incremental"`) |

### Analyses (`/api/v1/analyses`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List analyses |
| `GET` | `/{id}` | Get analysis details |
| `GET` | `/{id}/events` | Stream analysis events (SSE) |
| `GET` | `/{id}/stream` | Stream analysis progress (SSE) |
| `GET` | `/{id}/analysis-data` | Get all phase data |
| `GET` | `/{id}/agent-files` | Get generated files (loads from intent layer storage) |
| `GET` | `/{id}/blueprint` | Get blueprint (`?format=json`) |

### Delivery (`/api/v1/delivery`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/preview` | Preview outputs without pushing |
| `POST` | `/apply` | Push outputs to target GitHub repo |

**Preview/Apply request:**
```json
{
  "source_repo_id": "uuid",
  "target_repo": "owner/repo",
  "token": "ghp_...",
  "outputs": ["claude_md", "agents_md", "intent_layer", "codebase_map", "claude_rules", "cursor_rules", "mcp_claude"],
  "strategy": "pr"
}
```

### Workspace (`/api/v1/workspace`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/repositories` | List analyzed repositories |
| `GET` | `/active` | Get active repository |
| `PUT` | `/active` | Set active repository |
| `DELETE` | `/active` | Clear active repository |
| `GET` | `/repositories/{id}/agent-files` | Get agent files for repo |
| `GET` | `/repositories/{id}/blueprint` | Get blueprint |
| `GET` | `/repositories/{id}/source-files/{path}` | Get source file content |
| `DELETE` | `/repositories/{id}` | Delete repository analysis |

### Other Routes

| Route Group | Purpose |
|------------|---------|
| `/api/v1/auth` | GitHub token authentication |
| `/api/v1/settings` | Ignored dirs, library capabilities configuration |
| `/api/v1/prompts` | Prompt CRUD + revision history |
| `/health` | Health check |
| `/mcp/sse` | MCP SSE stream |

---

## Database Schema

PostgreSQL with pgvector extension. Migrations in `backend/migrations/`.

### Migrations

| File | Purpose |
|------|---------|
| `001_initial_setup.sql` | Tables, indexes, seed data (idempotent) |
| `002_add_commit_sha.sql` | Adds `commit_sha` column to `analyses` table |

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | User accounts | `id`, `github_token_encrypted`, `created_at` |
| `user_profiles` | User preferences | `id`, `user_id`, `active_repository_id`, `preferences` |
| `repositories` | Tracked repositories | `id`, `user_id`, `owner`, `name`, `full_name`, `language` |
| `analyses` | Analysis runs | `id`, `repository_id`, `status`, `progress_percentage`, `error_message`, `commit_sha` |
| `analysis_prompts` | Prompt definitions | `id`, `name`, `category`, `prompt_template`, `variables`, `key` |
| `prompt_revisions` | Prompt revision history | `id`, `prompt_id`, `revision_number`, `prompt_template` |
| `analysis_data` | Phase inputs/outputs | `id`, `analysis_id`, `data_type`, `data` (JSONB) |
| `analysis_events` | SSE event log | `id`, `analysis_id`, `event_type`, `message` |
| `embeddings` | Code chunk vectors | `id`, `repository_id`, `file_path`, `chunk_type`, `embedding` (vector(384)) |
| `discovery_ignored_dirs` | Directories to skip | `id`, `directory_name` (unique) |
| `library_capabilities` | Library-to-capability mappings | `id`, `library_name` (unique), `ecosystem`, `capabilities` |

---

## Frontend (Web UI)

### Architecture

The frontend is a **Single Page Application** (SPA). The dashboard (`index.tsx`) manages all views via an `activeView` state variable.

### View Components

| Component | Purpose |
|-----------|---------|
| `RepositoryView` | Repository list, public repo URL analysis, re-analyze dialog (full/incremental) |
| `AnalysisView` | Real-time analysis progress via SSE |
| `BlueprintView` | Tabbed view of all outputs with file tree browser for per-folder CLAUDE.md |
| `SettingsView` | Ignored directories, library capabilities configuration |

### Blueprint View Features

- **File tree sidebar** with search, expand/collapse, and compact path merging (e.g., `src/api` instead of two levels)
- **Per-folder CLAUDE.md browsing** — Navigate generated context files for every significant folder
- **Delivery panel** with output toggles for: CLAUDE.md, AGENTS.md, per-folder context, CODEBASE_MAP.md, Claude rules, Cursor rules, MCP configs

### Re-Analyze Dialog

When re-analyzing a repo with an existing blueprint, a confirmation dialog appears with:
- **Incremental** — Faster, reuses cached enrichment for unchanged folders
- **Full** — Complete re-analysis from scratch

---

## Configuration

### Database Backends

| Backend | `DB_BACKEND` | Setup |
|---------|-------------|-------|
| **Local PostgreSQL** (recommended) | `postgres` | `docker compose up -d` — PostgreSQL (pgvector) + Redis |
| **Supabase** (cloud) | `supabase` | Create project at supabase.com, run migration SQL |

### Backend Environment Variables

Generated by `./run` at `backend/.env.local`:

```bash
# ── Database Backend ──────────────────────────────────────────
DB_BACKEND=postgres                # "postgres" (recommended) or "supabase"

# For postgres (recommended):
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/architecture_mcp

# For supabase (alternative):
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-supabase-anon-key

# ── AI (REQUIRED) ────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_AI_MODEL=claude-haiku-4-5-20251001
SYNTHESIS_AI_MODEL=claude-haiku-4-5-20251001
SYNTHESIS_MAX_TOKENS=64000

# ── Redis (optional — without it, analysis runs in-process) ──
REDIS_URL=redis://localhost:6379

# ── Optional ─────────────────────────────────────────────────
GITHUB_TOKEN=ghp_...               # Server-side GitHub token
STORAGE_PATH=./storage
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# ── Intent Layer ─────────────────────────────────────────────
INTENT_LAYER_ENABLE_AI_ENRICHMENT=true
INTENT_LAYER_MAX_CONCURRENT=5
INTENT_LAYER_MIN_FILES=2
INTENT_LAYER_GENERATE_CODEBASE_MAP=true
```

**Removed variables** (safe to delete from old `.env.local` files): `VECTOR_DB_TYPE`, `STORAGE_TYPE`, `MAX_ANALYSIS_WORKERS`, `RAG_ENABLED`, `EMBEDDING_PROVIDER`, `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `PINECONE_API_KEY`, `GCS_BUCKET_NAME`, `S3_BUCKET_NAME`, `AWS_*`. The app ignores unknown env vars.

### Frontend Environment Variables

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Prompt Customization

`backend/prompts.json` is the **only** source of truth for prompt content. After editing prompts, bump `"version"` — `./run` will auto-reseed on next start.

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
PYTHONPATH=src python -m pytest tests/unit/services/test_intent_layer_service.py -v

# Single test by name
PYTHONPATH=src python -m pytest tests/unit/services/ -k "test_incremental"
```

### Test Structure

```
tests/unit/
├── services/
│   ├── test_intent_layer_service.py      # Intent layer + incremental enrichment (22 tests)
│   ├── test_intent_layer_renderer.py     # Rendering modes (passthrough, minimal, blueprint, hybrid)
│   ├── test_hybrid_enrichment.py         # AI enrichment engine
│   ├── test_blueprint_folder_mapper.py   # Blueprint-to-folder mapping
│   ├── test_codebase_map_renderer.py     # CODEBASE_MAP.md generation
│   ├── test_local_repo_handler.py        # Local file I/O
│   ├── test_agent_file_generator.py      # Root CLAUDE.md, Cursor rules, AGENTS.md
│   ├── test_delivery_service.py          # Delivery + merge logic
│   ├── test_unified_features.py          # Frontend detection, unified pipeline
│   ├── test_mobile_support.py            # Android/iOS platform support
│   └── ...
├── workers/
│   └── test_analysis_workflows.py        # ARQ + in-process workflow tests
└── infrastructure/
    ├── test_github_push_client.py        # GitHub API operations
    ├── test_mcp_utils.py                 # MCP tools and resources
    └── ...
```

### Test Conventions

- Tests use `pytest` with `pytest-asyncio` for async tests
- Mocking via `unittest.mock` (`MagicMock`, `AsyncMock`, `patch`)
- Fixtures provide sample blueprints, mock storage, mock push clients

---

## Extending the System

### Adding a New MCP Tool

1. Define the tool function in `infrastructure/mcp/tools.py`
2. Register it with the MCP server in `infrastructure/mcp/server.py`
3. The tool should read from `StructuredBlueprint` — never write to it
4. Add tests in `tests/unit/infrastructure/test_mcp_utils.py`

### Adding a New Analysis Phase

1. Add the prompt to `prompts.json` with a unique key
2. Add the phase call in `phased_blueprint_generator.py`
3. Store results via `analysis_data_collector`
4. If the phase produces new data, extend `StructuredBlueprint` in `domain/entities/blueprint.py`
5. Add tests in `tests/unit/services/`

### Adding a New Output Format

1. Add a generator function in `agent_file_generator.py` (or a new file)
2. Add the output key to `_should_include()` in `delivery_service.py`
3. Wire it into the intent layer save logic in `analysis_service.py`
4. Add tests for the generator and delivery behavior

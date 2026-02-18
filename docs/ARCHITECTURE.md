# Architecture Blueprints — Developer Documentation

Comprehensive technical documentation covering system architecture, analysis pipeline internals, API reference, database schema, MCP server, delivery pipeline, and contribution guidelines.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Backend Architecture](#backend-architecture)
5. [Analysis Pipeline](#analysis-pipeline)
6. [StructuredBlueprint Data Model](#structuredblueprint-data-model)
7. [MCP Server](#mcp-server)
8. [Delivery Pipeline](#delivery-pipeline)
9. [API Reference](#api-reference)
10. [Database Schema](#database-schema)
11. [Frontend](#frontend)
12. [Configuration](#configuration)
13. [Testing](#testing)
14. [Extending the System](#extending-the-system)

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
│   │   │   ├── routes/                   # Route modules (11 files)
│   │   │   │   ├── analyses.py           # Analysis CRUD + streaming
│   │   │   │   ├── repositories.py       # Repository management + analyze trigger
│   │   │   │   ├── delivery.py           # Preview + apply delivery
│   │   │   │   ├── architecture.py       # Architecture rules + validation
│   │   │   │   ├── auth.py               # GitHub token auth
│   │   │   │   ├── workspace.py          # Workspace management
│   │   │   │   ├── prompts.py            # Prompt CRUD
│   │   │   │   ├── unified_blueprints.py # Multi-repo blueprints
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
├── README.md                           # Project overview
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
- **Frontend auto-detection** — `_detect_frontend()` checks for React, Vue, Angular, Next.js, Flutter, SwiftUI indicators and branches to unified synthesis when found

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
| Dependencies | `requirements.txt`, `package.json`, `go.mod`, `Cargo.toml`, etc. | ~1500 chars |
| Config files | `tsconfig.json`, `docker-compose.yml`, `.env.example`, etc. | ~4000 chars |
| Code samples | 10 representative files chosen by heuristics | ~5000 chars |

All gathered data is persisted to Supabase via `analysis_data_collector` with `data_type: "gathered"`.

#### Stage 2: RAG Indexing (`rag_retriever.py`) — Optional

For codebases with 50+ files, RAG indexing enables phase-specific code retrieval:

1. **Chunking** — Each code file is split by function/class boundaries using tree-sitter AST parsing
2. **Embedding** — Each chunk is embedded using `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
3. **Storage** — Vectors are stored in Supabase's pgvector extension
4. **Retrieval** — Each analysis phase queries with semantic terms and gets the top-15 most relevant chunks

```sql
-- pgvector similarity search (used internally)
SELECT file_path, metadata,
       1 - (embedding <=> query_embedding) as similarity
FROM embeddings
WHERE repository_id = $1
ORDER BY embedding <=> query_embedding
LIMIT 15;
```

Without RAG, each phase receives the same 10 static code samples. With RAG, each phase gets different, relevant code from across the entire codebase.

#### Stage 3: Phased AI Analysis (`phased_blueprint_generator.py`)

Six to eight sequential Claude API calls, each building on the outputs of previous phases:

| Phase | Input | Output | Purpose |
|-------|-------|--------|---------|
| **0. Observation** | File signatures from up to 300 files (~200 tokens each: path + imports + class/function names) | Architecture style, detected components, custom RAG search terms | Architecture-agnostic detection. Generates custom queries instead of assuming "service/repository/controller" |
| **1. Discovery** | File tree + dependencies + config files + observation results | Project type, entry points, module organization, config approach | Understand what the project is |
| **2. Layers** | Discovery output + file tree + RAG code samples | Layer definitions, dependency rules, structure type | Identify architectural boundaries |
| **3. Patterns** | Discovery + layers + RAG code samples | Structural patterns, behavioral patterns, cross-cutting concerns | Extract design patterns |
| **4. Communication** | All previous + RAG code samples | Internal/external communication, integrations, pattern selection guide | Map how components communicate |
| **5. Technology** | All previous + dependencies | Complete tech stack inventory | Document all technologies |
| **6. Frontend** (conditional) | Discovery results checked for frontend indicators | Frontend framework, rendering, state management, styling, conventions | Only runs if frontend code detected |
| **7. Synthesis** | All phase outputs combined | `StructuredBlueprint` JSON | Produce the final structured model |

Each phase's prompt is loaded from `prompts.json` via `PromptLoader` and rendered with template variables.

**Observation-first approach:** Traditional analysis assumes patterns like "service layer" or "repository pattern." The observation phase scans all file signatures first and detects the actual architecture style — whether that's actor-based, event-sourced, CQRS, feature-sliced, or something custom. It then generates targeted RAG queries for that specific architecture.

#### Stage 4: Blueprint Storage

The synthesis phase produces a `StructuredBlueprint` Pydantic model. This is serialized to JSON and stored at `storage/blueprints/{repository_id}/blueprint.json`.

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
2. **RAG retrieval** — Only ~5000 chars of the most relevant code per phase, selected by semantic search
3. **Progressive context** — Each phase outputs a compact JSON summary (~500-2500 chars) that feeds into the next
4. **Smart truncation** — Data is truncated with tracked limits; both gathered and sent sizes are stored for transparency

Per-phase context budget:

| Phase | File Tree | Dependencies | Code Samples | Previous Context | Total |
|-------|-----------|-------------|--------------|------------------|-------|
| Discovery | 3,000 | 1,500 | 4,000 | — | ~8,500 |
| Layers | 2,500 | — | 5,000 | 1,500 | ~9,000 |
| Patterns | — | — | 6,000 | 2,500 | ~8,500 |
| Communication | — | — | 5,000 | 3,000 | ~8,000 |
| Technology | — | 2,000 | 3,000 | 3,500 | ~8,500 |
| Synthesis | — | — | 4,000 | 12,500 | ~16,500 |

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

---

## MCP Server

The MCP server runs as part of the FastAPI backend via SSE transport at `/mcp/sse`.

### Architecture

```
FastAPI app
  └── /mcp/sse (Starlette mount, raw ASGI)
        └── SseServerTransport
              └── MCP Server (mcp SDK)
                    ├── Tools (5)
                    └── Resources (dynamic)
```

Defined in `infrastructure/mcp/`. The server is mounted as a raw ASGI app in `api/app.py` via Starlette to avoid FastAPI middleware interference with the SSE stream.

### Tools

| Tool | Parameters | Returns | Description |
|------|-----------|---------|-------------|
| `where_to_put` | `component_type` | Directory, naming pattern, example | Returns correct file location for a component type |
| `check_naming` | `name`, `scope` | Pass/fail with convention details | Validates name against naming conventions |
| `get_repository_blueprint` | — | Full blueprint JSON | Returns the complete `StructuredBlueprint` |
| `list_repository_sections` | — | Section IDs and names | Lists addressable blueprint sections |
| `get_repository_section` | `section_id` | Section content | Token-efficient alternative to full blueprint |

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

### Architecture (`/api/v1/architecture`)

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
| `DELETE` | `/repositories/{id}` | Delete repository analysis |

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

PostgreSQL hosted on Supabase with pgvector extension. A single initial migration in `backend/migrations/001_initial_setup.sql` creates all tables, indexes, and functions.

### Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | User accounts | `id`, `created_at`, `updated_at` |
| `repositories` | Tracked repositories | `id`, `user_id`, `owner`, `name`, `full_name`, `language`, `default_branch` |
| `analyses` | Analysis runs | `id`, `repository_id`, `status`, `progress_percentage`, `error_message`, `started_at`, `completed_at` |
| `blueprints` | Generated blueprints | `id`, `repository_id`, `analysis_id`, `blueprint_path` |
| `unified_blueprints` | Multi-repo blueprints | `id`, `name`, `description`, `strategy` |
| `analysis_prompts` | Prompts used per analysis | `id`, `analysis_id`, `phase`, `prompt_used` |
| `analysis_configurations` | Per-repo analysis config | `id`, `repository_id`, `config_data` |
| `analysis_data` | Phase inputs/outputs | `id`, `analysis_id`, `data_type`, `data_json` |
| `analysis_events` | SSE event log | `id`, `analysis_id`, `event_type`, `message` |
| `embeddings` | Code chunk vectors | `id`, `repository_id`, `file_path`, `chunk_type`, `embedding` (vector(384)), `metadata` |
| `architecture_rules` | Extracted rules | `id`, `repository_id`, `rule_type`, `rule_data` |
| `repository_architecture` | Architecture state | `id`, `repository_id`, `architecture_config` |
| `repository_architecture_config` | Architecture source config | `id`, `repository_id`, `reference_blueprint_id`, `strategy` |

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
| `phase_backend_synthesis` | Synthesis phase input/output |
| `summary` | Overall metrics (chars sent, phase count, timestamps) |

### pgvector

The `embeddings` table uses a `vector(384)` column for storing sentence-transformer embeddings. The `match_embeddings` SQL function performs cosine similarity search:

```sql
CREATE FUNCTION match_embeddings(
    query_embedding vector(384),
    match_repository_id uuid,
    match_count int DEFAULT 15
) RETURNS TABLE(...)
```

---

## Frontend

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

### Backend Environment Variables

Create `backend/.env.local`:

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret
ANTHROPIC_API_KEY=sk-ant-...

# Optional
GITHUB_TOKEN=ghp_...               # Server-side GitHub token (users can also provide their own)
REDIS_URL=redis://localhost:6379    # Optional — enables ARQ worker for background analysis; without it, analysis runs in-process
ENVIRONMENT=development
DEBUG=true
HOST=0.0.0.0
PORT=8000

# AI Model Configuration
DEFAULT_AI_MODEL=claude-haiku-4-5-20251001
SYNTHESIS_AI_MODEL=claude-haiku-4-5-20251001
SYNTHESIS_MAX_TOKENS=10000

# Storage
STORAGE_TYPE=local                 # local, gcs, or s3
STORAGE_PATH=./storage
TEMP_STORAGE_PATH=./temp

# Optional cloud storage
GCS_BUCKET_NAME=your-bucket
S3_BUCKET_NAME=your-bucket
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

### Frontend Environment Variables

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Prompt Customization

All AI prompts live in `backend/prompts.json`. Each key maps to a phase:

```json
{
  "prompts": {
    "discovery": {
      "name": "Discovery Analysis",
      "category": "discovery",
      "prompt_template": "You are analyzing a codebase...\n{repository_name}\n{file_tree}...",
      "variables": ["repository_name", "file_tree", "dependencies", "config_files"]
    }
  }
}
```

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
│   └── ...
├── workers/
│   └── test_analysis_workflows.py      # ARQ + in-process workflow tests (23 tests)
└── infrastructure/
    ├── test_github_push_client.py      # GitHub API operations
    ├── test_mcp_utils.py               # MCP tools and resources
    └── ...
```

Current test count: **389 unit tests**.

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

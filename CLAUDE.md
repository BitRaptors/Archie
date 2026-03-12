# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AI-powered system that analyzes GitHub repositories, generates Archie blueprints (structured JSON), and produces derivative outputs: human-readable markdown, CLAUDE.md, Cursor rules, and MCP tools for AI agent integration. The structured `StructuredBlueprint` (Pydantic model) is the single source of truth — all outputs derive from it.

## Commands

### Backend (Python FastAPI)
```bash
cd backend

# Run dev server (requires .env.local — see Environment section below)
PYTHONPATH=src uvicorn main:app --reload --port 8000

# Tests (use venv)
PYTHONPATH=src python -m pytest tests/unit/services/ -v          # Service tests (reliable)
PYTHONPATH=src python -m pytest tests/unit/services/test_unified_features.py -v  # Single file
PYTHONPATH=src python -m pytest tests/unit/services/ -k "test_detects_react"     # Single test

# Lint
ruff check src/ tests/
ruff check --fix src/ tests/    # Auto-fix
```

### Frontend (Next.js)
```bash
cd frontend
npm run dev       # Dev server (port 4000)
npm run build     # Production build
npm run lint      # ESLint
```

### MCP Server
The MCP server runs as part of the FastAPI backend via SSE transport at `/mcp/sse`.

## Architecture

### Monorepo Layout
- `backend/` — Python FastAPI, Clean Architecture (DDD layers)
- `frontend/` — Next.js 14 + React 18 + TypeScript + Tailwind (App)

### Backend Layers (`backend/src/`)
- **`api/`** — FastAPI routes, DTOs, middleware. Routes registered in `api/app.py`.
- **`application/services/`** — Business logic orchestration. Key services:
  - `analysis_service.py` — Main orchestrator: clone repo → extract data → run phased analysis → store blueprint
  - `phased_blueprint_generator.py` — Multi-phase AI analysis pipeline (observation → smart file reading → discovery → layers → patterns → communication → technology → [frontend] → implementation analysis → synthesis)
  - `blueprint_renderer.py` — Deterministic JSON→Markdown renderer
  - `agent_file_generator.py` — Generates CLAUDE.md, Cursor rules, AGENTS.md from blueprint JSON
  - `source_file_collector.py` — Copies the full cloned repository to persistent storage (`storage/repos/{repo_id}/`) after analysis, skipping `.git`, `node_modules`, etc.
  - `delivery_service.py` — Pushes architecture outputs to target GitHub repos (via PR or direct commit)
- **`application/agents/`** — Background workers: `orchestrator.py` coordinates `analysis_worker.py`, `sync_worker.py`, `validation_worker.py`
- **`domain/entities/`** — Pydantic models. `blueprint.py` defines `StructuredBlueprint` (schema v2.0.0) — the central data model everything derives from.
- **`domain/interfaces/`** — Repository interfaces (ports)
- **`infrastructure/`** — Adapters: `persistence/` (Supabase), `analysis/` (RAG, AST, embeddings), `mcp/` (MCP server + tools), `prompts/` (prompt loader), `storage/` (local/GCS/S3)
- **`config/`** — `settings.py` (Pydantic settings from `.env.local`), `container.py` (dependency-injector DI)

### Analysis Pipeline Flow
1. **Data Extraction** — File tree, dependencies, config files, code samples
2. **RAG Indexing** (optional) — Embed code chunks into pgvector; file-level retrieval returns full files (not fragments); phase-specific chunk type preferences boost relevance
3. **Observation Phase** — Full file signature scan, architecture-agnostic detection, identifies priority files per phase
4. **Smart File Reading** — Dynamic budget based on repo size (small: read all; medium: 400KB; large: 250KB). Supplementary reading fills remaining budget for small repos.
5. **File Registry Grounding** — Compact list of all source file paths injected into every phase prompt as a constraint. Prevents hallucinated file paths in output.
6. **Phased AI Analysis** — 7-9 Claude API calls building understanding incrementally, each phase uses priority files → RAG → code samples (cascade)
7. **Frontend Detection** — Auto-detects frontend (React, Vue, Angular, etc.) from discovery results
8. **Implementation Analysis** — Identifies existing capabilities using third-party libraries (e.g., push notifications, maps, auth)
9. **Synthesis** — Produces `StructuredBlueprint` JSON (unified or backend-only)
10. **Source File Retention** — Copies the full repo to `storage/repos/{repo_id}/` before temp dir is cleaned (skips .git, node_modules, etc.)
11. **Rendering** — Blueprint → markdown (with clickable `source://` file links), CLAUDE.md, Cursor rules, AGENTS.md

### Key Data Model
`StructuredBlueprint` (`domain/entities/blueprint.py`) contains: `meta`, `architecture_rules`, `decisions`, `components`, `communication`, `quick_reference`, `technology`, `deployment`, `frontend`, `implementation_guidelines`. The `deployment` section is auto-detected from infrastructure files (Docker, cloud configs, CI/CD, etc.) covering cloud providers, PaaS, mobile distribution, package registries, and desktop distribution. The `frontend` section is populated only when frontend code is detected. The `implementation_guidelines` section documents how existing capabilities were built (libraries, patterns, key files).

### Prompts
`backend/prompts.json` is the **only** source of truth for prompt content. Each key maps to a phase of analysis. The `PromptLoader` reads from file; the `DatabasePromptLoader` reads from the `analysis_prompts` table. **After changing `prompts.json`, bump its `"version"` field — `./run` will auto-reseed on next start.** (Or manually: `cd backend && PYTHONPATH=src python scripts/seed_prompts.py`). The migration SQL does NOT seed prompts — `seed_prompts.py` handles that via upsert.

### Database
Supabase PostgreSQL with pgvector. Single initial migration in `backend/migrations/001_initial_setup.sql`. Key tables: `repositories`, `analyses`, `blueprints`, `unified_blueprints`, `analysis_data`, `embeddings`, `architecture_rules`.

### MCP Server
Defined in `backend/src/infrastructure/mcp/`. Served via SSE transport at `/mcp/sse` (mounted in `api/app.py` as raw ASGI app via Starlette). Exposes tools (`where_to_put`, `check_naming`, `get_repository_blueprint`, `how_to_implement`, `list_implementations`, `how_to_implement_by_id`, `list_source_files`, `list_repository_sections`, `get_repository_section`, `get_file_content`) and resources. The delivery pipeline can push `.mcp.json` and `.cursor/mcp.json` configs to target repos.

### Delivery Pipeline
`delivery_service.py` + `api/routes/delivery.py` + `infrastructure/external/github_push_client.py`. Pushes generated outputs (CLAUDE.md, AGENTS.md, Cursor rules, MCP configs) to a target GitHub repository via branch+PR or direct commit. Uses PyGithub Trees API for atomic multi-file commits.

## Key Patterns

- **Dependency injection** via `dependency-injector` (`config/container.py`) — all services receive dependencies through constructor injection
- **Repository pattern** — domain interfaces in `domain/interfaces/`, implementations in `infrastructure/persistence/`
- **RAG fallback** — If RAG indexing fails or Supabase unavailable, analysis falls back to code samples
- **`analysis_data_collector`** — Shared singleton that persists per-phase analysis data to Supabase; initialized on app startup
- **Frontend auto-detection** — `_detect_frontend()` in the generator checks for React, Vue, Angular, Next.js, Flutter, SwiftUI, etc. indicators and branches to unified synthesis when found

## Documentation

When making changes that affect architecture, APIs, configuration, database schema, or project structure, update the following files to keep them in sync:

- **`docs/ARCHITECTURE.md`** — Comprehensive technical documentation (pipeline internals, API reference, database schema, MCP server, delivery pipeline, extending the system). Must reflect any new routes, services, config options, database tables, or MCP tools.
- **`README.md`** — Project overview, setup instructions, and usage guide. Must reflect any changes to prerequisites, environment variables, startup commands, or user-facing workflows.

## Environment

Backend requires `.env.local` in `backend/`. The `DB_BACKEND` variable determines which database credentials are needed:

**Required (always):**
- `ANTHROPIC_API_KEY` — Claude API key

**Required for `DB_BACKEND=supabase`:**
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_KEY` — Supabase anon/service key

**Required for `DB_BACKEND=postgres`:**
- `DATABASE_URL` — PostgreSQL connection string (uses Docker via `docker-compose.yml`)

**Optional:**
- `GITHUB_TOKEN` — GitHub API token (users can also provide their own per-request)
- `REDIS_URL` — Redis connection string (enables ARQ worker for background analysis; without Redis, analysis runs in-process automatically)
- `SUPABASE_JWT_SECRET` — Only needed if JWT verification is enabled

**Removed variables** (safe to delete from old `.env.local` files): `VECTOR_DB_TYPE`, `STORAGE_TYPE`, `MAX_ANALYSIS_WORKERS`, `RAG_ENABLED`, `EMBEDDING_PROVIDER`, `OPENAI_API_KEY`. The app ignores unknown env vars.

Frontend requires `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

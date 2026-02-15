# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

AI-powered system that analyzes GitHub repositories, generates architecture blueprints (structured JSON), and produces derivative outputs: human-readable markdown, CLAUDE.md, Cursor rules, and MCP tools for AI agent integration. The structured `StructuredBlueprint` (Pydantic model) is the single source of truth — all outputs derive from it.

## Commands

### Backend (Python FastAPI)
```bash
cd backend

# Run dev server (requires .env.local with SUPABASE_URL, SUPABASE_KEY, SUPABASE_JWT_SECRET, ANTHROPIC_API_KEY)
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
- `frontend/` — Next.js 14 + React 18 + TypeScript + Tailwind

### Backend Layers (`backend/src/`)
- **`api/`** — FastAPI routes, DTOs, middleware. Routes registered in `api/app.py`.
- **`application/services/`** — Business logic orchestration. Key services:
  - `analysis_service.py` — Main orchestrator: clone repo → extract data → run phased analysis → store blueprint
  - `phased_blueprint_generator.py` — Multi-phase AI analysis pipeline (observation → discovery → layers → patterns → communication → technology → [frontend] → synthesis)
  - `blueprint_renderer.py` — Deterministic JSON→Markdown renderer
  - `agent_file_generator.py` — Generates CLAUDE.md, Cursor rules, AGENTS.md from blueprint JSON
  - `delivery_service.py` — Pushes architecture outputs to target GitHub repos (via PR or direct commit)
- **`application/agents/`** — Background workers: `orchestrator.py` coordinates `analysis_worker.py`, `sync_worker.py`, `validation_worker.py`
- **`domain/entities/`** — Pydantic models. `blueprint.py` defines `StructuredBlueprint` (schema v2.0.0) — the central data model everything derives from.
- **`domain/interfaces/`** — Repository interfaces (ports)
- **`infrastructure/`** — Adapters: `persistence/` (Supabase), `analysis/` (RAG, AST, embeddings), `mcp/` (MCP server + tools), `prompts/` (prompt loader), `storage/` (local/GCS/S3)
- **`config/`** — `settings.py` (Pydantic settings from `.env.local`), `container.py` (dependency-injector DI)

### Analysis Pipeline Flow
1. **Data Extraction** — File tree, dependencies, config files, code samples
2. **RAG Indexing** (optional) — Embed code chunks into pgvector for semantic search
3. **Observation Phase** — Full file signature scan, architecture-agnostic detection
4. **Phased AI Analysis** — 6-8 Claude API calls building understanding incrementally
5. **Frontend Detection** — Auto-detects frontend (React, Vue, Angular, etc.) from discovery results
6. **Synthesis** — Produces `StructuredBlueprint` JSON (unified or backend-only)
7. **Rendering** — Blueprint → markdown, CLAUDE.md, Cursor rules, AGENTS.md

### Key Data Model
`StructuredBlueprint` (`domain/entities/blueprint.py`) contains: `meta`, `architecture_rules`, `decisions`, `components`, `communication`, `quick_reference`, `technology`, `frontend`. The `frontend` section is populated only when frontend code is detected.

### Prompts
All AI prompts live in `backend/prompts.json` (38KB). Each key maps to a phase of analysis. The `PromptLoader` (`infrastructure/prompts/prompt_loader.py`) renders them with template variables.

### Database
Supabase PostgreSQL with pgvector. Migrations in `backend/migrations/` (16 SQL files). Key tables: `repositories`, `analyses`, `blueprints`, `unified_blueprints`, `analysis_data`, `embeddings`, `architecture_rules`.

### MCP Server
Defined in `backend/src/infrastructure/mcp/`. Served via SSE transport at `/mcp/sse` (mounted in `api/app.py` as raw ASGI app via Starlette). Exposes tools (`validate_import`, `where_to_put`, `check_naming`, `get_repository_blueprint`) and resources. The delivery pipeline can push `.mcp.json` and `.cursor/mcp.json` configs to target repos.

### Delivery Pipeline
`delivery_service.py` + `api/routes/delivery.py` + `infrastructure/external/github_push_client.py`. Pushes generated outputs (CLAUDE.md, AGENTS.md, Cursor rules, MCP configs) to a target GitHub repository via branch+PR or direct commit. Uses PyGithub Trees API for atomic multi-file commits.

## Key Patterns

- **Dependency injection** via `dependency-injector` (`config/container.py`) — all services receive dependencies through constructor injection
- **Repository pattern** — domain interfaces in `domain/interfaces/`, implementations in `infrastructure/persistence/`
- **RAG fallback** — If RAG indexing fails or Supabase unavailable, analysis falls back to code samples
- **`analysis_data_collector`** — Shared singleton that persists per-phase analysis data to Supabase; initialized on app startup
- **Frontend auto-detection** — `_detect_frontend()` in the generator checks for React, Vue, Angular, Next.js, Flutter, SwiftUI, etc. indicators and branches to unified synthesis when found

## Environment

Backend requires `.env.local` in `backend/` with: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET`, `ANTHROPIC_API_KEY`. Optional: `GITHUB_TOKEN`, `REDIS_URL`. Frontend requires `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

# AGENTS.md

> Agent guidance for **BitRaptors/Archie**
> Generated: 2026-03-12T09:17:36.250579+00:00

Archie is a code analysis and architecture documentation platform that ingests GitHub or local repositories, runs multi-phase AI analysis via Claude, and produces structured blueprints, intent layers, and agent config files. The backend is Python/FastAPI with domain-driven design, async task processing via ARQ/Redis, and dual Supabase/Postgres persistence. The main frontend is a Next.js dashboard for managing analyses and viewing results; the landing app is a separate Next.js site with 3D visuals. Communication between frontend and backend uses REST + SSE for streaming analysis progress.

---

## Tech Stack

- **3d_graphics:** Three.js latest
- **ai_client:** Anthropic SDK >=0.7.0
- **animation:** GSAP + Lenis latest
- **backend_framework:** FastAPI >=0.104.0
- **backend_runtime:** Python 3.11
- **cache_queue:** Redis 7-alpine
- **database_driver:** asyncpg >=0.29.0
- **database_managed:** Supabase >=2.0.0
- **diagrams:** Mermaid latest
- **embeddings:** sentence-transformers >=2.2.0
- **frontend_framework:** Next.js 16.1.6
- **http_client:** Axios latest
- **linting_backend:** Ruff + mypy >=0.1.0
- **styling:** Tailwind CSS ^4 (landing), 3.x (frontend)
- **task_queue:** ARQ >=0.23.0
- **testing:** pytest + pytest-asyncio >=7.4.0
- **ui_primitives:** Radix UI / shadcn latest
- **validation:** Pydantic >=2.5.0

## Deployment

**Runs on:** Google Cloud Platform — Cloud Run for backend API; Supabase for managed PostgreSQL; Redis on Docker (local) or managed Redis (production)
**Compute:** Google Cloud Run — containerized FastAPI backend (backend/Dockerfile), Vercel or self-hosted — Next.js frontend and landing (deployment target not specified in repo)
**Container:** Docker — python:3.11-slim base image defined in backend/Dockerfile + None (Cloud Run is fully managed; no Kubernetes)
**CI/CD:**
- Google Cloud Build — backend/cloudbuild.yaml: build Docker image → push to GCR (gcr.io) → deploy to Cloud Run
**Distribution:**
- Docker image pushed to Google Container Registry (GCR)
- Cloud Run pulls image and serves backend API

## Commands

```bash
# dev_all
python start-dev.py
# backend_only
cd backend && .venv/bin/python src/main.py
# frontend_only
cd frontend && npm run dev
# landing_only
cd landing && npm run dev
# worker
cd backend && PYTHONPATH=src .venv/bin/python -m arq workers.tasks.WorkerSettings
# test_backend
cd backend && .venv/bin/pytest tests/
# lint_backend
cd backend && .venv/bin/ruff check src/
# setup
./setup.sh
```

## Project Structure

```
archie/
├── start-dev.py          # Dev orchestrator
├── backend/
│   ├── src/
│   │   ├── main.py
│   │   ├── api/          # Routes, DTOs, middleware
│   │   ├── application/  # Services, agents
│   │   ├── domain/       # Entities, interfaces, exceptions
│   │   ├── infrastructure/ # Persistence, external, analysis, MCP
│   │   ├── workers/      # ARQ tasks
│   │   └── config/       # Settings, DI container
│   ├── tests/            # unit + integration
│   ├── migrations/       # SQL migration files
│   ├── Dockerfile
│   └── cloudbuild.yaml
├── frontend/             # Next.js dashboard (pages router)
│   ├── pages/
│   ├── components/
│   ├── hooks/api/
│   ├── services/
│   ├── context/
│   └── lib/
└── landing/              # Next.js marketing site (app router)
    ├── app/
    └── components/
```

## Code Style

- **backend_services:** PascalCase class, snake_case methods (e.g. `PhasedBlueprintGenerator`, `analysis_service.py`, `smart_refresh_service.py`)
- **backend_interfaces:** I{Name} prefix for abstract interfaces (e.g. `IUserRepository`, `IAnalysisRepository`, `DatabaseClient`)
- **frontend_components:** PascalCase files and exports (e.g. `AnalysisView.tsx`, `BlueprintView.tsx`, `Shell.tsx`)
- **frontend_hooks:** use{Feature} camelCase (e.g. `useAuth`, `useWorkspace`, `useRepositoriesQuery`)

### backend_route: New FastAPI domain route module

File: `backend/src/api/routes/{domain}.py`

```
from fastapi import APIRouter, Depends
router = APIRouter(prefix='/{domain}', tags=['{domain}'])
@router.get('/')
async def list_items(service=Depends(get_service)): ...
```

### frontend_api_hook: Custom hook wrapping service layer

File: `frontend/hooks/api/use{Feature}.ts`

```
import { useState, useEffect } from 'react';
import { featureService } from '@/services/{feature}';
export function use{Feature}() { const [data, setData] = useState(null); ... }
```

### domain_entity: New domain entity dataclass

File: `backend/src/domain/entities/{entity}.py`

```
from dataclasses import dataclass
from datetime import datetime
@dataclass
class {Entity}:
    id: str
    created_at: datetime
```

## Development Rules

### Ci Cd

- Never push Docker images manually — backend/cloudbuild.yaml defines the full build/push/deploy pipeline to GCR and Cloud Run; trigger via GCP Cloud Build *(source: `backend/cloudbuild.yaml`)*

### Code Style

- Never place infrastructure imports (asyncpg, supabase SDK, anthropic) inside domain/entities/ or domain/interfaces/ — domain layer must stay framework-free *(source: `backend/src/domain/interfaces/database.py (pure ABC, no imports from infra)`)*
- Never modify files in frontend/components/ui/ directly — these are shadcn/radix primitives; extend by composing them in feature components under frontend/components/views/ *(source: `frontend/components/ui/ structure mirroring shadcn/ui generation pattern`)*

### Dependency Management

- Always add Python dependencies to backend/requirements.txt with pinned minimum versions; never use poetry or pipenv — the project uses plain pip with venv at backend/.venv *(source: `backend/requirements.txt + start-dev.py venv creation logic`)*
- Always use npm for frontend and landing dependencies; run npm install in the respective directory (frontend/ or landing/) — no yarn or pnpm detected *(source: `frontend/package.json, landing/package.json, start-dev.py npm run dev invocation`)*

### Environment

- Always create backend/.env.local and frontend/.env.local from .env.example before running; start-dev.py will hard-exit if either is missing *(source: `start-dev.py check_env_files() function`)*
- Always run ./setup.sh after pulling commits that change prompts.json — start-dev.py validates prompts version against .prompts-version and refuses to start on mismatch *(source: `start-dev.py version check block reading backend/prompts.json and backend/.prompts-version`)*

### Testing

- Always write async tests using pytest-asyncio for any code touching asyncpg, ARQ, or Anthropic SDK; use unittest.mock.AsyncMock for async dependencies *(source: `backend/tests/conftest.py + backend/tests/unit/services/test_phased_blueprint_generator.py pattern`)*

## Boundaries

### Always

- Run tests before committing
- Use `where_to_put` MCP tool before creating files
- Use `check_naming` MCP tool before naming components
- Follow file placement rules (see `.claude/rules/architecture.md`)

### Ask First

- Database schema changes
- Adding new dependencies
- Modifying CI/CD configuration
- Changes to deployment configuration

### Never

- Commit secrets or API keys
- Edit vendor/node_modules directories
- Remove failing tests without authorization

## Testing

- **pytest + pytest-asyncio >=7.4.0** — Backend unit and integration tests

```bash
# test_backend
cd backend && .venv/bin/pytest tests/
# lint_backend
cd backend && .venv/bin/ruff check src/
```

## Common Workflows

### Add a new analysis capability / feature flag
Files: `backend/src/domain/entities/analysis_settings.py`, `backend/src/api/routes/settings.py`, `backend/src/api/dto/requests.py`, `frontend/components/views/CapabilitiesSettingsView.tsx`, `frontend/services/settings.ts`
1. Add new field to AnalysisSettings entity in domain/entities/analysis_settings.py
2. Update settings DTO in api/dto/requests.py and settings route in api/routes/settings.py
3. Add toggle UI in CapabilitiesSettingsView.tsx; update frontend/services/settings.ts to send new field

### Add a new background analysis task
Files: `backend/src/workers/tasks.py`, `backend/src/workers/worker.py`, `backend/src/application/services/analysis_service.py`
1. Define async task function in backend/src/workers/tasks.py with ctx parameter
2. Register task in WorkerSettings.functions list in backend/src/workers/worker.py
3. Enqueue from analysis_service.py using arq queue.enqueue('task_name', **kwargs)

### Add a new REST endpoint with frontend integration
Files: `backend/src/api/routes/{domain}.py`, `backend/src/api/app.py`, `frontend/services/{domain}.ts`, `frontend/hooks/api/use{Domain}.ts`
1. Create route handler in backend/src/api/routes/{domain}.py using APIRouter; add DTOs
2. Register router in backend/src/api/app.py include_router call
3. Add Axios call in frontend/services/{domain}.ts; create frontend/hooks/api/use{Domain}.ts hook consuming it

### Run and debug analysis pipeline locally
Files: `start-dev.py`, `backend/.env.local`, `frontend/.env.local`, `backend/src/workers/tasks.py`
1. Ensure backend/.env.local and frontend/.env.local exist (copy from .env.example); set ANTHROPIC_API_KEY, REDIS_URL, DB credentials
2. Start Redis via docker-compose or local install; run python start-dev.py to launch backend + ARQ worker + frontend
3. Trigger analysis via dashboard at localhost:{frontend_port}; watch worker logs for PhasedBlueprintGenerator phases

## Pitfalls & Gotchas

- **ARQ Worker / Redis:** If Redis is unavailable at startup, start-dev.py falls back to in-process analysis silently — but production deployments require Redis for task persistence. Lost tasks are not retried.
  - *Always verify Redis connection before deploying; check REDIS_URL in backend/.env.local; monitor Redis memory to prevent queue overflow*
- **DB Backend Selection:** DB_BACKEND env var controls PostgresAdapter vs SupabaseAdapter selection in db_factory.py; wrong value silently uses wrong adapter, causing query failures.
  - *Explicitly set DB_BACKEND='postgres' or DB_BACKEND='supabase' in .env.local; run backend/tests/unit/infrastructure/test_db_factory.py to verify*
- **Prompts Version Mismatch:** start-dev.py checks prompts.json version against .prompts-version file and hard-exits if mismatched — running without ./setup.sh after a pull will block startup.
  - *Always run ./setup.sh after pulling changes that bump prompts.json version*
- **pgvector Embeddings:** SharedEmbedder loads full sentence-transformers model on first use (5-10s); vector column dimension must match model output (e.g. 384 for all-MiniLM-L6-v2) or inserts will fail silently.
  - *Use singleton pattern (already in shared_embedder.py); ensure vector(N) column dimension matches model in migrations/001_initial_setup.sql*
- **SSE Frontend Connection:** SSE streams from /analyses/{id}/stream are long-lived; if the frontend component unmounts without closing the EventSource, connections leak and Redis/ARQ events accumulate.
  - *Always close EventSource in useEffect cleanup function in the consuming hook*

## Architecture MCP Server

The `architecture-blueprints` MCP server is the single source of truth.
Call its tools for every architecture decision.

| Tool | When to Use |
|------|------------|
| `where_to_put` | Before creating or moving any file |
| `check_naming` | Before naming any new component |
| `list_implementations` | Discovering available implementation patterns |
| `how_to_implement_by_id` | Getting full details for a specific capability |
| `how_to_implement` | Fuzzy search when exact capability name unknown |
| `get_file_content` | Reading source files referenced in guidelines |

## File Placement

- **new_api_endpoint** → `backend/src/api/routes/{domain}.py — add route, register in app.py`
- **new_business_logic** → `backend/src/application/services/{feature}_service.py`
- **new_domain_entity** → `backend/src/domain/entities/{entity}.py`
- **new_db_query** → `backend/src/infrastructure/persistence/{entity}_repository.py`
- **new_frontend_page** → `frontend/pages/{name}.tsx — auto-routed by Next.js`
- **new_frontend_view** → `frontend/components/views/{Feature}View.tsx`
- **new_api_hook** → `frontend/hooks/api/use{Feature}.ts`
- **new_http_service** → `frontend/services/{domain}.ts`

---
*Auto-generated from structured architecture analysis.*
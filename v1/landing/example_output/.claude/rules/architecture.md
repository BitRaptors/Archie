## Components

### API Layer
- **Location:** `backend/src/api/`
- **Responsibility:** FastAPI routes, DTOs, error middleware, SSE streaming
- **Depends on:** Application Layer, Domain Layer

### Application Layer
- **Location:** `backend/src/application/services/`
- **Responsibility:** Orchestrates use cases; coordinates domain + infra; runs analysis workflows
- **Depends on:** Domain Layer, Infrastructure Layer

### Domain Layer
- **Location:** `backend/src/domain/`
- **Responsibility:** Core entities, abstract interfaces, domain exceptions; no framework dependencies

### Infrastructure Layer
- **Location:** `backend/src/infrastructure/`
- **Responsibility:** Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus
- **Depends on:** Domain Layer

### Workers
- **Location:** `backend/src/workers/`
- **Responsibility:** ARQ background job processing for long-running analyses
- **Depends on:** Application Layer

### Frontend Dashboard
- **Location:** `frontend/`
- **Responsibility:** Next.js dashboard for repo management, analysis results, settings, blueprint viewing
- **Depends on:** Backend API

### Landing Page
- **Location:** `landing/`
- **Responsibility:** Marketing site with Three.js shader background and GSAP scroll animations

## File Placement

| Component Type | Location | Naming | Example |
|---------------|----------|--------|---------|
| api_route | `backend/src/api/routes/` | `{domain}.py` | `backend/src/api/routes/analyses.py` |
| application_service | `backend/src/application/services/` | `{feature}_service.py` | `backend/src/application/services/analysis_service.py` |
| domain_entity | `backend/src/domain/entities/` | `{entity}.py` | `backend/src/domain/entities/analysis.py` |
| repository_impl | `backend/src/infrastructure/persistence/` | `{entity}_repository.py` | `backend/src/infrastructure/persistence/analysis_repository.py` |
| frontend_view | `frontend/components/views/` | `{Feature}View.tsx` | `frontend/components/views/AnalysisView.tsx` |
| api_hook | `frontend/hooks/api/` | `use{Domain}.ts(x)` | `frontend/hooks/api/useWorkspace.ts` |

## Where to Put Code

- **new_api_endpoint** -> `backend/src/api/routes/{domain}.py — add route, register in app.py`
- **new_business_logic** -> `backend/src/application/services/{feature}_service.py`
- **new_domain_entity** -> `backend/src/domain/entities/{entity}.py`
- **new_db_query** -> `backend/src/infrastructure/persistence/{entity}_repository.py`
- **new_frontend_page** -> `frontend/pages/{name}.tsx — auto-routed by Next.js`
- **new_frontend_view** -> `frontend/components/views/{Feature}View.tsx`
- **new_api_hook** -> `frontend/hooks/api/use{Feature}.ts`
- **new_http_service** -> `frontend/services/{domain}.ts`

## Naming Conventions

- **backend_services**: PascalCase class, snake_case methods (e.g. `PhasedBlueprintGenerator`, `analysis_service.py`, `smart_refresh_service.py`)
- **backend_interfaces**: I{Name} prefix for abstract interfaces (e.g. `IUserRepository`, `IAnalysisRepository`, `DatabaseClient`)
- **frontend_components**: PascalCase files and exports (e.g. `AnalysisView.tsx`, `BlueprintView.tsx`, `Shell.tsx`)
- **frontend_hooks**: use{Feature} camelCase (e.g. `useAuth`, `useWorkspace`, `useRepositoriesQuery`)
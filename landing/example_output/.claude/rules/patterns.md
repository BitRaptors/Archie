## Communication Patterns

### REST JSON (Frontend → Backend)
- **When:** All CRUD operations from dashboard
- **How:** Axios in frontend/services/*.ts sends JWT Bearer token; FastAPI validates and routes to services

### Server-Sent Events (SSE)
- **When:** Real-time analysis progress streaming
- **How:** Backend streams analysis events via sse-starlette; frontend consumes via EventSource

### ARQ Task Queue via Redis
- **When:** Long-running analysis jobs
- **How:** API enqueues job to Redis; ARQ worker picks up and runs PhasedBlueprintGenerator; results saved to DB

### Dependency Injection Container
- **When:** Wiring services, repos, DB clients at startup
- **How:** config/container.py creates singletons; FastAPI Depends() injects into route handlers

### Domain Event Bus
- **When:** Analysis lifecycle notifications
- **How:** Services publish AnalysisEvent objects to event_bus.py; subscribers persist events and trigger downstream actions

## Pattern Selection Guide

| Scenario | Pattern | Rationale |
|----------|---------|-----------|
| User triggers new analysis | POST REST → ARQ enqueue → worker runs PhasedBlueprintGenerator | Analysis takes minutes; must not block HTTP thread |
| Frontend polls analysis status | SSE stream from GET /analyses/{id}/stream | Avoids polling; backend pushes events as they are persisted |
| Service needs DB access | Inject DatabaseClient via DI container; use repository interface | Keeps services DB-agnostic; adapter swapped at runtime |

## Quick Pattern Lookup

- **long_running_task** -> Enqueue via ARQ in backend/src/workers/tasks.py
- **stream_progress** -> SSE via sse-starlette in analyses route
- **global_frontend_state** -> React Context in frontend/context/auth.tsx pattern
- **server_data_fetching** -> Custom hook in frontend/hooks/api/ calling frontend/services/

## Key Decisions

### Dual Database Backend via Adapter Pattern
**Chosen:** Abstract DatabaseClient interface with PostgresAdapter (asyncpg) and SupabaseAdapter
**Rationale:** Supports both managed Supabase and raw Postgres deployments from one codebase

### Async Task Queue for Analysis Workflows
**Chosen:** ARQ (Async Redis Queue) for long-running analysis jobs
**Rationale:** Prevents HTTP timeout on multi-phase LLM analysis; enables progress streaming via SSE

### Phased LLM Analysis with RAG Context
**Chosen:** Multi-phase Claude API calls with pgvector RAG retrieval per phase
**Rationale:** Reduces single request token size; retrieves relevant code per phase for accuracy

### Monorepo with Separate Frontend Apps
**Chosen:** backend/ + frontend/ + landing/ as independent apps in one repo
**Rationale:** Shared deployment tooling; landing and dashboard have different tech requirements (Three.js vs dashboard UI)

### MCP Integration for Claude Tool Use
**Chosen:** Model Context Protocol server embedded in infrastructure layer
**Rationale:** Exposes analysis resources and tools directly to Claude via MCP protocol
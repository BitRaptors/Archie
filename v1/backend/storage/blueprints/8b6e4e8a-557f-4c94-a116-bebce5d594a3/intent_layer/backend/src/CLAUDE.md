# src/
> Entry point: bootstraps FastAPI app, wires container/middleware/routes, runs uvicorn server with environment-driven config.

## Patterns

- create_app() factory in api/ returns configured FastAPI instance—called once at module load, stored as `app`
- Settings singleton injected via get_settings()—read once, reused for host/port/debug/reload configuration
- uvicorn.run() uses string module path 'main:app' to enable hot-reload without circular imports
- reload_dirs conditional on debug flag—prevents file watching overhead in production
- No service initialization here—defer to api.app.create_app() which wires Container in lifespan

## Navigation

**Parent:** [`backend/`](../CLAUDE.md)
**Peers:** [`scripts/`](../scripts/CLAUDE.md) | [`tests/`](../tests/CLAUDE.md)
**Children:** [`api/`](api/CLAUDE.md) | [`application/`](application/CLAUDE.md) | [`config/`](config/CLAUDE.md) | [`domain/`](domain/CLAUDE.md) | [`infrastructure/`](infrastructure/CLAUDE.md) | [`workers/`](workers/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `main.py` | CLI entry point: parse settings, launch uvicorn | Add new startup logic to create_app() lifespan, not here. Keep main.py minimal. |
| `__init__.py` | Package marker (empty) | Do not export—this is internal src namespace. Exports go through api/ or config/. |

## Key Imports

- `from api.app import create_app`
- `from config.settings import get_settings`

## Change server startup config (host, port, debug mode, reload dirs)

1. Update SETTINGS env vars or .env file (HOST, PORT, DEBUG)
2. Restart uvicorn—settings read once at module load via get_settings()
3. Reload logic auto-detects debug flag and applies reload_dirs

## Don't

- Don't initialize Container or services in main.py—async lifespan setup belongs in api.app.create_app()
- Don't hardcode host/port/debug—always read from Settings singleton via get_settings()
- Don't call uvicorn.run() with app object directly—use string path 'main:app' to enable reload

## Testing

- Unit test: mock get_settings() return value, verify uvicorn.run() called with correct args
- Integration test: run main.py against test .env, curl localhost:test_port to verify create_app() bootstrapped

## Debugging

- If reload not working: check debug=True in settings AND reload_dirs=['src'] is set
- If container not accessible in routes: verify create_app() stores app.container in lifespan before app returns

## Why It's Built This Way

- Minimal main.py: all orchestration pushed to create_app() and Container—keeps entry point stateless and testable
- uvicorn string path + reload_dirs: enables hot-reload without reimporting app, critical for dev velocity

## What Goes Here

- new_api_endpoint → `backend/src/api/routes/{domain}.py — add route, register in app.py`
- new_business_logic → `backend/src/application/services/{feature}_service.py`
- new_domain_entity → `backend/src/domain/entities/{entity}.py`
- new_db_query → `backend/src/infrastructure/persistence/{entity}_repository.py`

## Dependencies

**Depends on:** `Domain Layer`, `Infrastructure Layer`
**Exposes to:** `API Layer`, `Workers`

## Templates

### backend_route
**Path:** `backend/src/api/routes/{domain}.py`
```
from fastapi import APIRouter, Depends
router = APIRouter(prefix='/{domain}', tags=['{domain}'])
@router.get('/')
async def list_items(service=Depends(get_service)): ...
```

### domain_entity
**Path:** `backend/src/domain/entities/{entity}.py`
```
from dataclasses import dataclass
from datetime import datetime
@dataclass
class {Entity}:
    id: str
    created_at: datetime
```

## Subfolders

- [`api/`](api/CLAUDE.md) — FastAPI routes, DTOs, error middleware, SSE streaming
- [`application/`](application/CLAUDE.md) — Orchestrates use cases; coordinates domain + infra; runs analysis workflows
- [`config/`](config/CLAUDE.md) — 
- [`domain/`](domain/CLAUDE.md) — Core entities, abstract interfaces, domain exceptions; no framework dependencies
- [`infrastructure/`](infrastructure/CLAUDE.md) — Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus
- [`workers/`](workers/CLAUDE.md) — ARQ background job processing for long-running analyses

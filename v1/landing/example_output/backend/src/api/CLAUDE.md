# api/
> FastAPI application factory: wires container, middleware, routes, lifespan; entry point for all HTTP endpoints.

## Patterns

- Lifespan context manager (asynccontextmanager) manages Container resource init/shutdown and MCP session lifecycle — all bootstrapping happens here.
- Container stored in app.state (app.container) — child routes access via request.app.container for dependency resolution.
- Exception handler chain: global handler logs all exceptions; DomainException caught separately and mapped to HTTP status via middleware.
- Routes mounted with /api/v1 prefix uniformly — no inline route definitions, all routers imported from api.routes submodules.
- MCP mounted as raw Starlette ASGI app via app.mount(), not FastAPI router — required for non-HTTP protocol support.
- analysis_data_collector initialized once with db instance during lifespan — cross-process shared state pattern.

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`application/`](../application/CLAUDE.md) | [`config/`](../config/CLAUDE.md) | [`domain/`](../domain/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)
**Children:** [`dto/`](dto/CLAUDE.md) | [`middleware/`](middleware/CLAUDE.md) | [`routes/`](routes/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `app.py` | Application factory and lifespan orchestration | Edit create_app() to add routes; edit lifespan() for resource lifecycle changes. |

## Key Imports

- `from config.container import Container`
- `from domain.exceptions.domain_exceptions import DomainException`
- `from api.middleware.error_handler import domain_exception_handler`

## Add a new API route group

1. Create router in api.routes/my_feature.py with FastAPI Router
2. Import router in app.py: from api.routes import my_feature
3. Register: app.include_router(my_feature.router, prefix=/api/v1)

## Usage Examples

### Registering a new router in app factory
```python
from api.routes import my_feature
app.include_router(
    my_feature.router,
    prefix="/api/v1"
)
```

## Don't

- Don't inline route definitions here — keep all routes in api.routes submodules and import/register them.
- Don't initialize container resources outside lifespan — guarantees init/shutdown ordering and cleanup.
- Don't log database exceptions only in global handler — DomainException handler must dispatch first for domain-aware HTTP status codes.

## Testing

- Test lifespan: verify container.init_resources() and shutdown_resources() called; MCP session manager context entered/exited.
- Test exception handling: raise DomainException, verify domain_exception_handler called; raise generic Exception, verify global handler returns 500.

## Debugging

- MCP lifecycle issues: check if session_mgr.run() context hangs — trace get_session_manager() return None vs real manager.
- Container resolution failures in routes: app.container must exist in lifespan before any route tries request.app.container access.

## Why It's Built This Way

- MCP mounted as raw ASGI app, not FastAPI router, because MCP is multi-protocol (HTTP + SSE + stdio) and needs lower-level Starlette control.
- analysis_data_collector initialized in lifespan with db instance (not in route handlers) to guarantee single initialization across worker processes.

## What Goes Here

- new_api_endpoint → `backend/src/api/routes/{domain}.py — add route, register in app.py`

## Dependencies

**Depends on:** `Application Layer`, `Domain Layer`
**Exposes to:** `frontend`, `external clients`

## Templates

### backend_route
**Path:** `backend/src/api/routes/{domain}.py`
```
from fastapi import APIRouter, Depends
router = APIRouter(prefix='/{domain}', tags=['{domain}'])
@router.get('/')
async def list_items(service=Depends(get_service)): ...
```

## Subfolders

- [`dto/`](dto/CLAUDE.md) — FastAPI routes, DTOs, error middleware, SSE streaming
- [`middleware/`](middleware/CLAUDE.md) — FastAPI routes, DTOs, error middleware, SSE streaming
- [`routes/`](routes/CLAUDE.md) — FastAPI routes, DTOs, error middleware, SSE streaming

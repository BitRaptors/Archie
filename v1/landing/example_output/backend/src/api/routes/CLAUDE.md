# routes/
> FastAPI route handlers mapping HTTP endpoints to domain services; each route resolves dependencies via request container.

## Patterns

- Repository dependency pattern: async helper functions resolve from request.app.container, instantiate with db() — see settings.py, analyses.py
- DTO wrapping: response models convert domain entities to DTOs via model_dump() — AnalysisResponse, IgnoredDirectoryResponse
- Token resolution: resolve_github_token(request) fetches from env or Authorization header — delivery.py line 81
- SSE streaming generator: EventSourceResponse + async generator yields status, phase, log, completion events on 2s poll — analyses.py stream_analysis_progress
- Validation at route entry: check input, raise HTTPException(422/400/401/404) — library_capabilities validation, token checks
- Seed data pattern: immutable module constants (SEED_IGNORED_DIRS, SEED_LIBRARY_CAPABILITIES, ECOSYSTEM_OPTIONS) reset via replace_all()

## Navigation

**Parent:** [`api/`](../CLAUDE.md)
**Peers:** [`dto/`](../dto/CLAUDE.md) | [`middleware/`](../middleware/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `settings.py` | Ignored dirs + library capability CRUD, reset to seed. | Add new setting: create DTO, repo method, GET/PUT/POST routes, seed constant. |
| `analyses.py` | List, fetch, stream, and retrieve analysis data/events. | SSE streaming uses analysis_data_collector.get_data() and event polling — avoid blocking calls. |
| `delivery.py` | Preview and apply architecture outputs to GitHub or local. | Validate strategy, resolve token, call DeliveryService — map DTOs to service args. |
| `auth.py` | GitHub token validation and config exposure. | Token validation delegates to GitHubService — route only validates, doesn't implement logic. |
| `repositories.py` | Repository discovery, cloning, settings per repo. | Uses resolve_github_token() helper; similar structure to delivery.py. |

## Key Imports

- `from fastapi import APIRouter, HTTPException, Request`
- `from sse_starlette.sse import EventSourceResponse`
- `from application.services.<service_name> import <ServiceClass>`

## Add a new GET/PUT endpoint for a domain entity with repository persistence

1. Create DTO in api/dto/requests or responses
2. Create async helper function to resolve repo from request.app.container.db()
3. Define @router.get/put with DTO response_model and (body:DTO, request:Request) params
4. Call repo method, map entity to DTO via model_dump(), handle exceptions as HTTPException

## Usage Examples

### Repository dependency pattern with error handling
```python
async def _get_ignored_dirs_repo(request: Request) -> IgnoredDirsRepository:
    db = await request.app.container.db()
    return IgnoredDirsRepository(db=db)

@router.get("/ignored-dirs")
async def list_ignored_dirs(request: Request):
    repo = await _get_ignored_dirs_repo(request)
    dirs = await repo.get_all()
    return [IgnoredDirectoryResponse(**d.model_dump()) for d in dirs]
```

## Don't

- Don't fetch db() multiple times per route — cache in one helper and pass through
- Don't validate business logic in route; raise HTTPException(422) on DTO parse fail, delegate rest to service
- Don't block event streaming generator; poll with asyncio.sleep(2) and break on disconnected/status completion

## Testing

- Mock request.app.container.db() and verify repo method calls with correct args
- For SSE: mock analysis_data_collector.get_data() and event_repo, assert event_generator yields correct event types in order

## Debugging

- SSE stuck/slow: check asyncio.sleep(2) timing, verify analysis_data_collector.get_data() isn't blocking, ensure client disconnect check works
- Repository not found: trace resolve_github_token(request) — check env GITHUB_TOKEN, Authorization header, and GitHubService validation

## Why It's Built This Way

- Async helpers (_get_*_repo) deferred to each route for testability and to avoid passing container references
- SSE polling (2s intervals) chosen over WebSocket for simpler deployment and client reconnect resilience

## What Goes Here

- **One APIRouter file per domain feature** — `{domain}.py`
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

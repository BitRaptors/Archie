# tuck-in-tales-backend/
> FastAPI backend for Tuck-in Tales; Python async server with Supabase, OpenAI, Firebase integrations via environment config.

## Patterns

- config.py uses BaseSettings with os.getenv fallbacks—all external deps initialized at import time, graceful None if keys missing
- main.py registers routers under /api prefix via APIRouter(prefix='/api') then include_router—centralizes route organization
- Environment variables mandatory in .env (SUPABASE_URL, SUPABASE_ANON_KEY, OPENAI_API_KEY, FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
- Tests mock Supabase via dependency_overrides BEFORE AsyncClient creation, chain method calls (table→select→eq→maybe_single→execute)
- CORS enabled at app startup for frontend integration; Uvicorn runs on 127.0.0.1:8000 with --reload in dev
- Poetry manages Python dependencies (pyproject.toml); package.json is vestigial (contains only frontend Radix UI + Supabase JS)

## Navigation

**Parent:** [`root/`](../CLAUDE.md)
**Peers:** [`tuck-in-tales-frontend/`](../tuck-in-tales-frontend/CLAUDE.md) | [`tuck-in-tales-mobile/`](../tuck-in-tales-mobile/CLAUDE.md)
**Children:** [`src/`](src/CLAUDE.md) | [`tests/`](tests/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `pyproject.toml` | Python dependency manifest; defines FastAPI, Supabase client, OpenAI, Firebase versions | Add deps here, run poetry install, commit poetry.lock. Never edit lock directly. |
| `.env` | Sensitive config: Supabase, OpenAI, Firebase keys loaded by config.py at startup | Copy template from README, fill with actual credentials, never commit. Verify all required keys present. |
| `src/main.py` | FastAPI app instance, CORS config, router registration | Register new routers via include_router with /api prefix. Don't move app initialization. |
| `src/config.py` | BaseSettings class loads .env into typed config object at import | Add new env vars as class fields with defaults. Access via config instance, not os.getenv directly. |

## Key Imports

- `from fastapi import FastAPI, APIRouter, Depends`
- `from pydantic_settings import BaseSettings`
- `from supabase import create_client`

## Add new API endpoint with Supabase query

1. Create APIRouter subclass in src/routers/your_feature.py
2. Inject Supabase client via FastAPI dependency (mocked in tests)
3. Chain Supabase calls: table(name).select().eq(col, val).maybe_single().execute()
4. Register router in main.py with include_router(router, prefix='/api')

## Usage Examples

### Config pattern with BaseSettings
```python
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    supabase_url: str = os.getenv('SUPABASE_URL')
    openai_key: str = os.getenv('OPENAI_API_KEY')
    class Config:
        env_file = '.env'
```

### Router registration with /api prefix
```python
from fastapi import APIRouter
router = APIRouter(prefix='/api')
@router.get('/stories')
async def get_stories(): ...
app.include_router(router)
```

## Don't

- Don't use os.getenv directly in routes—use config.py BaseSettings; enables validation + typed access
- Don't create AsyncClient after dependency_overrides in tests—override first, then client; mocks won't attach otherwise
- Don't commit .env or firebase-service-account.json; add to .gitignore, provide example template in README

## Testing

- Mock Supabase client via app.dependency_overrides[get_supabase] = lambda: mock_client before AsyncClient(app)
- Chain mock methods matching SDK: table().select().eq().maybe_single().execute() returns {'data': [...], 'error': None}

## Debugging

- If env vars missing at startup: check .env exists in project root, all required keys set, no typos in config.py field names
- If Supabase mocks don't attach in tests: verify dependency_overrides set BEFORE AsyncClient instantiation, not after

## Why It's Built This Way

- BaseSettings + os.getenv fallback: graceful degradation if keys missing, no hard crash at import—enables local dev without full secrets
- Poetry over pip: lockfile reproducibility, monorepo-friendly, consistent with production environment pinning

## What Goes Here

- new_backend_route → `tuck-in-tales-backend/src/routes/{domain}.py + register in tuck-in-tales-backend/src/main.py`
- new_ai_workflow → `tuck-in-tales-backend/src/graphs/{domain}_generator.py`
- new_backend_model → `tuck-in-tales-backend/src/models/{domain}.py`

## Dependencies

**Depends on:** `Firebase Admin SDK`, `Supabase Client`, `User Model`
**Exposes to:** `API Routes`

## Templates

### backend_route
**Path:** `tuck-in-tales-backend/src/routes/{domain}.py`
```
router = APIRouter(prefix='/{domain}s', tags=['{domain}s'])
@router.post('/')
async def create(user_data: UserData = Depends(verify_firebase_token), supabase: Client = Depends(get_supabase_client)):
```

### langgraph_node
**Path:** `tuck-in-tales-backend/src/graphs/{domain}_generator.py`
```
async def generate_node(state: DomainState) -> DomainState:
    await send_sse_event(state['id'], 'status', {'msg': 'generating'})
    return {**state, 'result': result}
```

## Subfolders

- [`src/`](src/CLAUDE.md) — Verifies Firebase ID tokens; resolves or creates Supabase user records
- [`tests/`](tests/CLAUDE.md) — 

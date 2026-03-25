# backend-src/
> FastAPI application root: bootstraps CORS, routes, Firebase auth, and environment config for story generation API.

## Patterns

- Settings via pydantic_settings with os.getenv fallbacks; single instance `settings` exported for import everywhere
- APIRouter with /api prefix groups all child routers; include_router pattern chains multiple domains
- Firebase Admin SDK initialized on module import via separate init file (graceful degradation pattern)
- CORS origins hardcoded for dev (localhost:5173, localhost:3000); must update before production deploy
- Logging configured twice: basicConfig then explicit root logger setLevel (redundant but ensures INFO level)
- No __init__.py visible; child folders (routes, utils, models, graphs) are importable — package structure assumed

## Navigation

**Parent:** [`_restore/`](../CLAUDE.md)
**Children:** [`graphs/`](graphs/CLAUDE.md) | [`models/`](models/CLAUDE.md) | [`routes/`](routes/CLAUDE.md) | [`utils/`](utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `config.py` | Load .env vars; define Settings dataclass once | Add new ENV var: add class field with os.getenv default; instantiate settings once globally |
| `main.py` | FastAPI bootstrap; route registration; middleware setup | Add route: import router, include_router(router) under api_router. Never inline route logic |

## Key Imports

- `from src.config import settings (every route/util imports this)`
- `from src.routes import characters, stories, memories, family (main.py assembles these)`
- `from src.utils.firebase_admin_init import initialize_firebase_admin (startup hook)`

## Add new route domain (e.g., avatars endpoint)

1. Create src/routes/avatars.py with router = APIRouter(prefix='/avatars', tags=['avatars'])
2. Import router in main.py
3. Add api_router.include_router(avatars.router) before app.include_router(api_router)
4. All route handlers must call get_current_supabase_user and get_required_family_id for auth

## Usage Examples

### How settings is used in routes (pattern from children)
```python
from src.config import settings

@router.post('/generate-story')
async def create_story(req: StoryRequest):
    openai_model = settings.OPENAI_CHAT_MODEL
    # Use model...
```

## Don't

- Don't pass raw os.getenv in route handlers — use `settings.FIELD` only; config layer owns env reads
- Don't define CORS origins in code — move to env var before prod; localhost hardcoding breaks deployments
- Don't initialize Firebase or LLM clients in routes — init on import via utils, inject or fetch singleton

## Testing

- Smoke test: POST http://localhost:8000/ returns welcome message; confirms FastAPI startup
- Auth test: Call protected route without Firebase token; should fail 401 before reaching handler logic

## Debugging

- Logging INFO set twice (basicConfig + root setLevel) — if logs silent, check both levels haven't been overridden by child modules
- CORS errors in browser? Check origins list includes exact scheme+host+port; wildcard won't work for credentials=True

## Why It's Built This Way

- Settings instance created once at module level — allows config injection without dependency containers, matches FastAPI conventions
- Firebase init separated to utils.firebase_admin_init — keeps main.py clean, enables graceful failure if credentials missing

## Subfolders

- [`graphs/`](graphs/CLAUDE.md) — 
- [`models/`](models/CLAUDE.md) — 
- [`routes/`](routes/CLAUDE.md) — 
- [`utils/`](utils/CLAUDE.md) — 

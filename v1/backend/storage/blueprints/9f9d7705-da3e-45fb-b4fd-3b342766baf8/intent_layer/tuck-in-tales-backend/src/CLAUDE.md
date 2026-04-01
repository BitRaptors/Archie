# src/
> Application entry point and configuration loader: FastAPI server initialization with CORS, router registration, and environment variable management.

## Patterns

- config.py uses BaseSettings with os.getenv fallbacks—all external dependencies initialized at import time with graceful None fallback if keys missing
- main.py registers routers under /api prefix via APIRouter(prefix="/api") then include_router—centralizes route organization
- CORS configured with allow_origins=["*"] and allow_credentials=False—development-wide permissive, never flip without environment check
- Firebase Admin SDK initialization imported but not shown—verify initialize_firebase_admin() runs before first protected route access
- Settings instantiated once as module-level singleton—settings object imported everywhere, never re-instantiated
- Logging explicitly set at root level after app creation—INFO level, ensures child loggers inherit unless overridden

## Navigation

**Parent:** [`tuck-in-tales-backend/`](../CLAUDE.md)
**Peers:** [`tests/`](../tests/CLAUDE.md)
**Children:** [`graphs/`](graphs/CLAUDE.md) | [`models/`](models/CLAUDE.md) | [`routes/`](routes/CLAUDE.md) | [`utils/`](utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `config.py` | Environment variable loading via BaseSettings | Add new env vars as class attributes; os.getenv() fallback prevents crashes if missing |
| `main.py` | FastAPI app factory and router registration | New routers: import from src.routes, then api_router.include_router(module.router) |

## Key Imports

- `from src.config import settings`
- `from src.routes import characters, stories, memories, family, prompts`
- `from src.utils.firebase_admin_init import initialize_firebase_admin`

## Add new API endpoint domain (router)

1. Create src/routes/newdomain.py with FastAPI router, auth checks via get_required_family_id()
2. Import router in main.py: from src.routes import newdomain
3. Register: api_router.include_router(newdomain.router)
4. Test: POST http://localhost:8000/api/endpoint with valid Bearer token

## Usage Examples

### Access settings in any module
```python
from src.config import settings

db_url = settings.SUPABASE_URL
api_key = settings.OPENAI_API_KEY or "MISSING"
```

## Don't

- Don't initialize clients in routers—init once in config.py or utils/* at import time, inject via dependency or global reference
- Don't hardcode origins in CORS—environment-gate allow_origins=["*"] to dev only; production must whitelist
- Don't assume Settings fields exist—use os.getenv() with defaults or Optional[str] to handle missing API keys gracefully

## Testing

- POST/PATCH to protected endpoints: include Authorization: Bearer {firebase_token} header; unauth requests return 401
- SSE streaming: connect to /api/endpoint/stream, verify event: message type and payload JSON before response close

## Why It's Built This Way

- Prefix all routes under /api—simplifies frontend routing and allows non-API endpoints at root later
- Settings as singleton—avoid re-parsing .env per request; load once at startup, inject where needed

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

- [`graphs/`](graphs/CLAUDE.md) — LangGraph StateGraph workflows for story, avatar, and memory AI operations
- [`models/`](models/CLAUDE.md) — 
- [`routes/`](routes/CLAUDE.md) — FastAPI route handlers; delegates to graphs/services; returns JSON or SSE streams
- [`utils/`](utils/CLAUDE.md) — Provider-specific wrappers for OpenAI, Gemini, Groq APIs

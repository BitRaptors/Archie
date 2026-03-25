# routes/
> FastAPI route handlers for family/character/memory domains with SSE streaming and Supabase integration.

## Patterns

- Every router checks family ownership via get_required_family_id(current_supabase_user) before DB access
- Background tasks trigger async graph jobs (avatar_generator_app, memory_analyzer) after resource creation
- SSE queues pre-created before background work starts so stream endpoints don't race on connection
- Photo uploads validated for type/size, stored in Supabase with family_id prefix, tracked in array fields
- Date objects converted to ISO strings before Supabase insert (characters.py line 30-32)
- HTTPException re-raised early; generic exceptions logged with exc_info=True then wrapped

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`graphs/`](../graphs/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `characters.py` | Character CRUD + avatar generation + relationships | Convert date fields to ISO before insert. Use get_required_family_id(). Pre-create SSE queue. |
| `family.py` | Family create/join/list + member/character summaries | Delegates to family_service layer. Response models map DB shapes (display_name, not name). |
| `memories.py` | Memory CRUD + photo storage + analysis triggers | Upload photos to memory-photos bucket with family_id prefix. Trigger run_memory_analysis in background. |
| `prompts.py` | Prompt versioning + active slug lookup | Read-only admin endpoints. Filter by is_active=True. No auth check (system config). |

## Key Imports

- `from src.utils.auth import get_current_supabase_user`
- `from src.utils.supabase import get_supabase_client`
- `from src.utils.sse import get_or_create_queue, send_sse_event`

## Add new family-scoped CRUD endpoint

1. Depend on get_current_supabase_user, call get_required_family_id() to extract/validate family_id
2. Add router dependency=[Depends(get_current_supabase_user)] to ensure auth
3. Filter all DB queries by family_id equality; check ownership before returning
4. Convert date/datetime to ISO; validate uploaded files before storage; log errors with exc_info=True

## Usage Examples

### Family-scoped query pattern
```python
family_id = get_required_family_id(current_supabase_user)
response = supabase.table("characters").select("*")\
    .eq("family_id", str(family_id))\
    .maybe_single().execute()
if response.data is None:
    raise HTTPException(status_code=404, detail="Not found")
```

## Don't

- Don't trust current_supabase_user.family_id without null check — always call get_required_family_id() to validate and return UUID
- Don't insert date objects directly into Supabase — convert to ISO string first (see characters.py line 31)
- Don't mix sync/async in same endpoint — use async only for OpenAI/Groq calls, keep DB sync via Supabase client

## Testing

- Mock Supabase client; verify eq('family_id', str(family_id)) is called on every query
- For file upload: test content_type validation, size >5MB rejection, and photo_paths array persistence

## Debugging

- If SSE stream disconnects before background task sends events: check that get_or_create_queue(resource_id) was called BEFORE background_tasks.add_task()
- If Supabase insert fails silently: response.data is empty — always check 'if not response.data' and raise HTTPException(500) early

## Why It's Built This Way

- Family_id stored as string in DB but passed as UUID in models — routes convert with str() on insert, UUID() on response validation
- Prompt endpoints have no auth (Depends not used) — prompts are system config, not user-scoped; family routes all require auth

## What Goes Here

- **One file per domain resource; receives requests and delegates to graphs/services** — `{domain}.py`
- new_backend_route → `tuck-in-tales-backend/src/routes/{domain}.py + register in tuck-in-tales-backend/src/main.py`

## Dependencies

**Depends on:** `Authentication`, `Graph Layer`, `Service Layer`, `Supabase Client`
**Exposes to:** `web-frontend`, `mobile-frontend`

## Templates

### backend_route
**Path:** `tuck-in-tales-backend/src/routes/{domain}.py`
```
router = APIRouter(prefix='/{domain}s', tags=['{domain}s'])
@router.post('/')
async def create(user_data: UserData = Depends(verify_firebase_token), supabase: Client = Depends(get_supabase_client)):
```

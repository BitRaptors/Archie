# routes/
> FastAPI route handlers for characters, families, memories, stories with family-scoped access control and authentication.

## Patterns

- All routes depend on get_current_supabase_user; extract family_id via get_required_family_id helper at route start
- Date/datetime objects must be converted to ISO strings before Supabase insert/update (see characters.py line ~32)
- Family-scoped queries filter by family_id string in every table operation to enforce multi-tenancy
- Async routes (create_memory, search_memories, update_memory) mix sync Supabase calls with async OpenAI embedding calls
- HTTP 404 returned for not-found OR access-denied to avoid leaking family membership info
- Response models (Character, Memory, Story, Family*Response) handle field serialization; validate before returning

## Navigation

**Parent:** [`backend-src/`](../CLAUDE.md)
**Peers:** [`graphs/`](../graphs/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `characters.py` | Character CRUD with avatar generation, photo uploads, SSE streaming | Always convert birthdate to ISO string. Validate ownership via family_id + character_id equality before return/update. |
| `family.py` | Family lifecycle: create, join, list members, set main character, update settings | Use family_service layer for DB ops. Helper function handles family_id extraction from user. Return FamilyDetailResponse or FamilyBasicResponse. |
| `memories.py` | Memory CRUD with vector embedding search for semantic recall across family | await get_embedding() before insert. Filter by family_id. Query embedding RPC returns MemorySearchResult objects. |
| `stories.py` | Story generation workflow: SSE streaming, character context fetching, graph-based composition | Call run_story_generation with CharacterInfo list. Use BackgroundTasks for cleanup. Handle date.today() for age calculation. |

## Key Imports

- `from src.utils.auth import get_current_supabase_user`
- `from src.utils.supabase import get_supabase_client`
- `from src.models.user import User`

## Add new authenticated endpoint to fetch/filter resources by family

1. Depend on get_current_supabase_user; call get_required_family_id(current_user)
2. Filter Supabase query with .eq('family_id', str(family_id))
3. Wrap response data in Pydantic model; return single/list based on route
4. Catch HTTPException separately; log errors with family_id context

## Usage Examples

### Date serialization pattern before Supabase insert
```python
memory_data = memory_in.model_dump()
if memory_data.get('date'):
    memory_data['date'] = memory_data['date'].isoformat()
response = supabase.table('memories').insert(memory_data).execute()
```

## Don't

- Don't skip date serialization before Supabase — JSON serialization will fail; use isoformat() explicitly
- Don't return raw DB rows without Pydantic validation — validates field types, aliases, and catches missing/extra fields early
- Don't query characters/memories/stories without eq('family_id') filter — enables unauthorized cross-family access

## Testing

- Mock Supabase client; assert query filters include family_id and current_user.id restrictions
- Test date serialization: pass date object, verify isoformat string sent to DB; test None birthdate edge case

## Debugging

- Date mismatch: check if birthdate passed as date object vs string; Supabase expects ISO string in JSON
- 404 vs 403 indistinguishable: add logging before raising 404 to confirm id exists but family_id mismatch

## Why It's Built This Way

- Async routes for embedding-heavy ops (memories, stories) to avoid blocking; sync Supabase calls wrapped in async context
- Helper function get_required_family_id() duplicated across files — consider moving to shared utils to reduce DRY violations

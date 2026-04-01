# persistence/
> Database abstraction layer providing async CRUD repositories for domain entities with backend-agnostic adapter pattern (Postgres/Supabase).

## Patterns

- Every repository wraps DatabaseClient (injected), never instantiates DB — enables swappable backends
- Datetime fields always parse ISO strings with Z-replacement: `.replace('Z', '+00:00')` before fromisoformat()
- Entity↔dict conversion via private _to_entity() and _to_dict() methods — keeps serialization logic encapsulated
- 204 DatabaseError catch returns empty/None gracefully — 204 is Supabase's 'no rows' response code
- upsert pattern: check existence first, then update or insert atomically to avoid race conditions
- replace_all() deletes all rows via neq() filter trick, then bulk-inserts fresh list — idempotent config reload

## Navigation

**Parent:** [`infrastructure/`](../CLAUDE.md)
**Peers:** [`analysis/`](../analysis/CLAUDE.md) | [`events/`](../events/CLAUDE.md) | [`external/`](../external/CLAUDE.md) | [`mcp/`](../mcp/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md) | [`storage/`](../storage/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `db_factory.py` | Singleton DB instance factory with backend routing | Add backends here only. New adapters inherit DatabaseClient interface. |
| `postgres_adapter.py` | asyncpg pool wrapper implementing DatabaseClient | Implement table()/select()/insert() chains; keep pool lifecycle here. |
| `supabase_adapter.py` | Supabase async client wrapper implementing DatabaseClient | Mirror PostgresAdapter API surface; handle Supabase-specific response shapes. |
| `analysis_repository.py` | Core Analysis entity CRUD + repo-scoped queries | New methods follow get_by_*() naming; always handle maybe_single() 204 errors. |
| `analysis_settings_repository.py` | Config-like tables (ignored dirs, library caps); replace_all() patterns | Use for read-only cache tables; replace_all() is atomic reload operation. |

## Key Imports

- `from domain.interfaces.database import DatabaseClient, DatabaseError`
- `from domain.entities.* import [Entity] — all repos map to domain entities only`
- `from infrastructure.persistence.db_factory import create_db — never direct adapter imports in services`

## Add new entity repository (e.g., NewEntityRepository)

1. Inherit IRepository[Entity, KeyType] or domain interface; inject DatabaseClient
2. Implement get_by_id(), get_all(), add(), update(), delete() with TABLE constant
3. Add _to_entity(dict) and _to_dict(entity) converters; handle datetime ISO parsing
4. Wrap maybe_single() calls with 204 error catch; return None instead of raising

## Usage Examples

### Datetime parsing pattern (safe for both Postgres/Supabase)
```python
created_at=datetime.fromisoformat(
    data['created_at'].replace('Z', '+00:00')
) if data.get('created_at') else None
```

### 204 error handling (Supabase returns 204 for no rows)
```python
except DatabaseError as e:
    if e.code == '204' or '204' in str(e):
        return None
    raise
```

## Don't

- Don't return raw result.data — always map through _to_entity() to enforce domain types
- Don't assume DB response structure — catch 204 errors and handle missing fields with .get()
- Don't create per-request DB instances — always inject singleton DatabaseClient from db_factory

## Testing

- Mock DatabaseClient with table().select().eq().maybe_single().execute() chain returning AsyncMock results
- Verify datetime parsing: pass ISO strings with Z suffix, assert entity.created_at is timezone-aware

## Debugging

- If 204 errors leak: check catch block handles both e.code == '204' and '204' in str(e) (Supabase inconsistency)
- If datetime fails: verify raw DB field includes 'Z' suffix; fromisoformat() needs explicit timezone offset

## Why It's Built This Way

- Backend abstraction via DatabaseClient interface allows Postgres+Supabase coexistence without changing repository code
- Singleton db_factory.py caches pool/client — every endpoint shares one connection; prevents connection exhaustion

## What Goes Here

- **Concrete repo implementations behind domain interfaces** — `{entity}_repository.py`
- new_db_query → `backend/src/infrastructure/persistence/{entity}_repository.py`

## Dependencies

**Depends on:** `Domain Layer`
**Exposes to:** `Application Layer`, `DI Container`

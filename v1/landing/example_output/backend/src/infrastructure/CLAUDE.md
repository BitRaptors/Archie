# infrastructure/
> Backend infrastructure layer: adapter pattern for persistence, storage, events, external APIs, and analysis with singleton/lazy-load patterns preventing resource duplication.

## Patterns

- Lazy singleton for expensive resources: _model = None, load on first use, shared across all consumers (analysis embedding model)
- Module-level dict registry (_subscribers: dict[str, list]) replaces class-based singletons for runtime-mutable state (event bus)
- Context manager cleanup (with subscribe() ... finally:) prevents memory leaks on async disconnects
- Backend-agnostic adapter: repositories wrap injected DatabaseClient, never instantiate — enables Postgres/Supabase swap
- Dual implementation with identical public API: PromptLoader (sync/file) and DatabasePromptLoader (async/db) — caller chooses which to await
- Safe path normalization: Path.relative_to(self._base_path) prevents filesystem path leaks in return values

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`application/`](../application/CLAUDE.md) | [`config/`](../config/CLAUDE.md) | [`domain/`](../domain/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)
**Children:** [`analysis/`](analysis/CLAUDE.md) | [`events/`](events/CLAUDE.md) | [`external/`](external/CLAUDE.md) | [`mcp/`](mcp/CLAUDE.md) | [`persistence/`](persistence/CLAUDE.md) | [`prompts/`](prompts/CLAUDE.md) | [`storage/`](storage/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `__init__.py` | Public exports for all child modules | Re-export Analysis, EventBus, all client/repository/storage/prompt classes used by domain layer |

## Add new repository or client adapter for domain entity

1. Accept DatabaseClient or external_client in __init__, never instantiate internally
2. Map domain exceptions (AuthorizationError, ValidationError) from underlying provider exceptions
3. Return normalized safe objects: paths via relative_to(), IDs without stale UUIDs

## Usage Examples

### Lazy singleton embedding model pattern (analysis/)
```python
_model = None
def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer('model-name')
    return _model
```

## Don't

- Don't loop encode(chunk) one-at-a-time — batch all chunks: encode(list, batch_size=64) cuts API calls 64x
- Don't cache rendered markdown from blueprint — render on-the-fly, data source is blueprint.json only
- Don't hardcode datetime parsing — always .replace('Z', '+00:00') before fromisoformat() for ISO string safety

## Testing

- Inject mock DatabaseClient to test repositories without touching real DB
- Mock asyncio.Queue subscribers dict to test event routing without SSE overhead

## Why It's Built This Way

- Lazy-load singleton (not eager) for 400MB embedding model: trades startup latency for memory efficiency across server lifetime
- Module-level dict registry instead of class singleton: mutable runtime state (subscribe/unsubscribe) requires function scope, not class scope

## What Goes Here

- new_db_query → `backend/src/infrastructure/persistence/{entity}_repository.py`

## Dependencies

**Depends on:** `Domain Layer`
**Exposes to:** `Application Layer`, `DI Container`

## Subfolders

- [`analysis/`](analysis/CLAUDE.md) — Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus
- [`events/`](events/CLAUDE.md) — Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus
- [`external/`](external/CLAUDE.md) — Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus
- [`mcp/`](mcp/CLAUDE.md) — Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus
- [`persistence/`](persistence/CLAUDE.md) — Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus
- [`prompts/`](prompts/CLAUDE.md) — Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus
- [`storage/`](storage/CLAUDE.md) — Concrete DB adapters, GitHub clients, RAG/embedding engines, storage, MCP, event bus

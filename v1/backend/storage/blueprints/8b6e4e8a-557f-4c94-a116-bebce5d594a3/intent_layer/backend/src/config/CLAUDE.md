# config/
> Central configuration & dependency injection: environment variables → Settings singleton, backend-agnostic DB abstraction, async resource lifecycle management.

## Patterns

- Settings validates db_backend choice (postgres vs supabase) with conditional required fields—fail fast at boot
- Repositories injected as Factory (new instance per request), services as Singleton (shared app lifetime)
- Resource providers for async initialization (db, arq_pool) with explicit shutdown hooks for cleanup
- Field defaults allow omission; extra env vars ignored (case_sensitive=False)—supports .env.local iteration without breaking
- ARQ pool gracefully degrades to None if Redis unavailable—analysis runs in-process as fallback
- Settings fields prefixed with intent_layer_, synthesis_, default_ai_ group related config logically

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`application/`](../application/CLAUDE.md) | [`domain/`](../domain/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `settings.py` | Pydantic BaseSettings with env var mapping & validation | Add Field() with default; use model_validator for cross-field checks |
| `container.py` | Dependency-injector DeclarativeContainer wiring | Add new service as Singleton/Factory provider; inject dependencies via constructor |
| `constants.py` | Immutable string constants for status, types, paths | Add class grouping related constants; use in comparisons, never hardcode strings |
| `__init__.py` | Exports for other packages to import from config | Export Container, Settings, constants after adding to module |

## Key Imports

- `from config import Container, get_settings`
- `from config.constants import AnalysisStatus, ChunkType`

## Add new environment variable to config

1. Add Field(default=...) to Settings class in settings.py with descriptive type hint
2. If conditional, add validation logic to _validate_db_backend() model_validator
3. Update .env.local example (outside repo) and document in README

## Usage Examples

### Conditional validation in Settings
```python
@model_validator(mode="after")
def _validate_db_backend(self) -> "Settings":
    if self.db_backend == "postgres":
        if not _is_set(self.database_url):
            raise ValueError("DATABASE_URL required")
```

## Don't

- Don't bypass Settings validation—always use get_settings() singleton, never instantiate Settings directly
- Don't add postgres_url when db_backend=supabase or supabase fields when db_backend=postgres—validator catches but wastes env vars
- Don't make Repository providers Singleton—Factory ensures fresh instances per request, preventing stale state across concurrent calls

## Testing

- Unit: Settings() with mocked env vars—verify validators reject missing required fields for active backend
- Integration: Container().db(), Container().arq_pool() async bootstrap—verify resources initialize and shutdown cleanly

## Debugging

- Settings validation fails silently if extra='ignore' masks typos—check .env.local case matches Field names exactly (case_sensitive=False applies only to env var names, not Field names)
- ARQ pool None return hides Redis outages—log at warning level and verify graceful in-process fallback invoked by checking analysis_service behavior

## Why It's Built This Way

- db_backend string toggle (not enum)—allows swapping backends without code changes; validator enforces correctness at runtime
- Resource lifecycle in container (not main.py)—centralizes async setup/teardown, enables testing with mock db/pool

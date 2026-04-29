# backend/
> FastAPI backend for repository analysis: bootstraps app, orchestrates pipeline phases, runs on PostgreSQL or Supabase.

## Patterns

- Settings singleton injected via get_settings() — read once at module load, reused throughout app lifecycle
- Environment-driven config: DB_BACKEND toggles between postgres and supabase without code changes
- create_app() factory in api/ returns configured FastAPI instance — called at module import, stored as `app`
- Temp storage isolated from main pipeline: scripts/ load cached phase JSONs, rerun synthesis alone, skip DB writes
- Idempotent SQL generation: seed_prompts.py reads single-source-of-truth prompts.json, generates upsert statements
- Fixture-based test DI: tmp_path → structured codebase → rules passed to all test suites consistently

## Navigation

**Parent:** [`root/`](../CLAUDE.md)
**Peers:** [`frontend/`](../frontend/CLAUDE.md) | [`landing/`](../landing/CLAUDE.md)
**Children:** [`scripts/`](scripts/CLAUDE.md) | [`src/`](src/CLAUDE.md) | [`tests/`](tests/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `.env.example` | Single source of truth for all runtime configuration | Copy to .env.local; sync new keys here first, tests read from .env.local |
| `requirements.txt` | Pins exact dependency versions for reproducibility | Add deps here, regenerate lock files, rebuild Docker image |
| `Dockerfile` | Production container image: Python 3.11, copies src/ and migrations/ | Update FROM image only if Python version changes; sync COPY commands with repo structure |

## Key Imports

- `from api.config import get_settings`
- `from src.main import app`

## Add new environment variable for feature flag or external service

1. Add key=value to .env.example with comment explaining purpose
2. Add field to Settings class in api/config.py with Field(default=...) and validation
3. Inject via get_settings() in route or service where needed

## Usage Examples

### Settings singleton pattern used throughout app
```python
from api.config import get_settings
settings = get_settings()
host, port = settings.HOST, settings.PORT
db_url = settings.DATABASE_URL
```

## Don't

- Don't hardcode paths — use STORAGE_PATH and TEMP_STORAGE_PATH from env config
- Don't couple test fixtures to specific repo structures — use sample_repo_builder for portability
- Don't write analysis state to DB during Phase 2 — save to temp storage, only commit on completion

## Testing

- Run pytest with fixture injection: tmp_path provides temp storage, mock_repo_builder creates parallel structures
- TEST_RESULTS.md documents actual pipeline success: 154 items found in BitRaptors/mobilfox-backend proves analyzer works

## Debugging

- Check logs for path resolution: 'Repository path (absolute): ...' in analysis_service and tasks.py show where clone succeeded
- Verify structure_data persistence: 'Phase 2: structure_data has X items' log line confirms data survived phase transition

## Why It's Built This Way

- Settings singleton over dependency injection — env vars are read once at startup, not per-request, reducing I/O
- Temp storage isolation — scripts/ sandbox testing and rerun logic away from main pipeline to prevent side effects

## What Goes Here

- new_api_endpoint → `backend/src/api/routes/{domain}.py — add route, register in app.py`
- new_business_logic → `backend/src/application/services/{feature}_service.py`
- new_domain_entity → `backend/src/domain/entities/{entity}.py`
- new_db_query → `backend/src/infrastructure/persistence/{entity}_repository.py`

## Dependencies

**Depends on:** `Domain Layer`, `Infrastructure Layer`
**Exposes to:** `API Layer`, `Workers`

## Templates

### backend_route
**Path:** `backend/src/api/routes/{domain}.py`
```
from fastapi import APIRouter, Depends
router = APIRouter(prefix='/{domain}', tags=['{domain}'])
@router.get('/')
async def list_items(service=Depends(get_service)): ...
```

### domain_entity
**Path:** `backend/src/domain/entities/{entity}.py`
```
from dataclasses import dataclass
from datetime import datetime
@dataclass
class {Entity}:
    id: str
    created_at: datetime
```

## Subfolders

- [`scripts/`](scripts/CLAUDE.md) — 
- [`src/`](src/CLAUDE.md) — Orchestrates use cases; coordinates domain + infra; runs analysis workflows
- [`tests/`](tests/CLAUDE.md) — 

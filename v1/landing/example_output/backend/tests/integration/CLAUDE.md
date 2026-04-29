# integration/
> Integration test suite validating end-to-end analysis pipeline: repo cloning, structure analysis, multi-phase AI processing, database persistence, event logging.

## Patterns

- Fixture-based DI: container.init_resources() + await container.db() in every test to resolve async dependencies
- Service composition: repo_service → analysis_service → phased_blueprint_generator chains via constructor injection
- Event-driven progress: analysis_service logs AnalysisEvent records via event_repo for real-time SSE updates
- Multi-backend DB support: tests parameterized to skip if DB_BACKEND != expected (Postgres vs Supabase detection)
- Token management: GITHUB_TOKEN envvar mandatory; tests pytest.skip() rather than fail when missing
- Path injection: sys.path.insert(0, src_path) in every test file to resolve application modules

## Navigation

**Parent:** [`tests/`](../CLAUDE.md)
**Peers:** [`unit/`](../unit/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `test_postgres_e2e.py` | Validates full pipeline: Postgres CRUD, analysis phases 0-6, intent layer, real Claude calls | Ensure services initialized with db_client for RAG; add phase validations post-generation |
| `test_full_analysis_e2e.py` | Tests complete workflow: user creation, repo fetch, cloning, 7-phase analysis | Update phase names if pipeline refactored; verify temp_dir cleanup in finally block |
| `test_real_analysis.py` | Single-repo integration test against BitRaptors/raptamagochi with ARQ job enqueueing | Replace mock_generator with real instance if testing intent layer; validate job_id returned |
| `validate_pipeline.py` | Standalone runner (no pytest): boots container, validates services wire, logs execution time | Add db assertions post-step; extend with blueprint validation or diff checks |

## Key Imports

- `from config.container import Container`
- `from infrastructure.persistence.analysis_repository import AnalysisRepository`
- `from application.services.analysis_service import AnalysisService`

## Add validation for new analysis phase or database entity

1. Create fixture helper (e.g., ensure_user, ensure_repo) that handles create-or-fetch idempotently
2. Add assertions on entity attributes post-persist (assert repo.full_name == f'{owner}/{repo_name}')
3. Log event_repo entries or progress_percentage updates to validate event bus wiring

## Usage Examples

### Standard container + services fixture pattern
```python
@pytest.fixture
async def services(container, github_token):
  db = await container.db()
  repo_repo = RepositoryRepository(db=db)
  analysis_service = AnalysisService(...)
  return {"repo_repo": repo_repo, "analysis_service": analysis_service}
```

## Don't

- Don't create container inside test; reuse @pytest.fixture async def container() to ensure cleanup via yield
- Don't call await container.db() before container.init_resources(); async resources uninitialized without it
- Don't hardcode test user_id; use uuid.uuid5(uuid.NAMESPACE_DNS, 'test-key') for deterministic, idempotent IDs

## Testing

- Run postgres tests: .env.local must have DB_BACKEND=postgres, DATABASE_URL, GITHUB_TOKEN, ANTHROPIC_API_KEY; skip pytest if missing
- Run e2e tests: pytest -v tests/integration/test_*.py; validate container shutdown_resources() via cleanup teardown

## Debugging

- If 'resource uninitialized' error: await container.init_resources() before resolving any Resource (db, arq_pool, supabase_client)
- If repo_path.exists() fails after clone: check git credentials in github_token and temp_dir permissions before assertion

## Why It's Built This Way

- Fixtures yield rather than return to guarantee async cleanup; container.shutdown_resources() called even if test fails
- Tests skip (not fail) on missing env tokens to allow CI/local runs without credentials; requires manual .env.local setup

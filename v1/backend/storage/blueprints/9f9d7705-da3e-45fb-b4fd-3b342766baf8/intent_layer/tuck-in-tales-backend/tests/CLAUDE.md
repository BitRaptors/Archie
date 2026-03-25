# tests/
> Test infrastructure fixture setup: AsyncClient + mocked Supabase dependencies for FastAPI route testing.

## Patterns

- Mock Supabase client via dependency_overrides before AsyncClient creation, not after.
- Chain mocked methods (table→select→eq→maybe_single→execute) to match actual Supabase SDK call patterns.
- Return MagicMock(data=...) from execute() — Supabase SDK wraps results in .data attribute.
- Override get_family_id_for_user as async function returning UUID, not a MagicMock.
- Clean up app.dependency_overrides = {} in fixture teardown to prevent test pollution.
- Use scope='function' for test_client, scope='session' for anyio_backend to avoid shared state.

## Navigation

**Parent:** [`tuck-in-tales-backend/`](../CLAUDE.md)
**Peers:** [`src/`](../src/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `conftest.py` | FastAPI test fixture + dependency mocking setup | Add new mocks by chaining methods on mock_supabase; override new dependencies before AsyncClient instantiation |
| `__init__.py` | Package marker (empty) | Leave empty unless exporting fixtures for cross-test-module reuse |

## Key Imports

- `from src.main import app`
- `from src.utils.supabase import get_supabase_client`
- `from src.utils.auth import get_family_id_for_user`

## Add a new mocked Supabase query chain for a route

1. Trace the actual route's supabase calls (e.g., table().select().eq().execute()).
2. Chain mocks on mock_supabase matching that call path with AsyncMock if async.
3. Return MagicMock(data=expected_result) from execute() terminal call.
4. Test using test_client fixture; it auto-injects the mocked dependency.

## Usage Examples

### Mocking a Supabase query chain with correct structure
```python
mock_supabase.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
    return_value=MagicMock(data={"id": "123", "name": "Test"})
)
```

## Don't

- Don't call AsyncMock() on storage methods (upload, remove) — they're sync in Supabase SDK.
- Don't create AsyncClient outside async context or forget to clean overrides — causes test pollution and port conflicts.
- Don't mock return_value as scalar — always wrap in MagicMock(data=...) to match SDK response structure.

## Testing

- Always await test_client methods: await test_client.get('/endpoint'); use pytest.mark.anyio on async tests.
- Verify dependency override worked by checking mock was called: mock_supabase.table.assert_called_with('table_name').

## Debugging

- If mocked supabase returns wrong shape, check .execute() returns MagicMock(data=...), not bare data.
- If test hangs, ensure test_client fixture is async and used with 'await'; verify anyio_backend fixture is present.

## Why It's Built This Way

- Dependency overrides set before AsyncClient creation ensures all route handlers receive mocks, not real clients.
- TEST_FAMILY_ID as session constant avoids UUID randomness in assertions; TEST_USER_ID as string matches Firebase UID type.

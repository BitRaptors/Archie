# api/
> Unit tests for FastAPI route handlers using TestClient + mocked services; validates request/response contracts.

## Patterns

- All tests use `app.container` mocking pattern — inject mock repos/services via `MagicMock()` before `TestClient(app)`
- Each route test file imports its router directly: `from api.routes.X import router` then `app.include_router(router, prefix="/api/v1")`
- Fixtures patch module-level factory functions (`_get_ignored_dirs_repo`, `_get_lib_caps_repo`) to inject test doubles
- Tests assert both status codes (200/404/422) AND response JSON shape — validates FastAPI validation layer works
- Mock services return domain entities (e.g., `DeliveryResult`, `SmartRefreshResult`, `IgnoredDirectory`) not dicts
- TestClient used synchronously even though routes are async — TestClient handles the event loop internally

## Navigation

**Parent:** [`unit/`](../CLAUDE.md)
**Peers:** [`domain/`](../domain/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md) | [`services/`](../services/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `test_delivery_routes.py` | Preview & apply delivery; validates PR/commit strategy responses. | Mock `delivery_service.preview` and `.apply` return domain result objects. |
| `test_settings_routes.py` | Enum endpoints + CRUD for ignored dirs & library capabilities. | Patch repo factories; test `get_all`/`replace_all` with domain entities. |
| `test_smart_refresh_route.py` | Smart-refresh service; validates status + warnings + updated files. | Mock `smart_refresh_service.refresh` returns `SmartRefreshResult`. |
| `test_workspace_routes.py` | Repository listing, active repo CRUD, agent file access. | Patch `_load_structured_blueprint`, `_get_repos`, `_get_profile_repo` factories. |

## Key Imports

- `from unittest.mock import AsyncMock, MagicMock, patch`
- `from fastapi.testclient import TestClient`
- `from domain.entities.* import [Entity classes returned by mocked services]`

## Add test for new route endpoint

1. Create fixture: mock the service method as `AsyncMock()` returning domain result
2. Add `@patch` on external calls like `resolve_github_token` if route uses them
3. Assert both `status_code` and response JSON keys/values match expected contract
4. For validation: test with empty/missing required fields → expect 422

## Usage Examples

### Standard fixture pattern: mock service + inject via container
```python
@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    mock_container = MagicMock()
    mock_container.delivery_service.return_value = AsyncMock()
    app.container = mock_container
    return app
```

## Don't

- Don't mock `app.container.db` directly unless route touches database — mocks are injected per dependency.
- Don't return dicts from mocks — return domain entities so serialization logic is tested.
- Don't test internal service logic in route tests — assert contract (status + JSON shape) only.

## Testing

- Run with `pytest backend/tests/unit/api/` — TestClient handles async event loop
- Test both happy path (200 + valid JSON) and error cases (404 validation, 422 missing fields, 500 service errors)

## Debugging

- If mock not called: check that route actually invokes the dependency — add `mock_service.method.assert_called_once_with(...)`
- If status is 500 instead of expected: check route exception handlers — FastAPI returns 500 for unhandled exceptions, use `@patch` to mock failures

## Why It's Built This Way

- Use `AsyncMock` for async service methods even in sync test — matches actual async route signatures
- Patch at module level (`api.routes.settings.factory_func`) not at import point — simpler setup, avoids timing issues

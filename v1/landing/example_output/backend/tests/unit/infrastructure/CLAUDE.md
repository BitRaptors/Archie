# infrastructure/
> Unit tests for database adapters, repositories, and external clients—validate abstraction layer translation and mock Supabase/Postgres fluent chains.

## Patterns

- Mock fluent query builders by chaining MagicMock methods that return self; set execute() return value at the end
- Repository _make_mock_db() pattern: build db → chain mock → set data on execute() → return both for assertion
- SupabaseAdapter wraps raw client.table() calls; SupabaseQueryBuilder delegates all methods (select, eq, insert, delete, order, limit, maybe_single, upsert, range) to underlying PostgREST builder
- LibraryCapabilitiesRepository normalizes Postgres TEXT[] formats ('{a,b,c}' string, list, empty '{}') to Python list in _parse_capabilities()
- DatabaseError carries optional code + message; QueryResult wraps response.data (can be None, list, or dict)
- db_factory caches singleton instances (_cached_db, _cached_pool) across calls; reset_cache fixture resets module state between tests

## Navigation

**Parent:** [`unit/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`domain/`](../domain/CLAUDE.md) | [`services/`](../services/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `test_analysis_settings_repository.py` | IgnoredDirsRepository and LibraryCapabilitiesRepository | Mock db.table().select().order().execute() chain. Test _parse_capabilities() Postgres array normalization. |
| `test_database_abstraction.py` | QueryResult, DatabaseError, SupabaseAdapter, SupabaseQueryBuilder | Mock PostgREST builder; verify chainable methods return QueryBuilder. Test None data on maybe_single(). |
| `test_db_factory.py` | Backend switching (Postgres/Supabase), caching, validation | Use reset_cache fixture. Patch get_settings, asyncpg, supabase.create_async_client. Verify singleton caching. |
| `test_github_push_client.py` | GitHubPushClient: branch creation, file commits, PR creation | Mock PyGithub Repository. Test GithubException translation to ValidationError/AuthorizationError. |

## Key Imports

- `from domain.interfaces.database import DatabaseClient, DatabaseError, QueryBuilder, QueryResult`
- `from infrastructure.persistence.supabase_adapter import SupabaseAdapter, SupabaseQueryBuilder`
- `from infrastructure.persistence.analysis_settings_repository import IgnoredDirsRepository, LibraryCapabilitiesRepository`

## Add test for new repository method

1. Create mock_db using _make_mock_db([{...row data...}])
2. Instantiate repository with db=mock_db
3. Call async method; assert result type and fields
4. Verify chain method calls (select, order, insert, execute)

## Usage Examples

### Mock fluent Supabase chain for testing
```python
mock_query = MagicMock()
for m in ('select', 'insert', 'eq', 'order', 'execute'):
  getattr(mock_query, m).return_value = mock_query
mock_query.execute = AsyncMock(return_value=MagicMock(data=[...]))
mock_db.table.return_value = mock_query
```

## Don't

- Don't instantiate ABC interfaces (QueryBuilder, DatabaseClient) directly—pytest.raises(TypeError) validates this
- Don't leave Postgres TEXT[] as string '{a,b,c}'—parse to list using _parse_capabilities() split logic
- Don't forget reset_cache fixture autouse in db_factory tests—state persists across test runs otherwise

## Testing

- Use @pytest.mark.asyncio for async methods; AsyncMock for async functions, MagicMock for sync
- For Supabase/PostgREST fluent chains: make each method return the chain mock itself (mock_query.select.return_value = mock_query)

## Debugging

- If Postgres adapter fails: check database_url format, asyncpg.create_pool mock setup, connection context manager __aenter__/__aexit__
- If query chains don't work: verify all intermediate methods return the chain object; mock_query.method.return_value = mock_query

## Why It's Built This Way

- Singleton pattern (_cached_db module variable) avoids recreating Supabase/Postgres clients per request—critical for connection pooling
- Postgres TEXT[] normalized to Python list at adapter level, not domain—keeps persistence layer format translation isolated

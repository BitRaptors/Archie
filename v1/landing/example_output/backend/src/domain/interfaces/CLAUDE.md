# interfaces/
> DB-agnostic interface layer isolating repositories from concrete persistence implementations via chainable query builders.

## Patterns

- QueryBuilder chains all DB operations (select, insert, update, delete, filters, execute) — never instantiate directly, always via DatabaseClient.table()
- DatabaseError abstracts PostgREST error codes so repositories catch without DB SDK imports
- IRepository<T, ID> generic base with CRUD; domain-specific repos extend it for custom queries (get_by_full_name, get_by_analysis_id)
- IUserProfileRepository breaks the pattern — single-row design, no ID param, upsert instead of separate add/update
- QueryResult wraps Any data — repositories unpack it; never assume list vs dict vs None without checking
- Concrete DB adapters implement both QueryBuilder AND DatabaseClient; live in infrastructure/persistence/

## Navigation

**Parent:** [`domain/`](../CLAUDE.md)
**Peers:** [`entities/`](../entities/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `database.py` | QueryBuilder + DatabaseClient abstractions + error bridge | Add filter methods here only if used across 2+ repos; else move to concrete adapter |
| `repositories.py` | Domain-specific repository interfaces (User, Analysis, etc.) | Extend IRepository for new entities; add custom queries as abstract methods |

## Key Imports

- `from domain.interfaces.database import DatabaseClient, QueryBuilder, DatabaseError`
- `from domain.interfaces.repositories import IRepository, IUserRepository (for type hints in service/handler layers)`

## Add custom query method to existing repository

1. Add @abstractmethod to IRepository subclass (e.g., IRepositoryRepository.get_by_user_id)
2. Implement in concrete repo: inject DatabaseClient, call .table(name).filter_chain().execute()
3. Handle QueryResult.data unpacking — check type before slice/iterate

## Usage Examples

### Extend IRepository for domain-specific queries
```python
class IAnalysisEventRepository(IRepository[AnalysisEvent, str]):
    @abstractmethod
    async def get_by_analysis_id(self, analysis_id: str) -> list[AnalysisEvent]:
        ...
```

## Don't

- Don't pass raw DB client to repositories — inject DatabaseClient interface instead
- Don't assume QueryResult.data type — check None and unpack dict vs list per query intent
- Don't add repository-specific methods to QueryBuilder — keep it generic, override in concrete adapters if needed

## Testing

- Mock DatabaseClient.table() to return stub QueryBuilder; assert execute() returns QueryResult with expected data shape
- Test QueryResult unpacking: None, empty list, single dict, list of dicts — repository must handle all

## Debugging

- QueryBuilder chains silently — if execute() fails, trace back: which filter broke? Use concrete adapter logs to see SQL/PostgREST
- DatabaseError.code empty string? Concrete adapter not translating DB errors; check infrastructure/persistence/ implementation

## Why It's Built This Way

- QueryBuilder mirrors PostgREST API subset, not generic SQLAlchemy — easier to support Supabase-specific features (upsert on_conflict, rpc)
- IUserProfileRepository separate from IRepository pattern — single-row design signals future migration to multi-user; upsert + set_active_repo are stateful operations

## Dependencies

**Exposes to:** `Application Layer`, `Infrastructure Layer`, `API Layer`

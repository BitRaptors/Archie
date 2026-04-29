# domain/
> Domain layer: DB-agnostic entities and repository interfaces defining the boundary between business logic and persistence.

## Patterns

- All entities are @dataclass immutables with factory classmethod create() returning Self
- Timestamps always use datetime.now(timezone.utc)—never naive or local time
- QueryBuilder chains all DB operations (select, insert, update, delete, filters, execute)
- DatabaseClient.table() is the single entry point—never instantiate QueryBuilder directly
- DatabaseError abstracts PostgREST codes so repositories catch without SDK imports
- Repository interfaces define chainable queries, never concrete SQL or ORM details

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`application/`](../application/CLAUDE.md) | [`config/`](../config/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)
**Children:** [`entities/`](entities/CLAUDE.md) | [`interfaces/`](interfaces/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `__init__.py` | Export public entities and interfaces only | Add to __all__ when creating new entity or interface files |

## Key Imports

- `from domain.entities import AnalysisWorkflow, ArchitectureRule`
- `from domain.interfaces import RepositoryInterface, QueryBuilder`

## Add new domain entity for a workflow artifact

1. Create @dataclass in entities/ with immutable fields and UTC timestamp
2. Add create(cls, ...) → Self factory with datetime.now(timezone.utc)
3. Export in __init__.py, add to interfaces/ query builder if persistence needed

## Usage Examples

### Entity with UTC timestamp and factory
```python
@dataclass(frozen=True)
class AnalysisWorkflow:
    id: str
    created_at: datetime
    @classmethod
    def create(cls, id: str) -> Self:
        return cls(id=id, created_at=datetime.now(timezone.utc))
```

## Don't

- Don't use naive datetime or timezone.Local—always timezone.utc for consistency
- Don't instantiate QueryBuilder directly—always chain from DatabaseClient.table()
- Don't catch PostgREST codes in repositories—let DatabaseError abstract them

## Testing

- Verify entity immutability by confirming frozen=True on dataclass
- Mock DatabaseClient.table() to test repository interface chains without DB

## Debugging

- If timestamp comparison fails, check timezone—domain always uses UTC, never local
- If QueryBuilder chain breaks, trace from DatabaseClient.table()—the only valid entry point

## Why It's Built This Way

- Immutable dataclass entities prevent accidental state mutation in business logic flows
- Interface-based QueryBuilder isolates domain from PostgREST SDK, enabling test mocks and future DB swaps

## What Goes Here

- new_domain_entity → `backend/src/domain/entities/{entity}.py`

## Dependencies

**Exposes to:** `Application Layer`, `Infrastructure Layer`, `API Layer`

## Templates

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

- [`entities/`](entities/CLAUDE.md) — Core entities, abstract interfaces, domain exceptions; no framework dependencies
- [`interfaces/`](interfaces/CLAUDE.md) — Core entities, abstract interfaces, domain exceptions; no framework dependencies

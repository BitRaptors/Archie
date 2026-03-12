# middleware/
> Central exception handler mapping domain layer errors to HTTP status codes via FastAPI middleware.

## Patterns

- Exception-to-status lookup via isinstance() checks against EXCEPTION_STATUS_MAP dict (polymorphic dispatch)
- DomainException base class with code/message/details attributes expected by all subclasses
- JSONResponse wrapper with consistent error shape: {error: {code, message, details}}
- Handler catches DomainException; unmapped exceptions fall through to HTTP 500 default
- Status code discovery iterates map on each request (stateless, no caching optimization)

## Navigation

**Parent:** [`api/`](../CLAUDE.md)
**Peers:** [`dto/`](../dto/CLAUDE.md) | [`routes/`](../routes/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `error_handler.py` | Register with FastAPI.add_exception_handler() | Add exception type → status mapping; validate DomainException subclass imports |
| `__init__.py` | Export handler for registration in main app | Export domain_exception_handler only if used as module reference |

## Key Imports

- `from middleware import domain_exception_handler (in main FastAPI app setup)`

## Add new domain error type with correct HTTP status

1. Create exception class inheriting DomainException in domain/exceptions/domain_exceptions.py
2. Import new class at top of error_handler.py
3. Add entry to EXCEPTION_STATUS_MAP dict with appropriate status code
4. Handler auto-routes via isinstance() iteration

## Usage Examples

### Adding new exception type workflow
```python
# 1. In EXCEPTION_STATUS_MAP
RateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,

# 2. Import at top
from domain.exceptions.domain_exceptions import RateLimitError

# 3. Handler auto-routes on next raise RateLimitError()
```

## Don't

- Don't catch generic Exception — constrains to DomainException only; unmapped errors surface as 500
- Don't hardcode status codes in handlers — centralize in EXCEPTION_STATUS_MAP for maintainability
- Don't expose internal exception chain/traceback in JSONResponse content — details field is user-safe only

## Testing

- Raise each exception type; assert response status matches EXCEPTION_STATUS_MAP
- Raise unmapped DomainException subclass; assert 500 returned with proper error shape

## Why It's Built This Way

- Iterate EXCEPTION_STATUS_MAP per request vs. pre-compute reverse map: favors readability/maintainability over microsecond perf
- Return 500 for unmapped DomainException: defensive fallback prevents silent error swallowing

## Dependencies

**Depends on:** `Application Layer`, `Domain Layer`
**Exposes to:** `frontend`, `external clients`

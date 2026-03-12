# services/
> API client layer for backend service calls. Every function is a thin axios wrapper with consistent URL construction.

## Patterns

- All files use same API_URL pattern: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
- Service objects exported as singleton with methods (authService, deliveryService, etc.)
- Token handling: repositories.ts checks SERVER_TOKEN to skip Authorization header; delivery.ts conditionally adds Bearer token
- Request/response types paired with each service (DeliveryRequest/DeliveryResult, Prompt, PromptRevision, etc.)
- POST endpoints for state changes use axios.post; GET for read; PUT for updates; DELETE for logout
- All axios calls unwrap response.data — never return raw axios response

## Navigation

**Parent:** [`frontend/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`hooks/`](../hooks/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `auth.ts` | GitHub auth config check and token lifecycle. | Add header logic here for auth context changes only. |
| `repositories.ts` | Repo list, fetch, analyze, commit metadata. | Token dispatch logic lives here via authHeaders(). Don't add auth elsewhere. |
| `delivery.ts` | Preview and push outputs to GitHub (PR/commit/local). | Bearer token passed explicitly in apply(); mirror in new delivery methods. |
| `prompts.ts` | CRUD and revision history for LLM prompt templates. | Revert is POST; standard CRUD is GET/PUT. No custom headers needed. |
| `settings.ts` | Ignored dirs, library capabilities, ecosystem options, reset. | Grouped logically: directories, libraries, then data reset. No auth headers. |

## Add new endpoint to existing service

1. Define request/response interface at file top if needed
2. Add async method to service object following GET/POST/PUT/DELETE convention
3. Use API_URL constant and authHeaders() pattern if token required
4. Return response.data unwrapped

## Don't

- Don't add Authorization headers directly in service methods — centralize in authHeaders() or delivery's conditional token check
- Don't return axios response object — always unwrap response.data so callers get typed data only
- Don't hardcode API_URL in individual methods — define once at file top, reuse everywhere

## Testing

- Mock axios in tests; verify POST body structure matches backend schema (e.g., DeliveryRequest fields)
- For token paths: test authHeaders(SERVER_TOKEN) returns {}, authHeaders(token) returns Bearer header

## Debugging

- Check API_URL env var first — localhost:8000 default may mask production issues
- Axios error? Inspect response.data shape — backend returns data at root level, not nested

## Why It's Built This Way

- SERVER_TOKEN sentinel value skips Authorization to let backend use server-side token — reduces frontend token exposure
- All services as singleton objects, not classes — simpler import/use pattern, no instantiation ceremony

## What Goes Here

- new_http_service → `frontend/services/{domain}.ts`

## Dependencies

**Depends on:** `Backend API`
**Exposes to:** `end users`

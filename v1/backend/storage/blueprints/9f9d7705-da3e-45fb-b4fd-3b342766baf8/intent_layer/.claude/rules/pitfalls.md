## Pitfalls

- **SSE connection lifecycle:** If a LangGraph graph node raises an exception without calling send_sse_event(client_id, 'error', ...) first, the frontend EventSource in useSSEStream.ts will hang indefinitely waiting for a terminal event
  - *Wrap all graph nodes in try/except; always emit 'error' or 'done' event before re-raising. Check tuck-in-tales-backend/src/utils/sse.py terminal event handling.*
- **Firebase token + Supabase user sync:** verify_firebase_token in tuck-in-tales-backend/src/utils/auth.py calls get_or_create_supabase_user on every request; if Supabase is slow this adds latency to all authenticated calls
  - *Consider caching user lookups in-memory with TTL; or use Supabase's JWT verification directly to skip the extra DB call on subsequent requests*
- **_restore directory:** tuck-in-tales-frontend/_restore/backend-src/ contains legacy backend code that mirrors tuck-in-tales-backend/src/; changes to active backend are NOT reflected in _restore and vice versa
  - *Never import from _restore/; treat it as read-only historical reference. See tuck-in-tales-frontend/RESTORE-GUIDE.md for context.*
- **AI provider selection:** Provider routing in story_generator.py uses if/elif on provider string from prompt config; adding a new provider requires editing graph files directly
  - *When adding a new LLM provider, update tuck-in-tales-backend/src/utils/ with a new client module AND update all if/elif chains in tuck-in-tales-backend/src/graphs/*
- **Mobile vs web data fetching divergence:** Mobile uses TanStack Query hooks (hooks/queries/) with caching; web uses direct axios calls with manual useState — same API, different caching semantics
  - *When adding a new API call, create TanStack Query hook for mobile in tuck-in-tales-mobile/src/hooks/queries/; for web consider adding useQuery wrapper for consistency*

## Error Mapping

| Error | Status Code |
|-------|------------|
| `Invalid Firebase token` | 401 |
| `Missing AI provider API key` | 500 |
| `Supabase query error` | 500 |
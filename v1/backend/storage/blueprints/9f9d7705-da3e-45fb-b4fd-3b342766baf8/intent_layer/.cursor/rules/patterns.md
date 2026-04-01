---
description: Communication and design patterns, key architectural decisions
alwaysApply: true
---

## Communication Patterns

### FastAPI Dependency Injection
- **When:** All protected backend routes requiring auth or DB client
- **How:** Depends() resolves verify_firebase_token() and get_supabase_client() per request

### SSE Streaming
- **When:** Long-running AI generation (story, avatar, memory analysis)
- **How:** Graph nodes call send_sse_event(client_id, event, data); FastAPI returns StreamingResponse from sse_generator(client_id)

### REST + Axios
- **When:** All CRUD operations from web and mobile
- **How:** Axios instance in api/client.ts injects Firebase Bearer token from AuthContext

### TanStack Query (mobile)
- **When:** Mobile data fetching with caching and background sync
- **How:** useQuery/useMutation hooks in hooks/queries/ wrap api/client.ts calls

### LangGraph Node Execution
- **When:** All AI orchestration workflows
- **How:** Compiled StateGraph.stream(state) runs async nodes sequentially; nodes emit SSE events and update TypedDict state

## Pattern Selection Guide

| Scenario | Pattern | Rationale |
|----------|---------|-----------|
| New protected backend endpoint | FastAPI Depends(verify_firebase_token) + Depends(get_supabase_client) | Consistent auth and DB access pattern used across all existing routes |
| Long-running AI generation with frontend progress | LangGraph graph + SSE via sse.py + useSSEStream.ts hook | Established pattern for story/avatar/memory generation |
| Mobile data fetching | TanStack Query hook in hooks/queries/ | Caching, background sync, loading/error states handled automatically |

## Quick Pattern Lookup

- **streaming_generation** -> LangGraph graph + send_sse_event + SSE route + useSSEStream hook
- **auth_protected_route** -> Depends(verify_firebase_token) in route handler signature
- **mobile_data** -> TanStack Query hook wrapping api/client.ts call
- **web_data** -> Direct api/client.ts call in useEffect or custom hook
- **prompt_templating** -> resolve_prompt(key, variables, supabase) from tuck-in-tales-backend/src/utils/prompt_resolver.py

## Key Decisions

### Server-Sent Events for real-time streaming
**Chosen:** SSE via asyncio.Queue registry in utils/sse.py
**Rationale:** One-way server push is sufficient for generation progress; simpler than WebSockets

### Firebase Auth + Supabase for persistence
**Chosen:** Firebase ID tokens verified backend-side; Supabase PostgreSQL as data store
**Rationale:** Firebase handles OAuth/social login; Supabase provides RLS-protected PostgreSQL

### Multi-provider AI abstraction
**Chosen:** Separate client modules (openai_client, gemini_client, groq_client) selected via config
**Rationale:** Enables runtime provider switching and fallback without code changes

### Monorepo with concurrently
**Chosen:** Single repo with root package.json orchestrating all three platforms
**Rationale:** Shared domain model naming; coordinated dev startup via concurrently

### Expo Router file-based routing for mobile
**Chosen:** app/ directory with grouped layouts (auth), (tabs)
**Rationale:** Convention-over-configuration mirrors web file-based router patterns
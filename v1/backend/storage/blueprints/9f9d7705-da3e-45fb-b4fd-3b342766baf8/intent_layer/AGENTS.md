# AGENTS.md

> Agent guidance for **csacsi/BedtimeApp**
> Generated: 2026-03-23T10:08:44.244058+00:00

BedtimeApp (Tuck-in-Tales) is a monorepo generating personalized AI bedtime stories for children. The backend is FastAPI/Python using LangGraph to orchestrate multi-step AI workflows across OpenAI, Gemini, and Groq. The web frontend is a React/Vite SPA and the mobile app uses React Native/Expo with file-based routing. Authentication uses Firebase ID tokens verified by the backend, with Supabase as the primary PostgreSQL database. Real-time story and avatar generation progress is streamed to clients via Server-Sent Events.

---

## Tech Stack

- **ai_orchestration:** LangGraph latest
- **ai_provider:** OpenAI latest Python SDK, Google Generative AI latest, Groq latest Python SDK
- **auth:** Firebase latest
- **backend_framework:** FastAPI latest
- **build_tool:** Vite 5.x
- **database:** Supabase latest
- **dependency_mgmt:** Poetry latest
- **http_client:** Axios latest
- **mobile_framework:** React Native + Expo latest
- **routing_mobile:** Expo Router latest
- **routing_web:** React Router v6
- **state_server:** TanStack Query ^5.x
- **styling:** Tailwind CSS 3.x
- **ui_primitives:** Radix UI ^1.x
- **validation:** Pydantic 2.x
- **web_framework:** React 18.x

## Deployment

**Runs on:** Backend: Python/Uvicorn server (Poetry); Web: Browser SPA (Vite build); Mobile: iOS/Android native via Expo
**Compute:** Uvicorn ASGI server (backend), Vite dev/static build (web), Expo EAS or Expo Go (mobile)
**Container:** Not detected; no Dockerfile found + None detected; single Uvicorn process
**Distribution:**
- Web: Vite static build output for CDN/static hosting
- Mobile: Expo build (EAS) for App Store / Google Play

## Commands

```bash
# dev_all
npm run dev (root) — starts backend + web frontend concurrently
# dev_backend
cd tuck-in-tales-backend && poetry run uvicorn src.main:app --reload
# dev_web
cd tuck-in-tales-frontend && npm run dev
# dev_mobile
cd tuck-in-tales-mobile && npx expo start
# test_backend
cd tuck-in-tales-backend && poetry run pytest
# build_web
cd tuck-in-tales-frontend && npm run build (tsc -b && vite build)
```

## Project Structure

```
BedtimeApp/
├── package.json          # root monorepo scripts (concurrently)
├── package-lock.json
├── DOCS/                 # architecture docs, plans, schema
├── tuck-in-tales-backend/
│   ├── src/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routes/       # characters, stories, family, memories, prompts
│   │   ├── models/       # character, story, family, memory, user, prompt
│   │   ├── graphs/       # story_generator, avatar_generator, memory_analyzer
│   │   ├── services/     # family_service
│   │   └── utils/        # auth, sse, supabase, llm clients, prompt_resolver
│   └── tests/
├── tuck-in-tales-frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/        # all route-level page components
│   │   ├── components/   # ui/, Auth/, Layout/, prompts/
│   │   ├── hooks/        # useSSEStream, useStoryStream, etc.
│   │   ├── context/      # AuthContext
│   │   ├── models/       # TS interfaces mirroring backend
│   │   ├── api/          # client.ts
│   │   └── utils/        # firebase, supabaseUtils
│   └── _restore/         # legacy backend backup (do not modify)
└── tuck-in-tales-mobile/
    ├── App.tsx
    ├── app/              # Expo Router: (auth)/, (tabs)/, story/[id].tsx
    └── src/
        ├── api/          # client.ts
        ├── context/      # AuthContext
        ├── hooks/        # queries/, useGoogleSignIn
        ├── models/       # TS interfaces
        ├── config/       # firebase, supabase
        └── utils/        # supabaseUtils
```

## Code Style

- **backend:** snake_case for files, functions, variables (e.g. `family_service.py`, `get_supabase_client`, `verify_firebase_token`)
- **frontend_web:** PascalCase components, camelCase hooks/utils (e.g. `CharacterList.tsx`, `useStoryStream.ts`, `promptVariables.ts`)
- **mobile:** File-based routes use lowercase with brackets for dynamic segments (e.g. `app/(tabs)/characters.tsx`, `app/story/[id].tsx`, `app/(auth)/login.tsx`)
- **models:** Shared domain names across backend (Pydantic) and frontend (TypeScript interfaces) (e.g. `character.py / character.ts`, `story.py / story.ts`, `family.py / family.ts`)

### backend_route: FastAPI router with auth + DB injection

File: `tuck-in-tales-backend/src/routes/{domain}.py`

```
router = APIRouter(prefix='/{domain}s', tags=['{domain}s'])
@router.post('/')
async def create(user_data: UserData = Depends(verify_firebase_token), supabase: Client = Depends(get_supabase_client)):
```

### langgraph_node: Async LangGraph node emitting SSE events

File: `tuck-in-tales-backend/src/graphs/{domain}_generator.py`

```
async def generate_node(state: DomainState) -> DomainState:
    await send_sse_event(state['id'], 'status', {'msg': 'generating'})
    return {**state, 'result': result}
```

### web_page: React page component with auth-protected route

File: `tuck-in-tales-frontend/src/pages/{Domain}Page.tsx`

```
export default function {Domain}Page() {
  const { user } = useAuth();
  return <div>...</div>;
}
```

## Development Rules

### Code Style

- Always use FastAPI Depends(verify_firebase_token) and Depends(get_supabase_client) on every protected route handler — never access Firebase or Supabase directly in route function bodies without dependency injection *(source: `tuck-in-tales-backend/src/utils/auth.py, tuck-in-tales-backend/src/utils/supabase.py`)*
- Always emit a terminal SSE event ('done' or 'error') from every LangGraph graph node execution path — never leave an SSE queue open without a terminal signal *(source: `tuck-in-tales-backend/src/utils/sse.py, tuck-in-tales-backend/src/graphs/story_generator.py`)*
- Never import from or modify tuck-in-tales-frontend/_restore/ — it is a read-only legacy backup; all active backend code lives exclusively in tuck-in-tales-backend/src/ *(source: `tuck-in-tales-frontend/RESTORE-GUIDE.md`)*
- When adding a new LangGraph AI workflow, mirror domain model names exactly between tuck-in-tales-backend/src/models/{domain}.py (Pydantic) and tuck-in-tales-frontend/src/models/{domain}.ts (TypeScript interface) *(source: `tuck-in-tales-backend/src/models/character.py, tuck-in-tales-frontend/src/models/character.ts`)*

### Environment

- Never hardcode AI provider API keys or Firebase credentials — all secrets must be loaded via pydantic-settings BaseSettings in config.py from environment variables *(source: `tuck-in-tales-backend/src/config.py`)*

### Testing

- Backend tests use pytest with fixtures defined in conftest.py — always add new route tests to tuck-in-tales-backend/tests/routes/ following the pattern in test_characters.py *(source: `tuck-in-tales-backend/tests/conftest.py, tuck-in-tales-backend/tests/routes/test_characters.py`)*

## Boundaries

### Always

- Run tests before committing
- Use `where_to_put` MCP tool before creating files
- Use `check_naming` MCP tool before naming components
- Follow file placement rules (see `.claude/rules/architecture.md`)

### Ask First

- Database schema changes
- Adding new dependencies
- Modifying CI/CD configuration
- Changes to deployment configuration

### Never

- Commit secrets or API keys
- Edit vendor/node_modules directories
- Remove failing tests without authorization
- Never import from _restore/; treat it as read-only historical reference. See tuck-in-tales-frontend/RESTORE-GUIDE.md for context.

## Testing

```bash
# test_backend
cd tuck-in-tales-backend && poetry run pytest
```

## Common Workflows

### Add a new AI-powered feature with streaming progress
Files: `tuck-in-tales-backend/src/graphs/story_generator.py`, `tuck-in-tales-backend/src/utils/sse.py`, `tuck-in-tales-backend/src/routes/stories.py`, `tuck-in-tales-frontend/src/hooks/useSSEStream.ts`, `tuck-in-tales-frontend/src/hooks/useStoryStream.ts`
1. Create tuck-in-tales-backend/src/graphs/{domain}_generator.py with LangGraph StateGraph; nodes call send_sse_event(client_id, 'chunk'/'status'/'done', data)
2. Add SSE route in tuck-in-tales-backend/src/routes/{domain}.py: POST to start generation, GET /{id}/stream returns StreamingResponse(sse_generator(id))
3. Register router in tuck-in-tales-backend/src/main.py
4. Create tuck-in-tales-frontend/src/hooks/use{Domain}Stream.ts extending useSSEStream.ts with domain-specific event handlers
5. Use hook in tuck-in-tales-frontend/src/pages/{Domain}Page.tsx to display real-time progress

### Add a new backend CRUD resource
Files: `tuck-in-tales-backend/src/models/character.py`, `tuck-in-tales-backend/src/routes/characters.py`, `tuck-in-tales-backend/src/main.py`, `tuck-in-tales-frontend/src/models/character.ts`, `tuck-in-tales-frontend/src/api/client.ts`
1. Create Pydantic model in tuck-in-tales-backend/src/models/{domain}.py
2. Create route file in tuck-in-tales-backend/src/routes/{domain}.py with Depends(verify_firebase_token) and Depends(get_supabase_client) on each handler
3. Register router in tuck-in-tales-backend/src/main.py: app.include_router({domain}_router)
4. Mirror TypeScript interface in tuck-in-tales-frontend/src/models/{domain}.ts and tuck-in-tales-mobile/src/models/{domain}.ts
5. Add mobile query hook in tuck-in-tales-mobile/src/hooks/queries/use{Domain}s.ts

### Add a new web page with protected route
Files: `tuck-in-tales-frontend/src/pages/CharactersPage.tsx`, `tuck-in-tales-frontend/src/App.tsx`, `tuck-in-tales-frontend/src/components/Layout/Sidebar.tsx`
1. Create tuck-in-tales-frontend/src/pages/{Domain}Page.tsx as a React functional component
2. Add route in tuck-in-tales-frontend/src/App.tsx inside the AppLayout ProtectedRoute wrapper: <Route path='/{domain}' element={<{Domain}Page />} />
3. Add navigation link in tuck-in-tales-frontend/src/components/Layout/Sidebar.tsx

### Add a new mobile tab screen
Files: `tuck-in-tales-mobile/app/(tabs)/_layout.tsx`, `tuck-in-tales-mobile/app/(tabs)/characters.tsx`, `tuck-in-tales-mobile/src/hooks/queries/useCharacters.ts`
1. Create tuck-in-tales-mobile/app/(tabs)/{screen}.tsx as Expo Router screen component
2. Add tab entry in tuck-in-tales-mobile/app/(tabs)/_layout.tsx TabList
3. Create data hook in tuck-in-tales-mobile/src/hooks/queries/use{Domain}.ts using TanStack Query useQuery wrapping api/client.ts

## Pitfalls & Gotchas

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

## Architecture MCP Server

The `architecture-blueprints` MCP server is the single source of truth.
Call its tools for every architecture decision.

| Tool | When to Use |
|------|------------|
| `where_to_put` | Before creating or moving any file |
| `check_naming` | Before naming any new component |
| `list_implementations` | Discovering available implementation patterns |
| `how_to_implement_by_id` | Getting full details for a specific capability |
| `how_to_implement` | Fuzzy search when exact capability name unknown |
| `get_file_content` | Reading source files referenced in guidelines |

## File Placement

- **new_backend_route** → `tuck-in-tales-backend/src/routes/{domain}.py + register in tuck-in-tales-backend/src/main.py`
- **new_ai_workflow** → `tuck-in-tales-backend/src/graphs/{domain}_generator.py`
- **new_backend_model** → `tuck-in-tales-backend/src/models/{domain}.py`
- **new_web_page** → `tuck-in-tales-frontend/src/pages/{Domain}Page.tsx + route in tuck-in-tales-frontend/src/App.tsx`
- **new_web_hook** → `tuck-in-tales-frontend/src/hooks/use{Domain}.ts`
- **new_mobile_screen** → `tuck-in-tales-mobile/app/(tabs)/{screen}.tsx or tuck-in-tales-mobile/app/{path}.tsx`
- **new_mobile_query** → `tuck-in-tales-mobile/src/hooks/queries/use{Domain}.ts`
- **shared_ui_component** → `tuck-in-tales-frontend/src/components/ui/{component}.tsx (shadcn pattern)`

---
*Auto-generated from structured architecture analysis.*
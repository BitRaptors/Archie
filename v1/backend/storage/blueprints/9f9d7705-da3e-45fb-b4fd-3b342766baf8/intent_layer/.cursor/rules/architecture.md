---
description: Architecture rules: components, file placement, naming conventions
alwaysApply: true
---

## Components

### API Routes
- **Location:** `tuck-in-tales-backend/src/routes/`
- **Responsibility:** FastAPI route handlers; delegates to graphs/services; returns JSON or SSE streams
- **Depends on:** Authentication, Graph Layer, Service Layer, Supabase Client

### Graph Layer
- **Location:** `tuck-in-tales-backend/src/graphs/`
- **Responsibility:** LangGraph StateGraph workflows for story, avatar, and memory AI operations
- **Depends on:** LLM Clients, SSE Utility, Supabase Client, Prompt Resolver

### Authentication
- **Location:** `tuck-in-tales-backend/src/utils/auth.py`
- **Responsibility:** Verifies Firebase ID tokens; resolves or creates Supabase user records
- **Depends on:** Firebase Admin SDK, Supabase Client, User Model

### SSE Utility
- **Location:** `tuck-in-tales-backend/src/utils/sse.py`
- **Responsibility:** asyncio.Queue registry keyed by client_id; emit and stream SSE events

### LLM Clients
- **Location:** `tuck-in-tales-backend/src/utils/`
- **Responsibility:** Provider-specific wrappers for OpenAI, Gemini, Groq APIs
- **Depends on:** Configuration

### Web Frontend
- **Location:** `tuck-in-tales-frontend/src/`
- **Responsibility:** React SPA with pages, SSE hooks, and auth context for all app features
- **Depends on:** Backend API, Firebase Auth, Supabase

### Mobile Frontend
- **Location:** `tuck-in-tales-mobile/`
- **Responsibility:** Expo Router mobile app with tab navigation, TanStack Query data fetching
- **Depends on:** Backend API, Firebase Auth, Supabase

## File Placement

| Component Type | Location | Naming | Example |
|---------------|----------|--------|---------|
| backend_route | `tuck-in-tales-backend/src/routes/` | `{domain}.py` | `tuck-in-tales-backend/src/routes/stories.py` |
| backend_graph | `tuck-in-tales-backend/src/graphs/` | `{domain}_generator.py or {domain}_analyzer.py` | `tuck-in-tales-backend/src/graphs/story_generator.py` |
| backend_model | `tuck-in-tales-backend/src/models/` | `{domain}.py` | `tuck-in-tales-backend/src/models/character.py` |
| web_page | `tuck-in-tales-frontend/src/pages/` | `{Domain}Page.tsx` | `tuck-in-tales-frontend/src/pages/StoryGenerationPage.tsx` |
| web_hook | `tuck-in-tales-frontend/src/hooks/` | `use{Domain}Stream.ts` | `tuck-in-tales-frontend/src/hooks/useStoryStream.ts` |
| mobile_query_hook | `tuck-in-tales-mobile/src/hooks/queries/` | `use{Domain}s.ts or use{Domain}.ts` | `tuck-in-tales-mobile/src/hooks/queries/useCharacters.ts` |

## Where to Put Code

- **new_backend_route** -> `tuck-in-tales-backend/src/routes/{domain}.py + register in tuck-in-tales-backend/src/main.py`
- **new_ai_workflow** -> `tuck-in-tales-backend/src/graphs/{domain}_generator.py`
- **new_backend_model** -> `tuck-in-tales-backend/src/models/{domain}.py`
- **new_web_page** -> `tuck-in-tales-frontend/src/pages/{Domain}Page.tsx + route in tuck-in-tales-frontend/src/App.tsx`
- **new_web_hook** -> `tuck-in-tales-frontend/src/hooks/use{Domain}.ts`
- **new_mobile_screen** -> `tuck-in-tales-mobile/app/(tabs)/{screen}.tsx or tuck-in-tales-mobile/app/{path}.tsx`
- **new_mobile_query** -> `tuck-in-tales-mobile/src/hooks/queries/use{Domain}.ts`
- **shared_ui_component** -> `tuck-in-tales-frontend/src/components/ui/{component}.tsx (shadcn pattern)`

## Naming Conventions

- **backend**: snake_case for files, functions, variables (e.g. `family_service.py`, `get_supabase_client`, `verify_firebase_token`)
- **frontend_web**: PascalCase components, camelCase hooks/utils (e.g. `CharacterList.tsx`, `useStoryStream.ts`, `promptVariables.ts`)
- **mobile**: File-based routes use lowercase with brackets for dynamic segments (e.g. `app/(tabs)/characters.tsx`, `app/story/[id].tsx`, `app/(auth)/login.tsx`)
- **models**: Shared domain names across backend (Pydantic) and frontend (TypeScript interfaces) (e.g. `character.py / character.ts`, `story.py / story.ts`, `family.py / family.ts`)
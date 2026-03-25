## Developer Recipes

### Add a new AI-powered feature with streaming progress
Files: `tuck-in-tales-backend/src/graphs/story_generator.py`, `tuck-in-tales-backend/src/utils/sse.py`, `tuck-in-tales-backend/src/routes/stories.py`, `tuck-in-tales-frontend/src/hooks/useSSEStream.ts`, `tuck-in-tales-frontend/src/hooks/useStoryStream.ts`
1. 1. Create tuck-in-tales-backend/src/graphs/{domain}_generator.py with LangGraph StateGraph; nodes call send_sse_event(client_id, 'chunk'/'status'/'done', data)
2. 2. Add SSE route in tuck-in-tales-backend/src/routes/{domain}.py: POST to start generation, GET /{id}/stream returns StreamingResponse(sse_generator(id))
3. 3. Register router in tuck-in-tales-backend/src/main.py
4. 4. Create tuck-in-tales-frontend/src/hooks/use{Domain}Stream.ts extending useSSEStream.ts with domain-specific event handlers
5. 5. Use hook in tuck-in-tales-frontend/src/pages/{Domain}Page.tsx to display real-time progress

### Add a new backend CRUD resource
Files: `tuck-in-tales-backend/src/models/character.py`, `tuck-in-tales-backend/src/routes/characters.py`, `tuck-in-tales-backend/src/main.py`, `tuck-in-tales-frontend/src/models/character.ts`, `tuck-in-tales-frontend/src/api/client.ts`
1. 1. Create Pydantic model in tuck-in-tales-backend/src/models/{domain}.py
2. 2. Create route file in tuck-in-tales-backend/src/routes/{domain}.py with Depends(verify_firebase_token) and Depends(get_supabase_client) on each handler
3. 3. Register router in tuck-in-tales-backend/src/main.py: app.include_router({domain}_router)
4. 4. Mirror TypeScript interface in tuck-in-tales-frontend/src/models/{domain}.ts and tuck-in-tales-mobile/src/models/{domain}.ts
5. 5. Add mobile query hook in tuck-in-tales-mobile/src/hooks/queries/use{Domain}s.ts

### Add a new web page with protected route
Files: `tuck-in-tales-frontend/src/pages/CharactersPage.tsx`, `tuck-in-tales-frontend/src/App.tsx`, `tuck-in-tales-frontend/src/components/Layout/Sidebar.tsx`
1. 1. Create tuck-in-tales-frontend/src/pages/{Domain}Page.tsx as a React functional component
2. 2. Add route in tuck-in-tales-frontend/src/App.tsx inside the AppLayout ProtectedRoute wrapper: <Route path='/{domain}' element={<{Domain}Page />} />
3. 3. Add navigation link in tuck-in-tales-frontend/src/components/Layout/Sidebar.tsx

### Add a new mobile tab screen
Files: `tuck-in-tales-mobile/app/(tabs)/_layout.tsx`, `tuck-in-tales-mobile/app/(tabs)/characters.tsx`, `tuck-in-tales-mobile/src/hooks/queries/useCharacters.ts`
1. 1. Create tuck-in-tales-mobile/app/(tabs)/{screen}.tsx as Expo Router screen component
2. 2. Add tab entry in tuck-in-tales-mobile/app/(tabs)/_layout.tsx TabList
3. 3. Create data hook in tuck-in-tales-mobile/src/hooks/queries/use{Domain}.ts using TanStack Query useQuery wrapping api/client.ts

## Implementation Guidelines

### Firebase Auth + Backend Token Verification [auth]
Libraries: `firebase-admin`, `firebase/auth`
Pattern: Frontend obtains Firebase ID token via auth.currentUser.getIdToken(); token sent as Bearer in Authorization header; backend Depends(verify_firebase_token) in auth.py validates via Firebase Admin SDK and provisions Supabase user on first login
Key files: `tuck-in-tales-backend/src/utils/auth.py`, `tuck-in-tales-backend/src/utils/firebase_admin_init.py`, `tuck-in-tales-frontend/src/context/AuthContext.tsx`, `tuck-in-tales-frontend/src/firebaseConfig.ts`, `tuck-in-tales-mobile/src/context/AuthContext.tsx`, `tuck-in-tales-mobile/src/config/firebase.ts`
Example: `@router.post('/') async def create(user_data: UserData = Depends(verify_firebase_token))`
- Token refresh is handled by Firebase SDK; use onAuthStateChanged for reactive updates
- api/client.ts on both platforms injects token automatically; never add Authorization manually
- get_or_create_supabase_user() is called per request; profile data is in Supabase, not Firebase

### SSE Streaming for Generation Progress [networking]
Libraries: `asyncio`, `FastAPI StreamingResponse`, `EventSource (browser)`
Pattern: asyncio.Queue registry in sse.py keyed by client_id; graph nodes call send_sse_event(id, event, data); route exposes GET /{id}/stream returning StreamingResponse(sse_generator(id)); frontend useSSEStream.ts opens EventSource and dispatches named events
Key files: `tuck-in-tales-backend/src/utils/sse.py`, `tuck-in-tales-frontend/src/hooks/useSSEStream.ts`, `tuck-in-tales-frontend/src/hooks/useStoryStream.ts`, `tuck-in-tales-frontend/src/hooks/useAvatarStream.ts`, `tuck-in-tales-frontend/src/hooks/useMemoryStream.ts`
Example: `const { pages, isStreaming } = useStoryStream(storyId);`
- client_id must match between graph state and frontend hook parameter (typically story_id or character_id)
- Always emit terminal event ('done'/'error') from graph nodes to close EventSource
- SSE is unidirectional; use REST for any client→server communication during streaming

### LangGraph AI Workflow Orchestration [state_management]
Libraries: `langgraph`
Pattern: StateGraph compiled with async nodes; state flows as TypedDict; nodes invoke LLM clients, emit SSE events, update Supabase; graph invoked from route handlers via compiled_graph.stream(initial_state)
Key files: `tuck-in-tales-backend/src/graphs/story_generator.py`, `tuck-in-tales-backend/src/graphs/avatar_generator.py`, `tuck-in-tales-backend/src/graphs/memory_analyzer.py`
Example: `workflow = StateGraph(StoryState); workflow.add_node('generate', node_fn); app = workflow.compile()`
- Use asyncio.to_thread() for sync Supabase client calls within async nodes
- State TypedDict must be defined before graph compilation
- Emit SSE status events at start of each node for frontend progress indication

### Multi-Provider AI Client Abstraction [networking]
Libraries: `openai`, `google-generativeai`, `groq`
Pattern: Separate client modules per provider; IMAGE_GENERATION_PROVIDER env var in config.py selects provider at runtime; graphs use if/elif to route to correct client; FALLBACK_DEFAULTS in prompt_resolver.py specify per-prompt provider
Key files: `tuck-in-tales-backend/src/config.py`, `tuck-in-tales-backend/src/utils/openai_client.py`, `tuck-in-tales-backend/src/utils/gemini_client.py`, `tuck-in-tales-backend/src/utils/groq_client.py`, `tuck-in-tales-backend/src/utils/prompt_resolver.py`
Example: `if settings.IMAGE_GENERATION_PROVIDER == 'OPENAI': await openai_client.generate_image(desc)`
- All API keys loaded via pydantic-settings BaseSettings in config.py from environment
- Missing optional provider keys (GROQ_API_KEY) won't break startup; only fail at call time
- Avatar uses Gemini vision for analysis; OpenAI gpt-image-1 for generation by default

### Prompt Template Resolution with Caching [state_management]
Libraries: `functools`
Pattern: resolve_prompt(key, variables, supabase) in prompt_resolver.py fetches prompt config from Supabase 'prompts' table, caches with TTL, performs ${variable} substitution; falls back to FALLBACK_DEFAULTS dict if DB row missing
Key files: `tuck-in-tales-backend/src/utils/prompt_resolver.py`, `tuck-in-tales-backend/src/models/prompt.py`, `tuck-in-tales-frontend/src/components/prompts/PromptEditor.tsx`, `tuck-in-tales-frontend/src/pages/PromptsPage.tsx`
Example: `prompt_config = await resolve_prompt('story_generation', {'character': name}, supabase)`
- PromptEditor/PromptPlayground in web frontend allows live editing of prompt templates in Supabase
- FALLBACK_DEFAULTS in prompt_resolver.py must be updated when adding new prompt keys
- Cache TTL is ~60s; changes to prompts in Supabase are reflected within 1 minute
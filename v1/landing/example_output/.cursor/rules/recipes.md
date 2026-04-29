---
description: Developer recipes and implementation guidelines
alwaysApply: true
---

## Developer Recipes

### Add a new analysis capability / feature flag
Files: `backend/src/domain/entities/analysis_settings.py`, `backend/src/api/routes/settings.py`, `backend/src/api/dto/requests.py`, `frontend/components/views/CapabilitiesSettingsView.tsx`, `frontend/services/settings.ts`
1. 1. Add new field to AnalysisSettings entity in domain/entities/analysis_settings.py
2. 2. Update settings DTO in api/dto/requests.py and settings route in api/routes/settings.py
3. 3. Add toggle UI in CapabilitiesSettingsView.tsx; update frontend/services/settings.ts to send new field

### Add a new background analysis task
Files: `backend/src/workers/tasks.py`, `backend/src/workers/worker.py`, `backend/src/application/services/analysis_service.py`
1. 1. Define async task function in backend/src/workers/tasks.py with ctx parameter
2. 2. Register task in WorkerSettings.functions list in backend/src/workers/worker.py
3. 3. Enqueue from analysis_service.py using arq queue.enqueue('task_name', **kwargs)

### Add a new REST endpoint with frontend integration
Files: `backend/src/api/routes/{domain}.py`, `backend/src/api/app.py`, `frontend/services/{domain}.ts`, `frontend/hooks/api/use{Domain}.ts`
1. 1. Create route handler in backend/src/api/routes/{domain}.py using APIRouter; add DTOs
2. 2. Register router in backend/src/api/app.py include_router call
3. 3. Add Axios call in frontend/services/{domain}.ts; create frontend/hooks/api/use{Domain}.ts hook consuming it

### Run and debug analysis pipeline locally
Files: `start-dev.py`, `backend/.env.local`, `frontend/.env.local`, `backend/src/workers/tasks.py`
1. 1. Ensure backend/.env.local and frontend/.env.local exist (copy from .env.example); set ANTHROPIC_API_KEY, REDIS_URL, DB credentials
2. 2. Start Redis via docker-compose or local install; run python start-dev.py to launch backend + ARQ worker + frontend
3. 3. Trigger analysis via dashboard at localhost:{frontend_port}; watch worker logs for PhasedBlueprintGenerator phases

## Implementation Guidelines

### JWT Authentication with Supabase Auth [authentication]
Libraries: `python-jose[cryptography]>=3.3.0`, `passlib[bcrypt]>=1.7.4`, `supabase>=2.0.0`
Pattern: Backend validates JWT via python-jose; Supabase Auth is the identity provider; frontend stores token in AuthContext and attaches as Bearer header via Axios interceptors in services.
Key files: `backend/src/api/routes/auth.py`, `backend/src/domain/entities/user.py`, `frontend/context/auth.tsx`, `frontend/hooks/useAuth.tsx`, `frontend/services/auth.ts`
Example: `const { user, login } = useAuth(); await login(email, password);`
- Token expiry must be validated server-side on every request via FastAPI Depends(get_current_user)
- Supabase Auth claims must align with custom JWT validation logic in auth.py

### Phased AI Blueprint Generation with Streaming [ai_analysis]
Libraries: `anthropic>=0.7.0`, `sse-starlette>=1.8.0`, `tiktoken>=0.7.0`
Pattern: PhasedBlueprintGenerator calls Claude across multiple phases with RAG-retrieved code context per phase; progress_callback persists AnalysisEvent objects; frontend streams events via SSE.
Key files: `backend/src/application/services/phased_blueprint_generator.py`, `backend/src/api/routes/analyses.py`, `backend/src/infrastructure/analysis/rag_retriever.py`, `backend/src/infrastructure/prompts/database_prompt_loader.py`
Example: `await phased_gen.generate(analysis, progress_callback=log_event_to_db)`
- Use tiktoken to count tokens before each Claude call to avoid context window overflow
- Prompt loader can be swapped: file-based PromptLoader or DatabasePromptLoader injected via constructor

### Dual-backend Database Abstraction [persistence]
Libraries: `asyncpg>=0.29.0`, `supabase>=2.0.0`, `psycopg2-binary>=2.9.9`
Pattern: db_factory.py reads DB_BACKEND env var and returns either PostgresAdapter (asyncpg pool) or SupabaseAdapter (PostgREST); all repositories receive DatabaseClient interface, never concrete adapter.
Key files: `backend/src/infrastructure/persistence/db_factory.py`, `backend/src/infrastructure/persistence/postgres_adapter.py`, `backend/src/infrastructure/persistence/supabase_adapter.py`, `backend/src/domain/interfaces/database.py`
Example: `db_client = await create_db(settings)  # returns DatabaseClient`
- Connection pool (_cached_pool) is initialized once; call shutdown_db() on app shutdown to release connections
- Add HNSW index on pgvector columns for production similarity search performance

### RAG-based Code Retrieval with pgvector [persistence]
Libraries: `sentence-transformers>=2.2.0`, `torch>=2.0.0`, `pgvector>=0.2.0`
Pattern: SharedEmbedder generates code vectors; stored in pgvector columns; RAGRetriever performs cosine similarity search to fetch relevant code snippets for each LLM analysis phase.
Key files: `backend/src/infrastructure/analysis/shared_embedder.py`, `backend/src/infrastructure/analysis/query_embedder.py`, `backend/src/infrastructure/analysis/rag_retriever.py`
Example: `snippets = await rag_retriever.retrieve_similar(repo_id, query_vector, top_k=5)`
- SharedEmbedder is a singleton — do not instantiate per-request
- Vector dimension in DB column must match model output dimension exactly

### MCP Server for Claude Tool Integration [ai_integration]
Libraries: `anthropic>=0.7.0`
Pattern: infrastructure/mcp/ exposes analysis resources and tools via Model Context Protocol; Claude can query blueprints and codebase maps directly through the MCP server endpoint.
Key files: `backend/src/infrastructure/mcp/server.py`, `backend/src/infrastructure/mcp/resources.py`, `backend/src/infrastructure/mcp/tools.py`, `backend/src/api/routes/mcp.py`
Example: `MCP server registered at /mcp route; Claude calls tools defined in infrastructure/mcp/tools.py`
- MCP tools and resources must be kept in sync with actual domain entity schemas
- Test MCP integration via backend/tests/unit/infrastructure/test_mcp_server.py
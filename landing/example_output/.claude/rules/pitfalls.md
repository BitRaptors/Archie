## Pitfalls

- **ARQ Worker / Redis:** If Redis is unavailable at startup, start-dev.py falls back to in-process analysis silently — but production deployments require Redis for task persistence. Lost tasks are not retried.
  - *Always verify Redis connection before deploying; check REDIS_URL in backend/.env.local; monitor Redis memory to prevent queue overflow*
- **DB Backend Selection:** DB_BACKEND env var controls PostgresAdapter vs SupabaseAdapter selection in db_factory.py; wrong value silently uses wrong adapter, causing query failures.
  - *Explicitly set DB_BACKEND='postgres' or DB_BACKEND='supabase' in .env.local; run backend/tests/unit/infrastructure/test_db_factory.py to verify*
- **Prompts Version Mismatch:** start-dev.py checks prompts.json version against .prompts-version file and hard-exits if mismatched — running without ./setup.sh after a pull will block startup.
  - *Always run ./setup.sh after pulling changes that bump prompts.json version*
- **pgvector Embeddings:** SharedEmbedder loads full sentence-transformers model on first use (5-10s); vector column dimension must match model output (e.g. 384 for all-MiniLM-L6-v2) or inserts will fail silently.
  - *Use singleton pattern (already in shared_embedder.py); ensure vector(N) column dimension matches model in migrations/001_initial_setup.sql*
- **SSE Frontend Connection:** SSE streams from /analyses/{id}/stream are long-lived; if the frontend component unmounts without closing the EventSource, connections leak and Redis/ARQ events accumulate.
  - *Always close EventSource in useEffect cleanup function in the consuming hook*

## Error Mapping

| Error | Status Code |
|-------|------------|
| `DomainException` | 400 |
| `Not found entity` | 404 |
| `Unauthenticated` | 401 |
| `Unhandled exception` | 500 |
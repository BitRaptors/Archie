---
description: Development rules: imperative do/don't rules from codebase signals
alwaysApply: true
---

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
## Development Rules

### Ci Cd

- Never push Docker images manually — backend/cloudbuild.yaml defines the full build/push/deploy pipeline to GCR and Cloud Run; trigger via GCP Cloud Build *(source: `backend/cloudbuild.yaml`)*

### Code Style

- Never place infrastructure imports (asyncpg, supabase SDK, anthropic) inside domain/entities/ or domain/interfaces/ — domain layer must stay framework-free *(source: `backend/src/domain/interfaces/database.py (pure ABC, no imports from infra)`)*
- Never modify files in frontend/components/ui/ directly — these are shadcn/radix primitives; extend by composing them in feature components under frontend/components/views/ *(source: `frontend/components/ui/ structure mirroring shadcn/ui generation pattern`)*

### Dependency Management

- Always add Python dependencies to backend/requirements.txt with pinned minimum versions; never use poetry or pipenv — the project uses plain pip with venv at backend/.venv *(source: `backend/requirements.txt + start-dev.py venv creation logic`)*
- Always use npm for frontend and landing dependencies; run npm install in the respective directory (frontend/ or landing/) — no yarn or pnpm detected *(source: `frontend/package.json, landing/package.json, start-dev.py npm run dev invocation`)*

### Environment

- Always create backend/.env.local and frontend/.env.local from .env.example before running; start-dev.py will hard-exit if either is missing *(source: `start-dev.py check_env_files() function`)*
- Always run ./setup.sh after pulling commits that change prompts.json — start-dev.py validates prompts version against .prompts-version and refuses to start on mismatch *(source: `start-dev.py version check block reading backend/prompts.json and backend/.prompts-version`)*

### Testing

- Always write async tests using pytest-asyncio for any code touching asyncpg, ARQ, or Anthropic SDK; use unittest.mock.AsyncMock for async dependencies *(source: `backend/tests/conftest.py + backend/tests/unit/services/test_phased_blueprint_generator.py pattern`)*
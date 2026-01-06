# Setup Guide

## Database Setup ✅

All database migrations have been successfully applied to the Supabase project "ArchitectureMCP" (ID: `jxkfqiotreydrlgglsrt`).

**Project Details:**
- URL: `https://jxkfqiotreydrlgglsrt.supabase.co`
- Anon Key: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp4a2ZxaW90cmV5ZHJsZ2dsc3J0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc2MzIyNjYsImV4cCI6MjA4MzIwODI2Nn0.f9uROBzyPfRPUlI6H2jyuQ68IAMGJ34ztelnE-Bg-rU`

**Tables Created:**
- ✅ users
- ✅ repositories
- ✅ analyses
- ✅ blueprints
- ✅ unified_blueprints
- ✅ unified_blueprint_repositories
- ✅ analysis_prompts
- ✅ analysis_configurations
- ✅ analysis_data
- ✅ embeddings (with pgvector extension)

## Environment Configuration

### Backend (.env.local)

Create `backend/.env.local` with the following content:

```bash
# Application
APP_NAME=Repository Analysis API
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=true

# Server
HOST=0.0.0.0
PORT=8000

# Supabase
SUPABASE_URL=https://jxkfqiotreydrlgglsrt.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp4a2ZxaW90cmV5ZHJsZ2dsc3J0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc2MzIyNjYsImV4cCI6MjA4MzIwODI2Nn0.f9uROBzyPfRPUlI6H2jyuQ68IAMGJ34ztelnE-Bg-rU
# Get JWT_SECRET from Supabase Dashboard > Settings > API > JWT Secret
SUPABASE_JWT_SECRET=your-jwt-secret-here

# Redis
REDIS_URL=redis://localhost:6379

# GitHub API (optional, users provide their own tokens)
GITHUB_TOKEN=

# AI Providers
# Get your Anthropic API key from https://console.anthropic.com/
ANTHROPIC_API_KEY=your-anthropic-api-key-here
DEFAULT_AI_MODEL=claude-3-5-sonnet-20241022

# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Vector Database
VECTOR_DB_TYPE=pgvector

# Storage
STORAGE_TYPE=local

# Analysis
MAX_ANALYSIS_WORKERS=4
ANALYSIS_TIMEOUT_SECONDS=3600
```

### Frontend (.env.local)

Create `frontend/.env.local` with:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Running the Application

### Backend

1. Activate virtual environment:
```bash
cd backend
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. Start the server:
```bash
python src/main.py
# Or: uvicorn src.main:app --reload
```

The API will be available at `http://localhost:8000`

### Frontend

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Required API Keys

Before running the application, you need to:

1. **Get Supabase JWT Secret:**
   - Go to Supabase Dashboard: https://supabase.com/dashboard/project/jxkfqiotreydrlgglsrt
   - Navigate to Settings > API
   - Copy the JWT Secret
   - Add it to `backend/.env.local` as `SUPABASE_JWT_SECRET`

2. **Get Anthropic API Key:**
   - Go to https://console.anthropic.com/
   - Create an API key
   - Add it to `backend/.env.local` as `ANTHROPIC_API_KEY`

3. **Optional - Redis:**
   - Install Redis locally or use Redis Cloud
   - Update `REDIS_URL` in `backend/.env.local` if needed

## Testing the Setup

1. Test backend health endpoint:
```bash
curl http://localhost:8000/health
```

2. Test frontend:
   - Open http://localhost:3000
   - You should see the authentication page

## Next Steps

1. Configure environment variables (see above)
2. Start Redis (if using background tasks)
3. Run backend: `cd backend && source .venv/bin/activate && python src/main.py`
4. Run frontend: `cd frontend && npm run dev`
5. Test the application by authenticating with a GitHub token



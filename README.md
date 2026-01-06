# Repository Analysis System

A comprehensive system for analyzing GitHub repositories and generating architecture blueprints accessible via MCP.

## Architecture

- **Backend**: FastAPI (Python) with layered architecture
- **Frontend**: Next.js (React/TypeScript)
- **Database**: Supabase (PostgreSQL with pgvector)
- **Storage**: Cloud Storage (GCS/S3) or Local
- **MCP Server**: Extends existing MCP server with analyzed repository resources

## Quick Start

### Start Both Servers

Use the startup script to run both backend and frontend:

**Linux/Mac:**
```bash
./start-dev.sh
```

**Windows:**
```batch
start-dev.bat
```

**Python (Cross-platform):**
```bash
python start-dev.py
```

This will automatically:
- Check for required environment files
- Create virtual environment if needed
- Install dependencies if needed
- Start backend on http://localhost:8000
- Start frontend on http://localhost:3000

Press `Ctrl+C` to stop both servers.

## Setup

### Prerequisites

1. **Configure environment variables:**
   - Copy `backend/.env.example` to `backend/.env.local`
   - Add your `SUPABASE_JWT_SECRET` and `ANTHROPIC_API_KEY`
   - Copy `frontend/.env.example` to `frontend/.env.local` (if needed)

2. **Database setup:**
   - All migrations have been applied to Supabase
   - See `SETUP_COMPLETE.md` for details

### Manual Setup (if not using startup script)

**Backend:**

1. Install dependencies:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Start server:
```bash
python src/main.py
# Or: uvicorn src.main:app --reload
```

**Frontend:**

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start dev server:
```bash
npm run dev
```

## Key Features

- GitHub repository analysis
- Embedding-based semantic search
- Custom prompt system
- Unified blueprints from multiple repos
- MCP integration for Cursor

## Getting Started

### 1. Get a GitHub Token

You'll need a GitHub Personal Access Token to authenticate. See **[GITHUB_TOKEN_GUIDE.md](./GITHUB_TOKEN_GUIDE.md)** for detailed instructions.

**Quick steps:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scopes: `repo` and `read:user`
4. Copy the token (starts with `ghp_`)

### 2. Start the Application

```bash
./start-dev.sh
```

### 3. Authenticate

1. Open the frontend (usually http://localhost:3000)
2. Navigate to the Authentication page
3. Paste your GitHub token
4. Click "Authenticate"

## Development

See the plan document for detailed implementation guide.

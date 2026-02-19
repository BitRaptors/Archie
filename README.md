# Architecture Blueprints

AI-powered system that analyzes GitHub repositories, learns their architecture, and enforces it through AI coding agents via MCP.

## Why

**Claude Code reads your code. Architecture Blueprints understands your architecture.**

AI agents write code that works but is architecturally blind — each session they skim a few files and guess. After 50 AI-assisted PRs you have 50 different interpretations of where things go and which patterns to use.

Architecture Blueprints fixes this:

- **Deep analysis** — 7-9 AI phases scan your entire codebase: layers, naming, communication patterns, implementation patterns. Minutes of structured analysis, not seconds of skimming.
- **Real-time enforcement** — MCP tools the agent calls *before* acting. `where_to_put`, `check_naming`, `how_to_implement` return concrete answers, not suggestions.
- **One source of truth** — CLAUDE.md, Cursor rules, AGENTS.md, and MCP tools all derive from the same blueprint. Switch tools, onboard someone — same rules.
- **Reuse what works** — Analyzed a well-architected project? Apply its blueprint as a reference architecture for new projects. Your best codebase becomes a reusable template that every AI agent follows — proven patterns, not reinvented ones.

## How It Works

```
  GitHub Repo
       |
       v
  1. Clone & Extract    -- file tree, dependencies, configs, code samples
       |
       v
  2. RAG Index           -- chunk code, embed with sentence-transformers, store in pgvector
       |
       v
  3. Phased AI Analysis  -- 7-9 Claude API calls, each building on the previous
       |                     (observation → smart file reading → discovery →
       |                      layers → patterns → communication → technology →
       |                      [frontend] → implementation analysis → synthesis)
       v
  4. StructuredBlueprint -- single JSON source of truth (Pydantic model)
       |
       ├──> CLAUDE.md          -- AI agent instructions for project root
       ├──> .cursor/rules/     -- Cursor IDE integration
       ├──> AGENTS.md          -- multi-agent system guidance
       ├──> MCP Server         -- real-time where_to_put, check_naming
       └──> Delivery to GitHub -- push outputs via PR or direct commit (non-destructive merge)
```

The AI agent in your IDE connects to the MCP server. Before it creates a file, it calls `where_to_put`. Before it names a class, it calls `check_naming`. If any check fails, the agent fixes the violation before proceeding.

## How to Set Up

### Prerequisites

- An [Anthropic API key](https://console.anthropic.com) (the only required secret)
- Docker (installed automatically by setup script on macOS/Linux) — or a [Supabase](https://supabase.com) project if you prefer cloud database
- Python 3.11+ and Node.js 18+ (installed automatically by setup script if missing)

### Quick Start (recommended)

```bash
git clone https://github.com/your-org/architecture-blueprints.git
cd architecture-blueprints

# One-time setup — installs everything, creates env files, starts database
./setup.sh

# Start the application
./start-dev.sh       # Linux/Mac
# Or: python start-dev.py (cross-platform) / start-dev.bat (Windows)
```

**That's it.** The setup script will:
1. Ask you to choose a database: **postgres** (local Docker, recommended) or **supabase** (cloud)
2. Install Docker, Python, and Node.js if missing
3. Start PostgreSQL + Redis containers (if postgres chosen)
4. Run database migrations automatically (tables, indexes, seed data)
5. Create Python venv and install backend dependencies
6. Install frontend dependencies
7. Generate `backend/.env.local` and `frontend/.env.local` — prompting you for your Anthropic API key

Then `start-dev.sh` starts backend (`http://localhost:8000`), frontend (`http://localhost:4000`), and an ARQ worker (if Redis is available).

### Database Options

| Option | When to use | What happens |
|--------|------------|--------------|
| **postgres** (recommended) | Local development, no cloud account needed | Docker runs PostgreSQL (with pgvector) + Redis locally. Migration runs automatically on first start. |
| **supabase** | You already have a Supabase project, or want cloud persistence | You must manually run `backend/migrations/001_initial_setup.sql` in your Supabase SQL editor. |

### Manual Setup (alternative)

If you prefer not to use `setup.sh`:

```bash
# 1. Create env files
cp backend/.env.example backend/.env.local   # Fill in ANTHROPIC_API_KEY + DB credentials
cp frontend/.env.example frontend/.env.local  # Defaults work as-is

# 2. Start database (pick one)
docker compose up -d                          # Local postgres + redis
# OR: run 001_initial_setup.sql in your Supabase SQL editor

# 3. Install dependencies
cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd ../frontend && npm install

# 4. Start
cd ../backend && PYTHONPATH=src uvicorn main:app --reload --port 8000
# In another terminal:
cd frontend && npm run dev
```

### Get a GitHub Token

You need a GitHub Personal Access Token for repository access: [github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic) → select `repo` + `read:user` scopes.

## How to Use

### Analyze a repository

1. Open the frontend at `http://localhost:4000`
2. Authenticate with your GitHub token
3. Enter a repository URL and start analysis
4. Wait for the phased analysis to complete (typically 1-3 minutes)
5. View the generated blueprint, CLAUDE.md, Cursor rules, and analysis data

### Deliver outputs to a repo

1. From the blueprint view, open the Delivery panel
2. Select which outputs to push (CLAUDE.md, AGENTS.md, Cursor rules, MCP configs)
3. Choose strategy: **PR** (creates a branch + pull request) or **commit** (direct to default branch)
4. The delivery pipeline merges non-destructively — your existing content is preserved

### Connect the MCP server to your IDE

Add the MCP server to your IDE config (`.mcp.json` or `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "architecture-blueprints": {
      "url": "http://localhost:8000/mcp/sse"
    }
  }
}
```

The MCP server exposes these tools:

| Tool | Purpose |
|------|---------|
| `where_to_put` | Get correct directory and naming pattern for a component |
| `check_naming` | Verify a name follows the project's conventions |
| `get_repository_blueprint` | Get the full architecture blueprint |
| `list_repository_sections` | List addressable blueprint sections |
| `get_repository_section` | Get a specific section (token-efficient) |
| `how_to_implement` | Look up how a capability is already implemented (libraries, patterns, key files) |

### Run tests

```bash
cd backend
PYTHONPATH=src python -m pytest tests/unit/ -v
```

---

For detailed technical documentation, architecture internals, and API reference, see **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**.

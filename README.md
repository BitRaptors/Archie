# Architecture Blueprints

AI-powered system that analyzes GitHub repositories, learns their architecture, and enforces it through AI coding agents via MCP.

## Why

AI coding agents (Claude Code, Cursor, Copilot) are powerful but architecturally unaware. They generate code that works but often violates your project's conventions: wrong file locations, forbidden imports, inconsistent naming, broken layer boundaries.

**Architecture Blueprints** solves this by:

- **Learning your architecture automatically** — no manual rule-writing. Point it at a repo, and it discovers patterns, layers, naming conventions, and dependency rules from the actual code.
- **Enforcing it in real-time** — the `architecture-blueprints` MCP server provides tools that AI agents must call before creating files, adding imports, or naming components. The agent gets a yes/no answer instantly.
- **Keeping every AI tool in sync** — a single `StructuredBlueprint` JSON is the source of truth. CLAUDE.md, Cursor rules, AGENTS.md, and MCP tools all derive from it. Change the blueprint, and every output updates.
- **Preserving your existing config** — the delivery pipeline merges into your files (fenced markdown sections, key-level JSON merge) instead of overwriting them.

Without this, every AI-generated PR is a coin flip on whether it follows your architecture. With it, the agent checks the rules before writing a single line.

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
  3. Phased AI Analysis  -- 6-8 Claude API calls, each building on the previous
       |                     (observation → discovery → layers → patterns →
       |                      communication → technology → [frontend] → synthesis)
       v
  4. StructuredBlueprint -- single JSON source of truth (Pydantic model)
       |
       ├──> CLAUDE.md          -- AI agent instructions for project root
       ├──> .cursor/rules/     -- Cursor IDE integration
       ├──> AGENTS.md          -- multi-agent system guidance
       ├──> MCP Server         -- real-time validate_import, where_to_put, check_naming
       └──> Delivery to GitHub -- push outputs via PR or direct commit (non-destructive merge)
```

The AI agent in your IDE connects to the MCP server. Before it creates a file, it calls `where_to_put`. Before it adds an import, it calls `validate_import`. Before it names a class, it calls `check_naming`. If any check fails, the agent fixes the violation before proceeding.

## How to Set Up

### Prerequisites

- Python 3.11+
- Node.js 18+
- A [Supabase](https://supabase.com) project (PostgreSQL + pgvector)
- An [Anthropic API key](https://console.anthropic.com)

### 1. Clone and configure environment

```bash
git clone https://github.com/your-org/architecture-blueprints.git
cd architecture-blueprints

# Backend
cp backend/.env.example backend/.env.local
# Edit backend/.env.local and fill in:
#   SUPABASE_URL, SUPABASE_KEY, SUPABASE_JWT_SECRET, ANTHROPIC_API_KEY

# Frontend
cp frontend/.env.example frontend/.env.local
# Edit frontend/.env.local:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Run database migrations

Run the initial migration `backend/migrations/001_initial_setup.sql` in your Supabase project (SQL editor or CLI). This single file creates all tables, indexes, and functions.

### 3. Start the application

```bash
# Option A: startup script (recommended)
./start-dev.sh       # Linux/Mac
start-dev.bat        # Windows
python start-dev.py  # Cross-platform
# Or manually:

# Option B: manual
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src uvicorn main:app --reload --port 8000

# In another terminal:
cd frontend
npm install && npm run dev
```

Backend runs on `http://localhost:8000`, frontend on `http://localhost:4000`.

### 4. Get a GitHub token

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
| `validate_import` | Check if an import is allowed by dependency rules |
| `where_to_put` | Get correct directory and naming pattern for a component |
| `check_naming` | Verify a name follows the project's conventions |
| `get_repository_blueprint` | Get the full architecture blueprint |
| `list_repository_sections` | List addressable blueprint sections |
| `get_repository_section` | Get a specific section (token-efficient) |

### Run tests

```bash
cd backend
PYTHONPATH=src python -m pytest tests/unit/ -v
```

---

For detailed technical documentation, architecture internals, and API reference, see **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**.

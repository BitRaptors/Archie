# Architecture Blueprints

AI-powered system that analyzes GitHub repositories, learns their architecture, and enforces it through AI coding agents via MCP.

## Why

**Claude Code reads your code. Architecture Blueprints understands your architecture.**

AI agents write code that works but is architecturally blind - each session they skim a few files and guess. After 50 AI-assisted PRs you have 50 different interpretations of where things go and which patterns to use.

Architecture Blueprints fixes this:

- **Deep analysis** - 7-9 AI phases scan your entire codebase: layers, naming, communication patterns, implementation patterns. Minutes of structured analysis, not seconds of skimming.
- **Per-folder context** - Every significant folder gets its own `CLAUDE.md` with architecture guidance, coding patterns, key file guides, and common tasks. AI agents land in any folder and immediately know the rules.
- **Real-time enforcement** - MCP tools the agent calls *before* acting. `where_to_put`, `check_naming`, `how_to_implement` return concrete answers, not suggestions.
- **One source of truth** - CLAUDE.md, Cursor rules, AGENTS.md, and MCP tools all derive from the same blueprint. Switch tools, onboard someone - same rules.
- **Incremental re-analysis** - Changed a few folders? Incremental mode reuses cached AI enrichment for unchanged folders, cutting re-analysis time dramatically.
- **Reuse what works** - Analyzed a well-architected project? Apply its blueprint as a reference architecture for new projects. Your best codebase becomes a reusable template that every AI agent follows - proven patterns, not reinvented ones.

## How It Works

```
  GitHub Repo
       |
       v
  1. Clone & Extract    -- file tree, dependencies, configs, code samples
       |
       v
  2. RAG Index           -- chunk code, embed with sentence-transformers, store in pgvector
       |                     file-level retrieval returns full files (not fragments)
       |                     phase-specific chunk type preferences boost relevance
       v
  3. Phased AI Analysis  -- 7-9 Claude API calls, each building on the previous
       |                     (observation -> smart file reading -> discovery ->
       |                      layers -> patterns -> communication -> technology ->
       |                      [frontend] -> implementation analysis -> synthesis)
       |                     file registry injected into every phase prompt
       |                     dynamic file reading budget based on repo size
       v
  4. StructuredBlueprint -- single JSON source of truth (Pydantic model)
       |
       v
  5. Intent Layer        -- per-folder CLAUDE.md generation
       |                     deterministic blueprint mapping onto folder hierarchy
       |                     optional AI enrichment (patterns, key file guides,
       |                     common tasks, anti-patterns, code examples)
       |                     CODEBASE_MAP.md for cross-cutting navigation
       |                     incremental mode skips unchanged folders
       |
       |---> CLAUDE.md (root)    -- AI agent instructions for project root
       |---> src/api/CLAUDE.md   -- per-folder context (every significant folder)
       |---> CODEBASE_MAP.md     -- flat architecture overview for quick reference
       |---> .claude/rules/      -- Claude Code rule files
       |---> .cursor/rules/      -- Cursor IDE integration
       |---> AGENTS.md           -- multi-agent system guidance
       |---> MCP Server          -- real-time where_to_put, check_naming
       \---> Delivery to GitHub  -- push outputs via PR or direct commit (non-destructive merge)
```

The AI agent in your IDE connects to the MCP server. Before it creates a file, it calls `where_to_put`. Before it names a class, it calls `check_naming`. If any check fails, the agent fixes the violation before proceeding.

## Quick Start

```bash
git clone https://github.com/your-org/architecture-blueprints.git
cd architecture-blueprints
./run
```

That's it. One command. `./run` handles everything:

1. Installs Docker, Python, and Node.js if missing
2. Starts PostgreSQL (with pgvector) + Redis via Docker
3. Creates `backend/.env.local` and `frontend/.env.local` with sane defaults
4. Prompts for your Anthropic API key (or skip - the app starts, just warns)
5. Creates Python venv and installs backend dependencies
6. Installs frontend dependencies
7. Runs database migrations and seeds prompts
8. Starts backend (`http://localhost:8000`), frontend (`http://localhost:4000`), and ARQ worker

On subsequent runs, `./run` auto-detects changes - new dependencies, stale prompts, schema changes - and handles them before starting. You never need to manually re-install or re-seed.

### The only thing you need

An [Anthropic API key](https://console.anthropic.com). The script will prompt you on first run. You can also skip it and add it later to `backend/.env.local`.

### Recovery

```bash
./run --reset    # Forces full re-setup (recreates env files, reinstalls deps, re-seeds DB)
```

Use `--reset` when things go wrong or after pulling breaking changes.

### Database Options

| Option | When to use | What happens |
|--------|------------|--------------|
| **postgres** (default) | Local development, zero cloud dependency | Docker runs PostgreSQL (with pgvector) + Redis locally. Migration runs automatically. |
| **supabase** | Cloud-hosted database | Set `DB_BACKEND=supabase` in `backend/.env.local` with your Supabase credentials. Run `backend/migrations/001_initial_setup.sql` in the Supabase SQL editor. |

### Legacy scripts

`setup.sh` and `start-dev.sh` still exist but simply redirect to `./run`. Use `./run` directly.

## GitHub Token

A GitHub Personal Access Token is needed to access repositories for analysis (not required to run the app itself): [github.com/settings/tokens](https://github.com/settings/tokens) -> Generate new token (classic) -> select `repo` + `read:user` scopes.

You can enter it in the UI or set `GITHUB_TOKEN` in `backend/.env.local`.

## First Time: Analyze + Sync

After `./run` starts the app, you need to do two things: **analyze** your repository and **sync** the outputs back to it. This is a one-time setup per repo - after that, your AI agent has full architectural awareness.

### 1. Analyze your repository

1. Open `http://localhost:4000`
2. Authenticate with your GitHub token
3. Enter your repository URL and start analysis
4. Wait for the phased analysis to complete (typically 1-3 minutes)
5. Review the generated blueprint, per-folder CLAUDE.md files, and analysis data

### 2. Sync outputs to your repository

This is the critical step - analysis alone doesn't help your AI agent until the outputs are in your repo.

1. From the blueprint view, open the **Delivery** panel
2. Select which outputs to push (CLAUDE.md, per-folder context, AGENTS.md, Cursor rules, MCP configs, CODEBASE_MAP.md, Claude hooks)
3. Choose strategy: **PR** (creates a branch + pull request) or **commit** (direct to default branch)
4. The delivery pipeline merges non-destructively - your existing content is preserved

### 3. Use from your coding agent

That's it - there is no step 3. Once outputs are in your repo, your coding agent picks them up transparently:

- **Claude Code** - works natively. Reads `CLAUDE.md` and `.claude/rules/` automatically on every session. No configuration needed.
- **Other agents** (Cursor, Windsurf, etc.) - connect via MCP. Add the server to your IDE config and the agent gets `where_to_put`, `check_naming`, `how_to_implement` and full blueprint access.

Your agent is now architecturally aware. Every file it creates goes in the right place, follows your naming conventions, and reuses existing patterns - without you having to explain the codebase each session.

### Re-analyze after changes

When re-analyzing a repository that already has a blueprint, the UI offers two options:

- **Incremental** (faster) - Reuses cached AI enrichment for unchanged folders
- **Full** - Re-runs the entire pipeline from scratch

After re-analysis, sync again to push updated outputs.

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
| `where_to_put` | Get correct directory and naming pattern for a component type |
| `check_naming` | Validate a proposed name against project naming conventions |
| `how_to_implement` | Fuzzy search for how a capability is already implemented (libraries, patterns, key files) |
| `list_implementations` | List all documented implementation capabilities with IDs and summaries |
| `how_to_implement_by_id` | Get full implementation details for a specific capability by ID |
| `get_repository_blueprint` | Get the full architecture blueprint JSON |
| `list_repository_sections` | List addressable section IDs in the blueprint |
| `get_repository_section` | Get a specific blueprint section by slug (token-efficient) |
| `list_source_files` | List all source files collected during analysis with sizes |
| `get_file_content` | Read the content of a specific source file |

### Automatic validation (Claude Code)

When you include `claude_hooks` in your delivery outputs, Claude Code gets two hooks that run automatically:

- **Session start** checks if your local CLAUDE.md files are stale compared to the blueprint and warns you
- **After every response** collects changed files, validates them against architecture rules via AI, and regenerates stale CLAUDE.md files on the spot

This keeps your architecture docs current as you code. The blueprint itself is never regenerated by hooks. Only the CLAUDE.md files get re-rendered from the existing blueprint. If your architecture fundamentally changes, re-analyze from the UI.

### Run tests

```bash
cd backend
PYTHONPATH=src python -m pytest tests/unit/ -v
```

---

For detailed technical documentation, architecture internals, and API reference, see **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**.

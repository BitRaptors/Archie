# CLAUDE.md

> Architecture guidance for **BitRaptors/Archie**
> Style: Full-stack monorepo with DDD backend (FastAPI/Python) and dual Next.js frontends (main dashboard + landing page)
> Generated: 2026-03-12T09:17:36.250552+00:00

## Overview

Archie is a code analysis and architecture documentation platform that ingests GitHub or local repositories, runs multi-phase AI analysis via Claude, and produces structured blueprints, intent layers, and agent config files. The backend is Python/FastAPI with domain-driven design, async task processing via ARQ/Redis, and dual Supabase/Postgres persistence. The main frontend is a Next.js dashboard for managing analyses and viewing results; the landing app is a separate Next.js site with 3D visuals. Communication between frontend and backend uses REST + SSE for streaming analysis progress.

## Architecture

**Style:** Strict 4-layer DDD: api → application → domain → infrastructure
**Structure:** layered

Isolates business logic from infra, enables swapping DB backends (Supabase vs Postgres) without touching services

**Runs on:** Google Cloud Platform — Cloud Run for backend API; Supabase for managed PostgreSQL; Redis on Docker (local) or managed Redis (production)
**Compute:** Google Cloud Run — containerized FastAPI backend (backend/Dockerfile), Vercel or self-hosted — Next.js frontend and landing (deployment target not specified in repo)
**CI/CD:** Google Cloud Build — backend/cloudbuild.yaml: build Docker image → push to GCR (gcr.io) → deploy to Cloud Run

## Commands

```bash
# dev_all
python start-dev.py
# backend_only
cd backend && .venv/bin/python src/main.py
# frontend_only
cd frontend && npm run dev
# landing_only
cd landing && npm run dev
# worker
cd backend && PYTHONPATH=src .venv/bin/python -m arq workers.tasks.WorkerSettings
# test_backend
cd backend && .venv/bin/pytest tests/
# lint_backend
cd backend && .venv/bin/ruff check src/
# setup
./setup.sh
```

## Key Rules

Detailed architecture rules are split into topic files under `.claude/rules/`:

- `architecture.md` — Components, file placement, naming conventions
- `patterns.md` — Communication patterns, key decisions
- `recipes.md` — Developer recipes, implementation guidelines
- `pitfalls.md` — Common pitfalls, error mapping
- `dev-rules.md` — Development rules (always/never imperatives)
- `mcp-tools.md` — MCP server tool reference
- `frontend.md` — Frontend rules (when applicable)

## Architecture MCP Server (MANDATORY)

The `architecture-blueprints` MCP server is the single source of truth.
You MUST call `where_to_put` before creating files and `check_naming` before naming components.
See `.claude/rules/mcp-tools.md` for the full tool reference and workflow.

---
*Auto-generated from structured architecture analysis. Place in project root.*
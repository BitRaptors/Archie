# CLAUDE.md

> Architecture guidance for **csacsi/BedtimeApp**
> Style: Monorepo with three platforms: FastAPI backend, React SPA web frontend, React Native/Expo mobile app
> Generated: 2026-03-23T10:08:44.244044+00:00

## Overview

BedtimeApp (Tuck-in-Tales) is a monorepo generating personalized AI bedtime stories for children. The backend is FastAPI/Python using LangGraph to orchestrate multi-step AI workflows across OpenAI, Gemini, and Groq. The web frontend is a React/Vite SPA and the mobile app uses React Native/Expo with file-based routing. Authentication uses Firebase ID tokens verified by the backend, with Supabase as the primary PostgreSQL database. Real-time story and avatar generation progress is streamed to clients via Server-Sent Events.

## Architecture

**Style:** LangGraph StateGraph with async nodes emitting SSE events
**Structure:** layered

Multi-step AI generation (outline → pages → images) requires stateful orchestration with retries, branching, and streaming progress to the client

**Runs on:** Backend: Python/Uvicorn server (Poetry); Web: Browser SPA (Vite build); Mobile: iOS/Android native via Expo
**Compute:** Uvicorn ASGI server (backend), Vite dev/static build (web), Expo EAS or Expo Go (mobile)

## Commands

```bash
# dev_all
npm run dev (root) — starts backend + web frontend concurrently
# dev_backend
cd tuck-in-tales-backend && poetry run uvicorn src.main:app --reload
# dev_web
cd tuck-in-tales-frontend && npm run dev
# dev_mobile
cd tuck-in-tales-mobile && npx expo start
# test_backend
cd tuck-in-tales-backend && poetry run pytest
# build_web
cd tuck-in-tales-frontend && npm run build (tsc -b && vite build)
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
# CLAUDE.md

> Architecture guidance for **BitRaptors/PinLaunch**
> Style: Full-stack Next.js monolith with MVC-like layering
> Generated: 2026-03-23T10:18:13.675867+00:00

## Overview

PinLaunch is a Next.js 15 full-stack web app that generates landing pages from GitHub repos using Claude or Gemini AI. Users collect inspiration pins, select style presets, connect a GitHub repo, and stream AI-generated HTML/CSS files in real-time via SSE. The stack is React 19 frontend, Next.js API routes as backend, SQLite via better-sqlite3 for persistence, and Anthropic/Google AI SDKs for generation. Architecture follows App Router conventions with components in src/components, API handlers in src/app/api, and shared business logic in src/lib.

## Architecture

**Style:** Single Next.js app serving both frontend and backend API routes
**Structure:** layered

Eliminates cross-service complexity; API routes share TypeScript types with frontend; simpler deployment

**Runs on:** Vercel (inferred from Next.js 15 + no Docker/cloud config; local dev also supported)
**Compute:** Vercel Serverless Functions for src/app/api/* routes, Vercel Edge Network for static assets

## Commands

```bash
# dev
npm run dev
# build
npm run build
# start
npm start
# test
npm test (vitest run)
# lint
npm run lint
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
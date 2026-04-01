# Archie V1 (Archived)

This directory contains the original Archie web application — a FastAPI backend + Next.js frontend that analyzed GitHub repositories via a centralized server with RAG, database storage, and MCP server.

**This version is obsolete.** The current Archie is a standalone CLI tool distributed via `npx archie`. See the root README.md for usage.

## What's here

- `backend/` — FastAPI server with phased analysis pipeline, Supabase persistence, MCP server
- `frontend/` — Next.js 14 web UI for repository analysis
- `docker-compose.yml` — PostgreSQL + Redis for local development
- `run` / `start-dev.bat` — Startup scripts

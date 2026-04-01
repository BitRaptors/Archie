---
description: Communication and design patterns, key architectural decisions
alwaysApply: true
---

## Communication Patterns

### Server-Sent Events (SSE) Streaming
- **When:** Long-running AI generation producing real-time progress
- **How:** API route returns ReadableStream with text/event-stream; frontend reads via fetch + TextDecoder line buffering

### Direct REST fetch
- **When:** CRUD operations on pins, settings, presets, GitHub fetch
- **How:** Frontend calls fetch() with async/await; manages loading/error state in useState

### In-process function calls
- **When:** API routes calling service/infrastructure layer
- **How:** TypeScript imports; no HTTP overhead; synchronous for SQLite, async for AI APIs

### Callback prop drilling
- **When:** Child-to-parent result propagation in React tree
- **How:** Parent passes callback as prop; child invokes on completion

### sessionStorage persistence
- **When:** Preserving siteDir/sessionId/provider across page refreshes
- **How:** useEffect writes state to sessionStorage; useState initializer reads it back

## Pattern Selection Guide

| Scenario | Pattern | Rationale |
|----------|---------|-----------|
| Need real-time AI generation progress in UI | SSE Streaming via /api/generate/stream | Unidirectional stream; works on Vercel; no WebSocket server required |
| Simple data fetch (pins, settings, presets) | Direct REST fetch with useState loading/error | No caching library needed; data is small and user-initiated |
| Backend service accessing database or calling AI | In-process function call to src/lib/* modules | Same Node.js process; avoids HTTP overhead; TypeScript type safety |

## Quick Pattern Lookup

- **streaming_ai_response** -> Return ReadableStream from API route with text/event-stream header
- **database_access** -> Import getDb() from src/lib/db.ts; use prepared statements
- **github_metadata** -> Call getRepoContent() from src/lib/github.ts
- **multi_provider_ai** -> Check settings.ai_provider then branch to Claude or Gemini path

## Key Decisions

### SQLite over managed database
**Chosen:** better-sqlite3 with local file at data/builder.db
**Rationale:** Zero-config persistence for single-user local tool; WAL mode handles concurrency

### Dual AI provider support
**Chosen:** Runtime switching between Claude and Gemini via settings table
**Rationale:** Users can use whichever API key they have; Claude for streaming tool-use, Gemini as fallback

### SSE over WebSockets for streaming
**Chosen:** Server-Sent Events via ReadableStream in Next.js API routes
**Rationale:** Unidirectional stream fits generation use case; no WebSocket server needed; works on Vercel

### No external state management library
**Chosen:** React useState/useEffect with sessionStorage for persistence
**Rationale:** App has linear state flow; no cross-component sharing complex enough to warrant Redux/Zustand

### File-system output for generated sites
**Chosen:** Generated files written to process.cwd()/output/ directory
**Rationale:** Simple local preview via /api/preview catchall route; no cloud storage needed
# BitRaptors/PinLaunch — Architecture Map

> PinLaunch is a Next.js 15 full-stack web app that generates landing pages from GitHub repos using Claude or Gemini AI. Users collect inspiration pins, select style presets, connect a GitHub repo, and stream AI-generated HTML/CSS files in real-time via SSE. The stack is React 19 frontend, Next.js API routes as backend, SQLite via better-sqlite3 for persistence, and Anthropic/Google AI SDKs for generation. Architecture follows App Router conventions with components in src/components, API handlers in src/app/api, and shared business logic in src/lib.

**Architecture:** Full-stack Next.js monolith with MVC-like layering | **Platforms:** web-frontend, backend-api | **Generated:** 2026-03-23

## Architecture Diagram

```mermaid
graph TD
    Browser[Browser] --> Home[page.tsx Root]
    Home --> GenPanel[GeneratePanel]
    Home --> PinBoard[PinBoard]
    Home --> Preview[PreviewFrame]
    Home --> Refine[RefinementChat]
    GenPanel --> Terminal[ClaudeTerminal]
    Terminal -->|SSE fetch| StreamAPI[/api/generate/stream]
    Refine -->|POST| RefineAPI[/api/generate/refine]
    PinBoard -->|GET/POST| PinsAPI[/api/pins]
    Preview -->|GET| PreviewAPI[/api/preview/...path]
    StreamAPI --> GenLib[src/lib/generate.ts]
    RefineAPI --> GenLib
    GenLib -->|tool-use| Claude[Anthropic Claude]
    GenLib -->|fallback| Gemini[Google Gemini]
    GenLib -->|writes files| FS[Output Filesystem]
    StreamAPI --> DB[(SQLite db.ts)]
    PinsAPI --> DB
```

## Directory Structure

```
src/
├── app/
│   ├── api/
│   │   ├── generate/
│   │   │   ├── route.ts
│   │   │   ├── stream/route.ts
│   │   │   └── refine/route.ts
│   │   ├── pins/
│   │   │   ├── route.ts
│   │   │   └── [id]/route.ts
│   │   ├── github/route.ts
│   │   ├── settings/route.ts
│   │   ├── presets/route.ts
│   │   ├── preview/[...path]/route.ts
│   │   ├── screenshot/route.ts
│   │   └── health/route.ts
│   ├── layout.tsx
│   ├── page.tsx
│   └── globals.css
├── components/
│   ├── ClaudeTerminal.tsx
│   ├── GeneratePanel.tsx
│   ├── GitHubPanel.tsx
│   ├── PinBoard.tsx
│   ├── PinCard.tsx
│   ├── AddPinModal.tsx
│   ├── PresetsPanel.tsx
│   ├── PreviewFrame.tsx
│   ├── RefinementChat.tsx
│   ├── SettingsPanel.tsx
│   └── Header.tsx
└── lib/
    ├── db.ts
    ├── generate.ts
    ├── github.ts
    ├── prompts.json
    ├── generate.test.ts
    ├── generate.integration.test.ts
    └── stream-parsing.test.ts
```

## Module Guide

### API Route Handlers
**Location:** `src/app/api/`

Handle HTTP requests, parse bodies, call service layer, return responses

| File | Description |
|------|-------------|
| `src/app/api/generate/stream/route.ts` | POST handler returning SSE stream for Claude generation |
| `src/app/api/generate/refine/route.ts` | POST handler for iterative site refinement |
| `src/app/api/pins/route.ts` | GET/POST pins CRUD |
| `src/app/api/settings/route.ts` | GET/PUT settings key-value store |
| `src/app/api/preview/[...path]/route.ts` | Serves generated static files from output dir |

**Depends on:** Application Service Layer, Infrastructure Layer

### Application Service Layer
**Location:** `src/lib/`

Orchestrate AI generation, GitHub fetching, prompt construction

| File | Description |
|------|-------------|
| `src/lib/generate.ts` | Core AI generation orchestration and streaming |
| `src/lib/github.ts` | GitHub API wrapper via Octokit |
| `src/lib/prompts.json` | Prompt templates for AI generation |

**Depends on:** Infrastructure Layer, External AI APIs, GitHub API

- **streamClaudeGeneration**: Streams Claude tool-use generation as SSE events
- **getRepoContent**: Fetches GitHub repo metadata via Octokit

### Infrastructure Layer
**Location:** `src/lib/db.ts`

SQLite singleton, schema init, preset seeding

| File | Description |
|------|-------------|
| `src/lib/db.ts` | DB singleton with schema creation and preset seeding |

**Depends on:** better-sqlite3

- **getDb**: Returns initialized WAL-mode SQLite instance

### Feature Components
**Location:** `src/components/`

Stateful feature containers managing distinct UI domains

| File | Description |
|------|-------------|
| `src/components/GeneratePanel.tsx` | Prompt input, triggers generation, hosts ClaudeTerminal |
| `src/components/ClaudeTerminal.tsx` | Real-time SSE stream renderer with tool-use display |
| `src/components/RefinementChat.tsx` | Chat UI for iterative post-generation refinement |
| `src/components/GitHubPanel.tsx` | GitHub repo URL input and metadata display |
| `src/components/PinBoard.tsx` | Masonry grid of inspiration pins |
| `src/components/SettingsPanel.tsx` | API key and provider configuration modal |

**Depends on:** API Route Handlers via fetch

### Pages/Views Layer
**Location:** `src/app/`

Root layout, metadata, global styles, main page composition

| File | Description |
|------|-------------|
| `src/app/page.tsx` | Root page composing all feature panels, manages session state |
| `src/app/layout.tsx` | Root layout with metadata, Inter font, Header |

**Depends on:** Feature Components

## Common Tasks

### Add a new API endpoint with database access
**Files:** `src/app/api/[feature]/route.ts`, `src/lib/db.ts`

1. 1. Create src/app/api/[feature]/route.ts with export async function GET/POST
2. 2. Import getDb from '@/lib/db' and run prepared statements
3. 3. Return Response.json(result) or error with appropriate status code

### Add a new React feature panel
**Files:** `src/components/[Name]Panel.tsx`, `src/app/page.tsx`

1. 1. Create src/components/[Name]Panel.tsx with 'use client' directive and useState hooks
2. 2. Fetch data via fetch('/api/[feature]') in useEffect or event handlers
3. 3. Import and render the component in src/app/page.tsx alongside existing panels

### Add a new SSE streaming endpoint
**Files:** `src/app/api/[feature]/stream/route.ts`, `src/lib/generate.ts`

1. 1. Create a ReadableStream factory function in src/lib/generate.ts emitting JSON lines
2. 2. Create route.ts returning new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } })
3. 3. Consume in frontend with fetch + ReadableStream reader + TextDecoder line buffer pattern matching ClaudeTerminal.tsx

### Add a new AI generation preset
**Files:** `src/lib/db.ts`, `src/app/api/presets/route.ts`, `src/components/PresetsPanel.tsx`

1. 1. Add INSERT into seedPresets() in src/lib/db.ts (or run SQL manually on existing db)
2. 2. Verify /api/presets GET returns new preset
3. 3. Confirm PresetsPanel.tsx renders it (no code change needed if using generic list render)

## Gotchas

### SQLite on Vercel
data/builder.db is written to process.cwd() which is ephemeral on Vercel; all pins/settings/presets reset on redeploy

*Recommendation:* Run locally or mount a persistent volume; consider migrating to Turso/LibSQL for production

### SSE line buffering
TCP fragmentation can split a JSON event across multiple read() chunks; missing the buffer = lines.pop() pattern will cause JSON.parse errors

*Recommendation:* Always use the split('\n') + pop() remainder buffer pattern as in ClaudeTerminal.tsx; validated in src/lib/stream-parsing.test.ts

### better-sqlite3 in Next.js API routes
better-sqlite3 is synchronous and native; it cannot be used in Edge Runtime or client components; will crash if imported in 'use client' files

*Recommendation:* Never import src/lib/db.ts in components; always access via fetch to /api/* routes

### Preset seeding
seedPresets() only runs once on first DB connection (checked via SELECT COUNT); manually deleted presets will not be re-seeded without dropping the table

*Recommendation:* To reset presets, DELETE FROM presets then restart the server to trigger re-seed

### Dual AI provider stream format mismatch
Claude uses tool_use event types; Gemini uses blocking response; ClaudeTerminal SSE parser only handles Claude event schema

*Recommendation:* Refine endpoint handles Gemini separately; do not route Gemini through the ClaudeTerminal component

## Technology Stack

| Category | Name | Version | Purpose |
|----------|------|---------|---------|
| Framework | Next.js | ^15.2.0 | Full-stack framework: API routes + React SSR/CSR |
| UI | React | ^19.0.0 | Component-based frontend rendering |
| Language | TypeScript | ^5.0.0 | Static typing across all source files |
| Styling | Tailwind CSS | ^4.0.0 | Utility-first CSS with CSS variable theming |
| Database | better-sqlite3 | ^12.8.0 | Synchronous SQLite for pins, settings, presets |
| AI | @anthropic-ai/claude-code | ^2.1.76 | Claude streaming code generation with tool-use |
| AI | @google/generative-ai | ^0.24.1 | Gemini API for generation and refinement fallback |
| Integration | @octokit/rest | ^22.0.1 | GitHub API client for repo metadata extraction |
| Browser Automation | puppeteer | ^24.39.1 | Headless browser for screenshot capture |
| Testing | vitest | ^4.1.0 | Unit and integration test runner |

## Run Commands

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

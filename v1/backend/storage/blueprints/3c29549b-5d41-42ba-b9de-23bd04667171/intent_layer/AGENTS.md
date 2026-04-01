# AGENTS.md

> Agent guidance for **BitRaptors/PinLaunch**
> Generated: 2026-03-23T10:18:13.675880+00:00

PinLaunch is a Next.js 15 full-stack web app that generates landing pages from GitHub repos using Claude or Gemini AI. Users collect inspiration pins, select style presets, connect a GitHub repo, and stream AI-generated HTML/CSS files in real-time via SSE. The stack is React 19 frontend, Next.js API routes as backend, SQLite via better-sqlite3 for persistence, and Anthropic/Google AI SDKs for generation. Architecture follows App Router conventions with components in src/components, API handlers in src/app/api, and shared business logic in src/lib.

---

## Tech Stack

- **AI:** @anthropic-ai/claude-code ^2.1.76, @google/generative-ai ^0.24.1
- **Browser Automation:** puppeteer ^24.39.1
- **Database:** better-sqlite3 ^12.8.0
- **Framework:** Next.js ^15.2.0
- **Integration:** @octokit/rest ^22.0.1
- **Language:** TypeScript ^5.0.0
- **Styling:** Tailwind CSS ^4.0.0
- **Testing:** vitest ^4.1.0
- **UI:** React ^19.0.0

## Deployment

**Runs on:** Vercel (inferred from Next.js 15 + no Docker/cloud config; local dev also supported)
**Compute:** Vercel Serverless Functions for src/app/api/* routes, Vercel Edge Network for static assets
**Container:** None + None
**Distribution:**
- Web via Vercel deployment
- Local via npm run dev / start.sh

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

## Project Structure

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

## Code Style

- **API route files:** route.ts (fixed filename) (e.g. `src/app/api/health/route.ts`, `src/app/api/generate/stream/route.ts`)
- **React components:** PascalCase with feature suffix (e.g. `GeneratePanel.tsx`, `RefinementChat.tsx`, `PinBoard.tsx`)
- **Library functions:** camelCase verb+noun (e.g. `streamClaudeGeneration`, `getRepoContent`, `getDb`)
- **Test files:** [module].test.ts or [module].integration.test.ts (e.g. `generate.test.ts`, `generate.integration.test.ts`, `stream-parsing.test.ts`)

### API Route Handler: Standard Next.js API route with DB access

File: `src/app/api/[feature]/route.ts`

```
import { getDb } from '@/lib/db';
export async function GET() {
  const db = getDb(); return Response.json(db.prepare('SELECT * FROM pins').all()); }
```

### Feature Component: Client component with fetch and loading state

File: `src/components/[Name]Panel.tsx`

```
'use client';
import { useState, useEffect } from 'react';
export default function MyPanel() {
  const [data, setData] = useState(null); ... }
```

### SSE Streaming Route: API route returning Server-Sent Events

File: `src/app/api/[feature]/stream/route.ts`

```
export async function POST(req: Request) {
  const stream = createMyStream();
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } }); }
```

## Development Rules

### Code Style

- Always export HTTP verb functions (GET, POST, PUT, DELETE) from route.ts files; never use default exports for API routes *(source: `src/app/api/pins/route.ts, src/app/api/settings/route.ts — named export pattern`)*
- Always add 'use client' directive to components using useState/useEffect; omit for server-only layout/page files *(source: `src/components/GeneratePanel.tsx, ClaudeTerminal.tsx — all interactive components are client components`)*

### Dependency Management

- Always use npm; no yarn or pnpm — project uses package-lock.json exclusively *(source: `package-lock.json lockfileVersion 3 present; no yarn.lock or pnpm-lock.yaml`)*

### Environment

- Always initialize SQLite with WAL pragma via getDb() singleton; never create direct Database instances in route files *(source: `src/lib/db.ts — db.pragma('journal_mode = WAL') + singleton pattern`)*

### Testing

- Always mirror ClaudeTerminal.tsx SSE event handler logic in src/lib/stream-parsing.test.ts when adding new event types *(source: `src/lib/stream-parsing.test.ts — duplicates handleEvent, handleToolUse, TOOL_ICONS from ClaudeTerminal`)*
- Always run tests with vitest run (not vitest watch) for non-interactive CI execution *(source: `package.json — 'test': 'vitest run'`)*

## Boundaries

### Always

- Run tests before committing
- Use `where_to_put` MCP tool before creating files
- Use `check_naming` MCP tool before naming components
- Follow file placement rules (see `.claude/rules/architecture.md`)

### Ask First

- Database schema changes
- Adding new dependencies
- Modifying CI/CD configuration
- Changes to deployment configuration

### Never

- Commit secrets or API keys
- Edit vendor/node_modules directories
- Remove failing tests without authorization
- Never import src/lib/db.ts in components; always access via fetch to /api/* routes

## Testing

- **vitest ^4.1.0** — Unit and integration test runner

```bash
# test
npm test (vitest run)
# lint
npm run lint
```

## Common Workflows

### Add a new API endpoint with database access
Files: `src/app/api/[feature]/route.ts`, `src/lib/db.ts`
1. Create src/app/api/[feature]/route.ts with export async function GET/POST
2. Import getDb from '@/lib/db' and run prepared statements
3. Return Response.json(result) or error with appropriate status code

### Add a new React feature panel
Files: `src/components/[Name]Panel.tsx`, `src/app/page.tsx`
1. Create src/components/[Name]Panel.tsx with 'use client' directive and useState hooks
2. Fetch data via fetch('/api/[feature]') in useEffect or event handlers
3. Import and render the component in src/app/page.tsx alongside existing panels

### Add a new SSE streaming endpoint
Files: `src/app/api/[feature]/stream/route.ts`, `src/lib/generate.ts`
1. Create a ReadableStream factory function in src/lib/generate.ts emitting JSON lines
2. Create route.ts returning new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } })
3. Consume in frontend with fetch + ReadableStream reader + TextDecoder line buffer pattern matching ClaudeTerminal.tsx

### Add a new AI generation preset
Files: `src/lib/db.ts`, `src/app/api/presets/route.ts`, `src/components/PresetsPanel.tsx`
1. Add INSERT into seedPresets() in src/lib/db.ts (or run SQL manually on existing db)
2. Verify /api/presets GET returns new preset
3. Confirm PresetsPanel.tsx renders it (no code change needed if using generic list render)

## Pitfalls & Gotchas

- **SQLite on Vercel:** data/builder.db is written to process.cwd() which is ephemeral on Vercel; all pins/settings/presets reset on redeploy
  - *Run locally or mount a persistent volume; consider migrating to Turso/LibSQL for production*
- **SSE line buffering:** TCP fragmentation can split a JSON event across multiple read() chunks; missing the buffer = lines.pop() pattern will cause JSON.parse errors
  - *Always use the split('\n') + pop() remainder buffer pattern as in ClaudeTerminal.tsx; validated in src/lib/stream-parsing.test.ts*
- **better-sqlite3 in Next.js API routes:** better-sqlite3 is synchronous and native; it cannot be used in Edge Runtime or client components; will crash if imported in 'use client' files
  - *Never import src/lib/db.ts in components; always access via fetch to /api/* routes*
- **Preset seeding:** seedPresets() only runs once on first DB connection (checked via SELECT COUNT); manually deleted presets will not be re-seeded without dropping the table
  - *To reset presets, DELETE FROM presets then restart the server to trigger re-seed*
- **Dual AI provider stream format mismatch:** Claude uses tool_use event types; Gemini uses blocking response; ClaudeTerminal SSE parser only handles Claude event schema
  - *Refine endpoint handles Gemini separately; do not route Gemini through the ClaudeTerminal component*

## Architecture MCP Server

The `architecture-blueprints` MCP server is the single source of truth.
Call its tools for every architecture decision.

| Tool | When to Use |
|------|------------|
| `where_to_put` | Before creating or moving any file |
| `check_naming` | Before naming any new component |
| `list_implementations` | Discovering available implementation patterns |
| `how_to_implement_by_id` | Getting full details for a specific capability |
| `how_to_implement` | Fuzzy search when exact capability name unknown |
| `get_file_content` | Reading source files referenced in guidelines |

## File Placement

- **new_api_endpoint** → `src/app/api/[feature]/route.ts`
- **new_react_component** → `src/components/[Name].tsx`
- **shared_business_logic** → `src/lib/[module].ts`
- **database_schema_change** → `src/lib/db.ts getDb() initialization block`
- **prompt_templates** → `src/lib/prompts.json`
- **unit_tests** → `src/lib/[module].test.ts`

---
*Auto-generated from structured architecture analysis.*
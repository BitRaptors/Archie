---
description: Developer recipes and implementation guidelines
alwaysApply: true
---

## Developer Recipes

### Add a new API endpoint with database access
Files: `src/app/api/[feature]/route.ts`, `src/lib/db.ts`
1. 1. Create src/app/api/[feature]/route.ts with export async function GET/POST
2. 2. Import getDb from '@/lib/db' and run prepared statements
3. 3. Return Response.json(result) or error with appropriate status code

### Add a new React feature panel
Files: `src/components/[Name]Panel.tsx`, `src/app/page.tsx`
1. 1. Create src/components/[Name]Panel.tsx with 'use client' directive and useState hooks
2. 2. Fetch data via fetch('/api/[feature]') in useEffect or event handlers
3. 3. Import and render the component in src/app/page.tsx alongside existing panels

### Add a new SSE streaming endpoint
Files: `src/app/api/[feature]/stream/route.ts`, `src/lib/generate.ts`
1. 1. Create a ReadableStream factory function in src/lib/generate.ts emitting JSON lines
2. 2. Create route.ts returning new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } })
3. 3. Consume in frontend with fetch + ReadableStream reader + TextDecoder line buffer pattern matching ClaudeTerminal.tsx

### Add a new AI generation preset
Files: `src/lib/db.ts`, `src/app/api/presets/route.ts`, `src/components/PresetsPanel.tsx`
1. 1. Add INSERT into seedPresets() in src/lib/db.ts (or run SQL manually on existing db)
2. 2. Verify /api/presets GET returns new preset
3. 3. Confirm PresetsPanel.tsx renders it (no code change needed if using generic list render)

## Implementation Guidelines

### AI Streaming Generation via SSE [networking]
Libraries: `@anthropic-ai/claude-code ^2.1.76`
Pattern: streamClaudeGeneration() in src/lib/generate.ts creates a ReadableStream emitting JSON-formatted SSE events for Claude tool-use calls. Frontend ClaudeTerminal reads via fetch + TextDecoder line buffering, dispatching each event to UI state handlers.
Key files: `src/lib/generate.ts`, `src/app/api/generate/stream/route.ts`, `src/components/ClaudeTerminal.tsx`
Example: `const res = await fetch('/api/generate/stream', { method: 'POST', body: JSON.stringify({ userPrompt }) });`
- Keep SSE event payloads under 64KB to avoid TCP fragmentation issues
- Maintain sync between ClaudeTerminal.tsx handleEvent() and src/lib/stream-parsing.test.ts when adding event types
- Always set Cache-Control: no-cache and Connection: keep-alive headers on SSE responses

### SQLite Persistence via Repository Pattern [persistence]
Libraries: `better-sqlite3 ^12.8.0`
Pattern: getDb() in src/lib/db.ts returns a WAL-mode SQLite singleton. Auto-creates schema and seeds presets on first connection. All API routes use this single accessor.
Key files: `src/lib/db.ts`, `src/app/api/pins/route.ts`, `src/app/api/settings/route.ts`
Example: `const db = getDb(); const pins = db.prepare('SELECT * FROM pins ORDER BY created_at DESC').all();`
- Only call getDb() in API routes (Node.js runtime); never in client components
- WAL files (db-wal, db-shm) must be on same filesystem as main db file
- data/ directory auto-created via mkdirSync; ensure process.cwd() is writable

### GitHub Repo Metadata Extraction [networking]
Libraries: `@octokit/rest ^22.0.1`
Pattern: getRepoContent() in src/lib/github.ts uses Octokit to fetch README, package.json, file tree, and repo metadata via parallel Promise.all calls. Results feed into AI generation prompt.
Key files: `src/lib/github.ts`, `src/app/api/github/route.ts`
Example: `const content = await getRepoContent(repoUrl, githubToken);`
- Public API rate limit is 60 req/hr; provide github_token from settings for 5000 req/hr
- README and package.json returned as base64; decode before use
- Recursive tree listing includes all files; filter to avoid prompt size bloat

### Dual AI Provider Runtime Switching [state_management]
Libraries: `@anthropic-ai/claude-code ^2.1.76`, `@google/generative-ai ^0.24.1`
Pattern: settings.ai_provider value ('claude' or 'gemini') read from SQLite at request time in refine and generate routes. Claude path uses streaming tool-use; Gemini path uses blocking generateContent call.
Key files: `src/app/api/generate/refine/route.ts`, `src/app/api/generate/route.ts`, `src/lib/generate.ts`
Example: `const provider = settings.ai_provider || 'gemini'; if (provider === 'claude') { ... streamClaudeRefinement() }`
- Test both provider paths independently; event schemas differ significantly
- ClaudeTerminal component only handles Claude SSE event types
- Provider selection persisted to sessionStorage via page.tsx for UI consistency

### Generated Site File Preview [networking]
Libraries: `Node.js fs`
Pattern: Generated HTML/CSS/JS files written to process.cwd()/output/{dirName}/ by generate.ts. The /api/preview/[...path] catchall route reads files from this directory and returns them with correct MIME types and directory traversal protection.
Key files: `src/app/api/preview/[...path]/route.ts`, `src/lib/generate.ts`
Example: `<iframe src={`/api/preview/${siteDir}/index.html`} /> in PreviewFrame.tsx`
- Directory traversal protection must check resolved path stays within output/ directory
- MIME types inferred from file extension; ensure .css and .js extensions used in generation
- PreviewFrame uses refreshTrigger prop to force iframe reload after refinement
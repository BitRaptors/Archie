---
description: Common pitfalls and error mapping
alwaysApply: true
---

## Pitfalls

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

## Error Mapping

| Error | Status Code |
|-------|------------|
| `Missing AI API key` | 400 |
| `GitHub repo not found` | 404 |
| `SQLite SQLITE_CANTOPEN` | 500 |
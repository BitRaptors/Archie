# src/
> Root source directory: orchestrates app layout, UI components, and generation utilities for AI-powered landing page builder.

## Patterns

- Session state persisted to sessionStorage with provider fallback chain: saved preference → 'gemini' default
- Dual-mode UI: setup mode (pinboard + panels) when !siteDir, preview mode (sidebar + iframe) when siteDir populated
- CSS custom properties (--accent, --surface, --text, --border, --radius) centralized for theme consistency across components
- Prompt composition via conditional section assembly from prompts.json — only include blocks matching input signals
- GitHub data pipeline: parseReadmeSections() + extractDependencies() + inferProjectType() → structured prompt context
- Modal/dialog pattern: fixed inset-0 backdrop with stopPropagation on inner div prevents accidental closes

## Navigation

**Parent:** [`root/`](../CLAUDE.md)
**Children:** [`app/`](app/CLAUDE.md) | [`components/`](components/CLAUDE.md) | [`lib/`](lib/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `app/` | Root layout, home page, session persistence, provider selection | Update sessionStorage keys or provider fallback chain here first |
| `components/` | Reusable UI: modals, terminal streaming, preview frames, settings | Use CSS var(--*) tokens; test modal stopPropagation on inner divs |
| `lib/` | Prompts, repo parsing, API integration, database setup | Modify prompts.json sections; validate input decomposition pipeline logic |

## Add new AI provider or modify session persistence behavior

1. Update provider fallback chain in app/sessionStorage logic
2. Add provider-specific API integration in lib/ if needed
3. Test persistence across page reloads and provider switching

## Don't

- Don't hardcode provider names — use fallback chain from sessionStorage
- Don't duplicate theme values — use CSS custom properties instead of inline colors
- Don't nest modals without testing stopPropagation — backdrop clicks leak to parent handlers

## Testing

- Session state: reload page, verify sessionStorage persists provider choice and siteDir
- UI modes: toggle siteDir in console, confirm layout switches between setup and preview

## Why It's Built This Way

- sessionStorage over localStorage: session-scoped data survives tab navigation but not browser restart
- Prompt decomposition in lib/: reduces GitHub repo noise early, avoids prompt bloat in API calls

## What Goes Here

- new_api_endpoint → `src/app/api/[feature]/route.ts`
- new_react_component → `src/components/[Name].tsx`
- shared_business_logic → `src/lib/[module].ts`
- database_schema_change → `src/lib/db.ts getDb() initialization block`
- prompt_templates → `src/lib/prompts.json`
- unit_tests → `src/lib/[module].test.ts`

## Dependencies

**Depends on:** `Application Service Layer`, `Infrastructure Layer`
**Exposes to:** `Frontend Components`

## Templates

### API Route Handler
**Path:** `src/app/api/[feature]/route.ts`
```
import { getDb } from '@/lib/db';
export async function GET() {
  const db = getDb(); return Response.json(db.prepare('SELECT * FROM pins').all()); }
```

### Feature Component
**Path:** `src/components/[Name]Panel.tsx`
```
'use client';
import { useState, useEffect } from 'react';
export default function MyPanel() {
  const [data, setData] = useState(null); ... }
```

### SSE Streaming Route
**Path:** `src/app/api/[feature]/stream/route.ts`
```
export async function POST(req: Request) {
  const stream = createMyStream();
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } }); }
```

## Subfolders

- [`app/`](app/CLAUDE.md) — Root layout, metadata, global styles, main page composition
- [`components/`](components/CLAUDE.md) — Stateful feature containers managing distinct UI domains
- [`lib/`](lib/CLAUDE.md) — Orchestrate AI generation, GitHub fetching, prompt construction

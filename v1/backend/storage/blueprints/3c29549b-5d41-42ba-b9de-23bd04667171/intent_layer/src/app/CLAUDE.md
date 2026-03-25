# app/
> Root app layout and home page: dual-mode UI (setup → preview), session persistence, AI provider selection fallback.

## Patterns

- Session state persisted to sessionStorage with provider default chain: saved → 'gemini'
- Dual layout: setup mode (pinboard + right panels) when !siteDir, preview mode (left sidebar + iframe) when siteDir set
- Child panels communicate via callbacks (onSiteReady, onFileChange, onMessage) — no prop drilling
- refreshTrigger number incremented to force PreviewFrame remount/reload without state mutation
- Provider passed downstream to RefinementChat; GeneratePanel controls handleSiteReady payload

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md)
**Children:** [`api/`](api/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `page.tsx` | Home page: setup/preview UI orchestration | Add state here first. Pass callbacks to child panels. siteDir controls layout branch. |
| `layout.tsx` | Root layout wrapping Header + main | Metadata, fonts, global structure only. Style root element, not children. |
| `globals.css` | CSS variables + Tailwind base styles | Update --accent, --bg only. Custom scrollbar, focus rings, input states here. |

## Add new panel to setup/preview mode

1. Add state + callback to Home (if panel needs to update siteDir/provider)
2. Render in setup branch (grid right column) and preview branch (left sidebar)
3. Pass siteDir, sessionId, provider, callbacks as immutable props

## Don't

- Don't initialize state directly from sessionStorage in useState — use callback function to defer until client-side
- Don't pass provider as prop chain — set at root page level, read from session state
- Don't mutate refreshTrigger; increment with setter to guarantee PreviewFrame detects change

## Why It's Built This Way

- sessionStorage over localStorage: session-scoped so user can run multiple experiments in parallel tabs without collision
- refreshTrigger as number not boolean: allows multiple refreshes in sequence (n+1 always different from n)

## What Goes Here

- **App Router pages and layouts only in src/app** — `page.tsx or layout.tsx`
- new_api_endpoint → `src/app/api/[feature]/route.ts`

## Dependencies

**Depends on:** `Feature Components`
**Exposes to:** `Browser`

## Templates

### API Route Handler
**Path:** `src/app/api/[feature]/route.ts`
```
import { getDb } from '@/lib/db';
export async function GET() {
  const db = getDb(); return Response.json(db.prepare('SELECT * FROM pins').all()); }
```

### SSE Streaming Route
**Path:** `src/app/api/[feature]/stream/route.ts`
```
export async function POST(req: Request) {
  const stream = createMyStream();
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } }); }
```

## Subfolders

- [`api/`](api/CLAUDE.md) — Handle HTTP requests, parse bodies, call service layer, return responses

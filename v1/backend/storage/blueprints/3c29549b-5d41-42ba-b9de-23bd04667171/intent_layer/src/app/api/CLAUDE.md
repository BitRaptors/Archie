# api/
> API route handlers for pin CRUD and AI-driven site generation with provider selection fallback.

## Patterns

- Provider selection: explicit fallback chain (param → settings → 'gemini' default) executes BEFORE API calls
- Database queries run once at route entry, results passed immutably downstream to generators
- POST endpoints return inserted record immediately; GET endpoints order DESC by created_at
- SQL injection prevention: parameterized queries via db.prepare().run(?, ?, ?) — no string concatenation
- File output from generators written synchronously; errors propagate as HTTP responses

## Navigation

**Parent:** [`app/`](../CLAUDE.md)
**Children:** [`generate/`](generate/CLAUDE.md) | [`pins/`](pins/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `generate/route.ts` | POST endpoint orchestrating AI site generation from pins/presets | Resolve provider before database queries. Pass immutable input object to generator. |
| `pins/route.ts` | REST endpoints: GET all pins, POST single pin | Use db.prepare() with ? placeholders. Return full inserted record on POST. |

## Add new PIN CRUD endpoint or modify generation logic

1. Query database once at route entry with db.prepare() and parameterized placeholders
2. Pass immutable result object (not connection) to downstream handlers
3. Return full record on mutation; chain .order DESC for read-all endpoints

## Don't

- Don't concatenate provider name or user input into queries — use parameterized db.prepare().run(?, ?, ?)
- Don't pass mutable state or database connections downstream — serialize results at route entry
- Don't defer provider selection logic — resolve before any API call or database query

## Testing

- POST /api/pins: verify inserted record returned; GET /api/pins: verify DESC ordering by created_at
- POST /api/generate: test provider fallback chain (param missing → settings → 'gemini' default)

## Debugging

- Provider mismatch: check fallback chain execution order — param evaluated before settings default
- SQL errors: confirm parameterized query syntax db.prepare().run(?, ?, ?) — never interpolate user input

## Why It's Built This Way

- Provider fallback evaluated at route entry, not inside generator — prevents mid-execution swaps and simplifies error handling
- Immutable database results passed downstream — avoids connection leaks and concurrent query conflicts

## What Goes Here

- **App Router pages and layouts only in src/app** — `page.tsx or layout.tsx`
- new_api_endpoint → `src/app/api/[feature]/route.ts`

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

### SSE Streaming Route
**Path:** `src/app/api/[feature]/stream/route.ts`
```
export async function POST(req: Request) {
  const stream = createMyStream();
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } }); }
```

## Subfolders

- [`generate/`](generate/CLAUDE.md) — Handle HTTP requests, parse bodies, call service layer, return responses
- [`pins/`](pins/CLAUDE.md) — Handle HTTP requests, parse bodies, call service layer, return responses

# pins/
> REST API endpoints for pin CRUD operations; persists to SQLite with parameterized queries.

## Patterns

- GET returns all pins ordered DESC by created_at; POST creates single pin and returns inserted record
- Parameter binding via db.prepare().run(?, ?, ?) prevents SQL injection automatically
- POST validates required fields upfront (url), accepts optional fields (title, description) as null
- lastInsertRowid used to fetch fresh record after INSERT — ensures response matches DB state
- Explicit HTTP status codes: 400 for validation failure, 201 for successful creation, 200 implicit for GET

## Navigation

**Parent:** [`api/`](../CLAUDE.md)
**Peers:** [`generate/`](../generate/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `route.ts` | NextJS API route handler for /api/pins | Add validation before db.prepare(); maintain parameterized queries always |

## Key Imports

- `import { getDb } from "@/lib/db"`
- `import { NextRequest, NextResponse } from "next/server"`

## Add new pin field (e.g., tags, category)

1. Add column to schema and migration
2. Add field to INSERT statement and parameter binding: (?, ?, ?, ?)
3. Destructure new field from req.json()
4. Pass to .run() in correct order

## Don't

- Don't concatenate user input into SQL strings — use ? placeholders in prepare() statements
- Don't return unvalidated POST requests directly — fetch fresh record post-INSERT to guarantee DB consistency
- Don't omit status codes — explicit 201, 400, etc. signal intent to clients

## Testing

- GET: curl http://localhost:3000/api/pins — verify DESC ordering and all fields present
- POST: curl -X POST -H 'Content-Type: application/json' -d '{"url":"..."}' — verify 201 + full record echo; test missing url field returns 400

## Debugging

- lastInsertRowid returns undefined/null if db connection lost or INSERT fails silently — log result object before .get()
- SQL errors from malformed queries show in server console, not client response — check db.prepare() syntax

## Why It's Built This Way

- Fetch-after-INSERT pattern ensures response includes DB-generated fields (id, timestamps) without assuming defaults
- null defaults for optional fields (title, description) match schema — avoids empty string ambiguity

## What Goes Here

- **App Router pages and layouts only in src/app** — `page.tsx or layout.tsx`

## Dependencies

**Depends on:** `Application Service Layer`, `Infrastructure Layer`
**Exposes to:** `Frontend Components`

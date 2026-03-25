# tuck-in-tales-frontend/
> React + Vite frontend for TuckInTales; Firebase auth + Supabase DB/storage; backend-driven data ops.

## Patterns

- Environment variables split: Firebase config (auth) + Supabase URL/key (storage URLs only) + backend API base URL — backend holds service key
- All Supabase table IDs are UUIDs, inserted via backend service role — frontend never writes directly to DB
- Storage buckets: photos (private, backend signed URLs), avatars/story-images (public read) — bucket creation + RLS policies via SQL, not app code
- Dual AuthProvider wrapping (main.tsx + App.tsx) redundant but harmless — inner context takes precedence
- Protected routes enforce ProtectedRoute + AppLayout nesting — single auth + chrome control point
- Restore SQL files in _restore/ are unrelated to TuckInTales user data — migration.sql is source of truth for schema

## Navigation

**Parent:** [`root/`](../CLAUDE.md)
**Peers:** [`tuck-in-tales-backend/`](../tuck-in-tales-backend/CLAUDE.md) | [`tuck-in-tales-mobile/`](../tuck-in-tales-mobile/CLAUDE.md)
**Children:** [`_restore/`](_restore/CLAUDE.md) | [`src/`](src/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `.env` | Firebase + Supabase credentials + backend API URL | Update VITE_API_BASE_URL when backend host changes; never commit secrets |
| `supabase-migration.sql` | Creates all DB tables, indexes, RLS, match_memories RPC | Run in Supabase SQL Editor after project creation; idempotent (no IF EXISTS guards) |
| `RESTORE-GUIDE.md` | New Supabase project setup + storage bucket + RLS policy creation | Follow Step 1–6 when Supabase is paused; update hardcoded project ref in supabaseUtils.ts |
| `components.json` | shadcn/ui config: component aliases + Tailwind CSS variables | Run `npx shadcn-ui@latest add [component]` to install; aliases auto-resolve in imports |

## Connect new backend/Supabase instance

1. Update .env: VITE_API_BASE_URL, VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY
2. Run supabase-migration.sql in new project's SQL Editor
3. Create 3 storage buckets (photos private, avatars/story-images public) via RESTORE-GUIDE.md Step 3
4. Test: create account → family → character → upload photo & generate avatar

## Don't

- Don't write to Supabase DB from frontend — backend service role is the only writer; frontend calls backend API
- Don't hardcode Supabase project ref in avatar URLs — extract from VITE_SUPABASE_URL constant or env var
- Don't commit .env with real secrets — .gitignore already set; use .env.local for local overrides

## Testing

- Frontend: create account (Firebase), add family, upload character photo, generate story — confirms auth + backend + storage chain
- Storage: verify files appear in correct buckets; avatars/story-images are public-readable, photos are not

## Debugging

- Auth fails: check VITE_FIREBASE_* env vars; check AuthProvider wrapping in main.tsx and App.tsx (inner wins)
- Storage 404: verify bucket name in backend URL construction; check bucket is public (avatars/story-images) or backend has signed URL

## Why It's Built This Way

- Vite chosen for HMR speed + tree-shake; SWC faster than Babel on large codebases
- Dual AuthProvider: harmless redundancy; removes if inner provider will always be used, but no breaking cost to leave

## What Goes Here

- new_web_page → `tuck-in-tales-frontend/src/pages/{Domain}Page.tsx + route in tuck-in-tales-frontend/src/App.tsx`
- new_web_hook → `tuck-in-tales-frontend/src/hooks/use{Domain}.ts`
- shared_ui_component → `tuck-in-tales-frontend/src/components/ui/{component}.tsx (shadcn pattern)`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

## Templates

### web_page
**Path:** `tuck-in-tales-frontend/src/pages/{Domain}Page.tsx`
```
export default function {Domain}Page() {
  const { user } = useAuth();
  return <div>...</div>;
}
```

## Subfolders

- [`_restore/`](_restore/CLAUDE.md) — 
- [`src/`](src/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features

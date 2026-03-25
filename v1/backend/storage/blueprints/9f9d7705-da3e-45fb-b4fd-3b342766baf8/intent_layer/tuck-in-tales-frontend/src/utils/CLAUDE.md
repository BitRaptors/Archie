# utils/
> Auth token retrieval and Supabase storage URL generation for client-side asset access.

## Patterns

- Firebase token fetching forces refresh (true param) to guarantee fresh credentials.
- Supabase project ref extracted from URL hostname via split('.')[0] — brittle if domain structure changes.
- Three separate public URL builders (avatars, photos, memory-photos) all follow identical validation + construction logic.
- Guard clauses check for null/empty/invalid paths before URL construction; return null on validation failure.
- Environment variables required at module load time; missing values logged as warning, not error.
- Firebase auth.currentUser null-checked synchronously before async getIdToken() call.

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`hooks/`](../hooks/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `firebase.ts` | Manage Firebase authentication token lifecycle. | Add force refresh param, return null safely, catch errors explicitly. |
| `supabaseUtils.ts` | Construct public Supabase storage URLs; manage client config. | Replicate validation pattern for new buckets; extract SUPABASE_PROJECT_REF at top. |

## Add a new Supabase storage bucket public URL getter

1. Define BUCKET_NAME constant at module top (e.g., const DOCUMENTS_BUCKET = 'documents').
2. Copy getPublicPhotoUrl pattern: validate path, check SUPABASE_PROJECT_REF, return formatted URL or null.
3. Export new function with JSDoc describing bucket/path convention (e.g., 'family_id/doc_id/file.pdf').

## Don't

- Don't hard-code bucket names inline — extract as CONST at module level for reusability.
- Don't skip optional chaining on path params — always validate string type + trim() before URL use.
- Don't error on missing env vars at startup — warn + allow creation with empty strings (deferred failure).

## Debugging

- Missing Supabase URL: check .env file loaded and VITE_SUPABASE_URL key matches import.meta.env usage.
- Public URL returns null: first validate path is string, not null/undefined/empty, then verify SUPABASE_PROJECT_REF hostname parsing succeeded.

## Why It's Built This Way

- Firebase token forces refresh (true param) to prevent stale tokens in long-lived sessions; trade-off: extra API call per use.
- Separate URL builders per bucket (avatars vs photos vs memory-photos) allow bucket-specific logic later without cascading refactors.

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

# src/
> Root source folder containing platform-agnostic config, hooks, and TypeScript type definitions for mobile/web app.

## Patterns

- Platform.OS conditionals route to web (localStorage/getAuth) vs native (SecureStore/AsyncStorage/initializeAuth) implementations
- All token operations async on native, sync on web — callers must handle both patterns uniformly
- Auth hooks expose unified interface masking platform differences (signInWithPopup web, promptAsync native)
- Types mirror backend Pydantic: Basic/Summary for lists, Detail/Full for single entities, all include id + created_at
- Loading state managed in hook, Firebase credential exchange non-blocking, errors propagate as hook return values

## Navigation

**Parent:** [`tuck-in-tales-mobile/`](../CLAUDE.md)
**Peers:** [`app/`](../app/CLAUDE.md)
**Children:** [`config/`](config/CLAUDE.md) | [`hooks/`](hooks/CLAUDE.md) | [`models/`](models/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `config/firebase.ts` | Firebase initialization with platform-specific persistence | Conditionally call getAuth() (web) or initializeAuth() (native) |
| `config/supabase.ts` | Supabase client setup and auth token management | Token save/get/remove operations are async; await them on native |
| `hooks/useGoogleSignIn.ts` | Unified Google Sign-In across web and native platforms | Hook returns {user, loading, error}; handle platform routing internally |
| `models/index.ts` | TypeScript type definitions for entities (Character, Family, Story) | Add id (UUID string) and created_at (ISO date) to all new types |

## Key Imports

- `from 'src/config' — useInitialAuth, getTokenAsync, getFirebaseAuth`
- `from 'src/hooks' — useGoogleSignIn`
- `from 'src/models' — Character, Family, Story (+ Basic/Summary/Detail variants)`

## Add new authentication flow for platform X

1. Add Platform.OS conditional in config/firebase.ts or config/supabase.ts
2. Wrap hook return in loading/error state; expose unified interface
3. Test token persistence via platform-specific storage (SecureStore/localStorage)

## Don't

- Don't call getAuth() directly on native — use platform-conditional config export instead
- Don't mix sync token access (web) with async calls (native) — always await token operations
- Don't create new entity types without Basic, Summary, and Detail variants for different contexts

## Testing

- Web: verify localStorage token persists; native: check SecureStore retrieval on app restart
- Mock Platform.OS in tests; verify signInWithPopup called on web, promptAsync on native

## Why It's Built This Way

- Async token ops on native preserve SecureStore atomicity; web sync matches localStorage speed
- Hook-level platform routing hides complexity from consumers; types separate list/detail to prevent over-fetching

## What Goes Here

- new_mobile_query → `tuck-in-tales-mobile/src/hooks/queries/use{Domain}.ts`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`

## Subfolders

- [`config/`](config/CLAUDE.md) — Expo Router mobile app with tab navigation, TanStack Query data fetching
- [`hooks/`](hooks/CLAUDE.md) — Expo Router mobile app with tab navigation, TanStack Query data fetching
- [`models/`](models/CLAUDE.md) — Expo Router mobile app with tab navigation, TanStack Query data fetching

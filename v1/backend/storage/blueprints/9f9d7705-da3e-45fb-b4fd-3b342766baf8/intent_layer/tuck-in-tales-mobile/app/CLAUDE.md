# app/
> Root layout orchestrator: wraps entire app with auth, queries, gestures; routes unauthenticated→login, authenticated→tabs.

## Patterns

- Index.tsx always checks loading state first, then currentUser, then redirects—prevents auth flash
- RootLayout wraps three critical providers in order: GestureHandler→QueryClient→AuthProvider→Stack
- QueryClient configured once at root with retry=2 and staleTime=5min—all child queries inherit
- Stack uses group-based routing: (auth), (tabs), (modals with presentation:'modal')—no individual screen declarations
- Not-found screen links to /(tabs) not root—assumes users arriving here are post-auth

## Navigation

**Parent:** [`tuck-in-tales-mobile/`](../CLAUDE.md)
**Peers:** [`src/`](../src/CLAUDE.md)
**Children:** [`(auth)/`]((auth)/CLAUDE.md) | [`(tabs)/`]((tabs)/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `index.tsx` | Auth gate & redirect hub | Update redirect paths only—loading/redirect logic is finalized |
| `_layout.tsx` | Global provider tree & query defaults | Adjust staleTime/retry for data freshness; add providers before Stack only |
| `+not-found.tsx` | Fallback 404 screen | Keep home link pointing to (tabs)—assumes auth already passed |

## Key Imports

- `import { useAuth } from '../src/context/AuthContext'`
- `import { QueryClient, QueryClientProvider } from '@tanstack/react-query'`
- `import { Stack } from 'expo-router'`

## Add a new top-level route group (e.g., settings, admin)

1. Create new folder /(group-name) under app/
2. Add Stack.Screen name="(group-name)" in _layout.tsx (before or after modals)
3. Implement _layout.tsx inside group folder with child screens

## Don't

- Don't redirect in useEffect inside Index—Redirect component handles it synchronously before render
- Don't add screen declarations to Stack—use group folders (auth), (tabs), (modals) instead
- Don't move QueryClientProvider inside AuthProvider—QueryClient must wrap context that depends on queries

## Why It's Built This Way

- Index loading spinner prevents auth flash—waits for currentUser check before any redirect
- QueryClient at root ensures all child queries share retry/staleTime config—no per-query override noise

## What Goes Here

- new_mobile_screen → `tuck-in-tales-mobile/app/(tabs)/{screen}.tsx or tuck-in-tales-mobile/app/{path}.tsx`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`

## Subfolders

- [`(auth)/`]((auth)/CLAUDE.md) — Expo Router mobile app with tab navigation, TanStack Query data fetching
- [`(tabs)/`]((tabs)/CLAUDE.md) — Expo Router mobile app with tab navigation, TanStack Query data fetching

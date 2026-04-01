# hooks/
> Authentication hooks bridging Expo/Firebase Google Sign-In across web and native platforms with unified error handling.

## Patterns

- Platform-specific auth flow: web uses signInWithPopup, native uses Expo promptAsync via same hook interface
- Loading state managed locally in hook; Firebase credential exchange happens async without blocking UI
- Error state always reset before auth attempt; caught errors explicitly logged to console for debugging
- Debug logging on request object (redirectUri, clientId) helps diagnose auth setup misconfigurations early
- isReady flag gates sign-in availability: web always ready, native waits for Expo request initialization

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`config/`](../config/CLAUDE.md) | [`models/`](../models/CLAUDE.md)
**Children:** [`queries/`](queries/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `useGoogleSignIn.ts` | Cross-platform Google auth with Firebase credential exchange | Add platform checks before credential operations; always reset error state first |

## Key Imports

- `import { useGoogleSignIn } from '../hooks'`
- `import { signInWithGoogle, loading, error, isReady } from useGoogleSignIn`

## Add additional auth provider or new sign-in method

1. Create new hook following same pattern: [state hooks] → [platform-specific async function] → return {method, loading, error, isReady}
2. Reset error/loading states before auth attempt, catch errors with explicit console logging
3. Test isReady gate works on both platforms before exposing sign-in button

## Don't

- Don't call setLoading(false) in native flow inside promptAsync path — Firebase credential exchange happens in response effect, not in function
- Don't skip WebBrowser.maybeCompleteAuthSession() — required for Expo auth session completion on native
- Don't omit Platform.OS checks — auth APIs differ drastically between web (popup) and native (async flow)

## Testing

- Mock Platform.OS to 'web' and 'android'; verify signInWithPopup called on web, promptAsync on native
- Mock Firebase credential exchange failures; verify error state set and loading cleared in finally block

## Debugging

- If auth hangs on native: check isReady is true and request object populated; log redirectUri/clientId from useEffect
- If web popup fails silently: signInWithPopup throws; verify error catch block executes and logs full error object

## Why It's Built This Way

- Loading state kept in hook (not global) to support multiple auth methods independently without state collision
- Native flow defers setLoading(false) to response effect because promptAsync is async; web clears immediately in finally

## What Goes Here

- new_mobile_query → `tuck-in-tales-mobile/src/hooks/queries/use{Domain}.ts`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`

## Subfolders

- [`queries/`](queries/CLAUDE.md) — Expo Router mobile app with tab navigation, TanStack Query data fetching

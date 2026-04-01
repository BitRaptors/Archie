# (auth)/
> Authentication layout & login screen with email/Google sign-in, auto-redirects authenticated users to main app.

## Patterns

- useAuth() context + useGoogleSignIn() hook provide dual auth state management — always check both currentUser and googleError
- useEffect with currentUser dependency auto-redirects post-login before form UI renders (prevents flash)
- Error state cleared on new login attempt; both email and Google errors displayed in same Text component
- Loading state disables both buttons independently: email button uses local loading, Google uses hook's googleLoading + isReady check
- Stack layout hides header (headerShown: false) — auth screens intentionally minimal/header-free

## Navigation

**Parent:** [`app/`](../CLAUDE.md)
**Peers:** [`(tabs)/`](../(tabs)/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `_layout.tsx` | Auth route group wrapper, hides header | Add new auth screens as <Stack.Screen> siblings to login |
| `login.tsx` | Email + Google dual-auth form with auto-redirect | Preserve useEffect redirect logic; extract styles to separate file if adding screens |

## Key Imports

- `import { useAuth } from '../../src/context/AuthContext'`
- `import { useGoogleSignIn } from '../../src/hooks/useGoogleSignIn'`
- `import { signInWithEmailAndPassword } from 'firebase/auth'`

## Add signup or password reset screen

1. Create signup.tsx with identical TextInput/Pressable structure
2. Import same auth dependencies + useRouter
3. Add <Stack.Screen name="signup" /> to _layout.tsx
4. Redirect to login on success, not /(tabs)

## Don't

- Don't forget isReady check on Google button — prevents race conditions if SDK loads after mount
- Don't clear errors in finally block — email errors persist across attempts for debugging UX
- Don't rely on Firebase error messages alone — wrap with 'Failed to sign in' fallback for network failures

## Testing

- Mock useAuth to return null, verify login form displays; mock currentUser, verify router.replace called
- Test googleLoading=true blocks button and shows 'Signing in...'; test isReady=false also blocks

## Debugging

- If Google button never enables: check useGoogleSignIn returns isReady; Firebase SDK init may be async
- If redirect doesn't trigger: verify AuthContext updates currentUser after signInWithEmailAndPassword; check useEffect dependency

## Why It's Built This Way

- useEffect redirect fires BEFORE form render to prevent flashing auth UI to already-authenticated users
- Both error messages shown (email + google) because one hook may error while other is pending

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`

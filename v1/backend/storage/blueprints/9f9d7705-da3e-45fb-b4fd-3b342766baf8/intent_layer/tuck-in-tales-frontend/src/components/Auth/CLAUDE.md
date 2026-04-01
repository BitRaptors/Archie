# Auth/
> Auth folder handles Firebase login (email/password + Google OAuth) and route protection via context consumer.

## Patterns

- Separate loading states for email and Google flows prevent race conditions when both are pending
- Error messages map Firebase error codes to user-friendly strings—don't expose raw error codes
- ProtectedRoute consumes AuthContext directly; LoginForm navigates on success, doesn't manage auth state
- Input fields disable during any loading state (email OR googleLoading) to prevent double-submit
- Google sign-in uses GoogleAuthProvider with signInWithPopup; Firebase redirects happen inside try/catch

## Navigation

**Parent:** [`components/`](../CLAUDE.md)
**Peers:** [`Layout/`](../Layout/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md) | [`ui/`](../ui/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `LoginForm.tsx` | Firebase email + OAuth login UI with error handling | Add fields: update state, add validation, extend error mapping. Change auth: modify handler |
| `ProtectedRoute.tsx` | Route guard: redirects unauthenticated users to /login | Replace loading placeholder if needed. Keep Navigate with replace=true to prevent back loops |

## Key Imports

- `import { LoginForm } from '@/components/Auth/LoginForm'`
- `import ProtectedRoute from '@/components/Auth/ProtectedRoute'`
- `import { useAuth } from '@/context/AuthContext' (consumed by ProtectedRoute)`

## Add new sign-in method (e.g., phone, GitHub)

1. Create handler function following handleGoogleSignIn pattern (separate loading state)
2. Add error-code mapping for new provider's error codes
3. Wrap in try/catch, navigate('/account') on success, call setError on failure

## Don't

- Don't render inputs without disabled={loading || googleLoading}—allows simultaneous submissions
- Don't store auth state locally—consume from AuthContext, only use component state for form fields
- Don't catch auth errors without mapping codes—Firebase error codes are implementation details, not UX

## Testing

- LoginForm: mock signInWithEmailAndPassword/signInWithPopup, verify navigate calls and error states
- ProtectedRoute: mock useAuth hook with loading=true (shows 'Loading...'), currentUser=null (redirects), currentUser=user (renders children)

## Debugging

- If Google popup never fires: check GoogleAuthProvider instantiation inside handler, not at module level
- If inputs stay disabled after error: verify both loading AND googleLoading are reset in finally blocks

## Why It's Built This Way

- Separate googleLoading state prevents email form from disabling while Google popup waits—better UX for concurrent attempts
- ProtectedRoute uses loading placeholder instead of null/error because auth state is global; loading check belongs in context, not per-route

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

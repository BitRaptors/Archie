# config/
> Firebase and Supabase initialization with platform-specific auth persistence and token management.

## Patterns

- Platform.OS conditional routing: web uses localStorage/getAuth(), native uses SecureStore/AsyncStorage/initializeAuth()
- All token operations (save/get/remove) are async on native, sync on web — callers must handle both
- Firebase config sourced entirely from EXPO_PUBLIC_* env vars; no hardcoded credentials
- getReactNativePersistence requires @ts-expect-error because TS types lag Firebase RN runtime bundle
- Supabase helper wraps storage.getPublicUrl() with null-safety chaining to prevent undefined returns

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`hooks/`](../hooks/CLAUDE.md) | [`models/`](../models/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `firebase.ts` | Auth init, token lifecycle, ID token retrieval | Add Platform.OS checks for any new native-only features |
| `supabase.ts` | Supabase client, avatar URL generation | Keep getPublicAvatarUrl defensive: return null, never throw |

## Key Imports

- `import { app, auth, getFirebaseToken, saveToken, getToken, removeToken } from '@/config/firebase'`
- `import { supabase, getPublicAvatarUrl } from '@/config/supabase'`

## Add a new token type or storage location

1. Copy save/get/removeToken pattern with Platform.OS branching
2. Use SecureStore.setItemAsync on native, localStorage.setItem on web
3. Mirror async/sync behavior; native callers must await

## Don't

- Don't call getFirebaseToken() before auth.currentUser is hydrated — timing is unreliable, use onAuthStateChanged instead
- Don't store sensitive tokens in localStorage on web — current code does for consistency, but understand the tradeoff
- Don't assume getPublicAvatarUrl returns a string — always null-check, it returns null for falsy paths

## Testing

- Mock Platform.OS and test both branches separately — behavior differs (async vs sync, storage type)
- Verify env vars loaded: log firebaseConfig/supabaseUrl early in app startup before use

## Debugging

- If auth state vanishes after restart on native, check ReactNativeAsyncStorage is wired to initializeAuth — getAuth() alone won't persist
- If getPublicAvatarUrl returns null unexpectedly, trace avatarPath: likely null/undefined before call, not a storage issue

## Why It's Built This Way

- Platform-specific persistence required: web auth persists via browser storage; native needs explicit AsyncStorage + SecureStore for token security
- Supabase storage helper returns null instead of throwing: caller controls error handling, avoids cascading crashes on missing avatars

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`

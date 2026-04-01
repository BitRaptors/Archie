# tuck-in-tales-mobile/
> Expo React Native project root: bootstraps Firebase auth, Google OAuth, and platform routing via app.json + environment config.

## Patterns

- All Firebase/OAuth credentials injected via EXPO_PUBLIC_* vars in .env — never hardcoded, never committed
- app.json centralizes iOS/Android metadata + Google OAuth URL schemes (iOS bundleIdentifier, Android package must match OAuth config)
- .gitignore excludes .env*.local, native certs (*.p8, *.p12), and Metro health checks — prevents credential leaks
- GOOGLE_SIGNIN_SETUP.md documents exact Firebase Console path to Web Client ID — critical for dev, often the blocker
- App.tsx is a stub — actual routing lives in app/ folder via expo-router, not in root entry
- babel.config.js required for Expo module resolution; tsconfig.json strict for platform-conditional imports (Platform.OS)

## Navigation

**Parent:** [`root/`](../CLAUDE.md)
**Peers:** [`tuck-in-tales-backend/`](../tuck-in-tales-backend/CLAUDE.md) | [`tuck-in-tales-frontend/`](../tuck-in-tales-frontend/CLAUDE.md)
**Children:** [`app/`](app/CLAUDE.md) | [`src/`](src/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `.env.example` | Copy to .env; defines EXPO_PUBLIC_* vars for Firebase + OAuth | Add env per deployment (dev/staging/prod); Web Client ID is minimum |
| `app.json` | Expo config + iOS/Android platform-specific OAuth URL schemes | bundleIdentifier, package, infoPlist must match Google OAuth redirect URIs |
| `GOOGLE_SIGNIN_SETUP.md` | Step-by-step Google OAuth credential retrieval + troubleshooting | Follow exact Firebase Console path; restart Expo after .env update |
| `App.tsx` | Stub entry — actual app logic in app/ folder (expo-router) | Do not add logic here; route via app/index.tsx + app/_layout.tsx |

## Key Imports

- `From src/: Platform.OS conditional logic for token ops (SecureStore on native, localStorage on web)`
- `From app/ via expo-router: RootLayout wraps GestureHandler → QueryClient → AuthProvider → Stack navigator`

## Set up local dev environment with Google OAuth

1. Copy .env.example → .env; fill EXPO_PUBLIC_FIREBASE_* and GOOGLE_WEB_CLIENT_ID from Firebase Console
2. Verify app.json bundleIdentifier/package match OAuth redirect URIs in Google Cloud Console
3. Run npx expo start --web; test Google Sign-In button redirects to OAuth popup
4. On native: use Platform.OS conditionals in src/ to route SecureStore vs localStorage token ops

## Usage Examples

### Environment variable usage pattern (from .env.example)
```bash
EXPO_PUBLIC_FIREBASE_API_KEY="your-firebase-api-key"
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID="your-web-client-id.apps.googleusercontent.com"
// Accessed in code: const key = process.env.EXPO_PUBLIC_FIREBASE_API_KEY
```

## Don't

- Don't commit .env or credential files — .gitignore already excludes .env*.local; use .env.example as template
- Don't hardcode Firebase keys or OAuth IDs — extract to EXPO_PUBLIC_* env vars so Expo build system injects at compile time
- Don't restart dev server without restarting Expo after .env changes — new vars won't be available until full rebuild

## Testing

- Web: npx expo start --web, click Google Sign-In, verify OAuth popup opens and callback succeeds
- Native: use Expo Go app or eas build; verify SecureStore token persistence after OAuth redirect

## Debugging

- Invalid Client ID error: check Firebase Console Authentication > Google > Web SDK config; no extra spaces in .env
- Vars undefined in app/: restart full Expo server (Ctrl+C, npx expo start), not hot reload — new .env vars need compile

## Why It's Built This Way

- EXPO_PUBLIC_* prefix enforces env vars are public (bundled client-side); backend secrets stay in .env (server-only)
- app.json centralizes platform config so eas build reads correct iOS bundleIdentifier + Android package for OAuth

## What Goes Here

- new_mobile_screen → `tuck-in-tales-mobile/app/(tabs)/{screen}.tsx or tuck-in-tales-mobile/app/{path}.tsx`
- new_mobile_query → `tuck-in-tales-mobile/src/hooks/queries/use{Domain}.ts`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`

## Subfolders

- [`app/`](app/CLAUDE.md) — Expo Router mobile app with tab navigation, TanStack Query data fetching
- [`src/`](src/CLAUDE.md) — Expo Router mobile app with tab navigation, TanStack Query data fetching

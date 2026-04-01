# src/
> Root app entry point: wires auth context, routing, layout wrapper, and toast notifications. Vite config-driven.

## Patterns

- AuthProvider wraps entire app at two levels (main.tsx + App.tsx) — redundant but harmless, inner provider takes precedence
- All protected routes enforce ProtectedRoute + AppLayout nesting — single point of control for auth + chrome
- Routes follow predictable naming: /resource or /resource/:id for detail, /resource/create for form, /resource/list for index
- Firebase config via import.meta.env (Vite), auth service exported for use in context/api clients
- Sonner Toaster positioned top-right, richColors enabled — used by pages via api error handling + form success feedback

## Navigation

**Parent:** [`tuck-in-tales-frontend/`](../CLAUDE.md)
**Peers:** [`_restore/`](../_restore/CLAUDE.md)
**Children:** [`components/`](components/CLAUDE.md) | [`hooks/`](hooks/CLAUDE.md) | [`lib/`](lib/CLAUDE.md) | [`models/`](models/CLAUDE.md) | [`pages/`](pages/CLAUDE.md) | [`utils/`](utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `App.tsx` | Route registry + layout orchestration | Add route here; import page, wrap with ProtectedRoute + AppLayout |
| `firebaseConfig.ts` | Firebase SDK init + auth export | Never modify; auth used globally. Keep secrets in .env.local |
| `main.tsx` | React app mount + context bootstrap | Rarely touched. AuthProvider here is redundant with App.tsx — safe to remove one |
| `index.css` | Tailwind + design token theme in oklch | Modify --color-* CSS vars for brand changes; oklch(lightness chroma hue) format |

## Key Imports

- `import { AuthProvider } from './context/AuthContext'`
- `import { Toaster } from 'sonner'`
- `import { auth } from './firebaseConfig'`

## Add new authenticated page with navigation

1. Create page in pages/, export default component fetching own data
2. Import in App.tsx, add Route with path, ProtectedRoute, AppLayout wrapper
3. Add nav link in AppLayout (components/Layout/) — no props needed, component reads from useLocation()

## Usage Examples

### Protected route pattern from App.tsx
```tsx
<Route path="/characters" element={
  <ProtectedRoute>
    <AppLayout>
      <CharactersPage />
    </AppLayout>
  </ProtectedRoute>
} />
```

## Don't

- Don't nest ProtectedRoute without AppLayout — chrome won't render; always: ProtectedRoute > AppLayout > Page
- Don't add unprotected pages inside AppLayout — layout assumes auth context; only public pages (/, /login) live outside
- Don't import colors as hex — use CSS var(--color-primary); oklch tokens guarantee dark mode sync

## Testing

- Verify ProtectedRoute redirects unauthenticated users to /login; auth token absent → 403 from API
- Check Toaster appears top-right; trigger via api error in any page — should show failure toast

## Debugging

- If page mounts but AppLayout chrome missing: check route wrapping — must be ProtectedRoute > AppLayout > Page, not AppLayout > ProtectedRoute
- Auth context undefined in child components: verify AuthProvider wraps Router in main.tsx (it does); if not, move provider outside Router

## Why It's Built This Way

- Routes organized by resource (characters, stories, memories, family) not by workflow — mirrors backend API structure for clarity
- AppLayout + ProtectedRoute always paired: layout = chrome + context access, ProtectedRoute = auth gate. Separation keeps concerns clear.

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

- [`components/`](components/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features
- [`hooks/`](hooks/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features
- [`lib/`](lib/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features
- [`models/`](models/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features
- [`pages/`](pages/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features
- [`utils/`](utils/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features

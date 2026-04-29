# frontend/
> Next.js 14 frontend: dashboard + auth UI consuming backend API with TypeScript, Tailwind, React Query.

## Patterns

- API_URL sourced from NEXT_PUBLIC_API_URL env var with fallback to http://localhost:8000 in next.config.js and services/
- All axios service calls use identical pattern: singleton service object with method functions (authService, deliveryService, etc.)
- Components accept isLoading/isPending props and atomically disable all interactive elements during async operations
- React Context for auth state re-exported via hooks/useAuth() wrapper to isolate context dependency from consumers
- Markdown navigation parsing: generateId() must match ReactMarkdown heading ID generation or anchor links break
- View state machine in pages/: activeView + selectedId + repoId state + handlers that reset unrelated flags to prevent stale UI

## Navigation

**Parent:** [`root/`](../CLAUDE.md)
**Peers:** [`backend/`](../backend/CLAUDE.md) | [`landing/`](../landing/CLAUDE.md)
**Children:** [`components/`](components/CLAUDE.md) | [`hooks/`](hooks/CLAUDE.md) | [`lib/`](lib/CLAUDE.md) | [`pages/`](pages/CLAUDE.md) | [`services/`](services/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `.env.example` | Template for .env.local; copy before dev | Add vars here, document purpose; copy path in README |
| `next.config.js` | Build config; env var injection point | API_URL fallback + reactStrictMode=true; test both dev and build |
| `package.json` | Dependencies: Next.js 14, React 18, TanStack Query, axios, Tailwind, Mermaid | Lock axios ^1.6.0; verify react-query version matches hook calls |
| `tsconfig.json` | TypeScript strict mode + path aliases (inferred from usage) | Maintain strict:true; add baseUrl path aliases if cross-folder imports grow |

## Key Imports

- `from services/: authService, deliveryService, analysisService (re-exported in pages/)`
- `from hooks/: useAuth (wraps context consumer)`
- `from lib/: parseNavigation, generateId (used by pages/ and markdown renderer)`

## Add new API endpoint consumption (e.g., new service call from backend)

1. Create services/newFeatureService.ts with axios wrapper using API_URL fallback pattern
2. Import in pages/ and call within useEffect with hydration guard
3. Wire loading state to component prop and disable interactions atomically

## Don't

- Don't hardcode API_URL in component files — always use process.env.NEXT_PUBLIC_API_URL from services/
- Don't call setState without resetting orthogonal view state — leads to stale UI (e.g., selectedId persists after view change)
- Don't export Context directly from context/ — always export custom hook wrapper (useAuth pattern) for isolation

## Testing

- Dev: npm run dev, verify http://localhost:4000 + NEXT_PUBLIC_API_URL reaches backend (test via Network tab)
- Build: npm run build && npm start, confirm no env var errors and SSR hydration matches client

## Debugging

- Hydration mismatch: check useEffect dependencies and auth redirect timing — SSR can render unauthorized content before redirect
- Anchor links broken: verify generateId() in lib/markdown matches heading ID pattern in ReactMarkdown plugin

## Why It's Built This Way

- NEXT_PUBLIC_* prefix required — env vars private to server use standard names without it; this var is public by design
- Singleton service objects (not class instances): simpler testing, no constructor overhead, consistent with functional React

## What Goes Here

- new_frontend_page → `frontend/pages/{name}.tsx — auto-routed by Next.js`
- new_frontend_view → `frontend/components/views/{Feature}View.tsx`
- new_api_hook → `frontend/hooks/api/use{Feature}.ts`
- new_http_service → `frontend/services/{domain}.ts`

## Dependencies

**Depends on:** `Backend API`
**Exposes to:** `end users`

## Templates

### frontend_api_hook
**Path:** `frontend/hooks/api/use{Feature}.ts`
```
import { useState, useEffect } from 'react';
import { featureService } from '@/services/{feature}';
export function use{Feature}() { const [data, setData] = useState(null); ... }
```

## Subfolders

- [`components/`](components/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing
- [`hooks/`](hooks/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing
- [`lib/`](lib/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing
- [`pages/`](pages/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing
- [`services/`](services/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing

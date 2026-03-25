# hooks/
> Re-export authentication context hook; provides centralized access to auth state across app.

## Patterns

- Simple pass-through hook: useAuth() wraps useAuthContext() for consistent public API
- Context consumption pattern: hook layer isolates context dependency from components
- Folder acts as public API boundary: single export point for auth functionality

## Navigation

**Parent:** [`frontend/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md) | [`services/`](../services/CLAUDE.md)
**Children:** [`api/`](api/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `useAuth.tsx` | Re-export auth context hook to consumers | Keep as thin wrapper; logic lives in @/context/auth |

## Key Imports

- `from @/context/auth import useAuth (internal dependency only)`

## Add new auth-related hook to this folder

1. Create new file (e.g., useAuthUser.tsx)
2. Import from @/context/auth or @/api/auth as appropriate
3. Export hook with consistent naming pattern
4. Re-export from implicit __init__ or document in parent index

## Don't

- Don't import useAuthContext directly in components — import useAuth from hooks instead
- Don't add business logic here — this is a re-export layer only

## Why It's Built This Way

- Re-export pattern decouples component imports from context location; enables context refactoring without breaking consumers
- Single-file folder signals this is a placeholder for future auth hooks; expect growth here as auth needs expand

## What Goes Here

- new_api_hook → `frontend/hooks/api/use{Feature}.ts`

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

- [`api/`](api/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing

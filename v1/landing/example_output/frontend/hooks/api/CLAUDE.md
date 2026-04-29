# api/
> React Query hook layer wrapping service calls; centralizes caching, invalidation, auth token injection, and retry logic for API operations.

## Patterns

- Every hook wraps a service call via useMutation or useQuery; never call services directly from components
- Query keys structured as tuples (const KEYS object); enables precise invalidation and prevents key collisions
- Auth token injected at hook level via useAuth() — not passed from components; simplifies consumer code
- Mutations invalidate related query keys on success onSuccess callback; maintains cache coherence without manual refetches
- Conditional queries use enabled flag (!!token, !!repoId); lazy-loads data only when prerequisites exist
- Retry logic in useRepositoriesQuery differentiates 401 (invalid token, no retry) from transient errors (2 retries); prevents auth loops

## Navigation

**Parent:** [`hooks/`](../CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `usePrompts.ts` | Manage prompt CRUD, revisions, and rollback. | Add new mutation? Mirror onSuccess pattern: invalidate list + detail + revisions keys. |
| `useRepositoriesQuery.tsx` | List repos, analyze, fetch commit SHA; integrates auth. | New repo query? Check enabled: !!token && !!owner && !!repo pattern. Set staleTime explicitly. |
| `useSettings.ts` | Settings CRUD: ignored dirs, library capabilities, ecosystem options. | Reset mutations invalidate their own keys only; batch reset (useResetAllData) invalidates all queryKeys. |
| `useWorkspace.ts` | Active repo state, workspace repo list, agent files per repo. | Active repo mutations refresh both active and repositories keys to keep selection in sync. |
| `useDelivery.ts` | Push outputs to target repo (apply), generate preview. | Preview is on-demand mutation (no cache); apply mutation has no invalidation — may need workspace refresh. |

## Key Imports

- `import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'`
- `import { useAuth } from '@/hooks/useAuth'`
- `import { [service]Service } from '@/services/[domain]'`

## Add a new read-only query (e.g., fetch config option list)

1. Add key to KEYS object: myOption: ['settings', 'my-option'] as const
2. Create hook: useMyOption() with useQuery({ queryKey: KEYS.myOption, queryFn: () => service.get(), staleTime: Infinity if immutable or 60_000 if mutable })
3. Set enabled: !!dependency if data depends on auth or parent state

## Usage Examples

### Typical mutation with cache invalidation pattern
```typescript
mutationFn: (data) => service.update(id, data),
onSuccess: (_data, variables) => {
  qc.invalidateQueries({ queryKey: KEYS.list })
  qc.invalidateQueries({ queryKey: KEYS.detail(variables.id) })
}
```

## Don't

- Don't call services directly in components — use hooks; breaks caching and retry logic
- Don't forget enabled: !!condition on conditional queries; runs queryFn even when data not needed
- Don't invalidate overly broad keys (queryKey alone); use queryKey + partial match; prevents unnecessary refetches

## Testing

- Mock react-query: wrap test in QueryClientProvider with fresh client; assert queryKey invalidation via qc.getQueryState()
- Test conditionals: render hook with null token/id; verify queryFn never runs (check via mock assertion)

## Debugging

- Stale data? Check if mutations invalidate all affected keys (e.g., list + detail). Use React Query DevTools to inspect cache state.
- Enabled flag not working? Verify query condition is truthy — common miss: enabled: !!id when id could be falsy string like '0'.

## Why It's Built This Way

- Query keys as const tuples (not strings): enables type-safe, refactor-safe cache invalidation across mutations and nested keys
- Auth token at hook level, not component level: reduces prop drilling, centralizes retry logic (401 handling), simplifies testing

## What Goes Here

- **Custom hooks wrapping service layer for data fetching** — `use{Domain}.ts(x)`
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

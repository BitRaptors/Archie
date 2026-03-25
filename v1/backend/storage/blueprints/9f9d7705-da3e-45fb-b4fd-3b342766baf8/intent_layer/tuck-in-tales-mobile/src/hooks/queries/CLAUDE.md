# queries/
> React Query hooks for family data fetching with standardized caching, stale times, and error handling patterns.

## Patterns

- Every hook exports a queryKey constant (as const tuple) for cache invalidation and testing
- Stale times vary by data volatility: family/characters 5min, stories 2min (stories update more frequently)
- Parameterized query keys use factory functions for detail queries (useStory pattern)
- 404 errors treated as valid state (null data) not failures—useFamilyDetails catches and returns null
- Retry logic explicitly excludes 404s to prevent thrashing on missing resources
- Single-entity hooks use enabled flag to prevent queries when ID is falsy

## Navigation

**Parent:** [`hooks/`](../CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `useFamilyDetails.ts` | Primary guard for user onboarding state | When adding fields: update FamilyDetailResponse type, adjust staleTime if data volatility changes |
| `useStory.ts` | Detail fetch for single story with conditional execution | Template for other detail hooks; ensure enabled flag prevents unnecessary requests |
| `useCharacters.ts` | List fetch returning empty array fallback | Pattern for similar list queries; || [] prevents undefined bugs downstream |

## Key Imports

- `import { useCharacters, charactersQueryKey } from './hooks/queries'`
- `import { useStories, storiesQueryKey } from './hooks/queries'`
- `import { useFamilyDetails, familyQueryKey } from './hooks/queries'`

## Add a new list query hook

1. Export queryKey as const tuple ['domain', 'list']
2. Wrap api call with || [] fallback in queryFn
3. Set staleTime: 1000 * 60 * N (pick N based on update frequency)
4. Return typed UseQueryResult<T[], Error>

## Usage Examples

### Detail hook with conditional execution pattern
```typescript
export function useStory(storyId: string): UseQueryResult<Story, Error> {
  return useQuery({
    queryKey: storyQueryKey(storyId),
    queryFn: () => api.fetchStory(storyId),
    enabled: !!storyId,
  });
}
```

## Don't

- Don't throw 404s in list/detail queries—return null or [] so components don't crash on empty states
- Don't use identical staleTime for all queries—volatility should drive timing (stories shorter than characters)
- Don't skip enabled flag on parameterized hooks—prevents undefined ID queries from firing

## Testing

- Mock api.fetchX() to return test data, verify queryKey used for cache isolation
- Test 404 handling in useFamilyDetails—verify returns null, not error state

## Why It's Built This Way

- Query keys as const tuples allow TypeScript inference for useQueryClient().invalidateQueries() calls
- Explicit 404 handling in useFamilyDetails prevents race conditions during family creation flow

## What Goes Here

- **TanStack Query hooks for mobile data fetching** — `use{Domain}s.ts or use{Domain}.ts`
- new_mobile_query → `tuck-in-tales-mobile/src/hooks/queries/use{Domain}.ts`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`

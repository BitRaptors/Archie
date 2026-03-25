# hooks/
> SSE streaming hooks for async generation pipelines (stories, avatars, memories). Each wraps useSSEStream with domain-specific state.

## Patterns

- useSSEStream is the base abstraction; three domain hooks compose it with event parsing switch statements
- pagesRef/analysisTextRef accumulate streaming chunks; setState spreads ref.current to trigger renders
- Callback refs (onEventRef, onDoneRef) kept in sync without dependency array to prevent re-renders during long streams
- Events: 'status' updates UI, 'chunk' accumulates via ref, 'complete'/'done' stops stream, 'error' sets error state
- Each domain hook initializes empty state, passes enabled flag + memoryId/storyId to conditionally open connection
- SSE parsing: split on '\n\n', extract 'event: ' and 'data: ' lines, JSON.parse data, invoke onEvent callback

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `useSSEStream.ts` | Core SSE transport: fetch, parse events, invoke callbacks | Only modify if SSE protocol changes or auth token logic shifts. Add new event types in domain hooks, not here. |
| `useStoryStream.ts` | Story generation: outline → pages → text → images with retries | Add page event types here. Sync pagesRef mutations with setState spread to avoid stale UI. |
| `useMemoryStream.ts` | Memory analysis: text chunks, photo results, linked characters | startStream() resets state before enabling. Accumulate text in ref, set analysis on complete event. |
| `useAvatarStream.ts` | Avatar generation: status → visual description → image URL | Simplest hook; status updates + complete event sets URL. No chunking or retries. |

## Key Imports

- `from hooks import useSSEStream, useStoryStream, useMemoryStream, useAvatarStream`

## Add a new streaming event type (e.g., 'page_retry' already exists)

1. Add case in domain hook's handleEvent switch (useStoryStream, useMemoryStream, etc.)
2. If accumulating data: update ref, then setState(prev => ({ ...prev, pages: [...pagesRef.current] }))
3. If final state: setState directly without ref (e.g., 'complete' sets isComplete + error)
4. Test by triggering event from backend; verify UI updates without stale data

## Usage Examples

### Domain hook event handler pattern with ref accumulation
```typescript
case 'text_chunk': {
  const pageIdx = pagesRef.current.findIndex(p => p.page === data.page);
  if (pageIdx >= 0) {
    pagesRef.current[pageIdx].text += data.chunk;
    setState(prev => ({ ...prev, pages: [...pagesRef.current] }));
  }
  break;
}
```

## Don't

- Don't depend on onEvent/onDone directly in useEffect — use refs to keep callbacks stable across renders
- Don't mutate pagesRef/analysisTextRef without also calling setState spread — React won't re-render mutations alone
- Don't add event types to useSSEStream — they belong in domain hooks' switch statements

## Testing

- Mock fetch + ReadableStream; emit SSE events in sequence ('status' → 'text_chunk' → 'done'); assert state updates
- Verify ref mutations don't cause re-renders without setState; verify setState spread causes re-render

## Why It's Built This Way

- Callback refs prevent re-renders during long streams — needed because callbacks change but connection should stay open
- pagesRef/analysisTextRef accumulate chunks before setState — batching reduces renders, but must spread on setState else UI lags

## What Goes Here

- **Custom hooks wrapping SSE connections or domain-specific state** — `use{Domain}Stream.ts`
- new_web_hook → `tuck-in-tales-frontend/src/hooks/use{Domain}.ts`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

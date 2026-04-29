# views/
> View components for repository analysis pipeline UI: AnalysisView monitors streaming logs, BlueprintView displays generated blueprints, settings views configure discovery behavior.

## Patterns

- EventSource streaming with EventListener pattern: status, log, debug_* events parsed separately then composed into state
- Tab-based content switching (backend|claude|cursor|mcp|debug) with lazy-loaded SourceFileModal for file exploration
- Markdown rendering with custom handlers: mermaid code blocks → MermaidDiagram, source:// links → file modal, relative paths clickable
- Settings views use three-state pattern: loading skeleton → initialized local state → dirty/clean comparison against serverLibs/serverDirs
- Mutations trigger re-sync: updateMutation completes → useEffect re-syncs from rows → setInitialized(false) on reset forces full reload
- API URL from NEXT_PUBLIC_API_URL env, Bearer token from useAuth, isCompleteRef prevents duplicate event source subscriptions

## Navigation

**Parent:** [`components/`](../CLAUDE.md)
**Peers:** [`layout/`](../layout/CLAUDE.md) | [`ui/`](../ui/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `AnalysisView.tsx` | Streaming analysis monitor with live event log | Add event types in addEventListener blocks; scroll ref auto-scrolls; close EventSource on unmount |
| `BlueprintView.tsx` | Multi-tab blueprint display with file modal integration | markdownComponents handles code/link rendering; toc memoizes parseNavigation output; reset explore path when tab changes |
| `CapabilitiesSettingsView.tsx` | Library-capability registry editor with save/reset | isDirty compares sorted JSON; sync from server after mutations complete; handleAdd validates no duplicates |
| `IgnoredDirsSettingsView.tsx` | Directory exclusion list manager | serverDirs derived and sorted for comparison; trim input before checking duplicates; reset requires confirmation |

## Key Imports

- `from @/hooks/api/useSettings import useLibraryCapabilities, useUpdateLibraryCapabilities`
- `from @/hooks/api/useWorkspace import useActiveRepository, useSetActiveRepository`
- `from @/components/DebugView import DebugView`

## Add new tab or streaming event type

1. Add tab name to union type (e.g., 'backend' | 'new_tab')
2. Add case in activeTab conditional render or eventSource.addEventListener('event_name', ...)
3. Update state setter to accumulate or replace data consistently
4. Reset dependent state (explore path, search query) if tab affects UI scope

## Usage Examples

### EventSource listener pattern from AnalysisView
```typescript
eventSource.addEventListener('log', (e) => {
  const event = JSON.parse(e.data)
  setEvents((prev) => prev.some(p => p.id === event.id) ? prev : [...prev, event])
  scrollToBottom()
})
```

## Don't

- Don't close EventSource mid-stream — use isCompleteRef flag to prevent re-subscription on status check
- Don't assume file exists in explore path — reset currentExplorePath to '/' when switching tabs to avoid stale folder references
- Don't compare local state to server without sorting — settings views sort both sides before JSON.stringify dirty check

## Testing

- Mock EventSource with addEventListener listener tracking; fire 'complete' to verify cleanup and isCompleteRef flag
- Render settings view with isLoading=true → initialized=false → dirty=true, verify Save button enabled and Reset shows confirmation

## Debugging

- EventSource errors silently fall back to polling via error listener — check network tab and API response status if events stop flowing
- Stale file explorer state happens when currentExplorePath doesn't reset on tab switch — look for useEffect dependency on activeTab

## Why It's Built This Way

- EventSource chosen over polling because backend streams multiple event types (status, log, debug_*) without request overhead
- Settings use optimistic local state + server comparison because mutation latency allows user to see changes before sync

## What Goes Here

- **Page-level feature containers composed from sub-components** — `{Feature}View.tsx`
- new_frontend_view → `frontend/components/views/{Feature}View.tsx`

## Dependencies

**Depends on:** `Backend API`
**Exposes to:** `end users`

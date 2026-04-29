# pages/
> Next.js pages folder: routing entry points for Dashboard, Auth, and app initialization with centralized state management.

## Patterns

- View state machine: activeView + selectedId + repoId form orthogonal state; handlers reset unrelated flags to prevent stale UI
- Hydration guard + auth redirect in useEffects prevent SSR/client mismatch and unauthorized access before redirect completes
- Three-tier loading: mounted check → isAuthLoading → isActiveLoading → initialLoadDone prevents race conditions on first load
- Handler pattern: each navigation function (handleAnalyze, handleViewBlueprint, etc.) resets ALL state flags except repoId/selectedId for that view
- React Query cache + toast error handling centralized in _app.tsx; extractErrorMessage extracts nested error.response.data.detail from Axios
- Auth page dual-mode: serverTokenMode + clientToken logic splits between server-stored tokens and browser localStorage auth

## Navigation

**Parent:** [`frontend/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`hooks/`](../hooks/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`services/`](../services/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `index.tsx` | Dashboard router; SPA state machine for 4 views | Always reset flags in handlers. Preserve activeRepo sync logic when adding views. |
| `_app.tsx` | Global error handling, auth context, React Query setup | Update extractErrorMessage if API error shape changes. Toaster position is fixed. |
| `auth.tsx` | Token input form; redirects on successful auth | serverTokenMode redirects on load complete. Don't add form fields without updating useAuth hook. |
| `_document.tsx` | HTML skeleton only; minimal setup | Add <Head> meta tags here, not in _app.tsx. Keep side-effect free. |

## Key Imports

- `from @/hooks/useAuth import useAuth`
- `from @/hooks/api/useWorkspace import useWorkspaceRepositories, useActiveRepository`
- `from next/router import useRouter`

## Add new view type to dashboard (e.g., 'reports' view)

1. Add 'reports' to ViewState type union
2. Create handleReports handler that resets state (selectedId=null, repoId=null, initialBlueprintTab=undefined)
3. Add {activeView === 'reports' && <ReportsView />} in render
4. Add route in Sidebar navigation handler

## Usage Examples

### View state reset pattern in handlers
```typescript
const handleNavigate = (view: ViewState) => {
  setActiveView(view)
  setSelectedId(null)
  setInitialBlueprintTab(undefined)
  setRepoId(activeRepo?.active_repo_id || null)
}
```

## Don't

- Don't set repoId and selectedId simultaneously — one view uses repoId, other uses selectedId; both set crashes state machine
- Don't omit setInitialLoadDone check in activeRepo effect — infinite loops result from double-initialization
- Don't forget to reset initialBlueprintTab in handlers — stale tab persists across view transitions

## Testing

- Test initial load: mock useActiveRepository with active_repo_id, verify blueprint view auto-loads with correct repoId
- Test auth redirect: clear isAuthenticated, verify router.push('/auth') fires before mounted check completes

## Debugging

- useRouter.push('/auth') won't redirect until isAuthLoading=false AND !isAuthenticated both true — check hook state in DevTools
- State 'stuck' in wrong view? Check if handler reset selectedId/repoId/initialBlueprintTab; stale props prevent re-render

## Why It's Built This Way

- Three separate useState flags (repoId, selectedId, initialBlueprintTab) instead of single view object — ensures fine-grained re-renders and avoids accidental state coupling
- initialLoadDone guard prevents activeRepo effect from firing multiple times; activeRepo shape can change after user updates default repo elsewhere

## What Goes Here

- new_frontend_page → `frontend/pages/{name}.tsx — auto-routed by Next.js`

## Dependencies

**Depends on:** `Backend API`
**Exposes to:** `end users`

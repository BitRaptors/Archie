# layout/
> Layout wrapper components for consistent app chrome: header, sidebar nav, and main shell container.

## Patterns

- PageHeader uses sticky positioning (top-0 z-20) with backdrop blur for persistent context above scrolling content
- Shell uses fixed sidebar (lg:block hidden, z-50) with lg:pl-64 main offset — hidden on mobile, visible desktop
- Sidebar integrates router.useRouter() + useAuth hook directly; state flows down via onNavigate/onHistoryClick callbacks
- Active state tracking uses three separate IDs: activeView (string enum), activeRepoId (current context), openedRepoId (UI selection state)
- Icon components (LucideIcon) passed as props to PageHeader; icons in Sidebar imported directly and wrapped in badge containers
- Theme object (from @/lib/theme) applied conditionally to sidebar context card via cn() utility for semantic color switching

## Navigation

**Parent:** [`components/`](../CLAUDE.md)
**Peers:** [`ui/`](../ui/CLAUDE.md) | [`views/`](../views/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `PageHeader.tsx` | Sticky header with optional icon and action slots | Pass icon as LucideIcon component; actions as JSX. Adjust z-20 if modal stacking needed. |
| `Shell.tsx` | Two-column layout: fixed sidebar + responsive main content | Sidebar hidden <lg; main has pl-64 offset. Modify gradient bg via className prop. |
| `Sidebar.tsx` | Navigation hub: repo history, settings, auth, active project context | Pass history array + callbacks. Watch activeView vs activeRepoId distinction for correct highlighting. |

## Key Imports

- `from @/lib/utils import cn`
- `from lucide-react import {Icon names as LucideIcon components}`
- `from @/lib/theme import theme object for conditional styling`

## Add new sidebar navigation item with active state styling

1. Create Button with variant='ghost' matching existing repositories/settings pattern
2. Add to activeView conditional: pass icon, check activeView === 'new_view' for highlight classes
3. Wire onClick to onNavigate?.('new_view') callback to parent component

## Don't

- Don't call onNavigate/onHistoryClick inside event handlers without checking they exist — use ?. operator
- Don't rely on z-index layering without documenting: Shell sidebar z-50, PageHeader z-20, modal should exceed both
- Don't mutate history array directly — treat it as read-only; parent controls repo list state

## Testing

- Render Shell with sidebar mock; confirm sidebar hidden on small screens, visible on lg breakpoint
- Pass activeRepoId matching history item; verify active project card displays and context label shows

## Debugging

- Sidebar unresponsive: check onNavigate/onHistoryClick passed from parent; callbacks may be undefined
- Active state not highlighting: verify activeView string matches Button onClick condition exactly (case-sensitive)

## Why It's Built This Way

- Sidebar fixed (not sticky) to stay above page scroll; Shell main has lg:pl-64 offset instead of margin to avoid layout shift
- Three ID states (activeView, activeRepoId, openedRepoId) separate navigation tab, active project context, and visual selection intent

## Dependencies

**Depends on:** `Backend API`
**Exposes to:** `end users`

# components/
> Reusable UI components for repository analysis views: dialogs, debug panels, diagrams, delivery controls, and file trees.

## Patterns

- All interactive components accept isLoading/isPending state and disable actions atomically — see ConfirmationDialog, DeliveryPanel
- EventSource streaming UI (DebugView) parses debug_* event prefixes separately, composes into expandable phase tabs with truncation badges
- Mermaid diagrams render async to avoid DOM injection; use temp container + global init flag to prevent Mermaid UI pollution
- Modal/dialog overlays use fixed inset-0 z-50 with onClick target check to close only on backdrop, Escape key listener in useEffect
- Output selection uses checkbox arrays (outputs.includes + filter/spread pattern) — see DeliveryPanel OUTPUT_OPTIONS
- Code blocks render with custom Tailwind + theme tokens (console.bg, console.text) — max-h-96 overflow-y-auto for truncation visibility

## Navigation

**Parent:** [`frontend/`](../CLAUDE.md)
**Peers:** [`hooks/`](../hooks/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md) | [`services/`](../services/CLAUDE.md)
**Children:** [`layout/`](layout/CLAUDE.md) | [`ui/`](ui/CLAUDE.md) | [`views/`](views/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `ConfirmationDialog.tsx` | Modal confirm/cancel with destructive variant and loading spinner. | Update theme.status.errorPanel refs if redesigning alert icon background. |
| `DebugView.tsx` | Expandable phase analysis UI with summary stats, code blocks, markdown + Mermaid. | Phase tab rendering uses phases.find(p => p.phase === activePhaseTab); add phase type safety. |
| `DeliveryPanel.tsx` | Repository selector + output checkbox grid + strategy toggle + deliver mutation handler. | Auth token handling: filter SERVER_TOKEN before API call; don't send as Bearer. |
| `MermaidDiagram.tsx` | Async Mermaid renderer with error fallback and heuristic bracket quoting. | isInitialized global prevents re-init; cancelled flag stops stale renders. Keep both. |
| `ProjectTree.tsx` | Parse tree string into indented folder hierarchy, filter out file markers. | Depth calc: (depthMatch[1].length / 4) — adjust divisor if tree symbol set changes. |

## Key Imports

- `from @/lib/utils import cn`
- `from @/lib/theme import theme`
- `from lucide-react import AlertTriangle, Folder, CheckCircle2`

## Add a new expandable debug section to DebugView

1. Add field to PhaseInfo interface, populate in phases array
2. Add toggleSection call with unique id to expandedSections state
3. Wrap content in conditional render of expandedSections[id], use getTruncationBadge for char counts

## Usage Examples

### Atomic checkbox array toggle pattern from DeliveryPanel
```typescript
const toggleOutput = useCallback((key: string) => {
  setOutputs((prev) =>
    prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
  )
}, [])
```

## Don't

- Don't call mermaid.initialize on every render — use global isInitialized flag to init once
- Don't render unvalidated SVG directly — MermaidDiagram uses temp DOM + suppressErrorUI to contain injections
- Don't leave EventListener attached after unmount — ConfirmationDialog cleanup removes keydown listener in useEffect return

## Testing

- ConfirmationDialog: test Escape closes, backdrop click closes, confirmText/isLoading render correctly
- MermaidDiagram: mock mermaid.render, verify doRender cleans up tempDiv even on error, check cancelled flag stops setSvg

## Why It's Built This Way

- Temp DOM container in MermaidDiagram prevents Mermaid's default document.body injection of error UI; suppressErrorUI flag + cleanup guards against pollution
- Phase tabs in DebugView use nullable activePhaseTab defaulting to last phase — simplifies initial render without requiring explicit useState initialization

## What Goes Here

- new_frontend_view → `frontend/components/views/{Feature}View.tsx`

## Dependencies

**Depends on:** `Backend API`
**Exposes to:** `end users`

## Subfolders

- [`layout/`](layout/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing
- [`ui/`](ui/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing
- [`views/`](views/CLAUDE.md) — Next.js dashboard for repo management, analysis results, settings, blueprint viewing

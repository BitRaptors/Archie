# ui/
> Radix UI primitive wrappers with consistent styling via CVA variants and data-slot attributes for composable component system.

## Patterns

- Every component wraps a Radix primitive and exposes subcomponents (Root, Trigger, Content, etc.) for composition
- data-slot attributes on every element enable CSS targeting and E2E test selection without class fragility
- CVA (class-variance-authority) defines variants once, reused across button/badge/alert for DRY styling
- cn() utility merges default classes with user overrides—always pass className last in CVA call
- Slot pattern (asChild prop) allows semantic HTML replacement: Badge/Button can render as <a>, <div>, etc.
- Animation classes use data-[state] selectors—fade-in/zoom-in tied to Radix state, not manual JS

## Navigation

**Parent:** [`components/`](../CLAUDE.md)
**Peers:** [`Auth/`](../Auth/CLAUDE.md) | [`Layout/`](../Layout/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `button.tsx` | Base variant system template for all interactive components | Add size/variant → update cva variants object, preserve disabled:opacity-50 pattern |
| `alert-dialog.tsx` | Multi-part dialog composition with overlay and portal handling | Don't modify Radix children order; extend via className on AlertDialogContent |
| `badge.tsx` | Lightweight inline variant component with asChild flexibility | Badge reuses button styling pattern—keep Slot usage for link rendering |
| `alert.tsx` | CSS Grid-based alert with optional icon layout | has-[>svg] selector auto-adjusts grid cols—don't hardcode icon spacing |

## Key Imports

- `from '@/lib/utils' import cn`
- `from 'class-variance-authority' import cva`
- `from '@radix-ui/react-*' import subcomponent primitives (each component imports own Radix module)`

## Add new variant to existing component (e.g., button ghost → link)

1. Add key:value to variants object in CVA definition
2. Verify className chain: cn(variants({variant}), className)
3. Test via data-slot selector in E2E; check dark mode colors

## Don't

- Don't pass className first to cn()—cn(buttonVariants({variant, size, className})) ensures variants override user classes
- Don't skip data-slot attributes—they're test anchors and style hooks, not optional decoration
- Don't create new component files for minor style variations—use CVA variants instead

## Testing

- Query by data-slot attribute: [data-slot='button'] isolates component and its subparts from CSS noise
- CVA variant output is deterministic—test className string directly, not computed styles

## Debugging

- data-[state=open] animations fail silently if Radix state not propagated—check AlertDialogPrimitive export chain
- cn() merge order: default classes overridden by variant classes, then user className—last class wins

## Why It's Built This Way

- data-slot chosen over class-based selectors because semantic names survive refactoring and prevent specificity wars
- CVA variants centralized in each file (not shared utils) to keep component dependencies local and copyable

## What Goes Here

- shared_ui_component → `tuck-in-tales-frontend/src/components/ui/{component}.tsx (shadcn pattern)`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

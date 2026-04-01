# components/
> UI components for character management, confirmation dialogs, and mention-based text input with character references.

## Patterns

- Character cards use cursor-pointer + hover:shadow-md for clickable affordance; navigate via onClick → /characters/:id
- API errors map to user-friendly toast messages; store actionLoading per-character ID to prevent race conditions
- Mention system: @ trigger at word boundary → dropdown with filtered characters → @{Name} format for rendering
- Dropdown positioning via absolute z-50; outside click closes via document.addEventListener; keyboard nav (Arrow/Enter/Escape)
- Avatar fallback uses char.name?.charAt(0) with nullish coalescing to prevent crashes on missing names
- ConfirmationDialog wraps AlertDialog as composition; triggerButton passed as React.ReactNode for reuse without hardcoding

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`hooks/`](../hooks/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)
**Children:** [`Auth/`](Auth/CLAUDE.md) | [`Layout/`](Layout/CLAUDE.md) | [`prompts/`](prompts/CLAUDE.md) | [`ui/`](ui/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `CharacterList.tsx` | Grid view of characters with delete + edit actions | Add new action: update actionLoading state + add handler + wire to card button |
| `ConfirmationDialog.tsx` | Reusable AlertDialog wrapper for destructive actions | Pass triggerButton as children; confirmAction fires on confirm button click |
| `MentionInput.tsx` | Textarea with @ mention dropdown; renderMentionText displays styled mentions | Track mentionStart (not cursor) for replacement; reset selectedIndex on filter change |

## Key Imports

- `import { ConfirmationDialog } from './ConfirmationDialog'`
- `import { renderMentionText } from './MentionInput'`
- `import { getPublicAvatarUrl } from '@/utils/supabaseUtils'`

## Add new delete button to CharacterList card with confirmation

1. Import ConfirmationDialog; pass <Button variant='ghost'><TrashIcon/></Button> as triggerButton
2. Set confirmAction={() => handleDelete(char.id)} with title/description props
3. handleDelete already updates state + shows toast; wrap with setActionLoading to prevent double-clicks

## Don't

- Don't use cursor position directly for mention replacement — track mentionStart from @ index, replace from there
- Don't let dropdown close on textarea blur — use onMouseDown + preventDefault to prevent focus loss
- Don't expose raw API error codes to users — map via error.response?.data?.detail || fallback message

## Testing

- MentionInput: type 'A@john' (@ not at boundary) → dropdown hidden; type 'A john' then '@jo' → filtered dropdown appears
- CharacterList: delete character → verify from state removed + API called + toast shown; reload should not restore

## Debugging

- Mention dropdown not appearing: check lastAt !== -1, charBeforeAt is space/newline/start, textAfterAt has no '}' already
- Avatar image broken: verify getPublicAvatarUrl(char.avatar_url) returns valid Supabase public URL; fallback to initials works

## Why It's Built This Way

- MentionInput uses @{Name} format (vs @Name) to support multi-word character names unambiguously in renderMentionText regex
- CharacterList actionLoading is Record<string, boolean> (vs single boolean) to track per-character loading state independently

## What Goes Here

- shared_ui_component → `tuck-in-tales-frontend/src/components/ui/{component}.tsx (shadcn pattern)`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

## Subfolders

- [`Auth/`](Auth/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features
- [`Layout/`](Layout/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features
- [`prompts/`](prompts/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features
- [`ui/`](ui/CLAUDE.md) — React SPA with pages, SSE hooks, and auth context for all app features

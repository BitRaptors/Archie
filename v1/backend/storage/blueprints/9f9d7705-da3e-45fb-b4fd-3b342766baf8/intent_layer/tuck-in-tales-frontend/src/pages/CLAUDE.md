# pages/
> Page components for tuck-in-tales app. Each page owns its data fetching, state management, and form handling. Heavy lifting per-page.

## Patterns

- Pages fetch their own data via api.* client calls in useEffect + useCallback, not via props
- Form submissions validate input first (name required, date regex), then create resource, then upload/attach media
- Loading/error states tracked separately per async operation (uploadingPhotos, isDeleting, isSavingBio)
- useNavigate() for redirection after successful create/update; pass prefill via location.state for pre-population
- Markdown rendering uses custom components object passed to ReactMarkdown; pre blocks use whitespace-pre-wrap
- Chat/stream patterns: useState for message array + ref for scroll target; SSE hook manages connection lifecycle

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`hooks/`](../hooks/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `CharacterCreationPage.tsx` | Create character with bio, birth date, photo upload | Validate before create, upload photos after character exists, navigate to detail on success |
| `CharacterDetailPage.tsx` | Display, edit, delete character; avatar generation; relationships | Fetch character + photos on mount. Edit bio/birthDate separately. Use SSE hook for avatar stream. |
| `CharactersPage.tsx` | List all characters, navigate to create | Minimal page; delegates to CharacterList component and create navigation |
| `FamilyPage.tsx` | Manage family, members, language settings, main characters | Fetch family data, edit name/language. Use Combobox for language selection from SUPPORTED_LANGUAGES array. |
| `AccountPage.tsx` | Display current user email, verification, UID | Read-only display. useAuth hook for currentUser. No logout logic (removed). |

## Key Imports

- `from '@/api/client' import api`
- `from '@/context/AuthContext' import useAuth`
- `from '@/components/MentionInput' import MentionInput`

## Add a new editable field (like bio/birthDate) to CharacterDetailPage

1. Add state: editableField, isModified, isSaving, error
2. Add onChange handler that sets both edited state AND modified flag
3. Add save handler: validate, call api.updateCharacter(), catch/toast error, refetch or reset
4. Conditionally render edit/save/cancel buttons based on isModified flag

## Don't

- Don't handle logout on AccountPage — auth context/layout handles it globally
- Don't validate date format client-side with custom regex — use <input type='date'> and server validation
- Don't upload photos before character exists — always create resource first, capture ID, then attach media

## Testing

- Form submission: verify validation catches empty name, invalid date format; verify toast messages fire
- Photo upload: test file removal by name match; verify URL.revokeObjectURL called on unmount to prevent leaks

## Debugging

- Avatar generation timing: isGeneratingAvatar gate prevents double-trigger; SSE hook connection status + message logged
- Chat scroll: use chatScrollAreaRef.current to scroll to latest message after state update

## Why It's Built This Way

- Markdown components defined outside component to avoid re-creation on each render; pre uses whitespace-pre-wrap for code readability
- Photo signed URLs fetched separately and stored in state to decouple image loading from character data lifecycle

## What Goes Here

- **Route-level React components; one per app screen** — `{Domain}Page.tsx`
- new_web_page → `tuck-in-tales-frontend/src/pages/{Domain}Page.tsx + route in tuck-in-tales-frontend/src/App.tsx`

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

## Templates

### web_page
**Path:** `tuck-in-tales-frontend/src/pages/{Domain}Page.tsx`
```
export default function {Domain}Page() {
  const { user } = useAuth();
  return <div>...</div>;
}
```

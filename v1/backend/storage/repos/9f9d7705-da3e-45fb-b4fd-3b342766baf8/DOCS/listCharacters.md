# To-Do List for Displaying Character List

- [x] Add `fetchCharacters` function to API client (`src/api/client.ts`)
- [x] Create `CharacterList.tsx` component in `src/components/`
- [x] Implement data fetching (using `react-query` if set up, or state) in `CharacterList.tsx`
- [x] Display characters in `CharacterList.tsx` using Shadcn components (e.g., Card, Table)
- [x] Add `CharacterList` component to `src/pages/CharactersPage.tsx` (renamed from CharacterCreationPage)
- [x] Test the character list display
- [x] Update `docs/characters.md` if necessary (verify GET endpoint documentation)
- [x] Add `deleteCharacter` function to API client (`src/api/client.ts`)
- [x] Verify backend `DELETE /api/characters/{character_id}` route exists
- [x] Add `updateCharacter` function to API client (`src/api/client.ts`)
- [x] Verify backend `PUT /api/characters/{character_id}` route exists
- [x] Add Delete button and confirmation dialog to `CharacterList.tsx`
- [x] Implement delete handler in `CharacterList.tsx` (call API, update state)
- [x] Add Edit button to `CharacterList.tsx`
- [x] Implement basic edit handler (e.g., navigate to edit page/log ID)
- [x] Test Edit/Delete functionality (Delete tested, Edit deferred) 
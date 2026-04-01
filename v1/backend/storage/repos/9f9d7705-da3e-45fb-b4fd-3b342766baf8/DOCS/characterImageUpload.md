# To-Do List for Character Image Uploads

**Backend:**
- [x] Modify backend endpoint `POST /api/characters/{character_id}/photo` to accept multiple files (`List[UploadFile]`). Rename to `/photos`?
- [x] Update backend logic in `characters.py` to handle multiple file uploads (loop, save each).
- [x] Decide how to store multiple photo URLs/paths in the database (e.g., update character model/table with `photo_paths: List[str]`). - *Decision: Use `photo_paths` array.*
- [x] Update the response model for the upload endpoint if necessary.

**Frontend:**
- [x] Install `react-dropzone` library (`npm install react-dropzone`).
- [x] Add state for selected files (`File[]`) in `CharacterCreationPage.tsx`.
- [x] Integrate `react-dropzone` component into the form.
- [x] Display image previews.
- [x] Create new API function `uploadCharacterPhotos(characterId: string, files: File[])` in `client.ts` (using `FormData`).
- [x] Modify `handleSubmit` in `CharacterCreationPage.tsx`: 
    - First, call `api.createCharacter`.
    - On success, get the `characterId`.
    - If files were selected, call `api.uploadCharacterPhotos` with the ID and files.
    - Handle potential errors during photo upload separately.
- [x] Add loading/feedback specifically for the photo upload step.

**General:**
- [x] Update documentation (`docs/characters.md`) for the modified/new endpoint.
- [x] Test the entire flow: create character with images. 
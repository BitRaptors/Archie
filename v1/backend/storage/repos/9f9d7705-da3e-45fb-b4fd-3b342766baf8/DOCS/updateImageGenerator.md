# To-Do List for Updating Image Generator

- [x] Check `openai` library version in `tuck-in-tales-backend/pyproject.toml`.
- [x] Update `openai` library if necessary (`poetry update openai`).
- [x] Modify `generate_image` function in `tuck-in-tales-backend/src/graphs/avatar_generator.py`:
    - [x] Initialize `AsyncOpenAI` client (if not already done).
    - [x] Read original photo files specified in `state['photo_paths']` in binary mode.
    - [x] Call `await client.images.edit()` with `model="dall-e-2"`, the opened file objects, and the `dalle_prompt` from the state. # Note: Used dall-e-2 as gpt-image-1 is invalid and only used the first photo.
    - [x] Decode the `b64_json` response.
    - [x] Save the decoded image bytes to a file (upload to Supabase).
    - [x] Update the state with the path to the new avatar.
    - [x] Add error handling for API call and file operations.
- [ ] Restart backend server.
- [ ] Test avatar generation for a character.
- [ ] Mark tasks as complete in this list. 
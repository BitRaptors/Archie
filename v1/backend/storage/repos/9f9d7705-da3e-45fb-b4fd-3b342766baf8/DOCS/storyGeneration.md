# To-Do List for Story Generation Feature

## Backend (`tuck-in-tales-backend`)
- [x] Models: Define Pydantic models for Story Generation Request (character IDs, prompt) and Story Response in `src/models/story.py`.
- [x] Routes: Create `src/routes/stories.py` with an endpoint `POST /api/stories/generate`.
- [x] Dependencies: Add necessary libraries (e.g., `openai`, maybe `langchain`) to `pyproject.toml` if not already present.
- [ ] Logic: Implement background task for story generation:
  - [ ] Fetch selected character details (name, bio) from DB.
  - [ ] Construct a prompt for the LLM using character details and the optional user prompt.
  - [ ] Call LLM (e.g., OpenAI GPT) to generate story title and pages (text).
  - [ ] For each page, generate an image using an image model (e.g., DALL-E).
  - [ ] Upload generated images to Supabase storage (e.g., `stories/{story_id}/{page_index}.png`).
  - [ ] Save the complete story (family_id, title, pages JSONB with text and image URLs, language) to the `stories` table.
  - [ ] Handle errors during generation.
- [x] Endpoint: `POST /api/stories/generate` should accept the request, trigger the background task, and return `202 Accepted` immediately.

## Frontend (`tuck-in-tales-frontend`)
- [x] API Client: Add `generateStory` function to `src/api/client.ts`.
- [x] UI (`StoryGenerationPage.tsx`):
  - [x] Fetch characters using `api.fetchCharacters` on component mount.
  - [x] Implement state for selected character IDs, prompt text, loading status, and errors.
  - [x] Render character selection UI (e.g., list of Checkboxes in a ScrollArea).
  - [x] Render Textarea for the optional prompt.
  - [x] Render submit button.
  - [x] Add form handling logic (gather selections, prompt; call `api.generateStory`).
  - [x] Display loading indicator during submission.
  - [x] Show success/error messages (e.g., using `toast`).
- [x] Components: Install necessary Shadcn components (`Checkbox`, `Textarea`, `ScrollArea`, potentially `Card`).

## Documentation & Testing
- [x] Documentation: Update `docs/stories.md` (or create it) with the new endpoint details.
- [ ] Testing: Test backend endpoint triggering.
- [ ] Testing: Test frontend form submission and character selection.
- [ ] Testing: Verify background task runs and saves story/images correctly (manual check initially). 
# To-Do List for Story Generation Progress Page

- [ ] Create `StoryProgressPage.tsx` component file in `tuck-in-tales-frontend/src/pages/`.
- [ ] Add a route for `/story-progress/:clientId` in the frontend router (e.g., `App.tsx`) pointing to `StoryProgressPage`.
- [ ] Modify `StoryGenerationPage.tsx`:
    - [ ] Generate a unique client ID (e.g., using `uuid`) before submitting.
    - [ ] Update the `api.generateStory` call and backend endpoint (`/generate-story`) to accept and use this `clientId` for WebSocket communication.
    - [ ] Navigate to `/story-progress/:clientId` upon successful submission.
- [ ] Implement `StoryProgressPage.tsx`:
    - [ ] Get `clientId` from route parameters.
    - [ ] Establish WebSocket connection to the backend (e.g., `ws://localhost:8000/ws/{clientId}`) on component mount.
    - [ ] Define state variables to hold progress status, outline, page data (text, image prompts, image URLs), errors, etc.
    - [ ] Handle incoming WebSocket messages (`status`, `error`, `outline`, `page_text`, `image_prompt`, `page_image`).
    - [ ] Update component state based on received messages.
    - [ ] Render the UI to display the current step, generated outline, and pages with text/images as they arrive.
    - [ ] Handle WebSocket connection errors and closure.
- [ ] Style the `StoryProgressPage` for clarity and visual appeal.
- [ ] Add tests for the new page and WebSocket interactions (optional but recommended).
- [ ] Document the new page and WebSocket flow in `docs/story_generation.md` (or similar). 
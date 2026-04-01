# To-Do List for Refactoring Story Generation (Save & Update)

## Phase 1: Backend Changes

-   [ ] **Database Schema:**
    -   [ ] Add `status` column (TEXT, default 'INITIALIZING') to `stories` table.
    -   [ ] Add `input_prompt` column (TEXT, nullable) to `stories` table.
    -   [ ] Add `target_age` column (INTEGER, nullable) to `stories` table.
    -   [ ] Add `language` column (TEXT, default 'en') to `stories` table.
    -   [ ] Add `character_ids` column (ARRAY of UUID, `uuid[]`, nullable) to `stories` table.
    -   [ ] Verify `pages` column is JSONB and can store `[{ "page": int, "description": str | null, "text": str | null, "image_prompt": str | null, "image_url": str | null, "characters_on_page": list[str] | null }]`.
-   [ ] **Pydantic Models (`src/models/story.py`):**
    -   [ ] Add `status`, `input_prompt`, `target_age`, `language`, `character_ids` fields to `Story` model.
    -   [ ] Define `StoryPageProgress` TypedDict/Pydantic model for the structure within the `pages` list.
    -   [x] Update `Story.pages` to use `List[StoryPageProgress]`.
-   [ ] **Trigger Endpoint (`src/routes/stories.py` - `trigger_story_generation`):**
    -   [ ] Remove `generation_id` variable.
    -   [ ] Perform initial `INSERT` into `stories` table with basic info (`family_id`, `title`, `input_prompt`, `character_ids`, `target_age`, `language`, status='INITIALIZING', pages=[]).
    -   [ ] Retrieve the new `story_id` from the insert response.
    -   [ ] Pass `story_id` (and `characters_info`) to `run_story_generation` background task.
    -   [ ] Return `{"story_id": story_id}` from the endpoint.
-   [x] **Trigger Endpoint (`src/routes/stories.py` - `trigger_story_generation`):**
    -   [x] Remove `generation_id` variable.
    -   [x] Perform initial `INSERT` into `stories` table with basic info (`family_id`, `title`, `input_prompt`, `character_ids`, `target_age`, `language`, status='INITIALIZING', pages=[]).
    -   [x] Retrieve the new `story_id` from the insert response.
    -   [x] Pass `story_id` (and `characters_info`) to `run_story_generation` background task.
    -   [x] Return `{"story_id": story_id}` from the endpoint.
-   [ ] **LangGraph Core (`src/graphs/story_generator.py`):**
    -   [ ] Remove `SqliteSaver` / `MemorySaver` import and usage.
    -   [ ] Compile graph without `checkpointer`.
    -   [ ] Update `StoryGenerationState` (simplify, must include `story_id`, possibly `characters_info`).
    -   [ ] Update `run_story_generation` function:
        -   [ ] Accept `story_id: str`, `characters_info: List[CharacterInfo]`.
        -   [ ] Update story status to `OUTLINING` before `astream`.
        -   [ ] Prepare initial input for `astream` (incl. `story_id`, context).
        -   [ ] Invoke `astream` without `config`.
        -   [ ] Update story status to `COMPLETED` on success / `FAILED` on error after `astream`.
    -   [ ] Refactor Graph Nodes (use `story_id` to fetch/update DB):
        -   [ ] `generate_initial_outline`: Update DB `pages` with descriptions, set status=`GENERATING_PAGES`.
        -   [ ] `write_page_content`: Get current page `N`, update `pages[N-1].text`, `pages[N-1].characters_on_page` in DB.
        -   [ ] `generate_image_prompt`: Update `pages[N-1].image_prompt` in DB.
        -   [ ] `generate_page_image`: Update `pages[N-1].image_url` in DB.
        -   [ ] Ensure WebSocket status messages (`send_ws_status`) use `story_id` and are sent after DB updates.
    -   [ ] Remove `save_story_to_db` node.
    -   [ ] Refactor `should_continue_writing` conditional edge (fetch story from DB, check `pages` against outline length).
-   [ ] **Remove Old Endpoints (`src/routes/stories.py`):**
    -   [ ] Remove `/generation/{generation_id}/state` endpoint.
    -   [ ] Remove `/generation/{generation_id}/resume` endpoint.

## Phase 2: Frontend Changes

-   [ ] **API Client (`src/api/client.ts`):**
    -   [ ] Update `generateStory` to expect `{ story_id: string }` response.
    -   [ ] Remove `fetchGenerationState`, `resumeStory`.
    -   [ ] Ensure `fetchStoryById` exists and works correctly.
+   [x] **API Client (`src/api/client.ts`):**
+     -   [x] Update `generateStory` to expect `{ story_id: string }` response.
+     -   [x] Remove `fetchGenerationState`, `resumeStory`.
+     -   [x] Ensure `fetchStoryById` exists and works correctly.
-   [ ] **Story Generation Page (`src/pages/StoryGenerationPage.tsx`):**
    -   [ ] Update `handleSubmit` to receive `{ story_id: string }`.
    -   [ ] Navigate to `/stories/{story_id}`.
+   [x] **Story Generation Page (`src/pages/StoryGenerationPage.tsx`):**
+     -   [x] Update `handleSubmit` to receive `{ story_id: string }`.
+     -   [x] Navigate to `/stories/{story_id}`.
-   [ ] **Story Progress/Viewer Page (`src/pages/StoryProgressPage.tsx` or `StoryViewerPage.tsx`):**
    -   [ ] Rename/Refactor as needed (e.g., `StoryViewerPage`).
    -   [ ] Get `story_id` from `useParams`.
    -   [ ] Fetch initial state using `api.fetchStoryById(story_id)`.
    -   [ ] Implement polling or use WebSocket messages to trigger refetches via `fetchStoryById`.
    -   [ ] Update WebSocket connection to use `story_id`.
    -   [ ] Update UI rendering based on fetched story data (`status`, `pages`).
    -   [ ] Remove old resume logic.

## Phase 3: Resuming (Future)

-   [ ] Design resume logic (e.g., endpoint that fetches story, checks status, re-adds background task).
-   [ ] Implement backend resume endpoint.
-   [ ] Implement frontend resume button/logic. 
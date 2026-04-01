# Implementation Plan for `run_story_generation_task`

This document outlines the step-by-step implementation plan for the background task responsible for generating stories in `tuck-in-tales-backend/src/routes/stories.py`.

**Function Signature:** `async def run_story_generation_task(family_id: UUID, character_ids: List[UUID], prompt: str | None, language: str, supabase_client: Client)`

## Implementation Steps

- [x] **1. Setup & Logging:**
    - [x] Add initial log message indicating task start with parameters.
    - [x] Initialize OpenAI client (or other LLM/Image clients) using credentials from settings/environment variables.
    - [x] Wrap the entire process in a `try...except` block for top-level error catching.

- [x] **2. Fetch Character Details:**
    - [x] Use `supabase_client` to query the `characters` table.
    - [x] Filter by `family_id` and the provided `character_ids` list.
    - [x] Select relevant fields (e.g., `id`, `name`, `bio`, `avatar_url`).
    - [x] Handle cases where characters are not found or don't belong to the family (log warning/error, maybe raise exception if critical).
    - [x] Store fetched character details (e.g., in a list of dictionaries or Pydantic objects).

- [x] **3. Construct Story Prompt for LLM:**
    - [x] Create a base system prompt explaining the task (e.g., "You are a children's story writer...").
    - [x] Incorporate fetched character names and bios into the prompt (e.g., "The story should feature characters: Alice (a brave rabbit), Bob (a sleepy bear)...").
    - [x] Include the target `language` in the instructions.
    - [x] If a user `prompt` is provided, append it to the main prompt (e.g., "The user wants the story to be about: [user prompt]").
    - [x] Specify the desired output format (e.g., JSON with keys like `title` and `pages`, where `pages` is a list of strings, one per page).
    - [x] Consider adding constraints like approximate story length or number of pages.

- [x] **4. Call LLM for Story Text Generation:**
    - [x] Use the initialized LLM client (e.g., `openai.chat.completions.create`).
    - [x] Send the constructed prompt.
    - [x] Parse the response to extract the generated `title` and `pages` (list of text strings).
    - [x] Add error handling for the API call and response parsing.

- [x] **5. Process Story Pages (Image Generation & Upload):**
    - [x] Create a unique `story_id` (UUID) for this new story.
    - [x] Prepare an empty list to store the final page data (text + image URL).
    - [x] Loop through the generated text `pages` with their index:
        - [x] **a. Construct Image Prompt:** Create a prompt for the image model (e.g., DALL-E) based on the page's text content. Keep it concise and descriptive.
        - [x] **b. Call Image Model:** Use the image generation client (e.g., `openai.images.generate`) to create an image based on the prompt.
        - [x] **c. Download Image Data:** The API might return a URL or base64 data. If it's a URL, download the image content (e.g., using `httpx`).
        - [x] **d. Define Storage Path:** Create a unique path for the image in Supabase storage (e.g., `f"{family_id}/{story_id}/page_{index}.png"`).
        - [x] **e. Upload Image:** Use `supabase_client.storage.from_("story-images").upload()` to upload the image data to the defined path. Set appropriate content type.
        - [x] **f. Get Public URL:** Use `supabase_client.storage.from_("story-images").get_public_url()` to get the public URL for the uploaded image.
        - [x] **g. Store Page Data:** Append a dictionary `{"text": page_text, "image_url": public_image_url}` to the final pages list.
        - [x] **h. Error Handling:** Add `try...except` blocks for image generation, download, and upload steps.

- [x] **6. Save Story to Database:**
    - [x] Construct the final story data dictionary to insert into the `stories` table:
        - `id`: The generated `story_id`.
        - `family_id`: The provided `family_id`.
        - `title`: The generated title from the LLM.
        - `pages`: The list of page dictionaries (text + image URL) compiled in step 5.
        - `language`: The provided `language`.
    - [x] Use `supabase_client.table("stories").insert()` to save the record.
    - [x] Add error handling for the database insert operation.

- [x] **7. Final Logging & Cleanup:**
    - [x] Log successful completion of the task, including the new story ID.
    - [x] In the top-level `except` block, log any caught errors comprehensively.
    - [ ] Consider cleanup actions on failure if necessary (e.g., deleting partially uploaded images). (TODO) 
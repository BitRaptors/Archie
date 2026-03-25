# Stories API

This document outlines the API endpoints related to stories.

## `POST /api/stories/generate`

Triggers the background generation of a new story based on selected characters and an optional prompt.

**Request Body** (`application/json`):
```json
{
  "character_ids": ["uuid_char_1", "uuid_char_2"], // Required: Array of character UUIDs
  "prompt": "A funny adventure in the enchanted forest", // Optional: User-provided prompt (max 1000 chars)
  "language": "en" // Optional: Language code (defaults to 'en' if omitted)
}
```

**Response Body (Success - 202 Accepted)**:
Indicates that the generation process has started.
```json
{
  "message": "Story generation started successfully."
}
```

**Error Responses**:
- **400 Bad Request**: If `character_ids` is empty or invalid, or prompt is too long.
- **401 Unauthorized**: If the user is not authenticated.
- **403 Forbidden**: If the user does not belong to a family or tries to use characters from another family (validation should happen in background task ideally, but basic checks can be here).
- **500 Internal Server Error**: If there's an issue queueing the background task.

---

## Story Schemas

Refer to `src/models/story.py` for detailed Pydantic models (`Story`, `StoryPage`, `StoryGenerationRequest`).

*Note: Endpoints for retrieving generated stories (`GET /api/stories/` and `GET /api/stories/{story_id}`) are not yet implemented.* 
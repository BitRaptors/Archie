# SSE Streaming MVP Design

**Date**: 2026-02-18
**Status**: Approved
**Goal**: Replace WebSocket streaming with SSE, simplify family/character UI, enable token-level story streaming with character image references.

---

## 1. SSE Streaming Architecture

### Backend

New SSE endpoints using FastAPI `StreamingResponse`:

- `GET /api/stories/{story_id}/stream` - Story generation streaming
- `GET /api/characters/{character_id}/avatar/stream` - Avatar generation streaming

Both require `Authorization: Bearer <token>` header and return `text/event-stream`.

### SSE Event Format

```
event: status
data: {"step": "outlining", "message": "Creating story outline..."}

event: page_start
data: {"page": 1, "total_pages": 4}

event: text_chunk
data: {"page": 1, "chunk": "Once upon a time "}

event: page_image
data: {"page": 1, "image_url": "https://...supabase.../page_1.png"}

event: error
data: {"message": "Generation failed", "code": "LLM_ERROR"}

event: done
data: {"story_id": "..."}
```

### Async Queue Pattern

- LangGraph runs in an `asyncio.Task`
- An `asyncio.Queue` bridges graph nodes to SSE generator
- Each graph node pushes SSE events to the queue
- SSE generator reads from queue and yields formatted events

### Frontend

`fetch()` API with `ReadableStream` reader (not `EventSource`, which doesn't support custom headers):

```typescript
const response = await fetch(url, {
  headers: { Authorization: `Bearer ${token}` }
});
const reader = response.body.getReader();
// Parse SSE events from chunks
```

Custom hook: `useStoryStream(storyId)` returns `{ status, pages, error, isComplete }`.

---

## 2. Family Member = Character Model

### Data Model

No schema changes. The existing `characters` table serves as family members:
- `name`, `bio`, `birthdate`, `photo_paths`, `avatar_url`, `visual_description`
- `family_id` links to family
- `family_main_characters` junction table for default story characters

### UI Flow

**Family Page** (`/family`) - Main hub:
- Family name, join code
- Family members list (= characters)
- "Add family member" button -> character creation form
- Each member shows: name, age, avatar (or placeholder)
- "Generate avatar" button when photo exists but no avatar

**Add/Edit Member** (`/family/members/new`, `/family/members/:id/edit`):
- Name (required)
- Birth date
- Photo upload (optional, for avatar generation)
- Bio/description

**Story Generation** (`/stories/generate`):
- Family member selection (checkboxes with avatars)
- Story prompt
- Language selection
- "Generate story" -> SSE stream page

---

## 3. Story Generation Flow with SSE

### Full Flow

```
User: prompt + selected family members
  -> POST /api/stories/generate -> { story_id } (202 Accepted)
  -> GET /api/stories/{story_id}/stream -> SSE connection

LangGraph execution:
  1. determine_language
  2. download_character_avatars (from Supabase storage)
  3. generate_outline (LLM) -> SSE: status + outline
  4. write_page_content (LLM streaming) -> SSE: text_chunk tokens
  5. generate_image_prompt (LLM) -> SSE: status
  6. generate_page_image (Gemini/OpenAI + character avatars as reference) -> SSE: page_image
  7. Repeat 4-6 for each page
  8. -> SSE: done
```

### Character Images -> AI

The current implementation already downloads character avatars and passes them as reference images. This stays:
1. Selected characters' `avatar_url`s loaded at story start
2. Character visual descriptions included in image prompts
3. Avatar bytes passed as reference images to Gemini/OpenAI

### Error Handling

- SSE connection drop: frontend reconnects with `Last-Event-ID`
- Generation failure: `event: error` sent + story status = FAILED in DB
- Timeout: 5 min max generation time

---

## 4. What Changes

| Component | Change |
|-----------|--------|
| WebSocket (socket.io) | **Remove** - replaced by SSE |
| SSE endpoint (story) | **New** - `GET /api/stories/{id}/stream` |
| SSE endpoint (avatar) | **New** - `GET /api/characters/{id}/avatar/stream` |
| LangGraph nodes | **Modify** - write to queue instead of WebSocket |
| Frontend streaming | **New** - `useStoryStream` hook with fetch-based SSE |
| Family/Character UI | **Modify** - simplified "family member" UI |
| Data model | **Unchanged** - characters table stays |
| socket.io dependency | **Remove** from frontend package.json |
| websockets.py utility | **Remove/Replace** with SSE utility |

---

## 5. Avatar Generation SSE

Similar pattern to story streaming:

```
event: status
data: {"step": "analyzing_photo", "message": "Analyzing photo..."}

event: status
data: {"step": "generating_avatar", "message": "Generating avatar..."}

event: complete
data: {"avatar_url": "https://...supabase.../avatar.png"}

event: error
data: {"message": "Avatar generation failed"}
```

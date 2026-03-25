# SSE Streaming MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace WebSocket streaming with SSE, enable token-level story streaming, and simplify the family/character UI.

**Architecture:** FastAPI `StreamingResponse` with async generators on the backend, `fetch` + `ReadableStream` on the frontend. LangGraph nodes communicate with SSE generators via `asyncio.Queue`. The existing data model (characters table) is reused for family members.

**Tech Stack:** FastAPI, LangGraph, OpenAI (streaming), React, TypeScript, Supabase

---

### Task 1: Create SSE utility module (backend)

**Files:**
- Create: `tuck-in-tales-backend/src/utils/sse.py`

**Step 1: Create the SSE utility module**

```python
import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Registry of active SSE queues keyed by client_id (story_id or character_id)
_sse_queues: Dict[str, asyncio.Queue] = {}


def get_or_create_queue(client_id: str) -> asyncio.Queue:
    """Get existing queue or create a new one for the given client_id."""
    if client_id not in _sse_queues:
        _sse_queues[client_id] = asyncio.Queue()
        logger.info(f"SSE queue created for {client_id}")
    return _sse_queues[client_id]


def remove_queue(client_id: str):
    """Remove the queue for the given client_id."""
    if client_id in _sse_queues:
        del _sse_queues[client_id]
        logger.info(f"SSE queue removed for {client_id}")


async def send_sse_event(client_id: str, event: str, data: Dict[str, Any]):
    """Push an SSE event to the queue for the given client_id."""
    queue = _sse_queues.get(client_id)
    if queue:
        await queue.put({"event": event, "data": data})
    else:
        logger.warning(f"No SSE queue found for {client_id}, event '{event}' dropped")


def format_sse(event: str, data: Dict[str, Any]) -> str:
    """Format a dict as an SSE message string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def sse_generator(client_id: str, timeout: float = 300.0) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE-formatted strings from the queue.
    Terminates on 'done' or 'error' events, or after timeout.
    """
    queue = get_or_create_queue(client_id)
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=timeout)
                event = msg["event"]
                data = msg["data"]
                yield format_sse(event, data)
                if event in ("done", "error", "complete"):
                    break
            except asyncio.TimeoutError:
                yield format_sse("error", {"message": "Stream timeout"})
                break
    finally:
        remove_queue(client_id)
```

**Step 2: Commit**

```bash
git add tuck-in-tales-backend/src/utils/sse.py
git commit -m "feat: add SSE utility module for streaming events"
```

---

### Task 2: Add SSE story streaming endpoint (backend)

**Files:**
- Modify: `tuck-in-tales-backend/src/routes/stories.py`

**Step 1: Add the SSE stream endpoint**

Add these imports at the top of `stories.py`:
```python
from fastapi.responses import StreamingResponse
from src.utils.sse import sse_generator, get_or_create_queue
```

Add this new endpoint after the existing `generate_story` endpoint:

```python
@router.get("/{story_id}/stream")
async def stream_story_generation(
    story_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """SSE endpoint to stream story generation progress in real-time."""
    family_id = get_required_family_id(current_supabase_user)

    # Verify story belongs to this family
    response = supabase.table("stories").select("id, status")\
        .eq("id", str(story_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()
    if response.data is None:
        raise HTTPException(status_code=404, detail="Story not found or access denied")

    # If already completed/failed, return current status as single event
    story_status = response.data.get("status")
    if story_status in ("COMPLETED", "FAILED"):
        async def single_event():
            event = "done" if story_status == "COMPLETED" else "error"
            data = {"story_id": str(story_id), "status": story_status}
            yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        return StreamingResponse(single_event(), media_type="text/event-stream")

    # Ensure queue exists for this story (graph nodes will push to it)
    get_or_create_queue(str(story_id))

    return StreamingResponse(
        sse_generator(str(story_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

Add `import json` if not already imported.

**Step 2: Commit**

```bash
git add tuck-in-tales-backend/src/routes/stories.py
git commit -m "feat: add SSE streaming endpoint for story generation"
```

---

### Task 3: Add SSE avatar streaming endpoint (backend)

**Files:**
- Modify: `tuck-in-tales-backend/src/routes/characters.py`

**Step 1: Add the SSE stream endpoint**

Add imports:
```python
from fastapi.responses import StreamingResponse
from src.utils.sse import sse_generator, get_or_create_queue
import json
```

Add this new endpoint after `generate_character_avatar_endpoint`:

```python
@router.get("/{character_id}/avatar/stream")
async def stream_avatar_generation(
    character_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """SSE endpoint to stream avatar generation progress."""
    family_id = get_required_family_id(current_supabase_user)

    # Verify character belongs to family
    response = supabase.table("characters").select("id, avatar_url")\
        .eq("id", str(character_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()
    if response.data is None:
        raise HTTPException(status_code=404, detail="Character not found or access denied")

    get_or_create_queue(str(character_id))

    return StreamingResponse(
        sse_generator(str(character_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
```

**Step 2: Commit**

```bash
git add tuck-in-tales-backend/src/routes/characters.py
git commit -m "feat: add SSE streaming endpoint for avatar generation"
```

---

### Task 4: Refactor story_generator.py to use SSE queue (backend)

**Files:**
- Modify: `tuck-in-tales-backend/src/graphs/story_generator.py`

**Step 1: Replace WebSocket imports and helpers with SSE**

Replace the import:
```python
from src.utils.websockets import manager
```
with:
```python
from src.utils.sse import send_sse_event
```

Replace the three WebSocket helper functions (`send_ws_message`, `send_ws_status`, `send_ws_error`) with SSE versions:

```python
async def send_sse_status(story_id: str | None, message: str, step: str | None = None, page: int | None = None, total_pages: int | None = None):
    if story_id:
        payload = {"message": message}
        if step: payload["step"] = step
        if page is not None: payload["page"] = page
        if total_pages is not None: payload["total_pages"] = total_pages
        await send_sse_event(story_id, "status", payload)

async def send_sse_error(story_id: str | None, message: str, step: str | None = None, page: int | None = None):
    if story_id:
        payload = {"message": message}
        if step: payload["step"] = step
        if page is not None: payload["page"] = page
        await send_sse_event(story_id, "error", payload)
```

**Step 2: Update all node functions**

Do a search-and-replace across the file:
- `send_ws_message(story_id, "outline",` → `send_sse_event(story_id, "outline",`
- `send_ws_message(story_id, "page_text",` → `send_sse_event(story_id, "page_text",`
- `send_ws_message(story_id, "image_prompt",` → `send_sse_event(story_id, "image_prompt",`
- `send_ws_message(story_id, "page_image",` → `send_sse_event(story_id, "page_image",`
- `send_ws_status(` → `send_sse_status(`
- `send_ws_error(` → `send_sse_error(`
- `await send_ws_message(` → `await send_sse_event(`

**Step 3: Enable LLM streaming in write_page_content**

In the `write_page_content` function, replace the non-streaming LLM call with a streaming one. Find this block (~line 458-469):

```python
llm = ChatOpenAI(
    model=settings.OPENAI_CHAT_MODEL,
    temperature=0.7,
    max_tokens=350,
    openai_api_key=settings.OPENAI_API_KEY
)
await send_sse_status(story_id, f"Calling LLM for page {page_number_to_write} text...", step=step_name, page=page_number_to_write, total_pages=total_pages)
response = await llm.ainvoke(messages)

page_text = response.content
```

Replace with:

```python
llm = ChatOpenAI(
    model=settings.OPENAI_CHAT_MODEL,
    temperature=0.7,
    max_tokens=350,
    openai_api_key=settings.OPENAI_API_KEY,
    streaming=True
)
await send_sse_status(story_id, f"Writing page {page_number_to_write} text...", step=step_name, page=page_number_to_write, total_pages=total_pages)

# Send page_start event
await send_sse_event(story_id, "page_start", {"page": page_number_to_write, "total_pages": total_pages})

# Stream tokens
page_text = ""
async for chunk in llm.astream(messages):
    token = chunk.content
    if token:
        page_text += token
        await send_sse_event(story_id, "text_chunk", {"page": page_number_to_write, "chunk": token})
```

**Step 4: Update run_story_generation to send 'done' event**

In `run_story_generation`, after updating status to COMPLETED (~line 918-919):

```python
await update_story_data(story_id, {"status": "COMPLETED"})
await send_sse_event(story_id, "done", {"story_id": story_id})
```

Remove the old `send_ws_status` completion line.

**Step 5: Commit**

```bash
git add tuck-in-tales-backend/src/graphs/story_generator.py
git commit -m "feat: refactor story generator to use SSE with token streaming"
```

---

### Task 5: Refactor avatar_generator.py to use SSE queue (backend)

**Files:**
- Modify: `tuck-in-tales-backend/src/graphs/avatar_generator.py`

**Step 1: Replace WebSocket import with SSE**

Replace:
```python
from src.utils.websockets import send_avatar_update
```
with:
```python
from src.utils.sse import send_sse_event
```

**Step 2: Replace all send_avatar_update calls**

Create a local helper or replace inline. Each `send_avatar_update(character_id, status, message, ...)` becomes:

```python
await send_sse_event(str(character_id), "status", {"step": status, "message": message})
```

For error cases:
```python
await send_sse_event(str(character_id), "error", {"message": error_msg})
```

For completion in `run_avatar_generation_task` (in `characters.py`):
```python
await send_sse_event(str(character_id), "complete", {"avatar_url": final_state.get('final_avatar_path')})
```

**Step 3: Update run_avatar_generation_task in characters.py**

In `tuck-in-tales-backend/src/routes/characters.py`, update the `run_avatar_generation_task` function to use `send_sse_event` instead of `send_avatar_update`:

Replace import:
```python
from src.utils.websockets import send_avatar_update
```
with:
```python
from src.utils.sse import send_sse_event
```

Update the success/error messages in the function to use `send_sse_event`.

**Step 4: Commit**

```bash
git add tuck-in-tales-backend/src/graphs/avatar_generator.py tuck-in-tales-backend/src/routes/characters.py
git commit -m "feat: refactor avatar generator to use SSE instead of WebSocket"
```

---

### Task 6: Remove WebSocket code from backend

**Files:**
- Modify: `tuck-in-tales-backend/src/main.py`
- Delete or gut: `tuck-in-tales-backend/src/utils/websockets.py`

**Step 1: Clean up main.py**

Remove:
- The `from src.utils.websockets import manager` import
- The entire `progress_websocket_endpoint` function (lines 65-94)
- The entire `avatar_websocket_endpoint` function (lines 96-140)
- The `WebSocket`, `WebSocketDisconnect` imports from fastapi
- The `Query`, `status` imports if only used for WebSocket (check first)
- The `json` import if only used for WebSocket (check - it's used elsewhere)

Keep:
- Everything else (CORS, routers, root endpoint)

**Step 2: Remove or empty websockets.py**

Delete the file `tuck-in-tales-backend/src/utils/websockets.py` entirely, since no code should reference it anymore.

**Step 3: Verify no remaining imports of websockets module**

Search the codebase for `from src.utils.websockets` - there should be none after Tasks 4 and 5.

**Step 4: Commit**

```bash
git add tuck-in-tales-backend/src/main.py
git rm tuck-in-tales-backend/src/utils/websockets.py
git commit -m "chore: remove WebSocket code from backend"
```

---

### Task 7: Create useSSEStream hook (frontend)

**Files:**
- Create: `tuck-in-tales-frontend/src/hooks/useSSEStream.ts`

**Step 1: Create the SSE streaming hook**

```typescript
import { useState, useEffect, useRef, useCallback } from 'react';
import { auth } from '@/firebaseConfig';

interface SSEEvent {
  event: string;
  data: any;
}

interface UseSSEStreamOptions {
  url: string;
  enabled?: boolean;
  onEvent?: (event: SSEEvent) => void;
  onDone?: () => void;
  onError?: (error: string) => void;
}

interface UseSSEStreamReturn {
  isConnected: boolean;
  error: string | null;
  disconnect: () => void;
}

export function useSSEStream({
  url,
  enabled = true,
  onEvent,
  onDone,
  onError,
}: UseSSEStreamOptions): UseSSEStreamReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const disconnect = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsConnected(false);
  }, []);

  useEffect(() => {
    if (!enabled || !url) return;

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const connect = async () => {
      try {
        const user = auth.currentUser;
        if (!user) {
          setError('Not authenticated');
          return;
        }

        const token = await user.getIdToken();
        const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';
        const fullUrl = `${baseURL}${url}`;

        const response = await fetch(fullUrl, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Accept': 'text/event-stream',
          },
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        setIsConnected(true);
        setError(null);

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep incomplete line in buffer

          let currentEvent = '';
          let currentData = '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              currentData = line.slice(6).trim();
            } else if (line === '' && currentEvent && currentData) {
              // Empty line = end of event
              try {
                const parsedData = JSON.parse(currentData);
                const sseEvent: SSEEvent = { event: currentEvent, data: parsedData };

                onEvent?.(sseEvent);

                if (currentEvent === 'done' || currentEvent === 'complete') {
                  onDone?.();
                  disconnect();
                  return;
                }
                if (currentEvent === 'error') {
                  onError?.(parsedData.message || 'Stream error');
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', currentData, e);
              }
              currentEvent = '';
              currentData = '';
            }
          }
        }
      } catch (err: any) {
        if (err.name === 'AbortError') return;
        console.error('SSE stream error:', err);
        setError(err.message || 'Stream connection failed');
        onError?.(err.message || 'Stream connection failed');
      } finally {
        setIsConnected(false);
      }
    };

    connect();

    return () => {
      controller.abort();
      setIsConnected(false);
    };
  }, [url, enabled]); // intentionally minimal deps - callbacks are refs

  return { isConnected, error, disconnect };
}
```

**Step 2: Commit**

```bash
git add tuck-in-tales-frontend/src/hooks/useSSEStream.ts
git commit -m "feat: add useSSEStream hook for fetch-based SSE streaming"
```

---

### Task 8: Create useStoryStream hook (frontend)

**Files:**
- Create: `tuck-in-tales-frontend/src/hooks/useStoryStream.ts`

**Step 1: Create the story-specific streaming hook**

```typescript
import { useState, useCallback, useRef } from 'react';
import { useSSEStream } from './useSSEStream';

interface StoryPage {
  page: number;
  description?: string;
  text: string;
  imageUrl?: string;
  charactersOnPage?: string[];
}

interface StoryStreamState {
  status: string;
  statusMessage: string;
  title?: string;
  pages: StoryPage[];
  isComplete: boolean;
  isFailed: boolean;
  error: string | null;
}

export function useStoryStream(storyId: string | undefined) {
  const [state, setState] = useState<StoryStreamState>({
    status: 'connecting',
    statusMessage: 'Connecting to story stream...',
    pages: [],
    isComplete: false,
    isFailed: false,
    error: null,
  });

  const pagesRef = useRef<StoryPage[]>([]);

  const handleEvent = useCallback((event: { event: string; data: any }) => {
    const { event: eventType, data } = event;

    switch (eventType) {
      case 'status':
        setState(prev => ({
          ...prev,
          status: data.step || prev.status,
          statusMessage: data.message || prev.statusMessage,
        }));
        break;

      case 'outline':
        if (data.outline_pages) {
          const outlinePages: StoryPage[] = data.outline_pages.map((p: any) => ({
            page: p.page,
            description: p.description,
            text: '',
          }));
          pagesRef.current = outlinePages;
          setState(prev => ({
            ...prev,
            pages: [...outlinePages],
            statusMessage: `Outline ready (${data.total_pages} pages)`,
          }));
        }
        break;

      case 'page_start':
        setState(prev => ({
          ...prev,
          statusMessage: `Writing page ${data.page}...`,
        }));
        break;

      case 'text_chunk': {
        const pageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (pageIdx >= 0) {
          pagesRef.current[pageIdx].text += data.chunk;
          setState(prev => ({
            ...prev,
            pages: [...pagesRef.current],
          }));
        }
        break;
      }

      case 'page_text': {
        const pageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (pageIdx >= 0) {
          pagesRef.current[pageIdx].text = data.text;
          pagesRef.current[pageIdx].charactersOnPage = data.characters_on_page;
          setState(prev => ({
            ...prev,
            pages: [...pagesRef.current],
          }));
        }
        break;
      }

      case 'page_image': {
        const pageIdx = pagesRef.current.findIndex(p => p.page === data.page);
        if (pageIdx >= 0) {
          pagesRef.current[pageIdx].imageUrl = data.image_url;
          setState(prev => ({
            ...prev,
            pages: [...pagesRef.current],
            statusMessage: `Page ${data.page} image ready`,
          }));
        }
        break;
      }

      case 'done':
        setState(prev => ({
          ...prev,
          isComplete: true,
          status: 'completed',
          statusMessage: 'Story generation complete!',
        }));
        break;

      case 'error':
        setState(prev => ({
          ...prev,
          isFailed: true,
          error: data.message || 'Generation failed',
          statusMessage: data.message || 'Generation failed',
        }));
        break;
    }
  }, []);

  const handleDone = useCallback(() => {
    setState(prev => ({ ...prev, isComplete: true }));
  }, []);

  const handleError = useCallback((msg: string) => {
    setState(prev => ({ ...prev, error: msg, isFailed: true }));
  }, []);

  const { isConnected } = useSSEStream({
    url: storyId ? `/stories/${storyId}/stream` : '',
    enabled: !!storyId,
    onEvent: handleEvent,
    onDone: handleDone,
    onError: handleError,
  });

  return {
    ...state,
    isConnected,
  };
}
```

**Step 2: Commit**

```bash
git add tuck-in-tales-frontend/src/hooks/useStoryStream.ts
git commit -m "feat: add useStoryStream hook for real-time story generation"
```

---

### Task 9: Rewrite StoryProgressPage with SSE (frontend)

**Files:**
- Modify: `tuck-in-tales-frontend/src/pages/StoryProgressPage.tsx`

**Step 1: Rewrite the component**

Replace the entire file content. Key changes:
- Remove all WebSocket code (ws ref, WS_URL, socket connection/listeners)
- Remove polling interval code
- Use `useStoryStream` hook instead
- Keep the existing UI rendering structure (renderStatus, renderOutline, renderPages)
- The page renders text as it streams in (character by character)

```tsx
import React, { useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ExclamationTriangleIcon, CheckCircledIcon } from '@radix-ui/react-icons';
import { Loader2 } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { useStoryStream } from '@/hooks/useStoryStream';

export default function StoryProgressPage() {
  const { storyId } = useParams<{ storyId: string }>();
  const navigate = useNavigate();
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const {
    status,
    statusMessage,
    pages,
    isComplete,
    isFailed,
    error,
    isConnected,
  } = useStoryStream(storyId);

  const totalPages = pages.length;
  const pagesWithImage = pages.filter(p => p.imageUrl).length;
  const progressValue = totalPages > 0 ? (pagesWithImage / totalPages) * 100 : 0;

  const renderStatus = () => {
    if (isComplete) {
      return (
        <div className="flex items-center space-x-2 text-green-600">
          <CheckCircledIcon className="h-5 w-5" />
          <span className="font-semibold">Story Generation Complete!</span>
          <Button variant="link" size="sm" onClick={() => navigate(`/stories/${storyId}`)}>
            View Story
          </Button>
        </div>
      );
    }
    if (isFailed) {
      return (
        <Alert variant="destructive" className="mb-4">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Generation Failed</AlertTitle>
          <AlertDescription>{error || 'An error occurred during generation.'}</AlertDescription>
        </Alert>
      );
    }
    if (error && !isFailed) {
      return (
        <Alert variant="destructive" className="mb-4">
          <ExclamationTriangleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      );
    }

    return (
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {isConnected && <Loader2 className="h-4 w-4 animate-spin" />}
        <span className="text-sm font-medium">{statusMessage}</span>
        {totalPages > 0 && (
          <>
            <Progress value={progressValue} className="w-full sm:w-1/3 flex-grow" />
            <span className="text-xs text-muted-foreground">{pagesWithImage} / {totalPages} Pages Complete</span>
          </>
        )}
      </div>
    );
  };

  const renderOutline = () => {
    if (pages.length === 0) return null;
    const outlinePages = pages.filter(p => p.description);
    if (outlinePages.length === 0) return null;

    return (
      <Card className="my-4 bg-muted/30">
        <CardHeader><CardTitle className="text-base">Story Outline</CardTitle></CardHeader>
        <CardContent>
          <ul className="list-disc pl-5 space-y-1 text-sm">
            {outlinePages.map(page => (
              <li key={page.page}><strong>Page {page.page}:</strong> {page.description}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    );
  };

  const renderPages = () => {
    if (pages.length === 0 && !isComplete) {
      return <p className="text-sm text-muted-foreground text-center my-4">Waiting for story pages...</p>;
    }

    return pages.map(page => (
      <div key={page.page} ref={el => { pageRefs.current[page.page] = el; }}>
        <Card className="my-4 overflow-hidden">
          <CardHeader>
            <CardTitle>Page {page.page}</CardTitle>
            {page.description && <CardDescription>{page.description}</CardDescription>}
          </CardHeader>
          <CardContent className="space-y-4">
            {page.text ? (
              <p className="text-sm whitespace-pre-wrap">{page.text}</p>
            ) : (
              !isComplete && !isFailed ? (
                <Skeleton className="h-20 w-full" />
              ) : (
                <p className="text-sm text-muted-foreground italic">Content generation pending or failed.</p>
              )
            )}
            {page.imageUrl ? (
              <img
                src={page.imageUrl}
                alt={`Illustration for page ${page.page}`}
                className="rounded-md border aspect-video sm:aspect-square object-contain w-full max-w-md mx-auto block bg-muted"
                loading="lazy"
              />
            ) : page.text ? (
              <div className="flex justify-center">
                {!isComplete && !isFailed ? (
                  <Skeleton className="h-64 w-full max-w-md rounded-md bg-muted" />
                ) : (
                  <p className="text-sm text-muted-foreground italic">Image generation pending or failed.</p>
                )}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    ));
  };

  return (
    <div className="container mx-auto p-4 max-w-3xl">
      <Card>
        <CardHeader>
          <CardTitle>Story Generation Progress</CardTitle>
          <CardDescription>Tracking story ID: {storyId || 'N/A'}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 sticky top-16 sm:top-0 bg-background/95 backdrop-blur py-3 z-10 border-b">
            {renderStatus()}
          </div>
          {renderOutline()}
          <div className="space-y-4">
            {renderPages()}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add tuck-in-tales-frontend/src/pages/StoryProgressPage.tsx
git commit -m "feat: rewrite StoryProgressPage with SSE streaming"
```

---

### Task 10: Remove socket.io from frontend

**Files:**
- Modify: `tuck-in-tales-frontend/package.json`
- Remove any remaining WebSocket references from frontend code

**Step 1: Uninstall socket.io-client**

```bash
cd tuck-in-tales-frontend && npm uninstall socket.io-client
```

**Step 2: Search for remaining WebSocket/socket.io references**

Search for `socket.io`, `WebSocket`, `ws://`, `WS_URL` in the frontend code. Remove any remaining references in:
- `StoryProgressPage.tsx` (already replaced in Task 9)
- Any other pages that might use WebSocket (e.g., `CharacterDetailPage.tsx` for avatar progress)

**Step 3: Remove VITE_WS_URL from .env if present**

Check `tuck-in-tales-frontend/.env` and remove `VITE_WS_URL` if it exists.

**Step 4: Commit**

```bash
git add -A tuck-in-tales-frontend/
git commit -m "chore: remove socket.io dependency and WebSocket references from frontend"
```

---

### Task 11: Update CharacterDetailPage or avatar trigger to use SSE (frontend)

**Files:**
- Modify: whichever page triggers avatar generation (likely `CharacterDetailPage.tsx` or `CharacterCreationPage.tsx`)

**Step 1: Create useAvatarStream hook**

Create `tuck-in-tales-frontend/src/hooks/useAvatarStream.ts`:

```typescript
import { useState, useCallback } from 'react';
import { useSSEStream } from './useSSEStream';

interface AvatarStreamState {
  status: string;
  statusMessage: string;
  avatarUrl: string | null;
  isComplete: boolean;
  error: string | null;
}

export function useAvatarStream(characterId: string | undefined, enabled: boolean = false) {
  const [state, setState] = useState<AvatarStreamState>({
    status: 'idle',
    statusMessage: '',
    avatarUrl: null,
    isComplete: false,
    error: null,
  });

  const handleEvent = useCallback((event: { event: string; data: any }) => {
    const { event: eventType, data } = event;
    switch (eventType) {
      case 'status':
        setState(prev => ({
          ...prev,
          status: data.step || prev.status,
          statusMessage: data.message || prev.statusMessage,
        }));
        break;
      case 'complete':
        setState(prev => ({
          ...prev,
          isComplete: true,
          avatarUrl: data.avatar_url || null,
          statusMessage: 'Avatar generation complete!',
        }));
        break;
      case 'error':
        setState(prev => ({
          ...prev,
          error: data.message || 'Avatar generation failed',
          statusMessage: data.message || 'Failed',
        }));
        break;
    }
  }, []);

  const { isConnected } = useSSEStream({
    url: characterId ? `/characters/${characterId}/avatar/stream` : '',
    enabled: enabled && !!characterId,
    onEvent: handleEvent,
  });

  return { ...state, isConnected };
}
```

**Step 2: Integrate into the page that triggers avatar generation**

Find the page that calls `api.generateCharacterAvatar(characterId)` and after that call, enable the SSE stream to show progress. The exact integration depends on the current page structure - it should replace any WebSocket connection logic.

**Step 3: Commit**

```bash
git add tuck-in-tales-frontend/src/hooks/useAvatarStream.ts
git commit -m "feat: add useAvatarStream hook for SSE avatar generation progress"
```

---

### Task 12: Verify backend runs correctly

**Step 1: Start the backend**

```bash
cd tuck-in-tales-backend && poetry run uvicorn src.main:app --reload --port 8000
```

Expected: Server starts without import errors.

**Step 2: Check for any remaining references to removed modules**

```bash
grep -r "websockets" tuck-in-tales-backend/src/ --include="*.py"
grep -r "send_ws_" tuck-in-tales-backend/src/ --include="*.py"
grep -r "send_avatar_update" tuck-in-tales-backend/src/ --include="*.py"
```

Expected: No matches (all replaced with SSE equivalents).

**Step 3: Commit any fixes**

---

### Task 13: Verify frontend builds correctly

**Step 1: Build the frontend**

```bash
cd tuck-in-tales-frontend && npm run build
```

Expected: Build succeeds without TypeScript errors.

**Step 2: Check for remaining WebSocket references**

```bash
grep -r "socket.io\|WebSocket\|ws://" tuck-in-tales-frontend/src/ --include="*.ts" --include="*.tsx"
```

Expected: No matches.

**Step 3: Commit any fixes**

---

### Task 14: End-to-end smoke test

**Step 1: Start both servers**

Backend: `cd tuck-in-tales-backend && poetry run uvicorn src.main:app --reload --port 8000`
Frontend: `cd tuck-in-tales-frontend && npm run dev`

**Step 2: Test the flow**

1. Login
2. Go to Family page - verify family members (characters) display
3. Create a character if none exist
4. Upload a photo and trigger avatar generation - verify SSE progress
5. Go to Story Generation page - select characters, enter prompt
6. Submit - verify SSE stream shows progress with text appearing token-by-token
7. Verify story completion with images

**Step 3: Fix any issues found during testing**

**Step 4: Final commit**

```bash
git add -A
git commit -m "fix: address issues found during end-to-end testing"
```

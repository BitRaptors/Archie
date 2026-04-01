"""
SSE (Server-Sent Events) utility module.

Provides an async queue-based mechanism for streaming SSE events to clients.
This replaces WebSocket-based streaming with a simpler, more reliable SSE approach.

Usage:
    - Graph nodes call `send_sse_event(client_id, event, data)` to push events.
    - FastAPI endpoints use `sse_generator(client_id)` with StreamingResponse.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict

logger = logging.getLogger(__name__)

# Registry of asyncio.Queue objects keyed by client_id (story_id or character_id)
_queues: Dict[str, asyncio.Queue] = {}

# Events that signal the SSE stream should terminate
_TERMINAL_EVENTS = frozenset({"done", "error", "complete"})


def get_or_create_queue(client_id: str) -> asyncio.Queue:
    """Get an existing queue for client_id, or create a new one.

    Args:
        client_id: Unique identifier for the client (e.g. story_id or character_id).

    Returns:
        The asyncio.Queue associated with the client_id.
    """
    if client_id not in _queues:
        _queues[client_id] = asyncio.Queue()
        logger.info(f"Created SSE queue for client: {client_id}")
    return _queues[client_id]


def remove_queue(client_id: str) -> None:
    """Remove and discard the queue for client_id.

    Safe to call even if the queue does not exist.

    Args:
        client_id: Unique identifier for the client.
    """
    removed = _queues.pop(client_id, None)
    if removed is not None:
        logger.info(f"Removed SSE queue for client: {client_id}")
    else:
        logger.debug(f"No SSE queue to remove for client: {client_id}")


async def send_sse_event(
    client_id: str,
    event: str,
    data: Any,
) -> None:
    """Push an SSE event onto the queue for a given client.

    If no queue exists for the client_id yet, one is created automatically.
    This is the primary interface for graph nodes to emit streaming events.

    Args:
        client_id: Unique identifier for the client.
        event: The SSE event name (e.g. "chunk", "status", "done", "error").
        data: Payload to send. Will be JSON-serialized.
    """
    queue = get_or_create_queue(client_id)
    await queue.put({"event": event, "data": data})
    logger.debug(f"Enqueued SSE event '{event}' for client: {client_id}")


def format_sse(event: str, data: Any) -> str:
    """Format a dict as an SSE message string.

    Args:
        event: The SSE event name.
        data: Payload to serialize as JSON in the data field.

    Returns:
        A string in SSE wire format: ``event: {event}\\ndata: {json}\\n\\n``
    """
    json_data = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_data}\n\n"


async def sse_generator(
    client_id: str,
    timeout: float = 300.0,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted strings from the client queue.

    Intended for use with FastAPI's StreamingResponse::

        return StreamingResponse(
            sse_generator(story_id),
            media_type="text/event-stream",
        )

    The generator terminates when:
    - A terminal event ('done', 'error', 'complete') is received (yielded first).
    - The timeout is exceeded (an error event is yielded before terminating).
    - The consumer cancels / disconnects (cleanup runs in finally block).

    Args:
        client_id: Unique identifier for the client.
        timeout: Maximum time in seconds to keep the stream open. Defaults to 300.

    Yields:
        SSE-formatted message strings.
    """
    queue = get_or_create_queue(client_id)
    logger.info(f"SSE stream started for client: {client_id} (timeout={timeout}s)")

    try:
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"SSE stream timed out for client: {client_id}")
                yield format_sse("error", {"message": "Stream timed out"})
                return

            event = message.get("event", "message")
            data = message.get("data", {})

            yield format_sse(event, data)

            if event in _TERMINAL_EVENTS:
                logger.info(
                    f"SSE stream ending for client: {client_id} "
                    f"(terminal event: '{event}')"
                )
                return
    finally:
        remove_queue(client_id)
        logger.info(f"SSE stream cleaned up for client: {client_id}")

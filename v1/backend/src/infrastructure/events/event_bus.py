"""In-memory event bus for real-time SSE delivery via asyncio.Queue."""
import asyncio
from contextlib import asynccontextmanager

# Module-level singleton: analysis_id → list of subscriber queues
_subscribers: dict[str, list[asyncio.Queue]] = {}


async def publish(analysis_id: str, event: dict) -> None:
    """Push an event to all subscribers for the given analysis."""
    for queue in _subscribers.get(analysis_id, []):
        await queue.put(event)


@asynccontextmanager
async def subscribe(analysis_id: str):
    """Subscribe to events for an analysis. Yields an asyncio.Queue."""
    queue: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(analysis_id, []).append(queue)
    try:
        yield queue
    finally:
        _subscribers[analysis_id].remove(queue)
        if not _subscribers[analysis_id]:
            del _subscribers[analysis_id]

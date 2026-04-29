# events/
> In-memory event bus routing analysis events to SSE subscribers via asyncio.Queue with singleton subscriber registry.

## Patterns

- Module-level dict `_subscribers` acts as singleton registry: analysis_id → list of queues
- Context manager `subscribe()` ensures queue cleanup in finally block—prevents memory leaks on disconnect
- Broadcast via loop: `publish()` iterates all queues for an analysis_id, non-blocking put
- `setdefault()` + list.append() pattern creates subscriber list on first subscription
- No queue.get() backpressure—subscribers must drain their queue or it grows unbounded

## Navigation

**Parent:** [`infrastructure/`](../CLAUDE.md)
**Peers:** [`analysis/`](../analysis/CLAUDE.md) | [`external/`](../external/CLAUDE.md) | [`mcp/`](../mcp/CLAUDE.md) | [`persistence/`](../persistence/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md) | [`storage/`](../storage/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `event_bus.py` | Pub/sub routing for real-time event streaming | Always wrap subscribe() in async with. Keep publish() non-blocking. |

## Key Imports

- `from backend.src.infrastructure.events.event_bus import publish, subscribe`

## Add new event publisher for analysis updates

1. Import publish from event_bus
2. Call `await publish(analysis_id, {'type': 'event_name', 'data': ...})`
3. Event appears in all active subscriber queues for that analysis_id

## Usage Examples

### Subscribe and consume events in SSE endpoint
```python
async with subscribe(analysis_id) as queue:
    while True:
        event = await queue.get()
        yield f'data: {json.dumps(event)}\n\n'
```

## Don't

- Don't call publish() without wrapping in try/except—if any queue.put() fails, event is lost for remaining subscribers
- Don't hold queue reference outside subscribe() context—will cause orphaned queue references
- Don't assume FIFO ordering across multiple analyses—each analysis_id has independent queue list

## Testing

- Mock _subscribers dict directly; verify publish() distributes to all queues without loss
- Test subscribe() cleanup: confirm queue removed from registry after context exit

## Debugging

- Memory leak: check _subscribers dict size—if it grows, subscribers aren't exiting context manager properly
- Silent failures: publish() swallows queue.put() exceptions; add logging to catch hung subscribers blocking puts

## Why It's Built This Way

- Singleton _subscribers chosen for simplicity—no session/connection state management required
- asyncio.Queue chosen over list because subscribers iterate unpredictably; Queue.put() is non-blocking and safe

## Dependencies

**Depends on:** `Domain Layer`
**Exposes to:** `Application Layer`, `DI Container`

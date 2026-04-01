# workers/
> ARQ background worker for async repository analysis with phased blueprint generation and RAG-enabled prompting.

## Patterns

- startup() initializes entire service graph from Container—all downstream tasks receive pre-wired services via ctx dict, not lazy-loaded
- analyze_repository task stores services in ctx during startup, retrieves them at runtime—Future/coroutine detection guards against accidental async primitives in task handlers
- _safe_log() wraps event logging with exception swallowing to prevent logging failures from crashing the analysis job itself
- _mark_failed() uses retry loop (3 attempts, 1s backoff) to handle transient DB errors when persisting failure status
- DatabasePromptLoader injected into PhasedBlueprintGenerator—enables RAG-based prompt retrieval without hardcoded paths
- TempStorage().get_base_path() used for repository cloning—isolated temp dir prevents concurrent analysis contamination

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`application/`](../application/CLAUDE.md) | [`config/`](../config/CLAUDE.md) | [`domain/`](../domain/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `tasks.py` | Defines startup/shutdown hooks and analyze_repository task | Add new tasks as top-level async functions. Extend startup() to wire new services into ctx. |
| `worker.py` | ARQ worker entry point with Python 3.14+ compatibility | Only modify if asyncio/event loop behavior changes. Preserve RuntimeError→set_event_loop pattern. |

## Key Imports

- `from workers.tasks import startup, shutdown, analyze_repository (exposed to arq.run_worker)`
- `from config.container import Container (dependency injection root)`
- `from infrastructure.storage.temp_storage import TempStorage (repo cloning isolation)`

## Add a new background analysis phase or modify existing task flow

1. Define new async task function in tasks.py with (ctx, analysis_id, ...) signature
2. In startup(), instantiate any new service dependencies and store in ctx dict
3. Retrieve services from ctx in task; validate type (check for asyncio.Future), then execute
4. Use _safe_log() for SSE-visible events and _mark_failed() for error persistence

## Usage Examples

### Retrieve pre-wired service and handle Future guard
```python
analysis_service = ctx.get('analysis_service')
if asyncio.iscoroutine(analysis_service) or isinstance(analysis_service, asyncio.Future):
    raise ValueError(f'Service is Future, not instance: {type(analysis_service)}')
await analysis_service.run(analysis_id)
```

## Don't

- Don't call await container.db() in startup() multiple times—stash result in ctx to avoid repeated async initialization
- Don't store Futures/coroutines in ctx—task handlers receive them as-is; wrap in await immediately or validate type before use
- Don't let logging/event persistence failures crash the analysis task—use _safe_log() pattern with exception swallowing

## Testing

- Mock Container and services; inject into ctx dict before calling analyze_repository directly
- Validate startup() stores non-Future objects: assert not asyncio.iscoroutine(ctx['service_name'])

## Debugging

- If 'X is a Future/coroutine, not a service' error: startup() completed before service was awaited—check Container.init_resources() success
- Worker hangs during startup: likely awaiting Container.db() in startup()—check database connection pool and log output for 'DB client resolved' message

## Why It's Built This Way

- startup() wires entire service graph upfront—avoids per-task initialization overhead and ensures all services share same Container/DB connection
- RAG enabled via db_client passed to PhasedBlueprintGenerator—allows Phase 7 intent layer to retrieve context from persistence mid-task without external API calls

## Dependencies

**Depends on:** `Application Layer`
**Exposes to:** `Redis queue`

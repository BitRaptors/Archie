# workers/
> Unit tests for dual-path worker dispatch: ARQ when Redis available, in-process asyncio fallback when unavailable.

## Patterns

- Worker entry point detects Python 3.14+ missing event loop and creates one before run_worker
- Container._create_arq_pool catches ConnectionError and asyncio.TimeoutError, returns None silently for graceful degradation
- Route handler branches on arq_pool truthiness: enqueue_job if pool exists, else asyncio.create_task for in-process
- All fixtures use AsyncMock for service/repo mocks; PropertyMock + patch for event loop simulation
- Tests verify lifecycle (start/stop) and exception paths separately from happy-path dispatch logic

## Navigation

**Parent:** [`unit/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`domain/`](../domain/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md) | [`services/`](../services/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `test_analysis_workflows.py` | Verify Redis optional, event loop compat, dual dispatch | Add test class per subsystem; use AsyncMock fixtures consistently |

## Add new dispatch path test

1. Create TestNewPath class with @pytest.mark.asyncio method
2. Patch arq_pool state and mock all service returns
3. Assert correct enqueue_job or create_task call made
4. Verify state transitions (pending→running) via mock asserts

## Usage Examples

### Event loop creation on 3.14+
```python
with patch('workers.worker.asyncio') as mock_asyncio:
    mock_asyncio.get_event_loop.side_effect = RuntimeError()
    mock_asyncio.new_event_loop.return_value = MagicMock()
    main()
    mock_asyncio.new_event_loop.assert_called_once()
```

## Don't

- Don't assume asyncio.get_event_loop() always succeeds — catch RuntimeError for 3.14+ compat
- Don't let Redis errors crash container — return None from _create_arq_pool, check before enqueue
- Don't mix synchronous and async mocks in same test — use AsyncMock consistently for services

## Testing

- Use @pytest.mark.asyncio for all async test methods; patch both asyncio module and arq pool
- Mock entire service chain (analysis_repo, repository_repo, event_repo) — never use real DB

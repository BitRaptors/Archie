# services/
> Unit tests for service layer: validates business logic, API retry patterns, data collection, and blueprint generation workflows.

## Patterns

- Mock-first fixture design: all tests pre-wire mock Supabase/Anthropic clients as dependencies, inject via initialize()
- Async test suite: @pytest.mark.asyncio decorates all I/O tests; verify call counts and sleep durations for retry validation
- Phase-driven data capture: AnalysisDataCollector accumulates phase data (gathered/sent/output) in memory, persists via DatabaseClient abstraction
- Exponential backoff retry: _call_ai() retries 529/429 errors with 30s/60s sleeps, skips 400/401, exhausts after 4 attempts
- Blueprint fixture layering: sample_blueprint provides realistic ArchitectureRules/Components/Decisions; minimal_blueprint tests edge cases
- Error-specific assertions: test distinct anthropic exceptions (InternalServerError, RateLimitError, AuthenticationError) trigger correct retry vs. propagate paths

## Navigation

**Parent:** [`unit/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`domain/`](../domain/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `test_analysis_data_collector.py` | Validates in-memory and Supabase persistence of phase data | Add test for new phase fields in capture_phase_data; verify summary metrics update |
| `test_analysis_data_collector_db.py` | Enforces DatabaseClient abstraction, not SupabaseAdapter coupling | No SupabaseAdapter imports; test initialize(db) accepts any DatabaseClient impl |
| `test_api_retry.py` | Covers _call_ai retry logic for transient API failures | Mock specific anthropic exceptions; verify sleep durations match backoff strategy |
| `test_agent_file_generator.py` | Tests rule file generation from StructuredBlueprint entities | Extend sample_blueprint fixture when adding new Blueprint fields; verify RuleFile output |

## Key Imports

- `from anthropic import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError, AuthenticationError, BadRequestError`
- `from domain.entities.blueprint import StructuredBlueprint, ArchitectureRules, Component, Technology`
- `from domain.interfaces.database import DatabaseClient, QueryBuilder, QueryResult`

## Add test for new service method with API retry

1. Create mock client fixture with AsyncMock(side_effect=[error1, success])
2. Call service method in test; patch asyncio.sleep to spy on backoff
3. Assert call_count, sleep durations, and final result match spec

## Usage Examples

### Mock Anthropic client for retry test
```python
mock_client.messages.create = AsyncMock(
    side_effect=[_make_internal_server_error(), _make_success_response()]
)
with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
    result = await gen._call_ai(...)
assert mock_client.messages.create.call_count == 2
```

### Capture phase data in-memory
```python
await collector.capture_phase_data(
    analysis_id="test-id",
    phase_name="discovery",
    gathered={"file_tree": "..."},
    sent={"full_prompt": "..."}
)
assert "test-id" in collector._data
```

## Don't

- Don't instantiate Supabase/Anthropic directly in tests — use AsyncMock with configurable side_effects to control failures
- Don't test retry logic without mocking asyncio.sleep — verify backoff durations, not elapsed wall time
- Don't skip error type assertions — each exception class (429 vs 401) requires different test path

## Testing

- Use @pytest.mark.asyncio for all async tests; patch('asyncio.sleep') to verify backoff without delay
- Fixtures create fresh instances (AnalysisDataCollector, PhasedBlueprintGenerator); initialize(mock_db) to enable DB path

## Debugging

- Retry tests fail silently — check mock_client.messages.create.call_count and mock_sleep.call_count to isolate retry vs success paths
- Phase data missing — verify AnalysisDataCollector._data is keyed by analysis_id and contains 'gathered'/'phases'/'summary' top-level keys

## Why It's Built This Way

- DatabaseClient abstraction decouples tests from SupabaseAdapter; allows mocking any persistence layer via MockDB()
- Exponential backoff (30s, 60s) chosen for 529/429; immediate propagation for 400/401 to fail fast on client errors

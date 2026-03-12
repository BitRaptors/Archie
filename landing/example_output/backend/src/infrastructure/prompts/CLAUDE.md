# prompts/
> Dual prompt loading strategies: file-based for development, database-backed for production with caching.

## Patterns

- Both loaders expose identical public API (get_prompt_by_key, get_all_default_prompts) — swappable implementations
- DatabasePromptLoader is async; PromptLoader is sync — caller must know which to await
- In-memory cache with invalidation flag (_all_loaded) prevents re-querying entire dataset
- PromptPrompt.create() factory called consistently — validation happens in domain entity, not loader
- ValueError raised for missing keys in both implementations — consistent error contract
- Default path resolution: PromptLoader walks up from file location (parent.parent.parent.parent / 'prompts.json')

## Navigation

**Parent:** [`infrastructure/`](../CLAUDE.md)
**Peers:** [`analysis/`](../analysis/CLAUDE.md) | [`events/`](../events/CLAUDE.md) | [`external/`](../external/CLAUDE.md) | [`mcp/`](../mcp/CLAUDE.md) | [`persistence/`](../persistence/CLAUDE.md) | [`storage/`](../storage/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `prompt_loader.py` | File-based prompt loading with lazy caching | Add new methods only if sync/blocking stays acceptable |
| `database_prompt_loader.py` | Async database loader with manual cache control | All public methods must be async; await _repo calls |

## Key Imports

- `from infrastructure.prompts import PromptLoader, DatabasePromptLoader`
- `from domain.entities.analysis_prompt import AnalysisPrompt`

## Switch from file-based to database prompts in production

1. Inject DatabasePromptLoader instead of PromptLoader at DI container setup
2. Ensure all call sites await the async methods (await loader.get_prompt_by_key(key))
3. Call invalidate_cache() after database updates if real-time consistency required

## Usage Examples

### Both loaders expose same contract; differ in I/O strategy
```python
# File-based (sync)
prompt = loader.get_prompt_by_key('discovery')
# Database-backed (async)
prompt = await loader.get_prompt_by_key('discovery')
```

## Don't

- Don't mix sync/async — PromptLoader is blocking I/O, DatabasePromptLoader is awaitable; pick one per use site
- Don't assume cache is warm after get_prompt_by_key — only get_all_default_prompts populates _all_loaded flag
- Don't catch ValueError from missing keys — propagate; callers depend on exception as contract

## Testing

- Mock PromptRepository for DatabasePromptLoader; mock prompts.json for PromptLoader unit tests
- Test cache hit path separately — verify second call to same key skips repo call

## Why It's Built This Way

- Separate sync/async loaders instead of unified interface — async adds ceremony if not needed; consumers choose cost
- Manual invalidate_cache() method over auto-expiry — safe default (stale > broken); explicit refresh on writes

## Dependencies

**Depends on:** `Domain Layer`
**Exposes to:** `Application Layer`, `DI Container`

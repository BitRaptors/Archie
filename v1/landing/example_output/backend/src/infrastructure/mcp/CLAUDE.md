# mcp/
> MCP server exposing structured blueprint JSON as resources and tools for architecture queries.

## Patterns

- All data derives from blueprint.json (StructuredBlueprint) — markdown is rendered on-the-fly, never cached
- Resources filtered by active repo ID at serve time; URI rewrites replace stale repo UUIDs with current active ID
- Tools read StructuredBlueprint, render via blueprint_renderer.render_blueprint_markdown, then slice output by ## headers
- Glob matching supports ** recursive patterns; single-level uses fnmatch; separate code paths to avoid false matches
- BlueprintResources and BlueprintTools mirror each other: both load JSON, both render markdown, both slice sections
- Lazy initialization of DB clients (UserProfileRepository, RepositoryRepository) with silent fallback on import/connection failure

## Navigation

**Parent:** [`infrastructure/`](../CLAUDE.md)
**Peers:** [`analysis/`](../analysis/CLAUDE.md) | [`events/`](../events/CLAUDE.md) | [`external/`](../external/CLAUDE.md) | [`persistence/`](../persistence/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md) | [`storage/`](../storage/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `server.py` | MCP server lifecycle and request dispatch | Add tools via @srv.list_tools() + handler. Update active repo detection logic here. |
| `resources.py` | Expose blueprint sections as MCP resources | Change resource URI scheme only here. Always call _render_markdown + _slice_markdown together. |
| `tools.py` | Query and validate operations on blueprints | New tools query _load_structured_blueprint, render, slice. Keep glob/slugify utilities here. |

## Key Imports

- `from domain.entities.blueprint import StructuredBlueprint`
- `from application.services.blueprint_renderer import render_blueprint_markdown`
- `from mcp.server import Server; from mcp.types import Resource, Tool`

## Add a new query tool to the MCP server

1. Implement method in BlueprintTools that calls _load_structured_blueprint(repo_id) and queries StructuredBlueprint fields
2. Add Tool definition in @srv.list_tools() with name, description, and inputSchema
3. Add async handler that calls tools_manager method and returns formatted string result
4. Test by calling tool with active repo ID from get_active_repo_id()

## Usage Examples

### Glob matching logic for ** patterns
```python
def _match_segments(path_parts, pat_parts):
  if pat_parts[0] == '**':
    for i in range(len(path_parts) + 1):
      if _match_segments(path_parts[i:], pat_parts[1:]):
        return True
```

### Active repo resolution with URI rewrite
```python
if uri_str.startswith('blueprint://analyzed/'):
  active_id = await _get_active_repo_id()
  path_parts = uri_str.replace('blueprint://analyzed/', '').split('/')
  if path_parts:
    path_parts[0] = active_id
    uri_str = 'blueprint://analyzed/' + '/'.join(path_parts)
```

## Don't

- Don't cache rendered markdown across requests — repo content changes; re-render from JSON each time
- Don't hardcode repo_id in URIs — always resolve via _get_active_repo_id() and rewrite paths at read time
- Don't mix tool logic into resources.py or vice versa — they're separate managers despite code duplication

## Testing

- Verify glob_match with ** patterns: _glob_match('src/api/v1/users.py', 'src/api/**/*.py') must return True
- Check active repo filtering: list_resources() must exclude URIs not containing current active_id

## Debugging

- If blueprint.json fails to load: _load_blueprint silently returns None; check file exists and StructuredBlueprint.model_validate succeeds
- If resources/list_changed doesn't fire: _last_active_repo_id must differ from current; seed it in list_resources() first call

## Why It's Built This Way

- Render markdown on-the-fly instead of caching: supports live blueprint edits without server restart
- Rewrite repo_id in URIs at read time: allows cached old URIs to resolve to current active repo without invalidation

## Dependencies

**Depends on:** `Domain Layer`
**Exposes to:** `Application Layer`, `DI Container`

# graphs/
> LangGraph state machines orchestrating multi-step AI workflows (avatar generation, memory analysis, story generation) with streaming SSE updates.

## Patterns

- StateGraph nodes return `dict` updates merged into TypedDict state—never mutate state directly, always return new values.
- All async nodes call `send_sse_event(id, event_type, payload)` for real-time client feedback before/after expensive operations.
- Planner node (decision node) returns `{next_step: key}` to route conditional execution; END/START are reserved langgraph keywords.
- Signed URLs created for Supabase storage access; photo_paths stored as paths, signed_urls generated on-demand with 5min expiry.
- Vision models (Groq, Gemini) require image_url format with signed URLs; handle GroqError for model-specific failures (no vision support).
- Prompt resolution: `get_prompt_config(key)` fetches model/temp/tokens from DB, `resolve_prompt(key, vars)` injects variables into template.

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`models/`](../models/CLAUDE.md) | [`routes/`](../routes/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `avatar_generator.py` | Generate character avatar from photo via description→DALL-E | Update planner decision logic or add description refinement loop |
| `memory_analyzer.py` | Extract characters/events from memory text + photos | Adjust character detection prompts or photo person-matching heuristics |
| `story_generator.py` | Multi-page story generation with consistency checks per page | Modify page generation prompt, image download flow, or consistency retry logic |

## Key Imports

- `from src.utils.prompt_resolver import resolve_prompt, get_prompt_config`
- `from src.utils.sse import send_sse_event`

## Add new LLM step to graph (e.g., new analysis node)

1. Define new dict return type with output fields; add fields to state TypedDict.
2. Create async node function: fetch prompt config, resolve with context vars, call LLM with streaming.
3. Send SSE status/error events; parse response (check for JSON parse failure).
4. Update planner to route to new node; add new node to graph.add_node(); update edges.

## Usage Examples

### Node returning state updates
```python
async def generate_description(state: AvatarGeneratorState) -> dict:
    # ... process ...
    visual_desc = response.choices[0].message.content
    return {"visual_description": visual_desc, "next_step": "generate_image"}
```

## Don't

- Don't call `send_sse_event()` synchronously in sync functions—always `await` in async context to avoid blocking.
- Don't reuse signed URLs across requests—expiry is 300s; regenerate on each node if needed.
- Don't parse vision model responses without checking for refusal keywords ('sorry', 'cannot analyze')—log and handle gracefully.

## Testing

- Mock send_sse_event; invoke graph with minimal state dict; assert node returns expected state updates.
- Test prompt resolution with mock DB: verify template vars inject correctly before LLM call.

## Debugging

- Log state keys at planner entry (`list(state.keys())`) and node returns—reveals missing or unexpected fields.
- For Groq vision failures: check error message for 'does not support image input'—model mismatch, not request bug.

## Why It's Built This Way

- StateGraph chosen over LLMGraph: explicit state TypedDict enforces schema, planner node gives manual control over routing.
- Signed URLs + photo_paths split: paths stored in DB for durability, URLs generated on-demand to respect expiry/security.

## What Goes Here

- **LangGraph StateGraph workflows for multi-step AI orchestration** — `{domain}_generator.py or {domain}_analyzer.py`
- new_ai_workflow → `tuck-in-tales-backend/src/graphs/{domain}_generator.py`

## Dependencies

**Depends on:** `LLM Clients`, `SSE Utility`, `Supabase Client`, `Prompt Resolver`
**Exposes to:** `API Routes`

## Templates

### langgraph_node
**Path:** `tuck-in-tales-backend/src/graphs/{domain}_generator.py`
```
async def generate_node(state: DomainState) -> DomainState:
    await send_sse_event(state['id'], 'status', {'msg': 'generating'})
    return {**state, 'result': result}
```

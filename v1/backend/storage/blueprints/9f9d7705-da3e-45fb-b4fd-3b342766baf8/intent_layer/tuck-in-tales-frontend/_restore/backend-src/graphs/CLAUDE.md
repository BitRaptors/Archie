# graphs/
> LangGraph-based multi-step generation pipelines for avatars and stories with SSE streaming and Supabase persistence.

## Patterns

- TypedDict state schemas define all graph variables upfront; nodes return partial dicts to update only changed fields
- Planner node checks preconditions and routes to next step via 'next_step' key; enables conditional branching without explicit edges
- SSE events sent mid-execution via send_sse_event(str(id), event_type, payload) for real-time client updates
- Signed URLs generated for each photo access (5min expiry); passed to vision APIs rather than uploading image data
- Language code stored in state; mapped to full name via LANGUAGE_CODE_TO_NAME dict before passing to LLM prompts
- Groq/OpenAI clients imported from centralized src.utils modules, initialized once at module load

## Navigation

**Parent:** [`backend-src/`](../CLAUDE.md)
**Peers:** [`models/`](../models/CLAUDE.md) | [`routes/`](../routes/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `avatar_generator.py` | Photo→visual description→DALL-E prompt→avatar generation | Add nodes before planner routing; test each with mock Supabase signed URLs |
| `story_generator.py` | Story outline generation and page-by-page content creation | Fetch story record once per node; avoid re-querying same data in parallel branches |

## Key Imports

- `from langgraph.graph import StateGraph, END, START`
- `from src.utils.sse import send_sse_event`
- `from src.utils.supabase import get_supabase_client`

## Add a new generation step to a pipeline

1. Define output fields in state TypedDict
2. Create async node function that checks preconditions from state
3. Send SSE status event at start with step name
4. Return dict with next_step routing key or error_message
5. Add node to graph.add_node() before compiling

## Usage Examples

### Planner node routing pattern
```python
def planner(state: AvatarGeneratorState) -> dict:
    if not state.get('photo_paths'):
        return {"error_message": "No photos found."}
    elif not state.get('visual_description'):
        return {"next_step": "generate_description"}
    return {"next_step": "finish"}
```

## Don't

- Don't pass entire Supabase responses in state — fetch once in node, use locally, return only deltas
- Don't send image bytes over SSE or state — use signed URLs or storage paths instead
- Don't infer personality/age from vision API — stick to objective visual traits (hair, face shape, glasses)

## Testing

- Mock signed URLs in tests — don't call Supabase storage unless integration test
- Verify planner logic with state dicts missing expected fields (photo_paths=[], visual_description=None)

## Debugging

- Log [Graph - {character_id}] prefix for all node operations to trace execution path across async calls
- Check async_groq_client / async_openai_client availability early — log exact API key name if None

## Why It's Built This Way

- DB-driven approach removed checkpointer — story state lives in Supabase, graph is stateless and restartable
- Planner pattern chosen over explicit conditional edges — simpler to add routing rules without recompiling graph

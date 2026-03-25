# prompts/
> Prompt editing and testing UI: manages template variables, provider/model selection, and real-time LLM testing with variable substitution.

## Patterns

- Variable mention system: @ prefix triggers autocomplete; track startPos to replace from @ not cursor position
- Form state reset on prompt.id change: useEffect dependency ensures UI matches current prompt data
- Provider-model coupling: when provider changes, validate and reset model if not available in new provider
- Variable substitution: replaceAll(@key, value) for both system and user prompts before API test
- Textarea ref management: useRef + requestAnimationFrame for cursor restoration after variable insertion
- Lazy variable loading: PROMPT_VARIABLES[prompt.slug] pattern returns array or empty fallback

## Navigation

**Parent:** [`components/`](../CLAUDE.md)
**Peers:** [`Auth/`](../Auth/CLAUDE.md) | [`Layout/`](../Layout/CLAUDE.md) | [`ui/`](../ui/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `PromptEditor.tsx` | Full-featured prompt editing with variable mention system | Add fields to PromptUpdate interface, sync state + form reset, update mention logic if mention.field expands |
| `PromptPlayground.tsx` | Collapsible test harness: renders substituted prompts, calls API | Modify substituteVariables for new variable syntax, extend PromptTestRequest/Response types in models |

## Key Imports

- `from @/models/prompt import Prompt, PromptUpdate, PromptTestRequest, PromptTestResponse`
- `from @/lib/promptVariables import PROMPT_VARIABLES, AVAILABLE_PROVIDERS, AVAILABLE_MODELS`

## Add new prompt variable to template

1. Define in PROMPT_VARIABLES[slug] with name, description, sample properties
2. PromptEditor highlights @name automatically via renderHighlightedText regex
3. PromptPlayground inputs render from slugVariables, substitute via replaceAll(@name, value)

## Don't

- Don't mutate variables directly — use setter callbacks in handleTextareaChange; directly modifying state breaks mention tracking
- Don't trust current model in new provider — always validate against AVAILABLE_MODELS[provider] before setting
- Don't call setSelectionRange synchronously — wrap in requestAnimationFrame to let DOM update first

## Testing

- PromptPlayground.handleTest: calls api.testPrompt with rendered prompts; verify substitution in variable inputs before running
- Mention system: type @, check filtered suggestions appear; verify insertion maintains cursor and text integrity

## Debugging

- Cursor jumps after variable insert: check requestAnimationFrame timing; selectionStart may fire before textarea updates
- Mention menu won't close: verify handleTextareaChange detects space/newline after @ and sets active: false

## Why It's Built This Way

- Separate mention state from form state: keeps textarea rendering simple; only active mention UI bloats component
- Substitute variables in Playground, not Editor: Editor shows raw @variables for editing; Playground previews rendered output before test

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

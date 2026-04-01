# generate/
> POST endpoint orchestrating AI-driven site generation from pins/presets, delegating to provider-specific generators with file output.

## Patterns

- Provider selection: explicit fallback chain (param → settings → 'gemini' default) before API calls
- Database queries executed once at route entry, results passed as immutable input object downstream
- Error handling is coarse-grained: catch all generation errors, return 500 with message, no partial recovery
- File writing responsibility split: Claude generator handles write, Gemini generator deferred to writeGeneratedSite helper
- Output directory created via timestamp-based naming (site-${Date.now()}) with no collision detection or cleanup
- GitHub integration is optional/silent: try-catch swallows failures, null repoContent accepted downstream

## Navigation

**Parent:** [`api/`](../CLAUDE.md)
**Peers:** [`pins/`](../pins/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `route.ts` | POST handler: fetch DB state, call AI provider, return file manifest | Add validation before db.prepare calls. Keep provider selection unchanged. Update error messages only. |

## Add new AI provider (e.g., OpenAI) alongside Gemini/Claude

1. Implement generateWithOpenAI in /lib/generate matching function signature of generateWithClaude/Gemini
2. Add provider string to chosenProvider conditional (elif chosenProvider === 'openai')
3. Handle file writing: if OpenAI writes itself, use same pattern as Claude; else call writeGeneratedSite
4. Add settings validation for openai_api_key if required

## Don't

- Don't call getRepoContent without try-catch — GitHub failures must not crash generation; silent-fail is intentional
- Don't apply writeGeneratedSite for Claude — it handles its own I/O; only use for Gemini output
- Don't skip gemini_api_key validation — endpoint returns 400 before costly AI calls if missing

## Testing

- POST with valid userPrompt + provider='claude'/'gemini' should return 200 with outputDir and fileCount
- POST without gemini_api_key in settings should return 400 error before calling generation

## Debugging

- Check process.cwd() and output/ directory writable when files not appearing on disk — writeGeneratedSite may fail silently
- Validate input object shape (pins, repoContent, presets) before passing to generator — type drift causes cryptic AI errors

## Why It's Built This Way

- Provider param overrides settings default: allows per-request override without DB mutation, matches serverless request isolation
- Try-catch on GitHub fetch: repositories are optional features; generation must not fail for missing repos

## What Goes Here

- **App Router pages and layouts only in src/app** — `page.tsx or layout.tsx`

## Dependencies

**Depends on:** `Application Service Layer`, `Infrastructure Layer`
**Exposes to:** `Frontend Components`

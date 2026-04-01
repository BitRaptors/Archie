# lib/
> Utilities library: prompt building, repo parsing, database setup, Claude API integration for landing page generation.

## Patterns

- Prompt composition via modular sections assembled from prompts.json — each section conditionally included based on input (presets, pins, repoContent).
- Input decomposition: parseReadmeSections() + extractDependencies() + inferProjectType() reduce GitHub repo data to structured signals for prompt context.
- Database singleton with lazy initialization — getDb() creates DB, schema, and seeds presets only on first call; returns cached instance thereafter.
- Two Claude integration paths: non-streaming (--print --output-format json) for simple flows; streaming (--print --verbose --output-format stream-json) for verbose feedback.
- Section mapping uses keyword arrays + heading substring matching; truncates to 2000 chars to fit context windows without blowing token budgets.
- Tests split into unit (generate.test.ts parsing/extraction logic) and integration (generate.integration.test.ts actual Claude spawn) — spawning is slow, isolated in separate suite.

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`app/`](../app/CLAUDE.md) | [`components/`](../components/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `db.ts` | SQLite setup, schema, preset seeding on first boot. | Add table? Update CREATE TABLE IF NOT EXISTS block. Add preset? Push to seedPresets array. |
| `generate.ts` | Core prompt-building logic; parse repos, map to landing page sections. | New section type? Add to mapReadmeToLandingPageSections mapping array. Tweak prompt? Edit prompts.json, not code. |
| `prompts.json` | External prompt templates: task, blueprint, guidelines, design config. | Copy tweaks go here. Reference in generate.ts via prompts.X dot notation. |
| `generate.test.ts` | Unit tests: section parsing, dependency extraction, project type inference. | Add test for new signal type? Update inferProjectType() AND add test case. |
| `generate.integration.test.ts` | End-to-end: spawn real Claude, verify files written to tmpdir. | Slow tests (120s timeout). Only run locally or in CI nightly. Use makeTmpDir/cleanup pattern. |
| `github.ts` | Octokit wrapper; fetch repo metadata, readme, file tree from GitHub API. | File incomplete. Extract owner/repo from URL via regex. Call octokit methods for readme content. |
| `stream-parsing.test.ts` | Parse Claude streaming JSON output (event types, subtypes, results). | Verify line-by-line JSON parsing; validate event.type + event.subtype enums. |

## Key Imports

- `import { getDb } from './db' — for database access in generate flows`
- `import prompts from './prompts.json' — for prompt template strings in buildPrompt()`
- `import { spawn } from 'child_process' — for Claude CLI invocation in integration tests`

## Add new landing page section blueprint or copy guideline to prompt

1. Edit prompts.json: add new top-level key (e.g., 'newGuideline': 'Content here...').
2. In generate.ts buildPrompt(): add sections.push(prompts.newGuideline) in logical order.
3. Test: generate.test.ts verifies new section text appears in output string.
4. Spawn integration test validates Claude sees new guidance and generates accordingly.

## Usage Examples

### Lazy-load database singleton with schema seeding
```typescript
export function getDb(): Database.Database {
  if (!db) {
    db = new Database(DB_PATH);
    db.exec(`CREATE TABLE IF NOT EXISTS pins (...)`);
    seedPresets(db);
  }
  return db;
}
```

### Conditional prompt composition based on input
```typescript
if (input.presets.length > 0) {
  const grouped: Record<string, string> = {};
  for (const p of input.presets) {
    grouped[p.category] = `${p.name}: ${p.value}`;
  }
  sections.push(prompts.designConfiguration + ...);
}
```

## Don't

- Don't hardcode prompts in generate.ts — extract to prompts.json so product can edit copy without code redeploy.
- Don't call getDb() synchronously in hot paths — singleton is initialized once; subsequent calls are O(1) cache lookups.
- Don't spawn Claude without tmpdir isolation in tests — use makeTmpDir() + cleanup() to prevent filesystem pollution across test runs.

## Testing

- Unit: vitest generate.test.ts in isolation — no external API calls, fast (<1s). Validates parsing, inference, mapping logic.
- Integration: spawn real `claude` CLI with tmpdir as cwd, read written files, assert index.html exists. Slow (120s), run on commit/nightly only.

## Debugging

- Claude spawn timeouts: check --max-turns limit, increase if Claude needs more iteration. Verify tmpdir has write permissions. Log stderr from spawn for 'tool not allowed' errors.
- Prompt context explosion: truncate sections in mapReadmeToLandingPageSections (2000 char limit) before assembly to stay under token budget. Count tokens in prompts.json manually if growth stalls generation.

## Why It's Built This Way

- Prompt sections modular (not monolithic) — allows product/UI to conditionally omit design config if no presets, reducing token waste on small projects.
- Integration tests spawn actual Claude CLI instead of mocking — catches real formatting breakage when Claude output schema drifts; isolated to separate file so fast tests run without waiting.

## What Goes Here

- **Shared backend logic and DB access go in src/lib** — `camelCase.ts`
- **Tests co-located with implementation in src/lib** — `*.test.ts`
- shared_business_logic → `src/lib/[module].ts`
- database_schema_change → `src/lib/db.ts getDb() initialization block`
- prompt_templates → `src/lib/prompts.json`
- unit_tests → `src/lib/[module].test.ts`

## Dependencies

**Depends on:** `Infrastructure Layer`, `External AI APIs`, `GitHub API`
**Exposes to:** `API Route Handlers`

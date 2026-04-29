# lib/
> Markdown-to-navigation parser + semantic theme constants for blueprint documentation UI.

## Patterns

- ID generation is a shared contract: generateId() used by both parseNavigation() and ReactMarkdown heading components — IDs must match or links break.
- extractText() recursively unwraps React children to get plain text — handles strings, numbers, arrays, and element.props.children nesting.
- parseNavigation() strips markdown formatting (bold, links, backticks) from headings before generating IDs — regex patterns must match what markdown renders.
- Code blocks are skipped during parsing — tracked with inCodeBlock boolean toggled on ``` boundaries.
- H3 headings only nest under the most recent H2; orphan H3s before any H2 are silently dropped.
- theme.ts is a single-source-of-truth palette: every semantic concept maps to Tailwind class strings, composed with cn() in components.

## Navigation

**Parent:** [`frontend/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`hooks/`](../hooks/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md) | [`services/`](../services/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `blueprint-toc.ts` | Parse markdown headings → nav tree; generate heading IDs. | Sync generateId regex with React heading renderers. Update extraction regex if markdown format changes. |
| `blueprint-toc.test.ts` | Contract tests for ID generation and markdown parsing. | ID contract test validates parser IDs match ReactMarkdown IDs. Add test cases when heading formats change. |
| `theme.ts` | Semantic color/style constants keyed by UI purpose. | Edit only values; keys are component API. Validate all Tailwind classes exist in config. |
| `utils.ts` | cn() helper merges Tailwind classes without conflicts. | Re-export only; do not modify. Depends on clsx + tailwind-merge. |

## Key Imports

- `import { generateId, extractText, parseNavigation } from 'frontend/lib/blueprint-toc'`
- `import { theme } from 'frontend/lib/theme'`
- `import { cn } from 'frontend/lib/utils'`

## Add heading support to new blueprint section

1. Add ## or ### lines to markdown content
2. Verify generateId() produces expected slug (test with real heading text)
3. Confirm parseNavigation() nests H3s and strips formatting correctly
4. ReactMarkdown heading component automatically uses generateId(extractText(children))

## Usage Examples

### Extracting plain text from React children with nested elements
```typescript
extractText(['Architecture ', { props: { children: 'Overview' } }])
// → 'Architecture Overview'

extractText({ props: { children: 'nested' } })
// → 'nested'
```

## Don't

- Don't call generateId on already-stripped text — text passed to generateId must still have markdown formatting so regex patterns work correctly.
- Don't assume H3 without H2 parent exists — parseNavigation silently skips it; always nest H3 under an H2.
- Don't add theme keys lightly — every key is part of component API contract; coordinate with callers before adding.

## Testing

- Run vitest — blueprint-toc.test.ts has exhaustive contract tests for ID generation and markdown parsing.
- ID contract test validates parseNavigation IDs == ReactMarkdown IDs across real blueprint headings — must pass before merging.

## Debugging

- If sidebar nav shows wrong heading title: check parseNavigation markdown stripping regexes (bold, links, backticks) — they must match what React renders.
- If heading links are broken: generateId on markdown side must match extractText(children) side — trace through ID contract test with failing heading.

## Why It's Built This Way

- Shared generateId contract prevents nav/link drift — cheaper than syncing two ID generators, enforced by test.
- parseNavigation strips markdown before ID gen — simplifies ID logic, but requires test to validate it matches ReactMarkdown rendering.

## Dependencies

**Depends on:** `Backend API`
**Exposes to:** `end users`

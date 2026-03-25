# models/
> Type definitions for core domain models: Character, Family, Memory, Story, Prompt. Single source of truth for API contracts.

## Patterns

- Response types extend Basic types (e.g., FamilyDetailResponse extends FamilyBasicResponse) for list vs. detail scenarios
- Request/Input types use optional fields (?) for updates; required fields for creation (CharacterCreate vs. CharacterUpdate)
- Analysis workflow encoded in enums: Memory.analysis_status ('PENDING'|'ANALYZING'|'ANALYZED'|'CONFIRMED'|'FAILED')
- Category metadata co-located: CATEGORY_LABELS + CATEGORY_COLORS dicts in memory.ts for UI rendering
- Backend array fields (photo_paths, linked_character_ids, characters_on_page) always optional or nullable in responses
- Relationship tracking bidirectional: CharacterRelationship includes to_character_name/avatar_url to avoid N+1 fetches in UI

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`components/`](../components/CLAUDE.md) | [`hooks/`](../hooks/CLAUDE.md) | [`lib/`](../lib/CLAUDE.md) | [`pages/`](../pages/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `character.ts` | Character entity, relationships, and CRUD request shapes | Add optional fields to Character base, extend CharacterDetail if detail-specific data needed |
| `memory.ts` | Memory entity with AI analysis pipeline and photo person detection | New suggestion types added to MemorySuggestion.type union; photo detection coords are 0-100 percentages |
| `story.ts` | Story generation request/response with per-page progress tracking | StoryPageProgress mirrors backend—add fields here when backend adds page-level data |
| `family.ts` | Family container with members and character summaries | FamilyDetailResponse extends FamilyBasicResponse; add optional fields to Detail only |
| `prompt.ts` | LLM prompt versioning, testing, and configuration | response_format is generic Record<string, unknown>; available_variables is string array for template vars |

## Key Imports

- `import type { Character, CharacterSummary } from './character'`
- `import type { Memory, MemoryCategory } from './memory'`
- `import type { Story, StoryBasic } from './story'`

## Add new field to character/memory after backend change

1. Add field to Character/Memory base interface with correct type (? for optional, | null for nullable)
2. If field is in requests only, add to CharacterCreate/CharacterUpdate or MemoryConfirmRequest
3. Export type if other folders import it; verify in __init__.ts if one exists

## Don't

- Don't mix nullable (| null) and optional (?) on same field—use null for presence, ? for omission in requests
- Don't add UI-only fields to base types (e.g., isSelected)—create separate wrapper types or use hook state instead
- Don't duplicate category/status enums—define once (like CATEGORY_LABELS in memory.ts), import everywhere

## Testing

- Type-check imports: ensure Story uses StoryPageProgress not StoryPage for pages array
- Verify optional chaining: components access avatar_url? and photo_paths? safely (both always exist but may be null/empty)

## Why It's Built This Way

- CharacterSummary (id, name, avatar_url) exists to prevent circular bloat in Family.main_characters and Relationship.to_character_*
- DebugPromptEntry in Story/StoryPageProgress mirrors backend for transparency; UI reads raw_analysis for troubleshooting

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (browser)`

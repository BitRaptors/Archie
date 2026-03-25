# models/
> TypeScript type definitions mirroring backend Pydantic models for characters, families, and stories.

## Patterns

- All types include id (UUID string) and created_at (ISO date string) from backend
- Separate Basic/Summary types for lists; Detail/Full types for single entity views
- Optional fields use ? and null unions (field?: string | null) matching backend nullability
- Request types (Create, Update, GenerationRequest) have optional fields for partial updates
- Nested types compose: Story includes StoryPageProgress[], Family includes CharacterSummary[]
- Type extension used for variants: CharacterDetail extends Character, FamilyDetailResponse extends FamilyBasicResponse

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`config/`](../config/CLAUDE.md) | [`hooks/`](../hooks/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `character.ts` | Character entity types across CRUD operations | Add fields to Character first; propagate to Create/Update/Detail variants |
| `family.ts` | Family and member relationship types | FamilyDetailResponse is source of truth; update FamilySettingsUpdate for API inputs |
| `story.ts` | Story generation request and page progress tracking | StoryPageProgress is single source; Story extends StoryBasic with pages array |

## Key Imports

- `import type { Character, CharacterSummary } from './character'`
- `import type { Story, StoryPageProgress } from './story'`
- `import type { Family, FamilyDetailResponse } from './family'`

## Add new backend field to existing entity

1. Add field to base interface (Character, Family, Story)
2. Add to corresponding Create/Update request type if user-settable
3. Add to Summary/Detail variant if needed for that view
4. Verify null handling matches backend Pydantic model

## Usage Examples

### Adding optional field to existing entity
```typescript
export interface Character {
  id: string;
  name: string;
  birth_date?: string | null;  // New field
}
export interface CharacterCreate {
  name: string;
  birth_date?: string | null;  // Add to input type
}
```

## Don't

- Don't duplicate field definitions across types -- use type extension or composition instead
- Don't make required fields optional in Create/Update -- explicitly optional only for partial operations
- Don't use bare string for status field -- create Status enum type for type safety

## Testing

- Validate API responses match interface shape: JSON parse result satisfies interface
- Type-check component props: components receiving Character should accept Character, not any

## Why It's Built This Way

- Optional fields use ? + null union (not just ?) to match backend's nullable philosophy from Pydantic
- Story has duplicate type definition at end (extends StoryBasic with pages) -- consolidate to single definition

## Dependencies

**Depends on:** `Backend API`, `Firebase Auth`, `Supabase`
**Exposes to:** `end users (iOS/Android)`

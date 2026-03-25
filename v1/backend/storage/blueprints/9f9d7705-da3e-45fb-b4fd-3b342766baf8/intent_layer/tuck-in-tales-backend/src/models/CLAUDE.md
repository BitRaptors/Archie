# models/
> Pydantic models defining domain entities (Character, Family, Memory, Story, Prompt) with strict inheritance patterns for Create/Update/Full lifecycle.

## Patterns

- Base→Create→Update→Full model hierarchy: Base holds shared fields, Create for POST, Update for PATCH (all optional), Full adds id+timestamps
- family_id and embedding removed from Create/Update models—determined server-side by auth context, never client-settable
- Enums (AnalysisStatus, MemoryCategory, SuggestionType) constrain string fields; use str.Enum for JSON serialization
- TypedDict (StoryPageProgress) used for heterogeneous list items with optional keys—handles DB records with missing fields gracefully
- from_attributes=True + populate_by_name=True: ORM-to-Pydantic mapping + field alias support (e.g., birthdate→birth_date)
- Nested models (CharacterRelationship, MemorySuggestion, FamilyMember) flatten relationships; avoid circular refs

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`graphs/`](../graphs/CLAUDE.md) | [`routes/`](../routes/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `character.py` | Character entity lifecycle + relationships | Always sync Create/Update/Full; relationships optional in Full only |
| `memory.py` | Memory + analysis pipeline (status, categories, suggestions) | AnalysisStatus enum drives confirmation flow; MemorySuggestion is immutable |
| `story.py` | Story generation state machine + page progression | StoryPageProgress TypedDict handles partial page records; status drives API logic |
| `family.py` | Family + members context, join_code, language settings | FamilyDetails nests FamilyMember list; never expose raw auth user to API |
| `prompt.py` | LLM prompt versioning + testing harness | version immutable; PromptTestRequest is request-only, no DB model |

## Key Imports

- `from pydantic import BaseModel, Field`
- `from uuid import UUID`
- `from enum import Enum`

## Add optional field to existing entity without breaking Create/Update flow

1. Add field to CharacterBase with Optional + default=None
2. Field auto-inherits to CharacterCreate (no change needed)
3. CharacterUpdate: re-declare field as Optional (must be explicit for PATCH semantics)
4. Character (full): no change—inherits from Base

## Usage Examples

### Create/Update/Full hierarchy pattern
```python
class CharacterBase(BaseModel):
    name: str = Field(..., min_length=1)
class CharacterCreate(CharacterBase): pass
class CharacterUpdate(CharacterBase):
    name: Optional[str] = None
class Character(CharacterBase):
    id: UUID
```

## Don't

- Don't add family_id to Create/Update—derive from auth token; leads to privilege escalation
- Don't expose raw embedding field in models—internal only; use MemorySearchResult for similarity scores
- Don't make status/timestamps mutable in Update—use separate confirmation endpoints (MemoryConfirmRequest pattern)

## Testing

- Validate Create model serialization: Field constraints (min_length, max_length, aliases) must reject invalid input before DB layer
- Enum fields: confirm JSON round-trip preserves str value (AnalysisStatus.PENDING → 'PENDING' → AnalysisStatus.PENDING)

## Debugging

- populate_by_name=True: if birthdate alias fails, check Field(alias='birthdate') is present AND client sends either birthdate OR birth_date key
- TypedDict optional keys: StoryPageProgress missing 'text'? DB record may be old; code must handle None gracefully in routes

## Why It's Built This Way

- Separate Create/Update models: Create allows None for optional fields; Update forces all None-capable fields to preserve PATCH intent (don't overwrite unspecified fields)
- Enums as str subclass: string JSON serialization is implicit; AnalysisStatus 'PENDING' is API-safe without custom encoder

## What Goes Here

- **Pydantic models defining domain entities and API contracts** — `{domain}.py`
- new_backend_model → `tuck-in-tales-backend/src/models/{domain}.py`

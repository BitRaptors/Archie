# models/
> Pydantic request/response models for user, character, family, memory, story entities. Constraint: family_id auto-determined by auth, never user-supplied.

## Patterns

- family_id removed from Create/Update models, restored in full entity models — auth layer injects it server-side
- All Create models inherit from Base; Update models make all fields Optional; full entity adds id + timestamps
- Aliases used inconsistently (birthdate→birth_date in character only); populate_by_name=True allows both names
- Status field in Story tracks generation pipeline state (INITIALIZING→OUTLINING→GENERATING_PAGES→COMPLETED→FAILED)
- Optional fields default to None; required fields use Field(...) without default; max_length enforced at schema level
- from_attributes=True on all models enables ORM hydration; datetime.utcnow as default_factory for server-set timestamps

## Navigation

**Parent:** [`backend-src/`](../CLAUDE.md)
**Peers:** [`graphs/`](../graphs/CLAUDE.md) | [`routes/`](../routes/CLAUDE.md) | [`utils/`](../utils/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `character.py` | Character entity: name, bio, photos, birth_date, family link | Keep family_id out of Create/Update; add new fields to all three classes |
| `story.py` | Story generation: pages array, status, character refs, language | StoryGenerationRequest triggers async flow; Story model tracks page progress + status |
| `memory.py` | Memory entries with RAG search: text, date, embedding query support | MemorySearchRequest/Result separate concerns; embedding never exposed in API |
| `family.py` | Family aggregate: members list, join_code, language setting, details view | FamilyDetails nests FamilyMember array; FamilyUpdate is minimal (name, language only) |
| `user.py` | User identity: Firebase UID, email, display_name, family assignment | family_id optional on create (assigned later); id is string (Firebase UID), not UUID |

## Key Imports

- `from uuid import UUID, uuid4`
- `from pydantic import BaseModel, Field`
- `from datetime import datetime, date`

## Add new optional field to existing entity (e.g., new char attribute)

1. Add field to CharacterBase with Optional[Type]=None and Field constraints
2. Field auto-inherits to CharacterCreate and CharacterUpdate (already Optional)
3. Add field to Character full model with same default
4. Test: verify field serializes in from_attributes=True ORM context

## Usage Examples

### Auth-injected family_id pattern
```python
# CharacterCreate has no family_id
char = CharacterCreate(name="Alice", bio="...")
# Full Character adds it server-side:
db_char = Character(**char.dict(), id=uuid4(), family_id=auth.family_id)
```

## Don't

- Don't include family_id in Create/Update request models—auth layer determines it, client can't override
- Don't use orm_mode (Pydantic v1) — use from_attributes=True (Pydantic v2)
- Don't expose embedding vector or internal RAG state in API responses — keep in Memory, not in search results directly

## Testing

- Validate Create→Update→Full flow preserves all fields; family_id must only exist in full model
- Verify Field(min_length, max_length) constraints reject invalid input before DB hit

## Why It's Built This Way

- Status enum string in Story instead of separate enum class — simpler, frontend-friendly, extensible for new states
- User.id is Firebase UID (str) not UUID — auth system owns identity, app never generates it

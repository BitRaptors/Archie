# domain/
> Unit tests for domain entities: analysis settings constants, ignored directories, library capabilities, architecture rules.

## Patterns

- Constants (CAPABILITY_OPTIONS, ECOSYSTEM_OPTIONS, SEED_IGNORED_DIRS) tested for: sorted order, no duplicates, required values present
- Seed data (SEED_LIBRARY_CAPABILITIES) validated bidirectionally: all capabilities/ecosystems must exist in OPTIONS
- Pydantic models (IgnoredDirectory, LibraryCapability) tested via model_dump() serialization, not direct attribute access
- Factory methods (create_reference_rule, create_learned_rule) tested separately from model initialization
- Config objects support both creation with defaults and strategic updates (update_strategy raises ValueError on invalid)
- Tests assert specific error types (ValueError) for constraint violations, not generic exceptions

## Navigation

**Parent:** [`unit/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md) | [`services/`](../services/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `test_analysis_settings.py` | Validate domain constants and Pydantic models | Add new constant class → test sorted/duplicates/required items. New model → test defaults and model_dump() |
| `test_architecture_rule.py` | Test ArchitectureRule and RepositoryArchitectureConfig entities | Test factory methods separately. Config updates must validate strategy enum before applying |

## Add new domain constant or seed data

1. Define constant in domain/entities/analysis_settings.py
2. Test sorted (if list), no duplicates, required items present
3. If references other constants, test bidirectional validation

## Don't

- Don't test constants with simple equality — verify sorted(), duplicates, and known required values exist
- Don't skip bidirectional validation — if SEED_LIBRARY_CAPABILITIES references CAPABILITY_OPTIONS, test both directions
- Don't catch generic Exception — match specific ValueError for constraint violations like invalid merge_strategy

## Testing

- Constants: assert sorted, len(set(...)) == len(...), and hardcoded required values present
- Models: test default values, model_dump() serialization, and factory method branches (reference vs learned)

## Why It's Built This Way

- Seed data validated against OPTIONS at test time, not runtime — catches misconfigurations early
- Factory methods (create_reference_rule, create_learned_rule) separate from __init__ to enforce branching logic

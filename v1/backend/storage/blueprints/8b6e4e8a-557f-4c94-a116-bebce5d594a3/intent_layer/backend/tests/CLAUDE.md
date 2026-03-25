# tests/
> Shared pytest fixtures providing DI containers, mock repos, and sample architecture rules for all test suites.

## Patterns

- Fixture-based dependency injection: tmp_path → structured codebase → rules passed to tests
- Sample repo builders create parallel directory structures (src/api, src/services, src/domain) matching real layouts
- ArchitectureRule.create_reference_rule() for blueprint validation rules; .create_learned_rule() for discovered patterns
- SQL-safe rule data: rule_data dicts contain location, responsibility, depends_on fields for layer enforcement
- Confidence scoring on learned rules (0.85–0.95) tracks discovery certainty; source_files traces origin

## Navigation

**Parent:** [`backend/`](../CLAUDE.md)
**Peers:** [`scripts/`](../scripts/CLAUDE.md) | [`src/`](../src/CLAUDE.md)
**Children:** [`integration/`](integration/CLAUDE.md) | [`unit/`](unit/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `conftest.py` | Root fixture definitions for architecture validation tests | Add new fixtures for blueprints/rules; keep tmp_path builders lean |

## Key Imports

- `from domain.entities.architecture_rule import ArchitectureRule, RepositoryArchitectureConfig`
- `from pathlib import Path`
- `import pytest`

## Add new sample architecture rule for a blueprint/repo variant

1. Call ArchitectureRule.create_reference_rule() or .create_learned_rule() with blueprint_id/repository_id
2. Populate rule_data dict with location, responsibility, depends_on for layer rules
3. Set confidence 0.85+ for learned rules; add source_files list
4. Append to sample_architecture_rules or sample_learned_rules fixture

## Usage Examples

### Creating a reference layer rule for test validation
```python
ArchitectureRule.create_reference_rule(
    blueprint_id="python-backend",
    rule_type="layer",
    rule_id="layer-domain",
    name="Domain Layer",
    rule_data={"location": "src/domain/", "depends_on": []}
)
```

## Don't

- Don't hardcode file paths — use tmp_path fixtures for portable test repos
- Don't skip repository_id or blueprint_id on rules — required for rule traceability
- Don't create rules without confidence scores — breaks learned rule confidence tracking

## Testing

- Fixtures auto-resolve via pytest dependency injection — use as function params, no manual instantiation
- Validate rule_data keys match ArchitectureRule schema before test — fixture should mirror domain entity

## Why It's Built This Way

- Separate sample_architecture_rules, sample_learned_rules, sample_reference_rules fixtures to isolate rule types
- Use .create_reference_rule() factory method to enforce immutable blueprint rules; .create_learned_rule() for repo discovery

## Subfolders

- [`integration/`](integration/CLAUDE.md) — 
- [`unit/`](unit/CLAUDE.md) — 

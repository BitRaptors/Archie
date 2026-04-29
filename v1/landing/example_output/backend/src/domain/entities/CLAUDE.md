# entities/
> Domain entities for analysis workflows, architecture rules, and user/repository state—immutable dataclass models with factory methods and UTC timestamps.

## Patterns

- All entities use @dataclass with factory classmethod `create()` returning `Self` for construction
- Timestamps always use `datetime.now(timezone.utc)` — never naive datetime or local time
- Mutable state updates (start, complete, fail) call datetime.now() inline to track `updated_at`
- Analysis lifecycle: PENDING → IN_PROGRESS → COMPLETED/FAILED with status validation via config.constants
- Reference vs. learned rules: blueprint_id XOR repository_id determines rule origin; both have separate factories
- Prompt templating uses simple `{variable}` replacement in render(); variables list is pre-declared

## Navigation

**Parent:** [`domain/`](../CLAUDE.md)
**Peers:** [`interfaces/`](../interfaces/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `analysis.py` | Lifecycle state machine for code analysis jobs | Always update `updated_at` in state-change methods; clamp progress 0–100 |
| `architecture_rule.py` | Dual-origin rules: reference blueprints or learned from repos | Use blueprint_id XOR repository_id; validate merge_strategy against VALID_STRATEGIES |
| `analysis_settings.py` | Immutable enums: ecosystems, capabilities, file extensions, infrastructure files | Extend ECOSYSTEM_OPTIONS or CAPABILITY_OPTIONS as sorted lists; don't modify at runtime |
| `analysis_prompt.py` | Template prompts with variable substitution and factory creation | Render via context dict; variables must exist in list or {var} remains literal |

## Key Imports

- `from domain.entities.analysis import Analysis`
- `from domain.entities.architecture_rule import ArchitectureRule, RepositoryArchitectureConfig`
- `from domain.entities.analysis_settings import CAPABILITY_OPTIONS, ECOSYSTEM_OPTIONS, SOURCE_CODE_EXTENSIONS`

## Add new state transition to Analysis entity

1. Add new status constant to config.constants.AnalysisStatus
2. Create method (e.g., `def pause()`) that sets status, updated_at = now(timezone.utc), and any relevant fields
3. Test state preconditions if needed (e.g., can only pause if IN_PROGRESS)

## Usage Examples

### Analysis state transition with timestamp
```python
def complete(self) -> None:
    self.status = AnalysisStatus.COMPLETED
    self.progress_percentage = 100
    self.completed_at = datetime.now(timezone.utc)
    self.updated_at = datetime.now(timezone.utc)
```

## Don't

- Don't use naive datetime() — always wrap with timezone.utc for consistency across timezones
- Don't mutate analysis status without updating updated_at timestamp in same call
- Don't add runtime defaults to SEED_IGNORED_DIRS/capabilities; seed is reset-only, not fallback

## Testing

- Verify datetime.now(timezone.utc) produces UTC strings in isoformat() output—no local timezone leakage
- For rule merge strategy, confirm VALID_STRATEGIES enum check raises ValueError before persisting config

## Why It's Built This Way

- Dataclasses chosen for lightweight immutability + explicit field declaration; factory methods enforce construction invariants
- Prompt variables declared upfront so render() fails cleanly if context is missing keys, vs. silent {var} remain

## What Goes Here

- **Pure domain models with no infra dependencies** — `{entity}.py`
- new_domain_entity → `backend/src/domain/entities/{entity}.py`

## Dependencies

**Exposes to:** `Application Layer`, `Infrastructure Layer`, `API Layer`

## Templates

### domain_entity
**Path:** `backend/src/domain/entities/{entity}.py`
```
from dataclasses import dataclass
from datetime import datetime
@dataclass
class {Entity}:
    id: str
    created_at: datetime
```

# unit/
> Unit tests for scripts, setup integrity, and SQL generation—validate out-of-box project setup and seed data idempotency.

## Patterns

- SQL escaping for prompts: _escape_sql() doubles single quotes, applied to both names and templates before INSERT generation
- Idempotent SQL: all INSERT statements use ON CONFLICT (key) DO UPDATE SET pattern to enable safe re-runs
- Env parsing: _read_env() strips both double/single quotes, skips comments and blank lines, returns dict for backend selection
- File integrity tests: @pytest.mark.parametrize validates required paths exist and executable bits set on shell scripts
- Migration separation: SQL creates tables only; seed_prompts.py handles prompt INSERT/UPDATE—never mix in migration
- Fixture-based setup: SAMPLE_PROMPTS and SAMPLE_PROMPT_WITH_QUOTES reused across multiple test classes to avoid duplication

## Navigation

**Parent:** [`tests/`](../CLAUDE.md)
**Peers:** [`integration/`](../integration/CLAUDE.md)
**Children:** [`api/`](api/CLAUDE.md) | [`domain/`](domain/CLAUDE.md) | [`infrastructure/`](infrastructure/CLAUDE.md) | [`services/`](services/CLAUDE.md) | [`workers/`](workers/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `test_seed_prompts.py` | Validate SQL generation, escaping, env parsing for both backends | Add test class for new script function; reuse SAMPLE_PROMPTS fixture |
| `test_setup_integrity.py` | Verify required files, Docker setup, migrations, env examples | Add file path to parametrize list; add migration table check; validate new env keys |

## Key Imports

- `from unittest.mock import AsyncMock, MagicMock, patch, call`
- `from pathlib import Path`
- `import pytest`

## Add test for new required env key or migration table

1. Add key to @pytest.mark.parametrize('key', [...]) in TestEnvExamples or table name to TestMigrationSQL
2. Parametrization auto-generates N test cases; no need to write individual test_* methods
3. Run pytest backend/tests/unit/test_setup_integrity.py to verify

## Usage Examples

### SQL escape and generation pattern
```python
sql = _generate_sql(SAMPLE_PROMPTS)
assert "it''''s" not in sql  # Not quadruple-escaped
assert "user''s input" in sql  # Properly escaped once
assert "ON CONFLICT (key)" in sql  # Idempotent structure
```

### Env file parsing with tmp_path
```python
def test_parses_simple_env(self, tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("DB_BACKEND=postgres\n")
    result = _read_env(env_file)
    assert result["DB_BACKEND"] == "postgres"
```

## Don't

- Don't insert prompts in migration SQL — seed_prompts.py is sole source of truth for reproducible versioning
- Don't test shell scripts by executing them — parse content with regex and validate structure (file existence, mode bits, required strings)
- Don't mock at fixture level for all tests — pre-build mocks only if shared by 3+ tests, else inline in test_* methods

## Testing

- Use tmp_path fixture for env file tests: write .env.local with test content, pass to _read_env(), assert parsed dict
- SQL generation: call _generate_sql(SAMPLE_PROMPTS), assert 'INSERT INTO', 'ON CONFLICT', and escaped quote strings present

## Debugging

- SQL escape mismatch: verify quotes are doubled once (it's → it''s), not quadrupled (it''''s); regex check: assert "it''''s" NOT in sql
- File not found in parametrize: PROJECT_ROOT = parents[3] from test file; if path wrong, migrate to BACKEND_DIR or PROJECT_ROOT explicitly

## Why It's Built This Way

- Idempotent ON CONFLICT: enables safe re-runs of seed_prompts.py without manual cleanup; matches Postgres/Supabase intent
- Env parsing separate from seed script: _read_env() is reusable utility; script calls it to select backend before connecting

## Subfolders

- [`api/`](api/CLAUDE.md) — 
- [`domain/`](domain/CLAUDE.md) — 
- [`infrastructure/`](infrastructure/CLAUDE.md) — 
- [`services/`](services/CLAUDE.md) — 
- [`workers/`](workers/CLAUDE.md) — 

# _restore/
> SQL restore data snapshots: projects, prompts, and prompt versions for development/testing recovery.

## Patterns

- All files are INSERT statements with full column lists — enables safe partial restores without column-order coupling
- UUIDs for all IDs (projects.id, created_by, client_id) — matches Supabase schema conventions used by backend
- Timestamps in UTC with +00 offset (created_at, updated_at) — consistent with pydantic-settings and FastAPI time handling
- Prompt system/analysis/technical_instructions use template variables {variable_name} — enables parameterized prompt versioning
- JSON response_schema embedded as string property — stored as JSON but queried as text; parse before schema validation
- Version tracking on prompt_versions with change_notes — allows rollback; prompts.version references active version number

## Navigation

**Parent:** [`tuck-in-tales-frontend/`](../CLAUDE.md)
**Peers:** [`src/`](../src/CLAUDE.md)
**Children:** [`backend-src/`](backend-src/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `projects_rows.sql` | Test project fixtures with realistic state progression. | Add rows with valid client_id (dbc627a8-...) and created_by (user UUIDs). Increment step 1-9 for workflow state. |
| `prompts_rows.sql` | Active prompt definitions consumed by analysis endpoints. | Update when prompt logic changes. Keep version aligned with prompt_versions. Template {variable_name} must match backend parameter names. |
| `prompt_versions_rows.sql` | Versioned prompt history; enables version selection and rollback. | Insert before prompts update. Version is integer; change_notes document why. System/analysis/technical_instructions are instruction text, not executable code. |
| `pyproject.toml` | Python dependencies and project metadata for backend. | Pin minor versions (>=X.Y.Z,<X.(Y+1).0). Add new deps under tool.poetry.dependencies, dev under tool.poetry.group.dev. |

## Add test fixture rows for a new project workflow step

1. Copy existing project row from projects_rows.sql, generate new UUID for id
2. Increment current_step, set created_by/created_at to match test user; update updated_at to now
3. Insert into database via psql or Supabase SQL editor; verify foreign keys resolve (client_id, created_by exist)
4. Run backend integration tests against fixture — confirm project loads and workflow state matches expectation

## Usage Examples

### Load fixture in pytest setup
```python
def setup_test_db(supabase_client):
    with open('_restore/projects_rows.sql') as f:
        supabase_client.postgrest.execute_raw(f.read())
    yield
    supabase_client.postgrest.table('projects').delete().neq('id', None).execute()
```

## Don't

- Don't manually construct INSERT statements — use ordered column lists and quoting to match schema exactly
- Don't embed newlines in string values without escaping — use \n or split into separate rows if multi-line content needed
- Don't assume UUID or timestamp formats — always validate against actual database column types in schema

## Testing

- Load entire _restore folder into test database before each suite run; teardown after — ensures reproducible state
- Validate foreign key constraints after INSERT — created_by and client_id must exist in users and clients tables

## Why It's Built This Way

- Template variables {name} in prompts enable single prompt definition to scale across different step counts/target numbers without code changes
- JSON response_schema stored as string (not native JSON type) allows schema evolution without migrations; parse in Python before validation

## Subfolders

- [`backend-src/`](backend-src/CLAUDE.md) — 

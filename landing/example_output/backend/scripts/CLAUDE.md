# scripts/
> One-off utility scripts for pipeline iteration, prompt seeding, and validation—not production code.

## Patterns

- Isolation from main pipeline: rerun_synthesis.py loads cached phase JSONs, runs synthesis alone, saves to disk—no DB writes.
- Idempotent SQL generation: seed_prompts.py reads prompts.json (single source of truth), generates upsert statements, attempts dual-mode execution (psycopg2 + Supabase async).
- Hardcoded repo_id + manual path construction: validate_grounding.py expects REPO_ID constant set at top, walks storage/blueprints and storage/repos manually.
- CLI-driven with argparse or env vars: rerun_synthesis accepts repo_id + optional --model; seed_prompts reads .env.local for DB_BACKEND; validate_grounding is edit-and-run.
- Robust JSON parsing with fallback: rerun_synthesis strips markdown fences, searches for opening brace, gracefully falls back on partial brace extraction.
- Verbose console output with sizing: all scripts print char counts, token usage, or file counts to help debug truncation and understand data flow.

## Navigation

**Parent:** [`backend/`](../CLAUDE.md)
**Peers:** [`src/`](../src/CLAUDE.md) | [`tests/`](../tests/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `rerun_synthesis.py` | Re-synthesize blueprint from cached phase outputs without re-running discovery/layers/patterns. | Change max token limits or model in settings; adjust phase file list if pipeline phases change. |
| `seed_prompts.py` | Upsert analysis_prompts table from prompts.json; supports PostgreSQL and Supabase. | Add new prompts to prompts.json; bump version number. Script auto-generates SQL and executes. |
| `validate_grounding.py` | Spot-check blueprint artifact accuracy against real repo files—not automated, requires manual REPO_ID edit. | Edit REPO_ID constant; add new validation checks by extracting paths from blueprint sections. |

## Key Imports

- `from anthropic import AsyncAnthropic`
- `from domain.entities.blueprint import StructuredBlueprint`
- `from infrastructure.prompts.prompt_loader import PromptLoader`

## Iterate on blueprint synthesis prompt without re-running expensive phase analysis

1. Edit config/settings.py synthesis model or max_tokens
2. Run: PYTHONPATH=src python scripts/rerun_synthesis.py <repo_id>
3. Check storage/blueprints/<repo_id>/blueprint.json for output
4. If JSON parsing fails, inspect storage/blueprints/<repo_id>/synthesis_raw.txt

## Usage Examples

### Phase loading and truncation (rerun_synthesis.py)
```python
parsed = json.loads(raw)
phases[phase_file] = parsed if isinstance(parsed, str) else json.dumps(parsed, indent=2)
# Render with 10k char limits:
prompt_text = prompt.render({"discovery": phases.get("discovery", "")[:10000], ...})
```

### Idempotent SQL upsert (seed_prompts.py)
```sql
INSERT INTO analysis_prompts (..., key) VALUES (...)
ON CONFLICT (key) WHERE key IS NOT NULL DO UPDATE SET
    name = EXCLUDED.name,
    updated_at = NOW();
```

## Don't

- Don't assume prompts.json version—read and compare; seed_prompts.py checks version but doesn't auto-increment.
- Don't rely on DB execution in seed_prompts—always generate + save SQL file for Supabase users to paste manually.
- Don't hardcode repo IDs in scripts—pass as CLI args (rerun_synthesis does this; validate_grounding does not—fix if generalizing).

## Testing

- For rerun_synthesis: verify phase JSONs exist in storage/blueprints/<repo_id>/ before running; inspect token usage in output.
- For seed_prompts: check analysis_prompts table row count matches prompts.json after execution; validate ON CONFLICT upsert by re-running script.

## Debugging

- rerun_synthesis truncation: check stop_reason == 'max_tokens' in output; increase synthesis_max_tokens in settings or shorten phase inputs.
- validate_grounding false positives: file path extraction regex strips ' (notes)' and ' or alternatives'—review raw_paths if paths don't match real files.

## Why It's Built This Way

- Cached phase approach: synthesis can iterate on prompts without re-analyzing code, saving API cost and latency during prompt engineering.
- Dual-mode DB execution in seed_prompts: PostgreSQL via psycopg2 for local dev, async Supabase client for production; falls back to SQL file for manual paste.

# services/
> Orchestrate multi-phase codebase analysis, blueprint generation, and agent instruction file rendering via consistent StructuredBlueprint.

## Patterns

- All outputs (CLAUDE.md, Cursor rules, agent files) derive from single StructuredBlueprint — mutation point for consistency
- AnalysisDataCollector persists cross-process phase data to Supabase; always loads from DB for correctness, falls back to in-memory cache only
- PhasedBlueprintGenerator receives _progress_callback to decouple phase logging from event repository writes
- RuleFile renders platform-specific frontmatter (Claude paths: globs YAML; Cursor: description + alwaysApply boolean)
- AnalysisService checks commit SHA against previous completed analysis to short-circuit incremental mode (no-op if unchanged)
- BlueprintFolderMapper normalizes paths (strip ./, \→/), matches components by specificity, ignores non-matching folders

## Navigation

**Parent:** [`application/`](../CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `agent_file_generator.py` | Render CLAUDE.md, AGENTS.md, topic-split .claude/.cursor rules | Add topic builder function (_build_*_rule), return RuleFile or None |
| `analysis_service.py` | Orchestrate analysis pipeline: start, run phases, persist events | Inject new phase via phased_blueprint_generator; log via _log_event callback |
| `analysis_data_collector.py` | Cache analysis phase data in-memory, persist to Supabase, publish SSE | Call capture_phase_data() after each phase; always _load_from_supabase for cross-process reads |
| `blueprint_folder_mapper.py` | Map StructuredBlueprint sections onto filesystem folder paths | Add _match_* method for new blueprint section type; use _path_specificity for tiebreaking |
| `phased_blueprint_generator.py` | Execute multi-phase analysis using RAG retrieval and AI synthesis | Register phase via _phases dict; hook _progress_callback for logging |

## Key Imports

- `from domain.entities.blueprint import StructuredBlueprint`
- `from infrastructure.persistence.analysis_data_repository import AnalysisDataRepository`
- `from infrastructure.events.event_bus import publish`

## Add new analysis phase (e.g., 'domain_modeling')

1. Register phase in PhasedBlueprintGenerator._phases dict with prompt template
2. Call capture_phase_data() in run_analysis or generator after phase completes
3. Hook _log_event() for progress updates during phase execution
4. Update StructuredBlueprint schema if phase produces new section (e.g., domain_model)

## Usage Examples

### Capture and persist phase data with SSE publish
```python
await analysis_data_collector.capture_phase_data(
    analysis_id, 'domain_modeling',
    gathered={'classes': 42}, sent_to_ai={'prompt': '...'},
    output='...result...', rag_retrieved={'matches': [...]}
)
```

## Don't

- Don't update AnalysisDataCollector in-memory cache without Supabase upsert — worker/API will diverge
- Don't add analysis settings logic to AnalysisService.run_analysis — load via *Repository classes from DB
- Don't emit RuleFile.render_claude/cursor() output; use GeneratedOutput.to_file_map() for all files at once

## Testing

- Mock _progress_callback on PhasedBlueprintGenerator; verify AnalysisService._log_event called with correct event_type
- Verify AnalysisDataCollector._load_from_supabase reconstructs phases sorted by timestamp; mock repository to test fallback

## Debugging

- AnalysisDataCollector: if cross-process data missing, check Supabase upsert succeeded (watch _save_to_supabase exception handling)
- BlueprintFolderMapper: path not matching? Check _normalize_path applied (./stripped, \→/) and _path_specificity tiebreaker

## Why It's Built This Way

- AnalysisDataCollector always reads from Supabase first (not cache) — worker writes progressively, API reads concurrently without races
- RuleFile splits Claude/Cursor rendering — globs YAML only for Claude paths; Cursor always includes frontmatter + alwaysApply boolean

## What Goes Here

- **Orchestration services live in application layer** — `{feature}_service.py`
- new_business_logic → `backend/src/application/services/{feature}_service.py`

## Dependencies

**Depends on:** `Domain Layer`, `Infrastructure Layer`
**Exposes to:** `API Layer`, `Workers`

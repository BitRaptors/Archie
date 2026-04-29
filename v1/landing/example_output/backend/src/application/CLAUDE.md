# application/
> Application layer orchestration: coordinates services to expose multi-phase analysis, blueprint generation, and agent file rendering via single StructuredBlueprint source.

## Patterns

- StructuredBlueprint is the single mutation point—all outputs (CLAUDE.md, Cursor rules, agent files) derive from it to guarantee consistency across analysis phases
- AnalysisDataCollector persists cross-process state to Supabase; always load from DB first, fall back to in-memory cache only when DB unavailable
- Services layer orchestrates multi-phase workflows: analysis → blueprint → rendering; each phase consumes previous phase's output via StructuredBlueprint
- Consistent interface: all service methods accept StructuredBlueprint, mutate it predictably, return it for chaining or persistence

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`api/`](../api/CLAUDE.md) | [`config/`](../config/CLAUDE.md) | [`domain/`](../domain/CLAUDE.md) | [`infrastructure/`](../infrastructure/CLAUDE.md) | [`workers/`](../workers/CLAUDE.md)
**Children:** [`services/`](services/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `__init__.py` | Module exports and public API surface | Export service classes and StructuredBlueprint; maintain stable API for sibling modules |

## Add new rendering phase or service orchestrator

1. Create service class in services/ that accepts StructuredBlueprint + dependencies
2. Mutate Blueprint consistently; persist to Supabase via AnalysisDataCollector
3. Export service in __init__.py; wire into application entry point

## Don't

- Don't instantiate services with hardcoded state—pass StructuredBlueprint and DB client as dependencies for testability and phase chaining
- Don't cache analysis results in-memory without Supabase fallback—cross-process consistency breaks when workers restart
- Don't generate outputs independently—all CLAUDE.md, Cursor rules, agent files must derive from single StructuredBlueprint to prevent drift

## Testing

- Mock Supabase client in tests; verify AnalysisDataCollector loads from DB, falls back to in-memory only on connection failure
- Test service chaining: verify each phase's output feeds next phase's input without Blueprint corruption

## Why It's Built This Way

- Single StructuredBlueprint mutation point ensures all downstream outputs remain synchronized across analysis, rendering, and multi-phase workflows
- Supabase-first persistence with in-memory fallback supports distributed workers without requiring shared state servers

## What Goes Here

- new_business_logic → `backend/src/application/services/{feature}_service.py`

## Dependencies

**Depends on:** `Domain Layer`, `Infrastructure Layer`
**Exposes to:** `API Layer`, `Workers`

## Subfolders

- [`services/`](services/CLAUDE.md) — Orchestrates use cases; coordinates domain + infra; runs analysis workflows

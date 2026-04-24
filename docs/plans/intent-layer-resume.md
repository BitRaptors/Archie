# Plan: `/archie-intent-layer` resume + partial-finalize

**Status**: draft
**Date**: 2026-04-23
**Branch**: `feature/intent-layer-resume`

## Problem

`/archie-intent-layer` runs for minutes to hours on large repos (467 leaf folders on openmeter → ~6 waves of parallel Sonnet subagents). If the user hits a usage cap, context limit, or just closes the laptop mid-run, **there is no path back in.** The command's Phase 1 unconditionally calls `reset-state`, so re-invoking it throws away everything completed so far and starts from scratch.

What the user explicitly asked: *"I'm okay if we drop the not finished batches"* — they want the ability to **continue** OR **force-finalize what's done** so the partial work isn't wasted.

## Current state persistence (good news)

Per-batch state is already durable on disk:

- **`.archie/enrich_state.json`** — `{"done": [<folder>, ...], "wave": N}`. Written by `save-enrichment` after each batch completes. This means **the state needed to resume already exists** — we just don't read it.
- **`.archie/enrichments/<batch_id>.json`** — raw enrichment JSON from each completed subagent.
- **`.archie/enrich_batches.json`** — the folder DAG. Still valid across interruptions as long as the codebase hasn't changed enough to invalidate it.

The only script that destroys progress is `reset-state` (`cmd_reset_state`). It's called exactly once, in Phase 1 of `/archie-intent-layer`. Nothing else touches these files.

## Proposed flow

Turn the current fire-and-forget Phase 1 into a Phase 0 resume decision, mirroring the deep-scan Resume Prelude pattern.

### Phase 0 reconciliation (new)

When `/archie-intent-layer` starts, detect existing partial state:

```bash
python3 .archie/intent_layer.py inspect "$PWD" enrich_state.json --query '.done|length'
python3 .archie/intent_layer.py inspect "$PWD" enrich_batches.json --query '.folders|length' 2>/dev/null
```

Three cases:

1. **Fresh run** — no `enrich_state.json` or `.done` is empty. Proceed as today (Phase 0.5 mode picker → Phase 1 prepare+reset → Phase 2 loop). No change in behaviour.
2. **Partial state present** — `enrich_state.json` has `done: [...]` non-empty AND `enrich_batches.json` exists.
3. **`--continue` or `--finalize-partial` flag given** — skip the interactive prompt, go straight to the chosen path.

For case 2 (and case 3 without explicit flag), call `AskUserQuestion`:

> **Continue or restart?**
> A previous `/archie-intent-layer` run was interrupted. `{N}` of `{M}` folders are already enriched.
>
> 1. **Resume** — pick up where we stopped. Keeps completed enrichments, processes remaining folders, merges everything into per-folder CLAUDE.md files.
> 2. **Finalize partial** — merge what's already done into CLAUDE.md files and skip the unfinished folders. Fast, ends in one step. Use when you can't continue (usage cap, context limit, or just done with it).
> 3. **Fresh start** — discard progress and run from scratch with the mode picker (Phase 0.5).

Map answer → `RESUME_MODE ∈ {resume, finalize_partial, fresh}`.

### Pipeline deltas per mode

| Mode | Phase 0.5 (mode picker) | Phase 1 (prepare + reset) | Phase 2 (wave loop) | Phase 3 (merge) | Phase 4 (cleanup) |
|---|---|---|---|---|---|
| **fresh** (today's behaviour) | Run | Run (prepare + reset-state) | Run | Run | Run |
| **resume** | Skip (mode already decided — pick up what's left) | **Skip reset-state.** Do NOT re-run `prepare` (the DAG is still valid). Just re-create `.archie/enrichments/` if missing. | Run (next-ready picks up from done list automatically) | Run | Run |
| **finalize_partial** | Skip | Skip entirely | **Skip entirely — no new subagents spawn** | Run (merges whatever is in `.archie/enrichments/`) | Run |

The only script-side change needed: none. Every CLI subcommand already supports the semantics we need. The orchestration change is **purely in the `/archie-intent-layer` markdown** — decide which phases to execute based on `RESUME_MODE`.

### CLI flags (shell-level entry, optional)

For scripted callers:

- `/archie-intent-layer --continue` → `RESUME_MODE=resume`, skip the AskUserQuestion if partial state exists
- `/archie-intent-layer --finalize-partial` → `RESUME_MODE=finalize_partial`, skip the AskUserQuestion

Matches deep-scan's `--continue` / `--from N` pattern. Agents that already know they want to resume can pass the flag.

### Deep-scan Step 7 interaction

Deep-scan delegates to `/archie-intent-layer` for the core loop. If deep-scan was interrupted mid-Step-7, `--continue` at the deep-scan level should propagate to `--continue` at the intent-layer level (deep-scan's Resume Prelude already rehydrates `SCAN_MODE`; we just need one more passthrough).

Proposed deep-scan Step 7 delta: when `START_STEP == 7` (Resume Prelude lands here because the deep-scan was mid-Step-7 when compacted), call `/archie-intent-layer` with an **implicit resume**. The blueprint-check in intent-layer's Phase 0 is already skipped per the existing deep-scan delta; add a second delta: treat the intent-layer invocation as `--continue` when in this context.

## Merge semantics (already safe)

`cmd_merge` (`intent_layer.py merge`) reads every `.archie/enrichments/*.json` and writes CLAUDE.md files for each folder enrichment it finds. It already tolerates partial sets — missing folders just don't get a CLAUDE.md written. No change needed.

One verification: make sure `cmd_merge` doesn't delete or clobber existing per-folder CLAUDE.md files for folders that DIDN'T get enriched this run. Need to read `cmd_merge` to confirm; if it does clobber, add an `only-enriched` mode.

## Failure modes to handle

1. **`enrich_batches.json` is stale** (codebase restructured since last run). Resume would process ghost folders that no longer exist or skip new ones. Solution: during resume, diff `enrich_batches.json.folders` against current `scan.json.file_tree`. If drift > 10%, warn: *"DAG may be stale — consider fresh start."* Offer to proceed anyway or abort.
2. **User re-ran `/archie-deep-scan`** between the interrupted intent-layer and the resume attempt. Blueprint has changed; old enrichments might reference components that no longer exist. Solution: compare `last_deep_scan.json.commit_sha` against when `enrich_state.json` was written. If different, suggest fresh start with a loud note (but let the user override).
3. **Orphan enrichment files** in `.archie/enrichments/` that don't correspond to any folder in the current DAG (e.g., a batch covered folders later deleted). Currently `cmd_merge` would try to write CLAUDE.md to a non-existent folder. Solution: `cmd_merge` should `os.path.isdir(folder)` before writing. Low-risk addition.

## Scope & sequencing

Minimum viable (covers the user's ask):

1. **Phase 0 reconciliation prompt** — ~40 lines in `archie-intent-layer.md` (Phase 0 additions before the current Phase 0.5).
2. **`--continue` / `--finalize-partial` flags** — header parser at the top of the command file, 10–15 lines.
3. **Three-way dispatch in Phase 1 / Phase 2** — conditionals that skip `reset-state` / skip the wave loop based on `RESUME_MODE`. Another ~30 lines of markdown.
4. **Defensive `cmd_merge` tweak** — skip write if folder doesn't exist anymore. ~3 lines in `intent_layer.py`.
5. **Deep-scan Step 7 passthrough** — when deep-scan is resuming into Step 7, invoke intent-layer in `--continue` mode. ~5 lines in `archie-deep-scan.md`.

Stretch goals (later):

- **Drift detection** for stale DAGs (failure mode 1 above)
- **Orphan enrichment cleanup** — offer to prune `.archie/enrichments/*.json` entries no longer in the DAG
- **Progress persistence every N folders** within a wave (currently persistence is per-batch via `save-enrichment`, which is already frequent enough — probably unnecessary)

## Tests

- `test_intent_layer_resume.py` (new file):
  - `test_merge_tolerates_missing_enrichments` — `cmd_merge` runs on a partial `.archie/enrichments/` set without crashing
  - `test_merge_skips_deleted_folders` — after the defensive tweak, enrichments pointing at non-existent folders are skipped silently
  - `test_next_ready_skips_done_folders` — already covered? If not, add
  - `test_reset_state_wipes_both_files` — regression guard so we don't accidentally preserve state when the user asks for fresh

No script-level tests for the slash-command flow itself (too integration-y) — manual test plan instead.

## Manual test plan

1. Start `/archie-intent-layer` on a medium repo (10+ folders). Let 2–3 waves complete.
2. Kill with Ctrl+C. Verify `enrich_state.json.done` is non-empty.
3. Re-run `/archie-intent-layer`. Expect AskUserQuestion with "Resume / Finalize partial / Fresh start".
4. Choose **Resume** → pipeline should pick up, no re-processing of done folders, eventually merge → CLAUDE.md files everywhere.
5. Repeat step 1–2. Choose **Finalize partial** → merge only, CLAUDE.md only in enriched folders, unfinished ones get no file (existing ones preserved).
6. Repeat step 1–2. Choose **Fresh start** → reset-state wipes progress, full pipeline runs.
7. `/archie-intent-layer --continue` on clean state (no partial) → Phase 0 prompt should not appear; normal flow runs.
8. `/archie-intent-layer --finalize-partial` on clean state (no enrichments) → print `"Nothing to finalize."` and exit gracefully.

## Open questions

- **Should `--continue` imply the `Auto` mode when deciding incremental vs full?** Leaning no — resume means "finish what was started," so the prior mode is what matters. The mode is encoded in the DAG shape (prepared with or without `--only-folders`), so nothing to re-ask.
- **What happens if the user ran `/archie-intent-layer` in incremental mode, then /archie-deep-scan created a new baseline, then resumed?** The incremental DAG is now stale (its `last_deep_scan.json` reference is gone). Falls under failure mode 2 above — warn and let the user decide.

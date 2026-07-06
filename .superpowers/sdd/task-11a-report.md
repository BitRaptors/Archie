# Task 11a Report: Retire intent_synthesize, rewire PR-gate fallback to story model

## Changes made

### 1. delivery_review.py — fallback rewired
- Replaced the `intent_synthesize.synthesize` fallback (lines 255-265) with the
  `story_synthesize.imprint` fallback as specified.
- Updated the "# 4. Assemble intent" comment from referencing `.archie/intent.json`
  to reference the task story.

### 2. sync.py — dead functions removed
- Deleted `cmd_synthesize_intent`, `cmd_show_intent`, `cmd_confirm_intent`.
- Updated `_intent_imports()` to import only `intent_capture` (removed the
  `intent_synthesize` import that would fail after the module deletion).
- Updated `cmd_capture_intent` to call `ic = _intent_imports()` (no longer unpacks
  a tuple).

### 3. intent_synthesize.py — deleted
- `git rm archie/standalone/intent_synthesize.py`

### 4. Delivery test handling

**test_assemble_pr_intent_prefers_committed_file_no_resolve** — MIGRATED (not removed).
- The test used `intent.write_committed_intent` (the old `.archie/intent.json` path)
  and verified no LLM call when criteria are present. The new `assemble_pr_intent`
  reads from `story_store` (Task 8), so the old fixture was invisible to it.
- Migration: rewrote as `test_assemble_pr_intent_prefers_story_no_resolve` using
  `story_store.write_story` to write a story fixture; still asserts the story's
  facts become `acceptance_criteria` and no LLM resolve is called.
- `test_delivery_story_intent.py::test_assemble_pr_intent_uses_story_facts` covers
  the same path, but the migrated test adds the "no LLM call" assertion
  (`called["resolve"] == 0`), which that file does not check.

**test_run_pr_gate_auto_synthesizes_when_intent_missing** — MIGRATED (not removed).
- Mocked `intent_synthesize.synthesize` — the retired path.
- Migrated to `test_run_pr_gate_auto_imprints_when_no_story`: mocks
  `story_synthesize.imprint` and asserts it is called once when no current story
  exists. The fake imprint writes a real story via `story_store.write_story` so
  `assemble_pr_intent` can pick it up, preserving the end-to-end integrity check.

No test was removed; both retired-path tests were fully migrated.

**Did any test mock intent_synthesize?** Yes — `test_run_pr_gate_auto_synthesizes_when_intent_missing`.
Migrated above.

## Test result

```
python3 -m pytest tests/test_delivery_review.py tests/test_delivery_story_intent.py \
    tests/test_story_store.py tests/test_story_synthesize.py tests/test_story_subcommands.py -q
44 passed in 0.74s
```

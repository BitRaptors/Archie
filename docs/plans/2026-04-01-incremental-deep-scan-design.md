# Incremental Deep Scan Design

## Overview

Make `/archie-deep-scan` incremental by default. Only process what changed since the last deep scan. Fall back to full baseline when changes are too large or when explicitly requested.

## Behavior

```
/archie-deep-scan                → full baseline (current behavior, unchanged)
/archie-deep-scan --incremental  → incremental if blueprint exists, auto-falls back to full if too many changes or no blueprint
/archie-deep-scan --from N       → resume from step N (existing feature, unchanged)
```

## Change Detection

On incremental run:
1. Read last deep scan timestamp from `.archie/health_history.json` (latest entry with `scan_type: "deep"`)
2. Run `git diff --name-only <timestamp>..HEAD` to get changed files
3. Count changed files and compute ratio: `changed / total_files`

**Threshold decision:**
- If no blueprint exists → full baseline (first run)
- If `--full` flag → full baseline
- If changed files > 30 OR changed ratio > 20% → full 3-agent Wave 1
- Else → single focused incremental agent

## Per-Step Incremental Strategy

### Step 1: Scanner (unchanged)
Always runs fully — it's fast (<10s) and produces scan.json + skeletons.json that other steps depend on.

### Step 2: Read scan (unchanged)
Same as today.

### Step 3: Wave 1 — Incremental vs Full

**Full mode (first run, --full, or large change set):**
Same as today — 3 agents (Structure, Patterns, Technology) + optional UI Layer agent. Each reads the full codebase.

**Incremental mode:**
Single Sonnet agent with this context:
- The changed file list
- Current `blueprint_raw.json` (existing knowledge)
- Skeletons for changed files only
- The scan.json import graph (to understand what the changes affect)

Agent prompt: "These files changed since the last deep scan. Read them and the existing blueprint. Report what changed architecturally: new components, modified responsibilities, new patterns, changed dependencies, new technology. Return the same JSON structure as the full agents but only for affected sections."

Output: incremental findings JSON.

### Step 4: Merge — Patch vs Replace

**Full mode:** Same as today — merge all agent outputs into blueprint_raw.json.

**Incremental mode:** Patch the existing blueprint_raw.json:
- New components → add to components list
- Modified components → update in place (match by name/location)
- Removed files → flag components that may be stale
- New patterns/integrations → add
- Changed technology → update

The merge.py script needs a `--patch` mode that reads existing blueprint_raw.json and applies incremental findings.

### Step 5: Wave 2 Reasoning — Scoped vs Full

**Full mode:** Same as today — Opus reads everything, produces full reasoning.

**Incremental mode:** Opus gets:
- Existing blueprint.json (full architecture knowledge)
- The incremental diff from Step 4 (what changed)
- Changed file contents

Agent prompt: "The architecture was previously analyzed. These changes occurred. Update the decisions, trade-offs, and pitfalls ONLY if the changes affect them. Return only the sections that changed — unchanged sections will be preserved from the existing blueprint."

finalize.py needs a `--patch` mode that merges updated sections into existing blueprint.json.

### Step 6: Rule Synthesis — Additive

**Full mode:** Same as today — generate 20-40 rules.

**Incremental mode:** Agent gets:
- Existing rules.json
- The changed files and what changed architecturally (from Step 5)

Agent prompt: "These are the existing rules. These files changed. Are any existing rules now violated? Do the changes introduce new patterns that need new rules? Only propose new rules — do not regenerate existing ones."

extract_output.py merge logic already preserves existing rules by ID — this works as-is.

### Step 7: Intent Layer — Selective Re-enrichment

**Full mode:** Same as today — enrich all folders.

**Incremental mode:**
1. Identify affected folders: folders containing changed files + their parent chain
2. Run `intent_layer.py next-ready` but filtered to only affected folders
3. Re-enrich only those folders (using existing child summaries for unchanged children)
4. Merge: only overwrite CLAUDE.md for re-enriched folders

This is the biggest time savings — going from 107 folders to maybe 5-10.

### Step 8: Cleanup (unchanged)

### Step 9: Drift Detection — Scoped

**Full mode:** Same as today — full mechanical + AI drift.

**Incremental mode:**
- Mechanical drift (drift.py): runs on full codebase (it's fast)
- AI deep drift: only analyze changed files, not the full recent-files list

## Data Model Changes

### New fields in health_history.json entries
```json
{
  "scan_type": "deep",
  "scan_mode": "incremental",     // NEW: "full" or "incremental"
  "changed_files_count": 12,      // NEW: how many files triggered this scan
  "changed_ratio": 0.024          // NEW: changed/total ratio
}
```

### New file: .archie/last_deep_scan.json
```json
{
  "timestamp": "ISO-8601",
  "commit_sha": "abc123",
  "mode": "full",
  "steps_completed": [1,2,3,4,5,6,7,8,9]
}
```
Used for change detection: `git diff <commit_sha>..HEAD`.

## merge.py Changes

Add `--patch` mode:
```bash
python3 .archie/merge.py "$PROJECT_ROOT" --patch incremental_findings.json
```
Reads existing blueprint_raw.json, applies incremental changes, writes back.

## finalize.py Changes

Add `--patch` mode:
```bash
python3 .archie/finalize.py "$PROJECT_ROOT" --patch incremental_reasoning.json
```
Reads existing blueprint.json, merges updated sections, re-renders only changed rule files and CLAUDE.md.

## intent_layer.py Changes

Add `--only-folders` flag:
```bash
python3 .archie/intent_layer.py prepare "$PROJECT_ROOT" --only-folders folder1,folder2,...
```
Only marks specified folders (and their parent chain) as needing enrichment.

## Expected Performance

| Step | Full (today) | Incremental (small change) |
|------|-------------|--------------------------|
| Scanner | 10s | 10s |
| Wave 1 | 2-3 min (3 agents) | 30-60s (1 agent, fewer files) |
| Wave 2 | 2-3 min (Opus) | 1-2 min (Opus, scoped context) |
| Rule synthesis | 1 min | 30s |
| Intent layer | 5-8 min (107 folders) | 1-2 min (5-10 folders) |
| Drift | 2-3 min | 1 min |
| **Total** | **15-20 min** | **3-6 min** |

## Implementation Priority

1. Change detection + threshold logic in archie-deep-scan.md
2. Single-agent incremental Wave 1 prompt
3. merge.py --patch mode
4. finalize.py --patch mode
5. intent_layer.py --only-folders
6. Scoped Wave 2 reasoning
7. Scoped rule synthesis
8. last_deep_scan.json tracking

Steps 1-2 give the biggest win with least code change — even without patching, we can just run the full merge/finalize but with smaller agent input.

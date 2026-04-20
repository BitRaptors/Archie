# Deep-scan pitfall seeding — plan

**Branch:** `feature/deep-scan-pitfall-seeding`
**Date:** 2026-04-20
**Status:** draft — awaiting approval before implementation

## Problem

Running `/archie-scan` then `/archie-deep-scan` in sequence gives a much clearer picture of architectural problems than running either alone. Today the two commands operate independently — scan's findings are prose in `scan_report.md`, deep-scan's Opus Wave 2 reasons from first principles without ever reading scan's output. Users have to run both to get the full signal.

Previous attempt (shelved on `docs/scan-consolidation`) unified the agent roster across both scans. The output quality was good but runtime and token cost became unacceptable.

## Goal

A single `/archie-deep-scan` run produces the quality of today's sequential `/archie-scan` + `/archie-deep-scan`, with:

- no shared Wave 1 roster (keep the cheap scan and deep scan separate)
- scan's findings consumed as seeds for deep-scan's reasoning
- a consistent 4-field finding/pitfall schema shared across both

## Conceptual model

- **Finding** — "this specific problem exists in the code right now." Per-run artifact from scan. Lifecycle: NEW / RECURRING / RESOLVED. Evidence is concrete (file:line). Fix_direction is tactical.
- **Pitfall** — "this *kind* of problem is structurally likely given the architecture." Durable blueprint entry. Covers current manifestations and latent traps. Evidence cites architectural decisions; fix_direction is strategic and sequenced.

Both share the 4-field core: `{problem_statement, evidence, root_cause, fix_direction}`.

Scan → produces findings (`draft` depth).
Deep-scan → upgrades findings to `canonical` depth AND emits pitfalls in the blueprint. May also emit new findings it discovers from the overall-picture pass.

## Schema

### Finding
```json
{
  "id": "f_0001",
  "problem_statement": "string, one sentence",
  "evidence": ["file.py:42", "pattern in N files", "..."],
  "root_cause": "string, specific to this codebase",
  "fix_direction": "string, tactical, single sentence (scan) | ordered list of steps (deep-scan upgrade)",
  "severity": "error | warn | info",
  "confidence": 0.0,
  "applies_to": ["src/auth/"],
  "source": "scan:structure | scan:health | scan:patterns | deep:synthesis",
  "depth": "draft | canonical",
  "pitfall_id": "pf_NNNN (optional, set by deep-scan when a finding is tied to a pitfall)",
  "first_seen": "YYYY-MM-DDTHHMM UTC",
  "confirmed_in_scan": 1,
  "status": "active | resolved"
}
```

### Pitfall
Same required fields as Finding. Differences:
- `id` prefix `pf_` instead of `f_`
- `fix_direction` always an ordered list of steps
- `applies_to` = component/folder paths (broader than finding-level file paths)
- `source` always `deep:synthesis`
- `depth` always `canonical`
- No `stems_from` field (removed from the existing pitfall schema as part of this work)

### Storage
- `.archie/findings.json` — written by scan, updated by deep-scan
- `blueprint.pitfalls[]` in `.archie/blueprint.json` — written by deep-scan

## Quality bar (both schemas)

Quality-gated, not quantity-gated.

A finding or pitfall is valid only if:
- `problem_statement` is specific (not "code is complex")
- `evidence` is non-empty and references concrete code observations
- `root_cause` names a decision, pattern, or constraint — not a generic explanation
- `fix_direction` is actionable

**Soft floor of 3.** If an agent emits fewer than 3 items, it must explicitly state why (e.g., "area is clean; only one meaningful issue found"). The constraint prevents silent empty output but never forces fake content.

No hard upper cap. Render-time clipping in `scan_report.md` only (top-N by severity × confidence).

## Coupling

**Soft coupling, accumulating store.** `.archie/findings.json` is a shared, compounding store. Both `/archie-scan` and `/archie-deep-scan` read it on entry and write it on exit. Neither command requires the other to have run first — either can run any number of times in any order. Findings accumulate across runs: new ones are appended, recurring ones bump `confirmed_in_scan`, resolved ones flip `status`.

Deep-scan's value-add when findings exist: upgrade draft findings to canonical (richer `root_cause`, sequenced `fix_direction`) and add pitfalls rooted in architectural reasoning. Deep-scan's value-add when findings don't exist: produce canonical findings + pitfalls from scratch via Wave 2 analysis.

No staleness check, no prereq check.

## Files to touch

1. **`.claude/commands/archie-scan.md`** — Phase 4.
   - Insert new section `### 4b: Write structured findings` between current 4a (Evolve Blueprint) and current 4b (Write Scan Report, renumber to 4c).
   - Include: quality bar, finding schema, id-stability rules across scans, output path `.archie/findings.json`.
   - Renumber downstream subsections (4c, 4d, 4e).

2. **`.claude/commands/archie-deep-scan.md`** — Step 5 (Wave 2 Reasoning agent).
   - Add prereq check at top of Step 5: read `findings.json`, stop with actionable message if missing or stale (>24h).
   - Add `.archie/findings.json` to Wave 2 inputs.
   - Insert new subsection "6. Upgrade findings" before current section 6 (Pitfalls), renumber downstream.
   - Rewrite Pitfalls subsection to use the 4-field schema (drop `stems_from`; add `problem_statement`, `evidence`, `root_cause`; `fix_direction` is ordered list).
   - Update the JSON return schema block.

3. **`archie/standalone/renderer.py`** — strip `stems_from` rendering from pitfalls (~lines 393–406) and render the new 4-field shape. Also accept the new `findings[]` top-level key if present (for provenance, rendered or not TBD).

4. **`archie/standalone/finalize.py` / `merge.py`** (TBD — investigate during implementation). Any normalization code that expects `{area, description, recommendation, stems_from}` needs updating to the new 4-field shape. Existing blueprints with old pitfalls: migrate on first write.

5. **Sync mirrors:**
   - `npm-package/assets/archie-scan.md` ← `.claude/commands/archie-scan.md`
   - `npm-package/assets/archie-deep-scan.md` ← `.claude/commands/archie-deep-scan.md`
   - `npm-package/assets/renderer.py` ← `archie/standalone/renderer.py`
   - Plus any touched python files under `archie/standalone/`.
   - Run `python3 scripts/verify_sync.py` before commit.

## Implementation order

1. Draft the scan Phase 4b prompt change. Commit.
2. Draft the deep-scan prereq + Step 5 upgrade/pitfalls prompt changes. Commit.
3. Update `renderer.py` (and any `finalize.py`/`merge.py` touch points) for the new pitfall shape. Commit.
4. Sync npm-package assets. Run `verify_sync.py`. Commit.
5. Dogfood on Archie itself and `BabyWeather.Android`: run scan, inspect `findings.json`, run deep-scan, confirm upgrade chain (same ids, enriched root_cause/fix_direction) and pitfalls emitted. Iterate prompts as needed.

## Migration (existing blueprints)

Blueprints in the wild today have pitfalls with `{area, description, recommendation, stems_from, ...}`. On next deep-scan run on such a project:

- `renderer.py` tolerates legacy fields during a transition (reads old shape if new shape absent).
- Wave 2 rewrites pitfalls into the new shape; old fields are dropped after that run.
- No data migration script needed — the next deep-scan is the migration.

Decision point: whether to keep `area`, `description`, `recommendation` as transitional aliases in the renderer or do a clean break. Leaning clean break (simpler), confirmed during implementation if it causes user pain.

## Out of scope

- UI/viewer rendering of the new `findings.json` (separate pass if useful).
- Surfacing findings in `/archie-share` bundle (separate pass).
- Trend analysis across scans using findings (natural next step, not this PR).
- Pulling semantic findings spec / aggregator from the shelved branch (revisit later if demand arises).

## Open questions

- Is 24h the right staleness threshold? Could also be "scan_count equal to previous deep-scan's scan_count + 0 or 1".
- Should a deep-scan that creates a new pitfall `pf_N` retroactively set `pitfall_id` on *all* findings that match that pitfall, or only the one that surfaced it?
- Do we want a `resolved_at` on findings that flip to status `resolved`? (Minor, not blocking.)

---

When this plan is approved, implementation proceeds in the order above, each step committed separately for reviewability.

# Deterministic iOS Platform-Pitfall Seed — Design

**Date:** 2026-06-10
**Status:** Approved (design), pending implementation plan
**Author:** benchmark-driven (gasztro iOS measurements)

## Goal

Make `/archie-deep-scan` **deterministically and reliably** emit a known pitfall for
legacy Xcode projects: *new `.swift` source files must be registered in
`project.pbxproj` (`PBXSourcesBuildPhase`) or they are excluded from the build and
won't compile.* The pitfall must land in the blueprint's `pitfalls` and render into
the generated context (`pitfalls.md`) without depending on AI synthesis.

## Motivation (evidence)

The internal benchmark harness measured Archie on `Gasztroterkepek.iOS` ("add a
favorite restaurant" feature, Sonnet arms, Opus blind judge, n=3 ×3 runs):

- Without any pbxproj guidance, the Archie (treatment) arm is **high-variance**: it
  writes idiomatic code but **intermittently creates a new `.swift` file and forgets
  to register it in `project.pbxproj`** → build breaks → judge 4.5/5.0. One n=3 run
  averaged 8.70, another 5.50 (2/3 reps build-broken).
- A controlled experiment hand-injected this exact pitfall into the treatment context
  (faithful Archie format, in `pitfalls.md` + `dev-rules.md`). Result: treatment
  quality 5.50 → **8.33**, and the build-breaking failure mode **vanished** (0/3
  reps; judge: *"service properly added to the Xcode project"*).

The lever is proven. The AI deep-scan did not surface this pitfall on its own, so the
fix must be **deterministic**, not another AI prompt nudge.

## Approach (chosen)

Deterministic seed: the scanner detects a legacy-Xcode signal; `finalize` merges a
known pitfall (from a seed file) into the blueprint when the signal is present. This
parallels the existing `platform_rules.json` deterministic-seed pattern and is fully
unit-testable without mocking LLM agents.

Rejected alternatives:
- **Prompt-only** (add guidance to the Wave 2 Risk sub-agent prompt): re-introduces
  the exact AI-reliability failure we are fixing; not deterministically testable.
- **Hybrid** (deterministic signal → AI authors the pitfall): emission still hinges
  on the AI; more moving parts for no reliability gain over the pure seed.

## Architecture

Data flow (all deterministic Python, no AI in the path):

```
scanner.py  ──signal──▶  finalize.py  ──merged pitfall──▶  renderer.py ──▶ pitfalls.md
(detect)                 (seed + dedup)                    (unchanged)
```

### Component 1 — Scanner signal (`archie/standalone/scanner.py`)

- When an Xcode project is detected (a `*.xcodeproj/project.pbxproj` exists), read
  that `project.pbxproj` and test for the folder-sync marker
  `PBXFileSystemSynchronizedRootGroup` (plain substring search; read the file once).
- If the marker is **absent** → the target is a legacy, hand-maintained build phase →
  emit the signal. If **present** (Xcode 16 folder-synchronized) → no signal (those
  projects auto-include files on disk).
- Pure SPM projects (`Package.swift`, no `.xcodeproj`) emit **no** signal — SPM
  compiles sources by directory convention.
- Output: add to the scanner's result dict a new field
  `"platform_pitfall_signals": [ { "signal": "ios_legacy_xcode_no_folder_sync",
  "evidence_path": "<rel path to the detected project.pbxproj>" } ]`.
  Empty list when nothing matches. If multiple `.xcodeproj` match, emit a **single**
  signal entry (deduped by signal name); `evidence_path` is the first matching
  `project.pbxproj` in sorted order (deterministic).

**Interface:** a new pure function, e.g.
`detect_platform_pitfall_signals(root: Path, subprojects: list[dict]) -> list[dict]`,
called from the scanner's main assembly and stored under `platform_pitfall_signals`.
It depends only on the filesystem; testable in isolation with a fixture pbxproj.

### Component 2 — Seed data (`archie/standalone/platform_pitfalls.json`, NEW)

A small JSON catalog, analogous to `platform_rules.json`:

```json
{
  "pitfalls": [
    {
      "signal": "ios_legacy_xcode_no_folder_sync",
      "pitfall": {
        "id": "pf_ios_pbxproj_registration",
        "problem_statement": "New .swift source files are not auto-discovered in this legacy .pbxproj-listed Xcode target (no folder-synchronized groups), so a freshly created file not registered in the target's PBXSourcesBuildPhase is excluded from compilation and any code referencing it fails to build.",
        "evidence": ["<filled at merge time with the detected project.pbxproj path>"],
        "root_cause": "The project predates Xcode 16 folder-synchronized groups, so target membership is governed by hand-maintained .pbxproj records rather than file presence on disk. Creating a file outside Xcode's \"Add Files…\" writes it to disk but never registers it, and no build/test gate surfaces the omission until compilation fails.",
        "fix_direction": [
          "When adding a new .swift file, also edit <project>.xcodeproj/project.pbxproj: add a PBXFileReference, a PBXBuildFile, the owning group's child entry, and a PBXSourcesBuildPhase files entry — mirror an existing file.",
          "Prefer extending an existing same-layer file over creating a new one when the addition is small, to avoid pbxproj surgery.",
          "Use unique 24-hex-character object IDs for new pbxproj entries (never synthetic placeholders like FAV1/FAV2).",
          "After adding, confirm the file appears under the target's Compile Sources before relying on it."
        ],
        "severity": "error",
        "confidence": 1.0,
        "applies_to": [],
        "source": "platform_signal",
        "depth": "canonical"
      }
    }
  ]
}
```

The catalog is a list so future platform pitfalls (Android, etc.) can be added without
schema change (YAGNI: ship only the iOS entry now).

### Component 3 — Merge (`archie/standalone/finalize.py`)

- After `finalize` assembles `blueprint["pitfalls"]` from the agent files, load
  `platform_pitfalls.json` and the scanner's `platform_pitfall_signals`.
- For each present signal, look up its seeded pitfall. If a pitfall with the same `id`
  is **not** already in `blueprint["pitfalls"]`, append it — filling `evidence` with
  the signal's `evidence_path`. **Dedup by `id`** so re-scans are idempotent.
- Tag origin via `source: "platform_signal"` (already in seed).

**Interface:** a new pure function
`merge_platform_pitfalls(pitfalls: list[dict], signals: list[dict], catalog: dict) -> list[dict]`
returning the merged list. No I/O inside it (catalog + signals passed in) → trivially
testable; `finalize` does the file loading and calls it.

### Component 4 — Render (unchanged)

`renderer.py::_build_pitfalls_rule` already renders `blueprint["pitfalls"]` into
`pitfalls.md`. The seeded pitfall flows through with no renderer change.

### Component 5 — Install + sync

- `platform_pitfalls.json` must be available where deep-scan runs (the installed
  `.archie/` scripts). Add it to the install manifest alongside `platform_rules.json`,
  and copy canonical → `npm-package/assets/` (and any backend asset mirror).
- `scripts/verify_sync.py` already checks `archie/standalone/*.json` vs
  `npm-package/assets/*.json`, so the new JSON is covered once copied.

## Testing strategy (TDD)

1. **Scanner detection** (`tests/test_scanner.py`):
   - Fixture A: `App.xcodeproj/project.pbxproj` WITHOUT the marker → signal emitted
     with the correct `evidence_path`.
   - Fixture B: pbxproj WITH `PBXFileSystemSynchronizedRootGroup` → no signal.
   - Fixture C: `Package.swift` only, no `.xcodeproj` → no signal.
2. **Merge** (new test, e.g. `tests/test_platform_pitfalls.py`):
   - signal + catalog → pitfall present in output, `evidence` filled with the path.
   - re-run with the pitfall already present → no duplicate (dedup by id).
   - no signal → pitfalls unchanged.
3. **Sync**: `python3 scripts/verify_sync.py` passes after copying.

## Validation plan (post-implementation)

1. Revert the experimental hand-injection commit on `Gasztroterkepek.iOS` (`251e35e`)
   so the repo no longer carries the manual pitfall.
2. Re-run `/archie-deep-scan` (or the deterministic scan→finalize path) on gasztro and
   confirm `pf_ios_pbxproj_registration` appears in the regenerated `pitfalls.md`
   **automatically**.
3. Re-run the benchmark (n=3) and confirm the build-breaking failure mode stays gone
   (treatment ~8.3, no 4.5/5.0 reps). Append to the durable log for comparison.

## Scope

**In:** scanner signal detection, the seed catalog (one iOS pitfall), the finalize
merge with dedup, install-manifest + npm copies, unit tests, the validation re-run.

**Out (YAGNI):** Android/other platform pitfalls; a generic build-manifest framework;
auto-editing `project.pbxproj` for the user; a real-time enforcement hook (the
non-mechanical, single-file hook cannot do cross-file pbxproj checks — explicitly
rejected during research); changing the renderer or the Wave 2 prompts.

## Resolved decisions

- **Signal name:** `ios_legacy_xcode_no_folder_sync`.
- **Seed location:** `archie/standalone/platform_pitfalls.json` (canonical), mirrored
  to `npm-package/assets/`.
- **Seed authority vs AI:** the seed is authoritative for its `id`; the Wave 2 Risk
  agent does not need to know about it. If the agent independently emits an
  overlapping pitfall under a different id, both render (acceptable for v1).
- **Idempotency:** dedup by pitfall `id` at merge time.
```

# Platform Pitfalls — How the System Works & How to Extend It

A guide for contributors (human or AI) who want to understand or extend Archie's
**deterministic platform-pitfall seed** system, and the test conventions around it.

## What this system is (and why)

Archie's deep-scan normally synthesises pitfalls with an AI agent (Wave 2). That is
great for codebase-specific traps, but it is **unreliable for well-known platform
facts** — the AI sometimes just misses them.

A concrete example drove this feature: on legacy Xcode (iOS) projects, a newly created
`.swift` file must be manually registered in `project.pbxproj` or it is silently
excluded from the build. The AI deep-scan did not surface this, and a benchmark showed
the agent intermittently shipping non-compiling code because of it (quality dropped from
~8.7 to ~5.5 on the runs that hit it). Injecting the pitfall into the context fixed it.

So this system makes such **known, deterministically-detectable** pitfalls appear in the
generated context **every time**, with no AI in the path.

## How it works (data flow)

```
scanner.py            scan.json                 finalize.py                 renderer.py
detect_platform_   →  "platform_pitfall_   →    merge_platform_pitfalls  →  pitfalls.md
  pitfall_signals       signals": [...]           (into blueprint.pitfalls)   (agent reads this)
```

1. **Detect** — `archie/standalone/scanner.py::detect_platform_pitfall_signals(root)`
   inspects the repo and returns a list of signals, e.g.
   `[{"signal": "ios_legacy_xcode_no_folder_sync", "evidence_path": "App.xcodeproj/project.pbxproj"}]`.
   `run_scan` writes this under `scan.json["platform_pitfall_signals"]` (empty list when
   nothing matches).

2. **Seed catalog** — `archie/standalone/platform_pitfalls.json` maps each signal name to
   a canonical pitfall object:
   ```json
   {"pitfalls": [{"signal": "<signal-name>", "pitfall": {"id": "...", "problem_statement": "...", ...}}]}
   ```

3. **Merge** — `archie/standalone/finalize.py::merge_platform_pitfalls(pitfalls, signals, catalog)`
   is a **pure** function (no I/O). For every present signal it deep-copies the seeded
   pitfall, fills its `evidence` from the signal's `evidence_path`, and appends it —
   **deduped by pitfall `id`**, so re-scans are idempotent. `finalize()` calls it (loading
   `scan.json` + `platform_pitfalls.json` from `.archie/`) right before it writes
   `blueprint.json`.

4. **Render** — the existing `renderer.py::_render_pitfall_lines` turns
   `blueprint["pitfalls"]` into `.claude/rules/pitfalls.md`. **No renderer change is
   needed** — a seeded pitfall uses the same canonical shape as an AI-authored one.

### Key invariants
- **Deterministic** — detection is a filesystem/string check, never an LLM call.
- **Idempotent** — dedup by `id`; running the scan twice does not duplicate the pitfall.
- **Scoped** — a signal only fires when its precondition holds (e.g. an Xcode project
  that is NOT folder-synchronized; SPM-only projects emit nothing).
- **Two scanners exist:** `archie/standalone/scanner.py` is the one deep-scan runs (edit
  this); `archie/engine/scanner.py` is a separate packaged scanner — leave it alone unless
  the task is about the `archie-cli` package.

## How to add a NEW platform pitfall

Say you want to warn Android projects that `release` builds strip code via R8 and need
`@Keep` on reflection-accessed classes. You would:

1. **Add detection** (if a new signal is needed) in
   `archie/standalone/scanner.py::detect_platform_pitfall_signals`. Return a
   `{"signal": "<name>", "evidence_path": "<rel path>"}` entry when the precondition holds.
   Keep it cheap and deterministic (glob + substring check, like the iOS one). Reuse an
   existing signal if one already implies your precondition.

2. **Add the seed** to `archie/standalone/platform_pitfalls.json` — a new
   `{"signal": "<name>", "pitfall": {...}}` object. The pitfall must use the canonical
   fields: `id` (unique, e.g. `pf_android_r8_keep`), `problem_statement`, `evidence` (leave
   `[]` — the merge fills it), `root_cause`, `fix_direction` (list of steps), `severity`
   (`error`/`warn`), `confidence`, `applies_to`, `source: "platform_signal"`,
   `depth: "canonical"`.

3. **Nothing else** — the merge and renderer are generic; your pitfall flows through
   automatically.

4. **Sync the data file** to all three locations and verify:
   ```bash
   cp archie/standalone/platform_pitfalls.json archie/assets/platform_pitfalls.json
   cp archie/standalone/platform_pitfalls.json npm-package/assets/platform_pitfalls.json
   python3 scripts/verify_sync.py        # must print "SYNC CHECK PASSED"
   ```
   (If you changed `scanner.py`/`finalize.py`, also copy them to `npm-package/assets/`.)

## How to add tests

Archie's standalone scripts are **pure stdlib, not importable as a package**, so tests
load them **by path** with `importlib`. Copy this idiom (from `tests/test_platform_pitfall_signal.py`):

```python
import importlib.util, sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "_archie_scanner",
    Path(__file__).resolve().parent.parent / "archie" / "standalone" / "scanner.py",
)
_scanner = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_scanner"] = _scanner
_SPEC.loader.exec_module(_scanner)
```

Three existing test files are your templates — mirror them for a new pitfall:

| Test file | What it covers |
|---|---|
| `tests/test_platform_pitfall_signal.py` | `detect_*` — positive (signal fires) **and** negatives (precondition absent). Always test the negative cases. |
| `tests/test_platform_pitfalls_merge.py` | `merge_platform_pitfalls` — append + evidence fill, dedup idempotency, no-signal passthrough, unknown-signal ignored. |
| `tests/test_finalize_platform_pitfall.py` | `finalize()` end-to-end — a `.archie/` with `blueprint_raw.json` + `scan.json` + `platform_pitfalls.json` ⇒ the pitfall id lands in `blueprint.json`. Uses `finalize(root, agent_files=None)` (no AI). |

**Rules of thumb (follow these — they are how the repo works):**
- **TDD:** write the failing test first, run it to confirm it fails, then implement, then
  confirm it passes. One behaviour per test.
- **Always test the negative path** — a detector that never returns `[]` is a bug magnet.
- **Keep merge tests pure** — pass the catalog/signals in; never reach the filesystem.
- **Add an integration test** through `finalize()` so producer and consumer shapes can't
  silently drift apart.

### Running tests
```bash
python -m pytest tests/test_platform_pitfall_signal.py tests/test_platform_pitfalls_merge.py tests/test_finalize_platform_pitfall.py -v
python -m pytest tests/ -q          # full suite — must stay green
python3 scripts/verify_sync.py      # the 3 data-file copies + installers must match
```

## Validating real impact (optional)

The internal benchmark harness (`python3 -m archie.benchmark`, see
`archie/benchmark/README.md`) can measure whether a pitfall actually changes agent
behaviour: run the same task on a control arm (no Archie) and a treatment arm (with the
pitfall in context) and compare a blind judge's quality scores. That is how this system's
value was established — but it is not required for adding a routine pitfall; the unit +
integration tests above are the gate.

## File map

| Path | Role |
|---|---|
| `archie/standalone/scanner.py` | `detect_platform_pitfall_signals` + `run_scan` wiring (canonical; deep-scan runs this) |
| `archie/standalone/platform_pitfalls.json` | the seed catalog (signal → pitfall) |
| `archie/standalone/finalize.py` | `merge_platform_pitfalls` (pure) + the call before `blueprint.json` is written |
| `archie/standalone/renderer.py` | `_render_pitfall_lines` — renders pitfalls into `pitfalls.md` (unchanged by this system) |
| `archie/assets/` + `npm-package/assets/` | byte-identical copies of the standalone scripts + the seed JSON (kept in sync by `scripts/verify_sync.py`) |
| `archie/install.py`, `npm-package/bin/archie.mjs` | install the seed JSON into a target repo's `.archie/` |
| `tests/test_platform_pitfall*.py` | the three test files above |

Design + plan for the original feature: `docs/specs/2026-06-10-ios-platform-pitfall-seed-design.md`
and `…-plan.md`.

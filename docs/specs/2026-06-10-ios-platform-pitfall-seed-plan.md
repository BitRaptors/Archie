# Deterministic iOS Platform-Pitfall Seed — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/archie-deep-scan` deterministically emit the "register new `.swift` files in `project.pbxproj`" pitfall for legacy (non-folder-synchronized) Xcode projects, so it always lands in the generated context — no AI synthesis in the path.

**Architecture:** The standalone scanner (`archie/standalone/scanner.py`, the copy deep-scan runs) detects the signal and writes it into `scan.json`. `finalize.py` loads a seed catalog (`platform_pitfalls.json`) and merges the matching pitfall into `blueprint["pitfalls"]` (dedup by id) before the existing renderer turns it into `pitfalls.md`. The seed file ships through the same install/sync surfaces as `platform_rules.json`.

**Tech Stack:** Python 3.9+ stdlib (json, pathlib, os), pytest, Node installer (`archie.mjs`).

**Spec:** `docs/specs/2026-06-10-ios-platform-pitfall-seed-design.md`

**Out of scope:** The parallel packaged scanner `archie/engine/scanner.py` / `archie/engine/scan.py` is NOT used by deep-scan (deep-scan runs the installed copy of `archie/standalone/scanner.py`); leave it unchanged. No Android/other pitfalls, no `.pbxproj` auto-editing, no enforcement hook.

---

## File Structure

- `archie/standalone/scanner.py` — add `detect_platform_pitfall_signals()`, wire into `run_scan` return. (canonical; synced to `npm-package/assets/scanner.py`)
- `archie/standalone/finalize.py` — add pure `merge_platform_pitfalls()`, call it before the blueprint.json write. (canonical; synced to `npm-package/assets/finalize.py`)
- `archie/standalone/platform_pitfalls.json` — NEW seed catalog. (canonical; copied to `archie/assets/` and `npm-package/assets/`)
- `archie/install.py` — add the seed file to the installed data-files tuple.
- `npm-package/bin/archie.mjs` — add the seed file to the data-files array + the installed `.gitignore` block.
- `tests/test_platform_pitfall_signal.py` — NEW, scanner detection.
- `tests/test_platform_pitfalls_merge.py` — NEW, pure merge function.
- `tests/test_finalize_platform_pitfall.py` — NEW, finalize integration.

---

## Shared contracts (identical names everywhere)

- Signal name: `"ios_legacy_xcode_no_folder_sync"`.
- Scan field: `scan["platform_pitfall_signals"]` = `list[{"signal": str, "evidence_path": str}]` (empty list when none).
- Seed catalog shape: `{"pitfalls": [{"signal": str, "pitfall": {<canonical pitfall>}}]}`.
- Seeded pitfall id: `"pf_ios_pbxproj_registration"`.
- Merge function: `merge_platform_pitfalls(pitfalls: list, signals: list, catalog: dict) -> list` (pure, no I/O).

---

### Task 1: Scanner — detect the legacy-Xcode signal

**Files:**
- Modify: `archie/standalone/scanner.py`
- Test: `tests/test_platform_pitfall_signal.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_platform_pitfall_signal.py
"""Tests for archie/standalone/scanner.py::detect_platform_pitfall_signals.

Loaded by path (scanner.py is pure stdlib, not a package import).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "_archie_scanner",
    Path(__file__).resolve().parent.parent / "archie" / "standalone" / "scanner.py",
)
_scanner = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_scanner"] = _scanner
_SPEC.loader.exec_module(_scanner)

detect = _scanner.detect_platform_pitfall_signals

_LEGACY_PBX = "// !$*UTF8*$!\n{ objects = { 54BC /* X.swift in Sources */ = {isa = PBXBuildFile;}; }; }\n"
_SYNC_PBX = _LEGACY_PBX + "\n7A0 = {isa = PBXFileSystemSynchronizedRootGroup;};\n"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_legacy_xcode_emits_signal(tmp_path):
    _write(tmp_path / "App.xcodeproj" / "project.pbxproj", _LEGACY_PBX)
    signals = detect(tmp_path)
    assert signals == [{
        "signal": "ios_legacy_xcode_no_folder_sync",
        "evidence_path": "App.xcodeproj/project.pbxproj",
    }]


def test_folder_synchronized_xcode_emits_nothing(tmp_path):
    _write(tmp_path / "App.xcodeproj" / "project.pbxproj", _SYNC_PBX)
    assert detect(tmp_path) == []


def test_spm_only_emits_nothing(tmp_path):
    _write(tmp_path / "Package.swift", "// swift-tools-version:5.9\n")
    _write(tmp_path / "Sources" / "App" / "main.swift", "print(1)\n")
    assert detect(tmp_path) == []


def test_run_scan_includes_platform_pitfall_signals_key(tmp_path):
    _write(tmp_path / "App.xcodeproj" / "project.pbxproj", _LEGACY_PBX)
    scan = _scanner.run_scan(str(tmp_path))
    assert scan["platform_pitfall_signals"] == [{
        "signal": "ios_legacy_xcode_no_folder_sync",
        "evidence_path": "App.xcodeproj/project.pbxproj",
    }]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_platform_pitfall_signal.py -v`
Expected: FAIL — `AttributeError: module '_archie_scanner' has no attribute 'detect_platform_pitfall_signals'`.

- [ ] **Step 3: Add the detection function**

Add near `detect_subprojects` in `archie/standalone/scanner.py` (it reuses the module-level `SUBPROJECT_SKIP_DIRS`):

```python
def detect_platform_pitfall_signals(root) -> list:
    """Deterministic platform-pitfall signals consumed by finalize.

    Currently one: a legacy (non-folder-synchronized) Xcode project — a
    project.pbxproj lacking the PBXFileSystemSynchronizedRootGroup marker —
    requires new source files to be registered in PBXSourcesBuildPhase or they
    are silently excluded from the build. SPM-only projects (no .xcodeproj)
    compile by directory convention and emit nothing.
    """
    root = Path(root).resolve()
    for pbx in sorted(root.glob("**/*.xcodeproj/project.pbxproj")):
        rel = pbx.relative_to(root)
        if any(part in SUBPROJECT_SKIP_DIRS for part in rel.parts):
            continue
        try:
            text = pbx.read_text(errors="replace")
        except OSError:
            continue
        if "PBXFileSystemSynchronizedRootGroup" not in text:
            return [{
                "signal": "ios_legacy_xcode_no_folder_sync",
                "evidence_path": str(rel),
            }]
    return []
```

- [ ] **Step 4: Wire it into the `run_scan` return dict**

In `archie/standalone/scanner.py`, find the `return {` dict in `run_scan` (the one with `"bulk_content_manifest": bulk_manifest,` and `"_skeletons": skeletons,`). Add one line before `"_skeletons"`:

```python
        "bulk_content_manifest": bulk_manifest,
        "platform_pitfall_signals": detect_platform_pitfall_signals(root),
        "_skeletons": skeletons,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_platform_pitfall_signal.py -v`
Expected: PASS (4 cases).

- [ ] **Step 6: Commit**

```bash
git add archie/standalone/scanner.py tests/test_platform_pitfall_signal.py
git commit -m "feat(scanner): detect legacy-Xcode (no folder-sync) platform-pitfall signal"
```

---

### Task 2: Seed catalog + pure merge function

**Files:**
- Create: `archie/standalone/platform_pitfalls.json`
- Modify: `archie/standalone/finalize.py` (add `merge_platform_pitfalls`)
- Test: `tests/test_platform_pitfalls_merge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_platform_pitfalls_merge.py
"""Tests for archie/standalone/finalize.py::merge_platform_pitfalls (pure, no I/O)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "_archie_finalize", _ROOT / "archie" / "standalone" / "finalize.py",
)
_finalize = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_finalize"] = _finalize
_SPEC.loader.exec_module(_finalize)

merge = _finalize.merge_platform_pitfalls

_CATALOG = json.loads((_ROOT / "archie" / "standalone" / "platform_pitfalls.json").read_text())
_SIGNAL = [{"signal": "ios_legacy_xcode_no_folder_sync", "evidence_path": "App.xcodeproj/project.pbxproj"}]


def test_signal_appends_pitfall_with_evidence():
    out = merge([], _SIGNAL, _CATALOG)
    assert len(out) == 1
    assert out[0]["id"] == "pf_ios_pbxproj_registration"
    assert any("App.xcodeproj/project.pbxproj" in e for e in out[0]["evidence"])


def test_dedup_by_id_is_idempotent():
    once = merge([], _SIGNAL, _CATALOG)
    twice = merge(once, _SIGNAL, _CATALOG)
    assert len(twice) == 1


def test_no_signal_leaves_pitfalls_unchanged():
    existing = [{"id": "pf_0001", "problem_statement": "x"}]
    assert merge(existing, [], _CATALOG) == existing


def test_unknown_signal_is_ignored():
    out = merge([], [{"signal": "nope"}], _CATALOG)
    assert out == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_platform_pitfalls_merge.py -v`
Expected: FAIL — `FileNotFoundError` for `platform_pitfalls.json` (and missing `merge_platform_pitfalls`).

- [ ] **Step 3: Create the seed catalog**

```json
// archie/standalone/platform_pitfalls.json
{
  "pitfalls": [
    {
      "signal": "ios_legacy_xcode_no_folder_sync",
      "pitfall": {
        "id": "pf_ios_pbxproj_registration",
        "problem_statement": "New .swift source files are not auto-discovered in this legacy .pbxproj-listed Xcode target (no folder-synchronized groups), so a freshly created file that is not registered in the target's PBXSourcesBuildPhase is silently excluded from compilation and any code referencing it fails to build.",
        "evidence": [],
        "root_cause": "The project predates Xcode 16 folder-synchronized groups, so target membership is governed by hand-maintained .pbxproj records rather than file presence on disk. Creating a file outside Xcode's \"Add Files…\" writes it to disk but never registers it, and no build or test gate surfaces the omission until compilation fails.",
        "fix_direction": [
          "When adding a new .swift file, also edit the target's project.pbxproj: add a PBXFileReference, a PBXBuildFile, the owning group's child entry, and a PBXSourcesBuildPhase files entry — mirror an existing file.",
          "Prefer extending an existing same-layer file over creating a new one when the addition is small, to avoid pbxproj surgery.",
          "Use unique 24-hex-character object IDs for the new pbxproj entries (never synthetic placeholders like FAV1/FAV2).",
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

- [ ] **Step 4: Add the pure merge function to `finalize.py`**

Add at module level in `archie/standalone/finalize.py` (after the imports / near the top-level helpers):

```python
def merge_platform_pitfalls(pitfalls, signals, catalog):
    """Append deterministic platform pitfalls for present scanner signals.

    pitfalls : existing blueprint pitfalls (list).
    signals  : scan.json["platform_pitfall_signals"] — list of {signal, evidence_path}.
    catalog  : loaded platform_pitfalls.json — {"pitfalls": [{signal, pitfall}]}.

    Pure (no I/O). Dedup by pitfall id so re-scans are idempotent. Returns a new list.
    """
    result = list(pitfalls or [])
    existing_ids = {p.get("id") for p in result if isinstance(p, dict)}
    by_signal = {}
    for entry in (catalog or {}).get("pitfalls", []):
        sig = entry.get("signal")
        if sig and entry.get("pitfall"):
            by_signal.setdefault(sig, entry["pitfall"])
    for sig in signals or []:
        name = sig.get("signal") if isinstance(sig, dict) else sig
        seed = by_signal.get(name)
        if not seed or seed.get("id") in existing_ids:
            continue
        pitfall = json.loads(json.dumps(seed))  # deep copy
        ev = sig.get("evidence_path") if isinstance(sig, dict) else None
        if ev:
            pitfall["evidence"] = [
                f"{ev} — registered sources are enumerated here; a new file absent "
                f"from this manifest is excluded from the build"
            ]
        result.append(pitfall)
        existing_ids.add(pitfall.get("id"))
    return result
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_platform_pitfalls_merge.py -v`
Expected: PASS (4 cases).

- [ ] **Step 6: Commit**

```bash
git add archie/standalone/platform_pitfalls.json archie/standalone/finalize.py tests/test_platform_pitfalls_merge.py
git commit -m "feat(finalize): seed catalog + pure platform-pitfall merge (dedup by id)"
```

---

### Task 3: Wire the merge into the finalize pipeline

**Files:**
- Modify: `archie/standalone/finalize.py` (call merge before the blueprint.json write)
- Test: `tests/test_finalize_platform_pitfall.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_finalize_platform_pitfall.py
"""finalize() seeds the iOS pbxproj pitfall from scan.json signals (no AI needed)."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "_archie_finalize_int", _ROOT / "archie" / "standalone" / "finalize.py",
)
_finalize = importlib.util.module_from_spec(_SPEC)
sys.modules["_archie_finalize_int"] = _finalize
_SPEC.loader.exec_module(_finalize)


def _setup(tmp_path, signals):
    archie = tmp_path / ".archie"
    archie.mkdir(parents=True)
    (archie / "blueprint_raw.json").write_text(json.dumps({"pitfalls": []}))
    (archie / "scan.json").write_text(json.dumps({"platform_pitfall_signals": signals}))
    shutil.copyfile(
        _ROOT / "archie" / "standalone" / "platform_pitfalls.json",
        archie / "platform_pitfalls.json",
    )
    return archie


def test_finalize_seeds_pitfall_when_signal_present(tmp_path):
    archie = _setup(tmp_path, [{"signal": "ios_legacy_xcode_no_folder_sync",
                                "evidence_path": "App.xcodeproj/project.pbxproj"}])
    _finalize.finalize(tmp_path, agent_files=None)
    bp = json.loads((archie / "blueprint.json").read_text())
    ids = [p.get("id") for p in bp.get("pitfalls", [])]
    assert "pf_ios_pbxproj_registration" in ids


def test_finalize_no_signal_no_seed(tmp_path):
    archie = _setup(tmp_path, [])
    _finalize.finalize(tmp_path, agent_files=None)
    bp = json.loads((archie / "blueprint.json").read_text())
    assert bp.get("pitfalls", []) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_finalize_platform_pitfall.py -v`
Expected: FAIL — `blueprint.json` has no `pf_ios_pbxproj_registration` (merge not wired in).

- [ ] **Step 3: Wire the merge into `finalize()`**

In `archie/standalone/finalize.py::finalize`, locate the final full-mode write (the lines that read exactly):

```python
    bp_path = archie_dir / "blueprint.json"
    bp_path.write_text(json.dumps(bp, indent=2))
```

Insert immediately BEFORE those two lines:

```python
    # ── Deterministic platform-pitfall seed ───────────────────────────────
    # Inject known platform pitfalls (e.g. legacy-Xcode pbxproj registration)
    # from scanner signals before the blueprint is rendered. Dedup by id keeps
    # re-scans idempotent. Best-effort: never fail finalize over the seed.
    scan_path = archie_dir / "scan.json"
    pp_path = archie_dir / "platform_pitfalls.json"
    if scan_path.exists() and pp_path.exists():
        try:
            _signals = json.loads(scan_path.read_text()).get("platform_pitfall_signals", [])
            _catalog = json.loads(pp_path.read_text())
            bp["pitfalls"] = merge_platform_pitfalls(bp.get("pitfalls", []), _signals, _catalog)
        except Exception as _e:  # pragma: no cover - defensive
            print(f"  Warning: platform-pitfall seed skipped: {_e}", file=sys.stderr)

```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_finalize_platform_pitfall.py -v`
Expected: PASS (2 cases).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `python -m pytest tests/ -q`
Expected: PASS (existing + 3 new test files green).

- [ ] **Step 6: Commit**

```bash
git add archie/standalone/finalize.py tests/test_finalize_platform_pitfall.py
git commit -m "feat(finalize): seed platform pitfalls into blueprint from scan signals"
```

---

### Task 4: Install + sync the seed file (3-copy mirror)

**Files:**
- Copy: `archie/standalone/platform_pitfalls.json` → `archie/assets/platform_pitfalls.json`
- Copy: `archie/standalone/platform_pitfalls.json` → `npm-package/assets/platform_pitfalls.json`
- Modify: `archie/install.py` (data-files tuple)
- Modify: `npm-package/bin/archie.mjs` (data-files array + installed `.gitignore` block)

- [ ] **Step 1: Mirror the seed file to the two asset trees**

```bash
cp archie/standalone/platform_pitfalls.json archie/assets/platform_pitfalls.json
cp archie/standalone/platform_pitfalls.json npm-package/assets/platform_pitfalls.json
```

- [ ] **Step 2: Add the seed to `archie/install.py`**

Find the line `for name in ("platform_rules.json",):` and change it to:

```python
    for name in ("platform_rules.json", "platform_pitfalls.json"):
```

- [ ] **Step 3: Add the seed to the npm installer (`npm-package/bin/archie.mjs`)**

Find `for (const dataFile of ["platform_rules.json"]) {` and change to:

```js
for (const dataFile of ["platform_rules.json", "platform_pitfalls.json"]) {
```

In the same file, find the `archieGitignoreBlock` template string and add a line next to `.archie/platform_rules.json`:

```
.archie/platform_rules.json
.archie/platform_pitfalls.json
```

- [ ] **Step 4: Catch any other `platform_rules.json` install surface**

Run: `grep -rn "platform_rules.json" archie/ npm-package/ --include=*.py --include=*.mjs --include=*.js | grep -iv "load\|read\|render\|check\|index\|align\|finalize"`
For every remaining reference that **copies/installs** the file (not one that reads it for rules), add an analogous `platform_pitfalls.json` entry. (Expected surfaces: the two edited in Steps 2-3. If `archie/manifest_data.py` lists `platform_rules.json` as an installed data file, add `platform_pitfalls.json` there too, and mirror to `npm-package/assets/_install_pkg/manifest_data.py`.)

- [ ] **Step 5: Run the sync checker + full suite**

Run: `python3 scripts/verify_sync.py`
Expected: `SYNC CHECK PASSED` (the new JSON is byte-identical across `archie/standalone/` and `npm-package/assets/`).

Run: `python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add archie/assets/platform_pitfalls.json npm-package/assets/platform_pitfalls.json archie/install.py npm-package/bin/archie.mjs
git commit -m "chore(install): ship + install platform_pitfalls.json (mirror platform_rules)"
```

---

### Task 5: Validate on the real gasztro repo (deterministic, no AI)

This proves the automatic path end-to-end and is the product evidence. It uses
`finalize(root, agent_files=None)`, which runs the platform-pitfall merge + render
WITHOUT a full AI deep-scan.

- [ ] **Step 1: Revert the experimental hand-injection**

```bash
git -C /Users/csacsi/DEV/Gasztroterkepek.iOS revert --no-edit 251e35e
```
Confirms the repo no longer carries the manually-injected pitfall.

- [ ] **Step 2: Regenerate scan.json with the new scanner**

```bash
python3 archie/standalone/scanner.py /Users/csacsi/DEV/Gasztroterkepek.iOS
python3 -c "import json; print(json.load(open('/Users/csacsi/DEV/Gasztroterkepek.iOS/.archie/scan.json'))['platform_pitfall_signals'])"
```
Expected: a non-empty list containing `ios_legacy_xcode_no_folder_sync` with the real `evidence_path`.

- [ ] **Step 3: Install the seed, merge into the blueprint (finalize), then render**

`finalize` merges the pitfall into `blueprint.json`; `renderer.py` is what produces
`.claude/rules/pitfalls.md` from the blueprint — both must run.

```bash
GZ=/Users/csacsi/DEV/Gasztroterkepek.iOS
cp archie/standalone/platform_pitfalls.json "$GZ/.archie/platform_pitfalls.json"
# 1) merge the seeded pitfall into blueprint.json (no AI; agent_files=None)
python3 -c "import importlib.util,sys; from pathlib import Path; \
s=importlib.util.spec_from_file_location('f','archie/standalone/finalize.py'); \
m=importlib.util.module_from_spec(s); sys.modules['f']=m; s.loader.exec_module(m); \
m.finalize(Path('$GZ'), agent_files=None)"
# 2) confirm it landed in the blueprint
python3 -c "import json; ids=[p.get('id') for p in json.load(open('$GZ/.archie/blueprint.json')).get('pitfalls',[])]; print('pf_ios_pbxproj_registration' in ids, ids)"
# 3) regenerate the rendered context (pitfalls.md etc.)
python3 archie/standalone/renderer.py "$GZ"
grep -c "pf_ios_pbxproj_registration\|PBXSourcesBuildPhase\|project.pbxproj" "$GZ/.claude/rules/pitfalls.md"
```
Expected: step 2 prints `True ...`; step 3 grep count ≥ 1 — the pitfall now renders into `pitfalls.md` automatically, with no hand-editing.

- [ ] **Step 4: Commit the regenerated context on gasztro**

```bash
git -C /Users/csacsi/DEV/Gasztroterkepek.iOS add -A
git -C /Users/csacsi/DEV/Gasztroterkepek.iOS commit -m "archie: regenerate context with deterministic iOS pbxproj pitfall"
```

- [ ] **Step 5: Re-run the benchmark (n=3) and compare**

```bash
python3 .archie-bench/run_logged.py .archie-bench/gasztro-favorite.json
```
Expected: treatment `attempted=3`, NO build-breaking 4.5/5.0 reps, treatment quality back near ~8.3 (matching the hand-injection run). Append confirms in `.archie-bench/benchmark_log.jsonl` (now 3 logged runs).

- [ ] **Step 6: Record the outcome**

Update the memory note `project_benchmark_first_result.md` with the deterministic-path result, and clean up the gasztro bench branches/worktrees (`git worktree remove --force ...`, `git branch -D archie-bench/*`, `rm -rf .archie/benchmark`).

---

## Self-Review Notes (completed by plan author)

- **Spec coverage:** scanner signal → Task 1; seed catalog + merge → Task 2; finalize wiring → Task 3; install + sync (3 copies) → Task 4; validation re-run (revert hand-inject, auto-regen, benchmark) → Task 5. All spec sections covered.
- **Type consistency:** `platform_pitfall_signals` (list of `{signal, evidence_path}`), signal name `ios_legacy_xcode_no_folder_sync`, pitfall id `pf_ios_pbxproj_registration`, and `merge_platform_pitfalls(pitfalls, signals, catalog)` are spelled identically across scanner.py, finalize.py, the seed JSON, and all three test files.
- **No placeholders:** every code/JSON/command step is concrete. Task 4 Step 4 is a deterministic grep-and-mirror enumeration, not a vague "handle other cases".
- **Out of scope honored:** `archie/engine/` parallel scanner left untouched (not used by deep-scan); no enforcement hook; no `.pbxproj` auto-edit.
```

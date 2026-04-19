# Archie — Plan 5d: Blueprint freshness check (force Wave 1 when schema evolved)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Stop the silent skip-Wave-1 optimization from breaking new agents. When `/archie-deep-scan` adds a new Wave 1 agent (e.g. Plan 5b.1's `data_models`), the orchestrator's "no Swift code changed → reuse existing blueprint" reasoning currently bypasses Wave 1 entirely, so the new agent never runs against existing baselines. The blueprint stays missing the new section forever — until the user manually deletes `blueprint.json` or passes `--reconfigure`.

**Concrete trigger from a real user session (2026-04-19):** User ran `/archie-deep-scan` on Gasztroterkepek.iOS the morning after Plan 5b.1 was deployed. Orchestrator output:

> Context: no Swift code has changed since yesterday's baseline (commit c47188d3 is still HEAD). To avoid re-spawning 7 agents for identical output, I'll refresh the dynamic artifacts (scan.json, dependency graph, health, drift, scan_report) and reuse the existing blueprint, rules, per-folder CLAUDE.md files, and wiki.

Result: blueprint had no `data_models[]`, no `data-models/*.md` pages in wiki. The new feature was effectively invisible.

**Solution:** Add a deterministic "blueprint completeness" check at the very top of the deep-scan command, before any orchestrator reasoning about skipping Wave 1. The check compares the existing blueprint's top-level keys against an "expected keys" list maintained alongside the command. If any expected key is missing, force a full Wave 1 re-synthesis regardless of code-change state.

**Architecture:** A new tiny standalone helper `check_blueprint_completeness.py` reads `blueprint.json` and prints either `OK` (exit 0) or `STALE: missing <key1>, <key2>` (exit 1). The deep-scan command calls it as Step 0.5 and pipes the result into a marker file `/tmp/archie_force_full_wave1` that downstream steps inspect.

**Tech Stack:** Python 3.9+ stdlib, pytest. No new runtime dependencies.

**Depends on:** Plan 5b.1 + 5b.2 + 5c merged (so the expected keys list reflects the current schema).

**Reference spec:** Section 4.14 in T3.

---

## File structure

**New files:**
- `archie/standalone/check_blueprint_completeness.py` — the helper
- `tests/test_check_blueprint_completeness.py` — tests
- `npm-package/assets/check_blueprint_completeness.py` — sync copy

**Modified files:**
- `.claude/commands/archie-deep-scan.md` — new Step 0.5 + force-full-wave1 logic in Step 4
- `npm-package/assets/archie-deep-scan.md` — sync copy
- `npm-package/bin/archie.mjs` — register the new script in the copy list
- `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — Section 4.14
- `CLAUDE.md` — note in the sync rule list (if needed)

---

## Expected keys list (canonical)

Maintained inside `check_blueprint_completeness.py` as a module constant. Each entry has a key name + introduction marker (which plan/feature added it) so future devs know not to drop it:

```python
EXPECTED_KEYS = [
    # (key_name, introduced_in)
    ("meta", "Plan 1"),
    ("components", "Plan 1"),
    ("decisions", "Plan 1"),
    ("communication", "Plan 1"),
    ("pitfalls", "Plan 1"),
    ("technology", "Plan 1"),
    ("architecture_rules", "Plan 1"),
    ("development_rules", "Plan 1"),
    ("implementation_guidelines", "Plan 1"),
    ("quick_reference", "Plan 1"),
    ("architecture_diagram", "Plan 1"),
    ("capabilities", "Plan 2"),
    ("data_models", "Plan 5b.1"),
]
```

Note: `frontend` is conditional (only present for projects with frontend code). It is NOT in the expected list — completeness check only flags keys that should ALWAYS be present after a successful deep-scan.

`utilities` does not live in the blueprint — it lives in `scan.json.symbols[]` — so it's NOT in this list either. (Plan 5b.2 emit goes through scan.json, not blueprint.)

---

## Task 1: `check_blueprint_completeness.py` standalone helper

**Files:**
- Create: `archie/standalone/check_blueprint_completeness.py`
- Create: `tests/test_check_blueprint_completeness.py`

### Helper signature

```python
"""Check whether .archie/blueprint.json contains all expected top-level keys.

Run: python3 check_blueprint_completeness.py /path/to/project
Exit codes:
  0 — blueprint complete (or absent — let deep-scan handle missing-blueprint case)
  1 — blueprint exists but is stale (missing expected keys)

stdout: "OK" or "STALE: missing data_models (Plan 5b.1), capabilities (Plan 2)"
"""
```

When `blueprint.json` does NOT exist: print `MISSING` and exit 0 (let downstream "no blueprint → first-run" logic in deep-scan handle it). The check ONLY flags STALE blueprints.

When `blueprint.json` exists but is malformed JSON: print `MALFORMED` and exit 1 (force re-synthesis).

When all keys present: print `OK` and exit 0.

When some keys missing: print `STALE: missing <key1> (<intro>), <key2> (<intro>)` sorted by intro plan version, and exit 1.

The check operates ONLY on top-level key presence — does NOT validate inner structure. A `data_models: []` empty array counts as present (the agent ran but returned nothing).

### Tests (tests/test_check_blueprint_completeness.py)

```python
import json
import subprocess
import sys
from pathlib import Path

HELPER = Path(__file__).parent.parent / "archie" / "standalone" / "check_blueprint_completeness.py"


def _run(project: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(HELPER), str(project)],
        capture_output=True, text=True
    )
    return proc.returncode, proc.stdout.strip()


def test_blueprint_missing_returns_zero(tmp_path):
    # No .archie/blueprint.json at all → exit 0, MISSING
    code, out = _run(tmp_path)
    assert code == 0
    assert out == "MISSING"


def test_blueprint_complete_returns_zero(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    bp = {
        "meta": {}, "components": [], "decisions": {}, "communication": {},
        "pitfalls": [], "technology": {}, "architecture_rules": {},
        "development_rules": [], "implementation_guidelines": [],
        "quick_reference": {}, "architecture_diagram": "",
        "capabilities": [], "data_models": [],
    }
    (archie / "blueprint.json").write_text(json.dumps(bp))
    code, out = _run(tmp_path)
    assert code == 0
    assert out == "OK"


def test_blueprint_missing_data_models_returns_one(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    bp = {
        "meta": {}, "components": [], "decisions": {}, "communication": {},
        "pitfalls": [], "technology": {}, "architecture_rules": {},
        "development_rules": [], "implementation_guidelines": [],
        "quick_reference": {}, "architecture_diagram": "",
        "capabilities": [],
        # data_models intentionally missing
    }
    (archie / "blueprint.json").write_text(json.dumps(bp))
    code, out = _run(tmp_path)
    assert code == 1
    assert "STALE" in out
    assert "data_models" in out
    assert "Plan 5b.1" in out


def test_blueprint_missing_multiple_returns_one(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    bp = {"meta": {}, "components": []}  # almost everything missing
    (archie / "blueprint.json").write_text(json.dumps(bp))
    code, out = _run(tmp_path)
    assert code == 1
    assert "STALE" in out
    # Multiple missing keys should be listed
    assert "data_models" in out
    assert "capabilities" in out


def test_blueprint_malformed_returns_one(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "blueprint.json").write_text("not { valid json")
    code, out = _run(tmp_path)
    assert code == 1
    assert out == "MALFORMED"


def test_empty_data_models_array_counts_as_present(tmp_path):
    """An empty data_models[] means the agent ran and found nothing — that's OK."""
    archie = tmp_path / ".archie"
    archie.mkdir()
    bp = {k: ([] if k.endswith("s") else {}) for k, _ in __import__("subprocess")._dummy() or []}
    # Build it manually — too clever above. Just enumerate:
    bp = {
        "meta": {}, "components": [], "decisions": {}, "communication": {},
        "pitfalls": [], "technology": {}, "architecture_rules": {},
        "development_rules": [], "implementation_guidelines": [],
        "quick_reference": {}, "architecture_diagram": "",
        "capabilities": [], "data_models": [],
    }
    (archie / "blueprint.json").write_text(json.dumps(bp))
    code, _ = _run(tmp_path)
    assert code == 0
```

### Steps (TDD)

- [ ] **Step 1:** Create test file with the 6 tests
- [ ] **Step 2:** Verify FAIL (helper doesn't exist yet)
- [ ] **Step 3:** Implement `check_blueprint_completeness.py`
- [ ] **Step 4:** Verify PASS
- [ ] **Step 5:** Commit `feat(scan): add check_blueprint_completeness helper`

---

## Task 2: Wire into `archie-deep-scan.md`

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md`

### New Step 0.5 (insert immediately after the existing scope-resolution / Step 0)

```markdown
## Step 0.5: Blueprint freshness check

**If START_STEP > 0, skip this step.**

Before any "skip Wave 1 because no code changes" reasoning, deterministically verify that the existing `blueprint.json` (if any) contains all expected top-level keys. New Wave 1 agents added since the prior baseline produce keys that the old blueprint lacks — those gaps require a forced full re-synthesis regardless of code-change state.

```bash
FRESHNESS=$(python3 .archie/check_blueprint_completeness.py "$PROJECT_ROOT")
FRESHNESS_EXIT=$?
echo "Blueprint freshness: $FRESHNESS"
if [ $FRESHNESS_EXIT -ne 0 ]; then
    echo "FORCE_FULL_WAVE1=1 (blueprint stale or malformed)"
    touch /tmp/archie_force_full_wave1_$PROJECT_NAME
fi
```

The marker file `/tmp/archie_force_full_wave1_$PROJECT_NAME` is consumed in Step 3 / Step 4 (see below).
```

### Modify the Wave 1 trigger reasoning (around Step 3 in the command)

Find the existing decision logic (whether documented or implicit in the orchestrator's reasoning prose) about "skip Wave 1 if no code changes since baseline". Add an explicit override:

```markdown
**Force-full-Wave1 override (Plan 5d):** If `/tmp/archie_force_full_wave1_$PROJECT_NAME` exists, you MUST spawn the full Wave 1 set (Structure + Patterns + Technology + UI Layer + Capabilities + Data models) regardless of how many Swift files changed. The optimization to "reuse existing blueprint when no code changed" assumes the existing blueprint was produced by the current toolchain — when freshness check fails, that assumption is wrong.

The marker is cleaned up in Step 11 along with the other /tmp artifacts.
```

### Cleanup line update

Add `/tmp/archie_force_full_wave1_$PROJECT_NAME` to the existing `rm -f` cleanup line.

### Steps

- [ ] **Step 1:** Read existing `archie-deep-scan.md` to find the right insertion point for Step 0.5 (after scope resolution, before any agent-spawning reasoning)
- [ ] **Step 2:** Insert Step 0.5 block
- [ ] **Step 3:** Add force-full-Wave1 override note in/near Step 3
- [ ] **Step 4:** Extend cleanup `rm -f` line
- [ ] **Step 5:** Re-read the command to verify the new instructions read coherently
- [ ] **Step 6:** Commit `feat(deep-scan): force Wave 1 when blueprint missing expected keys`

---

## Task 3: NPM sync + register helper + spec Section 4.14

**Files:**
- Create: `npm-package/assets/check_blueprint_completeness.py` (copy)
- Modify: `npm-package/assets/archie-deep-scan.md` (copy)
- Modify: `npm-package/bin/archie.mjs` — add `"check_blueprint_completeness.py"` to the script copy list
- Modify: `docs/superpowers/specs/2026-04-17-llm-wiki-design.md` — Section 4.14

### Spec Section 4.14

Insert after Section 4.13:

```markdown
### 4.14 Blueprint freshness check (Plan 5d)

`/archie-deep-scan` previously skipped the Wave 1 agent set when the orchestrator detected no source-code changes since the last baseline. This optimization broke whenever a new Wave 1 agent was added (e.g. Plan 5b.1's `data_models`): the existing blueprint lacked the new key, but the optimization reused it anyway, so the new agent never produced output.

The fix is a small standalone helper `check_blueprint_completeness.py` that runs as Step 0.5. It compares `blueprint.json`'s top-level keys against an `EXPECTED_KEYS` list maintained inside the helper (each entry annotated with the plan that introduced it). When any expected key is missing — or the blueprint is malformed JSON — the helper exits non-zero and the deep-scan command writes a marker file `/tmp/archie_force_full_wave1_<project>` that the orchestrator must consult before applying the "no code changes → reuse blueprint" optimization.

Empty arrays count as present (the agent ran and returned nothing legitimately). A blueprint that's entirely missing exits zero with status `MISSING` — first-run logic handles that case. The check only flags STALE / MALFORMED blueprints.

Maintenance: any plan that adds a new Wave 1 agent must add a matching entry to `EXPECTED_KEYS` in the same commit. Without it, the new agent will silently regress on the first project upgrade.
```

### Steps

- [ ] **Step 1:** Copy helper + command md to assets
- [ ] **Step 2:** Add `"check_blueprint_completeness.py"` to `archie.mjs` script list
- [ ] **Step 3:** Run `python3 scripts/verify_sync.py` → must pass with 20 scripts (was 19)
- [ ] **Step 4:** Add Section 4.14 to spec
- [ ] **Step 5:** Commit `chore(scan): sync freshness check + spec Section 4.14`

---

## Task 4: Smoke test on Gasztroterkepek blueprint

**Verification only — no commit.**

Test the freshness check against the actual stale Gasztroterkep blueprint:

```bash
python3 archie/standalone/check_blueprint_completeness.py /Users/csacsi/DEV/Gasztroterkepek.iOS
# Expect: STALE: missing data_models (Plan 5b.1)
# Exit: 1
```

Then sync the new helper into Gasztroterkepek so the next deep-scan picks it up:

```bash
cp archie/standalone/check_blueprint_completeness.py /Users/csacsi/DEV/Gasztroterkepek.iOS/.archie/
cp .claude/commands/archie-deep-scan.md /Users/csacsi/DEV/Gasztroterkepek.iOS/.claude/commands/
```

User then runs `/archie-deep-scan` on Gasztroterkepek (without flags) — orchestrator should observe `FORCE_FULL_WAVE1=1` and spawn the full Wave 1 set, including the data_models agent.

---

## Self-review checklist

- [ ] All previous tests pass.
- [ ] `check_blueprint_completeness.py` correctly detects stale Gasztroterkepek blueprint.
- [ ] Deep-scan command reads coherently with the new Step 0.5 + override note.
- [ ] `verify_sync.py` passes with 20 scripts.
- [ ] Spec Section 4.14 documents the mechanism + maintenance contract.

## Known follow-ups (out of scope)

- **Auto-update EXPECTED_KEYS via plan tooling** — currently devs must remember to update the list when adding a Wave 1 agent. A lint check in CI could grep for `merge_<name>` definitions in merge.py and cross-reference. Out of scope; track if it becomes a recurring miss.
- **Per-key validation** (e.g. `data_models[*].name` non-empty) — beyond key-presence. Probably overkill — the merger already validates inner structure.
- **scan.json freshness** — Plan 5b.2's `symbols[]` lives in scan.json, not blueprint. A parallel `check_scan_completeness.py` could enforce the same contract there. Skip until a similar regression bites.

# Impact Ladder + Temperature Lever — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Archie a reachable "done" state: every finding/pitfall/gap carries an `impact` tier (regression/hazard/erosion/preference) and a per-user temperature dial filters what surfaces, with "N items above the line" as the headline.

**Architecture:** Display-time filtering over the full compounding store. One Python module (`impact_filter.py`) owns tier semantics, temperature settings, counting, and seeding; emission prompts gain an `impact` + `consequence_path` contract; the verifier gains bidirectional tier-correction verdicts; `finalize` gains a prior-wins merge so single-shot LLM tiers never overwrite stabilized ones; the viewer gains a 3-level dial, a standing-guardrails band, and a clear-event state.

**Tech Stack:** Python 3.9+ stdlib only (standalone scripts), React/TS viewer (vite + node:test), pytest.

**Spec:** `docs/archie-impact-temperature-design.md` (rev 2, commit fe733dd). Read it before starting any task.

## Global Constraints

- Python standalone scripts: zero dependencies beyond Python 3.9 stdlib.
- Every changed `archie/standalone/*.py` MUST be copied to `npm-package/assets/*.py`; every changed `share/viewer/src/**` file MUST be mirrored to `npm-package/assets/viewer/**` AND `archie/assets/viewer/**`. Run `python3 scripts/verify_sync.py` before every commit — it must pass.
- Impact tiers (exact strings): `"regression"`, `"hazard"`, `"erosion"`, `"preference"`.
- Temperature levels (exact strings): `"broken_now"`, `"can_hurt_you"`, `"everything"`. UI labels: "Broken now" / "Can hurt you" / "Everything" (sentence case).
- Settings file: `.archie/settings.local.json` — gitignored, per-user. Never write temperature into `findings.json`.
- Confidence floors by impact: regression 0.7, hazard 0.6, erosion 0.5 — applied ONLY in finalize's deep-scan path, never inside `editor_gate.gate()`.
- The dial never moves programmatically after the one-time seed. `source: "user"` is sticky.
- Findings count toward "done"; pitfalls/gaps never do (standing guardrails band).
- Never touch `pre-validate.sh`, `check_rules.py`, or any `severity_class` logic.
- Commit after every task with a conventional-commit message ending in the Co-Authored-By line used in this repo.

---

### Task 0: Validation experiment — ②/③ tier agreement (GATE)

No production code. Validates the riskiest assumption (spec §9) before building.
**If agreement < 80% on the hazard/erosion boundary, STOP and report — the
`consequence_path` schema needs hardening before Tasks 1+ proceed.**

**Files:**
- Create: `/private/tmp` NOT allowed — use the scratchpad dir if running interactively, or `docs/superpowers/` scratch (gitignored). Nothing from this task is committed except a one-paragraph result appended to the spec's §9.

- [ ] **Step 1: Build the fixture.** Extract the 18 real items from `/Users/hamutarto/DEV/Repos/SubscriberAgent/.archie/findings.json` (7 findings) and `/Users/hamutarto/DEV/Repos/SubscriberAgent/.archie/blueprint.json` (8 `pitfalls`, 3 `unenforced_invariants`) into one JSON array, each item keeping only: `id`, `problem_statement`, `evidence`, `root_cause`, `failure_mode` (pitfalls/gaps), `severity`, `kind`.

- [ ] **Step 2: Write the tagging prompt** (verbatim, this is the experiment's independent variable):

```
You are tagging architecture-scan items with an impact tier. Tiers:
- "regression": already misbehaving — a live caller fires the failure mode today.
- "hazard": not broken yet, but a realistic path to outage, data loss, money loss, or security exposure. To claim hazard you MUST fill consequence_path: {"asset": <named asset at risk>, "entry_point": <file:line where the path starts>, "trigger": <what realistically sets it off>}. If you cannot fill all three concretely, the item is erosion.
- "erosion": a real architectural decision or invariant undermined; the cost is maintainability, not behavior.

For each item in the JSON below, output ONLY a JSON array of {"id": ..., "impact": ..., "consequence_path": <object or null>}.

<items JSON here>
```

- [ ] **Step 3: Run 5 independent passes** (fresh conversation each — no shared context): `claude -p "<prompt>" --model claude-sonnet-5` five times, saving outputs as `run1.json` … `run5.json`.

- [ ] **Step 4: Score agreement.** For each of the 18 ids, the modal tier and its frequency. Report: (a) % of items where all 5 runs agree, (b) % where ≥4/5 agree, (c) list every item that crossed the hazard/erosion line between runs, with the differing consequence_paths.

- [ ] **Step 5: Gate decision.** ≥80% of items with ≥4/5 agreement on the ②/③ line ⇒ proceed. Otherwise stop, append findings to spec §9, and surface to the user. Either way append the measured numbers to `docs/archie-impact-temperature-design.md` §9 and commit that one-file change:

```bash
git add docs/archie-impact-temperature-design.md
git commit -m "docs(spec): record tier-agreement validation results"
```

---

### Task 1: `impact_filter.py` — the one module that owns tier + temperature semantics

**Files:**
- Create: `archie/standalone/impact_filter.py`
- Create: `tests/test_impact_filter.py`
- Copy: `npm-package/assets/impact_filter.py`

**Interfaces (Produces — later tasks import these by sibling-path, same pattern as `finalize.py`'s `_SCRIPT_DIR` import):**
- `TIER_ORDER: dict[str, int]` — `{"regression": 0, "hazard": 1, "erosion": 2, "preference": 3}`
- `LEVEL_MAX_TIER: dict[str, int]` — `{"broken_now": 0, "can_hurt_you": 1, "everything": 3}`
- `derive_legacy_impact(item: dict, is_pitfall: bool = False) -> str`
- `at_or_above(impact: str, level: str) -> bool`
- `load_temperature(project_root: Path) -> dict` — validated/repaired `{level, source, seeded_reason, set_at}`; returns `{}` if absent
- `save_temperature(project_root: Path, temp: dict) -> None`
- `compute_seed(health: dict, above_at_can_hurt_you: int, next_level_count: int) -> dict`
- `counts(project_root: Path) -> dict` — `{"level": str, "source": str, "above": int, "parked": int, "guardrails": int}`
- `stamp_or_get_last_clear(project_root: Path, above: int) -> dict | None` — when `above == 0` and no stamp exists for the current level, writes `{"at": iso, "level": str}` under `last_clear` in `settings.local.json`; when `above > 0` an existing stamp is returned unchanged (so the UI can say "N new since your last clear"); returns the stamp or `None`
- CLI: `python3 impact_filter.py counts <root>` and `python3 impact_filter.py seed <root>` — both print JSON to stdout

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_impact_filter.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import impact_filter as imf


def _mk_project(tmp_path, findings=None, blueprint=None, health=None):
    archie = tmp_path / ".archie"
    archie.mkdir()
    if findings is not None:
        (archie / "findings.json").write_text(json.dumps({"findings": findings}))
    if blueprint is not None:
        (archie / "blueprint.json").write_text(json.dumps(blueprint))
    if health is not None:
        (archie / "health.json").write_text(json.dumps(health))
    return tmp_path


def test_at_or_above_boundaries():
    assert imf.at_or_above("regression", "broken_now")
    assert not imf.at_or_above("hazard", "broken_now")
    assert imf.at_or_above("hazard", "can_hurt_you")
    assert not imf.at_or_above("erosion", "can_hurt_you")
    assert imf.at_or_above("erosion", "everything")
    assert imf.at_or_above("preference", "everything")


def test_derive_legacy_impact():
    assert imf.derive_legacy_impact({"kind": "behavioral_break"}) == "hazard"
    assert imf.derive_legacy_impact({"kind": "conformance_break"}) == "erosion"
    assert imf.derive_legacy_impact({"severity": "error"}, is_pitfall=True) == "hazard"
    assert imf.derive_legacy_impact({"severity": "warn"}, is_pitfall=True) == "erosion"
    # explicit impact always wins over derivation
    assert imf.derive_legacy_impact({"kind": "behavioral_break", "impact": "regression"}) == "regression"


def test_counts_findings_only_in_countdown(tmp_path):
    root = _mk_project(
        tmp_path,
        findings=[
            {"id": "f_1", "status": "active", "impact": "regression"},
            {"id": "f_2", "status": "active", "impact": "hazard"},
            {"id": "f_3", "status": "active", "impact": "erosion"},
            {"id": "f_4", "status": "demoted", "impact": "regression"},  # non-active never counts
        ],
        blueprint={
            "pitfalls": [{"id": "pf_1", "impact": "hazard"}, {"id": "pf_2", "impact": "erosion"}],
            "unenforced_invariants": [{"id": "gap-001", "impact": "hazard"}],
        },
    )
    imf.save_temperature(root, {"level": "can_hurt_you", "source": "user"})
    c = imf.counts(root)
    assert c["above"] == 2        # f_1, f_2 — findings only
    assert c["parked"] == 1       # f_3
    assert c["guardrails"] == 2   # pf_1, gap-001 (classes at/above the line)


def test_temperature_validate_and_repair(tmp_path):
    root = _mk_project(tmp_path, findings=[])
    (root / ".archie" / "settings.local.json").write_text(
        json.dumps({"temperature": {"level": "EVERYTHING!!", "source": "wat"}})
    )
    t = imf.load_temperature(root)
    assert t["level"] == "can_hurt_you"   # invalid level repaired to safe default
    assert t["source"] == "seeded"         # invalid source repaired


def test_seed_rule_and_small_repo_guard():
    # dirty repo -> can_hurt_you
    s = imf.compute_seed({"erosion": 0.74, "top20_share": 0.9, "total_functions": 2298}, 5, 5)
    assert s["level"] == "can_hurt_you"
    # tiny repo: top20_share degenerate, erosion low -> everything
    s = imf.compute_seed({"erosion": 0.1, "top20_share": 1.0, "total_functions": 4}, 2, 2)
    assert s["level"] == "everything"
    # load nudge colder: >25 items at baseline everything -> can_hurt_you
    s = imf.compute_seed({"erosion": 0.1, "top20_share": 0.2, "total_functions": 500}, 30, 30)
    assert s["level"] == "can_hurt_you"
    # never broken_now: 30 hazards at a can_hurt_you baseline stays can_hurt_you
    s = imf.compute_seed({"erosion": 0.9, "top20_share": 0.9, "total_functions": 500}, 30, 40)
    assert s["level"] == "can_hurt_you"
    # health missing -> load-only fallback, baseline can_hurt_you
    s = imf.compute_seed({}, 3, 3)
    assert s["level"] == "can_hurt_you"


def test_last_clear_stamped_and_kept(tmp_path):
    root = _mk_project(tmp_path, findings=[])
    imf.save_temperature(root, {"level": "can_hurt_you", "source": "user"})
    stamp = imf.stamp_or_get_last_clear(root, above=0)
    assert stamp["level"] == "can_hurt_you" and stamp["at"]
    later = imf.stamp_or_get_last_clear(root, above=3)   # items reappeared
    assert later == stamp                                # stamp survives


def test_seed_once_semantics(tmp_path):
    root = _mk_project(tmp_path, findings=[], health={"erosion": 0.9, "top20_share": 0.9, "total_functions": 100})
    first = imf.seed_if_absent(root)
    assert first["source"] == "seeded"
    imf.save_temperature(root, {"level": "broken_now", "source": "user"})
    second = imf.seed_if_absent(root)   # must NOT overwrite
    assert second["level"] == "broken_now"
    assert second["source"] == "user"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_impact_filter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'impact_filter'`

- [ ] **Step 3: Implement `archie/standalone/impact_filter.py`**

```python
#!/usr/bin/env python3
"""Impact-tier + temperature semantics — the single owner.

Reads .archie/findings.json + .archie/blueprint.json + .archie/health.json,
and the per-user .archie/settings.local.json (gitignored). Computes the
"N above the line" headline used by both the Step 9 receipt and the viewer.

Tiers: regression < hazard < erosion < preference (ordinal = noise).
Levels: broken_now (tier 0), can_hurt_you (0-1), everything (0-3).

Zero dependencies beyond Python 3.9 stdlib.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TIER_ORDER = {"regression": 0, "hazard": 1, "erosion": 2, "preference": 3}
LEVEL_MAX_TIER = {"broken_now": 0, "can_hurt_you": 1, "everything": 3}
DEFAULT_LEVEL = "can_hurt_you"
SETTINGS_NAME = "settings.local.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def derive_legacy_impact(item: dict, is_pitfall: bool = False) -> str:
    """Provisional tier for pre-impact items (spec §3 Legacy data)."""
    explicit = item.get("impact")
    if explicit in TIER_ORDER:
        return explicit
    if is_pitfall:
        return "hazard" if item.get("severity") == "error" else "erosion"
    kind = item.get("kind", "")
    if kind == "behavioral_break":
        return "hazard"
    return "erosion"


def at_or_above(impact: str, level: str) -> bool:
    tier = TIER_ORDER.get(impact, TIER_ORDER["erosion"])
    return tier <= LEVEL_MAX_TIER.get(level, LEVEL_MAX_TIER[DEFAULT_LEVEL])


def _settings_path(project_root: Path) -> Path:
    return Path(project_root) / ".archie" / SETTINGS_NAME


def load_temperature(project_root: Path) -> dict:
    """Read + validate + repair the temperature key. {} when absent."""
    path = _settings_path(project_root)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    temp = data.get("temperature")
    if not isinstance(temp, dict) or not temp:
        return {}
    repaired = dict(temp)
    if repaired.get("level") not in LEVEL_MAX_TIER:
        repaired["level"] = DEFAULT_LEVEL
    if repaired.get("source") not in ("seeded", "user"):
        repaired["source"] = "seeded"
    if repaired != temp:
        save_temperature(project_root, repaired)
    return repaired


def save_temperature(project_root: Path, temp: dict) -> None:
    path = _settings_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
    entry = dict(temp)
    entry.setdefault("set_at", _now_iso())
    data["temperature"] = entry
    path.write_text(json.dumps(data, indent=2))


def compute_seed(health: dict, above_at_can_hurt_you: int, next_level_count: int) -> dict:
    """Spec §4: baseline from health (small-repo guard), load nudge one notch,
    clamped to can_hurt_you/everything. Health-missing => load-only fallback."""
    erosion = health.get("erosion")
    top20 = health.get("top20_share")
    n_funcs = health.get("total_functions") or 0
    reason_bits = []
    if erosion is None:
        baseline = "can_hurt_you"
        reason_bits.append("health data not available yet")
    elif erosion >= 0.5 or (top20 is not None and top20 >= 0.7 and n_funcs >= 25):
        baseline = "can_hurt_you"
        reason_bits.append(f"code-health erosion {erosion:.2f}")
    else:
        baseline = "everything"
        reason_bits.append(f"healthy baseline (erosion {erosion:.2f})")
    level = baseline
    if above_at_can_hurt_you > 25 and baseline == "everything":
        level = "can_hurt_you"
        reason_bits.append(f"{above_at_can_hurt_you} items would surface")
    elif baseline == "can_hurt_you" and above_at_can_hurt_you == 0 and next_level_count < 10:
        level = "everything"
        reason_bits.append("quiet at the stricter level")
    return {
        "level": level,
        "source": "seeded",
        "seeded_reason": " — ".join(reason_bits),
        "set_at": _now_iso(),
    }


def stamp_or_get_last_clear(project_root: Path, above: int):
    """Clear is an event, not a state (spec §4). Stamp on reaching zero at the
    current level; never erase the stamp when items reappear."""
    path = _settings_path(project_root)
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}
    level = (data.get("temperature") or {}).get("level", DEFAULT_LEVEL)
    stamp = data.get("last_clear")
    if above == 0 and (not isinstance(stamp, dict) or stamp.get("level") != level):
        stamp = {"at": _now_iso(), "level": level}
        data["last_clear"] = stamp
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))
    return stamp if isinstance(stamp, dict) else None


def _load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _tiered_counts(project_root: Path, level: str) -> dict:
    archie = Path(project_root) / ".archie"
    store = _load_json(archie / "findings.json") or {}
    findings = store.get("findings") if isinstance(store, dict) else store
    findings = [f for f in (findings or []) if isinstance(f, dict)]
    active = [f for f in findings if (f.get("status") or "active") == "active"]
    above = sum(1 for f in active if at_or_above(derive_legacy_impact(f), level))
    parked = len(active) - above

    bp = _load_json(archie / "blueprint.json") or {}
    classes = list(bp.get("pitfalls") or []) + list(bp.get("unenforced_invariants") or [])
    guardrails = sum(
        1 for c in classes
        if isinstance(c, dict) and at_or_above(derive_legacy_impact(c, is_pitfall=True), level)
    )
    return {"above": above, "parked": parked, "guardrails": guardrails}


def counts(project_root: Path) -> dict:
    temp = load_temperature(project_root)
    level = temp.get("level", DEFAULT_LEVEL)
    result = _tiered_counts(project_root, level)
    result["level"] = level
    result["source"] = temp.get("source", "seeded") if temp else "unset"
    return result


def seed_if_absent(project_root: Path) -> dict:
    """One-time seed (spec §4). Existing temperature — seeded OR user — wins."""
    existing = load_temperature(project_root)
    if existing:
        return existing
    health = _load_json(Path(project_root) / ".archie" / "health.json") or {}
    chy = _tiered_counts(project_root, "can_hurt_you")["above"]
    nxt = _tiered_counts(project_root, "everything")["above"]
    seed = compute_seed(health, chy, nxt)
    save_temperature(project_root, seed)
    return seed


def main(argv: list) -> int:
    if len(argv) < 3 or argv[1] not in ("counts", "seed"):
        print("usage: impact_filter.py counts|seed <project_root>", file=sys.stderr)
        return 2
    root = Path(argv[2])
    if argv[1] == "counts":
        print(json.dumps(counts(root)))
    else:
        print(json.dumps(seed_if_absent(root)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_impact_filter.py -v`
Expected: 6 passed

- [ ] **Step 5: Copy to npm assets and verify sync**

```bash
cp archie/standalone/impact_filter.py npm-package/assets/impact_filter.py
python3 scripts/verify_sync.py
```
Expected: verify_sync passes. **Note:** if verify_sync flags `impact_filter.py` as an orphan asset (installer doesn't reference it yet), that's expected until Task 6 — check verify_sync's rules; if it hard-fails on orphans, defer the copy to Task 6 and note it.

- [ ] **Step 6: Commit**

```bash
git add archie/standalone/impact_filter.py npm-package/assets/impact_filter.py tests/test_impact_filter.py
git commit -m "feat(impact): impact_filter.py — tier order, temperature settings, counts, seed-once"
```

---

### Task 2: Emission contracts — `impact` + `consequence_path`, drop hardcoded `status`

Prompt-file edits only; no unit tests (validated by Task 3's merge tests + live scans).

**Files:**
- Modify: `archie/assets/workflow/deep-scan/steps/step-5b-risk.md` (finding contract ~lines 66-92, pitfall contract ~93-107, quality bar ~line 42)
- Modify: `archie/assets/workflow/deep-scan/steps/step-5-wave2-reasoning.md` (comprehensive-mode preamble untouched; add impact to any schema echo)
- Mirror copies per `scripts/verify_sync.py` output

**Interfaces:**
- Produces: emitted findings carry `"impact"` and optionally `"consequence_path"`; findings NO LONGER carry `"status"`. Task 3's merge and Task 4's verifier consume these.

- [ ] **Step 1: Edit the finding OUTPUT CONTRACT in `step-5b-risk.md`.** In the JSON schema block: remove the line `"status": "active",` and add after the `"kind"` line:

```
"impact": "regression|hazard|erosion",
"consequence_path": {"asset": "<named asset at risk>", "entry_point": "<rel/path.ext:line>", "trigger": "<what realistically sets it off>"},
```

- [ ] **Step 2: Add the tier-definition instruction block** after the existing quality-bar section (~line 42):

```
IMPACT TIER — required on every finding and pitfall. Impact is the user's gain
from fixing, independent of your confidence.
- "regression": already misbehaving — the triggering_call_site fires the failure
  mode under current code.
- "hazard": not broken yet, but a realistic path to outage, data loss, money
  loss, or security exposure. Claiming hazard on a conformance_break, pitfall,
  or gap REQUIRES consequence_path with all three fields concrete and
  verifiable; if you cannot name the asset, entry point, and trigger, the item
  is erosion. Do not narrate hypothetical consequences — the verifier will
  check the path.
- "erosion": a documented decision or invariant undermined; maintainability
  cost only. consequence_path must be omitted.
Do NOT emit a "status" field — lifecycle is owned by the store.
```

- [ ] **Step 3: Clarify the soft floor** — replace the existing "Soft floor of 3 total findings" sentence with:

```
Soft floor of 3 total findings in the updated store — an emission floor, never
a padding target: if fewer than 3 meet the bar, say so explicitly rather than
lowering the bar or inflating impact tiers to fill the count.
```

- [ ] **Step 4: Apply the same impact block to the pitfall contract** (~lines 93-107): add `"impact": "hazard|erosion"` (regression disallowed — a live-firing pitfall must be emitted as a finding) and the consequence_path requirement for hazard.

- [ ] **Step 5: Sync + commit**

```bash
python3 scripts/verify_sync.py   # follow its output for required mirror copies
git add archie/assets/workflow/deep-scan/steps/ npm-package/assets/ 
git commit -m "feat(impact): emission contracts — impact tier + consequence_path, drop hardcoded status"
```

---

### Task 3: `finalize.py` — prior-wins merge, impact_signal hysteresis vote, per-impact floors, platform pitfall tiers

**Files:**
- Modify: `archie/standalone/finalize.py` (`_merge_findings_into_store` lines 77-168; `_VERIFIER_PIPELINE_FIELDS` constant near top; gate call site ~line 374; `merge_platform_pitfalls` lines 27-57; `DEFAULT_COLD_FLOORS` region ~581)
- Test: `tests/test_finalize_impact_merge.py`
- Copy: `npm-package/assets/finalize.py`

**Interfaces:**
- Consumes: `impact_filter.derive_legacy_impact` (Task 1, sibling-path import), emissions shaped per Task 2.
- Produces: store entries where `impact` is stable (prior-wins), `impact_signal: {"value": str, "scan": str}` records a disagreeing re-emission, and new entries carry `impact` (or a derived provisional one with `"impact_provisional": true`). Task 5 consumes `impact_signal`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_finalize_impact_merge.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import finalize


def _store(tmp_path, findings):
    archie = tmp_path / ".archie"
    archie.mkdir(exist_ok=True)
    (archie / "findings.json").write_text(json.dumps({"findings": findings}))
    return archie


def test_prior_impact_wins_and_signal_recorded(tmp_path):
    archie = _store(tmp_path, [{"id": "f_1", "impact": "erosion", "status": "active"}])
    finalize._merge_findings_into_store(archie, [{"id": "f_1", "kind": "conformance_break", "impact": "hazard"}])
    store = json.loads((archie / "findings.json").read_text())
    f = store["findings"][0]
    assert f["impact"] == "erosion"                      # prior wins
    assert f["impact_signal"]["value"] == "hazard"       # disagreement recorded as a vote


def test_agreeing_reemission_clears_signal(tmp_path):
    archie = _store(tmp_path, [
        {"id": "f_1", "impact": "erosion", "status": "active",
         "impact_signal": {"value": "hazard", "scan": "old"}},
    ])
    finalize._merge_findings_into_store(archie, [{"id": "f_1", "impact": "erosion"}])
    f = json.loads((archie / "findings.json").read_text())["findings"][0]
    assert "impact_signal" not in f


def test_status_resurrection_fixed(tmp_path):
    # A demoted finding re-emitted WITH status active must stay demoted (prior wins).
    archie = _store(tmp_path, [{"id": "f_1", "status": "demoted", "impact": "hazard"}])
    finalize._merge_findings_into_store(archie, [{"id": "f_1", "status": "active", "impact": "hazard"}])
    f = json.loads((archie / "findings.json").read_text())["findings"][0]
    assert f["status"] == "demoted"


def test_new_id_takes_emitted_or_derived_impact(tmp_path):
    archie = _store(tmp_path, [])
    finalize._merge_findings_into_store(archie, [
        {"id": "f_9", "impact": "hazard"},
        {"id": "f_10", "kind": "behavioral_break"},       # no impact -> derived provisional
    ])
    by_id = {f["id"]: f for f in json.loads((archie / "findings.json").read_text())["findings"]}
    assert by_id["f_9"]["impact"] == "hazard"
    assert by_id["f_10"]["impact"] == "hazard"
    assert by_id["f_10"]["impact_provisional"] is True


def test_impact_floor_gate():
    kept = finalize.apply_impact_floors([
        {"id": "a", "impact": "regression", "confidence": 0.65},   # below 0.7 -> dropped
        {"id": "b", "impact": "hazard", "confidence": 0.65},       # above 0.6 -> kept
        {"id": "c", "impact": "erosion", "confidence": 0.55},      # above 0.5 -> kept
    ])
    assert [f["id"] for f in kept] == ["b", "c"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_finalize_impact_merge.py -v`
Expected: FAIL (`impact_signal` not set / `status` resurrected / `apply_impact_floors` missing)

- [ ] **Step 3: Implement in `finalize.py`.** (a) Add `"impact"` and `"status"` to the prior-wins set. Replace the `if prior:` body (lines 132-144) with:

```python
        if prior:
            merged = dict(nf)
            merged["first_seen"] = prior.get("first_seen") or nf.get("first_seen") or now
            merged["confirmed_in_scan"] = (prior.get("confirmed_in_scan") or 0) + 1
            # Lifecycle + tier are store-owned: the prior value ALWAYS wins over a
            # re-emission (spec: prior-wins merge). A disagreeing re-emitted impact
            # is recorded as a pending vote (impact_signal) for apply_verdicts.
            if prior.get("status"):
                merged["status"] = prior["status"]
            emitted_impact = nf.get("impact")
            prior_impact = prior.get("impact")
            if prior_impact:
                merged["impact"] = prior_impact
                if emitted_impact and emitted_impact != prior_impact:
                    merged["impact_signal"] = {"value": emitted_impact, "scan": now}
                else:
                    merged.pop("impact_signal", None)
                    if "impact_signal" in prior and emitted_impact == prior_impact:
                        pass  # agreement clears the stale signal
                    elif "impact_signal" in prior and not emitted_impact:
                        merged["impact_signal"] = prior["impact_signal"]
            for field in _VERIFIER_PIPELINE_FIELDS:
                if field not in merged and field in prior:
                    merged[field] = prior[field]
            by_id[fid] = merged
```

(b) In the `else:` (new-id) branch, after `merged.setdefault("status", "active")` add:

```python
            if "impact" not in merged:
                merged["impact"] = _impact_filter().derive_legacy_impact(merged)
                merged["impact_provisional"] = True
```

where `_impact_filter()` is a small sibling-path lazy import at module level (copy the exact pattern `finalize.py` already uses for sibling scripts at `_SCRIPT_DIR`, ~line 170).

(c) Add `apply_impact_floors` near `DEFAULT_COLD_FLOORS` (~line 581) and call it in the deep-scan gate path (call site ~line 374, AFTER `editor_gate.gate()` returns — never inside `gate()`):

```python
IMPACT_FLOORS = {"regression": 0.7, "hazard": 0.6, "erosion": 0.5, "preference": 0.5}


def apply_impact_floors(findings: list) -> list:
    """Spec §3 Gates: a claimed regression needs the highest confidence.
    Layered here (deep-scan path only) — editor_gate.gate() is shared with
    advisory review surfaces that carry no impact field."""
    kept = []
    for f in findings:
        floor = IMPACT_FLOORS.get(f.get("impact", "erosion"), 0.5)
        if (f.get("confidence") or 0) >= floor:
            kept.append(f)
    return kept
```

(d) In `merge_platform_pitfalls` (lines 27-57): every catalog-seeded pitfall gets `pitfall.setdefault("impact", "erosion")` — static tier, catalog entries may override by carrying their own.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_finalize_impact_merge.py tests/test_impact_filter.py -v`
Expected: all pass. Also run the existing finalize suite: `python -m pytest tests/ -k finalize -v` — no regressions.

- [ ] **Step 5: Copy + sync + commit**

```bash
cp archie/standalone/finalize.py npm-package/assets/finalize.py
python3 scripts/verify_sync.py
git add archie/standalone/finalize.py npm-package/assets/finalize.py tests/test_finalize_impact_merge.py
git commit -m "feat(impact): prior-wins merge with impact_signal vote, per-impact floors, platform pitfall tiers"
```

**Coordination note:** the spawned task "Fix demoted-finding resurrection on re-scan" overlaps with (a). If that task already landed, adapt: keep its status handling, add the impact handling beside it.

---

### Task 4: `verify_findings.py` — `impact_verdict` in both directions

**Files:**
- Modify: `archie/standalone/verify_findings.py` (verifier prompt DEMOTE block ~lines 70-77, verdict JSON schema ~line 91, verdict parsing, fail-open path ~231-233)
- Test: `tests/test_verify_findings_impact.py`
- Copy: `npm-package/assets/verify_findings.py`

**Interfaces:**
- Produces: verdict objects gain optional `"impact_verdict": "confirm" | "correct_to_regression" | "correct_to_hazard" | "correct_to_erosion"`. Task 5 consumes it.

- [ ] **Step 1: Write the failing tests** (target the pure parse/normalize function; find its name in the file — the function that turns the agent's text into `{verdict, confidence, reason}` — and extend tests around it):

```python
# tests/test_verify_findings_impact.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import verify_findings as vf


def test_parse_accepts_impact_verdict():
    raw = '{"verdict": "keep", "confidence": 0.8, "reason": "fires", "impact_verdict": "correct_to_regression"}'
    v = vf.parse_verdict(raw)   # adjust to the module's actual parse entry point
    assert v["impact_verdict"] == "correct_to_regression"


def test_parse_rejects_unknown_impact_verdict():
    raw = '{"verdict": "keep", "confidence": 0.8, "reason": "x", "impact_verdict": "correct_to_preference"}'
    v = vf.parse_verdict(raw)
    assert "impact_verdict" not in v   # invalid value stripped, verdict still usable


def test_fail_open_carries_no_impact_verdict():
    v = vf.parse_verdict("not json at all")
    assert v["verdict"] == "keep"
    assert "impact_verdict" not in v
```

- [ ] **Step 2: Run to verify failure.** `python -m pytest tests/test_verify_findings_impact.py -v` — FAIL.

- [ ] **Step 3: Implement.** (a) Extend the verdict schema line (~91) to document the new field. (b) In the parse/normalize function: accept `impact_verdict`, validate against the 4 allowed strings, strip if invalid. (c) Extend the verifier prompt with:

```
IMPACT VERDICT (optional field "impact_verdict"): after deciding keep/demote/drop,
check the finding's impact tier.
- "correct_to_regression": the triggering_call_site actually fires under current
  code — this is live, not latent.
- "correct_to_hazard": instance-anchored and real, but the failure mode does not
  fire today. (Distinct from demote: demote means this should not be a finding at
  all — it duplicates a pitfall class with no live instance. Pick exactly one.)
- "correct_to_erosion": the claimed consequence_path does not hold up — the asset
  is not reachable from the entry point, or the trigger is unrealistic.
- "confirm": the current tier is right.
Omit the field if unsure. Never invent a consequence you did not verify.
```

(d) Fail-open path (~231-233): unchanged verdict semantics, but ensure no `impact_verdict` is fabricated.

- [ ] **Step 4: Run tests.** `python -m pytest tests/test_verify_findings_impact.py -v` — pass; plus `python -m pytest tests/ -k verify -v` — no regressions.

- [ ] **Step 5: Copy + sync + commit**

```bash
cp archie/standalone/verify_findings.py npm-package/assets/verify_findings.py
python3 scripts/verify_sync.py
git add archie/standalone/verify_findings.py npm-package/assets/verify_findings.py tests/test_verify_findings_impact.py
git commit -m "feat(impact): verifier impact_verdict — bidirectional tier correction"
```

---

### Task 5: `apply_verdicts.py` — impact hysteresis + downgrade guard + atomic write

**Files:**
- Modify: `archie/standalone/apply_verdicts.py` (main loop ~118-216, `_two_consecutive`/`_has_material_change` ~93-119, write ~301-303)
- Test: `tests/test_apply_verdicts_impact.py`
- Copy: `npm-package/assets/apply_verdicts.py`

**Interfaces:**
- Consumes: `impact_verdict` (Task 4), `impact_signal` (Task 3), `impact_filter.load_temperature` + `at_or_above` (Task 1).
- Produces: findings' `impact` transitions under hysteresis; `impact_history` list (mirrors `verdict_history`, depth 3); a `last_scan_changes` block written into `findings.json` top level: `{"scan": iso, "moved_below_line": [{"id", "from", "to", "reason"}]}`. Task 6 (receipt) consumes `last_scan_changes`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_apply_verdicts_impact.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import apply_verdicts as av


def test_single_impact_verdict_is_pending_not_applied():
    f = {"id": "f_1", "impact": "hazard", "status": "active", "impact_history": []}
    av.apply_impact_verdict(f, "correct_to_erosion", material_change=False)
    assert f["impact"] == "hazard"                       # one verdict is not enough
    assert f["impact_history"] == ["correct_to_erosion"]


def test_two_consecutive_impact_verdicts_apply():
    f = {"id": "f_1", "impact": "hazard", "status": "active",
         "impact_history": ["correct_to_erosion"]}
    moved = av.apply_impact_verdict(f, "correct_to_erosion", material_change=False)
    assert f["impact"] == "erosion"
    assert moved == ("hazard", "erosion")


def test_material_change_applies_immediately():
    f = {"id": "f_1", "impact": "erosion", "status": "active", "impact_history": []}
    av.apply_impact_verdict(f, "correct_to_regression", material_change=True)
    assert f["impact"] == "regression"


def test_impact_signal_counts_as_a_vote():
    # Task 3 wrote impact_signal from a disagreeing re-emission; one matching
    # verifier verdict on top of it completes the 2-consecutive requirement.
    f = {"id": "f_1", "impact": "hazard", "status": "active",
         "impact_signal": {"value": "erosion", "scan": "s1"}, "impact_history": []}
    av.apply_impact_verdict(f, "correct_to_erosion", material_change=False)
    assert f["impact"] == "erosion"


def test_downgrade_guard_records_below_line_move(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    (archie / "findings.json").write_text(json.dumps({"findings": [
        {"id": "f_1", "impact": "hazard", "status": "active",
         "impact_history": ["correct_to_erosion"]},
    ]}))
    (archie / "settings.local.json").write_text(json.dumps(
        {"temperature": {"level": "can_hurt_you", "source": "user"}}))
    av.run_impact_pass(tmp_path, {"f_1": {"verdict": "keep", "impact_verdict": "correct_to_erosion"}})
    store = json.loads((archie / "findings.json").read_text())
    moves = store["last_scan_changes"]["moved_below_line"]
    assert moves == [{"id": "f_1", "from": "hazard", "to": "erosion",
                      "reason": "verifier correct_to_erosion (2 consecutive)"}]
```

- [ ] **Step 2: Run to verify failure.** `python -m pytest tests/test_apply_verdicts_impact.py -v` — FAIL.

- [ ] **Step 3: Implement.** Add to `apply_verdicts.py` (reusing the module's existing `_two_consecutive` discipline and `IMPACT_HISTORY_DEPTH = 3`):

```python
IMPACT_HISTORY_DEPTH = 3
_VERDICT_TO_TIER = {
    "correct_to_regression": "regression",
    "correct_to_hazard": "hazard",
    "correct_to_erosion": "erosion",
}


def apply_impact_verdict(finding: dict, impact_verdict: str, material_change: bool):
    """Move `impact` under the same hysteresis as status: 2 consecutive matching
    signals OR a git-anchored material change. An impact_signal recorded by the
    emission merge counts as one signal. Returns (old, new) when moved, else None."""
    target = _VERDICT_TO_TIER.get(impact_verdict)
    hist = finding.setdefault("impact_history", [])
    hist.append(impact_verdict)
    del hist[:-IMPACT_HISTORY_DEPTH]
    if not target or target == finding.get("impact"):
        finding.pop("impact_signal", None)
        return None
    signal = finding.get("impact_signal", {}).get("value")
    consecutive = len(hist) >= 2 and hist[-1] == hist[-2]
    signal_agrees = signal == target
    if material_change or consecutive or signal_agrees:
        old = finding.get("impact")
        finding["impact"] = target
        finding.pop("impact_signal", None)
        finding.pop("impact_provisional", None)
        return (old, target)
    return None
```

Wire it into the main verdict loop (where keep/demote/drop already apply, ~118-216); reuse the loop's existing git-anchor `material_change` boolean. After the loop, compute below-line moves using `impact_filter.load_temperature(project_root)` + `at_or_above` and write:

```python
    store["last_scan_changes"] = {
        "scan": now_iso,
        "moved_below_line": moved_below,   # [{"id","from","to","reason"}]
    }
```

Also replace the non-atomic `findings_path.write_text(...)` (~line 303) with the tempfile + `os.replace` pattern copied verbatim from `finalize.py:156-161`.

- [ ] **Step 4: Run tests.** `python -m pytest tests/test_apply_verdicts_impact.py -v` — pass; `python -m pytest tests/ -k verdict -v` — no regressions.

- [ ] **Step 5: Copy + sync + commit**

```bash
cp archie/standalone/apply_verdicts.py npm-package/assets/apply_verdicts.py
python3 scripts/verify_sync.py
git add archie/standalone/apply_verdicts.py npm-package/assets/apply_verdicts.py tests/test_apply_verdicts_impact.py
git commit -m "feat(impact): impact hysteresis, downgrade guard, atomic verdict write"
```

---

### Task 6: Step 9 receipt + installer (`archie.mjs`)

**Files:**
- Modify: `archie/assets/workflow/deep-scan/steps/step-9-finalize.md` (Phase 1 ~lines 12-20, receipt Phase 4 ~lines 60-75)
- Modify: `npm-package/bin/archie.mjs` (install manifest + gitignore block, ~line 487 region)
- Mirror copies per verify_sync

**Interfaces:**
- Consumes: `impact_filter.py` CLI (Task 1), `last_scan_changes` (Task 5).

- [ ] **Step 1: Seed after health.** In Phase 1, immediately after the two `measure_health.py` lines, add:

```
python3 .archie/impact_filter.py seed "$PROJECT_ROOT"
```

- [ ] **Step 2: Replace the receipt count.** In Phase 4, replace the `.findings|length` inspect line with:

```
python3 .archie/impact_filter.py counts "$PROJECT_ROOT"
```

and update the receipt template to render from its JSON:

```
- Above the line (<level>): <above> item(s) — fix these and you're done at this temperature
- Parked below the line: <parked> · Standing guardrails: <guardrails>
- <if last_scan_changes.moved_below_line non-empty>: Moved below your line this scan: <id> (<from> → <to>, <reason>)
- Adjust the line in /archie-viewer (Report tab).
```

Add `last_scan_changes` retrieval via the existing allowlisted inspect: `python3 .archie/intent_layer.py inspect "$PROJECT_ROOT" findings.json --query '.last_scan_changes'` (verify this dotted path works with `cmd_inspect`; if the allowlist in step-9 forbids it, extend the step's allowlisted-command list — the list lives in the step file itself).

- [ ] **Step 3: Installer.** In `archie.mjs`: add `impact_filter.py` to the copied-scripts manifest (same list that ships `measure_health.py`), and add `.archie/settings.local.json` to the generated gitignore block (the block that already handles `.claude/settings.local.json`).

- [ ] **Step 4: Verify install manifest consistency.** Run `python3 scripts/verify_sync.py` — the Task 1 orphan (if any) must now be resolved.

- [ ] **Step 5: Commit**

```bash
git add archie/assets/workflow/deep-scan/steps/step-9-finalize.md npm-package/bin/archie.mjs npm-package/assets/
git commit -m "feat(impact): receipt counts above-the-line via impact_filter; installer ships it + gitignores settings.local.json"
```

---

### Task 7: Viewer backend — `POST /api/temperature` + bundle exposure

**Files:**
- Modify: `archie/standalone/viewer.py` (do_POST allowlist line 299 + new branch; bundle/api serving ~266-361 to include temperature + counts)
- Modify: `archie/standalone/upload.py` — NO temperature in share bundles (spec §4); verify only, no change expected
- Test: `tests/test_viewer_temperature.py`
- Copy: `npm-package/assets/viewer.py`

**Interfaces:**
- Consumes: `impact_filter.load_temperature/save_temperature/counts/seed_if_absent` (Task 1).
- Produces: `GET /api/temperature` → `{"level","source","seeded_reason","recommendation":{...}|null, "counts":{"above","parked","guardrails"}}`; `POST /api/temperature` body `{"level": "<one of 3>"}` → sets `source:"user"`, returns the GET shape. Task 8 consumes both.

- [ ] **Step 1: Write the failing tests** (unit-test the handler helpers, not HTTP):

```python
# tests/test_viewer_temperature.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import viewer


def _root(tmp_path):
    (tmp_path / ".archie").mkdir()
    (tmp_path / ".archie" / "findings.json").write_text(json.dumps({"findings": []}))
    return tmp_path


def test_get_temperature_seeds_lazily(tmp_path):
    root = _root(tmp_path)
    out = viewer._get_temperature_payload(root)
    assert out["level"] in ("can_hurt_you", "everything")
    assert out["source"] == "seeded"
    assert set(out["counts"]) == {"above", "parked", "guardrails"}


def test_post_temperature_sets_user_source(tmp_path):
    root = _root(tmp_path)
    out = viewer._apply_temperature_action(root, {"level": "broken_now"})
    assert out["level"] == "broken_now"
    assert out["source"] == "user"


def test_post_temperature_rejects_bad_level(tmp_path):
    root = _root(tmp_path)
    try:
        viewer._apply_temperature_action(root, {"level": "nuclear"})
        assert False, "should have raised"
    except ValueError:
        pass
```

- [ ] **Step 2: Run to verify failure.** `python -m pytest tests/test_viewer_temperature.py -v` — FAIL.

- [ ] **Step 3: Implement in `viewer.py`.** Import `impact_filter` by the sibling-path pattern the file already uses. Add:

```python
def _recommendation(root, current):
    """Ongoing chip (spec §4): what the seed WOULD be now; None when it agrees."""
    import impact_filter as imf
    health = imf._load_json(Path(root) / ".archie" / "health.json") or {}
    chy = imf._tiered_counts(root, "can_hurt_you")["above"]
    nxt = imf._tiered_counts(root, "everything")["above"]
    would = imf.compute_seed(health, chy, nxt)
    if would["level"] == current.get("level"):
        return None
    return {"level": would["level"], "reason": would["seeded_reason"]}


def _get_temperature_payload(root):
    import impact_filter as imf
    temp = imf.seed_if_absent(root)
    payload = dict(temp)
    payload["counts"] = {k: v for k, v in imf.counts(root).items()
                         if k in ("above", "parked", "guardrails")}
    payload["recommendation"] = _recommendation(root, temp)
    # Clear is an event, not a state (spec §4): stamp last_clear when the
    # above-the-line list is empty; keep the stamp when items reappear so the
    # UI can say "N new items since your last clear".
    payload["last_clear"] = imf.stamp_or_get_last_clear(root, payload["counts"]["above"])
    return payload


def _apply_temperature_action(root, body):
    import impact_filter as imf
    level = body.get("level")
    if level not in imf.LEVEL_MAX_TIER:
        raise ValueError(f"Unknown level: {level}")
    imf.save_temperature(root, {"level": level, "source": "user"})
    return _get_temperature_payload(root)
```

Wire into the handler: add `"/api/temperature"` to the GET routing (serve `_get_temperature_payload(root)`) and to the do_POST allowlist tuple (line 299), with a branch mirroring the `/api/exposure` pattern (ValueError → 400).

- [ ] **Step 4: Run tests.** `python -m pytest tests/test_viewer_temperature.py -v` — pass.

- [ ] **Step 5: Copy + sync + commit**

```bash
cp archie/standalone/viewer.py npm-package/assets/viewer.py
python3 scripts/verify_sync.py
git add archie/standalone/viewer.py npm-package/assets/viewer.py tests/test_viewer_temperature.py
git commit -m "feat(impact): viewer temperature API — lazy seed, sticky user source, recommendation chip data"
```

---

### Task 8: Viewer frontend — dial, guardrails band, clear event, parity test

**Files:**
- Modify: `share/viewer/src/lib/findings.ts` (Finding interface ~17-45, `normalizeStructuredFinding` ~52-80, `rankFindings` ~167-176)
- Create: `share/viewer/src/lib/impactFilter.ts` + `share/viewer/src/lib/impactFilter.test.ts`
- Create: `share/viewer/src/components/TemperatureDial.tsx`
- Modify: `share/viewer/src/pages/ReportPage.tsx` (filter ~138-149 + dial/band/parked/clear rendering)
- Modify: `share/viewer/src/lib/api.ts` (GET/POST /api/temperature)
- Create: `tests/fixtures/impact_parity/case1.json` (+ `test_impact_parity` added to `tests/test_impact_filter.py`)
- Mirror: `npm-package/assets/viewer/**` and `archie/assets/viewer/**` per verify_sync

**Interfaces:**
- Consumes: Task 7's API shapes.
- Produces: `impactAtOrAbove(impact: string, level: string): boolean`, `deriveLegacyImpact(item, isPitfall)` — MUST match `impact_filter.py` semantics exactly (parity-tested).

- [ ] **Step 1: Write `impactFilter.ts`** (mirror of the Python, same constants):

```typescript
export const TIER_ORDER: Record<string, number> = { regression: 0, hazard: 1, erosion: 2, preference: 3 }
export const LEVEL_MAX_TIER: Record<string, number> = { broken_now: 0, can_hurt_you: 1, everything: 3 }
export const LEVEL_LABELS: Record<string, { label: string; hint: string }> = {
  broken_now: { label: 'Broken now', hint: 'already misbehaving' },
  can_hurt_you: { label: 'Can hurt you', hint: 'outage · money · data' },
  everything: { label: 'Everything', hint: 'incl. architecture debt' },
}

export function deriveLegacyImpact(item: any, isPitfall = false): string {
  if (item?.impact && item.impact in TIER_ORDER) return item.impact
  if (isPitfall) return item?.severity === 'error' ? 'hazard' : 'erosion'
  return item?.kind === 'behavioral_break' ? 'hazard' : 'erosion'
}

export function impactAtOrAbove(impact: string, level: string): boolean {
  const tier = TIER_ORDER[impact] ?? TIER_ORDER.erosion
  return tier <= (LEVEL_MAX_TIER[level] ?? LEVEL_MAX_TIER.can_hurt_you)
}
```

- [ ] **Step 2: Write the parity fixture + both tests.** `tests/fixtures/impact_parity/case1.json`:

```json
{
  "level": "can_hurt_you",
  "items": [
    {"impact": "regression", "expected_above": true},
    {"impact": "hazard", "expected_above": true},
    {"impact": "erosion", "expected_above": false},
    {"kind": "behavioral_break", "expected_above": true},
    {"kind": "conformance_break", "expected_above": false},
    {"severity": "error", "is_pitfall": true, "expected_above": true},
    {"severity": "warn", "is_pitfall": true, "expected_above": false}
  ]
}
```

`share/viewer/src/lib/impactFilter.test.ts` (node:test, same pattern as `blueprintTitle.test.ts`):

```typescript
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { deriveLegacyImpact, impactAtOrAbove } from './impactFilter'

test('parity with impact_filter.py on shared fixtures', () => {
  const fixture = JSON.parse(readFileSync(new URL('../../../../tests/fixtures/impact_parity/case1.json', import.meta.url), 'utf8'))
  for (const item of fixture.items) {
    const impact = deriveLegacyImpact(item, item.is_pitfall ?? false)
    assert.equal(impactAtOrAbove(impact, fixture.level), item.expected_above, JSON.stringify(item))
  }
})
```

Python side, append to `tests/test_impact_filter.py`:

```python
def test_impact_parity_fixture():
    fixture = json.loads((Path(__file__).parent / "fixtures" / "impact_parity" / "case1.json").read_text())
    for item in fixture["items"]:
        impact = imf.derive_legacy_impact(item, item.get("is_pitfall", False))
        assert imf.at_or_above(impact, fixture["level"]) == item["expected_above"], item
```

- [ ] **Step 3: Run both sides.**
Run: `python -m pytest tests/test_impact_filter.py::test_impact_parity_fixture -v` — pass.
Run: `cd share/viewer && node --experimental-strip-types --test src/lib/impactFilter.test.ts` (Node ≥ 22.6; if the runtime lacks strip-types, use `npx tsx --test src/lib/impactFilter.test.ts`) — pass.

- [ ] **Step 4: Extend `findings.ts`.** Add to the `Finding` interface: `impact?: string`, `impact_signal?: { value: string; scan: string }`, `consequence_path?: { asset: string; entry_point: string; trigger: string }`. Thread them through `normalizeStructuredFinding` (same pattern as the existing `verdict_history` threading at ~lines 38-44, 70-77). In `rankFindings` (~167-176), sort by `TIER_ORDER[deriveLegacyImpact(f)]` FIRST, then the existing severity/group keys.

- [ ] **Step 5: Build `TemperatureDial.tsx`.** A 3-segment control + recommendation chip + parked affordance, driven entirely by the Task 7 API payload. Props: `{ payload, onSetLevel(level), readOnly }` (readOnly = share mode → local state only, default `can_hurt_you`). Segments render `LEVEL_LABELS`; the chip renders `payload.recommendation` with an "Apply" button calling `onSetLevel(recommendation.level)`; the parked line renders "N quieter items parked below the line" as a button that bumps one level warmer. Follow the existing component idioms in `share/viewer/src/components/` (check `ReportSections.tsx` for card/heading classes).

- [ ] **Step 6: Wire `ReportPage.tsx`.** (a) Extend the active-filter (~138-149):

```typescript
const active = bundle!.findings!.filter((f: any) => (f?.status || 'active') === 'active')
const aboveLine = active.filter((f: any) => impactAtOrAbove(deriveLegacyImpact(f), level))
const parkedCount = active.length - aboveLine.length
```

(b) Headline band: `aboveLine.length` items "above the line · fix these and you're done at this temperature"; when 0, green clear state "Clear as of scan (date) at (label)". (c) Standing-guardrails band: pitfalls + gaps (from `bundle.blueprint`) filtered by the same predicate, rendered as a separate list titled "Standing guardrails" with copy "things Archie watches for, not tasks to finish" — reuse the existing pitfall-rendering components, do NOT count them in the headline. (d) fixPrompt stays attached everywhere it is today — verify no call sites removed.

- [ ] **Step 7: Typecheck + build.** `cd share/viewer && npx tsc -b && npx vite build` — clean.

- [ ] **Step 8: Manual verification.** `python3 archie/standalone/viewer.py /Users/hamutarto/DEV/Repos/SubscriberAgent` — open the report: dial shows, defaults seeded, switching levels refilters instantly, guardrails band shows pf_0004/pf_0005 at Can hurt you, parked affordance counts, POST persists across reload, share mode (if a bundle is handy) read-only.

- [ ] **Step 9: Mirror + sync + commit.** Copy changed viewer sources to BOTH `npm-package/assets/viewer/` and `archie/assets/viewer/` (verify_sync tells you the exact set):

```bash
python3 scripts/verify_sync.py
git add share/viewer/ npm-package/assets/viewer/ archie/assets/viewer/ tests/
git commit -m "feat(impact): viewer dial, standing guardrails band, clear event, TS/Python parity test"
```

---

### Task 9: Docs + final sweep

**Files:**
- Modify: `CLAUDE.md` (Rules System section — add the impact-tier table beside the severity_class table, explicitly "parallel, distinct: temperature never gates edits"; document the `.archie/settings.local.json` contract incl. "set source:user only on human request")
- Modify: `docs/archie-impact-temperature-design.md` (status → Implemented)
- Optional: `share/viewer/src/lib/fixPrompt.ts` — one additive header line `Impact: <tier>` when present (+ mirrors)

- [ ] **Step 1: Write the CLAUDE.md additions** (side-by-side tables + settings contract, ~20 lines).
- [ ] **Step 2: fixPrompt header line** — in `buildFixPrompt`, after the lead attribution line, when `item.impact` exists append `` `Impact: ${item.impact}` `` (+ consequence_path.asset when present). Mirror to both asset copies.
- [ ] **Step 3: Full suite.**

```bash
python -m pytest tests/ -v
python3 scripts/verify_sync.py
cd share/viewer && npx tsc -b
```
Expected: all pass (3 pre-existing failures noted in c37b8e5's message may persist — verify they're the same ones, not new).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/archie-impact-temperature-design.md share/viewer npm-package/assets archie/assets
git commit -m "docs(impact): taxonomy tables, settings contract; fixPrompt impact header; final sweep"
```

---

## Task ordering & independence

```
Task 0 (GATE) → Task 1 → {Task 2, Task 3, Task 4} (parallel-safe) → Task 5 → Task 6 → Task 7 → Task 8 → Task 9
```

Tasks 2/3/4 touch disjoint files and can run in any order after Task 1. Task 5 needs 3+4. Task 6 needs 1+5. Task 7 needs 1. Task 8 needs 7. Task 9 last.

**Out of scope (explicitly, per spec):** pitfall ack/lifecycle (v2), tier-④ producer, any CLI/slash write surface, `pre-validate.sh`/rules changes, hazard-share telemetry warning (spec §12 lists it as a mitigation option — defer until real scans show inflation).

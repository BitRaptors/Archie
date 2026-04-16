# Semantic Findings Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify `/archie-scan` and `/archie-deep-scan` findings under a single "Semantic Findings" schema with two tiers (systemic, localized), one shared calibration spec, and `synthesis_depth: draft | canonical`.

**Architecture:** Harvest findings from existing reads (Wave 1 observations, Wave 2 synthesis, shrunk Phase 2) rather than adding new passes. One `_shared/semantic_findings_spec.md` defines schema + severity rubric + quality gate; all agents reference it. Deep-scan's Wave 2 produces canonical findings and upgrades stored fast-scan drafts on each run. New Python aggregator merges wave1/2/phase2/mechanical → `semantic_findings.json`. Upload + viewer gain `bundle_version` branching for backward compat.

**Tech Stack:** Python 3.9+ (stdlib only), Markdown slash commands (Claude Code), JSON data files, embedded HTML/JS in `viewer.py`, pytest for Python tests.

**Design reference:** `docs/plans/2026-04-16-semantic-findings-design.md` (committed `be18b1c`).

---

## Phase A — Foundation (spec + aggregator script)

No user-visible change. Lays the calibration artifact and the new Python aggregator the commands will invoke.

### Task 1: Write the shared calibration spec

**Files:**
- Create: `.claude/commands/_shared/semantic_findings_spec.md`

**Step 1: Create the file with header + schema + quality gate + severity rubric + taxonomy + synthesis depth + source conventions.** Content per `docs/plans/2026-04-16-semantic-findings-design.md` "Shared calibration" section. Include: the full JSON schema (copy from design doc), the quality gate table, the severity rubric bullet list, the full type taxonomy (9 systemic + 12 localized) with one-sentence definition each, `synthesis_depth` explanation, `source` string enum, and the "no count caps" directive.

**Step 2: Add maintainer header at top:**

```markdown
# Shared fragment — Semantic Findings calibration spec

> **This file is the single source of truth for the Semantic Findings schema, severity rubric, and quality gate.**
> Every agent prompt that emits Semantic Findings MUST reference this file by path and follow it exactly.
> When you update calibration, update this file ONLY — do not restate calibration inline in any agent prompt.
> Changes here apply to both `/archie-scan` and `/archie-deep-scan` automatically.
```

**Step 3: Commit**

```bash
git add .claude/commands/_shared/semantic_findings_spec.md
git commit -m "docs(findings): add semantic_findings_spec shared fragment"
```

---

### Task 2: Write failing tests for the aggregator

**Files:**
- Create: `tests/test_aggregate_findings.py`

**Step 1: Write test for the finding signature function.** Signature = `type + sorted(components_affected)`. Used for NEW/RECURRING/RESOLVED matching.

```python
from archie.standalone.aggregate_findings import finding_signature

def test_finding_signature_orders_components():
    f = {"type": "fragmentation", "scope": {"components_affected": ["b", "a"]}}
    assert finding_signature(f) == "fragmentation|a|b"

def test_finding_signature_handles_missing_components():
    f = {"type": "cycle", "scope": {}}
    assert finding_signature(f) == "cycle|"

def test_finding_signature_ignores_evidence_locations():
    f1 = {"type": "god_component", "scope": {"components_affected": ["shared"], "locations": ["a.ts:1"]}}
    f2 = {"type": "god_component", "scope": {"components_affected": ["shared"], "locations": ["b.ts:2"]}}
    assert finding_signature(f1) == finding_signature(f2)
```

**Step 2: Write test for lifecycle_status computation** (new, recurring, resolved, worsening).

```python
from archie.standalone.aggregate_findings import compute_lifecycle

def test_lifecycle_new_when_no_prior():
    current = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}]
    result = compute_lifecycle(current, prior=[])
    assert result[0]["lifecycle_status"] == "new"
    assert result[0]["blast_radius_delta"] == 0

def test_lifecycle_recurring_when_in_prior():
    prior = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}]
    current = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}]
    result = compute_lifecycle(current, prior=prior)
    assert result[0]["lifecycle_status"] == "recurring"
    assert result[0]["blast_radius_delta"] == 0

def test_lifecycle_worsening_when_blast_grew():
    prior = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}]
    current = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 8}]
    result = compute_lifecycle(current, prior=prior)
    assert result[0]["lifecycle_status"] == "worsening"
    assert result[0]["blast_radius_delta"] == 5

def test_lifecycle_resolved_findings_emitted_separately():
    prior = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "blast_radius": 3}]
    current = []
    result = compute_lifecycle(current, prior=prior)
    resolved = [f for f in result if f["lifecycle_status"] == "resolved"]
    assert len(resolved) == 1
    assert resolved[0]["type"] == "cycle"
```

**Step 3: Write test for quality gate enforcement** (drop findings missing required fields).

```python
from archie.standalone.aggregate_findings import apply_quality_gate

def test_quality_gate_drops_systemic_missing_pattern_description():
    findings = [{
        "category": "systemic", "type": "fragmentation",
        "scope": {"components_affected": ["a","b","c"], "locations": ["x","y","z"]},
        # pattern_description missing
        "root_cause": "...", "fix_direction": "...", "blast_radius": 3
    }]
    kept = apply_quality_gate(findings)
    assert len(kept) == 0

def test_quality_gate_drops_systemic_with_fewer_than_3_evidence():
    findings = [{
        "category": "systemic", "type": "fragmentation",
        "pattern_description": "x",
        "scope": {"components_affected": ["a"], "locations": ["x"]},
        "root_cause": "...", "fix_direction": "...", "blast_radius": 1
    }]
    kept = apply_quality_gate(findings)
    assert len(kept) == 0

def test_quality_gate_keeps_localized_with_single_location():
    findings = [{
        "category": "localized", "type": "dependency_violation",
        "scope": {"components_affected": ["a"], "locations": ["x:1"]},
        "root_cause": "...", "fix_direction": "..."
    }]
    kept = apply_quality_gate(findings)
    assert len(kept) == 1
```

**Step 4: Write test for merge + dedupe across sources.**

```python
from archie.standalone.aggregate_findings import merge_sources

def test_merge_dedupes_by_signature_keeps_canonical():
    wave2 = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "synthesis_depth": "canonical", "source": "wave2"}]
    mech = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "synthesis_depth": "draft", "source": "mechanical"}]
    merged = merge_sources(wave1=[], wave2=wave2, phase2=[], mechanical=mech)
    sigs = [f["source"] for f in merged]
    assert sigs.count("mechanical") == 0
    assert sigs.count("wave2") == 1

def test_merge_never_downgrades_severity():
    wave2 = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "severity": "error", "source": "wave2"}]
    mech = [{"type": "cycle", "scope": {"components_affected": ["a"]}, "severity": "warn", "source": "mechanical"}]
    merged = merge_sources(wave1=[], wave2=wave2, phase2=[], mechanical=mech)
    assert len(merged) == 1
    assert merged[0]["severity"] == "error"
```

**Step 5: Run tests and confirm they fail (module doesn't exist yet)**

```bash
python3 -m pytest tests/test_aggregate_findings.py -v
```

Expected: `ModuleNotFoundError: No module named 'archie.standalone.aggregate_findings'`

**Step 6: Commit the failing tests**

```bash
git add tests/test_aggregate_findings.py
git commit -m "test(findings): failing tests for aggregate_findings module"
```

---

### Task 3: Implement the aggregator module

**Files:**
- Create: `archie/standalone/aggregate_findings.py`

**Step 1: Implement `finding_signature(finding) -> str`.**

```python
def finding_signature(finding: dict) -> str:
    ftype = finding.get("type", "")
    components = sorted(finding.get("scope", {}).get("components_affected", []) or [])
    return f"{ftype}|{'|'.join(components)}"
```

**Step 2: Implement `apply_quality_gate(findings) -> list`.** Drop systemic without `pattern_description`, `root_cause`, `fix_direction`, `blast_radius`, OR fewer than 3 locations. Drop localized without `root_cause`, `fix_direction`, or 1 location.

```python
def apply_quality_gate(findings: list) -> list:
    kept = []
    for f in findings:
        if f.get("category") == "systemic":
            if not f.get("pattern_description"): continue
            locations = f.get("scope", {}).get("locations", []) or []
            if len(locations) < 3: continue
            if not f.get("root_cause") or not f.get("fix_direction"): continue
            if f.get("blast_radius") is None: continue
        else:  # localized
            locations = f.get("scope", {}).get("locations", []) or []
            if len(locations) < 1: continue
            if not f.get("root_cause") or not f.get("fix_direction"): continue
        kept.append(f)
    return kept
```

**Step 3: Implement `compute_lifecycle(current, prior) -> list`.** Attach `lifecycle_status` + `blast_radius_delta` to current findings; emit resolved findings (in prior but not current) with `lifecycle_status: resolved`.

```python
def compute_lifecycle(current: list, prior: list) -> list:
    prior_by_sig = {finding_signature(f): f for f in prior}
    current_sigs = set()
    result = []
    for f in current:
        sig = finding_signature(f)
        current_sigs.add(sig)
        prev = prior_by_sig.get(sig)
        current_br = f.get("blast_radius") or 0
        prior_br = (prev.get("blast_radius") if prev else 0) or 0
        delta = current_br - prior_br
        f = {**f, "blast_radius_delta": delta}
        if prev is None:
            f["lifecycle_status"] = "new"
        elif delta > 0:
            f["lifecycle_status"] = "worsening"
        else:
            f["lifecycle_status"] = "recurring"
        result.append(f)
    for sig, prev in prior_by_sig.items():
        if sig not in current_sigs:
            resolved = {**prev, "lifecycle_status": "resolved", "blast_radius_delta": 0}
            result.append(resolved)
    return result
```

**Step 4: Implement `merge_sources(wave1, wave2, phase2, mechanical) -> list`.** Dedupe by signature. Priority: canonical > draft. Within same depth: wave2 > phase2 > wave1 > mechanical. Never downgrade severity when deduping.

```python
SOURCE_RANK = {"wave2": 4, "phase2": 3, "wave1_structure": 2, "wave1_patterns": 2, "mechanical": 1,
               "fast_agent_a": 2, "fast_agent_b": 2, "fast_agent_c": 2}
SEVERITY_RANK = {"error": 3, "warn": 2, "info": 1}

def _pick(a: dict, b: dict) -> dict:
    a_depth = 1 if a.get("synthesis_depth") == "canonical" else 0
    b_depth = 1 if b.get("synthesis_depth") == "canonical" else 0
    if a_depth != b_depth:
        winner = a if a_depth > b_depth else b
    else:
        a_rank = SOURCE_RANK.get(a.get("source", ""), 0)
        b_rank = SOURCE_RANK.get(b.get("source", ""), 0)
        winner = a if a_rank >= b_rank else b
    loser = b if winner is a else a
    # Never downgrade severity
    if SEVERITY_RANK.get(loser.get("severity", ""), 0) > SEVERITY_RANK.get(winner.get("severity", ""), 0):
        winner = {**winner, "severity": loser["severity"]}
    return winner

def merge_sources(wave1, wave2, phase2, mechanical) -> list:
    all_findings = list(wave1) + list(wave2) + list(phase2) + list(mechanical)
    by_sig: dict = {}
    for f in all_findings:
        sig = finding_signature(f)
        if sig in by_sig:
            by_sig[sig] = _pick(by_sig[sig], f)
        else:
            by_sig[sig] = f
    return list(by_sig.values())
```

**Step 5: Implement the CLI entrypoint `main()`.** Reads the four input JSON files (paths from argv or defaults in `.archie/`), reads prior `semantic_findings.json`, runs merge → quality gate → lifecycle, writes `.archie/semantic_findings.json`.

```python
import json
import sys
from pathlib import Path

def _load(path: Path) -> list:
    if not path.exists(): return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list): return data
    return data.get("findings", []) if isinstance(data, dict) else []

def main():
    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    archie_dir = project_root / ".archie"
    wave1 = _load(archie_dir / "semantic_findings_wave1.json")
    wave2 = _load(archie_dir / "semantic_findings_wave2.json")
    phase2 = _load(archie_dir / "semantic_findings_phase2.json")
    mechanical = _load(archie_dir / "drift_report.json")
    prior = _load(archie_dir / "semantic_findings.json")

    merged = merge_sources(wave1, wave2, phase2, mechanical)
    gated = apply_quality_gate(merged)
    with_lifecycle = compute_lifecycle(gated, prior)

    out = {"findings": with_lifecycle, "schema_version": 1}
    (archie_dir / "semantic_findings.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(with_lifecycle)} findings to semantic_findings.json", file=sys.stderr)

if __name__ == "__main__":
    main()
```

**Step 6: Run tests, verify they pass**

```bash
python3 -m pytest tests/test_aggregate_findings.py -v
```

Expected: all 9 tests pass.

**Step 7: Commit**

```bash
git add archie/standalone/aggregate_findings.py
git commit -m "feat(findings): aggregate_findings merges wave/phase/mechanical with lifecycle + quality gate"
```

---

### Task 4: Sync aggregator to npm-package

**Files:**
- Copy: `archie/standalone/aggregate_findings.py` → `npm-package/assets/aggregate_findings.py`
- Modify: `npm-package/bin/archie.mjs` if it lists tracked scripts (check first)

**Step 1: Copy the file**

```bash
cp archie/standalone/aggregate_findings.py npm-package/assets/aggregate_findings.py
```

**Step 2: Check if `archie.mjs` references standalone scripts**

```bash
grep -n "aggregate_findings\|standalone" npm-package/bin/archie.mjs | head -20
```

If `archie.mjs` uses a hardcoded list of assets, add `aggregate_findings.py` to the list. If it globs `npm-package/assets/*.py`, no change needed.

**Step 3: Run sync verifier**

```bash
python3 scripts/verify_sync.py
```

Expected: exit 0 (no drift).

**Step 4: Commit**

```bash
git add npm-package/assets/aggregate_findings.py npm-package/bin/archie.mjs
git commit -m "chore(npm): sync aggregate_findings to npm-package/assets"
```

---

## Phase B — Fast-scan prompt upgrade

Ship first — validates the spec live before touching deep-scan's more complex pipeline.

### Task 5: Update fast-scan Agent A prompt

**Files:**
- Modify: `.claude/commands/archie-scan.md` — Agent A section (lines 147-188)

**Step 1: Replace Agent A's `Your job` and `Output` sections** with new content that references the spec. Keep `Your inputs` section unchanged.

New Agent A text (replaces from `**Your job:**` through `Save output: /tmp/archie_agent_a_arch.json`):

```markdown
**Your job:**

Emit findings per `.claude/commands/_shared/semantic_findings_spec.md` — follow the schema, severity rubric, and quality gate exactly. Your domain is **architecture and dependencies**. Produce two kinds of output:

1. **pattern_observations** (for Wave 2 or fast-scan synthesis to consume): raw cross-file anomalies in your domain — dep-graph magnets, cycles crossing layers, inverted dependencies, workspace-boundary violations. These are NOT finished findings; they're signals. Each observation: `{type, evidence_locations, note}`.

2. **findings** in your domain:
   - **Systemic** (category: systemic): `god_component`, `boundary_violation`. Each with ≥3 evidence locations, pattern_description, root_cause, fix_direction, blast_radius.
   - **Localized** (category: localized): `dependency_violation`, `cycle`, `pattern_divergence` (where the pattern is dependency-shaped). Each with a single location, root_cause, fix_direction.

All findings MUST carry `synthesis_depth: "draft"` and `source: "fast_agent_a"`.

Do NOT emit count caps. Emit every finding you can substantiate with concrete evidence. Drop any finding that can't pass the quality gate.

**Efficiency rule:** read skeletons.json + dep_graph.json first. Only Read source files when the skeleton is genuinely insufficient to judge.

**Output:** Write to `/tmp/archie_agent_a.json`:

\`\`\`json
{
  "pattern_observations": [{"type": "", "evidence_locations": [], "note": ""}],
  "findings": [
    /* See semantic_findings_spec.md for the full finding schema.
       Omit pattern_description for localized findings. */
  ]
}
\`\`\`
```

**Step 2: Rename the output temp file.** Old: `/tmp/archie_agent_a_arch.json`. New: `/tmp/archie_agent_a.json` (simpler, consistent). Update the `Save output:` line and any references later in the file.

**Step 3: Commit**

```bash
git add .claude/commands/archie-scan.md
git commit -m "feat(archie-scan): Agent A emits Semantic Findings schema via shared spec"
```

---

### Task 6: Update fast-scan Agent B prompt

**Files:**
- Modify: `.claude/commands/archie-scan.md` — Agent B section (lines 190-230)

**Step 1: Replace Agent B's `Your job` and `Output` sections.** Keep `Your inputs` unchanged. New text:

```markdown
**Your job:**

Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **health and complexity**. Produce:

1. **health_scores** (existing — preserve): a summary of erosion, gini, top20_share, verbosity, total_loc for the viewer's Health tab.

2. **trend**: direction + details, comparing against health_history.json. Unchanged shape.

3. **findings** in your domain:
   - **Localized**: `complexity_hotspot` for functions with CC ≥ 10 (severity per the spec's CC rubric: ≥50 error, 25-49 warn, 10-24 info), `abstraction_bypass` where a single-method class or tiny function obscures structure.
   - **Systemic** (only when substantiated): `trajectory_degradation` when ≥3 hotspots are all worsening over history, `missing_abstraction` when the same minimal helper is re-implemented in many places.

All findings MUST carry `synthesis_depth: "draft"` and `source: "fast_agent_b"`.

For each complexity_hotspot, `root_cause` must be mechanistic — NOT "high CC" but "conflates auth validation with request parsing". Use skeletons first; Read the source only when CC signature is insufficient.

**Output:** Write to `/tmp/archie_agent_b.json`:

\`\`\`json
{
  "health_scores": {"erosion": 0.31, "gini": 0.58, "top20_share": 0.72, "verbosity": 0.003, "total_loc": 9400},
  "trend": {"direction": "improving|degrading|stable", "details": "..."},
  "findings": [ /* per semantic_findings_spec.md */ ]
}
\`\`\`
```

**Step 2: Rename output temp file to `/tmp/archie_agent_b.json`.**

**Step 3: Commit**

```bash
git add .claude/commands/archie-scan.md
git commit -m "feat(archie-scan): Agent B emits complexity findings via shared spec"
```

---

### Task 7: Update fast-scan Agent C prompt

**Files:**
- Modify: `.claude/commands/archie-scan.md` — Agent C section (lines 232-293)

**Step 1: Replace Agent C's `Your job` and `Output` sections.** Keep `Your inputs` + workspace-aware addendum unchanged. New text:

```markdown
**Your job:**

Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is **rules, patterns, and duplication**. Produce:

1. **findings**:
   - **Systemic**: `fragmentation` (same job done N different ways — e.g., 5 handlers each implement auth differently), `missing_abstraction` (copy-paste without helper), `inconsistency` (feature built one way in component X and another way in component Y). Each with ≥3 evidence locations.
   - **Localized**: `pattern_divergence` (outlier that breaks a pattern 0.7+ confident), `semantic_duplication` (near-twin functions), `rule_violation` (code breaking an adopted rule from `.archie/rules.json`).

2. **proposed_rules** (existing — preserve): new rules discovered in this scan, per the existing rule schema with `{id, description, rationale, severity, confidence}`.

3. **rule_confidence_updates** (existing — preserve): adjustments to previously-proposed rule confidence.

All findings MUST carry `synthesis_depth: "draft"` and `source: "fast_agent_c"`.

Be honest about systemic vs localized: if ≥3 locations exhibit the same problem, it's systemic; a single outlier is localized.

**Output:** Write to `/tmp/archie_agent_c.json`:

\`\`\`json
{
  "findings": [ /* per semantic_findings_spec.md */ ],
  "proposed_rules": [{"id": "scan-NNN", "description": "...", "rationale": "...", "severity": "error|warn", "confidence": 0.85}],
  "rule_confidence_updates": [{"rule_id": "...", "old_confidence": 0.7, "new_confidence": 0.85, "reason": "..."}]
}
\`\`\`
```

**Step 2: Rename output temp file to `/tmp/archie_agent_c.json`.**

**Step 3: Commit**

```bash
git add .claude/commands/archie-scan.md
git commit -m "feat(archie-scan): Agent C emits systemic pattern findings via shared spec"
```

---

### Task 8: Update fast-scan Phase 4 to invoke the aggregator

**Files:**
- Modify: `.claude/commands/archie-scan.md` — Phase 4 (lines ~299+)

**Step 1: Add an invocation step** at the start of Phase 4, after the three agents complete:

```markdown
### 4a: Aggregate findings → semantic_findings.json

Before synthesizing the blueprint, extract the findings from each agent's output into per-source files in .archie/, then invoke the aggregator. This produces the unified `semantic_findings.json` consumed by the viewer and the next scan.

```bash
python3 .archie/extract_output.py findings /tmp/archie_agent_a.json "$PROJECT_ROOT/.archie/semantic_findings_fast_a.json"
python3 .archie/extract_output.py findings /tmp/archie_agent_b.json "$PROJECT_ROOT/.archie/semantic_findings_fast_b.json"
python3 .archie/extract_output.py findings /tmp/archie_agent_c.json "$PROJECT_ROOT/.archie/semantic_findings_fast_c.json"
python3 .archie/aggregate_findings.py "$PROJECT_ROOT"
```

The aggregator reads all `semantic_findings_*.json` files in `.archie/`, merges by signature, applies the quality gate, computes lifecycle_status against prior `semantic_findings.json`, and writes the canonical result.
```

**Step 2: Update existing Phase 4 synthesis instructions** to read `semantic_findings.json` (the aggregated file) alongside `/tmp/archie_agent_*.json` when evolving the blueprint.

**Step 3: Commit**

```bash
git add .claude/commands/archie-scan.md
git commit -m "feat(archie-scan): Phase 4 aggregates findings before blueprint synthesis"
```

---

### Task 9: Add `findings` extractor to `extract_output.py`

**Files:**
- Modify: `archie/standalone/extract_output.py` — add new subcommand

**Step 1: Check existing structure**

```bash
grep -n "def main\|argv\|sys.argv\|command ==" archie/standalone/extract_output.py | head -20
```

**Step 2: Add a `findings` subcommand** that reads an agent output JSON, extracts the `findings` array, and writes a bare `{"findings": [...]}` JSON to the output path. If the agent output has no `findings` key, write `{"findings": []}`.

```python
def extract_findings(input_path: str, output_path: str) -> None:
    import json, pathlib
    data = json.loads(pathlib.Path(input_path).read_text(encoding="utf-8"))
    findings = data.get("findings", []) if isinstance(data, dict) else []
    pathlib.Path(output_path).write_text(json.dumps({"findings": findings}, indent=2), encoding="utf-8")
```

Wire into the existing CLI dispatcher (look for how `deep-drift` / `recent-files` are wired and follow the same pattern).

**Step 3: Write a unit test**

```python
# tests/test_extract_findings.py
import json
from pathlib import Path
from archie.standalone import extract_output

def test_extract_findings_from_agent_output(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps({
        "findings": [{"type": "cycle"}, {"type": "fragmentation"}],
        "other_data": "ignored"
    }))
    extract_output.extract_findings(str(inp), str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": [{"type": "cycle"}, {"type": "fragmentation"}]}

def test_extract_findings_missing_key(tmp_path):
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    inp.write_text(json.dumps({"no_findings_here": True}))
    extract_output.extract_findings(str(inp), str(out))
    result = json.loads(out.read_text())
    assert result == {"findings": []}
```

**Step 4: Run tests, confirm pass**

```bash
python3 -m pytest tests/test_extract_findings.py -v
```

**Step 5: Sync to npm-package + commit**

```bash
cp archie/standalone/extract_output.py npm-package/assets/extract_output.py
python3 scripts/verify_sync.py
git add archie/standalone/extract_output.py npm-package/assets/extract_output.py tests/test_extract_findings.py
git commit -m "feat(extract-output): add findings subcommand"
```

---

### Task 10: Sync archie-scan.md to npm-package

**Files:**
- Copy: `.claude/commands/archie-scan.md` → `npm-package/assets/archie-scan.md`
- Copy: `.claude/commands/_shared/semantic_findings_spec.md` → `npm-package/assets/_shared/semantic_findings_spec.md`

**Step 1: Ensure `npm-package/assets/_shared/` exists** (check if scope_resolution.md is there; if so, directory exists).

```bash
ls npm-package/assets/_shared/ 2>/dev/null || mkdir -p npm-package/assets/_shared/
```

**Step 2: Copy files**

```bash
cp .claude/commands/archie-scan.md npm-package/assets/archie-scan.md
cp .claude/commands/_shared/semantic_findings_spec.md npm-package/assets/_shared/semantic_findings_spec.md
```

**Step 3: Run verifier**

```bash
python3 scripts/verify_sync.py
```

Expected: exit 0.

**Step 4: Commit**

```bash
git add -f npm-package/assets/archie-scan.md npm-package/assets/_shared/semantic_findings_spec.md
git commit -m "chore(npm): sync archie-scan + semantic_findings_spec to npm-package"
```

---

### Task 11: Validate fast-scan on a real project

**Files:** None modified — validation only.

**Step 1: Pick a test target.** Use `~/DEV/gbr/craft-agents-oss` if available; else any project that has `.archie/` with a prior blueprint.

**Step 2: Back up current `.archie/`**

```bash
cp -r ~/DEV/gbr/craft-agents-oss/.archie ~/DEV/gbr/craft-agents-oss/.archie.bak-pre-semantic
```

**Step 3: Re-install latest Archie into the target**

```bash
cd ~/DEV/gbr/craft-agents-oss
npx @bitraptors/archie .  # or equivalent local install path
```

**Step 4: Run `/archie-scan`** in Claude Code on the target project. Capture timing.

**Step 5: Inspect the outputs:**
- `.archie/semantic_findings.json` exists and has `findings` key with items
- Each finding has required fields (category, type, severity, scope, root_cause, fix_direction, synthesis_depth: draft, source starts with `fast_agent_`)
- `lifecycle_status` populated on each finding
- Systemic findings have `pattern_description`; localized omit it
- Systemic findings have ≥3 locations in `scope.locations`

**Step 6: Document any quality issues** as notes in this plan. If systemic count is unexpectedly 0 or the quality gate dropped too many, iterate on Agent prompts or spec file before proceeding.

**Step 7: Restore backup** only if validation reveals issues requiring a revert:

```bash
# ONLY if reverting is needed:
rm -rf ~/DEV/gbr/craft-agents-oss/.archie
mv ~/DEV/gbr/craft-agents-oss/.archie.bak-pre-semantic ~/DEV/gbr/craft-agents-oss/.archie
```

No commit — this is validation only.

---

## Phase C — Deep-scan Wave 1 upgrade

### Task 12: Upgrade Wave 1 Structure agent prompt

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — Structure agent section (lines 228-331)

**Step 1: Keep all existing content** (the "CRITICAL INSTRUCTIONS", DO/DO NOT, all 6 numbered sections about observation).

**Step 2: Append a new section** at the end of Structure agent's prompt, before the `Return JSON:` block:

```markdown
> ### 7. Pattern observations (for Wave 2 to synthesize)
> While reading the files, note raw anomalies in your domain. These are NOT finished findings — Wave 2 will contextualize them.
>
> For each observation: `{type, evidence_locations, note}`. Types in your domain: `dep_magnet`, `layer_cycle`, `inverted_dependency`, `workspace_boundary_crossed`, `high_fan_in_rising`.
>
> Example:
> \`\`\`json
> {"type": "dep_magnet", "evidence_locations": ["packages/shared"], "note": "fan-in 22 across auth/storage/UI/logging — unrelated domains"}
> \`\`\`
>
> ### 8. Localized findings (your domain)
> Emit findings per `.claude/commands/_shared/semantic_findings_spec.md`. Your domain is architecture and dependencies — emit only `dependency_violation` and `cycle` types as Localized findings. Do NOT emit systemic findings (those are Wave 2's job). All findings you emit carry `synthesis_depth: "draft"` and `source: "wave1_structure"`.
```

**Step 3: Update the `Return JSON` block** to include the new keys:

```json
{
  "meta": {...},  // existing
  "components": {...},  // existing
  "architecture_rules": {...},  // existing
  "pattern_observations": [{"type": "", "evidence_locations": [], "note": ""}],
  "findings": [ /* per spec */ ]
}
```

**Step 4: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(archie-deep-scan): Wave 1 Structure adds pattern_observations + localized findings"
```

---

### Task 13: Upgrade Wave 1 Patterns agent prompt

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — Patterns agent section (lines 333-412)

**Step 1: Keep all existing content** (sections 1-8 about structural/behavioral/cross-cutting patterns).

**Step 2: Append a new section** before the `Return JSON:` block:

```markdown
> ### 9. Pattern observations (for Wave 2 to synthesize)
> While cataloging patterns, note cross-file anomalies — things that feel inconsistent, fragmented, or missing an abstraction.
>
> For each: `{type, evidence_locations, note}`. Types in your domain: `fragmentation_signal` (same job done N ways), `missing_abstraction_signal` (copy-paste), `pattern_outlier` (1-2 files deviating from an otherwise-consistent pattern), `inconsistency_signal` (feature built one way in X, another in Y).
>
> These are observations for Wave 2, not finished findings.
```

**Step 3: Update `Return JSON` block** to include `pattern_observations`:

```json
{
  "communication": {...},  // existing
  "quick_reference": {...},  // existing
  "pattern_observations": [{"type": "", "evidence_locations": [], "note": ""}]
}
```

**Step 4: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(archie-deep-scan): Wave 1 Patterns adds pattern_observations"
```

---

### Task 14: Add Wave 1 findings persistence to Step 4

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — Step 4 "Save Wave 1 output and merge" (~line 606)

**Step 1: After Wave 1 agents complete and outputs are saved to `/tmp/archie_sub*_$PROJECT_NAME.json`, extract their `findings` arrays and concatenate into one file at `.archie/semantic_findings_wave1.json`:**

```markdown
After Wave 1 outputs are saved, extract findings:

```bash
# Extract findings from each Wave 1 agent output
python3 .archie/extract_output.py findings /tmp/archie_sub1_$PROJECT_NAME.json /tmp/_wave1_struct_f.json
python3 .archie/extract_output.py findings /tmp/archie_sub2_$PROJECT_NAME.json /tmp/_wave1_patt_f.json

# Concatenate findings into one file
python3 -c "
import json
from pathlib import Path
struct = json.loads(Path('/tmp/_wave1_struct_f.json').read_text())
patt = json.loads(Path('/tmp/_wave1_patt_f.json').read_text())
combined = {'findings': struct.get('findings', []) + patt.get('findings', [])}
Path('$PROJECT_ROOT/.archie/semantic_findings_wave1.json').write_text(json.dumps(combined, indent=2))
"
rm -f /tmp/_wave1_struct_f.json /tmp/_wave1_patt_f.json
```
```

**Step 2: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(archie-deep-scan): persist Wave 1 findings to semantic_findings_wave1.json"
```

---

## Phase D — Deep-scan Wave 2 upgrade + upgrade pass

### Task 15: Upgrade Wave 2 prompt — add new reads + canonical findings production

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — Step 5 Wave 2 (lines 650-761)

**Step 1: Update the "Read" directive** at line 689 to add the new inputs:

```markdown
> Read `$PROJECT_ROOT/.archie/blueprint_raw.json` — it contains the full analysis from Wave 1 agents. Also read:
> - `$PROJECT_ROOT/.archie/skeletons.json` — for cross-file pattern spotting
> - `$PROJECT_ROOT/.archie/health.json` — for contextual CC interpretation
> - `$PROJECT_ROOT/.archie/drift_report.json` — mechanical drift (produced by Step 9 Phase 1; SKIP this read on first-pass Wave 2; it will exist only on `--from 9` re-runs)
> - `$PROJECT_ROOT/.archie/semantic_findings.json` — prior scan's findings, for the upgrade pass (SKIP if file doesn't exist)
> - Key source files: entry points, main configs, core abstractions
```

**Step 2: After section "8. Implementation Guidelines", add a new section "9. Semantic Findings (canonical)":**

```markdown
> ### 9. Semantic Findings (canonical)
>
> Produce canonical-tier Semantic Findings per `.claude/commands/_shared/semantic_findings_spec.md`. You are the primary producer of systemic findings in deep-scan — the Wave 1 agents fed you `pattern_observations` (in `blueprint_raw.json`); your job is to synthesize those observations + the blueprint you just built + targeted code reads into substantiated findings.
>
> **Systemic findings you produce** (canonical depth — deep root_cause with history, sequenced fix_direction):
> - `fragmentation`, `god_component`, `split_brain`, `erosion`, `missing_abstraction`, `inconsistency`, `boundary_violation`, `responsibility_diffusion`, `trajectory_degradation`.
>
> **Localized findings you produce**:
> - `decision_violation` (code contradicting a key_decision)
> - `trade_off_undermined` (matching a `violation_signals` entry)
> - `pitfall_triggered` (matching a `stems_from` chain)
> - `responsibility_leak` (component doing another's work)
> - `abstraction_bypass` (reaching through a layer)
> - `complexity_hotspot` (when health.json CC warrants contextual interpretation beyond Agent B's shallow read)
>
> No count cap. Emit every finding you can substantiate. Quality gate: each systemic requires ≥3 evidence locations + mechanistic root_cause + actionable fix_direction.
>
> All findings you emit carry `synthesis_depth: "canonical"` and `source: "wave2"`.
>
> ### 10. Upgrade pass (for drafts from prior scans)
>
> If you read `.archie/semantic_findings.json` successfully, process the entries in it:
>
> - For each entry with `synthesis_depth: "draft"` AND `lifecycle_status: "recurring"` that is NOT already in your Step 9 output (check by `type + sorted(components_affected)` signature):
>   1. Re-evaluate with canonical-tier reasoning: does it still hold against the current blueprint + code?
>   2. If yes: enrich `root_cause` (make it mechanistic with history context) and `fix_direction` (sequence the steps; reference decisions). Flip `synthesis_depth` to `"canonical"`. Keep the same `id`.
>   3. If no longer substantiated: drop it (the aggregator will mark it `resolved` via diff).
>
> Emit upgraded drafts in the same findings list, with `source: "wave2"` but preserved `id`.
```

**Step 3: Update the `Return JSON` block** to include `findings`:

```json
{
  "decisions": {...},
  "pitfalls": [...],
  "architecture_diagram": "",
  "implementation_guidelines": [...],
  "findings": [ /* canonical systemic + localized + upgraded drafts */ ]
}
```

**Step 4: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(archie-deep-scan): Wave 2 produces canonical findings + upgrades drafts"
```

---

### Task 16: Persist Wave 2 findings to `.archie/semantic_findings_wave2.json`

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — Step 5 Save block (~line 766)

**Step 1: After the existing `Write /tmp/archie_sub_x_$PROJECT_NAME.json` line, add:**

```bash
python3 .archie/extract_output.py findings /tmp/archie_sub_x_$PROJECT_NAME.json "$PROJECT_ROOT/.archie/semantic_findings_wave2.json"
```

**Step 2: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(archie-deep-scan): persist Wave 2 findings to semantic_findings_wave2.json"
```

---

## Phase E — Shrunk Phase 2

### Task 17: Replace deep-scan Phase 2 with narrow agent

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — Step 9 Phase 2 (lines 998-1051)

**Step 1: Replace the entire Phase 2 section** (from `### Phase 2: Deep architectural drift (AI)` through the `python3 .archie/extract_output.py deep-drift` block) with:

```markdown
### Phase 2: Narrow findings agent (semantic_duplication + pattern_erosion)

Wave 1/2 already produced most findings as byproducts of their existing reads. Phase 2 covers only what they can't: function-level near-twin detection (requires cross-file scanning) and pattern erosion vs per-folder CLAUDE.md (requires Intent Layer output, only available here).

Identify files to analyze:
```bash
git -C "$PROJECT_ROOT" log --name-only --pretty=format: --since="30 days ago" -- '*.kt' '*.java' '*.swift' '*.ts' '*.tsx' '*.py' '*.go' '*.rs' | sort -u | head -100
```
Fallback if empty: use all source files from `python3 .archie/extract_output.py recent-files "$PROJECT_ROOT/.archie/scan.json"`.

Spawn a Sonnet subagent (`model: "sonnet"`) with:

> You are a narrow findings agent. Emit Semantic Findings per `.claude/commands/_shared/semantic_findings_spec.md`. You only produce two types:
>
> 1. **`semantic_duplication`** (localized) — functions in different files with different signatures but essentially the same logic. AI agents frequently copy-paste a function, tweak the name/parameters, and leave the body identical or near-identical. Scan `.archie/skeletons.json` for functions with similar names (e.g., `getText`/`getTexts`, `loadUser`/`fetchUser`, `formatDate` in multiple files). Read suspicious pairs to confirm. For each confirmed duplicate group, emit one finding with category: localized, type: semantic_duplication, 1 canonical location + evidence listing duplicates, fix_direction specifying which function should be shared.
>
> 2. **`pattern_erosion`** (localized) — code in a folder that violates the patterns documented in that folder's CLAUDE.md. Read the folder's CLAUDE.md (if it exists; skip silently if missing), then read the files in the folder that changed recently. If a file deviates from a documented pattern, emit category: localized, type: pattern_erosion, location: the specific file, root_cause: which pattern is violated and how, fix_direction: how to conform.
>
> Do NOT emit systemic findings — those are Wave 2's job. Do NOT emit dependency_violation, cycle, complexity_hotspot, decision_violation, etc. — those come from Wave 1/2.
>
> All findings you emit carry `synthesis_depth: "draft"` and `source: "phase2"`.
>
> Return JSON: `{"findings": [...]}`.

Save the findings:

```
Write /tmp/archie_phase2_findings.json with the agent's COMPLETE output text
```

```bash
python3 .archie/extract_output.py findings /tmp/archie_phase2_findings.json "$PROJECT_ROOT/.archie/semantic_findings_phase2.json"
rm -f /tmp/archie_phase2_findings.json
```
```

**Step 2: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(archie-deep-scan): shrink Phase 2 to narrow agent (semantic_dupe + pattern_erosion)"
```

---

## Phase F — Deep-scan aggregation + rendering

### Task 18: Invoke aggregator in deep-scan Step 9 Phase 3

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — Step 9 Phase 3 (line ~1053)

**Step 1: Replace the existing Phase 3 preamble** (which reads `drift_report.json` directly) with an invocation of the aggregator first:

```markdown
### Phase 3: Aggregate + present combined assessment

Invoke the aggregator to merge all findings sources with lifecycle + quality gate:

```bash
python3 .archie/aggregate_findings.py "$PROJECT_ROOT"
```

This reads:
- `.archie/semantic_findings_wave1.json` (Wave 1 Structure + Patterns findings)
- `.archie/semantic_findings_wave2.json` (Wave 2 canonical systemic + localized + upgraded drafts)
- `.archie/semantic_findings_phase2.json` (narrow agent: semantic_duplication + pattern_erosion)
- `.archie/drift_report.json` (mechanical findings from Phase 1)
- `.archie/semantic_findings.json` (prior scan's findings, for lifecycle diff — if exists)

...and writes the canonical merged output to `.archie/semantic_findings.json`.

Now read `.archie/blueprint.json` and `.archie/semantic_findings.json` for presentation (below).
```

**Step 2: Leave existing Part 1 / Part 2 / Part 3 sections** (generated artifacts, architecture summary, health assessment) largely as-is.

**Step 3: Replace Part 4 "Architectural Drift"** with a new "Semantic Findings" presentation section — see Task 19.

**Step 4: Commit**

```bash
git add .claude/commands/archie-deep-scan.md
git commit -m "feat(archie-deep-scan): Phase 3 invokes aggregate_findings before presentation"
```

---

### Task 19: New `scan_report.md` layout

**Files:**
- Modify: `.claude/commands/archie-deep-scan.md` — Step 9 Phase 4 (the scan_report.md write)

**Step 1: Replace the Phase 4 `scan_report.md` template** with the layout from the design doc's "Output — scan_report.md layout" section. Structure:

```markdown
# Scan Report — <repo>

## Executive Summary
Health score: X.XX (trend: ↑↓→)
Systemic findings: N (new: X, recurring: Y, worsening: Z, resolved: W)
Top 3 systemic by severity × blast_radius:
  1. [error] <type> — <component name> (blast: N)
  ...

## Systemic Findings (N)
[For each systemic finding, full expandable treatment per design doc]

## Localized Findings (M)
[Compact tables grouped by category: dependency_violation / complexity_hotspot / pattern_divergence / rule_violation / etc.]

## Resolved Findings (W)
[Compressed list, grouped by type]

## Mechanical Findings (p)
[Items where source: mechanical, compact format]
```

**Step 2: Replace Part 6 ("Semantic Duplication")** with a pointer into the unified Localized section (semantic_duplication is a type now, not a separate concern):

```markdown
#### Part 6: Semantic duplication
Now surfaced as `type: semantic_duplication` in the Localized Findings section. No longer a separate report part.
```

**Step 3: Update Part 5 ("Top Risks")** to read from the aggregated `semantic_findings.json` systemic section ordered by severity × blast_radius:

```markdown
#### Part 5: Top Risks & Recommendations
Read `.archie/semantic_findings.json`. List the top 3-5 systemic findings ranked by `severity` (error > warn > info) then `blast_radius` (descending). For each: type + component name + pattern_description (one sentence) + fix_direction (one sentence).
```

**Step 4: Apply the same layout to `/archie-scan`'s Phase 4** report-writing step. Fast-scan's `scan_report.md` has the same structure; only the data sources differ.

**Files:**
- Modify: `.claude/commands/archie-scan.md` — Phase 4 scan_report write

**Step 5: Commit**

```bash
git add .claude/commands/archie-deep-scan.md .claude/commands/archie-scan.md
git commit -m "feat(scan-report): unified layout — Systemic headline, Localized tables, Resolved, Mechanical"
```

---

## Phase G — `/archie-share` and `/archie-viewer`

### Task 20: Failing tests for upload.py bundle shape

**Files:**
- Create: `tests/test_upload_bundle.py`

**Step 1: Write tests verifying the new bundle shape.**

```python
import json
from pathlib import Path
from archie.standalone import upload

def _make_project(tmp_path: Path, files: dict) -> Path:
    archie = tmp_path / ".archie"
    archie.mkdir()
    for name, content in files.items():
        (archie / name).write_text(json.dumps(content) if not isinstance(content, str) else content)
    return tmp_path

def test_bundle_includes_bundle_version_v2(tmp_path):
    project = _make_project(tmp_path, {"blueprint.json": {"meta": {}}})
    bundle = upload.build_bundle(project / ".archie")
    assert bundle.get("bundle_version") == "v2"

def test_bundle_includes_semantic_findings_when_present(tmp_path):
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "semantic_findings.json": {"findings": [{"type": "cycle", "category": "localized"}]}
    })
    bundle = upload.build_bundle(project / ".archie")
    assert "semantic_findings" in bundle
    assert bundle["semantic_findings"]["findings"][0]["type"] == "cycle"

def test_bundle_omits_semantic_findings_when_absent(tmp_path):
    project = _make_project(tmp_path, {"blueprint.json": {"meta": {}}})
    bundle = upload.build_bundle(project / ".archie")
    assert "semantic_findings" not in bundle

def test_bundle_still_includes_legacy_scan_report(tmp_path):
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "scan_report.md": "# legacy report"
    })
    bundle = upload.build_bundle(project / ".archie")
    assert bundle.get("scan_report") == "# legacy report"

def test_bundle_omits_wave_intermediates(tmp_path):
    """Internal wave1/wave2/phase2 files must NOT leak into the bundle."""
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "semantic_findings_wave1.json": {"findings": []},
        "semantic_findings_wave2.json": {"findings": []},
        "semantic_findings_phase2.json": {"findings": []},
    })
    bundle = upload.build_bundle(project / ".archie")
    assert "semantic_findings_wave1" not in bundle
    assert "semantic_findings_wave2" not in bundle
    assert "semantic_findings_phase2" not in bundle

def test_bundle_omits_drift_report_when_semantic_findings_present(tmp_path):
    """drift_report.json is folded into semantic_findings.json; don't duplicate."""
    project = _make_project(tmp_path, {
        "blueprint.json": {"meta": {}},
        "semantic_findings.json": {"findings": []},
        "drift_report.json": {"mechanical": []}
    })
    bundle = upload.build_bundle(project / ".archie")
    assert "drift_report" not in bundle
```

**Step 2: Check the current upload.py exported function name** — the tests assume `upload.build_bundle(archie_dir)`. If the function has a different name, rename in tests to match.

```bash
grep -n "^def \|def build\|def collect\|def bundle" archie/standalone/upload.py
```

**Step 3: Run tests, confirm failures**

```bash
python3 -m pytest tests/test_upload_bundle.py -v
```

Expected: tests fail (bundle_version key missing, semantic_findings logic not present).

**Step 4: Commit failing tests**

```bash
git add tests/test_upload_bundle.py
git commit -m "test(upload): failing tests for bundle_version v2 + semantic_findings"
```

---

### Task 21: Update upload.py to implement v2 bundle

**Files:**
- Modify: `archie/standalone/upload.py`

**Step 1: Find the existing `build_bundle` function (or equivalent).**

```bash
grep -n "^def " archie/standalone/upload.py
```

**Step 2: In the function that builds the bundle dict (starts at line 125 in current code), add:**

```python
# After all existing field population, before `return bundle`:
bundle["bundle_version"] = "v2"

semantic_findings = _read_json(archie_dir / "semantic_findings.json")
if semantic_findings:
    bundle["semantic_findings"] = semantic_findings
    # When semantic_findings exists, drift_report is redundant (folded in).
    # Keep scan_report (legacy viewer fallback).
```

**Step 3: If the existing code also unconditionally reads `drift_report.json` into the bundle, add a guard** — skip it when `semantic_findings.json` is present.

**Step 4: Run tests, confirm pass**

```bash
python3 -m pytest tests/test_upload_bundle.py -v
```

Expected: all 6 tests pass.

**Step 5: Sync to npm-package and commit**

```bash
cp archie/standalone/upload.py npm-package/assets/upload.py
python3 scripts/verify_sync.py
git add archie/standalone/upload.py npm-package/assets/upload.py
git commit -m "feat(share): upload.py emits bundle_version v2 with semantic_findings"
```

---

### Task 22: Add `/api/semantic-findings` endpoint to viewer.py

**Files:**
- Modify: `archie/standalone/viewer.py` — HTTP handler

**Step 1: Find the existing `/api/drift` handler** (seen at line 170-171).

```bash
grep -n "elif path ==" archie/standalone/viewer.py | head -30
```

**Step 2: Add a new handler immediately after `/api/drift`:**

```python
        elif path == "/api/semantic-findings":
            self._send_json(_load_json(archie_dir / "semantic_findings.json"))
```

**Step 3: Find the JS fetchJSON block** where `/api/drift` is consumed (around line 396).

**Step 4: Add `/api/semantic-findings` to the parallel fetchJSON block, and destructure it:**

```javascript
Promise.all([
    fetchJSON('/api/blueprint'),
    // ... existing
    fetchJSON('/api/drift'),
    fetchJSON('/api/semantic-findings'),  // NEW
    // ... existing
]).then(([blueprint, /* existing */, drift, semanticFindings /* NEW */, /* existing */]) => {
    // ...
    window.semanticFindings = semanticFindings || {findings: []};  // expose to renderers
});
```

**Step 5: Start the viewer manually and confirm the endpoint returns data**

```bash
cd /tmp && mkdir -p vtest/.archie && echo '{"findings": [{"type": "cycle"}]}' > vtest/.archie/semantic_findings.json
python3 /Users/hamutarto/DEV/BitRaptors/Archie/archie/standalone/viewer.py /tmp/vtest &
VIEWER_PID=$!
sleep 2
curl -s http://localhost:8080/api/semantic-findings
kill $VIEWER_PID
rm -rf /tmp/vtest
```

Expected: JSON response containing the finding.

**Step 6: Commit**

```bash
git add archie/standalone/viewer.py
git commit -m "feat(viewer): add /api/semantic-findings endpoint"
```

---

### Task 23: Render Semantic Findings panel in viewer

**Files:**
- Modify: `archie/standalone/viewer.py` — embedded JS/HTML rendering

**Step 1: Find where the "Drift Findings" panel is rendered** (around line 581-625).

**Step 2: Add a new renderer function BEFORE the drift panel renderer.** It branches: if `window.semanticFindings.findings` is non-empty, render the Semantic Findings panel and SKIP the legacy drift panel. If empty or `semantic_findings.json` missing, render the legacy drift panel as fallback.

```javascript
function renderSemanticFindings(sfData) {
  const findings = (sfData && sfData.findings) || [];
  if (findings.length === 0) return null;  // fallback to legacy drift panel

  const systemic = findings.filter(f => f.category === 'systemic');
  const localized = findings.filter(f => f.category === 'localized');
  const resolved = findings.filter(f => f.lifecycle_status === 'resolved');
  const mechanical = findings.filter(f => f.source === 'mechanical');

  let html = '<div class="semantic-findings-panel">';

  // Systemic section — headline cards
  html += `<div class="text-sm font-bold text-ink mb-4">Semantic Findings — Systemic (${systemic.length})</div>`;
  systemic.sort((a, b) => {
    const sev = {error: 3, warn: 2, info: 1};
    return (sev[b.severity] - sev[a.severity]) || ((b.blast_radius||0) - (a.blast_radius||0));
  });
  systemic.forEach(f => {
    html += renderSystemicCard(f);
  });

  // Localized section — compact tables by type
  html += `<div class="text-sm font-bold text-ink mt-6 mb-4">Localized (${localized.length})</div>`;
  const byType = groupBy(localized.filter(f => f.lifecycle_status !== 'resolved'), 'type');
  Object.keys(byType).sort().forEach(type => {
    html += renderLocalizedTable(type, byType[type]);
  });

  // Resolved — collapsed list
  if (resolved.length > 0) {
    html += `<details class="mt-6"><summary class="text-sm font-bold">Resolved (${resolved.length})</summary>`;
    html += '<ul class="text-xs text-ink/60 mt-2">';
    resolved.forEach(f => html += `<li>${f.type} — ${(f.scope && f.scope.components_affected || []).join(', ')}</li>`);
    html += '</ul></details>';
  }

  html += '</div>';
  return html;
}

function renderSystemicCard(f) {
  const sevColor = {error: '#d62828', warn: '#fb8500', info: '#808080'}[f.severity] || '#808080';
  const lifecycleBadge = (f.lifecycle_status || '').toUpperCase();
  const depthBadge = f.synthesis_depth === 'draft'
    ? '<span class="px-2 py-0.5 rounded border border-dashed text-xs">provisional</span>'
    : '';
  return `
    <details class="mb-4 border-l-4 pl-4" style="border-color: ${sevColor}">
      <summary class="cursor-pointer font-semibold">
        [${f.severity} · ${lifecycleBadge}] ${f.type} — ${(f.scope && f.scope.components_affected || []).join(', ')}
        ${depthBadge}
      </summary>
      <div class="mt-2 text-sm">
        <p><strong>Pattern:</strong> ${escape(f.pattern_description || '')}</p>
        <p><strong>Evidence:</strong></p>
        <ul class="ml-4 text-xs">
          ${(f.scope && f.scope.locations || []).map(l => `<li>${escape(l)}</li>`).join('')}
        </ul>
        <p><strong>Root cause:</strong> ${escape(f.root_cause || '')}</p>
        <p><strong>Fix direction:</strong> ${escape(f.fix_direction || '')}</p>
        <p><strong>Blast radius:</strong> ${f.blast_radius || 0}${f.blast_radius_delta ? ` (Δ ${f.blast_radius_delta > 0 ? '+' : ''}${f.blast_radius_delta})` : ''}</p>
        ${f.blueprint_anchor ? `<p><strong>Blueprint:</strong> <code>${escape(f.blueprint_anchor)}</code></p>` : ''}
      </div>
    </details>
  `;
}

function renderLocalizedTable(type, items) {
  let html = `<div class="mb-3"><div class="text-xs font-semibold">${type} (${items.length})</div><table class="text-xs w-full"><thead><tr><th>Sev</th><th>Location</th><th>Evidence</th><th>Fix</th></tr></thead><tbody>`;
  items.forEach(f => {
    const loc = (f.scope && f.scope.locations || [])[0] || '';
    html += `<tr><td>${f.severity}</td><td><code>${escape(loc)}</code></td><td>${escape(f.evidence || '')}</td><td>${escape(f.fix_direction || '')}</td></tr>`;
  });
  html += '</tbody></table></div>';
  return html;
}

function groupBy(arr, key) {
  return arr.reduce((acc, item) => { (acc[item[key]] = acc[item[key]] || []).push(item); return acc; }, {});
}

function escape(s) { return String(s).replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c])); }
```

**Step 3: In the existing tab rendering code** (near line 581), replace the drift-panel invocation with a guarded call:

```javascript
const semanticHTML = renderSemanticFindings(window.semanticFindings);
if (semanticHTML) {
  // Render Semantic Findings panel (new)
  panelHTML += semanticHTML;
} else {
  // Fallback: legacy Drift Findings panel (unchanged code below)
  // ... existing drift panel code ...
}
```

**Step 4: Manually launch the viewer on a project with `semantic_findings.json`** and confirm rendering.

**Step 5: Commit**

```bash
git add archie/standalone/viewer.py
git commit -m "feat(viewer): Semantic Findings panel (systemic cards + localized tables + resolved)"
```

---

### Task 24: Sync viewer.py to npm-package

**Files:**
- Copy: `archie/standalone/viewer.py` → `npm-package/assets/viewer.py`

**Step 1: Copy and verify**

```bash
cp archie/standalone/viewer.py npm-package/assets/viewer.py
python3 scripts/verify_sync.py
```

**Step 2: Commit**

```bash
git add npm-package/assets/viewer.py
git commit -m "chore(npm): sync viewer.py"
```

---

## Phase H — Deep-scan sync + end-to-end validation

### Task 25: Sync archie-deep-scan.md and all assets to npm-package

**Files:**
- Copy: `.claude/commands/archie-deep-scan.md` → `npm-package/assets/archie-deep-scan.md`

**Step 1: Copy and verify sync**

```bash
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
python3 scripts/verify_sync.py
```

Expected: exit 0.

**Step 2: Commit**

```bash
git add -f npm-package/assets/archie-deep-scan.md
git commit -m "chore(npm): sync archie-deep-scan after semantic findings upgrade"
```

---

### Task 26: End-to-end validation on craft-agents-oss

**Files:** None modified — validation only.

**Step 1: Back up the target's `.archie/`**

```bash
cp -r ~/DEV/gbr/craft-agents-oss/.archie ~/DEV/gbr/craft-agents-oss/.archie.bak-e2e
```

**Step 2: Re-install latest Archie**

```bash
cd ~/DEV/gbr/craft-agents-oss && npx @bitraptors/archie .  # or local npm-pack equivalent
```

**Step 3: Run `/archie-deep-scan --from 9`** (reuses existing blueprint; just re-does findings).

**Step 4: Inspect outputs:**
- `.archie/semantic_findings.json` — has findings with both `synthesis_depth: canonical` (from Wave 2) AND `synthesis_depth: draft` (from Phase 2).
- `.archie/semantic_findings_wave2.json` — exists, contains canonical systemic findings.
- `.archie/semantic_findings_phase2.json` — exists, contains semantic_duplication + pattern_erosion only.
- `.archie/scan_report.md` — new layout: Executive Summary → Systemic → Localized → Resolved → Mechanical.
- Wave 2 upgrade pass: any previously-stored drafts (from a prior fast-scan) are now `synthesis_depth: canonical`.

**Step 5: Run `/archie-scan`** immediately after, and confirm:
- Fast-scan produces additional draft findings (if anything changed).
- Diff `.archie/semantic_findings.json` between deep-scan and fast-scan runs: lifecycle_status correctly tagged for recurring items.

**Step 6: Open the viewer**

```bash
python3 ~/DEV/gbr/craft-agents-oss/.archie/viewer.py ~/DEV/gbr/craft-agents-oss
```

Confirm:
- Semantic Findings panel renders.
- Systemic findings appear first as headline cards.
- Localized findings in compact tables.
- Resolved in collapsed section.

**Step 7: Test share flow**

```bash
cd ~/DEV/gbr/craft-agents-oss && python3 .archie/upload.py .
```

Capture the returned URL. Open it; confirm the hosted viewer renders (will use legacy panel until hosted viewer ships v2 rendering — Task 27 note).

**Step 8: Document findings.** Write validation results into a short section at the bottom of `docs/plans/2026-04-16-semantic-findings.md` titled `## Validation results`, including counts (systemic/localized/resolved), any quality gate drops, any anomalies.

**Step 9: Restore the backup ONLY if a revert is needed.** If all looks good, delete the backup:

```bash
rm -rf ~/DEV/gbr/craft-agents-oss/.archie.bak-e2e
```

No commit for validation; commit only if the plan doc is updated with results.

---

### Task 27: Hosted viewer deployment note

**Files:**
- Modify: `docs/plans/2026-04-16-semantic-findings.md` — add deployment note

**Step 1: Append a `## Deployment` section to this plan file:**

```markdown
## Deployment — hosted viewer

The hosted viewer code (same `viewer.py`, served behind Supabase-linked URL) must ship BEFORE any `bundle_version: v2` bundle is shared publicly. Sequence:

1. Deploy the updated `viewer.py` to the hosted environment (ops/infra task — outside this plan's scope).
2. Verify the hosted viewer handles both v1 bundles (legacy path: reads `scan_report` markdown, old `drift` panel) and v2 bundles (new path: reads `semantic_findings`).
3. Only after hosted viewer is live, release the npm package version that includes the new `upload.py` with `bundle_version: "v2"`.

Until step 3 is complete, users on the new npm version who share bundles will get the legacy render on the hosted side. This degrades gracefully — no data loss, just less-rich UI on old deployments.
```

**Step 2: Commit**

```bash
git add docs/plans/2026-04-16-semantic-findings.md
git commit -m "docs(plan): hosted viewer deployment ordering note"
```

---

### Task 28: Supersede `docs/SCAN_CONSOLIDATION.md`

**Files:**
- Modify: `docs/SCAN_CONSOLIDATION.md` — add supersession notice at top

**Step 1: Prepend a notice** to the existing `docs/SCAN_CONSOLIDATION.md`:

```markdown
> **⚠️ Superseded.** This plan has been replaced by `docs/plans/2026-04-16-semantic-findings-design.md`. The "triple-the-Phase-2-agent-count" approach described below was reconsidered — it would have *added* codebase reads; the new design harvests findings from existing Wave 1/2 reads. See the design doc for the current direction.
>
> Kept here for history.

---

# (original content below)
```

**Step 2: Commit**

```bash
git add docs/SCAN_CONSOLIDATION.md
git commit -m "docs: mark SCAN_CONSOLIDATION.md superseded by semantic-findings-design"
```

---

### Task 29: Verify all syncs + final pass

**Files:** None modified — verification.

**Step 1: Run sync verifier one last time**

```bash
python3 scripts/verify_sync.py
```

Expected: exit 0. If any drift, resolve before merging.

**Step 2: Run full test suite**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass (the new tests + all existing ones).

**Step 3: Review the branch**

```bash
git log --oneline docs/scan-consolidation ^main
git diff main...docs/scan-consolidation --stat
```

Confirm the commit chain tells a coherent story: design → foundation → fast-scan → Wave 1 → Wave 2 → Phase 2 → rendering → share/viewer → validation.

**Step 4: Open PR**

```bash
gh pr create --title "Semantic Findings — unified findings across /archie-scan and /archie-deep-scan" --body "$(cat <<'EOF'
## Summary
- Unifies /archie-scan and /archie-deep-scan findings under one "Semantic Findings" schema with systemic + localized tiers
- Shared calibration via `.claude/commands/_shared/semantic_findings_spec.md` — single source of truth for schema, severity rubric, quality gate
- New `aggregate_findings.py` merges wave1/wave2/phase2/mechanical with lifecycle (new/recurring/resolved/worsening) and quality gate
- Wave 2 produces canonical-tier findings AND upgrades stored drafts on each deep-scan run
- Shrunk Phase 2: was 1 broad agent, now 1 narrow agent covering only semantic_duplication + pattern_erosion
- `upload.py` + `viewer.py` updated with `bundle_version` branching for backward compat
- Supersedes `docs/SCAN_CONSOLIDATION.md`

## Test plan
- [ ] `python3 -m pytest tests/` passes
- [ ] `python3 scripts/verify_sync.py` passes
- [ ] `/archie-deep-scan --from 9` on craft-agents-oss produces semantic_findings.json with both canonical and draft entries
- [ ] `/archie-scan` on craft-agents-oss produces draft-only findings and diffs correctly (lifecycle_status) against prior
- [ ] Local viewer renders Semantic Findings panel (systemic cards + localized tables + resolved)
- [ ] `/archie-share` upload returns a URL; hosted viewer renders legacy panel (expected until hosted viewer ships v2 support)
- [ ] `bundle_version: "v2"` present in fresh upload bundle

See `docs/plans/2026-04-16-semantic-findings-design.md` for the full design rationale.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Verification checklist

- [ ] `.claude/commands/_shared/semantic_findings_spec.md` exists with schema + severity rubric + quality gate + taxonomy + synthesis_depth + no-count-caps directive
- [ ] `archie/standalone/aggregate_findings.py` exists with `finding_signature`, `apply_quality_gate`, `compute_lifecycle`, `merge_sources`, `main`
- [ ] `tests/test_aggregate_findings.py` passes
- [ ] `tests/test_upload_bundle.py` passes
- [ ] `tests/test_extract_findings.py` passes
- [ ] Fast-scan Agent A/B/C prompts reference the shared spec and emit the new schema
- [ ] Deep-scan Wave 1 Structure + Patterns emit `pattern_observations` and localized findings
- [ ] Deep-scan Wave 2 emits canonical systemic + localized findings and performs the upgrade pass on stored drafts
- [ ] Deep-scan Step 9 Phase 2 is shrunk — only `semantic_duplication` + `pattern_erosion`
- [ ] Deep-scan Step 9 Phase 3 invokes `aggregate_findings.py`
- [ ] `scan_report.md` layout: Executive Summary → Systemic → Localized → Resolved → Mechanical
- [ ] `upload.py` emits `bundle_version: "v2"` and includes `semantic_findings`; excludes wave/phase intermediates and `drift_report` when `semantic_findings` present
- [ ] `viewer.py` has `/api/semantic-findings` endpoint and Semantic Findings panel (systemic cards + localized tables + resolved)
- [ ] Legacy Drift Findings panel still renders when `semantic_findings.json` is absent
- [ ] `docs/SCAN_CONSOLIDATION.md` marked superseded
- [ ] All npm-package syncs via `scripts/verify_sync.py`
- [ ] End-to-end run on craft-agents-oss produces expected outputs

---

## Files summary

| Status | File | Purpose |
|---|---|---|
| New | `.claude/commands/_shared/semantic_findings_spec.md` | Single source of truth for schema + calibration |
| New | `archie/standalone/aggregate_findings.py` | Merge + quality gate + lifecycle |
| New | `tests/test_aggregate_findings.py` | Aggregator unit tests |
| New | `tests/test_upload_bundle.py` | Upload bundle shape tests |
| New | `tests/test_extract_findings.py` | Findings extractor tests |
| New | `docs/plans/2026-04-16-semantic-findings-design.md` | Design doc (already committed) |
| New | `docs/plans/2026-04-16-semantic-findings.md` | This plan |
| Modified | `.claude/commands/archie-scan.md` | Three agents use shared spec + new schema; Phase 4 aggregates |
| Modified | `.claude/commands/archie-deep-scan.md` | Wave 1/2 emit findings; Phase 2 shrunk; Phase 3 aggregates; Phase 4 new layout |
| Modified | `archie/standalone/extract_output.py` | New `findings` subcommand |
| Modified | `archie/standalone/upload.py` | `bundle_version: v2`, includes `semantic_findings` |
| Modified | `archie/standalone/viewer.py` | `/api/semantic-findings` + new panel; legacy panel as fallback |
| Modified | `docs/SCAN_CONSOLIDATION.md` | Superseded notice |
| Synced | `npm-package/assets/*` | Mirror canonical |

## Risks and mitigations

- **Prompt drift between spec and inlined text.** Mitigation: follow-up script in `scripts/verify_shared_prompts.py` (out of scope for this plan). For now, convention: never inline calibration, always reference spec by path.
- **Wave 2 output size bloat.** Opus output grows — canonical findings + upgrade pass. Mitigation: upgrade pass capped at recurring drafts only; resolved drafts dropped before Wave 2 sees them.
- **Inflation despite quality gate.** Mitigation: spec file includes good-vs-bad examples for `root_cause`, `pattern_description`, `fix_direction`. Aggregator's `apply_quality_gate` enforces field presence.
- **Hosted viewer deploy lag.** Mitigation: Task 27 makes the ordering explicit — deploy hosted viewer first, bump npm version second.

## Out of scope

- Project-configurable severity thresholds (follow-up).
- `scripts/verify_shared_prompts.py` drift checker (follow-up).
- Viewer blast-radius visualization graphics (follow-up).
- Auto-rule proposal from systemic findings (follow-up).

# Archie Delivery Review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a delivery-review capability that reconciles intent (ticket/prompt), blueprint (invariants/decisions), and the diff+code into evidence-backed findings, surfaced across deep-scan, sync, and the PR gate.

**Architecture:** One shared review core (evidence schema · diff basis · blueprint selector · editor gate) plus a blueprint-free behavioral engine and an intent resolver. Three surfaces call the core: deep-scan (whole-repo cold read, edge B only), sync (continuous light reconciliation), PR gate (full A/B/C reconciliation + delivery verdict). All findings land in one store (`.archie/findings.json`) through one editor gate.

**Tech Stack:** Zero-dependency Python 3.9+ stdlib. LLM calls via the existing `agent_cli.run_verifier` (local/hooks, `--model haiku`) and `intent_review.call_anthropic` (GitHub Action). Tests: pytest, mocking the LLM seam exactly as the existing suite does.

## Global Constraints

- **Zero runtime dependencies** beyond Python 3.9+ stdlib (copy verbatim from `CLAUDE.md`).
- **File sync:** edit `archie/standalone/*.py` first, then copy to `npm-package/assets/*.py`; edit `.claude/commands/*.md` first, then copy to `npm-package/assets/`. Run `python3 scripts/verify_sync.py` before every commit.
- **Finding schema is additive-only:** the existing fields (`id`, `problem_statement`, `evidence`, `triggering_call_site`, `root_cause`, `applies_to`, `first_seen`, `confirmed_in_scan`, `status`, `verdict_history`, `last_verdict_reason`, `last_verdict_confidence`, `pending_demotion`, `pending_promotion`, `demoted_at`, `dropped_at`) must remain untouched. New fields are added alongside, never renamed.
- **Editor gate cannot invent findings** — it may only drop / merge / suppress / rewrite copy, never add a finding no producer emitted.
- **Advisory kinds never auto-fold** — the `_CONTRACT_SECTIONS`/`_CONTRACT_FILES` guards in `sync.py` stay authoritative; delivery review is read-only against the contract.
- **Vocabulary:** use `falsification` (never "disproof"), `evidence schema` (never "proof schema"), `contract → tracer → challenger` (never "planner/worker/reviewer"). See `docs/archie-delivery-review-design.md` §11.
- **Never port** the peer system's business-specific specialists.
- **LLM model default:** `haiku` for selection/normalization, `sonnet` for reasoning, `opus` for the two gates; local calls go through `run_verifier`, which already sets `--model`.
- **Import convention (CRITICAL — overrides the `import archie.standalone.X` lines shown in task code blocks below).** The only interpreter is `python3` (3.9.6); `archie/__init__.py` imports `tomllib` (3.11+), so importing via the `archie` package breaks collection on 3.9. Follow the repo convention instead:
  - **Test files:** add the standalone dir to `sys.path`, then import by bare name —
    ```python
    import sys
    from pathlib import Path
    _STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
    sys.path.insert(0, str(_STANDALONE))
    import <module> as <alias>  # noqa: E402
    ```
  - **Implementation files importing sibling standalone modules:** at the top, `sys.path.insert(0, str(Path(__file__).parent))` then `from <sibling> import <name>` (bare module name — e.g. `from agent_cli import run_verifier`, `from evidence_schema import make_finding`), never `from archie.standalone.<sibling> import ...`. This matches `arch_review.py`/`verify_findings.py`.
  - Run tests with `python3 -m pytest` (there is no `python` on PATH).

---

## Phase 1 — Shared Core

### Task 1: Evidence schema + finding builder

**Files:**
- Create: `archie/standalone/evidence_schema.py`
- Test: `tests/test_evidence_schema.py`

**Interfaces:**
- Produces: `EVIDENCE_FIELDS: tuple[str, ...]`; `make_finding(*, id, kind, edge, problem_statement, anchor, assumptions, evidence, falsification, confidence, source, severity_class) -> dict`; `has_evidence_fields(finding: dict) -> bool`; `clamp_confidence(finding: dict, ceiling: float) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evidence_schema.py
import archie.standalone.evidence_schema as es

def test_make_finding_carries_all_fields():
    f = es.make_finding(
        id="f_1", kind="behavioral_break", edge="B",
        problem_statement="null deref on export path",
        anchor={"file": "export.py", "line": 44, "changed": True},
        assumptions=["field may be None"], evidence=["export.py:44 dereferences x"],
        falsification="a guard exists upstream of export.py:44",
        confidence=0.7, source="behavioral", severity_class="pitfall_triggered",
    )
    assert es.has_evidence_fields(f)
    assert f["falsification"] and f["anchor"]["changed"] is True

def test_clamp_confidence_caps_but_never_raises():
    f = es.make_finding(id="f_2", kind="intent_unmet", edge="A",
        problem_statement="p", anchor={"file": "a.py", "line": 1, "changed": True},
        assumptions=[], evidence=["e"], falsification="fx",
        confidence=0.9, source="reconcile:edgeA", severity_class="pattern_divergence")
    assert es.clamp_confidence(f, 0.5)["confidence"] == 0.5
    assert es.clamp_confidence(f, 0.99)["confidence"] == 0.9

def test_has_evidence_fields_false_when_missing_falsification():
    assert es.has_evidence_fields({"id": "x", "anchor": {}, "evidence": []}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_evidence_schema.py -v`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError: make_finding`.

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/evidence_schema.py
"""Evidence schema: the single finding shape every producer emits.

Additive over the legacy finding dict — legacy fields (problem_statement,
triggering_call_site, ...) are preserved; these fields are added alongside.
Zero dependencies beyond the Python 3.9+ stdlib.
"""
from __future__ import annotations

EVIDENCE_FIELDS = ("kind", "edge", "anchor", "assumptions", "falsification", "confidence")

def make_finding(*, id, kind, edge, problem_statement, anchor, assumptions,
                 evidence, falsification, confidence, source, severity_class) -> dict:
    return {
        "id": id,
        "kind": kind,
        "edge": edge,
        "problem_statement": problem_statement,
        # keep the legacy anchor mirror so verify_findings can still read a call site
        "triggering_call_site": f'{anchor.get("file","")}:{anchor.get("line","")}',
        "anchor": dict(anchor),
        "assumptions": list(assumptions),
        "evidence": list(evidence),
        "falsification": falsification,
        "confidence": float(confidence),
        "source": source,
        "severity_class": severity_class,
        "applies_to": [anchor.get("file", "")],
    }

def has_evidence_fields(finding: dict) -> bool:
    if not all(k in finding for k in EVIDENCE_FIELDS):
        return False
    return bool(finding.get("falsification")) and bool(finding.get("anchor"))

def clamp_confidence(finding: dict, ceiling: float) -> dict:
    out = dict(finding)
    out["confidence"] = min(float(finding.get("confidence", 0.0)), float(ceiling))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_evidence_schema.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/evidence_schema.py npm-package/assets/evidence_schema.py
python3 scripts/verify_sync.py
git add archie/standalone/evidence_schema.py npm-package/assets/evidence_schema.py tests/test_evidence_schema.py
git commit -m "feat(review): evidence schema + finding builder"
```

---

### Task 2: Diff basis (base-detection ladder + merge-base diff)

**Files:**
- Create: `archie/standalone/diff_basis.py`
- Test: `tests/test_diff_basis.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `detect_base(root: Path, explicit: str | None = None, run=subprocess.run) -> str`; `changed_files(root: Path, base: str, run=subprocess.run) -> list[str]`. The `run` parameter is injected so tests never shell out.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_diff_basis.py
from pathlib import Path
import archie.standalone.diff_basis as db

class FakeRun:
    def __init__(self, table): self.table = table
    def __call__(self, argv, **kw):
        key = " ".join(argv)
        class R: pass
        r = R(); out = self.table.get(key, ("", 1))
        r.stdout, r.returncode = out[0], out[1]; r.stderr = ""
        return r

def test_detect_base_prefers_explicit():
    assert db.detect_base(Path("/x"), explicit="develop", run=FakeRun({})) == "develop"

def test_detect_base_uses_gh_pr_view():
    run = FakeRun({"gh pr view --json baseRefName -q .baseRefName": ("main\n", 0)})
    assert db.detect_base(Path("/x"), run=run) == "main"

def test_detect_base_falls_back_to_main():
    assert db.detect_base(Path("/x"), run=FakeRun({})) == "main"

def test_changed_files_uses_merge_base():
    run = FakeRun({
        "git -C /x merge-base HEAD main": ("abc123\n", 0),
        "git -C /x diff --name-only abc123": ("a.py\nb.py\n", 0),
    })
    assert db.changed_files(Path("/x"), "main", run=run) == ["a.py", "b.py"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_diff_basis.py -v`
Expected: FAIL (`AttributeError: detect_base`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/diff_basis.py
"""Diff basis: pick the base ref and list branch-introduced files.

Mirrors the well-known local ladder: --base -> gh pr view -> git remote HEAD ->
main. `run` is injectable so the ladder is unit-testable without git.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

def _out(run, argv):
    try:
        r = run(argv, capture_output=True, text=True)
        return (r.stdout or "").strip(), r.returncode
    except Exception:
        return "", 1

def detect_base(root: Path, explicit: str | None = None, run=subprocess.run) -> str:
    if explicit:
        return explicit
    out, code = _out(run, ["gh", "pr", "view", "--json", "baseRefName", "-q", ".baseRefName"])
    if code == 0 and out:
        return out
    out, code = _out(run, ["git", "-C", str(root), "symbolic-ref", "refs/remotes/origin/HEAD"])
    if code == 0 and out:
        return out.rsplit("/", 1)[-1]
    return "main"

def changed_files(root: Path, base: str, run=subprocess.run) -> list[str]:
    mb, code = _out(run, ["git", "-C", str(root), "merge-base", "HEAD", base])
    ref = mb if code == 0 and mb else base
    out, code = _out(run, ["git", "-C", str(root), "diff", "--name-only", ref])
    return [ln for ln in out.splitlines() if ln.strip()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_diff_basis.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/diff_basis.py npm-package/assets/diff_basis.py
python3 scripts/verify_sync.py
git add archie/standalone/diff_basis.py npm-package/assets/diff_basis.py tests/test_diff_basis.py
git commit -m "feat(review): diff-basis base-detection ladder"
```

---

### Task 3: Blueprint selector (deterministic specialist router)

**Files:**
- Create: `archie/standalone/selector.py`
- Test: `tests/test_selector.py`

**Interfaces:**
- Consumes: blueprint dict (keys `domain_invariants[].enforced_at`, `decisions.key_decisions[].forced_by`, `persistence_stores[].location`/`name`, `data_models[].location`).
- Produces: `select_specialists(blueprint: dict, changed_files: list[str]) -> dict` returning `{"specialists": [...], "reason": {...}}`. `specialists` is a subset of `{"invariant-integrity", "decision-integrity", "data-lifecycle"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_selector.py
import archie.standalone.selector as sel

BP = {
  "domain_invariants": [{"id": "inv-1", "enforced_at": ["billing/usage.py:88", "billing/"]}],
  "decisions": {"key_decisions": [{"title": "d1", "forced_by": "core/router.py"}]},
  "persistence_stores": [{"name": "pg", "location": "db/models.py"}],
  "data_models": [{"name": "Cart", "location": "db/models.py"}],
}

def test_invariant_specialist_selected_on_cited_file():
    out = sel.select_specialists(BP, ["billing/usage.py"])
    assert "invariant-integrity" in out["specialists"]
    assert "inv-1" in out["reason"]["invariant-integrity"]

def test_data_lifecycle_selected_on_store_file():
    out = sel.select_specialists(BP, ["db/models.py"])
    assert "data-lifecycle" in out["specialists"]

def test_no_touch_returns_empty():
    assert sel.select_specialists(BP, ["README.md"])["specialists"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_selector.py -v`
Expected: FAIL (`AttributeError: select_specialists`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/selector.py
"""Non-reviewing router: intersect changed files with blueprint anchors to
pick Lane-2 specialists. Decides WHO runs; never reviews.
"""
from __future__ import annotations

def _anchor_files(anchors) -> list[str]:
    out = []
    for a in anchors or []:
        s = str(a).split(":", 1)[0]
        if s:
            out.append(s)
    return out

def _hit(changed: list[str], targets: list[str]) -> bool:
    for c in changed:
        for t in targets:
            if not t:
                continue
            if c == t or c.startswith(t.rstrip("/") + "/") or t.rstrip("/") in c:
                return True
    return False

def select_specialists(blueprint: dict, changed_files: list[str]) -> dict:
    specialists, reason = [], {}
    for inv in blueprint.get("domain_invariants", []) or []:
        if _hit(changed_files, _anchor_files(inv.get("enforced_at"))):
            specialists.append("invariant-integrity")
            reason.setdefault("invariant-integrity", []).append(inv.get("id", "?"))
            break
    decisions = (blueprint.get("decisions") or {}).get("key_decisions", []) or []
    forced = [str(d.get("forced_by", "")) for d in decisions if d.get("forced_by")]
    if _hit(changed_files, forced):
        specialists.append("decision-integrity")
        reason["decision-integrity"] = "changed a decision's forced_by file"
    store_files = [str(s.get("location", "")) for s in blueprint.get("persistence_stores", []) or []]
    store_files += [str(m.get("location", "")) for m in blueprint.get("data_models", []) or []]
    if _hit(changed_files, store_files):
        specialists.append("data-lifecycle")
        reason["data-lifecycle"] = "changed a persistence/data-model file"
    if "invariant-integrity" in reason:
        reason["invariant-integrity"] = "cites domain_invariant " + ",".join(reason["invariant-integrity"])
    return {"specialists": specialists, "reason": reason}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_selector.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/selector.py npm-package/assets/selector.py
python3 scripts/verify_sync.py
git add archie/standalone/selector.py npm-package/assets/selector.py tests/test_selector.py
git commit -m "feat(review): blueprint-derived specialist selector"
```

---

### Task 4: Editor gate (schema + anchor + dedup, cannot invent)

**Files:**
- Create: `archie/standalone/editor_gate.py`
- Test: `tests/test_editor_gate.py`

**Interfaces:**
- Consumes: `evidence_schema.has_evidence_fields`; existing store finding shape.
- Produces: `gate(raw_findings: list[dict], store: list[dict], *, changed_lines: dict[str, set[int]] | None, floors: dict[str, float]) -> dict` returning `{"confirmed": [...], "suppressed": [...]}`. Enforces: schema present, confidence ≥ per-kind floor, anchor maps to a changed line when `changed_lines` given, dedup vs store by `(anchor.file, kind)`. It never adds a finding absent from `raw_findings`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_editor_gate.py
import archie.standalone.editor_gate as eg
from archie.standalone.evidence_schema import make_finding

def _f(fid, file, line, conf, kind="behavioral_break"):
    return make_finding(id=fid, kind=kind, edge="B", problem_statement="p",
        anchor={"file": file, "line": line, "changed": True}, assumptions=[],
        evidence=["e"], falsification="fx", confidence=conf,
        source="behavioral", severity_class="pitfall_triggered")

FLOORS = {"behavioral_break": 0.5, "intent_unmet": 0.4}

def test_drops_below_floor():
    out = eg.gate([_f("f1", "a.py", 3, 0.2)], [], changed_lines=None, floors=FLOORS)
    assert out["confirmed"] == [] and out["suppressed"][0]["reason"] == "below_floor"

def test_drops_when_anchor_not_on_changed_line():
    out = eg.gate([_f("f1", "a.py", 99, 0.9)], [], changed_lines={"a.py": {1, 2}}, floors=FLOORS)
    assert out["confirmed"] == [] and out["suppressed"][0]["reason"] == "anchor_unchanged"

def test_dedups_against_store():
    store = [{"anchor": {"file": "a.py"}, "kind": "behavioral_break", "id": "old"}]
    out = eg.gate([_f("f1", "a.py", 1, 0.9)], store, changed_lines={"a.py": {1}}, floors=FLOORS)
    assert out["confirmed"] == [] and out["suppressed"][0]["reason"] == "duplicate"

def test_keeps_valid_new_finding():
    out = eg.gate([_f("f1", "a.py", 1, 0.9)], [], changed_lines={"a.py": {1}}, floors=FLOORS)
    assert len(out["confirmed"]) == 1 and out["confirmed"][0]["id"] == "f1"

def test_cannot_invent_only_passes_through_inputs():
    out = eg.gate([], [], changed_lines=None, floors=FLOORS)
    assert out["confirmed"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_editor_gate.py -v`
Expected: FAIL (`AttributeError: gate`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/editor_gate.py
"""Editor gate: the single reliability pass every surface routes through.
Validates, floor-gates, anchor-checks, and dedups. It NEVER invents a finding
absent from its input — every confirmed item is an input item, unchanged in id.
"""
from __future__ import annotations
from archie.standalone.evidence_schema import has_evidence_fields

def _dupe_key(f: dict):
    return ((f.get("anchor") or {}).get("file", ""), f.get("kind", ""))

def gate(raw_findings, store, *, changed_lines, floors) -> dict:
    confirmed, suppressed = [], []
    seen = {_dupe_key(s) for s in store}
    for f in raw_findings:
        if not has_evidence_fields(f):
            suppressed.append({"id": f.get("id"), "reason": "schema"}); continue
        floor = floors.get(f.get("kind", ""), 0.5)
        if float(f.get("confidence", 0.0)) < floor:
            suppressed.append({"id": f.get("id"), "reason": "below_floor"}); continue
        anchor = f.get("anchor") or {}
        if changed_lines is not None:
            lines = changed_lines.get(anchor.get("file", ""), set())
            if anchor.get("line") not in lines:
                suppressed.append({"id": f.get("id"), "reason": "anchor_unchanged"}); continue
        key = _dupe_key(f)
        if key in seen:
            suppressed.append({"id": f.get("id"), "reason": "duplicate"}); continue
        seen.add(key)
        confirmed.append(f)
    return {"confirmed": confirmed, "suppressed": suppressed}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_editor_gate.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/editor_gate.py npm-package/assets/editor_gate.py
python3 scripts/verify_sync.py
git add archie/standalone/editor_gate.py npm-package/assets/editor_gate.py tests/test_editor_gate.py
git commit -m "feat(review): editor gate (floor/anchor/dedup, cannot invent)"
```

---

## Phase 2 — Behavioral Engine (blueprint-free)

### Task 5: Reachability layer over the scanner import graph

**Files:**
- Create: `archie/standalone/reachability.py`
- Test: `tests/test_reachability.py`

**Interfaces:**
- Consumes: `scan.json`'s `import_graph: {file: [imported_module,...]}`.
- Produces: `consumers(import_graph: dict, changed_file: str) -> list[str]` (files that import, directly or transitively, the changed file).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reachability.py
import archie.standalone.reachability as r

GRAPH = {"a.py": ["b"], "b.py": ["c"], "c.py": [], "d.py": ["a"]}

def test_direct_and_transitive_consumers():
    got = set(r.consumers(GRAPH, "c.py"))
    assert got == {"b.py", "a.py", "d.py"}

def test_leaf_change_has_no_consumers():
    assert r.consumers(GRAPH, "d.py") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_reachability.py -v`
Expected: FAIL (`AttributeError: consumers`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/reachability.py
"""Reachability over the scanner's file-level import graph.

The scanner emits import_graph = {file: [imported_module,...]}. We invert it to
"who depends on X" and walk transitively to approximate blast radius. This is
file-level (not call-level) — a deliberately cheap over-approximation.
"""
from __future__ import annotations

def _module_stem(f: str) -> str:
    return f.rsplit("/", 1)[-1].rsplit(".", 1)[0]

def consumers(import_graph: dict, changed_file: str) -> list[str]:
    stem = _module_stem(changed_file)
    reverse: dict[str, set[str]] = {}
    for src, imports in import_graph.items():
        for imp in imports:
            reverse.setdefault(_module_stem(str(imp)), set()).add(src)
    out, frontier, seen = [], [changed_file], {changed_file}
    while frontier:
        cur = frontier.pop()
        for dep in reverse.get(_module_stem(cur), set()):
            if dep not in seen:
                seen.add(dep); out.append(dep); frontier.append(dep)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_reachability.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/reachability.py npm-package/assets/reachability.py
python3 scripts/verify_sync.py
git add archie/standalone/reachability.py npm-package/assets/reachability.py tests/test_reachability.py
git commit -m "feat(review): reachability layer over import graph"
```

---

### Task 6: Behavioral reviewer (prompt builder + response parser)

**Files:**
- Create: `archie/standalone/behavioral_review.py`
- Test: `tests/test_behavioral_review.py`

**Interfaces:**
- Consumes: `evidence_schema.make_finding`; `reachability.consumers`; `agent_cli.run_verifier`.
- Produces: `build_prompt(diff_text: str, consumer_map: dict[str, list[str]]) -> str`; `parse_findings(raw: str) -> list[dict]` (tolerant JSON parse → evidence-schema findings); `review(root, diff_text, import_graph, changed_files, run=run_verifier) -> list[dict]`.

- [ ] **Step 1: Write the failing test** (LLM seam mocked, mirroring `test_verify_findings.py`)

```python
# tests/test_behavioral_review.py
import json
import archie.standalone.behavioral_review as br

def test_build_prompt_lists_consumers():
    p = br.build_prompt("diff --git a/x.py", {"x.py": ["y.py", "z.py"]})
    assert "x.py" in p and "y.py" in p and "falsification" in p

def test_parse_findings_maps_to_evidence_schema():
    raw = json.dumps({"findings": [{
        "problem_statement": "N+1 in loop", "file": "x.py", "line": 5,
        "assumptions": ["called per row"], "evidence": ["x.py:5 queries in loop"],
        "falsification": "query is batched upstream", "confidence": 0.8,
        "kind": "behavioral_break"}]})
    out = br.parse_findings(raw)
    assert out[0]["kind"] == "behavioral_break" and out[0]["anchor"]["line"] == 5
    assert out[0]["falsification"]

def test_review_mocked(monkeypatch):
    monkeypatch.setattr(br, "run_verifier", lambda *a, **k: json.dumps({"findings": []}))
    assert br.review("/x", "diff", {}, ["x.py"]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_behavioral_review.py -v`
Expected: FAIL (`AttributeError: build_prompt`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/behavioral_review.py
"""Blueprint-free behavioral reviewer: reasons about the code itself
(crash / data-loss / perf / security) and consults blast radius. LLM is called
through run_verifier; prompt-builder and parser are pure and unit-tested.
"""
from __future__ import annotations
import json
from pathlib import Path
from archie.standalone.agent_cli import run_verifier
from archie.standalone.reachability import consumers  # noqa: F401 (used by callers)
from archie.standalone.evidence_schema import make_finding

_SYSTEM = (
    "You are a behavioral code reviewer. Report only issues INTRODUCED or worsened "
    "by this diff. For each, give a falsification test ('how you'd prove me wrong'). "
    "Anchor every finding to a changed line. Return JSON {\"findings\":[...]}."
)

def build_prompt(diff_text: str, consumer_map: dict) -> str:
    radius = "\n".join(f"{f} -> {', '.join(c)}" for f, c in consumer_map.items())
    return (f"{_SYSTEM}\n\nDIFF:\n{diff_text}\n\nBLAST RADIUS (changed file -> consumers):\n"
            f"{radius}\n\nEach finding needs: problem_statement, file, line, assumptions[], "
            "evidence[], falsification, confidence(0-1), kind"
            "(behavioral_break).")

def parse_findings(raw: str) -> list[dict]:
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1]) if start >= 0 else {}
    except Exception:
        return []
    out = []
    for i, f in enumerate(data.get("findings", [])):
        if not f.get("falsification"):
            continue
        out.append(make_finding(
            id=f.get("id") or f"f_beh_{i}", kind=f.get("kind", "behavioral_break"), edge="B",
            problem_statement=f.get("problem_statement", ""),
            anchor={"file": f.get("file", ""), "line": f.get("line"), "changed": True},
            assumptions=f.get("assumptions", []), evidence=f.get("evidence", []),
            falsification=f["falsification"], confidence=float(f.get("confidence", 0.0)),
            source="behavioral", severity_class="pitfall_triggered"))
    return out

def review(root, diff_text, import_graph, changed_files, run=run_verifier) -> list[dict]:
    cmap = {cf: consumers(import_graph, cf) for cf in changed_files}
    raw = run(build_prompt(diff_text, cmap), Path(root), "claude")
    return parse_findings(raw or "")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_behavioral_review.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/behavioral_review.py npm-package/assets/behavioral_review.py
python3 scripts/verify_sync.py
git add archie/standalone/behavioral_review.py npm-package/assets/behavioral_review.py tests/test_behavioral_review.py
git commit -m "feat(review): behavioral reviewer (prompt/parse + blast radius)"
```

---

## Phase 3 — Intent Resolver

### Task 7: intent_spec normalization + confidence ceiling

**Files:**
- Create: `archie/standalone/intent.py`
- Test: `tests/test_intent.py`

**Interfaces:**
- Produces: `CONFIDENCE_CEILING: dict[str, float]` keyed by source; `normalize(raw_text: str, source: str, ticket_ids: list[str]) -> dict` → `intent_spec {source, confidence, ticket_ids, goals, acceptance_criteria, non_goals, raw}`; `ceiling_for(intent_spec: dict) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intent.py
import archie.standalone.intent as it

def test_normalize_sets_source_and_confidence():
    spec = it.normalize("Add rate limiting to export", source="prompt", ticket_ids=[])
    assert spec["source"] == "prompt" and spec["confidence"] == "medium"
    assert spec["raw"].startswith("Add rate")

def test_inferred_source_is_low_and_advisory_ceiling():
    spec = it.normalize("", source="inferred", ticket_ids=[])
    assert spec["confidence"] == "low"
    assert it.ceiling_for(spec) <= 0.5

def test_linked_ticket_is_high_confidence():
    spec = it.normalize("AC1: scope by tenant", source="linear", ticket_ids=["ARCH-1"])
    assert spec["confidence"] == "high" and it.ceiling_for(spec) == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_intent.py -v`
Expected: FAIL (`AttributeError: normalize`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/intent.py
"""Intent resolver: normalize any intent source to one shape and expose the
confidence ceiling that caps edge-A findings (the anti-noise valve for the
no-ticket case).
"""
from __future__ import annotations

_CONF_BY_SOURCE = {"linear": "high", "prompt": "medium", "pr_body": "medium",
                   "commits": "low", "inferred": "low"}
CONFIDENCE_CEILING = {"high": 1.0, "medium": 0.75, "low": 0.5}

def normalize(raw_text: str, source: str, ticket_ids: list[str]) -> dict:
    conf = _CONF_BY_SOURCE.get(source, "low")
    return {
        "source": source,
        "confidence": conf,
        "ticket_ids": list(ticket_ids),
        "goals": [],                 # populated by the LLM normalize step in resolve()
        "acceptance_criteria": [],   # ditto
        "non_goals": [],
        "raw": raw_text,
    }

def ceiling_for(intent_spec: dict) -> float:
    return CONFIDENCE_CEILING.get(intent_spec.get("confidence", "low"), 0.5)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_intent.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/intent.py npm-package/assets/intent.py
python3 scripts/verify_sync.py
git add archie/standalone/intent.py npm-package/assets/intent.py tests/test_intent.py
git commit -m "feat(review): intent_spec normalization + confidence ceiling"
```

---

### Task 8: Intent ladder resolution + per-branch record

**Files:**
- Modify: `archie/standalone/intent.py`
- Test: `tests/test_intent_ladder.py`

**Interfaces:**
- Consumes: `intent.normalize`; `_common._load_json`.
- Produces: `ticket_ids_from(branch: str, pr_body: str, commit_msgs: list[str]) -> list[str]`; `load_branch_record(archie_dir: Path, branch: str) -> dict | None`; `save_branch_record(archie_dir: Path, branch: str, spec: dict) -> None` (writes `.archie/intent/<branch>.json`, merging over any existing higher-confidence spec).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intent_ladder.py
import json
from pathlib import Path
import archie.standalone.intent as it

def test_ticket_ids_from_branch_and_body():
    ids = it.ticket_ids_from("feature/ARCH-123-export", "closes ARCH-124", ["fix ARCH-123"])
    assert set(ids) == {"ARCH-123", "ARCH-124"}

def test_save_and_load_branch_record(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    spec = it.normalize("do X", source="prompt", ticket_ids=[])
    it.save_branch_record(ad, "feature/x", spec)
    got = it.load_branch_record(ad, "feature/x")
    assert got["raw"] == "do X"

def test_save_does_not_downgrade_confidence(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    it.save_branch_record(ad, "b", it.normalize("t", source="linear", ticket_ids=["A-1"]))
    it.save_branch_record(ad, "b", it.normalize("p", source="prompt", ticket_ids=[]))
    assert it.load_branch_record(ad, "b")["source"] == "linear"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_intent_ladder.py -v`
Expected: FAIL (`AttributeError: ticket_ids_from`).

- [ ] **Step 3: Write minimal implementation** (append to `intent.py`)

```python
# --- append to archie/standalone/intent.py ---
import re, json
from pathlib import Path

_RANK = {"inferred": 0, "commits": 1, "pr_body": 2, "prompt": 2, "linear": 3}
_TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

def ticket_ids_from(branch: str, pr_body: str, commit_msgs: list[str]) -> list[str]:
    text = " ".join([branch or "", pr_body or "", " ".join(commit_msgs or [])])
    seen, out = set(), []
    for m in _TICKET_RE.findall(text):
        if m not in seen:
            seen.add(m); out.append(m)
    return out

def _record_path(archie_dir: Path, branch: str) -> Path:
    safe = branch.replace("/", "__")
    return archie_dir / "intent" / f"{safe}.json"

def load_branch_record(archie_dir: Path, branch: str):
    p = _record_path(archie_dir, branch)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None

def save_branch_record(archie_dir: Path, branch: str, spec: dict) -> None:
    existing = load_branch_record(archie_dir, branch)
    if existing and _RANK.get(existing.get("source"), 0) > _RANK.get(spec.get("source"), 0):
        return
    p = _record_path(archie_dir, branch)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(spec, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_intent_ladder.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/intent.py npm-package/assets/intent.py
python3 scripts/verify_sync.py
git add archie/standalone/intent.py npm-package/assets/intent.py tests/test_intent_ladder.py
git commit -m "feat(review): intent ladder resolution + per-branch record"
```

---

## Phase 4 — Reconciliation Reviewer

### Task 9: Edge A (intent ⋈ diff) reviewer

**Files:**
- Create: `archie/standalone/reconcile.py`
- Test: `tests/test_reconcile_edge_a.py`

**Interfaces:**
- Consumes: `intent.ceiling_for`; `evidence_schema.make_finding` + `clamp_confidence`; `agent_cli.run_verifier`.
- Produces: `build_edge_a_prompt(intent_spec, diff_text) -> str`; `parse_edge_a(raw, intent_spec) -> list[dict]` (each finding confidence clamped by `ceiling_for(intent_spec)`); `review_edge_a(root, intent_spec, diff_text, run=run_verifier) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_reconcile_edge_a.py
import json
import archie.standalone.reconcile as rc
import archie.standalone.intent as it

def test_edge_a_prompt_lists_criteria():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1", "text": "scope by tenant"}]
    p = rc.build_edge_a_prompt(spec, "diff")
    assert "ac1" in p and "scope by tenant" in p

def test_edge_a_clamps_to_intent_ceiling():
    spec = it.normalize("", source="inferred", ticket_ids=[])  # ceiling 0.5
    raw = json.dumps({"findings": [{"criterion_id": "ac1", "verdict": "unmet",
        "file": "x.py", "line": 1, "evidence": ["missing"], "falsification": "wired elsewhere",
        "confidence": 0.9}]})
    out = rc.parse_edge_a(raw, spec)
    assert out[0]["kind"] == "intent_unmet" and out[0]["confidence"] == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_reconcile_edge_a.py -v`
Expected: FAIL (`AttributeError: build_edge_a_prompt`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/reconcile.py
"""Reconciliation reviewer — edges A (intent vs diff) and C (intent vs blueprint).
Prompt-builders and parsers are pure; the LLM seam is run_verifier.
"""
from __future__ import annotations
import json
from pathlib import Path
from archie.standalone.agent_cli import run_verifier
from archie.standalone.evidence_schema import make_finding, clamp_confidence
from archie.standalone.intent import ceiling_for

_VERDICT_KIND = {"unmet": "intent_unmet", "partial": "intent_partial", "drift": "intent_drift"}

def build_edge_a_prompt(intent_spec: dict, diff_text: str) -> str:
    crit = "\n".join(f'- {c.get("id")}: {c.get("text")}' for c in intent_spec.get("acceptance_criteria", []))
    return ("Decide, per acceptance criterion, whether the DIFF implements it and the code is "
            "reachable. Verdict met|partial|unmet, plus drift for unrequested behavior. Give a "
            "falsification for each. Return JSON {\"findings\":[{criterion_id,verdict,file,line,"
            f"evidence[],falsification,confidence}}]}}\n\nCRITERIA:\n{crit}\n\nDIFF:\n{diff_text}")

def parse_edge_a(raw: str, intent_spec: dict) -> list[dict]:
    ceiling = ceiling_for(intent_spec)
    try:
        s, e = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[s:e + 1]) if s >= 0 else {}
    except Exception:
        return []
    out = []
    for i, f in enumerate(data.get("findings", [])):
        verdict = f.get("verdict")
        if verdict == "met" or not f.get("falsification"):
            continue
        finding = make_finding(
            id=f.get("id") or f"f_a_{i}", kind=_VERDICT_KIND.get(verdict, "intent_partial"),
            edge="A", problem_statement=f"{f.get('criterion_id','?')}: {verdict}",
            anchor={"file": f.get("file", ""), "line": f.get("line"), "changed": True},
            assumptions=[f"criterion {f.get('criterion_id')}"], evidence=f.get("evidence", []),
            falsification=f["falsification"], confidence=float(f.get("confidence", 0.0)),
            source="reconcile:edgeA", severity_class="pattern_divergence")
        out.append(clamp_confidence(finding, ceiling))
    return out

def review_edge_a(root, intent_spec, diff_text, run=run_verifier) -> list[dict]:
    raw = run(build_edge_a_prompt(intent_spec, diff_text), Path(root), "claude")
    return parse_edge_a(raw or "", intent_spec)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_reconcile_edge_a.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/reconcile.py npm-package/assets/reconcile.py
python3 scripts/verify_sync.py
git add archie/standalone/reconcile.py npm-package/assets/reconcile.py tests/test_reconcile_edge_a.py
git commit -m "feat(review): reconciliation edge A (intent vs diff)"
```

---

### Task 10: Verdict aggregation + reconcile orchestration

**Files:**
- Modify: `archie/standalone/reconcile.py`
- Test: `tests/test_verdict.py`

**Interfaces:**
- Consumes: confirmed findings (from `editor_gate.gate`), `intent_spec`.
- Produces: `aggregate_verdict(intent_spec: dict, confirmed: list[dict]) -> dict` → `{intent_completeness: "m/n", breaks: int, conflicts: int, gate_signal: float}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_verdict.py
import archie.standalone.reconcile as rc
import archie.standalone.intent as it

def test_aggregate_counts_completeness_and_breaks():
    spec = it.normalize("", source="linear", ticket_ids=["A-1"])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}, {"id": "ac3"}]
    confirmed = [
        {"kind": "intent_unmet", "assumptions": ["criterion ac2"]},
        {"kind": "conformance_break"}, {"kind": "behavioral_break"},
    ]
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["intent_completeness"] == "2/3" and v["breaks"] == 2 and v["conflicts"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_verdict.py -v`
Expected: FAIL (`AttributeError: aggregate_verdict`).

- [ ] **Step 3: Write minimal implementation** (append to `reconcile.py`)

```python
# --- append to archie/standalone/reconcile.py ---
def aggregate_verdict(intent_spec: dict, confirmed: list[dict]) -> dict:
    total = len(intent_spec.get("acceptance_criteria", []))
    unmet = sum(1 for f in confirmed if f.get("kind") in ("intent_unmet", "intent_partial"))
    met = max(0, total - unmet)
    breaks = sum(1 for f in confirmed if f.get("kind") in ("conformance_break", "behavioral_break"))
    conflicts = sum(1 for f in confirmed if f.get("kind") == "intent_conflict")
    gate_signal = round(1.0 - min(1.0, 0.25 * breaks + 0.5 * conflicts), 3)
    return {"intent_completeness": f"{met}/{total}", "breaks": breaks,
            "conflicts": conflicts, "gate_signal": gate_signal}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_verdict.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/reconcile.py npm-package/assets/reconcile.py
python3 scripts/verify_sync.py
git add archie/standalone/reconcile.py npm-package/assets/reconcile.py tests/test_verdict.py
git commit -m "feat(review): delivery verdict aggregation"
```

---

## Phase 5 — Wire deep-scan

### Task 11: Risk agent emits the evidence schema

**Files:**
- Modify: `npm-package/assets/workflow/deep-scan/steps/step-5b-risk.md`
- Modify: `.claude/commands/` mirror if present (else the npm asset is canonical for the workflow step)
- Test: `tests/test_risk_step_schema.py`

**Interfaces:**
- Produces: Risk-agent findings that already carry `kind`, `edge:"B"`, `anchor`, `assumptions`, `falsification`, `confidence` in addition to the legacy fields — so `evidence_schema.has_evidence_fields` returns True on them.

- [ ] **Step 1: Write the failing test** (contract test on a fixture the step must satisfy)

```python
# tests/test_risk_step_schema.py
import json, pathlib
from archie.standalone.evidence_schema import has_evidence_fields

def test_risk_fixture_satisfies_evidence_schema():
    fx = pathlib.Path("tests/fixtures/risk_finding_sample.json")
    finding = json.loads(fx.read_text())
    assert has_evidence_fields(finding)
    assert finding["edge"] == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_risk_step_schema.py -v`
Expected: FAIL (`FileNotFoundError` — fixture absent).

- [ ] **Step 3: Create the fixture + update the step prompt**

Create `tests/fixtures/risk_finding_sample.json`:
```json
{
  "id": "f_0001", "kind": "behavioral_break", "edge": "B",
  "problem_statement": "unbounded retry loop on transient error",
  "triggering_call_site": "jobs/worker.py:88",
  "anchor": {"file": "jobs/worker.py", "line": 88, "changed": false},
  "assumptions": ["error is retried without a ceiling"],
  "evidence": ["jobs/worker.py:88 while True: retry()"],
  "falsification": "a max-attempts guard exists in the enclosing function",
  "confidence": 0.7, "source": "deep_scan", "severity_class": "pitfall_triggered",
  "root_cause": "missing retry ceiling", "applies_to": ["jobs/worker.py"]
}
```

In `step-5b-risk.md`, update the emission contract so every finding includes `kind`, `edge: "B"`, `anchor {file,line,changed}`, `assumptions[]`, and `falsification` alongside the legacy fields. Add one line: *"Every finding MUST include a `falsification` — a code-checkable way to prove it wrong — or it is dropped downstream."*

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_risk_step_schema.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
python3 scripts/verify_sync.py
git add tests/fixtures/risk_finding_sample.json npm-package/assets/workflow/deep-scan/steps/step-5b-risk.md tests/test_risk_step_schema.py
git commit -m "feat(deep-scan): Risk agent emits evidence schema"
```

---

### Task 12: Cold-read pass + editor gate in finalize

**Files:**
- Modify: `archie/standalone/finalize.py`
- Test: `tests/test_finalize_gate.py`

**Interfaces:**
- Consumes: `editor_gate.gate`; `finalize._merge_findings_into_store`.
- Produces: `gate_and_merge(archie_dir: Path, raw_findings: list[dict], floors: dict[str, float]) -> dict` — runs `gate` with `changed_lines=None` (cold read: no diff anchor) using a **strict floor**, then merges confirmed findings via the existing `_merge_findings_into_store`. Returns `{merged: int, suppressed: int}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_finalize_gate.py
import json
from pathlib import Path
import archie.standalone.finalize as fz
from archie.standalone.evidence_schema import make_finding

def _f(fid, conf):
    return make_finding(id=fid, kind="behavioral_break", edge="B", problem_statement="p",
        anchor={"file": "a.py", "line": 3, "changed": False}, assumptions=[], evidence=["e"],
        falsification="fx", confidence=conf, source="deep_scan", severity_class="pitfall_triggered")

def test_cold_read_strict_floor(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    out = fz.gate_and_merge(ad, [_f("f1", 0.55), _f("f2", 0.9)], floors={"behavioral_break": 0.7})
    store = json.loads((ad / "findings.json").read_text())["findings"]
    ids = {f["id"] for f in store}
    assert "f2" in ids and "f1" not in ids and out["suppressed"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_finalize_gate.py -v`
Expected: FAIL (`AttributeError: gate_and_merge`).

- [ ] **Step 3: Write minimal implementation** (append to `finalize.py`)

```python
# --- append to archie/standalone/finalize.py ---
from archie.standalone.editor_gate import gate as _gate

def gate_and_merge(archie_dir, raw_findings, floors) -> dict:
    store = []
    findings_path = archie_dir / "findings.json"
    if findings_path.exists():
        try:
            store = json.loads(findings_path.read_text()).get("findings", [])
        except Exception:
            store = []
    result = _gate(raw_findings, store, changed_lines=None, floors=floors)
    merged = _merge_findings_into_store(archie_dir, result["confirmed"])
    return {"merged": merged, "suppressed": len(result["suppressed"])}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_finalize_gate.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/finalize.py npm-package/assets/finalize.py
python3 scripts/verify_sync.py
git add archie/standalone/finalize.py npm-package/assets/finalize.py tests/test_finalize_gate.py
git commit -m "feat(deep-scan): cold-read editor gate in finalize"
```

---

## Phase 6 — Wire sync + PR gate

### Task 13: sync light delivery review (status-line, non-blocking)

**Files:**
- Create: `archie/standalone/sync_review.py`
- Test: `tests/test_sync_review.py`

**Interfaces:**
- Consumes: `diff_basis`, `selector.select_specialists`, `intent.load_branch_record`, `reconcile.review_edge_a`, `behavioral_review.review`, `editor_gate.gate`, `reconcile.aggregate_verdict`.
- Produces: `run_sync_review(root, branch, blueprint, import_graph, diff_text, changed_files, changed_lines, floors, *, run=run_verifier) -> dict` → `{confirmed: [...], verdict: {...}, skipped: bool}`. **Skip-gate:** if `select_specialists` returns no specialists AND `changed_files` are all non-source, return `{skipped: True}` without any LLM call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync_review.py
import archie.standalone.sync_review as sr

BP = {"domain_invariants": [], "decisions": {"key_decisions": []},
      "persistence_stores": [], "data_models": []}

def test_skip_gate_no_llm_when_nothing_touched():
    called = {"n": 0}
    def fake_run(*a, **k): called["n"] += 1; return "{}"
    out = sr.run_sync_review("/x", "b", BP, {}, "diff", ["README.md"], {}, {}, run=fake_run)
    assert out["skipped"] is True and called["n"] == 0

def test_runs_when_source_touched(monkeypatch):
    monkeypatch.setattr(sr, "review_edge_a", lambda *a, **k: [])
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])
    out = sr.run_sync_review("/x", "b", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {})
    assert out["skipped"] is False and "verdict" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync_review.py -v`
Expected: FAIL (`AttributeError: run_sync_review`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/sync_review.py
"""Sync-surface delivery review: light, continuous, non-blocking. Runs edge A +
behavioral on the branch delta, gates, and returns a status-line verdict.
"""
from __future__ import annotations
from pathlib import Path
from archie.standalone._common import SOURCE_EXTENSIONS
from archie.standalone.agent_cli import run_verifier
from archie.standalone.selector import select_specialists
from archie.standalone.intent import load_branch_record, normalize
from archie.standalone.reconcile import review_edge_a, aggregate_verdict
from archie.standalone.behavioral_review import review as behavioral_review_run
from archie.standalone.editor_gate import gate

def _is_source(f: str) -> bool:
    return any(f.endswith(ext) for ext in SOURCE_EXTENSIONS)

def run_sync_review(root, branch, blueprint, import_graph, diff_text,
                    changed_files, changed_lines, floors, *, run=run_verifier) -> dict:
    sel = select_specialists(blueprint, changed_files)
    if not sel["specialists"] and not any(_is_source(f) for f in changed_files):
        return {"skipped": True}
    archie_dir = Path(root) / ".archie"
    spec = load_branch_record(archie_dir, branch) or normalize("", source="inferred", ticket_ids=[])
    raw = review_edge_a(root, spec, diff_text, run=run)
    raw += behavioral_review_run(root, diff_text, import_graph, changed_files, run=run)
    store = []
    fp = archie_dir / "findings.json"
    if fp.exists():
        import json
        try: store = json.loads(fp.read_text()).get("findings", [])
        except Exception: store = []
    result = gate(raw, store, changed_lines=changed_lines, floors=floors)
    return {"skipped": False, "confirmed": result["confirmed"],
            "verdict": aggregate_verdict(spec, result["confirmed"])}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sync_review.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
cp archie/standalone/sync_review.py npm-package/assets/sync_review.py
python3 scripts/verify_sync.py
git add archie/standalone/sync_review.py npm-package/assets/sync_review.py tests/test_sync_review.py
git commit -m "feat(sync): light delivery review with skip-gate"
```

---

### Task 14: PR-gate delivery review (intake + full reconcile + verdict comment)

**Files:**
- Create: `archie/standalone/delivery_review.py`
- Modify: `.github/workflows/archie-check.yml`
- Test: `tests/test_delivery_review.py`

**Interfaces:**
- Consumes: `diff_basis`, `intent`, `selector`, `reconcile`, `behavioral_review`, `editor_gate`, and `intent_review.post_or_update_comment` (reuse the existing upsert-comment helper + its `<!-- archie-... -->` marker pattern).
- Produces: `should_review(pr_meta: dict, max_files: int) -> tuple[bool, str]` (intake); `render_verdict(verdict: dict, confirmed: list[dict]) -> str` (Markdown delivery verdict).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_delivery_review.py
import archie.standalone.delivery_review as dr

def test_intake_skips_bot_and_large():
    ok, why = dr.should_review({"author": "dependabot[bot]", "changed_files": 3, "labels": []}, 75)
    assert ok is False and "bot" in why
    ok, why = dr.should_review({"author": "human", "changed_files": 200, "labels": []}, 75)
    assert ok is False and "too many files" in why

def test_intake_override_label_forces_run():
    ok, _ = dr.should_review({"author": "dependabot[bot]", "changed_files": 3,
                              "labels": ["archie-review"]}, 75)
    assert ok is True

def test_render_verdict_shows_completeness_and_breaks():
    md = dr.render_verdict({"intent_completeness": "3/4", "breaks": 1, "conflicts": 0},
                           [{"kind": "intent_unmet", "problem_statement": "ac2", "anchor": {"file": "x.py", "line": 4}}])
    assert "3/4" in md and "1" in md and "x.py:4" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_delivery_review.py -v`
Expected: FAIL (`AttributeError: should_review`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/delivery_review.py
"""PR-gate delivery review: intake + full A/B/C reconciliation + verdict comment.
Reuses intent_review.post_or_update_comment for the upsert. Diffing, intent, and
gating come from the shared core.
"""
from __future__ import annotations

_OVERRIDE_LABEL = "archie-review"
_SKIP_LABEL = "archie-skip"

def should_review(pr_meta: dict, max_files: int) -> tuple[bool, str]:
    labels = pr_meta.get("labels", []) or []
    if _OVERRIDE_LABEL in labels:
        return True, "override label"
    if str(pr_meta.get("author", "")).endswith("[bot]"):
        return False, "bot author"
    if _SKIP_LABEL in labels:
        return False, "skip label"
    if int(pr_meta.get("changed_files", 0)) > max_files:
        return False, "too many files"
    return True, "eligible"

def render_verdict(verdict: dict, confirmed: list[dict]) -> str:
    lines = ["<!-- archie-delivery-review -->", "## Delivery review", ""]
    lines.append(f"**Built the intent?** {verdict.get('intent_completeness','?')} acceptance criteria.")
    lines.append(f"**Broke anything?** {verdict.get('breaks',0)} break(s), "
                 f"{verdict.get('conflicts',0)} requirement conflict(s).")
    if confirmed:
        lines.append("")
        for f in confirmed:
            a = f.get("anchor", {})
            lines.append(f"- `{f.get('kind')}` {f.get('problem_statement','')} "
                         f"({a.get('file','')}:{a.get('line','')})")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_delivery_review.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire the Action + commit**

In `.github/workflows/archie-check.yml`, add a step after `archie check` (keep intent_review running):
```yaml
      - run: python3 .archie/delivery_review.py
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_BASE_REF: ${{ github.base_ref }}
          GITHUB_EVENT_PATH: ${{ github.event_path }}
```

```bash
cp archie/standalone/delivery_review.py npm-package/assets/delivery_review.py
python3 scripts/verify_sync.py
git add archie/standalone/delivery_review.py npm-package/assets/delivery_review.py .github/workflows/archie-check.yml tests/test_delivery_review.py
git commit -m "feat(pr-gate): delivery review intake + verdict comment"
```

---

## Self-Review

**Spec coverage:**
- §3 triangle → edges A (Task 9), B behavioral (Task 6) + conformance selector (Task 3), C (deferred — see gap below).
- §4 taxonomy → all six kinds flow through `make_finding` (Task 1) and `aggregate_verdict` (Task 10).
- §5 intent ladder / no-ticket → Tasks 7–8 (normalize, confidence ceiling, per-branch record).
- §6 core → evidence schema (1), diff_basis (2), selector (3), editor gate (4), behavioral engine (5–6), intent resolver (7–8), reconcile (9–10).
- §6.6a contract→tracer→challenger invariant specialist → **partial:** selector routes to it (Task 3) but the three-role loop itself is not yet its own task.
- §7 workflows → deep-scan (11–12), sync (13), PR gate (14).

**Gaps flagged (add as follow-up tasks before execution if you want full §-coverage):**
1. **Edge C reviewer** (`intent_conflict`) — `aggregate_verdict` counts it, but no producer emits it yet. Add a `review_edge_c` mirroring Task 9 against touched invariants.
2. **Invariant specialist `contract → tracer → challenger`** (§6.6a) — currently only routed to; the runner-backed loop needs its own task (planner-critic from public refs, contract read off `domain_invariants[].enforced_at`).
3. **Passive prompt capture hook** (§5) — Tasks 7–8 persist/read the branch record, but the hook that extracts the agent prompt into it is not yet a task.
4. **AIS integration** (§10 open q) — `gate_signal` is computed (Task 10) but not yet fed to the Architecture Integrity Score.

**Placeholder scan:** none — every code step contains runnable code and exact commands.

**Type consistency:** `make_finding` field names (`anchor`, `falsification`, `confidence`, `kind`, `edge`) are used identically in Tasks 1, 4, 6, 9, 12, 13; `gate(...)` signature matches its callers in Tasks 12–13; `intent_spec` keys match across Tasks 7–10.

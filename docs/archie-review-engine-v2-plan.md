# Review Engine v2 — Wave 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Archie's PR code review code-aware in CI (evidence pack + a jailed tool loop over the checkout), stable across runs (N-pass union with agreement confidence), broad (four universal specialist lenses), and single-sourced (one shared review core for local + CI) — all as a pure GitHub Action, zero new dependencies.

**Architecture:** A new `review_core.run_review()` builds a deterministic evidence pack, fans the reviewers out in parallel (edge-A, behavioral ×N, 4 universal lenses, edge-C, conformance, invariant specialist), and merges findings with agreement-weighted confidence. Both `delivery_review` (CI) and `sync_review` (local) call this one core (F3). The API LLM path gains an optional jailed `read_file`/`grep` tool loop so the invariant tracer/challenger can *verify* claims against the checkout in CI, matching the local `claude -p` capability.

**Tech Stack:** Python 3.9 stdlib only (`concurrent.futures`, `urllib`, `re`, `pathlib`). Existing Archie modules: `agent_cli.run_verifier` (LLM seam), `reachability.consumers` (blast radius), `evidence_schema` (findings), `editor_gate.gate`, `reconcile`, `invariant_specialist`.

## Global Constraints

Every task's requirements implicitly include these (verbatim from the spec + CLAUDE.md):

- Interpreter is `python3` only (3.9.6) — never `python`. Zero third-party dependencies (stdlib only).
- Standalone modules import siblings **bare** via a guarded `_p = str(Path(__file__).parent); if _p not in sys.path: sys.path.insert(0, _p)`. **Never** `from archie.standalone.X import ...`.
- Tests insert `Path(__file__).resolve().parent.parent / "archie" / "standalone"` on `sys.path`, then bare-import. Run tests by explicit path: `python3 -m pytest tests/test_X.py -q`.
- LLM seam is injectable: functions that call the model take `run=None` and resolve `if run is None: run = run_verifier` at call time (monkeypatch works).
- Reviewers/specialists stay blind-appropriate: the evidence pack is source excerpts + blueprint slice; no secrets, no `.git/`.
- Parallelism uses `concurrent.futures.ThreadPoolExecutor` (I/O-bound API calls). No shared mutable state — collect via future results. `ARCHIE_REVIEW_WORKERS=1` forces serial.
- File sync: after editing `archie/standalone/*.py`, copy to `npm-package/assets/*.py`; register any NEW standalone script in the array in `npm-package/bin/archie.mjs`; edit `archie/assets/workflows/*` then copy to `npm-package/assets/workflows/*`; run `python3 scripts/verify_sync.py` (must print `SYNC CHECK PASSED`) before committing.
- Commit trailer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Commit with `git -c user.email=gabor@mindone.app -c user.name="Gabor Bakos" commit`.
- Known pre-existing test failures (fail identically on base, NOT yours): `test_automated_sync_hooks.py::test_churn_track_hook_updates_counter`, `::test_stop_nudges_when_churn_crossed`, `test_install_loop.py::test_codex_rendered_tree_uses_codex_command_prefix_not_slash`, plus ~19 `tomllib` collection errors in `archie.*`-importing tests on Python 3.9.

---

## File Structure

**Create:**
- `archie/standalone/evidence_pack.py` — deterministic context builder (P0a). Pure except reading files under `root`.
- `archie/standalone/finding_merge.py` — union/dedup + agreement-weighted confidence (P1). Pure.
- `archie/standalone/universal_specialists.py` — four fixed category lenses (P2).
- `archie/standalone/review_core.py` — shared evidence-pack → parallel fan-out → merge (F3 + P1b).
- Tests: `tests/test_evidence_pack.py`, `tests/test_finding_merge.py`, `tests/test_universal_specialists.py`, `tests/test_review_core.py`, `tests/test_agent_cli_tools.py`.

**Modify:**
- `archie/standalone/behavioral_review.py` — `evidence=` param + `passes=` param.
- `archie/standalone/agent_cli.py` — jailed tool loop `_run_api_tools` + `run_verifier(..., tools=False)`.
- `archie/standalone/invariant_specialist.py` — tracer/challenger run with `tools=True`.
- `archie/standalone/delivery_review.py` — call `review_core`; evidence pack; diff-truncation disclosure.
- `archie/standalone/sync_review.py` — call `review_core`.
- `archie/assets/workflows/archie-intent-review.yml` (+ npm mirror) — `concurrency` block.
- `npm-package/bin/archie.mjs` — register the 4 new scripts.

**Scope note (F3):** the shared core unifies the *fan-out + merge* (the drift-prone, expensive part). Each publisher keeps its own `editor_gate.gate(...)` + verdict render (they legitimately differ on floors/changed-lines/output). This is the pragmatic F3 — one reviewer brain, two mouths — without rewriting both gating paths.

---

### Task 1: Evidence pack (P0a)

**Files:**
- Create: `archie/standalone/evidence_pack.py`
- Test: `tests/test_evidence_pack.py`

**Interfaces:**
- Consumes: `reachability.consumers(import_graph, changed_file) -> list[str]`.
- Produces: `build_pack(root, changed_files, import_graph, blueprint, budget_chars=40000) -> str` — a `CONTEXT` block: each changed source file's post-change content (per-file cap 8000 chars, truncation marked), up to 3 consumer files' anchor excerpts, and the blueprint slice for touched components. Honors a hard char budget with an explicit omission trailer.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_evidence_pack.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import evidence_pack as ep  # noqa: E402


def test_pack_includes_changed_file_contents(tmp_path):
    (tmp_path / "svc.py").write_text("def cost():\n    return billable * 0.12\n")
    pack = ep.build_pack(tmp_path, ["svc.py"], {}, {})
    assert "svc.py" in pack and "return billable * 0.12" in pack
    assert "CONTEXT" in pack


def test_pack_truncates_large_file_with_marker(tmp_path):
    (tmp_path / "big.py").write_text("x = 1\n" * 5000)  # ~30k chars
    pack = ep.build_pack(tmp_path, ["big.py"], {}, {}, budget_chars=40000)
    assert "[truncated" in pack


def test_pack_budget_trailer_when_over(tmp_path):
    for i in range(20):
        (tmp_path / f"f{i}.py").write_text("y = 2\n" * 2000)  # ~12k each
    files = [f"f{i}.py" for i in range(20)]
    pack = ep.build_pack(tmp_path, files, {}, {}, budget_chars=40000)
    assert len(pack) <= 40000 + 500  # budget + trailer slack
    assert "evidence truncated:" in pack


def test_pack_includes_blueprint_slice_for_touched_component(tmp_path):
    (tmp_path / "svc.py").write_text("x=1\n")
    bp = {"components": {"components": [
        {"name": "svc", "location": "svc.py", "responsibility": "does the thing",
         "key_interfaces": ["cost()"]}]}}
    pack = ep.build_pack(tmp_path, ["svc.py"], {}, bp)
    assert "does the thing" in pack


def test_pack_missing_file_is_skipped(tmp_path):
    pack = ep.build_pack(tmp_path, ["gone.py"], {}, {})
    assert isinstance(pack, str)  # no crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_evidence_pack.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'evidence_pack'`.

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/evidence_pack.py
"""Deterministic evidence pack: source excerpts + blueprint slice for the
reviewers, so the CI LLM path (which has no tools) still reviews code in context.
Pure aside from reading files under root. No LLM."""
from __future__ import annotations
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from reachability import consumers  # noqa: E402

_PER_FILE = 8000


def _read(root, rel, cap=_PER_FILE):
    try:
        text = (Path(root) / rel).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(text) > cap:
        return text[:cap] + f"\n[truncated {len(text) - cap} chars]\n"
    return text


def _blueprint_slice(blueprint, changed_files):
    comps = ((blueprint or {}).get("components") or {}).get("components") or []
    out = []
    changed = set(changed_files)
    for c in comps:
        loc = str(c.get("location", ""))
        if loc and any(cf == loc or cf.startswith(loc.rstrip("/") + "/") for cf in changed):
            ki = ", ".join(c.get("key_interfaces", []) or [])
            out.append(f"- {c.get('name')}: {c.get('responsibility','')} [interfaces: {ki}]")
    return "\n".join(out)


def build_pack(root, changed_files, import_graph, blueprint, budget_chars=40000) -> str:
    parts = ["CONTEXT (read-only source excerpts + architecture slice):"]
    used = len(parts[0])
    omitted = 0
    seen_consumers = set()
    for rel in changed_files:
        body = _read(root, rel)
        if body is None:
            continue
        block = f"\n--- {rel} ---\n{body}"
        if used + len(block) > budget_chars:
            omitted += 1
            continue
        parts.append(block); used += len(block)
        for cons in (consumers(import_graph, rel) or [])[:3]:
            if cons in seen_consumers or cons in changed_files:
                continue
            seen_consumers.add(cons)
            cbody = _read(root, cons, cap=1600)
            if cbody is None:
                continue
            cblock = f"\n--- consumer: {cons} ---\n{cbody}"
            if used + len(cblock) > budget_chars:
                omitted += 1; continue
            parts.append(cblock); used += len(cblock)
    bslice = _blueprint_slice(blueprint, changed_files)
    if bslice and used + len(bslice) + 40 <= budget_chars:
        parts.append("\nARCHITECTURE (touched components):\n" + bslice)
    if omitted:
        parts.append(f"\n[[evidence truncated: {omitted} file(s) omitted for budget]]")
    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_evidence_pack.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/evidence_pack.py tests/test_evidence_pack.py
git commit -m "feat(review): deterministic evidence pack (P0a)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Behavioral reviewer — evidence + N passes (P1 input)

**Files:**
- Modify: `archie/standalone/behavioral_review.py`
- Test: `tests/test_behavioral_review.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `build_prompt(diff_text, consumer_map, intent=None, evidence="")` (evidence appended as a CONTEXT section); `review(root, diff_text, import_graph, changed_files, run=None, intent=None, evidence="", passes=1)` — runs the prompt `passes` times and returns the concatenated findings (duplicates expected; merged later by `finding_merge`).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_behavioral_review.py
def test_build_prompt_includes_evidence():
    import behavioral_review as br
    p = br.build_prompt("diff --git a b", {}, intent=None, evidence="CONTEXT: def f(): ...")
    assert "CONTEXT: def f(): ..." in p


def test_review_runs_passes_times():
    import behavioral_review as br
    calls = {"n": 0}

    def fake_run(prompt, root, verifier, **kw):
        calls["n"] += 1
        return '{"findings":[{"problem_statement":"bug","file":"a.py","line":3,'\
               '"falsification":"prove","confidence":0.7}]}'

    out = br.review(".", "diff", {}, ["a.py"], run=fake_run, passes=3)
    assert calls["n"] == 3          # one call per pass
    assert len(out) == 3            # findings from all passes (merge happens later)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_behavioral_review.py -q`
Expected: FAIL — `build_prompt() got an unexpected keyword argument 'evidence'`.

- [ ] **Step 3: Write minimal implementation**

Edit `build_prompt` to accept `evidence=""` and append it; edit `review` to accept `evidence=""`, `passes=1` and loop. Replace the two functions:

```python
def build_prompt(diff_text: str, consumer_map: dict, intent=None, evidence="") -> str:
    prefix = ""
    if intent:
        _pp = str(Path(__file__).parent)
        if _pp not in sys.path:
            sys.path.insert(0, _pp)
        from intent import intent_brief  # noqa: E402
        brief = intent_brief(intent)
        if brief:
            prefix = ("INTENDED CHANGE (review whether the diff correctly and safely achieves this, "
                      "and flag where it does not):\n" + brief + "\n\n")
    radius = "\n".join(f"{f} -> {', '.join(c)}" for f, c in consumer_map.items())
    ctx = f"\n\n{evidence}" if evidence else ""
    return (
        prefix
        + f"{_SYSTEM}\n\nDIFF:\n{diff_text}\n\n"
        f"BLAST RADIUS (changed file -> consumers):\n{radius}{ctx}\n\n"
        "Each finding needs: problem_statement, file, line, assumptions[], "
        "evidence[], falsification, confidence(0-1), kind(behavioral_break)."
    )


def review(root, diff_text, import_graph, changed_files, run=None, intent=None,
           evidence="", passes=1) -> list[dict]:
    if run is None:
        run = run_verifier   # call-time global lookup → monkeypatch works
    cmap = {cf: consumers(import_graph, cf) for cf in changed_files}
    prompt = build_prompt(diff_text, cmap, intent=intent, evidence=evidence)
    out = []
    for _ in range(max(1, passes)):
        out += parse_findings(run(prompt, Path(root), "claude") or "")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_behavioral_review.py -q`
Expected: PASS (all, including the two new tests).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/behavioral_review.py tests/test_behavioral_review.py
git commit -m "feat(review): behavioral reviewer accepts evidence + N passes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Finding merge — union + dedup + agreement confidence (P1)

**Files:**
- Create: `archie/standalone/finding_merge.py`
- Test: `tests/test_finding_merge.py`

**Interfaces:**
- Consumes: `evidence_schema.coerce_confidence`.
- Produces: `merge(findings, passes=1) -> list[dict]` — groups by `(file, kind)` + ≥60% token-Jaccard on `problem_statement`; keeps one representative per group; sets `confidence = max(member confidences, appearances/passes)`. Fewer, agreement-weighted findings.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_finding_merge.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import finding_merge as fm  # noqa: E402


def _f(file, stmt, conf, kind="behavioral_break"):
    return {"kind": kind, "confidence": conf, "problem_statement": stmt,
            "anchor": {"file": file, "line": 1}}


def test_two_agreeing_passes_boost_confidence():
    a = _f("a.py", "null deref on billable_steps", 0.4)
    b = _f("a.py", "null deref when billable_steps is missing", 0.4)  # paraphrase
    out = fm.merge([a, b], passes=2)
    assert len(out) == 1
    assert out[0]["confidence"] >= 0.9   # 2/2 agreement → ~1.0


def test_single_pass_finding_kept_distinct():
    a = _f("a.py", "unbounded loop over rows", 0.8)
    b = _f("b.py", "missing index on user_id", 0.8)
    out = fm.merge([a, b], passes=2)
    assert len(out) == 2


def test_low_agreement_stays_low_confidence():
    a = _f("a.py", "maybe a race in the cache write", 0.3)
    out = fm.merge([a], passes=2)   # 1/2 agreement
    assert out[0]["confidence"] < 0.6   # renders as a "possible issue"


def test_empty():
    assert fm.merge([], passes=2) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_finding_merge.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'finding_merge'`.

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/finding_merge.py
"""Union + dedup + agreement-weighted confidence for review findings. Two passes
that surface the same finding boost its confidence; a lone hunch stays advisory.
Pure. Reuses the token overlap idea from story_synthesize."""
from __future__ import annotations
import re
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from evidence_schema import coerce_confidence  # noqa: E402

_BREAK_KINDS = ("behavioral_break", "conformance_break")


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 3}


def _same(a, b):
    if (a["anchor"].get("file"), a.get("kind")) != (b["anchor"].get("file"), b.get("kind")):
        return False
    ta, tb = _tokens(a.get("problem_statement")), _tokens(b.get("problem_statement"))
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.6


def merge(findings, passes=1) -> list:
    groups = []  # each: {"rep": finding, "count": int, "maxconf": float}
    for f in findings or []:
        placed = False
        for g in groups:
            if _same(g["rep"], f):
                g["count"] += 1
                g["maxconf"] = max(g["maxconf"], coerce_confidence(f.get("confidence")))
                placed = True
                break
        if not placed:
            groups.append({"rep": f, "count": 1,
                           "maxconf": coerce_confidence(f.get("confidence"))})
    out = []
    for g in groups:
        rep = dict(g["rep"])
        conf = g["maxconf"]
        if rep.get("kind") in _BREAK_KINDS:
            conf = max(conf, min(1.0, g["count"] / max(1, passes)))
        rep["confidence"] = conf
        out.append(rep)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_finding_merge.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/finding_merge.py tests/test_finding_merge.py
git commit -m "feat(review): finding merge with agreement-weighted confidence (P1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Universal specialist lenses (P2)

**Files:**
- Create: `archie/standalone/universal_specialists.py`
- Test: `tests/test_universal_specialists.py`

**Interfaces:**
- Consumes: `agent_cli.run_verifier`, `evidence_schema` helpers, `behavioral_review.parse_findings`.
- Produces: `LENSES` (list of `(key, focus)`); `review_one(root, diff_text, evidence, intent, lens, run=None) -> list[dict]` (one focused pass, findings tagged `source="universal:<key>"`); `review_universal(root, diff_text, evidence, intent, run=None) -> list[dict]` (all four lenses, sequential — used standalone/in tests; the core schedules `review_one` per lens in parallel).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_universal_specialists.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import universal_specialists as us  # noqa: E402


def test_four_lenses_defined():
    keys = [k for k, _ in us.LENSES]
    assert keys == ["null-safety", "security", "resource-perf", "concurrency"]


def test_review_one_tags_source_and_focus():
    lens = us.LENSES[1]  # security
    seen = {}

    def fake_run(prompt, root, verifier, **kw):
        seen["prompt"] = prompt
        return '{"findings":[{"problem_statement":"sql injection","file":"a.py",'\
               '"line":2,"falsification":"prove","confidence":0.8}]}'

    out = us.review_one(".", "diff", "CTX", None, lens, run=fake_run)
    assert "security" in seen["prompt"].lower()
    assert out[0]["source"] == "universal:security"


def test_review_universal_runs_all_four():
    calls = {"n": 0}

    def fake_run(prompt, root, verifier, **kw):
        calls["n"] += 1
        return "{}"

    us.review_universal(".", "diff", "CTX", None, run=fake_run)
    assert calls["n"] == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_universal_specialists.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'universal_specialists'`.

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/universal_specialists.py
"""Lane-1 universal specialist lenses: four focused, blueprint-free bug hunts over
the diff + evidence pack. Each is a cheap haiku pass; findings flow through the
same gate as behavioral. Blind to intent-conformance beyond the shared brief."""
from __future__ import annotations
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from agent_cli import run_verifier  # noqa: E402
from behavioral_review import parse_findings  # noqa: E402

LENSES = [
    ("null-safety", "null-safety and error handling: null/None dereferences, "
                    "unhandled exceptions, silently-swallowed errors, wrong-result paths"),
    ("security", "security: injection, secrets in code, missing authz/authn, unsafe "
                 "deserialization, path traversal"),
    ("resource-perf", "resource & performance: N+1 queries, unbounded growth, leaked "
                      "handles/connections, missing pagination, accidental O(n^2)"),
    ("concurrency", "concurrency & state: races, shared mutable state, non-atomic "
                    "read-modify-write, ordering assumptions"),
]


def _prompt(diff_text, evidence, intent, focus):
    _pp = str(Path(__file__).parent)
    if _pp not in sys.path:
        sys.path.insert(0, _pp)
    from intent import intent_brief  # noqa: E402
    brief = intent_brief(intent) if intent else ""
    pre = (f"INTENDED CHANGE (context, not the review target):\n{brief}\n\n" if brief else "")
    ctx = f"\n\n{evidence}" if evidence else ""
    return (
        pre
        + f"You are a code reviewer focused ONLY on {focus}. Report only issues in "
        "this category INTRODUCED or worsened by the diff. Give a falsification test "
        "and anchor each to a changed line. Return JSON {\"findings\":[{"
        "\"problem_statement\":...,\"file\":...,\"line\":...,\"evidence\":[...],"
        "\"falsification\":...,\"confidence\":0.0,\"kind\":\"behavioral_break\"}]}."
        f"\n\nDIFF:\n{diff_text}{ctx}"
    )


def review_one(root, diff_text, evidence, intent, lens, run=None) -> list:
    if run is None:
        run = run_verifier
    key, focus = lens
    raw = run(_prompt(diff_text, evidence, intent, focus), Path(root), "claude")
    out = parse_findings(raw or "")
    for f in out:
        f["source"] = f"universal:{key}"
    return out


def review_universal(root, diff_text, evidence, intent, run=None) -> list:
    out = []
    for lens in LENSES:
        out += review_one(root, diff_text, evidence, intent, lens, run=run)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_universal_specialists.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/universal_specialists.py tests/test_universal_specialists.py
git commit -m "feat(review): four universal specialist lenses (P2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Jailed tool loop in the API path (P0b)

**Files:**
- Modify: `archie/standalone/agent_cli.py`
- Test: `tests/test_agent_cli_tools.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `run_verifier(prompt, project_root, verifier, timeout=DEFAULT_TIMEOUT, model="haiku", tools=False)` — when `tools=True` AND the API path is taken (no `claude`/`codex` CLI, `ANTHROPIC_API_KEY` set), routes to `_run_api_tools(prompt, api_key, project_root, model, timeout, max_turns=6)` which runs a Messages-API tool-use loop offering `read_file(path, start_line, end_line)` and `grep(pattern, glob)`, both **jailed** to `project_root` (resolved path must stay inside root; `.git/` denied). Hard caps on turns and total tool bytes; on any cap or error, returns the last text (degrade, never raise). The `claude` CLI path already has Read/Grep/Glob and is unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_cli_tools.py
import json
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import agent_cli as ac  # noqa: E402


def test_tool_loop_reads_jailed_file_then_answers(tmp_path, monkeypatch):
    (tmp_path / "svc.py").write_text("line1\nline2\nSECRET_LOGIC\nline4\n")
    monkeypatch.setattr(ac.shutil, "which", lambda name: None)  # force API path
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    turns = {"n": 0}

    def fake_urlopen(req, timeout=0):
        turns["n"] += 1
        body = json.loads(req.data.decode())
        if turns["n"] == 1:
            payload = {"stop_reason": "tool_use", "content": [
                {"type": "tool_use", "id": "t1", "name": "read_file",
                 "input": {"path": "svc.py", "start_line": 1, "end_line": 4}}]}
        else:
            # confirm the tool result reached the model
            last = body["messages"][-1]["content"][0]["content"]
            assert "SECRET_LOGIC" in last
            payload = {"stop_reason": "end_turn",
                       "content": [{"type": "text", "text": "verified: found SECRET_LOGIC"}]}

        class R:
            def read(self_): return json.dumps(payload).encode()
            def __enter__(self_): return self_
            def __exit__(self_, *a): return False
        return R()

    monkeypatch.setattr(ac.urllib.request, "urlopen", fake_urlopen)
    out = ac.run_verifier("review this", tmp_path, "claude", tools=True)
    assert "SECRET_LOGIC" in out


def test_tool_loop_denies_path_escape(tmp_path, monkeypatch):
    monkeypatch.setattr(ac.shutil, "which", lambda name: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    def fake_urlopen(req, timeout=0):
        body = json.loads(req.data.decode())
        if body["messages"][-1]["role"] == "user" and isinstance(body["messages"][-1]["content"], str):
            payload = {"stop_reason": "tool_use", "content": [
                {"type": "tool_use", "id": "t1", "name": "read_file",
                 "input": {"path": "../../etc/passwd"}}]}
        else:
            last = body["messages"][-1]["content"][0]["content"]
            assert "denied" in last.lower() or "outside" in last.lower()
            payload = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "ok"}]}

        class R:
            def read(self_): return json.dumps(payload).encode()
            def __enter__(self_): return self_
            def __exit__(self_, *a): return False
        return R()

    monkeypatch.setattr(ac.urllib.request, "urlopen", fake_urlopen)
    out = ac.run_verifier("go", tmp_path, "claude", tools=True)
    assert out == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_agent_cli_tools.py -q`
Expected: FAIL — `run_verifier() got an unexpected keyword argument 'tools'`.

- [ ] **Step 3: Write minimal implementation**

Read `agent_cli.py` first. Add `_TOOLS`, `_exec_tool`, and `_run_api_tools` near `_run_api`, and thread `tools=False` through `run_verifier`. The API path currently is `key = os.environ.get("ANTHROPIC_API_KEY"); if key: return _run_api(prompt, key, timeout, model=model)` — branch on `tools` there.

```python
# add near _run_api in agent_cli.py
_TOOLS = [
    {"name": "read_file", "description": "Read lines from a file in the repo.",
     "input_schema": {"type": "object", "properties": {
         "path": {"type": "string"}, "start_line": {"type": "integer"},
         "end_line": {"type": "integer"}}, "required": ["path"]}},
    {"name": "grep", "description": "Regex-search the repo; returns matching path:line.",
     "input_schema": {"type": "object", "properties": {
         "pattern": {"type": "string"}, "glob": {"type": "string"}},
         "required": ["pattern"]}},
]


def _safe_path(root, rel):
    root = Path(root).resolve()
    try:
        p = (root / rel).resolve()
    except Exception:
        return None
    if root not in p.parents and p != root:
        return None
    if ".git" in p.parts:
        return None
    return p


def _exec_tool(root, name, args):
    if name == "read_file":
        p = _safe_path(root, str(args.get("path", "")))
        if p is None or not p.is_file():
            return "denied: path is outside the repo or not a file"
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return "denied: unreadable"
        s = max(1, int(args.get("start_line", 1)))
        e = min(len(lines), int(args.get("end_line", s + 199)))
        return "\n".join(f"{i}: {lines[i-1]}" for i in range(s, e + 1))[:8000]
    if name == "grep":
        import re as _re
        try:
            rx = _re.compile(str(args.get("pattern", "")))
        except Exception:
            return "denied: bad pattern"
        globp = str(args.get("glob", "*.py"))
        hits = []
        for f in Path(root).resolve().rglob(globp):
            if ".git" in f.parts or not f.is_file():
                continue
            try:
                for n, ln in enumerate(f.read_text("utf-8", errors="replace").splitlines(), 1):
                    if rx.search(ln):
                        hits.append(f"{f.relative_to(root)}:{n}: {ln.strip()[:200]}")
                        if len(hits) >= 40:
                            break
            except OSError:
                continue
            if len(hits) >= 40:
                break
        return "\n".join(hits) or "no matches"
    return "denied: unknown tool"


def _run_api_tools(prompt, api_key, project_root, model="haiku",
                   timeout=DEFAULT_TIMEOUT, max_turns=6, budget_bytes=60000) -> str:
    messages = [{"role": "user", "content": prompt}]
    spent = 0
    last_text = ""
    for _ in range(max_turns):
        body = json.dumps({
            "model": API_MODELS.get(model, API_MODEL),
            "max_tokens": 4096,
            "tools": _TOOLS,
            "messages": messages,
        }).encode()
        req = urllib.request.Request(
            ANTHROPIC_URL, data=body, method="POST",
            headers={"content-type": "application/json", "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
        except Exception:
            return last_text
        content = data.get("content") or []
        last_text = "".join(b.get("text", "") for b in content if b.get("type") == "text") or last_text
        if data.get("stop_reason") != "tool_use":
            return last_text
        messages.append({"role": "assistant", "content": content})
        results = []
        for b in content:
            if b.get("type") != "tool_use":
                continue
            if spent >= budget_bytes:
                out = "denied: tool budget exhausted"
            else:
                out = _exec_tool(project_root, b.get("name"), b.get("input") or {})
                spent += len(out)
            results.append({"type": "tool_result", "tool_use_id": b.get("id"), "content": out})
        messages.append({"role": "user", "content": results})
    return last_text
```

Then in `run_verifier`, change the signature and the API branch:

```python
def run_verifier(prompt: str, project_root: Path, verifier: str,
                 timeout: int = DEFAULT_TIMEOUT, model: str = "haiku",
                 tools: bool = False) -> str:
    if verifier == "codex" and shutil.which("codex"):
        return _run_codex(prompt, project_root, timeout)
    if shutil.which("claude"):
        return _run_claude(prompt, project_root, timeout, model=model)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        if tools:
            return _run_api_tools(prompt, key, project_root, model=model, timeout=timeout)
        return _run_api(prompt, key, timeout, model=model)
    return ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_agent_cli_tools.py tests/test_agent_cli.py tests/test_agent_cli_api.py -q`
Expected: PASS (the 2 new tests + existing agent_cli tests still green).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/agent_cli.py tests/test_agent_cli_tools.py
git commit -m "feat(review): jailed read_file/grep tool loop in the API path (P0b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Invariant specialist verifies via the tool loop

**Files:**
- Modify: `archie/standalone/invariant_specialist.py`
- Test: `tests/test_invariant_specialist.py` (append)

**Interfaces:**
- Consumes: `run_verifier(..., tools=True)` (Task 5).
- Produces: `review_invariants` unchanged in signature, but its two `run(...)` calls (tracer, challenger) now pass `tools=True` so those roles can read the cited anchor files in CI. A monkeypatched `run` still works (extra kwarg accepted/ignored).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_invariant_specialist.py
def test_tracer_and_challenger_request_tools():
    tracer = json.dumps({"invariant_id": "inv-x", "verdict": "violated",
                         "file": "a.py", "line": 2})
    challenger = json.dumps({"invariant_id": "inv-x", "decision": "confirm_violation",
                             "final_verdict": "violated", "reason": "r",
                             "falsification": "f", "file": "a.py", "line": 2})
    seen = []

    def rec(prompt, root, verifier, model="haiku", tools=False, **kw):
        seen.append(tools)
        return tracer if "TRACER" in prompt and "CHALLENGER" not in prompt else challenger

    isp.review_invariants(".", "diff", [INV], run=rec)
    assert seen == [True, True]   # both roles asked for tools
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_invariant_specialist.py -q`
Expected: FAIL — `seen == [False, False]` (tools not requested).

- [ ] **Step 3: Write minimal implementation**

In `review_invariants`, add `tools=True` to both `run(...)` calls. Read the function first; the two calls currently look like `run(build_tracer_prompt(contract, diff_text), Path(root), "claude")` and `run(build_challenger_prompt(contract, tracer, diff_text), Path(root), "claude")`. Change each to append `, tools=True`:

```python
        traw = run(build_tracer_prompt(contract, diff_text), Path(root), "claude",
                   model=TRACER_MODEL, tools=True)
        ...
        craw = run(build_challenger_prompt(contract, tracer, diff_text), Path(root), "claude",
                   model=CHALLENGER_MODEL, tools=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_invariant_specialist.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/invariant_specialist.py tests/test_invariant_specialist.py
git commit -m "feat(review): invariant tracer/challenger verify via tool loop (P0b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Shared review core — parallel fan-out + merge (F3 + P1b)

**Files:**
- Create: `archie/standalone/review_core.py`
- Test: `tests/test_review_core.py`

**Interfaces:**
- Consumes: `evidence_pack.build_pack`, `behavioral_review.review`, `universal_specialists.LENSES`/`review_one`, `reconcile.review_edge_a`/`review_edge_c`/`review_conformance`, `invariant_specialist.review_invariants`, `selector.touched_context`, `finding_merge.merge`.
- Produces: `run_review(root, diff_text, changed_files, blueprint, import_graph, spec, run=None, passes=2, workers=4) -> list[dict]` — builds the evidence pack, fans out ALL reviewers in a thread pool (`ARCHIE_REVIEW_WORKERS` overrides `workers`; `ARCHIE_REVIEW_PASSES` overrides `passes`), then returns `finding_merge.merge(all_raw, passes)`. Pre-gate: the caller runs `editor_gate.gate` + verdict.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_review_core.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import review_core as rc  # noqa: E402


def test_run_review_fans_out_and_merges(tmp_path):
    (tmp_path / "a.py").write_text("def f():\n    return None.x\n")
    spec = {"acceptance_criteria": [{"id": "ac1", "text": "do the thing"}], "non_goals": []}
    bp = {"domain_invariants": []}

    def fake_run(prompt, root, verifier, **kw):
        # behavioral + universals emit one finding each; edge-A silent
        if "focused ONLY on" in prompt or "behavioral code reviewer" in prompt:
            return '{"findings":[{"problem_statement":"null deref","file":"a.py","line":2,'\
                   '"falsification":"prove","confidence":0.8}]}'
        return "{}"

    out = rc.run_review(tmp_path, "diff --git a/a.py b/a.py", ["a.py"], bp, {}, spec,
                        run=fake_run, passes=2, workers=2)
    # 2 behavioral passes + 4 universal lenses all found "null deref on a.py" → merged to 1
    files = {f["anchor"]["file"] for f in out}
    assert "a.py" in files
    nulls = [f for f in out if "null deref" in f.get("problem_statement", "")]
    assert len(nulls) == 1                     # union+dedup collapsed them
    assert nulls[0]["confidence"] >= 0.9       # high agreement


def test_run_review_serial_when_workers_env_1(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHIE_REVIEW_WORKERS", "1")
    (tmp_path / "a.py").write_text("x=1\n")
    out = rc.run_review(tmp_path, "diff", ["a.py"], {"domain_invariants": []}, {},
                        {"acceptance_criteria": []}, run=lambda *a, **k: "{}", passes=1)
    assert isinstance(out, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_review_core.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'review_core'`.

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/review_core.py
"""Shared review brain: evidence pack -> parallel fan-out -> merge. One core for
both the CI delivery review and the local sync review (F3). Returns merged raw
findings pre-gate; the caller runs editor_gate + verdict."""
from __future__ import annotations
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from evidence_pack import build_pack             # noqa: E402
from behavioral_review import review as behavioral_review_run  # noqa: E402
import universal_specialists as us               # noqa: E402
from reconcile import review_edge_a, review_edge_c, review_conformance  # noqa: E402
from invariant_specialist import review_invariants  # noqa: E402
from selector import touched_context             # noqa: E402
from finding_merge import merge                  # noqa: E402


def _pmap(thunks, workers):
    if workers <= 1:
        return [t() for t in thunks]
    out = [None] * len(thunks)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(t): i for i, t in enumerate(thunks)}
        for fut, i in futs.items():
            try:
                out[i] = fut.result()
            except Exception:
                out[i] = []
    return out


def run_review(root, diff_text, changed_files, blueprint, import_graph, spec,
               run=None, passes=2, workers=4) -> list:
    passes = int(os.environ.get("ARCHIE_REVIEW_PASSES", passes))
    workers = int(os.environ.get("ARCHIE_REVIEW_WORKERS", workers))
    evidence = build_pack(root, changed_files, import_graph, blueprint)
    ctx = touched_context(blueprint, changed_files)
    has_intent = bool(spec.get("acceptance_criteria") or spec.get("goals"))

    thunks = [
        lambda: review_edge_a(root, spec, diff_text, run=run),
        lambda: behavioral_review_run(root, diff_text, import_graph, changed_files,
                                      run=run, intent=spec, evidence=evidence, passes=passes),
    ]
    for lens in us.LENSES:
        thunks.append(lambda lens=lens: us.review_one(root, diff_text, evidence, spec, lens, run=run))
    if has_intent:
        thunks.append(lambda: review_edge_c(root, spec,
                      (blueprint.get("domain_invariants") or []), run=run))
    if ctx["invariants"]:
        thunks.append(lambda: review_invariants(root, diff_text, ctx["invariants"], run=run))
    if ctx["decisions"]:
        thunks.append(lambda: review_conformance(root, diff_text, [], ctx["decisions"],
                      run=run, intent=spec))

    raw = []
    for group in _pmap(thunks, workers):
        raw += (group or [])
    return merge(raw, passes=passes)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_review_core.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/review_core.py tests/test_review_core.py
git commit -m "feat(review): shared review core — parallel fan-out + merge (F3, P1b)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Wire delivery_review to the core + truncation disclosure

**Files:**
- Modify: `archie/standalone/delivery_review.py`
- Test: `tests/test_delivery_review.py` (append)

**Interfaces:**
- Consumes: `review_core.run_review`.
- Produces: `run_pr_gate` collects `raw` from `review_core.run_review(...)` instead of the inline six-reviewer block; if the diff was truncated at `MAX_DIFF_CHARS`, the verdict header discloses it. `render_verdict` header gains a truncation note when `spec["diff_truncated"]` is set.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_delivery_review.py
def test_render_verdict_discloses_diff_truncation():
    import delivery_review as dr
    verdict = {"intent_completeness": "1/1", "breaks": 0, "possible_issues": 0, "conflicts": 0}
    spec = {"acceptance_criteria": [{"id": "ac1", "text": "x"}], "diff_truncated": True}
    body = dr.render_verdict(verdict, [], spec)
    assert "truncated" in body.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_delivery_review.py::test_render_verdict_discloses_diff_truncation -q`
Expected: FAIL — no truncation text.

- [ ] **Step 3: Write minimal implementation**

Read `delivery_review.py`. Two edits:

(a) In `render_verdict`, after the `> Grading against the task story ...` header line, add:
```python
    if spec.get("diff_truncated"):
        lines.append("> ⚠️ diff was truncated to the review budget — some files may be unreviewed.")
```

(b) In `run_pr_gate`, replace the inline reviewer fan-out (the `# 6. Run the reviewers` block: the `raw = []` through the end of the conformance `try/except`, lines ~329–362) with a single core call, and record truncation on the spec. Right after the diff is read (where `diff_text = (out or "")[:MAX_DIFF_CHARS]` is set), add `spec_truncated = len(out or "") > MAX_DIFF_CHARS`. Then replace the fan-out with:

```python
    # 6. Run the reviewers via the shared core (evidence pack + parallel fan-out + merge).
    raw = []
    try:
        from review_core import run_review
        if spec_truncated:
            spec["diff_truncated"] = True
        raw = run_review(root, diff_text, changed, blueprint, import_graph, spec)
    except Exception as e:
        print(f"[archie] review core failed ({e})")
```
(`spec_truncated` must be defined before this block; if the diff read failed, default it to `False`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_delivery_review.py tests/test_delivery_story_intent.py -q`
Expected: PASS (all; only the pre-known deferred failures elsewhere).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/delivery_review.py tests/test_delivery_review.py
git commit -m "feat(review): delivery review uses shared core + discloses diff truncation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Wire sync_review to the core

**Files:**
- Modify: `archie/standalone/sync_review.py`
- Test: `tests/test_sync_review.py` (create if absent; else append)

**Interfaces:**
- Consumes: `review_core.run_review`.
- Produces: `run_sync_review` builds its `raw` from `review_core.run_review(...)` (same fan-out as CI), then keeps its existing skip-gate, `editor_gate.gate`, and status-line verdict. Local and CI now share one reviewer brain.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync_review.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync_review as sr  # noqa: E402


def test_sync_review_uses_core(tmp_path, monkeypatch):
    (tmp_path / ".archie").mkdir()
    (tmp_path / "a.py").write_text("def f():\n    return None.x\n")
    called = {"core": False}
    import review_core
    real = review_core.run_review

    def spy(*a, **k):
        called["core"] = True
        return real(*a, **k)
    monkeypatch.setattr(review_core, "run_review", spy)

    def fake_run(prompt, root, verifier, **kw):
        return '{"findings":[{"problem_statement":"null deref","file":"a.py","line":2,'\
               '"falsification":"p","confidence":0.8}]}'

    sr.run_sync_review(tmp_path, "diff --git a/a.py b/a.py", ["a.py"],
                       {"acceptance_criteria": []}, {"domain_invariants": []}, {},
                       run=fake_run)
    assert called["core"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sync_review.py -q`
Expected: FAIL — core not called (sync still uses inline reviewers), or a signature mismatch. **Read `sync_review.run_sync_review` first** and adapt the test's call to its real signature (it takes `root, diff_text, changed_files, spec, blueprint, import_graph, run=...`) before implementing — keep the test asserting only that `review_core.run_review` was invoked.

- [ ] **Step 3: Write minimal implementation**

Read `sync_review.py`. Replace the inline reviewer calls (the `raw = review_edge_a(...)` through the conformance block, ~lines 95–112) with:
```python
    from review_core import run_review
    raw = run_review(root, diff_text, changed_files, blueprint, import_graph, spec, run=run)
```
Keep the surrounding skip-gate, `store`/`floors`, `gate(...)`, and verdict rendering exactly as they are. Remove now-unused direct imports only if they cause a lint error; leaving them is harmless.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sync_review.py tests/test_review_core.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/sync_review.py tests/test_sync_review.py
git commit -m "feat(review): sync review shares the review core (F3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Workflow concurrency + package sync + full green

**Files:**
- Modify: `archie/assets/workflows/archie-intent-review.yml` (+ copy to `npm-package/assets/workflows/`)
- Modify: `npm-package/bin/archie.mjs`
- Copy: new/changed standalone files into `npm-package/assets/`

**Interfaces:**
- Consumes: everything above.
- Produces: a synced package (`verify_sync.py` passes) with `concurrency` cancelling superseded runs and the four new scripts registered.

- [ ] **Step 1: Add the concurrency block**

Edit `archie/assets/workflows/archie-intent-review.yml` — insert directly after the `permissions:` block (before `jobs:`):
```yaml
concurrency:
  group: archie-review-${{ github.event.pull_request.number }}
  cancel-in-progress: true
```
Copy it to the mirror: `cp archie/assets/workflows/archie-intent-review.yml npm-package/assets/workflows/archie-intent-review.yml`.

- [ ] **Step 2: Register the new scripts + sync standalone mirror**

```bash
cp archie/standalone/evidence_pack.py        npm-package/assets/evidence_pack.py
cp archie/standalone/finding_merge.py        npm-package/assets/finding_merge.py
cp archie/standalone/universal_specialists.py npm-package/assets/universal_specialists.py
cp archie/standalone/review_core.py          npm-package/assets/review_core.py
cp archie/standalone/behavioral_review.py    npm-package/assets/behavioral_review.py
cp archie/standalone/agent_cli.py            npm-package/assets/agent_cli.py
cp archie/standalone/invariant_specialist.py npm-package/assets/invariant_specialist.py
cp archie/standalone/delivery_review.py      npm-package/assets/delivery_review.py
cp archie/standalone/sync_review.py          npm-package/assets/sync_review.py
```
Then edit `npm-package/bin/archie.mjs`: in the script-filename array, add `"evidence_pack.py", "finding_merge.py", "universal_specialists.py", "review_core.py"`.

- [ ] **Step 3: Verify sync**

Run: `python3 scripts/verify_sync.py`
Expected: `SYNC CHECK PASSED — <N> scripts, workflow + assets all in sync.` (Fix whatever it names if not.)

- [ ] **Step 4: Full suite**

Run:
```bash
python3 -m pytest tests/test_evidence_pack.py tests/test_finding_merge.py \
  tests/test_universal_specialists.py tests/test_agent_cli_tools.py tests/test_review_core.py \
  tests/test_sync_review.py tests/test_behavioral_review.py tests/test_invariant_specialist.py \
  tests/test_delivery_review.py tests/test_agent_cli.py tests/test_agent_cli_api.py -q
python3 -m pytest tests/ -q --continue-on-collection-errors 2>&1 | grep -E "passed|failed"
```
Expected: targeted subset all PASS; broad suite shows only the 3 known pre-existing failures (`churn_track`, `stop_nudges`, `codex_prefix`) + the ~19 tomllib collection errors.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(review): workflow concurrency + package sync + register v2 scripts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage (v2 §4–13, Wave 1 subset):**
- §4 P0a evidence pack → Task 1 (+ consumed in Tasks 2, 4, 7). ✓
- §5 P0b tool loop → Task 5 (loop + jail) + Task 6 (tracer/challenger opt-in). ✓ Verify-anchors rule is served by the tracer/challenger now being able to read files.
- §6 P1 N-pass + agreement → Task 2 (passes) + Task 3 (merge). ✓
- §6b P1b parallelization → Task 7 (`_pmap` + `ARCHIE_REVIEW_WORKERS`). ✓
- §7 P2 universal lenses → Task 4 (+ scheduled per-lens in Task 7). ✓
- §3/F3 one engine two mouths → Task 7 (core) + Tasks 8, 9 (both publishers call it). ✓
- §4 diff-truncation disclosure → Task 8. ✓
- §3 concurrency cancellation → Task 10. ✓
- Budget envs `ARCHIE_REVIEW_PASSES`/`WORKERS` → Task 7. ✓
- **Deferred to Wave 2 (not in this plan, by design):** P3 inline comments, P4 per-PR memory, P5 suggestions; and prompt-caching on the tool-loop static blocks (§13 lever) — noted as a fast-follow.

**Placeholder scan:** none — every code step shows complete code; wiring tasks name the exact function/lines to splice and instruct reading the current body first.

**Type consistency:** `build_pack(root, changed_files, import_graph, blueprint, budget_chars=40000)` matches its callers in Tasks 2/4-inputs and Task 7. `behavioral_review.review(..., evidence="", passes=1)` (Task 2) matches Task 7's call. `finding_merge.merge(findings, passes=1)` (Task 3) matches Task 7. `universal_specialists.review_one(root, diff_text, evidence, intent, lens, run=None)` + `LENSES` (Task 4) match Task 7's scheduling. `run_verifier(..., tools=False)` (Task 5) matches Task 6's `tools=True` calls. `review_core.run_review(root, diff_text, changed_files, blueprint, import_graph, spec, run=None, passes=2, workers=4)` (Task 7) matches Tasks 8 and 9.

**Implementer note:** Tasks 6, 8, 9 modify existing functions — **read the current body first** and splice the shown snippet into the real control flow (exact line numbers drift). Task 8/9 must preserve each publisher's existing gate + verdict; the core only replaces the fan-out.

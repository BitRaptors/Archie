# Branch Intent Capture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/archie-sync` writes a committed `.archie/intent.json` (agent-authored goals + acceptance criteria); the delivery review reads it at PR time, merges it with the PR body, and feeds it into the code review so behavioral + conformance review the diff *against the intent*.

**Architecture:** Add committed-intent read/write + a pure `merge_specs` to `intent.py`; a `sync.py write-intent` subcommand the sync agent calls; swap the PR gate + sync review to assemble intent from (committed file ⊕ PR body); then thread the assembled intent into the behavioral + conformance reviewers so the code review is intent-aware. Everything degrades gracefully — all sources optional, review stays non-blocking. **Linear ticket fetch is descoped from this plan** (a follow-up; see design §9).

**Tech Stack:** Zero-dependency Python 3.9+ stdlib. Tests: pytest, LLM mocked.

## Global Constraints

- **Zero runtime dependencies** beyond Python 3.9+ stdlib.
- **File sync:** edit `archie/standalone/*.py` first, copy to `npm-package/assets/*.py`; edit `archie/assets/workflow*/…` first, copy to the `npm-package/assets/…` mirror. Run `python3 scripts/verify_sync.py` before every commit — it must PASS.
- **Import convention (py3.9 — only `python3`, no `python`):** standalone modules import siblings BARE via guarded `sys.path.insert(0, str(Path(__file__).parent))` (`if _p not in sys.path`); tests use `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))` + bare `import <module>`. NEVER `from archie.standalone.X` (trips `tomllib` on 3.9). Run tests with `python3 -m pytest`.
- **LLM-injection convention:** orchestrators that call the LLM take `run=None` then `if run is None: run = run_verifier` (call-time lookup) so monkeypatch works.
- **Committed artifact:** `.archie/intent.json` must NOT be gitignored (the installer's gitignore block lists `.archie/*.py` etc., not `.archie/*.json` broadly — leave it committable).
- **Reuse existing:** `intent.normalize`, `intent.resolve`, `intent._RANK`, `intent.ticket_ids_from`, `evidence_schema.extract_json_obj`. Do not duplicate them.
- **Non-blocking:** `run_pr_gate` always exits 0; `write-intent` never crashes sync.
- Commit trailer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Task 1: Committed-intent read/write + `merge_specs` in `intent.py`

**Files:**
- Modify: `archie/standalone/intent.py` (append; `os`/`json`/`Path` already imported)
- Test: `tests/test_committed_intent.py`

**Interfaces:**
- Consumes: `intent._RANK` (module-level dict), `intent.normalize`.
- Produces: `INTENT_FILE = "intent.json"`; `merge_specs(*specs: dict) -> dict`; `load_committed_intent(root) -> dict | None`; `write_committed_intent(root, spec: dict) -> None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_committed_intent.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent as it  # noqa: E402


def test_merge_specs_unions_criteria_and_dedups():
    a = {"source": "sync", "confidence": "high", "goals": ["G1"],
         "acceptance_criteria": [{"id": "x", "text": "Tenant scoped"}], "ticket_ids": ["ARCH-1"], "raw": "plan"}
    b = {"source": "pr_body", "confidence": "medium", "goals": ["G1", "G2"],
         "acceptance_criteria": [{"id": "y", "text": "tenant scoped"}, {"id": "z", "text": "Rate limited"}],
         "ticket_ids": [], "raw": "body"}
    m = it.merge_specs(a, b)
    texts = [c["text"] for c in m["acceptance_criteria"]]
    assert texts == ["Tenant scoped", "Rate limited"]          # dedup by normalized text, order preserved
    assert m["acceptance_criteria"][0]["id"] == "ac1"          # ids reindexed
    assert m["goals"] == ["G1", "G2"] and m["ticket_ids"] == ["ARCH-1"]
    assert m["source"] == "sync"                               # highest _RANK wins (sync outranks pr_body)
    assert "plan" in m["raw"] and "body" in m["raw"]


def test_merge_specs_no_clobber_populated_by_empty():
    populated = {"source": "sync", "acceptance_criteria": [{"id": "a", "text": "Keep me"}], "goals": [], "raw": ""}
    empty = {"source": "pr_body", "acceptance_criteria": [], "goals": [], "raw": ""}
    m = it.merge_specs(populated, empty)
    assert [c["text"] for c in m["acceptance_criteria"]] == ["Keep me"]


def test_merge_specs_all_empty_returns_inferred():
    m = it.merge_specs(None, None)
    assert m["source"] == "inferred" and m["acceptance_criteria"] == []


def test_load_committed_intent_missing_and_malformed(tmp_path):
    assert it.load_committed_intent(tmp_path) is None          # no file
    ad = tmp_path / ".archie"; ad.mkdir()
    (ad / "intent.json").write_text("{ not json")
    assert it.load_committed_intent(tmp_path) is None          # malformed -> None
    (ad / "intent.json").write_text('["a","b"]')
    assert it.load_committed_intent(tmp_path) is None          # non-dict -> None


def test_write_committed_intent_merges_and_roundtrips(tmp_path):
    it.write_committed_intent(tmp_path, {"source": "sync", "acceptance_criteria": [{"id": "a", "text": "First"}],
                                         "goals": [], "ticket_ids": [], "raw": "one"})
    it.write_committed_intent(tmp_path, {"source": "sync", "acceptance_criteria": [{"id": "b", "text": "Second"}],
                                         "goals": [], "ticket_ids": [], "raw": "two"})
    got = it.load_committed_intent(tmp_path)
    assert [c["text"] for c in got["acceptance_criteria"]] == ["First", "Second"]   # merged across writes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_committed_intent.py -v`
Expected: FAIL (`AttributeError: module 'intent' has no attribute 'merge_specs'`).

- [ ] **Step 3: Append the implementation to `archie/standalone/intent.py`**

First, update the existing `_RANK` dict so the agent-authored committed intent (`source: "sync"`) is high-trust — change the line
`_RANK = {"inferred": 0, "commits": 1, "pr_body": 2, "prompt": 2, "linear": 3}`
to:
`_RANK = {"inferred": 0, "commits": 1, "pr_body": 2, "prompt": 2, "sync": 3, "linear": 3}`

Then append:
```python
# --- append to archie/standalone/intent.py ---
INTENT_FILE = "intent.json"


def merge_specs(*specs) -> dict:
    """Union acceptance_criteria (dedup by normalized text, ids reindexed), goals,
    and ticket_ids across specs. Highest-_RANK source label wins. None entries ignored.
    Never clobbers a populated field with an empty one (union only)."""
    specs = [s for s in specs if s]
    if not specs:
        return normalize("", source="inferred", ticket_ids=[])
    crit, seen = [], set()
    for s in specs:
        for c in (s.get("acceptance_criteria") or []):
            text = (c.get("text") if isinstance(c, dict) else str(c)) or ""
            key = text.strip().lower()
            if key and key not in seen:
                seen.add(key)
                crit.append({"id": f"ac{len(crit) + 1}", "text": text})
    goals, gseen = [], set()
    for s in specs:
        for g in (s.get("goals") or []):
            k = str(g).strip().lower()
            if k and k not in gseen:
                gseen.add(k)
                goals.append(str(g))
    tickets = []
    for s in specs:
        for t in (s.get("ticket_ids") or []):
            if t and t not in tickets:
                tickets.append(t)
    best = max(specs, key=lambda s: _RANK.get(s.get("source"), 0))
    raw = "\n\n".join(s.get("raw") for s in specs if s.get("raw"))
    return {
        "source": best.get("source", "inferred"),
        "confidence": best.get("confidence", "low"),
        "ticket_ids": tickets,
        "goals": goals,
        "acceptance_criteria": crit,
        "raw": raw,
    }


def load_committed_intent(root) -> dict:
    """Read .archie/intent.json -> spec dict, or None if absent/malformed/non-dict."""
    p = Path(root) / ".archie" / INTENT_FILE
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def write_committed_intent(root, spec: dict) -> None:
    """Merge `spec` over any existing .archie/intent.json and write atomically."""
    archie = Path(root) / ".archie"
    archie.mkdir(parents=True, exist_ok=True)
    existing = load_committed_intent(root)
    merged = merge_specs(existing, spec) if existing else spec
    p = archie / INTENT_FILE
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2))
    os.replace(tmp, p)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_committed_intent.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/intent.py npm-package/assets/intent.py
python3 scripts/verify_sync.py
git add archie/standalone/intent.py npm-package/assets/intent.py tests/test_committed_intent.py
git commit -m "feat(intent): committed intent file read/write + merge_specs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `sync.py write-intent` subcommand

**Files:**
- Modify: `archie/standalone/sync.py` (add `cmd_write_intent`, register `write-intent` in dispatch + `_usage`)
- Test: `tests/test_sync_write_intent.py`

**Interfaces:**
- Consumes: `intent.write_committed_intent` / `intent.INTENT_FILE` (bare import).
- Produces: `cmd_write_intent(root: Path, input_file: str | None) -> int` (always returns 0); CLI `python3 sync.py write-intent <root> <json-file>`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync_write_intent.py
import sys, json
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync  # noqa: E402
import intent as it  # noqa: E402


def test_write_intent_writes_committed_file(tmp_path):
    payload = tmp_path / "spec.json"
    payload.write_text(json.dumps({"source": "sync", "goals": ["G"],
        "acceptance_criteria": [{"id": "a", "text": "Scoped"}], "ticket_ids": ["ARCH-9"], "raw": "plan"}))
    rc = sync.cmd_write_intent(tmp_path, str(payload))
    assert rc == 0
    got = it.load_committed_intent(tmp_path)
    assert got["acceptance_criteria"][0]["text"] == "Scoped" and got["ticket_ids"] == ["ARCH-9"]


def test_write_intent_bad_payload_leaves_file_intact(tmp_path):
    it.write_committed_intent(tmp_path, {"source": "sync", "acceptance_criteria": [{"id": "a", "text": "Keep"}],
                                         "goals": [], "ticket_ids": [], "raw": ""})
    bad = tmp_path / "bad.json"; bad.write_text("{ not json")
    rc = sync.cmd_write_intent(tmp_path, str(bad))
    assert rc == 0
    assert it.load_committed_intent(tmp_path)["acceptance_criteria"][0]["text"] == "Keep"  # unchanged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sync_write_intent.py -v`
Expected: FAIL (`AttributeError: module 'sync' has no attribute 'cmd_write_intent'`).

- [ ] **Step 3: Add `cmd_write_intent` and register it**

Add the function to `archie/standalone/sync.py` (near the other `cmd_*` functions):
```python
def cmd_write_intent(root, input_file) -> int:
    """Merge a JSON intent spec (from input_file) into .archie/intent.json. Non-crashing:
    a bad payload logs and leaves any existing file untouched. Always returns 0."""
    import sys as _sys
    _p = str(Path(__file__).parent)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
    from intent import write_committed_intent, INTENT_FILE  # noqa: E402
    if not input_file or not Path(input_file).exists():
        print("[archie] write-intent: no payload file; .archie/intent.json unchanged", file=sys.stderr)
        return 0
    try:
        spec = json.loads(Path(input_file).read_text())
    except Exception as e:
        print(f"[archie] write-intent: bad payload ({e}); .archie/intent.json unchanged", file=sys.stderr)
        return 0
    if not isinstance(spec, dict):
        print("[archie] write-intent: payload not an object; unchanged", file=sys.stderr)
        return 0
    write_committed_intent(root, spec)
    print(f"[archie] intent written to .archie/{INTENT_FILE}")
    return 0
```

In the `main`/dispatch block (where other `cmd == "..."` branches live), add:
```python
    if cmd == "write-intent":
        return cmd_write_intent(root, argv[3] if len(argv) > 3 else None)
```
And add one line to `_usage()`:
```python
    print("  python3 sync.py write-intent  /path/to/repo  spec.json          (merge branch intent into .archie/intent.json)", file=sys.stderr)
```
(`json`, `sys`, `Path` are already imported in sync.py.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sync_write_intent.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/sync.py npm-package/assets/sync.py
python3 scripts/verify_sync.py
git add archie/standalone/sync.py npm-package/assets/sync.py tests/test_sync_write_intent.py
git commit -m "feat(sync): write-intent subcommand writes committed .archie/intent.json

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Sync review reads the committed intent

**Files:**
- Modify: `archie/standalone/sync_review.py` (the intent-load block, ~lines 73-77)
- Test: `tests/test_sync_review.py` (add one test)

**Interfaces:**
- Consumes: `intent.load_committed_intent` (bare import).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_sync_review.py (sr already imported)
def test_sync_review_uses_committed_intent(tmp_path, monkeypatch):
    import intent as it
    it.write_committed_intent(tmp_path, {"source": "sync", "goals": [],
        "acceptance_criteria": [{"id": "a", "text": "Scoped"}], "ticket_ids": [], "raw": "plan"})
    seen = {}
    monkeypatch.setattr(sr, "review_edge_a",
                        lambda root, spec, diff, run=None: seen.setdefault("crit", spec.get("acceptance_criteria")) or [])
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])
    BP = {"domain_invariants": [], "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": []}
    sr.run_sync_review(str(tmp_path), "feature/x", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {})
    assert seen.get("crit") and seen["crit"][0]["text"] == "Scoped"   # committed criteria reached edge-A
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sync_review.py::test_sync_review_uses_committed_intent -v`
Expected: FAIL (edge-A saw empty criteria; `seen["crit"]` is empty/None).

- [ ] **Step 3: Wire the committed intent in**

In `archie/standalone/sync_review.py`, extend the existing bare import from `intent`:
```python
from intent import load_branch_record, normalize, save_branch_record, load_committed_intent  # noqa: E402
```
Change the spec-load line (currently `spec = load_branch_record(archie_dir, branch) or normalize("", ...)`) to prefer the committed file:
```python
    spec = (load_committed_intent(root)
            or load_branch_record(archie_dir, branch)
            or normalize("", source="inferred", ticket_ids=[]))
```
(`root` is the function's root arg; `archie_dir` is already defined just above.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_sync_review.py -v`
Expected: PASS (all, incl. the new test; existing skip-gate test still green).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/sync_review.py npm-package/assets/sync_review.py
python3 scripts/verify_sync.py
git add archie/standalone/sync_review.py npm-package/assets/sync_review.py tests/test_sync_review.py
git commit -m "feat(review): sync review reads committed .archie/intent.json

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: PR-gate intent assembly (committed file ⊕ PR body)

**Files:**
- Modify: `archie/standalone/delivery_review.py` (`run_pr_gate` intent block, ~lines 192-212)
- Test: `tests/test_delivery_review.py` (add tests)

**Interfaces:**
- Consumes: `intent.load_committed_intent`, `intent.merge_specs`, `intent.normalize`, `intent.resolve`, `intent.ticket_ids_from` (all bare imports).
- Produces: a pure helper `assemble_pr_intent(root, pr_meta, env, *, run=None) -> dict` so the merge logic is unit-testable without the full gate.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_delivery_review.py  (dr already imported)
def test_assemble_pr_intent_prefers_committed_file_no_resolve(tmp_path):
    import intent as it
    it.write_committed_intent(tmp_path, {"source": "sync", "goals": [],
        "acceptance_criteria": [{"id": "a", "text": "From file"}], "ticket_ids": [], "raw": "plan"})
    called = {"resolve": 0}
    spec = dr.assemble_pr_intent(tmp_path, {"head_ref": "b", "title": "T", "body": "body"}, {},
                                 run=lambda *a, **k: called.__setitem__("resolve", called["resolve"] + 1) or "{}")
    assert [c["text"] for c in spec["acceptance_criteria"]] == ["From file"]
    assert called["resolve"] == 0                                  # criteria already present -> no LLM resolve


def test_assemble_pr_intent_body_only_resolves(tmp_path):
    # no committed file -> resolve() runs on the PR body to produce criteria
    payload = '{"acceptance_criteria":[{"id":"t","text":"From body"}]}'
    spec = dr.assemble_pr_intent(tmp_path, {"head_ref": "b", "title": "Add export", "body": "tenant scoped"}, {},
                                 run=lambda *a, **k: payload)
    assert [c["text"] for c in spec["acceptance_criteria"]] == ["From body"]


def test_assemble_pr_intent_all_empty(tmp_path):
    spec = dr.assemble_pr_intent(tmp_path, {"head_ref": "b", "title": "", "body": ""}, {}, run=lambda *a, **k: "{}")
    assert spec.get("acceptance_criteria") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_delivery_review.py -k assemble -v`
Expected: FAIL (`AttributeError: module 'delivery_review' has no attribute 'assemble_pr_intent'`).

- [ ] **Step 3: Add `assemble_pr_intent` and call it from `run_pr_gate`**

Add the helper to `archie/standalone/delivery_review.py`:
```python
def assemble_pr_intent(root, pr_meta, env, *, run=None):
    """Merge intent from committed .archie/intent.json ⊕ PR title/body.
    resolve() runs ONLY if the merged spec still has no acceptance_criteria."""
    import sys as _sys
    _p = str(Path(__file__).parent)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
    from intent import (load_committed_intent, merge_specs, normalize,
                        resolve, ticket_ids_from)  # noqa: E402

    file_spec = load_committed_intent(root)
    title = pr_meta.get("title") or ""
    body = pr_meta.get("body") or env.get("ARCHIE_PR_BODY", "")
    branch = pr_meta.get("head_ref") or ""
    pr_text = (title + "\n\n" + body).strip()
    tickets = ticket_ids_from(branch, pr_text, [])
    pr_spec = normalize(pr_text, "pr_body", tickets) if pr_text else None

    spec = merge_specs(file_spec, pr_spec)
    if not spec.get("acceptance_criteria") and spec.get("raw"):
        try:
            spec = resolve(spec, run=run)
        except Exception as e:
            print(f"[archie] intent resolve failed ({e})")
    return spec
```
In `run_pr_gate`, replace the whole `# 4. Resolve intent ...` try/except block (the one that builds `spec` from `ticket_ids_from`/`normalize`/`load_branch_record`) with:
```python
    # 4. Assemble intent: committed .archie/intent.json ⊕ PR title/body.
    try:
        spec = assemble_pr_intent(root, pr_meta, env)
    except Exception as e:
        print(f"[archie] intent assembly failed ({e})")
        spec = {"acceptance_criteria": [], "goals": [], "confidence": "low"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_delivery_review.py -v`
Expected: PASS (all, incl. the 3 new tests; existing gate tests green).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/delivery_review.py npm-package/assets/delivery_review.py
python3 scripts/verify_sync.py
git add archie/standalone/delivery_review.py npm-package/assets/delivery_review.py tests/test_delivery_review.py
git commit -m "feat(pr-gate): assemble intent from committed file + PR body

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Wire the capture step into `/archie-sync`

**Files:**
- Modify: `archie/assets/workflow/sync/SKILL.md` (add the intent-capture step) → copy to `npm-package/assets/workflow/sync/SKILL.md`
- Test: `tests/test_branch_intent_smoke.py`

**Interfaces:**
- Consumes: `sync.cmd_write_intent`, `intent.load_committed_intent` (end-to-end smoke).

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_branch_intent_smoke.py
import sys, json, subprocess
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent as it  # noqa: E402


def test_write_intent_cli_roundtrip(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"source": "sync", "goals": ["G"],
        "acceptance_criteria": [{"id": "a", "text": "Scoped"}], "ticket_ids": ["ARCH-9"], "raw": "plan"}))
    rc = subprocess.run(["python3", str(_STANDALONE / "sync.py"), "write-intent", str(tmp_path), str(spec)],
                        capture_output=True, text=True)
    assert rc.returncode == 0
    got = it.load_committed_intent(tmp_path)
    assert got["acceptance_criteria"][0]["text"] == "Scoped"


def test_sync_skill_has_intent_capture_step():
    skill = (Path(__file__).resolve().parent.parent / "archie" / "assets" / "workflow"
             / "sync" / "SKILL.md").read_text()
    assert "write-intent" in skill and ".archie/intent.json" in skill
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_branch_intent_smoke.py -v`
Expected: FAIL on `test_sync_skill_has_intent_capture_step` (`write-intent` not in the SKILL yet). The CLI roundtrip test should already pass (Task 2 shipped the subcommand).

- [ ] **Step 3: Add the intent-capture step to the sync SKILL**

In `archie/assets/workflow/sync/SKILL.md`, add this step (before the commit/fold step):
```markdown
### Capture branch intent (for delivery review)

Synthesize this branch's intent from the task, plan, and conversation, then persist it so the
PR-time delivery review can grade against what you set out to build:

1. Write a JSON spec to a temp file with this shape (author `goals` and concrete, checkable
   `acceptance_criteria` directly; include `ticket_id` if applicable):
   `{"source":"sync","goals":[...],"acceptance_criteria":[{"id":"ac1","text":"..."}],"ticket_id":"ARCH-123","raw":"<goal + plan>"}`
2. Run: `python3 .archie/sync.py write-intent . /tmp/archie_intent_spec.json`
   (merges into the committed `.archie/intent.json`; re-running refines it).
3. Stage `.archie/intent.json` so it is committed with the branch.

If the intent is genuinely unknown, write `raw` only (or skip); the review degrades to PR-body intent.
```

- [ ] **Step 4: Copy to the npm mirror, run tests + sync**

```bash
cp archie/assets/workflow/sync/SKILL.md npm-package/assets/workflow/sync/SKILL.md
python3 -m pytest tests/test_branch_intent_smoke.py -v      # both pass now
python3 scripts/verify_sync.py                               # PASS
```
Expected: 2 passed; sync PASS.

- [ ] **Step 5: Commit**

```bash
git add archie/assets/workflow/sync/SKILL.md npm-package/assets/workflow/sync/SKILL.md tests/test_branch_intent_smoke.py
git commit -m "feat(sync): capture branch intent step writes committed .archie/intent.json

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Make the code review intent-aware (behavioral + conformance)

**Files:**
- Modify: `archie/standalone/intent.py` (append `intent_brief`)
- Modify: `archie/standalone/behavioral_review.py` (`build_prompt` + `review` accept `intent`)
- Modify: `archie/standalone/reconcile.py` (`build_conformance_prompt` + `review_conformance` accept `intent`)
- Modify: `archie/standalone/sync_review.py` + `archie/standalone/delivery_review.py` (pass the assembled `spec` through)
- Test: `tests/test_behavioral_review.py`, `tests/test_reconcile_edge_c.py`

**Interfaces:**
- Consumes: the assembled intent `spec` (from `assemble_pr_intent` in T4 / the committed spec in T3).
- Produces: `intent.intent_brief(spec) -> str`; `behavioral_review.build_prompt(diff_text, consumer_map, intent=None)`; `behavioral_review.review(root, diff_text, import_graph, changed_files, run=None, intent=None)`; `reconcile.build_conformance_prompt(diff_text, invariants, decisions, intent=None)`; `reconcile.review_conformance(root, diff_text, invariants, decisions, run=None, intent=None)`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_behavioral_review.py  (br already imported)
def test_build_prompt_includes_intent_and_is_backward_compatible():
    spec = {"goals": ["Add tenant scoping"], "acceptance_criteria": [{"id": "ac1", "text": "scoped by tenant"}]}
    p = br.build_prompt("diff", {"x.py": []}, intent=spec)
    assert "INTENDED CHANGE" in p and ("tenant scoping" in p or "scoped by tenant" in p)
    assert "INTENDED CHANGE" not in br.build_prompt("diff", {"x.py": []})   # no intent -> unchanged


def test_review_threads_intent_into_prompt(monkeypatch):
    captured = {}
    monkeypatch.setattr(br, "run_verifier",
                        lambda prompt, *a, **k: captured.setdefault("p", prompt) or '{"findings":[]}')
    br.review("/x", "diff", {}, ["x.py"], intent={"goals": ["G-goal"], "acceptance_criteria": []})
    assert "G-goal" in captured["p"]
```
```python
# add to tests/test_reconcile_edge_c.py  (rc already imported)
def test_conformance_prompt_includes_intent():
    p = rc.build_conformance_prompt("diff", [{"id": "inv1", "invariant": "tenant iso"}], [],
                                    intent={"goals": ["Add export"], "acceptance_criteria": []})
    assert "Add export" in p
    assert "INTENDED CHANGE" not in rc.build_conformance_prompt("diff", [], [])   # backward compat
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_behavioral_review.py -k intent tests/test_reconcile_edge_c.py -k intent -v`
Expected: FAIL (`build_prompt() got an unexpected keyword argument 'intent'`).

- [ ] **Step 3: Implement**

Append to `archie/standalone/intent.py`:
```python
def intent_brief(spec) -> str:
    """One short block summarizing the intended change, for code-review prompts. '' if empty."""
    if not spec:
        return ""
    lines = []
    goals = spec.get("goals") or []
    if goals:
        lines.append("Goals: " + "; ".join(str(g) for g in goals))
    for c in (spec.get("acceptance_criteria") or []):
        text = c.get("text") if isinstance(c, dict) else str(c)
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines).strip()
```
In `archie/standalone/behavioral_review.py`, add an `intent` param and prepend the brief. `build_prompt`:
```python
def build_prompt(diff_text, consumer_map, intent=None):
    prefix = ""
    if intent:
        _p = str(Path(__file__).parent)
        if _p not in sys.path:
            sys.path.insert(0, _p)
        from intent import intent_brief  # noqa: E402
        brief = intent_brief(intent)
        if brief:
            prefix = ("INTENDED CHANGE (review whether the diff correctly and safely achieves this, "
                      "and flag where it does not):\n" + brief + "\n\n")
    # ... existing body, but return: prefix + <existing returned string>
```
And `review`:
```python
def review(root, diff_text, import_graph, changed_files, run=None, intent=None):
    if run is None:
        run = run_verifier
    cmap = {cf: consumers(import_graph, cf) for cf in changed_files}
    raw = run(build_prompt(diff_text, cmap, intent=intent), Path(root), "claude")
    return parse_findings(raw or "")
```
In `archie/standalone/reconcile.py`, add `intent` to `build_conformance_prompt` (prepend the same brief block via `from intent import intent_brief`) and thread it through `review_conformance`:
```python
def review_conformance(root, diff_text, invariants, decisions, run=None, intent=None):
    if run is None:
        from agent_cli import run_verifier
        run = run_verifier
    if not (invariants or decisions):
        return []
    raw = run(build_conformance_prompt(diff_text, invariants, decisions, intent=intent), Path(root), "claude")
    return parse_conformance(raw or "")
```
In `archie/standalone/sync_review.py`, pass `intent=spec` to both calls:
```python
    raw += behavioral_review_run(root, diff_text, import_graph, changed_files, run=run, intent=spec)
    ...
    raw += review_conformance(root, diff_text, ctx["invariants"], ctx["decisions"], run=run, intent=spec)
```
In `archie/standalone/delivery_review.py` `run_pr_gate`, pass `intent=spec` to both the behavioral and conformance calls (the `spec` from `assemble_pr_intent`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_behavioral_review.py tests/test_reconcile_edge_c.py tests/test_sync_review.py tests/test_delivery_review.py -v`
Expected: PASS (new intent tests + all existing green — the `intent=None` default keeps old calls working).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/intent.py npm-package/assets/intent.py
cp archie/standalone/behavioral_review.py npm-package/assets/behavioral_review.py
cp archie/standalone/reconcile.py npm-package/assets/reconcile.py
cp archie/standalone/sync_review.py npm-package/assets/sync_review.py
cp archie/standalone/delivery_review.py npm-package/assets/delivery_review.py
python3 scripts/verify_sync.py
git add archie/standalone/intent.py archie/standalone/behavioral_review.py archie/standalone/reconcile.py \
        archie/standalone/sync_review.py archie/standalone/delivery_review.py npm-package/assets/*.py \
        tests/test_behavioral_review.py tests/test_reconcile_edge_c.py
git commit -m "feat(review): intent-aware code review (behavioral + conformance)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:** §4 intent artifact → Task 1 (read/write/merge) + Task 2 (writer subcommand). §5.1 intent.py → Task 1. §5.3 PR assembly → Task 4 (Linear branch removed — deferred). §5.4 sync_review → Task 3. §5.5 /archie-sync capture → Task 5. **Intent-aware code review (behavioral + conformance consume the intent) → Task 6** (extends the design's delivery-review goal so the *code* review, not only edge-A, grades against intent). §7 error handling → per-task (malformed file → None in T1; bad payload leaves file intact in T2; assembly try/except in T4; `intent=None` default keeps T6 backward-compatible). §8 testing → each task's tests map to the spec's list. **Descoped:** §5.2 `linear_intent.py` + §5.6 `LINEAR_API_KEY` — moved to a follow-up (design §9).

**Placeholder scan:** none — every step has runnable code + exact commands.

**Type consistency:** `merge_specs`/`load_committed_intent`/`write_committed_intent`/`INTENT_FILE` (T1) consumed with identical names in T2/T3/T4; `intent_brief(spec)` (T6) consumed by behavioral + conformance builders; `assemble_pr_intent(root, pr_meta, env, *, run)` (T4) matches its tests; `review(..., intent=None)` / `review_conformance(..., intent=None)` (T6) are keyword-added, so all existing call sites stay valid; `intent_spec` shape (`source/confidence/ticket_ids/goals/acceptance_criteria/raw`) consistent across all tasks.

**Note on `merge_specs` arg order at the PR gate (T4):** `merge_specs(file_spec, pr_spec)` — order only affects the `source` *label* tie-break (highest `_RANK` wins regardless of position: `sync` > `pr_body` > `inferred`); criteria union is order-preserving, so committed-file criteria list first, then PR — intended.

**Placeholder scan:** none — every step has runnable code + exact commands.

**Type consistency:** `merge_specs`/`load_committed_intent`/`write_committed_intent`/`INTENT_FILE` (T1) consumed with identical names in T2/T3/T4; `assemble_pr_intent(root, pr_meta, env, *, run)` (T4) matches its tests; `intent_spec` shape (`source/confidence/ticket_ids/goals/acceptance_criteria/raw`) consistent across all tasks.

**Note on `merge_specs` arg order at the PR gate (T4):** `merge_specs(file_spec, pr_spec)` — order only affects the `source` *label* tie-break (highest `_RANK` wins regardless of position: `sync` > `pr_body` > `inferred`); criteria union is order-preserving, so committed-file criteria list first, then PR — intended.

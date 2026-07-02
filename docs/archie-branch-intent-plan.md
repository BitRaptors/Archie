# Branch Intent Capture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/archie-sync` writes a committed `.archie/intent.json` (agent-authored goals + acceptance criteria); the delivery review reads it at PR time and merges it with an optional Linear ticket and the PR body.

**Architecture:** Add committed-intent read/write + a pure `merge_specs` to `intent.py`; a small isolated `linear_intent.py` for the optional ticket fetch; a `sync.py write-intent` subcommand the sync agent calls; then swap the PR gate + sync review to assemble intent from (committed file ⊕ Linear ⊕ PR body). Everything degrades gracefully — all sources optional, review stays non-blocking.

**Tech Stack:** Zero-dependency Python 3.9+ stdlib (`urllib` for the Linear call). Tests: pytest, LLM/network mocked.

## Global Constraints

- **Zero runtime dependencies** beyond Python 3.9+ stdlib.
- **File sync:** edit `archie/standalone/*.py` first, copy to `npm-package/assets/*.py`; edit `archie/assets/workflows/*` first, copy to `npm-package/assets/workflows/*`. Register any NEW standalone script in `npm-package/bin/archie.mjs`'s copy list. Run `python3 scripts/verify_sync.py` before every commit — it must PASS.
- **Import convention (py3.9 — only `python3`, no `python`):** standalone modules import siblings BARE via guarded `sys.path.insert(0, str(Path(__file__).parent))` (`if _p not in sys.path`); tests use `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))` + bare `import <module>`. NEVER `from archie.standalone.X` (trips `tomllib` on 3.9). Run tests with `python3 -m pytest`.
- **LLM-injection convention:** orchestrators that call the LLM take `run=None` then `if run is None: run = run_verifier` (call-time lookup) so monkeypatch works.
- **Committed artifact:** `.archie/intent.json` must NOT be gitignored (the installer's gitignore block lists `.archie/*.py` etc., not `.archie/*.json` broadly — leave it committable).
- **Reuse existing:** `intent.normalize`, `intent.resolve`, `intent._RANK`, `evidence_schema.extract_json_obj`. Do not duplicate them.
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
    a = {"source": "linear", "confidence": "high", "goals": ["G1"],
         "acceptance_criteria": [{"id": "x", "text": "Tenant scoped"}], "ticket_ids": ["ARCH-1"], "raw": "ticket"}
    b = {"source": "sync", "confidence": "high", "goals": ["G1", "G2"],
         "acceptance_criteria": [{"id": "y", "text": "tenant scoped"}, {"id": "z", "text": "Rate limited"}],
         "ticket_ids": [], "raw": "plan"}
    m = it.merge_specs(a, b)
    texts = [c["text"] for c in m["acceptance_criteria"]]
    assert texts == ["Tenant scoped", "Rate limited"]          # dedup by normalized text, order preserved
    assert m["acceptance_criteria"][0]["id"] == "ac1"          # ids reindexed
    assert m["goals"] == ["G1", "G2"] and m["ticket_ids"] == ["ARCH-1"]
    assert m["source"] == "linear"                             # highest _RANK wins
    assert "ticket" in m["raw"] and "plan" in m["raw"]


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

## Task 2: `linear_intent.py` — optional ticket fetch

**Files:**
- Create: `archie/standalone/linear_intent.py`
- Modify: `npm-package/bin/archie.mjs` (add `"linear_intent.py"` to the script copy list)
- Test: `tests/test_linear_intent.py`

**Interfaces:**
- Produces: `fetch_ticket(ticket_id, api_key, post=_default_post) -> str | None`. `post(url, data: bytes, headers: dict) -> str` is injectable so tests never hit the network.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_linear_intent.py
import sys, json
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import linear_intent as li  # noqa: E402


def test_fetch_ticket_returns_title_and_description():
    def fake_post(url, data, headers):
        assert headers["Authorization"] == "key"
        return json.dumps({"data": {"issue": {"identifier": "ARCH-1", "title": "Export",
                                              "description": "tenant scoped, rate limited"}}})
    out = li.fetch_ticket("ARCH-1", "key", post=fake_post)
    assert "Export" in out and "tenant scoped" in out


def test_fetch_ticket_none_on_missing_input():
    called = {"n": 0}
    def fake_post(*a, **k): called["n"] += 1; return "{}"
    assert li.fetch_ticket(None, "key", post=fake_post) is None
    assert li.fetch_ticket("ARCH-1", None, post=fake_post) is None
    assert called["n"] == 0  # no network attempted


def test_fetch_ticket_none_on_error_or_no_issue():
    assert li.fetch_ticket("ARCH-1", "key", post=lambda *a, **k: (_ for _ in ()).throw(OSError("down"))) is None
    assert li.fetch_ticket("ARCH-1", "key", post=lambda *a, **k: json.dumps({"data": {"issue": None}})) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_linear_intent.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'linear_intent'`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/linear_intent.py
"""Optional Linear ticket fetch for delivery review. Best-effort: returns None on any
missing input or error. Zero deps (stdlib urllib). The HTTP call is injectable for tests.
"""
from __future__ import annotations
import json
import urllib.request

LINEAR_URL = "https://api.linear.app/graphql"
_QUERY = "query($id:String!){issue(id:$id){identifier title description}}"


def _default_post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode()


def fetch_ticket(ticket_id, api_key, post=_default_post):
    """Return the issue's 'title\\n\\ndescription' text, or None on missing input / any error."""
    if not ticket_id or not api_key:
        return None
    body = json.dumps({"query": _QUERY, "variables": {"id": ticket_id}}).encode()
    headers = {"Authorization": api_key, "Content-Type": "application/json"}
    try:
        raw = post(LINEAR_URL, body, headers)
        issue = (((json.loads(raw) or {}).get("data") or {}).get("issue")) or None
        if not issue:
            return None
        text = ((issue.get("title") or "") + "\n\n" + (issue.get("description") or "")).strip()
        return text or None
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_linear_intent.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/linear_intent.py npm-package/assets/linear_intent.py
# add "linear_intent.py" to the script array in npm-package/bin/archie.mjs (near delivery_review.py)
python3 scripts/verify_sync.py
git add archie/standalone/linear_intent.py npm-package/assets/linear_intent.py npm-package/bin/archie.mjs tests/test_linear_intent.py
git commit -m "feat(intent): optional Linear ticket fetch (best-effort)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `sync.py write-intent` subcommand

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

## Task 4: Sync review reads the committed intent

**Files:**
- Modify: `archie/standalone/sync_review.py` (lines ~73-77, the intent-load block)
- Test: `tests/test_sync_review.py` (add one test)

**Interfaces:**
- Consumes: `intent.load_committed_intent` (bare import).

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_sync_review.py (imports already present: sr, and it via intent)
def test_sync_review_uses_committed_intent(tmp_path, monkeypatch):
    import intent as it
    it.write_committed_intent(tmp_path, {"source": "sync", "goals": [],
        "acceptance_criteria": [{"id": "a", "text": "Scoped"}], "ticket_ids": [], "raw": "plan"})
    seen = {}
    monkeypatch.setattr(sr, "review_edge_a", lambda root, spec, diff, run=None: seen.setdefault("crit", spec.get("acceptance_criteria")) or [])
    monkeypatch.setattr(sr, "behavioral_review_run", lambda *a, **k: [])
    BP = {"domain_invariants": [], "decisions": {"key_decisions": []}, "persistence_stores": [], "data_models": []}
    sr.run_sync_review(str(tmp_path), "feature/x", BP, {}, "diff", ["a.py"], {"a.py": {1}}, {})
    assert seen.get("crit") and seen["crit"][0]["text"] == "Scoped"   # committed criteria reached edge-A
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sync_review.py::test_sync_review_uses_committed_intent -v`
Expected: FAIL (edge-A saw empty criteria; `seen["crit"]` is empty/None).

- [ ] **Step 3: Wire the committed intent in**

In `archie/standalone/sync_review.py`, add the bare import near the others:
```python
from intent import load_branch_record, normalize, save_branch_record, load_committed_intent  # noqa: E402
```
Change the spec-load line (currently `spec = load_branch_record(archie_dir, branch) or normalize("", ...)`) to prefer the committed file:
```python
    spec = (load_committed_intent(root)
            or load_branch_record(archie_dir, branch)
            or normalize("", source="inferred", ticket_ids=[]))
```
(`root` is the function's root arg; `archie_dir` already defined above it.)

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

## Task 5: PR-gate intent assembly (committed file ⊕ Linear ⊕ PR body)

**Files:**
- Modify: `archie/standalone/delivery_review.py` (`run_pr_gate` intent block, ~lines 192-212)
- Test: `tests/test_delivery_review.py` (add tests)

**Interfaces:**
- Consumes: `intent.load_committed_intent`, `intent.merge_specs`, `intent.normalize`, `intent.resolve`, `intent.ticket_ids_from`, `linear_intent.fetch_ticket` (all bare imports).
- Produces: a new pure helper `assemble_pr_intent(root, pr_meta, env, *, fetch=fetch_ticket, run=None) -> dict` so the merge logic is unit-testable without the full gate.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_delivery_review.py  (dr already imported)
def test_assemble_pr_intent_merges_file_ticket_and_body(tmp_path, monkeypatch):
    import intent as it
    it.write_committed_intent(tmp_path, {"source": "sync", "goals": [],
        "acceptance_criteria": [{"id": "a", "text": "From file"}], "ticket_ids": ["ARCH-9"], "raw": "plan"})
    pr_meta = {"head_ref": "feature/ARCH-9", "title": "T", "body": "body", "base_ref": "main"}
    env = {"LINEAR_API_KEY": "key"}
    spec = dr.assemble_pr_intent(tmp_path, pr_meta, env,
                                 fetch=lambda tid, key, **k: "Ticket title\n\nticket requirement",
                                 run=lambda *a, **k: '{"acceptance_criteria":[{"id":"t","text":"From ticket"}]}')
    texts = [c["text"] for c in spec["acceptance_criteria"]]
    assert "From file" in texts and "From ticket" in texts        # both sources merged


def test_assemble_pr_intent_no_ticket_uses_file_without_resolve(tmp_path):
    import intent as it
    it.write_committed_intent(tmp_path, {"source": "sync", "goals": [],
        "acceptance_criteria": [{"id": "a", "text": "Only file"}], "ticket_ids": [], "raw": "plan"})
    called = {"resolve": 0}
    spec = dr.assemble_pr_intent(tmp_path, {"head_ref": "b", "title": "", "body": ""}, {},
                                 fetch=lambda *a, **k: None,
                                 run=lambda *a, **k: called.__setitem__("resolve", called["resolve"] + 1) or "{}")
    assert [c["text"] for c in spec["acceptance_criteria"]] == ["Only file"]
    assert called["resolve"] == 0                                  # criteria already present -> no LLM resolve
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_delivery_review.py -k assemble -v`
Expected: FAIL (`AttributeError: module 'delivery_review' has no attribute 'assemble_pr_intent'`).

- [ ] **Step 3: Add `assemble_pr_intent` and call it from `run_pr_gate`**

Add the helper to `archie/standalone/delivery_review.py`:
```python
def assemble_pr_intent(root, pr_meta, env, *, fetch=None, run=None):
    """Merge intent from committed .archie/intent.json ⊕ optional Linear ticket ⊕ PR title/body.
    resolve() runs ONLY if the merged spec still has no acceptance_criteria."""
    import sys as _sys
    _p = str(Path(__file__).parent)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
    from intent import (load_committed_intent, merge_specs, normalize,
                        resolve, ticket_ids_from)  # noqa: E402
    if fetch is None:
        from linear_intent import fetch_ticket as fetch  # noqa: E402

    file_spec = load_committed_intent(root)
    title = pr_meta.get("title") or ""
    body = pr_meta.get("body") or env.get("ARCHIE_PR_BODY", "")
    branch = pr_meta.get("head_ref") or ""
    pr_text = (title + "\n\n" + body).strip()
    tickets = ticket_ids_from(branch, pr_text, [])
    ticket_id = (file_spec or {}).get("ticket_id") or (tickets[0] if tickets else None)

    ticket_spec = None
    try:
        ticket_text = fetch(ticket_id, env.get("LINEAR_API_KEY"))
        if ticket_text:
            ticket_spec = resolve(normalize(ticket_text, "linear",
                                            [ticket_id] if ticket_id else []), run=run)
    except Exception as e:
        print(f"[archie] ticket fetch skipped ({e})")

    pr_spec = normalize(pr_text, "pr_body", tickets) if pr_text else None
    spec = merge_specs(ticket_spec, file_spec, pr_spec)
    if not spec.get("acceptance_criteria") and spec.get("raw"):
        try:
            spec = resolve(spec, run=run)
        except Exception as e:
            print(f"[archie] intent resolve failed ({e})")
    return spec
```
In `run_pr_gate`, replace the whole `# 4. Resolve intent ...` try/except block (the one that builds `spec` from `ticket_ids_from`/`normalize`/`load_branch_record`) with:
```python
    # 4. Assemble intent: committed file ⊕ optional Linear ticket ⊕ PR title/body.
    try:
        spec = assemble_pr_intent(root, pr_meta, env)
    except Exception as e:
        print(f"[archie] intent assembly failed ({e})")
        spec = {"acceptance_criteria": [], "goals": [], "confidence": "low"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_delivery_review.py -v`
Expected: PASS (all, incl. the 2 new tests; existing gate tests green).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/delivery_review.py npm-package/assets/delivery_review.py
python3 scripts/verify_sync.py
git add archie/standalone/delivery_review.py npm-package/assets/delivery_review.py tests/test_delivery_review.py
git commit -m "feat(pr-gate): assemble intent from committed file + optional Linear + PR body

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Wire the capture step + workflow secret

**Files:**
- Modify: `archie/assets/workflows/archie-intent-review.yml` (add `LINEAR_API_KEY` to the delivery step) → copy to `npm-package/assets/workflows/archie-intent-review.yml`
- Modify: `archie/assets/workflow/sync/SKILL.md` (add the intent-capture step) → copy to `npm-package/assets/workflow/sync/SKILL.md`
- Modify: `archie/assets/setup-archie-intent-review.sh` (optional `LINEAR_API_KEY` prompt) → copy to npm asset
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


def test_delivery_workflow_declares_linear_key():
    wf = (Path(__file__).resolve().parent.parent / "archie" / "assets" / "workflows"
          / "archie-intent-review.yml").read_text()
    assert "LINEAR_API_KEY" in wf and "delivery_review.py" in wf
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_branch_intent_smoke.py -v`
Expected: FAIL on `test_delivery_workflow_declares_linear_key` (`LINEAR_API_KEY` not in the YAML yet). The CLI roundtrip test should already pass (Task 3 shipped the subcommand).

- [ ] **Step 3: Add the workflow secret, the sync capture step, and the setup prompt**

In `archie/assets/workflows/archie-intent-review.yml`, add to the **delivery-review** step's `env:` block:
```yaml
          LINEAR_API_KEY: ${{ secrets.LINEAR_API_KEY }}
```

In `archie/assets/workflow/sync/SKILL.md`, add an intent-capture step (before the commit/fold step). Exact text to insert:
```markdown
### Capture branch intent (for delivery review)

Synthesize this branch's intent from the task, plan, and conversation, then persist it so the
PR-time delivery review can grade against what you set out to build:

1. Write a JSON spec to a temp file with this shape (author `goals` and concrete, checkable
   `acceptance_criteria` directly; include `ticket_id` if a Linear ticket applies):
   `{"source":"sync","goals":[...],"acceptance_criteria":[{"id":"ac1","text":"..."}],"ticket_id":"ARCH-123","raw":"<goal + plan>"}`
2. Run: `python3 .archie/sync.py write-intent . /tmp/archie_intent_spec.json`
   (merges into the committed `.archie/intent.json`; re-running refines it).
3. Stage `.archie/intent.json` so it is committed with the branch.

If the intent is genuinely unknown, write `raw` only (or skip); the review degrades to PR-body intent.
```

In `archie/assets/setup-archie-intent-review.sh`, after the `ANTHROPIC_API_KEY` block, add an optional prompt:
```bash
# ===== SECTION 2b: OPTIONAL LINEAR KEY =====
printf 'Enter your LINEAR_API_KEY for ticket-grounded intent (optional, press Enter to skip): '
read -rs LINEAR_API_KEY
echo ""
if [ -n "$LINEAR_API_KEY" ]; then
    printf '%s' "$LINEAR_API_KEY" | gh secret set LINEAR_API_KEY
    unset LINEAR_API_KEY
    log_success "LINEAR_API_KEY secret set"
else
    log_info "No Linear key — delivery review will use the committed intent file + PR body."
fi
```

- [ ] **Step 4: Copy to npm mirrors, run tests + sync**

```bash
cp archie/assets/workflows/archie-intent-review.yml npm-package/assets/workflows/archie-intent-review.yml
cp archie/assets/workflow/sync/SKILL.md npm-package/assets/workflow/sync/SKILL.md
cp archie/assets/setup-archie-intent-review.sh npm-package/assets/setup-archie-intent-review.sh
python3 -m pytest tests/test_branch_intent_smoke.py -v      # both pass now
bash -n archie/assets/setup-archie-intent-review.sh          # valid bash
python3 scripts/verify_sync.py                               # PASS
```
Expected: 2 passed; sync PASS.

- [ ] **Step 5: Commit**

```bash
git add archie/assets/workflows/archie-intent-review.yml npm-package/assets/workflows/archie-intent-review.yml \
        archie/assets/workflow/sync/SKILL.md npm-package/assets/workflow/sync/SKILL.md \
        archie/assets/setup-archie-intent-review.sh npm-package/assets/setup-archie-intent-review.sh \
        tests/test_branch_intent_smoke.py
git commit -m "feat(ci): capture branch intent in sync + optional LINEAR_API_KEY in workflow

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:** §4 intent artifact → Task 1 (read/write/merge) + Task 3 (writer subcommand). §5.1 intent.py → Task 1. §5.2 linear_intent → Task 2. §5.3 PR assembly → Task 5. §5.4 sync_review → Task 4. §5.5 /archie-sync capture → Task 6. §5.6 workflow/setup → Task 6. §7 error handling → covered per-task (malformed file → None in T1; missing id/key/HTTP error → None in T2; bad payload leaves file intact in T3; assembly try/except in T5). §8 testing → each task's tests map to the spec's test list.

**Placeholder scan:** none — every step has runnable code + exact commands.

**Type consistency:** `merge_specs`/`load_committed_intent`/`write_committed_intent`/`INTENT_FILE` (T1) are consumed with identical names in T3/T4/T5; `fetch_ticket(ticket_id, api_key, post=)` (T2) matches the `fetch=` injection in T5; `assemble_pr_intent(root, pr_meta, env, *, fetch, run)` (T5) matches its tests. `intent_spec` shape (`source/confidence/ticket_ids/goals/acceptance_criteria/raw`) is consistent across all tasks.

**Note on `merge_specs` arg order at the PR gate (T5):** `merge_specs(ticket_spec, file_spec, pr_spec)` — order only affects the `source` *label* tie-break (highest `_RANK` wins regardless of position: `linear` > `pr_body`/`sync` > `inferred`); criteria union is order-preserving, so ticket criteria list first, then file, then PR — intended.

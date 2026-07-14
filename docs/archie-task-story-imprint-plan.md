# Task Story — Faithful Intent Imprint — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the acceptance-criteria-inventing intent synthesizer with a silent, versioned **task story** — a faithful summary of the user's ticket ⊕ inputs ⊕ plan, from which Archie derives provenance-checked facts that the delivery review grades against.

**Architecture:** A new blind-to-code synthesizer (`story_synthesize.py`) runs two LLM passes — summarize the captured user turns into a story, then derive facts from that story with a `from:` source pointer each. A storage module (`story_store.py`) writes one Markdown file per imprint (prose + fenced JSON facts) under `.archie/stories/<branch-slug>/<timestamp>.md`, retaining full history but resolving a session-scoped "current" for grading. The delivery review loads the current story's facts instead of `intent.json`, and renders the story + per-fact provenance in the verdict.

**Tech Stack:** Python 3.9 stdlib only (no third-party deps). Existing Archie standalone modules: `agent_cli.run_verifier` (LLM seam), `evidence_schema.extract_json_obj` (fenced-JSON parsing), `intent_capture` (event log).

## Global Constraints

Every task's requirements implicitly include these (copied verbatim from CLAUDE.md + the spec):

- Interpreter is `python3` only (3.9.6) — never `python`. Zero dependencies beyond the stdlib.
- Standalone modules import siblings **bare** via a guarded `sys.path.insert(0, str(Path(__file__).parent))` (`_p = str(Path(__file__).parent); if _p not in sys.path: sys.path.insert(0, _p)`). **Never** `from archie.standalone.X import ...` (trips `tomllib` on 3.9).
- Tests import standalone modules by inserting `Path(__file__).resolve().parent.parent / "archie" / "standalone"` on `sys.path`, then a bare `import`.
- LLM seam is injectable: functions that call the model take `run=None` and resolve it at call time — `if run is None: run = run_verifier` — so monkeypatching `run` works.
- The synthesizer is **blind to code**: it must never read the diff, blueprint code, or source files. Its prompts contain only the user's turns (+ optional ticket text).
- Writes are atomic: write a temp file then `os.replace`.
- Timestamps: `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")` (UTC, filesystem-safe, second precision).
- File sync: after editing `archie/standalone/*.py`, copy to `npm-package/assets/*.py`; register any NEW standalone script in the script list in `npm-package/bin/archie.mjs`; run `python3 scripts/verify_sync.py` (must print `SYNC CHECK PASSED`) before committing.
- Commit trailer on every commit: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Run the standalone test subset by explicit path (the full `pytest tests/` trips known `tomllib` collection errors on 3.9 — those 3 pre-existing failures in `test_automated_sync_hooks.py` ×2 and `test_install_loop.py` ×1 are unrelated and expected).

---

## File Structure

**Create:**
- `archie/standalone/story_store.py` — storage + versioning: branch slug, path, atomic write of the single prose+facts file, parse-back, history listing, session-scoped current resolver. No LLM.
- `archie/standalone/story_synthesize.py` — blind two-pass synthesizer: gather sources, story pass, facts pass, provenance validation, imprint orchestration.
- `tests/test_story_store.py`, `tests/test_story_synthesize.py`.

**Modify:**
- `archie/standalone/sync.py` — add `imprint` + `story` subcommands; remove `synthesize-intent`/`show-intent`/`confirm-intent`.
- `archie/standalone/delivery_review.py` — `assemble_pr_intent` loads story facts via `story_store`; `render_verdict` renders the story + per-fact provenance.
- `archie/assets/hook_scripts/stop.sh` — best-effort, non-blocking background imprint when a transition is pending.
- `archie/assets/workflow/sync/SKILL.md` — Step 5b references `imprint`/`story`.
- `npm-package/bin/archie.mjs` — register `story_store.py`, `story_synthesize.py`.

**Delete:**
- `archie/standalone/intent_synthesize.py` + `npm-package/assets/intent_synthesize.py` (+ its archie.mjs entry). Retire `tests/test_intent_synthesize.py`.

---

### Task 1: Story storage — slug + paths

**Files:**
- Create: `archie/standalone/story_store.py`
- Test: `tests/test_story_store.py`

**Interfaces:**
- Produces: `branch_slug(branch: str) -> str`; `story_dir(root, branch: str) -> Path` (returns `<root>/.archie/stories/<slug>/`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_story_store.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import story_store as ss  # noqa: E402


def test_branch_slug_flattens_slashes_and_specials():
    assert ss.branch_slug("feature/run-cost-preview") == "feature-run-cost-preview"
    assert ss.branch_slug("bugfix/AB-12_x") == "bugfix-AB-12_x"
    assert ss.branch_slug("") == "detached"


def test_story_dir_is_under_archie_stories(tmp_path):
    d = ss.story_dir(tmp_path, "feature/x")
    assert d == tmp_path / ".archie" / "stories" / "feature-x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_story_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'story_store'`.

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/story_store.py
"""Task-story storage: one Markdown file per imprint (prose + fenced JSON facts),
versioned by branch + timestamp under .archie/stories/<slug>/. No LLM. Best-effort:
callers treat a None/{} result as 'no story'."""
from __future__ import annotations
import re
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)

STORIES_SUBDIR = "stories"


def branch_slug(branch: str) -> str:
    """Flatten a branch name to a filesystem-safe directory segment."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", (branch or "").strip()).strip("-")
    return s or "detached"


def story_dir(root, branch: str) -> Path:
    return Path(root) / ".archie" / STORIES_SUBDIR / branch_slug(branch)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_story_store.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/story_store.py tests/test_story_store.py
git commit -m "feat(story): storage slug + path helpers

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Story storage — write + parse one file (round-trip)

**Files:**
- Modify: `archie/standalone/story_store.py`
- Test: `tests/test_story_store.py`

**Interfaces:**
- Consumes: `story_dir` (Task 1).
- Produces:
  - `write_story(root, branch, session_id, timestamp, story, facts, non_goals, supersedes=None, version=1) -> Path` — writes `<timestamp>.md` (prose + a `<!-- archie:facts -->` fenced JSON block), atomically; returns the path.
  - `parse_story_file(path) -> dict` — returns `{"story": str, "meta": dict, "facts": list, "non_goals": list}`; `{}` on unreadable/malformed.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_story_store.py
def test_write_then_parse_round_trip(tmp_path):
    facts = [{"id": "f1", "text": "total = steps × price",
              "from": {"src": "plan", "quote": "the total must be steps × price"}, "kind": "constraint"}]
    p = ss.write_story(tmp_path, "feature/x", session_id="sess-1",
                       timestamp="2026-07-06T091200", story="We add a cost preview.\n\nIt is fresh.",
                       facts=facts, non_goals=["applying the cap"], supersedes=None, version=1)
    assert p.exists() and p.name == "2026-07-06T091200.md"
    got = ss.parse_story_file(p)
    assert got["story"].startswith("We add a cost preview.")
    assert got["facts"] == facts
    assert got["non_goals"] == ["applying the cap"]
    assert got["meta"]["branch"] == "feature/x" and got["meta"]["session_id"] == "sess-1"
    assert got["meta"]["version"] == 1


def test_parse_bad_file_returns_empty(tmp_path):
    bad = tmp_path / "x.md"
    bad.write_text("no fenced json here")
    assert ss.parse_story_file(bad) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_story_store.py -q`
Expected: FAIL — `AttributeError: module 'story_store' has no attribute 'write_story'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to archie/standalone/story_store.py
import json
import os
from evidence_schema import extract_json_obj  # noqa: E402  (bare sibling import)

_FACTS_MARKER = "<!-- archie:facts -->"


def write_story(root, branch, session_id, timestamp, story, facts, non_goals,
                supersedes=None, version=1) -> Path:
    d = story_dir(root, branch)
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "branch": branch,
        "session_id": session_id,
        "imprinted_at": timestamp,
        "version": version,
        "supersedes": supersedes,
        "source": "sync",
        "confirmed": False,
        "facts": facts,
        "non_goals": non_goals,
    }
    body = (
        f"{(story or '').strip()}\n\n"
        f"{_FACTS_MARKER}\n"
        "```json\n" + json.dumps(meta, indent=2) + "\n```\n"
    )
    path = d / f"{timestamp}.md"
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)
    return path


def parse_story_file(path) -> dict:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    if _FACTS_MARKER not in text:
        return {}
    prose, _, rest = text.partition(_FACTS_MARKER)
    meta = extract_json_obj(rest)
    if not meta:
        return {}
    return {
        "story": prose.strip(),
        "meta": meta,
        "facts": meta.get("facts", []) or [],
        "non_goals": meta.get("non_goals", []) or [],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_story_store.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/story_store.py tests/test_story_store.py
git commit -m "feat(story): atomic single-file write + parse round-trip

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Story storage — history + session-scoped current

**Files:**
- Modify: `archie/standalone/story_store.py`
- Test: `tests/test_story_store.py`

**Interfaces:**
- Consumes: `story_dir`, `parse_story_file` (Tasks 1–2).
- Produces:
  - `list_versions(root, branch) -> list[Path]` — timestamped story files for the branch, oldest→newest.
  - `current_story(root, branch, session_id=None) -> dict | None` — the newest parsed story; when `session_id` is given, the newest whose `meta.session_id` matches; else the newest overall. `None` when there is none.
  - `next_version(root, branch) -> tuple[int, str | None]` — `(version, supersedes_timestamp)` for the next imprint.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_story_store.py
def _w(tmp, ts, sess, ver, sup=None):
    return ss.write_story(tmp, "feature/x", session_id=sess, timestamp=ts,
                          story=f"story {ts}", facts=[], non_goals=[], supersedes=sup, version=ver)


def test_list_versions_sorted_oldest_first(tmp_path):
    _w(tmp_path, "2026-07-06T090000", "s1", 1)
    _w(tmp_path, "2026-07-06T100000", "s2", 2)
    names = [p.name for p in ss.list_versions(tmp_path, "feature/x")]
    assert names == ["2026-07-06T090000.md", "2026-07-06T100000.md"]


def test_current_story_session_scoped(tmp_path):
    _w(tmp_path, "2026-07-06T090000", "old-session", 1)
    _w(tmp_path, "2026-07-06T100000", "this-session", 2)
    # newest overall
    assert ss.current_story(tmp_path, "feature/x")["meta"]["imprinted_at"] == "2026-07-06T100000"
    # scoped to a session returns that session's newest, not a newer other-session one
    _w(tmp_path, "2026-07-06T110000", "other-session", 3)
    got = ss.current_story(tmp_path, "feature/x", session_id="this-session")
    assert got["meta"]["imprinted_at"] == "2026-07-06T100000"


def test_current_story_none_when_absent(tmp_path):
    assert ss.current_story(tmp_path, "feature/none") is None


def test_next_version_increments_and_supersedes(tmp_path):
    assert ss.next_version(tmp_path, "feature/x") == (1, None)
    _w(tmp_path, "2026-07-06T090000", "s1", 1)
    assert ss.next_version(tmp_path, "feature/x") == (2, "2026-07-06T090000")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_story_store.py -q`
Expected: FAIL — `AttributeError: ... 'list_versions'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to archie/standalone/story_store.py
def list_versions(root, branch) -> list:
    d = story_dir(root, branch)
    if not d.exists():
        return []
    return sorted(d.glob("*.md"), key=lambda p: p.name)


def current_story(root, branch, session_id=None):
    versions = list_versions(root, branch)
    for path in reversed(versions):
        parsed = parse_story_file(path)
        if not parsed:
            continue
        if session_id is None or parsed["meta"].get("session_id") == session_id:
            return parsed
    return None


def next_version(root, branch):
    versions = list_versions(root, branch)
    if not versions:
        return (1, None)
    last = versions[-1]
    parsed = parse_story_file(last)
    ver = int(parsed["meta"].get("version", len(versions))) + 1 if parsed else len(versions) + 1
    return (ver, last.stem)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_story_store.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/story_store.py tests/test_story_store.py
git commit -m "feat(story): history listing + session-scoped current resolver

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Synthesizer — gather sources + story pass (Pass 1)

**Files:**
- Create: `archie/standalone/story_synthesize.py`
- Test: `tests/test_story_synthesize.py`

**Interfaces:**
- Consumes: `intent_capture.load_events` (existing), `evidence_schema.extract_json_obj` (existing).
- Produces:
  - `gather_sources(root) -> list[dict]` — `[{"src": "plan"|"ticket", "text": str}]` from the events log (`user_turn` texts, `src="plan"`) plus `.archie/ticket.md` if present (`src="ticket"`).
  - `build_story_prompt(sources) -> str` (pure) — contains the faithfulness instruction + the source texts, and **no** code/diff.
  - `parse_story(raw) -> str` (pure) — extracts `story` from a `{"story": "..."}` JSON reply; `""` on failure.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_story_synthesize.py
import json
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import story_synthesize as ssyn  # noqa: E402


def test_gather_sources_from_events_and_ticket(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    (ad / "intent-events.jsonl").write_text(
        json.dumps({"kind": "user_turn", "text": "add a cost preview"}) + "\n"
        + json.dumps({"kind": "transition"}) + "\n"
        + json.dumps({"kind": "user_turn", "text": "total = steps × price"}) + "\n")
    (ad / "ticket.md").write_text("ARCH-1: cost preview endpoint")
    srcs = ssyn.gather_sources(tmp_path)
    kinds = [(s["src"], s["text"]) for s in srcs]
    assert ("plan", "add a cost preview") in kinds
    assert ("plan", "total = steps × price") in kinds
    assert ("ticket", "ARCH-1: cost preview endpoint") in kinds


def test_story_prompt_is_faithful_and_blind():
    p = ssyn.build_story_prompt([{"src": "plan", "text": "add a cost preview"}])
    assert "summar" in p.lower() and "supported by a source" in p.lower()
    assert "add a cost preview" in p
    # blindness: no diff/code words leaked in
    assert "diff --git" not in p


def test_parse_story_extracts_prose():
    assert ssyn.parse_story(json.dumps({"story": "We add a cost preview."})) == "We add a cost preview."
    assert ssyn.parse_story("garbage") == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_story_synthesize.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'story_synthesize'`.

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/story_synthesize.py
"""Blind (code-unaware) two-pass task-story synthesizer. Pass 1 summarizes the
user's captured turns (+ optional ticket) into a faithful story; Pass 2 derives
facts, each traceable to a source. Prompt-builders + parsers are pure; the LLM is
called through run_verifier."""
from __future__ import annotations
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from evidence_schema import extract_json_obj  # noqa: E402
from intent_capture import load_events         # noqa: E402

_STORY_SYSTEM = (
    "You write a short TASK STORY that summarizes a change from the requirement below. "
    "Summarize — do not invent. Every sentence MUST be supported by a source. Do NOT add "
    "endpoints, field names, tests, or requirements that are not present in the sources. "
    "You are NOT shown the implementation, diff, or code. "
    "Return JSON {\"story\":\"<2-4 sentence narrative>\"}."
)


def gather_sources(root) -> list:
    out = []
    for e in load_events(root):
        if e.get("kind") == "user_turn" and (e.get("text") or "").strip():
            out.append({"src": "plan", "text": e["text"].strip()})
    ticket = Path(root) / ".archie" / "ticket.md"
    if ticket.exists():
        t = ticket.read_text(encoding="utf-8").strip()
        if t:
            out.append({"src": "ticket", "text": t})
    return out


def build_story_prompt(sources) -> str:
    body = "\n".join(f"- [{s.get('src')}] {s.get('text','')}" for s in (sources or []))
    return f"{_STORY_SYSTEM}\n\nSOURCES:\n{body}"


def parse_story(raw) -> str:
    d = extract_json_obj(raw or "")
    return (d.get("story") or "").strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_story_synthesize.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/story_synthesize.py tests/test_story_synthesize.py
git commit -m "feat(story): gather sources + faithful story pass (blind)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Synthesizer — facts pass (Pass 2) + provenance validation

**Files:**
- Modify: `archie/standalone/story_synthesize.py`
- Test: `tests/test_story_synthesize.py`

**Interfaces:**
- Consumes: `build_story_prompt`, sources (Task 4).
- Produces:
  - `build_facts_prompt(story, sources) -> str` (pure).
  - `parse_facts(raw) -> dict` (pure) — `{"facts": [...], "non_goals": [...]}`.
  - `validate_provenance(facts, sources) -> list` — keeps only facts whose `from.quote` shares ≥60% of its significant tokens (alphanumeric, length ≥3, lowercased) with the concatenated source text. Un-sourced/invented facts are dropped. Re-ids the survivors `f1..fN`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_story_synthesize.py
def test_facts_prompt_demands_provenance():
    p = ssyn.build_facts_prompt("We add a cost preview.", [{"src": "plan", "text": "cost preview"}])
    assert "cite" in p.lower() and "from" in p.lower()
    assert "We add a cost preview." in p


def test_parse_facts():
    raw = json.dumps({"facts": [{"id": "f1", "text": "t", "from": {"src": "plan", "quote": "q"}}],
                      "non_goals": ["ng"]})
    got = ssyn.parse_facts(raw)
    assert got["facts"][0]["text"] == "t" and got["non_goals"] == ["ng"]
    assert ssyn.parse_facts("junk") == {"facts": [], "non_goals": []}


def test_validate_provenance_drops_invented_facts():
    sources = [{"src": "plan", "text": "the total must be the number of billable steps times the price"}]
    facts = [
        {"text": "total is number of billable steps times price",
         "from": {"src": "plan", "quote": "the total must be the number of billable steps times the price"}},
        {"text": "response includes a billable_step_count field",   # invented — no source
         "from": {"src": "plan", "quote": "billable_step_count field must be present"}},
    ]
    kept = ssyn.validate_provenance(facts, sources)
    assert len(kept) == 1
    assert kept[0]["id"] == "f1"
    assert "total" in kept[0]["text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_story_synthesize.py -q`
Expected: FAIL — `AttributeError: ... 'build_facts_prompt'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to archie/standalone/story_synthesize.py
import re

_FACTS_SYSTEM = (
    "You extract checkable FACTS from the TASK STORY below. Extract only facts stated or "
    "directly implied by the story and its sources. Do NOT invent specifics (paths, field "
    "names, test cases) that are not present. Each fact MUST cite the source text it derives "
    "from in `from.quote`. Return JSON {\"facts\":[{\"id\":\"f1\",\"text\":\"...\","
    "\"from\":{\"src\":\"plan|ticket\",\"quote\":\"<verbatim source snippet>\"},"
    "\"kind\":\"goal|constraint|scope\"}],\"non_goals\":[\"...\"]}."
)


def build_facts_prompt(story, sources) -> str:
    body = "\n".join(f"- [{s.get('src')}] {s.get('text','')}" for s in (sources or []))
    return f"{_FACTS_SYSTEM}\n\nTASK STORY:\n{story}\n\nSOURCES:\n{body}"


def parse_facts(raw) -> dict:
    d = extract_json_obj(raw or "")
    return {"facts": d.get("facts", []) or [], "non_goals": d.get("non_goals", []) or []}


def _tokens(text) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 3}


def validate_provenance(facts, sources) -> list:
    source_tokens = set()
    for s in (sources or []):
        source_tokens |= _tokens(s.get("text", ""))
    kept = []
    for f in (facts or []):
        quote = ((f.get("from") or {}).get("quote")) or ""
        qtokens = _tokens(quote)
        if not qtokens:
            continue
        overlap = len(qtokens & source_tokens) / len(qtokens)
        if overlap >= 0.6:
            kept.append(f)
    for i, f in enumerate(kept, start=1):
        f["id"] = f"f{i}"
    return kept
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_story_synthesize.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/story_synthesize.py tests/test_story_synthesize.py
git commit -m "feat(story): facts pass + provenance validation drops invention

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Synthesizer — `imprint()` orchestration

**Files:**
- Modify: `archie/standalone/story_synthesize.py`
- Test: `tests/test_story_synthesize.py`

**Interfaces:**
- Consumes: `gather_sources`, `build_story_prompt`/`parse_story`, `build_facts_prompt`/`parse_facts`, `validate_provenance` (Tasks 4–5); `story_store.write_story`/`next_version` (Tasks 2–3); `agent_cli.run_verifier`.
- Produces: `imprint(root, branch, session_id, timestamp, run=None) -> Path | None` — runs both passes, validates, writes the versioned story file; returns the path, or `None` when there are no sources.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_story_synthesize.py
import story_store as ss  # noqa: E402


def test_imprint_writes_versioned_story(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    (ad / "intent-events.jsonl").write_text(
        json.dumps({"kind": "user_turn", "text": "total is billable steps times price"}) + "\n")

    def fake_run(prompt, root, verifier, **kw):
        if "TASK STORY" in prompt:   # facts pass
            return json.dumps({"facts": [{"text": "total = billable steps × price",
                "from": {"src": "plan", "quote": "total is billable steps times price"}}],
                "non_goals": []})
        return json.dumps({"story": "We add a cost preview."})   # story pass

    p = ssyn.imprint(tmp_path, "feature/x", "sess-1", "2026-07-06T091200", run=fake_run)
    assert p is not None and p.exists()
    got = ss.parse_story_file(p)
    assert got["story"] == "We add a cost preview."
    assert got["facts"][0]["id"] == "f1"
    assert got["meta"]["version"] == 1 and got["meta"]["session_id"] == "sess-1"


def test_imprint_returns_none_without_sources(tmp_path):
    (tmp_path / ".archie").mkdir()
    assert ssyn.imprint(tmp_path, "feature/x", "s", "2026-07-06T091200", run=lambda *a, **k: "") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_story_synthesize.py -q`
Expected: FAIL — `AttributeError: ... 'imprint'`.

- [ ] **Step 3: Write minimal implementation**

```python
# add to archie/standalone/story_synthesize.py
from agent_cli import run_verifier   # noqa: E402
import story_store                   # noqa: E402


def imprint(root, branch, session_id, timestamp, run=None):
    if run is None:
        run = run_verifier
    sources = gather_sources(root)
    if not sources:
        return None
    story = parse_story(run(build_story_prompt(sources), Path(root), "claude"))
    if not story:
        return None
    parsed = parse_facts(run(build_facts_prompt(story, sources), Path(root), "claude"))
    facts = validate_provenance(parsed["facts"], sources)
    version, supersedes = story_store.next_version(root, branch)
    return story_store.write_story(
        root, branch, session_id=session_id, timestamp=timestamp, story=story,
        facts=facts, non_goals=parsed["non_goals"], supersedes=supersedes, version=version)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_story_synthesize.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/story_synthesize.py tests/test_story_synthesize.py
git commit -m "feat(story): imprint() two-pass orchestration → versioned file

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: `sync.py` — `imprint` + `story` subcommands; retire old intent commands

**Files:**
- Modify: `archie/standalone/sync.py`
- Test: `tests/test_story_subcommands.py` (create)

**Interfaces:**
- Consumes: `story_synthesize.imprint`, `story_store.current_story`/`list_versions`/`parse_story_file`.
- Produces CLI: `sync.py imprint <root>` (writes a story using `GITHUB`/git branch + `CLAUDE_SESSION_ID` env or a generated stamp); `sync.py story <root>` (prints current); `sync.py story <root> --history`; `sync.py story <root> <timestamp>`. Removes `synthesize-intent`, `show-intent`, `confirm-intent`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_story_subcommands.py
import json
import subprocess
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import story_store as ss  # noqa: E402


def _run(root, *args):
    return subprocess.run([sys.executable, str(_STANDALONE / "sync.py"), *args, str(root)],
                          capture_output=True, text=True)


def test_story_command_prints_current(tmp_path):
    ss.write_story(tmp_path, "feature/x", "s1", "2026-07-06T090000",
                   story="We add a cost preview.", facts=[{"id": "f1", "text": "fresh compute",
                   "from": {"src": "plan", "quote": "fresh"}}], non_goals=[], version=1)
    # story reads the *current branch*; force it via env the command honors
    r = subprocess.run([sys.executable, str(_STANDALONE / "sync.py"), "story", str(tmp_path)],
                       capture_output=True, text=True, env={"ARCHIE_BRANCH": "feature/x", "PATH": ""})
    assert r.returncode == 0
    assert "We add a cost preview." in r.stdout and "f1" in r.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_story_subcommands.py -q`
Expected: FAIL — the `story` subcommand is unknown (non-zero exit / usage text).

- [ ] **Step 3: Write minimal implementation**

Read `archie/standalone/sync.py` first to find the `__main__` dispatch and the existing `synthesize-intent`/`show-intent`/`confirm-intent` branches (around the `if cmd == "capture-intent":` block). Replace those three branches with the two below, and add a branch-resolution helper near the top of the module.

```python
# add near the top-level helpers in archie/standalone/sync.py
import os as _os
import subprocess as _sp

def _branch(root) -> str:
    b = _os.environ.get("ARCHIE_BRANCH") or _os.environ.get("GITHUB_HEAD_REF")
    if b:
        return b
    try:
        out = _sp.run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
                      capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""

def _session_id() -> str:
    return _os.environ.get("CLAUDE_SESSION_ID") or _os.environ.get("ARCHIE_SESSION_ID") or "session"
```

```python
# in the __main__ dispatch of archie/standalone/sync.py, REPLACE the
# synthesize-intent / show-intent / confirm-intent branches with:
    if cmd == "imprint":
        from datetime import datetime, timezone
        import story_synthesize
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
        p = story_synthesize.imprint(root, _branch(root), _session_id(), ts)
        print(f"[archie] imprinted {p}" if p else "[archie] no sources — nothing imprinted",
              file=sys.stderr)
        sys.exit(0)
    if cmd == "story":
        import story_store
        rest = [a for a in sys.argv[3:] if a != root]
        if "--history" in rest:
            for pth in story_store.list_versions(root, _branch(root)):
                print(pth.stem)
            sys.exit(0)
        if rest:  # a specific timestamp
            parsed = story_store.parse_story_file(
                story_store.story_dir(root, _branch(root)) / f"{rest[0]}.md")
        else:
            parsed = story_store.current_story(root, _branch(root))
        if not parsed:
            print("[archie] no story for this branch", file=sys.stderr); sys.exit(0)
        print(parsed["story"] + "\n")
        for f in parsed["facts"]:
            src = (f.get("from") or {}).get("quote", "")
            print(f"  [{f.get('id')}] {f.get('text')}   (from: {src[:60]})")
        for ng in parsed["non_goals"]:
            print(f"  non-goal: {ng}")
        sys.exit(0)
```

Also update the usage/help text block to list `imprint` and `story` and drop the three retired commands.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_story_subcommands.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/sync.py tests/test_story_subcommands.py
git commit -m "feat(story): sync imprint + story subcommands; retire synthesize-intent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Delivery review — load story facts (replace `intent.json`)

**Files:**
- Modify: `archie/standalone/delivery_review.py` (function `assemble_pr_intent`)
- Test: `tests/test_delivery_story_intent.py` (create)

**Interfaces:**
- Consumes: `story_store.current_story`.
- Produces: `assemble_pr_intent(root, pr_meta)` returns a spec dict whose `acceptance_criteria` are the current story's `facts` (mapped to `{id, text}` plus retained `from`), merged with PR title/body, plus `non_goals`, `source`, `confirmed`, and a `story` string for rendering. No `intent.json` read remains.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_delivery_story_intent.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import story_store as ss           # noqa: E402
import delivery_review as dr       # noqa: E402


def test_assemble_pr_intent_uses_story_facts(tmp_path, monkeypatch):
    ss.write_story(tmp_path, "feature/x", "s1", "2026-07-06T090000",
                   story="We add a cost preview.",
                   facts=[{"id": "f1", "text": "total from live steps",
                           "from": {"src": "plan", "quote": "live steps"}}],
                   non_goals=["apply cap"], version=1)
    monkeypatch.setenv("ARCHIE_BRANCH", "feature/x")
    spec = dr.assemble_pr_intent(tmp_path, {"title": "Cost preview", "body": ""})
    texts = [c["text"] for c in spec["acceptance_criteria"]]
    assert "total from live steps" in texts
    assert spec["non_goals"] == ["apply cap"]
    assert spec["story"].startswith("We add a cost preview.")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_delivery_story_intent.py -q`
Expected: FAIL — the assembled spec has no `story` key / criteria come from the old path.

- [ ] **Step 3: Write minimal implementation**

Read `assemble_pr_intent` in `archie/standalone/delivery_review.py`. Replace the block that reads `.archie/intent.json` with a story-store load. Reuse the existing `_branch` resolution (import from `sync` is undesirable; inline the same env/git logic or import `story_store` + read `GITHUB_HEAD_REF`/`ARCHIE_BRANCH`). Minimal shape:

```python
# inside assemble_pr_intent(root, pr_meta), replacing the intent.json read:
    import os
    import story_store
    branch = (pr_meta.get("head_ref") or os.environ.get("ARCHIE_BRANCH")
              or os.environ.get("GITHUB_HEAD_REF") or "")
    story = story_store.current_story(root, branch)
    committed = {"acceptance_criteria": [], "non_goals": [], "source": "sync",
                 "confirmed": False, "story": ""}
    if story:
        committed["acceptance_criteria"] = [
            {"id": f.get("id"), "text": f.get("text", ""), "from": f.get("from")}
            for f in story["facts"]]
        committed["non_goals"] = story["non_goals"]
        committed["confirmed"] = bool(story["meta"].get("confirmed"))
        committed["story"] = story["story"]
    # then merge committed ⊕ PR title/body exactly as the prior code did (keep merge_specs call)
```

Keep the subsequent PR-body merge (`merge_specs` / title+body handling) unchanged so PR-only intent still works when there is no story.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_delivery_story_intent.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/delivery_review.py tests/test_delivery_story_intent.py
git commit -m "feat(story): delivery review loads story facts (drop intent.json read)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Delivery review — render the story + per-fact provenance

**Files:**
- Modify: `archie/standalone/delivery_review.py` (function `render_verdict`)
- Test: `tests/test_delivery_review.py` (append)

**Interfaces:**
- Consumes: the `story` on the spec (Task 8), `verdict`, `confirmed`.
- Produces: verdict markdown that includes a collapsible story block above the criteria, and appends each criterion's `from:` source to its ✓/✗ line.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_delivery_review.py
def test_render_verdict_includes_story_and_provenance():
    import delivery_review as dr
    verdict = {"intent_completeness": "1/1", "breaks": 0, "possible_issues": 0, "conflicts": 0}
    spec = {"story": "We add a per-run cost preview.",
            "acceptance_criteria": [{"id": "f1", "text": "total from live steps",
                                     "from": {"src": "plan", "quote": "computed fresh from live steps"}}]}
    body = dr.render_verdict(verdict, [], spec)
    assert "We add a per-run cost preview." in body        # story shown
    assert "computed fresh from live steps" in body        # per-fact provenance shown
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_delivery_review.py::test_render_verdict_includes_story_and_provenance -q`
Expected: FAIL — story/provenance not in output.

- [ ] **Step 3: Write minimal implementation**

In `render_verdict`, after the header `> Grading against …` line and before `**Built the intent?**`, insert the story; and in the per-criterion loop, append the source. Concretely:

```python
    # after the provenance/trust header block, before "Built the intent?":
    story = (spec.get("story") or "").strip()
    if story:
        lines.append("")
        lines.append("<details><summary>Task story</summary>\n\n" + _sanitize(story) + "\n\n</details>")

    # in the acceptance-criteria loop, change the criterion line to include its source:
    for c in crit:
        mark = "❌" if c.get("id") in unmet_ids else "✅"
        src = _sanitize(((c.get("from") or {}).get("quote") or ""))
        suffix = f"  ·  _from: {src[:70]}_" if src else ""
        lines.append(f"- {mark} {_sanitize(c.get('id'))} — {_sanitize(c.get('text', ''))}{suffix}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_delivery_review.py -q`
Expected: PASS (all, including the new test).

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/delivery_review.py tests/test_delivery_review.py
git commit -m "feat(story): render task story + per-fact provenance in the verdict

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: Silent trigger — Stop hook fires the imprint (non-blocking)

**Files:**
- Modify: `archie/assets/hook_scripts/stop.sh`
- Modify: `archie/assets/workflow/sync/SKILL.md` (Step 5b copy)
- Test: `tests/test_stop_imprint_hook.py` (create)

**Interfaces:**
- Consumes: `sync.py imprint`, `intent_capture` transition state.
- Produces: the Stop hook, when at least one transition has been recorded since the last imprint, launches `python3 "$PROJECT_ROOT/.archie/sync.py" imprint "$PROJECT_ROOT"` **in the background** (`&`, output discarded) so it never blocks the turn; always exits with the enforcement/original code.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stop_imprint_hook.py
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "archie" / "assets" / "hook_scripts" / "stop.sh"


def test_stop_hook_launches_imprint_in_background_nonblocking():
    text = SCRIPT.read_text()
    assert "sync.py" in text and "imprint" in text
    # must be backgrounded so it never blocks the turn
    line = next(l for l in text.splitlines() if "imprint" in l and "sync.py" in l)
    assert line.rstrip().endswith("&"), f"imprint call must be backgrounded: {line!r}"
    # uses PROJECT_ROOT, not cwd
    assert "$PROJECT_ROOT/.archie/sync.py" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_stop_imprint_hook.py -q`
Expected: FAIL — `imprint` not present in `stop.sh`.

- [ ] **Step 3: Write minimal implementation**

Read `archie/assets/hook_scripts/stop.sh`. It already computes `PROJECT_ROOT`. Before its final `exit`, add (guarded so a missing script/pending-state is a silent no-op):

```bash
# Silently imprint the task story when a discussion→implementation transition is
# pending (best-effort, backgrounded — must never block the turn end).
if [ -z "$ARCHIE_INTERNAL" ] && [ -f "$PROJECT_ROOT/.archie/sync.py" ]; then
  nohup python3 "$PROJECT_ROOT/.archie/sync.py" imprint "$PROJECT_ROOT" >/dev/null 2>&1 &
fi
```

Then update `archie/assets/workflow/sync/SKILL.md` Step 5b: replace the `synthesize-intent`/`show-intent` lines with `python3 .archie/sync.py imprint .` (regenerate the story) and `python3 .archie/sync.py story .` (review the story + facts). Copy the SKILL to `npm-package/assets/workflow/sync/SKILL.md`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_stop_imprint_hook.py -q`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add archie/assets/hook_scripts/stop.sh archie/assets/workflow/sync/SKILL.md npm-package/assets/workflow/sync/SKILL.md tests/test_stop_imprint_hook.py
git commit -m "feat(story): silent background imprint on Stop; sync SKILL step 5b

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Retire `intent_synthesize.py`, sync mirrors, register scripts, full green

**Files:**
- Delete: `archie/standalone/intent_synthesize.py`, `npm-package/assets/intent_synthesize.py`, `tests/test_intent_synthesize.py`
- Modify: `npm-package/bin/archie.mjs` (script list)
- Copy: the new/changed standalone files into `npm-package/assets/`

**Interfaces:**
- Consumes: everything above.
- Produces: a synced, self-consistent package (`verify_sync.py` passes) with the retired module removed and the two new modules registered.

- [ ] **Step 1: Delete the retired module + its test, and check for stragglers**

```bash
git rm archie/standalone/intent_synthesize.py npm-package/assets/intent_synthesize.py tests/test_intent_synthesize.py
grep -rn "intent_synthesize\|synthesize-intent\|show-intent\|confirm-intent" archie/ npm-package/ .claude/ | grep -v node_modules
```
Expected: no remaining references (fix any that print — e.g. stale help text or command docs).

- [ ] **Step 2: Sync canonical → npm mirror + register new scripts**

```bash
cp archie/standalone/story_store.py       npm-package/assets/story_store.py
cp archie/standalone/story_synthesize.py  npm-package/assets/story_synthesize.py
cp archie/standalone/sync.py              npm-package/assets/sync.py
cp archie/standalone/delivery_review.py   npm-package/assets/delivery_review.py
```
Then edit `npm-package/bin/archie.mjs`: in the script-list array, remove `"intent_synthesize.py"` and add `"story_store.py", "story_synthesize.py"`.

- [ ] **Step 3: Run the sync checker**

Run: `python3 scripts/verify_sync.py`
Expected: `SYNC CHECK PASSED — <N> scripts, workflow + assets all in sync.`

- [ ] **Step 4: Run the standalone test subset**

Run:
```bash
python3 -m pytest tests/test_story_store.py tests/test_story_synthesize.py \
  tests/test_story_subcommands.py tests/test_delivery_story_intent.py \
  tests/test_delivery_review.py tests/test_stop_imprint_hook.py \
  tests/test_editor_gate.py tests/test_verdict.py tests/test_diff_basis.py -q
```
Expected: PASS (all). Then run the broader suite and confirm only the 3 known pre-existing failures remain:
```bash
python3 -m pytest tests/ -q --continue-on-collection-errors 2>&1 | grep -E "passed|failed"
```
Expected: `3 failed, <N> passed …` where the 3 are `test_churn_track_hook_updates_counter`, `test_stop_nudges_when_churn_crossed`, `test_codex_rendered_tree_uses_codex_command_prefix_not_slash`.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(story): retire intent_synthesize, sync mirrors, register scripts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- §3 four decisions → Tasks 4–6 (source/story/facts/two-pass), 8 (grading), 10 (silent trigger). ✓
- §4 single versioned file (prose + fenced facts, `extract_json_obj`) → Tasks 2, 3. ✓
- §5 retention + session-scoped currency → Task 3 (`list_versions`, `current_story(session_id)`, `next_version`). ✓
- §6 components → story_synthesize (4–6), ticket source (4), `archie story` (7), verdict render (9), intent_capture unchanged (no task — correct). ✓
- §8 faithfulness guardrails → Task 5 (`validate_provenance` drops the `billable_step_count` invention — asserted). ✓
- §9 grading integration (edge-A on facts) → Task 8. ✓
- §10 degradation (no sources, bad output, malformed) → Tasks 6 (`None` paths), 2 (`parse_story_file` → `{}`). ✓
- §11 retire intent_synthesize + intent.json read → Tasks 8, 11. ✓
- §12 YAGNI (no Linear, no confirm gate, no back-and-forth) → honored; `confirmed` stays advisory metadata only. ✓
- §13 testing → each task ships tests; provenance-drop, session-currency, round-trip, blindness all covered. ✓

**Placeholder scan:** none — every code step shows complete code; wiring tasks name the exact function/dispatch to edit and give the full replacement snippet.

**Type consistency:** `imprint(root, branch, session_id, timestamp, run=None)` (Task 6) matches its caller in Task 7; `write_story(...)` / `next_version` / `current_story` signatures are consistent across Tasks 2–3, 6–8; facts carry `{id, text, from, kind}` consistently from Task 5 through render in Task 9; `parse_story_file` returns `{story, meta, facts, non_goals}` used identically in Tasks 3, 7, 8.

**Note for the implementer:** Tasks 7, 8, 9 modify existing functions — **read the current function first** (`sync.py __main__` dispatch, `delivery_review.assemble_pr_intent`, `delivery_review.render_verdict`) and splice the shown snippet into the real control flow rather than pasting blindly; keep the existing PR-body merge in `assemble_pr_intent`.

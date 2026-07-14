# Clean-Room Intent Capture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture intent at the discussion→implementation transition via the edit/prompt hooks Archie already installs (cheap, deterministic), then have an isolated agent — blind to the code — turn the logged verbatim requirement into a transparent, human-ratifiable `.archie/intent.json`.

**Architecture:** A deterministic event log (`intent_capture.py`) fed by the existing `pre-turn.sh`/`pre-validate.sh` hooks; an isolated LLM transform (`intent_synthesize.py`) that reads ONLY the events and regenerates the criteria (kills the scope-ratchet); `sync.py` subcommands for visibility + ratification; `non_goals` threaded into the reviewers; and a self-explanatory verdict comment. The coding agent no longer authors the yardstick.

**Tech Stack:** Zero-dependency Python 3.9+ stdlib. Tests: pytest, LLM mocked. Decision: human confirmation is **default-on-but-optional** — unconfirmed intent still grades, but the verdict labels it lower-trust.

## Global Constraints

- **Zero runtime dependencies** beyond Python 3.9+ stdlib. Only interpreter is `python3` (3.9.6); run tests with `python3 -m pytest` (no `python` on PATH).
- **File sync:** edit `archie/standalone/*.py` first, copy to `npm-package/assets/*.py`; edit `archie/assets/hook_scripts/*` first, copy to the `.archie/hooks/`-mirrored asset location per the existing pattern. Register any NEW standalone script in `npm-package/bin/archie.mjs`'s copy list. `python3 scripts/verify_sync.py` must PASS before every commit.
- **Import convention:** standalone modules import siblings BARE via guarded `sys.path.insert(0, str(Path(__file__).parent))` (`if _p not in sys.path`); tests use `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))` + bare `import <module>`. NEVER `from archie.standalone.X` (trips `tomllib` on 3.9).
- **LLM-injection convention:** LLM orchestrators take `run=None` then `if run is None: run = run_verifier` (call-time lookup).
- **Blindness (the core invariant):** `intent_synthesize` must read ONLY `.archie/intent-events.jsonl`. It must NEVER read the diff, blueprint code, or the coding conversation. Tests assert the built prompt contains no code and carries the "you are NOT shown the implementation" instruction.
- **Hooks are best-effort:** every hook path exits 0 and never blocks/fails the agent's action; any error → silent no-op.
- **Committed artifacts:** `.archie/intent-events.jsonl` and `.archie/intent.json` are committed (not gitignored); writes are atomic (`os.replace`).
- **Supersede:** this removes the old sync-SKILL "agent authors criteria" step; `.archie/intent.json` is henceforth written only by `intent_synthesize` or a human edit.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Task 1: Intent-event log + transition state machine — `intent_capture.py`

**Files:**
- Create: `archie/standalone/intent_capture.py`
- Modify: `npm-package/bin/archie.mjs` (add `"intent_capture.py"` to the script list)
- Test: `tests/test_intent_capture.py`

**Interfaces:**
- Produces: `EVENTS_FILE = "intent-events.jsonl"`; `record_user_turn(root, text) -> None`; `note_edit(root) -> bool` (records a `transition` marker + returns True iff this edit follows ≥1 unconsumed user turn); `load_events(root) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intent_capture.py
import sys
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent_capture as ic  # noqa: E402


def test_record_user_turn_appends_verbatim(tmp_path):
    ic.record_user_turn(tmp_path, "Add tenant-scoped export")
    events = ic.load_events(tmp_path)
    assert len(events) == 1 and events[0]["kind"] == "user_turn"
    assert events[0]["text"] == "Add tenant-scoped export"


def test_note_edit_fires_transition_only_after_a_planning_turn(tmp_path):
    # edit with no prior user turn -> no transition
    assert ic.note_edit(tmp_path) is False
    ic.record_user_turn(tmp_path, "plan: add rate limiting")
    # first edit after the turn -> transition
    assert ic.note_edit(tmp_path) is True
    # a second edit with no new turn -> no transition (already implementing)
    assert ic.note_edit(tmp_path) is False
    # new planning turn, then edit -> transition again (multi-point)
    ic.record_user_turn(tmp_path, "re-plan: also audit-log")
    assert ic.note_edit(tmp_path) is True
    transitions = [e for e in ic.load_events(tmp_path) if e["kind"] == "transition"]
    assert len(transitions) == 2


def test_malformed_line_is_skipped(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir()
    (ad / "intent-events.jsonl").write_text('{"kind":"user_turn","text":"ok"}\nnot json\n')
    assert [e["text"] for e in ic.load_events(tmp_path)] == ["ok"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_intent_capture.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'intent_capture'`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/intent_capture.py
"""Deterministic intent-event log. Fed by the edit/prompt hooks; NO LLM.
Detects the discussion->implementation transition so intent is captured
forward-looking at each plan->implement boundary. Best-effort: never raises.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)

EVENTS_FILE = "intent-events.jsonl"
_STATE_FILE = "intent-hook-state.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M")


def _events_path(root) -> Path:
    return Path(root) / ".archie" / EVENTS_FILE


def _append(root, event: dict) -> None:
    p = _events_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event) + "\n")


def _state_path(root) -> Path:
    return Path(root) / ".archie" / "tmp" / _STATE_FILE


def _load_state(root) -> dict:
    try:
        return json.loads(_state_path(root).read_text())
    except Exception:
        return {"pending_turns": 0}


def _save_state(root, state: dict) -> None:
    p = _state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state))
    import os
    os.replace(tmp, p)


def record_user_turn(root, text) -> None:
    """Append a verbatim user turn and mark a planning turn as pending."""
    text = str(text or "").strip()
    if not text:
        return
    _append(root, {"ts": _now(), "kind": "user_turn", "phase": "planning", "text": text})
    st = _load_state(root)
    st["pending_turns"] = int(st.get("pending_turns", 0)) + 1
    _save_state(root, st)


def note_edit(root) -> bool:
    """Called when a code-mutating tool runs. Records a transition marker iff
    this edit follows >=1 unconsumed planning turn. Returns whether it did."""
    st = _load_state(root)
    pending = int(st.get("pending_turns", 0))
    if pending <= 0:
        return False
    _append(root, {"ts": _now(), "kind": "transition", "phase": "implementation",
                   "note": f"first edit after {pending} planning turn(s)"})
    st["pending_turns"] = 0
    _save_state(root, st)
    return True


def load_events(root) -> list:
    p = _events_path(root)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


if __name__ == "__main__":
    # CLI for the hook scripts. Best-effort: always exit 0.
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else ""
        root = sys.argv[2] if len(sys.argv) > 2 else "."
        if cmd == "user-turn":
            record_user_turn(root, sys.stdin.read())
        elif cmd == "edit":
            note_edit(root)  # SILENT by design: no mid-work noise. Transparency lives in the
            # PR verdict comment + on-demand `show-intent`, never a terminal nag.
    except Exception:
        pass
    sys.exit(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_intent_capture.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/intent_capture.py npm-package/assets/intent_capture.py
# add "intent_capture.py" to the script array in npm-package/bin/archie.mjs
python3 scripts/verify_sync.py
git add archie/standalone/intent_capture.py npm-package/assets/intent_capture.py npm-package/bin/archie.mjs tests/test_intent_capture.py
git commit -m "feat(intent): deterministic intent-event log + transition state machine

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Isolated transform (blind to code) — `intent_synthesize.py`

**Files:**
- Create: `archie/standalone/intent_synthesize.py`
- Modify: `npm-package/bin/archie.mjs` (add `"intent_synthesize.py"`)
- Test: `tests/test_intent_synthesize.py`

**Interfaces:**
- Consumes: `intent_capture.load_events`; `evidence_schema.extract_json_obj`; `agent_cli.run_verifier`.
- Produces: `build_synthesis_prompt(events: list) -> str`; `parse_synthesis(raw: str) -> dict`; `synthesize(root, run=None) -> dict | None` (regenerates `.archie/intent.json` authoritatively from events — can RETIRE criteria — with `confirmed: false` + provenance; returns the spec or None if no events).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intent_synthesize.py
import sys, json
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import intent_synthesize as isyn  # noqa: E402
import intent_capture as ic  # noqa: E402


def test_prompt_is_blind_to_implementation():
    p = isyn.build_synthesis_prompt([{"kind": "user_turn", "text": "Add tenant-scoped export"}])
    assert "tenant-scoped export" in p
    assert "NOT shown the implementation" in p
    # blindness: the prompt must not smuggle code/diff markers
    assert "diff --git" not in p and "def " not in p


def test_parse_synthesis_maps_fields():
    raw = '{"goals":["Scope export"],"acceptance_criteria":[{"id":"ac1","text":"tenant scoped"}],"non_goals":["no UI change"]}'
    out = isyn.parse_synthesis(raw)
    assert out["goals"] == ["Scope export"]
    assert out["acceptance_criteria"][0]["text"] == "tenant scoped"
    assert out["non_goals"] == ["no UI change"]


def test_synthesize_writes_unconfirmed_spec_with_provenance(tmp_path):
    ic.record_user_turn(tmp_path, "Add tenant-scoped export, rate-limited")
    fake = lambda *a, **k: '{"goals":["G"],"acceptance_criteria":[{"id":"ac1","text":"scoped"}],"non_goals":[]}'
    spec = isyn.synthesize(tmp_path, run=fake)
    assert spec["confirmed"] is False and spec["capture_points"] >= 1
    on_disk = json.loads((tmp_path / ".archie" / "intent.json").read_text())
    assert on_disk["acceptance_criteria"][0]["text"] == "scoped"


def test_resynthesize_can_retire_criteria(tmp_path):
    ic.record_user_turn(tmp_path, "v1")
    isyn.synthesize(tmp_path, run=lambda *a, **k: '{"acceptance_criteria":[{"id":"ac1","text":"old"},{"id":"ac2","text":"drop me"}],"goals":[],"non_goals":[]}')
    ic.record_user_turn(tmp_path, "v2: dropped one")
    spec = isyn.synthesize(tmp_path, run=lambda *a, **k: '{"acceptance_criteria":[{"id":"ac1","text":"old"}],"goals":[],"non_goals":[]}')
    assert [c["text"] for c in spec["acceptance_criteria"]] == ["old"]   # retired, not accreted


def test_synthesize_no_events_returns_none(tmp_path):
    assert isyn.synthesize(tmp_path, run=lambda *a, **k: "{}") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_intent_synthesize.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write minimal implementation**

```python
# archie/standalone/intent_synthesize.py
"""Isolated intent transform: reads ONLY the intent-event log and regenerates
.archie/intent.json acceptance criteria. BLIND to the implementation by contract —
it never opens the diff, code, or the coding conversation. Regeneration (not union)
lets a re-plan RETIRE criteria, killing the scope-ratchet.
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)
from intent_capture import load_events            # noqa: E402
from evidence_schema import extract_json_obj       # noqa: E402

_SYSTEM = (
    "You author acceptance criteria for a change from its REQUIREMENT ONLY. "
    "You are NOT shown the implementation, diff, or code — do not assume how it was built. "
    "From the requirement/planning turns below, write the goals, concrete checkable "
    "acceptance_criteria, and any non_goals (things explicitly out of scope). "
    "Return JSON {\"goals\":[...],\"acceptance_criteria\":[{\"id\":\"ac1\",\"text\":\"...\"}],\"non_goals\":[...]}."
)


def build_synthesis_prompt(events) -> str:
    turns = "\n".join(f"- {e.get('text','')}" for e in (events or []) if e.get("kind") == "user_turn" and e.get("text"))
    return f"{_SYSTEM}\n\nREQUIREMENT / PLANNING TURNS:\n{turns}"


def parse_synthesis(raw) -> dict:
    data = extract_json_obj(raw or "")
    crit = []
    for i, c in enumerate(data.get("acceptance_criteria") or []):
        text = (c.get("text") if isinstance(c, dict) else str(c)) or ""
        if text.strip():
            crit.append({"id": f"ac{i + 1}", "text": text})
    goals = [str(g) for g in (data.get("goals") or []) if str(g).strip()]
    non_goals = [str(g) for g in (data.get("non_goals") or []) if str(g).strip()]
    return {"goals": goals, "acceptance_criteria": crit, "non_goals": non_goals}


def synthesize(root, run=None):
    """Regenerate .archie/intent.json from the event log (authoritative). Returns
    the spec, or None if there are no events. Blind to the implementation."""
    if run is None:
        from agent_cli import run_verifier
        run = run_verifier
    events = load_events(root)
    if not any(e.get("kind") == "user_turn" for e in events):
        return None
    raw = run(build_synthesis_prompt(events), Path(root), "claude")
    parsed = parse_synthesis(raw or "")
    caps = sorted({e["ts"] for e in events if e.get("kind") == "user_turn" and e.get("ts")})
    spec = {
        "source": "sync",
        "confidence": "medium",
        "goals": parsed["goals"],
        "acceptance_criteria": parsed["acceptance_criteria"],
        "non_goals": parsed["non_goals"],
        "ticket_ids": [],
        "raw": "",
        "confirmed": False,
        "capture_points": len(caps),
        "captured_at": caps,
        "synthesized_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M"),
    }
    p = Path(root) / ".archie" / "intent.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(spec, indent=2))
    os.replace(tmp, p)
    return spec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_intent_synthesize.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/intent_synthesize.py npm-package/assets/intent_synthesize.py
# add "intent_synthesize.py" to npm-package/bin/archie.mjs
python3 scripts/verify_sync.py
git add archie/standalone/intent_synthesize.py npm-package/assets/intent_synthesize.py npm-package/bin/archie.mjs tests/test_intent_synthesize.py
git commit -m "feat(intent): isolated blind transform regenerates intent.json from events

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Transparency subcommands — `sync.py show/synthesize/confirm/capture-intent`

**Files:**
- Modify: `archie/standalone/sync.py` (4 `cmd_*` + dispatch + `_usage`)
- Test: `tests/test_intent_subcommands.py`

**Interfaces:**
- Consumes: `intent_synthesize.synthesize`, `intent_capture.record_user_turn`.
- Produces: `cmd_synthesize_intent(root) -> int`; `cmd_show_intent(root) -> int`; `cmd_confirm_intent(root) -> int`; `cmd_capture_intent(root, text) -> int`. All return 0.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intent_subcommands.py
import sys, json
from pathlib import Path
_STANDALONE = Path(__file__).resolve().parent.parent / "archie" / "standalone"
sys.path.insert(0, str(_STANDALONE))
import sync  # noqa: E402


def _write_intent(tmp_path):
    ad = tmp_path / ".archie"; ad.mkdir(parents=True, exist_ok=True)
    (ad / "intent.json").write_text(json.dumps({"source": "sync", "confidence": "medium",
        "goals": ["G"], "acceptance_criteria": [{"id": "ac1", "text": "Scoped"}],
        "non_goals": [], "confirmed": False, "capture_points": 2}))


def test_show_intent_renders_criteria_and_provenance(tmp_path, capsys):
    _write_intent(tmp_path)
    assert sync.cmd_show_intent(tmp_path) == 0
    out = capsys.readouterr().out
    assert "Scoped" in out and "ac1" in out and "confirmed" in out.lower()


def test_confirm_intent_sets_flag(tmp_path):
    _write_intent(tmp_path)
    assert sync.cmd_confirm_intent(tmp_path) == 0
    assert json.loads((tmp_path / ".archie" / "intent.json").read_text())["confirmed"] is True


def test_capture_intent_appends_event(tmp_path):
    assert sync.cmd_capture_intent(tmp_path, "add rate limiting") == 0
    import intent_capture as ic
    assert any("rate limiting" in e.get("text", "") for e in ic.load_events(tmp_path))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_intent_subcommands.py -v`
Expected: FAIL (`AttributeError: module 'sync' has no attribute 'cmd_show_intent'`).

- [ ] **Step 3: Add the four subcommands + dispatch**

Add to `archie/standalone/sync.py` (near other `cmd_*`; the guarded bare-import helper is the file's existing pattern):
```python
def _intent_imports():
    import sys as _sys
    _pp = str(Path(__file__).parent)
    if _pp not in _sys.path:
        _sys.path.insert(0, _pp)
    import intent_capture, intent_synthesize
    return intent_capture, intent_synthesize


def cmd_capture_intent(root, text) -> int:
    ic, _ = _intent_imports()
    ic.record_user_turn(root, text or "")
    print("[archie] intent event captured")
    return 0


def cmd_synthesize_intent(root) -> int:
    _, isyn = _intent_imports()
    spec = isyn.synthesize(root)
    if not spec:
        print("[archie] no intent events yet — nothing to synthesize")
        return 0
    print(f"[archie] synthesized {len(spec['acceptance_criteria'])} acceptance criteria "
          f"(unconfirmed). Review: python3 .archie/sync.py show-intent .")
    return 0


def cmd_show_intent(root) -> int:
    p = Path(root) / ".archie" / "intent.json"
    if not p.exists():
        print("[archie] no .archie/intent.json yet")
        return 0
    spec = json.loads(p.read_text())
    print("== Archie branch intent ==")
    print(f"source: {spec.get('source','?')}  confidence: {spec.get('confidence','?')}  "
          f"confirmed: {spec.get('confirmed', False)}  capture_points: {spec.get('capture_points','?')}")
    for g in spec.get("goals", []):
        print(f"  goal: {g}")
    for c in spec.get("acceptance_criteria", []):
        print(f"  [{c.get('id')}] {c.get('text')}")
    for n in spec.get("non_goals", []):
        print(f"  non-goal: {n}")
    return 0


def cmd_confirm_intent(root) -> int:
    p = Path(root) / ".archie" / "intent.json"
    if not p.exists():
        print("[archie] no .archie/intent.json to confirm")
        return 0
    spec = json.loads(p.read_text())
    spec["confirmed"] = True
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(spec, indent=2))
    import os
    os.replace(tmp, p)
    print("[archie] intent confirmed — the delivery review will grade against these criteria")
    return 0
```
In the dispatch block add:
```python
    if cmd == "capture-intent":
        return cmd_capture_intent(root, argv[3] if len(argv) > 3 else "")
    if cmd == "synthesize-intent":
        return cmd_synthesize_intent(root)
    if cmd == "show-intent":
        return cmd_show_intent(root)
    if cmd == "confirm-intent":
        return cmd_confirm_intent(root)
```
And four `_usage()` lines describing them.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_intent_subcommands.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/sync.py npm-package/assets/sync.py
python3 scripts/verify_sync.py
git add archie/standalone/sync.py npm-package/assets/sync.py tests/test_intent_subcommands.py
git commit -m "feat(sync): show/synthesize/confirm/capture-intent subcommands (transparency)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Wire the existing hooks + retire the silent SKILL step

**Files:**
- Modify: `archie/assets/hook_scripts/pre-turn.sh` (append a user-turn capture) → copy to the npm/`.archie` mirror
- Modify: `archie/assets/hook_scripts/pre-validate.sh` (add an edit-transition marker call) → copy to mirror
- Modify: `archie/assets/workflow/sync/SKILL.md` (REMOVE the "Capture branch intent" agent-authoring step; point to `synthesize-intent`/`show-intent`) → copy to mirror
- Test: `tests/test_intent_hook_wiring.py`

**Interfaces:**
- Consumes: `intent_capture.py` CLI (`user-turn` / `edit`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_intent_hook_wiring.py
from pathlib import Path


def _hook(name):
    return (Path(__file__).resolve().parent.parent / "archie" / "assets" / "hook_scripts" / name).read_text()


def test_pre_turn_captures_user_intent():
    s = _hook("pre-turn.sh")
    assert "intent_capture.py" in s and "user-turn" in s


def test_pre_validate_marks_edit_transition():
    s = _hook("pre-validate.sh")
    assert "intent_capture.py" in s and "edit" in s


def test_sync_skill_no_longer_authors_criteria():
    skill = (Path(__file__).resolve().parent.parent / "archie" / "assets" / "workflow"
             / "sync" / "SKILL.md").read_text()
    # the old silent-authoring step is gone; replaced by synthesize/show
    assert "synthesize-intent" in skill or "show-intent" in skill
    assert "author `goals` and concrete" not in skill  # the old silent-author instruction removed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_intent_hook_wiring.py -v`
Expected: FAIL (hooks don't reference intent_capture yet).

- [ ] **Step 3: Wire the hooks (best-effort, never block)**

At the END of `archie/assets/hook_scripts/pre-turn.sh` (before its final `exit 0`), append:
```bash
# Archie intent capture (best-effort; never blocks the turn). Feeds the clean-room
# intent transform. The prompt is on stdin as JSON; capture it verbatim.
if [ -f .archie/intent_capture.py ]; then
  python3 -c "import sys,json;print(json.load(sys.stdin).get('prompt',''))" 2>/dev/null \
    | python3 .archie/intent_capture.py user-turn . 2>/dev/null || true
fi
```
(If `pre-turn.sh` already consumes stdin, capture stdin to a var first and tee it — match the script's existing stdin handling; the key requirement is a verbatim user-turn append that cannot fail the hook.)

At the END of `archie/assets/hook_scripts/pre-validate.sh` (before its terminal exit), append:
```bash
# Archie intent capture: mark the discussion->implementation transition (best-effort).
if [ -f .archie/intent_capture.py ]; then
  python3 .archie/intent_capture.py edit . 2>/dev/null || true
fi
```
In `archie/assets/workflow/sync/SKILL.md`, DELETE the "### Capture branch intent (for delivery review)" step that instructs the agent to author `goals`/`acceptance_criteria` and run `write-intent`. Replace it with:
```markdown
### Branch intent (captured automatically)

Archie captures your intent automatically from your planning turns (via hooks). To synthesize the
current acceptance criteria from those events and review them:

- `python3 .archie/sync.py synthesize-intent .`  — regenerate criteria from captured events (blind to code)
- `python3 .archie/sync.py show-intent .`         — review the goals + criteria + provenance
- `python3 .archie/sync.py confirm-intent .`      — mark them human-confirmed (optional; unconfirmed still grades, labeled lower-trust)

Stage `.archie/intent.json` and `.archie/intent-events.jsonl` so they commit with the branch.
```

- [ ] **Step 4: Copy mirrors, run tests + sync**

```bash
# copy the two hook scripts + SKILL.md to their npm/.archie mirror locations per the repo pattern
python3 -m pytest tests/test_intent_hook_wiring.py -v      # 3 passed
python3 scripts/verify_sync.py                             # PASS
```

- [ ] **Step 5: Commit**

```bash
git add archie/assets/hook_scripts/pre-turn.sh archie/assets/hook_scripts/pre-validate.sh \
        archie/assets/workflow/sync/SKILL.md tests/test_intent_hook_wiring.py \
        npm-package/assets/  # (the synced mirrors)
git commit -m "feat(hooks): wire intent capture into pre-turn/pre-validate; retire silent SKILL step

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Thread `non_goals` into the reviewers

**Files:**
- Modify: `archie/standalone/intent.py` (`merge_specs` carries `non_goals`)
- Modify: `archie/standalone/reconcile.py` (`build_edge_a_prompt` + `build_conformance_prompt` include non_goals) and `archie/standalone/behavioral_review.py` (via `intent_brief`)
- Test: `tests/test_committed_intent.py`, `tests/test_reconcile_edge_a.py`

**Interfaces:**
- Consumes: existing `merge_specs`, `intent_brief`.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_committed_intent.py
def test_merge_specs_carries_non_goals():
    a = {"source": "sync", "acceptance_criteria": [], "goals": [], "non_goals": ["no schema change"], "raw": ""}
    b = {"source": "pr_body", "acceptance_criteria": [], "goals": [], "non_goals": [], "raw": ""}
    assert it.merge_specs(a, b).get("non_goals") == ["no schema change"]
```
```python
# add to tests/test_reconcile_edge_a.py
def test_edge_a_prompt_includes_non_goals():
    spec = it.normalize("", source="sync", ticket_ids=[])
    spec["acceptance_criteria"] = [{"id": "ac1", "text": "scope it"}]
    spec["non_goals"] = ["do not touch the import path"]
    p = rc.build_edge_a_prompt(spec, "diff")
    assert "import path" in p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_committed_intent.py -k non_goals tests/test_reconcile_edge_a.py -k non_goals -v`
Expected: FAIL (`non_goals` dropped by merge_specs / absent from prompt).

- [ ] **Step 3: Implement**

In `archie/standalone/intent.py` `merge_specs`, union `non_goals` like `goals` and add it to the returned dict:
```python
    non_goals, ngseen = [], set()
    for s in specs:
        for g in (s.get("non_goals") or []):
            k = str(g).strip().lower()
            if k and k not in ngseen:
                ngseen.add(k)
                non_goals.append(str(g))
```
and add `"non_goals": non_goals,` to the returned dict.
In `archie/standalone/reconcile.py` `build_edge_a_prompt`, append a non-goals section when present:
```python
    ng = "\n".join(f"- {g}" for g in (intent_spec.get("non_goals") or []))
    ng_block = f"\n\nNON-GOALS (flag any diff behavior that violates these):\n{ng}" if ng else ""
```
and include `ng_block` in the returned prompt. Do the same in `build_conformance_prompt`. In `intent.intent_brief`, append `Non-goals:` lines so the behavioral reviewer sees them too.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_committed_intent.py tests/test_reconcile_edge_a.py tests/test_behavioral_review.py -v`
Expected: PASS (existing + new).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/intent.py npm-package/assets/intent.py
cp archie/standalone/reconcile.py npm-package/assets/reconcile.py
cp archie/standalone/behavioral_review.py npm-package/assets/behavioral_review.py
python3 scripts/verify_sync.py
git add archie/standalone/intent.py archie/standalone/reconcile.py archie/standalone/behavioral_review.py npm-package/assets/*.py tests/test_committed_intent.py tests/test_reconcile_edge_a.py
git commit -m "feat(review): thread non_goals into edge-A/conformance/behavioral prompts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Self-explanatory verdict comment + honest completeness

**Files:**
- Modify: `archie/standalone/reconcile.py` (`aggregate_verdict`: unknown vs met)
- Modify: `archie/standalone/delivery_review.py` (`render_verdict` takes `spec`; renders criteria + provenance + confirmed + correction footer; the caller passes `spec`)
- Test: `tests/test_verdict.py`, `tests/test_delivery_review.py`

**Interfaces:**
- Produces: `aggregate_verdict` returns an extra `unknown` count; `render_verdict(verdict, confirmed, spec) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_verdict.py
def test_aggregate_reports_unknown_criteria():
    spec = it.normalize("", source="sync", ticket_ids=[])
    spec["acceptance_criteria"] = [{"id": "ac1"}, {"id": "ac2"}, {"id": "ac3"}]
    confirmed = [{"kind": "intent_unmet", "criterion_id": "ac1"}]   # only 1 of 3 has a verdict
    v = rc.aggregate_verdict(spec, confirmed)
    assert v["unknown"] == 2 and v["intent_completeness"] == "0/3"   # 2 unaddressed are NOT counted met
```
```python
# add to tests/test_delivery_review.py
def test_render_verdict_shows_criteria_provenance_and_correction(tmp_path):
    spec = {"source": "sync", "confidence": "medium", "confirmed": False,
            "acceptance_criteria": [{"id": "ac1", "text": "tenant scoped"}, {"id": "ac2", "text": "rate limited"}]}
    verdict = {"intent_completeness": "1/2", "breaks": 0, "conflicts": 0, "unknown": 0}
    confirmed = [{"kind": "intent_unmet", "criterion_id": "ac2", "problem_statement": "no limiter",
                  "anchor": {"file": "x.py", "line": 4}, "source": "reconcile:edgeA"}]
    md = dr.render_verdict(verdict, confirmed, spec)
    assert "tenant scoped" in md and "rate limited" in md      # criteria listed
    assert "medium" in md and "unconfirmed" in md.lower()      # provenance + trust label
    assert "intent.json" in md                                  # correction loop stated
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_verdict.py -k unknown tests/test_delivery_review.py -k provenance -v`
Expected: FAIL (`unknown` not in verdict; `render_verdict` takes 2 args).

- [ ] **Step 3: Implement**

In `archie/standalone/reconcile.py` `aggregate_verdict`: build the set of criterion ids that got a verdict, count `unknown = total - addressed`, and compute `met = addressed - unmet` (so unaddressed criteria are `unknown`, never silently `met`). Add `"unknown": unknown` to the return dict; completeness stays `met/total`.

In `archie/standalone/delivery_review.py`, change `render_verdict(verdict, confirmed)` → `render_verdict(verdict, confirmed, spec)`:
```python
def render_verdict(verdict, confirmed, spec=None):
    spec = spec or {}
    crit = spec.get("acceptance_criteria") or []
    unmet_ids = {f.get("criterion_id") for f in confirmed if f.get("kind") in ("intent_unmet", "intent_partial")}
    trust = "human-confirmed" if spec.get("confirmed") else "unconfirmed (auto-synthesized — lower trust)"
    lines = ["<!-- archie-delivery-review -->", "## Archie delivery review", ""]
    lines.append(f"> Grading against `.archie/intent.json` · source: **{_sanitize(spec.get('source','?'))}** "
                 f"· confidence: **{_sanitize(spec.get('confidence','?'))}** · {trust}")
    lines.append("")
    unknown = verdict.get("unknown", 0)
    lines.append(f"**Built the intent?** {verdict.get('intent_completeness','?')} criteria met"
                 + (f" ({unknown} unknown)" if unknown else "") + ".")
    for c in crit:
        mark = "❌" if c.get("id") in unmet_ids else "✅"
        lines.append(f"- {mark} {_sanitize(c.get('id'))} — {_sanitize(c.get('text',''))}")
    lines.append("")
    lines.append(f"**Broke anything?** {verdict.get('breaks',0)} break(s), {verdict.get('conflicts',0)} conflict(s).")
    for f in confirmed:
        if f.get("kind") in ("intent_unmet", "intent_partial"):
            continue
        a = f.get("anchor", {}) or {}
        reviewer = _sanitize(str(f.get("source", "")).split(":")[-1])
        lines.append(f"- `{_sanitize(f.get('kind',''))}` {_sanitize(f.get('problem_statement',''))} "
                     f"({_sanitize(a.get('file',''))}:{_sanitize(a.get('line',''))}) · _{reviewer}_")
    lines.append("")
    lines.append("_Intent wrong? Edit `.archie/intent.json` (or re-run synthesize) and push — this comment updates._")
    return "\n".join(lines)
```
Update the one caller in `run_pr_gate` to pass `spec`: `body = render_verdict(verdict, confirmed, spec)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_verdict.py tests/test_delivery_review.py -v`
Expected: PASS (existing + new).

- [ ] **Step 5: Sync + commit**

```bash
cp archie/standalone/reconcile.py npm-package/assets/reconcile.py
cp archie/standalone/delivery_review.py npm-package/assets/delivery_review.py
python3 scripts/verify_sync.py
git add archie/standalone/reconcile.py archie/standalone/delivery_review.py npm-package/assets/*.py tests/test_verdict.py tests/test_delivery_review.py
git commit -m "feat(pr-gate): self-explanatory verdict (criteria, provenance, trust, correction) + unknown-vs-met

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:** §3A cheap capture → Task 1 (log + state machine) + Task 4 (hook wiring). §3B isolated blind transform → Task 2. §5.3 command surface → Task 3. §5.1 hook wiring → Task 4. §5.4 `non_goals` threading → Task 5. §6 transparency: announce (Task 1 CLI stderr), ratification (Task 3 confirm + default-on-but-optional), provenance/confidence/confirmed surfacing (Task 3 show + Task 6 verdict), self-explanatory verdict + correction loop (Task 6), audit trail (Tasks 1–2 committed logs). §4 artifacts → Tasks 1–2. §8 error handling → per-task (best-effort hooks Task 1/4; None-on-no-events Task 2; malformed skipped Task 1). §9 blindness invariant → Task 2 `test_prompt_is_blind_to_implementation`.

**Placeholder scan:** none — every code step has runnable code + exact commands. Task 4's mirror-copy is described against the repo's existing hook-asset pattern rather than a fixed path because the implementer must match how `pre-validate.sh` is currently mirrored (verify_sync enforces it).

**Type consistency:** `record_user_turn`/`note_edit`/`load_events`/`EVENTS_FILE` (T1) consumed identically in T2/T3/T4; `synthesize(root, run=None)` (T2) matches T3's `cmd_synthesize_intent`; `render_verdict(verdict, confirmed, spec)` (T6) — the added `spec` param is positional-with-default so the existing call updates in the same task; `aggregate_verdict` gains `unknown` used by T6's render; `non_goals` key consistent across T2/T5/T6.

**Decision recorded:** human confirmation is default-on-but-optional — `confirmed: false` still grades, and the verdict renders "unconfirmed (auto-synthesized — lower trust)" so it never masquerades as ratified (Task 6).

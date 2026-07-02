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

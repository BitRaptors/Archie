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

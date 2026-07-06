"""Blind (code-unaware) two-pass task-story synthesizer. Pass 1 summarizes the
user's captured turns (+ optional ticket) into a faithful story; Pass 2 derives
facts, each traceable to a source. Prompt-builders + parsers are pure; the LLM is
called through run_verifier."""
from __future__ import annotations
import re
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

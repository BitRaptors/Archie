"""Task-story storage: one Markdown file per imprint (prose + fenced JSON facts),
versioned by branch + timestamp under .archie/stories/<slug>/. No LLM. Best-effort:
callers treat a None/{} result as 'no story'."""
from __future__ import annotations
import json
import os
import re
import sys
from pathlib import Path

_p = str(Path(__file__).parent)
if _p not in sys.path:
    sys.path.insert(0, _p)

from evidence_schema import extract_json_obj  # noqa: E402

STORIES_SUBDIR = "stories"
_FACTS_MARKER = "<!-- archie:facts -->"


def branch_slug(branch: str) -> str:
    """Flatten a branch name to a filesystem-safe directory segment."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", (branch or "").strip()).strip("-")
    return s or "detached"


def story_dir(root, branch: str) -> Path:
    return Path(root) / ".archie" / STORIES_SUBDIR / branch_slug(branch)


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

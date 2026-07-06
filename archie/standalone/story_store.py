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

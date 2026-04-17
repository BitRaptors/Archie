"""Archie LLM Wiki index builder — backlinks and provenance (Pass 2).

Reads the markdown files written by wiki_builder.py, parses markdown links,
inverts them into a backlinks index, then appends a "Referenced by" section
to each page. Also computes SHA256 hashes for provenance.json.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


# Match [Title](../subdir/slug.md) — relative paths only, .md target, non-empty.
# Does not match external links, anchors, or images.
_LINK_RE = re.compile(r"(?<!\!)\[([^\]]+)\]\((?!https?:)([^)\s#]+\.md)\)")


def extract_links(page: Path) -> list[tuple[str, str]]:
    """Return [(relative_target, link_title), ...] for all relative .md links."""
    text = page.read_text(encoding="utf-8")
    return [(m.group(2), m.group(1)) for m in _LINK_RE.finditer(text)]


def _page_type_from_dir(path_parts: tuple[str, ...]) -> str:
    """Given ('components', 'foo.md') return 'component'. Best-effort singular."""
    if not path_parts:
        return "unknown"
    mapping = {
        "components": "component",
        "decisions": "decision",
        "patterns": "pattern",
        "pitfalls": "pitfall",
        "capabilities": "capability",
    }
    return mapping.get(path_parts[0], "unknown")


def _title_from_page(page: Path) -> str:
    """Return the first-level heading of a page, else filename stem."""
    for line in page.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return page.stem


def build_backlinks(wiki_root: Path) -> dict[str, list[dict]]:
    """Walk the wiki and return {target_rel_path: [{path, title, type}, ...]}.

    Keys and values use wiki-root-relative POSIX paths so the output is stable
    across platforms.
    """
    backlinks: dict[str, list[dict]] = {}
    for page in sorted(wiki_root.rglob("*.md")):
        rel_src = page.relative_to(wiki_root).as_posix()
        # Skip the _meta dir, it's not a real page.
        if rel_src.startswith("_meta/"):
            continue
        src_title = _title_from_page(page)
        src_type = _page_type_from_dir(page.relative_to(wiki_root).parts)
        for relative_target, _link_title in extract_links(page):
            # Resolve relative link against the source page's directory, then
            # re-express relative to wiki_root.
            target_abs = (page.parent / relative_target).resolve()
            try:
                rel_target = target_abs.relative_to(wiki_root.resolve()).as_posix()
            except ValueError:
                continue  # link escapes wiki_root; ignore
            backlinks.setdefault(rel_target, []).append(
                {"path": rel_src, "title": src_title, "type": src_type}
            )
    return backlinks

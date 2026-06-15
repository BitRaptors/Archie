#!/usr/bin/env python3
"""Archie development studio — deterministic issue-tracking engine.

Subcommands (Python never runs git — it only writes files):
  python3 studio.py init  /path/to/repo
  python3 studio.py new   /path/to/repo --title "..." --type feature --label backend
  python3 studio.py move  /path/to/repo ISS-NNN <status>
  python3 studio.py index /path/to/repo
  python3 studio.py next  /path/to/repo

Scaffolds and maintains `.archie/issues/` in the target project. The INDEX.md
tables are always DERIVED from ticket frontmatter — never hand-edited.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import re
import sys

STATUSES = ["planned", "in-progress", "in-review", "done", "blocked"]


def parse_frontmatter(text: str) -> dict | None:
    """Parse a minimal YAML frontmatter block (--- ... ---) at the top of text.

    Supports scalars (`key: value`) and inline lists (`key: [a, b]`). Returns
    None if no frontmatter block is present. Robust to a leading BOM/whitespace.
    """
    s = text.lstrip("﻿")
    if not s.startswith("---"):
        return None
    lines = s.splitlines()
    # first line is the opening ---; find the closing ---
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    fm: dict = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        val = raw.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            fm[key] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
        else:
            fm[key] = val
    return fm


def issues_dir(root: Path) -> Path:
    return root / ".archie" / "issues"


def iter_tickets(issues: Path) -> list[dict]:
    """Parse every ticket .md across status folders. Skip corrupt files (warn)."""
    tickets: list[dict] = []
    if not issues.exists():
        return tickets
    for status in STATUSES:
        folder = issues / status
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.md")):
            try:
                fm = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                fm = None
            if not fm or "id" not in fm:
                print(f"studio: skip unparseable ticket {path}", file=sys.stderr)
                continue
            fm["_path"] = path
            fm["_folder_status"] = status
            tickets.append(fm)
    return tickets


def next_id(tickets: list[dict], prefix: str) -> str:
    """Return the next zero-padded id (e.g. ISS-012) given existing tickets."""
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    nums = [int(m.group(1)) for t in tickets if (m := pat.match(str(t.get("id", ""))))]
    return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"



if __name__ == "__main__":
    print("studio.py: not yet wired", file=sys.stderr)
    sys.exit(1)

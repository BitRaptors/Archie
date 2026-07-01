"""Reachability over the scanner's file-level import graph.

The scanner emits import_graph = {file: [imported_module,...]}. We invert it to
"who depends on X" and walk transitively to approximate blast radius. This is
file-level (not call-level) — a deliberately cheap over-approximation.
"""
from __future__ import annotations

def _module_stem(f: str) -> str:
    return f.rsplit("/", 1)[-1].rsplit(".", 1)[0]

def consumers(import_graph: dict, changed_file: str) -> list[str]:
    stem = _module_stem(changed_file)
    reverse: dict[str, set[str]] = {}
    for src, imports in import_graph.items():
        for imp in imports:
            reverse.setdefault(_module_stem(str(imp)), set()).add(src)
    out, frontier, seen = [], [changed_file], {changed_file}
    while frontier:
        cur = frontier.pop()
        for dep in reverse.get(_module_stem(cur), set()):
            if dep not in seen:
                seen.add(dep); out.append(dep); frontier.append(dep)
    return out

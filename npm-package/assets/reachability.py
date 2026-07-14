"""Reachability over the scanner's file-level import graph.

The scanner emits import_graph = {file: [imported_module,...]}. We invert it to
"who depends on X" and walk transitively to approximate blast radius. This is
file-level (not call-level) — a deliberately cheap over-approximation.

Resolution strategy for the reverse graph:
  1. Exact key match — if the import string matches a graph key exactly, use it.
  2. Path-suffix match — if the import string contains "/" or ends with a known
     extension, find the graph key whose path ends with the import string.
  3. Stem fallback — bare module name matched against the last path component
     without extension.  This is a known imprecision: two files with the same
     basename (e.g. app/util.py and lib/util.py) will both appear as consumers
     when only a stem match is possible.  When the import string already contains
     a "/" the stem fallback is skipped entirely to avoid cross-directory false
     positives.
"""
from __future__ import annotations


def _module_stem(f: str) -> str:
    return f.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _resolve_import(imp: str, graph_keys: set[str]) -> str | None:
    """Map an import string to the best-matching graph key.

    Returns the matched key, or None if no match is found.
    """
    # 1. Exact key match
    if imp in graph_keys:
        return imp
    # 2. Path-suffix match (import looks like a path fragment)
    if "/" in imp:
        imp_py = imp if imp.endswith(".py") else imp + ".py"
        candidates = [k for k in graph_keys
                      if k == imp or k == imp_py
                      or k.endswith("/" + imp) or k.endswith("/" + imp_py)]
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            # Multiple matches — pick the one with fewest extra segments
            return min(candidates, key=lambda k: k.count("/"))
        return None  # path-ish import but unresolvable — skip stem fallback
    # 3. Stem fallback for bare module names only
    stem = _module_stem(imp)
    stem_matches = [k for k in graph_keys if _module_stem(k) == stem]
    if len(stem_matches) == 1:
        return stem_matches[0]
    # Multiple files share the same stem — ambiguous; return None to avoid false positives
    return None


def consumers(import_graph: dict, changed_file: str) -> list[str]:
    graph_keys = set(import_graph.keys())
    reverse: dict[str, set[str]] = {}
    for src, imports in import_graph.items():
        for imp in imports:
            key = _resolve_import(str(imp), graph_keys)
            if key is not None:
                reverse.setdefault(key, set()).add(src)
            else:
                # Unresolvable or ambiguous stem — fall back to stem for
                # backward-compat with graphs that only use bare names.
                stem = _module_stem(str(imp))
                reverse.setdefault("__stem__:" + stem, set()).add(src)

    out, frontier, seen = [], [changed_file], {changed_file}
    while frontier:
        cur = frontier.pop()
        # Direct key lookup
        for dep in reverse.get(cur, set()):
            if dep not in seen:
                seen.add(dep); out.append(dep); frontier.append(dep)
        # Stem-based lookup (for graphs with bare-name imports)
        stem_key = "__stem__:" + _module_stem(cur)
        for dep in reverse.get(stem_key, set()):
            if dep not in seen:
                seen.add(dep); out.append(dep); frontier.append(dep)
    return out

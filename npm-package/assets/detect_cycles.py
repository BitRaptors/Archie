#!/usr/bin/env python3
"""Archie import-graph cycle detector — directory-level circular dependency detection.

Run: python3 detect_cycles.py /path/to/repo
Output: JSON to stdout, summary to stderr.

Reads .archie/scan.json, builds a directory-level dependency graph from the
import_graph, detects cycles via Tarjan's SCC algorithm, and reports each cycle
with the specific file-level evidence that creates it.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath


# ── Source-Root Detection ─────────────────────────────────────────────────

# Common JVM/Android source root patterns
_SOURCE_ROOT_MARKERS = (
    "src/main/java/",
    "src/main/kotlin/",
    "src/test/java/",
    "src/test/kotlin/",
    "src/commonMain/kotlin/",
    "src/androidMain/kotlin/",
)


def _detect_source_roots(file_paths: set[str]) -> list[str]:
    """Detect JVM-style source roots from file paths.

    E.g. if files live at app/src/main/java/com/example/Foo.kt,
    returns ["app/src/main/java/"] so we can strip that prefix
    to get the package path com/example/.
    """
    roots: set[str] = set()
    for fp in file_paths:
        for marker in _SOURCE_ROOT_MARKERS:
            idx = fp.find(marker)
            if idx != -1:
                roots.add(fp[: idx + len(marker)])
    return sorted(roots, key=len, reverse=True)  # longest first


def _build_package_to_dir(
    file_paths: set[str], source_roots: list[str]
) -> dict[str, str]:
    """Build a mapping from dotted package prefix to actual directory path.

    For file app/src/main/java/com/bitraptors/foo/Bar.kt:
      package "com.bitraptors.foo" → dir "app/src/main/java/com/bitraptors/foo"
    """
    pkg_to_dir: dict[str, str] = {}
    for fp in file_paths:
        parent = str(PurePosixPath(fp).parent)
        if parent == ".":
            continue
        for root in source_roots:
            if fp.startswith(root):
                # Strip source root to get package path
                pkg_path = parent[len(root):]
                if pkg_path:
                    dotted = pkg_path.replace("/", ".")
                    pkg_to_dir[dotted] = parent
                break
    return pkg_to_dir


# ── Import Resolution ─────────────────────────────────────────────────────

def _resolve_import_to_dir(
    imp: str,
    importing_file: str,
    file_paths: set[str],
    dir_set: set[str],
    pkg_to_dir: dict[str, str],
) -> str | None:
    """Try to resolve an import string to a project directory.

    Returns the directory (relative to repo root) or None if unresolvable.
    """
    # JS/TS relative imports: starts with . or ..
    if imp.startswith("."):
        return _resolve_js_relative(imp, importing_file, file_paths, dir_set)

    # Dot-separated (Python, Kotlin, Java): com.example.module
    if "." in imp:
        return _resolve_dotted(imp, file_paths, dir_set, pkg_to_dir)

    return None


def _resolve_js_relative(
    imp: str, importing_file: str, file_paths: set[str], dir_set: set[str]
) -> str | None:
    """Resolve JS/TS relative import (e.g. ../utils/foo) to a directory."""
    importing_dir = str(PurePosixPath(importing_file).parent)
    resolved = str(PurePosixPath(importing_dir) / imp)

    # Normalise .. and . segments
    parts: list[str] = []
    for seg in resolved.split("/"):
        if seg == "..":
            if parts:
                parts.pop()
        elif seg and seg != ".":
            parts.append(seg)
    resolved = "/".join(parts)

    if not resolved:
        return None

    # Check if it matches a directory directly
    if resolved in dir_set:
        return resolved

    # Try common JS extensions
    js_exts = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
    for ext in js_exts:
        candidate = resolved + ext
        if candidate in file_paths:
            return str(PurePosixPath(candidate).parent)

    # Try index files in the resolved path (directory import)
    for idx in ("index.ts", "index.tsx", "index.js", "index.jsx"):
        candidate = resolved + "/" + idx
        if candidate in file_paths:
            return resolved

    return None


def _resolve_dotted(
    imp: str,
    file_paths: set[str],
    dir_set: set[str],
    pkg_to_dir: dict[str, str],
) -> str | None:
    """Resolve dotted import (Python/Kotlin/Java) to a directory.

    Uses source-root-aware package mapping for JVM languages,
    falls back to direct path mapping for Python.
    """
    segments = imp.split(".")

    # ── Strategy 1: Package-to-dir mapping (JVM) ──
    # Try progressively shorter prefixes against the package map
    for drop in range(0, min(len(segments), 4)):
        n = len(segments) - drop
        if n < 1:
            break
        pkg = ".".join(segments[:n])
        if pkg in pkg_to_dir:
            return pkg_to_dir[pkg]

    # ── Strategy 2: Direct path mapping (Python, flat projects) ──
    # Try full path as file: com/example/module.py, .kt, .java
    for ext in (".py", ".kt", ".java"):
        candidate = "/".join(segments) + ext
        if candidate in file_paths:
            return str(PurePosixPath(candidate).parent)

    # Try as package directory: com/example/module/__init__.py
    pkg_dir = "/".join(segments)
    init_candidate = pkg_dir + "/__init__.py"
    if init_candidate in file_paths:
        return pkg_dir

    if pkg_dir in dir_set:
        return pkg_dir

    # Try dropping the last segment (class name):
    # com.example.package.ClassName → com/example/package/
    for drop in range(1, min(len(segments), 4)):
        prefix_segments = segments[: len(segments) - drop]
        if not prefix_segments:
            break

        prefix_dir = "/".join(prefix_segments)
        if prefix_dir in dir_set:
            return prefix_dir

    return None


# ── Graph Building ────────────────────────────────────────────────────────

def build_directory_graph(
    import_graph: dict[str, list[str]],
    file_tree: list[dict],
) -> tuple[dict[str, set[str]], dict[tuple[str, str], list[dict]]]:
    """Build directory-level dependency graph from file-level import graph.

    Returns:
        (dir_graph, evidence)
        dir_graph: {dir: set of dirs it depends on}
        evidence: {(from_dir, to_dir): [list of evidence dicts]}
    """
    # Build lookup structures
    file_paths: set[str] = set()
    dir_set: set[str] = set()
    for f in file_tree:
        p = f["path"]
        file_paths.add(p)
        parent = str(PurePosixPath(p).parent)
        if parent != ".":
            dir_set.add(parent)
            # Also add ancestor dirs
            parts = parent.split("/")
            for i in range(1, len(parts)):
                dir_set.add("/".join(parts[:i]))

    # Detect JVM source roots and build package mapping
    source_roots = _detect_source_roots(file_paths)
    pkg_to_dir = _build_package_to_dir(file_paths, source_roots)

    dir_graph: dict[str, set[str]] = defaultdict(set)
    evidence: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for file_path, imports in import_graph.items():
        from_dir = str(PurePosixPath(file_path).parent)
        if from_dir == ".":
            from_dir = "."

        for imp in imports:
            to_dir = _resolve_import_to_dir(
                imp, file_path, file_paths, dir_set, pkg_to_dir
            )
            if to_dir is None:
                continue
            # Skip self-edges (same directory)
            if to_dir == from_dir:
                continue
            dir_graph[from_dir].add(to_dir)
            evidence[(from_dir, to_dir)].append({
                "from_file": file_path,
                "imports": imp,
                "to_dir": to_dir,
            })

    # Ensure all target dirs are also keys (needed for Tarjan)
    all_dirs = set(dir_graph.keys())
    for deps in list(dir_graph.values()):
        all_dirs.update(deps)
    for d in all_dirs:
        if d not in dir_graph:
            dir_graph[d] = set()

    return dict(dir_graph), dict(evidence)


# ── Cycle Detection (Tarjan's SCC) ───────────────────────────────────────

def tarjan_scc(graph: dict[str, set[str]]) -> list[list[str]]:
    """Find all strongly connected components with size > 1 (cycles)."""
    index_counter = [0]
    stack: list[str] = []
    on_stack: set[str] = set()
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    result: list[list[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)

        for w in graph.get(v, set()):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            component: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                component.append(w)
                if w == v:
                    break
            if len(component) > 1:
                result.append(sorted(component))

    # Raise recursion limit for large graphs
    sys.setrecursionlimit(max(10000, len(graph) * 3))

    for v in sorted(graph.keys()):
        if v not in index:
            strongconnect(v)

    return result


# ── Full Dependency Graph ─────────────────────────────────────────────────

def _find_component(dir_path: str, comp_map: dict[str, str]) -> str:
    """Find the best-matching component for a directory by path prefix."""
    best = ""
    best_len = 0
    for comp_path, comp_name in comp_map.items():
        if dir_path.startswith(comp_path) and len(comp_path) > best_len:
            best = comp_name
            best_len = len(comp_path)
    return best


def _count_files_per_dir(file_tree: list[dict]) -> dict[str, int]:
    """Count source files per directory."""
    counts: dict[str, int] = defaultdict(int)
    for f in file_tree:
        parent = str(PurePosixPath(f["path"]).parent)
        if parent == ".":
            parent = "."
        counts[parent] += 1
    return dict(counts)


def build_full_graph(root: Path) -> dict:
    """Build the full dependency graph with nodes, edges, cycles, and stats.

    Reads scan.json for the import graph and optionally blueprint.json for
    component membership. Persists the result to .archie/dependency_graph.json.
    """
    scan_path = root / ".archie" / "scan.json"
    if not scan_path.exists():
        return {"nodes": [], "edges": [], "cycles": [], "stats": {
            "nodeCount": 0, "edgeCount": 0, "cycleCount": 0}}

    try:
        scan = json.loads(scan_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"nodes": [], "edges": [], "cycles": [], "stats": {
            "nodeCount": 0, "edgeCount": 0, "cycleCount": 0}}

    import_graph = scan.get("import_graph", {})
    file_tree = scan.get("file_tree", [])

    if not import_graph:
        return {"nodes": [], "edges": [], "cycles": [], "stats": {
            "nodeCount": 0, "edgeCount": 0, "cycleCount": 0}}

    dir_graph, evidence = build_directory_graph(import_graph, file_tree)
    sccs = tarjan_scc(dir_graph)

    # Build component map from blueprint (if available)
    comp_map: dict[str, str] = {}
    bp_path = root / ".archie" / "blueprint.json"
    if bp_path.exists():
        try:
            bp = json.loads(bp_path.read_text())
            for comp in bp.get("components", {}).get("components", []):
                cp = comp.get("path", "")
                cn = comp.get("name", "")
                if cp and cn:
                    comp_map[cp] = cn
        except (json.JSONDecodeError, OSError):
            pass

    # Identify cycle directories
    cycle_dirs: set[str] = set()
    for scc in sccs:
        cycle_dirs.update(scc)

    # Count files per directory
    file_counts = _count_files_per_dir(file_tree)

    # Compute in-degree and out-degree
    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    for from_dir, to_dirs in dir_graph.items():
        out_degree[from_dir] = len(to_dirs)
        for to_dir in to_dirs:
            in_degree[to_dir] += 1

    # Build nodes
    all_dirs = set(dir_graph.keys())
    for deps in dir_graph.values():
        all_dirs.update(deps)

    nodes = []
    for d in sorted(all_dirs):
        label = d.split("/")[-1] if "/" in d else d
        nodes.append({
            "id": d,
            "label": label,
            "component": _find_component(d, comp_map),
            "inDegree": in_degree.get(d, 0),
            "outDegree": out_degree.get(d, 0),
            "inCycle": d in cycle_dirs,
            "fileCount": file_counts.get(d, 0),
        })

    # Build edges
    edges = []
    for from_dir, to_dirs in dir_graph.items():
        for to_dir in to_dirs:
            from_comp = _find_component(from_dir, comp_map)
            to_comp = _find_component(to_dir, comp_map)
            ev_list = evidence.get((from_dir, to_dir), [])
            edges.append({
                "from": from_dir,
                "to": to_dir,
                "weight": len(ev_list),
                "crossComponent": bool(
                    from_comp and to_comp and from_comp != to_comp
                ),
                "inCycle": from_dir in cycle_dirs and to_dir in cycle_dirs,
            })

    # Build cycle output
    cycles_out = []
    for scc in sccs:
        scc_set = set(scc)
        seen: set[tuple[str, str]] = set()
        cycle_evidence: list[dict] = []
        for fd in scc:
            for td in dir_graph.get(fd, set()):
                if td in scc_set:
                    for ev in evidence.get((fd, td), []):
                        key = (ev["from_file"], ev["to_dir"])
                        if key not in seen:
                            seen.add(key)
                            cycle_evidence.append(ev)
        cycles_out.append({"directories": scc, "evidence": cycle_evidence})

    result = {
        "nodes": nodes,
        "edges": edges,
        "cycles": cycles_out,
        "stats": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "cycleCount": len(sccs),
        },
    }

    # Persist
    out_path = root / ".archie" / "dependency_graph.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2) + "\n")

    return result


# ── Output ────────────────────────────────────────────────────────────────

def detect_cycles(root: Path) -> dict:
    """Main entry point: load scan.json and detect directory-level cycles."""
    scan_path = root / ".archie" / "scan.json"
    if not scan_path.exists():
        return {"cycles": [], "cycle_count": 0, "directory_edges": 0}

    try:
        scan = json.loads(scan_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"cycles": [], "cycle_count": 0, "directory_edges": 0}

    import_graph = scan.get("import_graph", {})
    file_tree = scan.get("file_tree", [])

    if not import_graph:
        return {"cycles": [], "cycle_count": 0, "directory_edges": 0}

    dir_graph, evidence = build_directory_graph(import_graph, file_tree)

    # Count total edges
    total_edges = sum(len(deps) for deps in dir_graph.values())

    # Find cycles
    sccs = tarjan_scc(dir_graph)

    cycles = []
    for scc in sccs:
        # Collect evidence for edges within this SCC
        # Deduplicate: keep one evidence entry per (from_file, to_dir) pair
        scc_set = set(scc)
        seen: set[tuple[str, str]] = set()
        cycle_evidence: list[dict] = []
        for from_dir in scc:
            for to_dir in dir_graph.get(from_dir, set()):
                if to_dir in scc_set:
                    for ev in evidence.get((from_dir, to_dir), []):
                        key = (ev["from_file"], ev["to_dir"])
                        if key not in seen:
                            seen.add(key)
                            cycle_evidence.append(ev)

        cycles.append({
            "directories": scc,
            "evidence": cycle_evidence,
        })

    return {
        "cycles": cycles,
        "cycle_count": len(cycles),
        "directory_edges": total_edges,
    }


# ── CLI ───────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 detect_cycles.py /path/to/repo [--full]", file=sys.stderr)
        sys.exit(1)

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    full_mode = "--full" in flags

    root = Path(args[0]).resolve() if args else Path(".").resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    if full_mode:
        result = build_full_graph(root)
        stats = result.get("stats", {})
        print(
            f"Dependency graph: {stats.get('nodeCount', 0)} directories, "
            f"{stats.get('edgeCount', 0)} edges, "
            f"{stats.get('cycleCount', 0)} cycle(s) "
            f"-> .archie/dependency_graph.json",
            file=sys.stderr,
        )
    else:
        result = detect_cycles(root)
        print(
            f"Import graph: {result['directory_edges']} directory edges, "
            f"{result['cycle_count']} cycle(s) detected",
            file=sys.stderr,
        )
        json.dump(result, sys.stdout, indent=2)
        print()  # trailing newline


if __name__ == "__main__":
    main()

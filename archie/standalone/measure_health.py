#!/usr/bin/env python3
"""Archie health metrics — erosion + verbosity scoring.

Run: python3 measure_health.py /path/to/repo
Reads .archie/skeletons.json and .archie/scan.json, writes JSON to stdout.

Metrics based on the SlopCodeBench research paper:
  - Erosion: fraction of complexity mass in high-CC functions
  - Verbosity: duplicate-line ratio via line-hash detection

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────

CC_THRESHOLD = 10          # functions above this are "high complexity"
CC_REPORT_THRESHOLD = 5    # include functions above this in output
DUP_MIN_LINES = 6          # minimum consecutive matching lines for a duplicate
MAX_DUP_REPORT = 50        # top N duplicates in output

# Extensions we can meaningfully analyze for CC
SOURCE_EXTENSIONS = {
    ".py", ".kt", ".kts", ".java", ".js", ".jsx", ".ts", ".tsx",
    ".swift", ".go", ".rs", ".rb", ".c", ".cpp", ".cc", ".cxx", ".h",
    ".hpp", ".cs", ".php", ".scala", ".m", ".mm",
}

# Regex decision-point patterns for non-Python languages
_DECISION_RE = re.compile(
    r"""(?x)
    \b(?:if|elif|else\s+if|elseif|else|for|foreach|while|do\b.*\bwhile|
        switch|case|catch|except|when|guard)\b
    | \?\s*[^?]     # ternary  ?:
    | &&             # logical AND
    | \|\|           # logical OR
    """
)

# Comment-line patterns for stripping before hashing
_COMMENT_LINE = re.compile(r"^\s*(?://|#|/?\*|\*/?|<!--|-->)")
_BLANK_LINE = re.compile(r"^\s*$")

# ── Python AST-based CC ──────────────────────────────────────────────────

def _cc_python_function(source: str, func_start: int, func_end: int) -> int:
    """Compute cyclomatic complexity of a Python function via AST."""
    # Extract the function lines and parse them
    lines = source.splitlines(True)
    func_lines = lines[func_start - 1 : func_end]
    if not func_lines:
        return 1

    # Dedent to column 0 so ast.parse works
    min_indent = 9999
    for ln in func_lines:
        stripped = ln.rstrip("\n\r")
        if stripped.strip():
            indent = len(stripped) - len(stripped.lstrip())
            min_indent = min(min_indent, indent)
    if min_indent == 9999:
        min_indent = 0

    dedented = "".join(ln[min_indent:] if len(ln) > min_indent else ln for ln in func_lines)

    try:
        tree = ast.parse(dedented, mode="exec")
    except SyntaxError:
        return 1

    cc = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler,
                             ast.Assert)):
            cc += 1
        elif isinstance(node, ast.BoolOp):
            # each `and`/`or` adds len(values)-1 decision points
            cc += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            cc += 1  # the implicit loop
            cc += len(node.ifs)  # each if-filter
    return cc


# ── Generic regex-based CC ───────────────────────────────────────────────

def _cc_regex(lines: list[str]) -> int:
    """Approximate cyclomatic complexity via regex for non-Python files."""
    cc = 1
    for line in lines:
        # Strip string literals to avoid false positives
        cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
        cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", cleaned)
        cc += len(_DECISION_RE.findall(cleaned))
    return cc


# ── Read source files ────────────────────────────────────────────────────

def _read_file(path: str) -> str | None:
    """Read a file, returning None on failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


# ── Erosion score ────────────────────────────────────────────────────────

def _compute_functions(repo: Path, skeletons: dict) -> list[dict]:
    """Analyze every function in skeletons for CC and SLOC."""
    results: list[dict] = []

    for rel_path, info in skeletons.items():
        symbols = info.get("symbols", [])
        line_count = info.get("line_count", 0)
        if not symbols or line_count == 0:
            continue

        ext = os.path.splitext(rel_path)[1].lower()
        if ext not in SOURCE_EXTENSIONS:
            continue

        # Filter to function-like symbols
        func_symbols = [s for s in symbols if s.get("kind") in ("func", "function", "method")]
        if not func_symbols:
            continue

        abs_path = repo / rel_path
        source = _read_file(str(abs_path))
        if source is None:
            continue

        source_lines = source.splitlines()
        is_python = ext == ".py"

        # Sort symbols by line number to determine function boundaries
        all_symbols_sorted = sorted(symbols, key=lambda s: s.get("line", 0))
        sym_lines = [s.get("line", 0) for s in all_symbols_sorted]

        for sym in func_symbols:
            start_line = sym.get("line", 0)
            if start_line <= 0:
                continue

            # Find end: next symbol's line or end of file
            idx_in_all = None
            for i, sl in enumerate(sym_lines):
                if sl == start_line:
                    idx_in_all = i
                    break
            if idx_in_all is not None and idx_in_all + 1 < len(sym_lines):
                end_line = sym_lines[idx_in_all + 1] - 1
            else:
                end_line = line_count

            func_lines = source_lines[start_line - 1 : end_line]
            sloc = sum(1 for ln in func_lines if ln.strip())

            if is_python:
                cc = _cc_python_function(source, start_line, end_line)
            else:
                cc = _cc_regex(func_lines)

            results.append({
                "path": rel_path,
                "name": sym.get("name", "?"),
                "cc": cc,
                "sloc": sloc,
                "line": start_line,
            })

    return results


def _erosion_score(functions: list[dict]) -> tuple[float, int]:
    """Compute erosion = heavy_mass / total_mass. Returns (score, high_cc_count)."""
    import math

    total_mass = 0.0
    heavy_mass = 0.0
    high_cc = 0

    for fn in functions:
        cc = fn["cc"]
        sloc = fn["sloc"]
        mass = cc * math.sqrt(max(sloc, 1))
        total_mass += mass
        if cc > CC_THRESHOLD:
            heavy_mass += mass
            high_cc += 1

    if total_mass == 0:
        return 0.0, 0
    return round(heavy_mass / total_mass, 4), high_cc


# ── Verbosity score ──────────────────────────────────────────────────────

def _hash_line(line: str) -> str | None:
    """Hash a normalized line, returning None for blank/comment lines."""
    stripped = line.strip()
    if not stripped:
        return None
    if _COMMENT_LINE.match(line):
        return None
    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", stripped)
    # Skip very short lines (braces, end, etc.) — they cause false positives
    if len(normalized) <= 3:
        return None
    return hashlib.md5(normalized.encode()).hexdigest()


def _find_duplicates(repo: Path, skeletons: dict) -> tuple[list[dict], int, int]:
    """Find duplicate line sequences. Returns (duplicates, total_dup_lines, total_loc)."""
    # Build per-file hash sequences
    file_hashes: dict[str, list[tuple[str | None, int]]] = {}  # path -> [(hash, line_no)]
    total_loc = 0

    for rel_path, info in skeletons.items():
        line_count = info.get("line_count", 0)
        if line_count == 0:
            continue
        ext = os.path.splitext(rel_path)[1].lower()
        if ext not in SOURCE_EXTENSIONS:
            continue

        abs_path = repo / rel_path
        source = _read_file(str(abs_path))
        if source is None:
            continue

        lines = source.splitlines()
        total_loc += len(lines)
        hashes = []
        for i, line in enumerate(lines):
            h = _hash_line(line)
            hashes.append((h, i + 1))
        file_hashes[rel_path] = hashes

    # Build index: hash -> list of (file, line_no)
    # Use rolling window of DUP_MIN_LINES consecutive non-None hashes
    # For efficiency, use tuple of consecutive hashes as key
    chunk_index: dict[tuple[str, ...], list[tuple[str, int]]] = {}

    for rel_path, hashes in file_hashes.items():
        # Extract only non-None hash positions
        valid = [(h, ln) for h, ln in hashes if h is not None]
        for i in range(len(valid) - DUP_MIN_LINES + 1):
            chunk = tuple(h for h, _ in valid[i : i + DUP_MIN_LINES])
            start_ln = valid[i][1]
            if chunk not in chunk_index:
                chunk_index[chunk] = []
            chunk_index[chunk].append((rel_path, start_ln))

    # Find duplicate chunks (appearing in different files)
    seen_pairs: set[tuple[str, int, str, int]] = set()
    duplicates: list[dict] = []
    dup_lines_set: set[tuple[str, int]] = set()  # (file, line) pairs counted as duplicate

    for chunk, locations in chunk_index.items():
        if len(locations) < 2:
            continue

        # Only cross-file duplicates
        files_in_chunk = set(loc[0] for loc in locations)
        if len(files_in_chunk) < 2:
            continue

        # Report pairs
        for i in range(len(locations)):
            for j in range(i + 1, len(locations)):
                fa, la = locations[i]
                fb, lb = locations[j]
                if fa == fb:
                    continue

                # Canonical ordering
                if (fa, la) > (fb, lb):
                    fa, la, fb, lb = fb, lb, fa, la

                pair_key = (fa, la, fb, lb)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Try to extend the match beyond DUP_MIN_LINES
                ha = file_hashes[fa]
                hb = file_hashes[fb]
                match_len = DUP_MIN_LINES

                # Extend forward
                idx_a = la - 1 + DUP_MIN_LINES
                idx_b = lb - 1 + DUP_MIN_LINES
                while idx_a < len(ha) and idx_b < len(hb):
                    h_a, _ = ha[idx_a]
                    h_b, _ = hb[idx_b]
                    if h_a is None and h_b is None:
                        # Both blank/comment — keep going
                        match_len += 1
                    elif h_a == h_b and h_a is not None:
                        match_len += 1
                    else:
                        break
                    idx_a += 1
                    idx_b += 1

                duplicates.append({
                    "file_a": fa,
                    "line_a": la,
                    "file_b": fb,
                    "line_b": lb,
                    "lines": match_len,
                })

                # Track duplicate lines for counting
                for offset in range(match_len):
                    dup_lines_set.add((fb, lb + offset))

    # Sort by line count descending, take top N
    duplicates.sort(key=lambda d: d["lines"], reverse=True)

    # Deduplicate overlapping ranges — keep longest
    kept: list[dict] = []
    covered: set[tuple[str, int, str, int]] = set()
    for dup in duplicates:
        fa, la, fb, lb, length = dup["file_a"], dup["line_a"], dup["file_b"], dup["line_b"], dup["lines"]
        # Check if this is mostly covered by an already-kept duplicate
        overlap = 0
        for offset in range(length):
            if (fa, la + offset, fb, lb + offset) in covered:
                overlap += 1
        if overlap > length * 0.5:
            continue
        kept.append(dup)
        for offset in range(length):
            covered.add((fa, la + offset, fb, lb + offset))

    return kept[:MAX_DUP_REPORT], len(dup_lines_set), total_loc


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 measure_health.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    repo = Path(sys.argv[1]).resolve()
    archie_dir = repo / ".archie"

    skel_path = archie_dir / "skeletons.json"
    scan_path = archie_dir / "scan.json"

    if not skel_path.exists():
        print(f"Error: {skel_path} not found. Run scanner first.", file=sys.stderr)
        sys.exit(1)

    with open(skel_path, "r", encoding="utf-8") as f:
        skeletons = json.load(f)

    # Compute function metrics
    functions = _compute_functions(repo, skeletons)
    erosion, high_cc_count = _erosion_score(functions)

    # Compute verbosity
    duplicates, dup_line_count, total_loc = _find_duplicates(repo, skeletons)
    verbosity = round(dup_line_count / total_loc, 4) if total_loc > 0 else 0.0

    # Filter and sort functions for output
    reported_functions = sorted(
        [f for f in functions if f["cc"] > CC_REPORT_THRESHOLD],
        key=lambda f: f["cc"],
        reverse=True,
    )

    result = {
        "erosion": erosion,
        "verbosity": verbosity,
        "total_functions": len(functions),
        "high_cc_functions": high_cc_count,
        "total_loc": total_loc,
        "duplicate_lines": dup_line_count,
        "functions": reported_functions,
        "duplicates": duplicates,
    }

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")

    # Summary to stderr
    print(
        f"Health: erosion={erosion} verbosity={verbosity}\n"
        f"  {len(functions)} functions analyzed, {high_cc_count} with CC>{CC_THRESHOLD}\n"
        f"  {total_loc} LOC, {dup_line_count} duplicate lines",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()

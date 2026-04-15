#!/usr/bin/env python3
"""Archie health metrics — erosion, verbosity, complexity distribution, waste.

Run: python3 measure_health.py /path/to/repo
Reads .archie/skeletons.json and .archie/scan.json, writes JSON to stdout.

Metrics based on the SlopCodeBench research paper:
  - Erosion: fraction of complexity mass in high-branching-complexity functions
  - Verbosity: duplicate-line ratio via line-hash detection
  - Gini coefficient: inequality of complexity distribution across functions
  - Top-20% share: fraction of total mass held by the heaviest 20% of functions
  - Abstraction waste: single-use functions, trivial wrappers, single-method classes

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import (  # noqa: E402
    SOURCE_EXTENSIONS,
    _cc_python_function,
    _cc_regex,
    _read_file,
)

# ── Configuration ─────────────────────────────────────────────────────────

CC_THRESHOLD = 10          # functions above this are "high complexity"
CC_REPORT_THRESHOLD = 5    # include functions above this in output
DUP_MIN_LINES = 6          # minimum consecutive matching lines for a duplicate
MAX_DUP_REPORT = 50        # top N duplicates in output

# Comment-line patterns for stripping before hashing
_COMMENT_LINE = re.compile(r"^\s*(?://|#|/?\*|\*/?|<!--|-->)")
_BLANK_LINE = re.compile(r"^\s*$")


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
    """Compute erosion = heavy_mass / total_mass. Returns (score, high_cc_count).

    Also annotates every function dict in-place with `mass` = cc * sqrt(max(sloc, 1))
    so downstream code (output rendering, cc_distribution, top-N selection by mass)
    can reuse the computation.
    """
    import math

    total_mass = 0.0
    heavy_mass = 0.0
    high_cc = 0

    for fn in functions:
        cc = fn["cc"]
        sloc = fn["sloc"]
        mass = cc * math.sqrt(max(sloc, 1))
        fn["mass"] = round(mass, 2)
        total_mass += mass
        if cc > CC_THRESHOLD:
            heavy_mass += mass
            high_cc += 1

    if total_mass == 0:
        return 0.0, 0
    return round(heavy_mass / total_mass, 4), high_cc


def _cc_distribution(functions: list[dict]) -> dict:
    """Count functions across fixed CC buckets. Covers ALL functions, not just
    reported ones — the scalar metrics are already distribution-based, and this
    gives stakeholders the histogram behind them."""
    buckets = {"1-2": 0, "3-5": 0, "6-10": 0, "11-20": 0, "21-50": 0, "51-100": 0, "101+": 0}
    for fn in functions:
        cc = fn.get("cc", 0)
        if cc <= 2:     buckets["1-2"] += 1
        elif cc <= 5:   buckets["3-5"] += 1
        elif cc <= 10:  buckets["6-10"] += 1
        elif cc <= 20:  buckets["11-20"] += 1
        elif cc <= 50:  buckets["21-50"] += 1
        elif cc <= 100: buckets["51-100"] += 1
        else:           buckets["101+"] += 1
    return buckets


def _mass_totals(functions: list[dict]) -> dict:
    """Surface the totals that erosion/gini/top20 are computed from.
    Relies on `mass` having been written onto each fn by _erosion_score."""
    total = 0.0
    heavy = 0.0
    for fn in functions:
        m = fn.get("mass", 0.0)
        total += m
        if fn.get("cc", 0) > CC_THRESHOLD:
            heavy += m
    return {
        "total": round(total, 2),
        "heavy": round(heavy, 2),
        "heavy_ratio": round(heavy / total, 4) if total > 0 else 0.0,
    }


# ── Complexity distribution ──────────────────────────────────────────────

def _gini_coefficient(functions: list[dict]) -> float:
    """Gini coefficient of complexity mass distribution.

    0 = perfectly equal (every function equally complex).
    1 = maximally unequal (one function holds all complexity).
    """
    import math

    masses = sorted(
        cc * math.sqrt(max(sloc, 1))
        for fn in functions
        for cc, sloc in [(fn["cc"], fn["sloc"])]
        if cc * math.sqrt(max(sloc, 1)) > 1e-9
    )
    n = len(masses)
    if n == 0:
        return 0.0
    total = sum(masses)
    if total == 0:
        return 0.0
    weighted = sum((i + 1) * v for i, v in enumerate(masses))
    return round((2 * weighted - (n + 1) * total) / (n * total), 4)


def _top20_share(functions: list[dict]) -> float:
    """Fraction of total complexity mass held by the top 20% of functions.

    0.20 = perfectly even. 0.90+ = a few functions dominate.
    """
    import math

    masses = sorted(
        (cc * math.sqrt(max(sloc, 1))
         for fn in functions
         for cc, sloc in [(fn["cc"], fn["sloc"])]),
        reverse=True,
    )
    if not masses:
        return 0.0
    total = sum(masses)
    if total == 0:
        return 0.0
    top_count = max(1, math.ceil(len(masses) * 0.2))
    return round(sum(masses[:top_count]) / total, 4)


# ── Abstraction waste ───────────────────────────────────────────────────

def _detect_waste(skeletons: dict) -> dict:
    """Detect abstraction waste from skeleton data.

    Finds:
      - Single-method classes: classes with only 1 method
      - Tiny functions: functions with <= 2 SLOC (likely trivial wrappers)
    """
    single_method_classes: list[dict] = []
    tiny_functions: list[dict] = []

    for rel_path, info in skeletons.items():
        symbols = info.get("symbols", [])
        if not symbols:
            continue

        # Find classes and their methods
        classes = [s for s in symbols if s.get("kind") in ("class",)]
        methods = [s for s in symbols if s.get("kind") in ("method",)]
        funcs = [s for s in symbols if s.get("kind") in ("func", "function")]

        # Single-method classes: class has exactly 1 method
        # Heuristic: methods between this class line and next class/end-of-file
        all_sorted = sorted(symbols, key=lambda s: s.get("line", 0))
        class_lines = [(c.get("name", "?"), c.get("line", 0)) for c in classes]

        for ci, (cname, cline) in enumerate(class_lines):
            # Find boundary: next class line or end of file
            if ci + 1 < len(class_lines):
                boundary = class_lines[ci + 1][1]
            else:
                boundary = info.get("line_count", 999999)

            # Count methods in this class's range
            class_methods = [
                m for m in methods
                if cline < m.get("line", 0) < boundary
            ]
            if len(class_methods) == 1:
                single_method_classes.append({
                    "path": rel_path,
                    "class": cname,
                    "method": class_methods[0].get("name", "?"),
                    "line": cline,
                })

        # Tiny functions (likely trivial wrappers or one-liners)
        for sym in funcs + methods:
            line = sym.get("line", 0)
            # Estimate SLOC: distance to next symbol or 0
            idx = next(
                (i for i, s in enumerate(all_sorted) if s.get("line", 0) == line),
                None,
            )
            if idx is not None and idx + 1 < len(all_sorted):
                end = all_sorted[idx + 1].get("line", line) - 1
            else:
                end = info.get("line_count", line)
            sloc = max(end - line, 0)
            if 0 < sloc <= 2:
                tiny_functions.append({
                    "path": rel_path,
                    "name": sym.get("name", "?"),
                    "line": line,
                    "sloc": sloc,
                })

    return {
        "single_method_classes": single_method_classes[:30],
        "single_method_class_count": len(single_method_classes),
        "tiny_functions": tiny_functions[:30],
        "tiny_function_count": len(tiny_functions),
    }


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

    # --append-history: read health.json, append entry to health_history.json, exit
    if "--append-history" in sys.argv:
        health_path = archie_dir / "health.json"
        if not health_path.exists():
            print(f"Error: {health_path} not found. Run measure_health first.", file=sys.stderr)
            sys.exit(1)

        with open(health_path, "r", encoding="utf-8") as f:
            health = json.load(f)

        # Determine scan type
        scan_type = "deep"
        if "--scan-type" in sys.argv:
            idx = sys.argv.index("--scan-type")
            if idx + 1 < len(sys.argv):
                scan_type = sys.argv[idx + 1]

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "erosion": health.get("erosion"),
            "gini": health.get("gini"),
            "top20_share": health.get("top20_share"),
            "verbosity": health.get("verbosity"),
            "total_loc": health.get("total_loc"),
            "scan_type": scan_type,
        }

        history_path = archie_dir / "health_history.json"
        if history_path.exists():
            with open(history_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # Handle both list and dict formats
            if isinstance(raw, list):
                history = raw
            elif isinstance(raw, dict) and "history" in raw:
                history = raw["history"]
            else:
                history = []
        else:
            history = []

        history.append(entry)

        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
            f.write("\n")

        # JSON entry to stdout
        json.dump(entry, sys.stdout, indent=2)
        sys.stdout.write("\n")

        # Summary to stderr
        print(
            f"Health history: appended entry #{len(history)} "
            f"(erosion={entry['erosion']} gini={entry['gini']} scan_type={scan_type})",
            file=sys.stderr,
        )
        sys.exit(0)

    skel_path = archie_dir / "skeletons.json"
    scan_path = archie_dir / "scan.json"

    if not skel_path.exists():
        print(f"Error: {skel_path} not found. Run scanner first.", file=sys.stderr)
        sys.exit(1)

    with open(skel_path, "r", encoding="utf-8") as f:
        skeletons = json.load(f)

    # Compute function metrics
    functions = _compute_functions(repo, skeletons)
    erosion, high_cc_count = _erosion_score(functions)   # annotates fn["mass"]
    gini = _gini_coefficient(functions)
    top20 = _top20_share(functions)
    cc_distribution = _cc_distribution(functions)
    mass_totals = _mass_totals(functions)

    # Compute verbosity
    duplicates, dup_line_count, total_loc = _find_duplicates(repo, skeletons)
    verbosity = round(dup_line_count / total_loc, 4) if total_loc > 0 else 0.0

    # Compute abstraction waste
    waste = _detect_waste(skeletons)

    # Filter and sort functions for output
    reported_functions = sorted(
        [f for f in functions if f["cc"] > CC_REPORT_THRESHOLD],
        key=lambda f: f["cc"],
        reverse=True,
    )

    result = {
        "erosion": erosion,
        "gini": gini,
        "top20_share": top20,
        "verbosity": verbosity,
        "total_functions": len(functions),
        "high_cc_functions": high_cc_count,
        "total_loc": total_loc,
        "duplicate_lines": dup_line_count,
        "cc_distribution": cc_distribution,
        "mass": mass_totals,
        "waste": waste,
        "functions": reported_functions,
        "duplicates": duplicates,
    }

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")

    # Summary to stderr
    print(
        f"Health: erosion={erosion} gini={gini} top20={top20} verbosity={verbosity}\n"
        f"  {len(functions)} functions analyzed, {high_cc_count} with branching complexity>{CC_THRESHOLD}\n"
        f"  {total_loc} LOC, {dup_line_count} duplicate lines\n"
        f"  Waste: {waste['single_method_class_count']} single-method classes, {waste['tiny_function_count']} tiny functions",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()

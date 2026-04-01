#!/usr/bin/env python3
"""Archie drift detector — finds architectural divergences and outliers.

Compares per-folder enrichments and file structure against the blueprint's
dominant patterns to surface: pattern inconsistencies, naming violations,
dependency direction breaches, and structural outliers.

Run:
  python3 drift.py /path/to/repo

Output: JSON drift report to stdout, human summary to stderr.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import _load_json  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Pattern consistency — which folders diverge from dominant patterns
# ---------------------------------------------------------------------------

def check_pattern_consistency(root: Path) -> list[dict]:
    """Find folders whose patterns diverge from the codebase-wide norms."""
    enrichments_dir = root / ".archie" / "enrichments"
    if not enrichments_dir.is_dir():
        return []

    # Collect all patterns across all folders
    folder_patterns: dict[str, list[str]] = {}
    all_enrichments: dict[str, dict] = {}
    for json_file in sorted(enrichments_dir.iterdir()):
        if not json_file.name.endswith(".json"):
            continue
        try:
            data = json.loads(json_file.read_text())
            if isinstance(data, dict):
                all_enrichments.update(data)
        except (json.JSONDecodeError, OSError):
            continue

    if not all_enrichments:
        return []

    # Extract pattern names per folder
    pattern_counter: Counter = Counter()
    for folder, info in all_enrichments.items():
        if not isinstance(info, dict):
            continue
        patterns = info.get("patterns", [])
        names = []
        for p in patterns:
            if isinstance(p, dict) and p.get("name"):
                names.append(p["name"].lower().strip())
            elif isinstance(p, str):
                names.append(p.lower().strip())
        folder_patterns[folder] = names
        for n in names:
            pattern_counter[n] += 1

    if not pattern_counter:
        return []

    # Find dominant patterns (used in >25% of folders)
    threshold = max(2, len(folder_patterns) * 0.25)
    dominant = {name for name, count in pattern_counter.items() if count >= threshold}

    # Group folders by their parent to find sibling divergences
    siblings: dict[str, list[str]] = defaultdict(list)
    for folder in folder_patterns:
        parent = str(Path(folder).parent)
        siblings[parent].append(folder)

    findings = []

    # Check sibling consistency — folders under the same parent should use
    # similar patterns
    for parent, sibs in siblings.items():
        if len(sibs) < 2:
            continue
        # Collect patterns used by siblings
        sib_patterns: Counter = Counter()
        for s in sibs:
            for p in folder_patterns.get(s, []):
                sib_patterns[p] += 1
        # Sibling-dominant: used by >50% of siblings
        sib_threshold = len(sibs) * 0.5
        sib_dominant = {name for name, count in sib_patterns.items() if count >= sib_threshold}

        for s in sibs:
            s_pats = set(folder_patterns.get(s, []))
            missing = sib_dominant - s_pats
            if missing and s_pats:  # has some patterns but missing dominant ones
                findings.append({
                    "type": "pattern_divergence",
                    "folder": s,
                    "message": f"Siblings under {parent}/ mostly use [{', '.join(sorted(missing))}] but this folder does not",
                    "expected": sorted(sib_dominant),
                    "actual": sorted(s_pats),
                    "severity": "warn",
                })

    return findings


# ---------------------------------------------------------------------------
# 2. Naming convention violations
# ---------------------------------------------------------------------------

def check_naming_conventions(root: Path) -> list[dict]:
    """Check files against naming conventions from the blueprint."""
    bp = _load_json(root / ".archie" / "blueprint.json")
    rules = bp.get("architecture_rules", {})
    conventions = rules.get("naming_conventions", [])
    scan = _load_json(root / ".archie" / "scan.json")
    files = [f.get("path", "") for f in scan.get("file_tree", [])]

    if not conventions or not files:
        return []

    findings = []
    for conv in conventions:
        if not isinstance(conv, dict):
            continue
        scope = conv.get("scope", "")
        pattern = conv.get("pattern", "")
        description = conv.get("description", "")
        examples = conv.get("examples", [])

        if not pattern or not scope:
            continue

        # Try to build a regex from the pattern description
        # Common patterns: PascalCase, camelCase, snake_case, kebab-case
        regex = None
        pat_lower = pattern.lower()
        if "pascalcase" in pat_lower or "pascal case" in pat_lower:
            regex = r'^[A-Z][a-zA-Z0-9]*'
        elif "camelcase" in pat_lower or "camel case" in pat_lower:
            regex = r'^[a-z][a-zA-Z0-9]*'
        elif "snake_case" in pat_lower or "snake case" in pat_lower:
            regex = r'^[a-z][a-z0-9_]*'
        elif "kebab" in pat_lower:
            regex = r'^[a-z][a-z0-9\-]*'

        if not regex:
            continue

        # Find files that match the scope but violate the pattern
        violations = []
        scope_lower = scope.lower()
        for fp in files:
            # Check if file is in scope — match path segments, not substrings
            fp_lower = fp.lower()
            if not (fp_lower.startswith(scope_lower + "/") or
                    ("/" + scope_lower + "/") in fp_lower or
                    fp_lower == scope_lower):
                continue
            filename = fp.rsplit("/", 1)[-1] if "/" in fp else fp
            name_part = filename.rsplit(".", 1)[0] if "." in filename else filename
            if not re.match(regex, name_part):
                violations.append(fp)

        if violations and len(violations) <= len(files) * 0.3:
            # Only report if it's a minority (actual outliers, not a bad rule)
            findings.append({
                "type": "naming_violation",
                "convention": description or pattern,
                "scope": scope,
                "violating_files": violations[:10],
                "count": len(violations),
                "severity": "info",
            })

    return findings


# ---------------------------------------------------------------------------
# 3. Dependency direction violations
# ---------------------------------------------------------------------------

def check_dependency_direction(root: Path) -> list[dict]:
    """Check import graph against component dependency declarations."""
    bp = _load_json(root / ".archie" / "blueprint.json")
    scan = _load_json(root / ".archie" / "scan.json")
    import_graph = scan.get("import_graph", {})

    comps_raw = bp.get("components", {})
    components = comps_raw.get("components", []) if isinstance(comps_raw, dict) else comps_raw if isinstance(comps_raw, list) else []

    if not import_graph or not components:
        return []

    # Build component location map and allowed dependency map
    comp_by_loc: dict[str, dict] = {}
    for comp in components:
        loc = (comp.get("location") or "").rstrip("/")
        if loc:
            comp_by_loc[loc] = comp

    findings = []

    # For each component, check if files import from components NOT in depends_on
    for comp in components:
        loc = (comp.get("location") or "").rstrip("/")
        if not loc:
            continue
        allowed_deps = set(comp.get("depends_on", []))
        comp_name = comp.get("name", loc)

        # Find all imports from files in this component
        for file_path, imports in import_graph.items():
            if not (file_path.startswith(loc + "/") or file_path == loc):
                continue
            for imp in imports:
                imp_path = imp.replace(".", "/")
                # Check if this import lands in another component
                for other_loc, other_comp in comp_by_loc.items():
                    if other_loc == loc:
                        continue
                    other_name = other_comp.get("name", other_loc)
                    if imp_path.startswith(other_loc) or other_loc in imp_path:
                        if other_name not in allowed_deps and other_loc not in allowed_deps:
                            findings.append({
                                "type": "dependency_violation",
                                "from_component": comp_name,
                                "to_component": other_name,
                                "file": file_path,
                                "import": imp,
                                "message": f"{comp_name} imports from {other_name} but does not declare it as a dependency",
                                "severity": "warn",
                            })

    # Deduplicate by (from, to) pair — keep first occurrence
    seen = set()
    deduped = []
    for f in findings:
        key = (f["from_component"], f["to_component"])
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    return deduped


# ---------------------------------------------------------------------------
# 4. Structural outliers — folders organized differently from siblings
# ---------------------------------------------------------------------------

def check_structural_outliers(root: Path) -> list[dict]:
    """Find folders that are structurally different from their siblings."""
    scan = _load_json(root / ".archie" / "scan.json")
    files = scan.get("file_tree", [])

    if not files:
        return []

    # Count files per directory and collect extensions
    dir_file_counts: dict[str, int] = defaultdict(int)
    dir_extensions: dict[str, Counter] = defaultdict(Counter)
    for f in files:
        p = f.get("path", "")
        if "/" not in p:
            continue
        parent = str(Path(p).parent)
        dir_file_counts[parent] += 1
        ext = f.get("extension", "")
        if ext:
            dir_extensions[parent][ext] += 1

    # Group by grandparent to find sibling directories
    siblings: dict[str, list[str]] = defaultdict(list)
    for d in dir_file_counts:
        grandparent = str(Path(d).parent)
        siblings[grandparent].append(d)

    findings = []
    for grandparent, sibs in siblings.items():
        if len(sibs) < 3:
            continue

        # Check for file count outliers (>3 standard deviations)
        counts = [dir_file_counts[s] for s in sibs]
        if not counts:
            continue
        avg = sum(counts) / len(counts)
        if avg == 0:
            continue
        variance = sum((c - avg) ** 2 for c in counts) / len(counts)
        std = variance ** 0.5

        if std == 0:
            continue

        for s in sibs:
            count = dir_file_counts[s]
            if std > 0 and abs(count - avg) > 3 * std and count > avg:
                findings.append({
                    "type": "structural_outlier",
                    "folder": s,
                    "message": f"Has {count} files — significantly more than sibling average ({avg:.0f}). May be a god-folder that should be split.",
                    "severity": "info",
                })

        # Check for extension mismatches — siblings should have similar file types
        sib_exts: Counter = Counter()
        for s in sibs:
            for ext in dir_extensions[s]:
                sib_exts[ext] += 1
        # Dominant extension: used by >60% of siblings
        dominant_exts = {ext for ext, cnt in sib_exts.items() if cnt >= len(sibs) * 0.6}

        for s in sibs:
            s_exts = set(dir_extensions[s].keys())
            unexpected = s_exts - dominant_exts
            if unexpected and dominant_exts and len(unexpected) > len(dominant_exts):
                findings.append({
                    "type": "structural_outlier",
                    "folder": s,
                    "message": f"Uses [{', '.join(sorted(unexpected))}] while siblings mostly use [{', '.join(sorted(dominant_exts))}]",
                    "severity": "info",
                })

    return findings


# ---------------------------------------------------------------------------
# 5. Anti-pattern clusters — folders with many anti-patterns
# ---------------------------------------------------------------------------

def check_antipattern_clusters(root: Path) -> list[dict]:
    """Find folders with an unusual density of anti-patterns."""
    enrichments_dir = root / ".archie" / "enrichments"
    if not enrichments_dir.is_dir():
        return []

    all_enrichments: dict[str, dict] = {}
    for json_file in sorted(enrichments_dir.iterdir()):
        if not json_file.name.endswith(".json"):
            continue
        try:
            data = json.loads(json_file.read_text())
            if isinstance(data, dict):
                all_enrichments.update(data)
        except (json.JSONDecodeError, OSError):
            continue

    if not all_enrichments:
        return []

    # Count anti-patterns per folder
    ap_counts = {}
    for folder, info in all_enrichments.items():
        if not isinstance(info, dict):
            continue
        anti = info.get("anti_patterns", [])
        if anti:
            ap_counts[folder] = len(anti)

    if not ap_counts:
        return []

    avg = sum(ap_counts.values()) / len(ap_counts) if ap_counts else 0
    threshold = max(avg * 2, 4)

    findings = []
    for folder, count in sorted(ap_counts.items(), key=lambda x: -x[1]):
        if count >= threshold:
            anti = all_enrichments[folder].get("anti_patterns", [])
            findings.append({
                "type": "antipattern_cluster",
                "folder": folder,
                "count": count,
                "anti_patterns": anti[:5],
                "message": f"Has {count} anti-patterns (avg: {avg:.1f}) — high-risk area for accidental violations",
                "severity": "warn",
            })

    return findings


# ---------------------------------------------------------------------------
# Main report
# ---------------------------------------------------------------------------

_SECTIONS = [
    ("pattern_divergences", "Pattern Divergences"),
    ("dependency_violations", "Dependency Violations"),
    ("naming_violations", "Naming Violations"),
    ("structural_outliers", "Structural Outliers"),
    ("antipattern_clusters", "Anti-Pattern Clusters"),
]


def generate_drift_report(root: Path) -> dict:
    """Generate a full drift report."""
    from datetime import datetime, timezone

    report = {
        "pattern_divergences": check_pattern_consistency(root),
        "naming_violations": check_naming_conventions(root),
        "dependency_violations": check_dependency_direction(root),
        "structural_outliers": check_structural_outliers(root),
        "antipattern_clusters": check_antipattern_clusters(root),
    }

    # Summary counts
    total = sum(len(v) for v in report.values())
    warns = sum(1 for v in report.values() for f in v if f.get("severity") == "warn")
    infos = total - warns

    report["summary"] = {
        "total_findings": total,
        "warnings": warns,
        "informational": infos,
        "checks_run": [k for k, v in report.items() if k != "summary"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return report


def print_human_summary(report: dict):
    """Print human-readable drift summary to stderr."""
    summary = report.get("summary", {})
    total = summary.get("total_findings", 0)

    print(f"\nDrift Analysis: {total} findings", file=sys.stderr)

    for section, label in _SECTIONS:
        items = report.get(section, [])
        if not items:
            continue
        print(f"\n  {label} ({len(items)}):", file=sys.stderr)
        for item in items[:5]:
            sev = item.get("severity", "info").upper()
            msg = item.get("message", "")
            folder = item.get("folder", "")
            if folder:
                print(f"    [{sev}] {folder}: {msg}", file=sys.stderr)
            else:
                print(f"    [{sev}] {msg}", file=sys.stderr)
        if len(items) > 5:
            print(f"    ... and {len(items) - 5} more", file=sys.stderr)

    if total == 0:
        print("  No architectural drift detected.", file=sys.stderr)
    print("", file=sys.stderr)


# ---------------------------------------------------------------------------
# Snapshot history
# ---------------------------------------------------------------------------

_HISTORY_DIR = "drift_history"


def _save_snapshot(root: Path, report: dict):
    """Save a timestamped drift snapshot for future diffing."""
    from datetime import datetime, timezone

    history_dir = root / ".archie" / _HISTORY_DIR
    history_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    snapshot_path = history_dir / f"drift_{ts}.json"
    snapshot_path.write_text(json.dumps(report, indent=2))

    # Also update the "latest" symlink / copy for easy access
    latest_path = history_dir / "latest.json"
    latest_path.write_text(json.dumps(report, indent=2))

    return snapshot_path


def _load_previous_snapshot(root: Path) -> dict | None:
    """Load the most recent snapshot before the current one."""
    history_dir = root / ".archie" / _HISTORY_DIR
    if not history_dir.is_dir():
        return None

    snapshots = sorted(
        [f for f in history_dir.iterdir() if f.name.startswith("drift_") and f.name.endswith(".json")],
        key=lambda f: f.name,
    )

    # Return second-to-last (the previous run), since the current run
    # may have already been saved
    if len(snapshots) >= 2:
        try:
            return json.loads(snapshots[-2].read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


# ---------------------------------------------------------------------------
# Diff engine
# ---------------------------------------------------------------------------

def _finding_key(finding: dict) -> str:
    """Create a stable identity key for a finding so we can diff across runs."""
    ftype = finding.get("type", "")
    folder = finding.get("folder", "")
    # For dependency violations, include both ends
    from_comp = finding.get("from_component", "")
    to_comp = finding.get("to_component", "")
    # For naming violations, include scope
    scope = finding.get("scope", "")
    convention = finding.get("convention", "")
    # Include message prefix to disambiguate same-folder findings
    # (e.g., two structural_outlier findings for the same folder: file count vs extension)
    msg = finding.get("message", "")[:80]

    parts = [ftype, folder, from_comp, to_comp, scope, convention, msg]
    return "|".join(p for p in parts if p)


def compute_diff(previous: dict, current: dict) -> dict:
    """Compare two drift reports and return new, resolved, and persisting findings."""
    diff_result = {
        "new": [],       # in current but not in previous
        "resolved": [],  # in previous but not in current
        "persisting": [],  # in both
    }

    prev_ts = previous.get("summary", {}).get("timestamp", "unknown")
    curr_ts = current.get("summary", {}).get("timestamp", "unknown")

    # Collect all findings from both reports, keyed
    prev_findings: dict[str, dict] = {}
    curr_findings: dict[str, dict] = {}

    for section, _ in _SECTIONS:
        for f in previous.get(section, []):
            prev_findings[_finding_key(f)] = f
        for f in current.get(section, []):
            curr_findings[_finding_key(f)] = f

    prev_keys = set(prev_findings.keys())
    curr_keys = set(curr_findings.keys())

    for key in sorted(curr_keys - prev_keys):
        diff_result["new"].append(curr_findings[key])
    for key in sorted(prev_keys - curr_keys):
        diff_result["resolved"].append(prev_findings[key])
    for key in sorted(curr_keys & prev_keys):
        diff_result["persisting"].append(curr_findings[key])

    diff_result["summary"] = {
        "previous_timestamp": prev_ts,
        "current_timestamp": curr_ts,
        "previous_total": previous.get("summary", {}).get("total_findings", 0),
        "current_total": current.get("summary", {}).get("total_findings", 0),
        "new_findings": len(diff_result["new"]),
        "resolved_findings": len(diff_result["resolved"]),
        "persisting_findings": len(diff_result["persisting"]),
    }

    return diff_result


def print_diff_summary(diff_result: dict):
    """Print human-readable diff to stderr."""
    s = diff_result["summary"]
    prev_total = s["previous_total"]
    curr_total = s["current_total"]
    delta = curr_total - prev_total

    delta_str = f"+{delta}" if delta > 0 else str(delta)
    print(f"\nDrift Diff: {prev_total} -> {curr_total} ({delta_str})", file=sys.stderr)
    print(f"  Previous: {s['previous_timestamp']}", file=sys.stderr)
    print(f"  Current:  {s['current_timestamp']}", file=sys.stderr)

    new = diff_result["new"]
    resolved = diff_result["resolved"]
    persisting = diff_result["persisting"]

    if new:
        print(f"\n  NEW ({len(new)}):", file=sys.stderr)
        for item in new:
            sev = item.get("severity", "info").upper()
            folder = item.get("folder", "")
            msg = item.get("message", "")
            print(f"    + [{sev}] {folder}: {msg}", file=sys.stderr)

    if resolved:
        print(f"\n  RESOLVED ({len(resolved)}):", file=sys.stderr)
        for item in resolved:
            sev = item.get("severity", "info").upper()
            folder = item.get("folder", "")
            msg = item.get("message", "")
            print(f"    - [{sev}] {folder}: {msg}", file=sys.stderr)

    if persisting:
        print(f"\n  PERSISTING ({len(persisting)})", file=sys.stderr)

    if not new and not resolved:
        print("\n  No changes since last run.", file=sys.stderr)

    print("", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_run(root: Path):
    """Run drift detection, save snapshot, auto-diff against previous, print summary."""
    report = generate_drift_report(root)
    print_human_summary(report)

    # Save report and snapshot
    out_path = root / ".archie" / "drift_report.json"
    out_path.write_text(json.dumps(report, indent=2))
    snapshot_path = _save_snapshot(root, report)
    print(f"Saved: {out_path}", file=sys.stderr)
    print(f"Snapshot: {snapshot_path}", file=sys.stderr)

    # Auto-diff against previous snapshot if one exists
    previous = _load_previous_snapshot(root)
    if previous:
        diff_result = compute_diff(previous, report)
        print_diff_summary(diff_result)

        diff_path = root / ".archie" / "drift_diff.json"
        diff_path.write_text(json.dumps(diff_result, indent=2))

    # Output JSON to stdout
    print(json.dumps(report, indent=2))


def cmd_history(root: Path):
    """List all drift snapshots with finding counts."""
    history_dir = root / ".archie" / _HISTORY_DIR
    if not history_dir.is_dir():
        print("No drift history found.", file=sys.stderr)
        return

    snapshots = sorted(
        [f for f in history_dir.iterdir() if f.name.startswith("drift_") and f.name.endswith(".json")],
        key=lambda f: f.name,
    )

    if not snapshots:
        print("No drift snapshots found.", file=sys.stderr)
        return

    entries = []
    prev_total = None
    for snap in snapshots:
        try:
            data = json.loads(snap.read_text())
            s = data.get("summary", {})
            total = s.get("total_findings", 0)
            warns = s.get("warnings", 0)
            ts = s.get("timestamp", "")

            delta = ""
            if prev_total is not None:
                d = total - prev_total
                delta = f"  (+{d})" if d > 0 else f"  ({d})" if d < 0 else "  (=)"
            prev_total = total

            entries.append({
                "file": snap.name,
                "timestamp": ts,
                "total": total,
                "warnings": warns,
                "delta": delta,
            })
        except (json.JSONDecodeError, OSError):
            continue

    print(f"\nDrift History ({len(entries)} snapshots):\n", file=sys.stderr)
    for e in entries:
        print(f"  {e['file']}  {e['total']:3d} findings ({e['warnings']} warn){e['delta']}", file=sys.stderr)
    print("", file=sys.stderr)

    # JSON to stdout
    print(json.dumps(entries, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  python3 drift.py /path/to/repo          — run drift detection (auto-diffs if previous exists)", file=sys.stderr)
        print("  python3 drift.py history /path/to/repo   — list all snapshots", file=sys.stderr)
        sys.exit(1)

    # Parse subcommand
    if sys.argv[1] == "history":
        if len(sys.argv) < 3:
            print("Usage: python3 drift.py history /path/to/repo", file=sys.stderr)
            sys.exit(1)
        root = Path(sys.argv[2]).resolve()
        cmd_history(root)
    else:
        root = Path(sys.argv[1]).resolve()
        cmd_run(root)

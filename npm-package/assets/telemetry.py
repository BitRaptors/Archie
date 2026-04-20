#!/usr/bin/env python3
"""Archie telemetry — per-run timing output to .archie/telemetry/.

Assembles step-level timing data and project metadata into a single JSON file
per scan run.  Called at the end of each scan or deep-scan command.

Usage (CLI):
  python3 telemetry.py /path/to/project --command scan --timing-file /tmp/archie_timing.json

The timing file is a JSON array of step objects:
  [{"name": "scan", "started_at": "ISO", "completed_at": "ISO"}, ...]

Programmatic:
  from archie.standalone.telemetry import write_telemetry
  write_telemetry("/path/to/project", "scan", steps_list)

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _parse_iso(ts: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning None on failure."""
    if not ts:
        return None
    try:
        # Handle Z suffix
        normalized = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


def _compute_seconds(started_at: str, completed_at: str) -> int:
    """Compute elapsed seconds between two ISO timestamps.

    Returns 0 if either timestamp is missing or unparseable.
    """
    start = _parse_iso(started_at)
    end = _parse_iso(completed_at)
    if start is None or end is None:
        return 0
    delta = (end - start).total_seconds()
    return max(0, int(delta))


def _read_project_metadata(archie_dir: Path) -> dict:
    """Read project stats from scan.json, returning zeros on failure."""
    defaults = {"source_files": 0, "total_loc": 0, "directories": 0}
    scan_path = archie_dir / "scan.json"
    if not scan_path.exists():
        return defaults
    try:
        data = json.loads(scan_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    stats = data.get("statistics", {})
    if not isinstance(stats, dict):
        return defaults
    return {
        "source_files": stats.get("source_files", 0) or 0,
        "total_loc": stats.get("total_loc", 0) or 0,
        "directories": stats.get("directories", 0) or 0,
    }


def write_telemetry(project_root: str, command: str, steps: list[dict]) -> Path:
    """Write a telemetry JSON file for one scan run.

    Args:
        project_root: Path to the project root.
        command: The command name ("scan" or "deep-scan").
        steps: List of step dicts, each with at least "name", "started_at",
               "completed_at". Extra fields (e.g. "model", "folders_processed")
               are preserved.

    Returns:
        Path to the written telemetry file.
    """
    root = Path(project_root)
    archie_dir = root / ".archie"
    telemetry_dir = archie_dir / "telemetry"
    telemetry_dir.mkdir(parents=True, exist_ok=True)

    project_meta = _read_project_metadata(archie_dir)

    # Enrich each step with computed seconds
    enriched_steps = []
    for step in steps:
        started = step.get("started_at", "")
        completed = step.get("completed_at", "")
        seconds = _compute_seconds(started, completed)
        enriched = {**step, "seconds": seconds}
        enriched_steps.append(enriched)

    # Derive top-level timestamps from first/last step
    started_at = ""
    completed_at = ""
    total_seconds = 0
    if enriched_steps:
        started_at = enriched_steps[0].get("started_at", "")
        # Find last step with a completed_at
        for s in reversed(enriched_steps):
            if s.get("completed_at"):
                completed_at = s["completed_at"]
                break
        total_seconds = _compute_seconds(started_at, completed_at)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    filename = f"{command}_{now}.json"

    output = {
        "command": command,
        "started_at": started_at,
        "completed_at": completed_at,
        "total_seconds": total_seconds,
        "project": project_meta,
        "steps": enriched_steps,
    }

    out_path = telemetry_dir / filename
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote telemetry to {out_path.relative_to(root)}", file=sys.stderr)
    return out_path


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Archie telemetry writer")
    parser.add_argument("project_root", help="Path to project root")
    parser.add_argument("--command", required=True, help="Command name (scan, deep-scan)")
    parser.add_argument("--timing-file", required=True, help="Path to JSON file with step timing data")
    args = parser.parse_args()

    timing_path = Path(args.timing_file)
    if not timing_path.exists():
        print(f"error: timing file not found: {timing_path}", file=sys.stderr)
        sys.exit(1)

    try:
        steps = json.loads(timing_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"error: could not read timing file: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(steps, list):
        print("error: timing file must contain a JSON array", file=sys.stderr)
        sys.exit(1)

    write_telemetry(args.project_root, args.command, steps)


if __name__ == "__main__":
    main()

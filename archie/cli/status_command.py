"""Implementation of `archie status` — displays blueprint freshness dashboard."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import click


def run_status(project_root: Path) -> None:
    """Read .archie/ artifacts and display a status dashboard."""
    root = project_root.resolve()
    archie_dir = root / ".archie"
    blueprint_path = archie_dir / "blueprint.json"

    # 1. Check blueprint existence
    if not blueprint_path.exists():
        click.echo("No blueprint found. Run: archie init .")
        return

    # 2. Load blueprint
    blueprint = _load_json(blueprint_path)
    analyzed_at = "N/A"
    blueprint_files: dict[str, str] = {}
    if blueprint is not None:
        meta = blueprint.get("meta", {})
        analyzed_at = meta.get("analyzed_at", "N/A")
        # Blueprint stores file hashes under file_tree or files key
        blueprint_files = _extract_blueprint_files(blueprint)

    # 3. Load scan.json and compute freshness
    scan_path = archie_dir / "scan.json"
    scan = _load_json(scan_path)
    scan_files: dict[str, str] = {}
    last_refresh = "N/A"
    if scan is not None:
        scan_files = _extract_scan_files(scan)
        try:
            mtime = os.path.getmtime(scan_path)
            last_refresh = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
        except OSError:
            last_refresh = "N/A"

    # Compute freshness stats
    blueprint_set = set(blueprint_files.keys())
    scan_set = set(scan_files.keys())
    new_files = scan_set - blueprint_set
    deleted_files = blueprint_set - scan_set
    common_files = blueprint_set & scan_set
    modified_files = {
        f for f in common_files if blueprint_files.get(f) != scan_files.get(f)
    }

    # 4. Load rules.json
    rules_path = archie_dir / "rules.json"
    rules_data = _load_json(rules_path)
    rules_list: list[dict] = []
    if rules_data is not None:
        rules_list = rules_data.get("rules", [])

    total_rules = len(rules_list)
    warn_rules = sum(1 for r in rules_list if r.get("severity") == "warn")
    error_rules = sum(1 for r in rules_list if r.get("severity") == "error")

    # 5. Load stats.jsonl
    stats_path = archie_dir / "stats.jsonl"
    checks_run = 0
    warnings = 0
    blocks = 0
    stats_available = False
    if stats_path.exists():
        try:
            for line in stats_path.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                checks_run += 1
                result = entry.get("result", "")
                if result == "warn":
                    warnings += 1
                elif result == "block":
                    blocks += 1
            stats_available = True
        except (json.JSONDecodeError, OSError):
            stats_available = False

    # 6. Print dashboard
    click.echo("")
    click.echo("Archie Blueprint Status")
    click.echo("\u2550" * 47)

    click.echo(f"  Last analysis:      {analyzed_at}")
    click.echo(f"  Last local refresh: {last_refresh}")
    click.echo("")

    if scan is not None:
        click.echo("Freshness")
        click.echo("\u2500" * 41)
        click.echo(f"  Files in blueprint:  {len(blueprint_files)}")
        click.echo(f"  Files on disk:       {len(scan_files)}")
        click.echo(f"  New files:           {len(new_files)}")
        click.echo(f"  Deleted files:       {len(deleted_files)}")
        click.echo(f"  Modified files:      {len(modified_files)}")
    else:
        click.echo("Freshness")
        click.echo("\u2500" * 41)
        click.echo("  N/A")
    click.echo("")

    if rules_data is not None:
        click.echo("Rules")
        click.echo("\u2500" * 41)
        click.echo(f"  Total:    {total_rules}")
        click.echo(f"  Warn:     {warn_rules}")
        click.echo(f"  Error:    {error_rules}")
    else:
        click.echo("Rules")
        click.echo("\u2500" * 41)
        click.echo("  N/A")
    click.echo("")

    if stats_available:
        click.echo("Enforcement (from stats.jsonl)")
        click.echo("\u2500" * 41)
        click.echo(f"  Checks run:        {checks_run}")
        click.echo(f"  Warnings:          {warnings}")
        click.echo(f"  Blocks:            {blocks}")
    else:
        click.echo("Enforcement (from stats.jsonl)")
        click.echo("\u2500" * 41)
        click.echo("  N/A")
    click.echo("")


def _load_json(path: Path) -> dict | None:
    """Safely load a JSON file, returning None on any error."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _extract_blueprint_files(blueprint: dict) -> dict[str, str]:
    """Extract file-path -> hash mapping from a blueprint."""
    files: dict[str, str] = {}
    # Try common structures
    file_tree = blueprint.get("file_tree", {})
    if isinstance(file_tree, dict):
        for fpath, info in file_tree.items():
            if isinstance(info, dict):
                files[fpath] = info.get("hash", "")
            elif isinstance(info, str):
                files[fpath] = info
    # Also check "files" key
    file_list = blueprint.get("files", {})
    if isinstance(file_list, dict):
        for fpath, info in file_list.items():
            if isinstance(info, dict):
                files[fpath] = info.get("hash", "")
            elif isinstance(info, str):
                files[fpath] = info
    return files


def _extract_scan_files(scan: dict) -> dict[str, str]:
    """Extract file-path -> hash mapping from scan.json."""
    files: dict[str, str] = {}
    file_tree = scan.get("file_tree", {})
    if isinstance(file_tree, dict):
        for fpath, info in file_tree.items():
            if isinstance(info, dict):
                files[fpath] = info.get("hash", "")
            elif isinstance(info, str):
                files[fpath] = info
    # Also support flat "files" key
    file_list = scan.get("files", {})
    if isinstance(file_list, dict):
        for fpath, info in file_list.items():
            if isinstance(info, dict):
                files[fpath] = info.get("hash", "")
            elif isinstance(info, str):
                files[fpath] = info
    return files

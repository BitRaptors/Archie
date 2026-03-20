"""Implementation of `archie refresh` — rescans and detects changes."""
from __future__ import annotations

import json
from pathlib import Path

import click

from archie.coordinator.planner import plan_subagent_groups
from archie.coordinator.prompts import build_subagent_prompt
from archie.engine.scan import run_scan


def _load_existing_hashes(archie_dir: Path) -> dict[str, str]:
    """Load file_hashes from the existing blueprint or scan."""
    blueprint_path = archie_dir / "blueprint.json"
    if blueprint_path.exists():
        try:
            data = json.loads(blueprint_path.read_text(encoding="utf-8"))
            return data.get("file_hashes", {})
        except (json.JSONDecodeError, OSError):
            pass

    scan_path = archie_dir / "scan.json"
    if scan_path.exists():
        try:
            data = json.loads(scan_path.read_text(encoding="utf-8"))
            return data.get("file_hashes", {})
        except (json.JSONDecodeError, OSError):
            pass

    return {}


def _compute_changes(
    old_hashes: dict[str, str],
    new_hashes: dict[str, str],
) -> tuple[list[str], list[str], list[str]]:
    """Return (new_files, deleted_files, modified_files)."""
    old_keys = set(old_hashes.keys())
    new_keys = set(new_hashes.keys())

    new_files = sorted(new_keys - old_keys)
    deleted_files = sorted(old_keys - new_keys)
    modified_files = sorted(
        f for f in old_keys & new_keys if old_hashes[f] != new_hashes[f]
    )
    return new_files, deleted_files, modified_files


def run_refresh(project_root: Path, deep: bool = False) -> None:
    """Rescan the repository and report changes since last scan/blueprint.

    Level 2 (always): rescan, compare hashes, print diff summary.
    Level 3 (--deep): generate a targeted refresh prompt for changed files.
    """
    root = Path(project_root).resolve()
    archie_dir = root / ".archie"

    # Load old hashes before rescanning
    old_hashes = _load_existing_hashes(archie_dir)

    # 1. Rescan
    click.echo("Scanning repository...")
    scan = run_scan(root, save=True)

    new_hashes = scan.file_hashes

    # 2-3. Compare
    new_files, deleted_files, modified_files = _compute_changes(old_hashes, new_hashes)

    # 4. Print summary
    total_changes = len(new_files) + len(deleted_files) + len(modified_files)

    if old_hashes:
        click.echo(f"\nChanges detected: {total_changes}")
        if new_files:
            click.echo(f"  New files: {len(new_files)}")
            for f in new_files[:20]:
                click.echo(f"    + {f}")
            if len(new_files) > 20:
                click.echo(f"    ... and {len(new_files) - 20} more")
        if deleted_files:
            click.echo(f"  Deleted files: {len(deleted_files)}")
            for f in deleted_files[:20]:
                click.echo(f"    - {f}")
            if len(deleted_files) > 20:
                click.echo(f"    ... and {len(deleted_files) - 20} more")
        if modified_files:
            click.echo(f"  Modified files: {len(modified_files)}")
            for f in modified_files[:20]:
                click.echo(f"    ~ {f}")
            if len(modified_files) > 20:
                click.echo(f"    ... and {len(modified_files) - 20} more")
        if total_changes == 0:
            click.echo("  No changes since last scan.")
    else:
        click.echo("\nNo previous scan found — baseline created.")
        click.echo(f"  Total files: {len(new_hashes)}")

    # Level 3: deep refresh
    if deep:
        changed_files = new_files + modified_files
        if not changed_files and not deleted_files:
            click.echo("\nNo changes to analyze — skipping deep refresh.")
            return

        # 5-6. Build targeted prompt
        click.echo("\nGenerating targeted refresh prompt...")

        # Create a targeted assignment for changed files only
        from archie.coordinator.planner import SubagentAssignment, ALL_SECTIONS

        assignment = SubagentAssignment(
            files=changed_files,
            token_total=sum(scan.token_counts.get(f, 0) for f in changed_files),
            sections=list(ALL_SECTIONS),
            module_hint="refresh-target",
        )

        prompt = build_subagent_prompt(assignment, scan)

        # Add refresh-specific context
        refresh_header = "# Refresh Analysis Prompt\n\n"
        refresh_header += "This is a **targeted refresh** — only changed files need deep analysis.\n\n"
        if deleted_files:
            refresh_header += "## Deleted files\n"
            for f in deleted_files:
                refresh_header += f"- {f}\n"
            refresh_header += "\n"
        refresh_header += "## Instructions\n"
        refresh_header += (
            "Analyze the changed files below and update the relevant blueprint sections. "
            "Focus on how these changes affect the existing architecture.\n\n"
        )
        refresh_header += "---\n\n"

        full_prompt = refresh_header + prompt

        # 7. Save
        archie_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = archie_dir / "refresh_prompt.md"
        prompt_path.write_text(full_prompt, encoding="utf-8")

        click.echo(f"  Saved: .archie/refresh_prompt.md")
        click.echo('\nRun /archie-refresh in Claude Code to complete deep analysis')

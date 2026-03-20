"""Implementation of `archie check` — validate changed files against rules."""

from __future__ import annotations

import subprocess
from pathlib import Path

import click

from archie.hooks.enforcement import check_pre_validate
from archie.rules.extractor import load_rules


def _git_changed_files(project_root: Path) -> list[str]:
    """Return files changed in the last commit via git diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True,
            text=True,
            cwd=project_root,
        )
        if result.returncode != 0:
            return []
        return [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    except FileNotFoundError:
        return []


def run_check(project_root: Path, files: list[str] | None = None) -> int:
    """Check files against architecture rules.

    Returns 0 if no errors, 1 if any error-severity violations.
    """
    project_root = project_root.resolve()
    archie_dir = project_root / ".archie"

    # No .archie directory — nothing to check
    if not archie_dir.is_dir():
        click.echo("No .archie/ directory found. Run `archie init` first.")
        click.echo("Skipping architecture check.")
        return 0

    rules = load_rules(project_root)
    if not rules:
        click.echo("No rules found in .archie/rules.json. Nothing to check.")
        return 0

    # Determine files to check
    if files:
        changed_files = files
    else:
        changed_files = _git_changed_files(project_root)

    if not changed_files:
        click.echo("No changed files to check.")
        return 0

    click.echo("Archie Architecture Check")
    click.echo("\u2550" * 25)
    click.echo(f"Checking {len(changed_files)} files against {len(rules)} rules...\n")

    total_pass = 0
    total_warn = 0
    total_error = 0

    for fpath in changed_files:
        result = check_pre_validate(fpath, rules)
        errors = result["errors"]
        warnings = result["warnings"]

        if errors:
            total_error += 1
            # Show first error as summary
            short = errors[0].split(":", 1)[-1].strip() if errors else ""
            click.echo(f"\u2717 {fpath} \u2014 error: {short}")
        elif warnings:
            total_warn += 1
            short = warnings[0].split(":", 1)[-1].strip() if warnings else ""
            click.echo(f"\u26a0 {fpath} \u2014 warning: {short}")
        else:
            total_pass += 1
            click.echo(f"\u2713 {fpath} \u2014 pass")

    click.echo(f"\nResults: {total_pass} pass, {total_warn} warning, {total_error} error")

    return 1 if total_error > 0 else 0

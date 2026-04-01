"""Implementation of `archie init` — runs the full local pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import click

from archie.coordinator.merger import merge_subagent_outputs, save_blueprint
from archie.coordinator.planner import plan_subagent_groups
from archie.coordinator.prompts import build_coordinator_prompt, build_subagent_prompt
from archie.coordinator.runner import check_claude_cli, run_subagents
from archie.engine.scan import run_scan
from archie.hooks.generator import install_git_hook, install_hooks
from archie.renderer.render import render_outputs
from archie.rules.extractor import extract_rules, save_rules


def run_init(repo_path: Path, local_only: bool = False) -> None:
    """Run the full Archie pipeline on *repo_path*.

    When *local_only* is False (the default), spawns Claude Code subagents
    to analyse the codebase and produces a full blueprint + rendered outputs.

    When *local_only* is True, only scans the repo and saves prompts for
    manual subagent execution.
    """
    root = Path(repo_path).resolve()
    archie_dir = root / ".archie"
    archie_dir.mkdir(parents=True, exist_ok=True)

    # 1. Scan
    click.echo("Scanning repository...")
    scan = run_scan(root, save=True)

    # 2. Stats
    file_count = len(scan.file_tree)
    frameworks = [f.name for f in scan.framework_signals]
    dep_count = len(scan.dependencies)
    total_tokens = sum(scan.token_counts.values())

    click.echo(f"  Files: {file_count}")
    click.echo(f"  Frameworks: {', '.join(frameworks) if frameworks else 'none detected'}")
    click.echo(f"  Dependencies: {dep_count}")
    click.echo(f"  Tokens: {total_tokens}")

    # 3. Plan subagent groups
    click.echo("Planning subagent groups...")
    groups = plan_subagent_groups(scan)
    click.echo(f"  Groups: {len(groups)}")

    # 4. Generate and save prompts
    click.echo("Generating prompts...")
    coordinator_prompt = build_coordinator_prompt(scan, groups)
    coord_path = archie_dir / "coordinator_prompt.md"
    coord_path.write_text(coordinator_prompt, encoding="utf-8")

    for i, group in enumerate(groups, 1):
        subagent_prompt = build_subagent_prompt(group, scan)
        sub_path = archie_dir / f"subagent_{i}_prompt.md"
        sub_path.write_text(subagent_prompt, encoding="utf-8")

    # 5. Install hooks
    click.echo("Installing hooks...")
    install_hooks(root)

    # 5b. Install git post-commit hook for auto-refresh
    if install_git_hook(root):
        click.echo("  Installed git post-commit hook for auto-refresh")

    if not local_only:
        # --- Full pipeline: spawn subagents, merge, render ---
        if not check_claude_cli():
            click.echo(
                "Error: claude CLI not found in PATH. "
                "Install it or use --local-only to skip subagent execution."
            )
            save_rules(root, [])
            return

        # 6a. Run subagents
        click.echo("")
        click.echo("Running analysis subagents...")
        outputs = run_subagents(root, scan, groups)

        if not outputs:
            click.echo("Warning: no subagent produced output. Saving empty rules.")
            save_rules(root, [])
            return

        # 6b. Merge subagent outputs
        click.echo("Merging subagent outputs...")
        repo_name = root.name
        blueprint = merge_subagent_outputs(outputs, scan, repo_name=repo_name)
        save_blueprint(root, blueprint)
        click.echo("  Blueprint saved to .archie/blueprint.json")

        # 6c. Render outputs
        click.echo("Rendering outputs...")
        rendered_files = render_outputs(blueprint, root)
        for rel_path in sorted(rendered_files.keys()):
            click.echo(f"  {rel_path}")

        # 6d. Extract and save rules
        click.echo("Extracting rules from blueprint...")
        rules = extract_rules(blueprint)
        save_rules(root, rules)
        click.echo(f"  Rules extracted: {len(rules)}")
    else:
        # --- Local-only: just extract rules from existing blueprint ---
        blueprint_path = archie_dir / "blueprint.json"
        if blueprint_path.exists():
            click.echo("Extracting rules from blueprint...")
            blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
            rules = extract_rules(blueprint)
            save_rules(root, rules)
            click.echo(f"  Rules extracted: {len(rules)}")
        else:
            click.echo("No blueprint found, saving empty rules...")
            save_rules(root, [])

    # 7. Summary
    click.echo("")
    click.echo("Archie initialized successfully!")
    click.echo("  .archie/scan.json")
    click.echo("  .archie/coordinator_prompt.md")
    for i in range(1, len(groups) + 1):
        click.echo(f"  .archie/subagent_{i}_prompt.md")
    click.echo("  .archie/rules.json")
    click.echo("  .claude/hooks/inject-context.sh")
    click.echo("  .claude/hooks/pre-validate.sh")
    click.echo("  .claude/settings.local.json")

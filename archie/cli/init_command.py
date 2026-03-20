"""Implementation of `archie init` — runs the full local pipeline."""
from __future__ import annotations

import json
from pathlib import Path

import click

from archie.coordinator.planner import plan_subagent_groups
from archie.coordinator.prompts import build_coordinator_prompt, build_subagent_prompt
from archie.engine.scan import run_scan
from archie.hooks.generator import install_hooks
from archie.rules.extractor import extract_rules, save_rules


def run_init(repo_path: Path, local_only: bool = False) -> None:
    """Run the full local Archie pipeline on *repo_path*.

    Steps:
    1. Scan the repository and save scan.json
    2. Print scan stats
    3. Plan subagent groups
    4. Generate and save coordinator + subagent prompts
    5. Install Claude Code hooks
    6. Extract rules from blueprint (if present) or save empty rules
    7. Print summary
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

    # 6. Rules
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
    click.echo(f"  .archie/scan.json")
    click.echo(f"  .archie/coordinator_prompt.md")
    for i in range(1, len(groups) + 1):
        click.echo(f"  .archie/subagent_{i}_prompt.md")
    click.echo(f"  .archie/rules.json")
    click.echo(f"  .claude/hooks/inject-context.sh")
    click.echo(f"  .claude/hooks/pre-validate.sh")
    click.echo(f"  .claude/settings.local.json")

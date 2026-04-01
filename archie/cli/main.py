import click
from pathlib import Path

from archie.cli.init_command import run_init
from archie.cli.refresh_command import run_refresh
from archie.cli.status_command import run_status
from archie.rules.extractor import load_rules, promote_rule, demote_rule

@click.group()
@click.version_option()
def cli():
    """Archie — your AI writes code, Archie enforces your architecture."""
    pass

@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--local-only", is_flag=True, default=False, help="Run in local-only mode (no remote calls).")
def init(path, local_only):
    """Analyze a repository and generate architecture blueprint + enforcement."""
    run_init(Path(path), local_only=local_only)

@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--deep", is_flag=True, default=False, help="Generate a targeted refresh prompt for changed files.")
def refresh(path, deep):
    """Rescan the repository and report changes since last scan."""
    run_refresh(Path(path), deep=deep)

@cli.command()
@click.option("--path", default=".", type=click.Path(exists=True), help="Project root directory.")
def status(path):
    """Show blueprint freshness and enforcement stats."""
    run_status(Path(path))

@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def rules(path):
    """List all architecture rules."""
    project_root = Path(path).resolve()
    rule_list = load_rules(project_root)
    if not rule_list:
        click.echo("No rules found. Run `archie init` first.")
        return
    for r in rule_list:
        sev = r.get("severity", "warn")
        rid = r.get("id", "unknown")
        desc = r.get("description", "")
        click.echo(f"  [{sev}] {rid}: {desc}")

@cli.command()
@click.argument("rule_id")
@click.argument("path", default=".", type=click.Path(exists=True))
def promote(rule_id, path):
    """Promote a rule to error severity (blocks code changes)."""
    project_root = Path(path).resolve()
    if promote_rule(project_root, rule_id):
        click.echo(f"Rule {rule_id} promoted to error.")
    else:
        click.echo(f"Rule {rule_id} not found.")

@cli.command()
@click.argument("rule_id")
@click.argument("path", default=".", type=click.Path(exists=True))
def demote(rule_id, path):
    """Demote a rule to warn severity (advisory only)."""
    project_root = Path(path).resolve()
    if demote_rule(project_root, rule_id):
        click.echo(f"Rule {rule_id} demoted to warn.")
    else:
        click.echo(f"Rule {rule_id} not found.")

@cli.command()
@click.option("--port", default=8000, help="Port to serve on.")
@click.option("--path", default=".", type=click.Path(exists=True), help="Project root with .archie/ directory.")
def serve(port, path):
    """Start lightweight viewer server for the frontend dashboard."""
    from archie.cli.serve_command import run_serve
    run_serve(Path(path), port)

@cli.command()
@click.option("--files", "-f", multiple=True, help="Specific files to check (default: git diff)")
@click.option("--path", default=".", type=click.Path(exists=True))
def check(files, path):
    """Check files against architecture rules (for CI)."""
    from archie.cli.check_command import run_check
    file_list = list(files) if files else None
    exit_code = run_check(Path(path), file_list)
    raise SystemExit(exit_code)


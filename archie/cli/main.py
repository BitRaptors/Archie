import click

@click.group()
@click.version_option()
def cli():
    """Archie — your AI writes code, Archie enforces your architecture."""
    pass

@cli.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def init(path):
    """Analyze a repository and generate architecture blueprint + enforcement."""
    click.echo(f"archie init {path} — not yet implemented")

@cli.command()
def status():
    """Show blueprint freshness and enforcement stats."""
    click.echo("archie status — not yet implemented")

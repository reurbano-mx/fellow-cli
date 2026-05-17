import click

from fellowai import __version__


@click.group()
@click.version_option(__version__, prog_name="fellowai")
def cli() -> None:
    """Unofficial CLI for Fellow.ai's developer API."""


@cli.command()
def login() -> None:
    """Configure workspace and API key."""
    raise NotImplementedError


@cli.command()
def logout() -> None:
    """Delete stored configuration."""
    raise NotImplementedError


@cli.command()
def me() -> None:
    """Show authenticated identity and workspace."""
    raise NotImplementedError


@cli.group()
def recordings() -> None:
    """Recording operations."""


@cli.group()
def notes() -> None:
    """Note operations."""


@cli.group(name="action-items")
def action_items() -> None:
    """Action item operations."""

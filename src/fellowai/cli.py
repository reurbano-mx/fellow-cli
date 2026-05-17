import click

from fellowai import __version__
from fellowai.commands.auth import login, logout, me


@click.group()
@click.version_option(__version__, prog_name="fellowai")
def cli() -> None:
    """Unofficial CLI for Fellow.ai's developer API."""


cli.add_command(login)
cli.add_command(logout)
cli.add_command(me)


@cli.group()
def recordings() -> None:
    """Recording operations."""


@cli.group()
def notes() -> None:
    """Note operations."""


@cli.group(name="action-items")
def action_items() -> None:
    """Action item operations."""

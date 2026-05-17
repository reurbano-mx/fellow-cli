import click

from fellowai import __version__
from fellowai.commands.auth import login, logout, me
from fellowai.commands import action_items as ai_cmds
from fellowai.commands import notes as notes_cmds
from fellowai.commands import recordings as recordings_cmds


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


recordings_cmds.register(recordings)


@cli.group()
def notes() -> None:
    """Note operations."""


notes_cmds.register(notes)


@cli.group(name="action-items")
def action_items() -> None:
    """Action item operations."""


ai_cmds.register(action_items)

import click

from fellowai import __version__
from fellowai.commands.auth import install_skill, login, logout, me
from fellowai.commands import action_items as ai_cmds
from fellowai.commands import notes as notes_cmds
from fellowai.commands import recordings as recordings_cmds


@click.group()
@click.version_option(__version__, prog_name="fellowai")
@click.option("--debug", is_flag=True, help="Show tracebacks and HTTP details on errors.")
@click.option("--verbose", "-v", is_flag=True,
              help="Log every HTTP request and response to stderr.")
@click.pass_context
def cli(ctx: click.Context, debug: bool, verbose: bool) -> None:
    """Unofficial CLI for Fellow.ai's developer API."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["verbose"] = verbose


cli.add_command(login)
cli.add_command(logout)
cli.add_command(me)
cli.add_command(install_skill)


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

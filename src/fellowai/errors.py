"""Shared error-to-CLI mapping."""

from __future__ import annotations

import sys
import traceback

import click

from fellowai.client import FellowError
from fellowai.config import ConfigError


def handle(error: Exception) -> None:
    """Print a sentence-shaped error or a traceback depending on --debug.

    Exits 1 for user-input validation errors (ValueError), 2 otherwise.
    """
    ctx = click.get_current_context(silent=True)
    debug = bool(ctx.obj.get("debug")) if (ctx and ctx.obj) else False

    if debug:
        traceback.print_exc(file=sys.stderr)
    elif isinstance(error, (FellowError, ConfigError, ValueError)):
        click.echo(f"Error: {error}", err=True)
    else:
        click.echo(f"Unexpected error: {error}. Re-run with --debug for details.", err=True)

    sys.exit(1 if isinstance(error, ValueError) else 2)

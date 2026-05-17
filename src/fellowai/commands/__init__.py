"""Shared helpers for command modules."""

from __future__ import annotations

import re
import sys

import click

from fellowai.client import FellowClient
from fellowai.config import ConfigError, load_config

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def make_client() -> FellowClient:
    """Build a FellowClient from saved/env config, or exit with a sentence error."""
    try:
        cfg = load_config()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    try:
        return FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def safe_filename_id(value: str) -> str:
    """Return value if it matches the resource-id charset, else raise ValueError.

    Guards against path traversal when writing API-returned ids to disk —
    Fellow ids are alphanumeric, but defense-in-depth refuses anything with
    slashes, dots, or other separators before it reaches the filesystem.
    """
    if not isinstance(value, str) or not _SAFE_ID.match(value):
        raise ValueError(f"Refusing to use unsafe resource id as filename: {value!r}")
    return value

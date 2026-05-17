"""Shared helpers for command modules."""

from __future__ import annotations

import sys

import click

from fellowai.client import FellowClient
from fellowai.config import ConfigError, load_config


def make_client() -> FellowClient:
    """Build a FellowClient from saved/env config, or exit 2 with a sentence error."""
    try:
        cfg = load_config()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    return FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)

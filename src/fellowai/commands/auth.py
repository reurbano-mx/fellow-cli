"""Login / logout / me commands."""

from __future__ import annotations

import sys
import webbrowser

import click

from fellowai.client import AuthError, FellowClient, FellowError
from fellowai.config import Config, ConfigError, delete_config, load_config, save_config


@click.command()
def login() -> None:
    """Configure your Fellow workspace and API key."""
    subdomain = click.prompt("Workspace subdomain", type=str).strip()
    url = f"https://{subdomain}.fellow.app/settings/api-keys"
    click.echo(f"Opening {url} ...")
    try:
        webbrowser.open(url)
    except Exception:
        click.echo("(Couldn't auto-open the browser. Open the URL above manually.)")
    api_key = click.prompt("API key", type=str, hide_input=True).strip()

    client = FellowClient(subdomain=subdomain, api_key=api_key)
    try:
        me = client.get_me()
    except AuthError as e:
        click.echo(f"Login failed: {e}", err=True)
        click.echo("Double-check your subdomain and API key.", err=True)
        sys.exit(2)
    except FellowError as e:
        click.echo(f"Login failed: {e}", err=True)
        sys.exit(2)

    save_config(Config(subdomain=subdomain, api_key=api_key))
    user = me.get("user", {})
    click.echo(f"✓ Authenticated as {user.get('email', '?')}")
    click.echo(f"✓ Saved to {_config_path_display()}")


def _config_path_display() -> str:
    import os
    from fellowai.config import _config_path  # type: ignore[attr-defined]
    return str(_config_path()).replace(os.path.expanduser("~"), "~")


@click.command()
def logout() -> None:
    """Delete stored configuration."""
    delete_config()
    click.echo("Logged out.")


@click.command()
def me() -> None:
    """Show authenticated identity and workspace."""
    try:
        cfg = load_config()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)

    client = FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)
    try:
        m = client.get_me()
    except FellowError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    user = m.get("user", {})
    ws = m.get("workspace", {})
    last4 = cfg.api_key[-4:] if len(cfg.api_key) >= 4 else "????"
    click.echo(f"{user.get('email', '?')}  workspace: {ws.get('subdomain', '?')}  key: ...{last4}")

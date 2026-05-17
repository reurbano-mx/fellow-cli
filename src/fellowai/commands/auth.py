"""Login / logout / me commands."""
from __future__ import annotations

import importlib.resources as resources
import sys
import webbrowser
from pathlib import Path

import click

from fellowai.client import AuthError, FellowClient, FellowError, _validate_subdomain
from fellowai.config import Config, ConfigError, delete_config, load_config, save_config


@click.command()
def login() -> None:
    """Configure your Fellow workspace and API key."""
    subdomain = click.prompt("Workspace subdomain", type=str).strip()
    try:
        _validate_subdomain(subdomain)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    url = f"https://{subdomain}.fellow.app/"
    click.echo(f"Opening {url} ...")
    click.echo(
        "In Fellow: click your workspace name (top left) → "
        "User settings → API, MCP & Webhooks → New API key."
    )
    click.echo(
        "Note: a workspace admin must first enable Developer API access "
        "under Workspace settings → Security."
    )
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

    try:
        client = FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    try:
        m = client.get_me()
    except FellowError as e:
        from fellowai.errors import handle
        handle(e)

    user = m.get("user", {})
    ws = m.get("workspace", {})
    last4 = cfg.api_key[-4:] if len(cfg.api_key) >= 4 else "????"
    click.echo(f"{user.get('email', '?')}  workspace: {ws.get('subdomain', '?')}  key: ...{last4}")


@click.command(name="install-skill")
def install_skill() -> None:
    """Install fellowai's SKILL.md into ~/.claude/skills/fellowai/."""
    skill_text = resources.files("fellowai").joinpath("SKILL.md").read_text()
    home = Path.home()
    dest_dir = home / ".claude" / "skills" / "fellowai"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / "SKILL.md"
    dest_file.write_text(skill_text)
    click.echo(f"✓ Installed skill to {dest_file}")

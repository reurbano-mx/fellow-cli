"""Notes commands: list, get, export."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from fellowai.client import FellowClient, FellowError
from fellowai.config import ConfigError, load_config
from fellowai.output import emit, render_note_markdown
from fellowai.time_parse import parse_since


def _client() -> FellowClient:
    try:
        cfg = load_config()
    except ConfigError as e:
        click.echo(str(e), err=True)
        sys.exit(2)
    return FellowClient(subdomain=cfg.subdomain, api_key=cfg.api_key)


def _build_filters(since: str | None, until: str | None) -> dict:
    filters: dict[str, Any] = {}
    if since:
        filters["created_at_start"] = parse_since(since)
    if until:
        filters["created_at_end"] = parse_since(until)
    return filters


def _build_include(with_content: bool, with_attendees: bool) -> dict:
    include: dict[str, Any] = {}
    if with_content:
        include["content_markdown"] = True
    if with_attendees:
        include["event_attendees"] = True
    return include


@click.command(name="list")
@click.option("--since")
@click.option("--until")
@click.option("--with-content", is_flag=True)
@click.option("--with-attendees", is_flag=True)
@click.option("--limit", type=int, default=50)
@click.option("--page-size", type=click.IntRange(1, 50), default=20)
@click.option("--json", "format_override", flag_value="json")
def notes_list(since, until, with_content, with_attendees, limit, page_size, format_override):
    """List notes."""
    client = _client()
    filters = _build_filters(since, until)
    include = _build_include(with_content, with_attendees)
    try:
        items = list(client.list_notes(
            filters=filters or None, include=include or None,
            limit=limit, page_size=page_size,
        ))
    except FellowError as e:
        from fellowai.errors import handle
        handle(e)
    emit(items, shape="list",
         columns=["id", "title", "event_start"],
         format_override=format_override,
         empty_message="No notes.")


@click.command(name="get")
@click.argument("note_id")
@click.option("--json", "format_override", flag_value="json")
@click.option("--md", "format_override", flag_value="md")
def notes_get(note_id, format_override):
    """Retrieve a single note (content and attendees included by default)."""
    client = _client()
    try:
        note = client.get_note(note_id)
    except FellowError as e:
        from fellowai.errors import handle
        handle(e)
    emit(note, shape="document",
         markdown_renderer=render_note_markdown,
         format_override=format_override or "md")


@click.command(name="export")
@click.option("--since")
@click.option("--until")
@click.option("--with-content", is_flag=True)
@click.option("--with-attendees", is_flag=True)
@click.option("--limit", type=int, default=200)
@click.option("--page-size", type=click.IntRange(1, 50), default=50)
@click.option("--format", "fmt", type=click.Choice(["json", "md", "both"]), default="md")
@click.option("--to", "destination", required=True)
def notes_export(since, until, with_content, with_attendees, limit, page_size, fmt, destination):
    """Export notes to disk or stdout."""
    if destination == "-" and fmt == "both":
        click.echo("Cannot export 'both' formats to stdout — pick json or md.", err=True)
        sys.exit(1)

    client = _client()
    filters = _build_filters(since, until)
    include = _build_include(with_content, with_attendees)
    try:
        items = list(client.list_notes(
            filters=filters or None, include=include or None,
            limit=limit, page_size=page_size,
        ))
    except FellowError as e:
        from fellowai.errors import handle
        handle(e)

    if destination == "-":
        if fmt == "json":
            sys.stdout.write(json.dumps(items, default=str) + "\n")
        else:
            for i, n in enumerate(items):
                if i:
                    sys.stdout.write("\n---\n\n")
                sys.stdout.write(render_note_markdown(n))
        return

    outdir = Path(destination)
    outdir.mkdir(parents=True, exist_ok=True)
    for n in items:
        nid = n["id"]
        if fmt in ("json", "both"):
            (outdir / f"{nid}.json").write_text(json.dumps(n, default=str))
        if fmt in ("md", "both"):
            (outdir / f"{nid}.md").write_text(render_note_markdown(n))


def register(group: click.Group) -> None:
    group.add_command(notes_list)
    group.add_command(notes_get)
    group.add_command(notes_export)

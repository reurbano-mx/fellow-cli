"""Recordings commands: list, get, export."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from fellowai.client import FellowError
from fellowai.commands import make_client as _client
from fellowai.output import emit, render_recording_markdown
from fellowai.time_parse import parse_since


def _build_filters(since: str | None, until: str | None,
                   updated_since: str | None, updated_until: str | None,
                   channel: str | None, title: str | None, event: str | None) -> dict:
    filters: dict[str, Any] = {}
    if since:
        filters["created_at_start"] = parse_since(since)
    if until:
        filters["created_at_end"] = parse_since(until)
    if updated_since:
        filters["updated_at_start"] = parse_since(updated_since)
    if updated_until:
        filters["updated_at_end"] = parse_since(updated_until)
    if channel:
        filters["channel_id"] = channel
    if title:
        filters["title"] = title
    if event:
        filters["event_guid"] = event
    return filters


def _build_include(with_transcript: bool, with_ai_notes: bool, with_media: bool) -> dict:
    include: dict[str, Any] = {}
    if with_transcript:
        include["transcript"] = True
    if with_ai_notes:
        include["ai_notes"] = True
    if with_media:
        include["media_url"] = True
    return include


def _warn_media_null(items: list[dict], requested_media: bool) -> None:
    if not requested_media:
        return
    if any(i.get("media_url") is None for i in items):
        click.echo(
            "Warning: media_url was requested but returned null for some recordings. "
            "Your API key is not privileged. Ask a workspace admin to provision a "
            "privileged key to download recording audio/video.",
            err=True,
        )


@click.command(name="list")
@click.option("--since")
@click.option("--until")
@click.option("--updated-since")
@click.option("--updated-until")
@click.option("--channel")
@click.option("--title")
@click.option("--event")
@click.option("--with-transcript", is_flag=True)
@click.option("--with-ai-notes", is_flag=True)
@click.option("--with-media", is_flag=True)
@click.option("--limit", type=int, default=50)
@click.option("--page-size", type=click.IntRange(1, 50), default=20)
@click.option("--json", "format_override", flag_value="json")
def recordings_list(
    since: str | None, until: str | None,
    updated_since: str | None, updated_until: str | None,
    channel: str | None, title: str | None, event: str | None,
    with_transcript: bool, with_ai_notes: bool, with_media: bool,
    limit: int, page_size: int, format_override: str | None,
) -> None:
    """List recordings."""
    client = _client()
    try:
        filters = _build_filters(since, until, updated_since, updated_until, channel, title, event)
        include = _build_include(with_transcript, with_ai_notes, with_media)
        items = list(client.list_recordings(
            filters=filters or None, include=include or None,
            limit=limit, page_size=page_size,
        ))
    except (FellowError, ValueError) as e:
        from fellowai.errors import handle
        handle(e)

    _warn_media_null(items, with_media)
    emit(items, shape="list",
         columns=["id", "title", "started_at"],
         format_override=format_override,
         empty_message="No recordings.")


@click.command(name="get")
@click.argument("recording_id")
@click.option("--no-transcript", is_flag=True)
@click.option("--no-ai-notes", is_flag=True)
@click.option("--no-media", is_flag=True)
@click.option("--json", "format_override", flag_value="json")
@click.option("--md", "format_override", flag_value="md")
def recordings_get(
    recording_id: str,
    no_transcript: bool, no_ai_notes: bool, no_media: bool,
    format_override: str | None,
) -> None:
    """Retrieve a single recording (transcript and AI notes included by default)."""
    client = _client()
    try:
        rec = client.get_recording(recording_id)
    except FellowError as e:
        from fellowai.errors import handle
        handle(e)

    if no_transcript:
        rec["transcript"] = None
    if no_ai_notes:
        rec["ai_notes"] = None
    if no_media:
        rec["media_url"] = None

    emit(rec, shape="document",
         markdown_renderer=render_recording_markdown,
         format_override=format_override or "md")


@click.command(name="export")
@click.option("--since")
@click.option("--until")
@click.option("--updated-since")
@click.option("--updated-until")
@click.option("--channel")
@click.option("--title")
@click.option("--event")
@click.option("--with-transcript", is_flag=True)
@click.option("--with-ai-notes", is_flag=True)
@click.option("--with-media", is_flag=True)
@click.option("--limit", type=int, default=200)
@click.option("--page-size", type=click.IntRange(1, 50), default=50)
@click.option("--format", "fmt", type=click.Choice(["json", "md", "both"]), default="md")
@click.option("--to", "destination", required=True)
def recordings_export(
    since: str | None, until: str | None,
    updated_since: str | None, updated_until: str | None,
    channel: str | None, title: str | None, event: str | None,
    with_transcript: bool, with_ai_notes: bool, with_media: bool,
    limit: int, page_size: int, fmt: str, destination: str,
) -> None:
    """Export recordings to disk or stdout."""
    if destination == "-" and fmt == "both":
        click.echo("Cannot export 'both' formats to stdout — pick json or md.")
        sys.exit(1)

    client = _client()
    try:
        filters = _build_filters(since, until, updated_since, updated_until, channel, title, event)
        include = _build_include(with_transcript, with_ai_notes, with_media)
        items = list(client.list_recordings(
            filters=filters or None, include=include or None,
            limit=limit, page_size=page_size,
        ))
    except (FellowError, ValueError) as e:
        from fellowai.errors import handle
        handle(e)

    _warn_media_null(items, with_media)

    if destination == "-":
        _write_stream(sys.stdout, items, fmt)
    else:
        outdir = Path(destination)
        outdir.mkdir(parents=True, exist_ok=True)
        for rec in items:
            rec_id = rec["id"]
            if fmt in ("json", "both"):
                (outdir / f"{rec_id}.json").write_text(json.dumps(rec, default=str))
            if fmt in ("md", "both"):
                (outdir / f"{rec_id}.md").write_text(render_recording_markdown(rec))


def _write_stream(stream, items: list[dict], fmt: str) -> None:
    if fmt == "json":
        stream.write(json.dumps(items, default=str) + "\n")
        return
    for i, rec in enumerate(items):
        if i:
            stream.write("\n---\n\n")
        stream.write(render_recording_markdown(rec))


def register(group: click.Group) -> None:
    group.add_command(recordings_list)
    group.add_command(recordings_get)
    group.add_command(recordings_export)

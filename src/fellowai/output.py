"""TTY-aware rendering: JSON when piped, table/markdown when interactive."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Iterable, Literal

from rich.console import Console
from rich.table import Table

Shape = Literal["list", "document", "card"]
FormatOverride = Literal["json", "md", None]


def emit(
    data: Any,
    *,
    shape: Shape,
    columns: list[str] | None = None,
    markdown_renderer: Callable[[Any], str] | None = None,
    card_renderer: Callable[[Any], str] | None = None,
    format_override: FormatOverride = None,
    empty_message: str | None = None,
) -> None:
    """Render `data` to stdout based on shape, TTY state, and overrides."""
    is_tty = sys.stdout.isatty()

    if format_override == "json":
        _print_json(data)
        return
    if format_override == "md" and markdown_renderer is not None:
        sys.stdout.write(markdown_renderer(data))
        if not (markdown_renderer(data) or "").endswith("\n"):
            sys.stdout.write("\n")
        return

    if shape == "list":
        items: list = list(data) if not isinstance(data, list) else data
        if not items:
            if is_tty and empty_message:
                sys.stdout.write(empty_message + "\n")
            else:
                _print_json([])
            return
        if is_tty:
            _print_table(items, columns or [])
        else:
            _print_json(items)
        return

    if shape == "document":
        if markdown_renderer is not None:
            sys.stdout.write(markdown_renderer(data))
            if not (markdown_renderer(data) or "").endswith("\n"):
                sys.stdout.write("\n")
        else:
            _print_json(data)
        return

    if shape == "card":
        if is_tty and card_renderer is not None:
            sys.stdout.write(card_renderer(data) + "\n")
        else:
            _print_json(data)
        return

    raise ValueError(f"Unknown shape: {shape}")


def _print_json(data: Any) -> None:
    sys.stdout.write(json.dumps(data, separators=(",", ":"), default=str))
    sys.stdout.write("\n")


def _print_table(items: Iterable[dict], columns: list[str]) -> None:
    console = Console(file=sys.stdout, force_terminal=True)
    table = Table()
    for col in columns:
        table.add_column(col)
    for item in items:
        table.add_row(*[str(item.get(c, "") or "") for c in columns])
    console.print(table)


# ---- Resource-specific markdown / card renderers ----


def render_recording_markdown(rec: dict) -> str:
    lines = [f"# {rec.get('title') or rec['id']}", ""]
    started = rec.get("started_at")
    ended = rec.get("ended_at")
    if started:
        lines.append(f"**Started:** {started}")
    if ended:
        lines.append(f"**Ended:** {ended}")
    lines.append("")

    ai_notes = rec.get("ai_notes")
    if ai_notes:
        for note in ai_notes:
            for section in note.get("sections", []):
                lines.append(f"## {section.get('title', '')}")
                lines.append("")
                content = section.get("content")
                if isinstance(content, str):
                    lines.append(content)
                elif isinstance(content, list):
                    for entry in content:
                        if isinstance(entry, dict) and "text" in entry:
                            lines.append(f"- {entry['text']}")
                        else:
                            lines.append(f"- {entry}")
                lines.append("")

    transcript = rec.get("transcript")
    if transcript:
        lines.append("## Transcript")
        lines.append("")
        for seg in transcript.get("speech_segments", []):
            lines.append(f"[{seg['speaker']}]: {seg['text']}")
        lines.append("")

    return "\n".join(lines)


def render_note_markdown(note: dict) -> str:
    lines = [f"# {note.get('title') or note['id']}", ""]
    if note.get("event_start"):
        lines.append(f"**Event:** {note['event_start']} → {note.get('event_end', '?')}")
    attendees = note.get("event_attendees")
    if attendees:
        lines.append("**Attendees:** " + ", ".join(a.get("email", "?") for a in attendees))
    lines.append("")
    body = note.get("content_markdown")
    if body:
        lines.append(body)
    return "\n".join(lines)


def render_action_item_card(item: dict) -> str:
    lines = [
        f"**{item['text']}**",
        f"  Status: {item.get('status', '?')}",
    ]
    if item.get("due_date"):
        lines.append(f"  Due: {item['due_date']}")
    assignees = item.get("assignees") or []
    if assignees:
        lines.append("  Assignees: " + ", ".join(a.get("full_name", "?") for a in assignees))
    if item.get("ai_detected"):
        lines.append("  (AI-detected)")
    return "\n".join(lines)
